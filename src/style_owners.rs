//! Named-style coordination over canonical Rust owners.
use crate::{failure, styles};
use crabxl::{
    Error, ErrorKind, LoadedWorkbook, NamedStyleOptions, Result, StyleCatalog, StyleComponent,
    StyleId, Workbook, WorkbookWriter,
};
use pyo3::{prelude::*, types::PyDict};

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
    let code = value
        .get_item("number_format")?
        .map(|v| v.extract::<String>())
        .transpose()?
        .unwrap_or_else(|| "General".into());
    let mut components = Vec::with_capacity(5);
    for name in ["font", "fill", "border", "alignment", "protection"] {
        if let Some(value) = value.get_item(name)? {
            components.push(
                value
                    .extract::<PyRef<'_, styles::NativeStyleComponent>>()?
                    .component
                    .clone(),
            );
        }
    }
    let mut style = owner
        .number(StyleId::new(0), code.into())
        .map_err(failure)?;
    for component in components {
        style = owner.component(style, component).map_err(failure)?;
    }
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
