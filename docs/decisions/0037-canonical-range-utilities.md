# Canonical range utilities

Public `CellRange` supports explicit bounds, worksheet titles, expansion,
shrinking, bounding union, intersection and containment/disjoint comparisons.
Geometric decisions and edge validation delegate to the shared Rust rectangle
API; public objects retain one-based coordinate and title fields. Invalid complete
adjustments fail before any fields are replaced.

Cell, row, column and edge projections enumerate coordinates only when requested.
The range object itself does not create worksheet cells. Compact merged views
reuse these utilities with an initialized public title; live declaration mutation
still requires its owner-aware coordinator rather than mutating a temporary set.

The adapter pins published core revision
`a82e7623c57edaaa644b160d2c8a07a30e16dcc8`. Rust 1.99 library compilation and Ruff
format/check pass. Public edge-case parity, standalone multi-range sets and live
merged-declaration integration remain tracked A11 acceptance dependencies.
