# Copyright (c) 2010-2024 openpyxl
# Standalone XML metadata adapters; Workbook package I/O remains native.
# ruff: noqa: F401, F811

from crabxl.descriptors.excel import Relation
from crabxl.descriptors.serialisable import Serialisable


class Drawing(Serialisable):

    tagname = "drawing"

    id = Relation()

    def __init__(self, id=None):
        self.id = id
