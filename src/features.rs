//! Worksheet and workbook features exchanged with Python as plain XML.
//!
//! The Python classes copied from openpyxl serialise to and parse from XML.
//! The Rust core owns the model and the package codecs; this module only moves
//! bytes through `crabxl::feature_xml`. Comments are built directly.
use crate::*;
use crabxl::feature_xml;
use crabxl::features::Comment;
use crabxl::{SheetFeatures, WorkbookFeatures};
use std::collections::BTreeMap;

pub(crate) type PivotInput = (usize, Vec<u8>, Vec<u8>, Option<Vec<u8>>);
type PivotObject = (u32, Vec<u8>, Vec<u8>, bool);
type PivotObjectEdit = (usize, Vec<u8>, Vec<u8>, bool, Option<Vec<u8>>);

#[pyfunction]
pub(crate) fn sheet_pivot_objects_read(
    py: Python<'_>,
    sheet: &NativeSheet,
) -> PyResult<Vec<PivotObject>> {
    let storage = Arc::clone(&sheet.storage);
    py.detach(move || {
        let storage = lock(&storage)?;
        let SheetStorage::Loaded { book, id } = &*storage else {
            return Ok(Vec::new());
        };
        let mut handle = lock(book)?;
        let pivots = handle
            .as_mut()
            .ok_or_else(closed)?
            .sheet_pivots(*id)
            .map_err(failure)?;
        pivots
            .iter()
            .map(|pivot| {
                Ok((
                    pivot.cache.id,
                    feature_xml::pivot_definition_to_xml(&pivot.definition).map_err(failure)?,
                    feature_xml::pivot_definition_to_xml(&pivot.cache.definition)
                        .map_err(failure)?,
                    pivot.cache.records().is_some(),
                ))
            })
            .collect()
    })
}

#[pyfunction]
pub(crate) fn sheet_pivot_records_read(
    py: Python<'_>,
    sheet: &NativeSheet,
    index: usize,
) -> PyResult<Option<Vec<u8>>> {
    let storage = Arc::clone(&sheet.storage);
    py.detach(move || {
        let storage = lock(&storage)?;
        let SheetStorage::Loaded { book, id } = &*storage else {
            return Ok(None);
        };
        let mut handle = lock(book)?;
        let book = handle.as_mut().ok_or_else(closed)?;
        book.sheet_pivots(*id).map_err(failure)?;
        let maximum = book
            .memory_allowance()
            .retained_data_bytes
            .saturating_sub(book.managed_retained_bytes());
        let pivot = book
            .sheet_pivots(*id)
            .map_err(failure)?
            .get(index)
            .ok_or_else(|| PyValueError::new_err("Pivot source changed"))?;
        let Some(records) = pivot.cache.records() else {
            return Ok(None);
        };
        let length = usize::try_from(records.len()).map_err(|_| {
            pyo3::exceptions::PyMemoryError::new_err("Pivot records exceed address space")
        })?;
        if length > maximum {
            return Err(pyo3::exceptions::PyMemoryError::new_err(
                "Pivot record projection exceeds the workbook memory allowance",
            ));
        }
        let mut output = Vec::new();
        output.try_reserve_exact(length).map_err(|_| {
            pyo3::exceptions::PyMemoryError::new_err("Cannot allocate pivot record projection")
        })?;
        records
            .write_to(&mut output)
            .map_err(|error| pyo3::exceptions::PyOSError::new_err(error.to_string()))?;
        Ok(Some(output))
    })
}

