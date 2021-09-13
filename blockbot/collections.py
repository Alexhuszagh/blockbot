'''
    collections
    ===========

    High-level, file-backed collections to simplify memoizing data.

    The collections are file-backed, so they are only transiently in
    memory. These use SQLite, a file-based SQL database, for storage.
'''

import atexit
import csv
import collections.abc
import os
import sqlite3
import typing

from . import path

# SQL

def table_exists(table):
    '''Create a format string to check if a table exists.'''
    # NOTE: We don't worry about SQL injection here, since we trust the table names.
    return f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';"


def create_table(table, columns, primary_key):
    '''Convert a list of columns into a string to pass to cursor.execute().'''

    # NOTE: We don't worry about SQL injection here, since we trust the table names.
    column_str = []
    for (name, column_type, nullable) in columns:
        column = f'{name} {column_type}'
        if not nullable:
            column = f'{column} NOT NULL'
        if name == primary_key:
            column = f'{column} PRIMARY KEY'
        column_str.append(column)
    return f'CREATE TABLE IF NOT EXISTS {table} ({", ".join(column_str)});'

def create_index(table, column, unique):
    '''Convert an column name into a string to pass to cursor.'''

    create = 'CREATE'
    if unique:
        create = f'{create} UNIQUE'
    return f'{create} INDEX IF NOT EXISTS {column}_index ON {table} ({column});'

def unsafe_select(table, condition, columns='*'):
    '''Create a query string to find a row.'''

    # WARNING: this can lead to SQL injection: only use it with
    # trusted parameters, that is, supplied by the programmer and
    # not by user-data.
    return f'SELECT {columns} FROM {table} WHERE {condition};'

def unsafe_delete(table, condition):
    '''Create a statement to delete a row.'''

    # WARNING: this can lead to SQL injection: only use it with
    # trusted parameters, that is, supplied by the programmer and
    # not by user-data.
    return f'DELETE FROM {table} WHERE {condition};'

def unsafe_insert(table, values, columns=None):
    '''Create a string to insert a row into the database.'''

    # WARNING: this can lead to SQL injection: only use it with
    # trusted parameters, that is, supplied by the programmer and
    # not by user-data.
    insert = f'INSERT OR REPLACE INTO {table}'
    if columns is not None:
        insert = f'{insert} ({", ".join(columns)})'
    return f'{insert} VALUES({", ".join(values)});'

def unsafe_insert_if_not_exists(table, values, columns=None):
    '''Create a string to insert a row into the database if the key does not exist.'''

    # WARNING: this can lead to SQL injection: only use it with
    # trusted parameters, that is, supplied by the programmer and
    # not by user-data.
    insert = f'INSERT OR IGNORE INTO {table}'
    if columns is not None:
        insert = f'{insert} ({", ".join(columns)})'
    return f'{insert} VALUES({", ".join(values)});'


# CONNECTION

# path: Connection objects for list of open connections.
CONNECTIONS = {}

class Connection:
    '''Reference-counted connection object to a backing database.'''

    def __init__(self, db_dir: str):
        self._path = db_dir
        self._conn = None
        self._cursor = None
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
            self._conn = sqlite3.connect(self._path)
            self._cursor = self._conn.cursor()
        self._open_connections += 1

    def close(self) -> None:
        '''Decrement open connections, and close connection if count reaches 0.'''

        if self._conn is not None:
            # Ensure we commit any changes over-eagerly.
            self._conn.commit()
            self._open_connections -= 1
        if self._conn is not None and self._open_connections == 0:
            self._conn.close()
            self._conn = None
            self._cursor = None

    def execute(self, statement, *parameters):
        '''Execute a given statement, with the additional parameters.'''

        if not self.is_open():
            raise RuntimeError('Cannot execute statement after closing connection.')
        return self._cursor.execute(statement, parameters)

    def begin_transaction(self):
        '''Begin SQLite transaction.'''
        if self._conn.in_transaction:
            self.execute('END TRANSACTION;')
        self.execute('BEGIN TRANSACTION;')

    def commit_transaction(self):
        '''Commit SQLite transaction.'''
        self.execute('COMMIT;')

    def rollback_transaction(self):
        '''Rollback SQLite transaction.'''
        self.execute('ROLLBACK;')

    def create_table(self, table, columns, primary_key, indexes=None):
        '''Try to create a new table in the database if it doesn't exist.'''

        statement = create_table(table, columns, primary_key)
        self.execute(statement)
        if indexes is not None:
            for (column, unique) in indexes:
                statement = create_index(table, column, unique)
                self.execute(statement)

    def drop_table(self, table):
        '''Delete (drop) the given table.'''
        self.execute(f'DROP TABLE {table};')

    def is_open(self) -> bool:
        return self._conn is not None

# COLLECTIONS


