# ADR 0020: Loaded display order

Ordinary loaded `Workbook.move_sheet` applies the existing public-reference
offset/list-insertion normalization and asks the canonical preserving owner to
commit the selected stable sheet identity's new position. The native operation
releases the GIL during metadata validation. Only after success does Python
reorder its worksheet views; its active index remains unchanged, matching
openpyxl 3.1.5. All source declarations, budgets, affected-graph guards and save
behavior belong to core, without a second spreadsheet model in Python.

The adapter pins core `31cfbee25dc5715088468451115ab888e28ac57a`. Existing shared
loaded edit workflows verify renamed sheets, retained cell aliases, pending
edits/append, active-index behavior, explicit active selection and repeated
openpyxl readback in the new order. The preserving-content workflow checks
atomic rejection of local defined-name reorder while retaining images, comments,
styles, unknown parts and the original local-name expression after rename.
Local owner-index remapping stays tracked as a deferred M4/M5 dependency.

All 547 tests, Ruff format/check and strict Clippy pass using a fresh release
Python 3.12.14/Rust 1.99 wheel. Core release bounded metadata, save and full value
readback measurements are in
[ordering evidence](https://github.com/crabxl/crabxl/blob/main/benchmarks/alpha7-lazy-reordering.md).
This checkpoint does not complete A7 or publish a new package version.
