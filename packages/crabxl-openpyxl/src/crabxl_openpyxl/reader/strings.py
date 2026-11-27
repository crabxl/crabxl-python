# Copyright (c) 2010-2024 openpyxl
"""Explicit shared-string XML projections using the canonical native run codec."""

import re

from crabxl_bindings._native import rich_text_from_xml

from ..cell.rich_text import CellRichText
from ..xml.constants import SHEET_MAIN_NS
from ..xml.functions import iterparse, tostring


def _strings(xml_source, rich):
    root = None
    for event, node in iterparse(xml_source, events=("start", "end")):
        if root is None:
            root = node
        if event == "end" and node.tag == f"{{{SHEET_MAIN_NS}}}si":
            node.tail = None
            value = CellRichText._from_native(
                rich_text_from_xml(tostring(node), unprotect=rich)
            )
            node.clear()
            root.remove(node)
            yield value


_ESCAPE = re.compile(
    r"_x([Dd][89ABab][0-9A-Fa-f]{2})__x([Dd][C-Fc-f][0-9A-Fa-f]{2})_|_x([0-9A-Fa-f]{4})_"
)


def _escaped(match):
    if match.group(1):
        pair = int(match.group(1), 16), int(match.group(2), 16)
        return chr(0x10000 + ((pair[0] - 0xD800) << 10) + pair[1] - 0xDC00)
    unit = int(match.group(3), 16)
    # A lone surrogate stays literal, as in the native reader.
    return match.group(0) if 0xD800 <= unit < 0xE000 else chr(unit)


def read_string_table(xml_source):
    """Read all shared strings as plain text, leaving caller streams open.

    Excel's _xHHHH_ escapes are decoded, as Excel does (openpyxl #2328)."""
    return [_ESCAPE.sub(_escaped, str(value)) for value in _strings(xml_source, False)]


def read_rich_text(xml_source):
    """Read all shared strings, retaining formatted runs when present."""
    strings = []
    for value in _strings(xml_source, True):
        if not value:
            value = ""
        elif len(value) == 1 and isinstance(value[0], str):
            value = value[0]
        strings.append(value)
    return strings
