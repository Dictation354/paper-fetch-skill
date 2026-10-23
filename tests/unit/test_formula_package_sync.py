from __future__ import annotations

import json

from tests.paths import SRC_DIR


FORMULA_PACKAGE = SRC_DIR / "paper_fetch" / "resources" / "formula" / "package.json"
FORMULA_LOCK = SRC_DIR / "paper_fetch" / "resources" / "formula" / "package-lock.json"


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _locked_dependencies(path):
    return _load_json(path)["packages"][""]["dependencies"]


def _locked_package_version(path, package_name: str) -> str:
    return str(_load_json(path)["packages"][f"node_modules/{package_name}"]["version"])


def test_formula_node_package_lock_matches_manifest() -> None:
    formula_dependencies = _load_json(FORMULA_PACKAGE)["dependencies"]
    assert set(formula_dependencies) == {
        "mathml-to-latex",
        "@mathjax/src",
        "@mathjax/mathjax-tex-font",
        "@mathjax/mathjax-mhchem-font-extension",
        "@mathjax/mathjax-bbm-font-extension",
    }
    assert _locked_dependencies(FORMULA_LOCK) == formula_dependencies
    assert all(
        specifier == "4.1.3"
        if name.startswith("@mathjax/")
        else specifier.startswith(">=") and " <" in specifier
        for name, specifier in formula_dependencies.items()
    )


def test_formula_lock_resolves_each_direct_dependency() -> None:
    for package_name in _load_json(FORMULA_PACKAGE)["dependencies"]:
        assert _locked_package_version(FORMULA_LOCK, package_name)
        if package_name.startswith("@mathjax/"):
            assert _locked_package_version(FORMULA_LOCK, package_name) == "4.1.3"