#[pyfunction]
pub(crate) fn sheet_pivot_objects_write(
    py: Python<'_>,
    sheet: &NativeSheet,
    inputs: Vec<PivotObjectEdit>,
) -> PyResult<()> {
    let storage = Arc::clone(&sheet.storage);
    py.detach(move || {
        let storage = lock(&storage)?;
        let SheetStorage::Loaded { book, id } = &*storage else {
            return Err(PyValueError::new_err(
                "Pivot settings require a loaded worksheet",
            ));
        };
        let mut handle = lock(book)?;
        let book = handle.as_mut().ok_or_else(closed)?;
        let mut pivots = book.sheet_pivots(*id).map_err(failure)?.to_vec();
        if inputs.len() > pivots.len() {
            return Err(PyValueError::new_err("Pivot source changed"));
        }
        let mut caches = BTreeMap::new();
        for (pivot, (identity, table, cache, changed_records, records)) in
            pivots.iter_mut().zip(inputs)
        {
            pivot.definition = feature_xml::pivot_table_from_xml(&table).map_err(failure)?;
            let mut updated = (*pivot.cache).clone();
            updated.definition = feature_xml::pivot_cache_from_xml(&cache).map_err(failure)?;
            if changed_records {
                if let Some(records) = records {
                    let root = feature_xml::pivot_records_from_xml(&records).map_err(failure)?;
                    let count = root
                        .attribute("count")
                        .unwrap_or("0")
                        .parse()
                        .map_err(|_| PyValueError::new_err("Invalid pivot record count"))?;
                    updated.set_records(records.into(), count);
                } else {
                    updated.clear_records();
                }
            }
            updated.synchronize_records_reference();
            updated.validate_worksheet_fields().map_err(failure)?;
            let updated = Arc::new(updated);
            if let Some(previous) = caches.get(&identity) {
                if Arc::as_ref(previous) != Arc::as_ref(&updated) {
                    return Err(PyValueError::new_err(
                        "Conflicting definitions for a shared pivot cache",
                    ));
                }
                pivot.cache = Arc::clone(previous);
            } else {
                caches.insert(identity, Arc::clone(&updated));
                pivot.cache = updated;
            }
        }
        book.set_sheet_pivots(*id, pivots).map_err(failure)
    })
}

fn chartsheet_xml(features: Option<&SheetFeatures>) -> PyResult<Vec<u8>> {
    features
        .and_then(|features| features.chartsheet.as_ref())
        .map(feature_xml::chartsheet_to_xml)
        .transpose()
        .map(|xml| xml.unwrap_or_default())
        .map_err(failure)
}

#[pyfunction]
pub(crate) fn sheet_chartsheet_read(py: Python<'_>, sheet: &NativeSheet) -> PyResult<Vec<u8>> {
    let storage = Arc::clone(&sheet.storage);
    py.detach(move || {
        let storage = lock(&storage)?;
        match &*storage {
            SheetStorage::Standalone(sheet) => chartsheet_xml(sheet.features()),
            SheetStorage::Bank { book, id } => {
                let book = lock(book)?;
                chartsheet_xml(book.sheet(*id).map_err(failure)?.features())
            }
            SheetStorage::Loaded { book, id } => {
                let mut handle = lock(book)?;
                let book = handle.as_mut().ok_or_else(closed)?;
                chartsheet_xml(Some(book.sheet_features(*id).map_err(failure)?))
            }
        }
    })
}

#[pyfunction]
pub(crate) fn reader_chartsheet_read(
    py: Python<'_>,
    reader: &NativeReader,
    name: String,
) -> PyResult<Vec<u8>> {
    let shared = Arc::clone(&reader.reader);
    py.detach(move || {
        let mut handle = lock(&shared)?;
        let reader = handle.as_mut().ok_or_else(closed)?;
        chartsheet_xml(Some(&reader.sheet_features(&name).map_err(failure)?))
    })
}

#[pyfunction]
pub(crate) fn sheet_chartsheet_write(
    py: Python<'_>,
    sheet: &NativeSheet,
    xml: Vec<u8>,
) -> PyResult<()> {
    let storage = Arc::clone(&sheet.storage);
    py.detach(move || {
        let root = feature_xml::chartsheet_from_xml(&xml).map_err(failure)?;
        update_sheet_features(
            &storage,
            |_, _| Ok(()),
            |features| {
                features.chartsheet = Some(root);
                Ok(0)
            },
        )?;
        Ok(())
    })
}

