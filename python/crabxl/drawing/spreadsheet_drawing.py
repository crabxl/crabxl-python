"""Positions for images and charts on a worksheet."""

from .._values import _address
from ..descriptors import Bool, NoneSet, Typed
from ..descriptors.nested import NestedText
from ..descriptors.serialisable import Serialisable
from .xdr import XDRPoint2D, XDRPositiveSize2D


class AnchorClientData(Serialisable):
    fLocksWithSheet = Bool(allow_none=True)
    fPrintsWithSheet = Bool(allow_none=True)

    def __init__(self, fLocksWithSheet=None, fPrintsWithSheet=None):
        self.fLocksWithSheet = fLocksWithSheet
        self.fPrintsWithSheet = fPrintsWithSheet


class AnchorMarker(Serialisable):
    tagname = "marker"
    col = NestedText(expected_type=int)
    colOff = NestedText(expected_type=int)
    row = NestedText(expected_type=int)
    rowOff = NestedText(expected_type=int)

    def __init__(self, col=0, colOff=0, row=0, rowOff=0):
        self.col, self.colOff = col, colOff
        self.row, self.rowOff = row, rowOff

    def _native(self):
        return self.row, self.col, self.rowOff, self.colOff


class OneCellAnchor(Serialisable):
    tagname = "oneCellAnchor"
    _from = Typed(expected_type=AnchorMarker)
    ext = Typed(expected_type=XDRPositiveSize2D)
    clientData = Typed(expected_type=AnchorClientData)
    __elements__ = ("_from", "ext", "clientData")

    def __init__(self, _from=None, ext=None, clientData=None):
        self.clientData = AnchorClientData() if clientData is None else clientData
        self._from = AnchorMarker() if _from is None else _from
        self.ext = XDRPositiveSize2D(0, 0) if ext is None else ext

    def _native(self):
        return self._from._native(), (self.ext.cx, self.ext.cy)


class TwoCellAnchor(Serialisable):
    tagname = "twoCellAnchor"
    editAs = NoneSet(values=("twoCell", "oneCell", "absolute"))
    _from = Typed(expected_type=AnchorMarker)
    to = Typed(expected_type=AnchorMarker)
    clientData = Typed(expected_type=AnchorClientData)
    __elements__ = ("_from", "to", "clientData")

    def __init__(self, editAs=None, _from=None, to=None, clientData=None):
        self.clientData = AnchorClientData() if clientData is None else clientData
        self.editAs = editAs
        self._from = AnchorMarker() if _from is None else _from
        self.to = AnchorMarker() if to is None else to

    def _native(self):
        return self._from._native(), self.to._native(), self.editAs


class AbsoluteAnchor(Serialisable):
    tagname = "absoluteAnchor"
    pos = Typed(expected_type=XDRPoint2D)
    ext = Typed(expected_type=XDRPositiveSize2D)
    clientData = Typed(expected_type=AnchorClientData)
    __elements__ = ("pos", "ext", "clientData")

    def __init__(self, pos=None, ext=None, clientData=None):
        self.clientData = AnchorClientData() if clientData is None else clientData
        self.pos = XDRPoint2D(0, 0) if pos is None else pos
        self.ext = XDRPositiveSize2D(0, 0) if ext is None else ext

    def _native(self):
        return (self.pos.x, self.pos.y), (self.ext.cx, self.ext.cy)


def _check_anchor(obj):
    from ..chart._chart import ChartBase
    from ..utils.units import cm_to_EMU, pixels_to_EMU
    from .image import Image

    anchor = obj.anchor
    if isinstance(anchor, (OneCellAnchor, TwoCellAnchor, AbsoluteAnchor)):
        return anchor
    row, col = _address(anchor)
    anchor = OneCellAnchor(_from=AnchorMarker(row=row - 1, col=col - 1))
    if isinstance(obj, ChartBase):
        anchor.ext = XDRPositiveSize2D(cm_to_EMU(obj.width), cm_to_EMU(obj.height))
    elif isinstance(obj, Image):
        anchor.ext = XDRPositiveSize2D(pixels_to_EMU(obj.width), pixels_to_EMU(obj.height))
    return anchor


def _anchor_input(anchor, cx, cy):
    if isinstance(anchor, str):
        row, col = _address(anchor)
        return (row - 1, col - 1, 0, 0), (cx, cy)
    if isinstance(anchor, (OneCellAnchor, TwoCellAnchor, AbsoluteAnchor)):
        return anchor._native()
    raise TypeError("Expected a cell coordinate or drawing anchor")


def _client_data_input(anchor):
    if isinstance(anchor, str):
        return None, None
    return anchor.clientData.fLocksWithSheet, anchor.clientData.fPrintsWithSheet
