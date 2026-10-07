//! Foreign objects and naming remain outside the canonical Rust core.
mod resources;
mod streaming;

use crabxl::{
    Cell, CellAddress, CellRange, CellValue, ColumnIndex, DataTableOptions, DateEpoch, DateKind,
    EditLimits, EditorOptions, Error, ErrorKind, ExactInteger, ExcelDateTime, Formula, FormulaFlag,
    FormulaFlags, FormulaMetadata, FormulaRange, FormulaType, LoadOptions, LoadedWorkbook,
    MemoryPolicy, ReadOptions, ResourceLimits, Row, RowIndex, SaveOptions, SheetId,
    SheetVisibility, StyleId, Workbook, WorkbookEditor, WorkbookLimits, WorkbookReader,
    WorkbookWriter, Worksheet, WorksheetEditor, WriteOptions,
};
use pyo3::{
    IntoPyObjectExt,
    exceptions::{
        PyIndexError, PyKeyError, PyMemoryError, PyNotImplementedError, PyOSError, PyRuntimeError,
        PyValueError,
    },
    prelude::*,
    types::{PyDict, PyList},
};
use std::{
    fs::File,
    path::PathBuf,
    sync::{Arc, Mutex, MutexGuard},
};

type TaggedValue = (String, Py<PyAny>);
type EncodedValue = (&'static str, Py<PyAny>);
type DecodedValues = (Vec<Py<PyAny>>, Option<Vec<u32>>);
type SharedLoaded = Arc<Mutex<Option<LoadedWorkbook<streaming::SharedFile>>>>;
fn failure(error: Error) -> PyErr {
    let mut text = error.to_string();
    let mut source = std::error::Error::source(&error);
    while let Some(cause) = source {
        text.push_str(": ");
        text.push_str(&cause.to_string());
        source = cause.source();
    }
    match error.kind() {
        ErrorKind::Unsupported => PyNotImplementedError::new_err(text),
        ErrorKind::MemoryBudgetExceeded => PyMemoryError::new_err(text),
        ErrorKind::SheetNotFound => PyKeyError::new_err(text),
        ErrorKind::Io => PyOSError::new_err(text),
        ErrorKind::InvalidState => PyRuntimeError::new_err(text),
        ErrorKind::NoVisibleSheet => PyIndexError::new_err(text),
        _ => PyValueError::new_err(text),
    }
}
fn visibility(value: &str) -> PyResult<SheetVisibility> {
    match value {
        "visible" => Ok(SheetVisibility::Visible),
        "hidden" => Ok(SheetVisibility::Hidden),
        "veryHidden" => Ok(SheetVisibility::VeryHidden),
        _ => Err(PyValueError::new_err(
            "Sheet state must be visible, hidden or veryHidden",
        )),
    }
}
fn lock<T>(value: &Mutex<T>) -> PyResult<MutexGuard<'_, T>> {
    value
        .lock()
        .map_err(|_| PyRuntimeError::new_err("Native resource lock was poisoned"))
}
fn closed() -> PyErr {
    PyValueError::new_err("Workbook is closed")
}
fn input_flag(fields: &Bound<'_, PyDict>, name: &str) -> PyResult<Option<FormulaFlag>> {
    let Some(value) = fields.get_item(name)? else {
        return Ok(None);
    };
    if value.is_none() {
        return Ok(None);
    }
    if let Ok(boolean) = value.extract::<bool>() {
        return Ok(Some(boolean.into()));
    }
    Ok(Some(FormulaFlag::from_literal(value.extract::<String>()?)))
}
fn input_text(fields: &Bound<'_, PyDict>, name: &str) -> PyResult<Option<Box<str>>> {
    fields
        .get_item(name)?
        .filter(|value| !value.is_none())
        .map(|value| value.extract::<String>().map(String::into_boxed_str))
        .transpose()
}
fn output_flag(fields: &Bound<'_, PyDict>, name: &str, flag: Option<&FormulaFlag>) -> PyResult<()> {
    if let Some(flag) = flag {
        if let Some(source) = flag.source() {
            fields.set_item(name, source)?;
        } else {
            fields.set_item(name, flag.value())?;
        }
    }
    Ok(())
}
fn decode(py: Python<'_>, value: TaggedValue) -> PyResult<CellValue> {
    let (kind, value) = value;
    let value = value.bind(py);
    Ok(match kind.as_str() {
        "empty" => CellValue::Empty,
        "bool" => CellValue::Boolean(value.extract()?),
        "int" => {
            let decimal: String = value.extract()?;
            match decimal.parse::<i64>() {
                Ok(integer) => CellValue::Integer(integer),
                Err(_) => {
                    CellValue::BigInteger(Box::new(ExactInteger::parse(&decimal).map_err(failure)?))
                }
            }
        }
        "float" => {
            let number: f64 = value.extract()?;
            CellValue::Number(number)
        }
        "text" => CellValue::text(value.extract::<String>()?),
        "error" => CellValue::error(value.extract::<String>()?),
        "formula" => CellValue::Formula(Box::new(
            Formula::from_source(value.extract::<String>()?, None, None).map_err(failure)?,
        )),
        "array" | "table" => {
            let fields = value.cast::<PyDict>()?;
            let reference = input_text(fields, "ref")?.map(FormulaRange::from_literal);
            let mut metadata = FormulaMetadata {
                kind: if kind == "array" {
                    FormulaType::Array
                } else {
                    FormulaType::DataTable
                },
                reference,
                ..Default::default()
            };
            let formula = if kind == "array" {
                Formula::from_array_text(input_text(fields, "text")?, None, metadata)
                    .map_err(failure)?
            } else {
                metadata.flags = FormulaFlags {
                    calculate_cell: input_flag(fields, "ca")?,
                    ..Default::default()
                };
                metadata.data_table = Some(Box::new(DataTableOptions {
                    two_dimensions: input_flag(fields, "dt2D")?,
                    row_table: input_flag(fields, "dtr")?,
                    deleted1: input_flag(fields, "del1")?,
                    deleted2: input_flag(fields, "del2")?,
                    input1: input_text(fields, "r1")?,
                    input2: input_text(fields, "r2")?,
                }));
                Formula::with_optional_expression(None, None, metadata).map_err(failure)?
            };
            CellValue::Formula(Box::new(formula))
        }
        "date" => {
            let (year, month, day): (i32, u32, u32) = value.extract()?;
            CellValue::DateTime(Box::new(
                ExcelDateTime::from_ymd(year, month, day).map_err(failure)?,
            ))
        }
        "datetime" => {
            let (y, m, d, h, minute, second, micro): (i32, u32, u32, u32, u32, u32, u32) =
                value.extract()?;
            CellValue::DateTime(Box::new(
                ExcelDateTime::from_ymd_hms_micro(y, m, d, h, minute, second, micro)
                    .map_err(failure)?,
            ))
        }
        "time" => {
            let (hour, minute, second, micro): (u32, u32, u32, u32) = value.extract()?;
            CellValue::DateTime(Box::new(
                ExcelDateTime::from_hms_micro(hour, minute, second, micro).map_err(failure)?,
            ))
        }
        "duration" => {
            let (days, seconds, micro): (i64, u32, u32) = value.extract()?;
            CellValue::DateTime(Box::new(
                ExcelDateTime::from_duration_parts(days, seconds, micro).map_err(failure)?,
            ))
        }
        _ => return Err(PyValueError::new_err("Unknown native value tag")),
    })
}
fn encode(py: Python<'_>, value: &CellValue) -> PyResult<EncodedValue> {
    let (kind, object) = match value {
        CellValue::Empty => ("n", py.None()),
        CellValue::Number(value) => ("n", value.into_py_any(py)?),
        CellValue::Integer(value) => ("n", value.into_py_any(py)?),
        CellValue::BigInteger(value) => ("bigint", value.as_str().into_py_any(py)?),
        CellValue::Boolean(value) => ("b", value.into_py_any(py)?),
        CellValue::Text(value) => ("s", value.as_str().into_py_any(py)?),
        CellValue::Error(value) => ("e", value.as_str().into_py_any(py)?),
        CellValue::Formula(value) => match value.formula_type() {
            FormulaType::Array | FormulaType::DataTable => {
                let metadata = value
                    .metadata()
                    .ok_or_else(|| PyValueError::new_err("Missing structured formula metadata"))?;
                let fields = PyDict::new(py);
                fields.set_item(
                    "ref",
                    metadata
                        .reference
                        .as_ref()
                        .map(|reference| reference.spelling().into_owned()),
                )?;
                if value.formula_type() == FormulaType::Array {
                    fields.set_item("text", value.array_text().as_deref())?;
                    ("array", fields.into_any().unbind())
                } else {
                    output_flag(&fields, "ca", metadata.flags.calculate_cell.as_ref())?;
                    if let Some(table) = &metadata.data_table {
                        for (name, flag) in [
                            ("dt2D", table.two_dimensions.as_ref()),
                            ("dtr", table.row_table.as_ref()),
                            ("del1", table.deleted1.as_ref()),
                            ("del2", table.deleted2.as_ref()),
                        ] {
                            output_flag(&fields, name, flag)?;
                        }
                        fields.set_item("r1", table.input1.as_deref())?;
                        fields.set_item("r2", table.input2.as_deref())?;
                    }
                    ("table", fields.into_any().unbind())
                }
            }
            _ => ("f", format!("={}", value.expression()).into_py_any(py)?),
        },
        CellValue::DateTime(value) => match value.kind() {
            DateKind::Date => (
                "date",
                value
                    .to_date()
                    .map_err(failure)?
                    .to_string()
                    .into_py_any(py)?,
            ),
            DateKind::DateTime => (
                "datetime",
                value
                    .to_datetime()
                    .map_err(failure)?
                    .to_string()
                    .into_py_any(py)?,
            ),
            DateKind::Time => (
                "time",
                value
                    .to_time()
                    .map_err(failure)?
                    .to_string()
                    .into_py_any(py)?,
            ),
            DateKind::Duration => {
                let duration = value.to_duration().map_err(failure)?;
                (
                    "duration",
                    (duration.num_seconds(), duration.subsec_micros()).into_py_any(py)?,
                )
            }
        },
        _ => return Err(PyNotImplementedError::new_err("Unsupported native value")),
    };
    Ok((kind, object))
}

