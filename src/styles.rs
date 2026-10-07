//! Conversion of public style values into canonical workbook components.
use crate::failure;
use crabxl::*;
use pyo3::{exceptions::PyValueError, prelude::*, types::PyDict};

fn field<'py, T: for<'a> FromPyObject<'a, 'py>>(
    value: &Bound<'py, PyDict>,
    name: &str,
) -> PyResult<Option<T>>
where
    for<'a> <T as FromPyObject<'a, 'py>>::Error: Into<PyErr>,
{
    value
        .get_item(name)?
        .filter(|v| !v.is_none())
        .map(|v| v.extract().map_err(Into::into))
        .transpose()
}
fn dictionary<'py>(value: &Bound<'py, PyDict>, name: &str) -> PyResult<Option<Bound<'py, PyDict>>> {
    value
        .get_item(name)?
        .filter(|v| !v.is_none())
        .map(|v| v.cast_into::<PyDict>().map_err(Into::into))
        .transpose()
}
fn color(value: &Bound<'_, PyDict>) -> PyResult<Color> {
    let kind: String = field(value, "type")?.unwrap_or_else(|| "rgb".into());
    let kind = match kind.as_str() {
        "rgb" => ArgbLiteral::parse(
            &field::<String>(value, "value")?.unwrap_or_else(|| "00000000".into()),
        )
        .map_err(failure)?
        .into_kind(),
        "theme" => ColorKind::Theme(field::<i64>(value, "value")?.unwrap_or(0).into()),
        "indexed" => ColorKind::Indexed(field::<i64>(value, "value")?.unwrap_or(0).into()),
        "auto" => ColorKind::Auto(field(value, "value")?.unwrap_or(false)),
        "unspecified" => ColorKind::Unspecified,
        _ => return Err(PyValueError::new_err("Invalid color identity")),
    };
    Ok(Color {
        kind,
        tint: field(value, "tint")?,
    })
}
fn optional_color(value: &Bound<'_, PyDict>, name: &str) -> PyResult<Option<Color>> {
    dictionary(value, name)?.as_ref().map(color).transpose()
}

