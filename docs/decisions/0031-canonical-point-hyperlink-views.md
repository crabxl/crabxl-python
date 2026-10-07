# ADR 0031: canonical point hyperlink views

Status: implemented point checkpoint; complete W13/A11 acceptance remains open.

NativeSheet converts one optional point record and dispatches mutation to the
canonical standalone worksheet, aggregate bank or LoadedWorkbook preserving
coordinator. The adapter pins published core e74d865a65c82027b818f3780b63574ac08a48b6.
Relationships and XML package edits remain in Rust; no Python graph engine exists.

Cell.hyperlink accepts a string, Hyperlink or None. Empty strings create empty
targets rather than delete metadata. Live target/location/tooltip/display/id
changes synchronize to the canonical record, restoring earlier owner updates if
another update fails. Clearing retains the cell value. Sparse strong view retention
keeps assigned public identity after callers release references; views use weak
worksheet bindings so detached objects do not independently retain workbooks.
Only requested/assigned points have public view objects. These Python object costs
are visible in process RSS, not part of the native model byte ledger.

Hyperlink and HyperlinkList expose public field/XML conversions. Targets are not
serialized hyperlink attributes, and equality follows serialized fields. XML
helpers do not edit workbook parts. Native binding registration stays composed
in the single PyO3 method table; conversion/dispatch is in worksheet/hyperlinks.rs.

Two focused tests cover a complete point lifecycle/source-copy/repeat-save path
and public XML reference behavior. A rebuilt wheel passes 554 compatibility cases,
Ruff and strict Clippy. [Measurements](../../benchmarks/alpha11-point-hyperlinks.md)
include Python object conversion and complete source edit/save.

Live ref relocation and shared objects with different anchor references explicitly
raise NotImplementedError. Compact range declarations, normal-load blank-anchor
binding, detached cell views, post-save generated id visibility and complete
structural/alias acceptance remain tracked A11 dependencies. Read-only/write-only
hyperlink surfaces are not implemented by this checkpoint. No A11 release is made.
