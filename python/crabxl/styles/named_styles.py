"""Named appearance builders backed by the workbook's canonical style registry."""

from weakref import ref

from ..compat import safe_string
from ..descriptors import Bool, Integer, Sequence, String, Typed
from ..descriptors.excel import ExtensionList
from ..descriptors.serialisable import Serialisable
from .alignment import Alignment
from .borders import Border
from .cell_style import CellStyle, StyleArray
from .fills import Fill, PatternFill
from .fonts import Font
from .numbers import (
    BUILTIN_FORMATS_MAX_SIZE,
    BUILTIN_FORMATS_REVERSE,
    NumberFormatDescriptor,
)
from .protection import Protection


class NamedStyle(Serialisable):
    font = Typed(expected_type=Font)
    fill = Typed(expected_type=Fill)
    border = Typed(expected_type=Border)
    alignment = Typed(expected_type=Alignment)
    number_format = NumberFormatDescriptor()
    protection = Typed(expected_type=Protection)
    builtinId = Integer(allow_none=True)
    hidden = Bool(allow_none=True)
    name = String()

    def __init__(
        self,
        name="Normal",
        font=None,
        fill=None,
        border=None,
        alignment=None,
        number_format=None,
        protection=None,
        builtinId=None,
        hidden=False,
    ):
        self._owner = None
        self._registered_name = None
        self._style = StyleArray()
        self.name = name
        self.font = font if font is not None else Font()
        self.fill = fill if fill is not None else PatternFill()
        self.border = border if border is not None else Border()
        self.alignment = alignment if alignment is not None else Alignment()
        self.number_format = number_format or "General"
        self.protection = protection if protection is not None else Protection()
        self.builtinId = builtinId
        self.hidden = bool(hidden)

    def __copy__(self):
        from copy import copy

        result = type(self)(
            name=self.name, number_format=self.number_format,
            builtinId=self.builtinId, hidden=self.hidden,
            **{name: copy(getattr(self, name)) for name in ("font", "fill", "border", "alignment", "protection")},
        )
        result._style = copy(self._style)
        return result

    def __deepcopy__(self, memo):
        from copy import deepcopy

        result = type(self)(name=self.name, number_format=self.number_format,
                            builtinId=self.builtinId, hidden=self.hidden)
        memo[id(self)] = result
        for name in ("font", "fill", "border", "alignment", "protection", "_style"):
            setattr(result, name, deepcopy(getattr(self, name), memo))
        return result

    def __setattr__(self, name, value):
        if name == "name" and (not isinstance(value, str) or not value):
            raise ValueError("Named style requires a nonempty name")
        if name == "number_format" and value is None:
            value = "General"
        if name == "number_format" and not isinstance(value, str):
            raise TypeError("Number format must be a string")
        owner = getattr(self, "_owner", None)
        if owner is not None and name in ("name", "hidden", "builtinId"):
            previous = getattr(self, name)
            object.__setattr__(self, name, value)
            workbook = owner()
            if workbook is not None:
                try:
                    if self._registered_name is None:
                        return
                    workbook._style_owner().update_named_style_metadata(
                        self._registered_name,
                        self.name,
                        self.builtinId,
                        bool(self.hidden),
                    )
                except Exception:
                    object.__setattr__(self, name, previous)
                    raise
                object.__setattr__(self, "_registered_name", self.name)
            return
        if owner is not None and name in (
            "font",
            "fill",
            "border",
            "alignment",
            "number_format",
            "protection",
        ):
            previous = getattr(self, name)
            object.__setattr__(self, name, value)
            workbook = owner()
            if workbook is not None:
                try:
                    if self._registered_name is None:
                        self._recalculate()
                    else:
                        workbook._style_owner().add_named_style(self._native(), update=True)
                        self._recalculate()
                except Exception:
                    object.__setattr__(self, name, previous)
                    raise
            return
        object.__setattr__(self, name, value)

    def __iter__(self):
        for key in ('name', 'builtinId', 'hidden', 'xfId'):
            value = getattr(self, key, None)
            if value is not None:
                yield key, safe_string(value)


    def as_tuple(self):
        """Return a style array representing the current style"""
        return self._style


    def as_xf(self):
        """
        Return equivalent XfStyle
        """
        xf = CellStyle.from_array(self._style)
        xf.xfId = None
        xf.pivotButton = None
        xf.quotePrefix = None
        if self.alignment != Alignment():
            xf.alignment = self.alignment
        if self.protection != Protection():
            xf.protection = self.protection
        return xf


    def as_name(self):
        """
        Return relevant named style

        """
        named = _NamedCellStyle(
            name=self.name,
            builtinId=self.builtinId,
            hidden=self.hidden,
            xfId=self._style.xfId
        )
        return named


    @property
    def _wb(self):
        return None if self._owner is None else self._owner()

    def bind(self, workbook):
        previous = self._owner
        previous_name = self._registered_name
        self._owner = ref(workbook)
        self._registered_name = None
        try:
            self._recalculate()
        except Exception:
            self._owner = previous
            self._registered_name = previous_name
            raise

    def _recalculate(self):
        workbook = self._wb
        if workbook is None:
            return
        if hasattr(workbook, "_style_owner"):
            values = workbook._style_owner().prepare_named_style(self._native())
            values[8] = self._style.xfId
            self._style = StyleArray(values)
            return
        for field, collection, key in (
            ("font", "_fonts", "fontId"), ("fill", "_fills", "fillId"),
            ("border", "_borders", "borderId"), ("alignment", "_alignments", "alignmentId"),
            ("protection", "_protections", "protectionId"),
        ):
            setattr(self._style, key, getattr(workbook, collection).add(getattr(self, field)))
        code = self.number_format
        if code in BUILTIN_FORMATS_REVERSE:
            self._style.numFmtId = BUILTIN_FORMATS_REVERSE[code]
        else:
            self._style.numFmtId = workbook._number_formats.add(code) + BUILTIN_FORMATS_MAX_SIZE

    def _native(self):
        return {
            "name": self.name,
            "number_format": self.number_format,
            "builtinId": self.builtinId,
            "hidden": self.hidden,
            **{
                name: getattr(self, name)._native()
                for name in ("font", "fill", "border", "alignment", "protection")
            },
        }

    def _bind(self, workbook):
        self.bind(workbook)
        self._style.xfId = workbook.named_styles.index(self.name)
        object.__setattr__(self, "_registered_name", self.name)


