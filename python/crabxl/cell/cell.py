"""Cell compatibility facade over canonical native handles."""

from typing import TYPE_CHECKING

from .._values import _data_type, _decode, _encode, _letters
from ..styles import Alignment, Border, Font, GradientFill, PatternFill, Protection
from ..styles._base import cell_component

if TYPE_CHECKING:
    from ..optimized import WriteOnlyCell


class Cell:
    """A live Python view of a Rust-owned cell; coordinates are one-based."""

    __slots__ = ("parent", "row", "column", "_detached", "_formula", "__weakref__")

    font = cell_component("font", Font)
    fill = cell_component("fill", (PatternFill, GradientFill))
    border = cell_component("border", Border)
    alignment = cell_component("alignment", Alignment)
    protection = cell_component("protection", Protection)

    def __init__(self, worksheet, row, column):
        self.parent, self.row, self.column = worksheet, row, column
        self._detached = None
        self._formula = None

    @property
    def style(self):
        if self._detached is not None:
            return self.parent.parent._style_owner().style_name(self.style_id)
        return self.parent._model().named_style(self.row - 1, self.column - 1)

    @style.setter
    def style(self, value):
        from ..styles import NamedStyle

        workbook = self.parent.parent
        if isinstance(value, NamedStyle):
            if value.name not in workbook.named_styles:
                workbook.add_named_style(value)
            value = value.name
        if not isinstance(value, str):
            raise TypeError("Style must be a name or NamedStyle")
        if self._detached is not None:
            from ..styles._base import component

            style, number, components = workbook._style_owner().named_style_snapshot(
                value
            )
            self._detached = (
                *self._detached[:2],
                style,
                number,
                {name: component(name, item) for name, item in components.items()},
            )
            return
        self.parent._model().set_named_style(self.row - 1, self.column - 1, value)

    @property
    def coordinate(self):
        return f"{_letters(self.column)}{self.row}"

    @property
    def column_letter(self):
        return _letters(self.column)

    @property
    def value(self):
        from ..worksheet.formula import ArrayFormula, DataTableFormula, bind

        value = _decode(self._tagged())
        if isinstance(value, (ArrayFormula, DataTableFormula)):
            if (
                self._formula is not None
                and type(self._formula) is type(value)
                and vars(self._formula) == vars(value)
            ):
                return self._formula
            self._formula = bind(value, self)
            return self._formula
        self._formula = None
        return value

    @value.setter
    def value(self, value):
        if self._detached is not None:
            tag = _encode(value)
            self._detached = (_data_type(tag), value, *self._detached[2:])
        else:
            self.parent._set(self.row, self.column, value)

    def _tagged(self):
        return (
            self._detached[:2]
            if self._detached is not None
            else self.parent._get(self.row, self.column)
        )

    @property
    def data_type(self):
        kind = self._tagged()[0]
        return (
            "f"
            if kind in ("array", "table")
            else "d"
            if kind in ("date", "datetime", "duration", "time")
            else "n"
            if kind == "bigint"
            else kind
        )

    @property
    def internal_value(self):
        return self.value

    def _snapshot(self):
        return (
            *self._tagged(),
            self.style_id,
            self.number_format,
            {
                name: __import__("copy").copy(getattr(self, name))
                for name in ("font", "fill", "border", "alignment", "protection")
            },
        )

    @property
    def style_id(self):
        if self._detached is not None:
            return self._detached[2] if len(self._detached) > 2 else 0
        return self.parent._model().style_id(self.row - 1, self.column - 1)

    @property
    def has_style(self):
        if self._detached is not None:
            return self.style_id != 0 or self.number_format != "General"
        return self.parent._model().has_style(self.row - 1, self.column - 1)

    @property
    def number_format(self):
        if self._detached is not None:
            return self._detached[3] if len(self._detached) > 3 else "General"
        return self.parent._model().number_format(self.row - 1, self.column - 1)

    @number_format.setter
    def number_format(self, code):
        if not isinstance(code, str):
            raise TypeError("Number format must be a string")
        if self._detached is not None:
            self._detached = (
                *self._detached[:2],
                self.style_id,
                code,
                *self._detached[4:],
            )
        else:
            self.parent._model().set_number_format(self.row - 1, self.column - 1, code)

    @property
    def is_date(self):
        if self.data_type == "d":
            return True
        return (
            self._detached is None
            and self.data_type == "n"
            and self.parent._model().is_date_format(self.row - 1, self.column - 1)
        )


__all__ = ["Cell", "WriteOnlyCell"]


def __getattr__(name):
    if name == "WriteOnlyCell":
        from ..optimized import WriteOnlyCell

        return WriteOnlyCell
    raise AttributeError(name)
