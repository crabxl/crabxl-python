//! `crabxl._native.ApiReader` and `ApiWriter`: streaming reads and writes.

use super::convert::{
    Modes, Phase, error, partial_style_from_python, raise, row_from_python, style_from_python,
    to_python,
};
use super::workbook::open_options;
use crabxl::read::{Reader, RowOptions};
use crabxl::write::{WriteOptions, Writer};
use crabxl::{OpenOptions, Span, Value};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyList, PyTuple};
use std::io::Cursor;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{Receiver, SyncSender, sync_channel};
use std::sync::{Arc, Mutex};

#[derive(Clone)]
enum Source {
    Path(PathBuf),
    Bytes(Arc<Vec<u8>>),
}

impl Source {
    fn open(&self, options: &OpenOptions) -> crabxl::Result<Reader> {
        match self {
            Self::Path(path) => Reader::open_with(path, options),
            Self::Bytes(bytes) => Reader::from_reader(Cursor::new(bytes.as_ref().clone()), options),
        }
    }
}

#[pyclass(frozen, module = "crabxl._native")]
pub(crate) struct ApiReader {
    source: Source,
    options: OpenOptions,
    modes: Modes,
    names: Vec<String>,
}

#[pymethods]
impl ApiReader {
    #[staticmethod]
    #[pyo3(signature = (path, data, limits, exact_numbers, serial_dates))]
    fn open(
        py: Python<'_>,
        path: Option<PathBuf>,
        data: Option<Vec<u8>>,
        limits: &str,
        exact_numbers: bool,
        serial_dates: bool,
    ) -> PyResult<Self> {
        let options = open_options(limits, None, "reject", exact_numbers)?;
        let source = match (path, data) {
            (Some(path), _) => Source::Path(path),
            (None, Some(data)) => Source::Bytes(Arc::new(data)),
            _ => {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Give a path or bytes",
                ));
            }
        };
        let reader = py
            .detach(|| source.open(&options))
            .map_err(|e| raise(py, e, Phase::Open))?;
        Ok(Self {
            names: reader.sheet_names(),
            source,
            options,
            modes: Modes {
                exact_numbers,
                serial_dates,
            },
        })
    }
    fn sheet_names(&self) -> Vec<String> {
        self.names.clone()
    }
    /// Start a row stream on its own thread. Batches of rows travel through
    /// a channel that holds two batches, so memory stays bounded.
    #[pyo3(signature = (sheet, columns=None, skip=0, limit=None, batch=1024))]
    fn rows(
        &self,
        py: Python<'_>,
        sheet: String,
        columns: Option<String>,
        skip: u32,
        limit: Option<u32>,
        batch: usize,
    ) -> PyResult<ApiRowStream> {
        let mut options = RowOptions::new().with_skip_rows(skip);
        if let Some(columns) = &columns {
            options = options
                .with_columns(columns.as_str())
                .map_err(|e| raise(py, e, Phase::Edit))?;
        }
        if let Some(limit) = limit {
            if limit == 0 {
                return Err(error(py, "InvalidInputError", "limit must be at least 1"));
            }
            options = options.with_max_rows(limit);
        }
        let batch = batch.clamp(1, 1 << 16);
        let (sender, receiver) = sync_channel(2);
        let cancel = Arc::new(AtomicBool::new(false));
        let worker_cancel = Arc::clone(&cancel);
        let source = self.source.clone();
        let open = self.options.clone();
        std::thread::spawn(move || {
            stream(source, open, sheet, options, batch, sender, worker_cancel)
        });
        Ok(ApiRowStream {
            receiver: Mutex::new(Some(receiver)),
            cancel,
            modes: self.modes,
        })
    }
}

type Batch = Vec<(u32, Vec<Value>, Vec<Option<String>>)>;

