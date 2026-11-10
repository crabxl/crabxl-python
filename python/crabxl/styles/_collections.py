"""Explicit views of the canonical native style component tables."""

from ._base import component


class StyleCollection:
    def __init__(self, workbook, name):
        self.workbook = workbook
        self.name = name

    def _values(self):
        values = self.workbook._style_owner().style_collection(self.name)
        if self.name == "number_format":
            return [value["code"] for value in values]
        result = []
        for value in values:
            native = value.pop("_native_component", None)
            decoded = component(self.name, value)
            if native is not None:
                object.__setattr__(
                    decoded, "_native_cache", (decoded._signature(), native)
                )
            result.append(decoded)
        return result

    def __len__(self):
        return len(self._values())

    def __iter__(self):
        return iter(self._values())

    def __getitem__(self, index):
        return self._values()[index]

    def __contains__(self, value):
        return value in self._values()

    def index(self, value):
        return self._values().index(value)

    def add(self, value):
        payload = value if self.name == "number_format" else value._native()
        return self.workbook._style_owner().style_collection_add(self.name, payload)

    def append(self, value):
        self.add(value)


class NamedStyleCollection:
    def __init__(self, workbook):
        self.workbook = workbook

    @property
    def names(self):
        return self.workbook.named_styles

    def __len__(self):
        return len(self.names)

    def __iter__(self):
        return (self[index] for index in range(len(self)))

    def __getitem__(self, key):
        from weakref import ref

        from .cell_style import StyleArray
        from .named_styles import NamedStyle

        records = self.workbook._style_owner().named_style_metadata()
        if isinstance(key, str):
            indices = [index for index, value in enumerate(records) if value[0] == key]
            if not indices:
                raise KeyError(f"No named style with the name{key} exists")
            key = indices[0]
        name, builtin, hidden = records[key]
        owner = self.workbook._style_owner()
        identity, number, components = owner.named_style_snapshot(name)
        style = NamedStyle(
            name=name,
            builtinId=builtin,
            hidden=hidden,
            number_format=number,
            **{name: component(name, value) for name, value in components.items()},
        )
        style._style = StyleArray(owner.style_array(identity))
        style._style.xfId = self.names.index(name)
        style._owner = ref(self.workbook)
        style._registered_name = name
        return style

    def append(self, style):
        self.workbook.add_named_style(style)
