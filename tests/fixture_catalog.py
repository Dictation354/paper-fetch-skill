from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from typing import Literal

from tests.golden_criteria import golden_criteria_manifest
from tests.paths import REPO_ROOT


OriginKind = Literal[
    "real_replay", "real_excerpt", "contract_scenario", "synthetic", "unverified"
]
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
        origin_kind = str(sample["origin_kind"])
        fixture_family = str(sample.get("fixture_family") or "golden")
        usage_kind = str(sample.get("usage_kind") or "content")
        assets = sample.get("assets", {})
        overrides = sample.get("asset_origins", {})
        unknown = set(overrides) - set(assets)
        if unknown:
            raise ValueError(
                f"Unknown asset_origins keys: {sample_id}: {sorted(unknown)}"
            )
        for asset_key, fixture_path in assets.items():
            asset_origin = overrides.get(asset_key, origin_kind)
            if asset_origin not in {
                "real_replay",
                "real_excerpt",
                "contract_scenario",
                "synthetic",
                "unverified",
            }:
                raise ValueError(f"Unknown asset origin: {sample_id}: {asset_origin}")
            if origin_kind == "synthetic" and asset_origin in {
                "real_replay",
                "real_excerpt",
            }:
                path = REPO_ROOT / fixture_path
                acquisition = next(
                    (parent for parent in path.parents if parent.name == "acquisition"),
                    None,
                )
                provenance = acquisition / "provenance.json" if acquisition else None
                if provenance is None or not provenance.is_file():
                    raise ValueError(
                        f"Unproven synthetic origin override: {fixture_path}"
                    )
                # JSON capture summaries are auxiliary provenance. Publisher
                # entity bytes require their independent recorded checksum.
                if path.name not in {
                    "provenance.json",
                    "capture.json",
                    "collection.json",
                    "article.json",
                    "identity.json",
                    "fetch.manifest.json",
                }:
                    provenance_records = json.loads(provenance.read_text())["records"]
                    record = next(
                        (
                            r
                            for r in provenance_records
                            if acquisition.parent / r["body_file"] == path
                        ),
                        None,
                    )
                    if (
                        record is None
                        or hashlib.sha256(path.read_bytes()).hexdigest()
                        != record["sha256"]
                    ):
                        raise ValueError(
                            f"Unproven synthetic origin override: {fixture_path}"
                        )
            records.append(
                _record(
                    fixture_path,
                    doi=doi,
                    source_url=source_url,
                    publisher=publisher,
                    origin_kind=asset_origin,  # type: ignore[arg-type]
                    fixture_family=fixture_family,  # type: ignore[arg-type]
                    usage_kind=usage_kind,  # type: ignore[arg-type]
                )
            )
    return records


@lru_cache(maxsize=1)
def fixture_catalog() -> dict[str, FixtureRecord]:
    from tests.support.fixture_provenance import rejected_source_hashes

    rejected = rejected_source_hashes()
    catalog: dict[str, FixtureRecord] = {}
    for record in _iter_manifest_records():
        existing = catalog.get(record.fixture_path)
        if existing and existing.origin_kind != record.origin_kind:
            raise ValueError(f"Conflicting asset origins: {record.fixture_path}")
        if (
            record.origin_kind in {"real_replay", "real_excerpt"}
            and record.absolute_path.suffix in {".html", ".xml", ".md"}
            and record.absolute_path.is_file()
        ):
            digest = hashlib.sha256(record.absolute_path.read_bytes()).hexdigest()
            if digest in rejected:
                raise ValueError(
                    f"Disproven real source ({rejected[digest]}): {record.fixture_path}"
                )
        catalog[record.fixture_path] = record
    return catalog
