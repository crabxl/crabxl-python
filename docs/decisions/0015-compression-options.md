# Per-save compression controls

Workbook.save accepts the keyword-only compression_level extension in ordinary,
write-only and loaded-edit modes. None preserves level 6, integers 1 through 9
select Deflate and 0 selects ZIP Stored. Non-integers (including bool) and values
outside 0..9 reject before touching a target or consuming write-only resources.
Existing positional filename calls remain valid. Level selection is per save;
ordinary and loaded workbooks can use different levels on repeat saves.

The adapter forwards the setting to canonical WriteOptions, SaveOptions or the
stream writer's set_compression_level. It does not encode or compress XLSX itself.
Unchanged loaded parts retain their original compressed bytes. Row budgets,
worksheet spools, formula-cache invalidation, atomic target replacement and failure
cleanup retain their existing contracts. No level makes staged styles, structural
editing or file-like I/O available.

Published wheels select pure-Rust zlib-rs explicitly. Source builders may choose
native zlib with no default features and deflate-zlib, requiring a C toolchain.
The backend is fixed at build time; it is not selected by compression_level.
Cargo features are additive, so native-only builds must disable default features.

Two focused tests loop across supported modes and representative levels, checking
public openpyxl values, XML agreement, ZIP method, invalid-option target protection
and write-only retry. Canonical tests/benchmarks cover both backends and full-part
CRC/hash agreement; native timings are not claimed as Python end-to-end timings.
Higher levels do not guarantee smaller output. M2 and test consolidation remain
scheduled for alpha.5.
