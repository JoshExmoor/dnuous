"""UTF-8 drop-in replacements for various os.path functions.

Dnuos has always assumed UTF-8 as the file system encoding, but this isn't
always the case, especially on Windows. These functions take UTF-8 strings,
decode them to unicode objects, and pass them to the underlying os.path
functions. Any functions that return paths with unicode objects are
encoded back into UTF-8 strings.

This has the effect that UTF-8 can be used even if the file system uses
a different encoding, due to decoding to unicode beforehand.
"""

import os
import sys

# Paths this long get the Windows extended-length prefix. MAX_PATH is 260
# including the terminating NUL, and directories are limited to 248 so that
# an 8.3 file name still fits.
_LONG_PATH = 248


def _extended(path):
    """Return path in a form Windows accepts beyond MAX_PATH.

    Python 2 is not long-path aware, so the Windows calls it makes fail for
    paths of 260 characters or more: isfile() then quietly returns False and
    such files were left out of the listing without any error. The \\\\?\\
    prefix lifts the limit. It also turns off path normalisation, so the
    path is made absolute first. Only unicode paths can use it (str paths go
    through the ANSI APIs, which are always limited).
    """

    if (sys.platform != 'win32' or not isinstance(path, unicode) or
            len(path) < _LONG_PATH or path.startswith(u'\\\\?\\')):
        return path
    path = os.path.abspath(path)
    if path.startswith(u'\\\\'):
        return u'\\\\?\\UNC\\' + path[2:]
    return u'\\\\?\\' + path


def listdir(path):

    try:
        path = path.decode('utf-8')
    except UnicodeError:
        # Try to emulate the behavior of os.listdir(u'...') if the path isn't
        # valid for the FS encoding. There's nothing we can do on Windows as
        # os.listdir uses non-wchar APIs for strs.
        if sys.platform == 'win32':
            raise

        fsenc = sys.getfilesystemencoding().lower()
        paths = []
        for p in os.listdir(path):
            try:
                paths.append(p.decode(fsenc).encode('utf-8'))
            except UnicodeError:
                paths.append(p)
        return paths

    paths = []
    # listdir returns bare names, so the prefix never reaches the output
    for p in os.listdir(_extended(path)):
        # Don't encode paths that aren't Unicode. os.listdir will return str
        # objects for any paths it couldn't decode to unicode objects (see
        # http://bugs.python.org/issue683592).
        if isinstance(p, unicode):
            paths.append(p.encode('utf-8'))
        else:
            paths.append(p)
    return paths


def _wrap(func, access=True):
    """Wrap func to take UTF-8 paths.

    access: func reads or changes the file system, so long paths get the
    extended-length prefix. Functions that return a path must not get it.
    """

    convert = access and _extended or (lambda p: p)

    def wrapper(path, *args, **kw):
        try:
            return func(convert(path.decode('utf-8')), *args, **kw)
        except UnicodeError:
            return func(path, *args, **kw)
    return wrapper


exists = _wrap(os.path.exists)
expanduser = _wrap(os.path.expanduser, access=False)
getmtime = _wrap(os.path.getmtime)
getsize = _wrap(os.path.getsize)
isdir = _wrap(os.path.isdir)
isfile = _wrap(os.path.isfile)
mkdir = _wrap(os.mkdir)
# os.makedirs splits the path and recurses, which the prefix would confuse
makedirs = _wrap(os.makedirs, access=False)
normpath = _wrap(os.path.normpath, access=False)
rename = _wrap(os.rename)
remove = _wrap(os.remove)
rmdir = _wrap(os.rmdir)
open = _wrap(open)
