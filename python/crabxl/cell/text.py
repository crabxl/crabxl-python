# XML text descriptors adapted from openpyxl, Copyright (c) 2010-2024 openpyxl.
# MIT license in third_party/licenses/openpyxl-MIT.txt.
"""Inline font values for canonical rich-text runs."""

from crabxl.descriptors import (
    Alias,
    Integer,
    NoneSet,
    Sequence,
    Typed,
)
from crabxl.descriptors.nested import (
    NestedText,
)
from crabxl.descriptors.serialisable import Serialisable
from crabxl.styles.fonts import Font


class InlineFont(Font):
    _aliases = {**Font._aliases, "rFont": "name"}
    __attrs__ = ()
    __elements__ = (
        "rFont",
        "charset",
        "family",
        "b",
        "i",
        "strike",
        "outline",
        "shadow",
        "condense",
        "extend",
        "color",
        "sz",
        "u",
        "vertAlign",
        "scheme",
    )

    def __repr__(self):
        return Serialisable.__repr__(self)

    def _mapping(self):
        values = super()._mapping()
        for name in ("b", "i"):
            if values[name] is False:
                values[name] = None
        return values

    def __init__(
        self,
        rFont=None,
        charset=None,
        family=None,
        b=None,
        i=None,
        strike=None,
        outline=None,
        shadow=None,
        condense=None,
        extend=None,
        color=None,
        sz=None,
        u=None,
        vertAlign=None,
        scheme=None,
    ):
        super().__init__(
            name=rFont,
            charset=charset,
            family=family,
            b=b,
            i=i,
            strike=strike,
            outline=outline,
            shadow=shadow,
            condense=condense,
            extend=extend,
            color=color,
            sz=sz,
            u=u,
            vertAlign=vertAlign,
            scheme=scheme,
        )

    def to_tree(self, tagname=None, idx=None, namespace=None):
        from ..styles import Font as PublicFont
        from ..styles.differential import _convert

        font = PublicFont(**{field: getattr(self, field) for field in self._fields})
        font.b, font.i = self.b, self.i
        node = _convert(font).to_tree(tagname or "RPrElt", idx, namespace)
        for child in node:
            if child.tag == "name":
                child.tag = "rFont"
        return node

    @classmethod
    def from_tree(cls, node):
        from copy import deepcopy

        node = deepcopy(node)
        for child in node:
            if child.tag.rsplit("}", 1)[-1] == "rFont":
                child.tag = child.tag.replace("rFont", "name")
        font = Font.from_tree(node)
        values = {
            "rFont" if field == "name" else field: getattr(font, field)
            for field in font._fields
        }
        present = {child.tag.rsplit("}", 1)[-1] for child in node}
        for field in ("b", "i"):
            if field not in present:
                values[field] = None
        return cls(**values)


class PhoneticProperties(Serialisable):
    tagname = "phoneticPr"

    fontId = Integer()
    type = NoneSet(
        values=(["halfwidthKatakana", "fullwidthKatakana", "Hiragana", "noConversion"])
    )
    alignment = NoneSet(values=(["noControl", "left", "center", "distributed"]))

    def __init__(
        self,
        fontId=None,
        type=None,
        alignment=None,
    ):
        self.fontId = fontId
        self.type = type
        self.alignment = alignment


class PhoneticText(Serialisable):
    tagname = "rPh"

    sb = Integer()
    eb = Integer()
    t = NestedText(expected_type=str)
    text = Alias("t")

    def __init__(
        self,
        sb=None,
        eb=None,
        t=None,
    ):
        self.sb = sb
        self.eb = eb
        self.t = t


class RichText(Serialisable):
    tagname = "RElt"

    rPr = Typed(expected_type=InlineFont, allow_none=True)
    font = Alias("rPr")
    t = NestedText(expected_type=str, allow_none=True)
    text = Alias("t")

    __elements__ = ("rPr", "t")

    def __init__(
        self,
        rPr=None,
        t=None,
    ):
        self.rPr = rPr
        self.t = t


class Text(Serialisable):
    tagname = "text"

    t = NestedText(allow_none=True, expected_type=str)
    plain = Alias("t")
    r = Sequence(expected_type=RichText, allow_none=True)
    formatted = Alias("r")
    rPh = Sequence(expected_type=PhoneticText, allow_none=True)
    phonetic = Alias("rPh")
    phoneticPr = Typed(expected_type=PhoneticProperties, allow_none=True)
    PhoneticProperties = Alias("phoneticPr")

    __elements__ = ("t", "r", "rPh", "phoneticPr")

    def __init__(
        self,
        t=None,
        r=(),
        rPh=(),
        phoneticPr=None,
    ):
        self.t = t
        self.r = r
        self.rPh = rPh
        self.phoneticPr = phoneticPr

    @property
    def content(self):
        """
        Text stripped of all formatting
        """
        snippets = []
        if self.plain is not None:
            snippets.append(self.plain)
        for block in self.formatted:
            if block.t is not None:
                snippets.append(block.t)
        return "".join(snippets)
