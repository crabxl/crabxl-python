"""Compatible exception names owned by the optional adapter."""


class IllegalCharacterError(ValueError):
    """A cell contains a character forbidden in XML."""


class WorkbookAlreadySaved(RuntimeError):
    """A streaming workbook or worksheet has already been consumed."""


class ReadOnlyWorkbookException(TypeError):
    """An operation requires an editable workbook."""
