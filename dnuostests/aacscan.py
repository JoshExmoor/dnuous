"""
>>> test()
"""

import glob
import os

import dnuos.audiotype
import dnuos.path


def test():
    """Verify AAC parsing reads only the metadata, not the whole file"""

    pattern = os.path.join(os.environ['DATA_DIR'], 'aac', '*', '*.m4a')
    files = sorted(glob.glob(pattern))
    assert files

    for name in files:
        stream = dnuos.audiotype.openstream(name)
        try:
            moov = stream._read_moov()
        finally:
            stream.close()
        assert moov is not None and moov[4:8] == b'moov', name

        # Reading through a counting file proves the parser doesn't scan
        # the audio data (it used to read 100% of every file).
        read = [0]
        real_open = dnuos.path.open

        def counting_open(path, mode='r', *args, **kwargs):
            handle = real_open(path, mode, *args, **kwargs)

            class Counter(object):
                def __getattr__(self, attr):
                    return getattr(handle, attr)

                def read(self, n=-1):
                    data = handle.read(n)
                    read[0] += len(data)
                    return data

            return Counter()

        dnuos.audiotype.dnuos.path.open = counting_open
        try:
            stream = dnuos.audiotype.openstream(name)
            stream.close()
        finally:
            dnuos.audiotype.dnuos.path.open = real_open
        size = dnuos.path.getsize(name)
        assert read[0] < size // 10, (name, read[0], size)
