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


def _cases(junit):
    """Yield (node ID, outcome) for each test in a JUnit XML report."""
    for case in ET.parse(junit).getroot().iter("testcase"):
        if case.find("failure") is not None or case.find("error") is not None:
            outcome = "failed"
        elif case.find("skipped") is not None:
            outcome = "skipped"
        else:
            outcome = "passed"
        module, _, owner = case.get("classname", "").rpartition(".")
        if not owner.startswith("Test"):
            module, owner = case.get("classname", ""), ""
        if not module:  # Collection error: the name is the module.
            yield case.get("name"), outcome
            continue
        parts = [module.replace(".", "/") + ".py", owner, case.get("name")]
        yield "::".join(p for p in parts if p), outcome


def _failures(junit):
    """Return the node IDs of failed or errored tests in a JUnit XML report."""
    return {node for node, outcome in _cases(junit) if outcome == "failed"}


def _package(node):
    parts = node.replace(".", "/").split("/")
    return parts[1] if parts[1:] and parts[1] not in ("tests", "py") else "(top level)"


def _report(junit, reasons, path):
    """Write the public compatibility page: results by openpyxl package."""
    rows = {}
    for node, outcome in _cases(junit):
        if outcome == "failed":
            outcome = (
                "deliberate"
                if reasons.get(node, "").startswith("deliberate")
                else "internal"
            )
        counts = rows.setdefault(
            _package(node),
            dict.fromkeys(("passed", "internal", "deliberate", "skipped"), 0),
        )
        counts[outcome] += 1
    total = {
        key: sum(r[key] for r in rows.values())
        for key in ("passed", "internal", "deliberate", "skipped")
    }
    public = total["passed"] + total["deliberate"]
    lines = [
        "---",
        "title: Compatibility",
        "description: Results of the openpyxl 3.1.5 test suite run against CrabXL.",
        "---",
        "",
        "CrabXL runs the test suite of openpyxl 3.1.5 without changes. Each",
        "`openpyxl` module that the tests use resolves to the matching `crabxl`",
        "module.",
        "",
        "## Summary",
        "",
        f"- {total['passed']:,} tests pass. This is "
        f"{total['passed'] / public:.1%} of the tests of the public API.",
        f"- {total['deliberate']} tests fail because CrabXL is different on",
        "  purpose. The next section lists them.",
        f"- {total['internal']} tests use private parts of openpyxl, for example the",
        "  `_reader` and `_writer` classes or the `_style` attribute. CrabXL does",
        "  this work in Rust, so these tests do not apply.",
        f"- {total['skipped']} tests are skipped or expected to fail in openpyxl itself.",
        "",
        "## Deliberate differences",
        "",
        "- CrabXL keeps the source names of VBA, external link and comment parts.",
        "  openpyxl renames them.",
        "- CrabXL keeps an unchanged calculation chain. openpyxl removes it.",
        "- CrabXL writes the elements of a projected pie chart in the order that the",
        "  file format specifies, because Excel requires it.",
        "",
        "## Results by package",
        "",
        "| openpyxl package | Pass | Private API | Different on purpose | Skipped |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, counts in sorted(rows.items()):
        lines.append(
            f"| `{name}` | {counts['passed']} | {counts['internal']} | {counts['deliberate']} | {counts['skipped']} |"
        )
    lines.append(
        f"| **Total** | **{total['passed']:,}** | **{total['internal']}** | **{total['deliberate']}** | **{total['skipped']}** |"
    )
    lines += [
        "",
        "To run the suite, see `tools/run_openpyxl_suite.py` in the",
        "[repository](https://github.com/crabxl/crabxl-python/blob/main/tools/run_openpyxl_suite.py).",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-checkout", type=Path, required=True)
    parser.add_argument("--expected", type=Path, help="JSON file of expected failures")
    parser.add_argument("--report", type=Path, help="write the compatibility page here")
    parser.add_argument("pytest_args", nargs="*")
    args = parser.parse_args()
    root = args.reference_checkout.resolve()
    if not (root / "openpyxl" / "__init__.py").exists():
        parser.error(f"No openpyxl package under {root}")
    sys.meta_path.insert(0, _Finder(root))
    import pytest

    junit = Path(tempfile.mkdtemp()) / "suite.xml"
    extra = [f"--junitxml={junit}"] if args.expected or args.report else []
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
    groups = json.loads(args.expected.read_text()) if args.expected else {}
    if args.report:
        _report(junit, {i: k for k, ids in groups.items() for i in ids}, args.report)
    if not args.expected:
        return code
    expected = {i for ids in groups.values() for i in ids}
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
