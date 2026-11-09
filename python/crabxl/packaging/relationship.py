# Copyright (c) 2010-2024 openpyxl
# Standalone XML metadata adapters; Workbook package I/O remains native.
# ruff: noqa: F401, F811

import posixpath
from warnings import warn

from crabxl.descriptors import (
    Alias,
    Sequence,
    String,
)
from crabxl.descriptors.container import ElementList
from crabxl.descriptors.serialisable import Serialisable
from crabxl.xml.constants import PKG_REL_NS, REL_NS
from crabxl.xml.functions import (
    Element,
    fromstring,
)


class Relationship(Serialisable):
    """Represents many kinds of relationships."""

    tagname = "Relationship"

    Type = String()
    Target = String()
    target = Alias("Target")
    TargetMode = String(allow_none=True)
    Id = String(allow_none=True)
    id = Alias("Id")

    def __init__(self, Id=None, Type=None, type=None, Target=None, TargetMode=None):
        """
        `type` can be used as a shorthand with the default relationships namespace
        otherwise the `Type` must be a fully qualified URL
        """
        if type is not None:
            Type = "{0}/{1}".format(REL_NS, type)
        self.Type = Type
        self.Target = Target
        self.TargetMode = TargetMode
        self.Id = Id


class RelationshipList(ElementList):
    tagname = "Relationships"
    expected_type = Relationship

    def append(self, value):
        super().append(value)
        if not value.Id:
            value.Id = f"rId{len(self)}"

    def find(self, content_type):
        """
        Find relationships by content-type
        NB. these content-types namespaced objects and different to the MIME-types
        in the package manifest :-(
        """
        for r in self:
            if r.Type == content_type:
                yield r

    def get(self, key):
        for r in self:
            if r.Id == key:
                return r
        raise KeyError("Unknown relationship: {0}".format(key))

    def to_dict(self):
        """Return a dictionary of relations keyed by id"""
        return {r.id: r for r in self}

    def to_tree(self):
        tree = super().to_tree()
        tree.set("xmlns", PKG_REL_NS)
        return tree


def get_rels_path(path):
    """
    Convert relative path to absolutes that can be loaded from a zip
    archive.
    The path to be passed in is that of containing object (workbook,
    worksheet, etc.)
    """
    folder, obj = posixpath.split(path)
    filename = posixpath.join(folder, "_rels", "{0}.rels".format(obj))
    return filename


def get_dependents(archive, filename):
    """Project caller-owned relationship XML; URI resolution stays native."""
    from .._native import resolve_relationship_targets

    node = fromstring(archive.read(filename))
    try:
        rels = RelationshipList.from_tree(node)
    except TypeError:
        warn(f"{filename} contains invalid dependency definitions")
        return RelationshipList()
    targets = resolve_relationship_targets(
        filename, [(rel.target, rel.TargetMode == "External") for rel in rels]
    )
    for rel, target in zip(rels, targets):
        rel.target = target
    return rels


def get_rel(archive, deps, id=None, cls=None):
    """
    Get related object based on id or rel_type
    """
    if not any([id, cls]):
        raise ValueError("Either the id or the content type are required")
    if id is not None:
        rel = deps.get(id)
    else:
        try:
            rel = next(deps.find(cls.rel_type))
        except StopIteration:  # no known dependency
            return

    path = rel.target
    src = archive.read(path)
    tree = fromstring(src)
    obj = cls.from_tree(tree)

    rels_path = get_rels_path(path)
    try:
        obj.deps = get_dependents(archive, rels_path)
    except KeyError:
        obj.deps = []

    return obj
