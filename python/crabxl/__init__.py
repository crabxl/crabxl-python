"""CrabXL: read, write and edit Excel XLSX files.

Three entry points cover the three ways of working with a file:

* :class:`Workbook` creates a workbook, or opens one to change and save it.
* :class:`Reader` reads large files row by row in bounded memory.
* :class:`Writer` writes large files row by row in bounded memory.

The openpyxl-compatible interface is in :mod:`crabxl.openpyxl`.
"""

from ._features import (
    Comparison,
    ConditionalFormat,
    DataValidation,
    DefinedName,
    Hyperlink,
    Image,
    Note,
    Properties,
    Table,
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
from .workbook import Columns, Range, Rows, Workbook, Worksheet, Worksheets
from .write import WorksheetWriter, Writer

__version__ = "0.2.2"

__all__ = [
    "Alignment",
    "Border",
    "CellInput",
    "Color",
    "Columns",
    "Comparison",
    "ConditionalFormat",
    "ConversionError",
    "CrabXLError",
    "DataValidation",
    "DefinedName",
    "ErrorValue",
    "FileFormatError",
    "Fill",
    "Font",
    "Formula",
    "Hyperlink",
    "Image",
    "InvalidInputError",
    "LimitExceededError",
    "MemoryLimitError",
    "Note",
    "NotFoundError",
    "PartialStyle",
    "Properties",
    "Protection",
    "Range",
    "Reader",
    "RichText",
    "Row",
    "Rows",
    "Side",
    "StateError",
    "Style",
    "Table",
    "TextRun",
    "UnsupportedError",
    "Value",
    "Workbook",
    "Worksheet",
    "WorksheetReader",
    "WorksheetWriter",
    "Worksheets",
    "Writer",
]
