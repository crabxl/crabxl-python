//! Shared value conversion, errors and handle synchronization.
use crate::*;

pub(crate) type TaggedValue = (String, Py<PyAny>);
pub(crate) type EncodedValue = (&'static str, Py<PyAny>);
pub(crate) type DecodedValues = (Vec<Py<PyAny>>, Option<Vec<u32>>);
pub(crate) type SharedLoaded = Arc<Mutex<Option<LoadedWorkbook<streaming::SharedFile>>>>;
pub(crate) fn failure(error: Error) -> PyErr {
    let mut text = error.to_string();
    let mut source = std::error::Error::source(&error);
    while let Some(cause) = source {
        text.push_str(": ");
        text.push_str(&cause.to_string());
        source = cause.source();
    }
    match error.kind() {
        ErrorKind::Unsupported => PyNotImplementedError::new_err(text),
        ErrorKind::MemoryBudgetExceeded => PyMemoryError::new_err(text),
        ErrorKind::SheetNotFound => PyKeyError::new_err(text),
        ErrorKind::Io => PyOSError::new_err(text),
        ErrorKind::InvalidState => PyRuntimeError::new_err(text),
        ErrorKind::NoVisibleSheet => PyIndexError::new_err(text),
        _ => PyValueError::new_err(text),
    }
}
pub(crate) fn visibility(value: &str) -> PyResult<SheetVisibility> {
    match value {
        "visible" => Ok(SheetVisibility::Visible),
        "hidden" => Ok(SheetVisibility::Hidden),
        "veryHidden" => Ok(SheetVisibility::VeryHidden),
        _ => Err(PyValueError::new_err(
            "Sheet state must be visible, hidden or veryHidden",
        )),
    }
}
pub(crate) fn lock<T>(value: &Mutex<T>) -> PyResult<MutexGuard<'_, T>> {
    value
        .lock()
        .map_err(|_| PyRuntimeError::new_err("Native resource lock was poisoned"))
}
pub(crate) fn closed() -> PyErr {
    PyValueError::new_err("Workbook is closed")
}
pub(crate) fn input_flag(fields: &Bound<'_, PyDict>, name: &str) -> PyResult<Option<FormulaFlag>> {
    let Some(value) = fields.get_item(name)? else {
        return Ok(None);
    };
    if value.is_none() {
        return Ok(None);
    }
    if let Ok(boolean) = value.extract::<bool>() {
        return Ok(Some(boolean.into()));
    }
    Ok(Some(FormulaFlag::from_literal(value.extract::<String>()?)))
}
pub(crate) fn input_text(fields: &Bound<'_, PyDict>, name: &str) -> PyResult<Option<Box<str>>> {
    fields
        .get_item(name)?
        .filter(|value| !value.is_none())
        .map(|value| value.extract::<String>().map(String::into_boxed_str))
        .transpose()
}
pub(crate) fn output_flag(
    fields: &Bound<'_, PyDict>,
    name: &str,
    flag: Option<&FormulaFlag>,
) -> PyResult<()> {
    if let Some(flag) = flag {
        if let Some(source) = flag.source() {
            fields.set_item(name, source)?;
        } else {
            fields.set_item(name, flag.value())?;
        }
    }
    Ok(())
}
pub(crate) fn decode(py: Python<'_>, value: TaggedValue) -> PyResult<CellValue> {
    let (kind, value) = value;
    let value = value.bind(py);
    Ok(match kind.as_str() {
        "empty" => CellValue::Empty,
        "bool" => CellValue::Boolean(value.extract()?),
        "int" => {
            let decimal: String = value.extract()?;
            match decimal.parse::<i64>() {
                Ok(integer) => CellValue::Integer(integer),
                Err(_) => {
                    CellValue::BigInteger(Box::new(ExactInteger::parse(&decimal).map_err(failure)?))
                }
            }
        }
        "float" => {
            let number: f64 = value.extract()?;
            CellValue::Number(number)
        }
        "text" => CellValue::text(value.extract::<String>()?),
        "error" => CellValue::error(value.extract::<String>()?),
        "formula" => CellValue::Formula(Box::new(
            Formula::from_source(value.extract::<String>()?, None, None).map_err(failure)?,
        )),
        "array" | "table" => {
            let fields = value.cast::<PyDict>()?;
            let reference = input_text(fields, "ref")?.map(FormulaRange::from_literal);
            let mut metadata = FormulaMetadata {
                kind: if kind == "array" {
                    FormulaType::Array
                } else {
                    FormulaType::DataTable
                },
                reference,
                ..Default::default()
            };
            let formula = if kind == "array" {
                Formula::from_array_text(input_text(fields, "text")?, None, metadata)
                    .map_err(failure)?
            } else {
                metadata.flags = FormulaFlags {
                    calculate_cell: input_flag(fields, "ca")?,
                    ..Default::default()
                };
                metadata.data_table = Some(Box::new(DataTableOptions {
                    two_dimensions: input_flag(fields, "dt2D")?,
                    row_table: input_flag(fields, "dtr")?,
                    deleted1: input_flag(fields, "del1")?,
                    deleted2: input_flag(fields, "del2")?,
                    input1: input_text(fields, "r1")?,
                    input2: input_text(fields, "r2")?,
                }));
                Formula::with_optional_expression(None, None, metadata).map_err(failure)?
            };
            CellValue::Formula(Box::new(formula))
        }
        "date" => {
            let (year, month, day): (i32, u32, u32) = value.extract()?;
            CellValue::DateTime(Box::new(
                ExcelDateTime::from_ymd(year, month, day).map_err(failure)?,
            ))
        }
        "datetime" => {
            let (y, m, d, h, minute, second, micro): (i32, u32, u32, u32, u32, u32, u32) =
                value.extract()?;
            CellValue::DateTime(Box::new(
                ExcelDateTime::from_ymd_hms_micro(y, m, d, h, minute, second, micro)
                    .map_err(failure)?,
            ))
        }
        "time" => {
            let (hour, minute, second, micro): (u32, u32, u32, u32) = value.extract()?;
            CellValue::DateTime(Box::new(
                ExcelDateTime::from_hms_micro(hour, minute, second, micro).map_err(failure)?,
            ))
        }
        "duration" => {
            let (days, seconds, micro): (i64, u32, u32) = value.extract()?;
            CellValue::DateTime(Box::new(
                ExcelDateTime::from_duration_parts(days, seconds, micro).map_err(failure)?,
            ))
        }
        _ => return Err(PyValueError::new_err("Unknown native value tag")),
    })
}
pub(crate) fn encode(py: Python<'_>, value: &CellValue) -> PyResult<EncodedValue> {
    let (kind, object) = match value {
        CellValue::Empty => ("n", py.None()),
        CellValue::Number(value) => ("n", value.into_py_any(py)?),
        CellValue::Integer(value) => ("n", value.into_py_any(py)?),
        CellValue::BigInteger(value) => ("bigint", value.as_str().into_py_any(py)?),
        CellValue::Boolean(value) => ("b", value.into_py_any(py)?),
        CellValue::Text(value) => ("s", value.as_str().into_py_any(py)?),
        CellValue::Error(value) => ("e", value.as_str().into_py_any(py)?),
        CellValue::Formula(value) => match value.formula_type() {
            FormulaType::Array | FormulaType::DataTable => {
                let metadata = value
                    .metadata()
                    .ok_or_else(|| PyValueError::new_err("Missing structured formula metadata"))?;
                let fields = PyDict::new(py);
                fields.set_item(
                    "ref",
                    metadata
                        .reference
                        .as_ref()
                        .map(|reference| reference.spelling().into_owned()),
                )?;
                if value.formula_type() == FormulaType::Array {
                    fields.set_item("text", value.array_text().as_deref())?;
                    ("array", fields.into_any().unbind())
                } else {
                    output_flag(&fields, "ca", metadata.flags.calculate_cell.as_ref())?;
                    if let Some(table) = &metadata.data_table {
                        for (name, flag) in [
                            ("dt2D", table.two_dimensions.as_ref()),
                            ("dtr", table.row_table.as_ref()),
                            ("del1", table.deleted1.as_ref()),
                            ("del2", table.deleted2.as_ref()),
                        ] {
                            output_flag(&fields, name, flag)?;
                        }
                        fields.set_item("r1", table.input1.as_deref())?;
                        fields.set_item("r2", table.input2.as_deref())?;
                    }
                    ("table", fields.into_any().unbind())
                }
            }
            _ => ("f", format!("={}", value.expression()).into_py_any(py)?),
        },
        CellValue::DateTime(value) => match value.kind() {
            DateKind::Date => (
                "date",
                value
                    .to_date()
                    .map_err(failure)?
                    .to_string()
                    .into_py_any(py)?,
            ),
            DateKind::DateTime => (
                "datetime",
                value
                    .to_datetime()
                    .map_err(failure)?
                    .to_string()
                    .into_py_any(py)?,
            ),
            DateKind::Time => (
                "time",
                value
                    .to_time()
                    .map_err(failure)?
                    .to_string()
                    .into_py_any(py)?,
            ),
            DateKind::Duration => {
                let duration = value.to_duration().map_err(failure)?;
                (
                    "duration",
                    (duration.num_seconds(), duration.subsec_micros()).into_py_any(py)?,
                )
            }
        },
        _ => return Err(PyNotImplementedError::new_err("Unsupported native value")),
    };
    Ok((kind, object))
}

// Scalar rows reach Python without per-cell tagged tuples or Python decode
// calls. Editable structured formulas remain live cell views, identified by
// relative column positions; read-only formulas keep their detached projection.
pub(crate) fn decode_values(
    py: Python<'_>,
    tagged: Vec<EncodedValue>,
    bound_formulas: bool,
) -> PyResult<DecodedValues> {
    let mut values = Vec::with_capacity(tagged.len());
    let mut formulas = None;
    let mut decoder = None;
    for (column, (kind, value)) in tagged.into_iter().enumerate() {
        if bound_formulas && matches!(kind, "array" | "table") {
            formulas.get_or_insert_with(Vec::new).push(column as u32);
            values.push(py.None());
        } else if matches!(
            kind,
            "bigint" | "date" | "datetime" | "time" | "duration" | "array" | "table"
        ) {
            if decoder.is_none() {
                decoder = Some(py.import("crabxl")?.getattr("_decode")?);
            }
            values.push(
                decoder
                    .as_ref()
                    .ok_or_else(closed)?
                    .call1(((kind, value),))?
                    .unbind(),
            );
        } else {
            values.push(value);
        }
    }
    Ok((values, formulas))
}
