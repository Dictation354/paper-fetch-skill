"""Elsevier provider client and XML asset helpers."""

from __future__ import annotations

import json
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

from ..config import build_user_agent
from ..http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, HttpTransport, RequestFailure, build_text_preview, is_xml_content_type
from ..metadata_types import ProviderMetadata
from ..models import AssetProfile, article_from_markdown, article_from_structure, metadata_only_article
from ..publisher_identity import normalize_doi
from ..utils import (
    build_asset_output_path,
    build_output_path,
    choose_public_landing_page_url,
    empty_asset_results,
    first_non_empty,
    sanitize_filename,
    save_payload,
    strip_html_tags,
)
from . import html_generic
from ._article_markdown import build_article_structure, write_article_markdown
from ._elsevier_xml_rules import (
    ELSEVIER_IMAGE_ASSET_TYPES,
    classify_elsevier_asset_kind,
    infer_elsevier_asset_group_key,
)
from ._flaresolverr import (
    FlareSolverrFailure,
    ensure_runtime_ready,
    fetch_html_with_flaresolverr,
    load_runtime_config,
    probe_runtime_status,
)
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


def xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def first_xml_child_text(element: ET.Element, child_local_name: str) -> str | None:
    for child in list(element):
        if not isinstance(child.tag, str):
            continue
        if xml_local_name(child.tag) != child_local_name:
            continue
        text = (child.text or "").strip()
        if text:
            return text
    return None


def extract_elsevier_keywords(root: Mapping[str, Any]) -> list[str]:
    """Extract author keywords from an Elsevier abstract-retrieval response.

    The Elsevier Abstract API returns keywords under several possible shapes
    depending on the view; this helper walks the common ones defensively.
    """
    if not isinstance(root, Mapping):
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
            add(value.get("$"))

    container = root.get("authkeywords")
    if isinstance(container, Mapping):
        items = container.get("author-keyword")
    elif isinstance(container, list):
        items = container
    else:
        items = None
    if isinstance(items, list):
        for item in items:
            add(item)
    elif items is not None:
        add(items)

    return keywords


def elsevier_asset_priority(asset_kind: str, asset_type: str, category: str | None = None) -> int:
    normalized_type = asset_type.strip().upper()
    normalized_category = (category or "").strip().lower()
    if asset_kind not in ELSEVIER_IMAGE_ASSET_TYPES:
        return 0
    if normalized_type == "IMAGE-HIGH-RES":
        return 0
    if normalized_type == "IMAGE-DOWNSAMPLED":
        return 1
    if normalized_type == "IMAGE-THUMBNAIL" or normalized_category == "thumbnail":
        return 3
    return 2


def build_elsevier_object_url(attachment_eid: str) -> str:
    encoded_eid = urllib.parse.quote(attachment_eid.strip(), safe="")
    return f"https://api.elsevier.com/content/object/eid/{encoded_eid}?httpAccept=%2A%2F%2A"


def _article_has_body_sections(article: Any) -> bool:
    return any(
        str(getattr(section, "kind", "") or "").lower() not in {"abstract", "references", "diagnostics"}
        and bool(str(getattr(section, "text", "") or "").strip())
        for section in list(getattr(article, "sections", []) or [])
    )


