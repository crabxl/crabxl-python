# ADR 0021: Loaded cell structure

## Decision

Delegate loaded insert_rows/delete_rows/insert_cols/delete_cols and move_range
(including translate=True) to the canonical preserving coordinator. Reuse the
same Python Cell alias updates as owned worksheets, applying them only after
the native operation succeeds. Reject affected unsupported graphs in Rust before
changing cells or aliases; remove the blanket existing-file rejection for these
now-verified operations.

The first native structural edit retires that sheet's coordinate overlays and
uses the same canonical bank for later edits, append and preserving repeat saves.
Shared source catalogs and original assets stay owned by that source-backed
workbook. No Python transformation engine, cell-model copy or fallback is added.
GIL release remains around native structure operations.

Supported structural output retains original style IDs and unrelated parts,
updates existing dimensions, preserves empty append extent, and invalidates
formula caches through the core policy. Insertion/deletion and ordinary moves do
not update unrelated formula/name/view expressions automatically. Translated
moves change only relative references inside the moved normal formulas.

Affected row/column formatting, rich/phonetic SSTs or inline runs, structured
formula groups, cm/vm, merges, hyperlinks, tables/rules, drawings and extensions
remain explicit M5/M6 dependencies. Data-only structural editing is unsupported.
Loaded sheet creation/copy/removal and remaining A7 gates stay open.

## Verification

Extend the existing shared loaded numeric/edit workflow without adding a test
function: inserted/deleted row/column alias coordinates, translated moves, later
scalar edits/append and repeat-save openpyxl readback. Extend the existing
style/image/comment/opaque fixture to verify structural rejection preserves its
Cell alias and allows subsequent scalar edits and repeat saves. Run all 547
compatibility/resource tests, Ruff format/check and strict Clippy against the
published pinned core. Core tests and native workflow measurements remain
separate evidence from Python parsing performance.
