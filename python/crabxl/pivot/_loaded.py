"""XML descriptor views over native, preserving pivot graphs."""

from weakref import ref

from .. import _native
from ..xml._preserve import (
    _merge_descriptor,
    preserving_fromstring,
    preserving_tostring,
)
from ..xml.functions import fromstring, tostring
from .cache import CacheDefinition
from .record import RecordList
from .table import TableDefinition


def _serialized(pivot):
    return (
        tostring(pivot.to_tree()),
        tostring(pivot.cache.to_tree()),
        tostring(pivot.cache.records.to_tree())
        if pivot.cache.records is not None
        else None,
    )


class PivotState:
    def __init__(self, pivots):
        self.pivots = tuple(pivots)
        self.previous = tuple(_serialized(pivot) for pivot in pivots)

    def push(self, sheet):
        current = tuple(_serialized(pivot) for pivot in self.pivots)
        if current == self.previous:
            return
        fresh = _native.sheet_pivot_objects_read(sheet._feature_handle())
        if len(fresh) < len(current):
            raise ValueError("Pivot source changed")
        inputs = []
        for index, (pivot, before, after, raw) in enumerate(
            zip(self.pivots, self.previous, current, fresh)
        ):
            table = _merge_descriptor(
                preserving_fromstring(bytes(raw[1])),
                fromstring(before[0]),
                fromstring(after[0]),
            )
            cache = _merge_descriptor(
                preserving_fromstring(bytes(raw[2])),
                fromstring(before[1]),
                fromstring(after[1]),
            )
            changed_records = before[2] != after[2]
            records = after[2]
            if changed_records and records is not None and before[2] is not None:
                encoded = _native.sheet_pivot_records_read(
                    sheet._feature_handle(), index
                )
                if encoded is not None:
                    records = preserving_tostring(
                        _merge_descriptor(
                            preserving_fromstring(bytes(encoded)),
                            fromstring(before[2]),
                            fromstring(records),
                        )
                    )
            inputs.append(
                (
                    id(pivot.cache),
                    preserving_tostring(table),
                    preserving_tostring(cache),
                    changed_records,
                    records if changed_records else None,
                )
            )
        _native.sheet_pivot_objects_write(sheet._feature_handle(), inputs)
        self.previous = current


def bind_pivots(sheet):
    """Match the reader's worksheet-local cache descriptor identity."""
    caches = {}
    rows = _native.sheet_pivot_objects_read(sheet._feature_handle())
    base = sheet._pivot_creation_state[0]
    if base is not None:
        rows = rows[:base]
    pivots = []
    for index, (identity, table, cache_xml, has_records) in enumerate(rows):
        cache = caches.get(identity)
        if cache is None:
            cache = CacheDefinition.from_tree(fromstring(bytes(cache_xml)))
            if has_records:
                records = _native.sheet_pivot_records_read(
                    sheet._feature_handle(), index
                )
                cache.records = RecordList.from_tree(fromstring(bytes(records)))
            caches[identity] = cache
            cache._crabxl_source = (ref(sheet), ref(cache))
        pivot = TableDefinition.from_tree(fromstring(bytes(table)))
        pivot.cache = cache
        pivots.append(pivot)
    sheet._pivot_state = PivotState(pivots)
