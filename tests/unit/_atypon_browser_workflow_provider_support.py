# ruff: noqa: F401
from __future__ import annotations

import json
import tempfile
import urllib.parse
import unittest
from pathlib import Path
from collections.abc import Mapping
from unittest import mock

from paper_fetch.http import RequestFailure
from paper_fetch.extraction.html import assets as html_assets
from paper_fetch.extraction.image_payloads import image_mime_type_from_bytes
from paper_fetch.providers import (
    acs as acs_provider,
    browser_runtime,
    ams as ams_provider,
    browser_workflow,
    pnas as pnas_provider,
    science as science_provider,
    wiley as wiley_provider,
)
from paper_fetch.providers.atypon_browser_workflow import (
    asset_scopes as atypon_browser_workflow_asset_scopes,
)
from paper_fetch.quality.html_availability import assess_html_fulltext_availability
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.tracing import trace_from_markers
from tests.block_fixtures import block_asset
from tests.golden_criteria import (
    golden_criteria_asset,
    golden_criteria_dir_for_doi,
    golden_criteria_scenario_asset,
)
from tests.provider_benchmark_samples import provider_benchmark_sample
from tests.unit._browser_workflow_deps import (
    browser_workflow_deps,
    install_browser_workflow_deps,
)
from tests.unit._paper_fetch_support import fulltext_pdf_bytes


SCIENCE_SAMPLE = provider_benchmark_sample("science")
PNAS_SAMPLE = provider_benchmark_sample("pnas")
WILEY_REGRESSION_FIXTURE = golden_criteria_asset("10.1111/gcb.16998", "original.html")
PNAS_REGRESSION_FIXTURE = golden_criteria_asset(
    "10.1073/pnas.2309123120", "original.html"
)
PNAS_COMMENTARY_FIXTURE = golden_criteria_asset(
    "10.1073/pnas.2317456120", "commentary.html"
)
SCIENCE_FRONTMATTER_REGRESSION_FIXTURE = golden_criteria_asset(
    "10.1126/science.abp8622", "original.html"
)
SCIENCE_DATALAYER_AUTHOR_FIXTURE = golden_criteria_asset(
    "10.1126/science.adp0212", "original.html"
)
SCIENCE_PAYWALL_SAMPLE_RAW = block_asset("10.1126/science.aeg3511", "raw.html")
SCIENCE_PAYWALL_SAMPLE_MARKDOWN = block_asset("10.1126/science.aeg3511", "extracted.md")
SCIENCE_FULLTEXT_FALLBACK_MARKDOWN = golden_criteria_asset(
    "10.1126/science.aeg3511", "extracted.md"
)
SCIENCE_ADL6155_ROOT_CAUSE_FIXTURE = golden_criteria_asset(
    "10.1126/sciadv.adl6155", "original.html"
)
SCIENCE_ADL6155_METADATA = golden_criteria_asset(
    "10.1126/sciadv.adl6155", "article.json"
)
SCIENCE_ADL6155_ASSET_DIR = (
    golden_criteria_dir_for_doi("10.1126/sciadv.adl6155") / "body_assets"
)
SCIENCE_ADZ3492_SVG_ASSET = (
    golden_criteria_dir_for_doi("10.1126/science.adz3492")
    / "body_assets"
    / "science.adz3492-f1.svg"
)
PNAS_PAYWALL_SAMPLE_RAW = block_asset("10.1073/pnas.2509692123", "raw.html")
PNAS_PAYWALL_SAMPLE_MARKDOWN = block_asset("10.1073/pnas.2509692123", "extracted.md")
PNAS_FULLTEXT_FALLBACK_MARKDOWN = golden_criteria_asset(
    "10.1073/pnas.2406303121", "extracted.md"
)
WILEY_2004GB002273_ROOT_CAUSE_FIXTURE = golden_criteria_asset(
    "10.1029/2004GB002273", "original.html"
)
WILEY_2004GB002273_METADATA = golden_criteria_asset(
    "10.1029/2004GB002273", "article.json"
)
WILEY_2004GB002273_ASSET_DIR = (
    golden_criteria_dir_for_doi("10.1029/2004GB002273") / "body_assets"
)


def png_header(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x06"
    )


def _typed_raw_payload(
    *,
    provider: str,
    source_url: str,
    content_type: str,
    body: bytes,
    route: str,
    markdown_text: str | None = None,
    source_trail: list[str] | None = None,
    extraction: Mapping[str, object] | None = None,
    availability_diagnostics: Mapping[str, object] | None = None,
    browser_context_seed: Mapping[str, object] | None = None,
    suggested_filename: str | None = None,
) -> RawFulltextPayload:
    diagnostics: dict[str, object] = {}
    if extraction is not None:
        diagnostics["extraction"] = dict(extraction)
    if availability_diagnostics is not None:
        diagnostics["availability_diagnostics"] = dict(availability_diagnostics)
    return RawFulltextPayload(
        provider=provider,
        source_url=source_url,
        content_type=content_type,
        body=body,
        content=ProviderContent(
            route_kind=route,
            source_url=source_url,
            content_type=content_type,
            body=body,
            markdown_text=markdown_text,
            diagnostics=diagnostics,
            browser_context_seed=dict(browser_context_seed or {}),
            suggested_filename=suggested_filename,
        ),
        trace=trace_from_markers(source_trail or []),
    )


def _payload_route(raw_payload: RawFulltextPayload) -> str | None:
    return raw_payload.content.route_kind if raw_payload.content is not None else None


def _payload_source_trail(raw_payload: RawFulltextPayload) -> list[str]:
    return [event.marker() for event in raw_payload.trace if event.marker()]


