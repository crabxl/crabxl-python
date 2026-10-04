# Python adapter architecture

The Rust core at https://github.com/crabxl/crabxl is canonical. This standalone repository contains PyO3 ownership/conversion adapters and an openpyxl-compatible Python object surface. It must not implement a second spreadsheet engine or silently fall back to openpyxl.

Cargo.toml pins the core Git revision. Compatibility tests and legal provenance live in tests and third_party. Rust models, validation, formulas, resources and XLSX codecs remain in core. Python view/cache and language argument/error mapping live here.

Registered new workbooks share the native aggregate sheet bank. Loaded models use the preserving original-package editor and separate per-model allowances. Compatibility and idiomatic extensions remain clearly distinguishable.

The core roadmap and feature inventory are authoritative: https://github.com/crabxl/crabxl/blob/main/docs/roadmap.md and https://github.com/crabxl/crabxl/blob/main/docs/features.json. See docs/binding-contract.md for all adapter priorities.
