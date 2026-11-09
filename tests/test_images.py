"""Loaded image views keep their native drawing metadata when edited or copied."""

from copy import deepcopy
from importlib import import_module
from io import BytesIO
from xml.etree.ElementTree import SubElement, fromstring, tostring
from zipfile import ZipFile

import openpyxl
import pytest
from PIL import Image as PillowImage


def source_image(path, anchor_kind):
    from openpyxl.drawing.image import Image
    from openpyxl.drawing.spreadsheet_drawing import (
        AbsoluteAnchor,
        AnchorClientData,
        AnchorMarker,
        OneCellAnchor,
        TwoCellAnchor,
    )
    from openpyxl.drawing.xdr import XDRPoint2D, XDRPositiveSize2D

    data = BytesIO()
    PillowImage.new("RGB", (16, 12), "blue").save(data, format="PNG")
    data.seek(0)
    picture = Image(data)
    client = AnchorClientData(fLocksWithSheet=False, fPrintsWithSheet=True)
    if anchor_kind == "one":
        picture.anchor = OneCellAnchor(
            _from=AnchorMarker(col=3, row=1),
            ext=XDRPositiveSize2D(300000, 200000),
            clientData=client,
        )
    elif anchor_kind == "two":
        picture.anchor = TwoCellAnchor(
            _from=AnchorMarker(col=3, row=1),
            to=AnchorMarker(col=5, row=4),
            editAs="oneCell",
            clientData=client,
        )
    else:
        picture.anchor = AbsoluteAnchor(
            pos=XDRPoint2D(20000, 40000),
            ext=XDRPositiveSize2D(300000, 200000),
            clientData=client,
        )
    book = openpyxl.Workbook()
    book.active["A1"] = 5
    book.active.add_image(picture)
    book.save(path)
    book.close()


@pytest.mark.parametrize("action", ["move", "copy", "stream_copy", "remove"])
@pytest.mark.parametrize("anchor_kind", ["one", "two", "absolute"])
def test_loaded_images_match_reference_after_edits(tmp_path, action, anchor_kind):
    source = tmp_path / "source.xlsx"
    source_image(source, anchor_kind)
    snapshots = []
    for name in ("openpyxl", "crabxl"):
        engine = import_module(name)
        book = engine.load_workbook(source)
        picture = book.active._images[0]
        assert (picture.width, picture.height, picture.format) == (16, 12, "png")
        assert picture.anchor.clientData.fLocksWithSheet is False
        assert picture.anchor.clientData.fPrintsWithSheet is True
        if action in ("copy", "stream_copy"):
            copied = deepcopy(picture)
            destination = engine.Workbook(write_only=action == "stream_copy")
            sheet = (
                destination.create_sheet()
                if action == "stream_copy"
                else destination.active
            )
            sheet.append([5])
            sheet.add_image(copied, "E5")
            book.close()
            book = destination
        elif action == "remove":
            book.active._images.clear()
        else:
            picture.anchor = "E5"
        output = tmp_path / f"{name}.xlsx"
        book.save(output)
        book.close()
        reference = openpyxl.load_workbook(output)
        images = reference.active._images
        snapshots.append(
            (
                list(reference.active.values),
                [
                    (
                        image.anchor._from.row,
                        image.anchor._from.col,
                        image.anchor.ext.cx,
                        image.anchor.ext.cy,
                        image._data(),
                    )
                    for image in images
                ],
            )
        )
        reference.close()
    assert snapshots[0] == snapshots[1]


def test_loaded_image_list_replacement_removes_images_without_reading_them(tmp_path):
    import crabxl

    source = tmp_path / "source.xlsx"
    source_image(source, "one")
    book = crabxl.load_workbook(source)
    assert book.active._image_views is None
    book.active._images = []
    target = tmp_path / "target.xlsx"
    book.save(target)
    book.close()
    reference = openpyxl.load_workbook(target)
    assert reference.active._images == []
    reference.close()


@pytest.mark.parametrize("save_before_access", [False, True])
def test_adding_images_keeps_loaded_prefix_lazy_and_preserves_new_view_identity(
    tmp_path, monkeypatch, save_before_access
):
    import crabxl
    from crabxl.drawing.image import Image

    source = tmp_path / "source.xlsx"
    source_image(source, "one")
    book = crabxl.load_workbook(source)
    data = BytesIO()
    PillowImage.new("RGB", (8, 8), "red").save(data, format="PNG")
    data.seek(0)
    added = Image(data)
    output = tmp_path / "output.xlsx"

    def unexpected_projection(*args):
        raise AssertionError("Adding an image must not decode the existing pictures")

    with monkeypatch.context() as patch:
        patch.setattr(Image, "_from_native", unexpected_projection)
        book.active.add_image(added, "F6")
        assert book.active._image_views is None
        if save_before_access:
            book.save(output)
    assert len(book.active._images) == 2
    assert book.active._images[1] is added
    added.anchor = "G7"
    book.save(output)
    book.close()
    reference = openpyxl.load_workbook(output)
    assert len(reference.active._images) == 2
    assert reference.active._images[1].anchor._from.row == 6
    assert reference.active._images[1].anchor._from.col == 6
    reference.close()


