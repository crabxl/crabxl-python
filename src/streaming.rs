//! Bounded optimized-mode handles; all spreadsheet codecs remain in CrabXL.
use super::*;
use crabxl::RowBatch;
mod writer;
use std::{
    io::{self, Read, Seek, SeekFrom},
    sync::{
        atomic::{AtomicBool, Ordering},
        mpsc::{self, Receiver},
    },
    thread::{self, JoinHandle},
};
pub(crate) use writer::NativeWriteBook;

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
