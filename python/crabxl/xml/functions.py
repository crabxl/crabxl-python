# Adapted from openpyxl 3.1.5 (MIT, Copyright (c) 2010 openpyxl); see third_party/licenses/openpyxl-MIT.txt.
"""XML helpers on the standard library ElementTree."""

import re
from xml.etree.ElementTree import (
    Element,
    SubElement,
    QName,
    fromstring,
    tostring,
    register_namespace,
)

from .constants import (
    CHART_NS,
    DRAWING_NS,
    SHEET_DRAWING_NS,
    CHART_DRAWING_NS,
    SHEET_MAIN_NS,
    REL_NS,
    VML_NS,
    COMMENTS_NS,
)

NS_REGEX = re.compile("({(?P<namespace>.*)})?(?P<localname>.*)")


def localname(node):
    if callable(node.tag):
        return "comment"
    m = NS_REGEX.match(node.tag)
    return m.group("localname")


def whitespace(node):
    if node.text != node.text.strip():
        node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
