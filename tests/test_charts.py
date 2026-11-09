"""Public chart creation comparisons with openpyxl 3.1.5."""

import importlib
from xml.etree.ElementTree import canonicalize, fromstring
from zipfile import ZipFile

import crabxl
import openpyxl
import pytest

CHARTS = (
    "BarChart",
    "BarChart3D",
    "LineChart",
    "LineChart3D",
    "AreaChart",
    "AreaChart3D",
    "PieChart",
    "PieChart3D",
    "DoughnutChart",
    "ProjectedPieChart",
    "ScatterChart",
    "BubbleChart",
    "RadarChart",
    "StockChart",
    "SurfaceChart",
    "SurfaceChart3D",
)


def test_chartsheet_edits_preserve_unmodelled_properties(tmp_path):
    from xml.etree.ElementTree import Element, SubElement, tostring

    from crabxl.styles import Color
    from openpyxl.chartsheet.properties import ChartsheetProperties

    source = tmp_path / "source.xlsx"
    book = openpyxl.Workbook()
    book.active.append([1, 2])
    sheet = book.create_chartsheet("Chart")
    sheet.sheetPr = ChartsheetProperties(
        codeName="Original", tabColor=openpyxl.styles.Color(rgb="FF123456")
    )
    sheet.headerFooter.oddHeader.center.text = "Original header"
    chart = openpyxl.chart.BarChart()
    chart.add_data(
        openpyxl.chart.Reference(
            book.active, min_col=1, max_col=2, min_row=1, max_row=1
        )
    )
    sheet.add_chart(chart)
    book.save(source)
    book.close()
    with ZipFile(source) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    part = "xl/chartsheets/sheet1.xml"
    root = fromstring(contents[part])
    for node in (root.find("{*}sheetPr"), root.find("{*}sheetViews/{*}sheetView")):
        node.set("{urn:crabxl:test}marker", "keep")
        extension = Element("{urn:crabxl:test}extra")
        SubElement(extension, "{urn:crabxl:test}value").text = "preserved"
        node.append(extension)
    contents[part] = tostring(root)
    with ZipFile(source, "w") as archive:
        for name, data in contents.items():
            archive.writestr(name, data)
    book = crabxl.load_workbook(source)
    sheet = book["Chart"]
    sheet.sheetPr.tabColor = Color(theme=2)
    sheet.sheetPr.published = False
    sheet.sheetViews.sheetView[0].zoomScale = 125
    sheet.oddHeader.center.text = "Edited header"
    for index in range(2):
        output = tmp_path / f"edited-{index}.xlsx"
        book.save(output)
        with ZipFile(output) as archive:
            root = fromstring(archive.read(part))
            for node in (
                root.find("{*}sheetPr"),
                root.find("{*}sheetViews/{*}sheetView"),
            ):
                assert node.get("{urn:crabxl:test}marker") == "keep"
                assert (
                    node.find("{urn:crabxl:test}extra/{urn:crabxl:test}value").text
                    == "preserved"
                )
            color = root.find("{*}sheetPr/{*}tabColor")
            assert color.get("theme") == "2"
            assert "rgb" not in color.attrib
            assert root.find("{*}sheetViews/{*}sheetView").get("zoomScale") == "125"
            assert "Edited header" in root.find("{*}headerFooter/{*}oddHeader").text
    book.close()


