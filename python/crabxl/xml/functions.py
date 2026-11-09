# Adapted from openpyxl 3.1.5 (MIT, Copyright (c) 2010 openpyxl); see third_party/licenses/openpyxl-MIT.txt.
"""XML helpers on the standard library ElementTree."""

import re
from xml.etree.ElementTree import (
    Element,
    SubElement,
    QName,
    fromstring,
    iterparse,
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
    COREPROPS_NS,
    CUSTPROPS_NS,
    DCTERMS_NS,
    DCTERMS_PREFIX,
    VTYPES_NS,
    XML_NS,
)

for _prefix, _namespace in (
    (DCTERMS_PREFIX, DCTERMS_NS),
    ("dcmitype", "http://purl.org/dc/dcmitype/"),
    ("cp", COREPROPS_NS),
    ("c", CHART_NS),
    ("a", DRAWING_NS),
    ("s", SHEET_MAIN_NS),
    ("r", REL_NS),
    ("vt", VTYPES_NS),
    ("xdr", SHEET_DRAWING_NS),
    ("cdr", CHART_DRAWING_NS),
    ("xml", XML_NS),
    ("cust", CUSTPROPS_NS),
):
    register_namespace(_prefix, _namespace)

NS_REGEX = re.compile("({(?P<namespace>.*)})?(?P<localname>.*)")


def localname(node):
    if callable(node.tag):
        return "comment"
    m = NS_REGEX.match(node.tag)
    return m.group("localname")


def whitespace(node):
    stripped = node.text.strip()
    if stripped and node.text != stripped:
        node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
