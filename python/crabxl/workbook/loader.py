"""Source-backed workbook loading and mode selection."""

from pathlib import Path

from .._native import (
    NativeEditor,
    NativeReader,
    resolve_model_budget,
)
from ..resources import ResourceOptions
from ..worksheet.worksheet import Worksheet
from .workbook import Workbook


def load_workbook(
    filename,
    read_only=False,
    keep_vba=False,
    data_only=False,
    keep_links=True,
    rich_text=False,
    *,
    max_memory_bytes=None,
    resource_options=None,
):
    """Use openpyxl call names; unsupported modes fail rather than change semantics."""
    if not keep_links or rich_text:
        raise NotImplementedError(
            "External-link removal and rich-text binding are not implemented"
        )
    if not isinstance(filename, (str, Path)):
        raise NotImplementedError("File-like binding input is not implemented")
    # VBA removal is staged; require explicit preservation for macro inputs.
    if str(filename).lower().endswith((".xlsm", ".xltm")) and not keep_vba:
        raise NotImplementedError("Macro removal is not implemented; use keep_vba=True")
    if resource_options is not None and not isinstance(
        resource_options, ResourceOptions
    ):
        raise TypeError("resource_options must be ResourceOptions or None")
    native_resources = (
        resource_options._native(max_memory_bytes, read_only=bool(read_only))
        if resource_options is not None
        else None
    )
    maximum = resolve_model_budget(max_memory_bytes, native_resources)
    workbook = Workbook(max_memory_bytes=maximum)
    workbook._reader = NativeReader(
        Path(filename),
        workbook._max_bytes,
        native_resources,
        editable=not read_only,
        data_only=bool(data_only),
    )
    try:
        workbook.read_only = bool(read_only)
        workbook._editor = (
            None
            if read_only
            else NativeEditor(
                Path(filename),
                max_memory_bytes,
                native_resources,
                reader=workbook._reader,
            )
        )
        workbook.data_only = data_only
        if read_only:
            from ..optimized import ReadOnlyWorksheet

            workbook._sheets = [
                ReadOnlyWorksheet(workbook, name) for name in workbook._reader.names()
            ]
        else:
            workbook._sheets = [
                Worksheet(workbook, name, _existing=True)
                for name in workbook._reader.names()
            ]
        workbook._active = workbook._reader.active_view_index()
        workbook._book = None  # NativeReader owns the canonical loaded bank.
    except BaseException:
        workbook._reader.close()
        raise
    return workbook
