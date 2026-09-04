"""Helpers for the offline golden fulltext corpus."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import tempfile
from typing import Any

from bs4 import BeautifulSoup

from paper_fetch.extraction.html.parsing import choose_parser
from paper_fetch.extraction.html.semantics import collect_html_section_hints
from paper_fetch.extraction.html._metadata import (
    merge_html_metadata,
    parse_html_metadata,
)
from paper_fetch.extraction.html.assets import merge_extracted_and_downloaded_assets
from paper_fetch.http import HttpTransport
from paper_fetch.models import article_from_markdown
from paper_fetch.publisher_identity import normalize_doi
from paper_fetch.providers import (
    _acs_html,
    _aip_html,
    _tandf_html,
    _pnas_html,
    _science_html,
    _ams_authors,
    _ams_references,
    _annualreviews_html,
    _atypon_browser_workflow_profiles as atypon_browser_workflow_profiles,
    _arxiv_html,
    _ieee_html,
    _ieee_metadata,
    _iop_html,
    _mdpi_authors,
    _mdpi_dom,
    _oxfordacademic_html,
    _royalsocietypublishing_html,
    _wiley_html,
    copernicus as copernicus_provider,
    elsevier as elsevier_provider,
    frontiers as frontiers_provider,
    arxiv as arxiv_provider,
    acs as acs_provider,
    aip as aip_provider,
    tandf as tandf_provider,
    pnas as pnas_provider,
    science as science_provider,
    ams as ams_provider,
    annualreviews as annualreviews_provider,
    iop as iop_provider,
    mdpi as mdpi_provider,
    plos as plos_provider,
    royalsocietypublishing as royalsocietypublishing_provider,
    springer as springer_provider,
    _springer_html as springer_html,
    wiley as wiley_provider,
)
from paper_fetch.providers._article_markdown_jats import parse_jats_xml
from paper_fetch.providers.browser_workflow.asset_download import (
    plan_browser_asset_download,
)
from paper_fetch.providers.ieee import IeeeClient
from paper_fetch.quality.html_availability import assess_html_fulltext_availability
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers._pdf_common import pdf_fetch_result_from_bytes
from paper_fetch.runtime import RuntimeContext
from paper_fetch.tracing import trace_from_markers
from paper_fetch.utils import normalize_text
from tests.golden_corpus_adapters import (
    GoldenCorpusAdapter,
    ProviderGoldenContract,
    golden_corpus_adapter,
    register_golden_corpus_adapter,
)
from tests.golden_criteria import (
    golden_criteria_asset,
    golden_criteria_repo_path,
    golden_criteria_sample_for_doi,
    iter_manifest_samples,
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
        return str(
            self.sample.get("source_url") or self.sample.get("landing_url") or ""
        )

    @property
    def landing_url(self) -> str:
        return str(
            self.sample.get("landing_url") or self.sample.get("source_url") or ""
        )

    @property
    def route_kind(self) -> str:
        return str(self.sample.get("route_kind") or "")

    @property
    def content_type(self) -> str:
        return str(self.sample.get("content_type") or "")

    @property
    def raw_path(self) -> Path:
        pdf_path = golden_criteria_asset(self.doi, "original.pdf")
        if self.route_kind == "pdf_fallback" and pdf_path.exists():
            return pdf_path
        html_path = golden_criteria_asset(self.doi, "original.html")
        if html_path.exists():
            return html_path
        xml_path = golden_criteria_asset(self.doi, "original.xml")
        if xml_path.exists():
            return xml_path
        article_path = golden_criteria_asset(self.doi, "article.html")
        if article_path.exists():
            return article_path
        if pdf_path.exists():
            return pdf_path
        raise FileNotFoundError(
            f"Golden fixture is missing canonical original.html/original.xml/original.pdf/article.html: {self.doi}"
        )

    @property
    def expected_path(self) -> Path:
        return golden_criteria_asset(self.doi, "expected.json")

    def load_expected(self) -> dict[str, Any]:
        return json.loads(self.expected_path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class GoldenCorpusReplayRecord:
    """Classify one manifest claim without promoting declarations to replay."""

    sample_id: str
    provider: str
    route_kind: str
    category: str
    reason: str
    fixture: GoldenCorpusFixture | None = None


@dataclass(frozen=True)
class GoldenCorpusReplayInventory:
    records: tuple[GoldenCorpusReplayRecord, ...]

    @property
    def replay_fixtures(self) -> tuple[GoldenCorpusFixture, ...]:
        return tuple(
            record.fixture
            for record in self.records
            if record.category == "real_replay" and record.fixture is not None
        )

    def count(self, category: str) -> int:
        return sum(record.category == category for record in self.records)


def iter_golden_corpus_fixtures() -> tuple[GoldenCorpusFixture, ...]:
    """Return only real, canonical, contracted and locally executable replays."""

    return golden_corpus_replay_inventory().replay_fixtures


def _has_replay_asset(sample: dict[str, Any]) -> bool:
    assets = sample.get("assets") if isinstance(sample.get("assets"), dict) else {}
    return any(
        name in assets
        for name in ("original.html", "original.xml", "original.pdf", "article.html")
    )


def _expected_contract_is_valid(expected: object) -> bool:
    if not isinstance(expected, dict):
        return False
    return (
        isinstance(expected.get("has"), dict)
        and isinstance(expected.get("counts"), dict)
        and expected.get("expected_content_kind") == "fulltext"
    )


def golden_corpus_fixture_for_doi(doi: str) -> GoldenCorpusFixture:
    sample = golden_criteria_sample_for_doi(doi)
    if "expected.json" not in sample.get("assets", {}) or not _has_replay_asset(sample):
        raise FileNotFoundError(
            f"Golden corpus fixture is missing expected.json: {doi}"
        )
    return GoldenCorpusFixture(sample_id=str(sample["sample_id"]), sample=sample)


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
        content=ProviderContent(
            route_kind="xml",
            source_url=fixture.source_url,
            content_type=fixture.content_type or "text/xml",
            body=fixture.raw_path.read_bytes(),
            merged_metadata=metadata,
        ),
        trace=trace_from_markers(["fulltext:elsevier_xml_ok"]),
    )
    client = elsevier_provider.ElsevierClient(HttpTransport(), {})
    return client.to_article_model(metadata, raw_payload)


def _build_springer_article(fixture: GoldenCorpusFixture):
    metadata = _base_metadata(fixture)
    html_text = fixture.raw_path.read_text(encoding="utf-8", errors="ignore")
    html_metadata = springer_html.parse_html_metadata(html_text, fixture.source_url)
    merged_metadata = springer_html.merge_html_metadata(metadata, html_metadata)
    if not merged_metadata.get("doi"):
        merged_metadata["doi"] = fixture.doi
    extraction_payload = springer_html.extract_html_payload(
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
                    "abstract_text": normalize_text(abstract_sections[0]["text"])
                    if abstract_sections
                    else None,
                    "abstract_sections": abstract_sections,
                    "section_hints": section_hints,
                    "extracted_authors": list(
                        extraction_payload.get("extracted_authors") or []
                    ),
                },
            },
        ),
        trace=trace_from_markers(["fulltext:springer_html_ok"]),
    )
    client = springer_provider.SpringerClient(HttpTransport(), {})
    return client.to_article_model(merged_metadata, raw_payload)


def _build_browser_workflow_article(fixture: GoldenCorpusFixture):
    metadata = _base_metadata(fixture)
    client_map = {
        "acs": acs_provider.AcsClient,
        "aip": aip_provider.AipClient,
        "tandf": tandf_provider.TandfClient,
        "ams": ams_provider.AmsClient,
        "annualreviews": annualreviews_provider.AnnualreviewsClient,
        "iop": iop_provider.IopClient,
        "mdpi": mdpi_provider.MdpiClient,
        "science": science_provider.ScienceClient,
        "pnas": pnas_provider.PnasClient,
        "wiley": wiley_provider.WileyClient,
    }
    client = client_map[fixture.provider](HttpTransport(), {})
    if fixture.route_kind == "pdf_fallback":
        body = fixture.raw_path.read_bytes()
        landing_path = golden_criteria_asset(fixture.doi, "landing.html")
        if landing_path.exists():
            landing_metadata = parse_html_metadata(
                landing_path.read_text(encoding="utf-8", errors="ignore"),
                fixture.landing_url,
            )
            metadata = merge_html_metadata(metadata, landing_metadata)
        if not metadata.get("doi"):
            metadata["doi"] = fixture.doi
        pdf_result = pdf_fetch_result_from_bytes(
            artifact_dir=None,
            source_url=fixture.source_url,
            final_url=fixture.source_url,
            pdf_bytes=body,
        )
        raw_payload = RawFulltextPayload(
            provider=fixture.provider,
            content=ProviderContent(
                route_kind="pdf_fallback",
                source_url=fixture.source_url,
                content_type=fixture.content_type or "application/pdf",
                body=body,
                markdown_text=pdf_result.markdown_text,
                merged_metadata=metadata,
                diagnostics={"pdf_fallback": {"fixture": "golden_corpus"}},
                reason=f"Loaded {fixture.provider} PDF fallback golden fixture.",
            ),
            trace=trace_from_markers(
                [
                    f"fulltext:{fixture.provider}_html_fail",
                    f"fulltext:{fixture.provider}_pdf_fallback_ok",
                ]
            ),
            warnings=[
                f"Full text was extracted from {fixture.provider} PDF fallback after the HTML path was not usable.",
            ],
        )
        return client.to_article_model(metadata, raw_payload)

    html_text = fixture.raw_path.read_text(encoding="utf-8", errors="ignore")
    markdown_text, extraction = client.extract_markdown(
        html_text,
        fixture.source_url,
        metadata=metadata,
    )
    downloaded_assets = (
        _downloaded_annualreviews_body_assets(
            fixture, list(extraction.get("extracted_assets") or [])
        )
        if fixture.provider == "annualreviews"
        else []
    )
    if fixture.provider == "aip":
        downloaded_assets = _downloaded_aip_body_assets(
            fixture,
            client,
            html_text,
            fixture.source_url,
        )
    raw_payload = RawFulltextPayload(
        provider=fixture.provider,
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
            merged_metadata=metadata,
            extracted_assets=list(extraction.get("extracted_assets") or []),
        ),
        trace=trace_from_markers([f"fulltext:{fixture.provider}_html_ok"]),
    )
    return client.to_article_model(
        metadata, raw_payload, downloaded_assets=downloaded_assets
    )


def _downloaded_aip_body_assets(
    fixture: GoldenCorpusFixture,
    client: Any,
    html_text: str,
    source_url: str,
) -> list[dict[str, Any]]:
    downloaded: list[dict[str, Any]] = []
    assets_dir = golden_criteria_asset(fixture.doi, "body_assets")
    if not assets_dir.is_dir():
        return downloaded
    local_asset_paths = sorted(assets_dir.glob("m_*.jpeg"))
    if not local_asset_paths:
        return downloaded
    plan = plan_browser_asset_download(
        article_id=fixture.doi,
        output_dir=assets_dir,
        html_text=html_text,
        source_url=source_url,
        profile={
            "client": client,
            "context": RuntimeContext(env={}),
            "asset_profile": "body",
        },
        deps=client.deps,
    )
    figure_index = 0
    for item in plan.body_assets:
        if str(item.get("kind") or "").lower() != "figure":
            continue
        if str(item.get("section") or "body").lower() not in {"", "body"}:
            continue
        asset_url = str(
            item.get("full_size_url")
            or item.get("url")
            or item.get("preview_url")
            or ""
        )
        if not asset_url:
            continue
        figure_index += 1
        if figure_index > len(local_asset_paths):
            break
        asset_path = local_asset_paths[figure_index - 1]
        downloaded_asset = dict(item)
        downloaded_asset.update(
            {
                "path": golden_criteria_repo_path(asset_path),
                "download_url": asset_url,
                "source_url": asset_url,
                "content_type": "image/jpeg",
                "download_tier": "full_size",
                "downloaded_bytes": asset_path.stat().st_size,
            }
        )
        downloaded.append(downloaded_asset)
    return downloaded


def _downloaded_annualreviews_body_assets(
    fixture: GoldenCorpusFixture,
    extracted_assets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    downloaded: list[dict[str, Any]] = []
    assets_dir = golden_criteria_asset(fixture.doi, "body_assets")
    if not assets_dir.is_dir():
        return downloaded
    local_asset_paths = sorted(assets_dir.glob("annualreviews-figure-*"))
    if not local_asset_paths:
        return downloaded
    figure_index = 0
    for item in extracted_assets:
        if str(item.get("kind") or "").lower() != "figure":
            continue
        if str(item.get("section") or "body").lower() not in {"", "body"}:
            continue
        asset_url = str(
            item.get("full_size_url")
            or item.get("url")
            or item.get("preview_url")
            or ""
        )
        if not asset_url:
            continue
        figure_index += 1
        if figure_index > len(local_asset_paths):
            break
        asset_path = local_asset_paths[figure_index - 1]
        downloaded_asset = dict(item)
        downloaded_asset.update(
            {
                "path": golden_criteria_repo_path(asset_path),
                "download_url": asset_url,
                "source_url": asset_url,
                "content_type": "image/gif"
                if asset_path.suffix.lower() == ".gif"
                else "image/png",
                "download_tier": "full_size",
                "downloaded_bytes": asset_path.stat().st_size,
            }
        )
        downloaded.append(downloaded_asset)
    return downloaded


def _ieee_fixture_metadata(fixture: GoldenCorpusFixture) -> dict[str, Any]:
    article_number = str(fixture.sample.get("article_number") or "")
    landing_metadata = _ieee_metadata._parse_landing_metadata(
        golden_criteria_asset(fixture.doi, "landing.html").read_text(
            encoding="utf-8", errors="ignore"
        )
    )
    metadata = _ieee_metadata._merge_ieee_metadata(
        _base_metadata(fixture),
        landing_metadata,
        fixture.landing_url,
    )
    references_path = golden_criteria_asset(fixture.doi, "references.json")
    if references_path.exists():
        references_payload = json.loads(references_path.read_text(encoding="utf-8"))
        references = _ieee_metadata._references_from_ieee_reference_payload(
            references_payload
        )
        if references:
            metadata["references"] = references
    if not metadata.get("doi"):
        metadata["doi"] = fixture.doi
    if article_number:
        metadata["article_number"] = article_number
        metadata["articleNumber"] = article_number
    return metadata


def _ieee_downloaded_body_assets(
    extracted_assets: list[dict[str, Any]],
    tmpdir: Path,
) -> list[dict[str, Any]]:
    downloaded_assets: list[dict[str, Any]] = []
    for index, item in enumerate(extracted_assets, start=1):
        if item.get("kind") not in {"figure", "table"} or item.get("section") != "body":
            continue
        asset_url = (
            item.get("url") or item.get("full_size_url") or item.get("preview_url")
        )
        if not asset_url:
            continue
        path = tmpdir / f"ieee-asset-{index}.gif"
        path.write_bytes(b"GIF89a\x01\x00\x01\x00\x00\x00;")
        downloaded = dict(item)
        downloaded.update(
            {
                "path": str(path),
                "download_url": asset_url,
                "source_url": asset_url,
                "content_type": "image/gif",
                "download_tier": "full_size",
            }
        )
        downloaded_assets.append(downloaded)
    return downloaded_assets


def _build_ieee_article(fixture: GoldenCorpusFixture):
    metadata = _ieee_fixture_metadata(fixture)
    html_text = fixture.raw_path.read_text(encoding="utf-8", errors="ignore")
    extraction = _ieee_html._extract_ieee_html(
        html_text,
        fixture.source_url,
        metadata=metadata,
    )
    body = extraction.html_text.encode("utf-8")
    raw_payload = RawFulltextPayload(
        provider="ieee",
        content=ProviderContent(
            route_kind="html",
            source_url=fixture.source_url,
            content_type=fixture.content_type or "text/html",
            body=body,
            markdown_text=extraction.markdown_text,
            merged_metadata=metadata,
            diagnostics={
                "extraction": {
                    "abstract_sections": extraction.abstract_sections,
                    "section_hints": extraction.section_hints,
                    "marker_counts": extraction.marker_counts,
                }
            },
            reason="Loaded IEEE real HTML fixture.",
            extracted_assets=extraction.extracted_assets,
        ),
        trace=trace_from_markers(["fulltext:ieee_html_ok"]),
    )
    client = IeeeClient(HttpTransport(), {})
    with tempfile.TemporaryDirectory() as tmpdir:
        downloaded_assets = _ieee_downloaded_body_assets(
            extraction.extracted_assets, Path(tmpdir)
        )
        return client.to_article_model(
            {"doi": fixture.doi}, raw_payload, downloaded_assets=downloaded_assets
        )


def _build_oxfordacademic_article(fixture: GoldenCorpusFixture):
    base_metadata = _base_metadata(fixture)
    if normalize_text(str(base_metadata.get("title") or "")) == fixture.doi:
        base_metadata.pop("title", None)
    if fixture.route_kind == "pdf_fallback":
        body = fixture.raw_path.read_bytes()
        if not base_metadata.get("doi"):
            base_metadata["doi"] = fixture.doi
        pdf_result = pdf_fetch_result_from_bytes(
            artifact_dir=None,
            source_url=fixture.source_url,
            final_url=fixture.source_url,
            pdf_bytes=body,
        )
        return article_from_markdown(
            source="oxfordacademic_pdf",
            metadata=base_metadata,
            doi=fixture.doi,
            markdown_text=pdf_result.markdown_text,
            trace=trace_from_markers(
                [
                    "fulltext:oxfordacademic_html_fail",
                    "fulltext:oxfordacademic_pdf_fallback_ok",
                ]
            ),
            warnings=[
                "Full text was extracted from Oxford Academic PDF fallback after the HTML route was not usable.",
            ],
        )

    html_text = fixture.raw_path.read_text(encoding="utf-8", errors="ignore")
    metadata = _oxfordacademic_html.merge_metadata_with_html(
        base_metadata,
        html_text,
        fixture.source_url,
        doi=fixture.doi,
    )
    extraction = _oxfordacademic_html.extract_markdown(
        html_text,
        fixture.source_url,
        metadata=metadata,
    )
    return article_from_markdown(
        source="oxfordacademic_html",
        metadata=extraction.metadata,
        doi=fixture.doi,
        markdown_text=extraction.markdown_text,
        abstract_sections=[],
        section_hints=extraction.section_hints,
        assets=extraction.extracted_assets,
        trace=trace_from_markers(["fulltext:oxfordacademic_html_ok"]),
    )


def _build_copernicus_article(fixture: GoldenCorpusFixture):
    metadata = _base_metadata(fixture)
    body = fixture.raw_path.read_bytes()
    landing_path = golden_criteria_asset(fixture.doi, "landing.html")
    if landing_path.exists():
        landing_metadata = parse_html_metadata(
            landing_path.read_text(encoding="utf-8", errors="ignore"),
            fixture.landing_url,
        )
        metadata = merge_html_metadata(metadata, landing_metadata)
        if not metadata.get("doi"):
            metadata["doi"] = fixture.doi
        if not metadata.get("landing_page_url"):
            metadata["landing_page_url"] = fixture.landing_url
    if fixture.route_kind == "pdf_fallback":
        pdf_result = pdf_fetch_result_from_bytes(
            artifact_dir=None,
            source_url=fixture.source_url,
            final_url=fixture.source_url,
            pdf_bytes=body,
        )
        raw_payload = RawFulltextPayload(
            provider="copernicus",
            content=ProviderContent(
                route_kind="pdf_fallback",
                source_url=fixture.source_url,
                content_type=fixture.content_type or "application/pdf",
                body=body,
                markdown_text=pdf_result.markdown_text,
                merged_metadata=metadata,
                diagnostics={"pdf_fallback": {"fixture": "golden_corpus"}},
                reason="Loaded Copernicus PDF fallback golden fixture.",
            ),
            trace=trace_from_markers(
                ["fulltext:copernicus_xml_fail", "fulltext:copernicus_pdf_fallback_ok"]
            ),
            warnings=[
                "Full text was extracted from Copernicus PDF fallback after the XML route was not usable.",
            ],
        )
        client = copernicus_provider.CopernicusClient(HttpTransport(), {})
        return client.to_article_model(metadata, raw_payload)
    extraction = copernicus_provider.parse_copernicus_xml(
        body,
        source_url=fixture.source_url,
        base_metadata=metadata,
    )
    metadata = dict(extraction.metadata)
    raw_payload = RawFulltextPayload(
        provider="copernicus",
        content=ProviderContent(
            route_kind="xml",
            source_url=fixture.source_url,
            content_type=fixture.content_type or "application/xml",
            body=body,
            markdown_text=extraction.markdown_text,
            merged_metadata=metadata,
            diagnostics={
                "extraction": {
                    "fixture": "golden_corpus",
                    "abstract_sections": extraction.abstract_sections,
                    "references": extraction.references,
                    "semantic_losses": extraction.semantic_losses,
                }
            },
            extracted_assets=extraction.assets,
        ),
        trace=trace_from_markers(["fulltext:copernicus_xml_ok"]),
    )
    client = copernicus_provider.CopernicusClient(HttpTransport(), {})
    return client.to_article_model(metadata, raw_payload)


def _build_royalsocietypublishing_article(fixture: GoldenCorpusFixture):
    metadata = _base_metadata(fixture)
    client = royalsocietypublishing_provider.RoyalsocietypublishingClient(
        HttpTransport(), {}
    )
    if fixture.route_kind == "pdf_fallback":
        body = fixture.raw_path.read_bytes()
        if not metadata.get("doi"):
            metadata["doi"] = fixture.doi
        pdf_result = pdf_fetch_result_from_bytes(
            artifact_dir=None,
            source_url=fixture.source_url,
            final_url=fixture.source_url,
            pdf_bytes=body,
        )
        raw_payload = RawFulltextPayload(
            provider="royalsocietypublishing",
            content=ProviderContent(
                route_kind="pdf_fallback",
                source_url=fixture.source_url,
                content_type=fixture.content_type or "application/pdf",
                body=body,
                markdown_text=pdf_result.markdown_text,
                merged_metadata=metadata,
                diagnostics={"pdf_fallback": {"fixture": "golden_corpus"}},
                reason="Loaded Royal Society Publishing PDF fallback golden fixture.",
            ),
            trace=trace_from_markers(
                [
                    "fulltext:royalsocietypublishing_html_fail",
                    "fulltext:royalsocietypublishing_pdf_fallback_ok",
                ]
            ),
            warnings=[
                "Full text was extracted from Royal Society Publishing PDF fallback after the HTML route was not usable.",
            ],
        )
        return client.to_article_model(metadata, raw_payload)

    html_text = fixture.raw_path.read_text(encoding="utf-8", errors="ignore")
    extraction = _royalsocietypublishing_html.extract_markdown(
        html_text,
        fixture.source_url,
        metadata=metadata,
        asset_profile="all",
    )
    raw_payload = RawFulltextPayload(
        provider="royalsocietypublishing",
        content=ProviderContent(
            route_kind="html",
            source_url=fixture.source_url,
            content_type=fixture.content_type or "text/html",
            body=extraction.html_text.encode("utf-8"),
            markdown_text=extraction.markdown_text,
            merged_metadata=extraction.metadata,
            diagnostics={
                "extraction": {
                    "metadata": extraction.metadata,
                    "abstract_sections": extraction.abstract_sections,
                    "section_hints": extraction.section_hints,
                    "references": extraction.metadata.get("references", []),
                    "extracted_assets": extraction.extracted_assets,
                }
            },
            reason="Loaded Royal Society Publishing real HTML fixture.",
            extracted_assets=extraction.extracted_assets,
        ),
        trace=trace_from_markers(["fulltext:royalsocietypublishing_html_ok"]),
    )
    return client.to_article_model(
        extraction.metadata,
        raw_payload,
        downloaded_assets=extraction.extracted_assets,
    )


def _build_plos_article(fixture: GoldenCorpusFixture):
    metadata = _base_metadata(fixture)
    body = fixture.raw_path.read_bytes()
    if fixture.route_kind == "pdf_fallback":
        pdf_result = pdf_fetch_result_from_bytes(
            artifact_dir=None,
            source_url=fixture.source_url,
            final_url=fixture.source_url,
            pdf_bytes=body,
        )
        return article_from_markdown(
            source="plos_pdf",
            metadata=metadata,
            doi=fixture.doi,
            markdown_text=pdf_result.markdown_text,
            trace=trace_from_markers(
                ["fulltext:plos_xml_fail", "fulltext:plos_pdf_fallback_ok"]
            ),
            warnings=[
                "Full text was extracted from PLOS PDF fallback after the XML route was not used.",
            ],
        )

    extraction = parse_jats_xml(
        body,
        source_url=fixture.source_url,
        base_metadata=metadata,
    )
    if extraction is None:
        raise ValueError(f"PLOS fixture is not parseable JATS XML: {fixture.doi}")
    article_metadata = dict(extraction.metadata)
    if extraction.references:
        article_metadata["references"] = list(extraction.references)
    downloaded_assets = _downloaded_plos_body_assets(fixture, list(extraction.assets))
    assets = (
        merge_extracted_and_downloaded_assets(extraction.assets, downloaded_assets)
        if downloaded_assets
        else extraction.assets
    )
    return article_from_markdown(
        source="plos_xml",
        metadata=article_metadata,
        doi=normalize_doi(str(article_metadata.get("doi") or fixture.doi)),
        markdown_text=extraction.markdown_text,
        abstract_sections=extraction.abstract_sections,
        assets=assets,
        trace=trace_from_markers(["fulltext:plos_xml_ok"]),
        semantic_losses=extraction.semantic_losses,
    )


def _build_frontiers_article(fixture: GoldenCorpusFixture):
    metadata = _base_metadata(fixture)
    body = fixture.raw_path.read_bytes()
    if fixture.route_kind == "pdf_fallback":
        pdf_result = pdf_fetch_result_from_bytes(
            artifact_dir=None,
            source_url=fixture.source_url,
            final_url=fixture.source_url,
            pdf_bytes=body,
        )
        return article_from_markdown(
            source="frontiers_pdf",
            metadata=metadata,
            doi=fixture.doi,
            markdown_text=pdf_result.markdown_text,
            trace=trace_from_markers(
                [
                    "fulltext:frontiers_xml_fail",
                    "fulltext:frontiers_pdf_fallback_ok",
                ]
            ),
            warnings=[
                "Full text was extracted from Frontiers PDF fallback after the XML route was not used.",
            ],
        )

    extraction = parse_jats_xml(
        body,
        source_url=fixture.source_url,
        base_metadata=metadata,
    )
    if extraction is None:
        raise ValueError(f"Frontiers fixture is not parseable JATS XML: {fixture.doi}")
    article_metadata = dict(extraction.metadata)
    article_metadata.setdefault("landing_page_url", fixture.landing_url)
    normalized_assets, replacements = (
        frontiers_provider._normalize_frontiers_extracted_assets(
            extraction.assets,
            doi=fixture.doi,
            landing_url=fixture.landing_url,
        )
    )
    raw_payload = RawFulltextPayload(
        provider="frontiers",
        content=ProviderContent(
            route_kind="xml",
            source_url=fixture.source_url,
            content_type=fixture.content_type or "text/xml",
            body=body,
            markdown_text=frontiers_provider._replace_markdown_urls(
                extraction.markdown_text,
                replacements,
            ),
            merged_metadata=article_metadata,
            diagnostics={
                "extraction": {
                    "abstract_sections": extraction.abstract_sections,
                    "references": extraction.references,
                    "semantic_losses": asdict(extraction.semantic_losses),
                }
            },
            extracted_assets=normalized_assets,
        ),
        trace=trace_from_markers(["fulltext:frontiers_xml_ok"]),
    )
    return frontiers_provider.FrontiersClient(HttpTransport(), {}).to_article_model(
        article_metadata,
        raw_payload,
    )


def _downloaded_plos_body_assets(
    fixture: GoldenCorpusFixture,
    extracted_assets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    downloaded: list[dict[str, Any]] = []
    assets_dir = golden_criteria_asset(fixture.doi, "body_assets")
    if not assets_dir.is_dir():
        return downloaded
    local_asset_paths = sorted(assets_dir.glob("*.png"))
    if not local_asset_paths:
        return downloaded
    local_assets_by_stem = {path.stem.lower(): path for path in local_asset_paths}
    for item in extracted_assets:
        kind = str(item.get("kind") or "").lower()
        if kind not in {"figure", "formula"}:
            continue
        if str(item.get("section") or "body").lower() not in {"", "body"}:
            continue
        asset_id = plos_provider._doi_asset_id(
            str(item.get("link") or item.get("original_url") or item.get("url") or "")
        )
        if not asset_id:
            continue
        asset_stem = asset_id.split("journal.", 1)[-1].lower()
        asset_path = local_assets_by_stem.get(asset_stem)
        if asset_path is None:
            continue
        downloaded_asset = dict(item)
        image_url = (
            plos_provider._plos_formula_image_url(asset_id)
            if kind == "formula"
            else plos_provider._plos_figure_image_url(asset_id)
        )
        downloaded_asset.update(
            {
                "path": golden_criteria_repo_path(asset_path),
                "download_url": image_url,
                "source_url": image_url,
                "content_type": "image/png",
                "download_tier": "full_size",
                "downloaded_bytes": asset_path.stat().st_size,
            }
        )
        downloaded.append(downloaded_asset)
    return downloaded


def _load_arxiv_fixture_metadata(fixture: GoldenCorpusFixture) -> dict[str, Any]:
    api_path = golden_criteria_asset(fixture.doi, "api.json")
    payload = json.loads(api_path.read_text(encoding="utf-8"))
    metadata = payload.get("provider_metadata") if isinstance(payload, dict) else None
    if not isinstance(metadata, dict):
        return _base_metadata(fixture)
    return dict(metadata)


def _build_arxiv_article(fixture: GoldenCorpusFixture):
    metadata = _load_arxiv_fixture_metadata(fixture)
    client = arxiv_provider.ArxivClient(HttpTransport(), {})
    if fixture.route_kind == "pdf_fallback":
        body = fixture.raw_path.read_bytes()
        pdf_result = pdf_fetch_result_from_bytes(
            artifact_dir=None,
            source_url=fixture.source_url,
            final_url=fixture.source_url,
            pdf_bytes=body,
        )
        raw_payload = RawFulltextPayload(
            provider="arxiv",
            content=ProviderContent(
                route_kind="pdf_fallback",
                source_url=fixture.source_url,
                content_type=fixture.content_type or "application/pdf",
                body=body,
                markdown_text=pdf_result.markdown_text,
                merged_metadata=metadata,
                diagnostics={"pdf_fallback": {"fixture": "golden_corpus"}},
                reason="Loaded arXiv PDF fallback golden fixture.",
            ),
            trace=trace_from_markers(
                [
                    "fulltext:arxiv_html_fail",
                    "fulltext:arxiv_pdf_fallback_ok",
                ]
            ),
            warnings=[
                "Full text was extracted from arXiv PDF fallback after the HTML route was not usable.",
            ],
        )
        return client.to_article_model(metadata, raw_payload)

    html_text = fixture.raw_path.read_text(encoding="utf-8", errors="ignore")
    extraction = _arxiv_html._extract_arxiv_html_markdown(
        html_text,
        fixture.source_url,
        metadata=metadata,
    )
    raw_payload = RawFulltextPayload(
        provider="arxiv",
        content=ProviderContent(
            route_kind="html",
            source_url=fixture.source_url,
            content_type=fixture.content_type or "text/html",
            body=html_text.encode("utf-8"),
            markdown_text=extraction.markdown_text,
            merged_metadata=extraction.merged_metadata,
            diagnostics={
                "availability_diagnostics": extraction.diagnostics,
                "extraction": extraction.diagnostics.get("extraction"),
                "semantic_losses": extraction.diagnostics.get("semantic_losses"),
            },
            reason="Loaded arXiv official HTML golden fixture.",
            extracted_assets=extraction.extracted_assets,
        ),
        trace=trace_from_markers(["fulltext:arxiv_html_ok"]),
        warnings=extraction.warnings,
    )
    return client.to_article_model(extraction.merged_metadata, raw_payload)


def _lightweight_arxiv_summary(fixture: GoldenCorpusFixture) -> dict[str, Any]:
    return _article_model_positive_summary(_build_arxiv_article(fixture), fixture)


def _article_model_positive_summary(
    article, fixture: GoldenCorpusFixture
) -> dict[str, Any]:
    abstract_sections = [
        section for section in article.sections if section.kind == "abstract"
    ]
    body_sections = [section for section in article.sections if section.kind == "body"]
    return {
        "doi": normalize_doi(str(article.doi or fixture.doi)),
        "has": {
            "title": bool(normalize_text(article.metadata.title)),
            "authors": bool(article.metadata.authors),
            "abstract": bool(normalize_text(article.metadata.abstract))
            or bool(abstract_sections),
            "body": bool(body_sections),
        },
        "validated_fields": ("title", "authors", "abstract", "body"),
        "blocking_fallback_signals": (),
        "source_candidate_hit": True,
    }


def build_article_from_fixture(fixture: GoldenCorpusFixture):
    return golden_corpus_adapter(fixture.provider).build_article(fixture)


def _lightweight_elsevier_summary(fixture: GoldenCorpusFixture) -> dict[str, Any]:
    return _article_model_positive_summary(_build_elsevier_article(fixture), fixture)


def _lightweight_springer_summary(fixture: GoldenCorpusFixture) -> dict[str, Any]:
    html_text = fixture.raw_path.read_text(encoding="utf-8", errors="ignore")
    metadata = springer_html.parse_html_metadata(html_text, fixture.source_url)
    extraction_payload = springer_html.extract_html_payload(
        html_text,
        fixture.source_url,
        title=str(metadata.get("title") or fixture.title),
    )
    return {
        "doi": normalize_doi(str(metadata.get("doi") or fixture.doi)),
        "has": {
            "title": bool(normalize_text(metadata.get("title"))),
            "authors": bool(extraction_payload["extracted_authors"]),
            "abstract": bool(normalize_text(metadata.get("abstract")))
            or bool(extraction_payload["abstract_sections"]),
            "body": bool(extraction_payload["section_hints"]),
        },
        "validated_fields": ("title", "authors", "abstract", "body"),
        "blocking_fallback_signals": (),
        "source_candidate_hit": True,
    }


def _lightweight_atypon_browser_workflow_summary(
    fixture: GoldenCorpusFixture,
) -> dict[str, Any]:
    if fixture.route_kind == "pdf_fallback":
        return _article_model_positive_summary(
            _build_browser_workflow_article(fixture), fixture
        )
    html_text = fixture.raw_path.read_text(encoding="utf-8", errors="ignore")
    metadata = parse_html_metadata(html_text, fixture.source_url)
    browser_helpers = {
        "ams": (
            _ams_authors.extract_authors,
            _ams_references.blocking_fallback_signals,
        ),
        "acs": (
            _acs_html.extract_authors,
            lambda _html_text: (),
        ),
        "aip": (
            _aip_html.extract_authors,
            lambda _html_text: (),
        ),
        "tandf": (
            _tandf_html.extract_authors,
            lambda _html_text: (),
        ),
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
        "iop": (
            _iop_html.extract_authors,
            lambda _html_text: (),
        ),
    }
    extract_authors, blocking_fallback_signals = browser_helpers[fixture.provider]
    candidate_urls = atypon_browser_workflow_profiles.build_html_candidates(
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
        "source_candidate_hit": fixture.source_url in candidate_urls
        or fixture.landing_url in candidate_urls,
    }


def _lightweight_mdpi_summary(fixture: GoldenCorpusFixture) -> dict[str, Any]:
    if fixture.route_kind == "pdf_fallback":
        return _article_model_positive_summary(
            _build_browser_workflow_article(fixture), fixture
        )
    html_text = fixture.raw_path.read_text(encoding="utf-8", errors="ignore")
    metadata = parse_html_metadata(html_text, fixture.source_url)
    article_html, title, abstract_text, _container_text_length = (
        _mdpi_dom._article_container_html(
            html_text,
            metadata,
        )
    )
    article_soup = BeautifulSoup(article_html, choose_parser())
    article = article_soup.find("article")
    section_hints = (
        collect_html_section_hints(article, title=title) if article is not None else []
    )
    client = mdpi_provider.MdpiClient(HttpTransport(), {})
    candidate_urls = client.html_candidates(
        fixture.doi,
        {"landing_page_url": fixture.landing_url},
    )
    return {
        "doi": normalize_doi(str(metadata.get("doi") or fixture.doi)),
        "has": {
            "title": bool(normalize_text(title or metadata.get("title"))),
            "authors": bool(_mdpi_authors.extract_authors(html_text)),
            "abstract": bool(normalize_text(abstract_text)),
            "body": bool(section_hints),
        },
        "validated_fields": ("title", "authors", "abstract", "body"),
        "blocking_fallback_signals": (),
        "source_candidate_hit": fixture.source_url in candidate_urls
        or fixture.landing_url in candidate_urls,
    }


def _lightweight_annualreviews_summary(fixture: GoldenCorpusFixture) -> dict[str, Any]:
    if fixture.route_kind == "pdf_fallback":
        return _article_model_positive_summary(
            _build_browser_workflow_article(fixture), fixture
        )
    html_text = fixture.raw_path.read_text(encoding="utf-8", errors="ignore")
    metadata = parse_html_metadata(html_text, fixture.source_url)
    (
        article_html,
        title,
        _container_text_length,
        section_hints,
        abstract_sections,
        _container_evidence,
    ) = _annualreviews_html._cleaned_article_html(html_text, fixture.source_url)
    client = annualreviews_provider.AnnualreviewsClient(HttpTransport(), {})
    candidate_urls = client.html_candidates(
        fixture.doi,
        {"landing_page_url": fixture.landing_url},
    )
    return {
        "doi": normalize_doi(str(metadata.get("doi") or fixture.doi)),
        "has": {
            "title": bool(normalize_text(title or metadata.get("title"))),
            "authors": bool(_annualreviews_html.extract_authors(html_text)),
            "abstract": bool(abstract_sections),
            "body": bool(section_hints) or bool(normalize_text(article_html)),
        },
        "validated_fields": ("title", "authors", "abstract", "body"),
        "blocking_fallback_signals": tuple(
            _annualreviews_html.blocking_fallback_signals(html_text)
        ),
        "source_candidate_hit": fixture.source_url in candidate_urls
        or fixture.landing_url in candidate_urls,
    }


def _lightweight_ieee_summary(fixture: GoldenCorpusFixture) -> dict[str, Any]:
    metadata = _ieee_fixture_metadata(fixture)
    html_text = fixture.raw_path.read_text(encoding="utf-8", errors="ignore")
    extraction = _ieee_html._extract_ieee_html(
        html_text,
        fixture.source_url,
        metadata=metadata,
    )
    return {
        "doi": fixture.doi,
        "has": {
            "title": bool(normalize_text(metadata.get("title"))),
            "authors": bool(metadata.get("authors")),
            "abstract": bool(normalize_text(metadata.get("abstract")))
            or bool(extraction.abstract_sections),
            "body": bool(extraction.section_hints)
            or bool(normalize_text(extraction.markdown_text)),
        },
        "validated_fields": ("title", "authors", "abstract", "body"),
        "blocking_fallback_signals": (),
        "source_candidate_hit": True,
    }


def _lightweight_copernicus_summary(fixture: GoldenCorpusFixture) -> dict[str, Any]:
    return _article_model_positive_summary(_build_copernicus_article(fixture), fixture)


def _lightweight_royalsocietypublishing_summary(
    fixture: GoldenCorpusFixture,
) -> dict[str, Any]:
    return _article_model_positive_summary(
        _build_royalsocietypublishing_article(fixture), fixture
    )


def _lightweight_plos_summary(fixture: GoldenCorpusFixture) -> dict[str, Any]:
    return _article_model_positive_summary(_build_plos_article(fixture), fixture)


def _lightweight_frontiers_summary(fixture: GoldenCorpusFixture) -> dict[str, Any]:
    return _article_model_positive_summary(_build_frontiers_article(fixture), fixture)


def _lightweight_oxfordacademic_summary(fixture: GoldenCorpusFixture) -> dict[str, Any]:
    return _article_model_positive_summary(
        _build_oxfordacademic_article(fixture), fixture
    )


def golden_contract_for_fixture(fixture: GoldenCorpusFixture) -> ProviderGoldenContract:
    return golden_corpus_adapter(fixture.provider).contract_for_fixture(fixture)


def _golden_replay_record(sample: dict[str, Any]) -> GoldenCorpusReplayRecord:
    sample_id = str(sample["sample_id"])
    provider = str(sample.get("publisher") or "")
    route_kind = str(sample.get("route_kind") or "")
    origin_kind = str(sample.get("origin_kind") or "real_replay")
    usage_kind = str(sample.get("usage_kind") or "content")
    base = {
        "sample_id": sample_id,
        "provider": provider,
        "route_kind": route_kind,
    }
    if origin_kind == "synthetic":
        return GoldenCorpusReplayRecord(
            **base,
            category="synthetic",
            reason="manifest origin_kind is synthetic",
        )
    if usage_kind != "content" or origin_kind in {"contract_scenario", "real_excerpt"}:
        return GoldenCorpusReplayRecord(
            **base,
            category="unit_only",
            reason=f"origin={origin_kind}, usage={usage_kind}",
        )
    assets = sample.get("assets") if isinstance(sample.get("assets"), dict) else {}
    if origin_kind != "real_replay" or "expected.json" not in assets:
        return GoldenCorpusReplayRecord(
            **base,
            category="manifest_only",
            reason="real replay declaration has no expected.json contract",
        )
    if not _has_replay_asset(sample):
        return GoldenCorpusReplayRecord(
            **base,
            category="manifest_only",
            reason="real replay declaration has no canonical raw asset",
        )
    fixture = GoldenCorpusFixture(sample_id=sample_id, sample=sample)
    try:
        if not fixture.raw_path.is_file() or not fixture.expected_path.is_file():
            raise FileNotFoundError("declared canonical replay assets are absent")
        if not _expected_contract_is_valid(fixture.load_expected()):
            raise ValueError(
                "expected.json does not contain the exact summary contract"
            )
        contract = golden_contract_for_fixture(fixture)
        if fixture.route_kind != contract.route_kind:
            raise ValueError("provider adapter route contract does not match fixture")
        if not fixture.content_type.startswith(contract.content_prefix):
            raise ValueError("provider adapter content contract does not match fixture")
        if not callable(golden_corpus_adapter(provider).build_article):
            raise TypeError("provider adapter is not executable")
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        return GoldenCorpusReplayRecord(
            **base,
            category="unexecutable",
            reason=str(exc),
        )
    return GoldenCorpusReplayRecord(
        **base,
        category="real_replay",
        reason="canonical raw asset, exact contract, and provider adapter are executable",
        fixture=fixture,
    )


def golden_corpus_replay_inventory() -> GoldenCorpusReplayInventory:
    records = tuple(
        _golden_replay_record(sample)
        for sample in iter_manifest_samples(fixture_family="golden")
    )
    return GoldenCorpusReplayInventory(
        records=tuple(sorted(records, key=lambda item: (item.provider, item.sample_id)))
    )


GOLDEN_CORPUS_SHARD_COUNT = 4


def plan_golden_corpus_shards(
    fixtures: tuple[GoldenCorpusFixture, ...] | None = None,
    *,
    shard_count: int = GOLDEN_CORPUS_SHARD_COUNT,
) -> tuple[tuple[GoldenCorpusFixture, ...], ...]:
    """Assign whole providers to deterministic, count-balanced exact shards."""

    if shard_count <= 0:
        raise ValueError("golden corpus shard_count must be positive")
    provider_groups: dict[str, list[GoldenCorpusFixture]] = defaultdict(list)
    for fixture in fixtures or iter_golden_corpus_fixtures():
        provider_groups[fixture.provider].append(fixture)
    shards: list[list[GoldenCorpusFixture]] = [[] for _ in range(shard_count)]
    for provider, group in sorted(
        provider_groups.items(), key=lambda item: (-len(item[1]), item[0])
    ):
        del provider
        shard_index = min(
            range(shard_count), key=lambda index: (len(shards[index]), index)
        )
        shards[shard_index].extend(sorted(group, key=lambda item: item.doi))
    return tuple(
        tuple(sorted(shard, key=lambda item: (item.provider, item.doi)))
        for shard in shards
    )


def _register_golden_corpus_adapters() -> None:
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="acs",
            build_article=_build_browser_workflow_article,
            lightweight_summary=_lightweight_atypon_browser_workflow_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="html",
                content_prefix="text/html",
                source="acs",
                primary_marker="fulltext:acs_html_ok",
            ),
            fallback_contracts={
                "pdf_fallback": ProviderGoldenContract(
                    route_kind="pdf_fallback",
                    content_prefix="application/pdf",
                    source="acs",
                    primary_marker="fulltext:acs_pdf_fallback_ok",
                ),
            },
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="ams",
            build_article=_build_browser_workflow_article,
            lightweight_summary=_lightweight_atypon_browser_workflow_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="html",
                content_prefix="text/html",
                source="ams_html",
                primary_marker="fulltext:ams_html_ok",
            ),
            fallback_contracts={
                "pdf_fallback": ProviderGoldenContract(
                    route_kind="pdf_fallback",
                    content_prefix="application/pdf",
                    source="ams_pdf",
                    primary_marker="fulltext:ams_pdf_fallback_ok",
                ),
            },
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="aip",
            build_article=_build_browser_workflow_article,
            lightweight_summary=_lightweight_atypon_browser_workflow_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="html",
                content_prefix="text/html",
                source="aip_html",
                primary_marker="fulltext:aip_html_ok",
            ),
            fallback_contracts={
                "pdf_fallback": ProviderGoldenContract(
                    route_kind="pdf_fallback",
                    content_prefix="application/pdf",
                    source="aip_pdf",
                    primary_marker="fulltext:aip_pdf_fallback_ok",
                ),
            },
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="annualreviews",
            build_article=_build_browser_workflow_article,
            lightweight_summary=_lightweight_annualreviews_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="html",
                content_prefix="text/html",
                source="annualreviews_html",
                primary_marker="fulltext:annualreviews_html_ok",
            ),
            fallback_contracts={
                "pdf_fallback": ProviderGoldenContract(
                    route_kind="pdf_fallback",
                    content_prefix="application/pdf",
                    source="annualreviews_pdf",
                    primary_marker="fulltext:annualreviews_pdf_fallback_ok",
                ),
            },
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="tandf",
            build_article=_build_browser_workflow_article,
            lightweight_summary=_lightweight_atypon_browser_workflow_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="html",
                content_prefix="text/html",
                source="tandf_html",
                primary_marker="fulltext:tandf_html_ok",
            ),
            fallback_contracts={
                "pdf_fallback": ProviderGoldenContract(
                    route_kind="pdf_fallback",
                    content_prefix="application/pdf",
                    source="tandf_pdf",
                    primary_marker="fulltext:tandf_pdf_fallback_ok",
                ),
            },
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="elsevier",
            build_article=_build_elsevier_article,
            lightweight_summary=_lightweight_elsevier_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="official",
                content_prefix="text/xml",
                source="elsevier_xml",
                primary_marker="fulltext:elsevier_xml_ok",
            ),
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="springer",
            build_article=_build_springer_article,
            lightweight_summary=_lightweight_springer_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="html",
                content_prefix="text/html",
                source="springer_html",
                primary_marker="fulltext:springer_html_ok",
            ),
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="science",
            build_article=_build_browser_workflow_article,
            lightweight_summary=_lightweight_atypon_browser_workflow_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="html",
                content_prefix="text/html",
                source="science",
                primary_marker="fulltext:science_html_ok",
            ),
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="wiley",
            build_article=_build_browser_workflow_article,
            lightweight_summary=_lightweight_atypon_browser_workflow_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="html",
                content_prefix="text/html",
                source="wiley_browser",
                primary_marker="fulltext:wiley_html_ok",
            ),
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="pnas",
            build_article=_build_browser_workflow_article,
            lightweight_summary=_lightweight_atypon_browser_workflow_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="html",
                content_prefix="text/html",
                source="pnas",
                primary_marker="fulltext:pnas_html_ok",
            ),
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="ieee",
            build_article=_build_ieee_article,
            lightweight_summary=_lightweight_ieee_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="html",
                content_prefix="text/html",
                source="ieee_html",
                primary_marker="fulltext:ieee_html_ok",
            ),
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="iop",
            build_article=_build_browser_workflow_article,
            lightweight_summary=_lightweight_atypon_browser_workflow_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="html",
                content_prefix="text/html",
                source="iop_html",
                primary_marker="fulltext:iop_html_ok",
            ),
            fallback_contracts={
                "pdf_fallback": ProviderGoldenContract(
                    route_kind="pdf_fallback",
                    content_prefix="application/pdf",
                    source="iop_pdf",
                    primary_marker="fulltext:iop_pdf_fallback_ok",
                ),
            },
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="copernicus",
            build_article=_build_copernicus_article,
            lightweight_summary=_lightweight_copernicus_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="xml",
                content_prefix="application/xml",
                source="copernicus_xml",
                primary_marker="fulltext:copernicus_xml_ok",
            ),
            fallback_contracts={
                "pdf_fallback": ProviderGoldenContract(
                    route_kind="pdf_fallback",
                    content_prefix="application/pdf",
                    source="copernicus_pdf",
                    primary_marker="fulltext:copernicus_pdf_fallback_ok",
                ),
            },
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="mdpi",
            build_article=_build_browser_workflow_article,
            lightweight_summary=_lightweight_mdpi_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="html",
                content_prefix="text/html",
                source="mdpi_html",
                primary_marker="fulltext:mdpi_html_ok",
            ),
            fallback_contracts={
                "pdf_fallback": ProviderGoldenContract(
                    route_kind="pdf_fallback",
                    content_prefix="application/pdf",
                    source="mdpi_pdf",
                    primary_marker="fulltext:mdpi_pdf_fallback_ok",
                ),
            },
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="arxiv",
            build_article=_build_arxiv_article,
            lightweight_summary=_lightweight_arxiv_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="html",
                content_prefix="text/html",
                source="arxiv_html",
                primary_marker="fulltext:arxiv_html_ok",
            ),
            fallback_contracts={
                "pdf_fallback": ProviderGoldenContract(
                    route_kind="pdf_fallback",
                    content_prefix="application/pdf",
                    source="arxiv_pdf",
                    primary_marker="fulltext:arxiv_pdf_fallback_ok",
                ),
            },
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="royalsocietypublishing",
            build_article=_build_royalsocietypublishing_article,
            lightweight_summary=_lightweight_royalsocietypublishing_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="html",
                content_prefix="text/html",
                source="royalsocietypublishing_html",
                primary_marker="fulltext:royalsocietypublishing_html_ok",
            ),
            fallback_contracts={
                "pdf_fallback": ProviderGoldenContract(
                    route_kind="pdf_fallback",
                    content_prefix="application/pdf",
                    source="royalsocietypublishing_pdf",
                    primary_marker="fulltext:royalsocietypublishing_pdf_fallback_ok",
                ),
            },
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="oxfordacademic",
            build_article=_build_oxfordacademic_article,
            lightweight_summary=_lightweight_oxfordacademic_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="html",
                content_prefix="text/html",
                source="oxfordacademic_html",
                primary_marker="fulltext:oxfordacademic_html_ok",
            ),
            fallback_contracts={
                "pdf_fallback": ProviderGoldenContract(
                    route_kind="pdf_fallback",
                    content_prefix="application/pdf",
                    source="oxfordacademic_pdf",
                    primary_marker="fulltext:oxfordacademic_pdf_fallback_ok",
                ),
            },
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="plos",
            build_article=_build_plos_article,
            lightweight_summary=_lightweight_plos_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="xml",
                content_prefix=("application/xml", "text/xml"),
                source="plos_xml",
                primary_marker="fulltext:plos_xml_ok",
            ),
            fallback_contracts={
                "pdf_fallback": ProviderGoldenContract(
                    route_kind="pdf_fallback",
                    content_prefix="application/pdf",
                    source="plos_pdf",
                    primary_marker="fulltext:plos_pdf_fallback_ok",
                ),
            },
        )
    )
    register_golden_corpus_adapter(
        GoldenCorpusAdapter(
            provider="frontiers",
            build_article=_build_frontiers_article,
            lightweight_summary=_lightweight_frontiers_summary,
            primary_contract=ProviderGoldenContract(
                route_kind="xml",
                content_prefix=("application/xml", "text/xml"),
                source="frontiers_xml",
                primary_marker="fulltext:frontiers_xml_ok",
            ),
            fallback_contracts={
                "pdf_fallback": ProviderGoldenContract(
                    route_kind="pdf_fallback",
                    content_prefix="application/pdf",
                    source="frontiers_pdf",
                    primary_marker="fulltext:frontiers_pdf_fallback_ok",
                ),
            },
        )
    )


_register_golden_corpus_adapters()


def expected_summary_from_article(article) -> dict[str, Any]:
    abstract_sections = [
        section for section in article.sections if section.kind == "abstract"
    ]
    body_sections = [section for section in article.sections if section.kind == "body"]
    data_sections = [
        section for section in article.sections if section.kind == "data_availability"
    ]
    code_sections = [
        section for section in article.sections if section.kind == "code_availability"
    ]
    figure_assets = [
        asset for asset in article.assets if getattr(asset, "kind", "") == "figure"
    ]
    table_assets = [
        asset for asset in article.assets if getattr(asset, "kind", "") == "table"
    ]
    return {
        "has": {
            "title": bool(normalize_text(article.metadata.title)),
            "authors": bool(article.metadata.authors),
            "abstract": bool(normalize_text(article.metadata.abstract))
            or bool(abstract_sections),
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
