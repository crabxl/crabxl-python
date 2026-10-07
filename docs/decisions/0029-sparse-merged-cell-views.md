# Canonical sparse merged-cell views

Status: usable W12 checkpoint; consolidated A11 acceptance remains open.

The adapter pins core revision `5b4d018717b8295e2ec8efef5a597c3942d6b22a`.
Rust owns merged geometry, shared border/protection appearances, physical-cell
cleanup, resource accounting and source-backed output. Python exposes lazy
`MergedCell` views and high-level `merge_cells`/`unmerge_cells`; it does not expand
rectangles or retain a second merge index. Membership and iteration query native
geometry directly. Only held cell aliases are detached after a successful edit.

Merged values are read-only. Styles resolve through the canonical catalog.
Finite visible bounds include geometry while appending retains the separate
logical cursor. The live range collection rejects raw membership/coordinate
mutation explicitly; use the high-level worksheet operations. Affected structural
movement and complete detached range utility compatibility remain tracked work.

Loaded edits normalize source geometry under the shared budget and export newly
derived appearances on model rewrite. Plain load/save preserves source parts.
Pending source values remain accessible without materializing a sheet that cannot
fit the aggregate allowance. Deferred edits into covered cells reject on save.
Detached native worksheet storage is boxed so lightweight bank handles do not
carry the inline model's size.

The release-built, exact-pinned CPython 3.12 wheel passes 549 existing/new shared
cases, Ruff check/format and strict native Clippy. The two-engine merge scenario
covers owned/source-backed operations, borders, protection, retained aliases,
read-only values, unmerging, source preservation and repeated saves. This is
checkpoint evidence, not complete A11 or M5 acceptance.
