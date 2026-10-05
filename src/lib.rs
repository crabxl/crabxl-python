//! Foreign objects and naming remain outside the canonical Rust core.
mod streaming;

use crabxl::{
    Cell, CellAddress, CellRange, CellValue, ColumnIndex, DataTableOptions, DateEpoch, DateKind,
    EditLimits, EditorOptions, Error, ErrorKind, ExactInteger, ExcelDateTime, Formula, FormulaFlag,
    FormulaFlags, FormulaMetadata, FormulaRange, FormulaType, MemoryPolicy, ReadOptions,
    ResourceLimits, Row, RowIndex, SaveOptions, SheetId, StyleId, Workbook, WorkbookEditor,
    WorkbookLimits, WorkbookReader, WorkbookWriter, Worksheet, WorksheetEditor, WriteOptions,
};
use pyo3::{
    IntoPyObjectExt,
    exceptions::{
        PyKeyError, PyMemoryError, PyNotImplementedError, PyOSError, PyRuntimeError, PyValueError,
    },
    prelude::*,
    types::PyDict,
};
use std::{
    fs::File,
    path::PathBuf,
    sync::{Arc, Mutex, MutexGuard},
};

type TaggedValue = (String, Py<PyAny>);
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
        _ => PyValueError::new_err(text),
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
fn encode(py: Python<'_>, value: &CellValue) -> PyResult<TaggedValue> {
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
    Ok((kind.into(), object))
}

