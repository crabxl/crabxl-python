"""Settings for existing Excel pivot tables."""

from dataclasses import dataclass


@dataclass(slots=True)
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
