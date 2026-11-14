"""
>>> test()
"""

import os
import subprocess
import sys

import dnuos

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(dnuos.__file__)))
SCRIPT = os.path.join(ROOT, 'scripts', 'dnuos')


def _run(*args):
    # The script lives in scripts/, so point it at this copy of the package
    env = dict(os.environ, PYTHONPATH=ROOT)
    proc = subprocess.Popen([sys.executable, SCRIPT] + list(args), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.communicate()
    return proc.returncode


def test():
    """Verify the dnuos script passes on the exit status of main()"""

    assert _run('--version') == 0
    assert _run('--help') == 0
    # Bad usage and a missing directory both exit with status 2
    assert _run('--no-such-option') == 2
    assert _run(os.path.join(os.path.dirname(SCRIPT), 'no', 'such', 'dir')) == 2
