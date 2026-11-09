//! Named-style coordination over canonical Rust owners.
use crate::{failure, styles};
use crabxl::{
    Error, ErrorKind, LoadedWorkbook, NamedStyleOptions, Result, StyleCatalog, StyleComponent,
    StyleId, Workbook, WorkbookWriter,
};
use pyo3::{prelude::*, types::PyDict};

/// Style directive keys that carry a `NativeStyleComponent`.
pub(crate) const STYLE_COMPONENTS: [&str; 7] = [
    "font",
    "fill",
    "border",
    "alignment",
    "protection",
    "quotePrefix",
    "pivotButton",
];

pub(crate) trait StyleOwner {
    fn catalog(&self) -> Option<&StyleCatalog>;
    fn component(&mut self, base: StyleId, component: StyleComponent) -> Result<StyleId>;
    fn number(&mut self, base: StyleId, code: Box<str>) -> Result<StyleId>;
    fn metadata(
        &mut self,
        name: &str,
        new_name: Box<str>,
        options: NamedStyleOptions,
    ) -> Result<()>;
    fn update(&mut self, name: &str, base: StyleId) -> Result<StyleId>;
    fn named(
        &mut self,
        name: Box<str>,
        base: StyleId,
        options: NamedStyleOptions,
    ) -> Result<StyleId>;
}
impl StyleOwner for Workbook {
    fn catalog(&self) -> Option<&StyleCatalog> {
        self.style_catalog()
    }
    fn component(&mut self, base: StyleId, component: StyleComponent) -> Result<StyleId> {
        self.derive_style_component(base, component)
    }
    fn number(&mut self, base: StyleId, code: Box<str>) -> Result<StyleId> {
        self.derive_number_format(base, code)
    }
    fn metadata(
        &mut self,
        name: &str,
        new_name: Box<str>,
        options: NamedStyleOptions,
    ) -> Result<()> {
        self.update_named_metadata(name, new_name, options)
    }
    fn update(&mut self, name: &str, base: StyleId) -> Result<StyleId> {
        self.update_named_style(name, base)
    }
    fn named(
        &mut self,
        name: Box<str>,
        base: StyleId,
        options: NamedStyleOptions,
    ) -> Result<StyleId> {
        self.register_named_style(name, base, options)
    }
}
impl<R: std::io::Read + std::io::Seek> StyleOwner for LoadedWorkbook<R> {
    fn catalog(&self) -> Option<&StyleCatalog> {
        self.model().style_catalog()
    }
    fn component(&mut self, base: StyleId, component: StyleComponent) -> Result<StyleId> {
        self.derive_style_component(base, component)
    }
    fn number(&mut self, base: StyleId, code: Box<str>) -> Result<StyleId> {
        self.derive_number_format(base, code)
    }
    fn metadata(
        &mut self,
        name: &str,
        new_name: Box<str>,
        options: NamedStyleOptions,
    ) -> Result<()> {
        self.update_named_metadata(name, new_name, options)
    }
    fn update(&mut self, name: &str, base: StyleId) -> Result<StyleId> {
        self.update_named_style(name, base)
    }
    fn named(
        &mut self,
        name: Box<str>,
        base: StyleId,
        options: NamedStyleOptions,
    ) -> Result<StyleId> {
        self.register_named_style(name, base, options)
    }
}
impl StyleOwner for WorkbookWriter {
    fn catalog(&self) -> Option<&StyleCatalog> {
        self.style_catalog()
    }
    fn component(&mut self, base: StyleId, component: StyleComponent) -> Result<StyleId> {
        self.derive_style_component(base, component)
    }
    fn number(&mut self, base: StyleId, code: Box<str>) -> Result<StyleId> {
        let mut format = self
            .style_catalog()
            .and_then(|catalog| catalog.cell_format(base))
            .cloned()
            .ok_or_else(|| Error::new(ErrorKind::InvalidData, "Unknown base style"))?;
        let number = self.register_number_format(code)?;
        format.number_format_id = number;
        format.apply_number_format = Some(true);
        self.register_format(format)
    }
    fn metadata(
        &mut self,
        name: &str,
        new_name: Box<str>,
        options: NamedStyleOptions,
    ) -> Result<()> {
        self.update_named_metadata(name, new_name, options)
    }
    fn update(&mut self, name: &str, base: StyleId) -> Result<StyleId> {
        self.update_named_style(name, base)
    }
    fn named(
        &mut self,
        name: Box<str>,
        base: StyleId,
        options: NamedStyleOptions,
    ) -> Result<StyleId> {
        self.register_named_style(name, base, options)
    }
}
pub(crate) fn names(catalog: Option<&StyleCatalog>) -> Vec<String> {
    catalog.map_or_else(
        || vec!["Normal".into()],
        |catalog| {
            catalog
                .named_styles
                .iter()
                .map(|style| style.name.to_string())
                .collect()
        },
    )
}
pub(crate) fn style_name(catalog: Option<&StyleCatalog>, style: StyleId) -> String {
    let name = catalog.and_then(|catalog| {
        catalog
            .cell_format(style)
            .and_then(|format| format.base_format_id)
            .and_then(|base| {
                catalog
                    .named_styles
                    .iter()
                    .find(|style| style.base_format_id == base)
            })
    });
    name.map_or_else(|| "Normal".into(), |style| style.name.to_string())
}
pub(crate) fn snapshot<'py>(
    py: Python<'py>,
    catalog: Option<&StyleCatalog>,
    style: StyleId,
) -> PyResult<(u32, String, Bound<'py, PyDict>)> {
    let components = PyDict::new(py);
    let appearance = catalog
        .map(|catalog| catalog.cell_style(style))
        .transpose()
        .map_err(failure)?;
    for name in ["font", "fill", "border", "alignment", "protection"] {
        components.set_item(
            name,
            if let Some(appearance) = appearance {
                styles::encode(py, name, appearance)?
            } else {
                styles::default_component(py, name)?
            },
        )?;
    }
    Ok((
        style.get(),
        appearance
            .and_then(|style| style.number_format)
            .unwrap_or("General")
            .into(),
        components,
    ))
}

