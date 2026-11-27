"""Retain opaque XML while applying edits to exposed metadata descriptors."""

from collections import defaultdict
from copy import deepcopy
from io import BytesIO
from xml.etree import ElementTree as ET
from xml.sax.saxutils import XMLGenerator
from xml.sax.xmlreader import AttributesImpl

from .functions import tostring


def _group(nodes):
    result = defaultdict(list)
    for node in nodes:
        result[node.tag].append(node)
    return result


def _merge_descriptor(original, before, after):
    """Apply descriptor edits to fresh XML, retaining opaque and native changes."""
    if original is None:
        return deepcopy(after)
    result = deepcopy(original)
    for name in before.attrib.keys() | after.attrib.keys():
        if before.get(name) == after.get(name):
            continue
        result.attrib.pop(name, None)
        if name in after.attrib:
            result.set(name, after.get(name))
    if before.text != after.text:
        result.text = after.text
    if [tostring(node) for node in before] == [tostring(node) for node in after]:
        return result
    prior, desired = _group(before), _group(after)
    tags = prior.keys() | desired.keys()
    existing = [node for node in result if node.tag in tags]
    fresh = _group(existing)
    position = list(result).index(existing[0]) if existing else len(result)
    for node in existing:
        result.remove(node)
    unchanged = {
        tag: [tostring(item) for item in prior[tag]]
        == [tostring(item) for item in desired[tag]]
        for tag in tags
    }
    offsets = defaultdict(int)
    for node in after:
        tag, index = node.tag, offsets[node.tag]
        offsets[tag] += 1
        old = fresh[tag][index] if index < len(fresh[tag]) else None
        base = prior[tag][index] if index < len(prior[tag]) else None
        if unchanged[tag]:
            merged = deepcopy(old) if old is not None else None
        else:
            merged = (
                _merge_descriptor(old, base, node)
                if base is not None
                else deepcopy(node)
            )
        if merged is not None:
            result.insert(position, merged)
            position += 1
        if unchanged[tag] and offsets[tag] == len(desired[tag]):
            for extra in fresh[tag][offsets[tag] :]:
                result.insert(position, deepcopy(extra))
                position += 1
    return result




class _NamespaceElement(ET.Element):
    __slots__ = ("_ns_bindings",)

    def __deepcopy__(self, memo):
        result = type(self)(self.tag, deepcopy(self.attrib, memo))
        memo[id(self)] = result
        result.text, result.tail = self.text, self.tail
        result._ns_bindings = dict(self._ns_bindings) if self._ns_bindings else None
        result.extend(deepcopy(child, memo) for child in self)
        return result


class _NamespaceBuilder(ET.TreeBuilder):
    def __init__(self):
        super().__init__(element_factory=_NamespaceElement, insert_comments=True, insert_pis=True)
        self.pending = {}

    def start_ns(self, prefix, uri):
        self.pending[prefix or ""] = uri

    def start(self, tag, attrs):
        node = super().start(tag, attrs)
        node._ns_bindings = self.pending or None
        self.pending = {}
        return node


def preserving_fromstring(value):
    return ET.fromstring(value, parser=ET.XMLParser(target=_NamespaceBuilder()))


def inherit_namespace_context(child, parent):
    bindings = dict(getattr(parent, "_ns_bindings", None) or {})
    bindings.update(getattr(child, "_ns_bindings", None) or {})
    child._ns_bindings = bindings


def preserving_tostring(root):
    """Keep lexical QName values valid without a process-global prefix registry."""
    output = BytesIO()
    writer = XMLGenerator(output, encoding="utf-8")

    def emit(node, inherited):
        if node.tag is ET.Comment:
            output.write(("<!--" + (node.text or "") + "-->").encode("utf-8"))
        elif node.tag is ET.ProcessingInstruction:
            target, _, data = (node.text or "").partition(" ")
            writer.processingInstruction(target, data)
        else:
            bindings = dict(inherited)
            attrs = {}
            declared = dict(getattr(node, "_ns_bindings", None) or {})
            for name, value in node.attrib.items():
                if isinstance(name, str) and name == "xmlns":
                    declared[""] = value
                elif isinstance(name, str) and name.startswith("xmlns:"):
                    declared[name[6:]] = value
            for prefix, uri in declared.items():
                if bindings.get(prefix) != uri:
                    attrs["xmlns:" + prefix if prefix else "xmlns"] = uri
                    bindings[prefix] = uri

            def qualified(name, attribute=False):
                if isinstance(name, ET.QName):
                    name = name.text
                if not name.startswith("{"):
                    return name
                uri, local = name[1:].rsplit("}", 1)
                matches = [prefix for prefix, value in bindings.items() if value == uri and (prefix or not attribute)]
                if matches:
                    prefix = "" if "" in matches else matches[0]
                else:
                    index = 0
                    while f"ns{index}" in bindings:
                        index += 1
                    prefix = f"ns{index}"
                    bindings[prefix] = uri
                    attrs["xmlns:" + prefix] = uri
                return prefix + ":" + local if prefix else local

            tag = qualified(node.tag)
            for name, value in node.attrib.items():
                if isinstance(name, str) and (name == "xmlns" or name.startswith("xmlns:")):
                    continue
                key = qualified(name, attribute=True)
                attrs[key] = qualified(value, attribute=True) if isinstance(value, ET.QName) else value
            writer.startElement(tag, AttributesImpl(attrs))
            if node.text:
                writer.characters(node.text)
            for child in node:
                emit(child, bindings)
            writer.endElement(tag)
        if node.tail:
            writer.characters(node.tail)

    emit(root, {"xml": "http://www.w3.org/XML/1998/namespace"})
    writer.endDocument()
    return output.getvalue()
