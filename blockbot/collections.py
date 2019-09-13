'''
    collections
    ===========

    High-level, file-backed collections to simplify memoizing data.

    The collections are file-backed, so they are only transiently in
    memory. These use WiredTiger, the high-performance protocol behind
    MongoDB, for storage.
'''

import atexit
import csv
import collections.abc
import os
import typing
import wiredtiger

from . import path

# HELPERS

def filter_columns(columns, key_format, value_format):
    '''Get the serialized CSV columns.'''

    fmt = key_format + value_format
    if columns is None:
        return None
    zipped = zip(fmt, columns)
    return [column for letter, column in zipped if letter != 'x']


def filter_fmt(key_format, value_format):
    '''Get the filtered format variable (missing 'x' values).'''

    fmt = key_format + value_format
    return fmt.replace('x', '')


def pack_csv_value(value, letter):
    '''Pack value to CSV.'''

    if letter == 's' or letter == 'S':
        return value.encode('unicode_escape').decode('utf-8')
    elif letter == 'u':
        raise ValueError('Cannot serialize raw byte array to CSV.')
    elif letter == 'x':
        raise ValueError('Cannot serialize empty value to CSV.')
    else:
        # Integral type.
        return str(value)


def pack_csv(row, fmt):
    '''Pack row to CSV'''

    zipped = zip(row, fmt)
    return [pack_csv_value(value, letter) for value, letter in zipped]


def unpack_csv_value(string, letter):
    '''Unpack value from CSV.'''

    if letter == 's' or letter == 'S':
        return string.encode('utf-8').decode('unicode_escape')
    elif letter == 'u':
        raise ValueError('Cannot load raw byte array from CSV.')
    elif letter == 'x':
        raise ValueError('Cannot load empty value from CSV.')
    else:
        # Integral type.
        return int(string)


def unpack_csv(row, fmt):
    '''Unpack row from CSV.'''

    zipped = zip(row, fmt)
    return [unpack_csv_value(string, letter) for string, letter in zipped]


def new_keygetter(key_format):
    '''Create keygetter from the number of items in the key.'''

    key_count = len(key_format.replace('x', ''))
    if key_count == 0:
        return lambda x: None
    if key_count == 1:
        return lambda x: x[0]
    return lambda x: tuple(x[:key_count])


def new_valuegetter(key_format, value_format):
    '''Create valuegetter from the number of items in the key.'''

    key_count = len(key_format.replace('x', ''))
    value_count = len(value_format.replace('x', ''))
    if value_count == 0:
        return lambda x: None
    if value_count == 1:
        return lambda x: x[key_count]
    return lambda x: tuple(x[key_count:])


def new_rowgetter(actual_columns, expected_columns):
    '''Create a rowgetter that re-orders the row items to be in the expected format.'''

    if len(actual_columns) != len(expected_columns):
        raise ValueError('Invalid columns for CSV file.')

    column_index = {j: i for i, j in enumerate(expected_columns)}
    order = [column_index[i] for i in actual_columns]

    def rowgetter(in_row):
        out_row = [None for _ in range(len(in_row))]
        for in_index, out_index in enumerate(order):
            out_row[out_index] = in_row[in_index]
        return out_row

    return rowgetter


# CONNECTION

# path: Connection objects for list of open connections.
CONNECTIONS = {}

class Connection:
    '''Reference-counted connection object to a backing database.'''

    def __init__(self, db_dir: str):
        self._path = db_dir
        self._conn = None
        self._session = None
        self._open_connections = 0

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    @staticmethod
    def new(path):
        '''Create new connection object.'''
        return CONNECTIONS.setdefault(path, Connection(path))

    def open(self) -> None:
        '''Open connection to database if none exist, and increment open connections.'''

        if self._conn is None:
            self._conn = wiredtiger.wiredtiger_open(self._path, 'create')
            self._session = self._conn.open_session()
        self._open_connections += 1

    def close(self) -> None:
        '''Decrement open connections, and close connection if count reaches 0.'''

        if self._conn is not None:
            self._open_connections -= 1
        if self._conn is not None and self._open_connections == 0:
            self._conn.close()
            self._conn = None
            self._session = None

    def begin_transaction(self):
        return self._session.begin_transaction()

    def commit_transaction(self):
        return self._session.commit_transaction()

    def rollback_transaction(self):
        return self._session.rollback_transaction()

    def open_cursor(self, table):
        return self._session.open_cursor(table)

    def create(self, table, table_format):
        return self._session.create(table, table_format)

    def drop(self, table):
        return self._session.drop(table)

    def is_open(self) -> bool:
        return self._conn is not None

