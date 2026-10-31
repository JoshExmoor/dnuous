"""Script for gathering information about directories of audio files"""

__version__ = '2.0.0'

import locale
import os
import sys
import time
import warnings
from itertools import chain

import dnuos.output.db
import dnuos.path
from dnuos import appdata, audiodir
from dnuos.cache import Cache, memoized
from dnuos.conf import parse_args
from dnuos.misc import dir_depth, equal_elements, formatwarning
from dnuos.misc import merge, sort_with, _
from dnuos.output.db import DBColumn

__all__ = ['main']

class Data(object):
    """Holds data for cache"""

    def __init__(self, unknown_types=()):

        self.bad_files = []
        self.size = {
            "Total": 0.0,
            "FLAC": 0.0,
            "Ogg": 0.0,
            "Opus": 0.0,
            "MP3": 0.0,
            "MPC": 0.0,
            "AAC": 0.0,
            'Other': 0.0,
        }
        if unknown_types:
            self.size.update(dict([(t, 0.0) for t in unknown_types]))
        self.times = {
            'start': 0,
            'elapsed_time': 0.0,
        }


def make_raw_listing(basedirs, exclude_paths, sort_cmp, use_merge,
                     adir_class):
    """Make an iterator over all subdirectories of the base directories,
    including the base directories themselves. The directory trees are
    sorted either separately or together according to the merge setting.
    """

    trees = []
    for basedir in basedirs:
        if dnuos.path.isdir(basedir):
            trees.append(walk2(basedir, sort_cmp, exclude_paths))
        else:
            root = os.path.dirname(basedir)
            trees.append([(basedir[len(root):], root)])

    if use_merge:
        tree = merge(trees, lambda a, b: sort_cmp(a[0], b[0]))
    else:
        tree = chain(*trees)

    return to_adir(tree, adir_class)


def prepare_listing(dir_pairs, options, data):
    """Add layers of functionality"""

    dir_pairs = timer_wrapper(dir_pairs, data.times)
    if options.show_progress:
        dir_pairs = indicate_progress(dir_pairs)
    if options.debug:
        dir_pairs = print_bad(dir_pairs)
    elif options.list_bad:
        dir_pairs = collect_bad(dir_pairs, data.bad_files)
    dir_pairs = filter(non_empty, dir_pairs)
    if options.no_mixed:
        dir_pairs = filter(no_mixed, dir_pairs)
    if options.no_cbr:
        dir_pairs = filter(no_cbr_mp3, dir_pairs)
    if options.no_non_profile:
        dir_pairs = filter(profile_only_mp3, dir_pairs)
    if options.mp3_min_bit_rate != 0:
        dir_pairs = filter(enough_bitrate_mp3(options.mp3_min_bit_rate),
                            dir_pairs)
    if options.mp3_max_bit_rate != 0:
        dir_pairs = filter(to_little_bitrate_mp3(options.mp3_max_bit_rate),
                            dir_pairs)
    if options.output_module == dnuos.output.db:
        output_db_predicate = make_output_db_predicate(options)
        dir_pairs = filter(output_db_predicate, dir_pairs)
    if not options.output_module == dnuos.output.db:
        dir_pairs = total_sizes(dir_pairs, data.size)
    if (not options.stripped and
        options.output_module in [dnuos.output.plaintext, dnuos.output.html]):
        dir_pairs = add_empty(dir_pairs)
    if options.list_files:
        dir_pairs = add_files(dir_pairs, options.sort_cmp)
    return dir_pairs


def setup_cache(cache_filename):
    """Creates and readies cache"""

    return Cache(filename=cache_filename,
                 version=audiodir.Dir.__version__)


def setup_renderer(output_module, format_string, fields, options):
    """Create and readies renderer"""

    renderer = output_module.Renderer()
    renderer.format_string = format_string
    renderer.setup_columns(fields, options)
    return renderer


