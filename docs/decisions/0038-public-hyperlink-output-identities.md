# Public hyperlink output identities

Ordinary owned and loaded saves prepare output relationship identities for
existing public hyperlink views, then update their `id` fields only after the
output save succeeds. Updates follow native workbook/declaration order, including
shared public objects. Location-only declarations receive no relationship ID.
Write-only live metadata remains separate pending work.

The native adapter validates requested sheet ownership, selects canonical
declaration owners and sorts coordinate-only queries. A borrowed native visitor
returns identities in actual output order. Compact ranges match only requested
views; neither their cells nor their URLs are expanded. The selection allocates
bounded query/result vectors and reserves identifier payload bytes against the
shared source/model allowance. Source planning includes that workspace charge.

Public ID assignment bypasses live field synchronization, retaining canonical
source identity hints and avoiding an extra metadata edit after save. Workbooks
without hyperlink views skip identity selection. Further measured save-path
integration and alias transaction scaling remain performance dependencies.

The adapter pins published core revision
`630acb9d485808ff6d73b2b3b4b96e5d032b40b0`. Rust 1.99 library compilation and Ruff
format/check pass. Identity, repeated-save, shared-object and failure assertions
will be consolidated with the rest of A11 before publication.
