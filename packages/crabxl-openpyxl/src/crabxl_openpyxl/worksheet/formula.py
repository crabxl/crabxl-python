"""Compatibility formula objects; validation and XLSX behavior live in Rust."""

from weakref import WeakKeyDictionary, ref

_owners = WeakKeyDictionary()


def bind(value, owner):
    _owners[value] = (ref(owner.parent), owner.row, owner.column)
    return value


class _FormulaView:
    def __setattr__(self, name, value):
        binding = _owners.get(self)
        worksheet = binding[0]() if binding is not None else None
        if worksheet is not None:
            from .. import _decode

            row, column = binding[1:]
            current = _decode(worksheet._get(row, column))
            if type(current) is type(self) and vars(current) == vars(self):
                updated = type(self).__new__(type(self))
                updated.__dict__.update(vars(self))
                object.__setattr__(updated, name, value)
                worksheet._set(row, column, updated)
        object.__setattr__(self, name, value)


class ArrayFormula(_FormulaView):
    t = "array"

    def __init__(self, ref, text=None):
        self.ref = ref
        self.text = text

    def __iter__(self):
        yield "t", self.t
        yield "ref", self.ref


class DataTableFormula(_FormulaView):
    t = "dataTable"

    def __init__(
        self,
        ref,
        ca=False,
        dt2D=False,
        dtr=False,
        r1=None,
        r2=None,
        del1=False,
        del2=False,
        **kw,
    ):
        self.ref = ref
        self.ca = ca
        self.dt2D = dt2D
        self.dtr = dtr
        self.r1 = r1
        self.r2 = r2
        self.del1 = del1
        self.del2 = del2

    def __iter__(self):
        for name in ("t", "ref", "dt2D", "dtr", "r1", "r2", "del1", "del2", "ca"):
            value = getattr(self, name)
            if value:
                yield name, "1" if value is True else str(value)
