
Optional/literal array text compatibility tests and same-call benchmark fixtures are original public API comparisons, without further reference implementation inspection. Rust core owns expression presence and Unicode body slicing; the adapter only converts properties and optional ownership. Existing selected upstream tests/assertions remain unchanged. See ADR 0008.

Literal formula reference/input tests are original public constructor/save/reload/property comparisons. They add no copied implementation. Canonical ownership and coordinate validation live in Rust core. All 63 selected upstream bodies and parameters remain unchanged. See ADR 0009.

Raw flag and compatible formula-header comparisons are original public API tests. The 63 selected pinned test bodies/parameters remain unchanged and verified. No additional reference implementation is copied or inspected. See ADR 0010.

Temporal default-format readback cases are original shared public API comparisons. The canonical format defaults and style variants live in Rust core. All 63 selected original test bodies/parameters remain unchanged. See ADR 0011.