pub(crate) fn native_pivots(
    inputs: Vec<PivotInput>,
) -> PyResult<Vec<crabxl::features::PivotTable>> {
    let mut added = Vec::with_capacity(inputs.len());
    let mut caches = BTreeMap::new();
    for (identity, table, cache, records) in inputs {
        let mut pivot =
            feature_xml::pivot_from_xml(&table, &cache, records.as_deref()).map_err(failure)?;
        pivot.cache.validate_worksheet_fields().map_err(failure)?;
        if let Some(existing) = caches.get(&identity) {
            if pivot.cache.as_ref() != Arc::as_ref(existing) {
                return Err(PyValueError::new_err(
                    "Conflicting definitions for a shared pivot cache",
                ));
            }
            pivot.cache = Arc::clone(existing);
        } else {
            caches.insert(identity, Arc::clone(&pivot.cache));
        }
        added.push(pivot);
    }
    Ok(added)
}

#[pyfunction]
#[pyo3(signature = (sheet, base, inputs, cache_sources=None))]
pub(crate) fn sheet_pivots_write(
    py: Python<'_>,
    sheet: &NativeSheet,
    base: Option<usize>,
    inputs: Vec<PivotInput>,
    cache_sources: Option<Vec<(usize, String, usize)>>,
) -> PyResult<usize> {
    let storage = Arc::clone(&sheet.storage);
    py.detach(move || {
        let identities: Vec<_> = inputs.iter().map(|input| input.0).collect();
        let mut added = native_pivots(inputs)?;
        let mut shared = BTreeMap::new();
        if let Some(sources) = cache_sources.filter(|sources| !sources.is_empty()) {
            let storage = lock(&storage)?;
            let SheetStorage::Loaded { book, .. } = &*storage else {
                return Err(PyValueError::new_err(
                    "Shared source caches require a loaded workbook",
                ));
            };
            let mut handle = lock(book)?;
            let book = handle.as_mut().ok_or_else(closed)?;
            for (identity, name, index) in sources {
                let source = book
                    .sheet_id(&name)
                    .ok_or_else(|| PyValueError::new_err("Pivot source worksheet changed"))?;
                let pivot = book
                    .sheet_pivots(source)
                    .map_err(failure)?
                    .get(index)
                    .ok_or_else(|| PyValueError::new_err("Pivot source changed"))?;
                shared.insert(identity, Arc::clone(&pivot.cache));
            }
        }
        for (pivot, identity) in added.iter_mut().zip(identities) {
            if let Some(cache) = shared.get(&identity) {
                pivot.cache = Arc::clone(cache);
                for edge in &mut pivot.relationships {
                    if edge.kind.rsplit('/').next() == Some("pivotCacheDefinition") {
                        edge.target = cache
                            .source_part
                            .as_deref()
                            .unwrap_or("crabxl/cache")
                            .into();
                    }
                }
            }
        }
        update_sheet_features(
            &storage,
            |book, id| book.sheet_pivots(id).map(|_| ()),
            |features| {
                let pivots = features.pivots.get_or_insert_with(Vec::new);
                let base = base.unwrap_or(pivots.len());
                if base > pivots.len() {
                    return Err(PyValueError::new_err("Pivot source changed"));
                }
                pivots.truncate(base);
                pivots.extend(added);
                Ok(base)
            },
        )
    })
}

pub(crate) type CommentTuple = (u32, u32, String, String, f64, f64, bool);

pub(crate) fn native_comments(comments: Vec<CommentTuple>) -> PyResult<Vec<Comment>> {
    comments
        .into_iter()
        .map(|(row, column, author, text, width, height, visible)| {
            let mut comment = Comment::new(
                CellAddress::new(row, column).map_err(failure)?,
                text,
                author,
            );
            comment.width = width;
            comment.height = height;
            comment.visible = visible;
            Ok(comment)
        })
        .collect()
}
pub(crate) type SheetOut = (
    Vec<u8>,
    Vec<Vec<u8>>,
    Vec<CommentTuple>,
    BTreeMap<u32, Vec<u8>>,
);
pub(crate) type WorkbookOut = (
    Vec<u8>,
    Option<Vec<u8>>,
    Option<Vec<u8>>,
    Option<Vec<u8>>,
    Option<Vec<u8>>,
);

fn pending_integration(what: &str) -> PyErr {
    PyNotImplementedError::new_err(format!(
        "{what} on a loaded workbook requires the core editor integration of features"
    ))
}

