"""Tests of the redesigned crabxl API (not the openpyxl adapter)."""

from __future__ import annotations

import dataclasses
import datetime as dt
import io
import os
import stat
from decimal import Decimal

import crabxl as xl
import openpyxl
import pytest

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def reopen(book: xl.Workbook, **options: object) -> xl.Workbook:
    return xl.Workbook.open(book.to_bytes(), **options)  # type: ignore[arg-type]


def sample() -> xl.Workbook:
    book = xl.Workbook()
    sheet = book.worksheets.add("Data")
    sheet.append(["Region", "Amount"])
    sheet.extend([["North", 10], ["South", 20], ["West", 30]])
    sheet["B5"].value = xl.Formula("SUM(B2:B4)")
    return book


def test_new_workbook_is_empty_and_needs_a_sheet() -> None:
    book = xl.Workbook()
    assert book.sheet_names == []
    with pytest.raises(xl.StateError):
        book.to_bytes()
    book.worksheets.add("Data")
    with pytest.raises(xl.InvalidInputError):
        book.worksheets.add("data")
    assert "DATA" in book.worksheets
    with pytest.raises(xl.NotFoundError) as caught:
        book.worksheets["Missing"]
    assert isinstance(caught.value, LookupError)
    book.close()
    assert book.closed
    with pytest.raises(xl.StateError):
        book.sheet_names


def test_values_keep_their_types() -> None:
    book = xl.Workbook()
    sheet = book.worksheets.add("V")
    values = [
        42,
        2**80,
        0.1,
        "=not a formula",
        True,
        dt.date(2026, 11, 25),
        dt.datetime(2026, 11, 25, 9, 30, 15, 250000),
        dt.time(12, 30),
        dt.timedelta(days=1, hours=6),
        xl.ErrorValue.DIV0,
        None,
    ]
    sheet["A1:K1"].values = [values]
    sheet["L1"].value = xl.Formula("=A1*2")
    sheet["M1"].value = Decimal("3.14159265358979323846")
    sheet["N1"].value = xl.RichText(
        [xl.TextRun("bold", xl.Font(bold=True)), xl.TextRun(" plain")]
    )
    again = reopen(book).worksheets["V"]
    assert list(again["A1:K1"].values[0]) == values
    assert type(again["A1"].value) is int and type(again["C1"].value) is float
    assert again["D1"].formula is None
    assert again["L1"].formula == xl.Formula("A1*2")
    assert again["L1"].value is None  # No cached result until calculated.
    assert again["M1"].value == pytest.approx(3.141592653589793)
    rich = again["N1"].value
    assert isinstance(rich, xl.RichText) and rich.text == "bold plain"
    assert rich.runs[0].font is not None and rich.runs[0].font.bold
    exact = reopen(book, numbers="exact").worksheets["V"]
    assert exact["M1"].value == Decimal("3.14159265358979323846")
    assert exact["C1"].value == Decimal("0.1")
    serial = reopen(book, dates="serial").worksheets["V"]
    assert serial["F1"].value == 46351.0


def test_invalid_values_raise_before_writing() -> None:
    sheet = xl.Workbook().worksheets.add("S")
    for bad in (
        float("nan"),
        "x" * 32_768,
        object(),
        dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
    ):
        with pytest.raises(xl.InvalidInputError):
            sheet["A1"].value = bad  # type: ignore[assignment]
    with pytest.raises(xl.InvalidInputError):
        sheet["A1:B2"].values = [[1, 2]]
    with pytest.raises(xl.InvalidInputError):
        sheet["ZZZZ1"]
    with pytest.raises(xl.InvalidInputError):
        sheet["A1:B2"].value
    assert sheet["A1"].value is None


def test_typed_reads() -> None:
    sheet = sample().worksheets["Data"]
    assert sheet["B2"].value_as(int) == 10
    assert sheet["B2"].value_as(float) == 10.0
    with pytest.raises(xl.ConversionError) as caught:
        sheet["A2"].value_as(float)
    assert isinstance(caught.value, TypeError) and caught.value.cell == "A2"
    assert sheet.used_range is not None and sheet.used_range.ref == "A1:B5"
    assert list(sheet["A1:B5"].iter_rows())[1] == ("North", 10)


