"""Merged geometry, shared appearance and preserving saves through public APIs."""

import gc
import importlib
import zipfile

import crabxl
import openpyxl
import pytest


@pytest.mark.parametrize("loaded", [False, True])
def test_cell_lookup_recovers_native_views_after_collection(tmp_path, loaded):
    snapshots = []
    for engine in (openpyxl, crabxl):
        book = engine.Workbook()
        sheet = book.active
        sheet["B2"] = 7
        sheet.merge_cells("C3:E4")
        path = tmp_path / f"lookup-{engine.__name__}.xlsx"
        if loaded:
            book.save(path)
            book.close()
            book = engine.load_workbook(path)
            sheet = book.active
        gc.collect()
        cells = [sheet._cells.get(key) for key in ((2, 2), (3, 3), (4, 5))]
        snapshots.append(
            [(type(cell).__name__, cell.coordinate, cell.value) for cell in cells]
        )
        assert sheet._cells.get((20, 20), "missing") == "missing"
        assert sheet._cells.get((0, 1)) is None
        assert sheet._cells[2, 2] is cells[0]
        book.close()
    assert snapshots[0] == snapshots[1]


@pytest.mark.parametrize("engine", [openpyxl, crabxl], ids=["openpyxl", "crabxl"])
@pytest.mark.parametrize("loaded", [False, True])
def test_merge_range_format_preserves_values_and_has_no_declaration(
    engine, tmp_path, loaded
):
    MergeRange = importlib.import_module(
        engine.__name__ + ".worksheet.merge"
    ).MergedCellRange
    source = tmp_path / "source.xlsx"
    baseline = openpyxl.Workbook()
    baseline.save(source)
    baseline.close()
    book = engine.load_workbook(source) if loaded else engine.Workbook()
    try:
        sheet = book.active
        sheet["B2"] = "retained"
        sheet["B1"] = "edge"
        sheet["B1"].font = engine.styles.Font(bold=True)
        sheet["B1"].border = engine.styles.Border(left=engine.styles.Side(style="hair"))
        sheet["A1"].border = engine.styles.Border(
            top=engine.styles.Side(style="thick"),
            bottom=engine.styles.Side(style="double"),
            left=engine.styles.Side(style="thin"),
            right=engine.styles.Side(style="dashed"),
        )
        merged = MergeRange(sheet, "A1:C3")
        merged.format()
        merged.format()
        assert sheet["B2"].value == "retained"
        assert sheet["B1"].value == "edge"
        assert sheet["B1"].font.bold
        assert sheet["B1"].border.left.style == "hair"
        assert not sheet.merged_cells.ranges
        for row, col in merged.top:
            assert sheet.cell(row, col).border.top.style == "thick"
        for row, col in merged.bottom:
            assert sheet.cell(row, col).border.bottom.style == "double"
        target = tmp_path / "formatted.xlsx"
        book.save(target)
    finally:
        book.close()
    verified = openpyxl.load_workbook(target)
    try:
        assert verified.active["B2"].value == "retained"
        assert verified.active["B1"].value == "edge"
        assert verified.active["B1"].font.bold
        assert not verified.active.merged_cells.ranges
        assert verified.active["C3"].border.bottom.style == "double"
    finally:
        verified.close()


@pytest.mark.parametrize("engine", [openpyxl, crabxl], ids=["openpyxl", "crabxl"])
def test_direct_worksheet_merge_and_unmerge(engine):
    book = engine.Workbook()
    try:
        sheet = engine.worksheet.worksheet.Worksheet(book)
        sheet["A1"] = "anchor"
        sheet["B2"] = "discarded"
        sheet.merge_cells("A1:B2")
        assert "A1:B2" in sheet.merged_cells
        assert sheet.merged_cells == "A1:B2"
        assert sheet["A1"].value == "anchor"
        assert sheet["B2"].value is None
        sheet.unmerge_cells("A1:B2")
        assert "A1:B2" not in sheet.merged_cells
        assert sheet.merged_cells == ""
        sheet["B2"] = "editable"
        assert sheet["B2"].value == "editable"
    finally:
        book.close()