class SqliteDict(collections.abc.MutableMapping):
    '''
    Dict-like wrapper for an underlying SQLite table.

    We effectively use a SQLite database like a key/value store,
    just for portability since it's standard in Python without
    any external dependencies. We also add a few other features
    for nicer lookups on indexed values.
    '''

    def __init__(
        self,
        dbpath: str,
        table: str,
        columns: typing.List[typing.Tuple[str, str, bool]],
        primary_key: str,
        indexes: typing.Optional[typing.Tuple[str, bool]] = None,
    ) -> None:
        self._path = dbpath
        self._conn = Connection.new(self._path)
        self._table = table
        self._columns = columns
        self._primary_key = primary_key
        self._indexes = indexes

        # Some internal helpers.
        self._column_names =[i[0] for i in columns]

    # PROPERTIES

    @property
    def table(self):
        '''Get the table name.'''
        return self._table

    @property
    def columns(self):
        '''Get column names.'''
        return self._column_names

    @property
    def primary_key(self):
        '''Get primary key name.'''
        return self._primary_key

    # CONNECTION

    def open(self) -> None:
        '''Open connection to table.'''

        if self._conn is None:
            raise ValueError('Trying to open table on a closed connection.')
        if self._path != ':memory:':
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._conn.open()

        # Try to create the table if it doesn't exist, along with indexes.
        self._conn.create_table(
            self.table,
            self._columns,
            self.primary_key,
            self._indexes,
        )

    def close(self) -> None:
        '''Close connection.'''

        if self._conn is not None:
            self._conn.close()
        self._conn = None

    def is_open(self) -> bool:
        '''Check if connection is open.'''

        if self._conn is None or not self._conn.is_open():
            return False
        # Need to check if the table exists.
        cursor = self._conn.execute(table_exists(self.table))
        return cursor.fetchone() is not None

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

        # Write to file.
        with open(path, mode) as f:
            writer = csv.writer(f, delimiter=delimiter, quotechar=quotechar)
            # Write the columns.
            if self.columns is not None:
                writer.writerow(self.columns)

            statement = f'SELECT * FROM {self.table};'
            for row in self._conn.execute(statement):
                writer.writerow(row)

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

        # Roll into a single transaction. If it fails, we want to revert.
        self._conn.begin_transaction()
        try:
            with open(path, mode) as f:
                reader = csv.reader(f, delimiter=delimiter, quotechar=quotechar)
                iterable = iter(reader)

                columns = next(iterable)
                if columns != self.columns:
                    raise ValueError(f'Unexpected column headings: got {columns}, expected {self.columns}.')

                # Add all values from disk.
                # Use insert which either inserts new entries and overwrites
                # existing ones.
                params = ['?'] * len(self.columns)
                statement = unsafe_insert(self.table, params)
                for row in iterable:
                    if len(row) != len(self.columns):
                        raise ValueError('Invalid number of items for row in CSV file.')
                    self._conn.execute(statement, *row)

            # Commit transaction when finished with all data.
            self._conn.commit_transaction()
        except Exception:
            # Error during parsing, need to rollback and re-raise error.
            self._conn.rollback_transaction()
            raise

    # MAGIC

    def _torow(self, key, value):
        '''Convert a dict value to a row.'''

        copy = {self.primary_key: key, **value}
        return [copy[i] for i in self.columns]

    def _tovalue(self, value, columns=None):
        '''Convert a row to a dict result.'''

        if columns is None:
            columns = self.columns

        result = dict(zip(columns, value))
        result.pop(self.primary_key, None)
        return result

    def keys(self):
        '''Get an iterable yielding all subsequent keys in the dict.'''

        for key, _ in self.items():
            yield key

    def values(self):
        '''Get an iterable yielding all subsequent values in the dict.'''

        for _, value in self.items():
            yield value

    def items(self):
        '''Get an iterable yielding all subsequent items in the dict.'''

        if not self.is_open():
            self.open()

        statement = f'SELECT * FROM {self.table};'
        for row in self._conn.execute(statement):
            value = dict(zip(self.columns, row))
            key = value.pop(self.primary_key)
            yield (key, value)

    def get(self, key, default=None):
        '''Get an item from the SQL database, returning default if it's not present.'''

        try:
            return self[key]
        except KeyError:
            return default

    def setdefault(self, key, default):
        '''Set a value if not present.'''

        if not self.is_open():
            self.open()

        params = ['?'] * len(self.columns)
        statement = unsafe_insert_if_not_exists(self.table, params)
        self._conn.execute(statement, *self._torow(key, default))

    def __getitem__(self, key):
        if not self.is_open():
            self.open()

        condition = f'{self.primary_key} = ?'
        statement = unsafe_select(self.table, condition)
        cursor = self._conn.execute(statement, key)
        value = cursor.fetchone()
        if value is None:
            raise KeyError(f'SqliteDict has no key "{key}".')
        return self._tovalue(value, self.columns)

    def __setitem__(self, key, value):
        if not self.is_open():
            self.open()

        params = ['?'] * len(self.columns)
        statement = unsafe_insert(self.table, params)
        self._conn.execute(statement, *self._torow(key, value))

    def __delitem__(self, key):
        if not self.is_open():
            self.open()

        condition = f'{self.primary_key} = ?'
        statement = unsafe_delete(self.table, condition)
        self._conn.execute(statement, key)

    def __iter__(self):
        return self.keys()

    def __contains__(self, key):
        if not self.is_open():
            self.open()

        condition = f'{self.primary_key} = ?'
        statement = unsafe_select(self.table, condition)
        cursor = self._conn.execute(statement, key)
        return cursor.fetchone() is not None

    def __len__(self):
        if not self.is_open():
            self.open()

        statement = f'SELECT COUNT(*) FROM {self._table};'
        cursor = self._conn.execute(statement)
        return cursor.fetchone()[0]

# MANAGED OBJECTS

def sqlite_dict(
    table: str,
    columns: typing.List[typing.Tuple[str, str, bool]],
    primary_key: str,
    indexes: typing.Optional[typing.Tuple[str, bool]] = None,
    dbpath: str = path.db_path(),
) -> SqliteDict:
    '''
    Generate dict with SQLite backing store.

    # Example

        sqlite_dict(
            table='block_followers_processed_accounts',
            columns=(
                ('user_id', 'TEXT', False),
                ('screen_name', 'TEXT', False),
                ('cursor', 'TEXT', True),
            ),
            # indexes=('screen_name', True),
            primary_key='user_id',
            dbpath=':memory:',
        )
    '''

    inst = SqliteDict(dbpath, table, columns, primary_key, indexes)
    atexit.register(inst.close)
    return inst
