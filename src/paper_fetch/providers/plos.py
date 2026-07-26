"""PLOS public JATS XML provider client."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
from collections.abc import Mapping, Sequence
import re
import urllib.parse

from ..config import build_publisher_user_agent, resolve_asset_download_concurrency
from ..extraction.html.assets import (
    FIGURE_KIND,
    SUPPLEMENTARY_KIND,
    download_assets,
    html_asset_identity_key,
    split_body_and_supplementary_assets,
)
from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.provider_rules import ProviderFrontMatterRules, ProviderHtmlRules
from ..http import (
    DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    HttpTransport,
    PDF_MIME_TYPE,
    RequestFailure,
)
from ..http.headers import header_value
from ..models import (
    AssetProfile,
    SourceKind,
    article_from_markdown,
    metadata_only_article,
)
from ..provider_catalog import (
    BodyTextThresholds,
    ProviderSpec,
    provider_pdf_path_templates,
    provider_xml_path_templates,
)
from ..publisher_identity import normalize_doi
from ..runtime import RuntimeContext
from ..tracing import download_marker, fulltext_marker, trace_from_markers
from ..utils import empty_asset_results, normalize_text
from ._article_markdown_jats import parse_jats_xml
from ._payloads import build_provider_payload
from ._pdf_common import (
    default_pdf_headers,
    pdf_asset_output_dir,
    pdf_asset_profile_from_context,
    pdf_fetch_result_assets,
    pdf_fetch_result_warnings,
)
from ._pdf_fallback import PdfFallbackStrategy, PdfFetchFailure, fetch_pdf_over_http
from ._registry import ProviderBundle, register_provider_bundle
from .base import (
    ProviderArtifacts,
    ProviderClient,
    ProviderFailure,
    ProviderStatusResult,
    RawFulltextPayload,
    build_provider_status_check,
    combine_provider_failures,
    map_request_failure,
    summarize_capability_status,
)
from ..reason_codes import NO_RESULT, OK, PDF_FALLBACK


register_provider_bundle(
    ProviderBundle(
        catalog=ProviderSpec(
            name="plos",
            display_name="PLOS",
            official=True,
            domains=("journals.plos.org",),
            doi_prefixes=("10.1371/",),
            publisher_aliases=(
                "plos",
                "public library of science",
                "public library of science (plos)",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=False,
            client_factory_path="paper_fetch.providers.plos:PlosClient",
            status_order=13,
            domain_suffixes=("plos.org",),
            xml_path_templates=(
                "/{journal_path}/article/file?id={doi}&type=manuscript",
            ),
            pdf_path_templates=(
                "/{journal_path}/article/file?id={doi}&type=printable",
            ),
            emits_html_managed_marker=False,
            html_capable=False,
            xml_root_tags=("article",),
            xml_file_tokens=("10.1371", "plos"),
            body_text_thresholds=BodyTextThresholds(min_chars=1200),
        ),
        html_rules=ProviderHtmlRules(
            name="plos",
            front_matter=ProviderFrontMatterRules(
                exact_texts=(),
                contains_tokens=(),
                publication_keywords=("plos", "public library of science"),
            ),
            availability=AvailabilityPolicy(name="plos", no_signals=True),
        ),
        sources=("plos_xml", "plos_pdf"),
    )
)


PLOS_JOURNAL_PATHS = {
    "pbio": "plosbiology",
    "pcbi": "ploscompbiol",
    "pclm": "climate",
    "pdig": "digitalhealth",
    "pgen": "plosgenetics",
    "pgph": "globalpublichealth",
    "pmed": "plosmedicine",
    "pntd": "plosntds",
    "pone": "plosone",
    "ppat": "plospathogens",
    "pstr": "sustainabilitytransformation",
    "pwat": "water",
}
PLOS_DOI_JOURNAL_PATTERN = re.compile(
    r"^10\.1371/journal\.(?P<code>[a-z0-9]+)\.", flags=re.IGNORECASE
)
PLOS_HOST = "https://journals.plos.org"
PLOS_ASSET_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def _plos_journal_path(doi_or_asset_id: str) -> str:
    normalized = normalize_doi(doi_or_asset_id)
    match = PLOS_DOI_JOURNAL_PATTERN.match(normalized)
    if not match:
        raise ProviderFailure(
            NO_RESULT,
            f"PLOS DOI is not in a supported journal.* form: {doi_or_asset_id}",
        )
    code = match.group("code").lower()
    journal_path = PLOS_JOURNAL_PATHS.get(code)
    if not journal_path:
        raise ProviderFailure(
            NO_RESULT, f"PLOS journal code is not supported yet: {code}"
        )
    return journal_path


def _candidate_url(doi: str, *, templates: tuple[str, ...]) -> str:
    normalized_doi = normalize_doi(doi)
    journal_path = _plos_journal_path(normalized_doi)
    template = templates[0]
    return (
        f"{PLOS_HOST}{template.format(doi=normalized_doi, journal_path=journal_path)}"
    )


def _xml_candidate_url(doi: str) -> str:
    return _candidate_url(doi, templates=provider_xml_path_templates("plos"))


def _pdf_candidate_url(doi: str) -> str:
    return _candidate_url(doi, templates=provider_pdf_path_templates("plos"))


def _response_body(response: Mapping[str, Any]) -> bytes:
    body = response.get("body", b"")
    if isinstance(body, bytes):
        return body
    if isinstance(body, bytearray):
        return bytes(body)
    if isinstance(body, str):
        return body.encode("utf-8")
    return b""


def _looks_like_html(body: bytes, content_type: str) -> bool:
    lowered_type = normalize_text(content_type).lower()
    if "html" in lowered_type:
        return True
    prefix = body[:1024].lstrip().lower()
    return (
        prefix.startswith(b"<!doctype html")
        or prefix.startswith(b"<html")
        or b"<html" in prefix
    )


def _merge_assets(
    extracted_assets: Sequence[Mapping[str, Any]] | None,
    downloaded_assets: Sequence[Mapping[str, Any]] | None,
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


def _filter_assets_for_profile(
    assets: Sequence[Mapping[str, Any]] | None,
    *,
    asset_profile: AssetProfile,
) -> list[dict[str, Any]]:
    if asset_profile == "none":
        return []
    filtered: list[dict[str, Any]] = []
    for item in assets or []:
        asset = dict(item)
        kind = normalize_text(
            str(asset.get("kind") or asset.get("asset_type") or "")
        ).lower()
        section = normalize_text(str(asset.get("section") or "")).lower()
        if asset_profile != "all" and (
            kind == "supplementary" or section == "supplementary"
        ):
            continue
        filtered.append(asset)
    return filtered


def _doi_asset_id(value: str) -> str:
    normalized = normalize_text(value)
    if normalized.startswith("info:doi/"):
        return normalize_text(normalized.removeprefix("info:doi/"))
    if "10.1371/journal." in normalized:
        return normalized[normalized.find("10.1371/journal.") :]
    return ""


def _plos_figure_image_url(asset_id: str) -> str:
    journal_path = _plos_journal_path(asset_id)
    return f"{PLOS_HOST}/{journal_path}/article/figure/image?size=large&id={asset_id}"


def _plos_formula_image_url(asset_id: str) -> str:
    journal_path = _plos_journal_path(asset_id)
    return f"{PLOS_HOST}/{journal_path}/article/file?id={asset_id}&type=thumbnail"


def _plos_supplementary_file_url(asset_id: str) -> str:
    journal_path = _plos_journal_path(asset_id)
    return f"{PLOS_HOST}/{journal_path}/article/file?type=supplementary&id={asset_id}"


def _is_plos_formula_asset(asset: Mapping[str, Any], asset_id: str) -> bool:
    kind = normalize_text(
        str(asset.get("kind") or asset.get("asset_type") or "")
    ).lower()
    return kind == "formula" or bool(
        re.search(r"\.e\d+\Z", normalize_text(asset_id), flags=re.IGNORECASE)
    )


def _plos_figure_candidates(
    _transport, *, asset, user_agent, figure_page_fetcher=None
) -> list[str]:
    del _transport, user_agent, figure_page_fetcher
    candidates: list[str] = []
    for key in ("url", "full_size_url", "download_url", "original_url", "link"):
        value = normalize_text(str(asset.get(key) or ""))
        asset_id = _doi_asset_id(value)
        if asset_id:
            candidates.append(
                _plos_formula_image_url(asset_id)
                if _is_plos_formula_asset(asset, asset_id)
                else _plos_figure_image_url(asset_id)
            )
        elif value.startswith("http://") or value.startswith("https://"):
            candidates.append(value)
    return list(dict.fromkeys(candidates))


def _fetch_plos_redirected_image(
    transport: HttpTransport,
    candidate_url: str,
    *,
    headers: Mapping[str, str],
) -> dict[str, Any] | None:
    current_url = candidate_url
    for _ in range(4):
        response = transport.request(
            "GET",
            current_url,
            headers=headers,
            timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
            retry_on_rate_limit=True,
            retry_on_transient=True,
        )
        status_code = int(response.get("status_code") or 200)
        if status_code not in PLOS_ASSET_REDIRECT_STATUSES:
            return response
        response_headers = (
            response.get("headers")
            if isinstance(response.get("headers"), Mapping)
            else {}
        )
        location = header_value(response_headers, "location")
        if not location:
            return response
        current_url = urllib.parse.urljoin(current_url, location)
    return None


def _normalize_plos_supplementary_assets(
    assets: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    normalized_assets: list[dict[str, Any]] = []
    for item in assets:
        asset = dict(item)
        for key in ("url", "download_url", "original_url", "link"):
            asset_id = _doi_asset_id(str(asset.get(key) or ""))
            if not asset_id:
                continue
            url = _plos_supplementary_file_url(asset_id)
            asset["link"] = url
            asset["original_url"] = url
            asset["download_url"] = url
            break
        normalized_assets.append(asset)
    return normalized_assets


class PlosClient(ProviderClient):
    name = "plos"

    def __init__(self, transport: HttpTransport, env: Mapping[str, str]) -> None:
        self.transport = transport
        self.env = dict(env)
        self.user_agent = build_publisher_user_agent(env)

    def probe_status(self) -> ProviderStatusResult:
        return summarize_capability_status(
            self.name,
            official_provider=self.official_provider,
            checks=[
                build_provider_status_check(
                    "xml_route",
                    OK,
                    "PLOS public JATS XML route is available without provider credentials.",
                    details={"mode": "direct_http_xml"},
                ),
                build_provider_status_check(
                    PDF_FALLBACK,
                    OK,
                    "PLOS printable PDF fallback is available when XML is not usable; body/all asset requests can save exported PDF images when artifacts are enabled.",
                    details={"mode": "direct_http_pdf"},
                ),
            ],
        )

    def _xml_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/xml,text/xml,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "User-Agent": self.user_agent,
        }

    def _asset_headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent}

    def _fetch_xml_payload(
        self, doi: str, metadata: Mapping[str, Any]
    ) -> RawFulltextPayload:
        candidate = _xml_candidate_url(doi)
        try:
            response = self.transport.request(
                "GET",
                candidate,
                headers=self._xml_headers(),
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            raise map_request_failure(exc) from exc

        status_code = int(response.get("status_code") or 200)
        if status_code >= 400:
            raise ProviderFailure(
                NO_RESULT, f"PLOS XML endpoint returned HTTP {status_code}."
            )
        headers = (
            response.get("headers")
            if isinstance(response.get("headers"), Mapping)
            else {}
        )
        content_type = header_value(headers, "content-type", "application/xml")
        body = _response_body(response)
        if not body:
            raise ProviderFailure(
                NO_RESULT, "PLOS XML endpoint returned an empty body."
            )
        if _looks_like_html(body, content_type):
            raise ProviderFailure(
                NO_RESULT, "PLOS XML endpoint returned HTML instead of JATS XML."
            )

        final_url = normalize_text(str(response.get("url") or candidate)) or candidate
        extraction = parse_jats_xml(body, source_url=final_url, base_metadata=metadata)
        if extraction is None:
            raise ProviderFailure(
                NO_RESULT, "PLOS XML response did not parse as a JATS article."
            )
        if (
            not normalize_text(extraction.markdown_text)
            and not extraction.references
            and not extraction.abstract_sections
        ):
            raise ProviderFailure(
                NO_RESULT,
                "PLOS XML response did not contain article body, references, or abstract text.",
            )

        return build_provider_payload(
            provider=self.name,
            route_kind="xml",
            source_url=final_url,
            content_type=content_type,
            body=body,
            markdown_text=extraction.markdown_text,
            merged_metadata=extraction.metadata,
            diagnostics={
                "extraction": {
                    "abstract_sections": extraction.abstract_sections,
                    "references": extraction.references,
                    "references_count": len(extraction.references),
                    "assets_count": len(extraction.assets),
                    "conversion_notes": list(extraction.conversion_notes),
                    "semantic_losses": asdict(extraction.semantic_losses),
                }
            },
            reason="Downloaded full text from the PLOS public JATS XML route.",
            extracted_assets=extraction.assets,
            trace_markers=[fulltext_marker(self.name, "ok", route="xml")],
        )

    def _fetch_pdf_payload(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        xml_failure_message: str,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        candidate = _pdf_candidate_url(doi)
        effective_asset_profile = pdf_asset_profile_from_context(context)
        try:
            pdf_result = PdfFallbackStrategy(
                transport=self.transport,
                headers=default_pdf_headers(self.user_agent, referer=candidate),
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                asset_profile=effective_asset_profile,
                asset_output_dir=pdf_asset_output_dir(
                    context, asset_profile=effective_asset_profile, doi=doi
                ),
                fetcher=fetch_pdf_over_http,
            ).fetch([candidate])
        except PdfFetchFailure as exc:
            raise ProviderFailure(NO_RESULT, exc.message) from exc

        article_metadata = dict(metadata)
        article_metadata.setdefault("doi", normalize_doi(doi) or doi)
        return build_provider_payload(
            provider=self.name,
            route_kind=PDF_FALLBACK,
            source_url=pdf_result.final_url or pdf_result.source_url or candidate,
            content_type=PDF_MIME_TYPE,
            body=pdf_result.pdf_bytes,
            markdown_text=pdf_result.markdown_text,
            merged_metadata=article_metadata,
            diagnostics={PDF_FALLBACK: {"candidates": [candidate]}},
            reason="Downloaded full text from the PLOS printable PDF fallback after XML was not usable.",
            suggested_filename=pdf_result.suggested_filename,
            extracted_assets=pdf_fetch_result_assets(pdf_result),
            html_failure_message=xml_failure_message,
            warnings=[
                *pdf_fetch_result_warnings(pdf_result),
                f"PLOS XML route was not usable ({xml_failure_message}); used printable PDF fallback.",
            ],
            trace_markers=[
                fulltext_marker(self.name, "fail", route="xml"),
                fulltext_marker(self.name, "ok", route=PDF_FALLBACK),
            ],
            content_needs_local_copy=True,
            needs_local_copy=True,
        )

    def fetch_raw_fulltext(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        context = self._runtime_context(context)
        failures: list[tuple[str, ProviderFailure]] = []
        try:
            return self._fetch_xml_payload(doi, metadata)
        except ProviderFailure as exc:
            failures.append(("xml", exc))

        xml_failure = failures[-1][1]
        try:
            return self._fetch_pdf_payload(
                doi,
                metadata,
                xml_failure_message=xml_failure.message,
                context=context,
            )
        except ProviderFailure as exc:
            failures.append(("pdf", exc))

        combined = combine_provider_failures(failures)
        raise ProviderFailure(
            combined.code,
            "PLOS full-text routes were not usable. " + combined.message,
            warnings=combined.warnings,
            source_trail=[
                fulltext_marker(self.name, "fail", route="xml"),
                fulltext_marker(self.name, "fail", route="pdf"),
                *combined.source_trail,
            ],
        )

    def should_download_related_assets_for_result(
        self,
        raw_payload: RawFulltextPayload,
        *,
        provisional_article=None,
    ) -> bool:
        del provisional_article
        content = raw_payload.content
        return (
            normalize_text(content.route_kind if content is not None else "").lower()
            != PDF_FALLBACK
        )

    def download_related_assets(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        output_dir: Path | None,
        *,
        asset_profile: AssetProfile = "all",
        context: RuntimeContext | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        context = self._runtime_context(context, output_dir=output_dir)
        if output_dir is None or asset_profile == "none":
            return empty_asset_results()
        content = raw_payload.content
        route = normalize_text(
            content.route_kind if content is not None else ""
        ).lower()
        if route == PDF_FALLBACK:
            return empty_asset_results()
        extracted_assets = _filter_assets_for_profile(
            list(content.extracted_assets if content is not None else []),
            asset_profile=asset_profile,
        )
        if not extracted_assets:
            return empty_asset_results()

        body_assets, supplementary_assets = split_body_and_supplementary_assets(
            extracted_assets
        )
        body_image_assets = [
            dict(item)
            for item in body_assets
            if normalize_text(
                str(item.get("kind") or item.get("asset_type") or "")
            ).lower()
            in {"figure", "formula"}
        ]
        merged_metadata = content.merged_metadata if content is not None else None
        article_id = (
            normalize_doi(str((merged_metadata or {}).get("doi") or doi or ""))
            or normalize_doi(doi)
            or normalize_text(str(metadata.get("title") or ""))
            or raw_payload.source_url
        )

        body_result = (
            download_assets(
                FIGURE_KIND,
                self.transport,
                article_id=article_id,
                assets=body_image_assets,
                output_dir=output_dir,
                user_agent=self.user_agent,
                asset_profile=asset_profile,
                headers=self._asset_headers(),
                candidate_builder=_plos_figure_candidates,
                document_fetcher=lambda url, _asset: _fetch_plos_redirected_image(
                    self.transport,
                    url,
                    headers=self._asset_headers(),
                ),
                asset_download_concurrency=resolve_asset_download_concurrency(
                    context.env
                ),
            )
            if body_image_assets
            else empty_asset_results()
        )
        normalized_supplementary = _normalize_plos_supplementary_assets(
            supplementary_assets
        )
        supplementary_result = (
            download_assets(
                SUPPLEMENTARY_KIND,
                self.transport,
                article_id=article_id,
                assets=normalized_supplementary,
                output_dir=output_dir,
                user_agent=self.user_agent,
                asset_profile=asset_profile,
                headers=self._asset_headers(),
                asset_download_concurrency=resolve_asset_download_concurrency(
                    context.env
                ),
            )
            if normalized_supplementary and asset_profile == "all"
            else empty_asset_results()
        )
        return {
            "assets": [
                *list(body_result.get("assets") or []),
                *list(supplementary_result.get("assets") or []),
            ],
            "asset_failures": [
                *list(body_result.get("asset_failures") or []),
                *list(supplementary_result.get("asset_failures") or []),
            ],
        }

    def to_article_model(
        self,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
        context: RuntimeContext | None = None,
    ):
        del context
        content = raw_payload.content
        merged_metadata = (
            content.merged_metadata
            if content is not None
            else raw_payload.merged_metadata
        )
        article_metadata = dict(
            merged_metadata if isinstance(merged_metadata, Mapping) else metadata
        )
        doi = normalize_doi(
            str(article_metadata.get("doi") or metadata.get("doi") or "")
        )
        route = normalize_text(
            content.route_kind if content is not None else ""
        ).lower()
        trace = list(
            raw_payload.trace
            or trace_from_markers([fulltext_marker(self.name, "ok", route="xml")])
        )
        warnings = list(raw_payload.warnings)
        if asset_failures:
            warnings.append(
                f"PLOS related assets were only partially downloaded ({len(asset_failures)} failed)."
            )

        source: SourceKind = "plos_pdf" if route == PDF_FALLBACK else "plos_xml"
        markdown_text = str(
            (content.markdown_text if content is not None else "") or ""
        ).strip()
        if not markdown_text:
            warnings.append("PLOS retrieval did not produce usable Markdown.")
            return metadata_only_article(
                source=source,
                metadata=article_metadata,
                doi=doi or None,
                warnings=warnings,
                trace=trace,
            )

        diagnostics = (
            dict(content.diagnostics.get("extraction") or {})
            if content is not None
            else {}
        )
        references = diagnostics.get("references")
        if isinstance(references, list) and references:
            article_metadata["references"] = [
                dict(item) if isinstance(item, Mapping) else item for item in references
            ]
        abstract_sections = diagnostics.get("abstract_sections")
        semantic_losses = diagnostics.get("semantic_losses")
        assets = _merge_assets(
            list(content.extracted_assets if content is not None else []),
            list(downloaded_assets or []),
        )
        article = article_from_markdown(
            source=source,
            metadata=article_metadata,
            doi=normalize_doi(str(article_metadata.get("doi") or doi)) or None,
            markdown_text=markdown_text,
            abstract_sections=abstract_sections
            if isinstance(abstract_sections, list)
            else None,
            assets=assets,
            warnings=warnings,
            trace=trace,
            semantic_losses=semantic_losses
            if isinstance(semantic_losses, Mapping)
            else None,
        )
        if asset_failures:
            article.quality.asset_failures = [dict(item) for item in asset_failures]
        return article

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
        if (
            normalize_text(content.route_kind if content is not None else "").lower()
            != PDF_FALLBACK
        ):
            return artifacts
        pdf_assets = list(content.extracted_assets if content is not None else [])
        return ProviderArtifacts(
            assets=[*list(artifacts.assets), *pdf_assets],
            asset_failures=list(artifacts.asset_failures),
            allow_related_assets=False,
            text_only=not pdf_assets,
            skip_trace=trace_from_markers(
                [download_marker("plos_assets_skipped_text_only")]
            )
            if not pdf_assets
            else [],
        )


__all__ = ["PlosClient"]
