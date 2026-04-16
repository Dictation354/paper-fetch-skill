"""Springer provider client and XML asset helpers."""

from __future__ import annotations

import json
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
    empty_asset_results,
    first_non_empty,
    sanitize_filename,
    save_payload,
    strip_html_tags,
)
from ._article_markdown import build_article_structure, write_article_markdown
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

XLINK_HREF = "{http://www.w3.org/1999/xlink}href"


def extract_springer_keywords(record: Mapping[str, Any]) -> list[str]:
    """Extract keywords from a Springer Meta API record.

    The API exposes them under several aliases (``keyword``, ``subjects``,
    ``subject``); accept all common shapes.
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


def springer_xml_local_name(tag: str) -> str:
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

    local_name = springer_xml_local_name(element.tag)
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
        tag = springer_xml_local_name(element.tag)
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
        self.meta_api_key = env.get("SPRINGER_META_API_KEY", "").strip()
        self.openaccess_api_key = env.get("SPRINGER_OPENACCESS_API_KEY", "").strip()
        self.fulltext_api_key = env.get("SPRINGER_FULLTEXT_API_KEY", "").strip()
        self.fulltext_url_template = env.get("SPRINGER_FULLTEXT_URL_TEMPLATE", "").strip()
        self.fulltext_auth_header = env.get("SPRINGER_FULLTEXT_AUTH_HEADER", "").strip()
        self.fulltext_accept = env.get("SPRINGER_FULLTEXT_ACCEPT", "application/xml").strip() or "application/xml"
        self.user_agent = build_user_agent(env)

    def probe_status(self) -> ProviderStatusResult:
        return summarize_capability_status(
            self.name,
            official_provider=self.official_provider,
            checks=[
                build_provider_status_check(
                    "metadata_api",
                    "ok" if self.meta_api_key else "not_configured",
                    (
                        "Springer Meta API credentials are configured."
                        if self.meta_api_key
                        else "SPRINGER_META_API_KEY is required for Springer metadata retrieval."
                    ),
                    missing_env=[] if self.meta_api_key else ["SPRINGER_META_API_KEY"],
                ),
                build_provider_status_check(
                    "openaccess_api",
                    "ok" if self.openaccess_api_key else "not_configured",
                    (
                        "Springer Open Access API credentials are configured."
                        if self.openaccess_api_key
                        else "SPRINGER_OPENACCESS_API_KEY is required for Springer Open Access full-text retrieval."
                    ),
                    missing_env=[] if self.openaccess_api_key else ["SPRINGER_OPENACCESS_API_KEY"],
                ),
                build_provider_status_check(
                    "fulltext_api",
                    "ok" if self.fulltext_api_key and self.fulltext_url_template else "not_configured",
                    (
                        "Springer Full Text API credentials are configured."
                        if self.fulltext_api_key and self.fulltext_url_template
                        else "SPRINGER_FULLTEXT_API_KEY and SPRINGER_FULLTEXT_URL_TEMPLATE are required for Springer Full Text API retrieval."
                    ),
                    missing_env=[
                        name
                        for name, configured in (
                            ("SPRINGER_FULLTEXT_API_KEY", bool(self.fulltext_api_key)),
                            ("SPRINGER_FULLTEXT_URL_TEMPLATE", bool(self.fulltext_url_template)),
                        )
                        if not configured
                    ],
                    details={
                        "auth_header": self.fulltext_auth_header or None,
                        "accept": self.fulltext_accept,
                    },
                ),
            ],
        )

    def _headers(self, accept: str) -> dict[str, str]:
        return {
            "Accept": accept,
            "User-Agent": self.user_agent,
        }

    def _meta_query(self, doi: str) -> dict[str, str]:
        if not self.meta_api_key:
            raise ProviderFailure(
                "not_configured",
                "SPRINGER_META_API_KEY is not configured.",
                missing_env=["SPRINGER_META_API_KEY"],
            )
        return {
            "api_key": self.meta_api_key,
            "q": f"doi:{doi}",
        }

    def _openaccess_query(self, doi: str) -> dict[str, str]:
        if not self.openaccess_api_key:
            raise ProviderFailure(
                "not_configured",
                "SPRINGER_OPENACCESS_API_KEY is not configured.",
                missing_env=["SPRINGER_OPENACCESS_API_KEY"],
            )
        return {
            "api_key": self.openaccess_api_key,
            "q": f"doi:{doi}",
        }

    def fetch_metadata(self, query: Mapping[str, str | None]) -> ProviderMetadata:
        doi = normalize_doi(query.get("doi"))
        if not doi:
            raise ProviderFailure(
                "not_supported",
                "Springer official metadata retrieval needs a DOI in this implementation.",
            )

        try:
            response = self.transport.request(
                "GET",
                "https://api.springernature.com/meta/v2/json",
                headers=self._headers("application/json"),
                query=self._meta_query(doi),
                retry_on_rate_limit=True,
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            raise map_request_failure(exc) from exc

        payload = json.loads(response["body"].decode("utf-8"))
        records = payload.get("records") or []
        if not records:
            raise ProviderFailure("no_result", "Springer Meta API returned no records.")
        return self._normalize_record(records[0], response["url"])

    def fetch_fulltext(self, doi: str, metadata: ProviderMetadata, output_dir: Path | None) -> dict[str, Any]:
        payload = self.fetch_raw_fulltext(doi, metadata)
        normalized_doi = normalize_doi(doi)
        output_path = build_output_path(output_dir, normalized_doi, metadata.get("title"), payload.content_type, payload.source_url)
        saved_path = save_payload(output_path, payload.body)
        asset_results = self.download_related_assets(normalized_doi, metadata, payload, output_dir)
        markdown_path = None
        if is_xml_content_type(payload.content_type):
            markdown_path = write_article_markdown(
                provider="springer",
                metadata=metadata,
                xml_body=payload.body,
                output_dir=output_dir,
                xml_path=saved_path,
                assets=asset_results["assets"],
            )
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
            "reason": str(payload.metadata.get("reason") or "Downloaded full text from the official Springer Open Access API."),
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
        normalized_doi = normalize_doi(doi)
        if not normalized_doi or not is_xml_content_type(raw_payload.content_type):
            return empty_asset_results()
        return download_springer_related_assets(
            self.transport,
            doi=normalized_doi,
            xml_body=raw_payload.body,
            output_dir=output_dir,
            user_agent=self.user_agent,
            asset_profile=asset_profile,
        )

    def fetch_raw_fulltext(self, doi: str, metadata: ProviderMetadata) -> RawFulltextPayload:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            raise ProviderFailure("not_supported", "Springer full-text retrieval requires a DOI.")

        failures: list[tuple[str, ProviderFailure]] = []

        if self.fulltext_url_template or self.fulltext_api_key:
            try:
                return self._fetch_fulltext_api(normalized_doi, metadata)
            except ProviderFailure as exc:
                failures.append(("Springer Full Text API", exc))

        try:
            return self._fetch_openaccess_fulltext(normalized_doi, metadata)
        except ProviderFailure as exc:
            failures.append(("Springer Open Access API", exc))

        raise combine_provider_failures(failures)

    def _fetch_fulltext_api(self, doi: str, metadata: ProviderMetadata) -> RawFulltextPayload:
        if not self.fulltext_url_template or not self.fulltext_api_key:
            missing_env: list[str] = []
            if not self.fulltext_api_key:
                missing_env.append("SPRINGER_FULLTEXT_API_KEY")
            if not self.fulltext_url_template:
                missing_env.append("SPRINGER_FULLTEXT_URL_TEMPLATE")
            raise ProviderFailure(
                "not_configured",
                "SPRINGER_FULLTEXT_API_KEY and SPRINGER_FULLTEXT_URL_TEMPLATE are required for Springer Full Text API retrieval.",
                missing_env=missing_env,
            )

        encoded_doi = urllib.parse.quote(doi, safe="")
        url = self.fulltext_url_template.format(
            doi=encoded_doi,
            raw_doi=doi,
            api_key=urllib.parse.quote(self.fulltext_api_key, safe=""),
        )
        headers = self._headers(self.fulltext_accept)
        if self.fulltext_auth_header:
            headers[self.fulltext_auth_header] = self.fulltext_api_key

        try:
            response = self.transport.request(
                "GET",
                url,
                headers=headers,
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_rate_limit=True,
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            raise map_request_failure(exc) from exc

        content_type = response["headers"].get("content-type", self.fulltext_accept)
        return RawFulltextPayload(
            provider="springer",
            source_url=response["url"],
            content_type=content_type,
            body=response["body"],
            metadata={"reason": "Downloaded full text from the official Springer Full Text API."},
            needs_local_copy=not (content_type.startswith("text/") or is_xml_content_type(content_type)),
        )

    def _fetch_openaccess_fulltext(self, doi: str, metadata: ProviderMetadata) -> RawFulltextPayload:
        try:
            response = self.transport.request(
                "GET",
                "https://api.springernature.com/openaccess/jats",
                headers=self._headers("application/xml"),
                query=self._openaccess_query(doi),
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_rate_limit=True,
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            raise map_request_failure(exc) from exc

        content_type = response["headers"].get("content-type", "application/xml")
        return RawFulltextPayload(
            provider="springer",
            source_url=response["url"],
            content_type=content_type,
            body=response["body"],
            metadata={"reason": "Downloaded full text from the official Springer Open Access API."},
            needs_local_copy=not (content_type.startswith("text/") or is_xml_content_type(content_type)),
        )

    def to_article_model(
        self,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ):
        doi = normalize_doi(metadata.get("doi"))
        warnings: list[str] = []
        if is_xml_content_type(raw_payload.content_type):
            xml_path = Path(f"{sanitize_filename(doi or str(metadata.get('title') or 'article'))}.xml")
            structure = build_article_structure(
                provider="springer",
                metadata=metadata,
                xml_body=raw_payload.body,
                xml_path=xml_path,
                assets=list(downloaded_assets or []),
            )
            if structure is not None:
                return article_from_structure(
                    source="springer_xml",
                    metadata=metadata,
                    doi=doi or None,
                    abstract_lines=structure.abstract_lines,
                    body_lines=structure.body_lines,
                    figure_entries=structure.figure_entries,
                    table_entries=structure.table_entries,
                    supplement_entries=structure.supplement_entries,
                    conversion_notes=structure.conversion_notes,
                    warnings=warnings,
                )
        if raw_payload.content_type.startswith("text/"):
            try:
                text = raw_payload.body.decode("utf-8", errors="replace")
            except Exception:
                text = ""
            if text.strip():
                warnings.append("Official full text was not available in XML format; returned plain text instead.")
            return article_from_markdown(
                source="springer_xml",
                metadata=metadata,
                doi=doi or None,
                markdown_text=text,
                warnings=warnings,
            )
        warnings.append("Official full text was not convertible to AI-friendly Markdown.")
        return metadata_only_article(
            source="springer_xml",
            metadata=metadata,
            doi=doi or None,
            warnings=warnings,
        )

    def _normalize_record(self, record: Mapping[str, Any], source_url: str) -> ProviderMetadata:
        links: list[FulltextLink] = []
        raw_url_field = record.get("url")
        if isinstance(raw_url_field, list):
            for item in raw_url_field:
                if isinstance(item, dict) and item.get("value"):
                    links.append(
                        {
                            "url": item.get("value"),
                            "content_type": item.get("format"),
                            "content_version": None,
                            "intended_application": "text-mining",
                        }
                    )
        elif isinstance(raw_url_field, str) and raw_url_field:
            links.append(
                {
                    "url": raw_url_field,
                    "content_type": None,
                    "content_version": None,
                    "intended_application": "text-mining",
                }
            )

        return {
            "status": "ok",
            "provider": "springer",
            "official_provider": True,
            "source_url": source_url,
            "doi": first_non_empty(record.get("doi"), record.get("doiValue")),
            "title": first_non_empty(record.get("title"), record.get("publicationName")),
            "journal_title": first_non_empty(record.get("journalTitle"), record.get("publicationName")),
            "publisher": first_non_empty(record.get("publisher"), "Springer Nature"),
            "abstract": strip_html_tags(record.get("abstract")),
            "published": first_non_empty(record.get("publicationDate"), record.get("publicationDateStart")),
            "landing_page_url": links[0]["url"] if links else (record.get("url") if isinstance(record.get("url"), str) else None),
            "license_urls": [],
            "fulltext_links": links,
            "keywords": extract_springer_keywords(record),
        }
