# Retained rich-value bindings

Explicitly assigned rich values retain their Python object identity in a sparse
worksheet-owned index. Read-created views remain weakly cached, so scanning rich
cells does not retain every converted Python object. Canonical text, formatting
and resource validation remain in Rust.

Overwriting or removing a cell retires its assigned view. Structural relocation
keeps the assignment policy at the destination coordinate. Live mutation and
rollback restore both the canonical payload and the original retention policy.

Copying a worksheet binds its existing caller-visible rich values to the copied
coordinates. Native values remain independently owned; subsequent edits to the
shared public object synchronize the registered owners through normal native
operations. Cells without an existing Python view incur no conversion during
copying. Deferred native alias grouping and further alias-scaling work remain
tracked rather than materializing every rich source value in Python.

This checkpoint passes Ruff formatting and checking. Behavioral tests and copied
value interoperability belong to consolidated A11 pre-release acceptance.
