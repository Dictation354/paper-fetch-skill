from __future__ import annotations

from pathlib import Path

from paper_fetch import service as paper_fetch
from paper_fetch.http import (
    DEFAULT_TIMEOUT_SECONDS,
    HttpRequestPolicy,
    HttpTransport,
    RequestFailure,
)
from paper_fetch.models import (
    ArticleModel,
    FetchEnvelope,
    Metadata,
    Quality,
    RenderOptions,
    Section,
    TokenEstimateBreakdown,
)
from paper_fetch.providers.base import (
    ProviderClient,
)
from paper_fetch.utils import empty_asset_results


class FixtureProvider(ProviderClient):
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
        provider_name = getattr(raw_payload, "provider", None)
        if not provider_name and isinstance(metadata, dict):
            provider_name = metadata.get("provider")
        self.name = str(provider_name or "provider")
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

    def to_article_model(
        self,
        metadata,
        raw_payload,
        *,
        downloaded_assets=None,
        asset_failures=None,
        context=None,
    ):
        del context
        if self._article_factory is not None:
            return self._article_factory(
                metadata,
                raw_payload,
                downloaded_assets=downloaded_assets,
                asset_failures=asset_failures,
            )
        return self._article

    def download_related_assets(
        self,
        doi,
        metadata,
        raw_payload,
        output_dir,
        *,
        asset_profile="all",
        context=None,
    ):
        del context
        if self._related_asset_error:
            raise self._related_asset_error
        if self._related_asset_factory is not None:
            return self._related_asset_factory(
                doi, metadata, raw_payload, output_dir, asset_profile=asset_profile
            )
        if self._related_assets is not None:
            return self._related_assets
        return empty_asset_results()


class FixtureHtmlTransport(HttpTransport):
    def __init__(self, responses):
        self.responses = responses
        self.calls: list[dict[str, object]] = []

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
        follow_redirects=True,
        max_redirects=5,
        allowed_hosts=None,
        max_response_bytes=None,
        max_compressed_response_bytes=None,
        request_policy: HttpRequestPolicy | None = None,
    ):
        policy = request_policy or HttpRequestPolicy(
            transient_backoff_base_seconds=transient_backoff_base_seconds,
            follow_redirects=follow_redirects,
            max_redirects=max_redirects,
            allowed_hosts=tuple(allowed_hosts) if allowed_hosts is not None else None,
            max_response_bytes=max_response_bytes,
            max_compressed_response_bytes=max_compressed_response_bytes,
        )
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "query": dict(query or {}),
                "timeout": timeout,
                "retry_on_rate_limit": retry_on_rate_limit,
                "rate_limit_retries": rate_limit_retries,
                "max_rate_limit_wait_seconds": max_rate_limit_wait_seconds,
                "retry_on_transient": retry_on_transient,
                "transient_retries": transient_retries,
                "transient_backoff_base_seconds": (
                    policy.transient_backoff_base_seconds
                ),
                "follow_redirects": policy.follow_redirects,
                "max_redirects": policy.max_redirects,
                "allowed_hosts": tuple(policy.allowed_hosts or ()),
                "max_response_bytes": policy.max_response_bytes,
                "max_compressed_response_bytes": (policy.max_compressed_response_bytes),
                "request_policy": policy,
            }
        )
        del (
            headers,
            query,
            timeout,
            retry_on_rate_limit,
            rate_limit_retries,
            max_rate_limit_wait_seconds,
            retry_on_transient,
            transient_retries,
            transient_backoff_base_seconds,
            follow_redirects,
            max_redirects,
            allowed_hosts,
            max_response_bytes,
            max_compressed_response_bytes,
            request_policy,
        )
        if url not in self.responses:
            raise RequestFailure(404, f"Missing fixture response for {url}")
        response = dict(self.responses[url])
        response.setdefault("status_code", 200)
        response.setdefault("headers", {})
        response.setdefault("url", url)
        return response


