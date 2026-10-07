//! Formula, address, budget and save entry points.
use crate::*;

#[pyfunction]
pub(crate) fn tokenize_formula<'py>(
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
pub(crate) fn classify_formula_operand(value: &str) -> &'static str {
    crabxl::classify_formula_operand(value).as_str()
}
#[pyfunction]
pub(crate) fn translate_formula(
    expression: &str,
    rows: i64,
    columns: i64,
    max_bytes: usize,
) -> PyResult<String> {
    crabxl::translate_expression(expression, rows, columns, max_bytes).map_err(failure)
}
#[pyfunction]
pub(crate) fn translate_axis(reference: &str, delta: i64, row: bool) -> PyResult<String> {
    crabxl::translate_axis(reference, delta, row).map_err(failure)
}
#[pyfunction]
pub(crate) fn formula_position(reference: &str) -> PyResult<(u64, u32)> {
    crabxl::formula_position(reference).map_err(failure)
}
#[pyfunction]
pub(crate) fn cell_address(reference: &str) -> PyResult<(u32, u32)> {
    let address: CellAddress = reference.parse().map_err(failure)?;
    Ok((address.row.get() + 1, address.column.get() + 1))
}
#[pyfunction]
pub(crate) fn column_index(reference: &str) -> PyResult<u32> {
    let address: CellAddress = format!("{reference}1").parse().map_err(failure)?;
    Ok(address.column.get() + 1)
}
#[pyfunction]
pub(crate) fn column_letters(column: u32) -> PyResult<String> {
    let index = column
        .checked_sub(1)
        .ok_or_else(|| PyValueError::new_err("Column index must be positive"))?;
    let mut coordinate = CellAddress::new(0, index).map_err(failure)?.to_string();
    coordinate.pop();
    Ok(coordinate)
}
#[pyfunction]
pub(crate) fn finite_range(reference: &str) -> PyResult<(u32, u32, u32, u32)> {
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
pub(crate) fn resolve_model_budget(
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
pub(crate) fn save_models(
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
                WorkbookWriter::from_canonical_style_catalog(options, catalog.clone())
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
