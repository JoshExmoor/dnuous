#!/usr/bin/env python3
"""Build a standalone Windows executable of Dnuos with PyInstaller.

Usage:
    python -m pip install pyinstaller==6.11.1
    python build_exe.py [--onedir] [--dist DIR]

Produces dist/py3/dnuos.exe by default: a single file that bundles Python and
the translations, so it runs on machines without Python installed. Use
--onedir for a folder build, which starts faster but ships many files.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from glob import glob

HERE = os.path.dirname(os.path.abspath(__file__))
PYINSTALLER_VERSION = '6.11.1'

# The entry script must not be named dnuos.py: inside the bundle it would
# shadow the dnuos package and `import dnuos` would import itself.
ENTRY_SCRIPT = """import sys
import dnuos
sys.exit(dnuos.cli())
"""


def compile_translations():
    """Compile .po catalogs and return PyInstaller --add-data arguments"""

    sys.path.insert(0, HERE)
    try:
        from msgfmt import compile_catalog
    finally:
        sys.path.remove(HERE)

    add_data = []
    pattern = os.path.join(HERE, 'dnuos', 'locale', '*', 'LC_MESSAGES',
                           '*.po')
    for po in glob(pattern):
        compile_catalog(po)
        mo = os.path.splitext(po)[0] + '.mo'
        dest = os.path.relpath(os.path.dirname(mo), HERE)
        add_data += ['--add-data', '%s%s%s' % (mo, os.pathsep, dest)]
    return add_data


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--onedir', action='store_true',
                        help='build a folder instead of a single file')
    parser.add_argument('--dist', default=os.path.join(HERE, 'dist', 'py3'),
                        help='output directory [default: dist/py3]')
    args = parser.parse_args()

    try:
        import PyInstaller
    except ImportError:
        sys.exit('PyInstaller is not installed. Install it with:\n'
                 '    %s -m pip install pyinstaller==%s'
                 % (sys.executable, PYINSTALLER_VERSION))
    if PyInstaller.__version__ != PYINSTALLER_VERSION:
        print('warning: built and tested with PyInstaller %s, found %s'
              % (PYINSTALLER_VERSION, PyInstaller.__version__),
              file=sys.stderr)

    add_data = compile_translations()
    work = tempfile.mkdtemp(prefix='dnuos_exe_')
    try:
        entry = os.path.join(work, 'dnuos_entry.py')
        with open(entry, 'w') as f:
            f.write(ENTRY_SCRIPT)
        cmd = [sys.executable, '-m', 'PyInstaller',
               '--noconfirm', '--clean', '--console',
               args.onedir and '--onedir' or '--onefile',
               '--name', 'dnuos',
               '--paths', HERE,
               '--distpath', os.path.abspath(args.dist),
               '--workpath', os.path.join(work, 'build'),
               '--specpath', work] + add_data + [entry]
        status = subprocess.call(cmd)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    if status:
        return status
    exe = os.path.join(os.path.abspath(args.dist),
                       args.onedir and os.path.join('dnuos', 'dnuos.exe')
                       or 'dnuos.exe')
    # Smoke test: the bundle must import the package and run
    status = subprocess.call([exe, '-V'])
    if status:
        print('error: %s -V failed with status %d' % (exe, status),
              file=sys.stderr)
        return status
    print('Built %s' % exe)
    return 0


if __name__ == '__main__':
    sys.exit(main())
