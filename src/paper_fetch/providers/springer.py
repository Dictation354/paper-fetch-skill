"""Springer HTML provider client."""

from __future__ import annotations

from dataclasses import dataclass
import re
import urllib.parse
from pathlib import Path
from typing import Any, Mapping

from ..config import build_user_agent
from ..http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, HttpTransport, RequestFailure, build_text_preview
from ..metadata_types import ProviderMetadata
from ..models import AssetProfile, article_from_markdown, metadata_only_article
from ..publisher_identity import normalize_doi
from ..tracing import merge_trace, source_trail_from_trace, trace_from_markers
from ..utils import (
    build_output_path,
    choose_public_landing_page_url,
    dedupe_authors,
    empty_asset_results,
    extend_unique,
    normalize_text,
    save_payload,
)
from . import _springer_html
from ._science_pnas_html import rewrite_inline_figure_links
from ._html_tables import inject_inline_table_blocks, render_table_markdown, table_placeholder
from .html_assets import html_asset_identity_key
from ._pdf_candidates import build_springer_pdf_candidates
from ._pdf_fallback import PdfFetchFailure, fetch_pdf_over_http
from ._html_availability import assess_html_fulltext_availability, availability_failure_message
from .base import (
    ProviderArtifacts,
    ProviderClient,
    ProviderContent,
    ProviderFailure,
    ProviderFetchResult,
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
MARKDOWN_TEXT_KEY = "markdown_text"
SPRINGER_TABLE_LABEL_PATTERN = re.compile(
    r"\b(?P<prefix>extended\s+data\s+table|table)\.?\s*(?P<number>\d+[A-Za-z]?)\b",
    flags=re.IGNORECASE,
)
SPRINGER_IMAGE_URL_PATTERN = re.compile(r"\.(?:avif|gif|jpe?g|png|tiff?|webp)(?:[?#]|$)", flags=re.IGNORECASE)
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
    ".c-article-satellite-title",
    "figcaption",
)


@dataclass
class SpringerHtmlAttempt:
    normalized_doi: str
    landing_url: str
    response: Mapping[str, Any]
    response_url: str
    html_text: str
    merged_metadata: dict[str, Any]
    warnings: list[str]
    markdown_text: str
    abstract_sections: list[dict[str, Any]]
    section_hints: list[dict[str, Any]]
    extracted_authors: list[str]
    extracted_references: list[dict[str, Any]]
    inline_table_assets: list[dict[str, Any]]
    diagnostics: Any


