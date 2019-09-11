'''
    collections
    ===========

    High-level, file-backed collections to simplify memoizing data.

    The collections are file-backed, so they are only transiently in
    memory. These use WiredTiger, the high-performance protocol behind
    MongoDB, for storage.
'''

import atexit
import collections.abc
import os
import wiredtiger

from . import path

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

    def open_cursor(self, table):
        return self._session.open_cursor(table)

    def create(self, table, table_format):
        return self._session.create(table, table_format)

    def drop(self, table):
        return self._session.drop(table)

    def is_open(self) -> bool:
        return self._conn is not None


class WiredTigerBase:
    '''Base class for a wired-tiger wrapper.'''

    def __init__(
        self,
        db_dir: str,
        name: str,
        key_format: str,
        value_format: str
    ) -> None:
        self._path = os.path.realpath(db_dir)
        self._conn = Connection.new(self._path)
        self._curr = None
        self._name = name
        self._table = f'table:{self._name}'
        self._format = f'key_format={key_format},value_format={value_format}'

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


class WiredTigerDict(WiredTigerBase, collections.abc.MutableMapping):
    '''File-backed store resembling a Python dict. Lazily opened.'''

    def __init__(self, name: str, key_format='S', value_format='S') -> None:
        super().__init__(path.db_dir(), name, key_format, value_format)

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
        return self._curr.__iter__()

    def __len__(self):
        raise NotImplementedError


class WiredTigerSet(WiredTigerBase, collections.abc.MutableSet):
    '''File-backed store resembling a Python set. Lazily opened.'''

    def __init__(self, name: str, key_format='S') -> None:
        super().__init__(path.db_dir(), name, key_format, 'x')

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
        for (key,) in self._curr.__iter__():
            yield key

    def __len__(self):
        raise NotImplementedError


def wired_tiger_dict(
    name: str,
    key_format: str = 'S',
    value_format: str = 'S'
) -> WiredTigerDict:
    '''Generate dict with wiredtiger backing store.'''

    inst = WiredTigerDict(name, key_format, value_format)
    atexit.register(inst.close)
    return inst


def wired_tiger_set(name: str, key_format: str = 'S') -> WiredTigerSet:
    '''Generate set with wiredtiger backing store.'''

    inst = WiredTigerSet(name, key_format)
    atexit.register(inst.close)
    return inst
