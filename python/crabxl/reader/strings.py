# Copyright (c) 2010-2024 openpyxl
"""Explicit shared-string XML projections using the canonical native run codec."""

from .._native import rich_text_from_xml
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


def read_string_table(xml_source):
    """Read all shared strings as plain text, leaving caller streams open."""
    return [str(value).replace("x005F_", "") for value in _strings(xml_source, False)]


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