fn stream(
    source: Source,
    options: OpenOptions,
    sheet: String,
    rows: RowOptions,
    batch: usize,
    sender: SyncSender<crabxl::Result<Batch>>,
    cancel: Arc<AtomicBool>,
) {
    let run = || -> crabxl::Result<()> {
        let mut reader = source.open(&options)?;
        let mut stream = reader.rows(&sheet, &rows)?;
        let mut row = crabxl::read::Row::new();
        let mut pending: Batch = Vec::with_capacity(batch);
        while !cancel.load(Ordering::Relaxed) && stream.read_into(&mut row)? {
            let formulas = (0..row.values().len())
                .map(|index| row.formula(index).map(|f| f.text().to_owned()))
                .collect::<Vec<_>>();
            let formulas = if formulas.iter().any(Option::is_some) {
                formulas
            } else {
                Vec::new()
            };
            pending.push((row.index(), row.values().to_vec(), formulas));
            if pending.len() == batch {
                let full = std::mem::replace(&mut pending, Vec::with_capacity(batch));
                if sender.send(Ok(full)).is_err() {
                    return Ok(());
                }
            }
        }
        if !pending.is_empty() {
            let _ = sender.send(Ok(pending));
        }
        Ok(())
    };
    if let Err(error) = run() {
        let _ = sender.send(Err(error));
    }
}

#[pyclass(frozen, module = "crabxl._native")]
pub(crate) struct ApiRowStream {
    receiver: Mutex<Option<Receiver<crabxl::Result<Batch>>>>,
    cancel: Arc<AtomicBool>,
    modes: Modes,
}

#[pymethods]
impl ApiRowStream {
    /// The next batch as a list of `(index, values, formulas)` tuples, or
    /// `None` after the last row.
    fn next_batch<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyList>>> {
        // The lock moves into the closure: a receiver cannot cross threads by reference.
        let received = py.detach(|| {
            let guard = self.receiver.lock().ok()?;
            Some(guard.as_ref()?.recv())
        });
        let Some(received) = received else {
            return Ok(None);
        };
        let batch = match received {
            Ok(Ok(batch)) => batch,
            Ok(Err(failure)) => {
                self.close();
                return Err(raise(py, failure, Phase::Open));
            }
            Err(_) => {
                self.close();
                return Ok(None);
            }
        };
        let list = PyList::empty(py);
        for (index, values, formulas) in batch {
            let values = values
                .iter()
                .map(|value| to_python(py, value, self.modes))
                .collect::<PyResult<Vec<_>>>()?;
            let formulas = if formulas.is_empty() {
                py.None()
            } else {
                PyTuple::new(py, formulas)?.into_any().unbind()
            };
            list.append((index, PyTuple::new(py, values)?, formulas))?;
        }
        Ok(Some(list))
    }
    /// Stop the stream and release its thread.
    fn close(&self) {
        self.cancel.store(true, Ordering::Relaxed);
        if let Ok(mut guard) = self.receiver.lock() {
            guard.take();
        }
    }
}

impl Drop for ApiRowStream {
    fn drop(&mut self) {
        self.cancel.store(true, Ordering::Relaxed);
    }
}

#[pyclass(frozen, module = "crabxl._native")]
pub(crate) struct ApiWriter {
    writer: Mutex<Option<Writer>>,
    path: Option<PathBuf>,
}

impl ApiWriter {
    fn with<R>(
        &self,
        py: Python<'_>,
        work: impl FnOnce(&mut Writer) -> crabxl::Result<R>,
    ) -> PyResult<R> {
        let mut guard = self
            .writer
            .lock()
            .map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("Writer lock was poisoned"))?;
        let writer = guard
            .as_mut()
            .ok_or_else(|| error(py, "StateError", "The writer is finished or closed"))?;
        work(writer).map_err(|e| raise(py, e, Phase::Edit))
    }
}

