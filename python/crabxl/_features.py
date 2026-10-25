"""Lazy bridge between the openpyxl feature classes and the Rust feature model.

Features cross the boundary as SpreadsheetML XML. Nothing is converted when a
workbook loads. The first access of a feature on a sheet reads that sheet's XML
once; classes are built on demand. On save only sheets and workbooks whose
feature state was created are pushed back, and components that were never
accessed keep their original XML.
"""

from xml.etree.ElementTree import Element, fromstring, tostring

from . import _native

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_ORDER = (
    "sheetProtection",
    "autoFilter",
    "sortState",
    "conditionalFormatting",
    "dataValidations",
    "headerFooter",
)


def _local(element):
    return element.tag.rsplit("}", 1)[-1]


class SheetState:
    """Feature classes of one worksheet, created on first access."""

    __slots__ = ("sheet", "dxfs", "elements", "table_xml", "raw_comments", "objs")

    def __init__(self, sheet):
        self.sheet = sheet
        self.objs = {}
        workbook = sheet.parent
        if workbook.write_only:
            raise NotImplementedError(
                "Features are not available on write-only worksheets"
            )
        if workbook.read_only:
            raw = _native.reader_sheet_features(workbook._reader, sheet.title)
        else:
            raw = _native.sheet_features_read(sheet._feature_handle())
        self.elements = {}
        if raw is None:
            self.table_xml, self.raw_comments, self.dxfs = [], [], {}
            return
        document, self.table_xml, self.raw_comments, self.dxfs = raw
        for child in fromstring(document):
            self.elements.setdefault(_local(child), []).append(child)

    def get(self, name):
        obj = self.objs.get(name)
        if obj is None:
            obj = self.objs[name] = getattr(self, "_build_" + name)()
        return obj

    def _first(self, tag):
        found = self.elements.get(tag)
        return found[0] if found else None

    def _build_protection(self):
        from .worksheet.protection import SheetProtection

        element = self._first("sheetProtection")
        if element is None:
            return SheetProtection()
        protection = SheetProtection.from_tree(element)
        password = element.get("password")
        if password is not None:
            protection.set_password(password, True)
        return protection

    def _build_auto_filter(self):
        from .worksheet.filters import AutoFilter

        element = self._first("autoFilter")
        return AutoFilter() if element is None else AutoFilter.from_tree(element)

    def _build_data_validations(self):
        from .worksheet.datavalidation import DataValidationList

        element = self._first("dataValidations")
        return (
            DataValidationList()
            if element is None
            else DataValidationList.from_tree(element)
        )

    def _build_header_footer(self):
        from .worksheet.header_footer import HeaderFooter

        element = self._first("headerFooter")
        return HeaderFooter() if element is None else HeaderFooter.from_tree(element)

    def _build_tables(self):
        from .worksheet.table import Table, TableList

        tables = TableList()
        for xml in self.table_xml:
            tables.add(Table.from_tree(fromstring(xml)))
        return tables

    def _build_conditional_formatting(self):
        from .formatting.formatting import (
            ConditionalFormatting,
            ConditionalFormattingList,
        )
        from .styles.differential import DifferentialStyle

        formatting = ConditionalFormattingList()
        dxfs = {}
        for element in self.elements.get("conditionalFormatting", ()):
            block = ConditionalFormatting.from_tree(element)
            for rule in block.rules:
                if rule.dxfId is not None and rule.dxfId in self.dxfs:
                    if rule.dxfId not in dxfs:
                        dxfs[rule.dxfId] = DifferentialStyle.from_tree(
                            fromstring(self.dxfs[rule.dxfId])
                        )
                    rule.dxf = dxfs[rule.dxfId]
                formatting.add(block, rule)
        return formatting

    def _build_comments(self):
        from .comments import Comment

        comments = {}
        for row, column, author, text, width, height, visible in self.raw_comments:
            comment = Comment(text, author, height=height, width=width)
            comment._visible = visible
            comments[row + 1, column + 1] = comment
        return comments

    # -- save ---------------------------------------------------------

    def push(self):
        sheet = self.sheet
        handle = sheet._feature_handle()
        root = Element("worksheet", {"xmlns": MAIN_NS})
        objs = self.objs
        dxf_ids = {}

        def original(tag):
            root.extend(self.elements.get(tag, ()))

        def tree(obj):
            element = obj.to_tree()
            if len(element) or element.attrib:
                root.append(element)

        if "protection" in objs:
            if objs["protection"]:
                tree(objs["protection"])
        else:
            original("sheetProtection")
        if "auto_filter" in objs:
            if objs["auto_filter"]:
                tree(objs["auto_filter"])
        else:
            original("autoFilter")
        original("sortState")
        if "conditional_formatting" in objs:
            from .styles.differential import DifferentialStyle

            empty = DifferentialStyle()
            for block in objs["conditional_formatting"]:
                for rule in block.rules:
                    if rule.dxf and rule.dxf != empty:
                        xml = tostring(rule.dxf.to_tree())
                        if xml not in dxf_ids:
                            dxf_ids[xml] = _native.sheet_register_dxf(handle, xml)
                        rule.dxfId = dxf_ids[xml]
                root.append(block.to_tree())
        else:
            original("conditionalFormatting")
        if "data_validations" in objs:
            if objs["data_validations"]:
                tree(objs["data_validations"])
        else:
            original("dataValidations")
        if "header_footer" in objs:
            tree(objs["header_footer"])
        else:
            original("headerFooter")

        if "tables" in objs:
            tables = []
            for index, table in enumerate(objs["tables"].values(), 1):
                self._prepare_table(table)
                table.id = index
                tables.append(tostring(table.to_tree()))
        else:
            tables = list(self.table_xml)
        if "comments" in objs:
            comments = [
                (
                    row - 1,
                    column - 1,
                    comment.author or "",
                    comment.content or "",
                    float(comment.width),
                    float(comment.height),
                    getattr(comment, "_visible", False),
                )
                for (row, column), comment in sorted(objs["comments"].items())
            ]
        else:
            comments = list(self.raw_comments)
        _native.sheet_features_write(handle, tostring(root), tables, comments)

    def _prepare_table(self, table):
        from warnings import warn

        if table.tableColumns:
            return
        table._initialise_columns()
        if table.headerRowCount:
            try:
                row = self.sheet[table.ref][0]
                for cell, column in zip(row, table.tableColumns):
                    if cell.data_type != "s":
                        warn(
                            "File may not be readable: column headings must be strings."
                        )
                    column.name = str(cell.value)
            except TypeError:
                warn("Column headings are missing, file may not be readable")


