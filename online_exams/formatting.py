"""Escaped lightweight text formatting and local, native MathML (no CDN)."""
import re
from xml.etree import ElementTree

from django.utils.html import escape
from django.utils.safestring import mark_safe
from latex2mathml.converter import convert
from latex2mathml import exceptions as math_errors

MATH_ERRORS = tuple(value for value in vars(math_errors).values()
                    if isinstance(value, type) and issubclass(value, Exception))


def math_markup(source):
    markup = convert(source)
    root = ElementTree.fromstring(markup)
    # Allow only MathML, with no links, styles or executable/event attributes.
    for element in root.iter():
        if not element.tag.startswith("{http://www.w3.org/1998/Math/MathML}"):
            raise ValueError("invalid math namespace")
        if element.tag.split("}")[-1] not in {
                "math", "mrow", "mi", "mn", "mo", "mtext", "ms", "mspace", "mtable", "mtr", "mtd",
                "mfrac", "msqrt", "mroot", "msub", "msup", "msubsup", "mover", "munder", "munderover",
                "mfenced", "menclose", "mpadded", "mphantom", "mstyle", "merror", "mmultiscripts",
                "mprescripts", "none"}:
            raise ValueError("invalid math element")
        for key in list(element.attrib):
            if key not in {"display", "mathvariant", "stretchy", "fence", "separator",
                           "accent", "accentunder", "columnalign", "rowalign", "columnspacing",
                           "rowspacing", "linethickness", "notation", "lspace", "rspace",
                           "width", "height", "depth", "movablelimits", "displaystyle",
                           "scriptlevel", "form", "maxsize", "minsize"}:
                del element.attrib[key]
    return ElementTree.tostring(root, encoding="unicode").replace("ns0:", "").replace(":ns0", "")


def render_text(value):
    pieces = re.split(r"(\\\(.*?\\\))", str(value), flags=re.S)
    output = []
    for piece in pieces:
        if piece.startswith(r"\(") and piece.endswith(r"\)"):
            try:
                output.append(math_markup(piece[2:-2]))
            except (*MATH_ERRORS, ValueError, KeyError, IndexError, RecursionError, ElementTree.ParseError):
                output.append(str(escape(piece)))
        else:
            text = str(escape(piece))
            text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
            text = re.sub(r"__(.+?)__", r"<em>\1</em>", text)
            output.append(text.replace("\n", "<br>"))
    return mark_safe("".join(output))
