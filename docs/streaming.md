---
title: Streaming
description: Read and write files of any size with bounded memory.
---

## Read

`Reader` reads one worksheet at a time, row by row. It never holds a whole
sheet.

```python
import crabxl as xl

with xl.Reader.open("events.xlsx") as reader:
    events = reader.worksheets["Events"]
    for row in events.iter_rows(columns="A:D", skip=1, limit=1000):
        event_id, kind, when, amount = row
        print(row.number, row.formulas)
```

`iter_rows` returns the rows that hold at least one cell. Each `Row` behaves
like a tuple of values, dense from its first column, with `None` for empty
cells. `row.number` is the row number as Excel shows it.

| Option | Effect |
|---|---|
| `columns` | Only these columns, such as `"A:D"`. Every row then has exactly these columns. |
| `skip` | Skip this many rows from the top. |
| `limit` | Stop after this many rows. |

`iter_batches(size)` returns lists of rows. Each iterator reads its own stream,
so several iterators can run at once.

## Write

`Writer` spools each row to a temporary file, so memory stays small for any
number of rows. Rows go in order and cannot change after you write them.

```python
import crabxl as xl

with xl.Writer.create("export.xlsx", compression=1) as writer:
    sheet = writer.worksheets.add("Events")
    sheet.freeze_panes = "A2"  # Set before the first row.
    sheet.columns("A:C").width = 16
    sheet.append(["id", "kind", "amount"], style=xl.Style(font=xl.Font(bold=True)))
    sheet.extend((n, "sale", n * 1.5) for n in range(1_000_000))
    sheet.merge("E1:F1")
```

The writer finishes when the `with` block ends. If the block raises an
exception, the writer discards its output and does not touch the target. A
path target is replaced atomically. Several worksheets can be open at once:
`writer.worksheets["Events"]` returns an open sheet.
