//! Conversions between Python objects and the crabxl API: errors, values,
//! styles and features.

use crabxl::style::{
    Alignment, Border, BorderLine, BorderSide, Color, Fill, Font, Protection, Style,
};
use crabxl::{ErrorKind, ErrorValue, Formula, Number, Temporal, TemporalKind, Value};
use pyo3::IntoPyObjectExt;
use pyo3::exceptions::PyOSError;
use pyo3::prelude::*;
use pyo3::types::{
    PyBool, PyDate, PyDateAccess, PyDateTime, PyDelta, PyDeltaAccess, PyDict, PyFloat, PyInt,
    PyList, PyString, PyTime, PyTimeAccess, PyTuple, PyTzInfoAccess,
};

/// What the failing call was doing, to tell bad files from bad arguments.
#[derive(Clone, Copy, PartialEq, Eq)]
pub(crate) enum Phase {
    Open,
    Edit,
}

/// Raise the CrabXL exception that matches an error.
pub(crate) fn raise(py: Python<'_>, error: crabxl::Error, phase: Phase) -> PyErr {
    let mut text = error.message().to_owned();
    let mut source = std::error::Error::source(&error);
    let mut io_kind = None;
    while let Some(cause) = source {
        text.push_str(": ");
        text.push_str(&cause.to_string());
        io_kind = io_kind.or(cause
            .downcast_ref::<std::io::Error>()
            .map(std::io::Error::kind));
        source = cause.source();
    }
    if error.kind() == ErrorKind::Io {
        return match io_kind {
            Some(kind) => PyErr::from(std::io::Error::new(kind, text)),
            None => PyOSError::new_err(text),
        };
    }
    let class = match error.kind() {
        ErrorKind::Archive | ErrorKind::Xml => "FileFormatError",
        ErrorKind::InvalidData if phase == Phase::Open => "FileFormatError",
        ErrorKind::InvalidData => "InvalidInputError",
        ErrorKind::SheetNotFound | ErrorKind::NotFound => "NotFoundError",
        ErrorKind::Conversion => "ConversionError",
        ErrorKind::Unsupported => "UnsupportedError",
        ErrorKind::LimitExceeded => "LimitExceededError",
        ErrorKind::MemoryBudgetExceeded => "MemoryLimitError",
        _ => "StateError",
    };
    let build = || -> PyResult<PyErr> {
        let module = py.import("crabxl.errors")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("sheet", error.sheet())?;
        kwargs.set_item("cell", error.cell().map(|cell| cell.to_string()))?;
        kwargs.set_item("part", error.part())?;
        let instance = module
            .getattr(class)?
            .call((text.clone(),), Some(&kwargs))?;
        Ok(PyErr::from_value(instance))
    };
    build().unwrap_or_else(|failure| failure)
}

/// Raise a CrabXL exception from the binding itself.
pub(crate) fn error(py: Python<'_>, class: &str, message: impl Into<String>) -> PyErr {
    let message = message.into();
    match py
        .import("crabxl.errors")
        .and_then(|module| module.getattr(class)?.call1((message.clone(),)))
    {
        Ok(instance) => PyErr::from_value(instance),
        Err(failure) => failure,
    }
}

/// How numbers and dates come back to Python.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct Modes {
    /// Non-integers as `decimal.Decimal` with the exact text.
    pub exact_numbers: bool,
    /// Dates and times as their serial number instead of `datetime` types.
    pub serial_dates: bool,
}