# COLLECTIONS


class WiredTigerBase:
    '''Base class for a wired-tiger wrapper.'''

    def __init__(
        self,
        db_dir: str,
        name: str,
        key_format: str,
        value_format: str,
        columns: typing.Optional[typing.Tuple[str]]
    ) -> None:
        self._path = os.path.realpath(db_dir)
        self._conn = Connection.new(self._path)
        self._curr = None
        self._name = name
        self._table = f'table:{self._name}'
        self._key_format = key_format
        self._value_format = value_format
        self._columns = columns
        self._format = f'key_format={key_format},value_format={value_format}'
        if columns is not None:
            self._format += f',columns=({",".join(columns)})'

    # CONNECTION

    def open(self) -> None:
        '''Open connection to table.'''

        os.makedirs(self._path, exist_ok=True)
        self._conn.open()

        # Try to open a cursor to the table, otherwise, create the table
        # and open the cursor.
        try:
            self._curr = self._conn.open_cursor(self._table)
        except wiredtiger.WiredTigerError as exc:
            if exc.args == ('No such file or directory',):
                # Table does not exist.
                code = self._conn.create(self._table, self._format)
                if code != 0:
                    raise wiredtiger.WiredTigerError(f'Unable to create table, error code {code}.')
                self._curr = self._conn.open_cursor(self._table)
            else:
                # Unknown error, re-raise.
                raise

    def close(self) -> None:
        '''Close connection.'''

        if self._conn is not None:
            self._conn.close()
        self._conn = None
        self._curr = None

    def is_open(self) -> bool:
        '''Check if connection is open.'''
        return self._curr is not None

    # SERIALIZATION

    def to_csv(
        self,
        path: str,
        mode: str = 'w',
        delimiter: str = ',',
        quotechar: str = '"',
    ) -> None:
        '''Serialize backing store to CSV.'''

        # Ensure we have an open connection before we do anything.
        if not self.is_open():
            self.open()

        # Get the column headers and the packing format.
        columns = filter_columns(self._columns, self._key_format, self._value_format)
        fmt = filter_fmt(self._key_format, self._value_format)

        # Write to file.
        with open(path, mode) as f:
            writer = csv.writer(f, delimiter=delimiter, quotechar=quotechar)
            # Write the columns.
            if columns is not None:
                writer.writerow(columns)

            # Write the values.
            # Iteration returns a flat map of values.
            # Reset the cursor so we always iterate over the full map.
            self._curr.reset()
            for item in self._curr.__iter__():
                writer.writerow(pack_csv(item, fmt))

    def load_csv(
        self,
        path: str,
        mode: str = 'r',
        delimiter: str = ',',
        quotechar: str = '"',
    ) -> None:
        '''Deserialize backing store from CSV.'''

        # Ensure we have an open connection before we do anything.
        if not self.is_open():
            self.open()

        # Get the column headers and the packing format.
        columns = filter_columns(self._columns, self._key_format, self._value_format)
        fmt = filter_fmt(self._key_format, self._value_format)
        keygetter = new_keygetter(self._key_format)
        valuegetter = new_valuegetter(self._key_format, self._value_format)

        # Roll into a single transaction. If it fails, we want to revert.
        self._conn.begin_transaction()
        try:
            with open(path, mode) as f:
                reader = csv.reader(f, delimiter=delimiter, quotechar=quotechar)
                iterable = iter(reader)

                # Need to determine how to parser the data if the columns
                # are not None.
                rowgetter = lambda x: x
                if self._columns is not None:
                    # Likely going to need to re-arrange items...
                    rowgetter = new_rowgetter(next(iterable), columns)

                # Add all values from disk.
                # Use insert which either inserts new entries and overwrites
                # existing ones.
                for row in iterable:
                    if len(row) != len(fmt):
                        raise ValueError('Invalid number of items for row in CSV file.')
                    # Going to need to re-arrange the row to match the format...
                    item = unpack_csv(rowgetter(row), fmt)
                    self._curr.set_key(keygetter(item))
                    self._curr.set_value(valuegetter(item))
                    self._curr.insert()

            # Commit transaction when finished with all data.
            self._conn.commit_transaction()
        except Exception:
            # Error during parsing, need to rollback and re-raise error.
            self._conn.rollback_transaction()
            raise


