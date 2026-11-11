"""Configuration module for Dnuos"""

import glob
import os
import re
import sys
import argparse

import dnuos.path
import dnuos.output
import dnuos.output.db
import dnuos.output.html
import dnuos.output.plaintext
from dnuos import appdata
from dnuos.misc import deprecation, natcmp, sort_with, _

# Translate argparse's own messages ("usage:", "options", errors) through the
# Dnuos catalog, as was done for optparse.
argparse._ = _

# Output templates accepted by --template (modules in dnuos.output)
TEMPLATES = ('plaintext', 'html', 'db')


class OptionError(Exception):
    """An invalid option value, reported as a usage error"""


class _Callback(argparse.Action):
    """Run callback(namespace, option_string, value, parser) for an option.

    Keeps the option handlers below as small functions, the way optparse's
    callback actions worked. OptionError becomes a normal usage error.
    """

    def __init__(self, option_strings, dest, callback=None, **kwargs):
        kwargs.setdefault('default', argparse.SUPPRESS)
        super().__init__(option_strings, dest, **kwargs)
        self.callback = callback

    def __call__(self, parser, namespace, values, option_string=None):
        try:
            self.callback(namespace, option_string, values, parser)
        except OptionError as err:
            parser.error(str(err))

def _ioctl_width(fd):

    from fcntl import ioctl
    from struct import pack, unpack
    from termios import TIOCGWINSZ
    return unpack('HHHH', ioctl(fd, TIOCGWINSZ, pack('HHHH', 0, 0, 0, 0)))[1]


def get_terminal_width():
    """Returns terminal width"""

    width = 0
    try:
        width = _ioctl_width(sys.stdout.fileno())
    except (AttributeError, ImportError, OSError, ValueError):
        pass
    if not width:
        try:
            width = int(os.environ.get('COLUMNS', 0))
        except ValueError:
            pass
    return width


def exit_with_output_help(namespace, opt_str, value, parser):
    """Prints output help and exits program"""

    print(_(r"""
Anything enclosed by brackets is considered a field. A field must have the
following syntax:
  [TAG]
  [TAG,WIDTH]
  [TAG,WIDTH,SUFFIX]
  [TAG,,SUFFIX]

TAG is any of the following characters:
  a  list of bitrates in Audiolist compatible format
  A  artist name as found in ID3 tags
  b  bitrate with suffix (e.g. 192k)
  B  bitrate in bps
  C  album name as found in ID3 tags
  D  depth; distance from respective basedir
  f  number of audio files (including spacers)
  l  length in minutes and seconds
  L  length in seconds
  m  time of last change
  M  time of last change in seconds since the epoch
  n  directory name (indented)
  N  directory name
  p  profile
  P  full path
  q  quality
  s  size with suffix (e.g 65.4M)
  S  size in bytes
  t  file type
  T  bitrate type:
       ~ mixed files
       C constant bitrate
       L lossless compression
       V variable bitrate
  V  encoder
  Y  year as found in ID3 tags

WIDTH defines the exact width of the field. The output is cropped to this
width if needed. Negative values will give left aligned output. Cropping is
always done on the right.

SUFFIX lets you specify a unit to be concatenated to all non-empty data.

Other interpreted sequences are:
  \[  [
  \]  ]
  \n  new line
  \t  tab character

Unescaped brackets are forbidden unless they define a field.

Note: If you have any whitespace in your output string you must put it inside
quotes or otherwise it will not get parsed right.
"""))
    sys.exit()


def set_db_format(namespace, opt_str, value, parser):

    namespace.outfile = value
    namespace.output_module = dnuos.output.db
    deprecation(_('The %s option is deprecated and will be removed in a '
                  'future version. Use --template=db --file=FILE instead to '
                  'ensure compatibility with future versions.') % opt_str)


def set_format_string(namespace, opt_str, value, parser):

    try:
        namespace.format_string, namespace.fields = (
            parse_format_string2(value))
    except ValueError:
        raise OptionError(_('Bad format string argument to %s')
                               % opt_str)


def set_html_format(namespace, opt_str, value, parser):

    namespace.output_module = dnuos.output.html
    deprecation(_('The %s option is deprecated and will be removed in a '
                  'future version. Use --template=html instead to ensure '
                  'compatibility with future versions.') % opt_str)


def set_mp3_min_bitrate(namespace, opt_str, value, parser):

    if value >= 0 and value <= 320:
        namespace.mp3_min_bit_rate = 1000 * value
    else:
        raise OptionError(_('Bitrate must be 0 or in the range (1..320)'))

