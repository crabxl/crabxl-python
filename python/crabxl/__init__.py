"""CrabXL: read, write and edit Excel XLSX files.

Three entry points cover the three ways of working with a file:

* :class:`Workbook` creates a workbook, or opens one to change and save it.
* :class:`Reader` reads large files row by row in bounded memory.
* :class:`Writer` writes large files row by row in bounded memory.

The openpyxl-compatible interface is in :mod:`crabxl.openpyxl`.
"""

import importlib

from ._features import (
    Chart,
    ChartKind,
    Comparison,
    ConditionalFormat,
    DataValidation,
    DefinedName,
    Hyperlink,
    Image,
    Margins,
    Note,
    Orientation,
    PageSetup,
    PlacedImage,
    Properties,
    Series,
    Table,
    ValidationValue,
)
from ._values import CellInput, ErrorValue, Formula, RichText, TextRun, Value
from .errors import (
    ConversionError,
    CrabXLError,
    FileFormatError,
    InvalidInputError,
    LimitExceededError,
    MemoryLimitError,
    NotFoundError,
    StateError,
    UnsupportedError,
)
from .read import Reader, Row, WorksheetReader
from .styles import (
    Alignment,
    Border,
    Color,
    Fill,
    Font,
    PartialStyle,
    Protection,
    Side,
    Style,
)
from .workbook import (
    Charts,
    Columns,
    ConditionalFormats,
    DefinedNames,
    Images,
    Merges,
    Range,
    Rows,
    Tables,
    Validations,
    Workbook,
    Worksheet,
    Worksheets,
)
from .write import WorksheetWriter, Writer

__version__ = "0.3.0"

__all__ = [
    "Alignment",
    "Border",
    "CellInput",
    "Chart",
    "ChartKind",
    "Charts",
    "Color",
    "Columns",
    "Comparison",
    "ConditionalFormat",
    "ConditionalFormats",
    "ConversionError",
    "CrabXLError",
    "DataValidation",
    "DefinedName",
    "DefinedNames",
    "ErrorValue",
    "FileFormatError",
    "Fill",
    "Font",
    "Formula",
    "Hyperlink",
    "Image",
    "Images",
    "InvalidInputError",
    "LimitExceededError",
    "Margins",
    "MemoryLimitError",
    "Merges",
    "Note",
    "NotFoundError",
    "Orientation",
    "PageSetup",
    "PartialStyle",
    "PlacedImage",
    "Properties",
    "Protection",
    "Range",
    "Reader",
    "RichText",
    "Row",
    "Rows",
    "Series",
    "Side",
    "StateError",
    "Style",
    "Table",
    "Tables",
    "TextRun",
    "UnsupportedError",
    "Validations",
    "ValidationValue",
    "Value",
    "Workbook",
    "Worksheet",
    "WorksheetReader",
    "WorksheetWriter",
    "Worksheets",
    "Writer",
]


def __getattr__(name: str) -> object:
    # Point code written for crabxl 0.2 to the openpyxl-compatible module. An
    # ImportError, because ``from crabxl import x`` hides an AttributeError's text.
    if not name.startswith("__"):
        openpyxl = importlib.import_module(f"{__name__}.openpyxl")
        if hasattr(openpyxl, name):
            raise ImportError(
                f"crabxl.{name} moved to crabxl.openpyxl.{name} in 0.3: "
                f"use 'from crabxl.openpyxl import {name}'",
                name=__name__,
            )
    raise AttributeError(f"module 'crabxl' has no attribute {name!r}")
