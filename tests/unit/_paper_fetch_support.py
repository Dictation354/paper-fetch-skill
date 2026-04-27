from __future__ import annotations

from pathlib import Path
from dataclasses import replace

import fitz

from paper_fetch import service as paper_fetch
from paper_fetch.http import HttpTransport, RequestFailure
from paper_fetch.models import ArticleModel, FetchEnvelope, Metadata, Quality, RenderOptions, Section, TokenEstimateBreakdown
from paper_fetch.providers.base import ProviderArtifacts, ProviderFailure, ProviderFetchResult
from paper_fetch.tracing import trace_from_markers
from paper_fetch.utils import empty_asset_results


class StubProvider:
    name = "provider"

    def __init__(
        self,
        metadata=None,
        raw_payload=None,
        raw_error=None,
        article=None,
        article_factory=None,
        related_assets=None,
        related_asset_factory=None,
        related_asset_error=None,
    ):
        self._metadata = metadata
        self._raw_payload = raw_payload
        self._raw_error = raw_error
        self._article = article
        self._article_factory = article_factory
        self._related_assets = related_assets
        self._related_asset_factory = related_asset_factory
        self._related_asset_error = related_asset_error

    def fetch_metadata(self, query):
        if isinstance(self._metadata, Exception):
            raise self._metadata
        return self._metadata

    def fetch_raw_fulltext(self, doi, metadata, *, context=None):
        del context
        if self._raw_error:
            raise self._raw_error
        return self._raw_payload

    def to_article_model(self, metadata, raw_payload, *, downloaded_assets=None, asset_failures=None, context=None):
        del context
        if self._article_factory is not None:
            return self._article_factory(
                metadata,
                raw_payload,
                downloaded_assets=downloaded_assets,
                asset_failures=asset_failures,
            )
        return self._article

    def download_related_assets(self, doi, metadata, raw_payload, output_dir, *, asset_profile="all", context=None):
        del context
        if self._related_asset_error:
            raise self._related_asset_error
        if self._related_asset_factory is not None:
            return self._related_asset_factory(doi, metadata, raw_payload, output_dir, asset_profile=asset_profile)
        if self._related_assets is not None:
            return self._related_assets
        return empty_asset_results()

    def fetch_result(self, doi, metadata, output_dir, *, asset_profile="none", artifact_store=None, context=None):
        del artifact_store
        raw_payload = self.fetch_raw_fulltext(doi, metadata, context=context)
        content = getattr(raw_payload, "content", None)
        if content is not None and getattr(raw_payload, "needs_local_copy", False) and not content.needs_local_copy:
            content = replace(content, needs_local_copy=True)
            raw_payload.content = content
        route = str(raw_payload.metadata.get("route") or "").strip().lower()
        provider_name = str(raw_payload.provider or self.name or "provider").strip().lower()
        downloaded_assets = []
        asset_failures = []
        skip_warning = None
        skip_trace = []
        allow_related_assets = True
        if provider_name.startswith("elsevier") and route == "pdf_fallback":
            allow_related_assets = False
            skip_warning = (
                "Elsevier PDF fallback currently returns text-only full text; "
                "figure and supplementary asset downloads are not implemented yet."
            )
            skip_trace = trace_from_markers(["download:elsevier_assets_skipped_text_only"])
        elif provider_name == "springer" and route == "pdf_fallback":
            allow_related_assets = False
            skip_warning = (
                "Springer PDF fallback currently returns text-only full text; "
                "figure and supplementary asset downloads are not implemented yet."
            )
            skip_trace = trace_from_markers(["download:springer_assets_skipped_text_only"])
        elif provider_name in {"wiley", "science", "pnas"} and route == "pdf_fallback":
            allow_related_assets = False
            provider_label = "PNAS" if provider_name == "pnas" else provider_name.title()
            skip_warning = (
                f"{provider_label} PDF fallback currently returns text-only full text; "
                "figure and supplementary asset downloads are not implemented yet."
            )
            skip_trace = trace_from_markers([f"download:{provider_name}_assets_skipped_text_only"])
        elif output_dir is not None and asset_profile != "none":
            try:
                asset_results = self.download_related_assets(
                    doi,
                    metadata,
                    raw_payload,
                    output_dir,
                    asset_profile=asset_profile,
                    context=context,
                )
                downloaded_assets = list(asset_results.get("assets") or [])
                asset_failures = list(asset_results.get("asset_failures") or [])
            except (ProviderFailure, RequestFailure, OSError) as exc:
                article = self.to_article_model(
                    metadata,
                    raw_payload,
                    downloaded_assets=[],
                    asset_failures=[],
                    context=context,
                )
                article.quality.warnings.append(f"{provider_name.replace('_', ' ').title()} related assets could not be downloaded: {exc}")
                article.quality.source_trail.append(f"download:{provider_name}_assets_failed")
                return ProviderFetchResult(
                    provider=provider_name or "provider",
                    article=article,
                    content=content,
                    warnings=list(getattr(raw_payload, "warnings", []) or []),
                    trace=list(getattr(raw_payload, "trace", []) or []),
                    artifacts=ProviderArtifacts(),
                )

        article = self.to_article_model(
            metadata,
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
            context=context,
        )
        return ProviderFetchResult(
            provider=provider_name or "provider",
            article=article,
            content=content,
            warnings=list(getattr(raw_payload, "warnings", []) or []),
            trace=list(getattr(raw_payload, "trace", []) or []),
            artifacts=ProviderArtifacts(
                assets=[dict(item) for item in downloaded_assets],
                asset_failures=[dict(item) for item in asset_failures],
                allow_related_assets=allow_related_assets,
                text_only=not allow_related_assets,
                skip_warning=skip_warning,
                skip_trace=skip_trace,
            ),
        )


