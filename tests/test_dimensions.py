"""Dimension metadata projections use the workbook's canonical style catalog."""

import importlib
from copy import copy

import pytest


@pytest.mark.parametrize("loaded", [False, True])
@pytest.mark.parametrize("write_only", [False, True])
def test_dimension_metadata_matches_reference(tmp_path, loaded, write_only):
    if loaded and write_only:
        pytest.skip("Loaded workbooks cannot be write-only")
    snapshots = []
    for engine in ("openpyxl", "crabxl"):
        module = importlib.import_module(engine)
        dimensions = importlib.import_module(f"{engine}.worksheet.dimensions")
        styles = importlib.import_module(f"{engine}.styles")
        book = module.Workbook(write_only=write_only)
        sheet = book.create_sheet() if write_only else book.active
        path = tmp_path / f"{engine}.xlsx"
        if loaded:
            book.save(path)
            book.close()
            book = module.load_workbook(path)
            sheet = book.active
        column = dimensions.ColumnDimension(sheet, index="D", width=19)
        assert column.font.name == "Calibri"
        column.font = styles.Font(bold=True, color="FF0000")
        column.number_format = "0.00"
        column.reindex()
        row = dimensions.RowDimension(sheet, index=3, height=23, hidden=True)
        attributes = dict(column)
        xml_attributes = dict(column.to_tree().attrib)
        # IDs address different catalogs; the saved style is checked below.
        assert int(attributes.pop("style")) > 0
        assert int(xml_attributes.pop("style")) > 0
        snapshots.append((attributes, xml_attributes, dict(row)))
        sheet.column_dimensions["D"] = column
        sheet.row_dimensions[3] = row
        sheet.append([1])
        sheet.append([2])
        sheet.append([3])
        book.save(path)
        book.close()
        oracle = importlib.import_module("openpyxl").load_workbook(path)
        saved = oracle.active.column_dimensions["D"]
        assert saved.font.bold and saved.font.color.rgb == "00FF0000"
        assert saved.number_format == "0.00"
        assert saved.width == 19
        assert oracle.active.row_dimensions[3].height == 23
        oracle.close()
    assert snapshots[0] == snapshots[1]


def test_grouped_column_xml_matches_reference():
    snapshots = []
    for engine in ("openpyxl", "crabxl"):
        book = importlib.import_module(engine).Workbook()
        dimensions = book.active.column_dimensions
        assert dimensions.to_tree() is None
        dimensions.group("B", "E", outline_level=2, hidden=True)
        dimensions["G"].width = 0
        tree = dimensions.to_tree()
        snapshots.append(
            (tree.tag, [dict(item.attrib) for item in tree], dimensions.max_outline)
        )
        book.close()
    assert snapshots[0] == snapshots[1]


@pytest.mark.parametrize("row", [False, True])
def test_dimension_copy_is_independent(tmp_path, row):
    snapshots = []
    for engine in ("openpyxl", "crabxl"):
        module = importlib.import_module(engine)
        styles = importlib.import_module(f"{engine}.styles")
        book = module.Workbook()
        dimensions = (
            book.active.row_dimensions if row else book.active.column_dimensions
        )
        first, second = (1, 2) if row else ("A", "B")
        original = dimensions[first]
        blank = copy(original)
        assert not blank.has_style and blank.style_id == 0
        original.font = styles.Font(bold=True)
        original.number_format = "0.00"
        duplicate = copy(original)
        duplicate.font = styles.Font(italic=True)
        if not row:
            duplicate.min = duplicate.max = 2
        dimensions[second] = duplicate
        path = tmp_path / f"copy-{engine}.xlsx"
        book.save(path)
        book.close()
        oracle = importlib.import_module("openpyxl").load_workbook(path)
        saved = oracle.active.row_dimensions if row else oracle.active.column_dimensions
        snapshots.append(
            [
                (saved[key].font.bold, saved[key].font.italic, saved[key].number_format)
                for key in (first, second)
            ]
        )
        oracle.close()
    assert (
        snapshots[0] == snapshots[1] == [(True, False, "0.00"), (False, True, "0.00")]
    )
