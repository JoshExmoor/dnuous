"""
>>> test()
"""

import doctest
import io
import locale

import dnuos


class FakeDir(object):

    def __init__(self, size):
        self.size = size


def test():
    """Verify the progress counter only grows and never leaves residue"""

    # Run the examples in the progress functions' docstrings
    for func in (dnuos.format_progress, dnuos.indicate_progress):
        runner = doctest.DocTestRunner()
        for case in doctest.DocTestFinder().find(func, globs={
                'format_progress': dnuos.format_progress,
                'indicate_progress': dnuos.indicate_progress}):
            runner.run(case)
        assert runner.failures == 0, func.__name__

    old = locale.setlocale(locale.LC_ALL)
    locale.setlocale(locale.LC_ALL, 'C')
    try:
        # Sizes that used to cross unit boundaries (k -> M -> G) and shrink
        # the text: 1023k, 1M, 99.9M, 102M, 1023M, 1G...
        kib = 1024
        steps = [1023 * kib, kib, 98 * 1024 * kib + 921 * kib, 2150 * kib,
                 921 * 1024 * kib, 1024 * 1024 * kib, 0]
        out = io.StringIO()
        pairs = [(FakeDir(size), '/') for size in steps]
        assert len(list(dnuos.indicate_progress(pairs, outs=out))) == len(steps)

        lines = out.getvalue().split('\r')[1:-2]
        values = [float(l.split()[0].replace(',', '')) for l in lines]
        assert values == sorted(values), values
        # Every redraw is at least as wide as the previous one
        widths = [len(l) for l in lines]
        assert widths == sorted(widths), widths
        # The final clear covers the widest line
        assert out.getvalue().endswith('\r' + ' ' * widths[-1] + '\r')
    finally:
        locale.setlocale(locale.LC_ALL, old)
