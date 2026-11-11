"""Public appearance values backed by the canonical Rust style catalog."""

from importlib import import_module

# Each name loads its module on first use, so that reading cell values does not
# import the style classes and their XML support.
_MODULES = {
    "Alignment": "alignment",
    "Border": "borders",
    "Side": "borders",
    "Color": "colors",
    "Fill": "fills",
    "GradientFill": "fills",
    "PatternFill": "fills",
    "DEFAULT_FONT": "fonts",
    "Font": "fonts",
    "NamedStyle": "named_styles",
    "NumberFormatDescriptor": "numbers",
    "is_builtin": "numbers",
    "is_date_format": "numbers",
    "Protection": "protection",
}


def __getattr__(name):
    module = _MODULES.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{module}", __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted([*globals(), *_MODULES])


__all__ = [
    "Alignment",
    "Border",
    "Color",
    "DEFAULT_FONT",
    "Fill",
    "Font",
    "GradientFill",
    "NamedStyle",
    "NumberFormatDescriptor",
    "PatternFill",
    "Protection",
    "Side",
    "is_builtin",
    "is_date_format",
]