def main(argv=None, locale=''):
    """Main entry point"""

    # Replace characters the terminal can't encode with question marks
    # instead of crashing.
    reconfigure = getattr(sys.stdout, 'reconfigure', None)
    if reconfigure is not None:
        try:
            reconfigure(errors='replace')
        except (TypeError, ValueError):
            pass

    import locale as locale_
    try:
        locale_.setlocale(locale_.LC_ALL, locale)
    except locale_.Error:
        pass

    if argv is None:
        argv = sys.argv

    warnings.formatwarning = formatwarning
    try:
        options = parse_args(argv)
    except SystemExit as e:
        return e.code
    data = Data(options.unknown_types)
    audiodir.Dir.valid_types.extend(options.unknown_types or ())

    if options.delete_cache:
        import shutil
        try:
            shutil.rmtree(options.cache_dir)
        except OSError as err:
            print(_('Failed to delete cache: %s') % err, file=sys.stderr)
            return 2
        print(_('Removed cache directory %s') % options.cache_dir)
        return 0

    adir_class = audiodir.Dir
    if options.use_cache:
        try:
            appdata.create_user_data_dir(options.cache_dir)
            cache = setup_cache(appdata.user_data_file('dirs',
                                options.cache_dir))
            if options.cull_cache:
                culled = cache.cull()
                cache.save()
                print(_('Culled %d non-existent directories') % culled)
                return 0
            adir_class = memoized(audiodir.Dir, cache)
        except (ImportError, IOError) as err:
            options.use_cache = False
            print(_('Failed to create cache directory:'), file=sys.stderr)
            if options.debug:
                raise
            print(err, file=sys.stderr)
            print(_('Use the --disable-cache switch to '
                                   'disable caching'), file=sys.stderr)

    try:
        renderer = setup_renderer(options.output_module,
                                  options.format_string, options.fields,
                                  options)
    except KeyError:
        print(_('Format string can only contain valid fields'), file=sys.stderr)
        print(_('Use the --help-output-string switch for more '
                               'information'), file=sys.stderr)
        return 2

    # Append basedirs to exclude_paths to avoid traversing nested
    # basedirs again.
    adirs = make_raw_listing(options.basedirs,
                             options.exclude_paths + options.basedirs,
                             options.sort_cmp, options.merge, adir_class)
    adirs = prepare_listing(adirs, options, data)
    result = renderer.render(adirs, options, data)

    # Output
    encoding = getattr(options.output_module, 'OUTPUT_ENCODING', 'utf-8')
    outfile = (options.outfile and
               dnuos.path.open(options.outfile, 'w', encoding=encoding,
                               errors='replace')
               or sys.stdout)
    try:
        for chunk in result:
            print(chunk, file=outfile)
    finally:
        if outfile is not sys.stdout:
            outfile.close()
        # Store updated cache
        if options.basedirs and options.use_cache:
            try:
                cache.save()
            except IOError as err:
                print(_('Failed to save cache data:'), file=sys.stderr)
                if options.debug:
                    raise
                print(err, file=sys.stderr)
                print(_('Use the --disable-cache switch to '
                                       'disable caching'), file=sys.stderr)
                return 2


def cli():
    """Console script entry point. Returns the process exit status."""

    try:
        return main()
    except KeyboardInterrupt:
        if '--debug' in sys.argv:
            raise
        return 130


def format_progress(processed):
    """Format the progress line for a byte count.

    A single unit (MB) is used so the number only ever grows; switching
    units (1023k -> 1.00M) made it look like it went backwards.

    >>> format_progress(0)
    '0.0 MB processed'
    >>> format_progress(1536 * 1024)
    '1.5 MB processed'
    """

    megs = locale.format_string('%.1f', processed / (1024.0 * 1024),
                                grouping=True)
    return (_('%sB processed\r') % (megs + ' M')).rstrip('\r')


def indicate_progress(dir_pairs, sizes=None, outs=sys.stderr):
    """Indicate progress.

    Yields an unchanged iteration of dirs with an added side effect: the
    total size of the audio scanned so far (including the directory just
    scanned) is written to outs on a single, redrawn line.

    >>> import io
    >>> class D(object):
    ...     def __init__(self, size): self.size = size
    >>> out = io.StringIO()
    >>> pairs = [(D(100 * 1024 * 1024), '/'), (D(2 * 1024 * 1024), '/')]
    >>> len(list(indicate_progress(pairs, outs=out)))
    2
    >>> out.getvalue().split('\\r')[1:]
    ['100.0 MB processed', '102.0 MB processed', '                  ', '']
    """

    processed = 0
    width = 0
    for adir, root in dir_pairs:
        processed += adir.size or 0
        line = format_progress(processed)
        # Pad to the widest line so far, so nothing is left behind when the
        # text gets shorter.
        width = max(width, len(line))
        outs.write('\r' + line.ljust(width))
        outs.flush()
        yield adir, root
    if width:
        outs.write('\r' + ' ' * width + '\r')
        outs.flush()


def print_bad(dir_pairs):
    """Print bad files.

    Yields an unchanged iteration of dirs with an added side effect.
    After each directory is yielded its bad files are output to
    stderr.
    """

    for adir, root in dir_pairs:
        yield adir, root
        for badfile, traceback in adir.bad_files:
            print(_('Audiotype failed for:'), badfile, file=sys.stderr)
            print(traceback, file=sys.stderr)


def collect_bad(dir_pairs, bad_files):
    """Collect bad files.

    Yields an unchanged iteration of dirs with an added side effect.
    After each directory is yielded its bad files are appended to
    bad_files.
    """

    for adir, root in dir_pairs:
        yield adir, root
        bad_files.extend(adir.bad_files)


def non_empty(adir_root):
    """Empty directory predicate.

    Directories are considered empty if they contain no recognized audio files.
    """
    (adir, root) = adir_root
    return adir.num_files > len(adir.bad_files)


def no_mixed(adir_root):
    """No mixed audio directories predicate"""
    (adir, root) = adir_root
    return (adir.mediatype != 'Mixed' and adir.brtype != '~' and
            len(adir.bad_files) == 0)


def no_cbr_mp3(adir_root):
    """No CBR MP3 files predicate"""
    (adir, root) = adir_root
    return adir.mediatype != "MP3" or adir.brtype not in "C~"