@pytest.mark.parametrize("action", ["move", "copy", "stream_copy"])
def test_loaded_image_edits_keep_picture_metadata_and_related_parts(tmp_path, action):
    import crabxl
    from openpyxl.packaging.relationship import get_dependents, get_rels_path

    source = tmp_path / "source.xlsx"
    source_image(source, "one")
    drawing_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    with ZipFile(source) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    drawing = fromstring(parts["xl/drawings/drawing1.xml"])
    picture = drawing.find(".//{*}pic")
    nonvisual = picture.find("{*}nvPicPr/{*}cNvPr")
    nonvisual.set("descr", "Keep this description")
    SubElement(nonvisual, f"{{{drawing_ns}}}hlinkClick", {f"{{{rel_ns}}}id": "rIdLink"})
    extension = SubElement(
        SubElement(picture.find("{*}spPr"), f"{{{drawing_ns}}}extLst"),
        f"{{{drawing_ns}}}ext",
        {"uri": "urn:qa:image"},
    )
    SubElement(
        extension,
        "{urn:qa:image}marker",
        {f"{{{rel_ns}}}id": "rIdMeta", "value": "preserve"},
    )
    parts["xl/drawings/drawing1.xml"] = tostring(drawing)
    relationships = fromstring(parts["xl/drawings/_rels/drawing1.xml.rels"])
    SubElement(
        relationships,
        f"{{{package_ns}}}Relationship",
        {
            "Id": "rIdLink",
            "Type": rel_ns + "/hyperlink",
            "Target": "https://example.com/picture",
            "TargetMode": "External",
        },
    )
    SubElement(
        relationships,
        f"{{{package_ns}}}Relationship",
        {
            "Id": "rIdMeta",
            "Type": "urn:qa:metadata",
            "Target": "../customXml/picture.bin",
        },
    )
    parts["xl/drawings/_rels/drawing1.xml.rels"] = tostring(relationships)
    parts["xl/customXml/picture.bin"] = b"retained image metadata"
    content_types = fromstring(parts["[Content_Types].xml"])
    SubElement(
        content_types,
        "{http://schemas.openxmlformats.org/package/2006/content-types}Default",
        {"Extension": "bin", "ContentType": "application/octet-stream"},
    )
    parts["[Content_Types].xml"] = tostring(content_types)
    with ZipFile(source, "w") as archive:
        for name, data in parts.items():
            archive.writestr(name, data)

    book = crabxl.load_workbook(source)
    image = book.active._images[0]
    if action != "move":
        copied = deepcopy(image)
        destination = crabxl.Workbook(write_only=action == "stream_copy")
        sheet = (
            destination.create_sheet()
            if action == "stream_copy"
            else destination.active
        )
        sheet.add_image(copied, "E5")
        sheet.append([5])
        book.close()
        book = destination
    else:
        image.anchor = "E5"
    output = tmp_path / "output.xlsx"
    book.save(output)
    book.close()
    with ZipFile(output) as archive:
        worksheet = fromstring(archive.read("xl/worksheets/sheet1.xml"))
        drawing_id = worksheet.find("{*}drawing").get(f"{{{rel_ns}}}id")
        sheet_relationships = {
            edge.Id: edge
            for edge in get_dependents(
                archive, get_rels_path("xl/worksheets/sheet1.xml")
            )
        }
        drawing_part = sheet_relationships[drawing_id].Target
        picture = fromstring(archive.read(drawing_part)).find(".//{*}pic")
        assert (
            picture.find("{*}nvPicPr/{*}cNvPr").get("descr") == "Keep this description"
        )
        assert picture.find(".//{urn:qa:image}marker").get("value") == "preserve"
        relationships = {
            edge.Id: edge
            for edge in get_dependents(archive, get_rels_path(drawing_part))
        }
        hyperlink_id = picture.find("{*}nvPicPr/{*}cNvPr/{*}hlinkClick").get(
            f"{{{rel_ns}}}id"
        )
        assert relationships[hyperlink_id].Target == "https://example.com/picture"
        assert relationships[hyperlink_id].TargetMode == "External"
        metadata_id = picture.find(".//{urn:qa:image}marker").get(f"{{{rel_ns}}}id")
        assert (
            archive.read(relationships[metadata_id].Target)
            == b"retained image metadata"
        )
