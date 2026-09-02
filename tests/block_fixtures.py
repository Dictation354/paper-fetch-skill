from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from paper_fetch.extraction.html._metadata import parse_html_metadata
from paper_fetch.extraction.html.signals import HtmlExtractionFailure
from paper_fetch.http import HttpTransport
from paper_fetch.providers import (
    _springer_html as springer_html,
    annualreviews as annualreviews_provider,
    pnas as pnas_provider,
    science as science_provider,
    wiley as wiley_provider,
)
from paper_fetch.quality.html_availability import assess_html_fulltext_availability
from tests.golden_criteria import (
    doi_to_fixture_slug,
    iter_manifest_samples,
)
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

    @property
    def negative_case_kind(self) -> str:
        return str(self.sample["negative_case_kind"])

    @property
    def provider_route(self) -> str:
        return str(self.sample["provider_route"])

    @property
    def source_identity(self) -> str:
        return str(self.sample["source_identity"])

    @property
    def expected_reason(self) -> str:
        return str(self.sample["expected_reason"])

    @property
    def expected_failure_code(self) -> str:
        return str(self.sample["expected_failure_code"])

    @property
    def expected_content_kind(self) -> str:
        return str(self.sample["expected_content_kind"])

    @property
    def raw_path(self) -> Path:
        assets = self.sample.get("assets")
        if not isinstance(assets, dict):
            raise FileNotFoundError(
                f"Block fixture has no asset mapping: {self.sample_id}"
            )
        candidates = [name for name in ("raw.html", "raw.xml") if name in assets]
        if len(candidates) != 1:
            raise FileNotFoundError(
                f"Block fixture must declare exactly one canonical raw asset: {self.sample_id}"
            )
        path = self.asset(candidates[0])
        if not path.is_file():
            raise FileNotFoundError(f"Block fixture raw asset is absent: {path}")
        return path


@dataclass(frozen=True)
class BlockReplayResult:
    accepted: bool
    content_kind: str
    reason: str
    failure_code: str
    provider_route: str
    source_identity: str
    extractor: str


_HTML_CLIENTS = {
    "annualreviews": annualreviews_provider.AnnualreviewsClient,
    "pnas": pnas_provider.PnasClient,
    "science": science_provider.ScienceClient,
    "wiley": wiley_provider.WileyClient,
}


def _exception_replay_result(
    fixture: BlockFixture, exc: HtmlExtractionFailure
) -> BlockReplayResult:
    reason = str(exc.reason)
    return BlockReplayResult(
        accepted=False,
        content_kind="abstract_only" if reason == "abstract_only" else "metadata_only",
        reason=reason,
        failure_code="html_extraction_rejected",
        provider_route=fixture.provider_route,
        source_identity=fixture.source_identity,
        extractor=f"{fixture.provider}.extract_markdown",
    )


def _execute_html_block_fixture(fixture: BlockFixture) -> BlockReplayResult:
    html_text = fixture.raw_path.read_text(encoding="utf-8", errors="ignore")
    metadata = {
        **parse_html_metadata(html_text, fixture.source_url),
        "doi": fixture.doi,
        "title": fixture.title,
    }
    if fixture.provider == "springer":
        extraction = springer_html.extract_html_payload(
            html_text,
            title=fixture.title,
            source_url=fixture.source_url,
        )
        markdown_text = str(extraction["markdown_text"])
        section_hints = list(extraction.get("section_hints") or [])
        extractor = "springer.extract_html_payload"
    else:
        try:
            client_type = _HTML_CLIENTS[fixture.provider]
        except KeyError as exc:
            raise ValueError(
                f"No current HTML extractor registered for block provider {fixture.provider!r}"
            ) from exc
        try:
            markdown_text, extraction = client_type(
                HttpTransport(), {}
            ).extract_markdown(
                html_text,
                fixture.source_url,
                metadata=metadata,
            )
        except HtmlExtractionFailure as exc:
            return _exception_replay_result(fixture, exc)
        section_hints = list(extraction.get("section_hints") or [])
        extractor = f"{fixture.provider}.extract_markdown"
    diagnostics = assess_html_fulltext_availability(
        markdown_text,
        metadata,
        provider=fixture.provider,
        html_text=html_text,
        title=fixture.title,
        final_url=fixture.source_url,
        section_hints=section_hints,
    )
    return BlockReplayResult(
        accepted=diagnostics.accepted,
        content_kind=diagnostics.content_kind,
        reason=diagnostics.reason,
        failure_code="accepted" if diagnostics.accepted else "availability_rejected",
        provider_route=fixture.provider_route,
        source_identity=fixture.source_identity,
        extractor=extractor,
    )


def execute_block_fixture(fixture: BlockFixture) -> BlockReplayResult:
    """Replay the canonical raw response through the current extraction boundary."""

    if fixture.raw_path.suffix.lower() == ".html":
        return _execute_html_block_fixture(fixture)
    raise ValueError(
        f"No current XML negative replay adapter for {fixture.provider}:{fixture.provider_route}"
    )


def block_dir_for_doi(doi: str) -> Path:
    return BLOCK_FIXTURE_ROOT / doi_to_fixture_slug(doi)


def block_asset(doi: str, filename: str) -> Path:
    return block_dir_for_doi(doi) / filename


def iter_block_samples() -> tuple[BlockFixture, ...]:
    fixtures = [
        BlockFixture(sample_id=str(sample["sample_id"]), sample=sample)
        for sample in iter_manifest_samples(fixture_family="block")
    ]
    return tuple(sorted(fixtures, key=lambda item: (item.provider, item.doi)))