pub(crate) fn register(
    owner: &mut impl StyleOwner,
    value: &Bound<'_, PyDict>,
    update: bool,
) -> PyResult<u32> {
    let name: String = value
        .get_item("name")?
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("Missing style name"))?
        .extract()?;
    if !update
        && owner.catalog().is_some_and(|catalog| {
            catalog
                .named_styles
                .iter()
                .any(|style| style.name.as_ref() == name)
        })
    {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "Style {name} exists already"
        )));
    }
    let builtin = value
        .get_item("builtinId")?
        .filter(|v| !v.is_none())
        .map(|v| v.extract::<u32>())
        .transpose()?;
    let hidden = value
        .get_item("hidden")?
        .map(|v| v.extract::<bool>())
        .transpose()?
        .unwrap_or(false);
    let style = prepare(owner, value)?;
    if update {
        return owner
            .update(&name, style)
            .map(|id| id.get())
            .map_err(failure);
    }
    owner
        .named(
            name.into(),
            style,
            NamedStyleOptions {
                builtin_id: builtin,
                hidden: Some(hidden),
                ..Default::default()
            },
        )
        .map(|id| id.get())
        .map_err(failure)
}

pub(crate) fn metadata(
    owner: &mut impl StyleOwner,
    name: &str,
    new_name: String,
    builtin: Option<u32>,
    hidden: bool,
) -> PyResult<()> {
    owner
        .metadata(
            name,
            new_name.into(),
            NamedStyleOptions {
                builtin_id: builtin,
                hidden: Some(hidden),
                ..Default::default()
            },
        )
        .map_err(failure)
}

pub(crate) fn prepare(owner: &mut impl StyleOwner, value: &Bound<'_, PyDict>) -> PyResult<StyleId> {
    let base = value
        .get_item("style_id")?
        .map(|value| value.extract::<u32>())
        .transpose()?
        .unwrap_or(0);
    let code = value
        .get_item("number_format")?
        .map(|v| v.extract::<String>())
        .transpose()?
        .unwrap_or_else(|| "General".into());
    let mut components = Vec::with_capacity(5);
    for name in STYLE_COMPONENTS {
        if let Some(value) = value.get_item(name)? {
            components.push(
                value
                    .extract::<PyRef<'_, styles::NativeStyleComponent>>()?
                    .component
                    .clone(),
            );
        }
    }
    let mut style = if value.contains("number_format")? {
        owner
            .number(StyleId::new(base), code.into())
            .map_err(failure)?
    } else {
        StyleId::new(base)
    };
    for component in components {
        style = owner.component(style, component).map_err(failure)?;
    }
    Ok(style)
}

pub(crate) fn prepare_array(
    owner: &mut impl StyleOwner,
    value: &Bound<'_, PyDict>,
) -> PyResult<[u32; 9]> {
    let style = prepare(owner, value)?;
    owner
        .catalog()
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("Missing style catalog"))?
        .style_array(style)
        .map_err(failure)
}

fn collection_slot(name: &str) -> PyResult<usize> {
    match name {
        "font" => Ok(0),
        "fill" => Ok(1),
        "border" => Ok(2),
        "number_format" => Ok(3),
        "protection" => Ok(4),
        "alignment" => Ok(5),
        _ => Err(pyo3::exceptions::PyValueError::new_err(
            "Unknown style collection",
        )),
    }
}