class FixtureHtmlTransport(HttpTransport):
    def __init__(self, responses):
        self.responses = responses

    def request(
        self,
        method,
        url,
        *,
        headers=None,
        query=None,
        timeout=20,
        retry_on_rate_limit=False,
        rate_limit_retries=1,
        max_rate_limit_wait_seconds=5,
        retry_on_transient=False,
        transient_retries=2,
        transient_backoff_base_seconds=0.5,
    ):
        if url not in self.responses:
            raise RequestFailure(404, f"Missing fixture response for {url}")
        response = dict(self.responses[url])
        response.setdefault("status_code", 200)
        response.setdefault("headers", {})
        response.setdefault("url", url)
        return response


def build_envelope(article: ArticleModel, *, include_markdown: bool = True) -> FetchEnvelope:
    modes = {"article"}
    if include_markdown:
        modes.add("markdown")
    return paper_fetch.build_fetch_envelope(article, modes=modes, render=RenderOptions())


def fetch_paper_model(
    query: str,
    *,
    allow_downloads: bool = True,
    asset_profile: str = "none",
    output_dir: Path | None = None,
    clients=None,
    transport=None,
    env=None,
) -> ArticleModel:
    envelope = paper_fetch.fetch_paper(
        query,
        modes={"article"},
        strategy=paper_fetch.FetchStrategy(
            allow_metadata_only_fallback=True,
            asset_profile=asset_profile,
        ),
        download_dir=output_dir if allow_downloads else None,
        clients=clients,
        transport=transport,
        env=env,
    )
    assert envelope.article is not None
    return envelope.article


def sample_article() -> paper_fetch.ArticleModel:
    return ArticleModel(
        doi="10.1016/test",
        source="elsevier_xml",
        metadata=Metadata(
            title="Example Article",
            authors=["Alice Example", "Bob Example"],
            abstract="Example abstract",
            journal="Example Journal",
            published="2026-01-01",
        ),
        sections=[
            Section(heading="Introduction", level=2, kind="body", text="Introduction text " * 30),
            Section(heading="Discussion", level=2, kind="body", text="Discussion text " * 30),
        ],
        references=[],
        assets=[],
        quality=Quality(
            has_fulltext=True,
            token_estimate=600,
            warnings=[],
            token_estimate_breakdown=TokenEstimateBreakdown(abstract=120, body=480, refs=64),
        ),
    )


def sample_html_article() -> paper_fetch.ArticleModel:
    article = sample_article()
    article.source = "springer_html"
    return article


def build_pdf_bytes(lines: list[str]) -> bytes:
    document = fitz.open()
    page = document.new_page()
    y = 72
    for line in lines:
        if y > 760:
            page = document.new_page()
            y = 72
        page.insert_text((72, y), line)
        y += 14
    payload = document.tobytes()
    document.close()
    return payload


def fulltext_pdf_bytes() -> bytes:
    paragraph = "This study evaluates landscape responses using repeated satellite observations across multiple seasons."
    lines = ["Abstract"]
    lines.extend([paragraph] * 14)
    lines.append("Introduction")
    lines.extend([paragraph] * 18)
    lines.append("Methods")
    lines.extend([paragraph] * 18)
    lines.append("Results")
    lines.extend([paragraph] * 18)
    lines.append("Discussion")
    lines.extend([paragraph] * 18)
    lines.append("References")
    lines.extend([paragraph] * 6)
    return build_pdf_bytes(lines)


def short_pdf_bytes() -> bytes:
    return build_pdf_bytes(["Journal cover", "Author information", "Downloaded PDF"])
