"""A workbook tab containing charts and no worksheet cells."""

from ..drawing.spreadsheet_drawing import AbsoluteAnchor
from ..worksheet.header_footer import HeaderFooter
from ..worksheet.page import PageMargins, PrintPageSetup
from ..worksheet.worksheet import Worksheet
from .custom import CustomChartsheetViews
from .properties import ChartsheetProperties
from .protection import ChartsheetProtection
from .publish import WebPublishItems
from .relation import DrawingHF as DrawingHF
from .relation import SheetBackgroundPicture as SheetBackgroundPicture
from .views import ChartsheetViewList

_PROPERTIES = {
    "sheetPr": ChartsheetProperties,
    "sheetViews": ChartsheetViewList,
    "sheetProtection": ChartsheetProtection,
    "customSheetViews": CustomChartsheetViews,
    "pageMargins": PageMargins,
    "pageSetup": PrintPageSetup,
    "headerFooter": HeaderFooter,
    "webPublishItems": WebPublishItems,
}


def _merge_property(original, replacement, value):
    """Retain unmodelled XML while replacing the descriptor's owned fields."""
    from copy import deepcopy

    from ..styles.colors import Color

    if original is None:
        return replacement
    result = deepcopy(original)
    attributes = getattr(value, "__attrs__", tuple(replacement.attrib))
    if isinstance(value, Color):
        attributes = ("rgb", "indexed", "auto", "theme", "tint")
    for name in list(result.attrib):
        if name.rsplit("}", 1)[-1] in attributes:
            del result.attrib[name]
    result.attrib.update(replacement.attrib)
    result.text = replacement.text
    for name in getattr(value, "__elements__", ()):
        old = [
            child
            for child in result
            if isinstance(child.tag, str) and child.tag.rsplit("}", 1)[-1] == name
        ]
        new = [
            child
            for child in replacement
            if isinstance(child.tag, str) and child.tag.rsplit("}", 1)[-1] == name
        ]
        position = list(result).index(old[0]) if old else len(result)
        for child in old:
            result.remove(child)
        values = getattr(value, name, None)
        values = values if isinstance(values, (list, tuple)) else [values]
        for index, child in enumerate(new):
            merged = _merge_property(
                old[index] if index < len(old) else None,
                child,
                values[index] if index < len(values) else None,
            )
            result.insert(position + index, merged)
    return result


def _chartsheet_property(name):
    def get(self):
        return self._properties()["values"][name]

    def set(self, value):
        if value is None:
            if name in ("sheetViews", "headerFooter"):
                raise TypeError(f"{name} cannot be None")
        elif not isinstance(value, _PROPERTIES[name]):
            raise TypeError(f"Expected {_PROPERTIES[name].__name__}")
        self._properties()["values"][name] = value

    return property(get, set)


class Chartsheet(Worksheet):
    """A chart-only workbook tab."""

    __slots__ = ()

    tagname = "chartsheet"
    idx_base = 0
    namespace = None
    mime_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.chartsheet+xml"
    )

    @property
    def path(self):
        # openpyxl numbers chartsheet parts in tab order when it saves.
        return f"/xl/chartsheets/sheet{self.parent.chartsheets.index(self) + 1}.xml"

    sheetPr = _chartsheet_property("sheetPr")
    sheetViews = _chartsheet_property("sheetViews")
    sheetProtection = _chartsheet_property("sheetProtection")
    customSheetViews = _chartsheet_property("customSheetViews")
    pageMargins = _chartsheet_property("pageMargins")
    pageSetup = _chartsheet_property("pageSetup")
    headerFooter = _chartsheet_property("headerFooter")
    HeaderFooter = headerFooter
    webPublishItems = _chartsheet_property("webPublishItems")
    page_margins = pageMargins
    page_setup = pageSetup
    views = sheetViews

    @property
    def sheet_view(self):
        return self.sheetViews.sheetView[0]

    def _properties(self):
        state = getattr(self, "_chartsheet_state", None)
        if state is not None:
            return state
        from .._native import reader_chartsheet_read, sheet_chartsheet_read
        from ..xml.functions import fromstring, tostring

        self.parent._check_open()
        if self.parent.write_only:
            xml = b""
        elif self.parent.read_only:
            xml = bytes(reader_chartsheet_read(self.parent._reader, self.title))
        else:
            xml = bytes(sheet_chartsheet_read(self._feature_handle()))
        root = fromstring(
            xml
            or b'<chartsheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0" zoomToFit="1"/></sheetViews></chartsheet>'
        )
        values = {}
        for tag, cls in _PROPERTIES.items():
            element = root.find("{*}" + tag)
            values[tag] = cls.from_tree(element) if element is not None else None
        if values["sheetViews"] is None:
            values["sheetViews"] = ChartsheetViewList()
        if values["headerFooter"] is None:
            values["headerFooter"] = HeaderFooter()
        self._chartsheet_state = state = {
            "root": root,
            "values": values,
            "serialized": {
                tag: tostring(value.to_tree()) if value is not None else None
                for tag, value in values.items()
            },
        }
        state["previous"] = self._chartsheet_xml()
        return state

    def _chartsheet_xml(self):
        from copy import deepcopy

        from ..xml.functions import tostring

        state = getattr(self, "_chartsheet_state", None)
        if state is None:
            return None
        root = deepcopy(state["root"])
        for child in list(root):
            if (
                isinstance(child.tag, str)
                and child.tag.rsplit("}", 1)[-1] in _PROPERTIES
            ):
                root.remove(child)
        position = 0
        for tag, value in state["values"].items():
            original = state["root"].find("{*}" + tag)
            serialized = tostring(value.to_tree()) if value is not None else None
            if serialized == state["serialized"][tag]:
                element = deepcopy(original) if original is not None else None
            elif value is not None and (tag != "headerFooter" or value):
                element = _merge_property(original, value.to_tree(), value)
            else:
                element = None
            if element is not None:
                root.insert(position, element)
                position += 1
        return tostring(root)

    def _flush_features(self):
        from .._native import sheet_chartsheet_write

        state = getattr(self, "_chartsheet_state", None)
        if state is not None:
            xml = self._chartsheet_xml()
            if xml != state["previous"]:
                sheet_chartsheet_write(self._feature_handle(), xml)
                state["previous"] = xml
        super()._flush_features()

    @property
    def oddHeader(self):
        return self.headerFooter.oddHeader

    @oddHeader.setter
    def oddHeader(self, value):
        self.headerFooter.oddHeader = value

    @property
    def oddFooter(self):
        return self.headerFooter.oddFooter

    @oddFooter.setter
    def oddFooter(self, value):
        self.headerFooter.oddFooter = value

    @property
    def evenHeader(self):
        return self.headerFooter.evenHeader

    @evenHeader.setter
    def evenHeader(self, value):
        self.headerFooter.evenHeader = value

    @property
    def evenFooter(self):
        return self.headerFooter.evenFooter

    @evenFooter.setter
    def evenFooter(self, value):
        self.headerFooter.evenFooter = value

    @property
    def firstHeader(self):
        return self.headerFooter.firstHeader

    @firstHeader.setter
    def firstHeader(self, value):
        self.headerFooter.firstHeader = value

    @property
    def firstFooter(self):
        return self.headerFooter.firstFooter

    @firstFooter.setter
    def firstFooter(self, value):
        self.headerFooter.firstFooter = value

    def add_chart(self, chart):
        super().add_chart(chart, AbsoluteAnchor())

    def cell(self, *args, **kwargs):
        raise TypeError("Chartsheets do not contain cells")

    __getitem__ = __setitem__ = __delitem__ = append = iter_rows = iter_cols = cell
