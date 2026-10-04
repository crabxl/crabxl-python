# ADR 0012: Owned temporal style retention

The adapter pins published core 1b1a8726f266917ec589ae4eefc43d0e61c9b732. Owned core set/append resolves temporal styles before cell commit, with shared preset IDs and combined prospective-cell/style budgeting. The adapter carries the existing canonical StyleId when assigning a replacement value; it does not copy appearance components, implement format classification or introduce its own preset table.

Forty new shared tests cover four initial temporal kinds replaced by four kinds or a numeric value. Assigned getters, the original saved snapshot and two replacement saves match public reference formats and loaded values. All 487 tests pass with the installed locked release wheel, including all 63 selected unchanged original test bodies and parameter sets verified against the pinned reference checkout.

The default owned temporal registry and ordinary default writer share canonical preset identities. Repeated adapter save borrows the cells; it does not consume the public workbook. Arbitrary owned/source style catalog saving, general style object getters/setters, rich strings and unified loaded bank ownership remain staged. No default-ID assumption is extended to arbitrary imported styles.

benchmarks/temporal-calls.md records actual identical Python assignment/getter/two-save calls, separately from native Rust owned/streaming measurements. Required speed and desired RSS hold for this supported overlap; other APIs, native competitors and full package compatibility remain independent acceptance work.