class AssetTransport:
    def __init__(
        self, responses: dict[tuple[str, str], dict[str, object] | Exception]
    ) -> None:
        self.responses = responses
        # Empty mappings model a publisher/CDN access gate for browser-recovery
        # tests. Non-empty mappings remain strict so unexpected candidates fail.
        self.missing_requests_are_access_gated = not responses
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
        request_policy=None,
    ):
        if request_policy is not None:
            timeout = request_policy.timeout_seconds
            retry_on_rate_limit = request_policy.retry_on_rate_limit
            retry_on_transient = request_policy.retry_on_transient
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "query": dict(query or {}),
                "timeout": timeout,
                "retry_on_rate_limit": retry_on_rate_limit,
                "retry_on_transient": retry_on_transient,
            }
        )
        key = (method, url)
        if key not in self.responses:
            if self.missing_requests_are_access_gated:
                raise RequestFailure(
                    403,
                    f"HTTP 403 access gate for {url}",
                    body=b"<html>Access denied</html>",
                    headers={"content-type": "text/html"},
                    url=url,
                )
            raise AssertionError(f"Missing fake response for {method} {url}")
        response = self.responses[key]
        if isinstance(response, Exception):
            raise response
        return response


class AtyponBrowserWorkflowProviderTestCase(unittest.TestCase):
    def assert_direct_asset_attempted(self, transport: AssetTransport) -> None:
        self.assertGreaterEqual(len(transport.calls), 1)
        self.assertTrue(
            all(call.get("method") == "GET" for call in transport.calls),
            transport.calls,
        )

    def _metadata_from_golden_criteria(
        self, article_path: Path, doi: str
    ) -> dict[str, object]:
        article_payload = json.loads(article_path.read_text(encoding="utf-8"))
        metadata = dict(article_payload.get("metadata") or {})
        metadata["doi"] = doi
        metadata["references"] = list(article_payload.get("references") or [])
        return metadata

    def _map_local_assets_by_basename(
        self,
        extracted_assets: list[dict[str, object]],
        *,
        asset_dir: Path,
    ) -> list[dict[str, object]]:
        local_by_name = {
            path.name: str(path.resolve())
            for path in asset_dir.iterdir()
            if path.is_file()
        }
        downloaded_assets: list[dict[str, object]] = []
        for asset in extracted_assets:
            candidate_names: list[str] = []
            for field in (
                "full_size_url",
                "url",
                "preview_url",
                "figure_page_url",
                "source_url",
            ):
                raw_value = str(asset.get(field) or "").strip()
                if not raw_value:
                    continue
                parsed = urllib.parse.urlparse(
                    raw_value
                    if not raw_value.startswith("//")
                    else f"https:{raw_value}"
                )
                basename = Path(urllib.parse.unquote(parsed.path)).name
                if basename:
                    candidate_names.append(basename)
                    if "." not in basename:
                        candidate_names.append(f"{basename}.html")
            local_path = next(
                (
                    local_by_name[name]
                    for name in candidate_names
                    if name in local_by_name
                ),
                None,
            )
            if not local_path:
                continue
            downloaded_asset = dict(asset)
            downloaded_asset["path"] = local_path
            downloaded_assets.append(downloaded_asset)
        return downloaded_assets

    def _runtime_config(
        self, tmpdir: str, provider: str, doi: str
    ) -> browser_runtime.BrowserRuntimeConfig:
        tmp = Path(tmpdir)
        return browser_runtime.BrowserRuntimeConfig(
            provider=provider,
            doi=doi,
            artifact_dir=tmp / "artifacts",
            headless=True,
            user_agent="paper-fetch-test/1",
        )

    def _build_browser_html_raw_payload(
        self,
        client,
        *,
        html: str,
        landing_url: str,
        extraction_metadata: Mapping[str, object],
        source_trail: list[str] | None = None,
    ) -> tuple[str, dict[str, object], RawFulltextPayload]:
        markdown_text, extraction = client.extract_markdown(
            html,
            landing_url,
            metadata=extraction_metadata,
        )
        raw_payload = _typed_raw_payload(
            provider=client.name,
            source_url=landing_url,
            content_type="text/html",
            body=html.encode("utf-8"),
            route="html",
            markdown_text=markdown_text,
            source_trail=list(source_trail or [f"fulltext:{client.name}_html_ok"]),
            extraction=extraction,
        )
        return markdown_text, extraction, raw_payload

    def _build_browser_fixture_article(
        self,
        client,
        *,
        html: str,
        landing_url: str,
        article_metadata: Mapping[str, object],
        extraction_metadata: Mapping[str, object] | None = None,
        downloaded_assets: list[dict[str, object]] | None = None,
        asset_failures: list[dict[str, object]] | None = None,
        source_trail: list[str] | None = None,
    ):
        _, extraction, raw_payload = self._build_browser_html_raw_payload(
            client,
            html=html,
            landing_url=landing_url,
            extraction_metadata=extraction_metadata or article_metadata,
            source_trail=source_trail,
        )
        article = client.to_article_model(
            dict(article_metadata),
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )
        return article, extraction, raw_payload

    def _assert_provider_owned_author_case(
        self,
        *,
        client,
        html_fixture: Path,
        doi: str,
        title: str,
        landing_url: str,
        expected_authors: list[str],
    ) -> None:
        article, _, _ = self._build_browser_fixture_article(
            client,
            html=html_fixture.read_text(encoding="utf-8"),
            landing_url=landing_url,
            article_metadata={"doi": doi, "title": title, "authors": []},
            extraction_metadata={"doi": doi, "title": title},
        )
        self.assertEqual(
            article.metadata.authors[: len(expected_authors)], expected_authors
        )


__all__ = [name for name in globals() if not name.startswith("__")]
