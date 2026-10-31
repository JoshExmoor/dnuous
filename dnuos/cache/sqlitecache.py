"""sqlite3-based cache"""

import os
import pickle
import sqlite3
from collections.abc import MutableMapping

import dnuos.path


def _key(path):
    """Encode a path for storage.

    Paths are stored as file system encoded bytes so that undecodable file
    names (surrogate-escaped str on POSIX) survive the round trip.
    """

    return os.fsencode(path)


class Cache(MutableMapping):
    """A dict with persistence, backed by sqlite3"""

    def __init__(self, filename, version):

        filename = '.'.join([filename, version, 'sqlite'])

        self._conn = sqlite3.connect(filename)
        c = self._conn.cursor()
        try:
            c.execute('create table if not exists dirs '
                      '(path text unique, dir blob)')
            self._conn.commit()
        finally:
            c.close()

        self.version = version

    def __getitem__(self, key):

        c = self._conn.cursor()
        try:
            c.execute('select dir from dirs where path = ? limit 1',
                      (_key(key),))
            row = c.fetchone()
            if not row:
                raise KeyError(key)
            else:
                return pickle.loads(row[0])
        finally:
            c.close()

    def __setitem__(self, key, value):

        c = self._conn.cursor()
        try:
            c.execute('replace into dirs values (?, ?)',
                      (_key(key),
                       pickle.dumps(value, pickle.HIGHEST_PROTOCOL)))
            self._conn.commit()
        finally:
            c.close()

    def __delitem__(self, key):

        c = self._conn.cursor()
        try:
            c.execute('delete from dirs where path = ?', (_key(key),))
            self._conn.commit()
            if c.rowcount == 0:
                raise KeyError(key)
        finally:
            c.close()

    def keys(self):

        c = self._conn.cursor()
        try:
            c.execute('select path from dirs')
            return [os.fsdecode(row[0]) for row in c.fetchall()]
        finally:
            c.close()

    def __iter__(self):

        return iter(self.keys())

    def __len__(self):

        c = self._conn.cursor()
        try:
            c.execute('select count(*) from dirs')
            return c.fetchone()[0]
        finally:
            c.close()

    def cull(self):
        """Removes bad directories and returns count"""

        paths = [path for path in self.keys()
                 if not dnuos.path.isdir(path)]

        for path in paths:
            del self[path]

        c = self._conn.cursor()
        try:
            c.execute('vacuum')
        finally:
            c.close()

        return len(paths)

    def save(self):
        """Serializes data to file"""

        self._conn.close()
