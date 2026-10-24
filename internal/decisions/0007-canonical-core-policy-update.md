# Canonical core policy compatibility update

Cargo pins core 9a13237f06b349eef12ac2f358b4eee4c66f1d19. The adapter continues to use canonical Rust readers, models and serializers; no Python spreadsheet engine or reference fallback is added. Public save/reload comparisons cover every data-table property after creation and loaded edits, including assigned false flags, source string flags and empty input omission. Cache-only unknown-header projection and visible cm/vm scalar/array caches use the same Rust semantics.

Verification: release wheel built and installed from the locked revision; rustfmt and warning-free Clippy pass; 325 pytest cases pass. The three provenance verifications retain 37/17/9 unchanged original reference test bodies and parameters (63 total). New tests are independently written public API comparisons. Native core performance measurements are not Python same-call speed claims.

Typed style/rich/theme Python surfaces, cm/vm graph edits, array_formulae, optional ArrayFormula text presence and full loaded bank/structural acceptance remain incomplete. The complete baseline remains required.