@pytest.mark.parametrize("backend", ["openpyxl", "crabxl"])
@pytest.mark.parametrize("mode", ["new", "loaded", "write_only"])
def test_chartsheet_properties_survive_save_and_reload(backend, mode, tmp_path):
    engine = importlib.import_module(backend)
    properties = importlib.import_module(f"{backend}.chartsheet.properties")
    protection = importlib.import_module(f"{backend}.chartsheet.protection")
    page = importlib.import_module(f"{backend}.worksheet.page")
    charts = importlib.import_module(f"{backend}.chart")
    book = engine.Workbook(write_only=mode == "write_only")
    data = book.create_sheet("Data")
    data.append(["Region", "Units"])
    data.append(["North", 12])
    chart = charts.BarChart()
    chart.add_data(
        charts.Reference(data, min_col=2, min_row=1, max_row=2),
        titles_from_data=True,
    )
    sheet = book.create_chartsheet("Chart")
    sheet.add_chart(chart)
    if mode == "loaded":
        source = tmp_path / "source.xlsx"
        book.save(source)
        book.close()
        book = engine.load_workbook(source)
        sheet = book["Chart"]
    sheet.sheetPr = properties.ChartsheetProperties(
        published=False,
        codeName="ChartCode",
        tabColor=engine.styles.Color(rgb="FF123456"),
    )
    sheet.sheetViews.sheetView[0].zoomScale = 85
    sheet.sheetViews.sheetView[0].zoomToFit = False
    sheet.sheetProtection = protection.ChartsheetProtection(
        content=True, objects=True, password="secret"
    )
    sheet.pageMargins = page.PageMargins(left=0.4, right=0.5, top=0.6, bottom=0.7)
    sheet.pageSetup = page.PrintPageSetup(orientation="landscape", paperSize=9)
    sheet.headerFooter.oddHeader.center.text = "Chart report"
    for index in range(1 if mode == "write_only" else 2):
        output = tmp_path / f"{backend}-{mode}-{index}.xlsx"
        book.save(output)
        for reader in (openpyxl, crabxl):
            for read_only in (False, True):
                result = reader.load_workbook(output, read_only=read_only)
                actual = result["Chart"]
                assert actual.sheetPr.published is False
                assert actual.sheetPr.codeName == "ChartCode"
                assert actual.sheetPr.tabColor.rgb == "FF123456"
                assert actual.sheetViews.sheetView[0].zoomScale == 85
                assert actual.sheetViews.sheetView[0].zoomToFit is False
                assert actual.sheetProtection.content is True
                assert actual.sheetProtection.objects is True
                assert actual.sheetProtection.password == "CEBB"
                assert actual.pageMargins.left == 0.4
                assert actual.pageSetup.orientation == "landscape"
                assert actual.pageSetup.paperSize == 9
                assert actual.headerFooter.oddHeader.center.text == "Chart report"
                assert list(result["Data"].values) == [
                    ("Region", "Units"),
                    ("North", 12),
                ]
                result.close()
        with ZipFile(output) as archive:
            parts = [
                name
                for name in archive.namelist()
                if name.startswith("xl/chartsheets/")
                and name.endswith(".xml")
                and "/_rels/" not in name
            ]
            assert len(parts) == 1
            root = fromstring(archive.read(parts[0]))
            assert len(root.findall("{*}drawing")) == 1
    book.close()


@pytest.mark.parametrize("engine", [crabxl, openpyxl], ids=["crabxl", "openpyxl"])
def test_write_only_chartsheet_between_streamed_worksheets(tmp_path, engine):
    chart_api = importlib.import_module(f"{engine.__name__}.chart")
    workbook = engine.Workbook(write_only=True)
    data = workbook.create_sheet("Data")
    dashboard = workbook.create_chartsheet("Dashboard")
    other = workbook.create_sheet("Other")
    data.append(["Units"])
    other.append([7])
    data.append([12])
    chart = chart_api.BarChart()
    chart.add_data(chart_api.Reference(data, min_col=1, min_row=2, max_row=3))
    dashboard.add_chart(chart)
    if engine is crabxl:
        dashboard.close()
    data.append([24])
    output = tmp_path / f"stream-chartsheet-{engine.__name__}.xlsx"
    workbook.save(output)
    workbook.close()

    verified = openpyxl.load_workbook(output)
    try:
        assert verified.sheetnames == ["Data", "Dashboard", "Other"]
        assert list(verified["Data"].values) == [("Units",), (12,), (24,)]
        assert list(verified["Other"].values) == [(7,)]
        assert (
            verified.chartsheets[0]._charts[0].series[0].val.numRef.f
            == "'Data'!$A$2:$A$3"
        )
    finally:
        verified.close()