def test_styles_round_trip_and_map() -> None:
    book = sample()
    sheet = book.worksheets["Data"]
    header = xl.Style(
        font=xl.Font(bold=True, color="FFFFFF"),
        fill=xl.Fill("1F4E79"),
        border=xl.Border.all(xl.Side("thin", "000000")),
        alignment=xl.Alignment(horizontal="center", wrap_text=True),
    )
    sheet["A1:B1"].style = header
    sheet["B2:B4"].map_style(lambda style: style.replace(number_format="#,##0.00"))
    sheet.columns("A:B").width = 18
    sheet.rows("1").height = 24
    sheet.freeze_panes = "A2"
    again = reopen(book).worksheets["Data"]
    style = again["A1"].style
    assert style.font.bold and style.font.color == xl.Color("FFFFFF")
    assert style.fill == xl.Fill("1F4E79")
    assert style.border.left == xl.Side("thin", "000000")
    assert style.alignment.horizontal == "center" and style.alignment.wrap_text
    assert again["B3"].style.number_format == "#,##0.00"
    assert again.columns("B").width == 18
    assert again.rows("1").height == 24
    assert again.freeze_panes == "A2"
    again.freeze_panes = None
    assert again.freeze_panes is None
    with pytest.raises(xl.InvalidInputError):
        xl.Color("12345")


def test_objects_round_trip() -> None:
    book = sample()
    sheet = book.worksheets["Data"]
    table = xl.Table("Sales", "A1:B5", None, banded_rows=False, totals_row=True)
    sheet.tables.add(table)
    with pytest.raises(xl.InvalidInputError):
        sheet.tables.add(xl.Table("sales", "D1:E3"))
    with pytest.raises(xl.InvalidInputError):
        sheet.tables.add(xl.Table("Short", "D1:E2", totals_row=True))
    rules = [
        xl.DataValidation.list(["North", "South", "West"], ranges=["A2:A4", "C2"]),
        xl.DataValidation.list_from("$A$2:$A$4", ranges="D2"),
        xl.DataValidation.whole("between", 0, 100, ranges="B2:B4"),
        xl.DataValidation.decimal(">", 0.5, ranges="E2"),
        xl.DataValidation.text_length("<=", 10, ranges="F2"),
        xl.DataValidation.custom("ISNUMBER(G2)", ranges="G2"),
        dataclasses.replace(
            xl.DataValidation.whole(">", 1, ranges="H2"),
            allow_blank=False,
            prompt=("Count", "A whole number"),
            error=("Wrong", "Try again"),
        ),
    ]
    for rule in rules:
        sheet.validations.add(rule)
    red = xl.PartialStyle(font=xl.Font(bold=True), fill=xl.Fill.solid("FFC7CE"))
    formats = [
        xl.ConditionalFormat.cell(
            "between", 1, 15, ranges=["B2:B4", "D2"], style=red, stop_if_true=True
        ),
        xl.ConditionalFormat.formula("$B2>15", ranges="A2:A4", style=red),
    ]
    for format in formats:
        sheet.conditional_formats.add(format)
    sheet["B2"].note = xl.Note("Preliminary", "Finance")
    sheet["A2"].hyperlink = xl.Hyperlink.url(
        "https://example.com/north", tooltip="North"
    )
    sheet["A3"].hyperlink = xl.Hyperlink.location("Data!B3")
    sheet.merges.add("D1:E2")
    sheet.images.add(xl.Image(PNG), at="G2")
    sheet.protect("secret")
    book.defined_names.add(xl.DefinedName("Total", "Data!$B$5"))
    book.properties = xl.Properties(title="Q3", creator="Finance")
    again = reopen(book)
    data = again.worksheets["Data"]
    assert list(data.tables) == [table] and data.tables["sales"] == table
    assert list(data.validations) == rules
    assert list(data.conditional_formats) == formats
    assert data["B2"].note == xl.Note("Preliminary", "Finance")
    assert data["A2"].hyperlink == xl.Hyperlink.url(
        "https://example.com/north", tooltip="North"
    )
    assert data["A3"].hyperlink == xl.Hyperlink.location("Data!B3")
    assert "D1:E2" in data.merges and len(data.images) == 1 and data.is_protected
    assert again.defined_names["Total"].formula == "Data!$B$5"
    assert again.properties.title == "Q3"
    data["B2"].note = None
    assert data["B2"].note is None
    data.tables.remove("Sales")
    with pytest.raises(xl.NotFoundError):
        data.tables.remove("Sales")


