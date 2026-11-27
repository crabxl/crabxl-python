//! `crabxl_bindings._native.ApiWorkbook`: the engine behind `crabxl.Workbook`.

use super::convert::{
    Modes, Phase, color_from_python, color_to_python, error, from_python,
    partial_style_from_python, partial_style_to_python, raise, row_from_python, style_from_python,
    style_to_python, to_python,
};
use crabxl::features::{
    Chart, ChartKind, Comparison, ConditionalFormat, ConditionalKind, DataValidation, DefinedName,
    Hyperlink, Image, Margins, Note, Orientation, PageSetup, Series, Table, ValidationKind,
};
use crabxl::{
    CellRef, DataLossPolicy, Limits, Memory, OpenOptions, SaveOptions, Span, Temporal, Visibility,
    Workbook,
};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList, PyTuple};
use std::io::Cursor;
use std::sync::{Mutex, MutexGuard};

#[pyclass(frozen, module = "crabxl_bindings._native")]
pub(crate) struct ApiWorkbook {
    book: Mutex<Option<Workbook>>,
    modes: Modes,
}

pub(crate) fn open_options(
    limits: &str,
    memory: Option<usize>,
    data_loss: &str,
    exact: bool,
) -> PyResult<OpenOptions> {
    let limits = match limits {
        "default" => Limits::Default,
        "strict" => Limits::Strict,
        "unlimited" => Limits::Unlimited,
        other => {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "limits must be 'default', 'strict' or 'unlimited', not {other:?}"
            )));
        }
    };
    let data_loss = match data_loss {
        "reject" => DataLossPolicy::Reject,
        "allow" => DataLossPolicy::Allow,
        other => {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "data_loss must be 'reject' or 'allow', not {other:?}"
            )));
        }
    };
    Ok(OpenOptions::new()
        .with_limits(limits)
        .with_memory(memory.map_or(Memory::Auto, Memory::Budget))
        .with_data_loss(data_loss)
        .with_exact_numbers(exact))
}

/// The Python spelling of a comparison.
fn comparison_name(comparison: Comparison) -> &'static str {
    match comparison {
        Comparison::Between => "between",
        Comparison::NotBetween => "not_between",
        Comparison::Equal => "==",
        Comparison::NotEqual => "!=",
        Comparison::GreaterThan => ">",
        Comparison::GreaterThanOrEqual => ">=",
        Comparison::LessThan => "<",
        Comparison::LessThanOrEqual => "<=",
        _ => "between",
    }
}

fn comparison(name: &str) -> PyResult<Comparison> {
    Ok(match name {
        "between" => Comparison::Between,
        "not_between" => Comparison::NotBetween,
        "==" | "equal" => Comparison::Equal,
        "!=" | "not_equal" => Comparison::NotEqual,
        ">" | "greater_than" => Comparison::GreaterThan,
        ">=" | "greater_than_or_equal" => Comparison::GreaterThanOrEqual,
        "<" | "less_than" => Comparison::LessThan,
        "<=" | "less_than_or_equal" => Comparison::LessThanOrEqual,
        other => {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Unknown comparison {other:?}"
            )));
        }
    })
}

fn visibility_name(visibility: Visibility) -> &'static str {
    match visibility {
        Visibility::Hidden => "hidden",
        Visibility::VeryHidden => "very_hidden",
        _ => "visible",
    }
}

