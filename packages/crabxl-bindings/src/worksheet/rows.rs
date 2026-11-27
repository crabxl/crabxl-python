//! Borrowed row projections and deferred live structured-value conversion.
use super::*;

/// The cells of one row from `first` to `last`, each converted by `convert`.
pub(super) fn map<T>(
    sheet: &NativeSheet,
    row: u32,
    first: u32,
    last: u32,
    create_missing: bool,
    mut convert: impl FnMut(&CellValue) -> PyResult<T>,
) -> PyResult<Vec<T>> {
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
                values.push(convert(value)?);
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
            values.push(convert(
                sheet
                    .get(address)
                    .map_or(&CellValue::Empty, |cell| &cell.value),
            )?);
        }
        Ok(values)
    })
}

/// Final Python values for one row. Structured formulas and rich text stay
/// live cell views: they are None here and their columns are returned.
pub(super) fn values(
    sheet: &NativeSheet,
    py: Python<'_>,
    row: u32,
    first: u32,
    last: u32,
    create_missing: bool,
) -> PyResult<DecodedValues> {
    let mut column = 0;
    let mut bound = None;
    let mut decoder = None;
    let values = map(sheet, row, first, last, create_missing, |value| {
        let live = match value.unannotated() {
            CellValue::RichText(_) => true,
            CellValue::Formula(formula) => matches!(
                formula.formula_type(),
                FormulaType::Array | FormulaType::DataTable
            ),
            _ => false,
        };
        column += 1;
        if live {
            bound.get_or_insert_with(Vec::new).push(column - 1);
            return Ok(py.None());
        }
        read_value(py, value, &mut decoder)
    })?;
    Ok((values, bound))
}