/// A Python object for a cell value.
pub(crate) fn to_python(py: Python<'_>, value: &Value, modes: Modes) -> PyResult<Py<PyAny>> {
    match value {
        Value::Blank => Ok(py.None()),
        Value::Bool(value) => value.into_py_any(py),
        Value::Number(number) => number_to_python(py, number, modes),
        Value::Text(text) => text.as_str().into_py_any(py),
        Value::RichText(text) => {
            let module = py.import("crabxl._values")?;
            let runs = PyList::empty(py);
            for run in &text.runs {
                let font = match &run.font {
                    Some(font) => font_to_python(py, font)?,
                    None => py.None(),
                };
                runs.append(module.getattr("TextRun")?.call1((&*run.text, font))?)?;
            }
            Ok(module
                .getattr("RichText")?
                .call1((PyTuple::new(py, runs)?,))?
                .unbind())
        }
        Value::Temporal(temporal) => temporal_to_python(py, temporal, modes),
        Value::Error(error) => {
            let module = py.import("crabxl._values")?;
            Ok(module
                .getattr("ErrorValue")?
                .call1((error.code(),))?
                .unbind())
        }
        _ => Ok(py.None()),
    }
}

fn number_to_python(py: Python<'_>, number: &Number, modes: Modes) -> PyResult<Py<PyAny>> {
    if let Some(text) = number.to_integer_string() {
        return match text.parse::<i64>() {
            Ok(value) => value.into_py_any(py),
            Err(_) => Ok(py.get_type::<PyInt>().call1((text,))?.unbind()),
        };
    }
    if modes.exact_numbers {
        let decimal = py.import("decimal")?.getattr("Decimal")?;
        return Ok(decimal.call1((number.to_exact_string(),))?.unbind());
    }
    number.to_f64().into_py_any(py)
}

fn temporal_to_python(py: Python<'_>, temporal: &Temporal, modes: Modes) -> PyResult<Py<PyAny>> {
    if modes.serial_dates {
        return temporal.serial().into_py_any(py);
    }
    let unrepresentable = |error: crabxl::Error| {
        self::error(
            py,
            "ConversionError",
            format!(
                "The serial {} has no Python {}: {}. Open with dates=\"serial\" to read serial numbers.",
                temporal.serial(),
                match temporal.kind() {
                    TemporalKind::Date => "date",
                    TemporalKind::Time => "time",
                    TemporalKind::Duration => "timedelta",
                    _ => "datetime",
                },
                error.message()
            ),
        )
    };
    match temporal.kind() {
        TemporalKind::Duration => {
            let micros = temporal.to_duration_micros().map_err(unrepresentable)?;
            let days = micros.div_euclid(86_400_000_000);
            let rest = micros.rem_euclid(86_400_000_000);
            Ok(PyDelta::new(
                py,
                i32::try_from(days).map_err(|_| {
                    unrepresentable(crabxl::Error::new(ErrorKind::Conversion, "out of range"))
                })?,
                (rest / 1_000_000) as i32,
                (rest % 1_000_000) as i32,
                false,
            )?
            .into_any()
            .unbind())
        }
        TemporalKind::Time => {
            let (hour, minute, second, micro) =
                temporal.to_time_of_day().map_err(unrepresentable)?;
            Ok(
                PyTime::new(py, hour as u8, minute as u8, second as u8, micro, None)?
                    .into_any()
                    .unbind(),
            )
        }
        kind => {
            let (year, month, day, hour, minute, second, micro) =
                temporal.to_parts().map_err(unrepresentable)?;
            let python = match kind {
                TemporalKind::Date => PyDate::new(py, year, month as u8, day as u8)?.into_any(),
                _ => PyDateTime::new(
                    py,
                    year,
                    month as u8,
                    day as u8,
                    hour as u8,
                    minute as u8,
                    second as u8,
                    micro,
                    None,
                )?
                .into_any(),
            };
            Ok(python.unbind())
        }
    }
}

