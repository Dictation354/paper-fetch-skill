"""Springer provider client and legacy XML asset helpers."""

from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

from ..config import build_user_agent
from ..http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, HttpTransport, RequestFailure, build_text_preview, is_xml_content_type
from ..metadata_types import FulltextLink, ProviderMetadata
from ..models import AssetProfile, article_from_markdown, article_from_structure, metadata_only_article
from ..publisher_identity import normalize_doi
from ..utils import (
    build_asset_output_path,
    build_output_path,
    choose_public_landing_page_url,
    empty_asset_results,
    first_non_empty,
    normalize_text,
    sanitize_filename,
    save_payload,
    strip_html_tags,
)
from . import html_generic
from ._article_markdown import build_article_structure, write_article_markdown
from .base import (
    ProviderClient,
    ProviderFailure,
    ProviderStatusResult,
    RawFulltextPayload,
    build_provider_status_check,
    map_request_failure,
    summarize_capability_status,
)

XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
MAX_SPRINGER_HTML_REDIRECTS = 5


def extract_springer_keywords(record: Mapping[str, Any]) -> list[str]:
    """Extract keywords from a Springer metadata record.

    Legacy XML fixtures expose them under several aliases (``keyword``,
    ``subjects``, ``subject``); accept all common shapes.
    """
    if not isinstance(record, Mapping):
        return []
    keywords: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        if isinstance(value, str):
            text = value.strip()
            if text and text not in seen:
                seen.add(text)
                keywords.append(text)
        elif isinstance(value, Mapping):
            add(value.get("$") or value.get("value") or value.get("name"))
        elif isinstance(value, list):
            for item in value:
                add(item)

    for key in ("keyword", "keywords", "subjects", "subject"):
        if key in record:
            add(record.get(key))

    return keywords


def build_springer_static_asset_url(doi: str, source_href: str, *, asset_bucket: str) -> str:
    href = source_href.strip()
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("//"):
        return f"https:{href}"

    article_segment = urllib.parse.quote(f"art:{normalize_doi(doi)}", safe="")
    resource_segment = urllib.parse.quote(href.lstrip("/"), safe="/")
    return f"https://static-content.springer.com/{asset_bucket}/{article_segment}/{resource_segment}"


def springer_tag_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def walk_springer_asset_elements(
    element: ET.Element,
    *,
    location: str = "body",
    in_table: bool = False,
) -> list[tuple[ET.Element, str, bool]]:
    entries: list[tuple[ET.Element, str, bool]] = []
    if not isinstance(element.tag, str):
        return entries

    local_name = springer_tag_local_name(element.tag)
    next_location = location
    if local_name == "body":
        next_location = "body"
    elif local_name in {"app-group", "app"} and location != "supplementary":
        next_location = "appendix"
    elif local_name == "supplementary-material":
        next_location = "supplementary"

    next_in_table = in_table or local_name == "table-wrap"
    entries.append((element, next_location, next_in_table))
    for child in list(element):
        if isinstance(child.tag, str):
            entries.extend(
                walk_springer_asset_elements(
                    child,
                    location=next_location,
                    in_table=next_in_table,
                )
            )
    return entries


def extract_springer_asset_references(xml_body: bytes, doi: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_body)
    except ET.ParseError:
        return []

    references: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for element, location, in_table in walk_springer_asset_elements(root):
        tag = springer_tag_local_name(element.tag)
        if tag not in {"graphic", "inline-graphic", "media"}:
            continue

        href = (element.get(XLINK_HREF) or element.get("href") or "").strip()
        if not href:
            continue

        key = (tag, href, location)
        if key in seen:
            continue
        seen.add(key)

        if tag == "media":
            asset_type = "supplementary"
            asset_bucket = "esm"
        else:
            asset_type = "table_asset" if in_table else "image"
            asset_bucket = "image"
        references.append(
            {
                "tag": tag,
                "asset_type": asset_type,
                "source_href": href,
                "source_url": build_springer_static_asset_url(doi, href, asset_bucket=asset_bucket),
                "section": location,
            }
        )

    return references


def filter_springer_asset_references(
    references: list[dict[str, Any]],
    *,
    asset_profile: AssetProfile,
) -> list[dict[str, Any]]:
    if asset_profile == "none":
        return []
    if asset_profile == "body":
        allowed_asset_types = {"image", "table_asset"}
        return [
            reference
            for reference in references
            if str(reference.get("section") or "") == "body"
            and str(reference.get("asset_type") or "") in allowed_asset_types
        ]
    return list(references)


def download_springer_related_assets(
    transport: HttpTransport,
    *,
    doi: str,
    xml_body: bytes,
    output_dir: Path | None,
    user_agent: str,
    asset_profile: AssetProfile = "all",
) -> dict[str, list[dict[str, Any]]]:
    if output_dir is None:
        return empty_asset_results()

    references = filter_springer_asset_references(
        extract_springer_asset_references(xml_body, doi),
        asset_profile=asset_profile,
    )
    if not references:
        return empty_asset_results()

    asset_dir = output_dir / f"{sanitize_filename(doi)}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()
    downloads: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for reference in references:
        try:
            response = transport.request(
                "GET",
                reference["source_url"],
                headers={"User-Agent": user_agent, "Accept": "*/*"},
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_rate_limit=True,
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            failures.append(
                {
                    "asset_type": reference["asset_type"],
                    "tag": reference["tag"],
                    "source_href": reference["source_href"],
                    "source_url": reference["source_url"],
                    "section": reference.get("section"),
                    "status": exc.status_code,
                    "reason": str(exc),
                }
            )
            continue

        content_type = response["headers"].get("content-type")
        output_path = build_asset_output_path(
            asset_dir,
            reference["source_href"],
            content_type,
            response["url"],
            used_names,
        )
        downloads.append(
            {
                "asset_type": reference["asset_type"],
                "tag": reference["tag"],
                "source_href": reference["source_href"],
                "source_url": response["url"],
                "content_type": content_type,
                "path": save_payload(output_path, response["body"]),
                "downloaded_bytes": len(response["body"]),
                "section": reference.get("section"),
            }
        )

    return {
        "assets": downloads,
        "asset_failures": failures,
    }


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
        response, response_url = self._fetch_html_response(landing_url)

        html_text = html_generic.decode_html(response["body"])
        html_metadata = html_generic.parse_html_metadata(html_text, response_url)
        merged_metadata = html_generic.merge_html_metadata(metadata, html_metadata)
        if not merged_metadata.get("doi"):
            merged_metadata["doi"] = normalized_doi
        markdown_text = html_generic.clean_markdown(html_generic.extract_article_markdown(html_text, response_url))
        if not html_generic.has_sufficient_article_body(markdown_text, merged_metadata):
            raise ProviderFailure("no_result", "Springer HTML extraction did not produce enough article body text.")
        extracted_assets = html_generic.extract_html_assets(html_text, response_url, asset_profile="all")
        return RawFulltextPayload(
            provider="springer",
            source_url=response_url,
            content_type=response["headers"].get("content-type", "text/html"),
            body=response["body"],
            metadata={
                "reason": "Downloaded full text from the Springer landing page HTML.",
                "merged_metadata": merged_metadata,
                "markdown_text": markdown_text,
                "extracted_assets": extracted_assets,
            },
            needs_local_copy=False,
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
        warnings: list[str] = []
        source_trail = ["fulltext:springer_html_ok"]
        assets = list(downloaded_assets or [])
        if not markdown_text:
            warnings.append("Springer HTML retrieval did not produce usable Markdown.")
            source_trail = ["fulltext:springer_html_fail"]
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
