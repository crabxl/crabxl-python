//! Rich display runs and pronunciation metadata adapt canonical core records.
use crate::{failure, styles};
use crabxl::{PhoneticProperties, PhoneticRun, RichText, RichTextRun, StyleComponent};
use pyo3::{
    exceptions::PyValueError,
    prelude::*,
    types::{PyBytes, PyDict, PyList},
};

#[pyfunction]
pub(crate) fn rich_text_from_xml<'py>(py: Python<'py>, xml: &[u8]) -> PyResult<Bound<'py, PyDict>> {
    let value =
        crabxl::read_rich_text(std::io::Cursor::new(xml), crabxl::ResourceLimits::default())
            .map_err(failure)?;
    encode(py, &value)
}

#[pyfunction]
pub(crate) fn rich_text_to_xml<'py>(
    py: Python<'py>,
    fields: &Bound<'_, PyDict>,
) -> PyResult<Bound<'py, PyBytes>> {
    let value = decode(fields)?;
    let mut output = Vec::new();
    crabxl::write_rich_text(&mut output, &value, crabxl::ResourceLimits::default())
        .map_err(failure)?;
    Ok(PyBytes::new(py, &output))
}

pub(crate) fn decode(value: &Bound<'_, PyDict>) -> PyResult<RichText> {
    let runs = value
        .get_item("runs")?
        .ok_or_else(|| PyValueError::new_err("Missing rich text runs"))?;
    let mut result = RichText::default();
    for item in runs.try_iter()? {
        let (text, font): (String, Option<Bound<'_, PyAny>>) = item?.extract()?;
        let font = font
            .map(|fields| -> PyResult<_> {
                if let Ok(value) = fields.extract::<PyRef<'_, styles::NativeStyleComponent>>() {
                    let StyleComponent::Font(font) = &value.component else {
                        return Err(PyValueError::new_err("Invalid run font component"));
                    };
                    return Ok(font.clone());
                }
                let StyleComponent::Font(font) = styles::decode("font", fields.cast::<PyDict>()?)?
                else {
                    return Err(PyValueError::new_err("Invalid run font"));
                };
                font.validate().map_err(failure)?;
                Ok(font)
            })
            .transpose()?;
        result.runs.push(RichTextRun {
            text: text.into_boxed_str(),
            font,
        });
    }
    if let Some(runs) = value.get_item("phonetic_runs")? {
        for item in runs.try_iter()? {
            let (start, end, text): (u32, u32, String) = item?.extract()?;
            if start > end {
                return Err(PyValueError::new_err("Reversed phonetic range"));
            }
            result.phonetic_runs.push(PhoneticRun {
                start,
                end,
                text: text.into_boxed_str(),
            });
        }
    }
    if let Some(fields) = value
        .get_item("phonetic_properties")?
        .filter(|v| !v.is_none())
    {
        let (font_id, kind, alignment): (u32, Option<String>, Option<String>) = fields.extract()?;
        result.phonetic_properties = Some(Box::new(PhoneticProperties {
            font_id,
            kind: kind.map(String::into_boxed_str),
            alignment: alignment.map(String::into_boxed_str),
        }));
    }
    Ok(result)
}

pub(crate) fn encode<'py>(py: Python<'py>, value: &RichText) -> PyResult<Bound<'py, PyDict>> {
    let result = PyDict::new(py);
    let runs = PyList::empty(py);
    for run in &value.runs {
        let font = run
            .font
            .as_deref()
            .map(|font| styles::encode_font(py, font))
            .transpose()?;
        runs.append((run.text.as_ref(), font))?;
    }
    result.set_item("runs", runs)?;
    let pronunciation = PyList::empty(py);
    for run in &value.phonetic_runs {
        pronunciation.append((run.start, run.end, run.text.as_ref()))?;
    }
    result.set_item("phonetic_runs", pronunciation)?;
    result.set_item(
        "phonetic_properties",
        value
            .phonetic_properties
            .as_deref()
            .map(|v| (v.font_id, v.kind.as_deref(), v.alignment.as_deref())),
    )?;
    Ok(result)
}
