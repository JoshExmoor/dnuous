"""
>>> test()
"""

import os
import shutil
import struct
import tempfile

import dnuos.audiotype


def _flac(freq, samples, audio=4000):
    """A minimal FLAC file: just a STREAMINFO block and some 'audio'"""

    info = (freq << 44) | (1 << 41) | (15 << 36) | samples  # 2 ch, 16 bit
    return (b'fLaC' + struct.pack('>I', 0x80000000 | 34) +
            struct.pack('>3HI3Q', 4096, 4096, 0, 0, info, 0, 0) +
            b'\x00' * audio)


def test():
    """Verify FLAC files shorter than a second (or of unknown length) parse"""

    tmpdir = tempfile.mkdtemp()
    try:
        cases = [('normal', 44100, 44100 * 10),
                 ('short', 44100, 22050),
                 ('unknown', 44100, 0),
                 ('norate', 0, 44100)]
        streams = {}
        for name, freq, samples in cases:
            path = os.path.join(tmpdir, name + '.flac')
            with open(path, 'wb') as f:
                f.write(_flac(freq, samples))
            stream = dnuos.audiotype.openstream(path)
            stream.close()
            streams[name] = stream

        size = streams['normal'].streamsize()
        assert streams['normal'].time == 10
        assert streams['normal'].bitrate() == size * 8 // 10
        # Half a second: whole-second length is 0, but the bitrate is real
        size = streams['short'].streamsize()
        assert streams['short'].time == 0
        assert streams['short'].bitrate() == size * 8 * 2, \
            streams['short'].bitrate()
        assert streams['unknown'].time == 0
        assert streams['unknown'].bitrate() == 0
        assert streams['norate'].time == 0
    finally:
        shutil.rmtree(tmpdir, True)
