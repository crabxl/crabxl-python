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

pub(crate) type CommentTuple = (u32, u32, String, String, f64, f64, bool);
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
    let xml = feature_xml::sheet_features_to_xml(features).map_err(failure)?;
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
        for (row, column, author, text, width, height, visible) in comments {
            let mut comment = Comment::new(
                CellAddress::new(row, column).map_err(failure)?,
                text,
                author,
            );
            comment.width = width;
            comment.height = height;
            comment.visible = visible;
            features.comments.push(comment);
        }
        let mut storage = lock(&storage)?;
        match &mut *storage {
            SheetStorage::Standalone(sheet) => {
                sheet.edit().set_features(Some(features)).map_err(failure)
            }
            SheetStorage::Bank { book, id } => lock(book)?
                .sheet_mut(*id)
                .map_err(failure)?
                .set_features(Some(features))
                .map_err(failure),
            SheetStorage::Loaded { book, id } => lock(book)?
                .as_mut()
                .ok_or_else(closed)?
                .set_sheet_features(*id, features)
                .map_err(failure),
        }
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
    let xml = feature_xml::workbook_features_to_xml(features).map_err(failure)?;
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
    } else {
        return Err(PyValueError::new_err("Unknown workbook owner"));
    };
    py.detach(move || {
        let features = match source {
            Source::Book(book) => lock(&book)?.features().cloned(),
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
        Loaded(SharedLoaded),
    }
    let target = if let Ok(book) = owner.cast::<NativeBook>() {
        Target::Book(Arc::clone(&book.borrow().book))
    } else if let Ok(reader) = owner.cast::<NativeReader>() {
        match &reader.borrow().loaded {
            Some(loaded) => Target::Loaded(Arc::clone(loaded)),
            None => return Err(pending_integration("Setting workbook features")),
        }
    } else {
        return Err(PyValueError::new_err("Unknown workbook owner"));
    };
    py.detach(move || {
        let features = feature_xml::workbook_features_from_xml(
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
            Target::Loaded(loaded) => lock(&loaded)?
                .as_mut()
                .ok_or_else(closed)?
                .set_workbook_features(features)
                .map_err(failure),
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
