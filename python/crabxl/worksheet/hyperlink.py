"""Live hyperlink views over canonical point metadata."""

from weakref import WeakKeyDictionary
from xml.etree.ElementTree import Element

from .._values import _letters

_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


class Hyperlink:
    tagname = "hyperlink"
    __attrs__ = ("ref", "location", "tooltip", "display", "id")

    def __init__(
        self, ref=None, location=None, tooltip=None, display=None, id=None, target=None
    ):
        self._bindings = WeakKeyDictionary()
        self._stream_bindings = WeakKeyDictionary()
        self.ref = ref
        self.location = location
        self.tooltip = tooltip
        self.display = display
        self.id = id
        self.target = target

    def __setattr__(self, name, value):
        if name == "ref":
            if not isinstance(value, str):
                raise TypeError("Hyperlink ref must be a string")
        elif name in ("location", "tooltip", "display", "id", "target"):
            if value is not None and not isinstance(value, str):
                raise TypeError(f"Hyperlink {name} must be a string or None")
        else:
            object.__setattr__(self, name, value)
            return
        previous = getattr(self, name, None)
        object.__setattr__(self, name, value)
        try:
            self._sync()
        except BaseException:
            object.__setattr__(self, name, previous)
            raise

    def _fields(self, owner=None):
        reference = None if owner == self.ref else self.ref
        return (
            self.target,
            self.location,
            self.tooltip,
            self.display,
            self.id,
            reference,
        )

    def _sync(self):
        committed = []
        try:
            for sheet, coordinates in list(self._bindings.items()):
                for row, column in tuple(coordinates):
                    if sheet._hyperlink_views.get((row, column)) is not self:
                        coordinates.discard((row, column))
                        continue
                    native = sheet._model()
                    previous = native.hyperlink(row - 1, column - 1)
                    native.update_hyperlink(
                        row - 1, column - 1, self._fields(f"{_letters(column)}{row}")
                    )
                    committed.append(
                        (native.update_hyperlink, (row - 1, column - 1), previous)
                    )
            for workbook, group in list(self._stream_bindings.items()):
                if workbook._saved or workbook._closed:
                    del self._stream_bindings[workbook]
                    continue
                native = workbook._stream_writer
                previous = native.hyperlink(group)
                native.update_hyperlink(group, self._fields())
                committed.append((native.update_hyperlink, (group,), previous))
        except BaseException:
            for update, arguments, previous in reversed(committed):
                update(*arguments, previous)
            raise

    def _bind_stream(self, workbook, coordinate):
        previous = self.ref
        self.ref = coordinate
        try:
            group = self._stream_bindings.get(workbook)
            if group is None:
                group = workbook._stream_writer.register_hyperlink(self._fields())
                self._stream_bindings[workbook] = group
            workbook._stream_links[group] = self
            return group
        except BaseException:
            self.ref = previous
            raise

    def _bind(self, sheet, row, column):
        coordinate = f"{sheet.cell(row, column).column_letter}{row}"
        previous = self.ref
        native = sheet._model()
        object.__setattr__(self, "ref", coordinate)
        try:
            self._sync()
            native.set_hyperlink(row - 1, column - 1, self._fields(coordinate))
        except BaseException:
            object.__setattr__(self, "ref", previous)
            self._sync()
            raise
        self._bindings.setdefault(sheet, set()).add((row, column))
        sheet._hyperlink_views[row, column] = self
        return self

    def __copy__(self):
        return type(self)(
            ref=self.ref,
            location=self.location,
            tooltip=self.tooltip,
            display=self.display,
            id=self.id,
            target=self.target,
        )

    def __eq__(self, other):
        return isinstance(other, Hyperlink) and all(
            getattr(self, name) == getattr(other, name) for name in self.__attrs__
        )

    def __iter__(self):
        return (
            (name, getattr(self, name))
            for name in self.__attrs__
            if getattr(self, name) is not None
        )

    def to_tree(self, tagname=None, idx=None, namespace=None):
        tag = tagname or self.tagname
        element = Element(f"{{{namespace}}}{tag}" if namespace else tag)
        for name in self.__attrs__:
            value = getattr(self, name)
            if value is not None:
                element.set(f"{{{_REL}}}id" if name == "id" else name, value)
        return element

    @classmethod
    def from_tree(cls, node):
        if node.tag not in (cls.tagname, f"{{{_MAIN}}}{cls.tagname}"):
            raise ValueError("Expected a hyperlink element")
        fields = dict(node.attrib)
        if f"{{{_REL}}}id" in fields:
            fields["id"] = fields.pop(f"{{{_REL}}}id")
        if list(node):
            raise NotImplementedError("Hyperlink child elements are not implemented")
        return cls(**fields)


class HyperlinkList:
    tagname = "hyperlinks"
    __attrs__ = ()

    def __init__(self, hyperlink=()):
        self.hyperlink = hyperlink

    @property
    def hyperlink(self):
        return self._hyperlinks

    @hyperlink.setter
    def hyperlink(self, value):
        if not isinstance(value, (list, tuple)):
            raise TypeError("HyperlinkList hyperlink must be a list or tuple")
        if any(not isinstance(item, Hyperlink) for item in value):
            raise TypeError("HyperlinkList entries must be Hyperlink objects")
        self._hyperlinks = list(value)

    def to_tree(self, tagname=None, idx=None, namespace=None):
        tag = tagname or self.tagname
        node = Element(f"{{{namespace}}}{tag}" if namespace else tag)
        node.extend(item.to_tree(namespace=namespace) for item in self.hyperlink)
        return node

    @classmethod
    def from_tree(cls, node):
        if node.tag not in (cls.tagname, f"{{{_MAIN}}}{cls.tagname}"):
            raise ValueError("Expected a hyperlinks element")
        if node.attrib:
            raise NotImplementedError("HyperlinkList attributes are not implemented")
        return cls([Hyperlink.from_tree(child) for child in node])
