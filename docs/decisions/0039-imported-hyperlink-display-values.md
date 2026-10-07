# Imported hyperlink display values

Ordinary editable Python loading enables the native empty-value binding policy.
Existing values and queued explicit overrides remain intact; otherwise source
hyperlink targets/locations initialize display values. Later metadata edits retain
the initialized value. Read-only streams and cells retain their existing surface.

Initialization and serialization stay in Rust. Range metadata remains compact,
while required physical display cells belong to the explicitly materialized
normal model and share immutable string payloads. The existing resource settings
control that model. Source saves retain their guarded graph dependencies.

Overlapping source declarations with empty values require original-order binding
and currently return explicit NotImplementedError. Already populated overlap
cases remain readable. This ordered-value case, write-only live metadata, raw
merged declarations, standalone range sets and final compatibility are still A11
work; this checkpoint must not be treated as complete acceptance.

The adapter pins published core revision
`497417f6d5fa776a86641b98714567956b04433f`. Rust 1.99 library compilation and
formatting pass. No new tests or performance measurements run during this
implementation stage.
