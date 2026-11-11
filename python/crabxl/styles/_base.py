"""Small public style values; workbook ownership and interning stay in Rust."""

from copy import copy
from functools import cache

from .._native import make_style_component


class StyleValue:
    _fields = ()
    _aliases = {}
    _children = ()

    def __repr__(self):
        from .differential import _convert

        value = _convert(self)
        result = repr(value).replace(
            f"<{value.__module__}.{type(value).__name__} object>",
            f"<{self.__module__}.{type(self).__name__} object>",
            1,
        )
        return result.replace("crabxl.styles._x.", "crabxl.styles.")

    def __iter__(self):
        from .differential import _convert

        return iter(_convert(self))

    def to_tree(self, tagname=None, idx=None, namespace=None):
        from .differential import _convert

        options = {"tagname": tagname, "idx": idx, "namespace": namespace}
        return _convert(self).to_tree(
            **{key: value for key, value in options.items() if value is not None}
        )

    @classmethod
    def from_tree(cls, node):
        from . import _x

        target = _x.fills.Stop if cls.__name__ == "Stop" else getattr(_x, cls.__name__)
        return _from_xml_style(target.from_tree(node))

    def __setattr__(self, name, value):
        name = self._aliases.get(name, name)
        if name not in self._fields:
            raise AttributeError(name)
        old = getattr(self, name, None)
        object.__setattr__(self, name, value)
        object.__setattr__(self, "_revision", getattr(self, "_revision", 0) + 1)
        if getattr(self, "_listeners", None):
            from ..cell.rich_text import _notify

            try:
                _notify(self)
            except BaseException:
                object.__setattr__(self, name, old)
                object.__setattr__(self, "_revision", self._revision + 1)
                raise

    def __getattr__(self, name):
        if name in self._aliases:
            return getattr(self, self._aliases[name])
        raise AttributeError(name)

    def __eq__(self, other):
        if isinstance(other, StyleProxy):
            other = other._target
        if type(other).__module__.startswith("crabxl.styles._x."):
            from .differential import _convert

            return _convert(self) == other
        if type(self) is not type(other):
            return False
        if getattr(self, "_component", None) == "alignment":
            return dict(self) == dict(other)
        return all(getattr(self, name) == getattr(other, name) for name in self._fields)

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
        raise AttributeError(
            "Style objects are immutable and cannot be changed.Reassign the style with a copy"
        )

    def __copy__(self):
        return copy(self._target)

    def __repr__(self):
        return repr(self._target)

    def __add__(self, other):
        return self._target + other

    def __eq__(self, other):
        return self._target == other

    __hash__ = None


def _from_xml_style(value):
    from . import (
        Alignment,
        Border,
        Color,
        Font,
        GradientFill,
        PatternFill,
        Protection,
        Side,
        _x,
    )
    from .fills import Stop

    if isinstance(value, _x.Color):
        return Color(tint=value.tint, **{value.type: value.value})
    classes = {
        cls.__name__: cls
        for cls in (
            Alignment,
            Border,
            Font,
            GradientFill,
            PatternFill,
            Protection,
            Side,
            Stop,
        )
    }
    target = classes.get(type(value).__name__)
    if target is not None:
        return target(
            **{
                field: _from_xml_style(getattr(value, field))
                for field in target._fields
                # The XML descriptor omits the vestigial mergeCell argument.
                if field != "mergeCell"
            }
        )
    if isinstance(value, (list, tuple)):
        return [_from_xml_style(item) for item in value]
    return value


def color_from_native(values):
    """Materialize a validated native color without repeating input validation."""
    from .colors import Color

    if values is None:
        return None
    result = Color.__new__(Color)
    result.__dict__.update(values)
    return result


def font_from_native(values, font_type=None):
    """Share trusted component/run conversion while preserving public defaults."""
    from .fonts import Font

    if font_type is None:
        font_type = Font
    result = font_type.__new__(font_type)
    result.__dict__.update(values)
    object.__setattr__(result, "b", bool(values["b"]))
    object.__setattr__(result, "i", bool(values["i"]))
    object.__setattr__(result, "color", color_from_native(values["color"]))
    return result


def component(name, values):
    """Decode a borrowed native component into a small public value."""
    from . import (
        Alignment,
        Border,
        GradientFill,
        PatternFill,
        Protection,
        Side,
    )
    from .fills import Stop

    def decode_color(item):
        return color_from_native(item)

    values = dict(values)
    if name == "font":
        return font_from_native(values)
    if name == "border":
        for field in ("diagonalUp", "diagonalDown", "outline"):
            if values[field] is None:
                del values[field]
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


@cache
def _style_types(expected):
    """Resolve style class names, such as "Font" or ("PatternFill", "GradientFill")."""
    from .. import styles

    if isinstance(expected, str):
        return getattr(styles, expected)
    return tuple(getattr(styles, item) for item in expected)


def cell_component(name, expected):
    """A cell style property. `expected` names the accepted style classes."""

    def get(cell):
        if cell._detached is not None:
            values = cell._detached[4] if len(cell._detached) > 4 else {}
            kinds = _style_types(expected)
            value = values.get(name) or (
                kinds[0]() if isinstance(kinds, tuple) else kinds()
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
        if not isinstance(value, _style_types(expected)):
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
