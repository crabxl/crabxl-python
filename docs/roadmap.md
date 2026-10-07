# Python compatibility roadmap

Source modules follow the [adapter architecture](architecture.md#source-module-boundaries); modularization retains the planned functionality and release numbering.

## Planned release stages

Follow the canonical [Alpha.6 and later release plan](https://github.com/crabxl/crabxl/blob/main/docs/alpha-6-and-later-plan.md):

- **A6:** urgent large/stream-generated archive compatibility; default archive byte caps removed, explicit finite caps retained.
- **A7:** M4 loaded bank/resource integration, existing-file sheet mutations,
  append and row/column structural operations for supported content.
- **A8:** measured read/write/edit and Python binding performance backlog.
- **A9/A10:** published style assignment/temporal formats and complete cell appearance components.
- **A11:** named styles/themes, row/column styles, merges/dimensions/outlines, hyperlinks and editable rich text.
- **A12:** remaining M5 features and complete M5 acceptance.
- **A13:** images, anchors, chart families/chartsheets and loaded drawing graph edits.
- **A14:** pivots/cache records, external links, macro/template policies and complex metadata.
- **A15:** complete M4/M6 feature integration and acceptance.
- **A16:** full-feature performance/RAM work and M7 compatibility/platform/release quality.

On 2026-10-07 the user approved approximately six remaining publications.
The complete scope of the former A11–A28 targets is retained as work packages.
Implement coherent feature groups before concentrating missing tests and fixes;
retain the relevant acceptance gates before each publication.

The user selected staged M4 acceptance. A7 must reject affected unimplemented
M5/M6 graphs before mutation and retain their dependency cases for later feature
releases. Its M4 stage can be accepted without claiming full graph support or full
M4 closure. Core implementation alone does not complete a Python capability.
Each package release pins the verified published core revision and passes the
applicable public-reference, resource/cleanup, Ruff, and platform wheel checks.
Alpha.6–Alpha.10 are published and verified from public registries. A11 named styles, themes and row/column appearance are in progress; later targets remain planned.
The consolidated [Alpha 9–28 scope and publication plan](https://github.com/crabxl/crabxl/blob/main/docs/alpha-9-28-plan.md) supersedes the previous single-release M5 target.

Loaded scalar/formula row append now uses canonical atomic model/package
updates and is covered by the shared public-reference edit/save workflow.
Supported loaded row/column insertion/deletion and range moves now coordinate
canonical cells, live aliases and preserving repeat saves (ADR 0021). Affected
unimplemented M5/M6 graphs reject atomically; the remaining A7 gates stay open.

Loaded `Worksheet.title` now supports lazy/materialized rename, reference suffix
selection and repeat preserving saves (ADR 0019). Loaded `Workbook.move_sheet`
uses canonical bounded display-order updates and deferred active-index semantics
(ADR 0020). Affected local defined-name owner remapping remains a deferred M5
dependency. Sheet creation/copy/removal and remaining affected feature-graph
dependencies stay tracked before staged A7 acceptance.

Alpha.5 adds canonical resource/SST/Auto controls and test consolidation, and
pins the verified M2 core acceptance revision. Core M2 closure does not imply
complete Python compatibility. Ordinary, write-only and loaded-edit save routes
retain alpha.4 compression policies without a binding ZIP codec.

Ordinary `iter_rows(values_only=True)` batches native conversion one row at a
time, retaining live structured formulas and edits between rows. Same-mode
numeric measurements are recorded in
[values iteration evidence](../benchmarks/values-calls.md). Scalar `read_only` and `write_only` modes now use bounded canonical streams;
see [stream ownership](decisions/0014-optimized-stream-ownership.md).

Target: openpyxl 3.1.5 public calls, mental model and observable behavior. Core capabilities remain governed by the CrabXL M4-M7 roadmap at https://github.com/crabxl/crabxl/blob/main/docs/roadmap.md.

Current acceptance is partial: 547 tests, including 63 unchanged original test bodies, cover supported owned scalar/date/ISO and normal/shared/array/data-table formula models and lazy preserving edits. Typed style editing and rich-string Python objects, loaded structural/feature editing, complete optimized-mode styles, file-like I/O, tokenizer and all advanced baseline features remain required. This is not full-suite compatibility.

Pin and validate the core revision before updates. Shared reference assertions and separate extension tests should evolve independently. Python is first priority; Node and WASM later share an ExcelJS-compatible interface.

Plain shared strings and inline literal-pattern workflows now use core revision dd38e85 with explicit empty-SST save preservation differences. Loaded component allowances are separate; full rich text, date/style catalogs and aggregate loaded budgets remain incomplete.

The adapter now pins core 512a958 for default rich display-text projection and unchanged-run preservation. Typed rich_text=True remains an explicit unsupported mode; compatibility classes/conversion are not claimed from the core model alone.

Structured formula objects match public constructor fields and loaded XML flag spelling. Attribute edits route through canonical Rust values, and bindings use weak worksheet ownership so formula views do not keep a closed workbook alive. Original physical array/table targets support repeated saves; shared-group replacement, typed cm/vm graph editing and dependency-aware group moves remain staged. Optional ArrayFormula text presence and literal/source body conversion are verified; the full array_formulae worksheet mapping remains staged; this checkpoint does not claim complete formula APIs.

Nonfinite owned numbers are retained until save; NaN/infinity serialize as blank numeric values through the canonical default core policy. Scientific overflow lexemes load as infinity, including formula caches. Public normal/cache-only readback and original-cell edits are tested against the pinned reference.

Core revision 7e9eb8db (post-alpha.1 source with Windows same-path save replacement, quick-xml 0.42 and streaming APIs) is pinned for canonical style/default-theme serialization, visible annotated-value projection, compatible cache-only reads and formula attribute write policies. Public tests compare every data-table field after creation and loaded-property edits, including false/source-string flags and empty input omission. These capabilities live in core; the adapter adds no duplicate codec. Owned theme/style Python properties, complete rich text and loaded structural editing remain staged.

Array formula literal text and optional range properties use canonical Rust conversions. Forty additional public comparisons cover None/empty/equals/non-equals/Unicode text, missing array references, loaded property updates and repeated saves. None data-table reference reload remains a recorded reference defect, not a native crash requirement. See ADR 0008 and benchmarks/array-calls.md.

Owned temporal value replacement retains canonical format IDs and supports repeated default-catalog saves (ADR 0012). General Python style object APIs and arbitrary source-catalog save integration remain required.

Literal shared-formula group identities, including absent, empty, padded, signed, opaque and escaped IDs, now match public ordinary/data-only loading; normal-mode unchanged saves are repeatable. Core worksheet views and printing exist at this pin, but their Python property proxies remain staged. See ADR 0013 and benchmarks/shared-identity-calls.md.

Optimized-mode and current ordinary performance evidence: [numeric and Unicode workloads](../benchmarks/optimized-modes.md).

Alpha.5 exposes canonical read resource limits, Auto tuning,
SST RAM/disk/Auto policies, decoded cache/temp bounds and loaded patch caps.
Read-only workers inherit those settings. Creation accepts Auto tuning separately;
compression remains per-save. This is a verified resource extension checkpoint,
not aggregate loaded-bank accounting or complete Python compatibility (ADR 0016).

Alpha.5 publication and fresh public installation are complete; see
[release evidence](validation/alpha5-release.md). All 25 wheels and the sdist
are verified. Core M2 acceptance is closed; full adapter compatibility remains staged.

Ordinary loaded worksheets now share the canonical source-backed bank, imported
style identities and aggregate source/model/overlay/SST accounting (ADR 0017).
Pending edits update cached models without repeated binding-owned overlay clones.
Supported source-backed cell structure is verified in ADR 0021; loaded sheet
creation/copy/removal and the remaining feature-graph gates stay open before A7
acceptance.

Worksheet visibility and deferred signed active views now use canonical core
coordination across owned, loaded and write-only workbooks (ADR 0018). Metadata
edits save without materializing source cells; read-only visibility remains a
snapshot without a save route. This checkpoint does not complete A7 M4.

Loaded worksheet creation, copy and removal now share the canonical bank and
package transaction (ADRs 0022-0024), including live/detached aliases and repeated
saves. Unsupported graph owners remain explicitly staged for M5/M6. Final A7
compatibility/resource/platform acceptance and publication remain open.

A7 staged M4 evidence is consolidated in the canonical core's
`docs/validation/alpha7-m4-stage-acceptance.md`. The adapter pins its exact A7
release revision and passes a fresh CPython 3.12 release-wheel run (547 tests),
Ruff format/check and strict native Clippy. A7 public multi-platform publication is verified in the core audit; the deferred M5/M6 graph interactions still keep full M4 open.

The selected M5 formula-token checkpoint now exposes Rust-backed Token/Tokenizer
objects and live translator token mutation. Existing shared assertions cover
selected lexical factories/rendering and malformed cases; complete tokenizer edge
auditing and all other assigned M5 features remain open. See
[the measured token-tool decision](decisions/0025-borrowed-formula-tokens.md).


A9 adds live `Cell.number_format`, `style_id`, `has_style` and format-aware
`is_date`, plus explicit `WriteOnlyCell.number_format`. Rust derives shared
formats without replacing unrelated appearance components. New model saves now
export their canonical catalog; loaded edits use guarded source models and
relationship-resolved stylesheet rewrites. Retained deleted/overwritten cell
views keep their value/format snapshot. Complete component APIs remain A10 work.
Signed/unknown style sections, sources without a stylesheet and affected
unmodeled source graphs retain explicit errors. A9 publication is pending.
