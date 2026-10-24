# ADR 0013: Canonical shared-formula identities

The adapter pins published core fa5f3b0fb1148803ee312de726fd182be152e504. Core ADR 0041 owns exact shared-group identity and canonical formula expansion; adapter code adds no parsing or translation logic. The pin also includes canonical worksheet view/printing models; Python proxies for these remain staged.

Sixty additional public comparison cases cover missing, empty, numeric, padded, signed, oversized, opaque, whitespace and XML-escaped IDs. Exact identities expand followers; distinct identities remain unresolved as in the reference. Ordinary/data-only getters and values-only iteration agree, and ordinary unmodified saves are checked twice through public reference readback. Cache-only save semantics, shared-group editing and optimized read-only Python mode remain staged.

All 547 tests pass against the installed locked release wheel. Provenance checks verify the same 63 original reference bodies and parameter sets; the new cases are original tests, not extra copied implementation. The same-call benchmark measures actual adapter loading and Python iteration separately from native core results. Required speed and desired RSS hold for this workload, without a claim of full API or milestone completion.
