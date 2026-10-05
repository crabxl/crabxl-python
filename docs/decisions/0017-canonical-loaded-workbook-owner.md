# ADR 0017: One canonical owner for loaded Python workbooks

## Decision

Ordinary `load_workbook` now constructs the canonical Rust `LoadedWorkbook` from
one seekable shared file. `NativeReader`, `NativeEditor` and materialized
`NativeSheet` handles share its lifetime through an owner-scoped Arc/Mutex. Sheet
handles retain stable core IDs instead of independent standalone cell maps.
The editor no longer opens the original path again for this public load route.
Read-only workers keep their bounded streaming path and do not materialize bank
models.

Heavy source initialization, sheet materialization and saving release the Python
GIL. Source style ownership transfers into the core bank once; number-format and
date/active metadata borrow the same owner. Pending edits do not eagerly load a
sheet. Once loaded, model values stay synchronized by the core coordinator.
Python no longer repeatedly applies cloned overlays in `_model()`; structured
formula views and cell aliases continue to resolve the current canonical value.
Values-only loaded row conversion borrows the model without a mutation facade.

The existing resolved Python `max_memory_bytes` is the joint retained-data
ceiling for source catalogs/inventory, all registered models, preserving overlays
and SST/cache storage. Canonical I/O working space remains additional; construction
adds that reserve before passing the resolved budget to the core, avoiding a
second subtraction. Per-model limits still clamp individual sheets. Forced RAM
must fit alongside retained models; Auto may spill/shrink strings, and Disk uses
the same owned cleanup rules. Duplicate overlay/model payloads are conservatively
charged by the core. Python objects, caller-retained rows and process/allocator
costs remain outside these managed charges; this is not an RSS cap.

Closing either loaded native owner releases the shared model bank. Public workbook
close also closes the original source and stops streaming workers. Retained native
sheet handles then fail explicitly rather than keeping usable detached copies.
The private legacy `NativeEditor` construction/apply path remains available for
independent native editor callers; the public loaded route always shares its
reader's canonical owner and validates identities when explicitly applying.

## Acceptance and boundaries

The compatibility suite retains the original upstream test bodies. One added
resource workflow verifies two separately fitting worksheets that cannot fit
jointly, failed second-sheet loading/retry, cached native and public aliases,
pending edits before loading, two successful saves checked through openpyxl,
one actual source descriptor on Linux, closed handles, unchanged source bytes,
and adjacent ZIP cleanup. Existing RAM/Auto/Disk tests retain value and actual
temporary-handle assertions; forced RAM ordinary-mode fixtures now allow enough
space for both source and model. A one-byte per-sheet cap rejects even the stable
empty holder at construction.

This checkpoint pins published core `ea969d9ffc0b07497f3fec2dba016780c1403cee`.
All 545 CPython 3.12 tests, Ruff formatting/checking and Clippy pass locally.
Full multi-ABI/platform release gates remain required before A6 publication.
Loaded typed-date/style mutation, workbook/sheet and row/column structure still
require subsequent A6 checkpoints. Typed chartsheet/dialog models remain M6;
their original parts can survive unrelated worksheet edits through core
preservation, which is not typed access or full feature completion.
