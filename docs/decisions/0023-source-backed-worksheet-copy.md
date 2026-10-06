# ADR 0023: Source-backed worksheet copy

Status: implemented for the staged supported subset; removal remains pending.

`copy_worksheet()` uses the canonical loaded bank pinned at
`8848a2727a293a99dedd4625ea4c9dcfecd009d7`. Python retains a stable new native
handle, validates same-owner membership and generates a compatible unique title.
The native copy includes current source edits and is independent of subsequent
source/copy edits. A requested copy is budgeted model duplication, not an engine
wrapper or rollback snapshot.

Public openpyxl 3.1.5 behavior makes copies visible even when their source is
hidden. Both registered-new and loaded adapters now apply that policy; core
retains its independent typed visibility semantics. Core streams supported
original property templates while omitting views and header/footer state.
Affected unimplemented feature graphs reject before registering a copy.

The existing shared loaded numeric workflow covers current edited values,
independence, hidden copies, copying a copy, active selection and repeated
openpyxl readback. All 547 current tests, Ruff format/check and native Clippy pass.
No upstream implementation or assertions were copied into this original adapter.
Loaded removal and staged A7 acceptance remain open.
