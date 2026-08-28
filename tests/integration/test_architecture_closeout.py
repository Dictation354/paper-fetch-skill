from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

from tests.paths import REPO_ROOT, SRC_DIR, TESTS_ROOT

PAPER_FETCH_SRC = SRC_DIR / "paper_fetch"
SERVICE_PATH = PAPER_FETCH_SRC / "service.py"
RESOLVE_QUERY_PATH = PAPER_FETCH_SRC / "resolve" / "query.py"
PROVIDERS_DIR = PAPER_FETCH_SRC / "providers"
PROVIDER_MAGIC_METADATA_KEYS = (
    "route",
    "reason",
    "markdown_text",
    "merged_metadata",
    "availability_diagnostics",
    "extraction",
    "html_fetcher",
    "browser_context_seed",
    "suggested_filename",
    "html_failure_reason",
    "html_failure_message",
    "extracted_assets",
    "warnings",
    "source_trail",
)
MAGIC_KEY_PATTERN = re.compile(
    r"\[(?:\"|\')("
    + "|".join(PROVIDER_MAGIC_METADATA_KEYS)
    + r")(?:\"|\')\]|get\((?:\"|\')("
    + "|".join(PROVIDER_MAGIC_METADATA_KEYS)
    + r")(?:\"|\')"
)
RAW_PAYLOAD_METADATA_MAGIC_PATTERN = re.compile(
    r"\b(?:raw_payload|payload)\.metadata(?:\[(?:\"|\')("
    + "|".join(PROVIDER_MAGIC_METADATA_KEYS)
    + r")(?:\"|\')\]|\.get\((?:\"|\')("
    + "|".join(PROVIDER_MAGIC_METADATA_KEYS)
    + r")(?:\"|\'))"
)
def pythonpath_env() -> dict[str, str]:
    env = os.environ.copy()
    entries = [str(SRC_DIR)]
    if env.get("PYTHONPATH"):
        entries.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(entries)
    return env


def is_sys_path_mutation(call: ast.Call) -> bool:
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in {"insert", "append"}
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "path"
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "sys"
    )


def is_spec_from_file_location(call: ast.Call) -> bool:
    func = call.func
    return (
        isinstance(func, ast.Name)
        and func.id == "spec_from_file_location"
        or isinstance(func, ast.Attribute)
        and func.attr == "spec_from_file_location"
    )


def is_sys_modules_subscript(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "modules"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "sys"
    )


def legacy_import_problem(node: ast.AST) -> tuple[str, int] | None:
    if isinstance(node, ast.Import):
        for alias in node.names:
            name = alias.name
            if name in {
                "article_model",
                "fetch_common",
                "providers",
            } or name.startswith("providers."):
                return f"legacy import '{name}'", node.lineno
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module in {
            "article_model",
            "fetch_common",
            "providers",
        } or module.startswith("providers."):
            return f"legacy from-import '{module}'", node.lineno
    return None


