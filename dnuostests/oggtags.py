"""
>>> test()
"""

import os
import shutil
import struct
import tempfile

import dnuos.audiotype
import dnuos.path


def _pages(packets, serial=1234, last_granule=48000 * 10):
    """Lay packets out as Ogg pages (CRCs aren't checked by dnuos).

    Each packet is split into 255-byte lacing segments, and a page holds at
    most 255 segments, so a large packet spans several pages.
    """

    pages, seq = [], 0
    for index, packet in enumerate(packets):
        sizes = [255] * (len(packet) // 255) + [len(packet) % 255]
        pos, first = 0, True
        while sizes:
            lacing, sizes = sizes[:255], sizes[255:]
            body = packet[pos:pos + sum(lacing)]
            pos += sum(lacing)
            flags = (0 if first else 1) | (2 if seq == 0 else 0)
            last = index == len(packets) - 1 and not sizes
            granule = last_granule if last else (0 if index < 2 else -1)
            flags |= 4 if last else 0
            pages.append('OggS' + struct.pack('<BBqIII', 0, flags, granule,
                                              serial, seq, 0) +
                         chr(len(lacing)) + ''.join(map(chr, lacing)) + body)
            seq += 1
            first = False
    return ''.join(pages)


def _comments(vendor, comments):
    data = struct.pack('<I', len(vendor)) + vendor
    data += struct.pack('<I', len(comments))
    for c in comments:
        data += struct.pack('<I', len(c)) + c
    return data


# A ~100 KB cover picture (base64 text in real files) forces the comment
# packet across several pages, as in the files that failed.
PICTURE = 'METADATA_BLOCK_PICTURE=' + 'A' * 100000
TAGS = ['ENCODER=test', PICTURE, 'ARTIST=Big Boy Knox',
        'ALBUM=San Antonio Blues 1937', 'DATE=1937']


def _opus(tags):
    head = 'OpusHead' + struct.pack('<BBHIhB', 1, 2, 312, 44100, 0, 0)
    return _pages([head, 'OpusTags' + tags, '\xfc' * 300])


def _vorbis(tags):
    ident = '\x01vorbis' + struct.pack('<IBI3iB', 0, 2, 44100, 0, 128000,
                                       0, 0xb8) + '\x01'
    return _pages([ident, '\x03vorbis' + tags + '\x01', '\x00' * 300],
                  last_granule=44100 * 10)


def test():
    """Verify Ogg comment headers spanning several pages are parsed"""

    tmpdir = tempfile.mkdtemp()
    try:
        files = {}
        for name, data in [
                ('big.opus', _opus(_comments('libopus test', TAGS))),
                ('big.ogg', _vorbis(_comments('Xiph test', TAGS)))]:
            files[name] = os.path.join(tmpdir, name)
            f = open(files[name], 'wb')
            try:
                f.write(data)
            finally:
                f.close()
            # More pages than the 3 packets: the tags really span pages
            assert data.count('OggS') > 3, name

        stream = dnuos.audiotype.openstream(files['big.opus'])
        stream._f.close()
        assert stream.vendor == 'libopus test', stream.vendor
        assert stream.artist() == {'vorbis': 'Big Boy Knox'}
        assert stream.album() == {'vorbis': 'San Antonio Blues 1937'}
        assert stream.year() == {'vorbis': '1937'}
        assert abs(stream.time - (480000 - 312) / 48000.0) < 1e-9

        stream = dnuos.audiotype.openstream(files['big.ogg'])
        stream._f.close()
        assert stream.vendor == 'Xiph test', stream.vendor
        assert stream.artist() == {'vorbis': 'Big Boy Knox'}
        assert stream.year() == {'vorbis': '1937'}

        # A corrupt comment length must fail without asking for a huge read
        corrupt = os.path.join(tmpdir, 'corrupt.opus')
        tags = _comments('libopus test', TAGS)
        pos = 4 + 12 + 4
        tags = tags[:pos] + struct.pack('<I', 0x5a3b2c42) + tags[pos + 4:]
        f = open(corrupt, 'wb')
        try:
            f.write(_opus(tags))
        finally:
            f.close()
        biggest = [0]
        real_open = dnuos.path.open

        def counting_open(path, mode='r', *args, **kwargs):
            handle = real_open(path, mode, *args, **kwargs)

            class Counter(object):
                def __getattr__(self, attr):
                    return getattr(handle, attr)

                def read(self, n=-1):
                    biggest[0] = max(biggest[0], n)
                    return handle.read(n)

            return Counter()

        dnuos.audiotype.dnuos.path.open = counting_open
        try:
            try:
                stream = dnuos.audiotype.openstream(corrupt)
            except ValueError:
                pass
            else:
                raise AssertionError('corrupt comment header accepted')
        finally:
            dnuos.audiotype.dnuos.path.open = real_open
        assert biggest[0] <= dnuos.path.getsize(corrupt), biggest[0]
    finally:
        shutil.rmtree(tmpdir, True)