/// A cell input from a Python object: a value or a `crabxl.Formula`.
pub(crate) fn from_python(value: &Bound<'_, PyAny>) -> PyResult<crabxl::CellInput> {
    let py = value.py();
    let invalid = |message: String| self::error(py, "InvalidInputError", message);
    let convert = |result: crabxl::Result<Value>| result.map_err(|e| raise(py, e, Phase::Edit));
    if value.is_none() {
        return Ok(crabxl::CellInput::Value(Value::Blank));
    }
    if value.is_instance_of::<PyBool>() {
        return Ok(crabxl::CellInput::Value(Value::Bool(value.extract()?)));
    }
    if value.is_instance_of::<PyInt>() {
        return Ok(crabxl::CellInput::Value(match value.extract::<i64>() {
            Ok(number) => Value::from(number),
            Err(_) => convert(Number::exact(&value.str()?.to_cow()?).map(Value::Number))?,
        }));
    }
    if value.is_instance_of::<PyFloat>() {
        let number: f64 = value.extract()?;
        if !number.is_finite() {
            return Err(invalid("XLSX cannot store NaN or infinity".into()));
        }
        return Ok(crabxl::CellInput::Value(Value::from(number)));
    }
    if value.is_instance_of::<PyString>() {
        let text = value.cast::<PyString>()?.to_cow()?;
        if text.chars().nth(32_767).is_some() {
            return Err(invalid("A cell holds at most 32,767 characters".into()));
        }
        return Ok(crabxl::CellInput::Value(Value::from(&*text)));
    }
    if value.is_instance_of::<PyDateTime>() {
        let value = value.cast::<PyDateTime>()?;
        if value.get_tzinfo().is_some() {
            return Err(invalid(
                "Excel dates have no time zone; convert to a naive datetime first".into(),
            ));
        }
        return Ok(crabxl::CellInput::Value(convert(
            Temporal::datetime(
                value.get_year(),
                value.get_month().into(),
                value.get_day().into(),
                value.get_hour().into(),
                value.get_minute().into(),
                value.get_second().into(),
                value.get_microsecond(),
            )
            .map(Value::Temporal),
        )?));
    }
    if value.is_instance_of::<PyDate>() {
        let value = value.cast::<PyDate>()?;
        return Ok(crabxl::CellInput::Value(convert(
            Temporal::date(
                value.get_year(),
                value.get_month().into(),
                value.get_day().into(),
            )
            .map(Value::Temporal),
        )?));
    }
    if value.is_instance_of::<PyTime>() {
        let value = value.cast::<PyTime>()?;
        if value.get_tzinfo().is_some() {
            return Err(invalid("Excel times have no time zone".into()));
        }
        return Ok(crabxl::CellInput::Value(convert(
            Temporal::time(
                value.get_hour().into(),
                value.get_minute().into(),
                value.get_second().into(),
                value.get_microsecond(),
            )
            .map(Value::Temporal),
        )?));
    }
    if value.is_instance_of::<PyDelta>() {
        let value = value.cast::<PyDelta>()?;
        return Ok(crabxl::CellInput::Value(convert(
            Temporal::duration(
                value.get_days().into(),
                value.get_seconds() as u32,
                value.get_microseconds() as u32,
            )
            .map(Value::Temporal),
        )?));
    }
    let module = py.import("crabxl._values")?;
    if value.is_instance(&module.getattr("Formula")?)? {
        let text: String = value.getattr("text")?.extract()?;
        return Formula::new(text)
            .map(crabxl::CellInput::Formula)
            .map_err(|e| raise(py, e, Phase::Edit));
    }
    if value.is_instance(&module.getattr("ErrorValue")?)? {
        let code: String = value.getattr("code")?.extract()?;
        return Ok(crabxl::CellInput::Value(convert(
            ErrorValue::parse(&code).map(Value::Error),
        )?));
    }
    if value.is_instance(&py.import("decimal")?.getattr("Decimal")?)? {
        let text = value.str()?.to_cow()?.into_owned();
        if !value.call_method0("is_finite")?.extract::<bool>()? {
            return Err(invalid("XLSX cannot store NaN or infinity".into()));
        }
        return Ok(crabxl::CellInput::Value(convert(
            Number::exact(&text).map(Value::Number),
        )?));
    }
    if value.is_instance(&module.getattr("RichText")?)? {
        let mut runs = Vec::new();
        for run in value.getattr("runs")?.try_iter()? {
            let run = run?;
            let text: String = run.getattr("text")?.extract()?;
            let font = run.getattr("font")?;
            runs.push(crabxl::TextRun {
                text: text.into(),
                font: if font.is_none() {
                    None
                } else {
                    Some(Box::new(font_from_python(&font)?))
                },
            });
        }
        let rich = crabxl::RichText {
            runs,
            ..Default::default()
        };
        return Ok(crabxl::CellInput::Value(Value::RichText(rich)));
    }
    Err(self::error(
        py,
        "InvalidInputError",
        format!("Cannot write a value of type {}", value.get_type().name()?),
    ))
}

