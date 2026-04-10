from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path

from tests.paths import REPO_ROOT, SKILL_DIR, SRC_DIR, TESTS_ROOT

ARCHITECTURE_DOC = REPO_ROOT / "docs" / "architecture" / "target-architecture.md"


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
            if name in {"article_model", "fetch_common", "providers"} or name.startswith("providers."):
                return f"legacy import '{name}'", node.lineno
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module in {"article_model", "fetch_common", "providers"} or module.startswith("providers."):
            return f"legacy from-import '{module}'", node.lineno
    return None


def forbidden_test_patterns(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    problems: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and is_sys_path_mutation(node):
            problems.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} uses sys.path mutation")
        elif isinstance(node, ast.Call) and is_spec_from_file_location(node):
            problems.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} uses spec_from_file_location")
        elif isinstance(node, ast.Assign):
            if any(is_sys_modules_subscript(target) for target in node.targets):
                problems.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} mutates sys.modules")
        elif isinstance(node, ast.AnnAssign) and is_sys_modules_subscript(node.target):
            problems.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} mutates sys.modules")
        elif isinstance(node, ast.AugAssign) and is_sys_modules_subscript(node.target):
            problems.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} mutates sys.modules")

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


class ArchitectureCloseoutTests(unittest.TestCase):
    def test_tests_no_longer_depend_on_legacy_import_hacks(self) -> None:
        problems: list[str] = []
        for path in iter_test_files():
            problems.extend(forbidden_test_patterns(path))
        self.assertEqual(problems, [], "\n".join(problems))

    def test_repo_skill_source_stays_runtime_agnostic(self) -> None:
        self.assertTrue((SKILL_DIR / "SKILL.md").exists())
        self.assertFalse((SKILL_DIR / "agents" / "openai.yaml").exists())

        entries = sorted(path.relative_to(SKILL_DIR).as_posix() for path in SKILL_DIR.rglob("*"))
        self.assertEqual(entries, ["SKILL.md"])

    def test_repo_hygiene_guards_against_old_script_package_and_tracked_benchmarks(self) -> None:
        self.assertFalse((REPO_ROOT / "scripts" / "__init__.py").exists())
        self.assertFalse((REPO_ROOT / "references" / "formula_backend_report.json").exists())

    def test_architecture_doc_defers_backlog_to_problems_md(self) -> None:
        text = ARCHITECTURE_DOC.read_text(encoding="utf-8")
        header = text.split("## Decision", 1)[0]

        self.assertIn("problems.md", header)
        self.assertNotIn("Remaining deltas", header)

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
        self.assertIn("Fetch AI-friendly full text for a paper by DOI, URL, or title.", result.stdout)
        self.assertIn("--query", result.stdout)
        self.assertIn("--format", result.stdout)
        self.assertIn("--no-html-fallback", result.stdout)
        self.assertIn("PAPER_FETCH_DOWNLOAD_DIR", result.stdout)


if __name__ == "__main__":
    unittest.main()
