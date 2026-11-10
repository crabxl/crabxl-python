"""Opaque metadata must keep lexical QName bindings as well as attribute values."""

from copy import deepcopy
from xml.etree import ElementTree as ET

from crabxl.xml._preserve import (
    _merge_descriptor,
    inherit_namespace_context,
    preserving_fromstring,
    preserving_tostring,
)


def test_descriptor_edits_keep_unused_prefixes_shadowing_comments_and_instructions():
    source = preserving_fromstring(
        b'<root xmlns:p="urn:one" xmlns:t="urn:types" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        b'value="p:Root" xsi:type="t:Root"><known value="old"/>tail'
        b'<p:child xmlns:p="urn:two" value="p:Child"/><!--keep--><?probe data?></root>'
    )
    before = ET.fromstring('<root><known value="old"/></root>')
    after = ET.fromstring('<root><known value="new"/></root>')
    result = _merge_descriptor(source, before, after)
    encoded = preserving_tostring(result)
    checked = preserving_fromstring(encoded)
    assert checked._ns_bindings["p"] == "urn:one"
    assert checked._ns_bindings["t"] == "urn:types"
    assert checked.get("value") == "p:Root"
    assert checked.get("{http://www.w3.org/2001/XMLSchema-instance}type") == "t:Root"
    assert checked[0].get("value") == "new"
    assert checked[0].tail == "tail"
    assert checked[1].tag == "{urn:two}child"
    assert checked[1]._ns_bindings["p"] == "urn:two"
    assert checked[1].get("value") == "p:Child"
    assert b"<!--keep-->" in encoded
    assert b"<?probe data?>" in encoded
    assert source[0].get("value") == "old"


def test_extracted_and_copied_metadata_keeps_parent_namespace_context():
    source = preserving_fromstring(
        b'<root xmlns:t="urn:types"><child value="t:Thing"/></root>'
    )
    inherit_namespace_context(source[0], source)
    copied = deepcopy(source[0])
    checked = preserving_fromstring(preserving_tostring(copied))
    assert checked._ns_bindings["t"] == "urn:types"
    assert checked.get("value") == "t:Thing"


def test_new_qname_values_and_escaped_text_are_serialized_with_valid_bindings():
    root = ET.Element(
        "{urn:main}root",
        {
            "type": ET.QName("urn:types", "Thing"),
            "quoted": 'A & "B"',
            ET.QName("urn:attrs", "field"): "kept",
        },
    )
    root.text = "Unicode 中文 <&>"
    checked = preserving_fromstring(preserving_tostring(root))
    prefix, local = checked.get("type").split(":")
    assert checked._ns_bindings[prefix] == "urn:types"
    assert local == "Thing"
    assert checked.get("quoted") == 'A & "B"'
    assert checked.text == "Unicode 中文 <&>"
    assert checked.get("{urn:attrs}field") == "kept"
