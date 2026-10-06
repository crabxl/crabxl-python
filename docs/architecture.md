# Python adapter architecture

The Rust core at https://github.com/crabxl/crabxl is canonical. This standalone repository contains PyO3 ownership/conversion adapters and an openpyxl-compatible Python object surface. It must not implement a second spreadsheet engine or silently fall back to openpyxl.

Cargo.toml pins the core Git revision. Compatibility tests and legal provenance live in tests and third_party. Rust models, validation, formulas, resources and XLSX codecs remain in core. Python view/cache and language argument/error mapping live here.

Registered new workbooks share the native aggregate sheet bank. Ordinary loaded
workbooks share a canonical source-backed bank with stable sheet handles, one
preserving editor/source and joint model/catalog/overlay/SST allowances; see
[ADR 0017](decisions/0017-canonical-loaded-workbook-owner.md). Compatibility and
idiomatic extensions remain clearly distinguishable.

Loaded `Worksheet.append` delegates to the canonical preserving coordinator,
which updates the model and package overlay atomically. Python normalizes row
iterables and column dictionaries, converts values, and releases the GIL for
the native operation. Empty rows advance the source-aware append cursor.
Unsupported source graphs/values remain explicit errors before mutation.

Loaded title changes use the same canonical preserving coordinator without
materializing cells or replacing native identities; see
[ADR 0019](decisions/0019-source-backed-sheet-title.md).

Loaded display reordering commits the canonical source-index permutation before
changing Python worksheet views. Signed active display indexes remain deferred;
affected local defined-name graphs reject atomically pending M5. See
[ADR 0020](decisions/0020-source-sheet-display-order.md).
The pinned packed model's numeric Python cost is recorded in
[paired measurements](../benchmarks/alpha7-packed-reading.md).

Loaded row/column insertion/deletion and range moves now use the canonical
preserving coordinator; Python updates existing Cell aliases only after success.
Later edits/append and repeat saves share that bank. Affected unsupported feature
graphs reject atomically; see [ADR 0021](decisions/0021-loaded-cell-structure.md).

Ordinary scalar values iteration now projects canonical ordered row cursors
directly into Python values, retaining live structured-formula objects. Cached
read-only rows avoid a GIL detach/attach cycle; blocking receives still release
the GIL. Both use one adapter conversion helper and unchanged bounded buffers.
The [calamine comparison](../benchmarks/alpha7-direct-values.md) records remaining
parser/model and conversion costs; neither mode meets the speed target yet.
Output tags borrow fixed native literals, while input tags retain owned caller
validation. The [paired adapter measurement](../benchmarks/alpha7-static-tags.md)
records small ordinary gains and no clear streaming gain, independently of core
namespace representation changes.

Worksheet visibility and deferred signed active-view selection use the canonical
core coordinator in ordinary loaded mode, the registered bank in owned mode, and
the streaming writer in write-only mode; see
[ADR 0018](decisions/0018-canonical-visibility-and-active-views.md). Metadata-only
loaded changes do not materialize cell models. Read-only visibility is a snapshot
view and cannot be serialized. Python maps the core's no-visible-sheet error to
`IndexError`; a single hidden sheet maps to `ValueError`.

The core roadmap and feature inventory are authoritative: https://github.com/crabxl/crabxl/blob/main/docs/roadmap.md and https://github.com/crabxl/crabxl/blob/main/docs/features.json. See docs/binding-contract.md for all adapter priorities.

Optimized streams and ownership are described in [ADR 0014](decisions/0014-optimized-stream-ownership.md). The pinned canonical core uses quick-xml 0.42; the binding contains no duplicated codecs.

The canonical default-namespace cache is verified through ordinary and read-only
Python values iteration; see [paired performance evidence](../benchmarks/alpha7-namespace-reading.md).

Resource extensions map immutable Python configuration to canonical Rust limits,
SST options and Auto controls. Both ordinary and optimized readers inherit the
same settings; no resource strategy is implemented in Python. Mode applicability,
original component allowances are documented in ADR 0016; ordinary loaded-bank
ownership and joint retained accounting now follow ADR 0017.

Loaded `create_sheet()` registers a model in the existing source owner and keeps
its stable handle in a Python worksheet view. New and original sheets share the
preserving save transaction; see [ADR 0022](decisions/0022-source-backed-sheet-creation.md).

Loaded `copy_worksheet()` delegates requested duplication and source-template
preservation to core and maps compatible visible-copy behavior in the adapter;
see [ADR 0023](decisions/0023-source-backed-worksheet-copy.md).

Loaded removal transfers the shared worksheet handle to its detached canonical
model after checked core disposal. Python dispatch changes only after success,
so title reuse cannot reconnect old cell aliases; see
[ADR 0024](decisions/0024-source-backed-worksheet-removal.md).

Physical-cell deletion on ordinary loaded worksheets calls the canonical guarded
Rust removal operation. Existing Python cell aliases retain the removed value,
while subsequent coordinate access creates an independent cell view. Aliases are
updated only after native success, so rejected affected graphs retain the original
view and value. Missing-cell removal leaves source XML and formula caches intact.

Linux Auto availability now follows canonical core ADR 0076: clean inactive
cgroup file cache contributes to estimated available capacity, while dirty,
writeback, active cache and shared-memory pages do not. The adapter adds no
separate detector. Explicit budgets and caller-supplied Auto availability keep
their existing behavior. A fresh wheel pinned to core
`3cfb8c4b2c08f360b32f060b6b34246e010cdb28` passes all 547 compatibility cases.

The adapter now pins core `bfeb2714dcea31f0facaa5c999547b071e7a55c8` for
bounded buffered scalar decoding (core ADR 0077). Python uses the same native
stream and loaded model; no separate scalar parser or compatibility fallback is
added. All 547 compatibility cases and Ruff/Clippy pass with a freshly rebuilt
wheel. Complete Python-operation measurements and remaining performance gaps
are recorded in [the A8 report](../benchmarks/alpha8-buffered-scalars.md).

Core `4f25c545684a03a879d717c27cf1bb91acd14676` additionally prepares simple
SST entries from bounded buffered XML (core ADR 0078), with direct canonical
shared ownership. Fresh-wheel compatibility remains 547 passing cases. Both
ordinary and read-only Python unique-text operations improve against A7 in
complete conversion-inclusive measurements; the report retains their scope.
