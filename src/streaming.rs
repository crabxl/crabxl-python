//! Bounded optimized-mode handles; all spreadsheet codecs remain in CrabXL.
use super::*;
use crabxl::{RowBatch, WriteStats};
use std::{
    io::{self, Read, Seek, SeekFrom},
    sync::{
        atomic::{AtomicBool, Ordering},
        mpsc::{self, Receiver},
    },
    thread::{self, JoinHandle},
};

/// Independent logical positions over one locked original file. Cloning a File
/// alone shares its OS offset; seek/read must therefore be one locked operation.
#[derive(Clone)]
pub(crate) struct SharedFile {
    file: Arc<Mutex<Option<File>>>,
    position: u64,
}
impl SharedFile {
    pub(crate) fn open(path: PathBuf) -> PyResult<Self> {
        Ok(Self {
            file: Arc::new(Mutex::new(Some(
                File::open(path).map_err(|error| PyOSError::new_err(error.to_string()))?,
            ))),
            position: 0,
        })
    }
    pub(crate) fn close(&self) -> PyResult<()> {
        lock(&self.file)?.take();
        Ok(())
    }
    fn handle(&self) -> io::Result<MutexGuard<'_, Option<File>>> {
        self.file
            .lock()
            .map_err(|_| io::Error::other("Source lock was poisoned"))
    }
}
impl Read for SharedFile {
    fn read(&mut self, output: &mut [u8]) -> io::Result<usize> {
        let count = {
            let mut handle = self.handle()?;
            let file = handle
                .as_mut()
                .ok_or_else(|| io::Error::other("Workbook is closed"))?;
            file.seek(SeekFrom::Start(self.position))?;
            file.read(output)?
        };
        self.position += count as u64;
        Ok(count)
    }
}
impl Seek for SharedFile {
    fn seek(&mut self, position: SeekFrom) -> io::Result<u64> {
        let target = match position {
            SeekFrom::Start(value) => i128::from(value),
            SeekFrom::Current(delta) => i128::from(self.position) + i128::from(delta),
            SeekFrom::End(delta) => {
                let handle = self.handle()?;
                i128::from(
                    handle
                        .as_ref()
                        .ok_or_else(|| io::Error::other("Workbook is closed"))?
                        .metadata()?
                        .len(),
                ) + i128::from(delta)
            }
        };
        self.position = target
            .try_into()
            .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "Invalid source position"))?;
        Ok(self.position)
    }
}

struct ReadState {
    receiver: Option<Receiver<crabxl::Result<RowBatch>>>,
    rows: std::vec::IntoIter<Row>,
    worker: Option<JoinHandle<()>>,
    cancel: Arc<AtomicBool>,
}
impl ReadState {
    fn close(&mut self) -> PyResult<()> {
        self.cancel.store(true, Ordering::Relaxed);
        self.receiver.take();
        self.rows = Vec::new().into_iter();
        if let Some(worker) = self.worker.take() {
            worker
                .join()
                .map_err(|_| PyRuntimeError::new_err("Streaming reader worker panicked"))?;
        }
        Ok(())
    }
    fn next(&mut self) -> PyResult<Option<Row>> {
        loop {
            if let Some(row) = self.rows.next() {
                return Ok(Some(row));
            }
            let Some(receiver) = &self.receiver else {
                return Ok(None);
            };
            match receiver.recv() {
                Ok(Ok(batch)) => self.rows = batch.rows.into_iter(),
                Ok(Err(error)) => {
                    self.close()?;
                    return Err(failure(error));
                }
                Err(_) => {
                    self.close()?;
                    return Ok(None);
                }
            }
        }
    }
}
type DenseRow = (u32, Vec<EncodedValue>, Vec<Option<u32>>);

