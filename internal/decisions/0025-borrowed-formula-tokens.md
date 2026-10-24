# Canonical formula tokens and live translation

Status: selected token-tool checkpoint implemented; complete M5 acceptance remains open.

The adapter pins core `263c45b5cc6fdfe7339eabfb7dc2520c1a48f2d0`. Its canonical
lexer adapts the stable umya lexical states recorded in the core port inventory,
retaining source borrowing for ordinary tokens and separately budgeted owned
storage for noncontiguous newline words. No reference implementation was read
or copied for the adapter; behavior observations use public openpyxl 3.1.5 calls.

`Token`, `Tokenizer`, public factories/rendering and `Translator.get_tokens()`
now expose lexical objects. Mutable token spelling affects later translation.
Lexing and operand classification stay in Rust. PyO3 builds the public tuple list
directly from borrowed token strings, without an intermediate owned Rust string
vector; token objects use the reference's three fixed slots. Token storage has
an explicit configurable `MAX_TOKEN_BYTES` work allowance, distinct from the
existing translator output allowance. Python object/interpreter allocations are
additional; the native allowance does not claim a hard process-RSS ceiling.

The existing shared formula test covers function/error/exponent/array/newline
tokens, public factories, malformed input, live mutation and translation for both
engines. No test functions were added. All 547 compatibility cases pass; the final
slot change separately passes the 16 affected translation cases. Ruff and strict
Clippy pass. Full tokenizer edge-case auditing and the other M5 families remain
required. Unknown spill/error syntax rejects explicitly. Native generated-reference
colon tokens intentionally address pending reference MR !345; this differs from
the pinned reference's erroneous adjacent operand representation. Native unmatched
closers produce typed errors instead of reproducing its internal stack IndexError.

## Measured complete calls

The [worker](../../benchmarks/tokenizer_calls.py) runs one warmup and five rotating
cold-process samples per engine, serially with no overlapping builds, tests,
profiling or fixture generation. Warm imports precede timing; lexical parsing,
Python objects, complete iteration, rendering and spelling/category checksum
remain inside the timed operation. Each sample processes 200,000 calls and
1,225,000 tokens with checksum 1,244,300,000 for both engines.

| Public operation | Median seconds | Peak RSS median KiB |
| --- | ---: | ---: |
| openpyxl 3.1.5 | 3.239121 | 31,216 |
| CrabXL preview | 1.498300 | 18,316 |

These cases show about 2.16 times faster complete tokenization. RSS includes
module/interpreter baseline and only the current formula's tokens; it does not
measure retained workbook cells, giant token graphs or per-token memory savings.
No worksheet, ZIP or temporary-file work occurs. This is not a read/write/edit
performance claim or complete M5 acceptance. The preview wheel is still labeled
`0.1.0a8`; its native and source hashes distinguish it from the public A8 release.
[Raw results](../../benchmarks/results/alpha9-tokenizer-python.json) retain every
sample, worker identity and source revision. The smaller initial run is retained
as preliminary evidence, without treating differing workloads as a slot timing win.
