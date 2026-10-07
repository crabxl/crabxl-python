# Editable rich-value views

Status: usable W13 checkpoint; consolidated A11 acceptance remains open.

The adapter pins published core revision
`ccb3ef0411951645466ce6048298d3b7f74dc5c2`.

`load_workbook(rich_text=True)` now selects canonical native rich parsing.
`cell.rich_text.CellRichText`/`TextBlock` and `cell.text.InlineFont` adapt display
runs and shared run-font fields. Rust owns values, pronunciation metadata, font
identity validation, storage and serialization. Python retains only caller-held
views and weak registrations; it does not implement a second string codec.

List, text, font and nested color mutation updates all current bound coordinates.
Native failure restores the changed UI field/list and previously updated owners.
The resource scenario covers failure in a later owner and successful retry.
Native overwrites detach old registrations, while structural movement relocates
held views. Registrations use weak owner dictionaries and coordinate sets;
shared objects/fonts avoid repeated owner-list scans. Ordinary append preserves
held object binding. Write-only append snapshots and counts nested payload bytes.

Ordinary and read-only shared strings honor the rich flag; read-only inline values
use the observed openpyxl 3.1.5 plain projection. Rust supports independent inline
preservation. Shared-string RAM/disk selection uses existing resource options.
Phonetic metadata remains native and is retained through typed edits with valid
imported font identities, even though the reference public rich list drops it.

Native row projection defers live rich/structured values instead of converting a
payload twice. `src/worksheet/rows.rs` owns that borrowed projection;
`src/rich_text.rs` maps typed records. Scalar conversion and font validation remain
shared. Complete XML-tree utility APIs, copied-sheet rich alias semantics and
remaining consolidated structural acceptance are still tracked work.

Run input reuses immutable cached native font components; trusted output shares
font/color materialization and preserves public boolean defaults. User input still
uses canonical validation. Shared-value/font observation uses weak dictionaries
instead of repeated owner-list scans. Core measurements report creation, typed
load/scan, editing, output and RSS separately, with remaining costs explicit.

The CPython 3.12 development wheel passes 552 cases, Ruff check/format and strict
native Clippy. Shared scenarios include nested/shared mutation, row relocation,
source preservation, repeated saves, disk SST, inline/SST read-only behavior,
write-only snapshots and openpyxl reopening. This does not claim the full rich
public module or A11 gate is complete.