// A handle owns either a detached worksheet or a stable identity in the shared
// core bank. No Python object or payload clone lives in the canonical model.
enum SheetStorage {
    Standalone(Worksheet),
    Bank {
        book: Arc<Mutex<Workbook>>,
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
    fn get(&self, py: Python<'_>, row: u32, column: u32) -> PyResult<TaggedValue> {
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
    ) -> PyResult<Vec<TaggedValue>> {
        CellAddress::new(row, first).map_err(failure)?;
        CellAddress::new(row, last).map_err(failure)?;
        if first > last {
            return Ok(Vec::new());
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
    fn remove(&self, row: u32, column: u32) -> PyResult<()> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        self.with_mut(|sheet| {
            sheet.remove(address);
            Ok(())
        })
    }
    fn append(&self, py: Python<'_>, values: Vec<TaggedValue>) -> PyResult<u32> {
        let values = values
            .into_iter()
            .map(|value| decode(py, value))
            .collect::<PyResult<Vec<_>>>()?;
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
    fn rename(&self, name: String) -> PyResult<()> {
        let mut storage = lock(&self.storage)?;
        match &mut *storage {
            SheetStorage::Standalone(sheet) => sheet.rename(name).map_err(failure),
            SheetStorage::Bank { book, id } => lock(book)?.rename_sheet(*id, name).map_err(failure),
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
        let new = py.detach(move || lock(&bank)?.copy_sheet(id, name).map_err(failure))?;
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
    source: streaming::SharedFile,
    alive: Arc<std::sync::atomic::AtomicBool>,
    max_bytes: usize,
}
#[pymethods]
impl NativeReader {
    #[new]
    fn new(py: Python<'_>, path: PathBuf, max_bytes: usize) -> PyResult<Self> {
        let source = streaming::SharedFile::open(path)?;
        let input = source.clone();
        let reader = py.detach(move || {
            let limits = ResourceLimits {
                max_materialized_bytes: max_bytes,
                ..ResourceLimits::default()
            };
            let working = crabxl::memory_allowance(MemoryPolicy::Budget(usize::MAX), limits)
                .map_err(failure)?
                .working_reserve_bytes;
            let budget = max_bytes
                .checked_add(working)
                .ok_or_else(|| PyValueError::new_err("Shared-string allowance overflows"))?;
            let mut reader = WorkbookReader::with_limits(input, limits).map_err(failure)?;
            reader.set_shared_string_options(crabxl::SharedStringOptions {
                memory_policy: MemoryPolicy::Budget(budget),
                ..crabxl::SharedStringOptions::default()
            });
            Ok::<_, PyErr>(reader)
        })?;
        Ok(Self {
            reader: Arc::new(Mutex::new(Some(reader))),
            source,
            alive: Arc::new(std::sync::atomic::AtomicBool::new(true)),
            max_bytes,
        })
    }
    fn names(&self) -> PyResult<Vec<String>> {
        Ok(lock(&self.reader)?
            .as_ref()
            .ok_or_else(closed)?
            .sheets()
            .iter()
            .map(|sheet| sheet.name().into())
            .collect())
    }
    fn date_1904(&self) -> PyResult<bool> {
        Ok(lock(&self.reader)?.as_ref().ok_or_else(closed)?.date_1904())
    }
    fn active_index(&self) -> PyResult<Option<usize>> {
        Ok(lock(&self.reader)?
            .as_ref()
            .ok_or_else(closed)?
            .active_index())
    }
    fn load_sheet(
        &self,
        py: Python<'_>,
        name: String,
        max_bytes: usize,
        data_only: bool,
    ) -> PyResult<NativeSheet> {
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
}
#[pymethods]
impl NativeEditor {
    #[new]
    #[pyo3(signature = (path, max_bytes=None))]
    fn new(py: Python<'_>, path: PathBuf, max_bytes: Option<usize>) -> PyResult<Self> {
        let editor = py.detach(move || {
            let file = File::open(path).map_err(|error| PyOSError::new_err(error.to_string()))?;
            WorkbookEditor::with_options(
                file,
                EditorOptions {
                    memory_policy: max_bytes
                        .map_or_else(MemoryPolicy::default, MemoryPolicy::Budget),
                    ..EditorOptions::default()
                },
            )
            .map_err(failure)
        })?;
        Ok(Self {
            editor: Arc::new(Mutex::new(Some(editor))),
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
    ) -> PyResult<Option<TaggedValue>> {
        let editor = lock(&self.editor)?;
        editor
            .as_ref()
            .ok_or_else(closed)?
            .pending_value(name, CellAddress::new(row, col).map_err(failure)?)
            .map(|value| encode(py, value))
            .transpose()
    }
    fn apply(&self, name: &str, sheet: &NativeSheet) -> PyResult<()> {
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
        Ok(lock(&self.editor)?
            .as_ref()
            .ok_or_else(closed)?
            .patch_bytes())
    }
    fn save(&self, py: Python<'_>, path: PathBuf, verify: bool) -> PyResult<()> {
        let editor = Arc::clone(&self.editor);
        py.detach(move || {
            lock(&editor)?
                .as_mut()
                .ok_or_else(closed)?
                .save_path(
                    path,
                    SaveOptions {
                        verify_unchanged: verify,
                    },
                )
                .map(|_| ())
                .map_err(failure)
        })
    }
    fn close(&self) -> PyResult<()> {
        lock(&self.editor)?.take();
        Ok(())
    }
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
fn resolve_model_budget(max_bytes: Option<usize>) -> PyResult<usize> {
    if let Some(bytes) = max_bytes {
        if bytes == 0 {
            return Err(PyValueError::new_err("Memory allowance must be positive"));
        }
        Ok(bytes)
    } else {
        crabxl::memory_allowance(MemoryPolicy::default(), ResourceLimits::default())
            .map(|allowance| allowance.retained_data_bytes)
            .map_err(failure)
    }
}
#[pyfunction]
#[pyo3(signature = (path, sheets, active_sheet=0, iso_dates=false, date_1904=false))]
fn save_models(
    py: Python<'_>,
    path: PathBuf,
    sheets: Vec<Py<NativeSheet>>,
    active_sheet: usize,
    iso_dates: bool,
    date_1904: bool,
) -> PyResult<()> {
    let sheets = sheets
        .iter()
        .map(|sheet| Arc::clone(&sheet.borrow(py).storage))
        .collect::<Vec<_>>();
    py.detach(move || {
        let mut writer = WorkbookWriter::new(WriteOptions {
            active_sheet,
            iso_dates,
            date_1904,
            ..WriteOptions::default()
        })
        .map_err(failure)?;
        for sheet in sheets {
            NativeSheet { storage: sheet }
                .with(|sheet| writer.write_worksheet(sheet).map_err(failure))?;
        }
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
        Ok(())
    })
}
#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<NativeSheet>()?;
    module.add_class::<streaming::NativeReadStream>()?;
    module.add_class::<streaming::NativeWriteBook>()?;
    module.add_class::<NativeBook>()?;
    module.add_class::<NativeReader>()?;
    module.add_class::<NativeEditor>()?;
    module.add_function(wrap_pyfunction!(save_models, module)?)?;
    module.add_function(wrap_pyfunction!(resolve_model_budget, module)?)?;
    module.add_function(wrap_pyfunction!(cell_address, module)?)?;
    module.add_function(wrap_pyfunction!(translate_formula, module)?)?;
    module.add_function(wrap_pyfunction!(formula_position, module)?)?;
    module.add_function(wrap_pyfunction!(translate_axis, module)?)?;
    module.add_function(wrap_pyfunction!(column_index, module)?)?;
    module.add_function(wrap_pyfunction!(column_letters, module)?)?;
    module.add_function(wrap_pyfunction!(finite_range, module)?)?;
    Ok(())
}