/// The cells of one Python row.
pub(crate) fn row_from_python(row: &Bound<'_, PyAny>) -> PyResult<Vec<crabxl::CellInput>> {
    if row.is_instance_of::<PyString>() {
        return Err(error(
            row.py(),
            "InvalidInputError",
            "A row is a sequence of values, not a string",
        ));
    }
    row.try_iter()?.map(|value| from_python(&value?)).collect()
}

// ----- Styles -----

fn color_to_python(py: Python<'_>, color: &Color) -> PyResult<Py<PyAny>> {
    use crabxl_core::ColorKind;
    let module = py.import("crabxl.styles")?;
    let class = module.getattr("Color")?;
    let tint = color.tint.unwrap_or(0.0);
    Ok(match &color.kind {
        ColorKind::Theme(index) => class
            .call_method1("theme", (index.as_i64().unwrap_or(0), tint))?
            .unbind(),
        ColorKind::Indexed(index) => class
            .call_method1("indexed", (index.as_i64().unwrap_or(0),))?
            .unbind(),
        ColorKind::Auto(_) | ColorKind::Unspecified => class.call_method0("automatic")?.unbind(),
        _ => match color.to_rgb() {
            Some((r, g, b)) => class.call1((format!("{r:02X}{g:02X}{b:02X}"),))?.unbind(),
            None => py.None(),
        },
    })
}

fn color_from_python(value: &Bound<'_, PyAny>) -> PyResult<Option<Color>> {
    if value.is_none() {
        return Ok(None);
    }
    let py = value.py();
    let kind: String = value.getattr("kind")?.extract()?;
    let tint: f64 = value.getattr("tint")?.extract()?;
    let edit = |e| raise(py, e, Phase::Edit);
    Ok(Some(match kind.as_str() {
        "rgb" => {
            let text: String = value.getattr("value")?.extract()?;
            Color::hex(&text).map_err(edit)?
        }
        "theme" => Color::theme(value.getattr("value")?.extract()?, tint).map_err(edit)?,
        "indexed" => Color {
            kind: crabxl_core::ColorKind::Indexed(value.getattr("value")?.extract::<i64>()?.into()),
            tint: None,
        },
        _ => Color {
            kind: crabxl_core::ColorKind::Auto(true),
            tint: None,
        },
    }))
}

pub(crate) fn font_to_python(py: Python<'_>, font: &Font) -> PyResult<Py<PyAny>> {
    let kwargs = PyDict::new(py);
    kwargs.set_item("name", font.name.as_deref())?;
    kwargs.set_item("size", font.size)?;
    kwargs.set_item("bold", font.bold.unwrap_or(false))?;
    kwargs.set_item("italic", font.italic.unwrap_or(false))?;
    kwargs.set_item("strike", font.strike.unwrap_or(false))?;
    kwargs.set_item(
        "underline",
        font.underline.map(|u| match u {
            crabxl::style::Underline::None => "none",
            crabxl::style::Underline::Double => "double",
            crabxl::style::Underline::SingleAccounting => "single_accounting",
            crabxl::style::Underline::DoubleAccounting => "double_accounting",
            _ => "single",
        }),
    )?;
    let color = match &font.color {
        Some(color) => color_to_python(py, color)?,
        None => py.None(),
    };
    kwargs.set_item("color", color)?;
    Ok(py
        .import("crabxl.styles")?
        .getattr("Font")?
        .call((), Some(&kwargs))?
        .unbind())
}