def http_response(
    url: str,
    body: bytes,
    content_type: str,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    response_headers = {"content-type": content_type}
    if headers is not None:
        response_headers.update(headers)
    return {
        "status_code": status_code,
        "headers": response_headers,
        "body": body,
        "url": url,
    }


class RecordingTransport(HttpTransport):
    def __init__(self, responses: dict[tuple[str, str], object]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def request(
        self,
        method,
        url,
        *,
        headers=None,
        query=None,
        timeout=None,
        retry_on_rate_limit=None,
        rate_limit_retries=None,
        max_rate_limit_wait_seconds=None,
        retry_on_transient=None,
        transient_retries=None,
        transient_backoff_base_seconds=0.5,
        follow_redirects=True,
        max_redirects=5,
        allowed_hosts=None,
        max_response_bytes=None,
        max_compressed_response_bytes=None,
        request_policy: HttpRequestPolicy | None = None,
    ):
        policy = request_policy or HttpRequestPolicy(
            transient_backoff_base_seconds=transient_backoff_base_seconds,
            follow_redirects=follow_redirects,
            max_redirects=max_redirects,
            allowed_hosts=tuple(allowed_hosts) if allowed_hosts is not None else None,
            max_response_bytes=max_response_bytes,
            max_compressed_response_bytes=max_compressed_response_bytes,
        )
        effective_timeout = int(
            timeout or policy.timeout_seconds or DEFAULT_TIMEOUT_SECONDS
        )
        effective_retry_on_rate_limit = (
            bool(policy.retry_on_rate_limit)
            if retry_on_rate_limit is None
            else bool(retry_on_rate_limit)
        )
        effective_rate_limit_retries = int(
            rate_limit_retries
            if rate_limit_retries is not None
            else policy.rate_limit_retries
            if policy.rate_limit_retries is not None
            else 1
        )
        effective_rate_limit_wait = int(
            max_rate_limit_wait_seconds
            if max_rate_limit_wait_seconds is not None
            else policy.max_rate_limit_wait_seconds
            if policy.max_rate_limit_wait_seconds is not None
            else 5
        )
        effective_retry_on_transient = (
            bool(policy.retry_on_transient)
            if retry_on_transient is None
            else bool(retry_on_transient)
        )
        effective_transient_retries = int(
            transient_retries
            if transient_retries is not None
            else policy.transient_retries
            if policy.transient_retries is not None
            else 2
        )
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "query": dict(query or {}),
                "timeout": effective_timeout,
                "retry_on_rate_limit": effective_retry_on_rate_limit,
                "rate_limit_retries": effective_rate_limit_retries,
                "max_rate_limit_wait_seconds": effective_rate_limit_wait,
                "retry_on_transient": effective_retry_on_transient,
                "transient_retries": effective_transient_retries,
                "transient_backoff_base_seconds": (
                    policy.transient_backoff_base_seconds
                ),
                "follow_redirects": policy.follow_redirects,
                "max_redirects": policy.max_redirects,
                "allowed_hosts": tuple(policy.allowed_hosts or ()),
                "max_response_bytes": policy.max_response_bytes,
                "max_compressed_response_bytes": (policy.max_compressed_response_bytes),
                "request_policy": policy,
            }
        )
        key = (method, url)
        if key not in self.responses:
            raise AssertionError(f"Missing fake response for {method} {url}")
        response = self.responses[key]
        if isinstance(response, list):
            if not response:
                raise AssertionError(f"No queued fake response left for {method} {url}")
            response = response.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def build_envelope(
    article: ArticleModel, *, include_markdown: bool = True
) -> FetchEnvelope:
    modes = {"article"}
    if include_markdown:
        modes.add("markdown")
    return paper_fetch.build_fetch_envelope(
        article, modes=modes, render=RenderOptions()
    )


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
    context = paper_fetch.RuntimeContext(
        env=env,
        transport=transport,
        clients=clients,
        download_dir=output_dir if allow_downloads else None,
    )
    envelope = paper_fetch.fetch_paper(
        query,
        modes={"article"},
        strategy=paper_fetch.FetchStrategy(
            allow_metadata_only_fallback=True,
            asset_profile=asset_profile,
        ),
        context=context,
    )
    assert envelope.article is not None
    return envelope.article


def sample_article(doi: str = "10.1016/test") -> paper_fetch.ArticleModel:
    return ArticleModel(
        doi=doi,
        source="elsevier_xml",
        metadata=Metadata(
            title="Example Article",
            authors=["Alice Example", "Bob Example"],
            abstract="Example abstract",
            journal="Example Journal",
            published="2026-01-01",
        ),
        sections=[
            Section(
                heading="Introduction",
                level=2,
                kind="body",
                text="Introduction text " * 30,
            ),
            Section(
                heading="Discussion", level=2, kind="body", text="Discussion text " * 30
            ),
        ],
        references=[],
        assets=[],
        quality=Quality(
            has_fulltext=True,
            token_estimate=600,
            warnings=[],
            token_estimate_breakdown=TokenEstimateBreakdown(
                abstract=120, body=480, refs=64
            ),
        ),
    )


def sample_html_article() -> paper_fetch.ArticleModel:
    article = sample_article()
    article.source = "springer_html"
    return article


def build_pdf_bytes(lines: list[str]) -> bytes:
    import fitz

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
