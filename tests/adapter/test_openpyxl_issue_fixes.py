"""Fixes for openpyxl bugs that CrabXL had copied. Issue numbers refer to openpyxl's tracker."""

import io
import re
import zipfile

import crabxl_openpyxl as crabxl
import pytest
from crabxl_openpyxl.formula.tokenizer import Tokenizer


def _sheet_xml(book, name="xl/worksheets/sheet1.xml"):
    buffer = io.BytesIO()
    book.save(buffer)
    with zipfile.ZipFile(buffer) as archive:
        return archive.read(name).decode(), buffer


def _panes(xml):
    return [m.group(1) for m in re.finditer(r'<selection(?: pane="(\w+)")?', xml)]


def test_refreezing_and_unfreezing_drop_old_selections():  # 2334
    book = crabxl.Workbook()
    sheet = book.active
    sheet.freeze_panes = "B2"
    sheet.freeze_panes = "C3"
    assert _panes(_sheet_xml(book)[0]) == ["topRight", "bottomLeft", "bottomRight"]
    sheet.freeze_panes = None
    xml, buffer = _sheet_xml(book)
    assert "<pane" not in xml and _panes(xml) == [None]
    loaded = crabxl.load_workbook(buffer)
    loaded.active.freeze_panes = "A3"
    assert _panes(_sheet_xml(loaded)[0]) == ["bottomLeft"]


def test_overlapping_merges_are_rejected():  # 2302
    sheet = crabxl.Workbook().active
    sheet.merge_cells("A1:A2")
    sheet.merge_cells("A1:A2")
    with pytest.raises(ValueError, match="overlaps"):
        sheet.merge_cells("A1:A3")
    sheet.merge_cells("B1:C2")
    assert sorted(str(r) for r in sheet.merged_cells.ranges) == ["A1:A2", "B1:C2"]


def test_write_only_rows_can_use_every_column():
    book = crabxl.Workbook(write_only=True)
    sheet = book.create_sheet()
    sheet.append(list(range(16384)))
    sheet.append(["x" * 30000] * 40)
    buffer = io.BytesIO()
    book.save(buffer)
    loaded = crabxl.load_workbook(buffer, read_only=True)
    rows = list(loaded.active.iter_rows(values_only=True))
    assert rows[0][-1] == 16383 and rows[1][39] == "x" * 30000


@pytest.mark.parametrize("insert", ["rows", "cols"])
def test_hyperlinks_follow_inserted_rows_and_columns(insert):  # 2320
    book = crabxl.Workbook()
    sheet = book.active
    sheet["B2"] = "link"
    sheet["B2"].hyperlink = "https://example.com"
    getattr(sheet, f"insert_{insert}")(1)
    target = "B3" if insert == "rows" else "C2"
    xml, buffer = _sheet_xml(book)
    assert re.findall(r'<hyperlink ref="(\w+)"', xml) == [target]
    loaded = crabxl.load_workbook(buffer).active
    assert loaded[target].hyperlink.target == "https://example.com"


def test_excel_escapes_are_decoded_and_literals_protected():  # 2328, 1410
    book = crabxl.Workbook()
    book.active["A1"] = "lit _x0041_ text"
    xml, buffer = _sheet_xml(book)
    assert "lit _x005F_x0041_ text" in xml
    assert crabxl.load_workbook(buffer).active["A1"].value == "lit _x0041_ text"
    shared = io.BytesIO()
    with zipfile.ZipFile(buffer) as source, zipfile.ZipFile(shared, "w") as target:
        for item in source.infolist():
            data = source.read(item)
            if item.filename == "xl/worksheets/sheet1.xml":
                data = data.replace(b"lit _x005F_x0041_ text", b"CR _x000D_ here")
            target.writestr(item, data)
    assert crabxl.load_workbook(shared).active["A1"].value == "CR \r here"


def test_spill_references_tokenize():  # 2309
    items = Tokenizer("=SUM(A1#)+$B$2#").items
    assert [(t.value, t.subtype) for t in items if t.type == "OPERAND"] == [
        ("A1#", "RANGE"),
        ("$B$2#", "RANGE"),
    ]


@pytest.mark.parametrize("write_only", [False, True])
def test_text_over_cell_limit_raises(write_only):  # 2223
    book = crabxl.Workbook(write_only=write_only)
    sheet = book.create_sheet() if write_only else book.active
    with pytest.raises(ValueError, match="32,767"):
        if write_only:
            sheet.append(["x" * 32768])
        else:
            sheet["A1"] = "x" * 32768
    if not write_only:
        sheet["A1"] = "x" * 32767
        assert len(sheet["A1"].value) == 32767
