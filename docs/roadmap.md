# Python compatibility roadmap

Target: openpyxl 3.1.5 public calls, mental model and observable behavior. Core capabilities remain governed by the CrabXL M4-M7 roadmap at https://github.com/crabxl/crabxl/blob/main/docs/roadmap.md.

Current acceptance is partial: 365 tests, including 63 unchanged original test bodies, cover supported owned scalar/date/ISO and normal/shared/array/data-table formula models and lazy preserving edits. Typed style editing and rich-string Python objects, loaded structural/feature editing, optimized modes, file-like I/O, tokenizer and all advanced baseline features remain required. This is not full-suite compatibility.

Pin and validate the core revision before updates. Shared reference assertions and separate extension tests should evolve independently. Python is first priority; Node and WASM later share an ExcelJS-compatible interface.

Plain shared strings and inline literal-pattern workflows now use core revision dd38e85 with explicit empty-SST save preservation differences. Loaded component allowances are separate; full rich text, date/style catalogs and aggregate loaded budgets remain incomplete.

The adapter now pins core 512a958 for default rich display-text projection and unchanged-run preservation. Typed rich_text=True remains an explicit unsupported mode; compatibility classes/conversion are not claimed from the core model alone.

Structured formula objects match public constructor fields and loaded XML flag spelling. Attribute edits route through canonical Rust values, and bindings use weak worksheet ownership so formula views do not keep a closed workbook alive. Original physical array/table targets support repeated saves; shared-group replacement, typed cm/vm graph editing and dependency-aware group moves remain staged. Optional ArrayFormula text presence and literal/source body conversion are verified; the full array_formulae worksheet mapping remains staged; this checkpoint does not claim complete formula APIs.

Nonfinite owned numbers are retained until save; NaN/infinity serialize as blank numeric values through the canonical default core policy. Scientific overflow lexemes load as infinity, including formula caches. Public normal/cache-only readback and original-cell edits are tested against the pinned reference.

Core revision a3d957f is pinned for canonical style/default-theme serialization, visible annotated-value projection, compatible cache-only reads and formula attribute write policies. Public tests compare every data-table field after creation and loaded-property edits, including false/source-string flags and empty input omission. These capabilities live in core; the adapter adds no duplicate codec. Owned theme/style Python properties, complete rich text and loaded structural editing remain staged.

Array formula literal text and optional range properties use canonical Rust conversions. Forty additional public comparisons cover None/empty/equals/non-equals/Unicode text, missing array references, loaded property updates and repeated saves. None data-table reference reload remains a recorded reference defect, not a native crash requirement. See ADR 0008 and benchmarks/array-calls.md.
