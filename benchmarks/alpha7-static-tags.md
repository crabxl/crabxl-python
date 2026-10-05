# Borrowed native output tags

Native output uses fixed static tags instead of allocating a Rust String for
each encoded cell. Caller-supplied input tags remain owned and validated. Python
still receives the same str tags where exposed, direct scalar values in values
rows and the same temporal/structured-formula decoding behavior.

This comparison isolates the adapter change: both wheels pin canonical core
`31cfbee25dc5715088468451115ab888e28ac57a`. The separate compact-namespace
experiment is not included. Rust 1.99 release, Python 3.12.14, Linux x86-64,
two-CPU quota. One warmup and three rotating serial cold-process samples;
generation/build/tests excluded, imports and cleanup included. Exact counts and
checksums are verified. Installed native/Python source hashes identify both
development wheels, which retain the unchanged alpha.6 package version.

At 100,000 rows by ten numeric columns:

| Operation | Before wall (s) | After wall (s) | Calamine wall (s) | After RSS (KiB) | Calamine RSS (KiB) |
|---|---:|---:|---:|---:|---:|
| Ordinary editable load and values scan | 0.7371 | 0.7230 | 0.5306 | 51,972 | 87,736 |
| Read-only load and values scan | 0.6351 | 0.6379 | 0.5163 | 20,364 | 87,672 |

Ordinary values traversal is 0.0947 to 0.0894 seconds, about 6% lower; total
time improves about 2%. Parsing/model loading is unchanged by this adapter
refinement and varies between samples. Read-only has no clear improvement and
is about 0.4% slower in this sample. Peak RSS at this scale is unchanged, despite
removing the per-cell tag allocation and reducing temporary Rust tuple storage.
Both speed targets remain unmet; these numeric-only results do not establish
Pandas/Polars adoption, NYC performance or universal RAM superiority.

Calamine 0.8.2 retains a noneditable range; it does not provide the bounded ZIP
stream or preserving editable model measured here. Its overlapping value scan
remains the speed target. Ordinary `open_seconds` includes iterator construction
and deferred model materialization; compare complete operation boundaries.
CrabXL uses a 1 GiB model allowance and no read-side temporary files for this
workload. Calamine remains a benchmark-only dependency.

All 547 tests, Ruff format/check and strict Clippy pass with the fresh wheel.
No mirrored implementation tests or timing thresholds were added.
Raw reports: [ordinary](results/alpha7-static-tags-python.json),
[read-only](results/alpha7-static-tags-read-only.json).
