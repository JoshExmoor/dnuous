"""
>>> test()
"""

import os
import shutil
import sys
import tempfile
from io import StringIO

import dnuos
import dnuos.audiodir


def _run(lib, cache_dir, scans):
    old = sys.stderr, sys.stdout
    sys.stderr = sys.stdout = StringIO()
    del scans[:]
    try:
        dnuos.main(['dnuos', '-q', '--cache-dir=' + cache_dir, lib],
                   locale='C')
    finally:
        sys.stderr, sys.stdout = old
    return sorted(os.path.relpath(p, lib) for p in scans)


def test():
    """Verify a rescanned stale directory is written back to the cache"""

    tmpdir = tempfile.mkdtemp()
    lib = os.path.join(tmpdir, 'lib')
    shutil.copytree(os.path.join(os.environ['DATA_DIR'], 'lame'), lib)
    cache_dir = os.path.join(tmpdir, 'cache')
    os.mkdir(cache_dir)

    scans = []
    real_load = dnuos.audiodir.Dir.load

    def counting_load(self):
        scans.append(self.path)
        return real_load(self)

    dnuos.audiodir.Dir.load = counting_load
    try:
        assert len(_run(lib, cache_dir, scans)) > 1
        assert _run(lib, cache_dir, scans) == []

        # Change one directory so its cache entry becomes stale
        target = os.path.join(lib, '3961-aps')
        with open(os.path.join(target, 'cover.txt'), 'w') as f:
            f.write('x')
        st = os.stat(target)
        os.utime(target, (st.st_atime, st.st_mtime + 10))

        assert _run(lib, cache_dir, scans) == ['3961-aps']
        # It used to be rescanned on every run from here on
        assert _run(lib, cache_dir, scans) == []
    finally:
        dnuos.audiodir.Dir.load = real_load
        shutil.rmtree(tmpdir, True)