def test_chartsheet_creation_and_loaded_round_trip(tmp_path):
    from crabxl.chart import BarChart, Reference
    from crabxl.chartsheet import Chartsheet

    source = tmp_path / "chartsheet.xlsx"
    output = tmp_path / "chartsheet-edited.xlsx"
    book = crabxl.Workbook()
    data = book.active
    data.append([12])
    view = book.create_chartsheet("Dashboard", index=0)
    chart = BarChart()
    chart.add_data(Reference(data, min_col=1, min_row=1, max_row=1))
    view.add_chart(chart)
    assert book.worksheets == [data] and book.chartsheets == [view]
    book.save(source)
    book.close()
    with ZipFile(source) as archive:
        part = next(
            name
            for name in archive.namelist()
            if name.startswith("xl/chartsheets/sheet") and name.endswith(".xml")
        )
        assert (
            fromstring(archive.read(part)).find(".//{*}sheetView").attrib["zoomToFit"]
            == "1"
        )

    loaded = crabxl.load_workbook(source)
    try:
        view = loaded["Dashboard"]
        assert isinstance(view, Chartsheet)
        assert loaded.sheetnames == ["Dashboard", "Sheet"]
        loaded["Sheet"]["A1"] = 24
        second = loaded.create_chartsheet("Second")
        chart = BarChart()
        chart.add_data(Reference(loaded["Sheet"], min_col=1, min_row=1, max_row=1))
        second.add_chart(chart)
        loaded.save(output)
    finally:
        loaded.close()
    verified = openpyxl.load_workbook(output)
    try:
        assert verified.sheetnames == ["Dashboard", "Sheet", "Second"]
        assert [len(view._charts) for view in verified.chartsheets] == [1, 1]
        assert verified["Sheet"]["A1"].value == 24
    finally:
        verified.close()
    readonly = crabxl.load_workbook(output, read_only=True)
    try:
        assert [view.title for view in readonly.chartsheets] == ["Dashboard", "Second"]
        assert [sheet.title for sheet in readonly] == ["Sheet"]
    finally:
        readonly.close()


def build_gallery(engine, path):
    chart_api = importlib.import_module(f"{engine.__name__}.chart")
    book = engine.Workbook()
    data = book.active
    data.title = "Data"
    for row in (("Region", "Units"), ("A", 10), ("B", 20), ("C", 15)):
        data.append(row)
    gallery = book.create_sheet("Gallery")
    for index, name in enumerate(CHARTS):
        chart = getattr(chart_api, name)()
        chart.title = name
        if name in ("ScatterChart", "BubbleChart"):
            values = chart_api.Reference(data, min_col=2, min_row=2, max_row=4)
            size = values if name == "BubbleChart" else None
            chart.series.append(chart_api.Series(values, values, size, title="Units"))
        else:
            chart.add_data(
                chart_api.Reference(data, min_col=2, min_row=1, max_row=4),
                titles_from_data=True,
            )
            chart.set_categories(
                chart_api.Reference(data, min_col=1, min_row=2, max_row=4)
            )
        if name == "ProjectedPieChart":
            chart.splitType = None
            chart.serLines = None
        gallery.add_chart(
            chart, f"{'A' if index % 2 == 0 else 'K'}{2 + index // 2 * 18}"
        )
    book.save(path)
    book.close()


