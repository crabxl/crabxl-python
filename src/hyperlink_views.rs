//! Bounded output identity selection for existing public hyperlink objects.
use crate::*;

pub(crate) type Requests = Vec<(Py<NativeSheet>, Vec<(u32, u32)>)>;
pub(crate) type Output = Vec<(usize, u32, u32, Option<String>)>;
type Captured = Vec<(SheetId, Vec<(u32, u32)>)>;

enum Owner<'a> {
    Bank(&'a Arc<Mutex<Workbook>>),
    Loaded(&'a SharedLoaded),
}
fn capture(py: Python<'_>, requests: Requests, owner: Owner<'_>) -> PyResult<Captured> {
    let mut result = Vec::with_capacity(requests.len());
    for (sheet, coordinates) in requests {
        let sheet = sheet.borrow(py);
        let storage = lock(&sheet.storage)?;
        let id = match (&*storage, &owner) {
            (SheetStorage::Bank { book, id }, Owner::Bank(expected))
                if Arc::ptr_eq(book, expected) =>
            {
                *id
            }
            (SheetStorage::Loaded { book, id }, Owner::Loaded(expected))
                if Arc::ptr_eq(book, expected) =>
            {
                *id
            }
            _ => {
                return Err(PyValueError::new_err(
                    "Hyperlink view belongs to another workbook",
                ));
            }
        };
        result.push((id, coordinates));
    }
    Ok(result)
}

struct Query {
    sheet: SheetId,
    request: usize,
    row: u32,
    column: u32,
    owner: CellAddress,
}
impl Query {
    fn key(&self) -> (u64, u32, u32) {
        (
            self.sheet.serial(),
            self.owner.row.get(),
            self.owner.column.get(),
        )
    }
}
struct Projection {
    queries: Vec<Query>,
    output: Output,
    workspace: usize,
    strings_available: usize,
}
impl Projection {
    fn prepare(book: &Workbook, requests: Captured, available: usize) -> Result<Self, Error> {
        let count = requests
            .iter()
            .try_fold(0usize, |count, (_, coordinates)| {
                count.checked_add(coordinates.len())
            })
            .ok_or_else(budget)?;
        let slots = count
            .checked_mul(size_of::<Query>() + size_of::<(usize, u32, u32, Option<String>)>())
            .ok_or_else(budget)?;
        if slots > available {
            return Err(budget());
        }
        let mut strings = 0usize;
        for (id, coordinates) in &requests {
            let links = book.sheet(*id)?.hyperlinks();
            for &(row, column) in coordinates {
                let address = CellAddress::new(row, column)?;
                if let Some(link) = links.get(address) {
                    strings = strings.saturating_add(
                        link.relationship_id
                            .as_ref()
                            .map_or(64, |value| value.len().max(64)),
                    );
                }
            }
        }
        if slots.saturating_add(strings) > available {
            return Err(budget());
        }
        let mut queries = Vec::new();
        queries.try_reserve_exact(count).map_err(|_| budget())?;
        let mut output = Vec::new();
        output.try_reserve_exact(count).map_err(|_| budget())?;
        let workspace = queries.capacity() * size_of::<Query>()
            + output.capacity() * size_of::<(usize, u32, u32, Option<String>)>()
            + strings;
        if workspace > available {
            return Err(budget());
        }
        for (request, (id, coordinates)) in requests.into_iter().enumerate() {
            let links = book.sheet(id)?.hyperlinks();
            for (row, column) in coordinates {
                let address = CellAddress::new(row, column)?;
                if links.get(address).is_none() {
                    continue;
                }
                let owner = links
                    .covering_range(address)
                    .map_or(address, |range| range.start);
                queries.push(Query {
                    sheet: id,
                    request,
                    row,
                    column,
                    owner,
                });
            }
        }
        queries.sort_unstable_by_key(Query::key);
        Ok(Self {
            queries,
            output,
            workspace,
            strings_available: strings,
        })
    }
    fn visit(&mut self, value: crabxl::HyperlinkOutput<'_>) -> Result<(), Error> {
        let key = (
            value.sheet.serial(),
            value.owner.row.get(),
            value.owner.column.get(),
        );
        let first = self.queries.partition_point(|query| query.key() < key);
        for query in self.queries[first..]
            .iter()
            .take_while(|query| query.key() == key)
        {
            let bytes = value.identity.map_or(0, str::len);
            if bytes > self.strings_available || self.output.len() == self.output.capacity() {
                return Err(budget());
            }
            self.strings_available -= bytes;
            self.output.push((
                query.request,
                query.row + 1,
                query.column + 1,
                value.identity.map(str::to_owned),
            ));
        }
        Ok(())
    }
}
fn budget() -> Error {
    Error::new(
        ErrorKind::MemoryBudgetExceeded,
        "Public hyperlink identity selection exceeds its shared allowance",
    )
}

pub(crate) fn owned(
    py: Python<'_>,
    book: &Arc<Mutex<Workbook>>,
    requests: Requests,
) -> PyResult<Output> {
    let requests = capture(py, requests, Owner::Bank(book))?;
    let book = Arc::clone(book);
    py.detach(move || {
        let book = lock(&book)?;
        let mut projection =
            Projection::prepare(&book, requests, book.remaining_bytes()).map_err(failure)?;
        for (sheet, model) in book.sheets() {
            crabxl::visit_owned_hyperlink_ids(sheet, model.hyperlinks(), |value| {
                projection.visit(value)
            })
            .map_err(failure)?;
        }
        Ok(projection.output)
    })
}
pub(crate) fn loaded(py: Python<'_>, book: &SharedLoaded, requests: Requests) -> PyResult<Output> {
    let requests = capture(py, requests, Owner::Loaded(book))?;
    let book = Arc::clone(book);
    py.detach(move || {
        let mut handle = lock(&book)?;
        let loaded = handle.as_mut().ok_or_else(closed)?;
        let available = loaded
            .memory_allowance()
            .retained_data_bytes
            .saturating_sub(loaded.managed_retained_bytes());
        let mut projection =
            Projection::prepare(loaded.model(), requests, available).map_err(failure)?;
        loaded
            .visit_hyperlink_output_ids(projection.workspace, |value| projection.visit(value))
            .map_err(failure)?;
        Ok(projection.output)
    })
}
