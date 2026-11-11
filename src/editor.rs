//! Preserving edits and source-backed save lifecycle.
use crate::*;

#[pyclass]
pub(crate) struct NativeEditor {
    pub(crate) editor: Arc<Mutex<Option<WorkbookEditor<File>>>>,
    pub(crate) loaded: Option<SharedLoaded>,
}
#[pymethods]
impl NativeEditor {
    pub(crate) fn remove_external_links(&self, py: Python<'_>, _data_only: bool) -> PyResult<()> {
        let loaded = self.loaded.as_ref().ok_or_else(closed)?;
        let loaded = Arc::clone(loaded);
        py.detach(move || {
            let mut handle = lock(&loaded)?;
            let book = handle.as_mut().ok_or_else(closed)?;
            if book.external_links().map_err(failure)?.is_empty() {
                return Ok(());
            }
            book.remove_external_links().map_err(failure)
        })
    }

    pub(crate) fn set_template(&self, template: bool, keep_vba: bool) -> PyResult<()> {
        use crabxl::features::WorkbookFormat;
        let format = match (template, keep_vba) {
            (false, false) => WorkbookFormat::Xlsx,
            (false, true) => WorkbookFormat::Xlsm,
            (true, false) => WorkbookFormat::Xltx,
            (true, true) => WorkbookFormat::Xltm,
        };
        let loaded = self
            .loaded
            .as_ref()
            .ok_or_else(|| PyValueError::new_err("Template changes require a loaded workbook"))?;
        lock(loaded)?
            .as_mut()
            .ok_or_else(closed)?
            .set_workbook_format(format)
            .map_err(failure)
    }

    pub(crate) fn set_vba(&self, keep: bool) -> PyResult<()> {
        use crabxl::features::MacroPolicy;
        let loaded = self
            .loaded
            .as_ref()
            .ok_or_else(|| PyValueError::new_err("VBA removal requires a loaded workbook"))?;
        lock(loaded)?
            .as_mut()
            .ok_or_else(closed)?
            .set_macro_policy(if keep {
                MacroPolicy::Preserve
            } else {
                MacroPolicy::Remove
            })
            .map_err(failure)
    }

    pub(crate) fn set_date_options(&self, date_1904: bool, iso_dates: bool) -> PyResult<()> {
        let loaded = self
            .loaded
            .as_ref()
            .ok_or_else(|| PyValueError::new_err("Date options require a loaded workbook"))?;
        lock(loaded)?
            .as_mut()
            .ok_or_else(closed)?
            .set_date_options(
                if date_1904 {
                    crabxl::DateEpoch::Mac1904
                } else {
                    crabxl::DateEpoch::Windows1900
                },
                iso_dates,
            )
            .map_err(failure)
    }

