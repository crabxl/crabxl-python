# Adapted from openpyxl 3.1.5 (MIT, Copyright (c) 2010 openpyxl); see third_party/licenses/openpyxl-MIT.txt.

from crabxl.descriptors import (
    Typed,
    Sequence,
    Alias,
)
from crabxl.descriptors.serialisable import Serialisable
from crabxl.styles._x import (
    Font,
    Fill,
    Border,
    Alignment,
    Protection,
)
from ._x.numbers import NumberFormat
from . import _base
from . import _x


def _convert(value):
    """Turn a crabxl style value into its XML-serialisable counterpart."""
    if isinstance(value, _base.StyleProxy):
        value = value._target
    if not isinstance(value, _base.StyleValue):
        return value
    name = type(value).__name__
    if name == "Color":
        kind = value.type
        kwargs = {
            "rgb": {"rgb": value.value},
            "indexed": {"indexed": value.value},
            "theme": {"theme": value.value},
            "auto": {"auto": value.value},
        }[kind]
        return _x.Color(tint=value.tint, **kwargs)
    target = {"Stop": _x.fills.Stop}.get(name) or getattr(_x, name)
    kwargs = {}
    for field in value._fields:
        item = getattr(value, field)
        if isinstance(item, (list, tuple)):
            item = [_convert(v) for v in item]
        else:
            item = _convert(item)
        kwargs[field] = item
    return target(**kwargs)


class _Converting(Typed):
    def __set__(self, instance, value):
        super().__set__(instance, _convert(value))


class DifferentialStyle(Serialisable):
    tagname = "dxf"

    __elements__ = ("font", "numFmt", "fill", "alignment", "border", "protection")

    font = _Converting(expected_type=Font, allow_none=True)
    numFmt = _Converting(expected_type=NumberFormat, allow_none=True)
    fill = _Converting(expected_type=Fill, allow_none=True)
    alignment = _Converting(expected_type=Alignment, allow_none=True)
    border = _Converting(expected_type=Border, allow_none=True)
    protection = _Converting(expected_type=Protection, allow_none=True)

    def __init__(
        self,
        font=None,
        numFmt=None,
        fill=None,
        alignment=None,
        border=None,
        protection=None,
        extLst=None,
    ):
        self.font = font
        self.numFmt = numFmt
        self.fill = fill
        self.alignment = alignment
        self.border = border
        self.protection = protection
        self.extLst = extLst


class DifferentialStyleList(Serialisable):
    """
    Dedupable container for differential styles.
    """

    tagname = "dxfs"

    dxf = Sequence(expected_type=DifferentialStyle)
    styles = Alias("dxf")
    __attrs__ = ("count",)

    def __init__(self, dxf=(), count=None):
        self.dxf = dxf

    def append(self, dxf):
        """
        Check to see whether style already exists and append it if does not.
        """
        if not isinstance(dxf, DifferentialStyle):
            raise TypeError("expected " + str(DifferentialStyle))
        if dxf in self.styles:
            return
        self.styles.append(dxf)

    def add(self, dxf):
        """
        Add a differential style and return its index
        """
        self.append(dxf)
        return self.styles.index(dxf)

    def __bool__(self):
        return bool(self.styles)

    def __getitem__(self, idx):
        return self.styles[idx]

    @property
    def count(self):
        return len(self.dxf)