def set_mp3_max_bitrate(namespace, opt_str, value, parser):

    if value >= 0 and value <= 320:
        namespace.mp3_max_bit_rate = 1000 * value
    else:
        raise OptionError(_('Bitrate must be 0 or in the range (1..320)'))

def set_output_module(namespace, opt_str, value, parser):

    # Only the real templates; other dnuos.output modules aren't renderers
    if value not in TEMPLATES:
        raise OptionError(_("Unknown template %s") % value)
    namespace.output_module = getattr(dnuos.output, value)


def set_preferred_tag(namespace, opt_str, value, parser):

    if value in [1, 2]:
        namespace.prefer_tag = value
    else:
        raise OptionError(_("Invalid argument to %s") % opt_str)


def set_cache_dir(namespace, opt_str, value, parser):

    value = os.path.normpath(os.path.expanduser(value))
    if dnuos.path.isdir(value):
        namespace.cache_dir = value
    else:
        raise OptionError(_("No such directory: %s") % value)


def set_unknown_types(namespace, opt_str, value, parser):

    namespace.unknown_types = tuple(set([v.strip().lower() for v in
                                             value.split(',') if v.strip()]))


def add_exclude_dir(namespace, opt_str, value, parser):

    value = os.path.abspath(value)
    if dnuos.path.isdir(value):
        namespace.exclude_paths.append(value)
    else:
        raise OptionError(_("No such directory: %s") % value)


def parse_format_string(data):
    r"""Extract field strings from input, replacing them with %s

    >>> parse_format_string('abcde')
    ('abcde', [])
    >>> parse_format_string('[a]bcde')
    ('%sbcde', ['a'])
    >>> parse_format_string('ab[c]de')
    ('ab%sde', ['c'])
    >>> parse_format_string('a[b]c[d]e')
    ('a%sc%se', ['b', 'd'])
    >>> parse_format_string(r'ab\[c]de')
    ('ab\\[c]de', [])
    >>> parse_format_string(r'ab\\[c]de')
    ('ab\\\\%sde', ['c'])
    >>> parse_format_string(r'ab\\\[c]de')
    ('ab\\\\\\[c]de', [])
    >>> parse_format_string(r'ab\\\\[c]de')
    ('ab\\\\\\\\%sde', ['c'])
    """
    even_backslashes = r'(?:^|[^\\])(?:\\\\)*'
    field_re = re.compile(r'(?P<backslashes>%s)\[(?P<field>.*?%s)\]' %
                          (even_backslashes, even_backslashes))

    fields = []
    match = field_re.search(data)
    while match:
        fields.append(match.group('field'))
        data = field_re.sub(r'\1%s', data, 1)
        match = field_re.search(data)

    return data, fields


def parse_format_string2(data):
    """--output format string -> (python format string, Column instances)

    This is a wrapper for parse_format_string() unescaping the format string
    and making Column instances from the field strings.
    """

    format, fields = parse_format_string(data)
    return unescape(format), [unescape(f) for f in fields]