def extract_elsevier_asset_references(xml_body: bytes) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_body)
    except ET.ParseError:
        return []

    references_by_key: dict[tuple[str, str], tuple[int, dict[str, Any]]] = {}

    def register(reference: dict[str, Any], *, key: tuple[str, str], priority: int) -> None:
        existing = references_by_key.get(key)
        if existing is None or priority < existing[0]:
            references_by_key[key] = (priority, reference)

    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        if xml_local_name(element.tag) != "object":
            continue

        source_url = (element.text or "").strip()
        if not source_url:
            continue

        object_type = (element.get("type") or "").strip()
        category = (element.get("category") or "").strip()
        mimetype = (element.get("mimetype") or "").strip()
        ref = (element.get("ref") or source_url).strip()

        asset_kind = classify_elsevier_asset_kind(ref, object_type, category)

        reference = {
            "asset_type": asset_kind,
            "source_kind": "object",
            "source_ref": ref,
            "source_url": source_url,
            "content_type": mimetype or None,
            "filename_hint": Path(urllib.parse.urlparse(source_url).path).name or ref,
            "object_type": object_type or None,
            "category": category or None,
        }
        register(
            reference,
            key=(asset_kind, infer_elsevier_asset_group_key(ref)),
            priority=elsevier_asset_priority(asset_kind, object_type, category),
        )

    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        if xml_local_name(element.tag) != "attachment":
            continue

        attachment_type = (first_xml_child_text(element, "attachment-type") or "").strip()
        attachment_eid = (first_xml_child_text(element, "attachment-eid") or "").strip()
        filename = (first_xml_child_text(element, "filename") or "").strip()
        mimetype = None
        extension = (first_xml_child_text(element, "extension") or "").strip().lower()
        if extension:
            guessed_content_type = {
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "gif": "image/gif",
                "png": "image/png",
                "pdf": "application/pdf",
                "xls": "application/vnd.ms-excel",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "zip": "application/zip",
            }
            mimetype = guessed_content_type.get(extension)

        if not attachment_eid:
            continue
        asset_kind = classify_elsevier_asset_kind(attachment_eid, attachment_type)

        reference = {
            "asset_type": asset_kind,
            "source_kind": "attachment",
            "source_ref": attachment_eid,
            "source_url": build_elsevier_object_url(attachment_eid),
            "content_type": mimetype,
            "filename_hint": filename or attachment_eid,
            "attachment_type": attachment_type or None,
        }
        register(
            reference,
            key=(asset_kind, infer_elsevier_asset_group_key(attachment_eid)),
            priority=elsevier_asset_priority(asset_kind, attachment_type),
        )

    return [item[1] for item in references_by_key.values()]


def filter_elsevier_asset_references(
    references: list[dict[str, Any]],
    *,
    asset_profile: AssetProfile,
) -> list[dict[str, Any]]:
    if asset_profile == "none":
        return []
    if asset_profile == "body":
        allowed_asset_types = {"image", "table_asset"}
        return [reference for reference in references if str(reference.get("asset_type") or "") in allowed_asset_types]
    return list(references)


