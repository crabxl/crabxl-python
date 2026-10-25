"""Compatible exception names owned by the optional adapter."""


class IllegalCharacterError(ValueError):
    """A cell contains a character forbidden in XML."""


class WorkbookAlreadySaved(RuntimeError):
    """A streaming workbook or worksheet has already been consumed."""


class ReadOnlyWorkbookException(TypeError):
    """An operation requires an editable workbook."""


class CellCoordinatesException(ValueError):
    """Raised when a coordinate string is invalid."""


class InvalidFileException(Exception):
    """Raised when a file is not a valid workbook."""


class SheetTitleException(Exception):
    """Raised when a sheet title is invalid."""


class NamedRangeException(Exception):
    """Raised for an invalid named range."""
