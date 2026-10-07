//! Point metadata conversion over canonical owned and source-backed sheets.
use super::*;

pub(crate) type LinkFields = (
    Option<String>,
    Option<String>,
    Option<String>,
    Option<String>,
    Option<String>,
    Option<String>,
);

fn fields(links: &crabxl::Hyperlinks, address: CellAddress) -> Option<LinkFields> {
    let link = links.get(address)?;
    let mut fields = owned_fields(link);
    if links.covering_range(address).is_some() {
        fields.5 = None;
    }
    Some(fields)
}

pub(crate) fn owned_fields(link: &crabxl::Hyperlink) -> LinkFields {
    (
        link.target.as_deref().map(str::to_owned),
        link.location.as_deref().map(str::to_owned),
        link.tooltip.as_deref().map(str::to_owned),
        link.display.as_deref().map(str::to_owned),
        link.relationship_id.as_deref().map(str::to_owned),
        link.reference.as_deref().map(str::to_owned),
    )
}

pub(crate) fn decode(fields: LinkFields) -> crabxl::Hyperlink {
    let (target, location, tooltip, display, relationship_id, reference) = fields;
    crabxl::Hyperlink {
        reference: reference.map(String::into_boxed_str),
        target: target.map(String::into_boxed_str),
        location: location.map(String::into_boxed_str),
        tooltip: tooltip.map(String::into_boxed_str),
        display: display.map(String::into_boxed_str),
        relationship_id: relationship_id.map(String::into_boxed_str),
        external: true,
    }
}

#[pyfunction]
pub(crate) fn initial_hyperlink_value(
    py: Python<'_>,
    fields: LinkFields,
) -> PyResult<EncodedValue> {
    encode(py, &decode(fields).initial_cell_value())
}

impl NativeSheet {
    pub(crate) fn hyperlink_fields(&self, row: u32, column: u32) -> PyResult<Option<LinkFields>> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        let storage = lock(&self.storage)?;
        match &*storage {
            SheetStorage::Standalone(sheet) => Ok(fields(sheet.hyperlinks(), address)),
            SheetStorage::Bank { book, id } => Ok(fields(
                lock(book)?.sheet(*id).map_err(failure)?.hyperlinks(),
                address,
            )),
            SheetStorage::Loaded { book, id } => Ok(fields(
                lock(book)?
                    .as_mut()
                    .ok_or_else(closed)?
                    .hyperlinks(*id)
                    .map_err(failure)?,
                address,
            )),
        }
    }

    pub(crate) fn replace_hyperlink(
        &self,
        row: u32,
        column: u32,
        value: Option<LinkFields>,
        initialize_value: bool,
    ) -> PyResult<()> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        let link = value.map(decode);
        let mut storage = lock(&self.storage)?;
        match &mut *storage {
            SheetStorage::Standalone(sheet) => if initialize_value {
                sheet.set_hyperlink(address, link)
            } else {
                sheet.update_hyperlink(address, link)
            }
            .map_err(failure),
            SheetStorage::Bank { book, id } => {
                let mut bank = lock(book)?;
                let mut sheet = bank.sheet_mut(*id).map_err(failure)?;
                if initialize_value {
                    sheet.set_hyperlink(address, link)
                } else {
                    sheet.update_hyperlink(address, link)
                }
                .map_err(failure)
            }
            SheetStorage::Loaded { book, id } => {
                let mut loaded = lock(book)?;
                let loaded = loaded.as_mut().ok_or_else(closed)?;
                if initialize_value {
                    loaded.set_hyperlink(*id, address, link)
                } else {
                    loaded.update_hyperlink(*id, address, link)
                }
                .map_err(failure)
            }
        }
    }
}
