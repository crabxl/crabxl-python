//! Shared adapter imports; no engine implementation belongs here.
pub(crate) use crabxl::{
    Cell, CellAddress, CellRange, CellValue, ColumnIndex, DataTableOptions, DateEpoch, DateKind,
    EditLimits, EditorOptions, Error, ErrorKind, ExactInteger, ExcelDateTime, Formula, FormulaFlag,
    FormulaFlags, FormulaMetadata, FormulaRange, FormulaType, LoadOptions, LoadedWorkbook,
    MemoryPolicy, ReadOptions, ResourceLimits, Row, RowIndex, SaveOptions, SheetId,
    SheetVisibility, StyleId, Workbook, WorkbookEditor, WorkbookLimits, WorkbookReader,
    WorkbookWriter, Worksheet, WorksheetEditor, WriteOptions,
};
pub(crate) use pyo3::{
    IntoPyObjectExt,
    exceptions::{
        PyIndexError, PyKeyError, PyMemoryError, PyNotImplementedError, PyOSError, PyRuntimeError,
        PyValueError,
    },
    prelude::*,
    types::{PyBytes, PyDict, PyList},
};
pub(crate) use std::{
    fs::File,
    path::PathBuf,
    sync::{Arc, Mutex, MutexGuard},
};
