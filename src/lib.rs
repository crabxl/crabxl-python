//! Python module registration; canonical models remain in crabxl.
mod dimensions;
mod editor;
mod functions;
mod imports;
mod reader;
mod resources;
mod streaming;
mod style_owners;
mod styles;
mod values;
mod workbook;
mod worksheet;

use editor::NativeEditor;
use functions::*;
use imports::*;
use reader::NativeReader;
use values::*;
use workbook::NativeBook;
use worksheet::{NativeSheet, SheetStorage};

#[pyfunction]
fn default_style_component<'py>(py: Python<'py>, name: &str) -> PyResult<Bound<'py, PyDict>> {
    styles::default_component(py, name)
}

#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<NativeSheet>()?;
    module.add_class::<streaming::NativeReadStream>()?;
    module.add_class::<streaming::NativeWriteBook>()?;
    module.add_class::<NativeBook>()?;
    module.add_class::<NativeReader>()?;
    module.add_class::<resources::NativeResources>()?;
    module.add_class::<NativeEditor>()?;
    module.add_function(wrap_pyfunction!(default_style_component, module)?)?;
    module.add_function(wrap_pyfunction!(styles::make_style_component, module)?)?;
    module.add_function(wrap_pyfunction!(save_models, module)?)?;
    module.add_function(wrap_pyfunction!(resolve_model_budget, module)?)?;
    module.add_function(wrap_pyfunction!(cell_address, module)?)?;
    module.add_function(wrap_pyfunction!(translate_formula, module)?)?;
    module.add_function(wrap_pyfunction!(tokenize_formula, module)?)?;
    module.add_function(wrap_pyfunction!(classify_formula_operand, module)?)?;
    module.add_function(wrap_pyfunction!(formula_position, module)?)?;
    module.add_function(wrap_pyfunction!(translate_axis, module)?)?;
    module.add_function(wrap_pyfunction!(column_index, module)?)?;
    module.add_function(wrap_pyfunction!(column_letters, module)?)?;
    module.add_function(wrap_pyfunction!(finite_range, module)?)?;
    Ok(())
}
