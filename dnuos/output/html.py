"""HTML renderer"""

from html import escape

import dnuos
from dnuos.misc import _
from dnuos.output import plaintext
from dnuos.output.abstract_renderer import AbstractRenderer

class Renderer(AbstractRenderer):

    def __init__(self):

        self.renderer = plaintext.Renderer()

    def __set_format_string(self, format_string):

        self.renderer.format_string = format_string
    format_string = property(fset=__set_format_string)

    def __set_columns(self, columns):

        self.renderer.columns = columns
    columns = property(fset=__set_columns)

    def render(self, dir_pairs, options, data):
        """Render directories as HTML to stdout.

        Directories are rendered like in plain text, but with HTML header
        and footer.
        """

        yield """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"
"http://www.w3.org/TR/html4/strict.dtd">
<html lang="%s">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<meta name="generator" content="Dnuos %s">
<title>%s</title>
<style type="text/css">
body { color: %s; background: %s; }
/* Monospace fonts with wide script coverage, so characters aren't borrowed
   from proportional fonts (which breaks column alignment). */
pre { font-family: "Cascadia Mono", Consolas, "MS Gothic", "Noto Sans Mono CJK JP",
      "Noto Sans Mono", "DejaVu Sans Mono", Menlo, monospace; }
</style>
</head>
<body>
<pre>""" % (_('en'), dnuos.__version__, _('Music List'),
            options.text_color, options.bg_color)

        for chunk in self.renderer.render(dir_pairs, options, data):
            yield escape(chunk, quote=False)

        yield """</pre>
</body>
</html>"""
