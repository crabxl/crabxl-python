# Imported hyperlink display values

Ordinary editable Python loading enables the native empty-value binding policy.
Existing values and queued explicit overrides remain intact; otherwise source
hyperlink targets/locations initialize display values. Later metadata edits retain
the initialized value. Read-only streams and cells retain their existing surface.

Initialization and serialization stay in Rust. Range metadata remains compact,
while required physical display cells belong to the explicitly materialized
normal model and share immutable string payloads. The existing resource settings
control that model. Source saves retain their guarded graph dependencies.

Overlapping source declarations now initialize values in original XML order;
later metadata updates retain the first initialized nonempty value. Destination-
free declarations retain logical extents without dense empty-cell allocation.
The extra bounded worksheet scan applies only to overlapping source declarations.
Write-only live metadata, raw merged declarations, standalone range sets and final
compatibility remain A11 gates.

The adapter pins published core revision
`857fd3877f7e56e7ce7b10b7514560a8c5ce20d1`. Rust 1.99 library compilation and
formatting pass. No new tests or performance measurements run during this
implementation stage.