class WorkbookState:
    """Defined names, protection and properties of one workbook."""

    __slots__ = ("raw", "objs", "kept", "bound")

    def __init__(self, workbook):
        self.objs = {}
        self.kept = {}
        self.bound = False
        owner = workbook._reader or workbook._book
        if workbook.write_only:
            raise NotImplementedError("Features are not available in write-only mode")
        self.raw = _native.workbook_features_read(owner)

    def _parts(self):
        document, core, app, custom, _ = self.raw or (None,) * 5
        root = fromstring(document) if document else None
        return root, core, app, custom

    def build(self, workbook):
        """Create every workbook-level object and bind names to the sheets."""
        from .packaging.core import DocumentProperties
        from .packaging.custom import CustomPropertyList
        from .workbook.defined_name import DefinedNameList
        from .workbook.protection import WorkbookProtection
        from .worksheet.print_settings import PrintArea, PrintTitles

        self.bound = True
        root, core, _app, custom = self._parts()
        names = security = None
        if root is not None:
            for child in root:
                if _local(child) == "definedNames":
                    names = DefinedNameList.from_tree(child)
                elif _local(child) == "workbookProtection":
                    security = WorkbookProtection.from_tree(child)
        objs = self.objs
        objs["security"] = security or WorkbookProtection()
        objs["properties"] = (
            DocumentProperties.from_tree(fromstring(core))
            if core
            else DocumentProperties()
        )
        objs["custom"] = (
            CustomPropertyList.from_tree(fromstring(custom))
            if custom
            else CustomPropertyList()
        )
        from .workbook.defined_name import DefinedNameDict

        objs["names"] = DefinedNameDict()
        if names is not None:
            for index, group in names.by_sheet().items():
                if index == "global":
                    objs["names"] = group
                    continue
                if index >= len(workbook._sheets):
                    continue
                sheet = workbook._sheets[index]
                for name, defn in group.items():
                    reserved = defn.is_reserved
                    if reserved is None:
                        sheet._local_names()[name] = defn
                    elif reserved == "Print_Titles":
                        titles = PrintTitles.from_string(defn.value)
                        sheet._print_rows, sheet._print_cols = titles.rows, titles.cols
                    elif reserved == "Print_Area":
                        try:
                            sheet._print_area = PrintArea.from_string(defn.value)
                        except TypeError:
                            pass
        self.bound = True

    def push(self, workbook):
        from .packaging.core import DocumentProperties  # noqa: F401
        from .utils import quote_sheetname
        from .workbook.defined_name import DefinedName, DefinedNameList

        if not self.bound:
            self.build(workbook)
        objs = self.objs
        names = list(objs["names"].values())
        for index, sheet in enumerate(workbook._sheets):
            quoted = quote_sheetname(sheet.title)
            local = getattr(sheet, "_names", None)
            if local:
                for name in local.values():
                    name.localSheetId = index
                    names.append(name)
            state = getattr(sheet, "_feat", None)
            if state is not None:
                flt = state.get("auto_filter")
                if flt:
                    name = DefinedName(
                        name="_FilterDatabase", localSheetId=index, hidden=True
                    )
                    name.value = f"{quoted}!{flt}"
                    names.append(name)
            if sheet.print_titles:
                name = DefinedName(name="Print_Titles", localSheetId=index)
                name.value = sheet.print_titles
                names.append(name)
            if sheet.print_area:
                name = DefinedName(name="Print_Area", localSheetId=index)
                name.value = sheet.print_area
                names.append(name)
        root = Element("workbook", {"xmlns": MAIN_NS})
        security = objs["security"].to_tree("workbookProtection")
        if security.attrib or len(security):
            root.append(security)
        if names:
            root.append(DefinedNameList(definedName=names).to_tree())
        properties = objs["properties"]
        core = tostring(properties.to_tree())
        custom = objs["custom"]
        custom_xml = tostring(custom.to_tree()) if len(custom) else None
        app = self.raw[2] if self.raw else None
        _native.workbook_features_write(
            workbook._reader or workbook._book, tostring(root), core, app, custom_xml
        )
