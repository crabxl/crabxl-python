"""Resource controls must affect native behavior in both public read modes."""

import io
import os
import zipfile
from pathlib import Path

import crabxl
import openpyxl
import pytest

MIB = 1024 * 1024


def test_resource_validation_modes_and_auto_controls(tmp_path):
    for factory in [crabxl.AutoMemory, crabxl.ResourceLimits]:
        argument = (
            "available_bytes" if factory is crabxl.AutoMemory else "max_cell_bytes"
        )
        for value, error in [
            (True, TypeError),
            (1.5, TypeError),
            (-1, ValueError),
            (2**64, ValueError),
        ]:
            with pytest.raises(error):
                factory(**{argument: value})
    for argument, value in [
        ("fraction_per_mille", 0),
        ("fraction_per_mille", 1001),
        ("concurrent_operations", 0),
        ("concurrent_operations", 65536),
    ]:
        with pytest.raises(ValueError):
            crabxl.AutoMemory(**{argument: value})
    with pytest.raises(TypeError):
        crabxl.ResourceOptions(limits={"max_cell_bytes": 1})
    with pytest.raises(TypeError):
        crabxl.SharedStringOptions(cache_bytes=True)
    with pytest.raises(ValueError):
        crabxl.SharedStringOptions(storage="unknown")
    with pytest.raises(ValueError, match="Disk/cache"):
        crabxl.SharedStringOptions(storage="memory", temp_directory=tmp_path)
    path = tmp_path / "absent.xlsx"
    for read_only, options in [
        (False, crabxl.ResourceOptions(limits=crabxl.ResourceLimits(max_batch_rows=1))),
        (
            True,
            crabxl.ResourceOptions(
                limits=crabxl.ResourceLimits(max_materialized_bytes=1)
            ),
        ),
        (True, crabxl.ResourceOptions(max_patch_cells=1)),
    ]:
        with pytest.raises(ValueError):
            crabxl.load_workbook(path, read_only=read_only, resource_options=options)
    with pytest.raises(ValueError, match="Choose"):
        crabxl.load_workbook(
            path,
            max_memory_bytes=MIB,
            resource_options=crabxl.ResourceOptions(auto_memory=crabxl.AutoMemory()),
        )
    with pytest.raises(ValueError, match="Choose"):
        crabxl.Workbook(max_memory_bytes=MIB, auto_memory=crabxl.AutoMemory())
    with pytest.raises(MemoryError):
        crabxl.Workbook(auto_memory=crabxl.AutoMemory(maximum_bytes=1))
    for write_only in [False, True]:
        book = crabxl.Workbook(
            write_only=write_only,
            auto_memory=crabxl.AutoMemory(
                available_bytes=64 * MIB,
                headroom_bytes=0,
                maximum_bytes=8 * MIB,
                concurrent_operations=2,
            ),
        )
        sheet = book.create_sheet() if write_only else book.active
        sheet.append([7, "🦀", True])
        output = tmp_path / f"auto-{write_only}.xlsx"
        book.save(output, compression_level=1)
        book.close()
        checked = openpyxl.load_workbook(output, read_only=True)
        assert list(checked.active.values) == [(7, "🦀", True)]
        checked.close()