def download_elsevier_related_assets(
    transport: HttpTransport,
    *,
    doi: str,
    xml_body: bytes,
    output_dir: Path | None,
    headers: Mapping[str, str],
    asset_profile: AssetProfile = "all",
) -> dict[str, list[dict[str, Any]]]:
    if output_dir is None:
        return empty_asset_results()

    references = filter_elsevier_asset_references(
        extract_elsevier_asset_references(xml_body),
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
                headers=headers,
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_rate_limit=True,
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            failures.append(
                {
                    "asset_type": reference["asset_type"],
                    "source_kind": reference["source_kind"],
                    "source_ref": reference["source_ref"],
                    "source_url": reference["source_url"],
                    "status": exc.status_code,
                    "reason": str(exc),
                }
            )
            continue

        content_type = response["headers"].get("content-type", reference.get("content_type"))
        output_path = build_asset_output_path(
            asset_dir,
            reference.get("filename_hint"),
            content_type,
            response["url"],
            used_names,
        )
        downloads.append(
            {
                "asset_type": reference["asset_type"],
                "source_kind": reference["source_kind"],
                "source_ref": reference["source_ref"],
                "source_url": response["url"],
                "content_type": content_type,
                "path": save_payload(output_path, response["body"]),
                "downloaded_bytes": len(response["body"]),
            }
        )

    return {
        "assets": downloads,
        "asset_failures": failures,
    }


class ElsevierClient(ProviderClient):
    name = "elsevier"

    def __init__(self, transport: HttpTransport, env: Mapping[str, str]) -> None:
        self.transport = transport
        self.env = dict(env)
        self.api_key = env.get("ELSEVIER_API_KEY", "").strip()
        self.insttoken = env.get("ELSEVIER_INSTTOKEN", "").strip()
        self.authtoken = env.get("ELSEVIER_AUTHTOKEN", "").strip()
        self.clickthrough_token = env.get("ELSEVIER_CLICKTHROUGH_TOKEN", "").strip()
        self.user_agent = build_user_agent(env)

    def _base_headers(self, accept: str) -> dict[str, str]:
        if not self.api_key:
            raise ProviderFailure(
                "not_configured",
                "ELSEVIER_API_KEY is not configured.",
                missing_env=["ELSEVIER_API_KEY"],
            )
        headers = {
            "Accept": accept,
            "X-ELS-APIKey": self.api_key,
            "User-Agent": self.user_agent,
            "X-ELS-ReqId": str(uuid.uuid4()),
        }
        if self.insttoken:
            headers["X-ELS-Insttoken"] = self.insttoken
        if self.authtoken:
            headers["Authorization"] = f"Bearer {self.authtoken}"
        if self.clickthrough_token:
            headers["CR-Clickthrough-Client-Token"] = self.clickthrough_token
        return headers

    def probe_status(self) -> ProviderStatusResult:
        check_status = "ok" if self.api_key else "not_configured"
        message = (
            "Elsevier full-text API credentials are configured."
            if self.api_key
            else "ELSEVIER_API_KEY is required for Elsevier full-text retrieval."
        )
        missing_env = [] if self.api_key else ["ELSEVIER_API_KEY"]
        browser_status = probe_runtime_status(self.env, provider=self.name)
        return summarize_capability_status(
            self.name,
            official_provider=self.official_provider,
            checks=[
                build_provider_status_check(
                    "fulltext_api",
                    check_status,
                    message,
                    missing_env=missing_env,
                    details={
                        "insttoken_configured": bool(self.insttoken),
                        "authtoken_configured": bool(self.authtoken),
                        "clickthrough_token_configured": bool(self.clickthrough_token),
                    },
                ),
                *browser_status.checks,
            ],
        )

    def _official_article_url(self, doi: str) -> str:
        return f"https://api.elsevier.com/content/article/doi/{urllib.parse.quote(doi, safe='')}"

    def _browser_html_candidates(self, doi: str, metadata: ProviderMetadata) -> list[str]:
        candidates: list[str] = []
        for candidate in (
            choose_public_landing_page_url(metadata.get("landing_page_url")),
            f"https://doi.org/{urllib.parse.quote(doi, safe='')}",
        ):
            normalized = str(candidate or "").strip()
            if normalized and normalized not in candidates:
                candidates.append(normalized)
        return candidates

    def _fetch_official_payload(self, doi: str) -> RawFulltextPayload:
        url = self._official_article_url(doi)
        for accept in ("text/xml", "application/pdf", "text/plain", "application/json"):
            try:
                response = self.transport.request(
                    "GET",
                    url,
                    headers=self._base_headers(accept),
                    query={"view": "FULL"},
                    timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                    retry_on_rate_limit=True,
                    retry_on_transient=True,
                )
            except RequestFailure as exc:
                provider_failure = map_request_failure(exc)
                if provider_failure.code == "error" and exc.status_code in {406, 415}:
                    continue
                raise provider_failure from exc

            content_type = response["headers"].get("content-type", accept)
            return RawFulltextPayload(
                provider="elsevier",
                source_url=response["url"],
                content_type=content_type,
                body=response["body"],
                metadata={
                    "route": "official",
                    "reason": "Downloaded full text from the official Elsevier API.",
                },
                needs_local_copy=not (content_type.startswith("text/") or is_xml_content_type(content_type)),
            )

        raise ProviderFailure("error", "Elsevier full-text retrieval did not yield a supported representation.")

    def _official_payload_is_usable(self, metadata: ProviderMetadata, raw_payload: RawFulltextPayload) -> bool:
        article = self.to_article_model(metadata, raw_payload)
        if not article.quality.has_fulltext or not _article_has_body_sections(article):
            return False
        if raw_payload.content_type.startswith("text/") and not is_xml_content_type(raw_payload.content_type):
            try:
                markdown_text = raw_payload.body.decode("utf-8", errors="replace")
            except Exception:
                return False
            return html_generic.has_sufficient_article_body(markdown_text, metadata)
        return True

    def _finalize_browser_failure(
        self,
        official_failure: ProviderFailure | None,
        browser_failure: ProviderFailure,
    ) -> ProviderFailure:
        if official_failure is None:
            return browser_failure
        return combine_provider_failures(
            [
                ("official", official_failure),
                ("browser", browser_failure),
            ]
        )

    def fetch_metadata(self, query: Mapping[str, str | None]) -> ProviderMetadata:
        doi = normalize_doi(query.get("doi"))
        if not doi:
            raise ProviderFailure(
                "not_supported",
                "Elsevier official metadata retrieval needs a DOI in this implementation.",
            )

        url = f"https://api.elsevier.com/content/abstract/doi/{urllib.parse.quote(doi, safe='')}"
        try:
            response = self.transport.request(
                "GET",
                url,
                headers=self._base_headers("application/json"),
                query={"view": "META_ABS"},
                retry_on_rate_limit=True,
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            raise map_request_failure(exc) from exc

        payload = json.loads(response["body"].decode("utf-8"))
        root = payload.get("abstracts-retrieval-response", {})
        core = root.get("coredata", {}) if isinstance(root, dict) else {}
        metadata: ProviderMetadata = {
            "status": "ok",
            "provider": "elsevier",
            "official_provider": True,
            "source_url": response["url"],
            "doi": first_non_empty(core.get("prism:doi"), doi),
            "title": first_non_empty(core.get("dc:title"), core.get("title")),
            "journal_title": first_non_empty(core.get("prism:publicationName"), core.get("publicationName")),
            "publisher": first_non_empty(core.get("dc:publisher"), "Elsevier"),
            "abstract": strip_html_tags(
                first_non_empty(
                    core.get("dc:description"),
                    root.get("item", {}).get("bibrecord", {}).get("head", {}).get("abstracts"),
                )
            ),
            "published": first_non_empty(core.get("prism:coverDate"), core.get("prism:coverDisplayDate")),
            "landing_page_url": choose_public_landing_page_url(core.get("link"), core.get("prism:url")),
            "license_urls": [],
            "fulltext_links": [],
            "keywords": extract_elsevier_keywords(root),
        }
        if not metadata["title"]:
            raise ProviderFailure("no_result", "Elsevier metadata payload did not contain a title.")
        return metadata

    def fetch_fulltext(self, doi: str, metadata: ProviderMetadata, output_dir: Path | None) -> dict[str, Any]:
        payload = self.fetch_raw_fulltext(doi, metadata)
        normalized_doi = normalize_doi(doi)
        output_path = build_output_path(output_dir, normalized_doi, metadata.get("title"), payload.content_type, payload.source_url)
        saved_path = save_payload(output_path, payload.body)
        asset_results = self.download_related_assets(normalized_doi, metadata, payload, output_dir)
        markdown_path = None
        if is_xml_content_type(payload.content_type):
            markdown_path = write_article_markdown(
                provider="elsevier",
                metadata=metadata,
                xml_body=payload.body,
                output_dir=output_dir,
                xml_path=saved_path,
                assets=asset_results["assets"],
            )
        return {
            "attempted": True,
            "status": "saved" if output_path else "fetched",
            "provider": "elsevier",
            "official_provider": True,
            "source_url": payload.source_url,
            "content_type": payload.content_type,
            "path": saved_path,
            "markdown_path": markdown_path,
            "downloaded_bytes": len(payload.body),
            "content_preview": build_text_preview(payload.body, payload.content_type),
            "reason": str(payload.metadata.get("reason") or "Downloaded full text from the official Elsevier API."),
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
        return download_elsevier_related_assets(
            self.transport,
            doi=normalized_doi,
            xml_body=raw_payload.body,
            output_dir=output_dir,
            headers=self._base_headers("*/*"),
            asset_profile=asset_profile,
        )

    def fetch_raw_fulltext(self, doi: str, metadata: ProviderMetadata) -> RawFulltextPayload:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            raise ProviderFailure("not_supported", "Elsevier full-text retrieval requires a DOI.")
        official_failure: ProviderFailure | None = None
        warnings: list[str] = []
        source_trail: list[str] = []

        try:
            official_payload = self._fetch_official_payload(normalized_doi)
            if self._official_payload_is_usable(metadata, official_payload):
                return official_payload
            warnings.append(
                "Elsevier official XML/API response did not produce enough article body text; attempting browser fallback."
            )
            source_trail.append("fulltext:elsevier_xml_fail")
        except ProviderFailure as exc:
            official_failure = exc
            warnings.extend(exc.warnings)
            warnings.append(f"Elsevier official XML/API route was not usable ({exc.message}); attempting browser fallback.")
            source_trail.extend(exc.source_trail)
            source_trail.append("fulltext:elsevier_xml_fail")

        html_failure_reason: str | None = None
        html_failure_message: str | None = None

        try:
            runtime = load_runtime_config(self.env, provider=self.name, doi=normalized_doi)
            ensure_runtime_ready(runtime)
            html_result = fetch_html_with_flaresolverr(
                self._browser_html_candidates(normalized_doi, metadata),
                publisher=self.name,
                config=runtime,
            )
            html_metadata = html_generic.parse_html_metadata(html_result.html, html_result.final_url)
            merged_metadata = html_generic.merge_html_metadata(metadata, html_metadata)
            if not merged_metadata.get("doi"):
                merged_metadata["doi"] = normalized_doi
            markdown_text = html_generic.clean_markdown(
                html_generic.extract_article_markdown(html_result.html, html_result.final_url)
            )
            if html_generic.has_sufficient_article_body(markdown_text, merged_metadata):
                return RawFulltextPayload(
                    provider="elsevier_browser",
                    source_url=html_result.final_url,
                    content_type="text/html",
                    body=html_result.html.encode("utf-8"),
                    metadata={
                        "route": "html",
                        "reason": "Downloaded full text from the Elsevier browser fallback HTML route.",
                        "merged_metadata": merged_metadata,
                        "markdown_text": markdown_text,
                        "warnings": warnings,
                        "source_trail": [
                            *source_trail,
                            "fulltext:elsevier_html_ok",
                        ],
                        "html_fetcher": "flaresolverr",
                    },
                    needs_local_copy=False,
                )
            html_failure_reason = "insufficient_body"
            html_failure_message = "Elsevier HTML extraction did not produce enough article body text."
        except FlareSolverrFailure as exc:
            html_failure_reason = exc.kind
            html_failure_message = exc.message
        except ProviderFailure as exc:
            html_failure_reason = exc.code
            html_failure_message = exc.message

        warnings.append(
            f"Elsevier HTML route was not usable ({html_failure_reason or 'html_failed'}); returning metadata-only."
        )
        browser_failure_code = (
            html_failure_reason
            if html_failure_reason in {"not_configured", "rate_limited"}
            else "no_result"
        )
        browser_failure_message = (
            html_failure_message or "Elsevier browser fallback runtime is not ready."
            if browser_failure_code in {"not_configured", "rate_limited"}
            else (
                "Elsevier full text could not be retrieved via XML/API or HTML. "
                f"HTML failure: {html_failure_message or 'unknown'}"
            )
        )
        browser_failure = ProviderFailure(
            browser_failure_code,
            browser_failure_message,
            warnings=warnings,
            source_trail=[*source_trail, "fulltext:elsevier_html_fail"],
        )
        raise self._finalize_browser_failure(official_failure, browser_failure)

    def to_article_model(
        self,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ):
        route = str(raw_payload.metadata.get("route") or "").strip().lower()
        merged_metadata = raw_payload.metadata.get("merged_metadata")
        article_metadata = merged_metadata if isinstance(merged_metadata, Mapping) else metadata
        doi = normalize_doi(article_metadata.get("doi") or metadata.get("doi"))
        warnings = [str(item) for item in raw_payload.metadata.get("warnings") or [] if str(item).strip()]
        source_trail = [str(item) for item in raw_payload.metadata.get("source_trail") or [] if str(item).strip()]

        if route == "html":
            markdown_text = str(raw_payload.metadata.get("markdown_text") or "").strip()
            if not markdown_text:
                warnings.append("Elsevier browser fallback did not produce usable Markdown.")
                return metadata_only_article(
                    source="elsevier_browser",
                    metadata=article_metadata,
                    doi=doi or None,
                    warnings=warnings,
                    source_trail=source_trail + ["fulltext:elsevier_parse_fail"],
                )
            return article_from_markdown(
                source="elsevier_browser",
                metadata=article_metadata,
                doi=doi or None,
                markdown_text=markdown_text,
                warnings=warnings,
                source_trail=source_trail,
            )

        if is_xml_content_type(raw_payload.content_type):
            pseudo_assets = downloaded_assets if downloaded_assets else extract_elsevier_asset_references(raw_payload.body)
            xml_path = Path(f"{sanitize_filename(doi or str(metadata.get('title') or 'article'))}.xml")
            structure = build_article_structure(
                provider="elsevier",
                metadata=metadata,
                xml_body=raw_payload.body,
                xml_path=xml_path,
                assets=pseudo_assets,
            )
            if structure is not None:
                return article_from_structure(
                    source="elsevier_xml",
                    metadata=article_metadata,
                    doi=doi or None,
                    abstract_lines=structure.abstract_lines,
                    body_lines=structure.body_lines,
                    figure_entries=structure.figure_entries,
                    table_entries=structure.table_entries,
                    supplement_entries=structure.supplement_entries,
                    conversion_notes=structure.conversion_notes,
                    warnings=warnings,
                    source_trail=source_trail,
                )
        if raw_payload.content_type.startswith("text/"):
            try:
                text = raw_payload.body.decode("utf-8", errors="replace")
            except Exception:
                text = ""
            if text.strip():
                warnings.append("Official full text was not available in XML format; returned plain text instead.")
            return article_from_markdown(
                source="elsevier_xml",
                metadata=article_metadata,
                doi=doi or None,
                markdown_text=text,
                warnings=warnings,
                source_trail=source_trail,
            )
        warnings.append("Official full text was not convertible to AI-friendly Markdown.")
        return metadata_only_article(
            source="elsevier_xml",
            metadata=article_metadata,
            doi=doi or None,
            warnings=warnings,
            source_trail=source_trail,
        )
