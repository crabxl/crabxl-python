//! Point metadata conversion over canonical owned and source-backed sheets.
use super::*;

pub(super) type LinkFields = (
    Option<String>,
    Option<String>,
    Option<String>,
    Option<String>,
    Option<String>,
    Option<String>,
);

fn fields(link: &crabxl::Hyperlink) -> LinkFields {
    (
        link.target.as_deref().map(str::to_owned),
        link.location.as_deref().map(str::to_owned),
        link.tooltip.as_deref().map(str::to_owned),
        link.display.as_deref().map(str::to_owned),
        link.relationship_id.as_deref().map(str::to_owned),
        link.reference.as_deref().map(str::to_owned),
    )
}

impl NativeSheet {
    pub(crate) fn hyperlink_fields(&self, row: u32, column: u32) -> PyResult<Option<LinkFields>> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        let storage = lock(&self.storage)?;
        match &*storage {
            SheetStorage::Standalone(sheet) => Ok(sheet.hyperlinks().get(address).map(fields)),
            SheetStorage::Bank { book, id } => Ok(lock(book)?
                .sheet(*id)
                .map_err(failure)?
                .hyperlinks()
                .get(address)
                .map(fields)),
            SheetStorage::Loaded { book, id } => Ok(lock(book)?
                .as_mut()
                .ok_or_else(closed)?
                .hyperlinks(*id)
                .map_err(failure)?
                .get(address)
                .map(fields)),
        }
    }

    pub(crate) fn replace_hyperlink(
        &self,
        row: u32,
        column: u32,
        value: Option<LinkFields>,
    ) -> PyResult<()> {
        let address = CellAddress::new(row, column).map_err(failure)?;
        let link = value.map(
            |(target, location, tooltip, display, relationship_id, reference)| crabxl::Hyperlink {
                reference: reference.map(String::into_boxed_str),
                target: target.map(String::into_boxed_str),
                location: location.map(String::into_boxed_str),
                tooltip: tooltip.map(String::into_boxed_str),
                display: display.map(String::into_boxed_str),
                relationship_id: relationship_id.map(String::into_boxed_str),
                external: true,
            },
        );
        let mut storage = lock(&self.storage)?;
        match &mut *storage {
            SheetStorage::Standalone(sheet) => sheet.set_hyperlink(address, link).map_err(failure),
            SheetStorage::Bank { book, id } => lock(book)?
                .sheet_mut(*id)
                .map_err(failure)?
                .set_hyperlink(address, link)
                .map_err(failure),
            SheetStorage::Loaded { book, id } => lock(book)?
                .as_mut()
                .ok_or_else(closed)?
                .set_hyperlink(*id, address, link)
                .map_err(failure),
        }
    }
}
