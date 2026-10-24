# Canonical array text property compatibility

Cargo pins core 1ede2a445c9927dfa32289cf72eb734aa0fe3ea1. Literal array input maps to Formula::from_array_text and output maps to array_text(); an optional ref maps to the canonical optional range. The adapter does not cache a second formula expression or implement body slicing. Data-table expressions are canonically absent. All structured output includes a ref property, including None, so required public constructor calls retain optional source fields.

Verification: the locked release wheel is built/installed; formatting and warning-free Clippy pass; 365 tests pass, including 40 additional same-call array cases. Three provenance verifications retain 37/17/9 unchanged original test bodies and parameters (63 total). Cases cover None/empty/equals/non-equals/Unicode literal spelling, missing array refs, loaded edits, ordinary/data-only readback and repeated saves. Core public probes separately record the pinned missing data-table ref ordinary-reload defect; reproducing a crash is not required.

Complete array_formulae mapping, opaque formula reference strings, styles/rich/theme Python objects, loaded structural editing and all advanced baseline features remain required. Same-call Python performance is measured separately from native core benchmarks; see benchmarks/reports/array-calls.md.
