from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.paths import SRC_DIR

PAPER_FETCH_ROOT = SRC_DIR / "paper_fetch"
BOUNDARY_PATHS = [
    PAPER_FETCH_ROOT / "models.py",
    *sorted((PAPER_FETCH_ROOT / "extraction" / "html").glob("*.py")),
    *sorted((PAPER_FETCH_ROOT / "quality").glob("*.py")),
]
FORBIDDEN_PREFIX = "paper_fetch.providers._"


def _module_name_for_path(path: Path) -> str:
    relative = path.relative_to(SRC_DIR).with_suffix("")
    return ".".join(relative.parts)


def _resolve_import_from(module_name: str, node: ast.ImportFrom) -> str:
    if not node.level:
        return node.module or ""
    parts = module_name.split(".")
    base = parts[:-node.level]
    suffix = (node.module or "").split(".") if node.module else []
    return ".".join([*base, *suffix])


def _forbidden_provider_private_imports(path: Path) -> list[str]:
    module_name = _module_name_for_path(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(FORBIDDEN_PREFIX):
                    offenders.append(f"{path.relative_to(SRC_DIR)}:{node.lineno} imports {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            imported_module = _resolve_import_from(module_name, node)
            if imported_module.startswith(FORBIDDEN_PREFIX):
                offenders.append(f"{path.relative_to(SRC_DIR)}:{node.lineno} imports {imported_module}")
    return offenders


class ImportBoundaryTests(unittest.TestCase):
    def test_core_extraction_html_and_quality_do_not_import_provider_private_helpers(self) -> None:
        offenders: list[str] = []
        for path in BOUNDARY_PATHS:
            offenders.extend(_forbidden_provider_private_imports(path))

        self.assertEqual(offenders, [], "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
