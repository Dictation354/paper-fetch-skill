from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from tests.golden_criteria import golden_criteria_manifest
from tests.paths import REPO_ROOT


OriginKind = Literal["real_replay", "real_excerpt", "contract_scenario", "synthetic"]
FixtureFamily = Literal["golden", "block", "scenario"]
UsageKind = Literal["content", "infrastructure"]


@dataclass(frozen=True)
class FixtureRecord:
    fixture_path: str
    doi: str
    source_url: str
    publisher: str
    origin_kind: OriginKind
    fixture_family: FixtureFamily
    usage_kind: UsageKind

    @property
    def absolute_path(self) -> Path:
        return REPO_ROOT / self.fixture_path


def _repo_relative(path: Path | str) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.relative_to(REPO_ROOT).as_posix()
    return candidate.as_posix()


def _record(
    fixture_path: Path | str,
    *,
    doi: str,
    source_url: str,
    publisher: str,
    origin_kind: OriginKind,
    fixture_family: FixtureFamily,
    usage_kind: UsageKind = "content",
) -> FixtureRecord:
    return FixtureRecord(
        fixture_path=_repo_relative(fixture_path),
        doi=doi,
        source_url=source_url,
        publisher=publisher,
        origin_kind=origin_kind,
        fixture_family=fixture_family,
        usage_kind=usage_kind,
    )


def _iter_manifest_records() -> list[FixtureRecord]:
    manifest = golden_criteria_manifest()
    records: list[FixtureRecord] = []
    for sample_id, sample in manifest["samples"].items():
        doi = str(sample.get("doi") or sample_id)
        source_url = str(sample.get("source_url") or f"scenario://{sample_id}")
        publisher = str(sample.get("publisher") or "generic")
        origin_kind = str(sample.get("origin_kind") or "real_replay")
        fixture_family = str(sample.get("fixture_family") or "golden")
        usage_kind = str(sample.get("usage_kind") or "content")
        for fixture_path in sample.get("assets", {}).values():
            records.append(
                _record(
                    fixture_path,
                    doi=doi,
                    source_url=source_url,
                    publisher=publisher,
                    origin_kind=origin_kind,  # type: ignore[arg-type]
                    fixture_family=fixture_family,  # type: ignore[arg-type]
                    usage_kind=usage_kind,  # type: ignore[arg-type]
                )
            )
    return records


@lru_cache(maxsize=1)
def fixture_catalog() -> dict[str, FixtureRecord]:
    return {record.fixture_path: record for record in _iter_manifest_records()}


def fixture_record_for_path(path: Path | str) -> FixtureRecord | None:
    return fixture_catalog().get(_repo_relative(path))
