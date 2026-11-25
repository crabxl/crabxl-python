# Adapted from openpyxl 3.1.5 (MIT, Copyright (c) 2010 openpyxl); see third_party/licenses/openpyxl-MIT.txt.

from crabxl.openpyxl.descriptors.serialisable import Serialisable
from crabxl.openpyxl.descriptors.excel import Relation


class Related(Serialisable):
    id = Relation()

    def __init__(self, id=None):
        self.id = id

    def to_tree(self, tagname, idx=None):
        return super().to_tree(tagname)
