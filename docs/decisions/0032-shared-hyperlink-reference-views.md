# ADR 0032: live shared hyperlink reference views

Status: implemented point alias checkpoint; complete A11 acceptance remains open.

The adapter pins core 3754bb8ec8e35fd7ed4b0ab24f8e3629cc751152 for independent
serialized declaration references and bounded last-declaration capture. Native
conversion adds one optional reference field. Ordinary matching owner references
use None in the canonical model, avoiding extra coordinate strings and preserving
its no-independent-reference intersection path.

A live ref update synchronizes all retained owner bindings without relocating
physical cells. Assigning one Hyperlink to another cell changes its ref for existing
aliases, fills the new empty anchor normally, and retains public identity. Other
field mutations update those same aliases while preserving physical values.
Failures restore the public field and previously committed owner metadata. This
uses existing core transactions; it adds no Python XML/package editor.

The existing lifecycle scenario now verifies loaded ref mutation, shared assignment,
field synchronization, invalid-range rollback, independent copied-sheet metadata,
and source repeat save. Independent openpyxl and CrabXL readbacks agree that the
last duplicated declaration owns the saved target. All 554 compatibility cases,
Ruff and strict Clippy pass after rebuilding the exact-pin wheel.

[Ordinary point measurements](../../benchmarks/alpha11-hyperlink-references.md)
show no broad speedup claim. Synchronizing many shared owners currently takes time
proportional to alias count, and constructing repeated aliases can be quadratic;
canonical shared payload/group transactions remain a performance dependency.
Finite ranges, imported empty-anchor values, detached views, write-only metadata,
generated id visibility after save and complete structural acceptance remain open.
The read-only public reference does not expose hyperlink on ReadOnlyCell, as verified
through public behavior; no artificial read-only hyperlink API is required.
