#!/usr/bin/env python3
"""Build hook for Dnuos.

Project metadata lives in pyproject.toml. This file only adds a build step
that compiles the gettext catalogs (.po -> .mo) before the package files are
copied, so translations ship in wheels and installs.

Build/install with:  python -m pip install .
Run the tests with:  python runtests.py
"""

import os
import sys
from glob import glob

from setuptools import setup
from setuptools.command.build_py import build_py

HERE = os.path.dirname(os.path.abspath(__file__))


class build_py_with_mo(build_py):
    """build_py that compiles translations first"""

    def run(self):
        sys.path.insert(0, HERE)
        try:
            from msgfmt import compile_catalog
        finally:
            sys.path.remove(HERE)
        pattern = os.path.join(HERE, 'dnuos', 'locale', '*', 'LC_MESSAGES',
                               '*.po')
        for path in glob(pattern):
            compile_catalog(path)
        super().run()


setup(cmdclass={'build_py': build_py_with_mo})
