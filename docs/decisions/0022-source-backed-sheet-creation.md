# ADR 0022: Source-backed worksheet creation

Status: implemented; loaded copy/removal remain pending.

`Workbook.create_sheet(title=None, index=None)` delegates loaded creation to the
canonical Rust bank pinned at `579b4a487d1ff0bdfd6c2be22b01afaf02e01d50`.
Python normalizes names and insertion indexes, then retains the new stable native
handle in an existing-file worksheet view. Cells, append, structural edits,
visibility and title changes use the same owner as original source sheets.

No second native workbook or worksheet engine holds the newly created data.
Saves coordinate workbook declarations, relationships, content types and borrowed
row encoding in core. Affected unimplemented source policies and local-name
ownership graphs remain explicit errors. New typed-date style registration,
loaded sheet copy/removal and staged A7 acceptance remain open.

The shared loaded numeric workflow runs against both crabxl and pinned openpyxl
3.1.5. It covers indexed creation, live cell aliases across insertion, append,
formula values, escaped titles, visibility, active selection, global-name
preservation and repeated openpyxl readback. All 547 current tests pass; Ruff
format/check and native Clippy pass. No upstream assertions or fixtures were
copied for this original adapter coordinator.
