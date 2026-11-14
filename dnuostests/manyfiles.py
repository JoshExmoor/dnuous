"""
>>> test()
"""

import os
import shutil
import tempfile

import dnuos.audiodir
import dnuos.audiotype
from dnuostests.oggtags import _comments, _opus

# More than the 512 C stdio files Python 2 may have open at once on Windows.
COUNT = 600


def test():
    """Verify a directory with more files than the open-file limit parses"""

    tmpdir = tempfile.mkdtemp()
    try:
        data = _opus(_comments('libopus test', ['ARTIST=Big Boy Knox']))
        for i in xrange(COUNT):
            f = open(os.path.join(tmpdir, '%04d.opus' % i), 'wb')
            try:
                f.write(data)
            finally:
                f.close()

        # openstream must not leave the file open
        stream = dnuos.audiotype.openstream(os.path.join(tmpdir, '0000.opus'))
        assert stream._f.closed

        adir = dnuos.audiodir.Dir(tmpdir)
        assert adir.num_files == COUNT, adir.num_files
        assert adir.bad_files == [], adir.bad_files[:1]
        assert abs(adir.length - COUNT * (480000 - 312) / 48000.0) < 1e-6
    finally:
        shutil.rmtree(tmpdir, True)