pub(crate) fn decode(name: &str, value: &Bound<'_, PyDict>) -> PyResult<StyleComponent> {
    let result = match name {
        "font" => {
            let font = Font {
                name: field(value, "name")?.map(String::into),
                size: field(value, "sz")?,
                bold: field(value, "b")?,
                italic: field(value, "i")?,
                strike: field(value, "strike")?,
                outline: field(value, "outline")?,
                shadow: field(value, "shadow")?,
                condense: field(value, "condense")?,
                extend: field(value, "extend")?,
                family: field(value, "family")?,
                charset: field::<i64>(value, "charset")?.map(Into::into),
                color: optional_color(value, "color")?,
                underline: field::<String>(value, "u")?
                    .map(|v| match v.as_str() {
                        "none" => Ok(Underline::None),
                        "single" => Ok(Underline::Single),
                        "double" => Ok(Underline::Double),
                        "singleAccounting" => Ok(Underline::SingleAccounting),
                        "doubleAccounting" => Ok(Underline::DoubleAccounting),
                        _ => Err(PyValueError::new_err("Invalid underline")),
                    })
                    .transpose()?,
                vertical: field::<String>(value, "vertAlign")?
                    .map(|v| match v.as_str() {
                        "baseline" => Ok(TextVerticalAlignment::Baseline),
                        "superscript" => Ok(TextVerticalAlignment::Superscript),
                        "subscript" => Ok(TextVerticalAlignment::Subscript),
                        _ => Err(PyValueError::new_err("Invalid font vertical alignment")),
                    })
                    .transpose()?,
                scheme: field::<String>(value, "scheme")?
                    .map(|v| match v.as_str() {
                        "none" => Ok(FontScheme::None),
                        "major" => Ok(FontScheme::Major),
                        "minor" => Ok(FontScheme::Minor),
                        _ => Err(PyValueError::new_err("Invalid font scheme")),
                    })
                    .transpose()?,
            };
            StyleComponent::Font(Box::new(font))
        }
        "alignment" => StyleComponent::Alignment(Some(Box::new(Alignment {
            rotation: field(value, "textRotation")?,
            wrap_text: field(value, "wrapText")?,
            shrink_to_fit: field(value, "shrinkToFit")?,
            indent: field(value, "indent")?,
            relative_indent: field(value, "relativeIndent")?,
            justify_last_line: field(value, "justifyLastLine")?,
            reading_order: field(value, "readingOrder")?,
            merge_cell: field(value, "mergeCell")?,
            horizontal: field::<String>(value, "horizontal")?
                .map(|v| HorizontalAlignment::parse(&v).map_err(failure))
                .transpose()?,
            vertical: field::<String>(value, "vertical")?
                .map(|v| VerticalAlignment::parse(&v).map_err(failure))
                .transpose()?,
        }))),
        "protection" => StyleComponent::Protection(Some(Protection {
            locked: field(value, "locked")?,
            hidden: field(value, "hidden")?,
        })),
        "border" => {
            let mut border = Border {
                sides: Default::default(),
                diagonal_up: field(value, "diagonalUp")?,
                diagonal_down: field(value, "diagonalDown")?,
                outline: field(value, "outline")?,
            };
            for (index, name) in [
                "left",
                "right",
                "top",
                "bottom",
                "diagonal",
                "vertical",
                "horizontal",
                "start",
                "end",
            ]
            .iter()
            .enumerate()
            {
                border.sides[index] = dictionary(value, name)?
                    .map(|side| -> PyResult<BorderSide> {
                        Ok(BorderSide {
                            line: field::<String>(&side, "style")?
                                .map(|v| BorderLine::parse(&v).map_err(failure))
                                .transpose()?,
                            color: optional_color(&side, "color")?,
                        })
                    })
                    .transpose()?;
            }
            StyleComponent::Border(Box::new(border))
        }
        "fill" => {
            let fill = if value.contains("patternType")? {
                Fill::Pattern(PatternFill {
                    pattern: field::<String>(value, "patternType")?
                        .map(|v| FillPattern::parse(&v).map_err(failure))
                        .transpose()?,
                    foreground: optional_color(value, "fgColor")?,
                    background: optional_color(value, "bgColor")?,
                })
            } else {
                let mut stops = Vec::new();
                if let Some(items) = value.get_item("stop")? {
                    for item in items.try_iter()? {
                        let stop = item?.cast_into::<PyDict>()?;
                        let color_value = dictionary(&stop, "color")?
                            .ok_or_else(|| PyValueError::new_err("Missing gradient color"))?;
                        stops.push(GradientStop {
                            position: field(&stop, "position")?.unwrap_or(0.0),
                            color: color(&color_value)?,
                        });
                    }
                }
                Fill::Gradient(GradientFill {
                    kind: field::<String>(value, "type")?
                        .map(|v| GradientKind::parse(&v).map_err(failure))
                        .transpose()?,
                    degree: field(value, "degree")?,
                    edges: [
                        field(value, "left")?,
                        field(value, "right")?,
                        field(value, "top")?,
                        field(value, "bottom")?,
                    ],
                    stops,
                })
            };
            StyleComponent::Fill(Box::new(fill))
        }
        _ => return Err(PyValueError::new_err("Unknown style component")),
    };
    Ok(result)
}

