# A8 complete Python operation verification

The comparison uses the public A7 baseline and a validated preview wheel pinned
to core `a6e83a21bef58597b458dd548f1cc0c41a4b63f7`. Both wheel labels still say
`0.1.0a7`; native/source hashes in the raw reports distinguish them. The released
A8 core `f08b8e6d494e575ba39289dde4895b7a9b648242` changes package versions and
release records without changing that runtime source. The final `0.1.0a8` wheel
pins this released core and separately passes all 547 compatibility cases.

One warmup and three rotating cold-process samples run serially without
overlapping local builds, tests, profiling or generation. Timings include imports,
load, conversion, complete iteration and cleanup. Numeric fixtures check total
count/checksum; unique-text workers additionally assert each string and its order.
Fixtures are generated before timing or reused from the pinned core reports.
Model allowances are 1 GiB, unique SST is forced RAM, and read temporary bytes
are zero. Read-only CPU can exceed wall time through producer/consumer overlap.

| One million cells | Public A7 seconds | Candidate seconds | python-calamine 0.8.2 seconds |
| --- | ---: | ---: | ---: |
| Numeric ordinary model | 0.746419 | 0.401509 | 0.510249 |
| Numeric read-only iteration | 0.652870 | 0.305090 | 0.511340 |
| Unique text ordinary model | 1.677984 | 1.061687 | 1.186817 |
| Unique text read-only iteration | 1.422103 | 0.921018 | 1.240314 |

Candidate median RSS is respectively 52,096, 20,484, 239,596 and 162,112 KiB;
reference RSS is 87,572, 87,596, 321,548 and 321,556 KiB. Candidate RSS is broadly
unchanged against A7 here. Core capacity accounting improves budget usability,
not physical retention for these already packed models. Calamine returns decoded
noneditable ranges; editable/preserving ownership and row-stream boundaries are
different. These controlled cases do not prove universal superiority or an
actual NYC workbook result. No dataframe integration is implemented.

Raw reports preserve installed identities, samples, fixture hashes and settings:
[numeric ordinary](results/alpha8-final-python-numeric-normal.json),
[numeric read-only](results/alpha8-final-python-numeric-stream.json),
[unique ordinary](results/alpha8-final-python-unique-normal.json) and
[unique read-only](results/alpha8-final-python-unique-stream.json).
Earlier write-only measurements and their limited gains remain in
[the byte-escaping report](results/alpha8-byte-escape-python-writes.json).

Existing resource tests retain failure/retry, alias and source-preservation
checks. Their finite fixtures now exercise real vector expansion and aggregate
retention instead of relying on the obsolete fixed per-cell estimate. No test
functions or timing assertions were added. Final wheel tests pass in 4.51 seconds;
Ruff formatting/checks and strict Clippy also pass. Platform release artifacts
and fresh public-package verification remain separate gates.