@pytest.mark.parametrize("engine", [openpyxl, crabxl], ids=["openpyxl", "crabxl"])
def test_merged_values_borders_aliases_and_preserving_repeat_saves(engine, tmp_path):
    for loaded in [False, True]:
        book = engine.Workbook()
        sheet = book.active
        sheet["A1"] = "anchor"
        sheet["B2"] = "discarded"
        sheet["A1"].border = engine.styles.Border(
            left=engine.styles.Side(style="thin"),
            top=engine.styles.Side(style="dashed"),
        )
        sheet["A1"].protection = engine.styles.Protection(locked=False, hidden=True)
        sheet["C3"].border = engine.styles.Border(
            right=engine.styles.Side(style="double"),
            bottom=engine.styles.Side(style="thick"),
        )
        if loaded:
            source = tmp_path / f"{engine.__name__}-source.xlsx"
            book.save(source)
            book.close()
            # A valid source may declare merges without pre-normalized edge styles.
            with zipfile.ZipFile(source) as archive:
                parts = {name: archive.read(name) for name in archive.namelist()}
            parts["xl/worksheets/sheet1.xml"] = parts[
                "xl/worksheets/sheet1.xml"
            ].replace(
                b"</sheetData>",
                b'</sheetData><mergeCells count="1"><mergeCell ref="A1:C3"/></mergeCells>',
            )
            with zipfile.ZipFile(
                source, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                for name, value in parts.items():
                    archive.writestr(name, value)
            book = engine.load_workbook(source)
            sheet = book.active
            assert sheet["B2"].value is None
            if engine is crabxl:
                untouched = tmp_path / "untouched.xlsx"
                book.save(untouched)
                with zipfile.ZipFile(untouched) as archive:
                    assert {
                        name: archive.read(name) for name in archive.namelist()
                    } == parts
        else:
            alias = sheet["B2"]
            sheet.merge_cells("A1:C3")
            assert alias.value == "discarded"
            alias.value = "detached"
            assert sheet["B2"].value is None
        merged_type = importlib.import_module(engine.__name__ + ".cell.cell").MergedCell
        assert isinstance(sheet["B2"], merged_type)
        with pytest.raises(AttributeError):
            sheet["B2"].value = 42
        assert sheet["A1"].value == "anchor"
        assert sheet.max_row == 3 and sheet.max_column == 3
        assert "B2" in sheet.merged_cells
        assert {str(value) for value in sheet.merged_cells.ranges} == {"A1:C3"}
        assert len(sheet.merged_cells.ranges) == 1
        assert sheet["A1"].border.right.style == "double"
        assert sheet["A1"].border.bottom.style == "thick"
        for coord, side, expected in [
            ("A2", "left", "thin"),
            ("B1", "top", "dashed"),
            ("C2", "right", "double"),
            ("B3", "bottom", "thick"),
        ]:
            cell = sheet[coord]
            assert getattr(cell.border, side).style == expected
            assert not cell.protection.locked and cell.protection.hidden
        sheet["A1"] = "changed"
        sheet.merge_cells("E5:F6")
        for suffix in [1, 2]:
            path = tmp_path / f"{engine.__name__}-{loaded}-{suffix}.xlsx"
            book.save(path)
            reopened = openpyxl.load_workbook(path)
            target = reopened.active
            assert target["A1"].value == "changed"
            assert target["A1"].border.right.style == "double"
            assert target["B3"].border.bottom.style == "thick"
            assert {str(value) for value in target.merged_cells.ranges} == {
                "A1:C3",
                "E5:F6",
            }
            reopened.close()
        sheet.unmerge_cells("A1:C3")
        assert sheet["A1"].value == "changed" and sheet["B2"].value is None
        assert not isinstance(sheet["B2"], merged_type)
        sheet["B2"] = "restored"
        assert sheet["B2"].value == "restored"
        book.close()