#[pymethods]
impl ApiWriter {
    #[staticmethod]
    #[pyo3(signature = (path, compression=None, temp_directory=None))]
    fn create(
        py: Python<'_>,
        path: Option<PathBuf>,
        compression: Option<u8>,
        temp_directory: Option<PathBuf>,
    ) -> PyResult<Self> {
        let mut options = WriteOptions::new();
        options.compression = compression;
        options.temp_directory = temp_directory;
        let writer = match &path {
            Some(path) => Writer::create(path, &options),
            None => Writer::new(&options),
        }
        .map_err(|e| raise(py, e, Phase::Edit))?;
        Ok(Self {
            writer: Mutex::new(Some(writer)),
            path,
        })
    }
    fn add_worksheet(&self, py: Python<'_>, name: &str) -> PyResult<()> {
        self.with(py, |writer| writer.add_worksheet(name).map(|_| ()))
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
        let mut guard = self
            .writer
            .lock()
            .map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("Writer lock was poisoned"))?;
        let writer = guard
            .as_mut()
            .ok_or_else(|| error(py, "StateError", "The writer is finished or closed"))?;
        let mut handle = writer
            .worksheet(sheet)
            .map_err(|e| raise(py, e, Phase::Edit))?;
        for row in rows.try_iter()? {
            let cells = row_from_python(&row?)?;
            match &style {
                Some(style) => handle.append_row_styled(cells, style),
                None => handle.append_row(cells),
            }
            .map_err(|e| raise(py, e, Phase::Edit))?;
        }
        Ok(())
    }
    fn skip_rows(&self, py: Python<'_>, sheet: &str, count: u32) -> PyResult<()> {
        self.with(py, |writer| writer.worksheet(sheet)?.skip_rows(count))
    }
    fn set_column_width(
        &self,
        py: Python<'_>,
        sheet: &str,
        columns: &str,
        width: f64,
    ) -> PyResult<()> {
        self.with(py, |writer| {
            writer
                .worksheet(sheet)?
                .set_column_width(Span::columns(columns)?, width)
        })
    }
    fn freeze_panes(&self, py: Python<'_>, sheet: &str, cell: &str) -> PyResult<()> {
        self.with(py, |writer| writer.worksheet(sheet)?.freeze_panes(cell))
    }
    fn merge(&self, py: Python<'_>, sheet: &str, range: &str) -> PyResult<()> {
        self.with(py, |writer| writer.worksheet(sheet)?.merge(range))
    }
    fn add_validation(
        &self,
        py: Python<'_>,
        sheet: &str,
        choices: Vec<String>,
        ranges: Vec<String>,
    ) -> PyResult<()> {
        self.with(py, |writer| {
            let mut rule = crabxl::features::DataValidation::list(choices)?;
            for range in &ranges {
                rule = rule.with_range(range.as_str())?;
            }
            writer.worksheet(sheet)?.add_data_validation(rule)
        })
    }
    fn add_formula_format(
        &self,
        py: Python<'_>,
        sheet: &str,
        range: &str,
        formula: &str,
        style: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let style = partial_style_from_python(style)?;
        self.with(py, |writer| {
            let format = crabxl::features::ConditionalFormat::formula(range, formula, style)?;
            writer.worksheet(sheet)?.add_conditional_format(format)
        })
    }
    fn finish(&self, py: Python<'_>) -> PyResult<()> {
        let writer = self
            .writer
            .lock()
            .map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("Writer lock was poisoned"))?
            .take()
            .ok_or_else(|| error(py, "StateError", "The writer is finished or closed"))?;
        if self.path.is_none() {
            return Err(error(
                py,
                "StateError",
                "This writer has no path; use finish_bytes",
            ));
        }
        py.detach(|| writer.finish())
            .map_err(|e| raise(py, e, Phase::Edit))
    }
    fn finish_bytes<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        let writer = self
            .writer
            .lock()
            .map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("Writer lock was poisoned"))?
            .take()
            .ok_or_else(|| error(py, "StateError", "The writer is finished or closed"))?;
        let bytes = py
            .detach(|| writer.finish_into(Cursor::new(Vec::new())))
            .map_err(|e| raise(py, e, Phase::Edit))?;
        Ok(PyBytes::new(py, bytes.get_ref()))
    }
    /// Discard everything written so far.
    fn abort(&self) {
        if let Ok(mut guard) = self.writer.lock() {
            guard.take();
        }
    }
}
