# Live write-only hyperlink views

WriteOnlyCell exposes the same public Hyperlink object and string assignment
surface as normal cells. Empty values initialize through the common native rule.
Appending assigns actual row/column coordinates and binds the hyperlink to a
writer-local group; row values remain immediate snapshots.

Hyperlink field updates coordinate ordinary cell aliases and write-only groups
through native metadata operations, retaining bounded native snapshots for
rollback. Write-only groups are shared by public object identity within a
workbook. The workbook keeps only weak observations of live public objects;
released objects leave no per-row Python metadata cache. Their native disk-backed
payloads/events remain sufficient to produce the final package.

Saving evaluates current metadata, including groups used in closed sheets, and
returns final IDs only for caller-visible groups. Public IDs change only after
successful output replacement. Finished/closed write-only owners no longer
participate in later object edits. Unlinked rows keep their original append path.

The adapter pins published native revision
`b4d1e3ed64616f531eed36f5283575a5e138b6eb` (core ADR 0100). Streaming read workers
and sequential writer adapters now live in separate Rust modules. Rust 1.99
library compilation and Ruff formatting/checking pass. No new tests or timing
measurements were run during implementation; alias, resource, I/O failure and
interoperability acceptance remains part of the consolidated A11 release gate.
