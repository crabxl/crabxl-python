//! Owned workbook bank bindings.
use crate::*;

#[pyclass]
pub(crate) struct NativeBook {
    pub(crate) book: Arc<Mutex<Workbook>>,
}
#[pymethods]
impl NativeBook {
    pub(crate) fn style_array(&self, style: u32) -> PyResult<[u32; 9]> {
        let book = lock(&self.book)?;
        match book.style_catalog() {
            Some(catalog) => catalog.style_array(StyleId::new(style)).map_err(failure),
            None if style == 0 => Ok([0; 9]),
            None => Err(PyValueError::new_err("Unknown cell style identity")),
        }
    }
    pub(crate) fn number_format(&self, style: u32) -> PyResult<String> {
        let book = lock(&self.book)?;
        Ok(book
            .style_catalog()
            .and_then(|catalog| {
                catalog
                    .cell_format(StyleId::new(style))
                    .and_then(|format| catalog.number_format(format.number_format_id))
            })
            .unwrap_or("General")
            .to_owned())
    }
    pub(crate) fn style_component<'py>(
        &self,
        py: Python<'py>,
        style: u32,
        name: &str,
    ) -> PyResult<Bound<'py, PyDict>> {
        let book = lock(&self.book)?;
        if let Some(catalog) = book.style_catalog() {
            styles::encode(
                py,
                name,
                catalog.cell_style(StyleId::new(style)).map_err(failure)?,
            )
        } else {
            styles::default_component(py, name)
        }
    }
    pub(crate) fn set_template(&self, template: bool) -> PyResult<()> {
        let mut book = lock(&self.book)?;
        let format = template.then_some(crabxl::features::WorkbookFormat::Xltx);
        if book.features().and_then(|features| features.format) == format {
            return Ok(());
        }
        let mut features = book.features().cloned().unwrap_or_default();
        features.format = format;
        book.set_features(Some(features));
        Ok(())
    }

    pub(crate) fn hyperlink_output_ids(
        &self,
        py: Python<'_>,
        requests: hyperlink_views::Requests,
    ) -> PyResult<hyperlink_views::Output> {
        hyperlink_views::owned(py, &self.book, requests)
    }
    pub(crate) fn theme<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyBytes>>> {
        Ok(lock(&self.book)?
            .theme()
            .map(|theme| PyBytes::new(py, theme.bytes())))
    }
    pub(crate) fn set_theme(&self, value: Option<Vec<u8>>) -> PyResult<()> {
        lock(&self.book)?
            .set_theme(value.map(|bytes| crabxl::Theme::from_bytes(bytes.into_boxed_slice())))
            .map_err(failure)
    }
    #[pyo3(signature = (name, new_name, builtin_id=None, hidden=false))]
    pub(crate) fn update_named_style_metadata(
        &self,
        name: &str,
        new_name: String,
        builtin_id: Option<u32>,
        hidden: bool,
    ) -> PyResult<()> {
        style_owners::metadata(&mut *lock(&self.book)?, name, new_name, builtin_id, hidden)
    }
    pub(crate) fn named_styles(&self) -> PyResult<Vec<String>> {
        Ok(style_owners::names(lock(&self.book)?.style_catalog()))
    }
    pub(crate) fn style_name(&self, style: u32) -> PyResult<String> {
        Ok(style_owners::style_name(
            lock(&self.book)?.style_catalog(),
            StyleId::new(style),
        ))
    }
    pub(crate) fn named_style_snapshot<'py>(
        &self,
        py: Python<'py>,
        name: &str,
    ) -> PyResult<(u32, String, Bound<'py, PyDict>)> {
        let mut book = lock(&self.book)?;
        let style = book.named_style_format(name).map_err(failure)?;
        style_owners::snapshot(py, book.style_catalog(), style)
    }
    fn style_collection<'py>(
        &self,
        py: Python<'py>,
        name: &str,
    ) -> PyResult<Vec<Bound<'py, PyDict>>> {
        style_owners::collection(py, lock(&self.book)?.style_catalog(), name)
    }
    fn style_collection_add(&self, name: &str, value: &Bound<'_, PyAny>) -> PyResult<u32> {
        style_owners::collection_add(&mut *lock(&self.book)?, name, value)
    }
    fn named_style_metadata(&self) -> PyResult<style_owners::NamedStyleMetadata> {
        Ok(style_owners::named_metadata(
            lock(&self.book)?.style_catalog(),
        ))
    }
    fn prepare_named_style(&self, value: &Bound<'_, PyDict>) -> PyResult<[u32; 9]> {
        style_owners::prepare_array(&mut *lock(&self.book)?, value)
    }
    fn prepare_cell_style(&self, value: &Bound<'_, PyDict>) -> PyResult<u32> {
        style_owners::prepare(&mut *lock(&self.book)?, value).map(|style| style.get())
    }
    #[pyo3(signature = (value, update=false))]
    pub(crate) fn add_named_style(&self, value: &Bound<'_, PyDict>, update: bool) -> PyResult<u32> {
        style_owners::register(&mut *lock(&self.book)?, value, update)
    }
    pub(crate) fn set_active_view_index(&self, index: i64) -> PyResult<()> {
        lock(&self.book)?.set_active_view_index(index);
        Ok(())
    }
    #[new]
    pub(crate) fn new(max_bytes: usize) -> PyResult<Self> {
        let mut book = Workbook::new(WorkbookLimits {
            max_bytes,
            sheet: EditLimits {
                max_bytes,
                ..EditLimits::default()
            },
            ..WorkbookLimits::default()
        })
        .map_err(failure)?;
        book.set_features(Some(crabxl::WorkbookFeatures {
            calculation: Some(crate::features::default_calculation()),
            ..Default::default()
        }));
        Ok(Self {
            book: Arc::new(Mutex::new(book)),
        })
    }
    #[pyo3(signature = (name, chartsheet=false))]
    pub(crate) fn create_sheet(&self, name: String, chartsheet: bool) -> PyResult<NativeSheet> {
        let mut book = lock(&self.book)?;
        let id = book.create_sheet(name).map_err(failure)?;
        if chartsheet {
            let mut root = crabxl::XmlElement::new("chartsheet");
            root.set_attribute(
                "xmlns",
                "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
            );
            let mut views = crabxl::XmlElement::new("sheetViews");
            let mut view = crabxl::XmlElement::new("sheetView");
            view.set_attribute("workbookViewId", "0");
            view.set_attribute("zoomToFit", "1");
            views.children.push(crabxl::XmlContent::Element(view));
            root.children.push(crabxl::XmlContent::Element(views));
            let result = book.sheet_mut(id).and_then(|mut sheet| {
                sheet.set_features(Some(crabxl::SheetFeatures {
                    chartsheet: Some(root),
                    ..Default::default()
                }))
            });
            if let Err(error) = result {
                book.remove_sheet(id).map_err(failure)?;
                return Err(failure(error));
            }
        }
        Ok(NativeSheet::in_bank(Arc::clone(&self.book), id))
    }
    pub(crate) fn copy_sheet(
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
    pub(crate) fn move_sheet(&self, sheet: &NativeSheet, position: usize) -> PyResult<()> {
        let storage = lock(&sheet.storage)?;
        let SheetStorage::Bank { book, id } = &*storage else {
            return Err(PyValueError::new_err("Sheet is not registered"));
        };
        if !Arc::ptr_eq(book, &self.book) {
            return Err(PyValueError::new_err("Sheet belongs to another workbook"));
        }
        lock(&self.book)?.move_sheet(*id, position).map_err(failure)
    }
    pub(crate) fn remove_sheet(&self, sheet: &NativeSheet) -> PyResult<()> {
        let mut storage = lock(&sheet.storage)?;
        let SheetStorage::Bank { book, id } = &*storage else {
            return Err(PyValueError::new_err("Sheet is not registered"));
        };
        if !Arc::ptr_eq(book, &self.book) {
            return Err(PyValueError::new_err("Sheet belongs to another workbook"));
        }
        let removed = lock(&self.book)?.remove_sheet(*id).map_err(failure)?;
        // Removed Python worksheet/cell aliases remain usable, as in openpyxl.
        *storage = SheetStorage::Standalone(Box::new(removed));
        Ok(())
    }
    pub(crate) fn date_1904(&self) -> PyResult<bool> {
        Ok(lock(&self.book)?.epoch() == DateEpoch::Mac1904)
    }
    pub(crate) fn set_date_1904(&self, value: bool) -> PyResult<()> {
        lock(&self.book)?.set_epoch(if value {
            DateEpoch::Mac1904
        } else {
            DateEpoch::Windows1900
        });
        Ok(())
    }
    pub(crate) fn charged_bytes(&self) -> PyResult<usize> {
        Ok(lock(&self.book)?.charged_bytes())
    }
}