def _merge_springer_assets(
    extracted_assets: list[Mapping[str, Any]] | None,
    downloaded_assets: list[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    by_identity: dict[str, dict[str, Any]] = {}

    for item in extracted_assets or []:
        asset = dict(item)
        merged.append(asset)
        identity = html_asset_identity_key(asset)
        if identity:
            by_identity[identity] = asset

    for item in downloaded_assets or []:
        asset = dict(item)
        identity = html_asset_identity_key(asset)
        existing = by_identity.get(identity) if identity else None
        if existing is not None:
            existing.update(asset)
            continue
        merged.append(asset)
        if identity:
            by_identity[identity] = asset

    return merged


def _filter_springer_assets_for_profile(
    assets: list[Mapping[str, Any]] | None,
    *,
    asset_profile: AssetProfile,
) -> list[dict[str, Any]]:
    if asset_profile == "none":
        return []

    filtered: list[dict[str, Any]] = []
    for item in assets or []:
        asset = dict(item)
        if asset_profile != "all":
            kind = normalize_text(str(asset.get("kind") or "")).lower()
            section = normalize_text(str(asset.get("section") or "")).lower()
            if kind == "supplementary" or section in {"supplementary", "appendix"}:
                continue
        filtered.append(asset)
    return filtered


def _springer_extraction_diagnostics_payload(attempt: SpringerHtmlAttempt) -> dict[str, Any]:
    return {
        "availability_diagnostics": attempt.diagnostics.to_dict(),
        "extraction": {
            "abstract_text": normalize_text(attempt.abstract_sections[0]["text"]) if attempt.abstract_sections else None,
            "abstract_sections": list(attempt.abstract_sections),
            "section_hints": list(attempt.section_hints),
            "extracted_authors": list(attempt.extracted_authors),
            "references": list(attempt.extracted_references),
            "inline_table_assets": list(attempt.inline_table_assets),
        },
    }


def _springer_html_payload_from_attempt(
    attempt: SpringerHtmlAttempt,
    *,
    trace_markers: list[str],
    reason: str,
    extracted_assets: list[dict[str, Any]] | None = None,
) -> RawFulltextPayload:
    content_type = attempt.response.get("headers", {}).get("content-type", "text/html")
    return RawFulltextPayload(
        provider="springer",
        source_url=attempt.response_url,
        content_type=content_type,
        body=attempt.response["body"],
        content=ProviderContent(
            route_kind="html",
            source_url=attempt.response_url,
            content_type=content_type,
            body=attempt.response["body"],
            markdown_text=attempt.markdown_text,
            merged_metadata=dict(attempt.merged_metadata),
            diagnostics=_springer_extraction_diagnostics_payload(attempt),
            reason=reason,
            extracted_assets=[dict(item) for item in (extracted_assets or [])],
        ),
        warnings=list(attempt.warnings),
        trace=trace_from_markers(trace_markers),
        merged_metadata=attempt.merged_metadata,
        needs_local_copy=False,
    )


def _finalize_springer_abstract_only_article(article, *, warnings: list[str] | None = None):
    article.quality.trace = merge_trace(article.quality.trace, trace_from_markers(["fulltext:springer_abstract_only"]))
    article.quality.source_trail = source_trail_from_trace(article.quality.trace)
    extend_unique(article.quality.warnings, list(warnings or []))
    return article


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
                prefix = "Extended Data Table" if "extended" in match.group("prefix").lower() else "Table"
                return f"{prefix} {match.group('number')}."
    if isinstance(node, BeautifulSoup) and isinstance(node.title, Tag):
        match = SPRINGER_TABLE_LABEL_PATTERN.search(_springer_short_text(node.title))
        if match:
            prefix = "Extended Data Table" if "extended" in match.group("prefix").lower() else "Table"
            return f"{prefix} {match.group('number')}."
    match = SPRINGER_TABLE_LABEL_PATTERN.search(_springer_short_text(node))
    if match:
        prefix = "Extended Data Table" if "extended" in match.group("prefix").lower() else "Table"
        return f"{prefix} {match.group('number')}."
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


def _springer_table_label_heading(label: str) -> str:
    return normalize_text(label).rstrip(".") or "Table"


def _springer_is_nature13376_extended_table(normalized_doi: str, label: str) -> bool:
    if normalize_doi(normalized_doi) != "10.1038/nature13376":
        return False
    normalized_label = normalize_text(label).lower().rstrip(".")
    return bool(re.match(r"^extended data table [1-4]\b", normalized_label))


def _springer_response_content_type(response: Mapping[str, Any]) -> str:
    headers = response.get("headers") or {}
    if not isinstance(headers, Mapping):
        return ""
    return normalize_text(str(headers.get("content-type") or headers.get("Content-Type") or ""))


def _springer_looks_like_image_response(response: Mapping[str, Any], response_url: str) -> bool:
    content_type = _springer_response_content_type(response).lower()
    if content_type.startswith("image/"):
        return True
    return bool(SPRINGER_IMAGE_URL_PATTERN.search(normalize_text(response_url)))


def _springer_table_image_asset(
    *,
    label: str,
    caption: str,
    image_url: str,
    page_url: str,
) -> dict[str, Any]:
    heading = _springer_table_label_heading(label)
    asset = {
        "kind": "table",
        "heading": heading,
        "caption": normalize_text(caption),
        "url": image_url,
        "section": "body",
    }
    if image_url:
        asset["full_size_url"] = image_url
    if page_url and page_url != image_url:
        asset["figure_page_url"] = page_url
    return asset


def _springer_table_image_markdown(asset: Mapping[str, Any], *, label: str) -> str:
    heading = normalize_text(str(asset.get("heading") or "")) or _springer_table_label_heading(label)
    image_url = normalize_text(str(asset.get("url") or asset.get("full_size_url") or ""))
    caption = normalize_text(str(asset.get("caption") or ""))
    if not image_url:
        return ""
    lines = [f"![{heading}]({image_url})"]
    label_text = normalize_text(label) or f"{heading}."
    caption_line = f"**{label_text}** {caption}".strip()
    if caption_line:
        lines.extend(["", caption_line])
    return "\n".join(lines)


def _springer_degraded_table_placeholder(label: str, reason: str) -> str:
    label_text = normalize_text(label) or "Table"
    return f"**{label_text}** Degraded placeholder: {normalize_text(reason)}"


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
        fallback_caption: str = "",
        allow_image_asset: bool = False,
        allow_degraded_placeholder: bool = False,
    ) -> tuple[str | None, str | None, dict[str, Any] | None]:
        try:
            response, response_url = self._fetch_html_response(table_url)
        except ProviderFailure as exc:
            reason = f"Springer inline table supplement for {fallback_label} could not be fetched ({exc.code}: {exc.message})."
            if allow_degraded_placeholder:
                return _springer_degraded_table_placeholder(fallback_label, reason), reason, None
            return (
                None,
                reason,
                None,
            )

        if BeautifulSoup is None:
            reason = f"Springer inline table supplement for {fallback_label} requires BeautifulSoup."
            if allow_degraded_placeholder:
                return _springer_degraded_table_placeholder(fallback_label, reason), reason, None
            return None, reason, None

        if allow_image_asset and _springer_looks_like_image_response(response, response_url):
            asset = _springer_table_image_asset(
                label=fallback_label,
                caption=fallback_caption,
                image_url=response_url,
                page_url=table_url,
            )
            return _springer_table_image_markdown(asset, label=fallback_label), None, asset

        table_html = _springer_html.decode_html(response["body"])
        soup = BeautifulSoup(table_html, "html.parser")
        table = soup.select_one(".c-article-table-container table, table")
        if isinstance(table, Tag):
            container = table.find_parent("figure")
            if not isinstance(container, Tag):
                container = table.find_parent("div", attrs={"data-container-section": "table"})
            label = _springer_table_label(container or soup, fallback=fallback_label)
            caption = _springer_table_caption(container or soup, label) or fallback_caption
            markdown = render_table_markdown(table, label=label, caption=caption)
            if not normalize_text(markdown):
                reason = f"Springer inline table supplement for {label} did not produce Markdown content."
                if allow_degraded_placeholder:
                    return _springer_degraded_table_placeholder(label, reason), reason, None
                return None, reason, None
            return markdown, None, None

        if allow_image_asset:
            image_url = _springer_html.extract_full_size_figure_image_url(table_html, response_url)
            if image_url:
                asset = _springer_table_image_asset(
                    label=fallback_label,
                    caption=fallback_caption,
                    image_url=image_url,
                    page_url=response_url,
                )
                return _springer_table_image_markdown(asset, label=fallback_label), None, asset

        reason = f"Springer inline table supplement for {fallback_label} did not include a table element."
        if allow_degraded_placeholder:
            return _springer_degraded_table_placeholder(fallback_label, reason), reason, None
        return None, reason, None

    def _prepare_html_with_inline_tables(
        self,
        html_text: str,
        source_url: str,
        *,
        normalized_doi: str,
    ) -> tuple[str, list[dict[str, str]], list[str], list[dict[str, Any]]]:
        if BeautifulSoup is None:
            return html_text, [], [], []

        soup = BeautifulSoup(html_text, "html.parser")
        table_entries: list[dict[str, str]] = []
        warnings: list[str] = []
        table_assets: list[dict[str, Any]] = []

        for node in _springer_inline_table_nodes(soup):
            if not isinstance(node, Tag) or node.parent is None:
                continue
            label = _springer_table_label(node)
            caption = _springer_table_caption(node, label)
            allow_nature13376_fallback = _springer_is_nature13376_extended_table(normalized_doi, label)
            table_url = ""
            for selector in SPRINGER_TABLE_LINK_SELECTORS:
                link = node.select_one(selector)
                if isinstance(link, Tag):
                    table_url = urllib.parse.urljoin(source_url, str(link.get("href") or "").strip())
                    if table_url:
                        break
            if not table_url:
                warning = f"Springer inline table supplement for {label} was skipped because no table page link was found."
                warnings.append(warning)
                if allow_nature13376_fallback:
                    placeholder = table_placeholder(len(table_entries) + 1)
                    block = soup.new_tag("p")
                    block.string = placeholder
                    node.replace_with(block)
                    table_entries.append(
                        {
                            "placeholder": placeholder,
                            "markdown": _springer_degraded_table_placeholder(label, warning),
                        }
                    )
                    continue
                node.decompose()
                continue

            markdown, warning, asset = self._render_table_page_markdown(
                table_url,
                fallback_label=label,
                fallback_caption=caption,
                allow_image_asset=allow_nature13376_fallback,
                allow_degraded_placeholder=allow_nature13376_fallback,
            )
            if warning:
                warnings.append(warning)
            if not markdown:
                node.decompose()
                continue

            if asset is not None:
                table_assets.append(asset)
            placeholder = table_placeholder(len(table_entries) + 1)
            block = soup.new_tag("p")
            block.string = placeholder
            node.replace_with(block)
            table_entries.append({"placeholder": placeholder, "markdown": markdown})

        return str(soup), table_entries, warnings, table_assets

    def fetch_metadata(self, query: Mapping[str, str | None]) -> ProviderMetadata:
        raise ProviderFailure(
            "not_supported",
            "Springer publisher metadata is taken from Crossref; the runtime does not use Springer publisher endpoints.",
        )

    def _prepare_html_attempt(self, doi: str, metadata: ProviderMetadata) -> SpringerHtmlAttempt:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            raise ProviderFailure("not_supported", "Springer direct HTML retrieval requires a DOI.")

        landing_url = choose_public_landing_page_url(
            metadata.get("landing_page_url"),
            f"https://doi.org/{urllib.parse.quote(normalized_doi, safe='')}",
        )
        response, response_url = self._fetch_html_response(landing_url)
        html_text = _springer_html.decode_html(response["body"])
        html_metadata = _springer_html.parse_html_metadata(html_text, response_url)
        merged_metadata = _springer_html.merge_html_metadata(metadata, html_metadata)
        if not merged_metadata.get("doi"):
            merged_metadata["doi"] = normalized_doi
        prepared_html, table_entries, table_warnings, table_assets = self._prepare_html_with_inline_tables(
            html_text,
            response_url,
            normalized_doi=normalized_doi,
        )
        extraction_payload = _springer_html.extract_html_payload(
            prepared_html,
            title=str(merged_metadata.get("title") or ""),
            source_url=response_url,
        )
        markdown_text = inject_inline_table_blocks(
            extraction_payload[MARKDOWN_TEXT_KEY],
            table_entries=table_entries,
            clean_markdown_fn=_springer_html.clean_markdown,
        )
        normalized_markdown_text = normalize_text(markdown_text)
        appended_table_markdown: list[str] = []
        for entry in table_entries:
            rendered_table = normalize_text(str(entry.get("markdown") or ""))
            if rendered_table and rendered_table not in normalized_markdown_text:
                appended_table_markdown.append(str(entry.get("markdown") or ""))
        if appended_table_markdown:
            markdown_text = _springer_html.clean_markdown(
                "\n\n".join([markdown_text, *appended_table_markdown])
            )
        abstract_sections = list(extraction_payload["abstract_sections"])
        section_hints = list(extraction_payload["section_hints"])
        diagnostics = assess_html_fulltext_availability(
            markdown_text,
            merged_metadata,
            provider=self.name,
            html_text=html_text,
            title=str(merged_metadata.get("title") or ""),
            requested_url=landing_url,
            final_url=response_url,
            response_status=int(response.get("status_code") or 0) or None,
            section_hints=section_hints,
        )
        return SpringerHtmlAttempt(
            normalized_doi=normalized_doi,
            landing_url=landing_url,
            response=response,
            response_url=response_url,
            html_text=html_text,
            merged_metadata=dict(merged_metadata),
            warnings=list(table_warnings),
            markdown_text=markdown_text,
            abstract_sections=abstract_sections,
            section_hints=section_hints,
            extracted_authors=list(extraction_payload.get("extracted_authors") or []),
            extracted_references=list(extraction_payload.get("references") or []),
            inline_table_assets=table_assets,
            diagnostics=diagnostics,
        )

    def _fetch_pdf_payload_from_html_attempt(
        self,
        attempt: SpringerHtmlAttempt,
        *,
        html_failure_message: str,
        warnings: list[str],
    ) -> RawFulltextPayload:
        pdf_candidates = build_springer_pdf_candidates(
            attempt.normalized_doi,
            attempt.merged_metadata,
            html_text=attempt.html_text,
            source_url=attempt.response_url,
        )
        pdf_result = fetch_pdf_over_http(
            self.transport,
            pdf_candidates,
            headers={
                "User-Agent": self.user_agent,
                "Referer": attempt.response_url,
            },
            timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
            seed_urls=[attempt.response_url] if attempt.response_url else None,
        )
        return RawFulltextPayload(
            provider="springer",
            source_url=pdf_result.final_url,
            content_type="application/pdf",
            body=pdf_result.pdf_bytes,
            content=ProviderContent(
                route_kind="pdf_fallback",
                source_url=pdf_result.final_url,
                content_type="application/pdf",
                body=pdf_result.pdf_bytes,
                markdown_text=pdf_result.markdown_text,
                merged_metadata=dict(attempt.merged_metadata),
                reason="Downloaded full text from the Springer direct PDF fallback route.",
                suggested_filename=pdf_result.suggested_filename,
                html_failure_message=html_failure_message,
                needs_local_copy=True,
            ),
            warnings=[
                *warnings,
                "Full text was extracted from PDF fallback after the Springer HTML path was not usable.",
            ],
            trace=trace_from_markers(
                [
                    "fulltext:springer_html_fail",
                    "fulltext:springer_pdf_fallback_ok",
                ]
            ),
            merged_metadata=attempt.merged_metadata,
            needs_local_copy=True,
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
            "reason": str((payload.content.reason if payload.content is not None else "") or "Downloaded full text from the Springer landing page HTML."),
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
        content = raw_payload.content
        if normalize_text(content.route_kind if content is not None else "").lower() == "pdf_fallback":
            return empty_asset_results()
        article_assets = _filter_springer_assets_for_profile(
            list(content.extracted_assets if content is not None else []),
            asset_profile=asset_profile,
        )
        if not article_assets:
            html_text = _springer_html.decode_html(raw_payload.body)
            article_assets = _filter_springer_assets_for_profile(
                _springer_html.extract_html_assets(
                    html_text,
                    raw_payload.source_url,
                    asset_profile="all",
                ),
                asset_profile=asset_profile,
            )
        if not article_assets:
            return empty_asset_results()
        merged_metadata = content.merged_metadata if content is not None else raw_payload.merged_metadata
        article_id = (
            normalize_doi(str((merged_metadata or {}).get("doi") or doi or ""))
            or normalize_doi(doi)
            or normalize_doi(str(metadata.get("doi") or ""))
            or normalize_text(str(metadata.get("title") or ""))
            or raw_payload.source_url
        )
        return _springer_html.download_figure_assets(
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
        attempt: SpringerHtmlAttempt | None = None

        try:
            attempt = self._prepare_html_attempt(doi, metadata)
            response_url = attempt.response_url
            html_text = attempt.html_text
            merged_metadata = dict(attempt.merged_metadata)
            warnings.extend(attempt.warnings)
            if attempt.diagnostics.accepted:
                extracted_assets = [
                    *_springer_html.extract_html_assets(
                        attempt.html_text,
                        attempt.response_url,
                        asset_profile="all",
                    ),
                    *[dict(item) for item in attempt.inline_table_assets],
                ]
                return _springer_html_payload_from_attempt(
                    attempt,
                    trace_markers=["fulltext:springer_html_ok"],
                    reason="Downloaded full text from the Springer landing page HTML.",
                    extracted_assets=extracted_assets,
                )
            html_failure = ProviderFailure(
                "no_result",
                availability_failure_message(attempt.diagnostics),
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

        try:
            pdf_attempt = attempt or SpringerHtmlAttempt(
                normalized_doi=normalized_doi,
                landing_url=landing_url,
                response={"headers": {}, "body": b""},
                response_url=response_url,
                html_text=html_text or "",
                merged_metadata=dict(merged_metadata),
                warnings=[],
                markdown_text="",
                abstract_sections=[],
                section_hints=[],
                extracted_authors=[],
                extracted_references=[],
                inline_table_assets=[],
                diagnostics=None,
            )
            return self._fetch_pdf_payload_from_html_attempt(
                pdf_attempt,
                html_failure_message=html_failure.message,
                warnings=warnings,
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

    def fetch_result(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        output_dir,
        *,
        asset_profile: AssetProfile = "none",
    ) -> ProviderFetchResult:
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
        raw_payload: RawFulltextPayload | None = None
        provisional_payload: RawFulltextPayload | None = None
        provisional_article = None
        attempt: SpringerHtmlAttempt | None = None

        try:
            attempt = self._prepare_html_attempt(doi, metadata)
            warnings.extend(attempt.warnings)
            response_url = attempt.response_url
            html_text = attempt.html_text
            merged_metadata = dict(attempt.merged_metadata)
            if attempt.diagnostics.accepted:
                extracted_assets = _filter_springer_assets_for_profile(
                    [
                        *_springer_html.extract_html_assets(
                            attempt.html_text,
                            attempt.response_url,
                            asset_profile="all",
                        ),
                        *[dict(item) for item in attempt.inline_table_assets],
                    ],
                    asset_profile=asset_profile,
                )
                raw_payload = _springer_html_payload_from_attempt(
                    attempt,
                    trace_markers=["fulltext:springer_html_ok"],
                    reason="Downloaded full text from the Springer landing page HTML.",
                    extracted_assets=extracted_assets,
                )
            else:
                html_failure = ProviderFailure(
                    "no_result",
                    availability_failure_message(attempt.diagnostics),
                    source_trail=["fulltext:springer_html_fail"],
                )
                provisional_payload = _springer_html_payload_from_attempt(
                    attempt,
                    trace_markers=["fulltext:springer_html_fail"],
                    reason="Springer HTML route only exposed abstract-level content after markdown extraction.",
                )
                provisional_article = self.to_article_model(metadata, provisional_payload)
        except ProviderFailure as exc:
            html_failure = ProviderFailure(
                exc.code,
                exc.message,
                retry_after_seconds=exc.retry_after_seconds,
                missing_env=exc.missing_env,
                warnings=exc.warnings,
                source_trail=[*exc.source_trail, "fulltext:springer_html_fail"],
            )
            warnings.extend(html_failure.warnings)

        if raw_payload is None:
            assert html_failure is not None
            warnings.extend(html_failure.warnings)
            warnings.append(f"Springer HTML route was not usable ({html_failure.message}); attempting PDF fallback.")
            pdf_attempt = attempt or SpringerHtmlAttempt(
                normalized_doi=normalized_doi,
                landing_url=landing_url,
                response={"headers": {}, "body": b""},
                response_url=response_url,
                html_text=html_text or "",
                merged_metadata=dict(merged_metadata),
                warnings=[],
                markdown_text="",
                abstract_sections=[],
                section_hints=[],
                extracted_authors=[],
                extracted_references=[],
                inline_table_assets=[],
                diagnostics=None,
            )
            try:
                raw_payload = self._fetch_pdf_payload_from_html_attempt(
                    pdf_attempt,
                    html_failure_message=html_failure.message,
                    warnings=warnings,
                )
            except PdfFetchFailure as exc:
                if provisional_article is not None:
                    failure_warning = (
                        "Springer full text could not be retrieved via HTML or PDF fallback. "
                        f"HTML failure: {html_failure.message} PDF failure: {exc.message}"
                    )
                    extend_unique(warnings, [failure_warning])
                    if provisional_article.quality.content_kind == "abstract_only":
                        provisional_article = _finalize_springer_abstract_only_article(
                            provisional_article,
                            warnings=[
                                *warnings,
                                (
                                    "Springer HTML route only exposed abstract-level content after markdown extraction, "
                                    "and PDF fallback did not return usable full text; returning abstract-only content."
                                ),
                            ],
                        )
                    else:
                        extend_unique(provisional_article.quality.warnings, warnings)
                    return ProviderFetchResult(
                        provider="springer",
                        article=provisional_article,
                        content=provisional_payload.content if provisional_payload is not None else None,
                        warnings=list(provisional_article.quality.warnings),
                        trace=list(provisional_article.quality.trace),
                        artifacts=ProviderArtifacts(),
                    )
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

        content = raw_payload.content
        artifact_policy = self.describe_artifacts(raw_payload)
        downloaded_assets: list[Mapping[str, Any]] = []
        asset_failures: list[Mapping[str, Any]] = []
        result_warnings = list(raw_payload.warnings)
        result_trace = list(raw_payload.trace)
        if output_dir is not None and asset_profile != "none" and artifact_policy.allow_related_assets:
            try:
                asset_results = self.download_related_assets(
                    normalized_doi,
                    metadata,
                    raw_payload,
                    output_dir,
                    asset_profile=asset_profile,
                )
                downloaded_assets = list(asset_results.get("assets") or [])
                asset_failures = list(asset_results.get("asset_failures") or [])
            except ProviderFailure as exc:
                result_warnings.append(f"Springer related assets could not be downloaded: {exc.message}")
                result_trace.extend(trace_from_markers(["download:springer_assets_failed"]))
            except (RequestFailure, OSError) as exc:
                result_warnings.append(f"Springer related assets could not be downloaded: {exc}")
                result_trace.extend(trace_from_markers(["download:springer_assets_failed"]))

        article = self.to_article_model(
            metadata,
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )
        artifacts = self.describe_artifacts(
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )
        return ProviderFetchResult(
            provider=raw_payload.provider or self.name,
            article=article,
            content=content,
            warnings=result_warnings,
            trace=list(result_trace or trace_from_markers(article.quality.source_trail)),
            artifacts=artifacts,
        )

    def to_article_model(
        self,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ):
        content = raw_payload.content
        merged_metadata = content.merged_metadata if content is not None else raw_payload.merged_metadata
        article_metadata = merged_metadata if isinstance(merged_metadata, Mapping) else metadata
        doi = normalize_doi(article_metadata.get("doi") or metadata.get("doi"))
        markdown_text = str((content.markdown_text if content is not None else "") or "").strip()
        route = normalize_text(content.route_kind if content is not None else "").lower()
        warnings = list(raw_payload.warnings)
        trace = list(raw_payload.trace or trace_from_markers(["fulltext:springer_html_ok"]))
        extracted_assets = list(content.extracted_assets if content is not None else [])
        assets = _merge_springer_assets(extracted_assets, list(downloaded_assets or []))
        extraction_payload = content.diagnostics.get("extraction") if content is not None else None
        abstract_sections = (
            list(extraction_payload.get("abstract_sections") or [])
            if isinstance(extraction_payload, Mapping)
            else []
        )
        section_hints = (
            list(extraction_payload.get("section_hints") or [])
            if isinstance(extraction_payload, Mapping)
            else []
        )
        extracted_references = (
            list(extraction_payload.get("references") or [])
            if isinstance(extraction_payload, Mapping)
            else []
        )
        if extracted_references:
            article_metadata = dict(article_metadata)
            article_metadata["references"] = extracted_references
        extracted_authors = (
            [
                normalize_text(str(item))
                for item in (extraction_payload.get("extracted_authors") or [])
                if normalize_text(str(item))
            ]
            if isinstance(extraction_payload, Mapping)
            else []
        )
        extracted_authors = _springer_html.normalize_display_authors(extracted_authors)
        if not extracted_authors and "html" in normalize_text(raw_payload.content_type).lower():
            html_text = bytes(raw_payload.body or b"").decode("utf-8", errors="replace")
            extracted_authors = _springer_html.extract_authors(html_text)
        if extracted_authors:
            existing_authors = [
                normalize_text(str(item))
                for item in (article_metadata.get("authors") or [])
                if normalize_text(str(item))
            ]
            article_metadata = dict(article_metadata)
            article_metadata["authors"] = dedupe_authors([*extracted_authors, *existing_authors])
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
                trace=trace,
            )
        if asset_failures:
            warnings.append(f"Springer related assets were only partially downloaded ({len(asset_failures)} failed).")
        if route != "pdf_fallback" and markdown_text:
            inline_figure_assets = [
                dict(item)
                for item in (downloaded_assets or [])
                if normalize_text(item.get("kind")).lower() == "figure"
                and normalize_text(item.get("section")).lower() != "supplementary"
                and normalize_text(item.get("section")).lower() != "appendix"
                and normalize_text(item.get("path"))
            ]
            if inline_figure_assets:
                markdown_text = rewrite_inline_figure_links(
                    markdown_text,
                    figure_assets=inline_figure_assets,
                    publisher="springer",
                )
        availability_diagnostics = (
            dict(content.diagnostics.get("availability_diagnostics") or {})
            if content is not None and isinstance(content.diagnostics.get("availability_diagnostics"), Mapping)
            else None
        )
        return article_from_markdown(
            source="springer_html",
            metadata=article_metadata,
            doi=doi or None,
            markdown_text=markdown_text,
            abstract_sections=abstract_sections,
            section_hints=section_hints,
            assets=assets,
            warnings=warnings,
            trace=trace,
            availability_diagnostics=availability_diagnostics,
            allow_downgrade_from_diagnostics=True,
        )

    def describe_artifacts(
        self,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ) -> ProviderArtifacts:
        artifacts = super().describe_artifacts(
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )
        content = raw_payload.content
        if normalize_text(content.route_kind if content is not None else "").lower() != "pdf_fallback":
            return artifacts
        return ProviderArtifacts(
            assets=list(artifacts.assets),
            asset_failures=list(artifacts.asset_failures),
            allow_related_assets=False,
            text_only=True,
            skip_warning=(
                "Springer PDF fallback currently returns text-only full text; "
                "figure and supplementary asset downloads are not implemented yet."
            ),
            skip_trace=trace_from_markers(["download:springer_assets_skipped_text_only"]),
        )
