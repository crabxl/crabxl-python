"""Reading values must not import the style, drawing or XML modules."""

import subprocess
import sys

SCRIPT = """
import sys
import crabxl_openpyxl as crabxl

book = crabxl.Workbook()
book.active.append([1, "text", 2.5])
book.save(sys.argv[1])
book.close()
for name in [m for m in sys.modules if m.startswith(("crabxl_openpyxl.", "lxml"))]:
    if name.startswith(("crabxl_openpyxl.styles.", "crabxl_openpyxl.descriptors", "crabxl_openpyxl.drawing",
                        "crabxl_openpyxl.chartsheet", "lxml")) and name != "crabxl_openpyxl.styles._base":
        del sys.modules[name]
for read_only in (True, False):
    book = crabxl.load_workbook(sys.argv[1], read_only=read_only)
    rows = list(book.worksheets[0].iter_rows(values_only=True))
    book.close()
    assert rows == [(1, "text", 2.5)], rows
heavy = sorted(
    name
    for name in sys.modules
    if name.startswith(("crabxl_openpyxl.descriptors", "crabxl_openpyxl.drawing", "crabxl_openpyxl.chartsheet", "lxml"))
    or (name.startswith("crabxl_openpyxl.styles.") and name != "crabxl_openpyxl.styles._base")
)
print(heavy)
"""


def test_reading_values_skips_style_and_xml_modules(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT, str(tmp_path / "book.xlsx")],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "[]"


def test_import_does_not_load_styles():
    code = "import sys, crabxl_openpyxl; print(sorted(m for m in sys.modules if m.startswith(('crabxl_openpyxl.styles.', 'lxml')) and m != 'crabxl_openpyxl.styles._base'))"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"
    # The style classes still load on first use.
    code = "import crabxl_openpyxl as crabxl; from crabxl_openpyxl.styles import Font; print(crabxl.Font is Font)"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "True"
