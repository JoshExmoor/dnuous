import locale
import time
import unicodedata

from dnuos.misc import to_human, _

class AbstractRenderer(object):

    def setup_columns(self, fields, options):

        self.columns = [parse_field(f, options) for f in fields]


class Column(object):

    def __init__(self, tag, width, suffix, options):

        attr_table = {
            "a": (_('Bitrate(s)'), lambda adir, **kw: adir.audiolist_format),
            "A": (_('Artist'), self._get_artist),
            "b": (_('Bitrate'), lambda adir, **kw: adir.bitrate),
            "B": (_('Bitrate'), lambda adir, **kw: adir.bitrate),
            "C": (_('Album'), self._get_album),
            "D": (_('Depth'), lambda adir, **kw: kw['depth']),
            "f": (_('Files'), lambda adir, **kw: adir.num_files),
            "l": (_('Length'), lambda adir, **kw: adir.length),
            "L": (_('Length'), lambda adir, **kw: adir.length),
            "m": (_('Modified'), lambda adir, **kw: adir.modified),
            "M": (_('Modified'), lambda adir, **kw: adir.modified),
            "n": (_('Album/Artist'), lambda adir, **kw: adir.name),
            "N": (_('Album/Artist'), lambda adir, **kw: adir.name),
            "p": (_('Profile'), self._get_profile),
            "P": (_('Path'), lambda adir, **kw: adir.path),
            "q": (_('Quality'), lambda adir, **kw: adir.quality),
            "s": (_('Size'), lambda adir, **kw: adir.size),
            "S": (_('Size'), lambda adir, **kw: adir.size),
            "t": (_('Type'), lambda adir, **kw: adir.mediatype),
            "T": (_('BR Type'), lambda adir, **kw: adir.brtype),
            "V": (_('Encoder'), lambda adir, **kw: adir.vendor),
            "Y": (_('Year'), self._get_year),
        }

        formatter_table = {
            "b": lambda data, depth: to_human(int(data), 1000.0),
            "B": lambda data, depth: locale.format_string('%d', data),
            "l": lambda data, depth: to_minutes(int(data)),
            "L": lambda data, depth: locale.format_string('%d', data),
            "m": lambda data, depth: time.ctime(data),
            "n": lambda data, depth: self.indent(data, depth),
            "s": lambda data, depth: to_human(data),
        }
        self.width, self.suffix = width, suffix
        if tag in formatter_table:
            self.formatter = formatter_table[tag]
        else:
            self.formatter = lambda x, y: x
        self.name, self.get = attr_table[tag]

        self._prefer_tag = options.prefer_tag

    def _textencode(self, str_):
        """Normalize an ID3 tag value: decode stray bytes, cut at NUL"""

        if isinstance(str_, bytes):
            str_ = str_.decode('latin-1')
        return str_.split('\0', 1)[0]

    def _get_tag_keys(self, data):
        if len(data) == 1:
            keys = list(data.keys())
            encoder = lambda x: x
        elif set(data.keys()) == set(['id3v1', 'id3v2']):
            if self._prefer_tag == 1:
                keys = ['id3v1', 'id3v2']
            elif self._prefer_tag == 2:
                keys = ['id3v2', 'id3v1']
            encoder = self._textencode
        else:
            keys = []
            encoder = lambda x: x
        return keys, encoder

    def _get_tag_value(self, data, keys):
        for key in keys:
            values = data[key]
            if len(values) != 1:
                return None
            elif values != set([None]):
                return tuple(values)[0]
            else:
                pass
        return None

    def _get_artist(self, adir, **kw):
        data = adir.artists
        if data is not None:
            keys, encoder = self._get_tag_keys(data)
            value = self._get_tag_value(data, keys)
            if value is not None:
                return encoder(value)
        return None

    def _get_album(self, adir, **kw):
        data = adir.albums
        if data is not None:
            keys, encoder = self._get_tag_keys(data)
            value = self._get_tag_value(data, keys)
            if value is not None:
                return encoder(value)
        return None

    def _get_year(self, adir, **kw):
        data = adir.years
        if data is not None:
            keys, encoder = self._get_tag_keys(data)
            value = self._get_tag_value(data, keys)
            if value is not None:
                return encoder(value)
        return None

    def _get_profile(self, adir, **kw):
        return adir.profile

    def _format(self, data, suffixes):

        if suffixes:
            if data:
                data += self.suffix
            else:
                data = ' ' * len(self.suffix)
        if self.width != None:
            data = fit_width(unicodedata.normalize('NFC', data), self.width)
        return data

    def header(self, suffixes=True):

        return self._format(self.name, suffixes)

    def get_formatted(self, adir, root, suffixes=True):

        depth = adir.depth_from(root)
        data = self.get(adir, depth=depth)
        if data is None:
            data = ''
        else:
            data = str(self.formatter(data, depth))
        return self._format(data, suffixes)


def char_width(char):
    """Number of terminal/monospace columns a character occupies.

    >>> [char_width(c) for c in 'a\\u00e9\\u5742\\uff21\\u0301\\u200b']
    [1, 1, 2, 2, 0, 0]
    """

    if unicodedata.combining(char) or unicodedata.category(char) in (
            'Mn', 'Me', 'Cf'):
        return 0
    if unicodedata.east_asian_width(char) in ('W', 'F'):
        return 2
    return 1


def display_width(text):
    """Number of columns text occupies in a monospace font.

    >>> display_width('Bj\\u00f6rk'), display_width('\\u5742\\u672c\\u9f8d\\u4e00')
    (5, 8)
    """

    return sum(char_width(c) for c in text)


def fit_width(text, width):
    """Crop text to abs(width) columns, then pad it to exactly that many.

    Like '%*.*s' % (width, abs(width), text), but counting display columns
    instead of characters, so double-width (CJK) and zero-width (combining)
    characters keep columns aligned. A negative width left-aligns. A wide
    character that would straddle the edge is replaced by a space.

    >>> fit_width('abc', 5), fit_width('abc', -5), fit_width('abcdef', -3)
    ('  abc', 'abc  ', 'abc')
    >>> fit_width('\\u5742\\u672c\\u9f8d', -5)
    '\\u5742\\u672c '
    >>> display_width(fit_width('\\u5742\\u672c\\u9f8d', -5))
    5
    """

    limit = abs(width)
    used = 0
    end = 0
    for i, char in enumerate(text):
        w = char_width(char)
        if used + w > limit:
            break
        used += w
        end = i + 1
    else:
        end = len(text)
    padding = ' ' * (limit - used)
    text = text[:end]
    return width < 0 and text + padding or padding + text


def parse_field(field_string, options):

    tag, width, suffix = (field_string.split(",") + ["", ""])[:3]
    if width == "":
        width = None
    else:
        width = int(width)
    column = Column(tag, width, suffix, options)
    column.indent = (lambda basename, depth, indent=options.indent:
                     " " * indent * depth + basename)
    return column


def to_minutes(value):

    return "%i:%02i" % (value // 60, value % 60)
