"""Thin aliases for the os/os.path functions Dnuos uses.

Under Python 2, Dnuos represented every path as a UTF-8 encoded byte string
and these functions decoded/encoded around the real os calls. Python 3 uses
str paths natively (with surrogateescape for undecodable names on POSIX), so
these are now plain aliases kept for API compatibility within the package.
"""

import builtins
import os

listdir = os.listdir
exists = os.path.exists
expanduser = os.path.expanduser


def getmtime(path):
    """Integer mtime (Python 2 Dnuos used os.stat_float_times(False))"""

    return int(os.path.getmtime(path))


getsize = os.path.getsize
isdir = os.path.isdir
isfile = os.path.isfile
mkdir = os.mkdir
makedirs = os.makedirs
normpath = os.path.normpath
rename = os.rename
remove = os.remove
rmdir = os.rmdir
open = builtins.open
