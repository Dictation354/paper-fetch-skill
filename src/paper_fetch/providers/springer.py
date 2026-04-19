"""Springer HTML provider client."""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Any, Mapping

from ..config import build_user_agent
from ..http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, HttpTransport, RequestFailure, build_text_preview
from ..metadata_types import ProviderMetadata
from ..models import AssetProfile, article_from_markdown, metadata_only_article
from ..publisher_identity import normalize_doi
from ..utils import (
    build_output_path,
    choose_public_landing_page_url,
    empty_asset_results,
    normalize_text,
    save_payload,
)
from . import html_generic
from ._html_tables import inject_inline_table_blocks, render_table_markdown, table_placeholder
from ._pdf_candidates import build_springer_pdf_candidates
from ._pdf_fallback import PdfFetchFailure, fetch_pdf_over_http
from ._html_availability import assess_html_fulltext_availability, availability_failure_message
from .base import (
    ProviderClient,
    ProviderFailure,
    ProviderStatusResult,
    RawFulltextPayload,
    build_provider_status_check,
    combine_provider_failures,
    map_request_failure,
    summarize_capability_status,
)

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

MAX_SPRINGER_HTML_REDIRECTS = 5
SPRINGER_TABLE_LABEL_PATTERN = re.compile(r"\btable\.?\s*(\d+[A-Za-z]?)\b", flags=re.IGNORECASE)
SPRINGER_INLINE_TABLE_SELECTORS = (
    "[data-test='inline-table']",
    ".c-article-table",
)
SPRINGER_TABLE_LINK_SELECTORS = (
    "a[data-test='table-link']",
    "a[href*='/tables/']",
)
SPRINGER_TABLE_CAPTION_SELECTORS = (
    "[data-test='table-caption']",
    ".c-article-table__figcaption",
    "figcaption",
    "header",
)
def _springer_short_text(node: Tag | BeautifulSoup | None) -> str:
    if node is None:
        return ""
    return normalize_text(node.get_text(" ", strip=True))


def _springer_strip_table_label(text: str, label: str) -> str:
    label_text = normalize_text(label).rstrip(".")
    if not label_text:
        return normalize_text(text)
    stripped = re.sub(rf"^{re.escape(label_text)}\.?\s*", "", text, flags=re.IGNORECASE)
    return normalize_text(stripped).lstrip(".:;,-) ]")


def _springer_table_label(node: Tag | BeautifulSoup, *, fallback: str = "Table") -> str:
    for selector in SPRINGER_TABLE_CAPTION_SELECTORS:
        candidate = node.select_one(selector)
        if isinstance(candidate, Tag):
            text = _springer_short_text(candidate)
            match = SPRINGER_TABLE_LABEL_PATTERN.search(text)
            if match:
                return f"Table {match.group(1)}."
    if isinstance(node, BeautifulSoup) and isinstance(node.title, Tag):
        match = SPRINGER_TABLE_LABEL_PATTERN.search(_springer_short_text(node.title))
        if match:
            return f"Table {match.group(1)}."
    match = SPRINGER_TABLE_LABEL_PATTERN.search(_springer_short_text(node))
    if match:
        return f"Table {match.group(1)}."
    return fallback


def _springer_table_caption(node: Tag | BeautifulSoup, label: str) -> str:
    for selector in SPRINGER_TABLE_CAPTION_SELECTORS:
        candidate = node.select_one(selector)
        if isinstance(candidate, Tag):
            text = _springer_strip_table_label(_springer_short_text(candidate), label)
            if text:
                return text
    if isinstance(node, BeautifulSoup) and isinstance(node.title, Tag):
        text = _springer_strip_table_label(_springer_short_text(node.title), label)
        if text:
            return text
    return ""


def _springer_inline_table_nodes(soup: BeautifulSoup) -> list[Tag]:
    nodes: list[Tag] = []
    seen: set[int] = set()
    for selector in SPRINGER_INLINE_TABLE_SELECTORS:
        try:
            matches = soup.select(selector)
        except Exception:
            continue
        for match in matches:
            if not isinstance(match, Tag) or id(match) in seen:
                continue
            seen.add(id(match))
            nodes.append(match)
    return nodes


