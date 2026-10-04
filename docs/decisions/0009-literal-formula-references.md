# ADR 0009: Canonical literal formula reference properties

The adapter pins published core 5ecb5bd6e032294d7c18ae461befe61f86d88b79 and converts reference strings to the core's literal FormulaReference rather than requiring geometry. Core alone handles string ownership, source codecs, compatible output and explicit physical validation. No language-layer parser or reference fallback is introduced.

Shared public tests cover array empty/absolute/worksheet-qualified/opaque references and fifteen table reference/input combinations. They check assigned values, save/reload and loaded-property edits through both engines. Empty compatible references/inputs are omitted; array reference reloads as None. The pinned reference's missing data-table reference reload defect remains documented in core ADR 0031; it is not made a required native crash.

All 403 tests pass using the installed locked release wheel. All 63 selected upstream original bodies and parameter sets remain unchanged, verified against the pinned source. New tests are original public API comparisons. Styles/rich objects, complete formula APIs and advanced loaded graph editing remain staged. See benchmarks/literal-reference-array-calls.md for measured supported same-call performance and sampling limits.
