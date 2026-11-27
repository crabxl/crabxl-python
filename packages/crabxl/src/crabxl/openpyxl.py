"""The openpyxl interface, from the crabxl-openpyxl package.

Install it with ``pip install "crabxl[openpyxl]"``. ``crabxl.openpyxl`` and
each of its submodules are the modules of ``crabxl_openpyxl`` themselves, so
``crabxl.openpyxl.Workbook is crabxl_openpyxl.Workbook``.
"""

import importlib
import sys
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec
from importlib.util import spec_from_loader
from types import ModuleType
from typing import TYPE_CHECKING, Any, override

_TARGET = "crabxl_openpyxl"

try:
    _adapter = importlib.import_module(_TARGET)
except ModuleNotFoundError as error:
    if error.name != _TARGET:
        raise
    raise ModuleNotFoundError(
        'crabxl.openpyxl needs crabxl-openpyxl: pip install "crabxl[openpyxl]"',
        name=_TARGET,
    ) from None


class _Alias(Loader):
    """Loads ``crabxl.openpyxl.x`` as the module ``crabxl_openpyxl.x``."""

    def __init__(self, module: ModuleType) -> None:
        super().__init__()
        self._module = module
        self._spec = module.__spec__

    @override
    def create_module(self, spec: ModuleSpec) -> ModuleType:
        return self._module

    @override
    def exec_module(self, module: ModuleType) -> None:
        # The import system set the alias spec; keep the module's own.
        module.__spec__ = self._spec


class _Finder(MetaPathFinder):
    @override
    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        if not fullname.startswith(f"{__name__}."):
            return None
        module = importlib.import_module(_TARGET + fullname.removeprefix(__name__))
        return spec_from_loader(
            fullname, _Alias(module), is_package=hasattr(module, "__path__")
        )


sys.meta_path.insert(0, _Finder())
sys.modules[__name__] = _adapter

if TYPE_CHECKING:
    # The adapter is untyped, like openpyxl.
    def __getattr__(name: str) -> Any: ...
