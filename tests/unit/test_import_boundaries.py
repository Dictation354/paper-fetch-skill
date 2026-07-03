from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path

from tests.paths import SRC_DIR

PAPER_FETCH_ROOT = SRC_DIR / "paper_fetch"
BOUNDARY_PATHS = [
    *sorted((PAPER_FETCH_ROOT / "models").rglob("*.py")),
    *sorted((PAPER_FETCH_ROOT / "markdown").glob("*.py")),
    *sorted((PAPER_FETCH_ROOT / "extraction" / "html").rglob("*.py")),
    *sorted((PAPER_FETCH_ROOT / "quality").glob("*.py")),
]
HTML_ASSET_IMPORT_BOUNDARY_PATHS = [
    PAPER_FETCH_ROOT / "extraction" / "html" / "assets" / "download.py",
    PAPER_FETCH_ROOT / "extraction" / "html" / "assets" / "supplementary.py",
]
FORBIDDEN_PREFIX = "paper_fetch.providers._"
PROVIDER_RULE_HOOK_IMPORTS = frozenset(
    {
        "paper_fetch.providers._ams_html",
        "paper_fetch.providers._pnas_html",
        "paper_fetch.providers._science_html",
        "paper_fetch.providers._wiley_html",
    }
)
PROVIDER_RULES_PATH = PAPER_FETCH_ROOT / "extraction" / "html" / "provider_rules.py"


def _module_name_for_path(path: Path) -> str:
    relative = path.relative_to(SRC_DIR).with_suffix("")
    return ".".join(relative.parts)


def _resolve_import_from(module_name: str, node: ast.ImportFrom) -> str:
    if not node.level:
        return node.module or ""
    parts = module_name.split(".")
    base = parts[: -node.level]
    suffix = (node.module or "").split(".") if node.module else []
    return ".".join([*base, *suffix])


def _imported_modules(
    path: Path, *, module_name: str | None = None
) -> list[tuple[str, int]]:
    module_name = module_name or _module_name_for_path(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_module = _resolve_import_from(module_name, node)
            imports.append((imported_module, node.lineno))
            imports.extend(
                (f"{imported_module}.{alias.name}", node.lineno)
                for alias in node.names
                if alias.name != "*"
            )
    return imports


def _forbidden_provider_private_imports(path: Path) -> list[str]:
    offenders: list[str] = []
    for imported_module, lineno in _imported_modules(path):
        if (
            path == PROVIDER_RULES_PATH
            and imported_module in PROVIDER_RULE_HOOK_IMPORTS
        ):
            continue
        if imported_module.startswith(FORBIDDEN_PREFIX):
            offenders.append(
                f"{path.relative_to(SRC_DIR)}:{lineno} imports {imported_module}"
            )
    return offenders


class ImportBoundaryTests(unittest.TestCase):
    def test_provider_neutral_modules_do_not_import_provider_private_helpers(
        self,
    ) -> None:
        offenders: list[str] = []
        for path in BOUNDARY_PATHS:
            offenders.extend(_forbidden_provider_private_imports(path))

        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_arxiv_provider_does_not_import_pypi_arxiv_package(self) -> None:
        offenders = [
            f"{imported_module}:{lineno}"
            for imported_module, lineno in _imported_modules(
                PAPER_FETCH_ROOT / "providers" / "arxiv.py"
            )
            if imported_module == "arxiv" or imported_module.startswith("arxiv.")
        ]

        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_html_asset_modules_do_not_import_public_models_package(self) -> None:
        offenders: list[str] = []
        for path in HTML_ASSET_IMPORT_BOUNDARY_PATHS:
            for imported_module, lineno in _imported_modules(path):
                if imported_module == "paper_fetch.models":
                    offenders.append(
                        f"{path.relative_to(SRC_DIR)}:{lineno} imports {imported_module}"
                    )

        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_root_import_does_not_load_heavy_optional_html_dependencies(
        self,
    ) -> None:
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import importlib
import sys

importlib.import_module("paper_fetch")

forbidden = sorted(
    name
    for name in sys.modules
    if name == "trafilatura"
    or name.startswith("trafilatura.")
    or name == "idutils"
    or name.startswith("idutils.")
)
provider_entries = sorted(
    name
    for name in sys.modules
    if name.startswith("paper_fetch.providers.")
    and name
    not in {
        "paper_fetch.providers.base",
        "paper_fetch.providers.protocols",
        "paper_fetch.providers.registry",
    }
)
if forbidden:
    raise SystemExit("forbidden optional modules loaded: " + ", ".join(forbidden))
if provider_entries:
    raise SystemExit("provider entry modules loaded: " + ", ".join(provider_entries))
""",
            ],
            check=False,
            text=True,
            capture_output=True,
            env={**os.environ, "PYTHONPATH": str(SRC_DIR)},
        )

        self.assertEqual(probe.returncode, 0, probe.stderr + probe.stdout)


if __name__ == "__main__":
    unittest.main()
