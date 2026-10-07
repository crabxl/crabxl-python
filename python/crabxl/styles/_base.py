"""Small public style values; workbook ownership and interning stay in Rust."""

from copy import copy

from .._native import make_style_component


class StyleValue:
    _fields = ()
    _aliases = {}
    _children = ()

    def __setattr__(self, name, value):
        name = self._aliases.get(name, name)
        if name not in self._fields:
            raise AttributeError(name)
        object.__setattr__(self, name, value)
        object.__setattr__(self, "_revision", getattr(self, "_revision", 0) + 1)

    def __getattr__(self, name):
        if name in self._aliases:
            return getattr(self, self._aliases[name])
        raise AttributeError(name)

    def __eq__(self, other):
        if isinstance(other, StyleProxy):
            other = other._target
        return type(self) is type(other) and all(
            getattr(self, name) == getattr(other, name) for name in self._fields
        )

    def __hash__(self):
        return hash(
            (type(self), *(self._hashable(getattr(self, n)) for n in self._fields))
        )

    @staticmethod
    def _hashable(value):
        return tuple(value) if isinstance(value, list) else value

    def __copy__(self):
        result = type(self).__new__(type(self))
        for name in self._fields:
            object.__setattr__(result, name, copy(getattr(self, name)))
        return result

    def _signature(self):
        revision = getattr(self, "_revision", 0)
        if not self._children:
            return revision
        return (
            revision,
            *(_value_signature(getattr(self, name)) for name in self._children),
        )

    def _native(self):
        key = self._signature()
        cached = getattr(self, "_native_cache", None)
        if cached is None or cached[0] != key:
            component_name = self._component
            cached = (key, make_style_component(component_name, self._mapping()))
            object.__setattr__(self, "_native_cache", cached)
        return cached[1]

    def _mapping(self):
        def encode(value):
            if isinstance(value, StyleValue):
                return value._mapping()
            if isinstance(value, (list, tuple)):
                return [encode(item) for item in value]
            return value

        return {name: encode(getattr(self, name)) for name in self._fields}


class StyleProxy:
    __slots__ = ("_target",)

    def __init__(self, target):
        object.__setattr__(self, "_target", target)

    def __getattr__(self, name):
        return getattr(self._target, name)

    def __setattr__(self, name, value):
        raise AttributeError("Style objects are immutable; copy and reassign the style")

    def __copy__(self):
        return copy(self._target)

    def __eq__(self, other):
        return self._target == other

    __hash__ = None


def component(name, values):
    """Decode a borrowed native component into a small public value."""
    from . import (
        Alignment,
        Border,
        Color,
        Font,
        GradientFill,
        PatternFill,
        Protection,
        Side,
    )
    from .fills import Stop

    def decode_color(item):
        if item is None:
            return None
        kind = item["type"]
        if kind == "unspecified":
            result = Color()
            result.type, result.value = kind, None
            result.tint = item["tint"]
            return result
        return Color(**{kind: item["value"]}, tint=item["tint"])

    values = dict(values)
    if name == "font":
        values["color"] = decode_color(values["color"])
        return Font(**values)
    if name == "border":
        for edge in Border._fields[:9]:
            item = values[edge]
            if item is not None:
                values[edge] = Side(
                    style=item["style"], color=decode_color(item["color"])
                )
        return Border(**values)
    if name == "fill":
        if "patternType" in values:
            for field in ("fgColor", "bgColor"):
                values[field] = decode_color(values[field])
            return PatternFill(**values)
        values["stop"] = [
            Stop(decode_color(item["color"]), item["position"])
            for item in values["stop"]
        ]
        for field in ("degree", "left", "right", "top", "bottom"):
            if values[field] is None:
                values[field] = 0
        if values["type"] is None:
            values["type"] = "linear"
        return GradientFill(**values)
    if name == "alignment":
        for field in ("textRotation", "indent", "relativeIndent", "readingOrder"):
            if values[field] is None:
                values[field] = 0
        return Alignment(**values)
    if name == "protection":
        return Protection(**values)
    raise ValueError("Unknown style component")


def cell_component(name, expected):
    def get(cell):
        if cell._detached is not None:
            values = cell._detached[4] if len(cell._detached) > 4 else {}
            value = values.get(name) or (
                expected[0]() if isinstance(expected, tuple) else expected()
            )
        else:
            value = component(
                name,
                cell.parent._model().style_component(
                    cell.row - 1, cell.column - 1, name
                ),
            )
        return StyleProxy(value)

    def set(cell, value):
        if isinstance(value, StyleProxy):
            value = value._target
        if not isinstance(value, expected):
            raise TypeError(f"Invalid {name} component")
        if cell._detached is not None:
            values = dict(cell._detached[4]) if len(cell._detached) > 4 else {}
            values[name] = copy(value)
            cell._detached = (*cell._detached[:4], values)
        else:
            cell.parent._model().set_style_component(
                cell.row - 1, cell.column - 1, name, value._native()
            )

    return property(get, set)


def _value_signature(value):
    if isinstance(value, StyleValue):
        return (id(value), value._signature())
    if isinstance(value, (list, tuple)):
        return tuple(_value_signature(item) for item in value)
    return value
