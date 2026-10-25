# Adapted from openpyxl 3.1.5 (MIT, Copyright (c) 2010 openpyxl); see third_party/licenses/openpyxl-MIT.txt.

from crabxl.descriptors.serialisable import Serialisable
from crabxl.descriptors.excel import Relation


class Related(Serialisable):
    id = Relation()

    def __init__(self, id=None):
        self.id = id

    def to_tree(self, tagname, idx=None):
        return super().to_tree(tagname)
