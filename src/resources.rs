//! Validated language configuration mapped to canonical resource policies.
use super::*;
use crabxl::{AutoMemory, SharedStringOptions, SharedStringStorage};
use std::collections::HashMap;

#[derive(Clone, Default)]
pub(crate) struct ResourceConfig {
    pub limits: ResourceLimits,
    pub memory_policy: MemoryPolicy,
    pub strings: SharedStringOptions,
    pub materialized_limit: Option<usize>,
    batch_rows: Option<usize>,
    batch_bytes: Option<usize>,
    string_memory_bytes: Option<usize>,
    patch_bytes: Option<usize>,
    patch_cells: Option<usize>,
}
impl ResourceConfig {
    pub fn reader_limits(&self, maximum: usize, streaming: bool) -> ResourceLimits {
        let mut limits = self.limits;
        limits.max_materialized_bytes = self.materialized_limit.unwrap_or(maximum).min(maximum);
        if streaming {
            limits.max_batch_rows = self.batch_rows.unwrap_or(256);
            limits.max_batch_bytes = self
                .batch_bytes
                .unwrap_or((maximum / 4).clamp(4096, 2 * 1024 * 1024))
                .min(maximum);
        }
        limits
    }
    pub fn string_options(
        &self,
        maximum: usize,
        limits: ResourceLimits,
    ) -> crabxl::Result<SharedStringOptions> {
        let mut options = self.strings.clone();
        let budget = if let Some(budget) = self.string_memory_bytes {
            budget
        } else {
            let working = crabxl::memory_allowance(MemoryPolicy::Budget(usize::MAX), limits)?
                .working_reserve_bytes;
            maximum.checked_add(working).ok_or_else(|| {
                Error::new(ErrorKind::InvalidData, "Shared-string allowance overflows")
            })?
        };
        options.memory_policy = MemoryPolicy::Budget(budget);
        Ok(options)
    }
    pub fn editor_options(&self, maximum: Option<usize>) -> EditorOptions {
        let mut options = EditorOptions {
            resources: self.limits,
            memory_policy: maximum.map_or(self.memory_policy, MemoryPolicy::Budget),
            ..Default::default()
        };
        if let Some(value) = self.patch_bytes {
            options.max_patch_bytes = value;
        }
        if let Some(value) = self.patch_cells {
            options.max_patch_cells = value;
        }
        options
    }
}
fn platform_size(value: u64) -> PyResult<usize> {
    usize::try_from(value).map_err(|_| PyValueError::new_err("Resource size exceeds this platform"))
}
#[pyclass(frozen)]
pub(crate) struct NativeResources {
    pub config: ResourceConfig,
}
#[pymethods]
impl NativeResources {
    #[new]
    #[allow(clippy::too_many_arguments)]
    #[pyo3(signature = (*, limits=None, auto=None, storage="auto", memory_bytes=None, cache_bytes=None, max_temp_bytes=None, max_entries=None, temp_directory=None, max_patch_bytes=None, max_patch_cells=None))]
    fn new(
        limits: Option<HashMap<String, u64>>,
        auto: Option<HashMap<String, u64>>,
        storage: &str,
        memory_bytes: Option<usize>,
        cache_bytes: Option<usize>,
        max_temp_bytes: Option<u64>,
        max_entries: Option<u64>,
        temp_directory: Option<PathBuf>,
        max_patch_bytes: Option<usize>,
        max_patch_cells: Option<usize>,
    ) -> PyResult<Self> {
        let mut config = ResourceConfig::default();
        macro_rules! limits {
            ($name:expr, $value:expr, $($field:ident),+) => {
                match $name {
                    $(stringify!($field) => config.limits.$field = platform_size($value)?,)+
                    "max_archive_bytes" => config.limits.max_archive_bytes = $value,
                    "max_total_uncompressed_bytes" => config.limits.max_total_uncompressed_bytes = $value,
                    "max_part_bytes" => config.limits.max_part_bytes = $value,
                    "max_metadata_bytes" => config.limits.max_metadata_bytes = $value,
                    _ => return Err(PyValueError::new_err(format!("Unknown resource limit: {}", $name))),
                }
            }
        }
        for (name, value) in limits.unwrap_or_default() {
            limits!(
                name.as_str(),
                value,
                input_buffer_bytes,
                max_materialized_bytes,
                max_archive_entries,
                max_xml_event_bytes,
                max_cell_bytes,
                max_theme_bytes,
                max_style_bytes,
                max_style_records,
                max_formula_table_bytes,
                max_shared_formulas,
                max_xml_depth,
                max_sheets,
                max_row_cells,
                max_row_bytes,
                max_batch_rows,
                max_batch_bytes
            );
            match name.as_str() {
                "max_materialized_bytes" => config.materialized_limit = Some(platform_size(value)?),
                "max_batch_rows" => config.batch_rows = Some(platform_size(value)?),
                "max_batch_bytes" => config.batch_bytes = Some(platform_size(value)?),
                _ => {}
            }
        }
        let mut memory = AutoMemory::default();
        for (name, value) in auto.unwrap_or_default() {
            match name.as_str() {
                "fraction_per_mille" => {
                    memory.fraction_per_mille = u16::try_from(value)
                        .map_err(|_| PyValueError::new_err("Auto fraction exceeds u16"))?
                }
                "headroom_bytes" => memory.headroom_bytes = value,
                "maximum_bytes" => memory.maximum_bytes = Some(platform_size(value)?),
                "available_bytes" => memory.available_bytes = Some(value),
                "concurrent_operations" => {
                    memory.concurrent_operations = u16::try_from(value).map_err(|_| {
                        PyValueError::new_err("Concurrent operation count exceeds u16")
                    })?
                }
                _ => {
                    return Err(PyValueError::new_err(format!(
                        "Unknown Auto option: {name}"
                    )));
                }
            }
        }
        config.memory_policy = MemoryPolicy::Auto(memory);
        config.strings.storage = match storage {
            "auto" => SharedStringStorage::Auto,
            "memory" => SharedStringStorage::Memory,
            "disk" => SharedStringStorage::Disk,
            _ => {
                return Err(PyValueError::new_err(
                    "Shared-string storage must be auto, memory or disk",
                ));
            }
        };
        if let Some(value) = cache_bytes {
            config.strings.cache_bytes = value;
        }
        if let Some(value) = max_temp_bytes {
            config.strings.max_temp_bytes = value;
        }
        if let Some(value) = max_entries {
            config.strings.max_entries = value;
        }
        config.strings.temp_directory = temp_directory;
        config.string_memory_bytes = memory_bytes;
        config.patch_bytes = max_patch_bytes;
        config.patch_cells = max_patch_cells;
        Ok(Self { config })
    }
}