#[pyclass(weakref)]
pub(crate) struct NativeReadStream {
    state: Arc<Mutex<ReadState>>,
    alive: Arc<AtomicBool>,
    first_column: u32,
    last_column: Option<u32>,
}
impl NativeReadStream {
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn start(
        source: SharedFile,
        alive: Arc<AtomicBool>,
        maximum: usize,
        config: resources::ResourceConfig,
        name: String,
        data_only: bool,
        rich_text: bool,
        first_row: u32,
        last_row: Option<u32>,
        first_column: u32,
        last_column: Option<u32>,
    ) -> PyResult<Self> {
        CellAddress::new(first_row, first_column).map_err(failure)?;
        if let Some(row) = last_row {
            RowIndex::new(row).map_err(failure)?;
        }
        if let Some(column) = last_column {
            ColumnIndex::new(column).map_err(failure)?;
        }
        let (sender, receiver) = mpsc::sync_channel(1);
        let cancel = Arc::new(AtomicBool::new(false));
        let worker_cancel = Arc::clone(&cancel);
        let worker_alive = Arc::clone(&alive);
        let worker = thread::Builder::new()
            .name("crabxl-stream".into())
            .spawn(move || {
                let work = || -> crabxl::Result<()> {
                    let limits = config.reader_limits(maximum, true);
                    let strings = config.string_options(maximum, limits)?;
                    let mut book = WorkbookReader::with_limits(source, limits)?;
                    book.set_shared_string_options(strings);
                    let options = ReadOptions {
                        rows: Some(
                            RowIndex::new(first_row)?
                                ..=RowIndex::new(last_row.unwrap_or(1_048_575))?,
                        ),
                        columns: Some(
                            ColumnIndex::new(first_column)?
                                ..=ColumnIndex::new(last_column.unwrap_or(16_383))?,
                        ),
                        stop_after_last_row: last_row.is_some(),
                        data_only,
                        rich_text,
                        // openpyxl read-only mode projects inline runs, while its
                        // shared-string catalog honors the rich_text flag.
                        inline_rich_text: Some(false),
                        ..Default::default()
                    };
                    let mut rows = book.rows_with_options(&name, options)?;
                    while !worker_cancel.load(Ordering::Relaxed)
                        && worker_alive.load(Ordering::Relaxed)
                    {
                        let Some(batch) = rows.read_batch()? else {
                            break;
                        };
                        let complete = last_row.is_some_and(|last| {
                            batch.rows.last().is_some_and(|row| row.index.get() >= last)
                        });
                        if sender.send(Ok(batch)).is_err() || complete {
                            break;
                        }
                    }
                    Ok(())
                };
                if let Err(error) = work() {
                    let _ = sender.send(Err(error));
                }
            })
            .map_err(|error| PyOSError::new_err(error.to_string()))?;
        Ok(Self {
            state: Arc::new(Mutex::new(ReadState {
                receiver: Some(receiver),
                rows: Vec::new().into_iter(),
                worker: Some(worker),
                cancel,
            })),
            alive,
            first_column,
            last_column,
        })
    }
}
#[pymethods]
impl NativeReadStream {
    fn next_values_row(&self, py: Python<'_>) -> PyResult<Option<(u32, Vec<Py<PyAny>>)>> {
        let Some((index, tagged, _)) = self.next_row(py, false)? else {
            return Ok(None);
        };
        let (values, _) = decode_values(py, tagged, false)?;
        Ok(Some((index, values)))
    }
    fn next_row(&self, py: Python<'_>, include_styles: bool) -> PyResult<Option<DenseRow>> {
        if !self.alive.load(Ordering::Relaxed) {
            return Err(closed());
        }
        // Cached rows require neither channel waiting nor a worker join. Keep
        // the GIL for this short nonblocking path; release it when receiving.
        let cached = self
            .state
            .try_lock()
            .ok()
            .and_then(|mut state| state.rows.next());
        let row = if let Some(row) = cached {
            Some(row)
        } else {
            let state = Arc::clone(&self.state);
            py.detach(move || lock(&state)?.next())?
        };
        let Some(row) = row else {
            return Ok(None);
        };
        let end = self
            .last_column
            .or_else(|| row.cells.last().map(|cell| cell.address.column.get()));
        let mut values = Vec::new();
        let mut styles = Vec::new();
        if let Some(end) = end.filter(|end| *end >= self.first_column) {
            values.reserve((end - self.first_column + 1) as usize);
            if include_styles {
                styles.reserve(values.capacity());
            }
            let mut cells = row.cells.iter().peekable();
            for column in self.first_column..=end {
                let cell = cells
                    .peek()
                    .filter(|cell| cell.address.column.get() == column)
                    .copied();
                values.push(encode(
                    py,
                    cell.map_or(&CellValue::Empty, |cell| &cell.value),
                )?);
                if include_styles {
                    styles.push(cell.map(|cell| cell.style.get()));
                }
                if cell.is_some() {
                    cells.next();
                }
            }
        }
        Ok(Some((row.index.get(), values, styles)))
    }
    fn close(&self, py: Python<'_>) -> PyResult<()> {
        let state = Arc::clone(&self.state);
        py.detach(move || lock(&state)?.close())
    }
}
impl Drop for NativeReadStream {
    fn drop(&mut self) {
        if let Ok(mut state) = self.state.lock() {
            let _ = state.close();
        }
    }
}

