"""Miscellaneous module for Dnuos.

Most of these things are algorithms for various lowlevel things. Not all
however.

Don't import other Dnuos modules from here.

Feel free to organize this in a better way if you know how. I don't.
"""

import locale
import os
import re
from functools import cmp_to_key, total_ordering
from heapq import heappop, heappush
from itertools import count
from warnings import warn

def cmp(a, b):
    """Python 2 style three-way comparison"""

    return (a > b) - (a < b)


def sort_with(seq, sort_cmp):
    """Sort a list in place using a three-way comparison function"""

    seq.sort(key=cmp_to_key(sort_cmp))


def _find_locale_dir():

    # Avoid unpacking the egg if translation isn't necessary
    lang = None
    for var in ('LC_ALL', 'LC_MESSAGES', 'LANG', 'LANGUAGE'):
        if os.environ.get(var):
            lang = os.environ[var].split(':')[0]
            break
    if not lang:
        try:
            lang = locale.getlocale()[0]
        except ValueError:
            return None
    if not lang or lang.split('_', 1)[0] == 'en':
        return None

    # __file__ isn't always available (e.g. in frozen builds)
    if '__file__' in globals():
        locale_dir = os.path.join(os.path.split(__file__)[0], 'locale')
        if os.path.isdir(locale_dir):
            return locale_dir
    return None

def _gettext():

    locale_dir = _find_locale_dir()
    if locale_dir:
        try:
            from gettext import translation
            return translation('dnuos', _find_locale_dir(),
                               fallback=True).gettext
        except ImportError:
            pass
    return lambda s: s

_ = _gettext()


_natsub = re.compile(r'\d+').sub
def _natkey(s):

    return _natsub(lambda i: str(len(i.group())) + i.group(), s)

def natcmp(a, b):
    """Compare two strings for natural sorting"""

    return locale.strcoll(_natkey(a), _natkey(b))

@total_ordering
class Lookahead(object):
    """Wrapper class for adding one element of lookahead to an iterator.
    Requires iterables of strings or sequences of strings.

    Example behavior:

    >>> x = Lookahead(iter(('0', '1', '2')))
    >>> x.lookahead
    '0'
    >>> next(x)
    '0'
    >>> x.lookahead
    '1'
    >>> next(x)
    '1'
    >>> x.lookahead
    '2'
    >>> y = Lookahead(iter(('1', '2', '3')))
    >>> next(y)
    '1'
    >>> x == y
    True
    >>> next(y)
    '2'
    >>> x <= y
    True
    >>> x.empty
    False
    >>> next(x)
    '2'
    >>> x.empty
    True
    """

    __slots__ = ['iterator', 'sort_cmp', 'lookahead', 'empty']

    def __init__(self, iterator, sort_cmp=None):

        self.iterator = iterator
        self.sort_cmp = sort_cmp or cmp
        self.lookahead = None
        self.empty = False
        next(self)

    def __iter__(self):

        return self

    def __next__(self):
        """Get next value"""

        result = self.lookahead
        try:
            self.lookahead = next(self.iterator)
        except StopIteration:
            self.lookahead = None
            self.empty = True
        return result

    # Compare iterator heads (as opposed to the entire iterators)
    def __eq__(self, other):

        return self.sort_cmp(self.lookahead, other.lookahead) == 0

    def __lt__(self, other):

        return self.sort_cmp(self.lookahead, other.lookahead) < 0

    __hash__ = object.__hash__


def deprecation(message):

    warn(message, DeprecationWarning, stacklevel=2)


def dir_depth(path):
    """Return the subdirectory depth of a path.

    >>> dir_depth('/')
    0
    >>> dir_depth('/usr')
    1
    >>> dir_depth('/usr/')
    1
    >>> dir_depth('/usr/local')
    2
    """

    parts = os.path.abspath(path).split(os.path.sep)[1:]
    return parts != [''] and len(parts) or 0


def equal_elements(seq1, seq2):
    """Return the largest n such that seq1[:n] == seq2[:n].

    >>> equal_elements('', '')
    0
    >>> equal_elements('abcd', 'abcd')
    4
    >>> equal_elements('abcd', 'abCD')
    2
    >>> equal_elements('abcd', 'abcdef')
    4
    >>> equal_elements('abcdef', 'abcd')
    4
    """

    for index in count():
        try:
            if seq1[index] != seq2[index]:
                return index
        except IndexError:
            return index


def formatwarning(message, category, filename, lineno, *args, **kwargs):
    """Custom warning formatting."""

    return "%s: %s\n" % (category.__name__, message)


def is_subdir(path1, path2):
    """Returns True if path1 is a subdirectory of path2, otherwise False.

    >>> import os
    >>> os_dir = os.path.dirname(os.__file__)
    >>> above_os = os.path.dirname(os_dir)
    >>> is_subdir(above_os, os_dir)
    False
    >>> is_subdir(os_dir, above_os)
    True
    >>> is_subdir(os_dir, os_dir)
    True
    """

    path1 = path1.split(os.path.sep)
    path2 = path2.split(os.path.sep)
    return path2 == path1[:len(path2)]


def merge(iterators, sort_cmp=None):
    """Merge n ordered iterators into one ordered iterator.

    Merge two ordered iterators
    >>> xs = iter(['a1', 'b1', 'c1'])
    >>> ys = iter(['a2', 'b2', 'c2'])
    >>> list(merge([xs, ys]))
    ['a1', 'a2', 'b1', 'b2', 'c1', 'c2']
    """

    # Make a heap of the given iterators. The heap is sorted by the
    # iterator head elements, or if those are equal, by the order of
    # insertion. Thats what the index is for.
    # Heappush and heappop use the __lt__ and __eq__ methods of the
    # elements for the sorting. Generator items dont have meaningful
    # comparison operators, so we wrap them in Lookahead which defines
    # the inequality as per the respective head elements.
    heap = []
    for index in range(0, len(iterators)):
        iterator = Lookahead(iterators[index], sort_cmp)
        if not iterator.empty:
            heappush(heap, (iterator, index))

    # Since all iterators are ordered (precondition) and the heap is ordered
    # by head elements of the iterators, the head element of the head
    # iterator on the heap is the smallest element of all remaining
    # elements, and thus the next element in the ordered merged iteration.
    while heap:
        iterator, index = heappop(heap)
        yield next(iterator)
        if not iterator.empty:
            heappush(heap, (iterator, index))


def to_human(value, radix=1024.0):
    """Convert a value to a string using SI suffixes.

    Example output:

    >>> to_human(20)
    '20.0 '
    >>> to_human(20 * 1024)
    '20.0k'
    >>> to_human(20 * 1024 ** 2)
    '20.0M'
    >>> to_human(20 * 1024 ** 3)
    '20.0G'
    >>> to_human(20 * 1024 ** 4)
    '20480G'
    """

    i = 0
    while value >= radix and i < 3:
        value /= radix
        i += 1
    suffix = " kMG"[i]
    if value > 100:
        value = locale.format_string('%d', value)
    elif value < 10:
        value = locale.format_string('%.2f', value)
    else:
        value = locale.format_string('%.1f', value)
    return "%s%s" % (value, suffix)