fn encode_color<'py>(py: Python<'py>, color: &Color) -> PyResult<Bound<'py, PyDict>> {
    let result = PyDict::new(py);
    match &color.kind {
        ColorKind::Argb(value) => {
            result.set_item("type", "rgb")?;
            result.set_item("value", format!("{value:08X}"))?;
        }
        ColorKind::ArgbLiteral(value) => {
            result.set_item("type", "rgb")?;
            result.set_item("value", value.to_string())?;
        }
        ColorKind::Theme(value) => {
            result.set_item("type", "theme")?;
            result.set_item(
                "value",
                value.to_string().parse::<i64>().map_err(|_| {
                    PyValueError::new_err("Theme identity exceeds Python adapter integer range")
                })?,
            )?;
        }
        ColorKind::Indexed(value) => {
            result.set_item("type", "indexed")?;
            result.set_item(
                "value",
                value.to_string().parse::<i64>().map_err(|_| {
                    PyValueError::new_err("Indexed identity exceeds Python adapter integer range")
                })?,
            )?;
        }
        ColorKind::Auto(value) => {
            result.set_item("type", "auto")?;
            result.set_item("value", value)?;
        }
        ColorKind::Unspecified => {
            result.set_item("type", "unspecified")?;
            result.set_item("value", py.None())?;
        }
    }
    result.set_item("tint", color.tint.unwrap_or(0.0))?;
    Ok(result)
}
fn put_color(
    py: Python<'_>,
    result: &Bound<'_, PyDict>,
    name: &str,
    color: Option<&Color>,
) -> PyResult<()> {
    match color {
        Some(color) => result.set_item(name, encode_color(py, color)?),
        None => result.set_item(name, py.None()),
    }
}
pub(crate) fn encode<'py>(
    py: Python<'py>,
    name: &str,
    view: StyleView<'_>,
) -> PyResult<Bound<'py, PyDict>> {
    let result = PyDict::new(py);
    match name {
        "font" => {
            let value = view.font;
            result.set_item("name", value.name.as_deref())?;
            result.set_item("sz", value.size)?;
            result.set_item("b", value.bold)?;
            result.set_item("i", value.italic)?;
            result.set_item("strike", value.strike)?;
            result.set_item("outline", value.outline)?;
            result.set_item("shadow", value.shadow)?;
            result.set_item("condense", value.condense)?;
            result.set_item("extend", value.extend)?;
            result.set_item("family", value.family)?;
            result.set_item(
                "charset",
                value
                    .charset
                    .as_ref()
                    .map(ToString::to_string)
                    .map(|v| v.parse::<i64>())
                    .transpose()
                    .map_err(|_| PyValueError::new_err("Charset exceeds adapter integer range"))?,
            )?;
            result.set_item(
                "u",
                value.underline.map(|v| match v {
                    Underline::None => "none",
                    Underline::Single => "single",
                    Underline::Double => "double",
                    Underline::SingleAccounting => "singleAccounting",
                    Underline::DoubleAccounting => "doubleAccounting",
                }),
            )?;
            result.set_item(
                "vertAlign",
                value.vertical.map(|v| match v {
                    TextVerticalAlignment::Baseline => "baseline",
                    TextVerticalAlignment::Superscript => "superscript",
                    TextVerticalAlignment::Subscript => "subscript",
                }),
            )?;
            result.set_item(
                "scheme",
                value.scheme.map(|v| match v {
                    FontScheme::None => "none",
                    FontScheme::Major => "major",
                    FontScheme::Minor => "minor",
                }),
            )?;
            put_color(py, &result, "color", value.color.as_ref())?;
        }
        "alignment" => {
            let default = Alignment::default();
            let value = view.alignment.unwrap_or(&default);
            result.set_item("textRotation", value.rotation)?;
            result.set_item("wrapText", value.wrap_text)?;
            result.set_item("shrinkToFit", value.shrink_to_fit)?;
            result.set_item("indent", value.indent)?;
            result.set_item("relativeIndent", value.relative_indent)?;
            result.set_item("justifyLastLine", value.justify_last_line)?;
            result.set_item("readingOrder", value.reading_order)?;
            result.set_item("mergeCell", value.merge_cell)?;
            result.set_item(
                "horizontal",
                value.horizontal.map(HorizontalAlignment::as_str),
            )?;
            result.set_item("vertical", value.vertical.map(VerticalAlignment::as_str))?;
        }
        "protection" => {
            let value = view.protection.copied().unwrap_or(Protection {
                locked: Some(true),
                hidden: Some(false),
            });
            result.set_item("locked", value.locked)?;
            result.set_item("hidden", value.hidden)?;
        }
        "border" => {
            let value = view.border;
            for (index, name) in [
                "left",
                "right",
                "top",
                "bottom",
                "diagonal",
                "vertical",
                "horizontal",
                "start",
                "end",
            ]
            .iter()
            .enumerate()
            {
                if let Some(side) = &value.sides[index] {
                    let item = PyDict::new(py);
                    item.set_item("style", side.line.map(BorderLine::as_str))?;
                    put_color(py, &item, "color", side.color.as_ref())?;
                    result.set_item(name, item)?;
                } else {
                    result.set_item(name, py.None())?;
                }
            }
            result.set_item("diagonalUp", value.diagonal_up)?;
            result.set_item("diagonalDown", value.diagonal_down)?;
            result.set_item("outline", value.outline)?;
        }
        "fill" => match view.fill {
            Fill::Pattern(value) => {
                result.set_item("patternType", value.pattern.map(FillPattern::as_str))?;
                put_color(py, &result, "fgColor", value.foreground.as_ref())?;
                put_color(py, &result, "bgColor", value.background.as_ref())?;
            }
            Fill::Gradient(value) => {
                result.set_item("type", value.kind.map(GradientKind::as_str))?;
                result.set_item("degree", value.degree)?;
                for (name, edge) in ["left", "right", "top", "bottom"].iter().zip(value.edges) {
                    result.set_item(name, edge)?;
                }
                let stops = pyo3::types::PyList::empty(py);
                for stop in &value.stops {
                    let item = PyDict::new(py);
                    item.set_item("position", stop.position)?;
                    item.set_item("color", encode_color(py, &stop.color)?)?;
                    stops.append(item)?;
                }
                result.set_item("stop", stops)?;
            }
        },
        _ => return Err(PyValueError::new_err("Unknown style component")),
    }
    Ok(result)
}

