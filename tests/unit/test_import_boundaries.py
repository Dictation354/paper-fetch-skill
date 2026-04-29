from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.paths import REPO_ROOT, SRC_DIR, TESTS_ROOT

PAPER_FETCH_ROOT = SRC_DIR / "paper_fetch"
BOUNDARY_PATHS = [
    PAPER_FETCH_ROOT / "models.py",
    *sorted((PAPER_FETCH_ROOT / "markdown").glob("*.py")),
    *sorted((PAPER_FETCH_ROOT / "extraction" / "html").glob("*.py")),
    *sorted((PAPER_FETCH_ROOT / "quality").glob("*.py")),
]
FORBIDDEN_PREFIX = "paper_fetch.providers._"
REMOVED_PROVIDER_COMPATIBILITY_MODULES = frozenset(
    {
        "paper_fetch.providers._article_markdown",
        "paper_fetch.providers._html_access_signals",
        "paper_fetch.providers._html_availability",
        "paper_fetch.providers._html_citations",
        "paper_fetch.providers._html_semantics",
        "paper_fetch.providers._html_tables",
        "paper_fetch.providers._html_text",
        "paper_fetch.providers._language_filter",
        "paper_fetch.providers._science_pnas",
        "paper_fetch.resolve.crossref",
    }
)


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


def _imported_modules(path: Path, *, module_name: str | None = None) -> list[tuple[str, int]]:
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
        if imported_module.startswith(FORBIDDEN_PREFIX):
            offenders.append(f"{path.relative_to(SRC_DIR)}:{lineno} imports {imported_module}")
    return offenders


def _iter_python_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def _uses_removed_compatibility_module(imported_module: str) -> bool:
    return any(
        imported_module == removed or imported_module.startswith(f"{removed}.")
        for removed in REMOVED_PROVIDER_COMPATIBILITY_MODULES
    )


class ImportBoundaryTests(unittest.TestCase):
    def test_provider_neutral_modules_do_not_import_provider_private_helpers(self) -> None:
        offenders: list[str] = []
        for path in BOUNDARY_PATHS:
            offenders.extend(_forbidden_provider_private_imports(path))

        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_source_and_tests_do_not_import_removed_provider_compatibility_modules(self) -> None:
        offenders: list[str] = []
        for path in [*_iter_python_files(PAPER_FETCH_ROOT), *_iter_python_files(TESTS_ROOT)]:
            module_name = (
                _module_name_for_path(path)
                if path.is_relative_to(SRC_DIR)
                else ".".join(path.relative_to(REPO_ROOT).with_suffix("").parts)
            )
            for imported_module, lineno in _imported_modules(path, module_name=module_name):
                if _uses_removed_compatibility_module(imported_module):
                    offenders.append(
                        f"{path.relative_to(REPO_ROOT)}:{lineno} imports {imported_module}"
                    )

        self.assertEqual(offenders, [], "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
