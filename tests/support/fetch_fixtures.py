from __future__ import annotations
import asyncio
import json
import threading
import time
from pathlib import Path
from paper_fetch.delivery.cache_index import (
    register_cache_files_for_doi,
    register_markdown_entry,
)
from paper_fetch.delivery.fetch_cache import (
    FETCH_ENVELOPE_CACHE_VERSION,
    fetch_envelope_cache_path,
    cache_request_fingerprint,
)
from paper_fetch.models import (
    EXTRACTION_REVISION,
    AcquisitionProvenance,
    ArticleModel,
    FetchEnvelope,
    Metadata,
    Quality,
    Section,
    TokenEstimateBreakdown,
)
from paper_fetch.resolve.query import ResolvedQuery
from paper_fetch.service import (
    HasFulltextProbeResult,
)
from paper_fetch.tracing import TraceContext, trace_event
from paper_fetch.utils import sanitize_filename


def sample_article() -> ArticleModel:
    return ArticleModel(
        doi="10.1000/example",
        source="elsevier_xml",
        metadata=Metadata(
            title="Example Article",
            authors=["Alice Example"],
            abstract="Example abstract",
            journal="Example Journal",
            publication_dates=[
                {"kind": "unspecified", "value": "2026-01-01", "source": "test"}
            ],
        ),
        sections=[
            Section(heading="Introduction", level=2, kind="body", text="Example body.")
        ],
        references=[],
        assets=[],
        quality=Quality(
            has_fulltext=True,
            token_estimate=128,
            warnings=["example warning"],
            token_estimate_breakdown=TokenEstimateBreakdown(
                abstract=32, body=96, refs=24
            ),
        ),
        acquisition=AcquisitionProvenance(
            provider="elsevier",
            route="xml_api",
            representation="xml",
            transport="api",
            fallback_used=False,
        ),
    )


def sample_envelope(*, modes: set[str], doi: str = "10.1000/example") -> FetchEnvelope:
    article = sample_article()
    article.doi = doi
    article.metadata.title = (
        "Example Article" if doi == "10.1000/example" else f"Article for {doi}"
    )
    return FetchEnvelope(
        doi=doi,
        source="elsevier_xml",
        trace=[
            trace_event("resolve", "doi_selected", "ok"),
            trace_event(
                "metadata",
                "elsevier",
                "ok",
                context=TraceContext(provider="elsevier", route="metadata_api"),
            ),
            trace_event(
                "fulltext",
                "elsevier_xml",
                "ok",
                context=TraceContext(provider="elsevier", route="xml_api"),
            ),
        ],
        quality=article.quality,
        article=article if "article" in modes else None,
        markdown="# Example Article\n\nExample body.\n"
        if "markdown" in modes
        else None,
        metadata=article.metadata if "metadata" in modes else None,
        acquisition=article.acquisition,
    )


def sample_resolved_query(query: str) -> ResolvedQuery:
    return ResolvedQuery(
        query=query,
        query_kind="doi",
        doi=query if query.startswith("10.") else "10.1000/example",
        landing_url="https://example.test/article",
        provider_hint="crossref",
        confidence=1.0,
        candidates=[],
        title="Example Article",
    )


def sample_probe_result(
    query: str,
    *,
    doi: str | None = None,
    title: str | None = None,
    state: str = "likely_yes",
    evidence: list[str] | None = None,
    warnings: list[str] | None = None,
) -> HasFulltextProbeResult:
    return HasFulltextProbeResult(
        query=query,
        doi=doi or (query if query.startswith("10.") else "10.1000/example"),
        title=title or f"Article for {query}",
        state=state,
        evidence=list(evidence or ["crossref_fulltext_link"]),
        warnings=list(warnings or []),
    )


def create_cached_downloads(download_dir: Path, doi: str) -> None:
    base = sanitize_filename(doi)
    download_dir.mkdir(parents=True, exist_ok=True)
    (download_dir / f"{base}.xml").write_text("<article />", encoding="utf-8")
    (download_dir / f"{base}.md").write_text(
        "\n".join(
            [
                "---",
                f'doi: "{doi}"',
                'source: "unit_test"',
                "has_fulltext: true",
                'content_kind: "fulltext"',
                "---",
                "",
                "# Cached Markdown",
                "",
            ]
        ),
        encoding="utf-8",
    )
    asset_dir = download_dir / f"{base}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    asset_path = asset_dir / "figure-1.png"
    asset_path.write_bytes(b"\x89PNG\r\n")
    register_markdown_entry(
        download_dir,
        doi,
        download_dir / f"{base}.md",
        source="unit_test",
        acquisition=AcquisitionProvenance(
            provider="elsevier",
            route="xml_api",
            representation="xml",
            transport="api",
        ),
        has_fulltext=True,
        content_kind="fulltext",
    )
    register_cache_files_for_doi(
        download_dir,
        doi,
        proven_artifact_paths=(download_dir / f"{base}.xml", asset_path),
    )


def create_cached_fetch_envelope(
    download_dir: Path,
    doi: str,
    *,
    modes: list[str] | None = None,
    extraction_revision: int = EXTRACTION_REVISION,
) -> None:
    request = {
        "target": "paper",
        "modes": list(modes or ["markdown"]),
        "strategy": {
            "allow_metadata_only_fallback": True,
            "preferred_providers": None,
            "asset_profile": "none",
            "require_local_body_assets": False,
            "require_full_size_body_assets": False,
        },
        "include_refs": "all",
        "max_tokens": "full_text",
    }
    payload = sample_envelope(modes=set(request["modes"]), doi=doi).to_dict()
    payload["schema_version"] = 4
    path = fetch_envelope_cache_path(download_dir, doi)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": FETCH_ENVELOPE_CACHE_VERSION,
                "extraction_revision": extraction_revision,
                "credential_scope": "public",
                "request_fingerprint": cache_request_fingerprint(doi, request),
                "request": request,
                "payload": payload,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    register_cache_files_for_doi(download_dir, doi, proven_artifact_paths=(path,))


def write_binary(path: Path, size: int = 8) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n" + (b"x" * max(0, size - 6)))


async def wait_for_threading_event(event: threading.Event, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if event.is_set():
            return True
        await asyncio.sleep(0.01)
    return event.is_set()


__all__ = [name for name in globals() if not name.startswith("__")]
