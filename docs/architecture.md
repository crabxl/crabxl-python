# Python adapter architecture

The Rust core at https://github.com/crabxl/crabxl is canonical. This standalone repository contains PyO3 ownership/conversion adapters and an openpyxl-compatible Python object surface. It must not implement a second spreadsheet engine or silently fall back to openpyxl.

Cargo.toml pins the core Git revision. Compatibility tests and legal provenance live in tests and third_party. Rust models, validation, formulas, resources and XLSX codecs remain in core. Python view/cache and language argument/error mapping live here.

Registered new workbooks share the native aggregate sheet bank. Ordinary loaded
workbooks share a canonical source-backed bank with stable sheet handles, one
preserving editor/source and joint model/catalog/overlay/SST allowances; see
[ADR 0017](decisions/0017-canonical-loaded-workbook-owner.md). Compatibility and
idiomatic extensions remain clearly distinguishable.

The core roadmap and feature inventory are authoritative: https://github.com/crabxl/crabxl/blob/main/docs/roadmap.md and https://github.com/crabxl/crabxl/blob/main/docs/features.json. See docs/binding-contract.md for all adapter priorities.

Optimized streams and ownership are described in [ADR 0014](decisions/0014-optimized-stream-ownership.md). The pinned canonical core uses quick-xml 0.42; the binding contains no duplicated codecs.

Resource extensions map immutable Python configuration to canonical Rust limits,
SST options and Auto controls. Both ordinary and optimized readers inherit the
same settings; no resource strategy is implemented in Python. Mode applicability,
original component allowances are documented in ADR 0016; ordinary loaded-bank
ownership and joint retained accounting now follow ADR 0017.