pub(crate) fn default_component<'py>(py: Python<'py>, name: &str) -> PyResult<Bound<'py, PyDict>> {
    let style = CellStyle::default();
    let format = CellFormat::default();
    encode(
        py,
        name,
        StyleView {
            format: &format,
            number_format: Some(&style.number_format),
            font: &style.font,
            fill: &style.fill,
            border: &style.borders,
            alignment: Some(&style.alignment),
            protection: Some(&style.protection),
        },
    )
}

#[pyclass]
pub(crate) struct NativeStyleComponent {
    pub(crate) component: StyleComponent,
}
#[pymethods]
impl NativeStyleComponent {
    #[getter]
    pub(crate) fn retained_bytes(&self) -> usize {
        std::mem::size_of::<Self>()
            + match &self.component {
                StyleComponent::Font(v) => v.heap_bytes(),
                StyleComponent::Fill(v) => v.heap_bytes(),
                StyleComponent::Border(v) => v.heap_bytes(),
                StyleComponent::Alignment(v) => {
                    v.as_ref().map_or(0, |_| std::mem::size_of::<Alignment>())
                }
                StyleComponent::Protection(_) => 0,
            }
    }
}
#[pyfunction]
pub(crate) fn make_style_component(
    name: &str,
    value: &Bound<'_, PyDict>,
) -> PyResult<NativeStyleComponent> {
    let component = decode(name, value)?;
    match &component {
        StyleComponent::Font(v) => v.validate().map_err(failure)?,
        StyleComponent::Fill(v) => v.validate().map_err(failure)?,
        StyleComponent::Border(v) => v.validate().map_err(failure)?,
        StyleComponent::Alignment(Some(v)) => v.validate().map_err(failure)?,
        _ => {}
    }
    Ok(NativeStyleComponent { component })
}