# Metadata containers adapted from openpyxl 3.1.5 (MIT).
# Copyright (c) 2010-2024 openpyxl
# ruff: noqa: F811
class NamedStyleList(list):
    """
    Named styles are editable and can be applied to multiple objects

    As only the index is stored in referencing objects the order mus
    be preserved.

    Returns a list of NamedStyles
    """

    def __init__(self, iterable=()):
        """
        Allow a list of named styles to be passed in and index them.
        """

        for idx, s in enumerate(iterable, len(self)):
            s._style.xfId = idx
        super().__init__(iterable)


    @property
    def names(self):
        return [s.name for s in self]


    def __getitem__(self, key):
        if isinstance(key, int):
            return super().__getitem__(key)


        for idx, name in enumerate(self.names):
            if name == key:
                return self[idx]

        raise KeyError("No named style with the name{0} exists".format(key))

    def append(self, style):
        if not isinstance(style, NamedStyle):
            raise TypeError("""Only NamedStyle instances can be added""")
        elif style.name in self.names: # hotspot
            raise ValueError("""Style {0} exists already""".format(style.name))
        style._style.xfId = (len(self))
        super().append(style)


class _NamedCellStyle(Serialisable):

    """
    Pointer-based representation of named styles in XML
    xfId refers to the corresponding CellStyleXfs

    Not used in client code.
    """

    tagname = "cellStyle"

    name = String()
    xfId = Integer()
    builtinId = Integer(allow_none=True)
    iLevel = Integer(allow_none=True)
    hidden = Bool(allow_none=True)
    customBuiltin = Bool(allow_none=True)
    extLst = Typed(expected_type=ExtensionList, allow_none=True)

    __elements__ = ()


    def __init__(self,
                 name=None,
                 xfId=None,
                 builtinId=None,
                 iLevel=None,
                 hidden=None,
                 customBuiltin=None,
                 extLst=None,
                ):
        self.name = name
        self.xfId = xfId
        self.builtinId = builtinId
        self.iLevel = iLevel
        self.hidden = hidden
        self.customBuiltin = customBuiltin


class _NamedCellStyleList(Serialisable):
    """
    Container for named cell style objects

    Not used in client code
    """

    tagname = "cellStyles"

    count = Integer(allow_none=True)
    cellStyle = Sequence(expected_type=_NamedCellStyle)

    __attrs__ = ("count",)

    def __init__(self,
                 count=None,
                 cellStyle=(),
                ):
        self.cellStyle = cellStyle


    @property
    def count(self):
        return len(self.cellStyle)


    def remove_duplicates(self):
        """
        Some applications contain duplicate definitions either by name or
        referenced style.

        As the references are 0-based indices, styles are sorted by
        index.

        Returns a list of style references with duplicates removed
        """

        def sort_fn(v):
            return v.xfId

        styles = []
        names = set()
        ids = set()

        for ns in sorted(self.cellStyle, key=sort_fn):
            if ns.xfId in ids or ns.name in names: # skip duplicates
                continue
            ids.add(ns.xfId)
            names.add(ns.name)

            styles.append(ns)

        return styles


def resolve_named_style(workbook, value):
    """Resolve public names and lazily register the standard style metadata."""
    if isinstance(value, NamedStyle):
        if value.name not in workbook.named_styles:
            workbook.add_named_style(value)
        return value.name
    if not isinstance(value, str):
        raise TypeError("Style must be a name or NamedStyle")
    if value not in workbook.named_styles:
        from copy import deepcopy

        from .builtins import styles

        if value not in styles:
            raise ValueError(f"{value} is not a known style")
        workbook.add_named_style(deepcopy(styles[value]))
    return value
