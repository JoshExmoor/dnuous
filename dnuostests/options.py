"""
>>> test()
"""

import io
import os
import sys

import dnuos.output.html
from dnuos.conf import parse_args


class Stream(io.StringIO):
    """A StringIO that can claim to be a terminal"""

    def __init__(self, tty=False):
        super().__init__()
        self.tty = tty

    def isatty(self):
        return self.tty


def run(args, stdout_tty=False, stderr_tty=False):
    """parse_args() with fake streams. Returns (options or exit code,
    stdout text, stderr text)."""

    old = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = Stream(stdout_tty), Stream(stderr_tty)
    try:
        try:
            result = parse_args(['dnuos'] + args)
        except SystemExit as e:
            result = e.code or 0
        return result, sys.stdout.getvalue(), sys.stderr.getvalue()
    finally:
        sys.stdout, sys.stderr = old


def test():
    """Verify argument parsing and when progress is shown"""

    data = os.environ['DATA_DIR']
    a, b = os.path.join(data, 'aac'), os.path.join(data, 'lame')

    # Combined short flags, options after and between directories, and
    # shortened long option names all work as they did with optparse
    opts = run(['-qi', a])[0]
    assert opts.show_progress is False and opts.sort_cmp is not None
    opts = run([a, '-q', b, '--disable'])[0]
    assert opts.basedirs == [os.path.abspath(a), os.path.abspath(b)]
    assert opts.use_cache is False and opts.show_progress is False
    opts = run(['-b', '192', '-P', '1', '-I3', '--template=html', a])[0]
    assert opts.mp3_min_bit_rate == 192000 and opts.prefer_tag == 1
    assert opts.indent == 3 and opts.output_module is dnuos.output.html

    # Bad values and unknown options are usage errors (exit status 2)
    for args, message in [(['--template', 'xml', a], 'Unknown template xml'),
                          (['--template', 'abstract_renderer', a],
                           'Unknown template abstract_renderer'),
                          (['-b', '999', a], 'Bitrate must be 0'),
                          (['-b', 'x', a], "invalid int value: 'x'"),
                          (['--no-such-option', a], 'unrecognized arguments'),
                          (['--ignore', a], 'ambiguous option'),
                          ([], 'No folders to process')]:
        code, out, err = run(args)
        assert code == 2, (args, code)
        assert message in err, (args, err)

    # Help exits successfully and lists the templates
    code, out, err = run(['-h'])
    assert code == 0 and 'plaintext, html, db' in out, out
    assert out.startswith('usage: dnuos [options] basedir ...'), out

    # Progress only appears when stderr is an interactive terminal, and not
    # when the listing goes to that same terminal
    def progress(args, stdout_tty, stderr_tty):
        return run(args + [a], stdout_tty, stderr_tty)[0].show_progress

    assert progress([], False, True) is True          # dnuos DIR > list.txt
    assert progress(['-f', 'out.txt'], True, True) is True
    assert progress([], True, True) is False          # listing on terminal
    assert progress([], False, False) is False        # stderr redirected
    assert progress(['-f', 'out.txt'], True, False) is False
    assert progress(['-q'], False, True) is False
    assert progress(['--debug'], False, True) is False
