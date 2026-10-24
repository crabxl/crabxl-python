# Rich XML tree utilities

`CellRichText.to_tree`, `CellRichText.from_tree` and `TextBlock.to_tree` convert
between public XML elements and canonical rich values through the native
standalone XML codec. Python only serializes or materializes the caller's tree;
Rust interprets text runs, fonts and phonetic records under the existing limits.
Bare public inline/shared-string roots acquire the spreadsheet namespace for
native parsing without mutating the caller's element. Standalone output is
projected back to the public bare element spelling.

The adapter pins published core revision
`8107b4df12951c1acfe243147f21a54a2b7fb872`. Rust 1.99 library compilation and Ruff
format/check pass. Utility compatibility, edge-case projections and round trips
remain part of consolidated A11 release acceptance, not an intermediate test run.
