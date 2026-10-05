"""CrabXL resource extensions; strategy selection and enforcement stay in Rust."""

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


def _validate_integers(options, names=None):
    names = names if names is not None else (item.name for item in fields(options))
    for name in names:
        value = getattr(options, name)
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer or None")
            if not 0 <= value <= 2**64 - 1:
                raise ValueError(f"{name} must fit an unsigned 64-bit integer")


def _configured(options):
    return {key: value for key, value in asdict(options).items() if value is not None}


@dataclass(frozen=True, slots=True, kw_only=True)
class AutoMemory:
    """None fields use Rust defaults; this controls managed allowances, not RSS."""

    fraction_per_mille: int | None = None
    headroom_bytes: int | None = None
    maximum_bytes: int | None = None
    available_bytes: int | None = None
    concurrent_operations: int | None = None

    def __post_init__(self):
        _validate_integers(self)
        if (
            self.fraction_per_mille is not None
            and not 1 <= self.fraction_per_mille <= 1000
        ):
            raise ValueError("fraction_per_mille must be between 1 and 1000")
        if (
            self.concurrent_operations is not None
            and not 1 <= self.concurrent_operations <= 65535
        ):
            raise ValueError("concurrent_operations must be between 1 and 65535")


@dataclass(frozen=True, slots=True, kw_only=True)
class ResourceLimits:
    """Read/edit limits. None preserves the canonical Rust or adapter mode default."""

    input_buffer_bytes: int | None = None
    max_materialized_bytes: int | None = None
    max_archive_bytes: int | None = None
    max_archive_entries: int | None = None
    max_total_uncompressed_bytes: int | None = None
    max_part_bytes: int | None = None
    max_metadata_bytes: int | None = None
    max_xml_event_bytes: int | None = None
    max_cell_bytes: int | None = None
    max_theme_bytes: int | None = None
    max_style_bytes: int | None = None
    max_style_records: int | None = None
    max_formula_table_bytes: int | None = None
    max_shared_formulas: int | None = None
    max_xml_depth: int | None = None
    max_sheets: int | None = None
    max_row_cells: int | None = None
    max_row_bytes: int | None = None
    max_batch_rows: int | None = None
    max_batch_bytes: int | None = None

    def __post_init__(self):
        _validate_integers(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class SharedStringOptions:
    """SST placement/cache limits; memory_bytes includes Rust's parser reserve."""

    storage: str = "auto"
    memory_bytes: int | None = None
    cache_bytes: int | None = None
    max_temp_bytes: int | None = None
    max_entries: int | None = None
    temp_directory: str | Path | None = None

    def __post_init__(self):
        if self.storage not in {"auto", "memory", "disk"}:
            raise ValueError("storage must be auto, memory or disk")
        _validate_integers(
            self, ["memory_bytes", "cache_bytes", "max_temp_bytes", "max_entries"]
        )
        if self.temp_directory is not None:
            object.__setattr__(self, "temp_directory", Path(self.temp_directory))
        if self.storage == "memory" and any(
            value is not None
            for value in [self.cache_bytes, self.max_temp_bytes, self.temp_directory]
        ):
            raise ValueError(
                "Disk/cache settings do not apply to forced-memory SST storage"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ResourceOptions:
    """Advanced load_workbook controls, separate from openpyxl compatibility."""

    limits: ResourceLimits = field(default_factory=ResourceLimits)
    auto_memory: AutoMemory | None = None
    shared_strings: SharedStringOptions = field(default_factory=SharedStringOptions)
    max_patch_bytes: int | None = None
    max_patch_cells: int | None = None

    def __post_init__(self):
        if not isinstance(self.limits, ResourceLimits):
            raise TypeError("limits must be ResourceLimits")
        if self.auto_memory is not None and not isinstance(
            self.auto_memory, AutoMemory
        ):
            raise TypeError("auto_memory must be AutoMemory or None")
        if not isinstance(self.shared_strings, SharedStringOptions):
            raise TypeError("shared_strings must be SharedStringOptions")
        _validate_integers(self, ["max_patch_bytes", "max_patch_cells"])

    def _native(self, maximum=None, *, read_only=False):
        from ._native import NativeResources

        if maximum is not None and self.auto_memory is not None:
            raise ValueError("Choose max_memory_bytes or auto_memory settings")
        if read_only:
            if self.limits.max_materialized_bytes is not None:
                raise ValueError(
                    "max_materialized_bytes applies to ordinary loaded worksheets"
                )
            if self.max_patch_bytes is not None or self.max_patch_cells is not None:
                raise ValueError("Patch limits do not apply to read_only workbooks")
        elif (
            self.limits.max_batch_rows is not None
            or self.limits.max_batch_bytes is not None
        ):
            raise ValueError("Batch limits apply to read_only workbooks")
        return NativeResources(
            limits=_configured(self.limits),
            auto=_configured(self.auto_memory)
            if self.auto_memory is not None
            else None,
            **asdict(self.shared_strings),
            max_patch_bytes=self.max_patch_bytes,
            max_patch_cells=self.max_patch_cells,
        )