class SpringerClient(ProviderClient):
    name = "springer"

    def __init__(self, transport: HttpTransport, env: Mapping[str, str]) -> None:
        self.transport = transport
        self.user_agent = build_user_agent(env)

    def probe_status(self) -> ProviderStatusResult:
        return summarize_capability_status(
            self.name,
            official_provider=self.official_provider,
            checks=[
                build_provider_status_check(
                    "html_route",
                    "ok",
                    "Springer direct HTML route is available.",
                    details={"mode": "direct_html"},
                ),
            ],
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": self.user_agent,
        }

    def _fetch_html_response(self, landing_url: str) -> tuple[dict[str, Any], str]:
        current_url = landing_url
        try:
            response = self.transport.request(
                "GET",
                current_url,
                headers=self._headers(),
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_transient=True,
            )
            for _ in range(MAX_SPRINGER_HTML_REDIRECTS):
                response_url = urllib.parse.urljoin(current_url, str(response.get("url") or "").strip() or current_url)
                status_code = int(response.get("status_code") or 0)
                redirect_location = str((response.get("headers") or {}).get("location") or "").strip()
                if status_code not in {301, 302, 303, 307, 308} or not redirect_location:
                    return response, response_url
                current_url = urllib.parse.urljoin(response_url, redirect_location)
                response = self.transport.request(
                    "GET",
                    current_url,
                    headers=self._headers(),
                    timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                    retry_on_transient=True,
                )
        except RequestFailure as exc:
            raise map_request_failure(exc) from exc
        raise ProviderFailure(
            "error",
            f"Springer direct HTML retrieval exceeded {MAX_SPRINGER_HTML_REDIRECTS} redirects.",
        )

    def _render_table_page_markdown(
        self,
        table_url: str,
        *,
        fallback_label: str,
    ) -> tuple[str | None, str | None]:
        try:
            response, _response_url = self._fetch_html_response(table_url)
        except ProviderFailure as exc:
            return (
                None,
                f"Springer inline table supplement for {fallback_label} could not be fetched ({exc.code}: {exc.message}).",
            )

        if BeautifulSoup is None:
            return None, f"Springer inline table supplement for {fallback_label} requires BeautifulSoup."

        table_html = html_generic.decode_html(response["body"])
        soup = BeautifulSoup(table_html, "html.parser")
        table = soup.select_one(".c-article-table-container table, table")
        if not isinstance(table, Tag):
            return None, f"Springer inline table supplement for {fallback_label} did not include a table element."

        container = table.find_parent("figure")
        if not isinstance(container, Tag):
            container = table.find_parent("div", attrs={"data-container-section": "table"})
        label = _springer_table_label(container or soup, fallback=fallback_label)
        caption = _springer_table_caption(container or soup, label)
        markdown = render_table_markdown(table, label=label, caption=caption)
        if not normalize_text(markdown):
            return None, f"Springer inline table supplement for {label} did not produce Markdown content."
        return markdown, None

    def _prepare_html_with_inline_tables(
        self,
        html_text: str,
        source_url: str,
    ) -> tuple[str, list[dict[str, str]], list[str]]:
        if BeautifulSoup is None:
            return html_text, [], []

        soup = BeautifulSoup(html_text, "html.parser")
        table_entries: list[dict[str, str]] = []
        warnings: list[str] = []

        for node in _springer_inline_table_nodes(soup):
            if not isinstance(node, Tag) or node.parent is None:
                continue
            label = _springer_table_label(node)
            table_url = ""
            for selector in SPRINGER_TABLE_LINK_SELECTORS:
                link = node.select_one(selector)
                if isinstance(link, Tag):
                    table_url = urllib.parse.urljoin(source_url, str(link.get("href") or "").strip())
                    if table_url:
                        break
            if not table_url:
                warnings.append(f"Springer inline table supplement for {label} was skipped because no table page link was found.")
                node.decompose()
                continue

            markdown, warning = self._render_table_page_markdown(table_url, fallback_label=label)
            if warning:
                warnings.append(warning)
                node.decompose()
                continue
            if not markdown:
                node.decompose()
                continue

            placeholder = table_placeholder(len(table_entries) + 1)
            block = soup.new_tag("p")
            block.string = placeholder
            node.replace_with(block)
            table_entries.append({"placeholder": placeholder, "markdown": markdown})

        return str(soup), table_entries, warnings

    def fetch_metadata(self, query: Mapping[str, str | None]) -> ProviderMetadata:
        raise ProviderFailure(
            "not_supported",
            "Springer publisher metadata is taken from Crossref; the runtime does not use Springer publisher endpoints.",
        )

    def fetch_fulltext(self, doi: str, metadata: ProviderMetadata, output_dir: Path | None) -> dict[str, Any]:
        payload = self.fetch_raw_fulltext(doi, metadata)
        normalized_doi = normalize_doi(doi)
        output_path = build_output_path(output_dir, normalized_doi, metadata.get("title"), payload.content_type, payload.source_url)
        saved_path = save_payload(output_path, payload.body)
        asset_results = self.download_related_assets(normalized_doi, metadata, payload, output_dir)
        markdown_path = None
        return {
            "attempted": True,
            "status": "saved" if output_path else "fetched",
            "provider": "springer",
            "official_provider": True,
            "source_url": payload.source_url,
            "content_type": payload.content_type,
            "path": saved_path,
            "markdown_path": markdown_path,
            "downloaded_bytes": len(payload.body),
            "content_preview": build_text_preview(payload.body, payload.content_type),
            "reason": str(payload.metadata.get("reason") or "Downloaded full text from the Springer landing page HTML."),
            **asset_results,
        }

    def download_related_assets(
        self,
        doi: str,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        output_dir: Path | None,
        *,
        asset_profile: AssetProfile = "all",
    ) -> dict[str, list[dict[str, Any]]]:
        if output_dir is None or asset_profile == "none":
            return empty_asset_results()
        if str(raw_payload.metadata.get("route") or "").strip().lower() == "pdf_fallback":
            return empty_asset_results()
        article_assets = list(raw_payload.metadata.get("extracted_assets") or [])
        if not article_assets:
            html_text = html_generic.decode_html(raw_payload.body)
            article_assets = html_generic.extract_html_assets(
                html_text,
                raw_payload.source_url,
                asset_profile=asset_profile,
            )
        if not article_assets:
            return empty_asset_results()
        article_id = (
            normalize_doi(str((raw_payload.metadata.get("merged_metadata") or {}).get("doi") or doi or ""))
            or normalize_doi(doi)
            or normalize_doi(str(metadata.get("doi") or ""))
            or normalize_text(str(metadata.get("title") or ""))
            or raw_payload.source_url
        )
        return html_generic.download_figure_assets(
            self.transport,
            article_id=article_id,
            assets=article_assets,
            output_dir=output_dir,
            user_agent=self.user_agent,
            asset_profile=asset_profile,
        )

    def fetch_raw_fulltext(self, doi: str, metadata: ProviderMetadata) -> RawFulltextPayload:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            raise ProviderFailure("not_supported", "Springer direct HTML retrieval requires a DOI.")

        landing_url = choose_public_landing_page_url(
            metadata.get("landing_page_url"),
            f"https://doi.org/{urllib.parse.quote(normalized_doi, safe='')}",
        )
        warnings: list[str] = []
        response_url = landing_url
        html_text: str | None = None
        merged_metadata = dict(metadata)
        html_failure: ProviderFailure | None = None

        try:
            response, response_url = self._fetch_html_response(landing_url)
            html_text = html_generic.decode_html(response["body"])
            html_metadata = html_generic.parse_html_metadata(html_text, response_url)
            merged_metadata = html_generic.merge_html_metadata(metadata, html_metadata)
            if not merged_metadata.get("doi"):
                merged_metadata["doi"] = normalized_doi
            prepared_html, table_entries, table_warnings = self._prepare_html_with_inline_tables(html_text, response_url)
            markdown_text = html_generic.clean_markdown(html_generic.extract_article_markdown(prepared_html, response_url))
            markdown_text = inject_inline_table_blocks(
                markdown_text,
                table_entries=table_entries,
                clean_markdown_fn=html_generic.clean_markdown,
            )
            warnings.extend(table_warnings)
            diagnostics = assess_html_fulltext_availability(
                markdown_text,
                merged_metadata,
                provider=self.name,
                html_text=html_text,
                title=str(merged_metadata.get("title") or ""),
                requested_url=landing_url,
                final_url=response_url,
                response_status=int(response.get("status_code") or 0) or None,
            )
            if diagnostics.accepted:
                extracted_assets = html_generic.extract_html_assets(html_text, response_url, asset_profile="all")
                return RawFulltextPayload(
                    provider="springer",
                    source_url=response_url,
                    content_type=response["headers"].get("content-type", "text/html"),
                    body=response["body"],
                    metadata={
                        "route": "html",
                        "reason": "Downloaded full text from the Springer landing page HTML.",
                        "merged_metadata": merged_metadata,
                        "markdown_text": markdown_text,
                        "warnings": warnings,
                        "availability_diagnostics": diagnostics.to_dict(),
                        "extracted_assets": extracted_assets,
                        "source_trail": ["fulltext:springer_html_ok"],
                    },
                    needs_local_copy=False,
                )
            html_failure = ProviderFailure(
                "no_result",
                availability_failure_message(diagnostics),
                source_trail=["fulltext:springer_html_fail"],
            )
        except ProviderFailure as exc:
            html_failure = ProviderFailure(
                exc.code,
                exc.message,
                retry_after_seconds=exc.retry_after_seconds,
                missing_env=exc.missing_env,
                warnings=exc.warnings,
                source_trail=[*exc.source_trail, "fulltext:springer_html_fail"],
            )

        assert html_failure is not None
        warnings.extend(html_failure.warnings)
        warnings.append(f"Springer HTML route was not usable ({html_failure.message}); attempting PDF fallback.")

        pdf_candidates = build_springer_pdf_candidates(
            normalized_doi,
            merged_metadata,
            html_text=html_text,
            source_url=response_url,
        )
        try:
            pdf_result = fetch_pdf_over_http(
                self.transport,
                pdf_candidates,
                headers={
                    "User-Agent": self.user_agent,
                    "Referer": response_url,
                },
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                seed_urls=[response_url] if response_url else None,
            )
        except PdfFetchFailure as exc:
            pdf_failure = ProviderFailure(
                "no_result",
                (
                    "Springer full text could not be retrieved via HTML or PDF fallback. "
                    f"HTML failure: {html_failure.message} PDF failure: {exc.message}"
                ),
                warnings=warnings,
                source_trail=["fulltext:springer_html_fail"],
            )
            raise combine_provider_failures([("html", html_failure), ("pdf", pdf_failure)]) from exc

        return RawFulltextPayload(
            provider="springer",
            source_url=pdf_result.final_url,
            content_type="application/pdf",
            body=pdf_result.pdf_bytes,
            metadata={
                "route": "pdf_fallback",
                "reason": "Downloaded full text from the Springer direct PDF fallback route.",
                "merged_metadata": merged_metadata,
                "markdown_text": pdf_result.markdown_text,
                "warnings": [
                    *warnings,
                    "Full text was extracted from PDF fallback after the Springer HTML path was not usable.",
                ],
                "html_failure_message": html_failure.message,
                "source_trail": [
                    "fulltext:springer_html_fail",
                    "fulltext:springer_pdf_fallback_ok",
                ],
                "suggested_filename": pdf_result.suggested_filename,
            },
            needs_local_copy=True,
        )

    def to_article_model(
        self,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ):
        merged_metadata = raw_payload.metadata.get("merged_metadata")
        article_metadata = merged_metadata if isinstance(merged_metadata, Mapping) else metadata
        doi = normalize_doi(article_metadata.get("doi") or metadata.get("doi"))
        markdown_text = str(raw_payload.metadata.get("markdown_text") or "").strip()
        route = str(raw_payload.metadata.get("route") or "").strip().lower()
        warnings = [str(item) for item in raw_payload.metadata.get("warnings") or [] if str(item).strip()]
        source_trail = [str(item) for item in raw_payload.metadata.get("source_trail") or [] if str(item).strip()]
        if not source_trail:
            source_trail = ["fulltext:springer_html_ok"]
        assets = list(downloaded_assets or [])
        if not markdown_text:
            warnings.append(
                "Springer PDF fallback did not produce usable Markdown."
                if route == "pdf_fallback"
                else "Springer HTML retrieval did not produce usable Markdown."
            )
            return metadata_only_article(
                source="springer_html",
                metadata=article_metadata,
                doi=doi or None,
                warnings=warnings,
                source_trail=source_trail,
            )
        if asset_failures:
            warnings.append(f"Springer related assets were only partially downloaded ({len(asset_failures)} failed).")
        return article_from_markdown(
            source="springer_html",
            metadata=article_metadata,
            doi=doi or None,
            markdown_text=markdown_text,
            assets=assets,
            warnings=warnings,
            source_trail=source_trail,
        )
