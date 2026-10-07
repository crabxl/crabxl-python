"""Named appearance builders backed by the workbook's canonical style registry."""

from weakref import ref

from .alignment import Alignment
from .borders import Border
from .fills import PatternFill
from .fonts import Font
from .protection import Protection


class NamedStyle:
    def __init__(
        self,
        name="Normal",
        font=None,
        fill=None,
        border=None,
        alignment=None,
        number_format=None,
        protection=None,
        builtinId=None,
        hidden=False,
    ):
        self._owner = None
        self.name = name
        self.font = font if font is not None else Font()
        self.fill = fill if fill is not None else PatternFill()
        self.border = border if border is not None else Border()
        self.alignment = alignment if alignment is not None else Alignment()
        self.number_format = number_format or "General"
        self.protection = protection if protection is not None else Protection()
        self.builtinId = builtinId
        self.hidden = bool(hidden)

    def __setattr__(self, name, value):
        if name == "name" and (not isinstance(value, str) or not value):
            raise ValueError("Named style requires a nonempty name")
        if name == "number_format" and not isinstance(value, str):
            raise TypeError("Number format must be a string")
        owner = getattr(self, "_owner", None)
        if owner is not None and name in ("name", "hidden", "builtinId"):
            previous = getattr(self, name)
            object.__setattr__(self, name, value)
            workbook = owner()
            if workbook is not None:
                try:
                    workbook._style_owner().update_named_style_metadata(
                        self._registered_name,
                        self.name,
                        self.builtinId,
                        bool(self.hidden),
                    )
                except Exception:
                    object.__setattr__(self, name, previous)
                    raise
                object.__setattr__(self, "_registered_name", self.name)
            return
        if owner is not None and name in (
            "font",
            "fill",
            "border",
            "alignment",
            "number_format",
            "protection",
        ):
            previous = getattr(self, name)
            object.__setattr__(self, name, value)
            workbook = owner()
            if workbook is not None:
                try:
                    workbook._style_owner().add_named_style(self._native(), update=True)
                except Exception:
                    object.__setattr__(self, name, previous)
                    raise
            return
        object.__setattr__(self, name, value)

    def _native(self):
        return {
            "name": self.name,
            "number_format": self.number_format,
            "builtinId": self.builtinId,
            "hidden": self.hidden,
            **{
                name: getattr(self, name)._native()
                for name in ("font", "fill", "border", "alignment", "protection")
            },
        }

    def _bind(self, workbook):
        self._owner = ref(workbook)
        object.__setattr__(self, "_registered_name", self.name)
