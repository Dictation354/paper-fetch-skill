"""Elsevier provider client and XML asset helpers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

from ..config import build_user_agent, resolve_asset_download_concurrency
from ..http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, HttpTransport, RequestFailure, is_xml_content_type
from ..metadata_types import ProviderMetadata
from ..models import AssetProfile, article_from_markdown, article_from_structure, metadata_only_article
from ..publisher_identity import normalize_doi
from ..runtime import RuntimeContext
from ..tracing import trace_from_markers
from ..utils import (
    build_asset_output_path,
    choose_public_landing_page_url,
    dedupe_authors,
    empty_asset_results,
    first_non_empty,
    normalize_text,
    sanitize_filename,
    save_payload,
    strip_html_tags,
)
from ._article_markdown_elsevier_document import build_article_structure
from ._elsevier_xml_rules import (
    ELSEVIER_IMAGE_ASSET_TYPES,
    classify_elsevier_asset_kind,
    infer_elsevier_asset_group_key,
)
from ._pdf_common import (
    PdfFetchFailure,
    filename_from_headers,
    looks_like_pdf_payload,
    pdf_fetch_result_from_bytes,
)
from ._waterfall import ProviderWaterfallStep, ProviderWaterfallState, run_provider_waterfall
from ..quality.html_availability import (
    assess_plain_text_fulltext_availability,
    assess_structured_article_fulltext_availability,
)
from ..extraction.html.assets import download_supplementary_assets as download_generic_supplementary_assets
from .base import (
    ProviderArtifacts,
    ProviderClient,
    ProviderContent,
    ProviderFailure,
    ProviderStatusResult,
    RawFulltextPayload,
    build_provider_status_check,
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


def elsevier_xml_root_from_payload(
    xml_body: bytes,
    *,
    context: RuntimeContext | None = None,
    source_url: str | None = None,
) -> ET.Element | None:
    if context is None:
        try:
            return ET.fromstring(xml_body)
        except ET.ParseError:
            return None

    key = context.build_parse_cache_key(
        provider="elsevier",
        role="xml_root",
        source=source_url,
        body=xml_body,
        parser="xml.etree.ElementTree",
    )

    def parse_root() -> ET.Element | None:
        try:
            return ET.fromstring(xml_body)
        except ET.ParseError:
            return None

    return context.get_or_set_parse_cache(key, parse_root, copy_value=False)


def extract_elsevier_asset_references(
    xml_body: bytes,
    *,
    context: RuntimeContext | None = None,
    source_url: str | None = None,
    xml_root: ET.Element | None = None,
) -> list[dict[str, Any]]:
    root = xml_root if xml_root is not None else elsevier_xml_root_from_payload(
        xml_body,
        context=context,
        source_url=source_url,
    )
    if root is None:
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


def elsevier_asset_result_kind(asset_type: str | None) -> str:
    normalized = normalize_text(asset_type).lower()
    if normalized == "table_asset":
        return "table"
    if normalized == "supplementary":
        return "supplementary"
    return "figure"


def elsevier_asset_result_section(asset_type: str | None) -> str:
    normalized = normalize_text(asset_type).lower()
    if normalized == "supplementary":
        return "supplementary"
    if normalized == "appendix_image":
        return "appendix"
    return "body"


def download_elsevier_related_assets(
    transport: HttpTransport,
    *,
    doi: str,
    xml_body: bytes,
    output_dir: Path | None,
    headers: Mapping[str, str],
    asset_profile: AssetProfile = "all",
    context: RuntimeContext | None = None,
    source_url: str | None = None,
    asset_download_concurrency: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if output_dir is None:
        return empty_asset_results()

    references = filter_elsevier_asset_references(
        extract_elsevier_asset_references(xml_body, context=context, source_url=source_url),
        asset_profile=asset_profile,
    )
    if not references:
        return empty_asset_results()
    body_references = [reference for reference in references if reference.get("asset_type") != "supplementary"]
    supplementary_references = [reference for reference in references if reference.get("asset_type") == "supplementary"]
    if asset_download_concurrency is not None:
        try:
            active_asset_download_concurrency = max(1, int(asset_download_concurrency))
        except (TypeError, ValueError):
            active_asset_download_concurrency = resolve_asset_download_concurrency(context.env if context is not None else None)
    else:
        active_asset_download_concurrency = resolve_asset_download_concurrency(context.env if context is not None else None)

    asset_dir = output_dir / f"{sanitize_filename(doi)}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()
    downloads: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    def fetch_body_reference(
        reference: Mapping[str, Any],
    ) -> tuple[Mapping[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
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
            return reference, None, {
                "kind": elsevier_asset_result_kind(reference.get("asset_type")),
                "asset_type": reference["asset_type"],
                "source_kind": reference["source_kind"],
                "source_ref": reference["source_ref"],
                "source_url": reference["source_url"],
                "status": exc.status_code,
                "reason": str(exc),
                "section": elsevier_asset_result_section(reference.get("asset_type")),
            }
        return reference, dict(response), None

    resolved_body_results: list[tuple[Mapping[str, Any], dict[str, Any] | None, dict[str, Any] | None]] = []
    if body_references:
        with ThreadPoolExecutor(max_workers=min(active_asset_download_concurrency, len(body_references))) as executor:
            futures = [executor.submit(fetch_body_reference, reference) for reference in body_references]
            for future in futures:
                resolved_body_results.append(future.result())

    for reference, response, failure in resolved_body_results:
        if failure is not None:
            failures.append(failure)
            continue
        assert response is not None

        content_type = response["headers"].get("content-type", reference.get("content_type"))
        asset_type = reference.get("asset_type")
        output_path = build_asset_output_path(
            asset_dir,
            reference.get("filename_hint"),
            content_type,
            response["url"],
            used_names,
        )
        downloads.append(
            {
                "kind": elsevier_asset_result_kind(asset_type),
                "heading": reference.get("filename_hint") or reference.get("source_ref") or "Asset",
                "caption": "",
                "asset_type": asset_type,
                "source_kind": reference["source_kind"],
                "source_ref": reference["source_ref"],
                "download_url": reference["source_url"],
                "source_url": response["url"],
                "content_type": content_type,
                "path": save_payload(output_path, response["body"]),
                "downloaded_bytes": len(response["body"]),
                "section": elsevier_asset_result_section(asset_type),
                "download_tier": "object_reference",
            }
        )

    supplementary_result = download_generic_supplementary_assets(
        transport,
        article_id=doi,
        assets=[
            {
                "kind": "supplementary",
                "heading": reference.get("filename_hint") or reference.get("source_ref") or "Supplementary Material",
                "caption": "",
                "section": "supplementary",
                "url": reference.get("source_url"),
                "download_url": reference.get("source_url"),
                "source_url": reference.get("source_url"),
                "content_type": reference.get("content_type"),
                "filename_hint": reference.get("filename_hint"),
                "asset_type": reference.get("asset_type"),
                "source_kind": reference.get("source_kind"),
                "source_ref": reference.get("source_ref"),
                "attachment_type": reference.get("attachment_type"),
                "object_type": reference.get("object_type"),
                "category": reference.get("category"),
            }
            for reference in supplementary_references
        ],
        output_dir=output_dir,
        user_agent=headers.get("User-Agent", ""),
        asset_profile=asset_profile,
        headers=headers,
        asset_download_concurrency=active_asset_download_concurrency,
    )
    downloads.extend(list(supplementary_result.get("assets") or []))
    failures.extend(list(supplementary_result.get("asset_failures") or []))

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
            ],
        )

    def _official_article_url(self, doi: str) -> str:
        return f"https://api.elsevier.com/content/article/doi/{urllib.parse.quote(doi, safe='')}"

    def _fetch_official_payload(self, doi: str) -> RawFulltextPayload:
        return self._fetch_official_xml_payload(doi)

    def _fetch_official_xml_payload(self, doi: str) -> RawFulltextPayload:
        url = self._official_article_url(doi)
        try:
            response = self.transport.request(
                "GET",
                url,
                headers=self._base_headers("text/xml"),
                query={"view": "FULL"},
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_rate_limit=True,
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            if exc.status_code in {404, 406, 415}:
                if exc.status_code == 404:
                    raise ProviderFailure("no_result", str(exc)) from exc
                raise ProviderFailure(
                    "no_result",
                    "Elsevier official XML representation is not available for this article.",
                ) from exc
            raise map_request_failure(exc) from exc

        content_type = str((response.get("headers") or {}).get("content-type") or "text/xml")
        if not is_xml_content_type(content_type):
            raise ProviderFailure(
                "no_result",
                f"Elsevier official XML route returned unsupported content type: {content_type}",
            )
        return RawFulltextPayload(
            provider="elsevier",
            source_url=response["url"],
            content_type=content_type,
            body=response["body"],
            content=ProviderContent(
                route_kind="official",
                source_url=response["url"],
                content_type=content_type,
                body=response["body"],
                reason="Downloaded full text from the official Elsevier API.",
            ),
            trace=trace_from_markers(["fulltext:elsevier_xml_ok"]),
            needs_local_copy=False,
        )

    def _fetch_official_pdf_payload(self, doi: str) -> RawFulltextPayload:
        url = self._official_article_url(doi)
        try:
            response = self.transport.request(
                "GET",
                url,
                headers=self._base_headers("application/pdf"),
                query={"view": "FULL"},
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_rate_limit=True,
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            if exc.status_code in {404, 406, 415}:
                if exc.status_code == 404:
                    raise ProviderFailure("no_result", str(exc)) from exc
                raise ProviderFailure(
                    "no_result",
                    "Elsevier official PDF representation is not available for this article.",
                ) from exc
            raise map_request_failure(exc) from exc

        response_headers = {
            str(key).lower(): str(value)
            for key, value in (response.get("headers") or {}).items()
        }
        final_url = str(response.get("url") or url)
        pdf_bytes = bytes(response.get("body") or b"")
        content_type = str(response_headers.get("content-type") or "application/pdf")
        if not looks_like_pdf_payload(content_type, pdf_bytes, final_url):
            raise ProviderFailure(
                "no_result",
                "Elsevier official PDF fallback did not return a PDF file.",
            )
        try:
            pdf_result = pdf_fetch_result_from_bytes(
                artifact_dir=None,
                source_url=url,
                final_url=final_url,
                pdf_bytes=pdf_bytes,
                suggested_filename=filename_from_headers(response_headers),
            )
        except PdfFetchFailure as exc:
            message = str(exc) if str(exc).strip() else "Elsevier official PDF fallback was not usable."
            raise ProviderFailure("no_result", message) from exc

        return RawFulltextPayload(
            provider="elsevier",
            source_url=pdf_result.final_url,
            content_type="application/pdf",
            body=pdf_result.pdf_bytes,
            content=ProviderContent(
                route_kind="pdf_fallback",
                source_url=pdf_result.final_url,
                content_type="application/pdf",
                body=pdf_result.pdf_bytes,
                markdown_text=pdf_result.markdown_text,
                reason="Downloaded full text from the official Elsevier API PDF fallback.",
                suggested_filename=pdf_result.suggested_filename,
            ),
            trace=trace_from_markers(
                [
                    "fulltext:elsevier_pdf_api_ok",
                    "fulltext:elsevier_pdf_fallback_ok",
                ]
            ),
            needs_local_copy=True,
        )

    def _official_payload_is_usable(
        self,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        *,
        context: RuntimeContext | None = None,
    ) -> bool:
        context = self._runtime_context(context)
        article = self.to_article_model(metadata, raw_payload, context=context)
        title = normalize_text(str(metadata.get("title") or getattr(getattr(article, "metadata", None), "title", None) or ""))
        if is_xml_content_type(raw_payload.content_type):
            diagnostics = assess_structured_article_fulltext_availability(article, title=title or None)
            if raw_payload.content is not None:
                diagnostics_payload = dict(raw_payload.content.diagnostics)
                diagnostics_payload["availability_diagnostics"] = diagnostics.to_dict()
                raw_payload.content = replace(raw_payload.content, diagnostics=diagnostics_payload)
            return diagnostics.accepted
        if raw_payload.content_type.startswith("text/") and not is_xml_content_type(raw_payload.content_type):
            try:
                markdown_text = raw_payload.body.decode("utf-8", errors="replace")
            except Exception:
                return False
            diagnostics = assess_plain_text_fulltext_availability(markdown_text, metadata, title=title or None)
            if raw_payload.content is not None:
                diagnostics_payload = dict(raw_payload.content.diagnostics)
                diagnostics_payload["availability_diagnostics"] = diagnostics.to_dict()
                raw_payload.content = replace(raw_payload.content, diagnostics=diagnostics_payload)
            return diagnostics.accepted
        if raw_payload.content is not None:
            diagnostics_payload = dict(raw_payload.content.diagnostics)
            diagnostics_payload["availability_diagnostics"] = assess_structured_article_fulltext_availability(
                article,
                title=title or None,
            ).to_dict()
            raw_payload.content = replace(raw_payload.content, diagnostics=diagnostics_payload)
        return False

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

    def download_related_assets(
        self,
        doi: str,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        output_dir: Path | None,
        *,
        asset_profile: AssetProfile = "all",
        context: RuntimeContext | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        context = self._runtime_context(context, output_dir=output_dir)
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
            context=context,
            source_url=raw_payload.source_url,
        )

    def fetch_raw_fulltext(
        self,
        doi: str,
        metadata: ProviderMetadata,
        *,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        context = self._runtime_context(context)
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            raise ProviderFailure("not_supported", "Elsevier full-text retrieval requires a DOI.")

        def run_xml(_state: ProviderWaterfallState) -> RawFulltextPayload:
            xml_payload = self._fetch_official_xml_payload(normalized_doi)
            if self._official_payload_is_usable(metadata, xml_payload, context=context):
                return xml_payload
            raise ProviderFailure(
                "no_result",
                "Elsevier official XML response did not produce enough article body text.",
            )

        def xml_failure_warning(failure: ProviderFailure, _state: ProviderWaterfallState) -> str:
            if failure.message == "Elsevier official XML response did not produce enough article body text.":
                return "Elsevier official XML response did not produce enough article body text; attempting official PDF fallback."
            return f"Elsevier official XML route was not usable ({failure.message}); attempting official PDF fallback."

        return run_provider_waterfall(
            [
                ProviderWaterfallStep(
                    label="xml",
                    run=run_xml,
                    failure_marker="fulltext:elsevier_xml_fail",
                    failure_warning=xml_failure_warning,
                ),
                ProviderWaterfallStep(
                    label="pdf",
                    run=lambda _state: self._fetch_official_pdf_payload(normalized_doi),
                    failure_marker="fulltext:elsevier_pdf_api_fail",
                    success_markers=(
                        "fulltext:elsevier_pdf_api_ok",
                        "fulltext:elsevier_pdf_fallback_ok",
                    ),
                    success_warning="Full text was extracted from the Elsevier API PDF fallback after the XML route was not usable.",
                ),
            ],
        )

    def to_article_model(
        self,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
        context: RuntimeContext | None = None,
    ):
        context = self._runtime_context(context)
        content = raw_payload.content
        route = normalize_text(content.route_kind if content is not None else "").lower()
        merged_metadata = content.merged_metadata if content is not None else raw_payload.merged_metadata
        article_metadata = merged_metadata if isinstance(merged_metadata, Mapping) else metadata
        doi = normalize_doi(article_metadata.get("doi") or metadata.get("doi"))
        warnings = list(raw_payload.warnings)
        trace = list(raw_payload.trace)

        if route == "pdf_fallback":
            markdown_text = str((content.markdown_text if content is not None else "") or "").strip()
            if not markdown_text:
                warnings.append("Elsevier official PDF fallback did not produce usable Markdown.")
                return metadata_only_article(
                    source="elsevier_pdf",
                    metadata=article_metadata,
                    doi=doi or None,
                    warnings=warnings,
                    trace=[*trace, *trace_from_markers(["fulltext:elsevier_parse_fail"])],
                )
            return article_from_markdown(
                source="elsevier_pdf",
                metadata=article_metadata,
                doi=doi or None,
                markdown_text=markdown_text,
                warnings=warnings,
                trace=trace,
            )

        if is_xml_content_type(raw_payload.content_type):
            xml_root = elsevier_xml_root_from_payload(
                raw_payload.body,
                context=context,
                source_url=raw_payload.source_url,
            )
            pseudo_assets = (
                downloaded_assets
                if downloaded_assets
                else extract_elsevier_asset_references(
                    raw_payload.body,
                    context=context,
                    source_url=raw_payload.source_url,
                    xml_root=xml_root,
                )
            )
            xml_path = Path(f"{sanitize_filename(doi or str(metadata.get('title') or 'article'))}.xml")
            structure = build_article_structure(
                provider="elsevier",
                metadata=metadata,
                xml_body=raw_payload.body,
                xml_path=xml_path,
                assets=pseudo_assets,
                xml_root=xml_root,
            )
            if structure is not None:
                xml_article_metadata = dict(article_metadata)
                if structure.authors:
                    existing_authors = [
                        normalize_text(str(item))
                        for item in (article_metadata.get("authors") or [])
                        if normalize_text(str(item))
                    ]
                    xml_article_metadata["authors"] = dedupe_authors([*structure.authors, *existing_authors])
                return article_from_structure(
                    source="elsevier_xml",
                    metadata=xml_article_metadata,
                    doi=doi or None,
                    abstract_lines=structure.abstract_lines,
                    body_lines=structure.body_lines,
                    figure_entries=structure.figure_entries,
                    table_entries=structure.table_entries,
                    supplement_entries=structure.supplement_entries,
                    conversion_notes=structure.conversion_notes,
                    references=structure.references,
                    semantic_losses=structure.semantic_losses,
                    warnings=warnings,
                    trace=trace,
                    inline_figure_keys=sorted(structure.used_figure_keys),
                    inline_table_keys=sorted(structure.used_table_keys),
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
                trace=trace,
            )
        warnings.append("Official full text was not convertible to AI-friendly Markdown.")
        return metadata_only_article(
            source="elsevier_xml",
            metadata=article_metadata,
            doi=doi or None,
            warnings=warnings,
            trace=trace,
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
        route = normalize_text(content.route_kind if content is not None else "").lower()
        if route != "pdf_fallback":
            return artifacts
        return ProviderArtifacts(
            assets=list(artifacts.assets),
            asset_failures=list(artifacts.asset_failures),
            allow_related_assets=False,
            text_only=True,
            skip_warning=(
                "Elsevier PDF fallback currently returns text-only full text; "
                "figure and supplementary asset downloads are not implemented yet."
            ),
            skip_trace=trace_from_markers(["download:elsevier_assets_skipped_text_only"]),
        )
