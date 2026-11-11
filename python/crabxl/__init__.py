"""An openpyxl-compatible adapter over the independent Rust core.

Compatibility is verified per capability. Unsupported features raise explicitly;
this package never falls back to the Python openpyxl implementation.
"""

from ._values import (
    _address as _address,
)
from ._values import (
    _column as _column,
)
from ._values import (
    _data_type as _data_type,
)
from ._values import (
    _decode as _decode,
)
from ._values import (
    _encode as _encode,
)
from ._values import (
    _letters as _letters,
)
from ._values import (
    _range as _range,
)
from .cell.cell import Cell as Cell
from .resources import AutoMemory as AutoMemory
from .resources import ResourceLimits as ResourceLimits
from .resources import ResourceOptions as ResourceOptions
from .resources import SharedStringOptions as SharedStringOptions
from .workbook.loader import load_workbook as load_workbook
from .workbook.workbook import Workbook as Workbook
from .worksheet.worksheet import Worksheet as Worksheet

__version__ = "0.2.0"
LXML = False
DEFUSEDXML = False


_STYLES = ("Alignment", "Border", "Font", "GradientFill", "PatternFill", "Protection")


def __getattr__(name):
    # Style classes load on first use, so that reading values stays fast.
    if name in _STYLES:
        from . import styles

        value = getattr(styles, name)
        globals()[name] = value
        return value
    if name == "NUMPY":
        from .compat.numbers import NUMPY

        globals()[name] = NUMPY
        return NUMPY
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
