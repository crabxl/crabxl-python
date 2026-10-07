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

Core `b5990868623e31b8cc3e47f4ba3bf0f906e54865` adds byte-oriented XML
escaping (core ADR 0079) without changing the binding's value model. Fresh-wheel
compatibility remains 547 passing cases; Python write-only regression measurements
include conversion/save and independent full-value readback. Their small numeric
differences are not described as a broad writer speed improvement.

Core `d944e766ac397ea0969180c886a8affb565badc7` removes arbitrary default
model cardinality caps (core ADR 0080). Coordinate bounds, byte budgets and
explicit caller count limits remain enforced. A freshly rebuilt wheel passes
all 547 compatibility cases, Ruff formatting/checks and strict Clippy. The
reported NYC workbook is unavailable locally, so this is not a measured claim
that its complete model fits a particular memory budget.

Released core `f08b8e6d494e575ba39289dde4895b7a9b648242` additionally integrates
descending block packing and capacity-aware model/growth reservations (core ADRs
0081-0082). Partial deletion shrinks only within operation headroom; explicitly
bounded banks retain capacity honestly when shrinking must be skipped. Native
functional probes support one million numeric cells under 64 MiB and row insertion
under 384 MiB. Python uses the canonical resource accounting directly.

The final `0.1.0a8` wheel passes 547 compatibility cases, Ruff and strict Clippy.
Two existing resource fixtures retain their atomic failure, retry, alias and source
checks with capacities appropriate to the new ledger. Complete numeric/unique-text
Python measurements, exact preview-wheel identities and remaining limits are in
[the A8 verification report](../benchmarks/alpha8-python-acceptance.md).

## Source module boundaries

The public `python/crabxl/__init__.py` only composes exports. Compatible objects
live in `cell/cell.py`, `worksheet/worksheet.py` and `workbook/workbook.py`;
`workbook/loader.py` selects loading modes and owns loading cleanup. `_values.py`
shares scalar conversion and coordinate adapters. Existing public import paths
remain available, including `WriteOnlyCell` in both cell modules.

The native `src/lib.rs` registers Python classes and functions. `workbook.rs`,
`worksheet.rs`, `reader.rs` and `editor.rs` implement the respective handle
contracts. `values.rs` shares conversion, synchronization and error mapping;
`functions.rs` adapts formula/address/resource/save entry points. `rich_text.rs`
adapts canonical runs and pronunciation records; `worksheet/rows.rs` owns borrowed
row projection and deferred live-value conversion. Existing
`streaming.rs`, `resources.rs`, `dimensions.rs`, `styles.rs` and `style_owners.rs`
remain dedicated adapters. `imports.rs` contains adapter imports only. No module
implements a second spreadsheet engine.

Dependencies flow from Python views to native handles and then to the pinned
Rust core. Module registration is composition; workbook ownership, model data,
resource accounting and codecs remain canonical in Rust. Shared Python helpers
import neither workbook nor worksheet objects, avoiding initialization cycles.

Use 300–600 lines as a practical review target and inspect files exceeding
800–1,000 lines for mixed responsibilities. These are guidelines, not hard
limits or a reason to introduce numbered fragments or extra runtime wrappers.

Point hyperlink views adapt canonical native metadata and preserving source edits.
Sparse public object retention preserves live identity; XML/relationship edits
stay in core. See [ADR 0031](decisions/0031-canonical-point-hyperlink-views.md) for
resource costs and unresolved full compatibility gates.
