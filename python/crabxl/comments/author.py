# Copyright (c) 2010-2024 openpyxl


from crabxl.descriptors import Alias, Sequence
from crabxl.descriptors.serialisable import Serialisable


class AuthorList(Serialisable):
    tagname = "authors"

    author = Sequence(expected_type=str)
    authors = Alias("author")

    def __init__(
        self,
        author=(),
    ):
        self.author = author