def test_read_edit_and_batch_limits_are_enforced_without_corrupting_source(tmp_path):
    source = tmp_path / "source.xlsx"
    original = openpyxl.Workbook()
    original.active.append([1, "long text", 3])
    original.save(source)
    original.close()
    before = source.read_bytes()

    # A write-only sink produces legal data descriptors; dimensions can be stale
    # independently of ZIP encoding. Exercise both public modes and ZIP64.
    class StreamSink:
        def __init__(self):
            self.buffer = io.BytesIO()

        def write(self, value):
            return self.buffer.write(value)

        def flush(self):
            pass

    with zipfile.ZipFile(source) as archive:
        parts = {item.filename: archive.read(item) for item in archive.infolist()}
    for zip64 in [False, True]:
        sink = StreamSink()
        with zipfile.ZipFile(sink, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, payload in parts.items():
                with archive.open(name, "w", force_zip64=zip64) as target:
                    target.write(payload)
        streamed = tmp_path / f"descriptor-{zip64}.xlsx"
        streamed.write_bytes(sink.buffer.getvalue())
        assert b"PK\x07\x08" in streamed.read_bytes()
        for read_only in [False, True]:
            for aggregate_cap in [None, sum(map(len, parts.values()))]:
                book = crabxl.load_workbook(
                    streamed,
                    read_only=read_only,
                    max_memory_bytes=8 * MIB,
                    resource_options=crabxl.ResourceOptions(
                        limits=crabxl.ResourceLimits(
                            max_total_uncompressed_bytes=aggregate_cap
                        )
                    ),
                )
                try:
                    assert list(book.active.values) == [(1, "long text", 3)]
                finally:
                    book.close()
            with pytest.raises(ValueError, match="max_total_uncompressed_bytes=10"):
                crabxl.load_workbook(
                    streamed,
                    read_only=read_only,
                    resource_options=crabxl.ResourceOptions(
                        limits=crabxl.ResourceLimits(max_total_uncompressed_bytes=10)
                    ),
                )
    for read_only in [False, True]:
        for limits in [
            crabxl.ResourceLimits(max_cell_bytes=3),
            crabxl.ResourceLimits(max_row_cells=1),
        ]:
            book = crabxl.load_workbook(
                source,
                read_only=read_only,
                max_memory_bytes=8 * MIB,
                resource_options=crabxl.ResourceOptions(limits=limits),
            )
            try:
                with pytest.raises(ValueError):
                    list(book.active.values)
            finally:
                book.close()
        with pytest.raises(ValueError):
            crabxl.load_workbook(
                source,
                read_only=read_only,
                resource_options=crabxl.ResourceOptions(
                    limits=crabxl.ResourceLimits(max_archive_entries=1)
                ),
            )
    # Even the stable, empty canonical sheet placeholder needs its name/holder.
    # A one-byte per-model cap fails at owner construction, before cell loading.
    with pytest.raises(MemoryError):
        crabxl.load_workbook(
            source,
            max_memory_bytes=8 * MIB,
            resource_options=crabxl.ResourceOptions(
                limits=crabxl.ResourceLimits(max_materialized_bytes=1)
            ),
        )
    book = crabxl.load_workbook(
        source,
        max_memory_bytes=8 * MIB,
        resource_options=crabxl.ResourceOptions(max_patch_cells=1),
    )
    try:
        book.active["A1"] = 99
        with pytest.raises(MemoryError):
            book.active["B1"] = 27
        assert book.active["A1"].value == 99
        assert book.active["B1"].value == "long text"
        book.active["A1"] = 88
        assert book.active["A1"].value == 88
    finally:
        book.close()
    book = crabxl.load_workbook(
        source,
        read_only=True,
        max_memory_bytes=8 * MIB,
        resource_options=crabxl.ResourceOptions(
            limits=crabxl.ResourceLimits(max_batch_rows=1, max_batch_bytes=4096)
        ),
    )
    assert list(book.active.values) == [(1, "long text", 3)]
    book.close()
    assert source.read_bytes() == before


def test_shared_string_placement_thresholds_limits_and_cleanup(
    tmp_path, shared_strings_source
):
    values = [f"v-{index:04}-" + "x" * 96 for index in range(10000)]
    source = shared_strings_source(tmp_path / "strings.xlsx", values)
    temporary = tmp_path / "owned-sst"
    temporary.mkdir()
    for read_only in [False, True]:
        for storage in ["memory", "auto", "disk"]:
            strings = crabxl.SharedStringOptions(
                storage=storage,
                memory_bytes=(8 if storage == "memory" else 2) * MIB,
                **(
                    {}
                    if storage == "memory"
                    else {"cache_bytes": 4096, "temp_directory": temporary}
                ),
            )
            book = crabxl.load_workbook(
                source,
                read_only=read_only,
                # Ordinary models and forced RAM SST now share one cap; the
                # original 4 MiB allowed each component that much separately.
                max_memory_bytes=(8 if not read_only and storage == "memory" else 4)
                * MIB,
                resource_options=crabxl.ResourceOptions(shared_strings=strings),
            )
            iterator = book.active.values
            assert next(iterator) == (values[0],)
            descriptors = Path("/proc/self/fd")
            if descriptors.is_dir():
                owned = []
                for descriptor in descriptors.iterdir():
                    try:
                        if str(temporary) in os.readlink(descriptor):
                            owned.append(descriptor)
                    except OSError:
                        pass
                assert len(owned) == (0 if storage == "memory" else 2)
            assert list(iterator) == [(value,) for value in values[1:]]
            book.close()
            assert not list(temporary.iterdir())

        for strings, error in [
            (
                crabxl.SharedStringOptions(storage="memory", memory_bytes=2 * MIB),
                MemoryError,
            ),
            (
                crabxl.SharedStringOptions(
                    storage="disk", max_temp_bytes=0, temp_directory=temporary
                ),
                ValueError,
            ),
            (crabxl.SharedStringOptions(max_entries=1), ValueError),
            (
                crabxl.SharedStringOptions(
                    storage="disk", temp_directory=temporary / "absent"
                ),
                OSError,
            ),
        ]:
            book = crabxl.load_workbook(
                source,
                read_only=read_only,
                max_memory_bytes=4 * MIB,
                resource_options=crabxl.ResourceOptions(shared_strings=strings),
            )
            try:
                with pytest.raises(error):
                    list(book.active.values)
            finally:
                book.close()
            assert not list(temporary.iterdir())


def test_loaded_bank_aggregate_failure_preserves_aliases_source_and_repeat_saves(
    tmp_path,
):
    source = tmp_path / "joint.xlsx"
    original = openpyxl.Workbook()
    first = original.active
    first.title = "First"
    second = original.create_sheet("Second")
    for value in range(6000):
        first.append([value])
        second.append([value])
    original.save(source)
    original.close()
    original_bytes = source.read_bytes()

    book = crabxl.load_workbook(source, max_memory_bytes=2 * MIB)
    try:
        # Reading and preserving edits share a single seekable source descriptor.
        descriptors = Path("/proc/self/fd")
        if descriptors.is_dir():
            opened = []
            for descriptor in descriptors.iterdir():
                try:
                    if os.readlink(descriptor) == str(source):
                        opened.append(descriptor)
                except OSError:
                    pass
            assert len(opened) == 1
        sheet = book["First"]
        alias = sheet["A1"]
        assert alias.value == 0
        native_alias = sheet._model()
        sheet["A1"] = 42
        assert alias.value == 42
        assert native_alias.get(0, 0) == ("n", 42)
        book["Second"]["A1"] = "queued before loading"
        # Each sheet fits alone; their retained models cannot fit jointly.
        for _ in range(2):
            with pytest.raises(MemoryError):
                _ = book["Second"]["A2"].value
            assert book["Second"]["A1"].value == "queued before loading"
            assert alias.value == 42
        sheet["A2"] = 99
        assert native_alias.get(1, 0) == ("n", 99)
        for index in range(2):
            output = tmp_path / f"joint-{index}.xlsx"
            book.save(output)
            checked = openpyxl.load_workbook(output, read_only=True)
            try:
                assert checked["First"]["A1"].value == 42
                assert checked["First"]["A2"].value == 99
                assert checked["Second"]["A1"].value == "queued before loading"
                assert checked["Second"]["A6000"].value == 5999
            finally:
                checked.close()
            assert not list(tmp_path.glob("crabxl-save-*"))
    finally:
        book.close()
    with pytest.raises(ValueError, match="closed"):
        native_alias.get(0, 0)
    assert source.read_bytes() == original_bytes
