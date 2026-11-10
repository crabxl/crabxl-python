# Adapted from openpyxl 3.1.5 (MIT, Copyright (c) 2010 openpyxl); see third_party/licenses/openpyxl-MIT.txt.

"""
Utility list for top level containers that contain one type of element

Provides the necessary API to read and write XML
"""

from crabxl.xml.functions import Element


class ElementList(list):
    # Subclasses define these; the base list has neither.
    @property
    def tagname(self):
        raise AttributeError(f"{type(self).__name__} has no tagname")

    @property
    def expected_type(self):
        raise AttributeError(f"{type(self).__name__} has no expected_type")

    @classmethod
    def from_tree(cls, tree):
        l = [cls.expected_type.from_tree(el) for el in tree]
        return cls(l)

    def to_tree(self):
        container = Element(self.tagname)
        for el in self:
            container.append(el.to_tree())
        return container

    def append(self, value):
        if not isinstance(value, self.expected_type):
            raise TypeError(
                f"Value must of type {self.expected_type} {type(value)} provided"
            )
        super().append(value)
