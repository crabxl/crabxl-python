//! Explicit picture views retain native drawing properties and dependency graphs.
use crate::*;
use std::io::Read;

type Marker = (u32, u32, i32, i32);
type Anchor = (
    u8,
    Marker,
    Marker,
    (i64, i64),
    (i64, i64),
    Option<String>,
    (Option<bool>, Option<bool>),
);

#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
pub(crate) struct NativeImage {
    pub(crate) image: Box<crabxl::Image>,
}

#[pymethods]
impl NativeImage {
    fn data<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        let length = usize::try_from(self.image.data.len())
            .ok()
            .filter(|length| *length <= isize::MAX as usize)
            .ok_or_else(|| pyo3::exceptions::PyMemoryError::new_err("Image is too large"))?;
        PyBytes::new_with(py, length, |bytes| {
            py.detach(|| self.image.data.reader().read_exact(bytes))
                .map_err(PyErr::from)
        })
    }

    fn anchor(&self) -> Anchor {
        use crabxl::DrawingAnchor;
        let marker =
            |value: &crabxl::DrawingMarker| (value.row, value.col, value.row_off, value.col_off);
        let zero = (0, 0, 0, 0);
        let flags = |name| {
            self.image
                .client_data
                .as_ref()
                .and_then(|element| element.attribute(name))
                .map(|value| !matches!(value, "0" | "false" | "False"))
        };
        let client = (flags("fLocksWithSheet"), flags("fPrintsWithSheet"));
        match &self.image.anchor {
            DrawingAnchor::OneCell { from, extent } => (
                0,
                marker(from),
                zero,
                (extent.cx, extent.cy),
                (0, 0),
                None,
                client,
            ),
            DrawingAnchor::TwoCell { from, to, edit_as } => (
                1,
                marker(from),
                marker(to),
                (0, 0),
                (0, 0),
                edit_as.map(|value| value.as_str().to_owned()),
                client,
            ),
            DrawingAnchor::Absolute { x, y, extent } => (
                2,
                zero,
                zero,
                (extent.cx, extent.cy),
                (*x, *y),
                None,
                client,
            ),
        }
    }

    fn __copy__(&self) -> Self {
        self.clone()
    }
    fn __deepcopy__(&self, _memo: &Bound<'_, PyAny>) -> Self {
        self.clone()
    }
}

#[pyfunction]
pub(crate) fn sheet_images_read(py: Python<'_>, sheet: &NativeSheet) -> PyResult<Vec<NativeImage>> {
    let storage = Arc::clone(&sheet.storage);
    py.detach(move || {
        let storage = lock(&storage)?;
        let images = match &*storage {
            SheetStorage::Standalone(sheet) => sheet
                .features()
                .and_then(|features| features.images.clone())
                .unwrap_or_default(),
            SheetStorage::Bank { book, id } => lock(book)?
                .sheet(*id)
                .map_err(failure)?
                .features()
                .and_then(|features| features.images.clone())
                .unwrap_or_default(),
            SheetStorage::Loaded { book, id } => lock(book)?
                .as_mut()
                .ok_or_else(closed)?
                .sheet_images(*id)
                .map_err(failure)?
                .to_vec(),
        };
        Ok(images
            .into_iter()
            .map(|image| NativeImage {
                image: Box::new(image),
            })
            .collect())
    })
}