def test_properties_dates_are_aware_datetimes() -> None:
    book = sample()
    created = dt.datetime(
        2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone(dt.timedelta(hours=8))
    )
    book.properties = xl.Properties(title="Q3", created=created)
    properties = reopen(book).properties
    assert properties.created == created and properties.created.tzinfo is not None
    with pytest.raises(xl.InvalidInputError):
        book.properties = xl.Properties(created=dt.datetime(2026, 1, 2))


def test_sheet_handles_follow_renames() -> None:
    book = sample()
    first = book.worksheets["Data"]
    second = book.worksheets["data"]
    assert first is second is book.worksheets[0]
    second.name = "Renamed"
    assert first.name == "Renamed" and first["B2"].value == 10
    book.worksheets.remove("Renamed")
    assert book.worksheets.add("Renamed") is not first


def test_openpyxl_names_point_to_the_adapter() -> None:
    with pytest.raises(ImportError, match="crabxl.openpyxl.load_workbook"):
        xl.load_workbook  # type: ignore[attr-defined]  # noqa: B018
    with pytest.raises(AttributeError):
        xl.not_a_name  # type: ignore[attr-defined]  # noqa: B018
    assert not hasattr(xl, "not_a_name")


def test_printing_filters_outline_charts_and_pictures_round_trip() -> None:
    book = sample()
    sheet = book.worksheets["Data"]
    page = xl.PageSetup(
        orientation="landscape",
        paper_size=9,
        fit_to=(1, 0),
        margins=xl.Margins(left=0.5),
        center_horizontally=True,
        grid_lines=True,
        print_area="A1:B5",
        title_rows="1",
        title_columns="A",
    )
    sheet.page_setup = page
    with pytest.raises(xl.InvalidInputError):
        sheet.page_setup = xl.PageSetup(scale=5)
    sheet.auto_filter = "A1:B4"
    with pytest.raises(xl.InvalidInputError):
        sheet.tables.add(xl.Table("Sales", "A1:B4"))
    sheet.tab_color = "FF0000"
    sheet.rows("2:3").outline_level = 1
    sheet.columns("B").outline_level = 2
    with pytest.raises(xl.InvalidInputError):
        sheet.rows("2").outline_level = 8
    bar = xl.Chart(
        "bar",
        "E2:K12",
        [xl.Series("Data!$B$2:$B$4", categories="Data!$A$2:$A$4", title="Amount")],
        title="Sales",
    )
    pie = xl.Chart("pie", "E14:K24", [xl.Series("Data!$B$2:$B$4")], legend=False)
    sheet.charts.add(bar)
    sheet.charts.add(pie)
    sheet.images.add(xl.Image(PNG), at="M2")
    rules = [
        xl.DataValidation.date(
            "between", dt.date(2026, 1, 1), dt.date(2026, 12, 31), ranges="C2:C4"
        ),
        xl.DataValidation.time(">", dt.time(9, 30), ranges="D2"),
    ]
    for rule in rules:
        sheet.validations.add(rule)
    red = xl.PartialStyle(fill=xl.Fill.solid("FFC7CE"))
    sheet.conditional_formats.add(
        xl.ConditionalFormat.formula("$B2>15", ranges="B2:B4", style=red)
    )

    again = reopen(book)
    data = again.worksheets["Data"]
    assert data.page_setup == page
    assert data.auto_filter == "A1:B4" and data.tab_color == xl.Color("FF0000")
    assert data.rows("2").outline_level == 1 and data.rows("4").outline_level == 0
    assert data.columns("B").outline_level == 2
    assert list(data.charts) == [bar, pie]
    assert list(data.images) == [xl.PlacedImage(xl.Image(PNG), "M2")]
    assert list(data.validations) == rules
    assert data.conditional_formats.remove("B3") == 1
    assert data.charts.remove("E2") == 1 and data.images.remove("A1:Z9") == 1
    data.auto_filter = None
    data.tab_color = None
    data.page_setup = xl.PageSetup()
    last = reopen(again).worksheets["Data"]
    assert last.page_setup == xl.PageSetup()
    assert last.auto_filter is None and last.tab_color is None
    assert len(last.charts) == 1 and not list(last.images)
    assert len(last.conditional_formats) == 0