fn sheet_out(
    features: Option<&SheetFeatures>,
    catalog: Option<&crabxl::StyleCatalog>,
) -> PyResult<Option<SheetOut>> {
    let Some(features) = features else {
        return Ok(None);
    };
    let xml = feature_xml::sheet_features_to_xml(&SheetFeatures {
        protection: features.protection.clone(),
        scenarios: features.scenarios.clone(),
        auto_filter: features.auto_filter.clone(),
        sort_state: features.sort_state.clone(),
        conditional_formats: features.conditional_formats.clone(),
        data_validations: features.data_validations.clone(),
        header_footer: features.header_footer.clone(),
        tables: features.tables.clone(),
        ..Default::default()
    })
    .map_err(failure)?;
    let comments = features
        .comments
        .iter()
        .map(|c| {
            (
                c.address.row.get(),
                c.address.column.get(),
                c.author.to_string(),
                c.text.to_string(),
                c.width,
                c.height,
                c.visible,
            )
        })
        .collect();
    let mut dxfs = BTreeMap::new();
    if let Some(catalog) = catalog {
        for rule in features
            .conditional_formats
            .iter()
            .flat_map(|block| block.rules.iter())
        {
            if let Some(id) = rule.dxf_id
                && let Some(style) = catalog.differential_styles.get(id as usize)
            {
                dxfs.insert(
                    id,
                    feature_xml::differential_style_to_xml(style).map_err(failure)?,
                );
            }
        }
    }
    Ok(Some((xml.worksheet, xml.tables, comments, dxfs)))
}

/// Features of a sheet of a new or loaded workbook, or `None` when it has none.
#[pyfunction]
pub(crate) fn sheet_features_read(
    py: Python<'_>,
    sheet: &NativeSheet,
) -> PyResult<Option<SheetOut>> {
    let storage = Arc::clone(&sheet.storage);
    py.detach(move || {
        let storage = lock(&storage)?;
        match &*storage {
            SheetStorage::Standalone(sheet) => sheet_out(sheet.features(), None),
            SheetStorage::Bank { book, id } => {
                let book = lock(book)?;
                let sheet = book.sheet(*id).map_err(failure)?;
                sheet_out(sheet.features(), book.style_catalog())
            }
            SheetStorage::Loaded { book, id } => {
                let mut handle = lock(book)?;
                let loaded = handle.as_mut().ok_or_else(closed)?;
                let features = loaded.sheet_features(*id).map_err(failure)?.clone();
                let catalog = loaded.model().style_catalog();
                sheet_out(Some(&features), catalog)
            }
        }
    })
}

/// Features of a sheet of a read-only workbook.
#[pyfunction]
pub(crate) fn reader_sheet_features(
    py: Python<'_>,
    reader: &NativeReader,
    name: String,
) -> PyResult<Option<SheetOut>> {
    let shared = Arc::clone(&reader.reader);
    py.detach(move || {
        let mut handle = lock(&shared)?;
        let reader = handle.as_mut().ok_or_else(closed)?;
        let features = reader.sheet_features(&name).map_err(failure)?;
        let catalog = reader.style_catalog().map_err(failure)?;
        sheet_out(Some(&features), catalog)
    })
}

/// Replace the features of a sheet of a new or loaded workbook.
#[pyfunction]
pub(crate) fn sheet_features_write(
    py: Python<'_>,
    sheet: &NativeSheet,
    worksheet: Vec<u8>,
    tables: Vec<Vec<u8>>,
    comments: Vec<CommentTuple>,
) -> PyResult<()> {
    let storage = Arc::clone(&sheet.storage);
    py.detach(move || {
        let refs = tables.iter().map(Vec::as_slice).collect::<Vec<_>>();
        let mut features =
            feature_xml::sheet_features_from_xml(&worksheet, &refs).map_err(failure)?;
        features.comments.extend(native_comments(comments)?);
        let mut storage = lock(&storage)?;
        match &mut *storage {
            SheetStorage::Standalone(sheet) => {
                retain_unexposed_sheet_features(&mut features, sheet.features());
                sheet.edit().set_features(Some(features)).map_err(failure)
            }
            SheetStorage::Bank { book, id } => {
                let mut book = lock(book)?;
                retain_unexposed_sheet_features(
                    &mut features,
                    book.sheet(*id).map_err(failure)?.features(),
                );
                book.sheet_mut(*id)
                    .map_err(failure)?
                    .set_features(Some(features))
                    .map_err(failure)
            }
            SheetStorage::Loaded { book, id } => {
                let mut handle = lock(book)?;
                let book = handle.as_mut().ok_or_else(closed)?;
                retain_unexposed_sheet_features(
                    &mut features,
                    Some(book.sheet_features(*id).map_err(failure)?),
                );
                book.set_sheet_features(*id, features).map_err(failure)
            }
        }
    })
}

