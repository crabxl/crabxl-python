# Named styles and live sparse dimensions

Status: initial W11 adapter checkpoint; consolidated A11 is not released.

The adapter pins native commit 7693aaadd24056f8f81791be1a877993d19d3ff7.
NamedStyle builders register canonical shared component and base-format IDs.
Bound top-level appearance edits affect future applications while previously
styled cells retain their appearance. Name, builtin and hidden metadata updates
use the canonical registry; rejected edits restore the Python builder field.
Detached cells retain local style snapshots and cannot recreate deleted cells
through named-style assignment.

RowDimension and ColumnDimension views access sparse native worksheet records.
DimensionHolder keeps weak aliases, not a second metadata model. Grouping is one
bounded native operation; removed aliases detach only after successful mutation.
Pending caller-created dimension objects retain their small public metadata until
registration. Number formats and the five appearance components use canonical
style interning. Missing mapping queries/removals do not create native records.

Normal loaded mode uses the source-backed workbook coordinator. Write-only mode
uses the live sequential spool's metadata: column settings must precede the first
row, row settings must precede that row's flush, and metadata-only trailing rows
are serialized on close. Unsupported late edits raise rather than disappear.
Loaded theme bytes replace the existing relationship target; None restores the
native standard theme on serialization. Missing source theme relationship
creation remains a named graph gap.

Focused owned/loaded/write-only checks generated files and reopened them with
openpyxl 3.1.5, including repeated saves, sparse row grouping, column alias
detachment, future named appearance changes, rename rollback and theme reset.
Complete public compatibility, merge geometry, hyperlinks, editable rich text
and representative full-group profiling remain A11 release gates. In particular,
raw style-array adapters and extended row descent serialization are not yet
implemented; no alpha version/tag is created for this checkpoint.
