"""Settings for existing Excel pivot tables."""

import sys
from dataclasses import dataclass


@dataclass(**({"slots": True} if sys.version_info >= (3, 10) else {}))
class PivotTableSettings:
    _name: str
    rowGrandTotals: bool
    colGrandTotals: bool
    showHeaders: bool
    showDrill: bool
    compact: bool
    outline: bool
    compactData: bool
    outlineData: bool

    @property
    def name(self):
        return self._name

    def _flags(self):
        return (
            self.rowGrandTotals,
            self.colGrandTotals,
            self.showHeaders,
            self.showDrill,
            self.compact,
            self.outline,
            self.compactData,
            self.outlineData,
        )