def parse_args(argv=sys.argv):

    # This resizes the default format string based on the terminal's width.
    # A minimum width 76 characters is imposed, and a maximum 140 characters.
    name_width = min(max(get_terminal_width() - 28, 52), 116)
    default_format_string = '[n,-%d]| [s,5] | [t,-4] | [q]' % name_width
    format_string, fields = parse_format_string2(default_format_string)
    # Keep the existing (translated) usage string; argparse spells %prog as
    # %(prog)s.
    usage = _('%prog [options] basedir ...').replace('%prog', '%(prog)s')
    parser = argparse.ArgumentParser(
        prog=os.path.basename(argv[0]), usage=usage, add_help=False)
    parser.set_defaults(bg_color="white",
                        cache_dir=appdata.user_data_dir('Dnuos', 'Dnuos'),
                        cull_cache=False,
                        debug=False,
                        delete_cache=False,
                        disp_date=False,
                        disp_result=False,
                        disp_time=False,
                        disp_version=False,
                        exclude_paths=[],
                        fields=fields,
                        format_string=format_string,
                        indent=4,
                        list_bad=True,
                        list_files=False,
                        merge=False,
                        mp3_min_bit_rate=0,
			mp3_max_bit_rate=0,
                        no_cbr=False,
                        no_mixed=False,
                        no_non_profile=False,
                        outfile=None,
                        output_module=dnuos.output.plaintext,
                        prefer_tag=2,
                        show_progress=True,
                        sort_cmp=natcmp,
                        stripped=False,
                        text_color="black",
                        use_cache=True,
                        unknown_types=(),
                        wildcards=False)

    def default(name):
        # Help texts are %-formatted by argparse, so escape any '%' in
        # interpolated values (e.g. a cache path containing one).
        return str(parser.get_default(name)).replace('%', '%%')

    parser.add_argument("-h", "--help", action="help",
                        help=_("Show this help message and exit"))
    parser.add_argument("--help-output-string",
                        action=_Callback, nargs=0,
                        callback=exit_with_output_help,
                        help=_('Show output string help message'))
    # Directories (or files) to list. Shown in the usage line, so it's
    # left out of the option list.
    parser.add_argument("basedir_args", nargs='*', help=argparse.SUPPRESS)

    group = parser.add_argument_group(_('Application'))
    group.add_argument("--debug",
                       dest="debug", action="store_true",
                       help=_('Output debug trace to stderr'))
    group.add_argument("--ignore-bad",
                       dest="list_bad", action="store_false",
                       help=_("Don't list files that cause Audiotype failure"))
    group.add_argument("-q", "--quiet",
                       dest="show_progress", action="store_false",
                       help=_('Omit progress indication'))
    group.add_argument("-V", "--version",
                       dest='disp_version', action='store_true',
                       help=_('Display version'))

    group = parser.add_argument_group(_('Caching'))
    group.add_argument("--cache-dir",
                       action=_Callback, callback=set_cache_dir,
                       help=_('Store cache in DIR (default %s)') %
                       default('cache_dir'),
                       metavar=_('DIR'))
    group.add_argument('--cull-cache',
                       dest='cull_cache', action='store_true',
                       help=_('Cull non-existent cached directories and exit'))
    group.add_argument('--delete-cache',
                       dest='delete_cache', action='store_true',
                       help=_('Delete the cache directory and exit'))
    group.add_argument('-C', '--disable-cache',
                       dest="use_cache", action="store_false",
                       help=_('Disable caching'))

    group = parser.add_argument_group(_('Directory walking'))
    group.add_argument("-e", "--exclude",
                       action=_Callback, callback=add_exclude_dir,
                       help=_('Exclude DIR from search'), metavar=_('DIR'))
    group.add_argument("-i", "--ignore-case",
                       dest="sort_cmp", action="store_const",
                       const=lambda a, b: natcmp(a.lower(), b.lower()),
                       help=_('Case-insensitive directory sorting'))
    group.add_argument('-L', '--list-files',
                       dest='list_files', action='store_true',
                       help=_("List audio files in directories (doesn't use "
                              "caching)"))
    group.add_argument("-m", "--merge",
                       dest="merge", action="store_true",
                       help=_('Parse basedirs in parallel and merge output'))
    group.add_argument('-u', '--unknown-types',
                       action=_Callback, callback=set_unknown_types,
                       help=_('A comma-separated list of unknown audio types '
                              'to list'), metavar=_('TYPES'))
    group.add_argument("-w", "--wildcards",
                       dest="wildcards", action="store_true",
                       help=_('Expand wildcards in basedirs'))

    group = parser.add_argument_group(_('Filtering'))
    group.add_argument("-U", "--max-bitrate",
                       action=_Callback, callback=set_mp3_max_bitrate,
                       type=int,
                       help=_('Include MP3s with bitrate lower than MAX '
                       '(in Kbps)'), metavar=_('MAX'))
    group.add_argument("-b", "--bitrate",
                       action=_Callback, callback=set_mp3_min_bitrate,
                       type=int,
                       help=_('Exclude MP3s with bitrate lower than MIN '
                       '(in Kbps)'), metavar=_('MIN'))
    group.add_argument("-l", "--lame-only",
                       dest="no_non_profile", action="store_true",
                       help=_('Exclude MP3s with no LAME profile'))
    group.add_argument("-v", "--vbr-only",
                       dest="no_cbr", action="store_true",
                       help=_('Exclude MP3s with constant bitrates'))
    group.add_argument("-M", "--no-mixed",
                       dest="no_mixed", action="store_true",
                       help=_('Exclude directories with mixed files'))

    group = parser.add_argument_group(_('Output'))
    group.add_argument("-B", "--bg",
                       dest="bg_color",
                       help=_('Set HTML background COLOR (default %s)') %
                       default('bg_color'),
                       metavar=_('COLOR'))
    group.add_argument("-f", "--file",
                       dest="outfile",
                       help=_('Write output to FILE'), metavar=_('FILE'))
    group.add_argument("-H", "--html",
                       action=_Callback, nargs=0, callback=set_html_format,
                       help=_('HTML output (deprecated, use --template html)'))
    group.add_argument("-I", "--indent",
                       dest="indent", type=int,
                       help=_('Set indent to n (default %s)') %
                       default('indent'),
                       metavar=_('n'))
    group.add_argument("-o", "--output",
                       action=_Callback, callback=set_format_string,
                       help=_('Set output format STRING used in plain-text '
                       'and HTML output. See --help-output-string for '
                       'details on syntax. (default %s)') %
                       default_format_string.replace('%', '%%'),
                       metavar=_('STRING'))
    group.add_argument("-O", "--output-db",
                       action=_Callback, callback=set_db_format,
                       help=_('Write list in output.db format to FILE '
                       '(deprecated, use --template db)'), metavar=_('FILE'))
    group.add_argument("-P", "--prefer-tag",
                       action=_Callback, callback=set_preferred_tag,
                       type=int,
                       help=_('If both ID3v1 and ID3v2 tags exist, prefer '
                       'n (1 or 2) (default %s)') % default('prefer_tag'),
                       metavar=_('n'))
    group.add_argument("-s", "--strip",
                       dest="stripped", action="store_true",
                       help=_('Strip output of field headers and empty '
                       'directories'))
    group.add_argument("--template",
                       action=_Callback, callback=set_output_module,
                       help=_('Set output TEMPLATE: %s (default plaintext)')
                       % ', '.join(TEMPLATES),
                       metavar=_('TEMPLATE'))
    group.add_argument("-T", "--text",
                       dest="text_color",
                       help=_('Set HTML text COLOR (default %s)') %
                       default('text_color'),
                       metavar=_('COLOR'))

    group = parser.add_argument_group(_('Statistics'))
    group.add_argument("-D", "--date",
                       dest="disp_date", action="store_true",
                       help=_('Display datestamp header'))
    group.add_argument("-S", "--stats",
                       dest="disp_result", action="store_true",
                       help=_('Display statistics results'))
    group.add_argument("-t", "--time",
                       dest="disp_time", action="store_true",
                       help=_('Display elapsed time footer'))

    # Intermixed parsing keeps optparse's behaviour of allowing options
    # after (or between) the directories, e.g. "dnuos DIR1 -q DIR2".
    options = parser.parse_intermixed_args(argv[1:])
    args = options.basedir_args
    del options.basedir_args

    # add basedirs
    options.basedirs = []
    for glob_dir in args:
        options.basedirs += [p for p in expand(options, glob_dir)
                             if p not in options.exclude_paths]
    if not options.basedirs and not (options.cull_cache or
        options.delete_cache):
        if options.disp_version:
            print(''.join(dnuos.output.plaintext.render_version(
                dnuos.__version__)))
            sys.exit()
        print((_("No folders to process.\nType `%s -h' "
                                "for help.") % os.path.basename(argv[0])), file=sys.stderr)
        sys.exit(2)

    for basedir in options.basedirs:
        if not dnuos.path.exists(basedir):
            print(_('No such file or directory: %s') % basedir, file=sys.stderr)
            sys.exit(2)

    # options overriding eachother
    # Progress is redrawn on stderr with '\r', so only show it on an
    # interactive terminal (not when stderr goes to a file or pipe), and not
    # when the listing itself is printed to that same terminal.
    if (options.debug or not _isatty(sys.stderr) or
            (not options.outfile and _isatty(sys.stdout))):
        options.show_progress = False
    if options.output_module == dnuos.output.db:
        options.list_bad = False

    return options


def _isatty(stream):
    """True if stream is a real terminal"""

    try:
        return stream.isatty()
    except (AttributeError, ValueError):
        return False


def expand(options, dir_):
    """translate a basedir to a list of absolute paths"""

    if options.wildcards and re.search(r"[*?]|(?:\[.*\])", dir_):
        dirs = glob.glob(dir_)
        sort_with(dirs, options.sort_cmp)
        return [os.path.abspath(d) for d in dirs]
    else:
        return [os.path.abspath(dir_)]


def unescape(data):
    """Unescapes escaped backslashes"""

    data = data.replace(r'\t', '\t').replace(r'\n', '\n')
    data = re.sub(r'\\([\\\[\]])', r'\1', data)
    return data