def forbidden_test_patterns(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    problems: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and is_sys_path_mutation(node):
            problems.append(
                f"{path.relative_to(REPO_ROOT)}:{node.lineno} uses sys.path mutation"
            )
        elif isinstance(node, ast.Call) and is_spec_from_file_location(node):
            problems.append(
                f"{path.relative_to(REPO_ROOT)}:{node.lineno} uses spec_from_file_location"
            )
        elif isinstance(node, ast.Assign):
            if any(is_sys_modules_subscript(target) for target in node.targets):
                problems.append(
                    f"{path.relative_to(REPO_ROOT)}:{node.lineno} mutates sys.modules"
                )
        elif isinstance(node, ast.AnnAssign) and is_sys_modules_subscript(node.target):
            problems.append(
                f"{path.relative_to(REPO_ROOT)}:{node.lineno} mutates sys.modules"
            )
        elif isinstance(node, ast.AugAssign) and is_sys_modules_subscript(node.target):
            problems.append(
                f"{path.relative_to(REPO_ROOT)}:{node.lineno} mutates sys.modules"
            )

        import_problem = legacy_import_problem(node)
        if import_problem is not None:
            problem, lineno = import_problem
            problems.append(f"{path.relative_to(REPO_ROOT)}:{lineno} uses {problem}")

    return problems


def iter_test_files() -> list[Path]:
    return [
        path
        for path in sorted(TESTS_ROOT.rglob("test_*.py"))
        if "fixtures" not in path.parts and path.name != "__init__.py"
    ]


def module_name_for_path(path: Path) -> str:
    relative = path.relative_to(SRC_DIR).with_suffix("")
    return ".".join(relative.parts)


def top_level_internal_imports(path: Path) -> list[str]:
    module_name = module_name_for_path(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    module_parts = module_name.split(".")

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("paper_fetch."):
                    imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = module_parts[: -node.level]
                target_parts = base_parts + (
                    (node.module or "").split(".") if node.module else []
                )
                imported_module = ".".join(part for part in target_parts if part)
            else:
                imported_module = node.module or ""
            if imported_module.startswith("paper_fetch."):
                imports.append(imported_module)
    return imports


def keyword_only_parameters(path: Path, function_name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return [arg.arg for arg in node.args.kwonlyargs]
    raise AssertionError(f"{function_name} not found in {path}")


def has_cycle(graph: dict[str, set[str]]) -> bool:
    visited: set[str] = set()
    active: set[str] = set()

    def visit(node: str) -> bool:
        if node in active:
            return True
        if node in visited:
            return False
        visited.add(node)
        active.add(node)
        for neighbor in graph.get(node, set()):
            if visit(neighbor):
                return True
        active.remove(node)
        return False

    return any(visit(node) for node in graph)


class ArchitectureCloseoutTests(unittest.TestCase):
    def test_tests_no_longer_depend_on_legacy_import_hacks(self) -> None:
        problems: list[str] = []
        for path in iter_test_files():
            problems.extend(forbidden_test_patterns(path))
        self.assertEqual(problems, [], "\n".join(problems))

    def test_service_facade_does_not_touch_provider_magic_metadata_keys(self) -> None:
        text = SERVICE_PATH.read_text(encoding="utf-8")
        self.assertNotRegex(text, MAGIC_KEY_PATTERN)

    def test_public_service_api_no_longer_accepts_legacy_runtime_keywords(self) -> None:
        self.assertEqual(
            keyword_only_parameters(SERVICE_PATH, "probe_has_fulltext"), ["context"]
        )
        self.assertEqual(
            keyword_only_parameters(SERVICE_PATH, "fetch_paper"),
            ["modes", "strategy", "render", "context"],
        )

    def test_resolve_query_stays_outside_provider_implementations(self) -> None:
        imports = top_level_internal_imports(RESOLVE_QUERY_PATH)
        disallowed = [
            name for name in imports if name.startswith("paper_fetch.providers")
        ]
        self.assertEqual(disallowed, [])

    def test_provider_modules_no_longer_use_magic_key_contract_reads_or_writes(
        self,
    ) -> None:
        offenders: list[str] = []
        for path in sorted(PROVIDERS_DIR.glob("*.py")):
            if path.name == "base.py":
                continue
            text = path.read_text(encoding="utf-8")
            if RAW_PAYLOAD_METADATA_MAGIC_PATTERN.search(text):
                offenders.append(path.relative_to(REPO_ROOT).as_posix())
        self.assertEqual(offenders, [])

    def test_production_code_does_not_read_raw_payload_metadata_magic_keys(
        self,
    ) -> None:
        offenders: list[str] = []
        for path in sorted(PAPER_FETCH_SRC.rglob("*.py")):
            if path == PROVIDERS_DIR / "base.py":
                continue
            text = path.read_text(encoding="utf-8")
            match = RAW_PAYLOAD_METADATA_MAGIC_PATTERN.search(text)
            if match:
                offenders.append(
                    f"{path.relative_to(REPO_ROOT).as_posix()}:{text[: match.start()].count(chr(10)) + 1}"
                )
        self.assertEqual(offenders, [])

    def test_targeted_static_import_graph_is_cycle_free(self) -> None:
        package_paths = sorted(PAPER_FETCH_SRC.rglob("*.py"))
        target_modules = {module_name_for_path(path) for path in package_paths}
        graph: dict[str, set[str]] = {
            module_name_for_path(path): set() for path in package_paths
        }
        for path in package_paths:
            module_name = module_name_for_path(path)
            for imported_module in top_level_internal_imports(path):
                if imported_module in target_modules:
                    graph[module_name].add(imported_module)
        self.assertFalse(has_cycle(graph), graph)

    def test_cli_module_help_smoke(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "paper_fetch.cli", "--help"],
            cwd=REPO_ROOT,
            env=pythonpath_env(),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "Fetch AI-friendly paper full text and manage browser-backed provider access.",
            result.stdout,
        )
        self.assertIn("--query", result.stdout)
        self.assertIn("--format", result.stdout)
        self.assertIn("PAPER_FETCH_DOWNLOAD_DIR", result.stdout)

    def test_formula_installer_help_smoke(self) -> None:
        result = subprocess.run(
            ["paper-fetch-install-formula-tools", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "Install optional external formula backends for paper-fetch.", result.stdout
        )
        self.assertIn("--target-dir", result.stdout)
        self.assertIn("--no-node", result.stdout)


if __name__ == "__main__":
    unittest.main()
