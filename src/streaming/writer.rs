//! Sequential writer bindings, separate from read-only worker lifetimes.
use super::*;
use crabxl::WriteStats;

struct WriteState {
    writer: Option<WorkbookWriter>,
    stats: WriteStats,
}
#[pyclass]
pub(crate) struct NativeWriteBook {
    state: Arc<Mutex<WriteState>>,
    maximum_row: usize,
    maximum_metadata: usize,
}
#[pymethods]
impl NativeWriteBook {
    fn register_hyperlink(&self, fields: worksheet::hyperlinks::LinkFields) -> PyResult<u64> {
        let link = worksheet::hyperlinks::decode(fields);
        lock(&self.state)?
            .writer
            .as_mut()
            .ok_or_else(closed)?
            .register_hyperlink_group(&link)
            .map_err(failure)
    }
    fn update_hyperlink(
        &self,
        group: u64,
        fields: worksheet::hyperlinks::LinkFields,
    ) -> PyResult<()> {
        let link = worksheet::hyperlinks::decode(fields);
        lock(&self.state)?
            .writer
            .as_mut()
            .ok_or_else(closed)?
            .update_hyperlink_group(group, &link)
            .map_err(failure)
    }
    fn hyperlink(&self, group: u64) -> PyResult<worksheet::hyperlinks::LinkFields> {
        let link = lock(&self.state)?
            .writer
            .as_mut()
            .ok_or_else(closed)?
            .hyperlink_group(group)
            .map_err(failure)?;
        Ok(worksheet::hyperlinks::owned_fields(&link))
    }
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
            maximum_metadata: maximum,
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
    #[pyo3(signature = (id, index, values, formats=None, hyperlinks=None))]
    fn append(
        &self,
        py: Python<'_>,
        id: usize,
        index: u32,
        values: Vec<TaggedValue>,
        formats: Option<Vec<(u32, Py<PyDict>)>>,
        hyperlinks: Option<Vec<(u32, u64)>>,
    ) -> PyResult<()> {
        let index = RowIndex::new(index).map_err(failure)?;
        if values.len() > 16_384 {
            return Err(PyValueError::new_err("Row exceeds Excel column limits"));
        }
        let hyperlinks = hyperlinks.unwrap_or_default();
        if hyperlinks.windows(2).any(|pair| pair[0].0 >= pair[1].0)
            || hyperlinks
                .last()
                .is_some_and(|(column, _)| *column as usize >= values.len())
        {
            return Err(PyValueError::new_err(
                "Invalid write-only hyperlink coordinates",
            ));
        }
        let links = hyperlinks
            .into_iter()
            .map(|(column, group)| {
                CellAddress::new(index.get(), column)
                    .map(|address| (address, group))
                    .map_err(failure)
            })
            .collect::<PyResult<Vec<_>>>()?;
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
        let mut bytes = format_bytes
            .saturating_add(values.len() * std::mem::size_of::<Cell>())
            .saturating_add(
                links
                    .capacity()
                    .saturating_mul(size_of::<(CellAddress, u64)>()),
            );
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
            writer
                .write_row_with_hyperlink_groups(&row, &links)
                .map_err(failure)
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
    #[pyo3(signature = (path, active, compression_level=None, hyperlink_groups=None))]
    fn save(
        &self,
        py: Python<'_>,
        path: PathBuf,
        active: i64,
        compression_level: Option<u8>,
        hyperlink_groups: Option<Vec<u64>>,
    ) -> PyResult<(i64, Vec<(u64, Option<String>)>)> {
        let mut requested = hyperlink_groups.unwrap_or_default();
        requested.sort_unstable();
        requested.dedup();
        let scratch = if requested.is_empty() {
            0
        } else {
            requested
                .capacity()
                .saturating_mul(size_of::<u64>())
                .saturating_add(
                    requested
                        .len()
                        .saturating_mul(size_of::<(u64, Option<String>)>() + 64),
                )
                .saturating_add(64)
        };
        if scratch > self.maximum_metadata {
            return Err(PyMemoryError::new_err(
                "Public hyperlink identity requests exceed metadata allowance",
            ));
        }
        let mut identities = Vec::new();
        identities
            .try_reserve_exact(requested.len())
            .map_err(|cause| PyMemoryError::new_err(cause.to_string()))?;
        identities.extend(requested.iter().map(|group| (*group, None)));
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
            writer
                .finish_with_hyperlink_ids(&mut temporary, scratch, |group, id| {
                    if let Ok(index) = requested.binary_search(&group) {
                        identities[index].1 = id.map(str::to_owned);
                    }
                    Ok(())
                })
                .map_err(failure)?;
            let temporary = temporary.into_temp_path();
            std::fs::rename(&temporary, path)
                .map_err(|error| PyOSError::new_err(error.to_string()))?;
            Ok((active_after, identities))
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
