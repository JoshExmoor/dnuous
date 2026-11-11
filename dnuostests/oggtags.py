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
            pages.append(b'OggS' + struct.pack('<BBqIII', 0, flags, granule,
                                               serial, seq, 0) +
                         bytes([len(lacing)]) + bytes(lacing) + body)
            seq += 1
            first = False
    return b''.join(pages)


def _comments(vendor, comments):
    data = struct.pack('<I', len(vendor)) + vendor
    data += struct.pack('<I', len(comments))
    for c in comments:
        data += struct.pack('<I', len(c)) + c
    return data


# A ~100 KB cover picture (base64 text in real files) forces the comment
# packet across at least two pages, as in the files that failed.
PICTURE = b'METADATA_BLOCK_PICTURE=' + b'A' * 100000
TAGS = [b'ENCODER=test', PICTURE, b'ARTIST=Big Boy Knox',
        b'ALBUM=San Antonio Blues 1937', b'DATE=1937']


def _opus(tags):
    head = b'OpusHead' + struct.pack('<BBHIhB', 1, 2, 312, 44100, 0, 0)
    return _pages([head, b'OpusTags' + tags, b'\xfc' * 300])


def _vorbis(tags):
    ident = b'\x01vorbis' + struct.pack('<IBI3iB', 0, 2, 44100, 0, 128000,
                                        0, 0xb8) + b'\x01'
    return _pages([ident, b'\x03vorbis' + tags + b'\x01', b'\x00' * 300],
                  last_granule=44100 * 10)


def test():
    """Verify Ogg comment headers spanning several pages are parsed"""

    tmpdir = tempfile.mkdtemp()
    try:
        files = {}
        for name, data in [
                ('big.opus', _opus(_comments(b'libopus test', TAGS))),
                ('big.ogg', _vorbis(_comments(b'Xiph test', TAGS)))]:
            files[name] = os.path.join(tmpdir, name)
            with open(files[name], 'wb') as f:
                f.write(data)
            # More pages than the 3 packets: the tags really span pages
            assert data.count(b'OggS') > 3, name

        stream = dnuos.audiotype.openstream(files['big.opus'])
        stream.close()
        assert stream.vendor == 'libopus test', stream.vendor
        assert stream.artist() == {'vorbis': 'Big Boy Knox'}
        assert stream.album() == {'vorbis': 'San Antonio Blues 1937'}
        assert stream.year() == {'vorbis': '1937'}
        assert abs(stream.time - (480000 - 312) / 48000.0) < 1e-9

        stream = dnuos.audiotype.openstream(files['big.ogg'])
        stream.close()
        assert stream.vendor == 'Xiph test', stream.vendor
        assert stream.artist() == {'vorbis': 'Big Boy Knox'}
        assert stream.year() == {'vorbis': '1937'}

        # A corrupt comment length must fail without asking for a huge read
        # (the old code tried to read ~1.5 GB per file, which was slow).
        corrupt = os.path.join(tmpdir, 'corrupt.opus')
        tags = bytearray(_comments(b'libopus test', TAGS))
        struct.pack_into('<I', tags, 4 + 12 + 4, 0x5a3b2c42)
        with open(corrupt, 'wb') as f:
            f.write(_opus(bytes(tags)))
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
                dnuos.audiotype.openstream(corrupt)
            except ValueError:
                pass
            else:
                raise AssertionError('corrupt comment header accepted')
        finally:
            dnuos.audiotype.dnuos.path.open = real_open
        assert biggest[0] <= dnuos.path.getsize(corrupt), biggest[0]
    finally:
        shutil.rmtree(tmpdir, True)