fn retain_unexposed_sheet_features(features: &mut SheetFeatures, current: Option<&SheetFeatures>) {
    if let Some(current) = current {
        features.chartsheet.clone_from(&current.chartsheet);
        features
            .chartsheet_parts
            .clone_from(&current.chartsheet_parts);
        features
            .printer_settings
            .clone_from(&current.printer_settings);
        features.images.clone_from(&current.images);
        features.charts.clone_from(&current.charts);
        features.shapes.clone_from(&current.shapes);
        features.pivots.clone_from(&current.pivots);
    }
}

type MarkerInput = (u32, u32, i32, i32);
#[derive(FromPyObject)]
pub(crate) enum ImageInput {
    #[pyo3(transparent)]
    New((Vec<u8>, String, AnchorInput, ClientDataInput)),
    #[pyo3(transparent)]
    Loaded(
        (
            Vec<u8>,
            String,
            AnchorInput,
            ClientDataInput,
            crate::images::NativeImage,
        ),
    ),
}
pub(crate) type ChartInput = (Vec<u8>, AnchorInput, ClientDataInput);

pub(crate) fn native_images(images: Vec<ImageInput>) -> crabxl::Result<Vec<crabxl::Image>> {
    images
        .into_iter()
        .map(|input| {
            let (data, format, anchor, client_data, prototype) = match input {
                ImageInput::New((data, format, anchor, client_data)) => {
                    (data, format, anchor, client_data, None)
                }
                ImageInput::Loaded((data, format, anchor, client_data, prototype)) => {
                    (data, format, anchor, client_data, Some(prototype.image))
                }
            };
            let mut image = crabxl::Image::new(
                data,
                crabxl::ImageFormat::from_content_type(&format)?,
                anchor.into_native()?,
            )?;
            if let Some(original) = prototype {
                image.name = original.name;
                image.description = original.description;
                image.properties = original.properties;
                image.drawing_parts = original.drawing_parts;
                image.order = original.order;
                image.client_data = original.client_data;
            }
            if let Some(element) = image.client_data.as_mut() {
                for (name, value) in [
                    ("fLocksWithSheet", client_data.0),
                    ("fPrintsWithSheet", client_data.1),
                ] {
                    element.attributes.retain(|(key, _)| key.as_ref() != name);
                    if let Some(value) = value {
                        element.set_attribute(name, if value { "1" } else { "0" });
                    }
                }
            } else {
                image.client_data = client_data_xml(client_data);
            }
            Ok(image)
        })
        .collect()
}

pub(crate) fn native_charts(charts: Vec<ChartInput>) -> crabxl::Result<Vec<crabxl::Chart>> {
    charts
        .into_iter()
        .map(|(xml, anchor, client_data)| {
            let mut chart = feature_xml::chart_from_xml(&xml, anchor.into_native()?)?;
            chart.client_data = client_data_xml(client_data);
            Ok(chart)
        })
        .collect()
}

type ClientDataInput = (Option<bool>, Option<bool>);

