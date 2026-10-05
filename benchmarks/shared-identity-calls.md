# Python literal shared-formula loading

Reproduce with the installed locked release wheel and public openpyxl 3.1.5:

```sh
python benchmarks/shared_identity_calls.py --measure /workspace/crabxl/benchmarks/measure
```

Raw evidence: [results/shared-identity-calls.json](results/shared-identity-calls.json). One warmup and five alternating serial cold-process runs include imports, ordinary load_workbook, values-only iteration, identical per-value checks and SHA256. Fixture generation is excluded. Both engines use ordinary loaded models; this is not read-only streaming or pure Rust throughput. Builds/tests did not overlap timing.

| Cells | Projection | crabxl seconds / RSS KiB | openpyxl seconds / RSS KiB |
|---|---|---|---|
| 5,000 | Formulas | 0.07549 / 16,200 | 0.26616 / 37,328 |
| 5,000 | Caches | 0.06813 / 16,204 | 0.23337 / 37,200 |
| 50,000 | Formulas | 0.32973 / 24,636 | 0.74352 / 61,268 |
| 50,000 | Caches | 0.28351 / 19,032 | 0.62764 / 59,768 |

Every formula/cache and matching digest is verified. Sampled temporary bytes are zero with cleanup checked; 25ms sampling can miss short-lived files. Final source ZIP is outside the sampled directory. Peak RSS includes Python/import overhead. Required speed and desired RSS hold for this supported overlap. No prior adapter pin supported the full literal-ID workload, so no equivalent prior-version regression or native-competitor claim is fabricated. Normal-mode repeat saves are correctness-tested separately; cache-only save, shared-group editing and complete formula compatibility remain open.
