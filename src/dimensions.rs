//! Thin conversion of sparse canonical dimension records.
use crate::{failure, styles::field};
use crabxl::{ColumnDimension, ColumnIndex, RowDimension, RowIndex, StyleId};
use pyo3::{prelude::*, types::PyDict};

pub(crate) fn row(value: &Bound<'_, PyDict>, index: u32) -> PyResult<RowDimension> {
    let mut row = RowDimension::new(RowIndex::new(index).map_err(failure)?);
    row.height = field(value, "height")?;
    row.style = field::<u32>(value, "style_id")?.map(StyleId::new);
    row.hidden = field(value, "hidden")?;
    row.outline_level = field(value, "outlineLevel")?;
    row.collapsed = field(value, "collapsed")?;
    row.custom_height = field(value, "customHeight")?;
    row.custom_format = field(value, "customFormat")?;
    row.thick_top = field(value, "thickTop")?;
    row.thick_bottom = field(value, "thickBot")?;
    row.descent = field(value, "descent")?;
    row.validate().map_err(failure)?;
    Ok(row)
}
pub(crate) fn column(value: &Bound<'_, PyDict>, index: u32) -> PyResult<ColumnDimension> {
    let first = field::<u32>(value, "min")?
        .unwrap_or(index + 1)
        .checked_sub(1)
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("Invalid column minimum"))?;
    let last = field::<u32>(value, "max")?
        .unwrap_or(first + 1)
        .checked_sub(1)
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("Invalid column maximum"))?;
    let mut column = ColumnDimension::new(
        ColumnIndex::new(first).map_err(failure)?,
        ColumnIndex::new(last).map_err(failure)?,
    )
    .map_err(failure)?;
    if first != index {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "Column key differs from interval start",
        ));
    }
    column.width = field(value, "width")?;
    column.style = field::<u32>(value, "style_id")?.map(StyleId::new);
    column.hidden = field(value, "hidden")?;
    column.best_fit = field(value, "bestFit")?;
    column.outline_level = field(value, "outlineLevel")?;
    column.collapsed = field(value, "collapsed")?;
    column.custom_width = field(value, "customWidth")?;
    column.phonetic = field(value, "phonetic")?;
    column.validate().map_err(failure)?;
    Ok(column)
}
pub(crate) fn encode_row<'py>(py: Python<'py>, row: &RowDimension) -> PyResult<Bound<'py, PyDict>> {
    let value = PyDict::new(py);
    value.set_item("height", row.height)?;
    value.set_item("style_id", row.style.map(|id| id.get()))?;
    value.set_item("hidden", row.hidden)?;
    value.set_item("outlineLevel", row.outline_level)?;
    value.set_item("collapsed", row.collapsed)?;
    value.set_item("customHeight", row.custom_height)?;
    value.set_item("customFormat", row.custom_format)?;
    value.set_item("thickTop", row.thick_top)?;
    value.set_item("thickBot", row.thick_bottom)?;
    value.set_item("descent", row.descent)?;
    Ok(value)
}
pub(crate) fn encode_column<'py>(
    py: Python<'py>,
    column: &ColumnDimension,
) -> PyResult<Bound<'py, PyDict>> {
    let value = PyDict::new(py);
    value.set_item("min", column.start.get() + 1)?;
    value.set_item("max", column.end.get() + 1)?;
    value.set_item("width", column.width)?;
    value.set_item("style_id", column.style.map(|id| id.get()))?;
    value.set_item("hidden", column.hidden)?;
    value.set_item("bestFit", column.best_fit)?;
    value.set_item("outlineLevel", column.outline_level)?;
    value.set_item("collapsed", column.collapsed)?;
    value.set_item("customWidth", column.custom_width)?;
    value.set_item("phonetic", column.phonetic)?;
    Ok(value)
}
pub(crate) fn encode<'py>(
    py: Python<'py>,
    dimensions: &crabxl::SheetDimensions,
    rows: bool,
    index: u32,
) -> PyResult<Option<Bound<'py, PyDict>>> {
    if rows {
        dimensions
            .row(RowIndex::new(index).map_err(failure)?)
            .map(|row| encode_row(py, row))
            .transpose()
    } else {
        dimensions
            .column(ColumnIndex::new(index).map_err(failure)?)
            .map(|column| encode_column(py, column))
            .transpose()
    }
}
pub(crate) fn keys(dimensions: &crabxl::SheetDimensions, rows: bool) -> Vec<u32> {
    if rows {
        dimensions
            .rows()
            .iter()
            .map(|row| row.index.get())
            .collect()
    } else {
        dimensions
            .columns()
            .iter()
            .map(|column| column.start.get())
            .collect()
    }
}

pub(crate) enum Dimension {
    Row(RowDimension),
    Column(ColumnDimension),
}
impl Dimension {
    pub(crate) fn snapshot(
        dimensions: &crabxl::SheetDimensions,
        rows: bool,
        index: u32,
    ) -> PyResult<Self> {
        if rows {
            let index = RowIndex::new(index).map_err(failure)?;
            Ok(Self::Row(
                dimensions
                    .row(index)
                    .cloned()
                    .unwrap_or_else(|| RowDimension::new(index)),
            ))
        } else {
            let index = ColumnIndex::new(index).map_err(failure)?;
            Ok(Self::Column(dimensions.column(index).cloned().unwrap_or(
                ColumnDimension::new(index, index).map_err(failure)?,
            )))
        }
    }
    pub(crate) fn style(&self) -> StyleId {
        match self {
            Self::Row(row) => row.style,
            Self::Column(column) => column.style,
        }
        .unwrap_or(StyleId::new(0))
    }
    pub(crate) fn set_style(&mut self, style: StyleId) {
        match self {
            Self::Row(row) => {
                row.style = Some(style);
                row.custom_format = Some(style.get() != 0);
            }
            Self::Column(column) => column.style = Some(style),
        }
    }
    pub(crate) fn apply(self, sheet: &mut crabxl::WorksheetEditor<'_>) -> crabxl::Result<()> {
        match self {
            Self::Row(row) => sheet.set_row_dimension(row),
            Self::Column(column) => sheet.set_column_dimension(column),
        }
    }
    pub(crate) fn apply_loaded<R: std::io::Read + std::io::Seek>(
        self,
        book: &mut crabxl::LoadedWorkbook<R>,
        id: crabxl::SheetId,
    ) -> crabxl::Result<()> {
        match self {
            Self::Row(row) => book.set_row_dimension(id, row),
            Self::Column(column) => book.set_column_dimension(id, column),
        }
    }
    pub(crate) fn apply_writer(
        self,
        book: &mut crabxl::WorkbookWriter,
        id: usize,
    ) -> crabxl::Result<()> {
        match self {
            Self::Row(row) => book.set_interleaved_row_dimension(id, row),
            Self::Column(column) => book.set_interleaved_column_dimension(id, column),
        }
    }
}
