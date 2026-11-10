# Copyright (c) 2010-2024 openpyxl
# ruff: noqa: F401, F811

from crabxl.descriptors.excel import Relation
from crabxl.descriptors.serialisable import Serialisable
from crabxl.xml.constants import CHART_NS


class ChartRelation(Serialisable):
    tagname = "chart"
    namespace = CHART_NS

    id = Relation()

    def __init__(self, id):
        self.id = id
