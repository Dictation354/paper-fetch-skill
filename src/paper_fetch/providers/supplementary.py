"""Supplementary-only acquisition, without body extraction or PDF fallback."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from bs4 import BeautifulSoup

from ..acquisition import AcquisitionProvenance
from ..arxiv_id import arxiv_id_from_query, canonical_arxiv_abs_url
from ..config import resolve_asset_download_concurrency
from ..extraction.html import decode_html
from ..extraction.html._metadata import parse_html_metadata
from ..extraction.html.assets import (
    AssetDownloadOptions,
    SUPPLEMENTARY_KIND,
    download_assets,
    split_body_and_supplementary_assets,
)
from ..extraction.html.assets.supplementary import extract_supplementary_assets
from ..extraction.html.landing import fetch_landing_html
from ..failure import FailureDiagnostics
from ..http import RequestFailure
from ..http.headers import header_value
from ..models.schema import SupplementaryResult
from ..publisher_identity import validate_extracted_identity
from ..reason_codes import ERROR, IDENTITY_MISMATCH, NO_ACCESS, NO_RESULT, NOT_SUPPORTED
from ..runtime import RuntimeContext
from ..utils import normalize_text
from ..xml_security import XmlParseFailure, parse_xml
from .base import (
    ProviderContent,
    ProviderFailure,
    RawFulltextPayload,
    map_request_failure,
)
from ._html_asset_engine import merge_assets_by_identity


def _verify_identity(metadata, observed):
    validation = validate_extracted_identity(metadata, {}, observed)
    if validation.status != "match":
        raise ProviderFailure(
            IDENTITY_MISMATCH if validation.status == "mismatch" else ERROR,
            validation.reason or "Supplementary index identity could not be verified.",
            diagnostics=FailureDiagnostics(
                error_category="identity_"
                + ("mismatch" if validation.status == "mismatch" else "unverified")
            ),
        )


def _semantic_scope(html_text: str) -> str:
    """Select explicit material sections when a provider has no scoped extractor."""
    soup = BeautifulSoup(html_text, "html.parser")
    roots = []
    tokens = (
        "supplement",
        "supporting",
        "source data",
        "source-data",
        "extended data",
        "extended-data",
        "multimedia",
    )
    for node in soup.find_all(True):
        identity = " ".join(
            [str(node.get("id") or ""), " ".join(node.get("class") or [])]
        ).lower()
        heading = (
            node.get_text(" ", strip=True).lower()
            if node.name in {"h2", "h3", "h4"}
            else ""
        )
        if any(token in identity for token in tokens):
            roots.append(str(node))
        elif heading and any(token in heading for token in tokens):
            parent = node.parent
            if parent and parent.name in {"section", "div", "li"}:
                roots.append(str(parent))
    # Explicit standalone attachment links are valid even on abstract/paywall pages.
    for anchor in soup.find_all("a", href=True):
        text = anchor.get_text(" ", strip=True).lower()
        href = str(anchor.get("href") or "").lower()
        if any(token in text for token in tokens) or "/article-supplement/" in href:
            roots.append(str(anchor))
    return "\n".join(roots)


def _html_assets(client, html_text, source_url, context):
    from .browser_workflow.client import BrowserWorkflowClient
    from ._springer_assets import extract_html_assets as springer_assets

    if client.name == "springer":
        assets = springer_assets(html_text, source_url, asset_profile="all")
        if not assets:
            from ._springer_assets import _springer_asset_is_peer_review

            assets = [
                asset
                for asset in extract_supplementary_assets(
                    _semantic_scope(html_text),
                    source_url,
                    noise_profile="springer_nature",
                )
                if not _springer_asset_is_peer_review(asset.get("heading", ""))
            ]
    elif isinstance(client, BrowserWorkflowClient):
        from .browser_workflow.assets import _cached_browser_workflow_assets
        from ..extraction.html.signals import HtmlExtractionFailure

        try:
            assets = _cached_browser_workflow_assets(
                client,
                html_text,
                source_url,
                asset_profile="all",
                context=context,
            )
        except HtmlExtractionFailure:
            assets = []
        # Some provider scopes require a body container. Explicit attachment sections
        # on abstract pages remain discoverable without accepting a body.
        assets.extend(
            extract_supplementary_assets(
                _semantic_scope(html_text), source_url, noise_profile=client.name
            )
        )
    elif client.name == "ieee":
        from ._ieee_supplementary import (
            _extract_ieee_supplementary_assets as ieee_assets,
        )

        assets = ieee_assets(html_text, source_url)
    else:
        assets = extract_supplementary_assets(
            _semantic_scope(html_text), source_url, noise_profile=client.name
        )
    _, supplements = split_body_and_supplementary_assets(assets)
    return merge_assets_by_identity([dict(asset) for asset in supplements])


def _fetch_browser_index(client, doi, metadata, context, candidates=None):
    from .browser_runtime import BrowserHtmlFetchOptions, BrowserHtmlReadiness
    from .browser_workflow.client import BrowserWorkflowClient
    from . import browser_runtime

    if isinstance(client, BrowserWorkflowClient):
        deps: Any = client.deps
        profile = client.require_profile()
        runtime = deps.load_runtime_config(client.env, provider=client.name, doi=doi)
        if not profile.persistent_storage_state:
            runtime = replace(
                runtime,
                profile_dir=None,
                user_data_dir=None,
                storage_state_path=None,
                persist_storage_state=False,
            )
        candidates = client.html_candidates(doi, metadata)
        options = BrowserHtmlFetchOptions(
            supplementary_index=True,
            blocked_resource_types=profile.blocked_resource_types or None,
            empty_script_response_urls=profile.empty_script_response_urls,
            readiness_budget_seconds=profile.html_readiness_budget_seconds,
        )
    else:
        deps = browser_runtime
        runtime = deps.load_runtime_config(client.env, provider=client.name, doi=doi)
        options = BrowserHtmlFetchOptions(supplementary_index=True)
    deps.ensure_runtime_ready(runtime)
    from .browser_runtime import BrowserRuntimeFailure

    try:
        return deps.fetch_html_with_browser(
            candidates,
            publisher=client.name,
            config=runtime,
            runtime_context=context,
            readiness=BrowserHtmlReadiness(wait_for_article_body=False),
            options=options,
        )
    except BrowserRuntimeFailure as exc:
        raise ProviderFailure(
            exc.kind,
            exc.message,
            diagnostics=FailureDiagnostics(
                provider=client.name,
                route="supplementary",
                stage="discovery",
                error_category=exc.kind,
                details=dict(exc.details),
            ),
        ) from exc


def _browser_index(client, doi, metadata, context):
    result = _fetch_browser_index(client, doi, metadata, context)
    observed = parse_html_metadata(result.html, result.final_url)
    _verify_identity(metadata, observed)
    return RawFulltextPayload(
        provider=client.name,
        content=ProviderContent(
            route_kind="html",
            source_url=result.final_url,
            content_type="text/html",
            body=result.html.encode(),
            merged_metadata=metadata,
            browser_context_seed=dict(result.browser_context_seed or {}),
            extracted_assets=_html_assets(
                client, result.html, result.final_url, context
            ),
        ),
    )


def _xml_candidates(client, doi, metadata):
    if client.name == "plos":
        from .plos import _candidate_url
        from ..provider_catalog import provider_xml_path_templates

        journal_path, _ = client._resolve_journal_path(doi, metadata)
        return [
            _candidate_url(
                doi,
                templates=provider_xml_path_templates("plos"),
                journal_path=journal_path,
            )
        ]
    if client.name == "frontiers":
        return [
            route.xml_url
            for route in client.route_candidates(doi, metadata)
            if route.xml_url
        ]
    if client.name == "elsevier":
        return [client._official_article_url(doi)]
    return []


def _xml_index(client, doi, metadata, context):
    from ._article_markdown_jats_blocks import _supplementary_entries
    from ._article_markdown_jats import extract_jats_metadata

    for url in _xml_candidates(client, doi, metadata):
        headers = (
            client._base_headers("text/xml")
            if client.name == "elsevier"
            else client._xml_headers()
        )
        if client.name == "plos":
            from .plos import _fetch_plos_redirected_response

            response = _fetch_plos_redirected_response(
                client.transport, url, headers=headers
            )
        else:
            response = client.transport.request(
                "GET",
                url,
                headers=headers,
                timeout=60,
                retry_on_transient=True,
                **({"query": {"view": "FULL"}} if client.name == "elsevier" else {}),
            )
        if not response:
            continue
        body = bytes(response.get("body") or b"")
        content_type = header_value(response.get("headers"), "content-type")
        if b"<html" in body[:500].lower() or "html" in content_type:
            continue
        root = parse_xml(
            body, source="supplementary index", allow_external_doctype=True
        )
        source_url = str(response.get("url") or url)
        observed = extract_jats_metadata(root, source_url=source_url)
        if client.name == "elsevier":
            from .elsevier import extract_elsevier_asset_references

            # Elsevier XML uses dc:identifier, rather than the JATS article-id.
            observed = {}
            for node in root.iter():
                if str(node.tag).endswith("}doi") or str(node.tag) == "doi":
                    observed["doi"] = normalize_text(node.text)
                    break
            assets = [
                {
                    **ref,
                    "kind": "supplementary",
                    "section": "supplementary",
                    "heading": ref.get("filename_hint")
                    or ref.get("source_ref")
                    or "Supplementary Material",
                    "url": ref.get("source_url"),
                    "download_url": ref.get("source_url"),
                }
                for ref in extract_elsevier_asset_references(body, xml_root=root)
                if ref.get("asset_type") == "supplementary"
            ]
        else:
            assets = _supplementary_entries(root, source_url)
        _verify_identity(
            metadata,
            {
                "doi": observed.get("response_doi") or observed.get("doi"),
                "title": observed.get("title"),
            },
        )
        if client.name == "plos":
            from .plos import _normalize_plos_supplementary_assets

            assets = _normalize_plos_supplementary_assets(assets)
        if client.name == "frontiers":
            from .frontiers import _normalize_frontiers_extracted_assets

            assets, _ = _normalize_frontiers_extracted_assets(
                assets,
                doi=doi,
                landing_url=str(metadata.get("landing_page_url") or source_url),
            )
            assets = client._resolve_supplementary_urls(assets, doi)
        return RawFulltextPayload(
            provider=client.name,
            content=ProviderContent(
                route_kind="xml",
                source_url=source_url,
                content_type=content_type or "application/xml",
                body=body,
                merged_metadata=metadata,
                extracted_assets=assets,
            ),
        )
    return None


def _http_index(client, doi, metadata, context):
    if client.name == "ieee":
        from ._ieee_landing import resolve_ieee_landing_url

        url = resolve_ieee_landing_url(client, doi, metadata)
    elif client.name == "copernicus":
        url = client._resolve_landing_url(doi, metadata)
    else:
        url = str(metadata.get("landing_page_url") or f"https://doi.org/{doi}")
    browser_seed = {}
    try:
        result = fetch_landing_html(
            url,
            transport=client.transport,
            headers={"User-Agent": client.user_agent, "Accept": "text/html"},
            retry_on_transient=True,
        )
    except RequestFailure as exc:
        if client.name not in {"ieee", "springer"} or exc.status_code not in {
            401,
            403,
            429,
        }:
            raise
        from ..extraction.html.landing import build_landing_html_result

        browser_result = _fetch_browser_index(client, doi, metadata, context, [url])
        browser_seed = dict(browser_result.browser_context_seed or {})
        result = build_landing_html_result(
            {
                "url": browser_result.final_url,
                "body": browser_result.html.encode(),
                "status_code": browser_result.response_status,
                "headers": browser_result.response_headers,
            },
            current_url=url,
            decoder=decode_html,
            metadata_parser=parse_html_metadata,
        )
    from ..extraction.html.signals import detect_html_block, summarize_html

    blocked = detect_html_block(
        "",
        summarize_html(result.html_text),
        result.status_code,
        html_text=result.html_text,
        response_headers=result.headers,
        include_paywall_text=False,
    )
    if blocked is not None:
        raise ProviderFailure(
            NO_ACCESS if blocked.reason != "publisher_not_found" else ERROR,
            blocked.message,
            diagnostics=FailureDiagnostics(
                provider=client.name,
                route="supplementary",
                stage="discovery",
                error_category=blocked.reason,
            ),
        )
    if client.name != "ieee":
        _verify_identity(metadata, result.metadata)
    assets = _html_assets(client, result.html_text, result.final_url, context)
    discovery_failures = []
    index_urls = []
    if client.name == "ieee":
        from . import _ieee_metadata as ieee_metadata
        from ._ieee_supplementary import fetch_ieee_multimedia_assets
        from ._ieee_url import _article_number_from_url, _article_number_from_metadata

        landing_metadata = ieee_metadata._parse_landing_metadata(result.html_text)
        _verify_identity(
            metadata,
            {
                "doi": landing_metadata.get("doi") or result.metadata.get("doi"),
                "title": landing_metadata.get("title") or result.metadata.get("title"),
            },
        )
        number = _article_number_from_metadata(
            landing_metadata
        ) or _article_number_from_url(result.final_url)
        attempt = ieee_metadata.IeeeLandingAttempt(
            normalized_doi=doi,
            landing_url=url,
            response_url=result.final_url,
            html_text=result.html_text,
            merged_metadata=dict(metadata),
            article_number=number,
            landing_metadata=landing_metadata,
            acquisition_source="http",
        )
        if number:
            multimedia_url = client._multimedia_url(number)
            index_urls.append(multimedia_url)
            try:
                assets.extend(
                    fetch_ieee_multimedia_assets(
                        client.transport,
                        attempt,
                        multimedia_url=multimedia_url,
                        headers=client._multimedia_headers(result.final_url),
                        runtime_context=context,
                        strict=True,
                    )
                )
            except (RequestFailure, ValueError, TypeError) as exc:
                discovery_failures.append(
                    {
                        "kind": "supplementary",
                        "heading": "Multimedia index",
                        "source_url": multimedia_url,
                        "reason": "ieee_multimedia_discovery_failed",
                        "message": str(exc),
                    }
                )
    return RawFulltextPayload(
        provider=client.name,
        content=ProviderContent(
            route_kind="html",
            source_url=result.final_url,
            content_type="text/html",
            body=result.html_text.encode(),
            merged_metadata=metadata,
            extracted_assets=assets,
            diagnostics={
                "supplementary_discovery_failures": discovery_failures,
                "supplementary_index_urls": index_urls,
            },
            browser_context_seed=browser_seed,
        ),
    )


def fetch_provider_supplementary(
    client: Any,
    doi: str,
    metadata: Mapping[str, Any],
    output_dir: Path | None,
    *,
    context: RuntimeContext,
):
    """Return materials and index provenance; never construct an ArticleModel."""
    from .browser_workflow.client import BrowserWorkflowClient

    supported = {
        "arxiv",
        "springer",
        "ieee",
        "plos",
        "frontiers",
        "copernicus",
        "elsevier",
    }
    if not isinstance(client, BrowserWorkflowClient) and client.name not in supported:
        raise ProviderFailure(
            NOT_SUPPORTED, f"{client.name} does not support supplementary retrieval."
        )
    context.raise_if_cancelled()
    if client.name == "arxiv":
        from ._arxiv_assets import discover_arxiv_ancillary_assets

        arxiv_id = arxiv_id_from_query(str(metadata.get("arxiv_id") or doi))
        arxiv_id, discovery = discover_arxiv_ancillary_assets(
            client.transport,
            arxiv_id,
            user_agent=client.user_agent,
            context=context,
        )
        source_url = canonical_arxiv_abs_url(arxiv_id)
        assets = discovery["assets"]
        result = SupplementaryResult(
            assets=assets,
            asset_failures=discovery["asset_failures"],
            discovery_complete=not discovery["asset_failures"],
            identity_verified=not discovery["asset_failures"],
            source_urls=[
                source_url,
                *([f"https://arxiv.org/src/{arxiv_id}/anc"] if assets else []),
            ],
        )
        raw = None
        acquisition = AcquisitionProvenance(
            provider=client.name,
            route="source_assets",
            representation="html",
            transport="http",
        )
    else:
        try:
            raw = (
                _browser_index(client, doi, metadata, context)
                if isinstance(client, BrowserWorkflowClient)
                else None
            )
            if raw is None and client.name in {"plos", "frontiers", "elsevier"}:
                try:
                    raw = _xml_index(client, doi, metadata, context)
                except (RequestFailure, XmlParseFailure):
                    raw = None
                except ProviderFailure as exc:
                    if (
                        exc.code not in {NO_RESULT, NO_ACCESS}
                        and exc.error_category != "identity_unverified"
                    ):
                        raise
                    raw = None
            if raw is None:
                raw = _http_index(client, doi, metadata, context)
        except RequestFailure as exc:
            failure = map_request_failure(exc)
            if failure.code == NO_RESULT:
                failure = failure.with_updates(code=ERROR)
            raise failure from exc
        assets = merge_assets_by_identity(
            [
                {
                    **asset,
                    "source_page_url": asset.get("source_page_url") or raw.source_url,
                }
                for asset in raw.content.extracted_assets
            ]
        )
        discovery_failures = raw.content.diagnostics.get(
            "supplementary_discovery_failures", []
        )
        result = SupplementaryResult(
            assets=assets,
            asset_failures=discovery_failures,
            discovery_complete=not discovery_failures,
            identity_verified=True,
            source_urls=[
                raw.source_url,
                *raw.content.diagnostics.get("supplementary_index_urls", []),
            ],
        )
        acquisition = AcquisitionProvenance(
            provider=client.name,
            route="supplementary",
            representation=raw.content.route_kind,
            transport="browser"
            if isinstance(client, BrowserWorkflowClient)
            or raw.content.browser_context_seed
            else "http",
        )
    if output_dir is None:
        result.assets = [
            {
                **asset,
                "archive_state": "not_archived",
                "not_archived_reason": "Downloads were not requested or artifact storage is disabled.",
            }
            for asset in assets
        ]
        return result, acquisition
    if not assets:
        return result, acquisition
    context.raise_if_cancelled()
    if isinstance(client, BrowserWorkflowClient):
        assert raw is not None
        browser_assets: list[Mapping[str, Any]] = list(assets)
        downloaded = client._download_browser_backed_related_assets(
            doi,
            metadata,
            raw,
            output_dir,
            asset_profile="all",
            assets=browser_assets,
            context=context,
        )
    elif client.name == "springer":
        from ._springer_assets import download_assets_for_springer

        downloaded = download_assets_for_springer(
            client.transport,
            article_id=doi,
            assets=assets,
            output_dir=output_dir,
            user_agent=client.user_agent,
            runtime_context=context,
        )
    elif client.name in {"plos", "frontiers", "ieee"}:
        assert raw is not None
        raw.content = replace(raw.content, extracted_assets=assets)
        downloaded = client.download_related_assets(
            doi, metadata, raw, output_dir, asset_profile="all", context=context
        )
    else:
        downloaded = download_assets(
            SUPPLEMENTARY_KIND,
            client.transport,
            article_id=doi,
            assets=assets,
            output_dir=output_dir,
            user_agent=client.user_agent,
            asset_profile="all",
            options=AssetDownloadOptions(
                runtime_context=context,
                artifact_store=context.artifact_store,
                asset_budget=context.asset_budget,
                provider_name=client.name,
                asset_download_concurrency=resolve_asset_download_concurrency(
                    context.env
                ),
            ),
        )
    # Preserve every discovered item, including individual download failures.
    from ..extraction.html.assets import html_asset_identity_key

    local_by_key = {
        html_asset_identity_key(asset): asset for asset in downloaded.get("assets", [])
    }
    result.assets = [
        {**asset, **local_by_key.get(html_asset_identity_key(asset), {})}
        for asset in assets
    ]
    result.asset_failures.extend(downloaded.get("asset_failures", []))
    return result, acquisition