pub(crate) fn font_from_python(value: &Bound<'_, PyAny>) -> PyResult<Font> {
    let mut font = Font::new();
    if let Some(name) = value.getattr("name")?.extract::<Option<String>>()? {
        font = font.with_name(name);
    }
    if let Some(size) = value.getattr("size")?.extract::<Option<f64>>()? {
        font = font.with_size(size);
    }
    for (attribute, setter) in [
        ("bold", Font::with_bold as fn(Font, bool) -> Font),
        ("italic", Font::with_italic),
        ("strike", Font::with_strike),
    ] {
        if value.getattr(attribute)?.extract::<bool>()? {
            font = setter(font, true);
        }
    }
    if let Some(underline) = value.getattr("underline")?.extract::<Option<String>>()? {
        font = font.with_underline(match underline.as_str() {
            "double" => crabxl::style::Underline::Double,
            "single_accounting" => crabxl::style::Underline::SingleAccounting,
            "double_accounting" => crabxl::style::Underline::DoubleAccounting,
            "none" => crabxl::style::Underline::None,
            _ => crabxl::style::Underline::Single,
        });
    }
    if let Some(color) = color_from_python(&value.getattr("color")?)? {
        font = font.with_color(color);
    }
    Ok(font)
}

fn side_name(line: BorderLine) -> &'static str {
    match line {
        BorderLine::None => "none",
        BorderLine::Thin => "thin",
        BorderLine::Medium => "medium",
        BorderLine::Thick => "thick",
        BorderLine::Dashed => "dashed",
        BorderLine::Dotted => "dotted",
        BorderLine::Double => "double",
        BorderLine::Hair => "hair",
        BorderLine::DashDot => "dash_dot",
        BorderLine::DashDotDot => "dash_dot_dot",
        BorderLine::MediumDashed => "medium_dashed",
        BorderLine::MediumDashDot => "medium_dash_dot",
        BorderLine::MediumDashDotDot => "medium_dash_dot_dot",
        BorderLine::SlantDashDot => "slant_dash_dot",
    }
}
fn side_line(name: &str) -> BorderLine {
    match name {
        "thin" => BorderLine::Thin,
        "medium" => BorderLine::Medium,
        "thick" => BorderLine::Thick,
        "dashed" => BorderLine::Dashed,
        "dotted" => BorderLine::Dotted,
        "double" => BorderLine::Double,
        "hair" => BorderLine::Hair,
        "dash_dot" => BorderLine::DashDot,
        "dash_dot_dot" => BorderLine::DashDotDot,
        "medium_dashed" => BorderLine::MediumDashed,
        "medium_dash_dot" => BorderLine::MediumDashDot,
        "medium_dash_dot_dot" => BorderLine::MediumDashDotDot,
        "slant_dash_dot" => BorderLine::SlantDashDot,
        _ => BorderLine::None,
    }
}

const HORIZONTAL: [(&str, crabxl::style::HorizontalAlignment); 8] = [
    ("general", crabxl::style::HorizontalAlignment::General),
    ("left", crabxl::style::HorizontalAlignment::Left),
    ("center", crabxl::style::HorizontalAlignment::Center),
    ("right", crabxl::style::HorizontalAlignment::Right),
    ("fill", crabxl::style::HorizontalAlignment::Fill),
    ("justify", crabxl::style::HorizontalAlignment::Justify),
    (
        "center_continuous",
        crabxl::style::HorizontalAlignment::CenterContinuous,
    ),
    (
        "distributed",
        crabxl::style::HorizontalAlignment::Distributed,
    ),
];
const VERTICAL: [(&str, crabxl::style::VerticalAlignment); 5] = [
    ("bottom", crabxl::style::VerticalAlignment::Bottom),
    ("center", crabxl::style::VerticalAlignment::Center),
    ("top", crabxl::style::VerticalAlignment::Top),
    ("justify", crabxl::style::VerticalAlignment::Justify),
    ("distributed", crabxl::style::VerticalAlignment::Distributed),
];

