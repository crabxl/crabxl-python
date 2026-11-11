# Pane descriptor layout adapted from openpyxl, Copyright (c) 2010-2024 openpyxl.
# MIT license in third_party/licenses/openpyxl-MIT.txt.
"""Worksheet compatibility facade over canonical native handles."""

import re
from weakref import WeakValueDictionary

from .._native import (
    NativeSheet,
)
from .._values import _ADDRESS, _address, _column, _encode, _letters, _range
from ..cell.cell import Cell, MergedCell


class Worksheet:
    """Sparse worksheet using the same public call conventions as openpyxl."""

    SHEETSTATE_VISIBLE = "visible"
    SHEETSTATE_HIDDEN = "hidden"
    SHEETSTATE_VERYHIDDEN = "veryHidden"

    mime_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
    )
    legacy_drawing = None

    BREAK_NONE = 0
    BREAK_ROW = 1
    BREAK_COLUMN = 2

    PAPERSIZE_LETTER = "1"
    PAPERSIZE_LETTER_SMALL = "2"
    PAPERSIZE_TABLOID = "3"
    PAPERSIZE_LEDGER = "4"
    PAPERSIZE_LEGAL = "5"
    PAPERSIZE_STATEMENT = "6"
    PAPERSIZE_EXECUTIVE = "7"
    PAPERSIZE_A3 = "8"
    PAPERSIZE_A4 = "9"
    PAPERSIZE_A4_SMALL = "10"
    PAPERSIZE_A5 = "11"

    ORIENTATION_PORTRAIT = "portrait"
    ORIENTATION_LANDSCAPE = "landscape"

    @property
    def path(self):
        # openpyxl numbers worksheet parts in tab order when it saves.
        return f"/xl/worksheets/sheet{self.parent.worksheets.index(self) + 1}.xml"

    @property
    def encoding(self):
        return self.parent.encoding

    @property
    def merged_cell_ranges(self):
        return list(self.merged_cells.ranges)

    def set_printer_settings(self, paper_size, orientation):
        self.page_setup.paperSize = paper_size
        self.page_setup.orientation = orientation

    @property
    def array_formulae(self):
        from .formula import ArrayFormula

        return {
            cell.coordinate: cell.value.ref
            for row in self.iter_rows()
            for cell in row
            if cell.data_type == "f" and isinstance(cell.value, ArrayFormula)
        }

    __slots__ = (
        "parent",
        "_title",
        "_existing",
        "_native",
        "_cells",
        "_row_dimensions",
        "_column_dimensions",
        "_merged_cells",
        "_rich_views",
        "_assigned_rich_views",
        "_hyperlink_views",
        "_image_views",
        "_new_images",
        "_image_state",
        "_charts",
        "_chart_state",
        "_pivot_state",
        "_new_pivots",
        "_pivot_creation_state",
        "_views",
        "_views_previous",
        "_printing",
        "_printing_previous",
        "_chartsheet_state",
        "_feat",
        "_names",
        "_print_rows",
        "_print_cols",
        "_print_area",
        "__weakref__",
    )

    def __init__(self, parent, title=None, *, _existing=False, _native=None):
        self._printing = None
        self._printing_previous = None
        self._views = None
        self._views_previous = None
        self.parent = parent
        self._title = (
            (title or "Sheet") if _existing else parent._unique_title(title or "Sheet")
        )
        self._existing = _existing
        self._native = (
            _native
            if _native is not None
            else None
            if _existing
            else NativeSheet(self._title, parent._max_bytes)
        )
        from ._cell_cache import CellCache

        self._cells = CellCache(self)
        self._rich_views = WeakValueDictionary()
        self._assigned_rich_views = {}
        self._hyperlink_views = {}
        self._image_views = None if _existing else []
        self._new_images = []
        self._image_state = (None, ())
        self._charts = []
        self._chart_state = (None, ())
        self._pivot_state = None
        self._new_pivots = []
        self._pivot_creation_state = (None, ())
        self._feat = self._names = self._print_rows = self._print_cols = None
        self._print_area = None
        self._row_dimensions = self._column_dimensions = None
        self._merged_cells = None
        self._validate_title(self._title)

    # -- features (tables, filters, rules, validation, comments, names) ----

    def _feature_handle(self):
        # Features load without cells; do not store this lazy handle as the
        # cell model handle, or cell reads would see an unloaded sheet.
        if self._native is not None:
            return self._native
        return self.parent._editor.sheet_handle(self.title)

    def _views_source(self):
        return bytes(self._model().views_xml())

    def _printing_source(self):
        return bytes(self._model().printing_xml())

    def _state(self):
        state = self._feat
        if state is None:
            self.parent._check_open()
            from .._features import SheetState

            state = self._feat = SheetState(self)
        return state

    def _flush_features(self):
        if self._printing is not None:
            current = self._printing_xml()
            if current != self._printing_previous:
                self._model().set_printing_xml(current)
                self._printing_previous = current

        if self._views is not None:
            from ..xml.functions import tostring

            current = tostring(self._views.to_tree())
            if current != self._views_previous:
                self._model().set_views_xml(current)
                self._views_previous = current

        state = None if self.parent.write_only else self._feat
        if state is not None and not self.parent.read_only:
            state.push()
        if self._pivot_state is not None:
            self._pivot_state.push(self)
        if self._new_pivots or self._pivot_creation_state[1]:
            from .._native import sheet_pivots_write

            base, previous = self._pivot_creation_state
            sources = self._pivot_cache_sources()
            current = self._pivot_inputs()
            if current != previous:
                base = sheet_pivots_write(
                    self._feature_handle(), base, current, sources
                )
                self._pivot_creation_state = (base, current)
        images = self._new_images if self._image_views is None else self._image_views
        if images or self._image_state[1] or self._image_state[0] is not None:
            from .._native import sheet_images_write

            base, previous = self._image_state
            current = tuple(image._native_input() for image in images)
            if current != previous:
                base = sheet_images_write(self._feature_handle(), base, current)
                self._image_state = (base, current)
        if self._charts or self._chart_state[1]:
            from .._native import sheet_charts_write

            base, previous = self._chart_state
            current = tuple(chart._native_input() for chart in self._charts)
            if current != previous:
                base = sheet_charts_write(self._feature_handle(), base, current)
                self._chart_state = (base, current)

    def add_chart(self, chart, anchor=None):
        """Add a chart to the worksheet, optionally changing its anchor."""
        from ..chart._chart import ChartBase

        self.parent._check_open()
        if self.parent.write_only and (self.closed or self._drawings_prepared):
            from ..utils.exceptions import WorkbookAlreadySaved

            raise WorkbookAlreadySaved("Workbook has already been saved")
        if not isinstance(chart, ChartBase):
            raise TypeError("Only chart objects can be added")
        if anchor is not None:
            chart.anchor = anchor
        self._charts.append(chart)

    @property
    def _pivots(self):
        if self.parent.read_only:
            return ()
        if self.parent.write_only or not self._existing:
            return tuple(self._new_pivots)
        if self._pivot_state is None:
            from ..pivot._loaded import bind_pivots

            bind_pivots(self)
        return self._pivot_state.pivots + tuple(self._new_pivots)

    def _pivot_cache_sources(self):
        sources, pushed = {}, set()
        for pivot in self._new_pivots:
            cache = pivot.cache
            origin = getattr(cache, "_crabxl_source", None)
            if origin is None or origin[1]() is not cache:
                continue
            source = origin[0]()
            if (
                source is None
                or source.parent is not self.parent
                or source not in self.parent.worksheets
            ):
                continue
            index = next(
                (
                    index
                    for index, existing in enumerate(source._pivot_state.pivots)
                    if existing.cache is cache
                ),
                None,
            )
            if index is None:
                continue
            if source is not self and source not in pushed:
                source._pivot_state.push(source)
                pushed.add(source)
            sources[id(cache)] = (id(cache), source.title, index)
        return tuple(sources.values())

    def _pivot_inputs(self):
        from ..xml.functions import tostring

        return tuple(
            (
                id(pivot.cache),
                tostring(pivot.to_tree()),
                tostring(pivot.cache.to_tree()),
                tostring(pivot.cache.records.to_tree())
                if pivot.cache.records is not None
                else None,
            )
            for pivot in self._new_pivots
        )

    def add_pivot(self, pivot):
        from ..pivot.table import TableDefinition

        self.parent._check_open()
        from ..chartsheet import Chartsheet

        if isinstance(self, Chartsheet):
            raise TypeError("Pivot tables require a cell worksheet")
        if self.parent.write_only and (self.closed or self._drawings_prepared):
            from ..utils.exceptions import WorkbookAlreadySaved

            raise WorkbookAlreadySaved("Workbook has already been saved")
        if not isinstance(pivot, TableDefinition):
            raise TypeError("Expected a pivot TableDefinition")
        if pivot.cache is None:
            raise ValueError("A pivot table requires a cache")
        self._new_pivots.append(pivot)

    @property
    def _images(self):
        if self._image_views is None:
            from .._native import sheet_images_read
            from ..drawing.image import Image

            prototypes = sheet_images_read(self._feature_handle())
            base, previous = self._image_state
            if base is not None:
                prototypes = prototypes[:base]
            images = [Image._from_native(value) for value in prototypes]
            self._image_state = (
                0,
                tuple(image._native_input() for image in images) + previous,
            )
            self._image_views = images + self._new_images
            self._new_images = []
        return self._image_views

    @_images.setter
    def _images(self, value):
        if self._existing and self._image_views is None:
            self._image_state = (0, None)
            self._new_images = []
        self._image_views = value

    def add_image(self, img, anchor=None):
        """Add an image to the worksheet, optionally changing its anchor."""
        from ..drawing.image import Image

        self.parent._check_open()
        if self.parent.write_only and (self.closed or self._drawings_prepared):
            from ..utils.exceptions import WorkbookAlreadySaved

            raise WorkbookAlreadySaved("Workbook has already been saved")
        if not isinstance(img, Image):
            raise TypeError("Only Image objects can be added")
        if anchor is not None:
            img.anchor = anchor
        if self._image_views is None:
            self._new_images.append(img)
        else:
            self._image_views.append(img)

    @property
    def tables(self):
        return self._state().get("tables")

    def add_table(self, table):
        """Check for a duplicate name in defined names and tables, then add."""
        from .table import Table

        if not isinstance(table, Table):
            raise TypeError("Only Table objects can be added")
        if self.parent._duplicate_name(table.name):
            raise ValueError("Table with name {0} already exists".format(table.name))
        self.tables.add(table)

    @property
    def auto_filter(self):
        return self._state().get("auto_filter")

    @auto_filter.setter
    def auto_filter(self, value):
        self._state().objs["auto_filter"] = value

    @property
    def conditional_formatting(self):
        return self._state().get("conditional_formatting")

    @conditional_formatting.setter
    def conditional_formatting(self, value):
        self._state().objs["conditional_formatting"] = value

    @property
    def data_validations(self):
        return self._state().get("data_validations")

    @data_validations.setter
    def data_validations(self, value):
        self._state().objs["data_validations"] = value

    def add_data_validation(self, data_validation):
        """Add a data-validation object to the sheet."""
        self.data_validations.append(data_validation)

    @property
    def protection(self):
        return self._state().get("protection")

    @protection.setter
    def protection(self, value):
        self._state().objs["protection"] = value

    @property
    def scenarios(self):
        return self._state().get("scenarios")

    @scenarios.setter
    def scenarios(self, value):
        self._state().objs["scenarios"] = value

    @property
    def HeaderFooter(self):
        return self._state().get("header_footer")

    @HeaderFooter.setter
    def HeaderFooter(self, value):
        self._state().objs["header_footer"] = value

    def _comment_map(self):
        return self._state().get("comments")

    def _relocate_comments(self, transform):
        state = self._feat
        if state is None or "comments" not in state.objs:
            return
        moved = {}
        for key, comment in state.objs["comments"].items():
            target = transform(*key)
            comment._parent = None
            if target is not None:
                moved[target] = comment
        state.objs["comments"] = moved

    def _local_names(self):
        self.parent._names_state()
        if self._names is None:
            from ..workbook.defined_name import DefinedNameDict

            self._names = DefinedNameDict()
        return self._names

    @property
    def defined_names(self):
        return self._local_names()

    @defined_names.setter
    def defined_names(self, value):
        self.parent._names_state()
        self._names = value

    @property
    def print_title_rows(self):
        self.parent._names_state()
        if self._print_rows:
            return str(self._print_rows)

    @print_title_rows.setter
    def print_title_rows(self, rows):
        from .print_settings import RowRange

        self.parent._names_state()
        if rows is not None:
            self._print_rows = RowRange(rows)

    @property
    def print_title_cols(self):
        self.parent._names_state()
        if self._print_cols:
            return str(self._print_cols)

    @print_title_cols.setter
    def print_title_cols(self, cols):
        from .print_settings import ColRange

        self.parent._names_state()
        if cols is not None:
            self._print_cols = ColRange(cols)

    @property
    def print_titles(self):
        from .print_settings import PrintTitles

        self.parent._names_state()
        if not (self._print_rows or self._print_cols):
            return None
        return str(
            PrintTitles(cols=self._print_cols, rows=self._print_rows, title=self.title)
        )

    @property
    def print_area(self):
        self.parent._names_state()
        if self._print_area is None:
            return ""
        self._print_area.title = self.title
        return str(self._print_area)

    @print_area.setter
    def print_area(self, value):
        from .print_settings import PrintArea

        self.parent._names_state()
        if not value:
            self._print_area = None
        elif isinstance(value, str):
            self._print_area = PrintArea.from_string(value)
        elif hasattr(value, "__iter__"):
            self._print_area = PrintArea.from_string(",".join(value))

    @property
    def oddHeader(self):
        return self.HeaderFooter.oddHeader

    @oddHeader.setter
    def oddHeader(self, value):
        self.HeaderFooter.oddHeader = value

    @property
    def oddFooter(self):
        return self.HeaderFooter.oddFooter

    @oddFooter.setter
    def oddFooter(self, value):
        self.HeaderFooter.oddFooter = value

    @property
    def evenHeader(self):
        return self.HeaderFooter.evenHeader

    @evenHeader.setter
    def evenHeader(self, value):
        self.HeaderFooter.evenHeader = value

    @property
    def evenFooter(self):
        return self.HeaderFooter.evenFooter

    @evenFooter.setter
    def evenFooter(self, value):
        self.HeaderFooter.evenFooter = value

    @property
    def firstHeader(self):
        return self.HeaderFooter.firstHeader

    @firstHeader.setter
    def firstHeader(self, value):
        self.HeaderFooter.firstHeader = value

    @property
    def firstFooter(self):
        return self.HeaderFooter.firstFooter

    @firstFooter.setter
    def firstFooter(self, value):
        self.HeaderFooter.firstFooter = value

    @property
    def row_dimensions(self):
        from ..worksheet.dimensions import DimensionHolder

        if self._row_dimensions is None:
            self._row_dimensions = DimensionHolder(self, rows=True)
        return self._row_dimensions

    @property
    def column_dimensions(self):
        from ..worksheet.dimensions import DimensionHolder

        if self._column_dimensions is None:
            self._column_dimensions = DimensionHolder(self)
        return self._column_dimensions

    @property
    def column_groups(self):
        return [
            dimension.range
            for dimension in self.column_dimensions.values()
            if dimension.min and dimension.max > dimension.min
        ]

    def _printing_get(self, name):
        if self._printing is None:
            from ..xml.functions import fromstring
            from .page import PageMargins, PrintOptions, PrintPageSetup
            from .pagebreak import ColBreak, RowBreak
            from .properties import PageSetupProperties

            root = fromstring(self._printing_source())
            classes = {
                "pageSetup": PrintPageSetup,
                "pageMargins": PageMargins,
                "printOptions": PrintOptions,
                "rowBreaks": RowBreak,
                "colBreaks": ColBreak,
                "pageSetUpPr": PageSetupProperties,
            }
            self._printing = {}
            for tag, cls in classes.items():
                element = root.find(".//{*}" + tag)
                obj = cls.from_tree(element) if element is not None else cls()
                if tag == "pageSetup":
                    obj._parent = self
                    if element is not None:
                        obj.id = element.get(
                            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                        )
                self._printing[tag] = obj
            from .dimensions import SheetFormatProperties
            from .properties import WorksheetProperties

            element = root.find("{*}sheetPr")
            properties = (
                WorksheetProperties.from_tree(element)
                if element is not None
                else WorksheetProperties()
            )
            # page_setup.fitToPage and sheet_properties.pageSetUpPr share one object.
            properties.pageSetUpPr = self._printing["pageSetUpPr"]
            self._printing["sheetPr"] = properties
            element = root.find("{*}sheetFormatPr")
            self._printing["sheetFormatPr"] = (
                SheetFormatProperties.from_tree(element)
                if element is not None
                else SheetFormatProperties()
            )
            self._printing_previous = self._printing_xml()
        return self._printing[name]

    def _printing_xml(self):
        from ..xml.functions import Element, SubElement, tostring

        root = Element(
            "worksheet",
            xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        )
        properties = self._printing["sheetPr"]
        properties.pageSetUpPr = self._printing["pageSetUpPr"]
        root.append(properties.to_tree())
        root.append(self._printing["sheetFormatPr"].to_tree())
        SubElement(root, "sheetData")
        for tag in (
            "printOptions",
            "pageMargins",
            "pageSetup",
            "rowBreaks",
            "colBreaks",
        ):
            root.append(self._printing[tag].to_tree())
        return tostring(root)

    @property
    def sheet_properties(self):
        return self._printing_get("sheetPr")

    @sheet_properties.setter
    def sheet_properties(self, value):
        from .properties import PageSetupProperties

        self._printing_get("sheetPr")
        if value.pageSetUpPr is None:
            value.pageSetUpPr = PageSetupProperties()
        self._printing["sheetPr"] = value
        self._printing["pageSetUpPr"] = value.pageSetUpPr

    @property
    def sheet_format(self):
        return self._printing_get("sheetFormatPr")

    @sheet_format.setter
    def sheet_format(self, value):
        self._printing_get("sheetFormatPr")
        self._printing["sheetFormatPr"] = value

    @property
    def page_setup(self):
        return self._printing_get("pageSetup")

    @page_setup.setter
    def page_setup(self, value):
        self._printing_get("pageSetup")
        value._parent = self
        self._printing["pageSetup"] = value

    @property
    def page_margins(self):
        return self._printing_get("pageMargins")

    @page_margins.setter
    def page_margins(self, value):
        self._printing_get("pageMargins")
        self._printing["pageMargins"] = value

    @property
    def print_options(self):
        return self._printing_get("printOptions")

    @print_options.setter
    def print_options(self, value):
        self._printing_get("printOptions")
        self._printing["printOptions"] = value

    @property
    def row_breaks(self):
        return self._printing_get("rowBreaks")

    @row_breaks.setter
    def row_breaks(self, value):
        self._printing_get("rowBreaks")
        self._printing["rowBreaks"] = value

    @property
    def col_breaks(self):
        return self._printing_get("colBreaks")

    @col_breaks.setter
    def col_breaks(self, value):
        self._printing_get("colBreaks")
        self._printing["colBreaks"] = value

    @property
    def views(self):
        if self._views is None:
            from ..xml.functions import fromstring, tostring
            from .views import SheetViewList

            self._views = SheetViewList.from_tree(fromstring(self._views_source()))
            self._views_previous = tostring(self._views.to_tree())
        return self._views

    @property
    def sheet_view(self):
        return self.views.active

    @property
    def active_cell(self):
        return self.sheet_view.selection[0].activeCell

    @property
    def selected_cell(self):
        return self.sheet_view.selection[0].sqref

    @property
    def show_gridlines(self):
        return self.sheet_view.showGridLines

    @property
    def freeze_panes(self):
        if self.sheet_view.pane is not None:
            return self.sheet_view.pane.topLeftCell

    @freeze_panes.setter
    def freeze_panes(self, topLeftCell=None):
        from .views import Pane, Selection

        if isinstance(topLeftCell, Cell):
            topLeftCell = topLeftCell.coordinate
        if topLeftCell == "A1":
            topLeftCell = None

        if not topLeftCell:
            self.sheet_view.pane = None
            return

        row, column = _address(topLeftCell)

        view = self.sheet_view
        view.pane = Pane(topLeftCell=topLeftCell, activePane="topRight", state="frozen")
        view.selection[0].pane = "topRight"

        if column > 1:
            view.pane.xSplit = column - 1
        if row > 1:
            view.pane.ySplit = row - 1
            view.pane.activePane = "bottomLeft"
            view.selection[0].pane = "bottomLeft"
            if column > 1:
                view.selection[0].pane = "bottomRight"
                view.pane.activePane = "bottomRight"

        if row > 1 and column > 1:
            sel = list(view.selection)
            sel.insert(0, Selection(pane="topRight", activeCell=None, sqref=None))
            sel.insert(1, Selection(pane="bottomLeft", activeCell=None, sqref=None))
            view.selection = sel

    @property
    def merged_cells(self):
        from .merge import MultiCellRange

        if self._merged_cells is None:
            self._merged_cells = MultiCellRange(self)
        return self._merged_cells

    @merged_cells.setter
    def merged_cells(self, value):
        if value is self._merged_cells:
            return
        self.merged_cells.ranges = value.ranges if hasattr(value, "ranges") else value

    def merge_cells(
        self,
        range_string=None,
        start_row=None,
        start_column=None,
        end_row=None,
        end_column=None,
    ):
        self._merge_cells(
            range_string, start_row, start_column, end_row, end_column, True
        )

    def unmerge_cells(
        self,
        range_string=None,
        start_row=None,
        start_column=None,
        end_row=None,
        end_column=None,
    ):
        self._merge_cells(
            range_string, start_row, start_column, end_row, end_column, False
        )

    def _merge_cells(
        self,
        range_string,
        start_row,
        start_column,
        end_row,
        end_column,
        merge,
        declare=True,
    ):
        if range_string is not None:
            bounds = _range(str(range_string))
        elif all(
            value is not None
            for value in (start_row, start_column, end_row, end_column)
        ):
            bounds = _range(
                f"{_letters(start_column)}{start_row}:{_letters(end_column)}{end_row}"
            )
        else:
            raise ValueError("A range or all four row/column bounds are required")
        first_row, first_col, last_row, last_col = bounds
        aliases = [
            (key, cell, cell._snapshot(), cell.hyperlink)
            for key, cell in list(self._cells.items())
            if declare
            and key != (first_row, first_col)
            and first_row <= key[0] <= last_row
            and first_col <= key[1] <= last_col
        ]
        self._model().merge_cells(tuple(value - 1 for value in bounds), merge, declare)

        def relocate(row, column):
            if (
                declare
                and (row, column) != (first_row, first_col)
                and (first_row <= row <= last_row and first_col <= column <= last_col)
            ):
                return None
            return row, column

        self._relocate_rich_views(relocate)
        self._relocate_hyperlink_views(relocate)
        self._relocate_comments(relocate)
        for key, cell, snapshot, hyperlink in aliases:
            cell._detached = snapshot
            cell._detached_hyperlink = hyperlink
            self._cells.pop(key, None)

    @staticmethod
    def _validate_title(title):
        if not isinstance(title, str) or not title:
            raise ValueError("Title must have at least one character")
        if re.search(r"[\\*?:/\[\]]", title):
            raise ValueError("Invalid character in sheet title")
        if len(title) > 31:
            import warnings

            warnings.warn(
                "Title is more than 31 characters. Some applications may not be able to read the file"
            )

    @property
    def title(self):
        return self._title

    @property
    def sheet_state(self):
        self.parent._check_open()
        if self._existing:
            return self.parent._reader.sheet_state(self.title)
        return self._native.sheet_state()

    @sheet_state.setter
    def sheet_state(self, state):
        self.parent._check_open()
        if self._existing:
            self.parent._editor.set_sheet_state(self.title, state, self.parent._active)
        else:
            self._native.set_sheet_state(state)

    @title.setter
    def title(self, title):
        self._validate_title(title)
        self.parent._check_open()
        if title != self._title:
            title = self.parent._unique_title(title, exclude=self)
            if self._existing:
                self.parent._editor.rename_sheet(self._title, title)
            else:
                self._native.rename(title)
            self._title = title

    def _model(self):
        self.parent._check_open()
        if self._native is None:
            self._native = self.parent._reader.load_sheet(
                self.title, self.parent._max_bytes, self.parent.data_only
            )
        return self._native

    def _get(self, row, column):
        self.parent._check_open()
        if self._existing:
            value = self.parent._editor.pending(self.title, row - 1, column - 1)
            if value is not None:
                return value
        return self._model().get(row - 1, column - 1)

    def _set(self, row, column, value):
        if isinstance(value, bytes):
            value = value.decode(self.parent.encoding)
        tagged = _encode(value)
        self._set_tagged(row, column, tagged)
        if tagged[0] == "rich":
            value._bind(self, row, column)

    def _set_tagged(self, row, column, tagged):
        self.parent._check_open()
        if self._existing:
            self.parent._editor.set(self.title, row - 1, column - 1, tagged)
        else:
            self._native.set(row - 1, column - 1, tagged)
        self._rich_views.pop((row, column), None)
        self._assigned_rich_views.pop((row, column), None)

    def _relocate_rich_views(self, transform):
        changed = []
        for coordinate, value in self._rich_views.items():
            target = transform(*coordinate)
            if target != coordinate:
                changed.append(
                    (coordinate, value, target, coordinate in self._assigned_rich_views)
                )
        for coordinate, value, _, _ in changed:
            self._rich_views.pop(coordinate, None)
            self._assigned_rich_views.pop(coordinate, None)
            value._bindings.get(self, set()).discard(coordinate)
        for _, value, target, assigned in changed:
            if target is not None:
                value._bind(self, *target, retain=assigned)

    def _relocate_hyperlink_views(self, transform):
        changed = []
        for coordinate, value in self._hyperlink_views.items():
            target = transform(*coordinate)
            if target != coordinate:
                changed.append((coordinate, value, target))
        for coordinate, value, _ in changed:
            self._hyperlink_views.pop(coordinate, None)
            value._bindings.get(self, set()).discard(coordinate)
        for coordinate, value, target in changed:
            if target is None:
                cell = self._cells.get_cached(coordinate)
                if cell is not None:
                    cell._detached_hyperlink = value
            else:
                self._hyperlink_views[target] = value
                value._bindings.setdefault(self, set()).add(target)

    def cell(self, row, column, value=None):
        if (
            not isinstance(row, int)
            or not isinstance(column, int)
            or not 1 <= row <= 1048576
            or not 1 <= column <= 16384
        ):
            raise ValueError("Row or column values must be within Excel bounds")
        key = row, column
        cell = self._cells.get_cached(key)
        if cell is None:
            pending = (
                self.parent._editor.pending(self.title, row - 1, column - 1)
                if self._existing and self._native is None
                else None
            )
            present, merged = (
                (True, False)
                if pending is not None
                else self._model().cell_state(row - 1, column - 1)
            )
            cell = (MergedCell if merged else Cell)(self, row, column)
            self._cells[key] = cell
            if not self._existing and not present and not merged:
                self._native.set(row - 1, column - 1, ("empty", None))
        if value is not None:
            cell.value = value
        return cell

    def __getitem__(self, key):
        if isinstance(key, slice):
            if not key.start or not key.stop:
                raise IndexError(f"{key} is not a valid coordinate or range")
            key = f"{key.start}:{key.stop}"
        if isinstance(key, int) or (isinstance(key, str) and key.isdecimal()):
            row = int(key)
            return tuple(self.iter_rows(min_row=row, max_row=row))[0]
        if isinstance(key, str) and ":" not in key and _ADDRESS.fullmatch(key):
            return self.cell(*_address(key))
        if isinstance(key, str) and key.isalpha():
            column = _column(key)
            return tuple(self.iter_cols(min_col=column, max_col=column))[0]
        if isinstance(key, str) and ":" in key:
            first, last = key.split(":", 1)
            if first.isdigit() and last.isdigit():
                rows = tuple(self.iter_rows(min_row=int(first), max_row=int(last)))
                return rows[0] if int(first) == int(last) else rows
            if first.isalpha() and last.isalpha():
                start, end = _column(first), _column(last)
                columns = tuple(self.iter_cols(min_col=start, max_col=end))
                return columns[0] if start == end else columns
            row, col, end_row, end_col = _range(key)
            return tuple(self.iter_rows(row, end_row, col, end_col))
        raise ValueError(f"{key} is not a valid coordinate or range")

    def __setitem__(self, key, value):
        row, column = _address(key)
        if self._existing and self._native is None:
            # Preserve bounded source overlays without forcing full-sheet loading.
            # The preserving core validates deferred affected graphs on save.
            self._set(row, column, value)
        else:
            self.cell(row, column).value = value

    def __delitem__(self, key):
        self.parent._check_open()
        row, column = _address(key)
        cell = self._cells.get_cached((row, column))
        if self._native is None and self._existing:
            self._native = self.parent._editor.sheet_handle(self.title)
        style = cell._snapshot()[2:] if cell is not None else None
        old, removed_hyperlink = self._model().remove(
            row - 1, column - 1, cell is not None
        )
        hyperlink = self._hyperlink_views.pop((row, column), None)
        self._rich_views.pop((row, column), None)
        self._assigned_rich_views.pop((row, column), None)
        if cell is not None:
            self._cells.pop((row, column), None)
            cell._detached = (*(old if old is not None else ("n", None)), *style)
            if hyperlink is None and removed_hyperlink is not None:
                from .hyperlink import Hyperlink

                target, location, tooltip, display, identity, reference = (
                    removed_hyperlink
                )
                hyperlink = Hyperlink(
                    reference or cell.coordinate,
                    location,
                    tooltip,
                    display,
                    identity,
                    target,
                )
            cell._detached_hyperlink = hyperlink

    @property
    def _current_row(self):
        return self._model().row_extent()

    @property
    def min_row(self):
        return self._model().bounds()[0]

    @property
    def min_column(self):
        return self._model().bounds()[1]

    @property
    def max_row(self):
        return self._model().bounds()[2]

    @property
    def max_column(self):
        return self._model().bounds()[3]

    def calculate_dimension(self):
        first_row, first_col, last_row, last_col = self._model().bounds()
        return f"{_letters(first_col)}{first_row}:{_letters(last_col)}{last_row}"

    @property
    def dimensions(self):
        return self.calculate_dimension()

    def iter_rows(
        self, min_row=None, max_row=None, min_col=None, max_col=None, values_only=False
    ):
        # bounds() scans every cell, so skip it when the caller gives the limits.
        if not max_row or not max_col:
            bounds = self._model().bounds()
            if (
                min_row is None
                and max_row is None
                and min_col is None
                and max_col is None
                and not self._native.contains(0, 0)
                and bounds == (1, 1, 1, 1)
            ):
                return iter(())
            max_row, max_col = max_row or bounds[2], max_col or bounds[3]
        min_row, min_col = min_row or 1, min_col or 1
        self.cell(min_row, min_col)
        if max_row < min_row or max_col < min_col:
            return iter(())

        def rows():
            for row in range(min_row, max_row + 1):
                if values_only:
                    values, formulas = self._model().row_values_only(
                        row - 1, min_col - 1, max_col - 1, not self._existing
                    )
                    # Structured formulas remain live cell-bound objects.
                    if formulas:
                        for column in formulas:
                            values[column] = self.cell(row, min_col + column).value
                    yield tuple(values)
                    continue
                cells = tuple(
                    self.cell(row, column) for column in range(min_col, max_col + 1)
                )
                yield cells

        return rows()

    def iter_cols(
        self, min_col=None, max_col=None, min_row=None, max_row=None, values_only=False
    ):
        if all(bound is None for bound in (min_col, max_col, min_row, max_row)):
            if self._model().bounds() == (1, 1, 1, 1) and not self._native.contains(
                0, 0
            ):
                return
        min_col, min_row = min_col or 1, min_row or 1
        max_col, max_row = max_col or self.max_column, max_row or self.max_row
        for column in range(min_col, max_col + 1):
            cells = tuple(self.cell(row, column) for row in range(min_row, max_row + 1))
            yield tuple(cell.value for cell in cells) if values_only else cells

    def __iter__(self):
        return self.iter_rows()

    @property
    def rows(self):
        return self.iter_rows()

    @property
    def columns(self):
        return self.iter_cols()

    @property
    def values(self):
        return self.iter_rows(values_only=True)

    def append(self, iterable):
        if isinstance(iterable, (str, bytes)):
            raise TypeError("Append requires a row iterable or column dictionary")
        # Rows of plain values convert natively; anything else falls through.
        # A loaded sheet not yet read in Python appends without loading it.
        if self._existing and self._native is None and self.parent._editor is not None:
            row = self.parent._editor.append_plain(self.title, iterable)
        else:
            row = self._model().append_plain(iterable)
        if row is not None:
            return
        if isinstance(iterable, dict):
            positions = [(_column(column), value) for column, value in iterable.items()]
            values = [None] * max((column for column, _ in positions), default=0)
            for column, value in positions:
                values[column - 1] = value
        else:
            values = []
            for value in iterable:
                if len(values) == 16384:
                    raise ValueError("Appended row exceeds Excel column bounds")
                values.append(value)
        values = [
            value.decode(self.parent.encoding) if isinstance(value, bytes) else value
            for value in values
        ]
        cells = {}
        for index, value in enumerate(values):
            if isinstance(value, Cell):
                if value.parent is not None and value.parent is not self:
                    raise ValueError("Cells cannot be copied from other worksheets")
                cells[index] = (value, value._detached or value._snapshot())
        literals = [
            value.value if isinstance(value, Cell) else value for value in values
        ]
        tagged = [
            ("typed", (value.data_type, _encode(literal)))
            if isinstance(value, Cell)
            else _encode(literal)
            for value, literal in zip(values, literals)
        ]
        row = self._model().append(tagged) + 1
        for index, (cell, snapshot) in cells.items():
            cell.parent, cell.row, cell.column = self, row, index + 1
            cell._detached = None
            self._cells[(row, index + 1)] = cell
            if snapshot[3] != "General":
                cell.number_format = snapshot[3]
            for name, component in snapshot[4].items():
                setattr(cell, name, component)
        for column, (value, encoded) in enumerate(zip(literals, tagged), 1):
            raw = encoded[1][1] if encoded[0] == "typed" else encoded
            if raw[0] == "rich":
                value._bind(self, row, column, retain=encoded[0] != "typed")

    def _shift(self, idx, amount, rows, insert):
        if idx < 1 or amount < 1:
            raise ValueError("Index and amount must be positive")
        cached = list(self._cells.items())
        detached = {
            (row, col): (cell._snapshot(), cell.hyperlink)
            for (row, col), cell in cached
            if not insert and idx <= (row if rows else col) < idx + amount
        }
        self._model().shift(idx - 1, amount, rows, insert)

        def relocate(row, column):
            coordinate = row if rows else column
            if not insert and idx <= coordinate < idx + amount:
                return None
            if coordinate >= idx + (0 if insert else amount):
                coordinate += amount if insert else -amount
                return (coordinate, column) if rows else (row, coordinate)
            return row, column

        self._relocate_rich_views(relocate)
        self._relocate_hyperlink_views(relocate)
        self._relocate_comments(relocate)
        self._cells.clear()
        for (row, col), cell in cached:
            coordinate = row if rows else col
            if (row, col) in detached:
                cell._detached, cell._detached_hyperlink = detached[row, col]
                continue
            if coordinate >= idx + (0 if insert else amount):
                coordinate += amount if insert else -amount
                if rows:
                    cell.row = coordinate
                else:
                    cell.column = coordinate
            self._cells[cell.row, cell.column] = cell

    def insert_rows(self, idx, amount=1):
        self._shift(idx, amount, True, True)

    def delete_rows(self, idx, amount=1):
        self._shift(idx, amount, True, False)

    def insert_cols(self, idx, amount=1):
        self._shift(idx, amount, False, True)

    def delete_cols(self, idx, amount=1):
        self._shift(idx, amount, False, False)

    def move_range(self, cell_range, rows=0, cols=0, translate=False):
        range_object = cell_range if hasattr(cell_range, "coord") else None
        first_row, first_col, last_row, last_col = _range(
            range_object.coord if range_object is not None else cell_range
        )
        cached = list(self._cells.items())
        overwritten = {
            (row, col): (cell._snapshot(), cell.hyperlink)
            for (row, col), cell in cached
            if first_row + rows <= row <= last_row + rows
            and first_col + cols <= col <= last_col + cols
            and not (first_row <= row <= last_row and first_col <= col <= last_col)
        }
        self._model().move_range(
            (first_row - 1, first_col - 1, last_row - 1, last_col - 1),
            rows,
            cols,
            translate,
        )

        def relocate(row, column):
            if first_row <= row <= last_row and first_col <= column <= last_col:
                return row + rows, column + cols
            if (
                first_row + rows <= row <= last_row + rows
                and first_col + cols <= column <= last_col + cols
            ):
                return None
            return row, column

        self._relocate_rich_views(relocate)
        self._relocate_hyperlink_views(relocate)
        self._relocate_comments(relocate)
        if range_object is not None:
            range_object.shift(row_shift=rows, col_shift=cols)
        self._cells.clear()
        for (row, col), cell in cached:
            if first_row <= row <= last_row and first_col <= col <= last_col:
                cell.row += rows
                cell.column += cols
            elif (row, col) in overwritten:
                cell._detached, cell._detached_hyperlink = overwritten[row, col]
                continue
            self._cells[cell.row, cell.column] = cell
