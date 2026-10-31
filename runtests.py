#!/usr/bin/env python3
"""Run the Dnuos doctest suite.

Usage: python runtests.py [--data-dir DIR]

Runs every doctest in the dnuos package (unit tests) and the dnuostests
package (functional tests that compare dnuos output against expected
listings). The functional tests need the test data directory, which
defaults to ./testdata, falling back to dnuostests/testdata.
"""

import argparse
import doctest
import importlib
import os
import sys
from glob import glob

HERE = os.path.dirname(os.path.abspath(__file__))


def testpkg(path):
    """Runs doctest on an entire package. Returns (failures, tests)."""

    modules = glob(os.path.join(path, '*.py'))
    modules += glob(os.path.join(path, '*', '*.py'))
    total_failures, total_tests, import_errors = 0, 0, 0
    for module in sorted(modules):
        # __main__ runs the CLI on import, so it can't be scanned
        if os.path.basename(module) in ('__init__.py', '__main__.py'):
            continue
        name = os.path.relpath(os.path.splitext(module)[0], HERE)
        name = name.replace(os.path.sep, '.')
        try:
            mod = importlib.import_module(name)
        except Exception as e:
            print('Unable to import %r: %s: %s' % (name, type(e).__name__, e),
                  file=sys.stderr)
            import_errors += 1
            continue
        failures, tests = doctest.testmod(mod)
        if tests > 0:
            print('%s: %s/%s passed' % (name, tests - failures, tests))
        total_failures += failures
        total_tests += tests

    print('Total: %s/%s passed' % (total_tests - total_failures, total_tests))
    print('')
    return total_failures + import_errors, total_tests


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # A local ./testdata takes precedence; otherwise use the tracked copy
    default_data = os.path.join(HERE, 'testdata')
    if not os.path.isdir(default_data):
        default_data = os.path.join(HERE, 'dnuostests', 'testdata')
    parser.add_argument('-d', '--data-dir', default=default_data,
                        help='path to test data [default: ./testdata if '
                             'present, else dnuostests/testdata]')
    args = parser.parse_args()
    os.environ['DATA_DIR'] = os.path.abspath(args.data_dir)
    sys.path.insert(0, HERE)

    failed = 0
    for pkg in ('dnuos', 'dnuostests'):
        failures, _ = testpkg(os.path.join(HERE, pkg))
        failed += failures
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
