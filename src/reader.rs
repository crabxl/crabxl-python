//! Source-backed workbook loading and reader lifecycle.
use crate::*;

#[pyclass]
pub(crate) struct NativeReader {
    pub(crate) reader: Arc<Mutex<Option<WorkbookReader<streaming::SharedFile>>>>,
    pub(crate) loaded: Option<SharedLoaded>,
    pub(crate) source: streaming::SharedFile,
    pub(crate) alive: Arc<std::sync::atomic::AtomicBool>,
    pub(crate) max_bytes: usize,
    pub(crate) config: resources::ResourceConfig,
}
#[pymethods]
impl NativeReader {
    pub(crate) fn theme<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyBytes>>> {
        if let Some(loaded) = &self.loaded {
            return Ok(lock(loaded)?
                .as_mut()
                .ok_or_else(closed)?
                .theme()
                .map_err(failure)?
                .map(|theme| PyBytes::new(py, theme.bytes())));
        }
        Ok(lock(&self.reader)?
            .as_mut()
            .ok_or_else(closed)?
            .theme()
            .map_err(failure)?
            .map(|theme| PyBytes::new(py, theme.bytes())))
    }
    pub(crate) fn set_theme(&self, value: Option<Vec<u8>>) -> PyResult<()> {
        let loaded = self.loaded.as_ref().ok_or_else(|| {
            PyNotImplementedError::new_err("Read-only theme mutation is unavailable")
        })?;
        lock(loaded)?
            .as_mut()
            .ok_or_else(closed)?
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
        let loaded = self.loaded.as_ref().ok_or_else(|| {
            PyNotImplementedError::new_err("Read-only style mutation is unavailable")
        })?;
        style_owners::metadata(
            lock(loaded)?.as_mut().ok_or_else(closed)?,
            name,
            new_name,
            builtin_id,
            hidden,
        )
    }
    pub(crate) fn named_styles(&self) -> PyResult<Vec<String>> {
        if let Some(loaded) = &self.loaded {
            return Ok(style_owners::names(
                lock(loaded)?
                    .as_ref()
                    .ok_or_else(closed)?
                    .model()
                    .style_catalog(),
            ));
        }
        let mut reader = lock(&self.reader)?;
        Ok(style_owners::names(
            reader
                .as_mut()
                .ok_or_else(closed)?
                .style_catalog()
                .map_err(failure)?,
        ))
    }
    pub(crate) fn style_name(&self, style: u32) -> PyResult<String> {
        let loaded = self.loaded.as_ref().ok_or_else(|| {
            PyNotImplementedError::new_err("Detached read-only cells are unavailable")
        })?;
        Ok(style_owners::style_name(
            lock(loaded)?
                .as_ref()
                .ok_or_else(closed)?
                .model()
                .style_catalog(),
            StyleId::new(style),
        ))
    }
    pub(crate) fn named_style_snapshot<'py>(
        &self,
        py: Python<'py>,
        name: &str,
    ) -> PyResult<(u32, String, Bound<'py, PyDict>)> {
        let loaded = self.loaded.as_ref().ok_or_else(|| {
            PyNotImplementedError::new_err("Read-only named style mutation is unavailable")
        })?;
        let mut loaded = lock(loaded)?;
        let book = loaded.as_mut().ok_or_else(closed)?;
        let style = book.named_style_format(name).map_err(failure)?;
        style_owners::snapshot(py, book.model().style_catalog(), style)
    }
    #[pyo3(signature = (value, update=false))]
    pub(crate) fn add_named_style(&self, value: &Bound<'_, PyDict>, update: bool) -> PyResult<u32> {
        let loaded = self.loaded.as_ref().ok_or_else(|| {
            PyNotImplementedError::new_err("Read-only named style mutation is unavailable")
        })?;
        style_owners::register(lock(loaded)?.as_mut().ok_or_else(closed)?, value, update)
    }
    #[new]
    #[pyo3(signature = (path, max_bytes, resources=None, *, editable=false, data_only=false))]
    pub(crate) fn new(
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
    pub(crate) fn names(&self) -> PyResult<Vec<String>> {
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
    pub(crate) fn date_1904(&self) -> PyResult<bool> {
        if let Some(loaded) = &self.loaded {
            return Ok(
                lock(loaded)?.as_ref().ok_or_else(closed)?.model().epoch() == DateEpoch::Mac1904
            );
        }
        Ok(lock(&self.reader)?.as_ref().ok_or_else(closed)?.date_1904())
    }
    pub(crate) fn active_index(&self) -> PyResult<Option<usize>> {
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
    pub(crate) fn active_view_index(&self) -> PyResult<i64> {
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
    pub(crate) fn sheet_state(&self, name: &str) -> PyResult<String> {
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
    pub(crate) fn load_sheet(
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
            storage: Arc::new(Mutex::new(SheetStorage::Standalone(Box::new(sheet)))),
        })
    }
    pub(crate) fn close(&self) -> PyResult<()> {
        self.alive
            .store(false, std::sync::atomic::Ordering::Relaxed);
        lock(&self.reader)?.take();
        if let Some(loaded) = &self.loaded {
            lock(loaded)?.take();
        }
        self.source.close()?;
        Ok(())
    }
    pub(crate) fn dimension(&self, name: &str) -> PyResult<Option<(u32, u32, u32, u32)>> {
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
    pub(crate) fn number_format(&self, style: u32) -> PyResult<String> {
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
    pub(crate) fn style_component<'py>(
        &self,
        py: Python<'py>,
        style: u32,
        name: &str,
    ) -> PyResult<Bound<'py, PyDict>> {
        let resolve = |catalog: Option<&crabxl::StyleCatalog>| {
            if let Some(catalog) = catalog {
                styles::encode(
                    py,
                    name,
                    catalog.cell_style(StyleId::new(style)).map_err(failure)?,
                )
            } else {
                styles::default_component(py, name)
            }
        };
        if let Some(loaded) = &self.loaded {
            return resolve(
                lock(loaded)?
                    .as_ref()
                    .ok_or_else(closed)?
                    .model()
                    .style_catalog(),
            );
        }
        resolve(
            lock(&self.reader)?
                .as_mut()
                .ok_or_else(closed)?
                .style_catalog()
                .map_err(failure)?,
        )
    }
    pub(crate) fn stream(
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