def test_structural_edits_update_references() -> None:
    book = sample()
    summary = book.worksheets.add("Summary")
    summary["A1"].value = xl.Formula("Data!B5*2")
    book.defined_names.add(xl.DefinedName("Total", "Data!$B$5"))
    data = book.worksheets["Data"]
    data.rows("3:4").insert()
    assert data["B7"].formula == xl.Formula("SUM(B2:B6)")
    assert summary["A1"].formula == xl.Formula("Data!B7*2")
    assert book.defined_names["Total"].formula == "Data!$B$7"
    data.columns("A").delete()
    assert summary["A1"].formula == xl.Formula("Data!A7*2")
    data.rows("7").delete()
    assert summary["A1"].formula == xl.Formula("Data!#REF!*2")


def test_sheets_copy_move_rename_hide() -> None:
    book = sample()
    copy = book.worksheets.copy("Data", "Copy")
    assert copy["B5"].formula == xl.Formula("SUM(B2:B4)")
    book.worksheets.move("Copy", 0)
    assert book.worksheets.names == ["Copy", "Data"]
    copy.name = "Backup"
    copy.visibility = "hidden"
    book.active_sheet = "Data"
    again = reopen(book)
    assert again.worksheets.names == ["Backup", "Data"]
    assert again.worksheets["Backup"].visibility == "hidden"
    assert again.active_sheet == "Data"
    again.worksheets.remove("Backup")
    assert [sheet.name for sheet in again.worksheets] == ["Data"]


@pytest.mark.skipif(os.name == "nt", reason="Windows files have no POSIX mode bits")
def test_saves_are_atomic_and_keep_permissions(tmp_path: os.PathLike[str]) -> None:
    path = os.path.join(tmp_path, "book.xlsx")
    sample().save(path)
    os.chmod(path, 0o640)
    with xl.Workbook.open(path) as book:
        book.worksheets["Data"]["A2"].value = "Changed"
        book.save(path)  # Over its own source.
    with xl.Workbook.open(path) as book:
        assert book.worksheets["Data"]["A2"].value == "Changed"
        assert book.worksheets["Data"]["A3"].value == "South"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o640
    assert os.listdir(tmp_path) == ["book.xlsx"]
    buffer = io.BytesIO()
    sample().save(buffer)
    assert buffer.getvalue()[:2] == b"PK"


def test_unmodeled_content_needs_consent(tmp_path: os.PathLike[str]) -> None:
    # openpyxl writes the file; an unknown attribute marks content CrabXL cannot keep.
    source = os.path.join(tmp_path, "source.xlsx")
    book = openpyxl.Workbook()
    book.active.protection.sheet = True
    book.save(source)
    import zipfile

    patched = os.path.join(tmp_path, "patched.xlsx")
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(patched, "w") as new:
        for item in old.infolist():
            data = old.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                data = data.replace(
                    b"<sheetProtection ", b'<sheetProtection futureFlag="1" '
                )
            new.writestr(item, data)
    strict = xl.Workbook.open(patched)
    strict.worksheets[0].unprotect()
    with pytest.raises(xl.UnsupportedError):
        strict.to_bytes()
    allowing = xl.Workbook.open(patched, data_loss="allow")
    allowing.worksheets[0].unprotect()
    assert allowing.to_bytes()[:2] == b"PK"


