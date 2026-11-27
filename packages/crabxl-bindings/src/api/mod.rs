//! The native layer of the redesigned `crabxl` Python API.
//!
//! These classes are private: the typed public classes in `python/crabxl`
//! wrap them.

pub(crate) mod convert;
pub(crate) mod stream;
pub(crate) mod workbook;

use pyo3::prelude::*;

pub(crate) fn register(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<workbook::ApiWorkbook>()?;
    module.add_class::<stream::ApiReader>()?;
    module.add_class::<stream::ApiRowStream>()?;
    module.add_class::<stream::ApiWriter>()?;
    Ok(())
}
