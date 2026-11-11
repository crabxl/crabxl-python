"""openpyxl 3.1.5 calls that crabxl supports in every mode, checked against openpyxl."""

import zipfile
from datetime import datetime
from xml.etree.ElementTree import fromstring

import crabxl
import openpyxl
import pytest
from crabxl.cell.cell import Cell
from crabxl.styles import Font, NamedStyle
from crabxl.styles.cell_style import StyleArray
from crabxl.worksheet.dimensions import ColumnDimension, RowDimension
from crabxl.worksheet.hyperlink import Hyperlink, HyperlinkList

MAC = datetime(1904, 1, 1)


def dated(path):
    book = openpyxl.Workbook()
    book.active["A1"] = datetime(2024, 1, 2, 6)
    book.active["B1"] = 5
    book.create_sheet("Two")["A1"] = datetime(1999, 12, 31)
    book.save(path)


@pytest.mark.parametrize("change", ["epoch", "iso_dates"])
def test_loaded_date_options_keep_date_values(tmp_path, change):
    source, output = tmp_path / "in.xlsx", tmp_path / "out.xlsx"
    dated(source)
    book = crabxl.load_workbook(source)
    if change == "epoch":
        book.epoch = MAC
    else:
        book.iso_dates = True
    book.save(output)
    book.close()
    with zipfile.ZipFile(output) as archive:
        workbook = archive.read("xl/workbook.xml").decode()
        sheet = archive.read("xl/worksheets/sheet1.xml").decode()
    assert ('date1904="1"' in workbook) == (change == "epoch")
    assert ('t="d"' in sheet) == (change == "iso_dates")
    for module in (openpyxl, crabxl):
        check = module.load_workbook(output)
        assert check.active["A1"].value == datetime(2024, 1, 2, 6)
        assert check.active["B1"].value == 5
        assert check["Two"]["A1"].value == datetime(1999, 12, 31)
        assert (check.epoch == MAC) == (change == "epoch")
        check.close()


def test_read_only_epoch_change_applies_to_later_reads(tmp_path):
    source = tmp_path / "in.xlsx"
    dated(source)
    values = []
    for module in (openpyxl, crabxl):
        book = module.load_workbook(source, read_only=True)
        book.epoch = MAC
        values.append(next(book.active.values)[0])
        book.close()
    assert values[0] == values[1] != datetime(2024, 1, 2, 6)


# openpyxl never closes the stream of a removed write-only sheet.
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_write_only_sheets_can_be_ordered_and_removed(tmp_path):
    results = []
    for module in (openpyxl, crabxl):
        book = module.Workbook(write_only=True)
        for title in "ABC":
            book.create_sheet(title).append([title])
        book.create_sheet("D", 0).append(["D"])
        book.move_sheet("C", -2)
        book.remove(book["A"])
        book.create_sheet("A").append(["new A"])
        output = tmp_path / f"{module.__name__}.xlsx"
        book.save(output)
        check = openpyxl.load_workbook(output)
        results.append([(ws.title, ws["A1"].value) for ws in check.worksheets])
    assert results[0] == results[1]
    assert [title for title, _ in results[1]] == ["D", "C", "B", "A"]


def test_read_only_workbooks_change_in_memory(tmp_path):
    source = tmp_path / "in.xlsx"
    dated(source)
    book = crabxl.load_workbook(source, read_only=True)
    book.move_sheet("Two", -1)
    assert book.sheetnames == ["Two", "Sheet"]
    book.remove(book["Two"])
    assert book.sheetnames == ["Sheet"]
    book.add_named_style(NamedStyle("loud", font=Font(bold=True)))
    assert "loud" in book.named_styles
    book.loaded_theme = b"<theme/>"
    assert book.loaded_theme == b"<theme/>"
    assert next(book.active.values)[0] == datetime(2024, 1, 2, 6)
    book.close()


def test_removed_vba_can_be_restored(tmp_path):
    source, output = tmp_path / "in.xlsm", tmp_path / "out.xlsm"
    openpyxl.Workbook().save(source)
    with zipfile.ZipFile(source) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    parts["[Content_Types].xml"] = (
        parts["[Content_Types].xml"]
        .replace(
            b"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
            b"application/vnd.ms-excel.sheet.macroEnabled.main+xml",
        )
        .replace(
            b"</Types>",
            b'<Override PartName="/xl/vbaProject.bin" '
            b'ContentType="application/vnd.ms-office.vbaProject"/></Types>',
        )
    )
    rels = "xl/_rels/workbook.xml.rels"
    parts[rels] = parts[rels].replace(
        b"</Relationships>",
        b'<Relationship Id="vba" Target="vbaProject.bin" '
        b'Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject"/>'
        b"</Relationships>",
    )
    parts["xl/vbaProject.bin"] = b"opaque VBA project"
    with zipfile.ZipFile(source, "w") as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    book = crabxl.load_workbook(source, keep_vba=True)
    book.vba_archive = None
    assert book.vba_archive is None
    book.vba_archive = True
    book.save(output)
    book.close()
    with zipfile.ZipFile(output) as archive:
        assert archive.read("xl/vbaProject.bin") == b"opaque VBA project"