/// A `crabxl.styles.Style` for an engine style.
pub(crate) fn style_to_python(py: Python<'_>, style: &Style) -> PyResult<Py<PyAny>> {
    let module = py.import("crabxl.styles")?;
    let fill = match style.fill() {
        Fill::Pattern(pattern) => match pattern.pattern {
            Some(crabxl::style::FillPattern::Solid) => match &pattern.foreground {
                Some(color) => module
                    .getattr("Fill")?
                    .call_method1("solid", (color_to_python(py, color)?,))?
                    .unbind(),
                None => py.None(),
            },
            _ => py.None(),
        },
        Fill::Gradient(_) => py.None(),
    };
    let side = |side: Option<&BorderSide>| -> PyResult<Py<PyAny>> {
        Ok(match side {
            Some(BorderSide {
                line: Some(line),
                color,
            }) if *line != BorderLine::None => {
                let color = match color {
                    Some(color) => color_to_python(py, color)?,
                    None => py.None(),
                };
                module
                    .getattr("Side")?
                    .call1((side_name(*line), color))?
                    .unbind()
            }
            _ => py.None(),
        })
    };
    let border = style.border();
    let border = module.getattr("Border")?.call1((
        side(border.left())?,
        side(border.right())?,
        side(border.top())?,
        side(border.bottom())?,
    ))?;
    let alignment = style.alignment();
    let kwargs = PyDict::new(py);
    kwargs.set_item(
        "horizontal",
        alignment
            .horizontal
            .and_then(|h| HORIZONTAL.iter().find(|(_, v)| *v == h).map(|(n, _)| *n)),
    )?;
    kwargs.set_item(
        "vertical",
        alignment
            .vertical
            .and_then(|h| VERTICAL.iter().find(|(_, v)| *v == h).map(|(n, _)| *n)),
    )?;
    kwargs.set_item("wrap_text", alignment.wrap_text.unwrap_or(false))?;
    kwargs.set_item("shrink_to_fit", alignment.shrink_to_fit.unwrap_or(false))?;
    kwargs.set_item("indent", alignment.indent.unwrap_or(0.0) as u32)?;
    kwargs.set_item("rotation", alignment.rotation.unwrap_or(0))?;
    let alignment = module.getattr("Alignment")?.call((), Some(&kwargs))?;
    let protection = style.protection();
    let protection = module.getattr("Protection")?.call1((
        protection.locked.unwrap_or(true),
        protection.hidden.unwrap_or(false),
    ))?;
    let kwargs = PyDict::new(py);
    kwargs.set_item("number_format", style.number_format())?;
    kwargs.set_item("font", font_to_python(py, style.font())?)?;
    kwargs.set_item("fill", fill)?;
    kwargs.set_item("border", border)?;
    kwargs.set_item("alignment", alignment)?;
    kwargs.set_item("protection", protection)?;
    Ok(module.getattr("Style")?.call((), Some(&kwargs))?.unbind())
}

