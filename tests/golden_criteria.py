from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Iterable

from tests.paths import FIXTURE_DIR, REPO_ROOT


GOLDEN_CRITERIA_ROOT = FIXTURE_DIR / "golden_criteria"
GOLDEN_CRITERIA_MANIFEST = GOLDEN_CRITERIA_ROOT / "manifest.json"


def doi_to_fixture_slug(doi: str) -> str:
    return doi.replace("/", "_")


@lru_cache(maxsize=1)
def _casefolded_sample_dirs() -> dict[str, Path]:
    return {
        path.name.casefold(): path
        for path in GOLDEN_CRITERIA_ROOT.iterdir()
        if path.is_dir() and path.name != "_scenarios"
    }


def golden_criteria_dir_for_doi(doi: str) -> Path:
    direct = GOLDEN_CRITERIA_ROOT / doi_to_fixture_slug(doi)
    if direct.exists():
        return direct
    return _casefolded_sample_dirs().get(direct.name.casefold(), direct)


def golden_criteria_asset(doi: str, filename: str) -> Path:
    return golden_criteria_dir_for_doi(doi) / filename


def golden_criteria_scenario_dir(name: str) -> Path:
    return GOLDEN_CRITERIA_ROOT / "_scenarios" / name


def golden_criteria_scenario_asset(name: str, filename: str) -> Path:
    return golden_criteria_scenario_dir(name) / filename


def golden_criteria_repo_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


@lru_cache(maxsize=1)
def golden_criteria_manifest() -> dict[str, Any]:
    return json.loads(GOLDEN_CRITERIA_MANIFEST.read_text(encoding="utf-8"))


def golden_criteria_sample(sample_id: str) -> dict[str, Any]:
    sample = dict(golden_criteria_manifest()["samples"][sample_id])
    sample["sample_id"] = sample_id
    return sample


@lru_cache(maxsize=1)
def _samples_by_doi_and_family() -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for sample_id, sample in golden_criteria_manifest()["samples"].items():
        fixture_family = str(sample.get("fixture_family") or "golden")
        doi = str(sample.get("doi") or sample_id)
        indexed[(fixture_family, doi.casefold())] = golden_criteria_sample(sample_id)
    return indexed


def fixture_sample_for_doi(doi: str, *, fixture_family: str = "golden") -> dict[str, Any]:
    return dict(_samples_by_doi_and_family()[(fixture_family, doi.casefold())])


def golden_criteria_sample_for_doi(doi: str) -> dict[str, Any]:
    return fixture_sample_for_doi(doi, fixture_family="golden")


def iter_manifest_samples(*, fixture_family: str | None = None) -> tuple[dict[str, Any], ...]:
    samples: Iterable[dict[str, Any]] = (
        golden_criteria_sample(sample_id) for sample_id in golden_criteria_manifest()["samples"]
    )
    if fixture_family is None:
        return tuple(samples)
    return tuple(sample for sample in samples if sample.get("fixture_family") == fixture_family)