def test_detached_cell_flags_apply_when_appended():
    book = crabxl.Workbook()
    cell = Cell(None, value="x")
    cell.quotePrefix = True
    cell.pivotButton = True
    assert cell.quotePrefix and cell.pivotButton
    book.active.append([cell])
    assert book.active["A1"].quotePrefix and book.active["A1"].pivotButton


def test_dimensions_accept_style_arrays_and_spans():
    book = crabxl.Workbook()
    sheet = book.active
    sheet["A1"].font = Font(bold=True)
    array = StyleArray(book._style_owner().style_array(sheet["A1"].style_id))
    sheet.row_dimensions[2] = RowDimension(sheet, index=2, s=array, spans="1:3")
    sheet.column_dimensions["B"] = ColumnDimension(sheet, index="B", style=array)
    assert sheet.row_dimensions[2].font.bold
    assert sheet.column_dimensions["B"].font.bold
    with pytest.raises(TypeError):
        RowDimension(sheet, index=3, s=0)


def test_long_titles_warn_and_save(tmp_path):
    output = tmp_path / "out.xlsx"
    book = crabxl.Workbook()
    with pytest.warns(UserWarning, match="more than 31 characters"):
        book.active.title = "x" * 40
    book.save(output)
    assert openpyxl.load_workbook(output).sheetnames == ["x" * 40]


def test_hyperlink_trees_match_openpyxl():
    node = fromstring('<hyperlink ref="A1"><child/></hyperlink>')
    assert Hyperlink.from_tree(node).ref == "A1"
    with pytest.raises(TypeError, match="unexpected keyword argument 'foo'"):
        HyperlinkList.from_tree(fromstring('<hyperlinks foo="1"/>'))


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_optimized_sheets_have_the_openpyxl_attributes(tmp_path):
    source = tmp_path / "in.xlsx"
    dated(source)
    for read_only in (True, False):
        theirs = (
            openpyxl.load_workbook(source, read_only=True).active
            if read_only
            else openpyxl.Workbook(write_only=True).create_sheet()
        )
        ours = (
            crabxl.load_workbook(source, read_only=True).active
            if read_only
            else crabxl.Workbook(write_only=True).create_sheet()
        )
        for name in ("cell", "iter_rows", "iter_cols", "add_chart", "freeze_panes"):
            assert hasattr(ours, name) == hasattr(theirs, name), (read_only, name)


@pytest.mark.parametrize("loaded", [False, True])
def test_removed_and_unattached_sheets_keep_working(tmp_path, loaded):
    from crabxl.formatting.rule import CellIsRule
    from crabxl.worksheet.worksheet import Worksheet

    source = tmp_path / "in.xlsx"
    dated(source)
    book = crabxl.load_workbook(source) if loaded else crabxl.Workbook()
    sheet = book["Two"] if loaded else book.create_sheet("Two")
    book.remove(sheet)
    sheet["A2"].number_format = "0.00"
    sheet["A2"].font = Font(bold=True)
    sheet.row_dimensions[2].font = Font(italic=True)
    sheet.conditional_formatting.add(
        "A2", CellIsRule(operator="equal", formula=["1"], font=Font(bold=True))
    )
    assert sheet["A2"].number_format == "0.00" and sheet["A2"].font.bold
    assert sheet.row_dimensions[2].font.italic
    unattached = Worksheet(book)
    unattached["A1"].font = Font(bold=True)
    assert unattached["A1"].font.bold
    book.save(tmp_path / "out.xlsx")
    assert "Two" not in openpyxl.load_workbook(tmp_path / "out.xlsx").sheetnames


def test_save_replaces_a_file_another_workbook_has_open(tmp_path):
    path = tmp_path / "book.xlsx"
    first = crabxl.Workbook()
    first.active["A1"] = 1
    first.save(path)
    loaded = crabxl.load_workbook(path)
    second = crabxl.Workbook()
    second.active["A1"] = 2
    second.save(path)
    assert loaded.active["A1"].value == 1
    assert crabxl.load_workbook(path).active["A1"].value == 2