struct WriteState {
    writer: Option<WorkbookWriter>,
    stats: WriteStats,
}
#[pyclass]
pub(crate) struct NativeWriteBook {
    state: Arc<Mutex<WriteState>>,
    maximum_row: usize,
}
#[pymethods]
impl NativeWriteBook {
    fn remove_dimension(&self, id: usize, rows: bool, index: u32) -> PyResult<bool> {
        let mut state = lock(&self.state)?;
        let writer = state.writer.as_mut().ok_or_else(closed)?;
        if rows {
            writer
                .remove_interleaved_row_dimension(id, RowIndex::new(index).map_err(failure)?)
                .map_err(failure)
        } else {
            writer
                .remove_interleaved_column_dimension(id, ColumnIndex::new(index).map_err(failure)?)
                .map_err(failure)
        }
    }
    #[allow(clippy::too_many_arguments)]
    fn group_dimensions(
        &self,
        id: usize,
        rows: bool,
        start: u32,
        end: u32,
        level: u32,
        hidden: bool,
    ) -> PyResult<()> {
        let mut state = lock(&self.state)?;
        let writer = state.writer.as_mut().ok_or_else(closed)?;
        if rows {
            writer
                .group_interleaved_rows(
                    id,
                    RowIndex::new(start).map_err(failure)?,
                    RowIndex::new(end).map_err(failure)?,
                    level,
                    hidden,
                )
                .map_err(failure)
        } else {
            writer
                .group_interleaved_columns(
                    id,
                    ColumnIndex::new(start).map_err(failure)?,
                    ColumnIndex::new(end).map_err(failure)?,
                    level,
                    hidden,
                )
                .map_err(failure)
        }
    }
    fn dimension_component<'py>(
        &self,
        py: Python<'py>,
        id: usize,
        rows: bool,
        index: u32,
        name: &str,
    ) -> PyResult<Bound<'py, PyDict>> {
        let state = lock(&self.state)?;
        let writer = state.writer.as_ref().ok_or_else(closed)?;
        let dimension = dimensions::Dimension::snapshot(
            writer.interleaved_dimensions(id).map_err(failure)?,
            rows,
            index,
        )?;
        styles::encode(
            py,
            name,
            writer
                .style_catalog()
                .ok_or_else(closed)?
                .cell_style(dimension.style())
                .map_err(failure)?,
        )
    }
    fn dimension_number_format(&self, id: usize, rows: bool, index: u32) -> PyResult<String> {
        let state = lock(&self.state)?;
        let writer = state.writer.as_ref().ok_or_else(closed)?;
        let dimension = dimensions::Dimension::snapshot(
            writer.interleaved_dimensions(id).map_err(failure)?,
            rows,
            index,
        )?;
        let catalog = writer.style_catalog().ok_or_else(closed)?;
        Ok(catalog
            .cell_format(dimension.style())
            .and_then(|format| catalog.number_format(format.number_format_id))
            .unwrap_or("General")
            .into())
    }
    fn set_dimension_component(
        &self,
        id: usize,
        rows: bool,
        index: u32,
        value: PyRef<'_, styles::NativeStyleComponent>,
    ) -> PyResult<()> {
        let mut state = lock(&self.state)?;
        let writer = state.writer.as_mut().ok_or_else(closed)?;
        let mut dimension = dimensions::Dimension::snapshot(
            writer.interleaved_dimensions(id).map_err(failure)?,
            rows,
            index,
        )?;
        let style = writer
            .derive_style_component(dimension.style(), value.component.clone())
            .map_err(failure)?;
        dimension.set_style(style);
        dimension.apply_writer(writer, id).map_err(failure)
    }
    fn set_dimension_number_format(
        &self,
        id: usize,
        rows: bool,
        index: u32,
        code: String,
    ) -> PyResult<()> {
        let mut state = lock(&self.state)?;
        let writer = state.writer.as_mut().ok_or_else(closed)?;
        let mut dimension = dimensions::Dimension::snapshot(
            writer.interleaved_dimensions(id).map_err(failure)?,
            rows,
            index,
        )?;
        let style = style_owners::StyleOwner::number(writer, dimension.style(), code.into())
            .map_err(failure)?;
        dimension.set_style(style);
        dimension.apply_writer(writer, id).map_err(failure)
    }
    fn dimension<'py>(
        &self,
        py: Python<'py>,
        id: usize,
        rows: bool,
        index: u32,
    ) -> PyResult<Option<Bound<'py, PyDict>>> {
        let state = lock(&self.state)?;
        dimensions::encode(
            py,
            state
                .writer
                .as_ref()
                .ok_or_else(closed)?
                .interleaved_dimensions(id)
                .map_err(failure)?,
            rows,
            index,
        )
    }
    fn dimension_keys(&self, id: usize, rows: bool) -> PyResult<Vec<u32>> {
        let state = lock(&self.state)?;
        Ok(dimensions::keys(
            state
                .writer
                .as_ref()
                .ok_or_else(closed)?
                .interleaved_dimensions(id)
                .map_err(failure)?,
            rows,
        ))
    }
    fn set_dimension(
        &self,
        id: usize,
        rows: bool,
        index: u32,
        value: &Bound<'_, PyDict>,
    ) -> PyResult<()> {
        let mut state = lock(&self.state)?;
        let writer = state.writer.as_mut().ok_or_else(closed)?;
        if rows {
            writer
                .set_interleaved_row_dimension(id, dimensions::row(value, index)?)
                .map_err(failure)
        } else {
            writer
                .set_interleaved_column_dimension(id, dimensions::column(value, index)?)
                .map_err(failure)
        }
    }
    fn theme<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyBytes>>> {
        Ok(lock(&self.state)?
            .writer
            .as_ref()
            .ok_or_else(closed)?
            .theme()
            .map(|theme| PyBytes::new(py, theme.bytes())))
    }
    fn set_theme(&self, value: Option<Vec<u8>>) -> PyResult<()> {
        let theme = value.map_or_else(crabxl::ThemeWritePolicy::default, |bytes| {
            crabxl::ThemeWritePolicy::Custom(crabxl::Theme::from_bytes(bytes.into_boxed_slice()))
        });
        lock(&self.state)?
            .writer
            .as_mut()
            .ok_or_else(closed)?
            .set_theme(theme)
            .map_err(failure)
    }
    #[pyo3(signature = (name, new_name, builtin_id=None, hidden=false))]
    fn update_named_style_metadata(
        &self,
        name: &str,
        new_name: String,
        builtin_id: Option<u32>,
        hidden: bool,
    ) -> PyResult<()> {
        style_owners::metadata(
            lock(&self.state)?.writer.as_mut().ok_or_else(closed)?,
            name,
            new_name,
            builtin_id,
            hidden,
        )
    }
    fn named_styles(&self) -> PyResult<Vec<String>> {
        Ok(style_owners::names(
            lock(&self.state)?
                .writer
                .as_ref()
                .ok_or_else(closed)?
                .style_catalog(),
        ))
    }
    #[pyo3(signature = (value, update=false))]
    fn add_named_style(&self, value: &Bound<'_, PyDict>, update: bool) -> PyResult<u32> {
        style_owners::register(
            lock(&self.state)?.writer.as_mut().ok_or_else(closed)?,
            value,
            update,
        )
    }
    fn named_style_format(&self, name: &str) -> PyResult<u32> {
        lock(&self.state)?
            .writer
            .as_mut()
            .ok_or_else(closed)?
            .named_style_format(name)
            .map(|id| id.get())
            .map_err(failure)
    }
    fn style_component<'py>(
        &self,
        py: Python<'py>,
        style: u32,
        name: &str,
    ) -> PyResult<Bound<'py, PyDict>> {
        let state = lock(&self.state)?;
        let writer = state.writer.as_ref().ok_or_else(closed)?;
        let catalog = writer.style_catalog().ok_or_else(closed)?;
        styles::encode(
            py,
            name,
            catalog.cell_style(StyleId::new(style)).map_err(failure)?,
        )
    }
    fn number_format(&self, style: u32) -> PyResult<String> {
        let state = lock(&self.state)?;
        let catalog = state
            .writer
            .as_ref()
            .ok_or_else(closed)?
            .style_catalog()
            .ok_or_else(closed)?;
        let format = catalog
            .cell_format(StyleId::new(style))
            .ok_or_else(|| PyValueError::new_err("Unknown style identity"))?;
        Ok(catalog
            .number_format(format.number_format_id)
            .unwrap_or("General")
            .into())
    }
    #[new]
    #[pyo3(signature = (maximum, iso_dates=false, date_1904=false, temp_directory=None))]
    fn new(
        maximum: usize,
        iso_dates: bool,
        date_1904: bool,
        temp_directory: Option<PathBuf>,
    ) -> PyResult<Self> {
        let options = WriteOptions {
            max_metadata_bytes: maximum,
            max_row_bytes: maximum.min(1024 * 1024),
            iso_dates,
            date_1904,
            temp_directory,
            ..Default::default()
        };
        let maximum_row = options.max_row_bytes;
        Ok(Self {
            state: Arc::new(Mutex::new(WriteState {
                writer: Some(WorkbookWriter::new(options).map_err(failure)?),
                stats: WriteStats::default(),
            })),
            maximum_row,
        })
    }
    fn create_sheet(&self, name: String) -> PyResult<usize> {
        lock(&self.state)?
            .writer
            .as_mut()
            .ok_or_else(closed)?
            .start_interleaved_sheet(name)
            .map_err(failure)
    }
    fn rename_sheet(&self, id: usize, name: String) -> PyResult<()> {
        lock(&self.state)?
            .writer
            .as_mut()
            .ok_or_else(closed)?
            .rename_interleaved_sheet(id, name)
            .map_err(failure)
    }
    fn set_sheet_state(&self, id: usize, state: &str) -> PyResult<()> {
        lock(&self.state)?
            .writer
            .as_mut()
            .ok_or_else(closed)?
            .set_sheet_visibility(id, visibility(state)?)
            .map_err(failure)
    }
    fn configure(&self, date_1904: bool, iso_dates: bool) -> PyResult<()> {
        lock(&self.state)?
            .writer
            .as_mut()
            .ok_or_else(closed)?
            .set_temporal_options(date_1904, iso_dates)
            .map_err(failure)
    }
    #[pyo3(signature = (id, index, values, formats=None))]
    fn append(
        &self,
        py: Python<'_>,
        id: usize,
        index: u32,
        values: Vec<TaggedValue>,
        formats: Option<Vec<(u32, Py<PyDict>)>>,
    ) -> PyResult<()> {
        let index = RowIndex::new(index).map_err(failure)?;
        if values.len() > 16_384 {
            return Err(PyValueError::new_err("Row exceeds Excel column limits"));
        }
        let formats = formats.unwrap_or_default();
        if formats.windows(2).any(|pair| pair[0].0 >= pair[1].0)
            || formats
                .last()
                .is_some_and(|(column, _)| *column as usize >= values.len())
        {
            return Err(PyValueError::new_err(
                "Invalid write-only format coordinates",
            ));
        }
        let mut decoded_formats = Vec::with_capacity(formats.len());
        let mut format_bytes = 0usize;
        for (column, value) in formats {
            let value = value.bind(py);
            let base = value
                .get_item("style_id")?
                .filter(|v| !v.is_none())
                .map(|v| v.extract::<u32>())
                .transpose()?;
            let number = value
                .get_item("number_format")?
                .filter(|v| !v.is_none())
                .map(|v| v.extract::<String>())
                .transpose()?;
            format_bytes = format_bytes.saturating_add(number.as_ref().map_or(0, String::len));
            let mut components = Vec::new();
            for name in ["font", "fill", "border", "alignment", "protection"] {
                if let Some(item) = value.get_item(name)? {
                    let native = item.extract::<PyRef<'_, styles::NativeStyleComponent>>()?;
                    format_bytes = format_bytes.saturating_add(native.retained_bytes());
                    if format_bytes > self.maximum_row {
                        return Err(PyMemoryError::new_err(
                            "Write-only row styles exceed their byte allowance",
                        ));
                    }
                    components.push(native.component.clone());
                }
            }
            decoded_formats.push((column, base, number, components));
        }
        let formats = decoded_formats;
        let mut row = Row::new(index);
        let mut bytes = format_bytes.saturating_add(values.len() * std::mem::size_of::<Cell>());
        for (column, value) in values.into_iter().enumerate() {
            let value = decode(py, value)?;
            bytes = bytes.saturating_add(value.heap_bytes());
            if bytes > self.maximum_row {
                return Err(PyMemoryError::new_err(
                    "Write-only row exceeds its byte allowance",
                ));
            }
            if !matches!(value, CellValue::Empty)
                || formats
                    .binary_search_by_key(&(column as u32), |(column, ..)| *column)
                    .is_ok()
            {
                row.cells.push(Cell {
                    address: CellAddress::new(index.get(), column as u32).map_err(failure)?,
                    value,
                    style: StyleId::new(0),
                });
            }
        }
        let mut formats = formats.into_iter().peekable();
        let state = Arc::clone(&self.state);
        py.detach(move || {
            let mut state = lock(&state)?;
            let writer = state.writer.as_mut().ok_or_else(closed)?;
            writer.activate_sheet(id).map_err(failure)?;
            for cell in &mut row.cells {
                if formats
                    .peek()
                    .is_some_and(|(column, ..)| *column == cell.address.column.get())
                {
                    let (_, base, code, components) = formats.next().ok_or_else(closed)?;
                    let code_was_explicit = code.is_some() || base.is_some();
                    let mut style = StyleId::new(base.unwrap_or(0));
                    if let Some(code) = code {
                        style = style_owners::StyleOwner::number(writer, style, code.into())
                            .map_err(failure)?;
                    }
                    for component in components {
                        style = writer
                            .derive_style_component(style, component)
                            .map_err(failure)?;
                    }
                    if code_was_explicit {
                        cell.set_style(style);
                    } else {
                        cell.set_appearance_style(style);
                    }
                }
            }
            writer.write_row(&row).map_err(failure)
        })
    }
    fn close_sheet(&self, id: usize) -> PyResult<()> {
        lock(&self.state)?
            .writer
            .as_mut()
            .ok_or_else(closed)?
            .close_interleaved_sheet(id)
            .map_err(failure)
    }
    fn stats(&self) -> PyResult<(u64, u64, u64)> {
        let state = lock(&self.state)?;
        let stats = state
            .writer
            .as_ref()
            .map_or(state.stats, WorkbookWriter::stats);
        Ok((stats.rows, stats.cells, stats.peak_temp_bytes))
    }
    #[pyo3(signature = (path, active, compression_level=None))]
    fn save(
        &self,
        py: Python<'_>,
        path: PathBuf,
        active: i64,
        compression_level: Option<u8>,
    ) -> PyResult<i64> {
        let state = Arc::clone(&self.state);
        py.detach(move || {
            let mut state = lock(&state)?;
            let writer = state.writer.as_mut().ok_or_else(closed)?;
            writer.set_active_view_index(active).map_err(failure)?;
            writer
                .set_compression_level(compression_level)
                .map_err(failure)?;
            state.stats = writer.stats();
            let writer = state.writer.take().ok_or_else(closed)?;
            let active_after = writer
                .active_view_selection()
                .map_err(failure)?
                .requested_index;
            let parent = path
                .parent()
                .filter(|path| !path.as_os_str().is_empty())
                .unwrap_or_else(|| std::path::Path::new("."));
            let mut temporary = tempfile::Builder::new()
                .prefix("crabxl-stream-save-")
                .tempfile_in(parent)
                .map_err(|error| PyOSError::new_err(error.to_string()))?;
            writer.finish(&mut temporary).map_err(failure)?;
            let temporary = temporary.into_temp_path();
            std::fs::rename(&temporary, path)
                .map_err(|error| PyOSError::new_err(error.to_string()))?;
            Ok(active_after)
        })
    }
    fn close(&self, py: Python<'_>) -> PyResult<()> {
        let state = Arc::clone(&self.state);
        py.detach(move || {
            if let Some(mut writer) = lock(&state)?.writer.take() {
                writer.abort().map_err(failure)?;
            }
            Ok(())
        })
    }
}
