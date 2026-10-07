"""Live sparse dimension views over canonical Rust metadata."""

from collections.abc import MutableMapping
from copy import copy
from weakref import WeakValueDictionary

from ..styles import Alignment, Border, Font, GradientFill, PatternFill, Protection
from ..styles._base import StyleProxy, component

_COMPONENTS = {
    "font": Font,
    "fill": (PatternFill, GradientFill),
    "border": Border,
    "alignment": Alignment,
    "protection": Protection,
}
_ALIASES = {"ht": "height", "outline_level": "outlineLevel", "auto_size": "bestFit"}
_DEFAULTS = {
    "hidden": False,
    "outlineLevel": 0,
    "collapsed": False,
    "thickTop": False,
    "thickBot": False,
    "bestFit": False,
    "phonetic": False,
}
_MISSING = object()


class Dimension:
    def _initialize(self, worksheet, index, metadata):
        object.__setattr__(self, "parent", worksheet)
        object.__setattr__(self, "_index", index)
        object.__setattr__(self, "_holder", None)
        object.__setattr__(self, "_pending", metadata)
        object.__setattr__(self, "_components", {})

    @classmethod
    def _live(cls, holder, key):
        value = cls.__new__(cls)
        value._initialize(holder.worksheet, key, None)
        object.__setattr__(value, "_holder", holder)
        return value

    def _metadata(self):
        if self._holder is None:
            return self._pending.copy()
        return (
            self._holder._call(
                "dimension", self._holder.rows, self._holder._index(self._index)
            )
            or {}
        )

    @property
    def index(self):
        return self._index

    @property
    def style_id(self):
        return self._metadata().get("style_id") or 0

    @property
    def style(self):
        return self.style_id

    @property
    def has_style(self):
        return self.style_id != 0 or bool(self._components)

    @property
    def customFormat(self):
        return self.has_style

    @property
    def customHeight(self):
        return self.height is not None

    @property
    def customWidth(self):
        return bool(self.width)

    @property
    def number_format(self):
        if self._holder is None:
            return self._pending.get("number_format", "General")
        return self._holder._call(
            "dimension_number_format",
            self._holder.rows,
            self._holder._index(self._index),
        )

    @number_format.setter
    def number_format(self, value):
        if not isinstance(value, str):
            raise TypeError("Number format must be a string")
        if self._holder is None:
            self._pending["number_format"] = value
        else:
            self._holder._call(
                "set_dimension_number_format",
                self._holder.rows,
                self._holder._index(self._index),
                value,
            )

    def __getattr__(self, name):
        name = _ALIASES.get(name, name)
        if name in _COMPONENTS:
            value = self._components.get(name)
            if value is None:
                if self._holder is None:
                    expected = _COMPONENTS[name]
                    value = (expected[0] if isinstance(expected, tuple) else expected)()
                else:
                    value = component(
                        name,
                        self._holder._call(
                            "dimension_component",
                            self._holder.rows,
                            self._holder._index(self._index),
                            name,
                        ),
                    )
            return StyleProxy(value)
        if name in self._fields:
            value = self._metadata().get(name)
            return (
                _DEFAULTS.get(name, 13.0 if name == "width" else None)
                if value is None
                else value
            )
        raise AttributeError(name)

    def __setattr__(self, name, value):
        name = _ALIASES.get(name, name)
        if name in _COMPONENTS:
            if isinstance(value, StyleProxy):
                value = value._target
            if not isinstance(value, _COMPONENTS[name]):
                raise TypeError(f"Invalid {name} component")
            if self._holder is None:
                self._components[name] = value
            else:
                self._holder._call(
                    "set_dimension_component",
                    self._holder.rows,
                    self._holder._index(self._index),
                    value._native(),
                )
            return
        if name == "number_format":
            type(self).number_format.fset(self, value)
            return
        if name in self._fields:
            metadata = self._metadata()
            metadata[name] = value
            if name == "height":
                metadata["customHeight"] = value is not None
            if name == "width":
                metadata["customWidth"] = bool(value)
            if self._holder is None:
                self._pending.update(metadata)
            else:
                self._holder._call(
                    "set_dimension",
                    self._holder.rows,
                    self._holder._index(self._index),
                    metadata,
                )
            return
        raise AttributeError(name)


class RowDimension(Dimension):
    _fields = (
        "height",
        "hidden",
        "outlineLevel",
        "collapsed",
        "thickTop",
        "thickBot",
        "descent",
    )

    def __init__(
        self,
        worksheet,
        index=0,
        ht=None,
        customHeight=None,
        s=None,
        customFormat=None,
        hidden=False,
        outlineLevel=0,
        outline_level=None,
        collapsed=False,
        visible=None,
        height=None,
        r=None,
        spans=None,
        thickBot=None,
        thickTop=None,
        **kwargs,
    ):
        if s is not None or spans is not None or kwargs:
            raise NotImplementedError(
                "Raw row style arrays and spans are not implemented"
            )
        self._initialize(
            worksheet,
            index if r is None else r,
            {
                "height": height if height is not None else ht,
                "hidden": hidden if visible is None else not visible,
                "outlineLevel": outlineLevel
                if outline_level is None
                else outline_level,
                "collapsed": collapsed,
                "thickBot": thickBot,
                "thickTop": thickTop,
            },
        )


