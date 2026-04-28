"""Helpers for the offline golden fulltext corpus."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from paper_fetch.extraction.html._metadata import parse_html_metadata
from paper_fetch.http import HttpTransport
from paper_fetch.publisher_identity import normalize_doi
from paper_fetch.providers import (
    _pnas_html,
    _science_html,
    _springer_html,
    _wiley_html,
    _science_pnas_profiles,
    elsevier as elsevier_provider,
    pnas as pnas_provider,
    science as science_provider,
    springer as springer_provider,
    wiley as wiley_provider,
)
from paper_fetch.quality.html_availability import assess_html_fulltext_availability
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.tracing import trace_from_markers
from paper_fetch.utils import normalize_text
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi, iter_manifest_samples


REPRESENTATIVE_GOLDEN_CORPUS_DOIS = (
    "10.1016/j.rse.2025.114648",
    "10.1038/s43247-024-01295-w",
    "10.1126/science.adp0212",
    "10.1111/gcb.16414",
    "10.1073/pnas.2309123120",
)


@dataclass(frozen=True)
class GoldenCorpusFixture:
    sample_id: str
    sample: dict[str, Any]

    @property
    def provider(self) -> str:
        return str(self.sample["publisher"])

    @property
    def doi(self) -> str:
        return str(self.sample["doi"])

    @property
    def title(self) -> str:
        return str(self.sample.get("title") or self.doi)

    @property
    def source_url(self) -> str:
        return str(self.sample.get("source_url") or self.sample.get("landing_url") or "")

    @property
    def landing_url(self) -> str:
        return str(self.sample.get("landing_url") or self.sample.get("source_url") or "")

    @property
    def route_kind(self) -> str:
        return str(self.sample.get("route_kind") or "")

    @property
    def content_type(self) -> str:
        return str(self.sample.get("content_type") or "")

    @property
    def raw_path(self) -> Path:
        html_path = golden_criteria_asset(self.doi, "original.html")
        if html_path.exists():
            return html_path
        xml_path = golden_criteria_asset(self.doi, "original.xml")
        if xml_path.exists():
            return xml_path
        raise FileNotFoundError(f"Golden fixture is missing canonical original.html/original.xml: {self.doi}")

    @property
    def expected_path(self) -> Path:
        return golden_criteria_asset(self.doi, "expected.json")

    def load_expected(self) -> dict[str, Any]:
        return json.loads(self.expected_path.read_text(encoding="utf-8"))


def iter_golden_corpus_fixtures() -> tuple[GoldenCorpusFixture, ...]:
    fixtures = [
        GoldenCorpusFixture(sample_id=str(sample["sample_id"]), sample=sample)
        for sample in iter_manifest_samples(fixture_family="golden")
        if "expected.json" in sample.get("assets", {})
    ]
    return tuple(sorted(fixtures, key=lambda item: (item.provider, item.doi)))


def golden_corpus_fixture_for_doi(doi: str) -> GoldenCorpusFixture:
    sample = golden_criteria_sample_for_doi(doi)
    if "expected.json" not in sample.get("assets", {}):
        raise FileNotFoundError(f"Golden corpus fixture is missing expected.json: {doi}")
    return GoldenCorpusFixture(sample_id=str(sample["sample_id"]), sample=sample)


def iter_golden_corpus_representative_fixtures() -> tuple[GoldenCorpusFixture, ...]:
    return tuple(golden_corpus_fixture_for_doi(doi) for doi in REPRESENTATIVE_GOLDEN_CORPUS_DOIS)


def _base_metadata(fixture: GoldenCorpusFixture) -> dict[str, Any]:
    return {
        "doi": fixture.doi,
        "title": fixture.title,
        "landing_page_url": fixture.landing_url,
        "authors": [],
        "fulltext_links": [],
        "references": [],
    }


def _build_elsevier_article(fixture: GoldenCorpusFixture):
    metadata = _base_metadata(fixture)
    raw_payload = RawFulltextPayload(
        provider="elsevier",
        source_url=fixture.source_url,
        content_type=fixture.content_type or "text/xml",
        body=fixture.raw_path.read_bytes(),
        metadata={"route": "official"},
        trace=trace_from_markers(["fulltext:elsevier_xml_ok"]),
        merged_metadata=metadata,
    )
    client = elsevier_provider.ElsevierClient(HttpTransport(), {})
    return client.to_article_model(metadata, raw_payload)


def _build_springer_article(fixture: GoldenCorpusFixture):
    metadata = _base_metadata(fixture)
    html_text = fixture.raw_path.read_text(encoding="utf-8", errors="ignore")
    html_metadata = _springer_html.parse_html_metadata(html_text, fixture.source_url)
    merged_metadata = _springer_html.merge_html_metadata(metadata, html_metadata)
    if not merged_metadata.get("doi"):
        merged_metadata["doi"] = fixture.doi
    extraction_payload = _springer_html.extract_html_payload(
        html_text,
        title=str(merged_metadata.get("title") or fixture.title),
        source_url=fixture.source_url,
    )
    abstract_sections = list(extraction_payload["abstract_sections"])
    section_hints = list(extraction_payload["section_hints"])
    diagnostics = assess_html_fulltext_availability(
        extraction_payload["markdown_text"],
        merged_metadata,
        provider="springer",
        html_text=html_text,
        title=str(merged_metadata.get("title") or fixture.title),
        final_url=fixture.source_url,
        section_hints=section_hints,
    )
    raw_payload = RawFulltextPayload(
        provider="springer",
        source_url=fixture.source_url,
        content_type="text/html",
        body=html_text.encode("utf-8"),
        content=ProviderContent(
            route_kind="html",
            source_url=fixture.source_url,
            content_type="text/html",
            body=html_text.encode("utf-8"),
            markdown_text=extraction_payload["markdown_text"],
            merged_metadata=merged_metadata,
            diagnostics={
                "availability_diagnostics": diagnostics.to_dict(),
                "extraction": {
                    "abstract_text": normalize_text(abstract_sections[0]["text"]) if abstract_sections else None,
                    "abstract_sections": abstract_sections,
                    "section_hints": section_hints,
                    "extracted_authors": list(extraction_payload.get("extracted_authors") or []),
                },
            },
        ),
        trace=trace_from_markers(["fulltext:springer_html_ok"]),
        merged_metadata=merged_metadata,
    )
    client = springer_provider.SpringerClient(HttpTransport(), {})
    return client.to_article_model(merged_metadata, raw_payload)


def _build_browser_workflow_article(fixture: GoldenCorpusFixture):
    metadata = _base_metadata(fixture)
    html_text = fixture.raw_path.read_text(encoding="utf-8", errors="ignore")
    client_map = {
        "science": science_provider.ScienceClient,
        "pnas": pnas_provider.PnasClient,
        "wiley": wiley_provider.WileyClient,
    }
    client = client_map[fixture.provider](HttpTransport(), {})
    markdown_text, extraction = client.extract_markdown(
        html_text,
        fixture.source_url,
        metadata=metadata,
    )
    raw_payload = RawFulltextPayload(
        provider=fixture.provider,
        source_url=fixture.source_url,
        content_type="text/html",
        body=html_text.encode("utf-8"),
        content=ProviderContent(
            route_kind="html",
            source_url=fixture.source_url,
            content_type="text/html",
            body=html_text.encode("utf-8"),
            markdown_text=markdown_text,
            diagnostics={
                "extraction": extraction,
                "availability_diagnostics": extraction.get("availability_diagnostics"),
            },
        ),
        trace=trace_from_markers([f"fulltext:{fixture.provider}_html_ok"]),
        merged_metadata=metadata,
    )
    return client.to_article_model(metadata, raw_payload)


def build_article_from_fixture(fixture: GoldenCorpusFixture):
    if fixture.provider == "elsevier":
        return _build_elsevier_article(fixture)
    if fixture.provider == "springer":
        return _build_springer_article(fixture)
    if fixture.provider in {"science", "pnas", "wiley"}:
        return _build_browser_workflow_article(fixture)
    raise ValueError(f"Unsupported golden fixture provider: {fixture.provider}")


def lightweight_positive_summary_from_fixture(fixture: GoldenCorpusFixture) -> dict[str, Any]:
    if fixture.provider == "elsevier":
        article = _build_elsevier_article(fixture)
        abstract_sections = [section for section in article.sections if section.kind == "abstract"]
        body_sections = [section for section in article.sections if section.kind == "body"]
        return {
            "doi": normalize_doi(str(article.doi or fixture.doi)),
            "has": {
                "title": bool(normalize_text(article.metadata.title)),
                "authors": bool(article.metadata.authors),
                "abstract": bool(normalize_text(article.metadata.abstract)) or bool(abstract_sections),
                "body": bool(body_sections),
            },
            "validated_fields": ("title", "authors", "abstract", "body"),
            "blocking_fallback_signals": (),
            "source_candidate_hit": True,
        }

    if fixture.provider == "springer":
        html_text = fixture.raw_path.read_text(encoding="utf-8", errors="ignore")
        metadata = _springer_html.parse_html_metadata(html_text, fixture.source_url)
        extraction_payload = _springer_html.extract_html_payload(
            html_text,
            fixture.source_url,
            title=str(metadata.get("title") or fixture.title),
        )
        return {
            "doi": normalize_doi(str(metadata.get("doi") or fixture.doi)),
            "has": {
                "title": bool(normalize_text(metadata.get("title"))),
                "authors": bool(extraction_payload["extracted_authors"]),
                "abstract": bool(normalize_text(metadata.get("abstract"))) or bool(extraction_payload["abstract_sections"]),
                "body": bool(extraction_payload["section_hints"]),
            },
            "validated_fields": ("title", "authors", "abstract", "body"),
            "blocking_fallback_signals": (),
            "source_candidate_hit": True,
        }

    if fixture.provider in {"science", "pnas", "wiley"}:
        html_text = fixture.raw_path.read_text(encoding="utf-8", errors="ignore")
        metadata = parse_html_metadata(html_text, fixture.source_url)
        browser_helpers = {
            "science": (
                _science_html.extract_authors,
                _science_html.blocking_fallback_signals,
            ),
            "pnas": (
                _pnas_html.extract_authors,
                _pnas_html.blocking_fallback_signals,
            ),
            "wiley": (
                _wiley_html.extract_authors,
                _wiley_html.blocking_fallback_signals,
            ),
        }
        extract_authors, blocking_fallback_signals = browser_helpers[fixture.provider]
        candidate_urls = _science_pnas_profiles.build_html_candidates(
            fixture.provider,
            fixture.doi,
            fixture.landing_url,
        )
        return {
            "doi": normalize_doi(str(metadata.get("doi") or fixture.doi)),
            "has": {
                "title": bool(normalize_text(metadata.get("title"))),
                "authors": bool(extract_authors(html_text)),
            },
            "validated_fields": ("title", "authors"),
            "blocking_fallback_signals": tuple(blocking_fallback_signals(html_text)),
            "source_candidate_hit": fixture.source_url in candidate_urls or fixture.landing_url in candidate_urls,
        }

    raise ValueError(f"Unsupported golden fixture provider: {fixture.provider}")


def expected_summary_from_article(article) -> dict[str, Any]:
    abstract_sections = [section for section in article.sections if section.kind == "abstract"]
    body_sections = [section for section in article.sections if section.kind == "body"]
    data_sections = [section for section in article.sections if section.kind == "data_availability"]
    code_sections = [section for section in article.sections if section.kind == "code_availability"]
    figure_assets = [asset for asset in article.assets if getattr(asset, "kind", "") == "figure"]
    table_assets = [asset for asset in article.assets if getattr(asset, "kind", "") == "table"]
    return {
        "has": {
            "title": bool(normalize_text(article.metadata.title)),
            "authors": bool(article.metadata.authors),
            "abstract": bool(normalize_text(article.metadata.abstract)) or bool(abstract_sections),
            "body": bool(body_sections),
            "figures": bool(figure_assets),
            "references": bool(article.references),
            "data_availability": bool(data_sections),
            "code_availability": bool(code_sections),
        },
        "counts": {
            "sections": len(article.sections),
            "abstract_sections": len(abstract_sections),
            "body_sections": len(body_sections),
            "figures": len(figure_assets),
            "tables": len(table_assets),
            "references": len(article.references),
        },
        "expected_content_kind": article.quality.content_kind,
    }
