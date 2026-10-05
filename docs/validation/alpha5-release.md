# Alpha.5 verified publication

Python `0.1.0a5` is published. Tag `0.1.0-alpha.5` points to
`5523e6c734286a5658007cc47bc3ddf973cf26d8` and pins canonical Rust alpha.5
`7efa37b10c6b19757ff58dbf930f9e233b3af7d4`. Tags and artifacts are immutable.

[Release Python alpha](https://github.com/crabxl/crabxl-python/actions/runs/37294935553)
and [Python compatibility](https://github.com/crabxl/crabxl-python/actions/runs/37294935699)
are successful. All 25 wheels (CPython 3.11–3.15 on five platforms) and the
independently tested sdist are public; PyPI upload uses OIDC. Ruff format/check,
Rustfmt and strict Clippy pass. Each platform reuses compilation across five ABIs.
See [artifact identities and installation evidence](alpha5-release.json).

A fresh CPython 3.12 environment installs only the public PyPI package. It
verifies ordinary/write-only creation, SST RAM/Auto/disk policies, bounded read
batches, Auto model allowance, loaded patch-limit failure/retry, source protection,
per-save compression and complete readback with no openpyxl installed. The
installed native/configuration files match the public wheel's bytes; wheel/sdist
hashes and the canonical source pin are checked. A model allowance excludes
canonical parser working reserve; maximum_bytes is an operation cap rather than
an all-component or process RSS limit.

Core M2 acceptance and public Rust 1.88 installation are verified in the canonical
repository's `docs/validation/alpha5-m2-acceptance.md` and `alpha5-release.md`.
Complete Python style/rich/feature proxies and remaining M4–M7 capabilities stay
planned. This is a verified usable release, not full openpyxl API compatibility.