/// An engine style for a `crabxl.styles.Style`.
pub(crate) fn style_from_python(value: &Bound<'_, PyAny>) -> PyResult<Style> {
    let mut style =
        Style::new().with_number_format(value.getattr("number_format")?.extract::<String>()?);
    style = style.with_font(font_from_python(&value.getattr("font")?)?);
    let fill = value.getattr("fill")?;
    if !fill.is_none()
        && let Some(color) = color_from_python(&fill.getattr("color")?)?
    {
        style = style.with_fill(Fill::solid(color));
    }
    let border = value.getattr("border")?;
    let mut sides = Border::new();
    let side = |name: &str| -> PyResult<Option<BorderSide>> {
        let side = border.getattr(name)?;
        if side.is_none() {
            return Ok(None);
        }
        let line: String = side.getattr("style")?.extract()?;
        Ok(Some(BorderSide {
            line: Some(side_line(&line)),
            color: color_from_python(&side.getattr("color")?)?,
        }))
    };
    if let Some(left) = side("left")? {
        sides = sides.with_left(left);
    }
    if let Some(right) = side("right")? {
        sides = sides.with_right(right);
    }
    if let Some(top) = side("top")? {
        sides = sides.with_top(top);
    }
    if let Some(bottom) = side("bottom")? {
        sides = sides.with_bottom(bottom);
    }
    style = style.with_border(sides);
    let alignment = value.getattr("alignment")?;
    let mut aligned = Alignment::new();
    if let Some(name) = alignment
        .getattr("horizontal")?
        .extract::<Option<String>>()?
        && let Some((_, value)) = HORIZONTAL.iter().find(|(n, _)| *n == name)
    {
        aligned = aligned.with_horizontal(*value);
    }
    if let Some(name) = alignment.getattr("vertical")?.extract::<Option<String>>()?
        && let Some((_, value)) = VERTICAL.iter().find(|(n, _)| *n == name)
    {
        aligned = aligned.with_vertical(*value);
    }
    if alignment.getattr("wrap_text")?.extract::<bool>()? {
        aligned = aligned.with_wrap_text(true);
    }
    if alignment.getattr("shrink_to_fit")?.extract::<bool>()? {
        aligned = aligned.with_shrink_to_fit(true);
    }
    let indent: u8 = alignment.getattr("indent")?.extract()?;
    if indent > 0 {
        aligned = aligned.with_indent(indent);
    }
    let rotation: u8 = alignment.getattr("rotation")?.extract()?;
    if rotation > 0 {
        aligned = aligned.with_rotation(rotation);
    }
    style = style.with_alignment(aligned);
    let protection = value.getattr("protection")?;
    style = style.with_protection(Protection::new(
        protection.getattr("locked")?.extract()?,
        protection.getattr("hidden")?.extract()?,
    ));
    Ok(style)
}

/// A `crabxl.styles.PartialStyle` for an engine partial style. Only solid
/// fills have a Python form; other fills read as `None`.
pub(crate) fn partial_style_to_python(
    py: Python<'_>,
    style: &crabxl::style::PartialStyle,
) -> PyResult<Py<PyAny>> {
    let module = py.import("crabxl.styles")?;
    let kwargs = PyDict::new(py);
    if let Some(font) = style.font() {
        kwargs.set_item("font", font_to_python(py, font)?)?;
    }
    if let Some(Fill::Pattern(pattern)) = style.fill()
        && let Some(color) = pattern.background.as_ref().or(pattern.foreground.as_ref())
    {
        kwargs.set_item(
            "fill",
            module
                .getattr("Fill")?
                .call_method1("solid", (color_to_python(py, color)?,))?,
        )?;
    }
    Ok(module
        .getattr("PartialStyle")?
        .call((), Some(&kwargs))?
        .unbind())
}

/// An engine partial style for a `crabxl.styles.PartialStyle`.
pub(crate) fn partial_style_from_python(
    value: &Bound<'_, PyAny>,
) -> PyResult<crabxl::style::PartialStyle> {
    let mut partial = crabxl::style::PartialStyle::new();
    let font = value.getattr("font")?;
    if !font.is_none() {
        partial = partial.with_font(font_from_python(&font)?);
    }
    let fill = value.getattr("fill")?;
    if !fill.is_none()
        && let Some(color) = color_from_python(&fill.getattr("color")?)?
    {
        partial = partial.with_fill(Fill::solid(color));
    }
    Ok(partial)
}
