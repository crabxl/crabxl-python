"""Mutable public rich-text views; canonical values and validation stay in Rust."""

from copy import copy
from weakref import WeakKeyDictionary, WeakValueDictionary

from .text import InlineFont


def _notify(value):
    _sync(list(getattr(value, "_listeners", {}).values()))


def _sync(values):
    from .._values import _decode, _encode

    updates = []
    for value in values:
        payload = value._native()
        for worksheet, coordinates in value._bindings.items():
            retained = set()
            for row, column in coordinates:
                if worksheet._rich_views.get((row, column)) is not value:
                    continue
                previous = worksheet._get(row, column)
                retained.add((row, column))
                updates.append((value, worksheet, row, column, previous, payload))
            value._bindings[worksheet] = retained
    committed = []
    try:
        for value, sheet, row, column, previous, payload in updates:
            sheet._set_tagged(row, column, ("rich", payload))
            committed.append((value, sheet, row, column, previous))
    except BaseException:
        for value, sheet, row, column, previous in reversed(committed):
            sheet._set_tagged(row, column, _encode(_decode(previous)))
            sheet._rich_views[row, column] = value
        raise
    for value, sheet, row, column, _, _ in updates:
        sheet._rich_views[row, column] = value
    for value in values:
        value._observe()


class TextBlock:
    def __init__(self, font, text):
        self.font, self.text = font, text

    def __setattr__(self, name, value):
        if name == "font" and not isinstance(value, InlineFont):
            raise TypeError("TextBlock font must be InlineFont")
        if name == "text" and not isinstance(value, str):
            raise TypeError("TextBlock text must be a string")
        old = getattr(self, name, None)
        object.__setattr__(self, name, value)
        if name in ("font", "text"):
            try:
                _notify(self)
            except BaseException:
                object.__setattr__(self, name, old)
                raise

    def __str__(self):
        return self.text

    def __eq__(self, other):
        return (
            isinstance(other, TextBlock)
            and self.font == other.font
            and self.text == other.text
        )

    def __copy__(self):
        return type(self)(copy(self.font), self.text)


class CellRichText(list):
    def __init__(self, *args):
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            args = args[0]
        self._bindings = WeakKeyDictionary()
        self._phonetic_runs = []
        self._phonetic_properties = None
        self._check(args)
        super().__init__(args)
        self._observe()

    @staticmethod
    def _check(values):
        if any(not isinstance(v, (str, int, float, TextBlock)) for v in values):
            raise TypeError("Rich text accepts strings, numbers and TextBlock values")

    def _observe(self):
        for item in self:
            if isinstance(item, TextBlock):
                for value in (item, item.font, item.font.color):
                    if value is None:
                        continue
                    listeners = getattr(value, "_listeners", None)
                    if listeners is None:
                        listeners = WeakValueDictionary()
                        object.__setattr__(value, "_listeners", listeners)
                    listeners[id(self)] = self

    def _native(self):
        return {
            "runs": [
                (item.text, item.font._native())
                if isinstance(item, TextBlock)
                else (str(item), None)
                for item in self
            ],
            "phonetic_runs": self._phonetic_runs,
            "phonetic_properties": self._phonetic_properties,
        }

    @classmethod
    def _from_native(cls, fields):
        from ..styles._base import font_from_native

        values = []
        for text, font in fields["runs"]:
            if font is None:
                values.append(text)
            else:
                values.append(TextBlock(font_from_native(font, InlineFont), text))
        result = cls(values)
        result._phonetic_runs = fields.get("phonetic_runs", [])
        result._phonetic_properties = fields.get("phonetic_properties")
        return result

    def _bind(self, worksheet, row, column):
        self._bindings.setdefault(worksheet, set()).add((row, column))
        self._observe()
        worksheet._rich_views[row, column] = self
        return self

    def _change(self, action):
        old = list(self)
        try:
            result = action()
            self._check(self)
            _sync([self])
        except BaseException:
            list.__setitem__(self, slice(None), old)
            raise
        self._observe()
        return result

    def __str__(self):
        return "".join(str(item) for item in self)

    def __repr__(self):
        return f"CellRichText({list.__repr__(self)})"

    def as_list(self):
        return [str(item) for item in self]

    def __setitem__(self, key, value):
        return self._change(lambda: list.__setitem__(self, key, value))

    def __delitem__(self, key):
        return self._change(lambda: list.__delitem__(self, key))

    def append(self, value):
        return self._change(lambda: list.append(self, value))

    def extend(self, values):
        return self._change(lambda: list.extend(self, values))

    def insert(self, index, value):
        return self._change(lambda: list.insert(self, index, value))

    def pop(self, index=-1):
        return self._change(lambda: list.pop(self, index))

    def remove(self, value):
        return self._change(lambda: list.remove(self, value))

    def clear(self):
        return self._change(lambda: list.clear(self))

    def reverse(self):
        return self._change(lambda: list.reverse(self))

    def sort(self, *, key=None, reverse=False):
        return self._change(lambda: list.sort(self, key=key, reverse=reverse))

    def __iadd__(self, values):
        values = [values] if isinstance(values, (str, TextBlock)) else list(values)

        def combine():
            list.extend(self, values)
            optimized = []
            for item in self:
                item = copy(item)
                if not str(item):
                    continue
                if (
                    optimized
                    and isinstance(item, str)
                    and isinstance(optimized[-1], str)
                ):
                    optimized[-1] += item
                elif (
                    optimized
                    and isinstance(item, TextBlock)
                    and isinstance(optimized[-1], TextBlock)
                    and item.font == optimized[-1].font
                ):
                    optimized[-1].text += item.text
                else:
                    optimized.append(item)
            list.__setitem__(self, slice(None), optimized)

        self._change(combine)
        return self

    def __add__(self, values):
        result = CellRichText([copy(item) for item in self])
        result._phonetic_runs = list(self._phonetic_runs)
        result._phonetic_properties = self._phonetic_properties
        result += values
        return result

    def __imul__(self, count):
        self._change(lambda: list.__imul__(self, count))
        return self
