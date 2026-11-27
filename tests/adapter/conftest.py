"""Shared generated OOXML fixtures; no copied upstream implementation or data."""

import zipfile
from xml.sax.saxutils import escape

import openpyxl
import pytest


@pytest.fixture
def shared_strings_source():
    def generate(path, values):
        if not path.exists():
            book = openpyxl.Workbook()
            book.save(path)
            book.close()
        with zipfile.ZipFile(path) as archive:
            parts = {name: archive.read(name) for name in archive.namelist()}
        main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        count = len(values)
        parts["xl/sharedStrings.xml"] = (
            f'<sst xmlns="{main}" count="{count}" uniqueCount="{count}">'
            + "".join(f"<si><t>{escape(value)}</t></si>" for value in values)
            + "</sst>"
        ).encode()
        parts["xl/worksheets/sheet1.xml"] = (
            f'<worksheet xmlns="{main}"><dimension ref="A1:A{count}"/><sheetData>'
            + "".join(
                f'<row r="{index + 1}"><c r="A{index + 1}" t="s"><v>{index}</v></c></row>'
                for index in range(count)
            )
            + "</sheetData></worksheet>"
        ).encode()
        parts["xl/_rels/workbook.xml.rels"] = parts[
            "xl/_rels/workbook.xml.rels"
        ].replace(
            b"</Relationships>",
            b'<Relationship Id="shared" '
            b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
            b'Target="sharedStrings.xml"/></Relationships>',
        )
        parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(
            b"</Types>",
            b'<Override PartName="/xl/sharedStrings.xml" '
            b'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
            b"</Types>",
        )
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in parts.items():
                archive.writestr(name, content)
        return path

    return generate