def test_files_open_in_openpyxl(tmp_path: os.PathLike[str]) -> None:
    path = os.path.join(tmp_path, "book.xlsx")
    book = sample()
    book.worksheets["Data"]["A1:B1"].style = xl.Style(font=xl.Font(bold=True))
    book.save(path)
    reference = openpyxl.load_workbook(path)
    sheet = reference["Data"]
    assert [cell.value for cell in sheet[2]] == ["North", 10]
    assert sheet["B5"].value == "=SUM(B2:B4)"
    assert sheet["A1"].font.b


def test_reader_streams_rows() -> None:
    data = sample().to_bytes()
    with xl.Reader.open(data) as reader:
        assert reader.sheet_names == ["Data"]
        rows = list(reader.worksheets["data"].iter_rows(columns="A:B", skip=1, limit=2))
        assert rows == [("North", 10), ("South", 20)]
        assert rows[0].number == 2
        everything = list(reader.worksheets[0].iter_rows())
        assert everything[-1].formulas[1] == xl.Formula("SUM(B2:B4)")
        batches = list(reader.worksheets[0].iter_batches(2))
        assert [len(batch) for batch in batches] == [2, 2, 1]
        with pytest.raises(xl.NotFoundError):
            reader.worksheets["Missing"]
    with pytest.raises(xl.FileFormatError):
        xl.Reader.open(b"not a zip file")


def test_writer_streams_and_aborts_on_error(tmp_path: os.PathLike[str]) -> None:
    path = os.path.join(tmp_path, "out.xlsx")
    bold = xl.Style(font=xl.Font(bold=True))
    with xl.Writer.create(path, compression=1) as writer:
        sheet = writer.worksheets.add("Events")
        sheet.freeze_panes = "A2"
        sheet.columns("A:B").width = 16
        sheet.append(["id", "when"], style=bold)
        sheet.extend(
            (n, dt.date(2026, 1, 1) + dt.timedelta(days=n)) for n in range(1000)
        )
        sheet.merge("D1:E1")
        choices = xl.DataValidation.list(["a", "b"], ranges=["C2:C9", "F2"])
        flag = xl.ConditionalFormat.formula(
            "$A2>5", ranges=["A2:A9", "C2"], style=xl.PartialStyle(font=bold.font)
        )
        sheet.add_validation(choices)
        sheet.add_conditional_format(flag)
        other = writer.worksheets.add("Other")
        other.append(["x"])
        writer.worksheets["Events"].append([1000, None])
    with xl.Workbook.open(path) as book:
        events = book.worksheets["Events"]
        assert events["B2"].value == dt.date(2026, 1, 1)
        assert events["A1"].style.font.bold and events.freeze_panes == "A2"
        assert list(events.validations) == [choices]
        assert [rule.ranges for rule in events.conditional_formats] == [flag.ranges]
        # The merge anchor D1 is a present cell.
        assert events.used_range is not None and events.used_range.ref == "A1:D1002"
    failed = os.path.join(tmp_path, "failed.xlsx")
    with pytest.raises(RuntimeError):
        with xl.Writer.create(failed) as writer:
            writer.worksheets.add("S").append([1])
            raise RuntimeError("stop")
    assert not os.path.exists(failed)
    with pytest.raises(xl.StateError):
        with xl.Writer.create(io.BytesIO()) as writer:
            sheet = writer.worksheets.add("S")
            sheet.append([1])
            sheet.freeze_panes = "A2"


def test_saves_are_byte_stable() -> None:
    book = sample()
    assert book.to_bytes() == book.to_bytes()