// Scalar rows reach Python without per-cell tagged tuples or Python decode
// calls. Editable structured formulas remain live cell views, identified by
// relative column positions; read-only formulas keep their detached projection.
fn decode_values(
    py: Python<'_>,
    tagged: Vec<EncodedValue>,
    bound_formulas: bool,
) -> PyResult<DecodedValues> {
    let mut values = Vec::with_capacity(tagged.len());
    let mut formulas = None;
    let mut decoder = None;
    for (column, (kind, value)) in tagged.into_iter().enumerate() {
        if bound_formulas && matches!(kind, "array" | "table") {
            formulas.get_or_insert_with(Vec::new).push(column as u32);
            values.push(py.None());
        } else if matches!(
            kind,
            "bigint" | "date" | "datetime" | "time" | "duration" | "array" | "table"
        ) {
            if decoder.is_none() {
                decoder = Some(py.import("crabxl")?.getattr("_decode")?);
            }
            values.push(
                decoder
                    .as_ref()
                    .ok_or_else(closed)?
                    .call1(((kind, value),))?
                    .unbind(),
            );
        } else {
            values.push(value);
        }
    }
    Ok((values, formulas))
}

// A handle owns either a detached worksheet or a stable identity in the shared
// core bank. No Python object or payload clone lives in the canonical model.
enum SheetStorage {
    Standalone(Worksheet),
    Bank {
        book: Arc<Mutex<Workbook>>,
        id: SheetId,
    },
    Loaded {
        book: SharedLoaded,
        id: SheetId,
    },
}
#[pyclass]
struct NativeSheet {
    storage: Arc<Mutex<SheetStorage>>,
}
impl NativeSheet {
    fn with<T>(&self, action: impl FnOnce(&Worksheet) -> PyResult<T>) -> PyResult<T> {
        let storage = lock(&self.storage)?;
        match &*storage {
            SheetStorage::Standalone(sheet) => action(sheet),
            SheetStorage::Bank { book, id } => action(lock(book)?.sheet(*id).map_err(failure)?),
            SheetStorage::Loaded { book, id } => action(
                lock(book)?
                    .as_ref()
                    .ok_or_else(closed)?
                    .model()
                    .sheet(*id)
                    .map_err(failure)?,
            ),
        }
    }
    fn with_mut<T>(
        &self,
        action: impl FnOnce(&mut WorksheetEditor<'_>) -> PyResult<T>,
    ) -> PyResult<T> {
        let mut storage = lock(&self.storage)?;
        match &mut *storage {
            SheetStorage::Standalone(sheet) => action(&mut sheet.edit()),
            SheetStorage::Bank { book, id } => {
                action(&mut lock(book)?.sheet_mut(*id).map_err(failure)?)
            }
            SheetStorage::Loaded { .. } => Err(PyNotImplementedError::new_err(
                "Loaded model mutation must use the preserving coordinator",
            )),
        }
    }
    fn in_loaded(book: SharedLoaded, id: SheetId) -> Self {
        Self {
            storage: Arc::new(Mutex::new(SheetStorage::Loaded { book, id })),
        }
    }
    fn in_bank(book: Arc<Mutex<Workbook>>, id: SheetId) -> Self {
        Self {
            storage: Arc::new(Mutex::new(SheetStorage::Bank { book, id })),
        }
    }
}
#[pymethods]
impl NativeSheet {
    #[new]
    fn new(name: String, max_bytes: usize) -> PyResult<Self> {
        Ok(Self {
            storage: Arc::new(Mutex::new(SheetStorage::Standalone(
                Worksheet::new(
                    name,
                    EditLimits {
                        max_bytes,
                        ..EditLimits::default()
                    },
                )
                .map_err(failure)?,
            ))),
        })
    }
    fn get(&self, py: Python<'_>, row: u32, column: u32) -> PyResult<EncodedValue> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        self.with(|sheet| {
            encode(
                py,
                sheet
                    .get(address)
                    .map_or(&CellValue::Empty, |cell| &cell.value),
            )
        })
    }
    fn style_id(&self, row: u32, column: u32) -> PyResult<u32> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        self.with(|sheet| Ok(sheet.get(address).map_or(0, |cell| cell.style.get())))
    }
    fn has_style(&self, row: u32, column: u32) -> PyResult<bool> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        let storage = lock(&self.storage)?;
        let resolve = |book: &Workbook, id| -> PyResult<bool> {
            let style = book
                .sheet(id)
                .map_err(failure)?
                .get(address)
                .map_or(StyleId::new(0), |cell| cell.style);
            Ok(book
                .style_catalog()
                .and_then(|catalog| catalog.cell_format(style))
                .is_some_and(|format| {
                    format.number_format_id != 0
                        || format.font_id != 0
                        || format.fill_id != 0
                        || format.border_id != 0
                        || format.base_format_id.unwrap_or(0) != 0
                        || format.quote_prefix == Some(true)
                        || format.pivot_button == Some(true)
                        || format
                            .alignment
                            .as_deref()
                            .is_some_and(|value| value != &Default::default())
                        || format.protection.is_some_and(|value| {
                            value.locked == Some(false) || value.hidden == Some(true)
                        })
                }))
        };
        match &*storage {
            SheetStorage::Standalone(sheet) => {
                Ok(sheet.get(address).is_some_and(|cell| cell.style.get() != 0))
            }
            SheetStorage::Bank { book, id } => resolve(&*lock(book)?, *id),
            SheetStorage::Loaded { book, id } => {
                resolve(lock(book)?.as_ref().ok_or_else(closed)?.model(), *id)
            }
        }
    }
    fn is_date_format(&self, row: u32, column: u32) -> PyResult<bool> {
        Ok(crabxl::classify_number_format(&self.number_format(row, column)?).is_some())
    }
    fn number_format(&self, row: u32, column: u32) -> PyResult<String> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        let storage = lock(&self.storage)?;
        let resolve = |book: &Workbook, id| -> PyResult<String> {
            let style = book
                .sheet(id)
                .map_err(failure)?
                .get(address)
                .map_or(StyleId::new(0), |cell| cell.style);
            Ok(book
                .style_catalog()
                .and_then(|catalog| {
                    catalog
                        .cell_format(style)
                        .and_then(|format| catalog.number_format(format.number_format_id))
                })
                .unwrap_or("General")
                .to_owned())
        };
        match &*storage {
            SheetStorage::Standalone(_) => Ok("General".to_owned()),
            SheetStorage::Bank { book, id } => resolve(&*lock(book)?, *id),
            SheetStorage::Loaded { book, id } => {
                resolve(lock(book)?.as_ref().ok_or_else(closed)?.model(), *id)
            }
        }
    }
    fn set_number_format(&self, row: u32, column: u32, code: String) -> PyResult<()> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        let storage = lock(&self.storage)?;
        match &*storage {
            SheetStorage::Standalone(_) => Err(PyNotImplementedError::new_err(
                "Detached sheet style registration remains unimplemented",
            )),
            SheetStorage::Bank { book, id } => {
                let mut book = lock(book)?;
                let previous = book
                    .sheet(*id)
                    .map_err(failure)?
                    .get(address)
                    .map_or(StyleId::new(0), |cell| cell.style);
                let style = book
                    .derive_number_format(previous, code.into())
                    .map_err(failure)?;
                book.sheet_mut(*id)
                    .map_err(failure)?
                    .set_style(address, style)
                    .map_err(failure)
            }
            SheetStorage::Loaded { book, id } => lock(book)?
                .as_mut()
                .ok_or_else(closed)?
                .set_number_format(*id, address, code.into())
                .map_err(failure),
        }
    }
    fn contains(&self, row: u32, column: u32) -> PyResult<bool> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        self.with(|sheet| Ok(sheet.get(address).is_some()))
    }
    fn row_values(
        &self,
        py: Python<'_>,
        row: u32,
        first: u32,
        last: u32,
        create_missing: bool,
    ) -> PyResult<Vec<EncodedValue>> {
        let row_index = CellAddress::new(row, first).map_err(failure)?.row;
        CellAddress::new(row, last).map_err(failure)?;
        if first > last {
            return Ok(Vec::new());
        }
        if !create_missing {
            return self.with(|sheet| {
                let mut cells = sheet
                    .row_cells(row_index)
                    .skip_while(|cell| cell.address.column.get() < first)
                    .take_while(|cell| cell.address.column.get() <= last)
                    .peekable();
                let mut values = Vec::with_capacity((last - first + 1) as usize);
                for column in first..=last {
                    let value = if cells
                        .peek()
                        .is_some_and(|cell| cell.address.column.get() == column)
                    {
                        cells.next().map_or(&CellValue::Empty, |cell| &cell.value)
                    } else {
                        &CellValue::Empty
                    };
                    values.push(encode(py, value)?);
                }
                Ok(values)
            });
        }
        self.with_mut(|sheet| {
            let mut values = Vec::with_capacity((last - first + 1) as usize);
            for column in first..=last {
                let address = CellAddress::new(row, column).map_err(failure)?;
                if create_missing && sheet.get(address).is_none() {
                    sheet
                        .set(Cell {
                            address,
                            value: CellValue::Empty,
                            style: StyleId::new(0),
                        })
                        .map_err(failure)?;
                }
                values.push(encode(
                    py,
                    sheet
                        .get(address)
                        .map_or(&CellValue::Empty, |cell| &cell.value),
                )?);
            }
            Ok(values)
        })
    }
    fn row_values_only(
        &self,
        py: Python<'_>,
        row: u32,
        first: u32,
        last: u32,
        create_missing: bool,
    ) -> PyResult<DecodedValues> {
        decode_values(
            py,
            self.row_values(py, row, first, last, create_missing)?,
            true,
        )
    }
    fn set(&self, py: Python<'_>, row: u32, column: u32, value: TaggedValue) -> PyResult<()> {
        let cell = Cell {
            address: CellAddress::new(row, column).map_err(failure)?,
            value: decode(py, value)?,
            style: StyleId::new(0),
        };
        self.with_mut(|sheet| {
            let mut cell = cell;
            cell.style = sheet
                .get(cell.address)
                .map_or(StyleId::new(0), |old| old.style);
            sheet.set(cell).map_err(failure)
        })
    }
    #[pyo3(signature = (row, column, retain=false))]
    fn remove(
        &self,
        py: Python<'_>,
        row: u32,
        column: u32,
        retain: bool,
    ) -> PyResult<Option<EncodedValue>> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        let storage = Arc::clone(&self.storage);
        let removed = py.detach(move || {
            let mut storage = lock(&storage)?;
            let removed = match &mut *storage {
                SheetStorage::Standalone(sheet) => sheet.edit().remove(address),
                SheetStorage::Bank { book, id } => {
                    lock(book)?.sheet_mut(*id).map_err(failure)?.remove(address)
                }
                SheetStorage::Loaded { book, id } => lock(book)?
                    .as_mut()
                    .ok_or_else(closed)?
                    .remove_cell(*id, address)
                    .map_err(failure)?,
            };
            Ok::<_, PyErr>(if retain { removed } else { None })
        })?;
        removed.map(|cell| encode(py, &cell.value)).transpose()
    }
    fn append(&self, py: Python<'_>, values: Vec<TaggedValue>) -> PyResult<u32> {
        let values = values
            .into_iter()
            .map(|value| decode(py, value))
            .collect::<PyResult<Vec<_>>>()?;
        {
            let storage = lock(&self.storage)?;
            if let SheetStorage::Loaded { book, id } = &*storage {
                let book = Arc::clone(book);
                let id = *id;
                drop(storage);
                return py.detach(move || {
                    lock(&book)?
                        .as_mut()
                        .ok_or_else(closed)?
                        .append(id, values)
                        .map(|row| row.get())
                        .map_err(failure)
                });
            }
        }
        self.with_mut(|sheet| sheet.append(values).map(|row| row.get()).map_err(failure))
    }
    fn bounds(&self) -> PyResult<(u32, u32, u32, u32)> {
        self.with(|sheet| {
            let mut bounds = (u32::MAX, u32::MAX, 0, 0);
            for cell in sheet.cells() {
                let row = cell.address.row.get() + 1;
                let col = cell.address.column.get() + 1;
                bounds.0 = bounds.0.min(row);
                bounds.1 = bounds.1.min(col);
                bounds.2 = bounds.2.max(row);
                bounds.3 = bounds.3.max(col);
            }
            Ok(if sheet.is_empty() {
                (1, 1, 1, 1)
            } else {
                bounds
            })
        })
    }
    fn row_extent(&self) -> PyResult<u32> {
        self.with(|sheet| Ok(sheet.row_extent()))
    }
    fn charged_bytes(&self) -> PyResult<usize> {
        self.with(|sheet| Ok(sheet.charged_bytes()))
    }
    fn sheet_state(&self) -> PyResult<String> {
        self.with(|sheet| Ok(sheet.visibility().as_str().to_owned()))
    }
    fn set_sheet_state(&self, state: &str) -> PyResult<()> {
        let visibility = visibility(state)?;
        let mut storage = lock(&self.storage)?;
        match &mut *storage {
            SheetStorage::Standalone(sheet) => {
                sheet.set_visibility(visibility);
                Ok(())
            }
            SheetStorage::Bank { book, id } => lock(book)?
                .set_sheet_visibility(*id, visibility)
                .map_err(failure),
            SheetStorage::Loaded { .. } => Err(PyNotImplementedError::new_err(
                "Loaded visibility changes require the preserving coordinator",
            )),
        }
    }
    fn rename(&self, name: String) -> PyResult<()> {
        let mut storage = lock(&self.storage)?;
        match &mut *storage {
            SheetStorage::Standalone(sheet) => sheet.rename(name).map_err(failure),
            SheetStorage::Bank { book, id } => lock(book)?.rename_sheet(*id, name).map_err(failure),
            SheetStorage::Loaded { .. } => Err(PyNotImplementedError::new_err(
                "Renaming existing sheets remains unimplemented",
            )),
        }
    }
    fn shift(
        &self,
        py: Python<'_>,
        index: u32,
        count: u32,
        rows: bool,
        insert: bool,
    ) -> PyResult<()> {
        let storage = Arc::clone(&self.storage);
        py.detach(move || {
            {
                let held = lock(&storage)?;
                if let SheetStorage::Loaded { book, id } = &*held {
                    let mut book = lock(book)?;
                    let book = book.as_mut().ok_or_else(closed)?;
                    return match (rows, insert) {
                        (true, true) => {
                            book.insert_rows(*id, RowIndex::new(index).map_err(failure)?, count)
                        }
                        (true, false) => {
                            book.delete_rows(*id, RowIndex::new(index).map_err(failure)?, count)
                        }
                        (false, true) => book.insert_columns(
                            *id,
                            ColumnIndex::new(index).map_err(failure)?,
                            count,
                        ),
                        (false, false) => book.delete_columns(
                            *id,
                            ColumnIndex::new(index).map_err(failure)?,
                            count,
                        ),
                    }
                    .map_err(failure);
                }
            }
            NativeSheet { storage }.with_mut(|sheet| {
                match (rows, insert) {
                    (true, true) => {
                        sheet.insert_rows(RowIndex::new(index).map_err(failure)?, count)
                    }
                    (true, false) => {
                        sheet.delete_rows(RowIndex::new(index).map_err(failure)?, count)
                    }
                    (false, true) => {
                        sheet.insert_columns(ColumnIndex::new(index).map_err(failure)?, count)
                    }
                    (false, false) => {
                        sheet.delete_columns(ColumnIndex::new(index).map_err(failure)?, count)
                    }
                }
                .map_err(failure)
            })
        })
    }
    fn move_range(
        &self,
        py: Python<'_>,
        bounds: (u32, u32, u32, u32),
        rows: i32,
        cols: i32,
        translate: bool,
    ) -> PyResult<()> {
        let (fr, fc, lr, lc) = bounds;
        let range = CellRange::new(
            CellAddress::new(fr, fc).map_err(failure)?,
            CellAddress::new(lr, lc).map_err(failure)?,
        )
        .map_err(failure)?;
        let storage = Arc::clone(&self.storage);
        py.detach(move || {
            {
                let held = lock(&storage)?;
                if let SheetStorage::Loaded { book, id } = &*held {
                    let mut book = lock(book)?;
                    let book = book.as_mut().ok_or_else(closed)?;
                    return if translate {
                        book.move_range_translated(*id, range, rows, cols)
                    } else {
                        book.move_range(*id, range, rows, cols)
                    }
                    .map_err(failure);
                }
            }
            NativeSheet { storage }.with_mut(|sheet| {
                if translate {
                    sheet.move_range_translated(range, rows, cols)
                } else {
                    sheet.move_range(range, rows, cols)
                }
                .map_err(failure)
            })
        })
    }
}
#[pyclass]
struct NativeBook {
    book: Arc<Mutex<Workbook>>,
}
#[pymethods]
impl NativeBook {
    fn set_active_view_index(&self, index: i64) -> PyResult<()> {
        lock(&self.book)?.set_active_view_index(index);
        Ok(())
    }
    #[new]
    fn new(max_bytes: usize) -> PyResult<Self> {
        Ok(Self {
            book: Arc::new(Mutex::new(
                Workbook::new(WorkbookLimits {
                    max_bytes,
                    sheet: EditLimits {
                        max_bytes,
                        ..EditLimits::default()
                    },
                    ..WorkbookLimits::default()
                })
                .map_err(failure)?,
            )),
        })
    }
    fn create_sheet(&self, name: String) -> PyResult<NativeSheet> {
        let id = lock(&self.book)?.create_sheet(name).map_err(failure)?;
        Ok(NativeSheet::in_bank(Arc::clone(&self.book), id))
    }
    fn copy_sheet(
        &self,
        py: Python<'_>,
        source: &NativeSheet,
        name: String,
    ) -> PyResult<NativeSheet> {
        let storage = lock(&source.storage)?;
        let SheetStorage::Bank { book, id } = &*storage else {
            return Err(PyValueError::new_err(
                "Source sheet is not registered in this workbook",
            ));
        };
        if !Arc::ptr_eq(book, &self.book) {
            return Err(PyValueError::new_err("Cannot copy between workbooks"));
        }
        let id = *id;
        let bank = Arc::clone(&self.book);
        // Validate the ID atomically under the bank lock. Release the handle
        // lock before detaching so GIL reacquisition cannot block a remover.
        drop(storage);
        let new = py.detach(move || {
            let mut bank = lock(&bank)?;
            let new = bank.copy_sheet(id, name).map_err(failure)?;
            bank.set_sheet_visibility(new, SheetVisibility::Visible)
                .map_err(failure)?;
            Ok::<_, PyErr>(new)
        })?;
        Ok(NativeSheet::in_bank(Arc::clone(&self.book), new))
    }
    fn move_sheet(&self, sheet: &NativeSheet, position: usize) -> PyResult<()> {
        let storage = lock(&sheet.storage)?;
        let SheetStorage::Bank { book, id } = &*storage else {
            return Err(PyValueError::new_err("Sheet is not registered"));
        };
        if !Arc::ptr_eq(book, &self.book) {
            return Err(PyValueError::new_err("Sheet belongs to another workbook"));
        }
        lock(&self.book)?.move_sheet(*id, position).map_err(failure)
    }
    fn remove_sheet(&self, sheet: &NativeSheet) -> PyResult<()> {
        let mut storage = lock(&sheet.storage)?;
        let SheetStorage::Bank { book, id } = &*storage else {
            return Err(PyValueError::new_err("Sheet is not registered"));
        };
        if !Arc::ptr_eq(book, &self.book) {
            return Err(PyValueError::new_err("Sheet belongs to another workbook"));
        }
        let removed = lock(&self.book)?.remove_sheet(*id).map_err(failure)?;
        // Removed Python worksheet/cell aliases remain usable, as in openpyxl.
        *storage = SheetStorage::Standalone(removed);
        Ok(())
    }
    fn date_1904(&self) -> PyResult<bool> {
        Ok(lock(&self.book)?.epoch() == DateEpoch::Mac1904)
    }
    fn set_date_1904(&self, value: bool) -> PyResult<()> {
        lock(&self.book)?.set_epoch(if value {
            DateEpoch::Mac1904
        } else {
            DateEpoch::Windows1900
        });
        Ok(())
    }
    fn charged_bytes(&self) -> PyResult<usize> {
        Ok(lock(&self.book)?.charged_bytes())
    }
}
#[pyclass]
struct NativeReader {
    reader: Arc<Mutex<Option<WorkbookReader<streaming::SharedFile>>>>,
    loaded: Option<SharedLoaded>,
    source: streaming::SharedFile,
    alive: Arc<std::sync::atomic::AtomicBool>,
    max_bytes: usize,
    config: resources::ResourceConfig,
}
#[pymethods]
impl NativeReader {
    #[new]
    #[pyo3(signature = (path, max_bytes, resources=None, *, editable=false, data_only=false))]
    fn new(
        py: Python<'_>,
        path: PathBuf,
        max_bytes: usize,
        resources: Option<PyRef<'_, resources::NativeResources>>,
        editable: bool,
        data_only: bool,
    ) -> PyResult<Self> {
        let config = resources.map_or_else(resources::ResourceConfig::default, |value| {
            value.config.clone()
        });
        let source = streaming::SharedFile::open(path)?;
        let input = source.clone();
        let worker_config = config.clone();
        let (reader, loaded) = py.detach(move || {
            let limits = worker_config.reader_limits(max_bytes, false);
            let options = worker_config
                .string_options(max_bytes, limits)
                .map_err(failure)?;
            if editable {
                // max_bytes is the already resolved retained-model allowance.
                // Add back only the canonical working reserve so resolving the
                // joint loaded budget does not subtract it a second time.
                let working = crabxl::memory_allowance(MemoryPolicy::Budget(usize::MAX), limits)
                    .map_err(failure)?
                    .working_reserve_bytes;
                let operation = max_bytes
                    .checked_add(working)
                    .ok_or_else(|| PyValueError::new_err("Loaded operation allowance overflows"))?;
                let loaded = LoadedWorkbook::with_options(
                    input,
                    LoadOptions {
                        resources: limits,
                        memory_policy: MemoryPolicy::Budget(operation),
                        shared_strings: options,
                        workbook: WorkbookLimits {
                            max_bytes,
                            sheet: EditLimits {
                                max_bytes: limits.max_materialized_bytes,
                                ..Default::default()
                            },
                            ..Default::default()
                        },
                        read: ReadOptions {
                            data_only,
                            ..Default::default()
                        },
                        editor: worker_config.editor_options(Some(operation)),
                    },
                )
                .map_err(failure)?;
                return Ok::<_, PyErr>((None, Some(loaded)));
            }
            let mut reader = WorkbookReader::with_limits(input, limits).map_err(failure)?;
            reader.set_shared_string_options(options);
            Ok::<_, PyErr>((Some(reader), None))
        })?;
        Ok(Self {
            reader: Arc::new(Mutex::new(reader)),
            loaded: loaded.map(|book| Arc::new(Mutex::new(Some(book)))),
            source,
            alive: Arc::new(std::sync::atomic::AtomicBool::new(true)),
            max_bytes,
            config,
        })
    }
    fn names(&self) -> PyResult<Vec<String>> {
        if let Some(loaded) = &self.loaded {
            return Ok(lock(loaded)?
                .as_ref()
                .ok_or_else(closed)?
                .model()
                .sheets()
                .map(|(_, sheet)| sheet.name().to_owned())
                .collect());
        }
        Ok(lock(&self.reader)?
            .as_ref()
            .ok_or_else(closed)?
            .sheets()
            .iter()
            .map(|sheet| sheet.name().into())
            .collect())
    }
    fn date_1904(&self) -> PyResult<bool> {
        if let Some(loaded) = &self.loaded {
            return Ok(
                lock(loaded)?.as_ref().ok_or_else(closed)?.model().epoch() == DateEpoch::Mac1904
            );
        }
        Ok(lock(&self.reader)?.as_ref().ok_or_else(closed)?.date_1904())
    }
    fn active_index(&self) -> PyResult<Option<usize>> {
        if let Some(loaded) = &self.loaded {
            return Ok(lock(loaded)?
                .as_ref()
                .ok_or_else(closed)?
                .model()
                .active_index());
        }
        Ok(lock(&self.reader)?
            .as_ref()
            .ok_or_else(closed)?
            .active_index())
    }
    fn active_view_index(&self) -> PyResult<i64> {
        if let Some(loaded) = &self.loaded {
            return Ok(lock(loaded)?
                .as_ref()
                .ok_or_else(closed)?
                .active_view_index());
        }
        Ok(lock(&self.reader)?
            .as_ref()
            .ok_or_else(closed)?
            .active_view_index())
    }
    fn sheet_state(&self, name: &str) -> PyResult<String> {
        if let Some(loaded) = &self.loaded {
            let handle = lock(loaded)?;
            let loaded = handle.as_ref().ok_or_else(closed)?;
            let id = loaded
                .sheet_id(name)
                .ok_or_else(|| PyKeyError::new_err(name.to_owned()))?;
            return Ok(loaded
                .model()
                .sheet(id)
                .map_err(failure)?
                .visibility()
                .as_str()
                .to_owned());
        }
        let handle = lock(&self.reader)?;
        let reader = handle.as_ref().ok_or_else(closed)?;
        let info = reader
            .sheets()
            .iter()
            .find(|sheet| sheet.name() == name)
            .ok_or_else(|| PyKeyError::new_err(name.to_owned()))?;
        Ok(info.visibility().as_str().to_owned())
    }
    fn load_sheet(
        &self,
        py: Python<'_>,
        name: String,
        max_bytes: usize,
        data_only: bool,
    ) -> PyResult<NativeSheet> {
        if let Some(loaded) = &self.loaded {
            let book = Arc::clone(loaded);
            let worker = Arc::clone(&book);
            let id = py.detach(move || {
                let mut handle = lock(&worker)?;
                let loaded = handle.as_mut().ok_or_else(closed)?;
                let id = loaded
                    .sheet_id(&name)
                    .ok_or_else(|| PyKeyError::new_err(name.clone()))?;
                loaded.sheet(id).map_err(failure)?;
                Ok::<_, PyErr>(id)
            })?;
            return Ok(NativeSheet::in_loaded(book, id));
        }
        let max_bytes = max_bytes
            .min(self.max_bytes)
            .min(self.config.materialized_limit.unwrap_or(usize::MAX));
        let reader = Arc::clone(&self.reader);
        let sheet = py.detach(move || {
            let mut handle = lock(&reader)?;
            let book = handle.as_mut().ok_or_else(closed)?;
            let mut sheet = Worksheet::new(
                name.as_str(),
                EditLimits {
                    max_bytes,
                    ..EditLimits::default()
                },
            )
            .map_err(failure)?;
            let mut rows = book
                .rows_with_options(
                    &name,
                    ReadOptions {
                        data_only,
                        ..ReadOptions::default()
                    },
                )
                .map_err(failure)?;
            let mut row = Row::new(RowIndex::new(0).map_err(failure)?);
            while rows.read_row_into(&mut row).map_err(failure)? {
                for cell in row.cells.drain(..) {
                    sheet.set(cell).map_err(failure)?;
                }
            }
            sheet.mark_clean();
            Ok::<_, PyErr>(sheet)
        })?;
        Ok(NativeSheet {
            storage: Arc::new(Mutex::new(SheetStorage::Standalone(sheet))),
        })
    }
    fn close(&self) -> PyResult<()> {
        self.alive
            .store(false, std::sync::atomic::Ordering::Relaxed);
        lock(&self.reader)?.take();
        if let Some(loaded) = &self.loaded {
            lock(loaded)?.take();
        }
        self.source.close()?;
        Ok(())
    }
    fn dimension(&self, name: &str) -> PyResult<Option<(u32, u32, u32, u32)>> {
        Ok(lock(&self.reader)?
            .as_mut()
            .ok_or_else(closed)?
            .worksheet_dimension(name)
            .map_err(failure)?
            .map(|range| {
                (
                    range.start.row.get() + 1,
                    range.start.column.get() + 1,
                    range.end.row.get() + 1,
                    range.end.column.get() + 1,
                )
            }))
    }
    fn number_format(&self, style: u32) -> PyResult<String> {
        if let Some(loaded) = &self.loaded {
            let handle = lock(loaded)?;
            let catalog = handle.as_ref().ok_or_else(closed)?.model().style_catalog();
            return Ok(catalog
                .and_then(|catalog| {
                    catalog
                        .cell_format(StyleId::new(style))
                        .and_then(|format| catalog.number_format(format.number_format_id))
                })
                .unwrap_or("General")
                .to_owned());
        }
        let mut reader = lock(&self.reader)?;
        let catalog = reader
            .as_mut()
            .ok_or_else(closed)?
            .style_catalog()
            .map_err(failure)?;
        Ok(catalog
            .and_then(|catalog| {
                catalog
                    .cell_format(StyleId::new(style))
                    .and_then(|format| catalog.number_format(format.number_format_id))
            })
            .unwrap_or("General")
            .to_owned())
    }
    fn stream(
        &self,
        name: String,
        data_only: bool,
        first_row: u32,
        last_row: Option<u32>,
        first_column: u32,
        last_column: Option<u32>,
    ) -> PyResult<streaming::NativeReadStream> {
        if !self.alive.load(std::sync::atomic::Ordering::Relaxed) {
            return Err(closed());
        }
        streaming::NativeReadStream::start(
            self.source.clone(),
            Arc::clone(&self.alive),
            self.max_bytes,
            self.config.clone(),
            name,
            data_only,
            first_row,
            last_row,
            first_column,
            last_column,
        )
    }
}
#[pyclass]
struct NativeEditor {
    editor: Arc<Mutex<Option<WorkbookEditor<File>>>>,
    loaded: Option<SharedLoaded>,
}
#[pymethods]
impl NativeEditor {
    #[new]
    #[pyo3(signature = (path, max_bytes=None, resources=None, *, reader=None))]
    fn new(
        py: Python<'_>,
        path: PathBuf,
        max_bytes: Option<usize>,
        resources: Option<PyRef<'_, resources::NativeResources>>,
        reader: Option<PyRef<'_, NativeReader>>,
    ) -> PyResult<Self> {
        if let Some(reader) = reader {
            let loaded = reader.loaded.as_ref().ok_or_else(|| {
                PyValueError::new_err("The reader must own an editable loaded workbook")
            })?;
            lock(loaded)?.as_ref().ok_or_else(closed)?;
            return Ok(Self {
                editor: Arc::new(Mutex::new(None)),
                loaded: Some(Arc::clone(loaded)),
            });
        }
        let config = resources.map_or_else(resources::ResourceConfig::default, |value| {
            value.config.clone()
        });
        let options = config.editor_options(max_bytes);
        let editor = py.detach(move || {
            let file = File::open(path).map_err(|error| PyOSError::new_err(error.to_string()))?;
            WorkbookEditor::with_options(file, options).map_err(failure)
        })?;
        Ok(Self {
            editor: Arc::new(Mutex::new(Some(editor))),
            loaded: None,
        })
    }
    fn set(
        &self,
        py: Python<'_>,
        name: &str,
        row: u32,
        col: u32,
        value: TaggedValue,
    ) -> PyResult<()> {
        if let Some(loaded) = &self.loaded {
            let value = decode(py, value)?;
            let mut handle = lock(loaded)?;
            let loaded = handle.as_mut().ok_or_else(closed)?;
            let id = loaded
                .sheet_id(name)
                .ok_or_else(|| PyKeyError::new_err(name.to_owned()))?;
            return loaded
                .upsert_value(id, CellAddress::new(row, col).map_err(failure)?, value)
                .map_err(failure);
        }
        lock(&self.editor)?
            .as_mut()
            .ok_or_else(closed)?
            .upsert_value(
                name,
                CellAddress::new(row, col).map_err(failure)?,
                decode(py, value)?,
            )
            .map_err(failure)
    }
    fn pending(
        &self,
        py: Python<'_>,
        name: &str,
        row: u32,
        col: u32,
    ) -> PyResult<Option<EncodedValue>> {
        if let Some(loaded) = &self.loaded {
            let handle = lock(loaded)?;
            let loaded = handle.as_ref().ok_or_else(closed)?;
            let id = loaded
                .sheet_id(name)
                .ok_or_else(|| PyKeyError::new_err(name.to_owned()))?;
            return loaded
                .pending_value(id, CellAddress::new(row, col).map_err(failure)?)
                .map(|value| encode(py, value))
                .transpose();
        }
        let editor = lock(&self.editor)?;
        editor
            .as_ref()
            .ok_or_else(closed)?
            .pending_value(name, CellAddress::new(row, col).map_err(failure)?)
            .map(|value| encode(py, value))
            .transpose()
    }
    fn apply(&self, name: &str, sheet: &NativeSheet) -> PyResult<()> {
        if let Some(loaded) = &self.loaded {
            let storage = lock(&sheet.storage)?;
            let SheetStorage::Loaded { book, id } = &*storage else {
                return Err(PyValueError::new_err(
                    "Loaded sheet belongs to a different owner",
                ));
            };
            if !Arc::ptr_eq(loaded, book) {
                return Err(PyValueError::new_err(
                    "Loaded sheet belongs to a different owner",
                ));
            }
            let handle = lock(loaded)?;
            let loaded = handle.as_ref().ok_or_else(closed)?;
            if loaded.sheet_id(name) != Some(*id) {
                return Err(PyValueError::new_err(
                    "Loaded sheet identity does not match",
                ));
            }
            // The core coordinator already synchronizes pending values with
            // cached models; repeating clones here would bypass its accounting.
            return Ok(());
        }
        let editor = lock(&self.editor)?;
        let editor = editor.as_ref().ok_or_else(closed)?;
        sheet.with_mut(|sheet| {
            for cell in editor.pending_cells(name) {
                let mut cell = cell.clone();
                cell.style = sheet
                    .get(cell.address)
                    .map_or(StyleId::new(0), |old| old.style);
                sheet.set(cell).map_err(failure)?;
            }
            Ok(())
        })
    }
    fn bounds(&self, name: &str) -> PyResult<(u32, u32)> {
        if let Some(loaded) = &self.loaded {
            let handle = lock(loaded)?;
            let loaded = handle.as_ref().ok_or_else(closed)?;
            let id = loaded
                .sheet_id(name)
                .ok_or_else(|| PyKeyError::new_err(name.to_owned()))?;
            return Ok(loaded.pending_cells(id).fold((0, 0), |(rows, cols), cell| {
                (
                    rows.max(cell.address.row.get() + 1),
                    cols.max(cell.address.column.get() + 1),
                )
            }));
        }
        let editor = lock(&self.editor)?;
        let editor = editor.as_ref().ok_or_else(closed)?;
        Ok(editor
            .pending_cells(name)
            .fold((0, 0), |(rows, cols), cell| {
                (
                    rows.max(cell.address.row.get() + 1),
                    cols.max(cell.address.column.get() + 1),
                )
            }))
    }
    fn patch_bytes(&self) -> PyResult<usize> {
        if let Some(loaded) = &self.loaded {
            return Ok(lock(loaded)?.as_ref().ok_or_else(closed)?.patch_bytes());
        }
        Ok(lock(&self.editor)?
            .as_ref()
            .ok_or_else(closed)?
            .patch_bytes())
    }
    fn set_active_view_index(&self, index: i64) -> PyResult<()> {
        if let Some(loaded) = &self.loaded {
            return lock(loaded)?
                .as_mut()
                .ok_or_else(closed)?
                .set_active_view_index(index)
                .map_err(failure);
        }
        lock(&self.editor)?
            .as_mut()
            .ok_or_else(closed)?
            .set_active_view_index(index)
            .map_err(failure)
    }
    #[pyo3(signature = (name, state, view_index=None))]
    fn set_sheet_state(&self, name: &str, state: &str, view_index: Option<i64>) -> PyResult<()> {
        let state = visibility(state)?;
        if let Some(loaded) = &self.loaded {
            let mut handle = lock(loaded)?;
            let loaded = handle.as_mut().ok_or_else(closed)?;
            let id = loaded
                .sheet_id(name)
                .ok_or_else(|| PyKeyError::new_err(name.to_owned()))?;
            let view = view_index.unwrap_or_else(|| loaded.active_view_index());
            return loaded
                .set_sheet_visibility_and_active_view(id, state, view)
                .map_err(failure);
        }
        if view_index.is_some() {
            return Err(PyNotImplementedError::new_err(
                "Combined visibility/view changes require the shared loaded coordinator",
            ));
        }
        lock(&self.editor)?
            .as_mut()
            .ok_or_else(closed)?
            .set_sheet_visibility(name, state)
            .map_err(failure)
    }
    fn sheet_handle(&self, name: &str) -> PyResult<NativeSheet> {
        let book = self.loaded.as_ref().ok_or_else(|| {
            PyNotImplementedError::new_err("Lazy handles require the canonical loaded bank")
        })?;
        let id = lock(book)?
            .as_ref()
            .ok_or_else(closed)?
            .sheet_id(name)
            .ok_or_else(|| PyKeyError::new_err(name.to_owned()))?;
        Ok(NativeSheet::in_loaded(Arc::clone(book), id))
    }
    fn remove_sheet(&self, py: Python<'_>, sheet: &NativeSheet) -> PyResult<()> {
        let book = self.loaded.as_ref().ok_or_else(|| {
            PyNotImplementedError::new_err("Sheet removal requires the canonical loaded bank")
        })?;
        let book = Arc::clone(book);
        let storage = Arc::clone(&sheet.storage);
        py.detach(move || {
            let mut storage = lock(&storage)?;
            let SheetStorage::Loaded { book: owner, id } = &*storage else {
                return Err(PyValueError::new_err(
                    "Sheet is not registered in the loaded workbook",
                ));
            };
            if !Arc::ptr_eq(owner, &book) {
                return Err(PyValueError::new_err(
                    "Sheet belongs to a different workbook",
                ));
            }
            let removed = lock(&book)?
                .as_mut()
                .ok_or_else(closed)?
                .remove_sheet(*id)
                .map_err(failure)?;
            *storage = SheetStorage::Standalone(removed);
            Ok(())
        })
    }
    fn copy_sheet(&self, py: Python<'_>, source: String, name: String) -> PyResult<NativeSheet> {
        let book = self.loaded.as_ref().ok_or_else(|| {
            PyNotImplementedError::new_err("Sheet copy requires the canonical loaded bank")
        })?;
        let worker = Arc::clone(book);
        let id = py.detach(move || {
            let mut handle = lock(&worker)?;
            let loaded = handle.as_mut().ok_or_else(closed)?;
            let source = loaded
                .sheet_id(&source)
                .ok_or_else(|| PyKeyError::new_err(source))?;
            let id = loaded.copy_sheet(source, name).map_err(failure)?;
            loaded
                .set_sheet_visibility(id, SheetVisibility::Visible)
                .map_err(failure)?;
            Ok::<_, PyErr>(id)
        })?;
        Ok(NativeSheet::in_loaded(Arc::clone(book), id))
    }
    fn create_sheet(&self, py: Python<'_>, name: String) -> PyResult<NativeSheet> {
        let book = self.loaded.as_ref().ok_or_else(|| {
            PyNotImplementedError::new_err("Sheet creation requires the canonical loaded bank")
        })?;
        let worker = Arc::clone(book);
        let id = py.detach(move || {
            lock(&worker)?
                .as_mut()
                .ok_or_else(closed)?
                .create_sheet(name)
                .map_err(failure)
        })?;
        Ok(NativeSheet::in_loaded(Arc::clone(book), id))
    }
    fn rename_sheet(&self, py: Python<'_>, name: String, title: String) -> PyResult<()> {
        if let Some(loaded) = &self.loaded {
            let loaded = Arc::clone(loaded);
            return py.detach(move || {
                let mut handle = lock(&loaded)?;
                let loaded = handle.as_mut().ok_or_else(closed)?;
                let id = loaded
                    .sheet_id(&name)
                    .ok_or_else(|| PyKeyError::new_err(name.clone()))?;
                loaded.rename_sheet(id, title).map_err(failure)
            });
        }
        let editor = Arc::clone(&self.editor);
        py.detach(move || {
            lock(&editor)?
                .as_mut()
                .ok_or_else(closed)?
                .rename_sheet(&name, title)
                .map_err(failure)
        })
    }
    fn move_sheet(&self, py: Python<'_>, name: String, position: usize) -> PyResult<()> {
        if let Some(loaded) = &self.loaded {
            let loaded = Arc::clone(loaded);
            return py.detach(move || {
                let mut handle = lock(&loaded)?;
                let loaded = handle.as_mut().ok_or_else(closed)?;
                let id = loaded
                    .sheet_id(&name)
                    .ok_or_else(|| PyKeyError::new_err(name.clone()))?;
                loaded.move_sheet(id, position).map_err(failure)
            });
        }
        let editor = Arc::clone(&self.editor);
        py.detach(move || {
            lock(&editor)?
                .as_mut()
                .ok_or_else(closed)?
                .move_sheet(&name, position)
                .map_err(failure)
        })
    }
    #[pyo3(signature = (path, verify, compression_level=None))]
    fn save(
        &self,
        py: Python<'_>,
        path: PathBuf,
        verify: bool,
        compression_level: Option<u8>,
    ) -> PyResult<i64> {
        if let Some(loaded) = &self.loaded {
            let loaded = Arc::clone(loaded);
            return py.detach(move || {
                let mut handle = lock(&loaded)?;
                let loaded = handle.as_mut().ok_or_else(closed)?;
                loaded
                    .save_path(
                        path,
                        SaveOptions {
                            verify_unchanged: verify,
                            compression_level,
                        },
                    )
                    .map_err(failure)?;
                Ok(loaded.active_view_index())
            });
        }
        let editor = Arc::clone(&self.editor);
        py.detach(move || {
            let mut handle = lock(&editor)?;
            let editor = handle.as_mut().ok_or_else(closed)?;
            editor
                .save_path(
                    path,
                    SaveOptions {
                        verify_unchanged: verify,
                        compression_level,
                    },
                )
                .map_err(failure)?;
            Ok(editor.active_view_index())
        })
    }
    fn close(&self) -> PyResult<()> {
        lock(&self.editor)?.take();
        if let Some(loaded) = &self.loaded {
            lock(loaded)?.take();
        }
        Ok(())
    }
}
#[pyfunction]
fn tokenize_formula<'py>(
    py: Python<'py>,
    expression: &str,
    max_bytes: usize,
) -> PyResult<Bound<'py, PyList>> {
    let tokens = crabxl::tokenize_formula(expression, max_bytes).map_err(failure)?;
    PyList::new(
        py,
        tokens.iter().map(|token| {
            (
                token.value.as_ref(),
                token.kind.as_str(),
                token.subtype.as_str(),
            )
        }),
    )
}
#[pyfunction]
fn classify_formula_operand(value: &str) -> &'static str {
    crabxl::classify_formula_operand(value).as_str()
}
#[pyfunction]
fn translate_formula(
    expression: &str,
    rows: i64,
    columns: i64,
    max_bytes: usize,
) -> PyResult<String> {
    crabxl::translate_expression(expression, rows, columns, max_bytes).map_err(failure)
}
#[pyfunction]
fn translate_axis(reference: &str, delta: i64, row: bool) -> PyResult<String> {
    crabxl::translate_axis(reference, delta, row).map_err(failure)
}
#[pyfunction]
fn formula_position(reference: &str) -> PyResult<(u64, u32)> {
    crabxl::formula_position(reference).map_err(failure)
}
#[pyfunction]
fn cell_address(reference: &str) -> PyResult<(u32, u32)> {
    let address: CellAddress = reference.parse().map_err(failure)?;
    Ok((address.row.get() + 1, address.column.get() + 1))
}
#[pyfunction]
fn column_index(reference: &str) -> PyResult<u32> {
    let address: CellAddress = format!("{reference}1").parse().map_err(failure)?;
    Ok(address.column.get() + 1)
}
#[pyfunction]
fn column_letters(column: u32) -> PyResult<String> {
    let index = column
        .checked_sub(1)
        .ok_or_else(|| PyValueError::new_err("Column index must be positive"))?;
    let mut coordinate = CellAddress::new(0, index).map_err(failure)?.to_string();
    coordinate.pop();
    Ok(coordinate)
}
#[pyfunction]
fn finite_range(reference: &str) -> PyResult<(u32, u32, u32, u32)> {
    let (first, last) = reference.split_once(':').unwrap_or((reference, reference));
    let range = CellRange::new(
        first.parse().map_err(failure)?,
        last.parse().map_err(failure)?,
    )
    .map_err(failure)?;
    Ok((
        range.start.row.get() + 1,
        range.start.column.get() + 1,
        range.end.row.get() + 1,
        range.end.column.get() + 1,
    ))
}
#[pyfunction]
#[pyo3(signature = (max_bytes, resources=None))]
fn resolve_model_budget(
    max_bytes: Option<usize>,
    resources: Option<PyRef<'_, resources::NativeResources>>,
) -> PyResult<usize> {
    if let Some(bytes) = max_bytes {
        if bytes == 0 {
            return Err(PyValueError::new_err("Memory allowance must be positive"));
        }
        Ok(bytes)
    } else {
        let config = resources.map_or_else(resources::ResourceConfig::default, |value| {
            value.config.clone()
        });
        crabxl::memory_allowance(config.memory_policy, config.limits)
            .map(|allowance| allowance.retained_data_bytes)
            .map_err(failure)
    }
}
#[pyfunction]
#[pyo3(signature = (path, sheets, active_sheet=0, iso_dates=false, date_1904=false, compression_level=None, book=None))]
// Preserve the legacy private binding arguments while accepting its canonical owner.
#[allow(clippy::too_many_arguments)]
fn save_models(
    py: Python<'_>,
    path: PathBuf,
    sheets: Vec<Py<NativeSheet>>,
    active_sheet: i64,
    iso_dates: bool,
    date_1904: bool,
    compression_level: Option<u8>,
    book: Option<PyRef<'_, NativeBook>>,
) -> PyResult<i64> {
    let book = book.map(|book| Arc::clone(&book.book));
    let sheets = sheets
        .iter()
        .map(|sheet| Arc::clone(&sheet.borrow(py).storage))
        .collect::<Vec<_>>();
    py.detach(move || {
        let options = WriteOptions {
            compression_level,
            iso_dates,
            date_1904,
            ..WriteOptions::default()
        };
        let mut writer = if let Some(book) = &book {
            let book = lock(book)?;
            let mut writer = if let Some(catalog) = book.style_catalog() {
                WorkbookWriter::from_style_catalog(options, catalog.clone())
            } else {
                WorkbookWriter::new(options)
            }
            .map_err(failure)?;
            writer.write_workbook(&book).map_err(failure)?;
            writer
        } else {
            let mut writer = WorkbookWriter::new(options).map_err(failure)?;
            for sheet in sheets {
                NativeSheet { storage: sheet }
                    .with(|sheet| writer.write_worksheet(sheet).map_err(failure))?;
            }
            writer
        };
        writer
            .set_active_view_index(active_sheet)
            .map_err(failure)?;
        let active_after = writer
            .active_view_selection()
            .map_err(failure)?
            .requested_index;
        // Protect an existing target through failures, with a full adjacent
        // output ZIP rather than duplicating model payloads in memory.
        let parent = path
            .parent()
            .filter(|parent| !parent.as_os_str().is_empty())
            .unwrap_or_else(|| std::path::Path::new("."));
        let mut temporary = tempfile::Builder::new()
            .prefix("crabxl-python-")
            .tempfile_in(parent)
            .map_err(|error| PyOSError::new_err(error.to_string()))?;
        writer.finish(&mut temporary).map_err(failure)?;
        temporary
            .persist(path)
            .map_err(|error| PyOSError::new_err(error.error.to_string()))?;
        Ok(active_after)
    })
}
#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<NativeSheet>()?;
    module.add_class::<streaming::NativeReadStream>()?;
    module.add_class::<streaming::NativeWriteBook>()?;
    module.add_class::<NativeBook>()?;
    module.add_class::<NativeReader>()?;
    module.add_class::<resources::NativeResources>()?;
    module.add_class::<NativeEditor>()?;
    module.add_function(wrap_pyfunction!(save_models, module)?)?;
    module.add_function(wrap_pyfunction!(resolve_model_budget, module)?)?;
    module.add_function(wrap_pyfunction!(cell_address, module)?)?;
    module.add_function(wrap_pyfunction!(translate_formula, module)?)?;
    module.add_function(wrap_pyfunction!(tokenize_formula, module)?)?;
    module.add_function(wrap_pyfunction!(classify_formula_operand, module)?)?;
    module.add_function(wrap_pyfunction!(formula_position, module)?)?;
    module.add_function(wrap_pyfunction!(translate_axis, module)?)?;
    module.add_function(wrap_pyfunction!(column_index, module)?)?;
    module.add_function(wrap_pyfunction!(column_letters, module)?)?;
    module.add_function(wrap_pyfunction!(finite_range, module)?)?;
    Ok(())
}
