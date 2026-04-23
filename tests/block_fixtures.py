from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tests.golden_criteria import doi_to_fixture_slug, fixture_sample_for_doi, iter_manifest_samples
from tests.paths import FIXTURE_DIR


BLOCK_FIXTURE_ROOT = FIXTURE_DIR / "block"


@dataclass(frozen=True)
class BlockFixture:
    sample_id: str
    sample: dict[str, Any]

    @property
    def doi(self) -> str:
        return str(self.sample["doi"])

    @property
    def provider(self) -> str:
        return str(self.sample["publisher"])

    @property
    def title(self) -> str:
        return str(self.sample.get("title") or self.doi)

    @property
    def source_url(self) -> str:
        return str(self.sample.get("source_url") or "")

    @property
    def root(self) -> Path:
        return BLOCK_FIXTURE_ROOT / doi_to_fixture_slug(self.doi)

    def asset(self, filename: str) -> Path:
        return self.root / filename


def block_dir_for_doi(doi: str) -> Path:
    return BLOCK_FIXTURE_ROOT / doi_to_fixture_slug(doi)


def block_asset(doi: str, filename: str) -> Path:
    return block_dir_for_doi(doi) / filename


def block_fixture_for_doi(doi: str) -> BlockFixture:
    sample = fixture_sample_for_doi(doi, fixture_family="block")
    return BlockFixture(sample_id=str(sample["sample_id"]), sample=sample)


def iter_block_samples() -> tuple[BlockFixture, ...]:
    fixtures = [
        BlockFixture(sample_id=str(sample["sample_id"]), sample=sample)
        for sample in iter_manifest_samples(fixture_family="block")
    ]
    return tuple(sorted(fixtures, key=lambda item: (item.provider, item.doi)))
