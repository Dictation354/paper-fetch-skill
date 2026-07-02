from __future__ import annotations

import ast
import re
from pathlib import Path

import paper_fetch.providers  # noqa: F401
from paper_fetch.providers._registry import iter_provider_bundles


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CENTRAL_PROVIDER_RULE_FILES = (
    PROJECT_ROOT / "src/paper_fetch/extraction/html/provider_rules.py",
    PROJECT_ROOT / "src/paper_fetch/quality/html_signals.py",
    PROJECT_ROOT / "src/paper_fetch/quality/html_availability.py",
)
CENTRAL_PROVIDER_BRANCH_DIRS = (
    PROJECT_ROOT / "src/paper_fetch/quality",
    PROJECT_ROOT / "src/paper_fetch/extraction/html",
)
PROVIDER_BRANCH_VARIABLE_NAMES = {
    "provider",
    "provider_name",
    "name",
    "publisher",
    "publisher_name",
}


def provider_names() -> tuple[str, ...]:
    return tuple(sorted(bundle.catalog.name for bundle in iter_provider_bundles()))


def test_central_modules_do_not_define_provider_specific_functions() -> None:
    for path in CENTRAL_PROVIDER_RULE_FILES:
        source = path.read_text()
        for provider in provider_names():
            pattern = re.compile(rf"^def {re.escape(provider)}_", flags=re.MULTILINE)
            assert pattern.search(source) is None, (
                f"{path.relative_to(PROJECT_ROOT)} defines {provider}_*"
            )


class ProviderBranchVisitor(ast.NodeVisitor):
    def __init__(self, providers: set[str]) -> None:
        self.providers = providers
        self.violations: list[tuple[int, str]] = []

    def visit_If(self, node: ast.If) -> None:
        self._check_compare(node.test)
        self.generic_visit(node)

    def _check_compare(self, node: ast.AST) -> None:
        for child in ast.walk(node):
            if not isinstance(child, ast.Compare):
                continue
            nodes = (child.left, *child.comparators)
            for left, operator, right in zip(nodes, child.ops, nodes[1:], strict=False):
                if not isinstance(operator, ast.Eq):
                    continue
                provider = self._provider_literal(left) or self._provider_literal(right)
                variable = self._provider_variable(left) or self._provider_variable(
                    right
                )
                if provider is not None and variable is not None:
                    self.violations.append((child.lineno, provider))

    def _provider_literal(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value.strip().lower()
            if value in self.providers:
                return value
        return None

    def _provider_variable(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name) and node.id in PROVIDER_BRANCH_VARIABLE_NAMES:
            return node.id
        return None


def test_central_html_and_quality_modules_do_not_branch_on_provider_name() -> None:
    providers = set(provider_names())

    for directory in CENTRAL_PROVIDER_BRANCH_DIRS:
        for path in sorted(directory.rglob("*.py")):
            module_ast = ast.parse(path.read_text(), filename=str(path))
            visitor = ProviderBranchVisitor(providers)
            visitor.visit(module_ast)

            assert not visitor.violations, (
                f"{path.relative_to(PROJECT_ROOT)} has provider-specific branch(es): "
                + ", ".join(
                    f"line {line} compares {provider!r}"
                    for line, provider in visitor.violations
                )
            )