pub(crate) fn collection<'py>(
    py: Python<'py>,
    catalog: Option<&StyleCatalog>,
    name: &str,
) -> PyResult<Vec<Bound<'py, PyDict>>> {
    let slot = collection_slot(name)?;
    let defaults;
    let catalog = match catalog {
        Some(value) => value,
        None => {
            defaults =
                crabxl::StyleRegistry::new(crabxl::StyleLimits::default()).map_err(failure)?;
            defaults.catalog()
        }
    };
    let mut output = Vec::new();
    if name == "number_format" {
        for number in &catalog.number_formats {
            if number.id() >= 164 {
                let value = PyDict::new(py);
                value.set_item("code", number.code())?;
                output.push(value);
            }
        }
        return Ok(output);
    }
    let base = catalog.cell_style(StyleId::new(0)).map_err(failure)?;
    if slot <= 2 {
        let length = match slot {
            0 => catalog.fonts.len(),
            1 => catalog.fills.len(),
            _ => catalog.borders.len(),
        };
        for index in 0..length {
            let mut view = base;
            match slot {
                0 => view.font = &catalog.fonts[index],
                1 => view.fill = &catalog.fills[index],
                _ => view.border = &catalog.borders[index],
            };
            output.push(collection_value(py, name, view)?);
        }
    } else {
        output.push(styles::default_component(py, name)?);
        for (index, array) in catalog.style_arrays().map_err(failure)?.iter().enumerate() {
            if array[slot] as usize == output.len() {
                let view = catalog
                    .cell_style(StyleId::new(index as u32))
                    .map_err(failure)?;
                output.push(collection_value(py, name, view)?);
            }
        }
    }
    Ok(output)
}

pub(crate) fn collection_add(
    owner: &mut impl StyleOwner,
    name: &str,
    value: &Bound<'_, PyAny>,
) -> PyResult<u32> {
    let slot = collection_slot(name)?;
    let style = if name == "number_format" {
        owner
            .number(StyleId::new(0), value.extract::<String>()?.into())
            .map_err(failure)?
    } else {
        let component = value
            .extract::<PyRef<'_, styles::NativeStyleComponent>>()?
            .component
            .clone();
        let valid = matches!(
            (name, &component),
            ("font", StyleComponent::Font(_))
                | ("fill", StyleComponent::Fill(_))
                | ("border", StyleComponent::Border(_))
                | ("alignment", StyleComponent::Alignment(_))
                | ("protection", StyleComponent::Protection(_))
        );
        if !valid {
            return Err(pyo3::exceptions::PyTypeError::new_err(
                "Wrong style component type",
            ));
        }
        owner
            .component(StyleId::new(0), component)
            .map_err(failure)?
    };
    let catalog = owner
        .catalog()
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("Missing style catalog"))?;
    if name == "number_format" {
        let code = value.extract::<String>()?;
        return catalog
            .number_formats
            .iter()
            .filter(|number| number.id() >= 164)
            .position(|number| number.code() == code)
            .map(|index| index as u32)
            .ok_or_else(|| {
                pyo3::exceptions::PyValueError::new_err(
                    "Built-in formats use their standard identities",
                )
            });
    }
    Ok(catalog.style_array(style).map_err(failure)?[slot])
}

fn collection_value<'py>(
    py: Python<'py>,
    name: &str,
    view: crabxl::StyleView<'_>,
) -> PyResult<Bound<'py, PyDict>> {
    let component = match name {
        "font" => StyleComponent::Font(Box::new(view.font.clone())),
        "fill" => StyleComponent::Fill(Box::new(view.fill.clone())),
        "border" => StyleComponent::Border(Box::new(view.border.clone())),
        "alignment" => StyleComponent::Alignment(view.alignment.cloned().map(Box::new)),
        "protection" => StyleComponent::Protection(view.protection.cloned()),
        _ => {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Unknown style component",
            ));
        }
    };
    let value = styles::encode(py, name, view)?;
    value.set_item(
        "_native_component",
        styles::NativeStyleComponent { component },
    )?;
    Ok(value)
}

pub(crate) type NamedStyleMetadata = Vec<(String, Option<u32>, Option<bool>)>;

pub(crate) fn named_metadata(catalog: Option<&StyleCatalog>) -> NamedStyleMetadata {
    catalog.map_or_else(
        || vec![("Normal".into(), Some(0), Some(false))],
        |catalog| {
            catalog
                .named_styles
                .iter()
                .map(|style| (style.name.to_string(), style.builtin_id, style.hidden))
                .collect()
        },
    )
}
