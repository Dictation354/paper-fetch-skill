from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "onboarding" / "manifests"
UNIT_DIR = REPO_ROOT / "tests" / "unit"
STEP_ALIASES = {
    "landing_html": ("landing_html", "landing html", "landing_url", "landing"),
    "article_html": ("article_html", "article html", "html_article", "html article"),
    "xml": ("xml",),
    "pdf_fallback": ("pdf_fallback", "pdf fallback"),
    "abstract_only": ("abstract_only", "abstract only"),
    "metadata_only": (
        "metadata_only",
        "metadata only",
        "metadata fallback",
        "metadata",
    ),
}


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _doi_slug(value: str) -> str:
    return value.strip().lower().replace("https://doi.org/", "").replace("/", "_")


def _manifest_paths() -> list[Path]:
    return sorted(MANIFEST_DIR.glob("*.yml"))


def _load_manifest(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path}: manifest root must be an object"
    return data


def _provider_test_paths(provider: str) -> list[Path]:
    paths: list[Path] = []
    provider_re = re.compile(rf"\b{re.escape(provider)}\b|{re.escape(provider)}_")
    for path in sorted(UNIT_DIR.glob("test_*.py")):
        if path.name == "test_provider_route_contract.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if provider in path.name or provider_re.search(text):
            paths.append(path)
    return paths


def _coverage_text(paths: list[Path]) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8", errors="ignore").lower() for path in paths
    )


def _step_dois(manifest: dict[str, Any], step: str) -> list[str]:
    values: list[str] = []
    markdown_contract = manifest.get("markdown_contract")
    if isinstance(markdown_contract, dict):
        contract = markdown_contract.get(step)
        if isinstance(contract, dict) and isinstance(contract.get("doi"), str):
            values.append(contract["doi"])
    fixtures = (
        manifest.get("fixtures") if isinstance(manifest.get("fixtures"), dict) else {}
    )
    doi_samples = (
        fixtures.get("doi_samples")
        if isinstance(fixtures.get("doi_samples"), dict)
        else {}
    )
    sample = doi_samples.get(step)
    if isinstance(sample, dict) and isinstance(sample.get("doi"), str):
        values.append(sample["doi"])
    return values


@pytest.mark.parametrize("manifest_path", _manifest_paths(), ids=lambda path: path.stem)
def test_provider_route_contract_has_provider_local_coverage(
    manifest_path: Path,
) -> None:
    manifest = _load_manifest(manifest_path)
    provider = manifest["name"]
    main_path = manifest.get("main_path")
    route_contract = manifest.get("route_contract")
    route_sources = (
        manifest.get("route_sources")
        if isinstance(manifest.get("route_sources"), dict)
        else {}
    )
    assert isinstance(main_path, list) and main_path, (
        f"{manifest_path}: main_path is required"
    )
    assert isinstance(route_contract, dict), (
        f"{manifest_path}: route_contract is required"
    )

    provider_test_paths = _provider_test_paths(provider)
    assert provider_test_paths, (
        f"{manifest_path}: no provider-local route test evidence found"
    )
    corpus = _coverage_text(provider_test_paths)
    normalized_corpus = _normalize(corpus)

    for step in main_path:
        assert step in route_contract, (
            f"{manifest_path}: route_contract.{step} is required"
        )
        contract = route_contract[step]
        assert isinstance(contract, dict), (
            f"{manifest_path}: route_contract.{step} must be an object"
        )
        success_requires = contract.get("success_requires")
        assert success_requires, (
            f"{manifest_path}: route_contract.{step}.success_requires is required"
        )

        step_evidence = [step, *STEP_ALIASES.get(str(step), ())]
        route_source = route_sources.get(step)
        if isinstance(route_source, str) and route_source:
            step_evidence.append(route_source)
        step_evidence.extend(_doi_slug(doi) for doi in _step_dois(manifest, step))
        assert any(_normalize(item) in normalized_corpus for item in step_evidence), (
            f"{manifest_path}: route_contract.{step} has no provider-local step/source/DOI "
            f"coverage in {[path.name for path in provider_test_paths]}"
        )

        for condition in success_requires:
            assert isinstance(condition, str) and condition.strip(), (
                f"{manifest_path}: route_contract.{step}.success_requires contains "
                "an empty condition"
            )
        for condition in contract.get("reject_if_any") or []:
            assert isinstance(condition, str) and condition.strip(), (
                f"{manifest_path}: route_contract.{step}.reject_if_any contains "
                "an empty condition"
            )

        if contract.get("require_pdf_magic") is True:
            assert any(
                token in normalized_corpus
                for token in (
                    "pdf magic",
                    "magic bytes",
                    "application pdf",
                    "content type",
                )
            ), (
                f"{manifest_path}: route_contract.{step}.require_pdf_magic needs explicit PDF magic coverage"
            )
        if contract.get("reject_html_wrapper") is True:
            assert any(
                token in normalized_corpus
                for token in ("html wrapper", "stamp jsp", "not a pdf", "text html")
            ), (
                f"{manifest_path}: route_contract.{step}.reject_html_wrapper needs explicit HTML wrapper coverage"
            )