def test_chart_families_match_openpyxl(tmp_path, monkeypatch):
    # Excel requires the type before the series, even though openpyxl can
    # read its own order. Set the oracle's element order for this comparison.
    from openpyxl.chart import ProjectedPieChart

    order = ProjectedPieChart.__elements__
    monkeypatch.setattr(
        ProjectedPieChart,
        "__elements__",
        ("ofPieType",) + tuple(item for item in order if item != "ofPieType"),
    )
    expected = tmp_path / "openpyxl.xlsx"
    actual = tmp_path / "crabxl.xlsx"
    build_gallery(openpyxl, expected)
    build_gallery(crabxl, actual)
    with ZipFile(expected) as reference, ZipFile(actual) as native:
        expected_parts = [
            name for name in reference.namelist() if name.startswith("xl/charts/chart")
        ]
        assert len(expected_parts) == 16
        for part in expected_parts:
            assert canonicalize(
                reference.read(part), rewrite_prefixes=True
            ) == canonicalize(native.read(part), rewrite_prefixes=True)
    workbook = openpyxl.load_workbook(actual)
    try:
        charts = workbook["Gallery"]._charts
        assert [type(chart).__name__ for chart in charts] == list(CHARTS)
        assert [(c.anchor._from.row, c.anchor._from.col) for c in charts] == [
            (1 + i // 2 * 18, i % 2 * 10) for i in range(16)
        ]
    finally:
        workbook.close()


def test_combined_chart_on_loaded_sheet_can_be_edited_and_resaved(tmp_path):
    from crabxl.chart import BarChart, LineChart, Reference
    from crabxl.comments import Comment

    source = tmp_path / "source.xlsx"
    output = tmp_path / "output.xlsx"
    reference = openpyxl.Workbook()
    reference.active.append([10, 20])
    reference.active.append([15, 25])
    original = openpyxl.chart.BarChart()
    original.add_data(
        openpyxl.chart.Reference(reference.active, min_col=1, min_row=1, max_row=2)
    )
    reference.active.add_chart(original, "D2")
    reference.save(source)
    reference.close()

    book = crabxl.load_workbook(source)
    try:
        sheet = book.active
        chart = BarChart()
        chart.add_data(Reference(sheet, min_col=1, min_row=1, max_row=2))
        line = LineChart()
        line.add_data(Reference(sheet, min_col=2, min_row=1, max_row=2))
        chart += line
        sheet.add_chart(chart, "D20")
        book.save(output)
        chart.title = "Combination"
        chart.anchor = "E20"
        sheet["A1"].comment = Comment("Keep the charts", "QA")
        book.save(output)
    finally:
        book.close()

    result = openpyxl.load_workbook(output)
    try:
        original, combined = result.active._charts
        assert (original.anchor._from.row, original.anchor._from.col) == (1, 3)
        assert (combined.anchor._from.row, combined.anchor._from.col) == (19, 4)
        assert combined.title.tx.rich.p[0].r[0].t == "Combination"
        assert [type(chart).__name__ for chart in combined._charts] == [
            "BarChart",
            "LineChart",
        ]
        assert result.active["A1"].comment.text == "Keep the charts"
    finally:
        result.close()


@pytest.mark.parametrize("engine", [crabxl, openpyxl], ids=["crabxl", "openpyxl"])
def test_write_only_drawings_after_interleaved_rows(tmp_path, engine):
    from PIL import Image as PillowImage

    chart_api = importlib.import_module(f"{engine.__name__}.chart")
    image_api = importlib.import_module(f"{engine.__name__}.drawing.image")
    cell_api = importlib.import_module(f"{engine.__name__}.cell")
    picture = tmp_path / "picture.png"
    PillowImage.new("RGB", (16, 12), "blue").save(picture)
    book = engine.Workbook(write_only=True)
    data = book.create_sheet("Data")
    other = book.create_sheet("Other")
    link = cell_api.WriteOnlyCell(data, value="North")
    link.hyperlink = "https://example.com"
    data.append([link, 10])
    other.append(["Other", 3])
    data.append(["South", 20])
    for sheet in (data, other):
        chart = chart_api.BarChart()
        chart.add_data(chart_api.Reference(sheet, min_col=2, min_row=1, max_row=1))
        sheet.add_chart(chart, "D2")
        sheet.add_image(image_api.Image(str(picture)), "A8")
    other.close()
    output = tmp_path / f"stream-{engine.__name__}.xlsx"
    book.save(output)
    book.close()

    with ZipFile(output) as archive:
        sheet_xml = fromstring(archive.read("xl/worksheets/sheet1.xml"))
        assert sheet_xml.find("{*}sheetFormatPr").attrib["defaultRowHeight"] == "15"
        drawing = fromstring(archive.read("xl/drawings/drawing1.xml"))
        assert drawing[0].find("{*}graphicFrame") is not None
        assert drawing[1].find("{*}pic") is not None

    result = openpyxl.load_workbook(output)
    try:
        assert result.sheetnames == ["Data", "Other"]
        assert list(result["Data"].values) == [("North", 10), ("South", 20)]
        assert result["Data"]["A1"].hyperlink.target == "https://example.com"
        for sheet in result.worksheets:
            assert len(sheet._charts) == len(sheet._images) == 1
            chart = sheet._charts[0]
            assert chart.series[0].val.numRef.f == f"'{sheet.title}'!$B$1"
            assert (chart.anchor._from.row, chart.anchor._from.col) == (1, 3)
            assert sheet._images[0]._data() == picture.read_bytes()
    finally:
        result.close()