def profile_only_mp3(adir_root):
    """No non-profile MP3 predicate"""
    (adir, root) = adir_root
    return adir.mediatype != "MP3" or adir.profile != ""


def enough_bitrate_mp3(mp3_min_bit_rate):
    """Create low-bitrate MP3 predicate"""

    # This implementation does not consider low-bitrate MP3s in Mixed dirs
    return lambda adir_root: (adir_root[0].mediatype != "MP3" or
                                 adir_root[0].bitrate >= mp3_min_bit_rate)

def to_little_bitrate_mp3(mp3_max_bit_rate):
    """Create max-bitrate MP3 predicate"""

    # This implementation does not consider low-bitrate MP3s in Mixed dirs
    return lambda adir_root1: (adir_root1[0].mediatype != "MP3" or
                                 adir_root1[0].bitrate <= mp3_max_bit_rate)


def make_output_db_predicate(options):
    """Predicate for whether something should be included in output.db"""

    artist_column = DBColumn("A", None, None, options)
    album_column = DBColumn("C", None, None, options)

    def output_db_predicate(adir_root):
        (adir, root) = adir_root
        return (adir.mediatype != "Mixed" and
                artist_column.get(adir) != None and
                album_column.get(adir) != None)
    return output_db_predicate


def total_sizes(dir_pairs, sizes):
    """Calculate audio file size totals.

    Yields an unchanged iteration of dirs with an added side effect.
    After each directory is yielded its filesize statistics are
    added to sizes.
    """

    for adir, root in dir_pairs:
        yield adir, root
        for mediatype, size in list(adir.sizes.items()):
            if mediatype in sizes:
                sizes[mediatype] += size
            else:
                sizes['Other'] += size
        sizes["Total"] += adir.size


def timer_wrapper(dir_pairs, times):
    """Time the iteration.

    Yields an unchanged iteration of dirs with an added side effect.
    Time in seconds elapsed over the entire iteration is stored in times.
    """

    times['start'] = time.perf_counter()
    for adir, root in dir_pairs:
        yield adir, root
    times['elapsed_time'] = time.perf_counter() - times['start']


class EmptyDir(object):
    """Represent a group of merged empty directories"""

    __slots__ = ['name', 'path']

    def __init__(self, path):

        self.name = os.path.basename(path)
        self.path = path

    def __getattr__(self, attr):

        return None

    def depth_from(self, root):
        """Returns the depth from one directory to another"""

        return dir_depth(self.path) - dir_depth(root) - 1


def add_empty(dir_pairs):
    """Insert empty ancestral directories

    Pre-order directory tree traversal is assumed.
    """

    oldpath = []
    for adir, root in dir_pairs:
        drive, root = os.path.splitdrive(root)
        path = adir.path[len(drive) + len(root):].strip(os.path.sep
                ).split(os.path.sep)
        start = equal_elements(path, oldpath)
        for depth in range(start, len(path) - 1):
            emptypath = os.path.join(drive, root, *path[:depth + 1])
            yield EmptyDir(emptypath), root
        oldpath = path

        yield adir, root


def add_files(dir_pairs, sort_cmp):
    """Makes individual audiodirs for each audio file"""

    for adir, root in dir_pairs:
        yield adir, root
        if not dnuos.path.isdir(adir.path):
            continue
        # EmptyDir placeholders report None here
        if not adir.num_files:
            continue
        files = adir.audio_files
        sort_with(files, sort_cmp)
        for path in files:
            yield audiodir.Dir(path), root


def walk2(basedir, sort_cmp, excluded):
    """Traverse a directory tree in pre-order

    Walk2 is a thin wrapper around walk. It splits each path into a
    (relpath, root) tuple where root is the parent directory of
    basedir.
    """

    root = os.path.dirname(basedir)
    for sub in walk(basedir, sort_cmp, excluded):
        yield sub[len(root):], root


def walk(dir_, sort_cmp, excluded):
    """Traverse a directory tree in pre-order.

    Directories are sorted by sort_cmp and branches specified in
    exclude are ignored. Symbolic links are followed.
    """

    try:
        subs = dnuos.path.listdir(dir_)
    except OSError:
        return
    subs = [os.path.join(dir_, sub)
            for sub in subs]
    subs = [sub for sub in subs
            if dnuos.path.isdir(sub)
               and sub not in excluded]
    sort_with(subs, sort_cmp)

    yield dir_
    for sub in subs:
        for res in walk(sub, sort_cmp, excluded):
            yield res


def to_adir(path_pairs, constructor):
    """Converts a sequence of path pairs into a sequence of dir pairs.

    A path pair is a tuple (relpath, root). A dir pair is tuple (Dir,
    root). The Dir is validated and root is assigned to it.
    """

    cache = getattr(constructor, 'cache', None)
    for relpath, root in path_pairs:
        path = root + relpath
        adir = constructor(path)
        if not adir.is_valid():
            adir.load()
            # A stale cache entry was just rescanned. Store the fresh result,
            # otherwise the directory is rescanned on every future run.
            if cache is not None:
                cache[path] = adir
        yield adir, root
