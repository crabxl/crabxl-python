"""Small public style values; workbook ownership and interning stay in Rust."""

from copy import copy
from functools import cache

from .._native import make_style_component


class StyleValue:
    _fields = ()
    _aliases = {}
    _children = ()
    _field_set = frozenset()
    # Class defaults keep these lookups off the raising __getattr__ path.
    _revision = 0
    _listeners = None
    _native_cache = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._field_set = frozenset(cls._fields)

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
        if name not in self._field_set:
            raise AttributeError(name)
        if not self._listeners:
            object.__setattr__(self, name, value)
            object.__setattr__(self, "_revision", self._revision + 1)
            return
        old = getattr(self, name, None)
        object.__setattr__(self, name, value)
        object.__setattr__(self, "_revision", self._revision + 1)
        if self._listeners:
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
        revision = self._revision
        if not self._children:
            return revision
        return (
            revision,
            *(_value_signature(getattr(self, name)) for name in self._children),
        )

    def _native(self):
        key = self._signature()
        cached = self._native_cache
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


@cache
def _classes():
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

    return (
        Alignment,
        Border,
        Color,
        Font,
        GradientFill,
        PatternFill,
        Protection,
        Side,
        Stop,
    )


def _trusted(cls, values):
    """Build a style value from validated native fields, skipping the setters."""
    result = cls.__new__(cls)
    result.__dict__.update(values)
    return result


def color_from_native(values):
    """Materialize a validated native color without repeating input validation."""
    return None if values is None else _trusted(_classes()[2], values)


def _color_or_default(values):
    if values is None:
        values = {"type": "rgb", "value": "00000000", "tint": 0.0}
    return _trusted(_classes()[2], values)


def font_from_native(values, font_type=None):
    """Share trusted component/run conversion while preserving public defaults."""
    result = _trusted(font_type or _classes()[3], values)
    result.__dict__.update(
        b=bool(values["b"]),
        i=bool(values["i"]),
        color=color_from_native(values["color"]),
    )
    return result


def component(name, values):
    """Decode a native component into a small public value."""
    Alignment, Border, _, _, GradientFill, PatternFill, Protection, Side, Stop = (
        _classes()
    )
    if name == "font":
        return font_from_native(values)
    values = dict(values)
    if name == "border":
        # The same defaults as Border().
        for field, default in (
            ("diagonalUp", False),
            ("diagonalDown", False),
            ("outline", True),
        ):
            if values[field] is None:
                values[field] = default
        for edge in Border._children:
            item = values[edge]
            if item is not None:
                values[edge] = _trusted(
                    Side,
                    {"style": item["style"], "color": color_from_native(item["color"])},
                )
        return _trusted(Border, values)
    if name == "fill":
        if "patternType" in values:
            # The same defaults as PatternFill().
            values["fgColor"] = _color_or_default(values["fgColor"])
            values["bgColor"] = _color_or_default(values["bgColor"])
            return _trusted(PatternFill, values)
        values["stop"] = [
            Stop(color_from_native(item["color"]), item["position"])
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
        return _trusted(Alignment, values)
    if name == "protection":
        return _trusted(Protection, values)
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