class WiredTigerDict(WiredTigerBase, collections.abc.MutableMapping):
    '''File-backed store resembling a Python dict. Lazily opened.'''

    def __init__(
        self,
        name: str,
        key_format='S',
        value_format='S',
        columns=None,
    ) -> None:
        super().__init__(path.db_dir(), name, key_format, value_format, columns)

    def __getitem__(self, key):
        if not self.is_open():
            self.open()
        return self._curr.__getitem__(key)

    def __setitem__(self, key, value):
        if not self.is_open():
            self.open()
        self._curr.__setitem__(key, value)

    def __delitem__(self, key):
        if not self.is_open():
            self.open()
        self._curr.__delitem__(key)

    def __iter__(self):
        if not self.is_open():
            self.open()

        # Need to consider unpacking keys and values.
        keygetter = new_keygetter(self._key_format)
        valuegetter = new_valuegetter(self._key_format, self._value_format)

        # Reset the cursor so we always iterate over the full map.
        self._curr.reset()
        for item in self._curr.__iter__():
            yield (keygetter(item), valuegetter(item))

    def __len__(self):
        raise NotImplementedError


class WiredTigerSet(WiredTigerBase, collections.abc.MutableSet):
    '''File-backed store resembling a Python set. Lazily opened.'''

    def __init__(
        self,
        name: str,
        key_format='S',
        columns=None,
    ) -> None:
        if columns is not None:
            # Need to add our own, internal column here...
            columns = (*columns, 'none')
        super().__init__(path.db_dir(), name, key_format, 'x', columns)

    def __contains__(self, key):
        if not self.is_open():
            self.open()
        self._curr.set_key(key)
        return self._curr.search() == 0

    def add(self, key):
        if not self.is_open():
            self.open()
        self._curr.set_key(key)
        self._curr.set_value()
        self._curr.insert()

    def discard(self, key):
        if not self.is_open():
            self.open()
        self._curr.set_key(key)
        if self._curr.remove() != 0:
            raise KeyError

    def __iter__(self):
        if not self.is_open():
            self.open()

        # If we have a single key, unpack it, otherwise, return a tuple.
        keygetter = new_keygetter(self._key_format)

        # Reset the cursor so we always iterate over the full map.
        self._curr.reset()
        for item in self._curr.__iter__():
            yield keygetter(item)

    def __len__(self):
        raise NotImplementedError

# MANAGED OBJECTS


def wired_tiger_dict(
    name: str,
    key_format: str = 'S',
    value_format: str = 'S',
    columns=None,
) -> WiredTigerDict:
    '''Generate dict with wiredtiger backing store.'''

    inst = WiredTigerDict(name, key_format, value_format, columns)
    atexit.register(inst.close)
    return inst


def wired_tiger_set(
    name: str,
    key_format: str = 'S',
    columns=None,
) -> WiredTigerSet:
    '''Generate set with wiredtiger backing store.'''

    inst = WiredTigerSet(name, key_format, columns)
    atexit.register(inst.close)
    return inst