fn client_data_xml((locks, prints): ClientDataInput) -> Option<crabxl::drawing::XmlElement> {
    if locks.is_none() && prints.is_none() {
        return None;
    }
    let mut element = crabxl::drawing::XmlElement::new("xdr:clientData");
    element.set_attribute(
        "xmlns:xdr",
        "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    );
    for (name, value) in [("fLocksWithSheet", locks), ("fPrintsWithSheet", prints)] {
        if let Some(value) = value {
            element.set_attribute(name, if value { "1" } else { "0" });
        }
    }
    Some(element)
}

#[derive(FromPyObject)]
pub(crate) enum AnchorInput {
    #[pyo3(transparent)]
    OneCell((MarkerInput, (i64, i64))),
    #[pyo3(transparent)]
    TwoCell((MarkerInput, MarkerInput, Option<String>)),
    #[pyo3(transparent)]
    Absolute(((i64, i64), (i64, i64))),
}

impl AnchorInput {
    fn into_native(self) -> crabxl::Result<crabxl::drawing::DrawingAnchor> {
        use crabxl::drawing::{DrawingAnchor, DrawingExtent, DrawingMarker};
        let marker = |(row, col, row_off, col_off)| DrawingMarker {
            row,
            col,
            row_off,
            col_off,
        };
        Ok(match self {
            Self::OneCell((from, (cx, cy))) => DrawingAnchor::OneCell {
                from: marker(from),
                extent: DrawingExtent { cx, cy },
            },
            Self::TwoCell((from, to, edit_as)) => DrawingAnchor::TwoCell {
                from: marker(from),
                to: marker(to),
                edit_as: edit_as.as_deref().map(str::parse).transpose()?,
            },
            Self::Absolute(((x, y), (cx, cy))) => DrawingAnchor::Absolute {
                x,
                y,
                extent: DrawingExtent { cx, cy },
            },
        })
    }
}

fn replace_drawing_suffix<T>(
    current: &mut Option<Vec<T>>,
    base: Option<usize>,
    mut added: Vec<T>,
    order: impl Fn(&mut T) -> &mut usize,
) -> PyResult<usize> {
    let current = current.get_or_insert_with(Vec::new);
    let base = base.unwrap_or(current.len());
    if base > current.len() {
        return Err(PyValueError::new_err("Drawing source changed"));
    }
    current.truncate(base);
    let last_order = current
        .iter_mut()
        .map(|item| *order(item))
        .max()
        .unwrap_or(0);
    for (index, item) in added.iter_mut().enumerate() {
        *order(item) = last_order.saturating_add(index + 1);
    }
    current.append(&mut added);
    Ok(base)
}

fn update_sheet_features(
    storage: &Mutex<SheetStorage>,
    prepare: impl FnOnce(&mut LoadedWorkbook<streaming::SharedFile>, SheetId) -> crabxl::Result<()>,
    update: impl FnOnce(&mut SheetFeatures) -> PyResult<usize>,
) -> PyResult<usize> {
    let mut storage = lock(storage)?;
    match &mut *storage {
        SheetStorage::Standalone(sheet) => {
            let mut features = sheet.features().cloned().unwrap_or_default();
            let base = update(&mut features)?;
            sheet.edit().set_features(Some(features)).map_err(failure)?;
            Ok(base)
        }
        SheetStorage::Bank { book, id } => {
            let mut book = lock(book)?;
            let mut features = book
                .sheet(*id)
                .map_err(failure)?
                .features()
                .cloned()
                .unwrap_or_default();
            let base = update(&mut features)?;
            book.sheet_mut(*id)
                .map_err(failure)?
                .set_features(Some(features))
                .map_err(failure)?;
            Ok(base)
        }
        SheetStorage::Loaded { book, id } => {
            let mut handle = lock(book)?;
            let book = handle.as_mut().ok_or_else(closed)?;
            prepare(book, *id).map_err(failure)?;
            let mut features = book.sheet_features(*id).map_err(failure)?.clone();
            let base = update(&mut features)?;
            book.set_sheet_features(*id, features).map_err(failure)?;
            Ok(base)
        }
    }
}

#[pyfunction]
pub(crate) fn sheet_images_write(
    py: Python<'_>,
    sheet: &NativeSheet,
    base: Option<usize>,
    images: Vec<ImageInput>,
) -> PyResult<usize> {
    let storage = Arc::clone(&sheet.storage);
    py.detach(move || {
        let images = native_images(images).map_err(failure)?;
        update_sheet_features(
            &storage,
            |book, id| book.sheet_images(id).map(|_| ()),
            |features| {
                replace_drawing_suffix(&mut features.images, base, images, |image| &mut image.order)
            },
        )
    })
}

#[pyfunction]
pub(crate) fn sheet_charts_write(
    py: Python<'_>,
    sheet: &NativeSheet,
    base: Option<usize>,
    charts: Vec<ChartInput>,
) -> PyResult<usize> {
    let storage = Arc::clone(&sheet.storage);
    py.detach(move || {
        let charts = native_charts(charts).map_err(failure)?;
        update_sheet_features(
            &storage,
            |book, id| book.sheet_charts(id).map(|_| ()),
            |features| {
                replace_drawing_suffix(&mut features.charts, base, charts, |chart| &mut chart.order)
            },
        )
    })
}

/// Register a differential style (`<dxf>` XML) and return its `dxfId`.
#[pyfunction]
pub(crate) fn sheet_register_dxf(
    py: Python<'_>,
    sheet: &NativeSheet,
    dxf: Vec<u8>,
) -> PyResult<u32> {
    let storage = Arc::clone(&sheet.storage);
    py.detach(move || {
        let style = feature_xml::differential_style_from_xml(&dxf).map_err(failure)?;
        let storage = lock(&storage)?;
        match &*storage {
            SheetStorage::Bank { book, .. } => lock(book)?
                .register_differential_style(style)
                .map_err(failure),
            SheetStorage::Loaded { book, .. } => lock(book)?
                .as_mut()
                .ok_or_else(closed)?
                .register_differential_style(style)
                .map_err(failure),
            SheetStorage::Standalone(_) => Err(PyNotImplementedError::new_err(
                "Conditional-format styles need a sheet owned by a workbook",
            )),
        }
    })
}

fn workbook_out(features: &WorkbookFeatures) -> PyResult<WorkbookOut> {
    let xml = feature_xml::workbook_features_to_xml(&WorkbookFeatures {
        defined_names: features.defined_names.clone(),
        protection: features.protection.clone(),
        calculation: features.calculation.clone(),
        views: features.views.clone(),
        workbook_properties: features.workbook_properties.clone(),
        properties: features.properties.clone(),
        ..Default::default()
    })
    .map_err(failure)?;
    Ok((xml.workbook, xml.core, xml.app, xml.custom, None))
}

/// Workbook features of a new workbook, a loaded workbook or a read-only reader.
#[pyfunction]
pub(crate) fn workbook_features_read(
    py: Python<'_>,
    owner: &Bound<'_, PyAny>,
) -> PyResult<Option<WorkbookOut>> {
    enum Source {
        Book(Arc<Mutex<Workbook>>),
        Writer(Arc<Mutex<streaming::WriteState>>),
        Loaded(SharedLoaded),
        Reader(Arc<Mutex<Option<WorkbookReader<streaming::SharedFile>>>>),
    }
    let source = if let Ok(book) = owner.cast::<NativeBook>() {
        Source::Book(Arc::clone(&book.borrow().book))
    } else if let Ok(reader) = owner.cast::<NativeReader>() {
        let reader = reader.borrow();
        match &reader.loaded {
            Some(loaded) => Source::Loaded(Arc::clone(loaded)),
            None => Source::Reader(Arc::clone(&reader.reader)),
        }
    } else if let Ok(writer) = owner.cast::<streaming::NativeWriteBook>() {
        Source::Writer(Arc::clone(&writer.borrow().state))
    } else {
        return Err(PyValueError::new_err("Unknown workbook owner"));
    };
    py.detach(move || {
        let features = match source {
            Source::Book(book) => lock(&book)?.features().cloned(),
            Source::Writer(state) => lock(&state)?
                .writer
                .as_ref()
                .ok_or_else(closed)?
                .workbook_features()
                .cloned(),
            Source::Loaded(loaded) => Some(
                lock(&loaded)?
                    .as_mut()
                    .ok_or_else(closed)?
                    .workbook_features()
                    .map_err(failure)?
                    .clone(),
            ),
            Source::Reader(reader) => Some(
                lock(&reader)?
                    .as_mut()
                    .ok_or_else(closed)?
                    .workbook_features()
                    .map_err(failure)?,
            ),
        };
        features.as_ref().map(workbook_out).transpose()
    })
}

/// Replace the workbook features of a new workbook.
#[pyfunction]
#[pyo3(signature = (owner, workbook, core=None, app=None, custom=None))]
pub(crate) fn workbook_features_write(
    py: Python<'_>,
    owner: &Bound<'_, PyAny>,
    workbook: Vec<u8>,
    core: Option<Vec<u8>>,
    app: Option<Vec<u8>>,
    custom: Option<Vec<u8>>,
) -> PyResult<()> {
    enum Target {
        Book(Arc<Mutex<Workbook>>),
        Writer(Arc<Mutex<streaming::WriteState>>),
        Loaded(SharedLoaded),
    }
    let target = if let Ok(book) = owner.cast::<NativeBook>() {
        Target::Book(Arc::clone(&book.borrow().book))
    } else if let Ok(reader) = owner.cast::<NativeReader>() {
        match &reader.borrow().loaded {
            Some(loaded) => Target::Loaded(Arc::clone(loaded)),
            None => return Err(pending_integration("Setting workbook features")),
        }
    } else if let Ok(writer) = owner.cast::<streaming::NativeWriteBook>() {
        Target::Writer(Arc::clone(&writer.borrow().state))
    } else {
        return Err(PyValueError::new_err("Unknown workbook owner"));
    };
    py.detach(move || {
        let mut features = feature_xml::workbook_features_from_xml(
            &workbook,
            core.as_deref(),
            app.as_deref(),
            custom.as_deref(),
        )
        .map_err(failure)?;
        match target {
            Target::Book(book) => {
                lock(&book)?.set_features(Some(features));
                Ok(())
            }
            Target::Writer(state) => {
                let mut state = lock(&state)?;
                let writer = state.writer.as_mut().ok_or_else(closed)?;
                if let Some(current) = writer.workbook_features() {
                    features.format = current.format;
                    features.macros.clone_from(&current.macros);
                    features.external_links.clone_from(&current.external_links);
                    features.metadata.clone_from(&current.metadata);
                }
                writer.set_workbook_features(Some(features));
                Ok(())
            }
            Target::Loaded(loaded) => {
                let mut handle = lock(&loaded)?;
                let loaded = handle.as_mut().ok_or_else(closed)?;
                let current = loaded.workbook_features().map_err(failure)?;
                features.format = current.format;
                features.macros.clone_from(&current.macros);
                features.external_links.clone_from(&current.external_links);
                features.metadata.clone_from(&current.metadata);
                loaded.set_workbook_features(features).map_err(failure)
            }
        }
    })
}

/// Give a new workbook openpyxl's default document properties without
/// creating the Python property classes. Existing properties are kept.
#[pyfunction]
pub(crate) fn workbook_default_properties(book: &NativeBook, now_iso: &str) -> PyResult<()> {
    let mut book = lock(&book.book)?;
    let mut features = book.features().cloned().unwrap_or_default();
    if features.properties == Default::default() {
        features.properties = crabxl::features::DocumentProperties::with_openpyxl_defaults(now_iso);
        book.set_features(Some(features));
    }
    Ok(())
}

pub(crate) fn default_calculation() -> crabxl::XmlElement {
    let mut value = crabxl::XmlElement::new("calcPr");
    value.set_attribute(
        "xmlns",
        "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    );
    value.set_attribute("calcId", "124519");
    value.set_attribute("fullCalcOnLoad", "1");
    value
}

#[pyfunction]
pub(crate) fn normalized_active_view(index: i64, states: Vec<String>) -> PyResult<Option<i64>> {
    let states: Vec<crabxl::SheetVisibility> = states
        .iter()
        .map(|state| crate::values::visibility(state))
        .collect::<PyResult<_>>()?;
    crabxl::normalize_active_view(index, states.len(), |index| states[index])
        .map(|selection| selection.serialized_index)
        .map_err(failure)
}
