# XML descriptors adapted from openpyxl 3.1.5; package writing is owned by Rust.
# Copyright (c) 2010-2024 openpyxl

from crabxl.descriptors import (
    Sequence,
    Typed,
)
from crabxl.descriptors.excel import ExtensionList
from crabxl.descriptors.sequence import (
    MultiSequence,
    MultiSequencePart,
)
from crabxl.descriptors.serialisable import Serialisable
from crabxl.xml.constants import SHEET_MAIN_NS

from .fields import (
    Boolean,
    DateTimeField,
    Error,
    Index,
    Missing,
    Number,
    Text,
)
from .fields import TupleList as TupleList


class Record(Serialisable):
    tagname = "r"

    _fields = MultiSequence()
    m = MultiSequencePart(expected_type=Missing, store="_fields")
    n = MultiSequencePart(expected_type=Number, store="_fields")
    b = MultiSequencePart(expected_type=Boolean, store="_fields")
    e = MultiSequencePart(expected_type=Error, store="_fields")
    s = MultiSequencePart(expected_type=Text, store="_fields")
    d = MultiSequencePart(expected_type=DateTimeField, store="_fields")
    x = MultiSequencePart(expected_type=Index, store="_fields")

    def __init__(
        self,
        _fields=(),
        m=None,
        n=None,
        b=None,
        e=None,
        s=None,
        d=None,
        x=None,
    ):
        self._fields = _fields


class RecordList(Serialisable):
    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheRecords+xml"
    rel_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheRecords"
    _id = 1
    _path = "/xl/pivotCache/pivotCacheRecords{0}.xml"

    tagname = "pivotCacheRecords"

    r = Sequence(expected_type=Record, allow_none=True)
    extLst = Typed(expected_type=ExtensionList, allow_none=True)

    __elements__ = ("r",)
    __attrs__ = ("count",)

    def __init__(
        self,
        count=None,
        r=(),
        extLst=None,
    ):
        self.r = r
        self.extLst = extLst

    @property
    def count(self):
        return len(self.r)

    def to_tree(self, tagname=None, idx=None, namespace=None):
        tree = super().to_tree(tagname=tagname, idx=idx, namespace=namespace)
        if tagname is None:
            tree.set("xmlns", SHEET_MAIN_NS)
        return tree

    @property
    def path(self):
        return self._path.format(self._id)
