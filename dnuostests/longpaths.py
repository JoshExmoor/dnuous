"""
>>> test()
"""

import os
import shutil
import sys
import tempfile

import dnuos.audiodir
import dnuos.path
from dnuostests.oggtags import _comments, _opus


def test():
    """Verify files with paths beyond the Windows MAX_PATH are listed"""

    tmpdir = tempfile.mkdtemp()
    try:
        # Each level stays under the 255 character name limit; together
        # the file paths are about 300 characters long.
        path = tmpdir
        for part in ['VA - ' + 'Deep South Blues Piano ' * 4, 'Vol. 1 ' * 20]:
            path = os.path.join(path, part.strip())
            dnuos.path.mkdir(path)
        data = _opus(_comments('libopus test', ['ARTIST=Harry Chatmon']))
        names = ['%02d Harry Chatmon - Smoke-Stack Blues.opus' % i
                 for i in range(1, 6)]
        for name in names:
            f = dnuos.path.open(os.path.join(path, name), 'wb')
            try:
                f.write(data)
            finally:
                f.close()
        assert len(os.path.join(path, names[0])) > 260

        assert sorted(dnuos.path.listdir(path)) == names
        adir = dnuos.audiodir.Dir(path)
        assert adir.num_files == len(names), adir.num_files
        assert adir.bad_files == [], adir.bad_files[:1]
    finally:
        if sys.platform == 'win32':
            shutil.rmtree(u'\\\\?\\' + os.path.abspath(tmpdir), True)
        else:
            shutil.rmtree(tmpdir, True)
