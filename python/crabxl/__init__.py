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
from .styles import (
    Alignment as Alignment,
)
from .styles import (
    Border as Border,
)
from .styles import (
    Font as Font,
)
from .styles import (
    GradientFill as GradientFill,
)
from .styles import (
    PatternFill as PatternFill,
)
from .styles import (
    Protection as Protection,
)
from .workbook.loader import load_workbook as load_workbook
from .workbook.workbook import Workbook as Workbook
from .worksheet.worksheet import Worksheet as Worksheet

__version__ = "0.1.0a10"
