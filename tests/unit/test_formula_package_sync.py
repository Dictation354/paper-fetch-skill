from __future__ import annotations

import json

from scripts import validate_macos_adaptation as macos_contract
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
    contract = macos_contract.load_contract()["components"]["formula_tools"]

    assert formula_dependencies == root_dependencies
    assert _locked_dependencies(FORMULA_LOCK) == root_dependencies
    assert _locked_dependencies(ROOT_LOCK) == root_dependencies
    assert root_dependencies == macos_contract.EXPECTED_FORMULA_NODE_DEPENDENCIES
    assert {
        "katex": contract["katex_specifier"],
        "mathml-to-latex": contract["mathml_to_latex_specifier"],
    } == root_dependencies
    assert all(
        specifier.startswith(">=") and " <" in specifier
        for specifier in root_dependencies.values()
    )
    assert contract["node_package_manifests"] == [
        path.relative_to(REPO_ROOT).as_posix()
        for path in (ROOT_PACKAGE, FORMULA_PACKAGE)
    ]
    assert contract["node_package_locks"] == [
        path.relative_to(REPO_ROOT).as_posix() for path in (ROOT_LOCK, FORMULA_LOCK)
    ]


def test_formula_lockfiles_resolve_same_compatible_dependency_versions() -> None:
    contract = macos_contract.load_contract()["components"]["formula_tools"]
    expected_versions = {
        "katex": contract["katex_version"],
        "mathml-to-latex": contract["mathml_to_latex_version"],
    }

    assert expected_versions == macos_contract.EXPECTED_FORMULA_NODE_RESOLUTIONS
    for package_name, expected_version in expected_versions.items():
        assert _locked_package_version(ROOT_LOCK, package_name) == expected_version
        assert _locked_package_version(FORMULA_LOCK, package_name) == expected_version
