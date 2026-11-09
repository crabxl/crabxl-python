"""Run the pinned openpyxl 3.1.5 test suite against crabxl.

Test modules (``tests`` packages, ``test_*`` and ``conftest`` files) load from the
reference checkout. Every other ``openpyxl.*`` import resolves to the matching
``crabxl.*`` module, so upstream assertions run unchanged against crabxl.

With ``--expected``, the run passes only when the failing tests match the tracked
list of expected failures: tests of openpyxl internals and deliberate differences.

Example:
    python tools/run_openpyxl_suite.py --reference-checkout ../reference/openpyxl \
        --expected tools/openpyxl_suite_expected.json
"""

import argparse
import importlib
import importlib.abc
import importlib.util
import json
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


class _Alias(importlib.abc.Loader):
    def __init__(self, module):
        self.module = module

    def create_module(self, spec):
        self.spec = self.module.__spec__
        return self.module

    def exec_module(self, module):
        module.__spec__ = self.spec  # Keep crabxl's own spec for its relative imports.


class _Finder(importlib.abc.MetaPathFinder):
    def __init__(self, root):
        self.root = root

    def find_spec(self, name, path=None, target=None):
        if name != "openpyxl" and not name.startswith("openpyxl."):
            return None
        parts = name.split(".")
        if any(p == "tests" or p.startswith("test_") or p == "conftest" for p in parts):
            base = self.root.joinpath(*parts)
            if (base / "__init__.py").exists():
                return importlib.util.spec_from_file_location(
                    name, base / "__init__.py", submodule_search_locations=[str(base)]
                )
            if base.with_suffix(".py").exists():
                return importlib.util.spec_from_file_location(
                    name, base.with_suffix(".py")
                )
            return None
        target_name = "crabxl" + name[len("openpyxl") :]
        try:
            module = importlib.import_module(target_name)
        except ModuleNotFoundError as error:
            # A missing crabxl module is reported as an upstream import failure.
            if error.name == target_name:
                return None
            raise
        return importlib.util.spec_from_loader(
            name, _Alias(module), is_package=hasattr(module, "__path__")
        )


def _failures(junit):
    """Return the node IDs of failed or errored tests in a JUnit XML report."""
    found = set()
    for case in ET.parse(junit).getroot().iter("testcase"):
        if case.find("failure") is None and case.find("error") is None:
            continue
        module, _, owner = case.get("classname", "").rpartition(".")
        if not owner.startswith("Test"):
            module, owner = case.get("classname", ""), ""
        if not module:  # Collection error: the name is the module.
            found.add(case.get("name"))
            continue
        parts = [module.replace(".", "/") + ".py", owner, case.get("name")]
        found.add("::".join(p for p in parts if p))
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-checkout", type=Path, required=True)
    parser.add_argument("--expected", type=Path, help="JSON file of expected failures")
    parser.add_argument("pytest_args", nargs="*")
    args = parser.parse_args()
    root = args.reference_checkout.resolve()
    if not (root / "openpyxl" / "__init__.py").exists():
        parser.error(f"No openpyxl package under {root}")
    sys.meta_path.insert(0, _Finder(root))
    import pytest

    junit = Path(tempfile.mkdtemp()) / "suite.xml"
    extra = [f"--junitxml={junit}"] if args.expected else []
    code = pytest.main(
        [
            str(root / "openpyxl"),
            "--rootdir",
            str(root),
            "-p",
            "no:cacheprovider",
            "--continue-on-collection-errors",
            "-o",
            "addopts=--strict-markers",
            "-q",
            *extra,
            *args.pytest_args,
        ]
    )
    if not args.expected:
        return code
    expected = {
        i for ids in json.loads(args.expected.read_text()).values() for i in ids
    }
    failed = _failures(junit)
    for label, ids in (
        ("Unexpected failure", failed - expected),
        ("Now passes", expected - failed),
    ):
        for node in sorted(ids):
            print(f"{label}: {node}")
    return int(failed != expected)


if __name__ == "__main__":
    raise SystemExit(main())
