# ADR 0018: Canonical visibility and deferred active views

## Decision

Pin core `02f7c1ca4a7a0ed53eafc64c59ba509ce4730f23` and expose its
`SheetVisibility` and deferred signed active-view selection through the public
`sheet_state` and `Workbook.active` properties. Owned sheets use stable native
bank handles. Loaded changes use the preserving coordinator, which validates
unsupported metadata and reserves aggregate overlay space before mutation.
Write-only sheets use the same canonical writer states; Python retains only a
metadata snapshot. Read-only snapshots are editable views without a save route.

An integer active request is deferred until save and preserves signed indices,
hidden targets and out-of-range requests according to the pinned public
reference. Assigning a hidden worksheet object rejects immediately. Native
indices are signed 64-bit; this checkpoint does not claim arbitrary Python
integer/coercion compatibility. Successful saves return the normalized requested
index, which may differ from the active sheet after reloading omitted view
metadata. Repeatable owned and loaded saves retain their models and source.
Write-only save remains consuming and releases spools on preflight failure.

All-hidden output rejects before target replacement: one hidden sheet raises
`ValueError`, while zero or multiple sheets with no visible sheet raise
`IndexError`. Loaded visibility and the Python view request commit together in
core, preventing partial changes when source policy or budget checks fail.
Neither operation copies or materializes worksheet cells. Existing formula
caches, calculation chains, unrelated XML and binary assets remain on the
original source and survive metadata-only saves.

## Acceptance and boundaries

One shared public-reference workflow covers ordinary owned, loaded and write-only
workbooks, two/three sheets, negative/hidden/out-of-range requests, repeated
saves, output values, visibility and active-view reload. It also covers hidden
object rejection, all-hidden recovery, read-only snapshots and copy visibility.
Selected original upstream test bodies remain unchanged.

The existing aggregate resource workflow now verifies metadata edits and saving
with a 4096-byte per-model cap that prevents loading either real worksheet.
All-hidden save leaves an existing target unchanged and cleans adjacent files;
recovery saves preserve all 6000 values per sheet, while a cell read still raises
`MemoryError`. Failed materialization does not prevent a subsequent save.

The 547 local CPython 3.12 cases pass, along with Ruff, rustfmt and strict Clippy.
Canonical release measurements at 10,000/100,000 cells are recorded in core's
`benchmarks/alpha7-sheet-visibility.md` and `benchmarks/alpha7-active-views.md`.
They verify fixed overlay accounting, zero materialized cells and full output
values, and do not establish a speed improvement for this binding checkpoint.
Multi-platform/ABI publication gates remain required.

This is an A7 M4 checkpoint, not stage acceptance or a new release. Loaded
creation/copy/removal/rename/reorder, append and row/column transformations,
typed source date/style mutation and affected M5/M6 graphs remain open.