class ColumnDimension(Dimension):
    _fields = (
        "width",
        "hidden",
        "bestFit",
        "outlineLevel",
        "collapsed",
        "min",
        "max",
        "phonetic",
    )

    def __init__(
        self,
        worksheet,
        index="A",
        width=13,
        bestFit=False,
        hidden=False,
        outlineLevel=0,
        outline_level=None,
        collapsed=False,
        style=None,
        min=None,
        max=None,
        customWidth=False,
        visible=None,
        auto_size=None,
    ):
        if style is not None:
            raise NotImplementedError("Raw column style arrays are not implemented")
        self._initialize(
            worksheet,
            index,
            {
                "width": width,
                "customWidth": bool(width),
                "bestFit": bestFit if auto_size is None else auto_size,
                "hidden": hidden if visible is None else not visible,
                "outlineLevel": outlineLevel
                if outline_level is None
                else outline_level,
                "collapsed": collapsed,
                "min": min,
                "max": max,
            },
        )


class DimensionHolder(MutableMapping):
    def __init__(self, worksheet, rows=False, default_factory=None):
        self.worksheet, self.rows = worksheet, rows
        self.default_factory = default_factory
        self._views = WeakValueDictionary()

    def _index(self, key):
        from .. import column_index

        if self.rows:
            if not isinstance(key, int) or not 1 <= key <= 1048576:
                raise ValueError("Invalid row dimension index")
            return key - 1
        return column_index(key) - 1

    def _call(self, method, *arguments):
        self.worksheet.parent._check_open()
        if self.worksheet.parent.write_only:
            return getattr(self.worksheet.parent._stream_writer, method)(
                self.worksheet._id, *arguments
            )
        return getattr(self.worksheet._model(), method)(*arguments)

    def __getitem__(self, key):
        index = self._index(key)
        if self._call("dimension", self.rows, index) is None:
            self._call(
                "set_dimension",
                self.rows,
                index,
                {} if self.rows else {"width": 13.0, "customWidth": True},
            )
        value = self._views.get(key)
        if value is None:
            value = (RowDimension if self.rows else ColumnDimension)._live(self, key)
            self._views[key] = value
        return value

    def __setitem__(self, key, value):
        expected = RowDimension if self.rows else ColumnDimension
        if not isinstance(value, expected):
            raise TypeError(f"Expected {expected.__name__}")
        components = {name: item._native() for name, item in value._components.items()}
        metadata = value._metadata()
        number = metadata.pop("number_format", None)
        self._call("set_dimension", self.rows, self._index(key), metadata)
        for item in components.values():
            self._call("set_dimension_component", self.rows, self._index(key), item)
        if number is not None:
            self._call(
                "set_dimension_number_format", self.rows, self._index(key), number
            )
        object.__setattr__(value, "_holder", self)
        object.__setattr__(value, "_index", key)
        object.__setattr__(value, "_pending", None)
        value._components.clear()
        self._views[key] = value

    def _snapshot(self, key):
        view = self._views.get(key)
        if view is None:
            return None
        metadata = view._metadata()
        metadata["number_format"] = view.number_format
        components = {name: copy(getattr(view, name)) for name in _COMPONENTS}
        return view, metadata, components

    def _detach(self, key, snapshot):
        self._views.pop(key, None)
        if snapshot is not None:
            view, metadata, components = snapshot
            object.__setattr__(view, "_pending", metadata)
            object.__setattr__(view, "_components", components)
            object.__setattr__(view, "_holder", None)

    def __delitem__(self, key):
        snapshot = self._snapshot(key)
        if not self._call("remove_dimension", self.rows, self._index(key)):
            raise KeyError(key)
        self._detach(key, snapshot)

    def get(self, key, default=None):
        return self[key] if key in self else default

    def pop(self, key, default=_MISSING):
        if key not in self:
            if default is _MISSING:
                raise KeyError(key)
            return default
        value = self[key]
        del self[key]
        return value

    def group(self, start, end=None, outline_level=1, hidden=False):
        end = start if end is None else end
        first, last = self._index(start), self._index(end)
        if first > last:
            raise ValueError("Reversed dimension group interval")
        removed = (
            {
                key: self._snapshot(key)
                for key in list(self._views)
                if first < self._index(key) <= last
            }
            if not self.rows
            else {}
        )
        self._call("group_dimensions", self.rows, first, last, outline_level, hidden)
        for key, snapshot in removed.items():
            self._detach(key, snapshot)

    def __iter__(self):
        from .. import _letters

        return iter(
            [
                index + 1 if self.rows else _letters(index + 1)
                for index in self._call("dimension_keys", self.rows)
            ]
        )

    def __len__(self):
        return len(self._call("dimension_keys", self.rows))

    def __contains__(self, key):
        return self._call("dimension", self.rows, self._index(key)) is not None
