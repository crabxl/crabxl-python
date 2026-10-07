# Standalone multi-range views

`crabxl.worksheet.cell_range.MultiCellRange` accepts coordinate strings and
iterables of public CellRange objects. It exposes mutable standalone range sets,
containment, add/remove, sorted output, equality and copy operations. All rectangle
parsing, containment and coordinate transformations use the existing native
geometry functions through CellRange; this is a public object container rather
than a second workbook model.

Standalone containers retain the public range identities supplied by callers.
They have no worksheet owner and cannot silently modify workbook geometry.
Worksheet-bound merged declarations remain separately coordinated native views;
their raw membership and coordinate mutations are a remaining A11 integration
gate. Standalone support does not imply that gate has passed.

Ruff formatting and checking pass. Behavioral acceptance is deferred to the
single consolidated pre-release stage after all A11 implementation is complete.
