# ADR 0024: Source-backed worksheet removal

Status: implemented for the staged supported subset; final A7 acceptance pending.

`Workbook.remove()` and `del workbook[name]` use the canonical loaded bank pinned
at `da8ddd796506ca7c8b825ee7487edea8bb6a55f3`. A lazy native handle identifies an
unmaterialized sheet without decoding it before core ownership checks.

The native worker validates same-owner registration, removes under its owner lock,
and switches the shared worksheet storage to the returned standalone model.
Those locks are released before reacquiring the GIL. Python removes the worksheet
view only after success and switches that view to detached-cell dispatch.
Existing cell aliases keep that exact model; reusing its display title registers
a different identity and cannot reconnect the old view to source-name overlays.
Detached caller-retained models keep their own edit limits and separate costs.

Core retires package declarations, relationships, content types, source parts and
pending edits together. Source templates remain available for surviving copies.
Unknown/shared consumers, outgoing graphs, linked VBA projects, local-name scopes
and unmodeled workbook identity graphs retain explicit M5/M6 rejection.

The shared loaded numeric workflow compares openpyxl 3.1.5 removal/title-reuse,
detached aliases, original/new/copy removal, active selection, repeated readback,
empty-workbook save failure and recovery. The existing opaque style/image/comment
workflow verifies failed removal leaves its view/cell aliases and repeated
preserving saves usable. All 547 current tests, Ruff format/check and native
Clippy pass. No upstream implementation or assertions were imported here.
