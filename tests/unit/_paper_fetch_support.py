from __future__ import annotations

from pathlib import Path

import fitz

from paper_fetch import service as paper_fetch
from paper_fetch.http import HttpTransport
from paper_fetch.models import ArticleModel, FetchEnvelope, Metadata, Quality, RenderOptions, Section
from paper_fetch.providers import html_generic
from paper_fetch.utils import empty_asset_results


class StubProvider:
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

    def fetch_raw_fulltext(self, doi, metadata):
        if self._raw_error:
            raise self._raw_error
        return self._raw_payload

    def to_article_model(self, metadata, raw_payload, *, downloaded_assets=None, asset_failures=None):
        if self._article_factory is not None:
            return self._article_factory(
                metadata,
                raw_payload,
                downloaded_assets=downloaded_assets,
                asset_failures=asset_failures,
            )
        return self._article

    def download_related_assets(self, doi, metadata, raw_payload, output_dir, *, asset_profile="all"):
        if self._related_asset_error:
            raise self._related_asset_error
        if self._related_asset_factory is not None:
            return self._related_asset_factory(doi, metadata, raw_payload, output_dir, asset_profile=asset_profile)
        if self._related_assets is not None:
            return self._related_assets
        return empty_asset_results()


class StubHtmlClient:
    def __init__(self, article=None, error=None):
        self.article = article
        self.error = error

    def fetch_article_model(self, landing_url, *, metadata=None, expected_doi=None, download_dir=None, asset_profile="none"):
        if self.error:
            raise self.error
        return self.article


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
            raise html_generic.RequestFailure(404, f"Missing fixture response for {url}")
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
    allow_html_fallback: bool = True,
    allow_downloads: bool = True,
    asset_profile: str = "none",
    output_dir: Path | None = None,
    clients=None,
    html_client=None,
    transport=None,
    env=None,
) -> ArticleModel:
    envelope = paper_fetch.fetch_paper(
        query,
        modes={"article"},
        strategy=paper_fetch.FetchStrategy(
            allow_html_fallback=allow_html_fallback,
            allow_metadata_only_fallback=True,
            asset_profile=asset_profile,
        ),
        download_dir=output_dir if allow_downloads else None,
        clients=clients,
        html_client=html_client,
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
        quality=Quality(has_fulltext=True, token_estimate=600, warnings=[]),
    )


def sample_html_article() -> paper_fetch.ArticleModel:
    article = sample_article()
    article.source = "html_generic"
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
