# Detached hyperlink values

Deleting a cell transfers its canonical hyperlink alongside the removed value
after native source-graph validation. A retained public Cell keeps its already
requested hyperlink identity, or materializes one from the transferred fields.
The removed coordinate is retired from the worksheet view index. Detached cells
can read, assign, mutate and clear hyperlinks without recreating a worksheet cell.

Assignment to an empty detached cell uses the same native initial-value rule as
ordinary assignment. Python retains the caller's detached object only; the core
continues to own live worksheet metadata and range splitting. Shared hyperlinks
may retain other live owners through their existing weak registrations.

The adapter pins published core revision
`04080123d4107aeaef5e2975846fb4fa3b9c81ed`. Rust 1.99 library compilation and Ruff
format/check pass. Deletion/alias edge cases join the single consolidated A11
pre-release acceptance pass; no new tests are added at this checkpoint.
