from __future__ import annotations

import json

from tests.paths import REPO_ROOT, SRC_DIR


ROOT_PACKAGE = REPO_ROOT / "package.json"
ROOT_LOCK = REPO_ROOT / "package-lock.json"
FORMULA_PACKAGE = SRC_DIR / "paper_fetch" / "resources" / "formula" / "package.json"
FORMULA_LOCK = SRC_DIR / "paper_fetch" / "resources" / "formula" / "package-lock.json"


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _locked_dependencies(path):
    return _load_json(path)["packages"][""]["dependencies"]


def _locked_package_version(path, package_name: str) -> str:
    return str(_load_json(path)["packages"][f"node_modules/{package_name}"]["version"])


def test_formula_node_package_dependencies_stay_in_sync() -> None:
    root_dependencies = _load_json(ROOT_PACKAGE)["dependencies"]
    formula_dependencies = _load_json(FORMULA_PACKAGE)["dependencies"]
    assert formula_dependencies == root_dependencies
    assert _locked_dependencies(FORMULA_LOCK) == root_dependencies
    assert _locked_dependencies(ROOT_LOCK) == root_dependencies
    assert all(
        specifier.startswith(">=") and " <" in specifier
        for specifier in root_dependencies.values()
    )


def test_formula_lockfiles_resolve_same_compatible_dependency_versions() -> None:
    for package_name in _load_json(ROOT_PACKAGE)["dependencies"]:
        assert _locked_package_version(ROOT_LOCK, package_name) == (
            _locked_package_version(FORMULA_LOCK, package_name)
        )
