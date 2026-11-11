//! Owned worksheet handles and cell/model operations.
use crate::*;
pub(crate) mod hyperlinks;
mod rows;

// A handle owns either a detached worksheet or a stable identity in the shared
// core bank. No Python object or payload clone lives in the canonical model.
pub(crate) enum SheetStorage {
    Standalone(Box<Worksheet>),
    Bank {
        book: Arc<Mutex<Workbook>>,
        id: SheetId,
    },
    Loaded {
        book: SharedLoaded,
        id: SheetId,
    },
}
impl SheetStorage {
    /// Put a sheet in a workbook of its own. `source` holds the styles that its
    /// style IDs refer to; without it the sheet gets the default styles.
    pub(crate) fn adopt(sheet: Worksheet, source: Option<&Workbook>) -> PyResult<Self> {
        let mut book = Workbook::new(WorkbookLimits {
            max_bytes: usize::MAX,
            sheet: EditLimits {
                max_bytes: usize::MAX,
                ..EditLimits::default()
            },
            ..WorkbookLimits::default()
        })
        .map_err(failure)?;
        let limits = crabxl::StyleLimits::default();
        match source.and_then(Workbook::style_catalog) {
            Some(catalog) => book.import_style_catalog(catalog.clone(), limits),
            None => book.initialize_style_catalog(limits),
        }
        .map_err(failure)?;
        if let Some(source) = source {
            book.set_epoch(source.epoch());
        }
        let id = book.adopt_sheet(sheet).map_err(failure)?;
        Ok(Self::Bank {
            book: Arc::new(Mutex::new(book)),
            id,
        })
    }
}
fn unowned() -> PyErr {
    PyRuntimeError::new_err("Worksheet has no workbook")
}
#[pyclass]
pub(crate) struct NativeSheet {
    pub(crate) storage: Arc<Mutex<SheetStorage>>,
}
impl NativeSheet {
    /// Lock the storage. A sheet without a workbook first gets one, so that
    /// style changes work as in openpyxl.
    pub(crate) fn styled(&self) -> PyResult<MutexGuard<'_, SheetStorage>> {
        let mut storage = lock(&self.storage)?;
        if let SheetStorage::Standalone(sheet) = &mut *storage {
            let placeholder = Box::new(
                Worksheet::new(sheet.name().to_owned(), EditLimits::default()).map_err(failure)?,
            );
            let sheet = std::mem::replace(sheet, placeholder);
            *storage = SheetStorage::adopt(*sheet, None)?;
        }
        Ok(storage)
    }
    pub(crate) fn with<T>(&self, action: impl FnOnce(&Worksheet) -> PyResult<T>) -> PyResult<T> {
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
    pub(crate) fn with_style_catalog<T>(
        &self,
        action: impl FnOnce(&Worksheet, Option<&crabxl::StyleCatalog>) -> PyResult<T>,
    ) -> PyResult<T> {
        let storage = lock(&self.storage)?;
        match &*storage {
            SheetStorage::Standalone(sheet) => action(sheet, None),
            SheetStorage::Bank { book, id } => {
                let book = lock(book)?;
                action(book.sheet(*id).map_err(failure)?, book.style_catalog())
            }
            SheetStorage::Loaded { book, id } => {
                let book = lock(book)?;
                let book = book.as_ref().ok_or_else(closed)?.model();
                action(book.sheet(*id).map_err(failure)?, book.style_catalog())
            }
        }
    }
    pub(crate) fn edit_dimension_style(
        &self,
        rows: bool,
        index: u32,
        change: impl FnOnce(&mut dyn style_owners::StyleOwner, StyleId) -> crabxl::Result<StyleId>,
    ) -> PyResult<()> {
        let storage = self.styled()?;
        match &*storage {
            SheetStorage::Bank { book, id } => {
                let mut book = lock(book)?;
                let mut dimension = dimensions::Dimension::snapshot(
                    book.sheet(*id).map_err(failure)?.dimensions(),
                    rows,
                    index,
                )?;
                let style = change(&mut *book, dimension.style()).map_err(failure)?;
                dimension.set_style(style);
                dimension
                    .apply(&mut book.sheet_mut(*id).map_err(failure)?)
                    .map_err(failure)
            }
            SheetStorage::Loaded { book, id } => {
                let mut book = lock(book)?;
                let book = book.as_mut().ok_or_else(closed)?;
                let mut dimension = dimensions::Dimension::snapshot(
                    book.model().sheet(*id).map_err(failure)?.dimensions(),
                    rows,
                    index,
                )?;
                let style = change(book, dimension.style()).map_err(failure)?;
                dimension.set_style(style);
                dimension.apply_loaded(book, *id).map_err(failure)
            }
            SheetStorage::Standalone(_) => Err(unowned()),
        }
    }
    pub(crate) fn with_mut<T>(
        &self,
        action: impl FnOnce(&mut WorksheetEditor<'_>) -> PyResult<T>,
    ) -> PyResult<T> {
        let mut storage = lock(&self.storage)?;
        match &mut *storage {
            SheetStorage::Standalone(sheet) => action(&mut sheet.edit()),
            SheetStorage::Bank { book, id } => {
                action(&mut lock(book)?.sheet_mut(*id).map_err(failure)?)
            }
            SheetStorage::Loaded { .. } => Err(PyRuntimeError::new_err(
                "Loaded model mutation must use the preserving coordinator",
            )),
        }
    }
    pub(crate) fn in_loaded(book: SharedLoaded, id: SheetId) -> Self {
        Self {
            storage: Arc::new(Mutex::new(SheetStorage::Loaded { book, id })),
        }
    }
    pub(crate) fn in_bank(book: Arc<Mutex<Workbook>>, id: SheetId) -> Self {
        Self {
            storage: Arc::new(Mutex::new(SheetStorage::Bank { book, id })),
        }
    }
}
#[pymethods]
impl NativeSheet {
    pub(crate) fn hyperlink(
        &self,
        row: u32,
        column: u32,
    ) -> PyResult<Option<hyperlinks::LinkFields>> {
        self.hyperlink_fields(row, column)
    }

    pub(crate) fn set_hyperlink(
        &self,
        row: u32,
        column: u32,
        value: Option<hyperlinks::LinkFields>,
    ) -> PyResult<()> {
        self.replace_hyperlink(row, column, value, true)
    }

    pub(crate) fn update_hyperlink(
        &self,
        row: u32,
        column: u32,
        value: Option<hyperlinks::LinkFields>,
    ) -> PyResult<()> {
        self.replace_hyperlink(row, column, value, false)
    }

    #[new]
    pub(crate) fn new(name: String, max_bytes: usize) -> PyResult<Self> {
        Ok(Self {
            storage: Arc::new(Mutex::new(SheetStorage::Standalone(Box::new(
                Worksheet::new(
                    name,
                    EditLimits {
                        max_bytes,
                        ..EditLimits::default()
                    },
                )
                .map_err(failure)?,
            )))),
        })
    }
    pub(crate) fn remove_dimension(&self, rows: bool, index: u32) -> PyResult<bool> {
        let storage = lock(&self.storage)?;
        if let SheetStorage::Loaded { book, id } = &*storage {
            let mut book = lock(book)?;
            let book = book.as_mut().ok_or_else(closed)?;
            return if rows {
                book.remove_row_dimension(*id, RowIndex::new(index).map_err(failure)?)
                    .map_err(failure)
            } else {
                book.remove_column_dimension(*id, ColumnIndex::new(index).map_err(failure)?)
                    .map_err(failure)
            };
        }
        drop(storage);
        self.with_mut(|sheet| {
            if rows {
                Ok(sheet
                    .remove_row_dimension(RowIndex::new(index).map_err(failure)?)
                    .is_some())
            } else {
                Ok(sheet
                    .remove_column_dimension(ColumnIndex::new(index).map_err(failure)?)
                    .is_some())
            }
        })
    }
    pub(crate) fn group_dimensions(
        &self,
        rows: bool,
        start: u32,
        end: u32,
        level: u32,
        hidden: bool,
    ) -> PyResult<()> {
        let storage = lock(&self.storage)?;
        if let SheetStorage::Loaded { book, id } = &*storage {
            let mut book = lock(book)?;
            let book = book.as_mut().ok_or_else(closed)?;
            return if rows {
                book.group_rows(
                    *id,
                    RowIndex::new(start).map_err(failure)?,
                    RowIndex::new(end).map_err(failure)?,
                    level,
                    hidden,
                )
                .map_err(failure)
            } else {
                book.group_columns(
                    *id,
                    ColumnIndex::new(start).map_err(failure)?,
                    ColumnIndex::new(end).map_err(failure)?,
                    level,
                    hidden,
                )
                .map_err(failure)
            };
        }
        drop(storage);
        self.with_mut(|sheet| {
            if rows {
                sheet
                    .group_rows(
                        RowIndex::new(start).map_err(failure)?,
                        RowIndex::new(end).map_err(failure)?,
                        level,
                        hidden,
                    )
                    .map_err(failure)
            } else {
                sheet
                    .group_columns(
                        ColumnIndex::new(start).map_err(failure)?,
                        ColumnIndex::new(end).map_err(failure)?,
                        level,
                        hidden,
                    )
                    .map_err(failure)
            }
        })
    }
    pub(crate) fn dimension_component<'py>(
        &self,
        py: Python<'py>,
        rows: bool,
        index: u32,
        name: &str,
    ) -> PyResult<Bound<'py, PyDict>> {
        self.with_style_catalog(|sheet, catalog| {
            let dimension = dimensions::Dimension::snapshot(sheet.dimensions(), rows, index)?;
            if let Some(catalog) = catalog {
                styles::encode(
                    py,
                    name,
                    catalog.cell_style(dimension.style()).map_err(failure)?,
                )
            } else {
                styles::default_component(py, name)
            }
        })
    }
    pub(crate) fn dimension_number_format(&self, rows: bool, index: u32) -> PyResult<String> {
        self.with_style_catalog(|sheet, catalog| {
            let dimension = dimensions::Dimension::snapshot(sheet.dimensions(), rows, index)?;
            Ok(catalog
                .and_then(|catalog| {
                    catalog
                        .cell_format(dimension.style())
                        .and_then(|format| catalog.number_format(format.number_format_id))
                })
                .unwrap_or("General")
                .into())
        })
    }
    pub(crate) fn set_dimension_component(
        &self,
        rows: bool,
        index: u32,
        value: PyRef<'_, styles::NativeStyleComponent>,
    ) -> PyResult<()> {
        let component = value.component.clone();
        self.edit_dimension_style(rows, index, |book, style| book.component(style, component))
    }
    pub(crate) fn set_dimension_number_format(
        &self,
        rows: bool,
        index: u32,
        code: String,
    ) -> PyResult<()> {
        self.edit_dimension_style(rows, index, |book, style| book.number(style, code.into()))
    }
    pub(crate) fn dimension<'py>(
        &self,
        py: Python<'py>,
        rows: bool,
        index: u32,
    ) -> PyResult<Option<Bound<'py, PyDict>>> {
        self.with(|sheet| dimensions::encode(py, sheet.dimensions(), rows, index))
    }
    pub(crate) fn dimension_keys(&self, rows: bool) -> PyResult<Vec<u32>> {
        self.with(|sheet| Ok(dimensions::keys(sheet.dimensions(), rows)))
    }
    pub(crate) fn set_dimension(
        &self,
        rows: bool,
        index: u32,
        value: &Bound<'_, PyDict>,
    ) -> PyResult<()> {
        let storage = lock(&self.storage)?;
        if let SheetStorage::Loaded { book, id } = &*storage {
            let mut book = lock(book)?;
            let book = book.as_mut().ok_or_else(closed)?;
            return if rows {
                book.set_row_dimension(*id, dimensions::row(value, index)?)
                    .map_err(failure)
            } else {
                book.set_column_dimension(*id, dimensions::column(value, index)?)
                    .map_err(failure)
            };
        }
        drop(storage);
        self.with_mut(|sheet| {
            if rows {
                sheet
                    .set_row_dimension(dimensions::row(value, index)?)
                    .map_err(failure)
            } else {
                sheet
                    .set_column_dimension(dimensions::column(value, index)?)
                    .map_err(failure)
            }
        })
    }
    pub(crate) fn named_style(&self, row: u32, column: u32) -> PyResult<String> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        let storage = lock(&self.storage)?;
        let resolve = |book: &Workbook, id| {
            let style = book.sheet(id).map_err(failure)?.style_at(address);
            Ok(style_owners::style_name(book.style_catalog(), style))
        };
        match &*storage {
            SheetStorage::Bank { book, id } => resolve(&*lock(book)?, *id),
            SheetStorage::Loaded { book, id } => {
                resolve(lock(book)?.as_ref().ok_or_else(closed)?.model(), *id)
            }
            SheetStorage::Standalone(_) => Ok("Normal".into()),
        }
    }
    pub(crate) fn set_named_style(&self, row: u32, column: u32, name: &str) -> PyResult<()> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        let storage = self.styled()?;
        match &*storage {
            SheetStorage::Bank { book, id } => {
                let mut book = lock(book)?;
                let style = book.named_style_format(name).map_err(failure)?;
                book.sheet_mut(*id)
                    .map_err(failure)?
                    .set_style(address, style)
                    .map_err(failure)
            }
            SheetStorage::Loaded { book, id } => {
                let mut book = lock(book)?;
                let book = book.as_mut().ok_or_else(closed)?;
                let style = book.named_style_format(name).map_err(failure)?;
                book.set_style(*id, address, style).map_err(failure)
            }
            SheetStorage::Standalone(_) => Err(unowned()),
        }
    }
    pub(crate) fn get(&self, py: Python<'_>, row: u32, column: u32) -> PyResult<EncodedValue> {
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
    pub(crate) fn style_id(&self, row: u32, column: u32) -> PyResult<u32> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        self.with(|sheet| Ok(sheet.style_at(address).get()))
    }
    pub(crate) fn has_style(&self, row: u32, column: u32) -> PyResult<bool> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        let storage = lock(&self.storage)?;
        let resolve = |book: &Workbook, id| -> PyResult<bool> {
            let style = book.sheet(id).map_err(failure)?.style_at(address);
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
            SheetStorage::Standalone(sheet) => Ok(sheet.style_at(address).get() != 0),
            SheetStorage::Bank { book, id } => resolve(&*lock(book)?, *id),
            SheetStorage::Loaded { book, id } => {
                resolve(lock(book)?.as_ref().ok_or_else(closed)?.model(), *id)
            }
        }
    }
    pub(crate) fn is_date_format(&self, row: u32, column: u32) -> PyResult<bool> {
        Ok(crabxl::classify_number_format(&self.number_format(row, column)?).is_some())
    }
    pub(crate) fn number_format(&self, row: u32, column: u32) -> PyResult<String> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        let storage = lock(&self.storage)?;
        let resolve = |book: &Workbook, id| -> PyResult<String> {
            let style = book.sheet(id).map_err(failure)?.style_at(address);
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
    pub(crate) fn set_number_format(&self, row: u32, column: u32, code: String) -> PyResult<()> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        let storage = self.styled()?;
        match &*storage {
            SheetStorage::Standalone(_) => Err(unowned()),
            SheetStorage::Bank { book, id } => {
                let mut book = lock(book)?;
                let previous = book.sheet(*id).map_err(failure)?.style_at(address);
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
    pub(crate) fn style_component<'py>(
        &self,
        py: Python<'py>,
        row: u32,
        column: u32,
        name: &str,
    ) -> PyResult<Bound<'py, PyDict>> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        let storage = self.styled()?;
        let resolve = |book: &Workbook, id| {
            let style = book.sheet(id).map_err(failure)?.style_at(address);
            if let Some(catalog) = book.style_catalog() {
                styles::encode(py, name, catalog.cell_style(style).map_err(failure)?)
            } else {
                styles::default_component(py, name)
            }
        };
        match &*storage {
            SheetStorage::Bank { book, id } => resolve(&*lock(book)?, *id),
            SheetStorage::Loaded { book, id } => {
                resolve(lock(book)?.as_ref().ok_or_else(closed)?.model(), *id)
            }
            SheetStorage::Standalone(_) => Err(unowned()),
        }
    }
    pub(crate) fn set_style_component(
        &self,
        row: u32,
        column: u32,
        _name: &str,
        value: PyRef<'_, styles::NativeStyleComponent>,
    ) -> PyResult<()> {
        let component = value.component.clone();
        let address = CellAddress::new(row, column).map_err(failure)?;
        let storage = self.styled()?;
        match &*storage {
            SheetStorage::Standalone(_) => Err(unowned()),
            SheetStorage::Bank { book, id } => {
                let mut book = lock(book)?;
                let previous = book.sheet(*id).map_err(failure)?.style_at(address);
                let style = book
                    .derive_style_component(previous, component)
                    .map_err(failure)?;
                book.sheet_mut(*id)
                    .map_err(failure)?
                    .set_appearance_style(address, style)
                    .map_err(failure)
            }
            SheetStorage::Loaded { book, id } => lock(book)?
                .as_mut()
                .ok_or_else(closed)?
                .set_style_component(*id, address, component)
                .map_err(failure),
        }
    }
    pub(crate) fn cell_state(&self, row: u32, column: u32) -> PyResult<(bool, bool)> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        self.with(|sheet| {
            Ok((
                sheet.get(address).is_some(),
                sheet.get(address).is_none()
                    && sheet.merged_ranges().virtual_style(address).is_some(),
            ))
        })
    }
    pub(crate) fn merge_count(&self) -> PyResult<usize> {
        self.with(|sheet| Ok(sheet.merged_ranges().ranges().len()))
    }
    pub(crate) fn merge_identity(&self, index: usize) -> PyResult<Option<u64>> {
        self.with(|sheet| {
            Ok(sheet
                .merged_ranges()
                .ranges()
                .get(index)
                .map(|entry| entry.identity()))
        })
    }
    pub(crate) fn merge_declaration(
        &self,
        identity: u64,
    ) -> PyResult<Option<(u32, u32, u32, u32)>> {
        self.with(|sheet| {
            Ok(sheet.merged_ranges().declaration(identity).map(|entry| {
                let range = entry.range();
                (
                    range.start.row.get() + 1,
                    range.start.column.get() + 1,
                    range.end.row.get() + 1,
                    range.end.column.get() + 1,
                )
            }))
        })
    }
    #[pyo3(signature = (coordinate, remove=false, identity=None, exact=false))]
    pub(crate) fn edit_merge_declaration(
        &self,
        coordinate: &str,
        remove: bool,
        identity: Option<u64>,
        exact: bool,
    ) -> PyResult<bool> {
        let range: CellRange = coordinate.parse().map_err(failure)?;
        let mut storage = lock(&self.storage)?;
        match &mut *storage {
            SheetStorage::Loaded { book, id } => {
                let mut book = lock(book)?;
                let book = book.as_mut().ok_or_else(closed)?;
                if let Some(identity) = identity {
                    book.replace_merge_declaration(*id, identity, range)
                        .map_err(failure)?;
                    Ok(true)
                } else if remove {
                    book.remove_merge_declaration(*id, range).map_err(failure)
                } else if exact {
                    book.add_exact_merge_declaration(*id, range)
                        .map_err(failure)
                } else {
                    book.add_merge_declaration(*id, range).map_err(failure)
                }
            }
            SheetStorage::Bank { book, id } => {
                let mut book = lock(book)?;
                let mut sheet = book.sheet_mut(*id).map_err(failure)?;
                if let Some(identity) = identity {
                    sheet
                        .replace_merge_declaration(identity, range)
                        .map_err(failure)?;
                    Ok(true)
                } else if remove {
                    sheet.remove_merge_declaration(range).map_err(failure)
                } else if exact {
                    sheet.add_exact_merge_declaration(range).map_err(failure)
                } else {
                    sheet.add_merge_declaration(range).map_err(failure)
                }
            }
            SheetStorage::Standalone(sheet) => {
                if let Some(identity) = identity {
                    sheet
                        .replace_merge_declaration(identity, range)
                        .map_err(failure)?;
                    Ok(true)
                } else if remove {
                    sheet.remove_merge_declaration(range).map_err(failure)
                } else if exact {
                    sheet.add_exact_merge_declaration(range).map_err(failure)
                } else {
                    sheet.add_merge_declaration(range).map_err(failure)
                }
            }
        }
    }
    pub(crate) fn replace_merge_declarations(&self, coordinates: Vec<String>) -> PyResult<()> {
        let ranges: Vec<CellRange> = coordinates
            .iter()
            .map(|value| value.parse())
            .collect::<crabxl::Result<_>>()
            .map_err(failure)?;
        let mut storage = lock(&self.storage)?;
        match &mut *storage {
            SheetStorage::Loaded { book, id } => lock(book)?
                .as_mut()
                .ok_or_else(closed)?
                .replace_merge_declarations(*id, &ranges)
                .map_err(failure),
            SheetStorage::Bank { book, id } => lock(book)?
                .sheet_mut(*id)
                .map_err(failure)?
                .replace_merge_declarations(&ranges)
                .map_err(failure),
            SheetStorage::Standalone(sheet) => {
                sheet.replace_merge_declarations(&ranges).map_err(failure)
            }
        }
    }
    pub(crate) fn merged_range(&self, index: usize) -> PyResult<Option<(u32, u32, u32, u32)>> {
        self.with(|sheet| {
            Ok(sheet.merged_ranges().ranges().get(index).map(|merge| {
                let range = merge.range();
                (
                    range.start.row.get() + 1,
                    range.start.column.get() + 1,
                    range.end.row.get() + 1,
                    range.end.column.get() + 1,
                )
            }))
        })
    }
    pub(crate) fn contains_merge(
        &self,
        first_row: u32,
        first_column: u32,
        last_row: u32,
        last_column: u32,
        exact: bool,
    ) -> PyResult<bool> {
        let range = CellRange::new(
            CellAddress::new(first_row, first_column).map_err(failure)?,
            CellAddress::new(last_row, last_column).map_err(failure)?,
        )
        .map_err(failure)?;
        self.with(|sheet| {
            Ok(if exact {
                sheet
                    .merged_ranges()
                    .ranges()
                    .iter()
                    .any(|merge| merge.range() == range)
            } else {
                sheet.merged_ranges().contains(range)
            })
        })
    }
    pub(crate) fn prepare_merge_anchor(
        &self,
        first_row: u32,
        first_column: u32,
        last_row: u32,
        last_column: u32,
    ) -> PyResult<()> {
        let range = CellRange::new(
            CellAddress::new(first_row, first_column).map_err(failure)?,
            CellAddress::new(last_row, last_column).map_err(failure)?,
        )
        .map_err(failure)?;
        let mut storage = lock(&self.storage)?;
        match &mut *storage {
            SheetStorage::Bank { book, id } => {
                let mut book = lock(book)?;
                let sheet = book.sheet(*id).map_err(failure)?;
                let anchor = sheet.style_at(range.start);
                let corner = sheet
                    .get(range.end)
                    .is_some()
                    .then(|| sheet.style_at(range.end));
                let (_, anchor) = book.prepare_merge(range, anchor, corner).map_err(failure)?;
                book.sheet_mut(*id)
                    .map_err(failure)?
                    .set_style(range.start, anchor)
                    .map_err(failure)
            }
            SheetStorage::Loaded { book, id } => lock(book)?
                .as_mut()
                .ok_or_else(closed)?
                .prepare_merge_anchor(*id, range)
                .map_err(failure),
            SheetStorage::Standalone(sheet) => {
                if sheet.get(range.start).is_none() {
                    sheet
                        .set(crabxl::Cell {
                            address: range.start,
                            value: crabxl::CellValue::Empty,
                            style: crabxl::StyleId::new(0),
                        })
                        .map_err(failure)?;
                }
                Ok(())
            }
        }
    }

    #[pyo3(signature = (bounds, merge, declare=true))]
    pub(crate) fn merge_cells(
        &self,
        py: Python<'_>,
        bounds: (u32, u32, u32, u32),
        merge: bool,
        declare: bool,
    ) -> PyResult<()> {
        let (first_row, first_column, last_row, last_column) = bounds;
        let range = CellRange::new(
            CellAddress::new(first_row, first_column).map_err(failure)?,
            CellAddress::new(last_row, last_column).map_err(failure)?,
        )
        .map_err(failure)?;
        let storage = Arc::clone(&self.storage);
        py.detach(move || {
            let mut storage = lock(&storage)?;
            match &mut *storage {
                SheetStorage::Bank { book, id } => {
                    let mut book = lock(book)?;
                    if merge && !declare {
                        book.format_merged_cells(*id, range)
                    } else if merge {
                        book.merge_cells(*id, range)
                    } else {
                        book.sheet_mut(*id)
                            .and_then(|mut sheet| sheet.unmerge_cells(range))
                    }
                    .map_err(failure)
                }
                SheetStorage::Loaded { book, id } => {
                    let mut book = lock(book)?;
                    let book = book.as_mut().ok_or_else(closed)?;
                    if merge && !declare {
                        book.format_merged_cells(*id, range)
                    } else if merge {
                        book.merge_cells(*id, range)
                    } else {
                        book.unmerge_cells(*id, range)
                    }
                    .map_err(failure)
                }
                SheetStorage::Standalone(sheet) => if merge {
                    let style = crabxl::StyleId::new(0);
                    let prepared =
                        crabxl::MergedCellRange::new(range, [style; 16]).map_err(failure)?;
                    if declare {
                        sheet.edit().merge_prepared(prepared, style)
                    } else {
                        sheet.edit().format_prepared_merge(prepared, style)
                    }
                } else {
                    sheet.unmerge_cells(range)
                }
                .map_err(failure),
            }
        })
    }
    pub(crate) fn contains(&self, row: u32, column: u32) -> PyResult<bool> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        self.with(|sheet| Ok(sheet.get(address).is_some()))
    }
    pub(crate) fn views_xml(&self) -> PyResult<Vec<u8>> {
        let storage = lock(&self.storage)?;
        let views = match &*storage {
            SheetStorage::Standalone(sheet) => sheet.sheet_views().cloned().unwrap_or_default(),
            SheetStorage::Bank { book, id } => lock(book)?
                .sheet(*id)
                .map_err(failure)?
                .sheet_views()
                .cloned()
                .unwrap_or_default(),
            SheetStorage::Loaded { book, id } => lock(book)?
                .as_mut()
                .ok_or_else(closed)?
                .sheet_views(*id)
                .map_err(failure)?,
        };
        crabxl::feature_xml::sheet_views_to_xml(&views).map_err(failure)
    }
    pub(crate) fn set_views_xml(&self, xml: &[u8]) -> PyResult<()> {
        let views = crabxl::feature_xml::sheet_views_from_xml(xml).map_err(failure)?;
        let mut storage = lock(&self.storage)?;
        match &mut *storage {
            SheetStorage::Standalone(sheet) => sheet.set_sheet_views(Some(views)),
            SheetStorage::Bank { book, id } => lock(book)?
                .sheet_mut(*id)
                .map_err(failure)?
                .set_sheet_views(Some(views)),
            SheetStorage::Loaded { book, id } => lock(book)?
                .as_mut()
                .ok_or_else(closed)?
                .set_sheet_views(*id, views),
        }
        .map_err(failure)
    }
    pub(crate) fn printing_xml(&self) -> PyResult<Vec<u8>> {
        let storage = lock(&self.storage)?;
        let views = match &*storage {
            SheetStorage::Standalone(sheet) => sheet.print_settings().cloned().unwrap_or_default(),
            SheetStorage::Bank { book, id } => lock(book)?
                .sheet(*id)
                .map_err(failure)?
                .print_settings()
                .cloned()
                .unwrap_or_default(),
            SheetStorage::Loaded { book, id } => lock(book)?
                .as_mut()
                .ok_or_else(closed)?
                .print_settings(*id)
                .map_err(failure)?,
        };
        crabxl::feature_xml::print_settings_to_xml(&views).map_err(failure)
    }
    pub(crate) fn set_printing_xml(&self, xml: &[u8]) -> PyResult<()> {
        let views = crabxl::feature_xml::print_settings_from_xml(xml).map_err(failure)?;
        let mut storage = lock(&self.storage)?;
        match &mut *storage {
            SheetStorage::Standalone(sheet) => sheet.set_print_settings(Some(views)),
            SheetStorage::Bank { book, id } => lock(book)?
                .sheet_mut(*id)
                .map_err(failure)?
                .set_print_settings(Some(views)),
            SheetStorage::Loaded { book, id } => lock(book)?
                .as_mut()
                .ok_or_else(closed)?
                .set_print_settings(*id, views),
        }
        .map_err(failure)
    }
    pub(crate) fn row_values(
        &self,
        py: Python<'_>,
        row: u32,
        first: u32,
        last: u32,
        create_missing: bool,
    ) -> PyResult<Vec<EncodedValue>> {
        rows::map(self, row, first, last, create_missing, |value| {
            encode(py, value)
        })
    }
    pub(crate) fn row_values_only(
        &self,
        py: Python<'_>,
        row: u32,
        first: u32,
        last: u32,
        create_missing: bool,
    ) -> PyResult<DecodedValues> {
        rows::values(self, py, row, first, last, create_missing)
    }
    pub(crate) fn set(
        &self,
        py: Python<'_>,
        row: u32,
        column: u32,
        value: TaggedValue,
    ) -> PyResult<()> {
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
    pub(crate) fn set_data_type(
        &self,
        py: Python<'_>,
        row: u32,
        column: u32,
        kind: &str,
    ) -> PyResult<()> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        let kind = crabxl::CellStorageType::parse(kind).map_err(failure)?;
        let storage = Arc::clone(&self.storage);
        py.detach(move || {
            let retype = |sheet: &Worksheet| {
                sheet
                    .get(address)
                    .map_or(CellValue::Empty, |cell| cell.value.clone())
                    .with_storage_type(kind)
                    .map_err(failure)
            };
            let mut storage = lock(&storage)?;
            match &mut *storage {
                SheetStorage::Standalone(sheet) => {
                    let value = retype(sheet)?;
                    let style = sheet
                        .get(address)
                        .map_or(StyleId::new(0), |cell| cell.style);
                    sheet
                        .edit()
                        .set(Cell {
                            address,
                            value,
                            style,
                        })
                        .map_err(failure)
                }
                SheetStorage::Bank { book, id } => {
                    let mut book = lock(book)?;
                    let sheet = book.sheet(*id).map_err(failure)?;
                    let value = retype(sheet)?;
                    let style = sheet
                        .get(address)
                        .map_or(StyleId::new(0), |cell| cell.style);
                    book.sheet_mut(*id)
                        .map_err(failure)?
                        .set(Cell {
                            address,
                            value,
                            style,
                        })
                        .map_err(failure)
                }
                SheetStorage::Loaded { book, id } => {
                    let mut handle = lock(book)?;
                    let book = handle.as_mut().ok_or_else(closed)?;
                    let value = retype(book.sheet(*id).map_err(failure)?)?;
                    book.upsert_value(*id, address, value).map_err(failure)
                }
            }
        })
    }
    #[pyo3(signature = (row, column, retain=false))]
    pub(crate) fn remove(
        &self,
        py: Python<'_>,
        row: u32,
        column: u32,
        retain: bool,
    ) -> PyResult<(Option<EncodedValue>, Option<hyperlinks::LinkFields>)> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        let storage = Arc::clone(&self.storage);
        let removed = py.detach(move || {
            let mut storage = lock(&storage)?;
            let removed = match &mut *storage {
                SheetStorage::Standalone(sheet) => sheet
                    .edit()
                    .remove_with_hyperlink(address)
                    .map_err(failure)?,
                SheetStorage::Bank { book, id } => lock(book)?
                    .sheet_mut(*id)
                    .map_err(failure)?
                    .remove_with_hyperlink(address)
                    .map_err(failure)?,
                SheetStorage::Loaded { book, id } => lock(book)?
                    .as_mut()
                    .ok_or_else(closed)?
                    .remove_cell_with_hyperlink(*id, address)
                    .map_err(failure)?,
            };
            Ok::<_, PyErr>(if retain { removed } else { (None, None) })
        })?;
        Ok((
            removed.0.map(|cell| encode(py, &cell.value)).transpose()?,
            removed.1.as_ref().map(hyperlinks::owned_fields),
        ))
    }
    pub(crate) fn append(&self, py: Python<'_>, values: Vec<TaggedValue>) -> PyResult<u32> {
        let values = values
            .into_iter()
            .map(|value| decode(py, value))
            .collect::<PyResult<Vec<_>>>()?;
        self.append_values(py, values)
    }
    /// Append a list or tuple of plain values without the tagged encoding.
    /// Returns None, having changed nothing, when Python must take the row.
    pub(crate) fn append_plain(
        &self,
        py: Python<'_>,
        values: &Bound<'_, PyAny>,
    ) -> PyResult<Option<u32>> {
        match plain_row(values)? {
            Some((values, _)) if values.len() <= 16_384 => self.append_values(py, values).map(Some),
            _ => Ok(None),
        }
    }
    pub(crate) fn bounds(&self) -> PyResult<(u32, u32, u32, u32)> {
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
            for merge in sheet.merged_ranges().ranges() {
                let range = merge.range();
                bounds.0 = bounds.0.min(range.start.row.get() + 1);
                bounds.1 = bounds.1.min(range.start.column.get() + 1);
                bounds.2 = bounds.2.max(range.end.row.get() + 1);
                bounds.3 = bounds.3.max(range.end.column.get() + 1);
            }
            Ok(if bounds.2 == 0 { (1, 1, 1, 1) } else { bounds })
        })
    }
    pub(crate) fn row_extent(&self) -> PyResult<u32> {
        self.with(|sheet| Ok(sheet.row_extent()))
    }
    pub(crate) fn charged_bytes(&self) -> PyResult<usize> {
        self.with(|sheet| Ok(sheet.charged_bytes()))
    }
    pub(crate) fn sheet_state(&self) -> PyResult<String> {
        self.with(|sheet| Ok(sheet.visibility().as_str().to_owned()))
    }
    pub(crate) fn set_sheet_state(&self, state: &str) -> PyResult<()> {
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
            SheetStorage::Loaded { .. } => Err(PyRuntimeError::new_err(
                "Loaded visibility changes require the preserving coordinator",
            )),
        }
    }
    pub(crate) fn rename(&self, name: String) -> PyResult<()> {
        let mut storage = lock(&self.storage)?;
        match &mut *storage {
            SheetStorage::Standalone(sheet) => sheet.rename(name).map_err(failure),
            SheetStorage::Bank { book, id } => lock(book)?.rename_sheet(*id, name).map_err(failure),
            SheetStorage::Loaded { .. } => Err(PyRuntimeError::new_err(
                "Renaming existing sheets remains unimplemented",
            )),
        }
    }
    pub(crate) fn shift(
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
    pub(crate) fn move_range(
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
impl NativeSheet {
    fn append_values(&self, py: Python<'_>, values: Vec<CellValue>) -> PyResult<u32> {
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
}
