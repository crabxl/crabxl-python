# Copyright (c) 2010-2024 openpyxl

from crabxl.openpyxl.descriptors.excel import (
    Relation,
)
from crabxl.openpyxl.descriptors.serialisable import Serialisable


class ExternalReference(Serialisable):
    tagname = "externalReference"

    id = Relation()

    def __init__(self, id):
        self.id = id