    pub(crate) fn hyperlink_output_ids(
        &self,
        py: Python<'_>,
        requests: hyperlink_views::Requests,
    ) -> PyResult<hyperlink_views::Output> {
        let loaded = self.loaded.as_ref().ok_or_else(|| {
            PyValueError::new_err("Hyperlink output identities require a canonical loaded workbook")
        })?;
        hyperlink_views::loaded(py, loaded, requests)
    }
    #[new]
    #[pyo3(signature = (path, max_bytes=None, resources=None, *, reader=None))]
    pub(crate) fn new(
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
            let file = File::open(path).map_err(PyErr::from)?;
            WorkbookEditor::with_options(file, options).map_err(failure)
        })?;
        Ok(Self {
            editor: Arc::new(Mutex::new(Some(editor))),
            loaded: None,
        })
    }
    pub(crate) fn set(
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
    /// Append a list or tuple of plain values to a loaded sheet without loading
    /// its model. Returns None when Python must take the row.
    pub(crate) fn append_plain(
        &self,
        py: Python<'_>,
        name: &str,
        values: &Bound<'_, PyAny>,
    ) -> PyResult<Option<u32>> {
        let Some(loaded) = &self.loaded else {
            return Ok(None);
        };
        let values = match plain_row(values)? {
            Some((values, _)) if values.len() <= 16_384 => values,
            _ => return Ok(None),
        };
        let loaded = Arc::clone(loaded);
        let name = name.to_owned();
        py.detach(move || {
            let mut handle = lock(&loaded)?;
            let loaded = handle.as_mut().ok_or_else(closed)?;
            let id = loaded
                .sheet_id(&name)
                .ok_or_else(|| PyKeyError::new_err(name.clone()))?;
            loaded
                .append(id, values)
                .map(|row| Some(row.get()))
                .map_err(failure)
        })
    }
    pub(crate) fn pending(
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
    pub(crate) fn apply(&self, name: &str, sheet: &NativeSheet) -> PyResult<()> {
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
    pub(crate) fn bounds(&self, name: &str) -> PyResult<(u32, u32)> {
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
    pub(crate) fn patch_bytes(&self) -> PyResult<usize> {
        if let Some(loaded) = &self.loaded {
            return Ok(lock(loaded)?.as_ref().ok_or_else(closed)?.patch_bytes());
        }
        Ok(lock(&self.editor)?
            .as_ref()
            .ok_or_else(closed)?
            .patch_bytes())
    }
    pub(crate) fn set_active_view_index(&self, index: i64) -> PyResult<()> {
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
    pub(crate) fn set_sheet_state(
        &self,
        name: &str,
        state: &str,
        view_index: Option<i64>,
    ) -> PyResult<()> {
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
            return Err(PyValueError::new_err(
                "Combined visibility/view changes require the shared loaded coordinator",
            ));
        }
        lock(&self.editor)?
            .as_mut()
            .ok_or_else(closed)?
            .set_sheet_visibility(name, state)
            .map_err(failure)
    }
    pub(crate) fn sheet_handle(&self, name: &str) -> PyResult<NativeSheet> {
        let book = self.loaded.as_ref().ok_or_else(|| {
            PyValueError::new_err("Lazy handles require the canonical loaded bank")
        })?;
        let id = lock(book)?
            .as_ref()
            .ok_or_else(closed)?
            .sheet_id(name)
            .ok_or_else(|| PyKeyError::new_err(name.to_owned()))?;
        Ok(NativeSheet::in_loaded(Arc::clone(book), id))
    }
    pub(crate) fn remove_sheet(&self, py: Python<'_>, sheet: &NativeSheet) -> PyResult<()> {
        let book = self.loaded.as_ref().ok_or_else(|| {
            PyValueError::new_err("Sheet removal requires the canonical loaded bank")
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
            let mut handle = lock(&book)?;
            let loaded = handle.as_mut().ok_or_else(closed)?;
            let removed = loaded.remove_sheet(*id).map_err(failure)?;
            *storage = SheetStorage::adopt(removed, Some(loaded.model()))?;
            Ok(())
        })
    }
    pub(crate) fn copy_sheet(
        &self,
        py: Python<'_>,
        source: String,
        name: String,
    ) -> PyResult<NativeSheet> {
        let book = self.loaded.as_ref().ok_or_else(|| {
            PyValueError::new_err("Sheet copy requires the canonical loaded bank")
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
    #[pyo3(signature = (name, chartsheet=false))]
    pub(crate) fn create_sheet(
        &self,
        py: Python<'_>,
        name: String,
        chartsheet: bool,
    ) -> PyResult<NativeSheet> {
        let book = self.loaded.as_ref().ok_or_else(|| {
            PyValueError::new_err("Sheet creation requires the canonical loaded bank")
        })?;
        let worker = Arc::clone(book);
        let id = py.detach(move || {
            let mut handle = lock(&worker)?;
            let book = handle.as_mut().ok_or_else(closed)?;
            if chartsheet {
                book.create_empty_chartsheet(name)
            } else {
                book.create_sheet(name)
            }
            .map_err(failure)
        })?;
        Ok(NativeSheet::in_loaded(Arc::clone(book), id))
    }
    pub(crate) fn rename_sheet(&self, py: Python<'_>, name: String, title: String) -> PyResult<()> {
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
    pub(crate) fn move_sheet(&self, py: Python<'_>, name: String, position: usize) -> PyResult<()> {
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
    #[pyo3(signature = (path, verify, compression_level=None, calculate=false))]
    pub(crate) fn save(
        &self,
        py: Python<'_>,
        path: PathBuf,
        verify: bool,
        compression_level: Option<u8>,
        calculate: bool,
    ) -> PyResult<i64> {
        if let Some(loaded) = &self.loaded {
            let loaded = Arc::clone(loaded);
            return py.detach(move || {
                let mut handle = lock(&loaded)?;
                let loaded = handle.as_mut().ok_or_else(closed)?;
                if calculate {
                    loaded.calculate().map_err(failure)?;
                }
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
        if calculate {
            return Err(PyValueError::new_err(
                "Formula calculation needs a loaded workbook",
            ));
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
    pub(crate) fn close(&self) -> PyResult<()> {
        lock(&self.editor)?.take();
        if let Some(loaded) = &self.loaded {
            lock(loaded)?.take();
        }
        Ok(())
    }
}
