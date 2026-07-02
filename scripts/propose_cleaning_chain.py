#!/usr/bin/env python3
"""Build fixture-driven cleaning-chain proposals for provider onboarding."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any
import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from paper_fetch.publisher_identity import normalize_doi  # noqa: E402
from paper_fetch.utils import normalize_text  # noqa: E402


DEFAULT_OUTPUT_DIR = "onboarding/cleaning-chain-proposals"
GOLDEN_MANIFEST_PATH = "tests/fixtures/golden_criteria/manifest.json"
SELECTOR_KEYWORDS = (
    "nav",
    "aside",
    "toolbar",
    "metrics",
    "share",
    "supplementary",
    "download",
    "citation",
)
BOILERPLATE_KEYWORDS = (
    "download",
    "citation",
    "share",
    "metrics",
    "article menu",
    "google scholar",
    "subscribe",
    "related",
    "navigation",
    "toolbar",
)
ANCHOR_PATTERNS = {
    "abstract": re.compile(r"\bAbstract\b", re.IGNORECASE),
    "references": re.compile(r"\bReferences?\b", re.IGNORECASE),
    "figure": re.compile(r"\bFigure\s+\d+", re.IGNORECASE),
    "table": re.compile(r"\bTable\s+\d+", re.IGNORECASE),
    "math": re.compile(
        r"(?:<math\b|class=[\"'][^\"']*(?:formula|math|equation)|\bEquation\s+\d+)",
        re.IGNORECASE,
    ),
}
SENTINEL_TOKENS = {
    "[formula unavailable]",
    "access denied",
}
CROSS_ROUTE_GUARD_TOKENS = {
    "article metrics",
    "download citation",
    "download pdf",
    "google scholar",
    "subscribe",
}


class BaselineRenderError(RuntimeError):
    """Raised when production provider replay cannot render a fixture baseline."""


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def _provider_slug(provider: str) -> str:
    slug = provider.strip().lower()
    if not slug:
        raise ValueError("provider must not be empty")
    return slug


def _doi_slug(doi: str) -> str:
    return normalize_doi(doi).replace("/", "_")


def _repo_rel(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _token_key(value: Any) -> str:
    return normalize_text(str(value or "")).casefold()


def _dedupe_normalized_tokens(tokens: list[str]) -> list[str]:
    deduped: dict[str, str] = {}
    for token in tokens:
        normalized = normalize_text(str(token))
        key = _token_key(normalized)
        if key and key not in deduped:
            deduped[key] = normalized
    return sorted(deduped.values(), key=lambda item: _token_key(item))


def _load_golden_manifest() -> dict[str, Any]:
    path = REPO_ROOT / GOLDEN_MANIFEST_PATH
    if not path.exists():
        return {"samples": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("samples"), dict):
        raise ValueError(f"{GOLDEN_MANIFEST_PATH} must contain samples object")
    return data


def _sample_for_doi(
    doi: str, golden_manifest: dict[str, Any]
) -> tuple[str, dict[str, Any]] | None:
    normalized = normalize_doi(doi)
    samples = golden_manifest.get("samples", {})
    slug = _doi_slug(normalized)
    sample = samples.get(slug)
    if isinstance(sample, dict):
        return slug, sample
    for sample_id, candidate in samples.items():
        if (
            isinstance(candidate, dict)
            and normalize_doi(str(candidate.get("doi") or "")) == normalized
        ):
            return str(sample_id), candidate
    return None


def _fixture_root(sample_id: str, sample: dict[str, Any]) -> Path:
    family = str(sample.get("fixture_family") or "golden")
    if family == "block":
        return REPO_ROOT / "tests" / "fixtures" / "block" / sample_id
    return REPO_ROOT / "tests" / "fixtures" / "golden_criteria" / sample_id


def _landing_html_is_provider_managed_raw(sample: dict[str, Any]) -> bool:
    assets = sample.get("assets") if isinstance(sample.get("assets"), dict) else {}
    return (
        str(sample.get("publisher") or "").lower() == "ieee"
        and bool(assets.get("landing.html"))
        and bool(assets.get("extracted.md"))
    )


def _raw_fixture_path(sample_id: str, sample: dict[str, Any]) -> Path | None:
    assets = sample.get("assets") if isinstance(sample.get("assets"), dict) else {}
    preferred_names = ("original.html", "original.xml", "original.pdf", "raw.html")
    if str(sample.get("route_kind") or "").lower() == "pdf_fallback":
        preferred_names = ("original.pdf", "original.html", "original.xml", "raw.html")
    elif "xml" in str(sample.get("route_kind") or "").lower():
        preferred_names = ("original.xml", "original.html", "original.pdf", "raw.html")
    for name in preferred_names:
        value = assets.get(name)
        if value:
            return REPO_ROOT / str(value)
    if _landing_html_is_provider_managed_raw(sample):
        return REPO_ROOT / str(assets["landing.html"])
    root = _fixture_root(sample_id, sample)
    fallback_names = (*preferred_names, "article.html", "raw.html")
    if _landing_html_is_provider_managed_raw(sample):
        fallback_names = (*fallback_names, "landing.html")
    for name in dict.fromkeys(fallback_names):
        path = root / name
        if path.exists():
            return path
    return None


def _skip_cleaning_inventory_item(
    purpose: str, sample: dict[str, Any], raw_path: Path | None
) -> bool:
    # Oxford Academic PDF fallback is a text-only route; HTML cleaning evidence comes from article fixtures.
    return (
        purpose == "pdf_fallback"
        and raw_path is not None
        and raw_path.suffix == ".pdf"
        and str(sample.get("publisher") or "").lower() == "oxfordacademic"
    )


def collect_fixture_inventory(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    golden_manifest = _load_golden_manifest()
    inventory: list[dict[str, Any]] = []

    def add_sample(
        purpose: str, sample: dict[str, Any], *, extra: bool = False
    ) -> None:
        doi = sample.get("doi")
        if not doi:
            return
        sample_entry = _sample_for_doi(str(doi), golden_manifest)
        if sample_entry is None:
            inventory.append(
                {
                    "purpose": purpose,
                    "doi": normalize_doi(str(doi)),
                    "fixture_path": None,
                    "raw_path": None,
                    "content_type": None,
                    "extra_fixture": extra,
                    "status": "missing_fixture",
                }
            )
            return
        sample_id, golden_sample = sample_entry
        raw_path = _raw_fixture_path(sample_id, golden_sample)
        if _skip_cleaning_inventory_item(purpose, golden_sample, raw_path):
            return
        inventory.append(
            {
                "purpose": purpose,
                "doi": normalize_doi(str(doi)),
                "sample_id": sample_id,
                "fixture_path": _repo_rel(_fixture_root(sample_id, golden_sample)),
                "raw_path": _repo_rel(raw_path) if raw_path else None,
                "content_type": golden_sample.get("content_type")
                or _content_type_for_path(raw_path),
                "fixture_family": golden_sample.get("fixture_family") or "golden",
                "extra_fixture": extra,
                "status": "ok" if raw_path else "missing_raw",
            }
        )

    fixtures = (
        manifest.get("fixtures") if isinstance(manifest.get("fixtures"), dict) else {}
    )
    doi_samples = (
        fixtures.get("doi_samples")
        if isinstance(fixtures.get("doi_samples"), dict)
        else {}
    )
    for purpose, sample in doi_samples.items():
        if isinstance(sample, dict):
            add_sample(str(purpose), sample)
    extra_fixtures = manifest.get("extra_fixtures")
    if isinstance(extra_fixtures, list):
        for index, sample in enumerate(extra_fixtures):
            if isinstance(sample, dict):
                add_sample(
                    str(sample.get("purpose") or f"extra_fixtures[{index}]"),
                    sample,
                    extra=True,
                )
    return inventory


def collect_skipped_cleaning_inventory_items(
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    golden_manifest = _load_golden_manifest()
    skipped: list[dict[str, Any]] = []

    def add_sample(
        purpose: str, sample: dict[str, Any], *, extra: bool = False
    ) -> None:
        doi = sample.get("doi")
        if not doi:
            return
        sample_entry = _sample_for_doi(str(doi), golden_manifest)
        if sample_entry is None:
            return
        sample_id, golden_sample = sample_entry
        raw_path = _raw_fixture_path(sample_id, golden_sample)
        if not _skip_cleaning_inventory_item(purpose, golden_sample, raw_path):
            return
        skipped.append(
            {
                "purpose": purpose,
                "doi": normalize_doi(str(doi)),
                "sample_id": sample_id,
                "raw_path": _repo_rel(raw_path) if raw_path else None,
                "extra_fixture": extra,
                "reason": "route is excluded from HTML cleaning-chain evidence",
            }
        )

    fixtures = (
        manifest.get("fixtures") if isinstance(manifest.get("fixtures"), dict) else {}
    )
    doi_samples = (
        fixtures.get("doi_samples")
        if isinstance(fixtures.get("doi_samples"), dict)
        else {}
    )
    for purpose, sample in doi_samples.items():
        if isinstance(sample, dict):
            add_sample(str(purpose), sample)
    extra_fixtures = manifest.get("extra_fixtures")
    if isinstance(extra_fixtures, list):
        for index, sample in enumerate(extra_fixtures):
            if isinstance(sample, dict):
                add_sample(
                    str(sample.get("purpose") or f"extra_fixtures[{index}]"),
                    sample,
                    extra=True,
                )
    return skipped


def _content_type_for_path(path: Path | None) -> str | None:
    if path is None:
        return None
    if path.suffix == ".html":
        return "text/html"
    if path.suffix == ".xml":
        return "application/xml"
    if path.suffix == ".pdf":
        return "application/pdf"
    return None


def _load_soup(path: Path) -> BeautifulSoup | None:
    if path.suffix not in {".html", ".xml"}:
        return None
    parser = "xml" if path.suffix == ".xml" else "html.parser"
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        return BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), parser)


def _line_records(text: str, fixture: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        normalized = normalize_text(line)
        if normalized:
            records.append(
                {
                    "fixture_path": fixture["raw_path"],
                    "purpose": fixture["purpose"],
                    "line": line_number,
                    "text": normalized,
                }
            )
    return records


class _ProviderFixtureReplay:
    def __init__(
        self, *, sample_id: str, sample: dict[str, Any], raw_path: Path
    ) -> None:
        self.sample_id = sample_id
        self.sample = sample
        self._raw_path = raw_path

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
        return self._raw_path


def _fixture_asset_path(fixture: _ProviderFixtureReplay, name: str) -> Path | None:
    assets = (
        fixture.sample.get("assets")
        if isinstance(fixture.sample.get("assets"), dict)
        else {}
    )
    value = assets.get(name)
    if not value:
        return None
    path = REPO_ROOT / str(value)
    return path if path.exists() else None


def _load_fixture_provider_metadata(fixture: _ProviderFixtureReplay) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "doi": fixture.doi,
        "title": fixture.title,
        "landing_page_url": fixture.landing_url,
        "source_url": fixture.source_url,
        "authors": [],
        "fulltext_links": [],
        "references": [],
    }
    api_path = _fixture_asset_path(fixture, "api.json")
    if api_path is not None:
        try:
            payload = json.loads(api_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        provider_metadata = (
            payload.get("provider_metadata") if isinstance(payload, dict) else {}
        )
        if isinstance(provider_metadata, dict):
            metadata.update(provider_metadata)
    return metadata


def _build_arxiv_article_from_fixture(fixture: _ProviderFixtureReplay) -> Any:
    from paper_fetch.arxiv_id import arxiv_id_from_doi
    from paper_fetch.http import HttpTransport, PDF_MIME_TYPE
    from paper_fetch.providers._arxiv_html import _extract_arxiv_html_markdown
    from paper_fetch.providers._arxiv_metadata import _minimal_arxiv_metadata
    from paper_fetch.providers._payloads import build_provider_payload
    from paper_fetch.providers._pdf_common import pdf_fetch_result_from_bytes
    from paper_fetch.providers.arxiv import ArxivClient
    from paper_fetch.reason_codes import PDF_FALLBACK
    from paper_fetch.tracing import fulltext_marker

    base_metadata = _load_fixture_provider_metadata(fixture)
    arxiv_id = str(
        base_metadata.get("arxiv_id") or arxiv_id_from_doi(fixture.doi) or ""
    )
    metadata = _minimal_arxiv_metadata(
        arxiv_id, doi=fixture.doi, metadata=base_metadata
    )
    body = fixture.raw_path.read_bytes()
    client = ArxivClient(HttpTransport(), {})
    if fixture.route_kind == PDF_FALLBACK or fixture.raw_path.suffix == ".pdf":
        pdf_result = pdf_fetch_result_from_bytes(
            artifact_dir=None,
            source_url=fixture.source_url,
            final_url=fixture.source_url,
            pdf_bytes=body,
        )
        raw_payload = build_provider_payload(
            provider="arxiv",
            route_kind=PDF_FALLBACK,
            source_url=fixture.source_url,
            content_type=PDF_MIME_TYPE,
            body=body,
            markdown_text=pdf_result.markdown_text,
            merged_metadata=metadata,
            diagnostics={PDF_FALLBACK: {"fixture": "cleaning_proposal"}},
            reason="Loaded arXiv PDF fallback fixture through provider replay.",
            warnings=[
                "Full text was extracted from arXiv PDF fallback fixture after HTML was not used."
            ],
            trace_markers=[fulltext_marker("arxiv", "ok", route=PDF_FALLBACK)],
        )
        return client.to_article_model(metadata, raw_payload)

    html_text = body.decode("utf-8", errors="replace")
    extraction = _extract_arxiv_html_markdown(
        html_text,
        fixture.source_url,
        metadata=metadata,
    )
    raw_payload = build_provider_payload(
        provider="arxiv",
        route_kind="html",
        source_url=fixture.source_url,
        content_type=fixture.content_type or "text/html",
        body=body,
        markdown_text=extraction.markdown_text,
        merged_metadata=extraction.merged_metadata,
        diagnostics={
            "availability_diagnostics": extraction.diagnostics,
            "extraction": extraction.diagnostics.get("extraction"),
            "semantic_losses": extraction.diagnostics.get("semantic_losses"),
        },
        reason="Loaded arXiv official HTML fixture through provider replay.",
        extracted_assets=extraction.extracted_assets,
        warnings=extraction.warnings,
        trace_markers=[fulltext_marker("arxiv", "ok", route="html")],
    )
    return client.to_article_model(metadata, raw_payload)


def _build_plos_article_from_fixture(fixture: _ProviderFixtureReplay) -> Any:
    from paper_fetch.models import article_from_markdown
    from paper_fetch.providers._article_markdown_jats import parse_jats_xml
    from paper_fetch.providers._pdf_common import pdf_fetch_result_from_bytes
    from paper_fetch.reason_codes import PDF_FALLBACK
    from paper_fetch.tracing import fulltext_marker, trace_from_markers

    metadata = _load_fixture_provider_metadata(fixture)
    body = fixture.raw_path.read_bytes()
    if fixture.route_kind == PDF_FALLBACK or fixture.raw_path.suffix == ".pdf":
        pdf_result = pdf_fetch_result_from_bytes(
            artifact_dir=None,
            source_url=fixture.source_url,
            final_url=fixture.source_url,
            pdf_bytes=body,
        )
        return article_from_markdown(
            source="plos_pdf",
            metadata=metadata,
            doi=normalize_doi(str(metadata.get("doi") or fixture.doi)) or None,
            markdown_text=pdf_result.markdown_text,
            warnings=[
                "Full text was extracted from PLOS PDF fallback fixture after XML was not used."
            ],
            trace=trace_from_markers(
                [
                    fulltext_marker("plos", "fail", route="xml"),
                    fulltext_marker("plos", "ok", route=PDF_FALLBACK),
                ]
            ),
        )

    extraction = parse_jats_xml(
        body,
        source_url=fixture.source_url,
        base_metadata=metadata,
    )
    if extraction is None:
        raise BaselineRenderError(
            f"PLOS fixture {fixture.sample_id} did not parse as JATS XML"
        )
    article_metadata = dict(extraction.metadata)
    if extraction.references:
        article_metadata["references"] = list(extraction.references)
    return article_from_markdown(
        source="plos_xml",
        metadata=article_metadata,
        doi=normalize_doi(str(article_metadata.get("doi") or fixture.doi)) or None,
        markdown_text=extraction.markdown_text,
        abstract_sections=extraction.abstract_sections,
        assets=extraction.assets,
        trace=trace_from_markers([fulltext_marker("plos", "ok", route="xml")]),
        semantic_losses=extraction.semantic_losses,
    )


def _build_ieee_article_from_fixture(
    fixture: _ProviderFixtureReplay,
    *,
    purpose: str | None,
) -> tuple[Any, str]:
    from paper_fetch.http import HttpTransport, PDF_MIME_TYPE
    from paper_fetch.providers import _ieee_metadata
    from paper_fetch.providers._payloads import build_provider_payload
    from paper_fetch.providers.ieee import IeeeClient
    from paper_fetch.reason_codes import ABSTRACT_ONLY, PDF_FALLBACK
    from paper_fetch.tracing import fulltext_marker

    landing_path = _fixture_asset_path(fixture, "landing.html")
    if landing_path is None and fixture.raw_path.name == "landing.html":
        landing_path = fixture.raw_path
    if landing_path is None:
        raise BaselineRenderError(
            f"IEEE fixture {fixture.sample_id} does not include landing.html"
        )

    landing_metadata = _ieee_metadata._parse_landing_metadata(
        landing_path.read_text(encoding="utf-8", errors="ignore")
    )
    metadata = _ieee_metadata._merge_ieee_metadata(
        _load_fixture_provider_metadata(fixture),
        landing_metadata,
        fixture.landing_url,
    )
    article_number = str(
        fixture.sample.get("article_number")
        or metadata.get("article_number")
        or metadata.get("articleNumber")
        or ""
    )
    if article_number:
        metadata["article_number"] = article_number
        metadata["articleNumber"] = article_number
    if not metadata.get("doi"):
        metadata["doi"] = fixture.doi

    landing_attempt = _ieee_metadata.IeeeLandingAttempt(
        normalized_doi=fixture.doi,
        landing_url=fixture.landing_url,
        response_url=fixture.landing_url,
        html_text=landing_path.read_text(encoding="utf-8", errors="ignore"),
        merged_metadata=metadata,
        article_number=article_number,
        landing_metadata=landing_metadata,
    )
    client = IeeeClient(HttpTransport(), {})
    normalized_purpose = str(purpose or "").lower()
    if normalized_purpose == ABSTRACT_ONLY:
        return (
            client.to_article_model(
                {"doi": fixture.doi},
                client._abstract_only_payload(
                    landing_attempt, warnings=[], trace_markers=[]
                ),
            ),
            "paper_fetch.providers.ieee:provider_managed_abstract_only",
        )

    expected_route = str(
        fixture.sample.get("expected_route") or fixture.route_kind or ""
    ).lower()
    extracted_path = _fixture_asset_path(fixture, "extracted.md")
    if (
        normalized_purpose == PDF_FALLBACK or expected_route == PDF_FALLBACK
    ) and extracted_path is not None:
        markdown_text = extracted_path.read_text(encoding="utf-8", errors="ignore")
        raw_payload = build_provider_payload(
            provider="ieee",
            route_kind=PDF_FALLBACK,
            source_url=fixture.source_url or fixture.landing_url,
            content_type=PDF_MIME_TYPE,
            body=b"",
            markdown_text=markdown_text,
            merged_metadata=metadata,
            diagnostics={PDF_FALLBACK: {"fixture": "cleaning_proposal"}},
            reason="Loaded IEEE text-only PDF fallback fixture through provider replay.",
            trace_markers=[
                fulltext_marker("ieee", "fail", route="html"),
                fulltext_marker("ieee", "ok", route=PDF_FALLBACK),
            ],
            needs_local_copy=True,
            content_needs_local_copy=True,
        )
        return (
            client.to_article_model({"doi": fixture.doi}, raw_payload),
            "paper_fetch.providers.ieee:provider_managed_pdf_fallback_fixture",
        )

    raise BaselineRenderError(
        f"IEEE fixture {fixture.sample_id} is not a provider-managed fallback sample"
    )


def _render_markdown_baseline(
    doi: str,
    fixture_root: Path,
    raw_path: Path,
    *,
    fixture_sample: dict[str, Any] | None = None,
    sample_id: str | None = None,
    purpose: str | None = None,
) -> tuple[str, str]:
    try:
        from tests.golden_corpus import build_article_from_fixture
        from tests.golden_criteria import golden_criteria_sample_for_doi

        sample = (
            dict(fixture_sample)
            if isinstance(fixture_sample, dict)
            else golden_criteria_sample_for_doi(doi)
        )
        fixture = _ProviderFixtureReplay(
            sample_id=str(sample_id or sample.get("sample_id") or _doi_slug(doi)),
            sample=sample,
            raw_path=raw_path,
        )
        extracted_path = _fixture_asset_path(fixture, "extracted.md")
        if sample.get("fixture_family") == "block" and extracted_path is not None:
            return (
                extracted_path.read_text(encoding="utf-8", errors="ignore"),
                f"{_repo_rel(extracted_path)}:provider_managed_block_markdown",
            )
        if fixture.provider == "ieee" and (
            str(purpose or "").lower() in {"abstract_only", "pdf_fallback"}
            or (
                fixture.raw_path.name == "landing.html"
                and _fixture_asset_path(fixture, "extracted.md") is not None
            )
        ):
            article, source = _build_ieee_article_from_fixture(fixture, purpose=purpose)
            return article.to_ai_markdown(
                asset_profile="body", max_tokens="full_text"
            ), source
        if fixture.provider == "plos" and fixture.raw_path.suffix in {".xml", ".pdf"}:
            article = _build_plos_article_from_fixture(fixture)
            return (
                article.to_ai_markdown(asset_profile="body", max_tokens="full_text"),
                "paper_fetch.providers._article_markdown_jats:plos_manifest_fixture",
            )
        if fixture.provider == "arxiv":
            article = _build_arxiv_article_from_fixture(fixture)
        else:
            article = build_article_from_fixture(fixture)
        return (
            article.to_ai_markdown(asset_profile="body", max_tokens="full_text"),
            "tests.golden_corpus:provider_adapter_production_chain",
        )
    except Exception as exc:
        try:
            fixture_ref = fixture_root.relative_to(REPO_ROOT)
        except ValueError:
            fixture_ref = fixture_root
        raise BaselineRenderError(
            "Unable to render production markdown baseline for "
            f"{doi} from fixture {fixture_ref}. "
            "Register or fix the provider golden corpus adapter instead of "
            "falling back to a generic converter."
        ) from exc


def collect_baselines(inventory: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    baselines: dict[str, dict[str, Any]] = {}
    for fixture in inventory:
        raw_path_value = fixture.get("raw_path")
        if not raw_path_value:
            continue
        raw_path = REPO_ROOT / str(raw_path_value)
        raw_text = ""
        soup = _load_soup(raw_path)
        if soup is not None:
            raw_text = soup.get_text("\n")
        elif raw_path.suffix == ".pdf":
            raw_text = ""
        fixture_root = REPO_ROOT / str(fixture["fixture_path"])
        sample_id = str(fixture.get("sample_id") or "")
        fixture_sample = _load_golden_manifest().get("samples", {}).get(sample_id)
        markdown, markdown_source = _render_markdown_baseline(
            str(fixture["doi"]),
            fixture_root,
            raw_path,
            fixture_sample=fixture_sample if isinstance(fixture_sample, dict) else None,
            sample_id=sample_id or None,
            purpose=str(fixture["purpose"]),
        )
        key = f"{fixture['purpose']}:{fixture['doi']}"
        baselines[key] = {
            "purpose": fixture["purpose"],
            "doi": fixture["doi"],
            "raw_path": fixture["raw_path"],
            "raw_text_chars": len(normalize_text(raw_text)),
            "raw_line_count": len(
                [line for line in raw_text.splitlines() if normalize_text(line)]
            ),
            "markdown_source": markdown_source,
            "markdown_chars": len(normalize_text(markdown)),
            "markdown_heading_count": len(
                re.findall(r"(?m)^\s{0,3}#{1,6}\s+", markdown)
            ),
            "raw_text": raw_text,
            "markdown": markdown,
        }
    return baselines


def collect_fixtures_digest(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    digest: list[dict[str, Any]] = []
    for fixture in inventory:
        raw_path_value = fixture.get("raw_path")
        item = {
            "purpose": fixture.get("purpose"),
            "doi": fixture.get("doi"),
            "raw_path": raw_path_value,
        }
        if raw_path_value:
            raw_path = REPO_ROOT / str(raw_path_value)
            if raw_path.exists():
                item["sha256"] = _sha256_file(raw_path)
            else:
                item["status"] = "missing_raw"
        else:
            item["status"] = fixture.get("status") or "missing_raw"
        digest.append(item)
    return digest


def mine_boilerplate_candidates(
    inventory: list[dict[str, Any]],
    baselines: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    occurrences: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fixture in inventory:
        raw_path_value = fixture.get("raw_path")
        if not raw_path_value:
            continue
        raw_path = REPO_ROOT / str(raw_path_value)
        soup = _load_soup(raw_path)
        if soup is None:
            continue
        for record in _line_records(soup.get_text("\n"), fixture):
            text = record["text"]
            lowered = text.lower()
            if len(text) < 4 or len(text) > 120:
                continue
            if not any(keyword in lowered for keyword in BOILERPLATE_KEYWORDS):
                continue
            occurrences[lowered].append(record)
    candidates: list[dict[str, Any]] = []
    for token, records in occurrences.items():
        purposes = sorted({str(record["purpose"]) for record in records})
        if len(purposes) < 2:
            continue
        candidates.append(
            {
                "token": records[0]["text"],
                "occurrences": len(records),
                "fixture_count": len({record["fixture_path"] for record in records}),
                "purposes": purposes,
                "provenance": records[:5],
                "appears_in_markdown_baseline": any(
                    token in normalize_text(item.get("markdown", "")).lower()
                    for item in baselines.values()
                ),
            }
        )
    return sorted(candidates, key=lambda item: (-item["fixture_count"], item["token"]))[
        :50
    ]


def mine_selector_candidates(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for fixture in inventory:
        raw_path_value = fixture.get("raw_path")
        if not raw_path_value:
            continue
        soup = _load_soup(REPO_ROOT / str(raw_path_value))
        if soup is None:
            continue
        for node in soup.find_all(True):
            attrs: list[str] = []
            node_id = node.get("id")
            if node_id:
                attrs.append(f"#{node_id}")
            classes = node.get("class") or []
            attrs.extend(
                f".{class_name}"
                for class_name in classes
                if isinstance(class_name, str)
            )
            attr_blob = " ".join(attrs).lower()
            if not attr_blob or not any(
                keyword in attr_blob for keyword in SELECTOR_KEYWORDS
            ):
                continue
            selector = f"{node.name}{''.join(attrs[:3])}"
            key = (str(fixture["raw_path"]), str(fixture["purpose"]), selector)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "selector": selector,
                    "purpose": fixture["purpose"],
                    "fixture_path": fixture["raw_path"],
                    "dom_path": _dom_path(node),
                    "sample_text": normalize_text(node.get_text(" ", strip=True))[:160],
                }
            )
    return candidates[:80]


def _dom_path(node: Any) -> str:
    parts: list[str] = []
    current = node
    while current is not None and getattr(current, "name", None):
        part = str(current.name)
        node_id = current.get("id")
        if node_id:
            part += f"#{node_id}"
        classes = current.get("class") or []
        if classes:
            part += "." + ".".join(str(value) for value in classes[:2])
        parts.append(part)
        current = current.parent
        if len(parts) >= 6:
            break
    return " > ".join(reversed(parts))


def mine_content_anchors(
    inventory: list[dict[str, Any]],
    baselines: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for fixture in inventory:
        key = f"{fixture['purpose']}:{fixture['doi']}"
        baseline = baselines.get(key)
        if baseline is None:
            continue
        raw_text = baseline.get("raw_text", "")
        for anchor_type, pattern in ANCHOR_PATTERNS.items():
            for match in list(pattern.finditer(raw_text))[:8]:
                line = raw_text[: match.start()].count("\n") + 1
                anchors.append(
                    {
                        "anchor_type": anchor_type,
                        "text": normalize_text(match.group(0)),
                        "purpose": fixture["purpose"],
                        "fixture_path": fixture["raw_path"],
                        "line": line,
                    }
                )
    return anchors[:120]


def calibrate_markdown_contract(
    manifest: dict[str, Any],
    baselines: dict[str, dict[str, Any]],
    anchors: list[dict[str, Any]],
    *,
    skip_purposes: set[str] | None = None,
) -> dict[str, Any]:
    markdown_contract = (
        manifest.get("markdown_contract")
        if isinstance(manifest.get("markdown_contract"), dict)
        else {}
    )
    skipped = {str(purpose) for purpose in (skip_purposes or set())}
    anchor_by_purpose: dict[str, list[str]] = defaultdict(list)
    for anchor in anchors:
        anchor_by_purpose[str(anchor["purpose"])].append(str(anchor["text"]))
    deltas: dict[str, Any] = {}
    all_raw = "\n".join(
        str(item.get("raw_text") or "") for item in baselines.values()
    ).lower()
    for purpose, contract in markdown_contract.items():
        purpose_key = str(purpose)
        if purpose_key in skipped:
            continue
        if not isinstance(contract, dict):
            continue
        doi = normalize_doi(str(contract.get("doi") or ""))
        baseline = baselines.get(f"{purpose_key}:{doi}")
        markdown = str((baseline or {}).get("markdown") or "")
        missing_include = [
            token
            for token in contract.get("must_include") or []
            if normalize_text(str(token))
            and normalize_text(str(token)) not in normalize_text(markdown)
        ]
        dead_negative = [
            token
            for token in contract.get("must_not_include") or []
            if normalize_text(str(token)).lower() not in all_raw
        ]
        classified_dead = classify_dead_must_not_include(dead_negative)
        current_includes = {
            _token_key(token)
            for token in contract.get("must_include") or []
            if _token_key(token)
        }
        suggested = [
            token
            for token in _dedupe_normalized_tokens(
                anchor_by_purpose.get(purpose_key, [])
            )
            if _token_key(token) not in current_includes
        ][:10]
        deltas[purpose_key] = {
            "doi": doi,
            "missing_must_include": missing_include,
            "dead_must_not_include": classified_dead,
            "suggested_must_include_from_fixtures": suggested,
        }
    return deltas


def classify_dead_must_not_include(
    tokens: list[Any],
) -> dict[str, list[dict[str, str]]]:
    classified: dict[str, list[dict[str, str]]] = {
        "sentinel": [],
        "cross_route_guard": [],
        "truly_vacuous": [],
    }
    for token in tokens:
        normalized = normalize_text(str(token))
        key = _token_key(normalized)
        if not key:
            continue
        if key in SENTINEL_TOKENS:
            classified["sentinel"].append(
                {
                    "token": normalized,
                    "reason": "defensive sentinel may be absent from clean fixtures",
                }
            )
        elif key in CROSS_ROUTE_GUARD_TOKENS:
            classified["cross_route_guard"].append(
                {
                    "token": normalized,
                    "reason": "site chrome guard may belong to another route or page shell",
                }
            )
        else:
            classified["truly_vacuous"].append(
                {
                    "token": normalized,
                    "reason": "token is absent from all participating raw fixtures and has no exemption",
                }
            )
    return classified


def detect_overcleaning_risks(
    inventory: list[dict[str, Any]],
    baselines: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    for fixture in inventory:
        key = f"{fixture['purpose']}:{fixture['doi']}"
        baseline = baselines.get(key)
        if baseline is None:
            continue
        markdown_norm = normalize_text(str(baseline.get("markdown") or "")).lower()
        raw_path_value = fixture.get("raw_path")
        if not raw_path_value:
            continue
        soup = _load_soup(REPO_ROOT / str(raw_path_value))
        if soup is None:
            continue
        for node in soup.find_all(["p", "figcaption", "caption", "li"]):
            text = normalize_text(node.get_text(" ", strip=True))
            if len(text) < 140:
                continue
            probe = text[:100].lower()
            if probe in markdown_norm:
                continue
            risks.append(
                {
                    "purpose": fixture["purpose"],
                    "doi": fixture["doi"],
                    "fixture_path": fixture["raw_path"],
                    "dom_path": _dom_path(node),
                    "sample_text": text[:220],
                    "risk": "raw long paragraph/caption/reference text is absent from rendered baseline",
                }
            )
            if len(risks) >= 80:
                return risks
    return risks


def token_conflict_report(
    candidates: list[dict[str, Any]],
    baselines: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for candidate in candidates:
        token = normalize_text(str(candidate["token"])).lower()
        hits: list[dict[str, str]] = []
        baseline_hits: list[dict[str, str]] = []
        for key, baseline in baselines.items():
            raw_text = normalize_text(str(baseline.get("raw_text") or "")).lower()
            markdown = normalize_text(str(baseline.get("markdown") or "")).lower()
            if token and token in raw_text:
                hits.append({"fixture": key, "purpose": str(baseline["purpose"])})
            if token and token in markdown:
                baseline_hits.append(
                    {"fixture": key, "purpose": str(baseline["purpose"])}
                )
        report.append(
            {
                "token": candidate["token"],
                "raw_hits": hits,
                "markdown_baseline_hits": baseline_hits,
                "possible_body_conflict": bool(baseline_hits),
            }
        )
    return report


def build_cleaning_chain_proposal(
    manifest: dict[str, Any], *, manifest_path: str
) -> dict[str, Any]:
    provider = _provider_slug(str(manifest["name"]))
    inventory = collect_fixture_inventory(manifest)
    skipped_inventory_items = collect_skipped_cleaning_inventory_items(manifest)
    baselines = collect_baselines(inventory)
    fixtures_digest = collect_fixtures_digest(inventory)
    boilerplate = mine_boilerplate_candidates(inventory, baselines)
    selectors = mine_selector_candidates(inventory)
    anchors = mine_content_anchors(inventory, baselines)
    skipped_purposes = {str(item.get("purpose")) for item in skipped_inventory_items}
    contract_delta = calibrate_markdown_contract(
        manifest,
        baselines,
        anchors,
        skip_purposes=skipped_purposes,
    )
    overcleaning = detect_overcleaning_risks(inventory, baselines)
    conflicts = token_conflict_report(boilerplate, baselines)
    sanitized_baselines = {
        key: {
            name: value
            for name, value in baseline.items()
            if name not in {"raw_text", "markdown"}
        }
        for key, baseline in baselines.items()
    }
    return {
        "schema_version": 1,
        "provider": provider,
        "manifest": manifest_path,
        "artifact": f"{DEFAULT_OUTPUT_DIR}/{provider}.yml",
        "evidence_artifact": f"{DEFAULT_OUTPUT_DIR}/{provider}.evidence.yml",
        "fixtures_digest": fixtures_digest,
        "raw_fixture_inventory": inventory,
        "skipped_cleaning_inventory": skipped_inventory_items,
        "raw_baselines": sanitized_baselines,
        "repeated_boilerplate_candidates": boilerplate,
        "selector_candidates": selectors,
        "content_anchors": anchors,
        "proposed_markdown_contract_delta": contract_delta,
        "overcleaning_probes": overcleaning,
        "token_conflict_report": conflicts,
        "notes": [
            "Proposal only; do not modify provider implementation automatically.",
            "Every candidate is derived from committed local fixture text or DOM evidence.",
            "markdown_semantic_reviewed remains operator-controlled.",
        ],
    }


def build_compact_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    boilerplate = proposal.get("repeated_boilerplate_candidates") or []
    selectors = proposal.get("selector_candidates") or []
    overcleaning = proposal.get("overcleaning_probes") or []
    conflicts = proposal.get("token_conflict_report") or []
    selected_drop_tokens = [
        {
            "token": candidate.get("token"),
            "fixture_count": candidate.get("fixture_count"),
            "purposes": candidate.get("purposes") or [],
            "appears_in_markdown_baseline": bool(
                candidate.get("appears_in_markdown_baseline")
            ),
        }
        for candidate in boilerplate
        if not candidate.get("appears_in_markdown_baseline")
    ][:12]
    selected_drop_selectors = [
        {
            "selector": candidate.get("selector"),
            "purpose": candidate.get("purpose"),
            "fixture_path": candidate.get("fixture_path"),
            "sample_text": candidate.get("sample_text"),
        }
        for candidate in selectors
    ][:12]
    conflict_tokens = [
        str(item.get("token"))
        for item in conflicts
        if item.get("possible_body_conflict") and item.get("token")
    ][:20]
    return {
        "schema_version": 2,
        "provider": proposal["provider"],
        "manifest": proposal["manifest"],
        "artifact": proposal["artifact"],
        "evidence_artifact": proposal["evidence_artifact"],
        "fixtures_digest": proposal["fixtures_digest"],
        "proposed_markdown_contract_delta": proposal[
            "proposed_markdown_contract_delta"
        ],
        "skipped_cleaning_inventory": proposal.get("skipped_cleaning_inventory") or [],
        "selected_drop_tokens": selected_drop_tokens,
        "selected_drop_selectors": selected_drop_selectors,
        "overcleaning_probe_summary": {
            "count": len(overcleaning),
            "samples": overcleaning[:3],
        },
        "token_conflict_summary": {
            "count": len(conflicts),
            "possible_body_conflict_tokens": conflict_tokens,
        },
        "notes": [
            "Compact proposal for implementation worker; full evidence is in evidence_artifact.",
            "sentinel and cross_route_guard contract deltas are warnings, not blockers.",
        ],
    }


def contract_check_result(proposal: dict[str, Any]) -> dict[str, Any]:
    blocking_missing: list[dict[str, Any]] = []
    blocking_truly_vacuous: list[dict[str, Any]] = []
    warning_sentinel: list[dict[str, Any]] = []
    warning_cross_route_guard: list[dict[str, Any]] = []
    for purpose, delta in (
        proposal.get("proposed_markdown_contract_delta") or {}
    ).items():
        doi = delta.get("doi")
        for token in delta.get("missing_must_include") or []:
            blocking_missing.append({"purpose": purpose, "doi": doi, "token": token})
        classified = (
            delta.get("dead_must_not_include") if isinstance(delta, dict) else {}
        )
        if not isinstance(classified, dict):
            continue
        for item in classified.get("truly_vacuous") or []:
            blocking_truly_vacuous.append({"purpose": purpose, "doi": doi, **item})
        for item in classified.get("sentinel") or []:
            warning_sentinel.append({"purpose": purpose, "doi": doi, **item})
        for item in classified.get("cross_route_guard") or []:
            warning_cross_route_guard.append({"purpose": purpose, "doi": doi, **item})
    has_blocking = bool(blocking_missing or blocking_truly_vacuous)
    return {
        "provider": proposal["provider"],
        "status": "fail" if has_blocking else "pass",
        "failure_code": "MARKDOWN_CONTRACT_DRIFT" if has_blocking else None,
        "blocking": {
            "missing_must_include": blocking_missing,
            "truly_vacuous": blocking_truly_vacuous,
        },
        "warnings": {
            "sentinel": warning_sentinel,
            "cross_route_guard": warning_cross_route_guard,
        },
        "fixtures_digest": proposal.get("fixtures_digest") or [],
        "overcleaning_probe_count": len(proposal.get("overcleaning_probes") or []),
        "token_conflict_count": len(proposal.get("token_conflict_report") or []),
    }


def _evidence_output_path(compact_output_path: Path) -> Path:
    return compact_output_path.with_suffix(".evidence.yml")


def _manifest_from_args(args: argparse.Namespace) -> tuple[Path, str]:
    if args.manifest:
        path = Path(args.manifest)
        if not path.is_absolute():
            path = REPO_ROOT / path
        return path, _repo_rel(path)
    provider = _provider_slug(args.provider)
    rel = f"onboarding/manifests/{provider}.yml"
    return REPO_ROOT / rel, rel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate fixture-driven cleaning-chain proposals."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--provider", help="provider name")
    source.add_argument("--manifest", help="provider manifest path")
    parser.add_argument(
        "--write", action="store_true", help="write proposal YAML artifact"
    )
    parser.add_argument(
        "--check-contract",
        action="store_true",
        help="include contract calibration in stdout for local review",
    )
    parser.add_argument("--output", help="optional proposal output path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest_path, manifest_ref = _manifest_from_args(args)
    manifest = _load_yaml(manifest_path)
    proposal = build_cleaning_chain_proposal(manifest, manifest_path=manifest_ref)
    output_path = (
        Path(args.output)
        if args.output
        else REPO_ROOT / DEFAULT_OUTPUT_DIR / f"{proposal['provider']}.yml"
    )
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    if args.write:
        compact = build_compact_proposal(proposal)
        evidence_output_path = _evidence_output_path(output_path)
        compact["artifact"] = _repo_rel(output_path)
        compact["evidence_artifact"] = _repo_rel(evidence_output_path)
        proposal["artifact"] = _repo_rel(output_path)
        proposal["evidence_artifact"] = _repo_rel(evidence_output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            yaml.safe_dump(compact, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        evidence_output_path.write_text(
            yaml.safe_dump(proposal, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "provider": proposal["provider"],
                    "output": _repo_rel(output_path),
                    "evidence_output": _repo_rel(evidence_output_path),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.check_contract:
        check = contract_check_result(proposal)
        print(
            yaml.safe_dump(
                check,
                sort_keys=False,
            ),
            end="",
        )
        return 1 if check["status"] == "fail" else 0
    print(
        yaml.safe_dump(
            build_compact_proposal(proposal), sort_keys=False, allow_unicode=False
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
