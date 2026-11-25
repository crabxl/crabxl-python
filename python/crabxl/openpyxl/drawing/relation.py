# Copyright (c) 2010-2024 openpyxl
# ruff: noqa: F401, F811

from crabxl.openpyxl.descriptors.excel import Relation
from crabxl.openpyxl.descriptors.serialisable import Serialisable
from crabxl.openpyxl.xml.constants import CHART_NS


class ChartRelation(Serialisable):
    tagname = "chart"
    namespace = CHART_NS

    id = Relation()

    def __init__(self, id):
        self.id = id
