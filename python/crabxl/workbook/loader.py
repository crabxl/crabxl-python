"""Source-backed workbook loading and mode selection."""

from os import PathLike
from pathlib import Path
from shutil import copyfileobj
from tempfile import TemporaryDirectory

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
    try:
        if isinstance(filename, (str, PathLike)):
            path = Path(filename)
        else:
            if not callable(getattr(filename, "read", None)):
                raise TypeError("Expected a path or readable binary stream")
            workbook._input_spool = TemporaryDirectory(prefix="crabxl-input-")
            path = Path(workbook._input_spool.name) / "workbook.xlsx"
            seekable = getattr(filename, "seekable", lambda: False)()
            if seekable:
                position = filename.tell()
                filename.seek(0)
            try:
                with path.open("wb") as target:
                    copyfileobj(filename, target, length=1024 * 1024)
            finally:
                if seekable:
                    filename.seek(position)
        workbook._reader = NativeReader(
            path,
            workbook._max_bytes,
            native_resources,
            editable=not read_only,
            data_only=bool(data_only),
            rich_text=bool(rich_text),
        )
        workbook.read_only = bool(read_only)
        workbook._editor = (
            None
            if read_only
            else NativeEditor(
                path,
                max_memory_bytes,
                native_resources,
                reader=workbook._reader,
            )
        )
        workbook._template, macro_enabled = workbook._reader.workbook_format()
        workbook._keep_vba = bool(keep_vba and macro_enabled)
        if workbook._editor is not None and macro_enabled and not workbook._keep_vba:
            workbook._editor.set_vba(False)
        if workbook._editor is not None and not keep_links:
            workbook._editor.remove_external_links(bool(data_only))
        workbook.data_only = data_only
        from ..chartsheet import Chartsheet

        chartsheets = set(workbook._reader.chartsheet_names())
        if read_only:
            from ..optimized import ReadOnlyWorksheet

            workbook._sheets = [
                Chartsheet(workbook, name, _existing=True)
                if name in chartsheets
                else ReadOnlyWorksheet(workbook, name)
                for name in workbook._reader.names()
            ]
        else:
            workbook._sheets = [
                (Chartsheet if name in chartsheets else Worksheet)(
                    workbook, name, _existing=True
                )
                for name in workbook._reader.names()
            ]
        workbook._active = workbook._reader.active_view_index()
        workbook._book = None  # NativeReader owns the canonical loaded bank.
    except BaseException:
        workbook.close()
        raise
    return workbook