impl ApiWorkbook {
    fn guard(&self, py: Python<'_>) -> PyResult<MutexGuard<'_, Option<Workbook>>> {
        let guard = self
            .book
            .lock()
            .map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("Workbook lock was poisoned"))?;
        if guard.is_none() {
            return Err(error(py, "StateError", "The workbook is closed"));
        }
        Ok(guard)
    }
    /// Run `work` on the workbook.
    fn book<R>(
        &self,
        py: Python<'_>,
        work: impl FnOnce(&mut Workbook) -> crabxl::Result<R>,
    ) -> PyResult<R> {
        let mut guard = self.guard(py)?;
        let book = guard
            .as_mut()
            .ok_or_else(|| error(py, "StateError", "The workbook is closed"))?;
        work(book).map_err(|e| raise(py, e, Phase::Edit))
    }
    /// Run `work` on one worksheet.
    fn sheet<R>(
        &self,
        py: Python<'_>,
        sheet: &str,
        work: impl FnOnce(&mut crabxl::Worksheet<'_>) -> crabxl::Result<R>,
    ) -> PyResult<R> {
        self.book(py, |book| {
            let mut handle = book.worksheet(sheet)?;
            work(&mut handle)
        })
    }
    fn wrap(book: Workbook, modes: Modes) -> Self {
        Self {
            book: Mutex::new(Some(book)),
            modes,
        }
    }
}

#[pymethods]
impl ApiWorkbook {
    #[staticmethod]
    fn create(py: Python<'_>, serial_dates: bool) -> PyResult<Self> {
        let book = Workbook::new().map_err(|e| raise(py, e, Phase::Edit))?;
        Ok(Self::wrap(
            book,
            Modes {
                exact_numbers: false,
                serial_dates,
            },
        ))
    }
    #[staticmethod]
    #[pyo3(signature = (path, limits, memory, data_loss, exact_numbers, serial_dates))]
    fn open_path(
        py: Python<'_>,
        path: std::path::PathBuf,
        limits: &str,
        memory: Option<usize>,
        data_loss: &str,
        exact_numbers: bool,
        serial_dates: bool,
    ) -> PyResult<Self> {
        let options = open_options(limits, memory, data_loss, exact_numbers)?;
        let book = py
            .detach(|| Workbook::open_with(&path, &options))
            .map_err(|e| raise(py, e, Phase::Open))?;
        Ok(Self::wrap(
            book,
            Modes {
                exact_numbers,
                serial_dates,
            },
        ))
    }
    #[staticmethod]
    #[pyo3(signature = (data, limits, memory, data_loss, exact_numbers, serial_dates))]
    fn open_bytes(
        py: Python<'_>,
        data: Vec<u8>,
        limits: &str,
        memory: Option<usize>,
        data_loss: &str,
        exact_numbers: bool,
        serial_dates: bool,
    ) -> PyResult<Self> {
        let options = open_options(limits, memory, data_loss, exact_numbers)?;
        let book = py
            .detach(|| Workbook::from_reader(Cursor::new(data), &options))
            .map_err(|e| raise(py, e, Phase::Open))?;
        Ok(Self::wrap(
            book,
            Modes {
                exact_numbers,
                serial_dates,
            },
        ))
    }
    fn close(&self) -> PyResult<()> {
        if let Ok(mut guard) = self.book.lock() {
            guard.take();
        }
        Ok(())
    }
    fn is_closed(&self) -> bool {
        self.book.lock().map_or(true, |guard| guard.is_none())
    }
    fn save_path(
        &self,
        py: Python<'_>,
        path: std::path::PathBuf,
        compression: Option<u8>,
        recalculate: bool,
    ) -> PyResult<()> {
        let mut options = SaveOptions::new().with_recalculate_on_open(recalculate);
        options.compression = compression;
        let mut guard = self.guard(py)?;
        let book = guard
            .as_mut()
            .ok_or_else(|| error(py, "StateError", "The workbook is closed"))?;
        py.detach(|| book.save_with(&path, &options))
            .map_err(|e| raise(py, e, Phase::Edit))
    }
    fn save_bytes<'py>(
        &self,
        py: Python<'py>,
        compression: Option<u8>,
        recalculate: bool,
    ) -> PyResult<Bound<'py, PyBytes>> {
        let mut options = SaveOptions::new().with_recalculate_on_open(recalculate);
        options.compression = compression;
        let mut guard = self.guard(py)?;
        let book = guard
            .as_mut()
            .ok_or_else(|| error(py, "StateError", "The workbook is closed"))?;
        let bytes = py
            .detach(|| book.write_to(Cursor::new(Vec::new()), &options))
            .map_err(|e| raise(py, e, Phase::Edit))?;
        Ok(PyBytes::new(py, bytes.get_ref()))
    }
    fn calculate(&self, py: Python<'_>) -> PyResult<()> {
        self.book(py, |book| book.calculate().map(|_| ()))
    }

    // ----- Sheets -----

    fn sheet_names(&self, py: Python<'_>) -> PyResult<Vec<String>> {
        self.book(py, |book| Ok(book.sheet_names()))
    }
    fn worksheet_names(&self, py: Python<'_>) -> PyResult<Vec<String>> {
        self.book(py, |book| Ok(book.worksheet_names()))
    }
    fn add_worksheet(&self, py: Python<'_>, name: &str, index: Option<usize>) -> PyResult<String> {
        self.book(py, |book| {
            let sheet = book.add_worksheet(name)?.name();
            if let Some(index) = index {
                book.move_sheet(&sheet, index)?;
            }
            Ok(sheet)
        })
    }
    fn copy_worksheet(&self, py: Python<'_>, source: &str, name: &str) -> PyResult<String> {
        self.book(py, |book| Ok(book.copy_worksheet(source, name)?.name()))
    }
    fn remove_sheet(&self, py: Python<'_>, name: &str) -> PyResult<()> {
        self.book(py, |book| book.remove_sheet(name))
    }
    fn move_sheet(&self, py: Python<'_>, name: &str, index: usize) -> PyResult<()> {
        self.book(py, |book| book.move_sheet(name, index))
    }
    fn rename_sheet(&self, py: Python<'_>, name: &str, new: &str) -> PyResult<()> {
        self.sheet(py, name, |sheet| sheet.rename(new))
    }
    fn active_sheet(&self, py: Python<'_>) -> PyResult<Option<String>> {
        self.book(py, |book| Ok(book.active_sheet()))
    }
    fn set_active_sheet(&self, py: Python<'_>, name: &str) -> PyResult<()> {
        self.book(py, |book| book.set_active_sheet(name))
    }
    fn visibility(&self, py: Python<'_>, name: &str) -> PyResult<&'static str> {
        self.book(py, |book| book.visibility(name).map(visibility_name))
    }
    fn set_visibility(&self, py: Python<'_>, name: &str, visibility: &str) -> PyResult<()> {
        let visibility = match visibility {
            "visible" => Visibility::Visible,
            "hidden" => Visibility::Hidden,
            "very_hidden" => Visibility::VeryHidden,
            other => {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "Unknown visibility {other:?}"
                )));
            }
        };
        self.book(py, |book| book.set_visibility(name, visibility))
    }

    // ----- Cells -----

    fn value(&self, py: Python<'_>, sheet: &str, cell: &str) -> PyResult<Py<PyAny>> {
        let value = self.sheet(py, sheet, |s| s.value(cell))?;
        to_python(py, &value, self.modes)
    }
    fn values<'py>(
        &self,
        py: Python<'py>,
        sheet: &str,
        range: &str,
    ) -> PyResult<Bound<'py, PyTuple>> {
        let grid = self.sheet(py, sheet, |s| s.values(range))?;
        let mut rows = Vec::with_capacity(grid.height());
        for row in grid.rows() {
            let cells = row
                .iter()
                .map(|value| to_python(py, value, self.modes))
                .collect::<PyResult<Vec<_>>>()?;
            rows.push(PyTuple::new(py, cells)?);
        }
        PyTuple::new(py, rows)
    }
    fn formula(&self, py: Python<'_>, sheet: &str, cell: &str) -> PyResult<Option<String>> {
        Ok(self
            .sheet(py, sheet, |s| s.formula(cell))?
            .map(|f| f.text().to_owned()))
    }
    fn set_value(
        &self,
        py: Python<'_>,
        sheet: &str,
        cell: &str,
        value: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let input = from_python(value)?;
        self.sheet(py, sheet, |s| s.set_value(cell, input))
    }
    fn fill(
        &self,
        py: Python<'_>,
        sheet: &str,
        range: &str,
        value: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let input = from_python(value)?;
        self.sheet(py, sheet, |s| {
            let range: crabxl::RangeRef = range.parse()?;
            for cell in range.cells() {
                s.set_value(cell, input.clone())?;
            }
            Ok(())
        })
    }
    fn set_values(
        &self,
        py: Python<'_>,
        sheet: &str,
        range: &str,
        rows: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let rows = rows
            .try_iter()?
            .map(|row| row_from_python(&row?))
            .collect::<PyResult<Vec<_>>>()?;
        self.sheet(py, sheet, |s| s.set_values(range, rows))
    }
    #[pyo3(signature = (sheet, rows, style=None))]
    fn append_rows(
        &self,
        py: Python<'_>,
        sheet: &str,
        rows: &Bound<'_, PyAny>,
        style: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        let style = style.map(style_from_python).transpose()?;
        let mut guard = self.guard(py)?;
        let book = guard
            .as_mut()
            .ok_or_else(|| error(py, "StateError", "The workbook is closed"))?;
        let mut handle = book
            .worksheet(sheet)
            .map_err(|e| raise(py, e, Phase::Edit))?;
        for row in rows.try_iter()? {
            let cells = row_from_python(&row?)?;
            let width = cells.len() as u32;
            let index = handle
                .append_row(cells)
                .map_err(|e| raise(py, e, Phase::Edit))?;
            if let Some(style) = &style
                && width > 0
            {
                let range = crabxl::RangeRef::new(
                    crabxl::CellRef::new(index, 0).map_err(|e| raise(py, e, Phase::Edit))?,
                    crabxl::CellRef::new(index, width - 1)
                        .map_err(|e| raise(py, e, Phase::Edit))?,
                )
                .map_err(|e| raise(py, e, Phase::Edit))?;
                handle
                    .set_style(range, style)
                    .map_err(|e| raise(py, e, Phase::Edit))?;
            }
        }
        Ok(())
    }
    fn clear(&self, py: Python<'_>, sheet: &str, range: &str) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.clear(range))
    }
    fn used_range(&self, py: Python<'_>, sheet: &str) -> PyResult<Option<String>> {
        Ok(self
            .sheet(py, sheet, |s| s.used_range())?
            .map(|range| range.to_string()))
    }

    // ----- Styles -----

    fn style(&self, py: Python<'_>, sheet: &str, cell: &str) -> PyResult<Py<PyAny>> {
        let style = self.sheet(py, sheet, |s| s.style(cell))?;
        style_to_python(py, &style)
    }
    fn set_style(
        &self,
        py: Python<'_>,
        sheet: &str,
        range: &str,
        style: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let style = style_from_python(style)?;
        self.sheet(py, sheet, |s| s.set_style(range, &style))
    }

    // ----- Layout -----

    fn column_width(&self, py: Python<'_>, sheet: &str, column: &str) -> PyResult<Option<f64>> {
        self.sheet(py, sheet, |s| s.column_width(column))
    }
    fn set_column_width(
        &self,
        py: Python<'_>,
        sheet: &str,
        columns: &str,
        width: f64,
    ) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.set_column_width(columns, width))
    }
    fn set_columns_hidden(
        &self,
        py: Python<'_>,
        sheet: &str,
        columns: &str,
        hidden: bool,
    ) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.set_columns_hidden(columns, hidden))
    }
    fn row_height(&self, py: Python<'_>, sheet: &str, row: &str) -> PyResult<Option<f64>> {
        self.sheet(py, sheet, |s| s.row_height(row))
    }
    fn set_row_height(&self, py: Python<'_>, sheet: &str, rows: &str, height: f64) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.set_row_height(rows, height))
    }
    fn set_rows_hidden(
        &self,
        py: Python<'_>,
        sheet: &str,
        rows: &str,
        hidden: bool,
    ) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.set_rows_hidden(rows, hidden))
    }
    fn frozen_panes(&self, py: Python<'_>, sheet: &str) -> PyResult<Option<String>> {
        Ok(self
            .sheet(py, sheet, |s| s.frozen_panes())?
            .map(|cell| cell.to_string()))
    }
    fn freeze_panes(&self, py: Python<'_>, sheet: &str, cell: Option<&str>) -> PyResult<()> {
        self.sheet(py, sheet, |s| match cell {
            Some(cell) => s.freeze_panes(cell),
            None => s.unfreeze_panes(),
        })
    }
    fn insert_rows(&self, py: Python<'_>, sheet: &str, rows: &str) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.insert_rows(rows))
    }
    fn delete_rows(&self, py: Python<'_>, sheet: &str, rows: &str) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.delete_rows(rows))
    }
    fn insert_columns(&self, py: Python<'_>, sheet: &str, columns: &str) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.insert_columns(columns))
    }
    fn delete_columns(&self, py: Python<'_>, sheet: &str, columns: &str) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.delete_columns(columns))
    }

    // ----- Merges -----

    fn merge(&self, py: Python<'_>, sheet: &str, range: &str) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.merge(range))
    }
    fn unmerge(&self, py: Python<'_>, sheet: &str, range: &str) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.unmerge(range))
    }
    fn merged_ranges(&self, py: Python<'_>, sheet: &str) -> PyResult<Vec<String>> {
        Ok(self
            .sheet(py, sheet, |s| s.merged_ranges())?
            .into_iter()
            .map(|range| range.to_string())
            .collect())
    }

    // ----- Objects -----

    fn tables<'py>(&self, py: Python<'py>, sheet: &str) -> PyResult<Bound<'py, PyList>> {
        let tables = self.sheet(py, sheet, |s| s.tables())?;
        let list = PyList::empty(py);
        for table in tables {
            list.append((
                table.name().to_owned(),
                table.range().to_string(),
                table.style().map(str::to_owned),
                table.banded_rows(),
                table.has_totals_row(),
            ))?;
        }
        Ok(list)
    }
    #[allow(clippy::too_many_arguments)]
    fn add_table(
        &self,
        py: Python<'_>,
        sheet: &str,
        name: &str,
        range: &str,
        style: Option<&str>,
        banded_rows: bool,
        totals_row: bool,
    ) -> PyResult<()> {
        self.sheet(py, sheet, |s| {
            let table = Table::new(name, range)?
                .with_style(style)
                .with_banded_rows(banded_rows)
                .with_totals_row(totals_row);
            s.add_table(table)
        })
    }
    fn remove_table(&self, py: Python<'_>, sheet: &str, name: &str) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.remove_table(name))
    }
    fn validations<'py>(&self, py: Python<'py>, sheet: &str) -> PyResult<Bound<'py, PyList>> {
        let rules = self.sheet(py, sheet, |s| s.data_validations())?;
        let list = PyList::empty(py);
        for rule in rules {
            let ranges: Vec<String> = rule.ranges().iter().map(ToString::to_string).collect();
            let kind = match rule.kind() {
                ValidationKind::WholeNumber => "whole",
                ValidationKind::Decimal => "decimal",
                ValidationKind::List => "list",
                ValidationKind::Date => "date",
                ValidationKind::Time => "time",
                ValidationKind::TextLength => "text_length",
                ValidationKind::Custom => "custom",
                _ => "any",
            };
            list.append((
                kind,
                ranges,
                rule.formula1().map(str::to_owned),
                rule.formula2().map(str::to_owned),
                rule.comparison().map(comparison_name),
                rule.allows_blank(),
                rule.prompt().map(|(t, m)| (t.to_owned(), m.to_owned())),
                rule.error().map(|(t, m)| (t.to_owned(), m.to_owned())),
            ))?;
        }
        Ok(list)
    }
    #[pyo3(signature = (sheet, kind, ranges, first, second=None, comparison=None, allow_blank=true, prompt=None, error_message=None))]
    #[allow(clippy::too_many_arguments)]
    fn add_validation(
        &self,
        py: Python<'_>,
        sheet: &str,
        kind: &str,
        ranges: Vec<String>,
        first: &Bound<'_, PyAny>,
        second: Option<&Bound<'_, PyAny>>,
        comparison: Option<&str>,
        allow_blank: bool,
        prompt: Option<(String, String)>,
        error_message: Option<(String, String)>,
    ) -> PyResult<()> {
        let comparison = comparison.map(self::comparison).transpose()?;
        let build = || -> PyResult<crabxl::Result<DataValidation>> {
            let need = |c: Option<Comparison>| {
                c.ok_or_else(|| {
                    pyo3::exceptions::PyValueError::new_err("This rule needs a comparison")
                })
            };
            Ok(match kind {
                "list" => DataValidation::list(first.extract::<Vec<String>>()?),
                "list_from" => Ok(DataValidation::list_from(&first.extract::<String>()?)),
                "custom" => Ok(DataValidation::custom(&first.extract::<String>()?)),
                "whole" => DataValidation::whole_number(
                    need(comparison)?,
                    first.extract()?,
                    second.map(|v| v.extract()).transpose()?,
                ),
                "decimal" => DataValidation::decimal(
                    need(comparison)?,
                    first.extract()?,
                    second.map(|v| v.extract()).transpose()?,
                ),
                "text_length" => DataValidation::text_length(
                    need(comparison)?,
                    first.extract()?,
                    second.map(|v| v.extract()).transpose()?,
                ),
                "date" => {
                    let date = |value: &Bound<'_, PyAny>| -> PyResult<crabxl::Result<Temporal>> {
                        let (year, month, day): (i32, u32, u32) = value.extract()?;
                        Ok(Temporal::date(year, month, day))
                    };
                    match (date(first)?, second.map(date).transpose()?.transpose()) {
                        (Ok(first), Ok(second)) => {
                            DataValidation::date(need(comparison)?, first, second)
                        }
                        (Err(e), _) | (_, Err(e)) => Err(e),
                    }
                }
                "time" => {
                    let time = |value: &Bound<'_, PyAny>| -> PyResult<crabxl::Result<Temporal>> {
                        let (hour, minute, second): (u32, u32, u32) = value.extract()?;
                        Ok(Temporal::time(hour, minute, second, 0))
                    };
                    match (time(first)?, second.map(time).transpose()?.transpose()) {
                        (Ok(first), Ok(second)) => {
                            DataValidation::time(need(comparison)?, first, second)
                        }
                        (Err(e), _) | (_, Err(e)) => Err(e),
                    }
                }
                other => {
                    return Err(pyo3::exceptions::PyValueError::new_err(format!(
                        "Unknown validation kind {other:?}"
                    )));
                }
            })
        };
        let rule = build()?;
        self.sheet(py, sheet, move |s| {
            let mut rule = rule?.with_allow_blank(allow_blank);
            if let Some((title, message)) = &prompt {
                rule = rule.with_prompt(title, message);
            }
            if let Some((title, message)) = &error_message {
                rule = rule.with_error(title, message);
            }
            for range in &ranges {
                rule = rule.with_range(range.as_str())?;
            }
            s.add_data_validation(rule)
        })
    }
    fn remove_validations(&self, py: Python<'_>, sheet: &str, range: &str) -> PyResult<usize> {
        self.sheet(py, sheet, |s| s.remove_data_validations(range))
    }
    fn conditional_formats<'py>(
        &self,
        py: Python<'py>,
        sheet: &str,
    ) -> PyResult<Bound<'py, PyList>> {
        let formats = self.sheet(py, sheet, |s| s.conditional_formats())?;
        let list = PyList::empty(py);
        for format in formats {
            let ranges: Vec<String> = format.ranges().iter().map(ToString::to_string).collect();
            let formulas: Vec<String> = format.formulas().map(str::to_owned).collect();
            let kind = match format.kind() {
                ConditionalKind::CellValue => "cell",
                ConditionalKind::Formula => "formula",
                _ => "other",
            };
            let style = match format.style() {
                Some(style) => partial_style_to_python(py, style)?,
                None => py.None(),
            };
            list.append((
                ranges,
                kind,
                formulas,
                format.comparison().map(comparison_name),
                style,
                format.stops_if_true(),
            ))?;
        }
        Ok(list)
    }
    #[pyo3(signature = (sheet, ranges, kind, style, formula, second=None, comparison=None, stop_if_true=false))]
    #[allow(clippy::too_many_arguments)]
    fn add_conditional_format(
        &self,
        py: Python<'_>,
        sheet: &str,
        ranges: Vec<String>,
        kind: &str,
        style: &Bound<'_, PyAny>,
        formula: String,
        second: Option<String>,
        comparison: Option<&str>,
        stop_if_true: bool,
    ) -> PyResult<()> {
        let style = partial_style_from_python(style)?;
        let comparison = comparison.map(self::comparison).transpose()?;
        let (first, rest) = ranges.split_first().ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err("A conditional format needs a range")
        })?;
        self.sheet(py, sheet, |s| {
            let mut format = match (kind, comparison) {
                ("cell", Some(comparison)) => ConditionalFormat::cell(
                    first.as_str(),
                    comparison,
                    formula,
                    second.as_deref(),
                    style,
                )?,
                ("formula", _) => ConditionalFormat::formula(first.as_str(), &formula, style)?,
                _ => {
                    return Err(crabxl::Error::new(
                        crabxl::ErrorKind::InvalidData,
                        format!("A {kind:?} conditional format cannot be added"),
                    ));
                }
            };
            for range in rest {
                format = format.with_range(range.as_str())?;
            }
            s.add_conditional_format(format.with_stop_if_true(stop_if_true))
        })
    }
    fn note(&self, py: Python<'_>, sheet: &str, cell: &str) -> PyResult<Option<(String, String)>> {
        Ok(self
            .sheet(py, sheet, |s| s.note(cell))?
            .map(|note| (note.text().to_owned(), note.author().to_owned())))
    }
    fn set_note(
        &self,
        py: Python<'_>,
        sheet: &str,
        cell: &str,
        text: &str,
        author: &str,
    ) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.set_note(cell, Note::new(text, author)))
    }
    fn remove_note(&self, py: Python<'_>, sheet: &str, cell: &str) -> PyResult<bool> {
        self.sheet(py, sheet, |s| s.remove_note(cell))
    }
    fn hyperlink(
        &self,
        py: Python<'_>,
        sheet: &str,
        cell: &str,
    ) -> PyResult<Option<(String, String, Option<String>)>> {
        Ok(self
            .sheet(py, sheet, |s| s.hyperlink(cell))?
            .map(|link| match link {
                Hyperlink::Url { target, tooltip } => ("url".to_owned(), target, tooltip),
                Hyperlink::Location { location, tooltip } => {
                    ("location".to_owned(), location, tooltip)
                }
            }))
    }
    fn set_hyperlink(
        &self,
        py: Python<'_>,
        sheet: &str,
        cell: &str,
        kind: &str,
        target: &str,
        tooltip: Option<&str>,
    ) -> PyResult<()> {
        self.sheet(py, sheet, |s| {
            let mut link = if kind == "url" {
                Hyperlink::url(target)?
            } else {
                Hyperlink::location(target)?
            };
            if let Some(tooltip) = tooltip {
                link = link.with_tooltip(tooltip);
            }
            s.set_hyperlink(cell, link)
        })
    }
    fn remove_hyperlink(&self, py: Python<'_>, sheet: &str, cell: &str) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.remove_hyperlink(cell))
    }
    fn add_image(&self, py: Python<'_>, sheet: &str, data: Vec<u8>, cell: &str) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.add_image(&Image::from_bytes(data)?, cell))
    }
    fn image_count(&self, py: Python<'_>, sheet: &str) -> PyResult<usize> {
        self.sheet(py, sheet, |s| s.image_count())
    }
    // ----- Charts, pictures, filters, outline and printing -----

    fn images<'py>(&self, py: Python<'py>, sheet: &str) -> PyResult<Bound<'py, PyList>> {
        let images = self.sheet(py, sheet, |s| s.images())?;
        let list = PyList::empty(py);
        for placed in images {
            list.append((
                PyBytes::new(py, placed.image.data()),
                placed.at.map(|at| at.to_string()),
            ))?;
        }
        Ok(list)
    }
    fn remove_images(&self, py: Python<'_>, sheet: &str, range: &str) -> PyResult<usize> {
        self.sheet(py, sheet, |s| s.remove_images(range))
    }
    fn charts<'py>(&self, py: Python<'py>, sheet: &str) -> PyResult<Bound<'py, PyList>> {
        let charts = self.sheet(py, sheet, |s| s.charts())?;
        let list = PyList::empty(py);
        for chart in charts {
            let kind = match chart.kind() {
                ChartKind::Column => "column",
                ChartKind::Bar => "bar",
                ChartKind::Line => "line",
                ChartKind::Area => "area",
                ChartKind::Pie => "pie",
                ChartKind::Doughnut => "doughnut",
                ChartKind::Scatter => "scatter",
                _ => "other",
            };
            let series: Vec<(String, Option<String>, Option<String>)> = chart
                .series()
                .iter()
                .map(|s| {
                    (
                        s.values().to_owned(),
                        s.categories().map(str::to_owned),
                        s.title().map(str::to_owned),
                    )
                })
                .collect();
            list.append((
                kind,
                chart.range().map(|range| range.to_string()),
                series,
                chart.title().map(str::to_owned),
                chart.has_legend(),
            ))?;
        }
        Ok(list)
    }
    #[allow(clippy::too_many_arguments)]
    fn add_chart(
        &self,
        py: Python<'_>,
        sheet: &str,
        kind: &str,
        range: &str,
        series: Vec<(String, Option<String>, Option<String>)>,
        title: Option<String>,
        legend: bool,
    ) -> PyResult<()> {
        let kind = match kind {
            "column" => ChartKind::Column,
            "bar" => ChartKind::Bar,
            "line" => ChartKind::Line,
            "area" => ChartKind::Area,
            "pie" => ChartKind::Pie,
            "doughnut" => ChartKind::Doughnut,
            "scatter" => ChartKind::Scatter,
            _ => ChartKind::Other,
        };
        self.sheet(py, sheet, |s| {
            let mut chart = Chart::new(kind, range)?.with_legend(legend);
            if let Some(title) = &title {
                chart = chart.with_title(title);
            }
            for (values, categories, name) in &series {
                let mut one = Series::new(values)?;
                if let Some(categories) = categories {
                    one = one.with_categories(categories);
                }
                if let Some(name) = name {
                    one = one.with_title(name);
                }
                chart = chart.with_series(one);
            }
            s.add_chart(&chart)
        })
    }
    fn remove_charts(&self, py: Python<'_>, sheet: &str, range: &str) -> PyResult<usize> {
        self.sheet(py, sheet, |s| s.remove_charts(range))
    }
    fn remove_conditional_formats(
        &self,
        py: Python<'_>,
        sheet: &str,
        range: &str,
    ) -> PyResult<usize> {
        self.sheet(py, sheet, |s| s.remove_conditional_formats(range))
    }
    fn auto_filter(&self, py: Python<'_>, sheet: &str) -> PyResult<Option<String>> {
        Ok(self
            .sheet(py, sheet, |s| s.auto_filter())?
            .map(|range| range.to_string()))
    }
    #[pyo3(signature = (sheet, range))]
    fn set_auto_filter(&self, py: Python<'_>, sheet: &str, range: Option<&str>) -> PyResult<()> {
        self.sheet(py, sheet, |s| match range {
            Some(range) => s.set_auto_filter(range),
            None => s.remove_auto_filter(),
        })
    }
    fn outline_level(&self, py: Python<'_>, sheet: &str, span: &str, rows: bool) -> PyResult<u8> {
        self.sheet(py, sheet, |s| {
            if rows {
                s.row_outline_level(span)
            } else {
                s.column_outline_level(span)
            }
        })
    }
    fn set_outline_level(
        &self,
        py: Python<'_>,
        sheet: &str,
        span: &str,
        rows: bool,
        level: u8,
    ) -> PyResult<()> {
        self.sheet(py, sheet, |s| {
            if rows {
                s.set_rows_outline_level(span, level)
            } else {
                s.set_columns_outline_level(span, level)
            }
        })
    }
    fn tab_color(&self, py: Python<'_>, sheet: &str) -> PyResult<Py<PyAny>> {
        match self.sheet(py, sheet, |s| s.tab_color())? {
            Some(color) => color_to_python(py, &color),
            None => Ok(py.None()),
        }
    }
    fn set_tab_color(&self, py: Python<'_>, sheet: &str, color: &Bound<'_, PyAny>) -> PyResult<()> {
        let color = color_from_python(color)?;
        self.sheet(py, sheet, |s| s.set_tab_color(color.as_ref()))
    }
    fn page_setup<'py>(&self, py: Python<'py>, sheet: &str) -> PyResult<Bound<'py, PyDict>> {
        let page = self.sheet(py, sheet, |s| s.page_setup())?;
        let span = |span: Span, rows: bool| -> PyResult<String> {
            let name = |index: u32| -> PyResult<String> {
                Ok(if rows {
                    (index + 1).to_string()
                } else {
                    CellRef::new(0, index)
                        .map_err(|e| raise(py, e, Phase::Edit))?
                        .column_name()
                })
            };
            let first = name(span.start)?;
            Ok(if span.count == 1 {
                first
            } else {
                format!("{first}:{}", name(span.start + span.count - 1)?)
            })
        };
        let dict = PyDict::new(py);
        dict.set_item(
            "orientation",
            page.orientation.map(|o| match o {
                Orientation::Portrait => "portrait",
                Orientation::Landscape => "landscape",
            }),
        )?;
        dict.set_item("paper_size", page.paper_size)?;
        dict.set_item("scale", page.scale)?;
        dict.set_item("fit_to", page.fit_to)?;
        let m = page.margins;
        dict.set_item(
            "margins",
            (m.left, m.right, m.top, m.bottom, m.header, m.footer),
        )?;
        dict.set_item("center_horizontally", page.center_horizontally)?;
        dict.set_item("center_vertically", page.center_vertically)?;
        dict.set_item("grid_lines", page.grid_lines)?;
        dict.set_item("print_area", page.print_area.map(|r| r.to_string()))?;
        dict.set_item(
            "title_rows",
            page.title_rows.map(|s| span(s, true)).transpose()?,
        )?;
        dict.set_item(
            "title_columns",
            page.title_columns.map(|s| span(s, false)).transpose()?,
        )?;
        Ok(dict)
    }
    #[allow(clippy::too_many_arguments)]
    #[pyo3(signature = (sheet, orientation, paper_size, scale, fit_to, margins, center_horizontally, center_vertically, grid_lines, print_area, title_rows, title_columns))]
    fn set_page_setup(
        &self,
        py: Python<'_>,
        sheet: &str,
        orientation: Option<&str>,
        paper_size: Option<u32>,
        scale: Option<u32>,
        fit_to: Option<(u32, u32)>,
        margins: (f64, f64, f64, f64, f64, f64),
        center_horizontally: bool,
        center_vertically: bool,
        grid_lines: bool,
        print_area: Option<&str>,
        title_rows: Option<&str>,
        title_columns: Option<&str>,
    ) -> PyResult<()> {
        let orientation = match orientation {
            None => None,
            Some("portrait") => Some(Orientation::Portrait),
            Some("landscape") => Some(Orientation::Landscape),
            Some(other) => {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "orientation must be 'portrait' or 'landscape', not {other:?}"
                )));
            }
        };
        self.sheet(py, sheet, |s| {
            let (left, right, top, bottom, header, footer) = margins;
            let page = PageSetup {
                orientation,
                paper_size,
                scale,
                fit_to,
                margins: Margins {
                    left,
                    right,
                    top,
                    bottom,
                    header,
                    footer,
                },
                center_horizontally,
                center_vertically,
                grid_lines,
                print_area: print_area.map(str::parse).transpose()?,
                title_rows: title_rows.map(Span::rows).transpose()?,
                title_columns: title_columns.map(Span::columns).transpose()?,
            };
            s.set_page_setup(&page)
        })
    }
    fn protect(&self, py: Python<'_>, sheet: &str, password: Option<&str>) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.protect(password))
    }
    fn unprotect(&self, py: Python<'_>, sheet: &str) -> PyResult<()> {
        self.sheet(py, sheet, |s| s.unprotect())
    }
    fn is_protected(&self, py: Python<'_>, sheet: &str) -> PyResult<bool> {
        self.sheet(py, sheet, |s| s.is_protected())
    }

    // ----- Workbook-level -----

    fn defined_names(&self, py: Python<'_>) -> PyResult<Vec<(String, String, Option<String>)>> {
        Ok(self
            .book(py, |book| book.defined_names())?
            .into_iter()
            .map(|name| {
                (
                    name.name().to_owned(),
                    name.formula().to_owned(),
                    name.sheet().map(str::to_owned),
                )
            })
            .collect())
    }
    fn add_defined_name(
        &self,
        py: Python<'_>,
        name: &str,
        formula: &str,
        sheet: Option<&str>,
    ) -> PyResult<()> {
        self.book(py, |book| {
            let mut defined = DefinedName::new(name, formula)?;
            if let Some(sheet) = sheet {
                defined = defined.with_sheet_scope(sheet);
            }
            book.add_defined_name(defined)
        })
    }
    fn remove_defined_name(&self, py: Python<'_>, name: &str) -> PyResult<()> {
        self.book(py, |book| book.remove_defined_name(name))
    }
    fn properties<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let properties = self.book(py, |book| book.properties())?;
        let dict = PyDict::new(py);
        dict.set_item("title", properties.title.as_deref())?;
        dict.set_item("subject", properties.subject.as_deref())?;
        dict.set_item("creator", properties.creator.as_deref())?;
        dict.set_item("description", properties.description.as_deref())?;
        dict.set_item("keywords", properties.keywords.as_deref())?;
        dict.set_item("category", properties.category.as_deref())?;
        dict.set_item("last_modified_by", properties.last_modified_by.as_deref())?;
        dict.set_item("created", properties.created.as_deref())?;
        dict.set_item("modified", properties.modified.as_deref())?;
        Ok(dict)
    }
    fn set_properties(&self, py: Python<'_>, values: &Bound<'_, PyDict>) -> PyResult<()> {
        let text = |name: &str| -> PyResult<Option<Box<str>>> {
            Ok(values
                .get_item(name)?
                .map(|value| value.extract::<Option<String>>())
                .transpose()?
                .flatten()
                .map(Into::into))
        };
        let title = text("title")?;
        let subject = text("subject")?;
        let creator = text("creator")?;
        let description = text("description")?;
        let keywords = text("keywords")?;
        let category = text("category")?;
        let last_modified_by = text("last_modified_by")?;
        let created = text("created")?;
        let modified = text("modified")?;
        self.book(py, |book| {
            let mut properties = book.properties()?;
            properties.title = title;
            properties.subject = subject;
            properties.creator = creator;
            properties.description = description;
            properties.keywords = keywords;
            properties.category = category;
            properties.last_modified_by = last_modified_by;
            properties.created = created;
            properties.modified = modified;
            book.set_properties(properties)
        })
    }
    fn modes(&self) -> (bool, bool) {
        (self.modes.exact_numbers, self.modes.serial_dates)
    }
}
