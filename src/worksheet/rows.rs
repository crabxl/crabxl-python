//! Borrowed row projections and deferred live structured-value conversion.
use super::*;

pub(super) fn tagged(
    sheet: &NativeSheet,
    py: Python<'_>,
    row: u32,
    first: u32,
    last: u32,
    create_missing: bool,
    defer_bound: bool,
) -> PyResult<Vec<EncodedValue>> {
    let row_index = CellAddress::new(row, first).map_err(failure)?.row;
    CellAddress::new(row, last).map_err(failure)?;
    if first > last {
        return Ok(Vec::new());
    }
    if !create_missing {
        return sheet.with(|sheet| {
            let mut cells = sheet
                .row_cells(row_index)
                .skip_while(|cell| cell.address.column.get() < first)
                .take_while(|cell| cell.address.column.get() <= last)
                .peekable();
            let mut values = Vec::with_capacity((last - first + 1) as usize);
            for column in first..=last {
                let value = if cells
                    .peek()
                    .is_some_and(|cell| cell.address.column.get() == column)
                {
                    cells.next().map_or(&CellValue::Empty, |cell| &cell.value)
                } else {
                    &CellValue::Empty
                };
                values.push(project(py, value, defer_bound)?);
            }
            Ok(values)
        });
    }
    sheet.with_mut(|sheet| {
        let mut values = Vec::with_capacity((last - first + 1) as usize);
        for column in first..=last {
            let address = CellAddress::new(row, column).map_err(failure)?;
            if create_missing
                && sheet.get(address).is_none()
                && sheet.merged_ranges().virtual_style(address).is_none()
            {
                sheet
                    .set(Cell {
                        address,
                        value: CellValue::Empty,
                        style: StyleId::new(0),
                    })
                    .map_err(failure)?;
            }
            values.push(project(
                py,
                sheet
                    .get(address)
                    .map_or(&CellValue::Empty, |cell| &cell.value),
                defer_bound,
            )?);
        }
        Ok(values)
    })
}

fn project(py: Python<'_>, value: &CellValue, defer_bound: bool) -> PyResult<EncodedValue> {
    if defer_bound {
        let kind = match value {
            CellValue::RichText(_) => Some("rich"),
            CellValue::Formula(formula) => match formula.formula_type() {
                FormulaType::Array => Some("array"),
                FormulaType::DataTable => Some("table"),
                _ => None,
            },
            _ => None,
        };
        if let Some(kind) = kind {
            return Ok((kind, py.None()));
        }
    }
    encode(py, value)
}
