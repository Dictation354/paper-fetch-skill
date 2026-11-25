"""Article-local image discovery and selective acquisition, independent of body reads."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import threading
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from .extraction.html import decode_html
from .extraction.html.assets import (
    FIGURE_KIND,
    AssetDownloadOptions,
    download_assets,
    extract_scoped_html_assets,
)
from .http import RequestFailure
from .manifest import parse_manifest_record
from .providers.base import ProviderContent, ProviderFailure, RawFulltextPayload
from .reason_codes import AUTH_REQUIRED
from .runtime import RuntimeContext

URL_FIELDS = (
    "url",
    "original_url",
    "download_url",
    "full_size_url",
    "preview_url",
    "source_url",
)
IMAGE_KINDS = {"figure", "formula", "table"}


def asset_urls(asset: Mapping[str, Any]) -> set[str]:
    return {str(asset[key]) for key in URL_FIELDS if asset.get(key)}


def image_index(assets: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Merge repeated references; IDs depend on source identity, never local paths."""
    result: list[dict[str, Any]] = []
    for raw in assets:
        asset = dict(raw)
        if not asset.get("url") and asset.get("link"):
            asset["url"] = asset["link"]
        kind = str(asset.get("kind") or asset.get("asset_type") or "").lower()
        if kind not in IMAGE_KINDS or (not asset_urls(asset) and not asset.get("path")):
            continue
        asset["kind"] = kind
        existing = next(
            (item for item in result if asset_urls(item) & asset_urls(asset)), None
        )
        if existing is not None:
            existing.update(
                {
                    key: value
                    for key, value in asset.items()
                    if value and not existing.get(key)
                }
            )
            if kind == "formula":
                existing["kind"] = kind
            continue
        identity = next(
            (
                str(asset[key])
                for key in ("url", "original_url", "download_url", "source_url", "path")
                if asset.get(key)
            ),
            "",
        )
        asset["asset_id"] = "img_" + hashlib.sha256(identity.encode()).hexdigest()[:20]
        result.append(asset)
    return result


@dataclass
class AssetContext:
    doi: str | None
    provider: str
    source_url: str
    assets: list[dict[str, Any]] = field(default_factory=list)
    discovery_complete: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    # A serializable seed only: no browser/page/client or credentials in public views.
    browser_context_seed: dict[str, Any] = field(default_factory=dict, repr=False)
    route_kind: str = "html"
    results: list[dict[str, Any]] = field(default_factory=list)
    lock: Any = field(default_factory=threading.RLock, repr=False)
    cleanup_temporary: bool = True
    _temporary: Path | None = field(default=None, repr=False)

    def fork(self):
        return AssetContext(
            doi=self.doi,
            provider=self.provider,
            source_url=self.source_url,
            assets=copy.deepcopy(self.assets),
            discovery_complete=self.discovery_complete,
            metadata=copy.deepcopy(self.metadata),
            browser_context_seed=copy.deepcopy(self.browser_context_seed),
            route_kind=self.route_kind,
        )

    def __deepcopy__(self, memo):
        return self.fork()

    def temporary_dir(self) -> Path:
        if self._temporary is None:
            self._temporary = Path(tempfile.mkdtemp(prefix="paper-fetch-images-"))
        return self._temporary

    def close(self) -> None:
        with self.lock:
            if self._temporary is not None and self.cleanup_temporary:
                shutil.rmtree(self._temporary, ignore_errors=True)
                self._temporary = None
            self.browser_context_seed.clear()

    def __del__(self):
        self.close()


def _representation(content: ProviderContent) -> str | None:
    if content.route_kind == "pdf_fallback" or "pdf" in content.content_type:
        return None
    if "html" in content.content_type or content.route_kind == "html":
        return "html"
    if "xml" in content.content_type or content.route_kind == "xml":
        return "xml"
    return None


def discover_content_images(
    content: ProviderContent,
    *,
    provider: str,
    client: Any = None,
    context: RuntimeContext | None = None,
) -> list[dict[str, Any]]:
    assets = list(content.extracted_assets)
    if _representation(content) == "xml" and not assets:
        assets = _xml_image_assets(content.body, content.source_url, provider)
    if _representation(content) == "html" and not assets:
        html = decode_html(content.body, content_type=content.content_type)
        if provider == "springer":
            from .providers._springer_assets import extract_html_assets

            assets = extract_html_assets(html, content.source_url, asset_profile="body")
        elif client is not None and hasattr(
            client, "_download_browser_backed_related_assets"
        ):
            from .providers.browser_workflow.assets import (
                _cached_browser_workflow_assets,
            )

            assets = _cached_browser_workflow_assets(
                client, html, content.source_url, asset_profile="body", context=context
            )
        else:
            assets = extract_scoped_html_assets(
                html, content.source_url, asset_profile="body", noise_profile=provider
            )
    return image_index(assets)


def _xml_image_assets(
    body: bytes, source_url: str, provider: str
) -> list[dict[str, Any]]:
    from .providers._article_markdown_jats_blocks import _figure_entry
    from .xml_security import parse_xml

    if provider == "elsevier":
        from .providers.elsevier import (
            elsevier_asset_result_kind,
            extract_elsevier_asset_references,
        )

        return [
            {
                **item,
                "kind": elsevier_asset_result_kind(item.get("asset_type")),
                "url": item.get("source_url"),
                "heading": item.get("source_ref") or "Image",
            }
            for item in extract_elsevier_asset_references(body, source_url=source_url)
        ]

    root = parse_xml(body, source="image index", allow_external_doctype=True)

    def local_name(node):
        return node.tag.rsplit("}", 1)[-1] if isinstance(node.tag, str) else ""

    assets = []
    parents = {child: parent for parent in root.iter() for child in parent}

    def image_kind(node):
        kind = "figure"
        while (node := parents.get(node)) is not None:
            name = local_name(node)
            if name in {"disp-formula", "inline-formula"}:
                return "formula"
            if name in {"table-wrap", "table"}:
                kind = "table"
        return kind

    for node in root.iter():
        name = local_name(node)
        if name == "fig":
            entry = _figure_entry(node, source_url)
            if entry:
                entry["kind"] = image_kind(node)
                assets.append(entry)
        elif name in {"graphic", "inline-graphic"}:
            href = node.get("{http://www.w3.org/1999/xlink}href") or node.get("href")
            if not href:
                continue
            assets.append(
                {
                    "kind": image_kind(node),
                    "heading": node.get("id") or name,
                    "url": urljoin(source_url, href),
                    "section": "body",
                }
            )
    if provider == "plos":
        from .providers.plos import _normalize_plos_asset_links
        from .publisher_identity import normalize_doi

        doi = next(
            (
                normalize_doi("".join(node.itertext()))
                for node in root.iter()
                if local_name(node) == "article-id" and node.get("pub-id-type") == "doi"
            ),
            "",
        )
        if doi:
            _normalize_plos_asset_links(assets, doi)
    return assets


def capture_asset_context(
    article: Any,
    content: ProviderContent | None,
    *,
    provider: str,
    client: Any,
    context: RuntimeContext,
) -> None:
    if content is None or _representation(content) is None:
        return
    from .extraction.html.signals import HtmlExtractionFailure
    from .xml_security import XmlParseFailure

    complete = True
    try:
        assets = discover_content_images(
            content, provider=provider, client=client, context=context
        )
    except (HtmlExtractionFailure, XmlParseFailure):
        assets = image_index(content.extracted_assets)
        complete = False
    assets = image_index([*assets, *(asdict(asset) for asset in article.assets)])
    state = AssetContext(
        doi=article.doi,
        provider=provider,
        source_url=content.source_url,
        assets=assets,
        discovery_complete=complete,
        metadata=asdict(article.metadata),
        browser_context_seed=dict(content.browser_context_seed),
        route_kind=_representation(content) or "html",
    )
    article.__dict__["_asset_context"] = state
    article.diagnostics["image_source_url"] = state.source_url
    article.diagnostics["image_provider"] = provider
    article.diagnostics["image_index"] = state.assets
    article.diagnostics["image_discovery_complete"] = state.discovery_complete


def context_from_envelope(envelope: Any) -> AssetContext:
    state = getattr(envelope, "_asset_context", None)
    if state is not None:
        return state
    from .provider_catalog import provider_for_source

    metadata = envelope.article.metadata if envelope.article else envelope.metadata
    details = asdict(metadata) if metadata else {}
    assets = image_index(
        [
            *envelope.diagnostics.get("image_index", []),
            *(
                [asdict(asset) for asset in envelope.article.assets]
                if envelope.article
                else []
            ),
        ]
    )
    return AssetContext(
        doi=envelope.doi,
        provider=envelope.diagnostics.get("image_provider")
        or provider_for_source(envelope.source)
        or envelope.source,
        source_url=envelope.diagnostics.get("image_source_url")
        or details.get("landing_page_url")
        or "",
        metadata=details,
        assets=assets,
        discovery_complete=bool(envelope.diagnostics.get("image_discovery_complete")),
    )


def _load_source(state: AssetContext, runtime: RuntimeContext) -> None:
    """Read a source page/index only; never call fetch_paper or a PDF converter."""
    from .auth import require_ams_auth
    from .extraction.html.landing import fetch_landing_html
    from .publisher_identity import validate_extracted_identity
    from .quality.access_boundary import raise_for_paywall

    if not state.source_url:
        raise ProviderFailure(
            "asset_index_unavailable", "No recoverable article source URL is available."
        )
    require_ams_auth(runtime.env or {}, provider=state.provider)
    client: Any = runtime.get_clients().get(state.provider)
    from .config import build_publisher_user_agent

    assert runtime.transport is not None
    landing = fetch_landing_html(
        state.source_url,
        transport=runtime.transport,
        max_redirects=5,
        headers={"User-Agent": build_publisher_user_agent(runtime.env or {})},
    )
    html, source_url = landing.html_text, landing.final_url
    observed_metadata = landing.metadata
    if landing.status_code in {401, 403} or "challenge" in html[:10000].lower():
        from .providers.browser_runtime import (
            fetch_html_with_browser,
            load_runtime_config,
        )

        config = load_runtime_config(
            runtime.env, provider=state.provider, doi=state.doi or ""
        )
        fetched = fetch_html_with_browser(
            [state.source_url],
            publisher=state.provider,
            config=config,
            browser_context_seed=state.browser_context_seed,
            runtime_context=runtime,
        )
        html, source_url = fetched.html, fetched.final_url
        from .extraction.html._metadata import parse_html_metadata

        observed_metadata = parse_html_metadata(html, source_url)
        state.browser_context_seed = dict(fetched.browser_context_seed)
    elif landing.status_code >= 400:
        raise ProviderFailure(
            "asset_index_unavailable",
            f"Source page returned HTTP {landing.status_code}.",
        )
    raise_for_paywall(
        html,
        metadata={**state.metadata, "doi": state.doi},
        source_url=source_url,
        provider=state.provider,
        context=runtime,
    )
    identity = validate_extracted_identity(
        {**state.metadata, "doi": state.doi},
        {
            "response_doi": observed_metadata.get("doi"),
            "response_title": observed_metadata.get("title"),
        },
    )
    if identity.mismatch:
        raise ProviderFailure(
            "identity_mismatch", identity.reason or "Source identity mismatch."
        )
    if html.lstrip().startswith("%PDF"):
        raise ProviderFailure(
            "asset_index_unavailable", "PDF images must be read with the host reader."
        )
    content_type = str(landing.headers.get("content-type") or "text/html")
    route_kind = (
        "xml" if "xml" in content_type and "html" not in content_type else "html"
    )
    content = ProviderContent(
        route_kind=route_kind,
        source_url=source_url,
        content_type=content_type,
        body=html.encode(),
        browser_context_seed=state.browser_context_seed,
    )
    state.route_kind = route_kind
    state.assets = image_index(
        [
            *state.assets,
            *discover_content_images(
                content, provider=state.provider, client=client, context=runtime
            ),
        ]
    )
    state.source_url = source_url
    state.discovery_complete = True


def context_from_query(query: str, runtime: RuntimeContext) -> AssetContext:
    from .service import resolve_paper

    resolved = resolve_paper(query, context=runtime)
    state = AssetContext(
        doi=resolved.doi,
        provider=resolved.provider_hint or "",
        source_url=resolved.landing_url
        or (f"https://doi.org/{resolved.doi}" if resolved.doi else ""),
        metadata={"title": resolved.title},
    )
    _load_source(state, runtime)
    return state


def _download_selected(
    state: AssetContext,
    selected: list[dict[str, Any]],
    output: Path,
    runtime: RuntimeContext,
) -> dict[str, Any]:
    from .auth import require_ams_auth

    require_ams_auth(runtime.env or {}, provider=state.provider)
    client: Any = runtime.get_clients().get(state.provider)
    content = ProviderContent(
        route_kind=state.route_kind,
        source_url=state.source_url,
        content_type="text/html",
        body=b"",
        extracted_assets=selected,
        browser_context_seed=state.browser_context_seed,
    )
    if (
        state.route_kind == "html"
        and client is not None
        and hasattr(client, "_download_browser_backed_related_assets")
    ):
        return client._download_browser_backed_related_assets(
            state.doi or "",
            state.metadata,
            RawFulltextPayload(provider=state.provider, content=content),
            output,
            asset_profile="body",
            context=runtime,
            assets=selected,
        )
    if (
        state.provider in {"springer", "plos", "copernicus", "arxiv"}
        and client is not None
    ):
        return client.download_related_assets(
            state.doi or "",
            state.metadata,
            RawFulltextPayload(provider=state.provider, content=content),
            output,
            asset_profile="body",
            context=runtime,
        )
    from .providers.browser_workflow.fetchers.image import (
        _build_shared_browser_image_fetcher,
    )

    headers = None
    header_filter = None
    sensitive_headers: tuple[str, ...] = ()
    if state.provider == "elsevier" and client is not None:
        from .providers.elsevier import _object_request_headers

        headers = client._base_headers("*/*")
        header_filter = _object_request_headers
        sensitive_headers = ("X-ELS-APIKey",)

    browser_fetcher = _build_shared_browser_image_fetcher(
        browser_context_seed_getter=lambda: state.browser_context_seed,
        seed_urls_getter=lambda: [state.source_url],
        min_width=1,
        min_height=1,
        runtime_context=runtime,
    )
    try:
        assert runtime.transport is not None
        return download_assets(
            FIGURE_KIND,
            runtime.transport,
            article_id=state.doi or state.source_url,
            assets=selected,
            output_dir=output,
            user_agent=getattr(client, "user_agent", "paper-fetch"),
            asset_profile="body",
            options=AssetDownloadOptions(
                browser_context_seed=state.browser_context_seed,
                headers=headers,
                candidate_headers_filter=header_filter,
                sensitive_headers=sensitive_headers,
                image_document_fetcher=browser_fetcher,
                provider_name=state.provider or None,
                runtime_context=runtime,
                fetch_policy="direct_then_browser",
            ),
        )
    finally:
        browser_fetcher.close()


def selected_assets_need_network(state, *, asset_ids=None, urls=None, kind=None):
    selectors = asset_ids if asset_ids is not None else urls
    selected = [
        asset
        for asset in state.assets
        if (kind is not None and asset["kind"] == kind)
        or (asset_ids is not None and asset["asset_id"] in asset_ids)
        or (urls is not None and asset_urls(asset).intersection(urls))
    ]
    indexed = selectors is not None and all(
        any(
            selector == asset["asset_id"]
            if asset_ids is not None
            else selector in asset_urls(asset)
            for asset in state.assets
        )
        for selector in selectors
    )
    return (not state.discovery_complete and not indexed) or any(
        not asset.get("path") or not Path(asset["path"]).expanduser().is_file()
        for asset in selected
    )


def fetch_selected_assets(
    state: AssetContext,
    *,
    asset_ids: list[str] | None = None,
    urls: list[str] | None = None,
    kind: str | None = None,
    output_dir: str | None = None,
    overwrite: bool = False,
    runtime: RuntimeContext | None = None,
) -> dict[str, Any]:
    if (
        sum(value is not None for value in (asset_ids, urls, kind)) != 1
        or (kind is not None and kind not in IMAGE_KINDS)
        or asset_ids == []
        or urls == []
    ):
        raise ValueError(
            "Choose exactly one nonempty selector: asset_ids, urls, or kind (formula, figure, table)."
        )
    owns_runtime = runtime is None
    runtime = runtime or RuntimeContext(artifact_mode="none")
    try:
        with state.lock:
            selectors = asset_ids if asset_ids is not None else urls
            indexed = selectors is not None and all(
                any(
                    (
                        selector == asset["asset_id"]
                        if asset_ids is not None
                        else selector in asset_urls(asset)
                    )
                    for asset in state.assets
                )
                for selector in selectors
            )
            if not state.discovery_complete and not indexed:
                _load_source(state, runtime)
            selected: list[dict[str, Any]] = []
            missing: list[dict[str, Any]] = []
            if kind:
                selected = [asset for asset in state.assets if asset["kind"] == kind]
            else:
                for selector in dict.fromkeys(
                    asset_ids if asset_ids is not None else urls or []
                ):
                    asset = next(
                        (
                            asset
                            for asset in state.assets
                            if (
                                selector == asset["asset_id"]
                                if asset_ids is not None
                                else selector in asset_urls(asset)
                            )
                        ),
                        None,
                    )
                    if asset is None:
                        missing.append(
                            {
                                "selector": selector,
                                "status": "failed",
                                "reason": "asset_not_found",
                            }
                        )
                    elif asset not in selected:
                        selected.append(asset)
            output = (
                Path(output_dir).expanduser().resolve()
                if output_dir
                else state.temporary_dir()
            )
            output.mkdir(parents=True, exist_ok=True)
            results = list(missing)
            for asset in selected:
                local = Path(asset["path"]).expanduser() if asset.get("path") else None
                if local is None or not local.is_file():
                    try:
                        downloaded = _download_selected(
                            state, [asset], state.temporary_dir(), runtime
                        )
                    except (ProviderFailure, RequestFailure, OSError) as error:
                        if (
                            isinstance(error, ProviderFailure)
                            and error.code == AUTH_REQUIRED
                        ):
                            raise
                        results.append(
                            {
                                "asset_id": asset["asset_id"],
                                "kind": asset["kind"],
                                "url": asset.get("url"),
                                "status": "failed",
                                "reason": getattr(
                                    error, "code", "asset_download_failed"
                                ),
                            }
                        )
                        continue
                    successes = downloaded.get("assets") or []
                    if not successes:
                        results.append(
                            {
                                "asset_id": asset["asset_id"],
                                "kind": asset["kind"],
                                "url": asset.get("url"),
                                "status": "failed",
                                "reason": "asset_download_failed",
                                "failures": downloaded.get("asset_failures") or [],
                            }
                        )
                        continue
                    positions = asset.get("body_positions")
                    asset.update(successes[0])
                    if positions is not None:
                        asset["body_positions"] = positions
                    local = Path(asset["path"]).resolve()
                path = local.resolve()
                if output_dir:
                    destination = output / f"{asset['asset_id']}{path.suffix}"
                    if destination != path:
                        if destination.exists() and not overwrite:
                            if destination.read_bytes() != path.read_bytes():
                                results.append(
                                    {
                                        "asset_id": asset["asset_id"],
                                        "status": "failed",
                                        "reason": "output_exists",
                                        "path": str(destination),
                                    }
                                )
                                continue
                        else:
                            shutil.copyfile(path, destination)
                    path = destination
                results.append(
                    {
                        **asset,
                        "path": str(path),
                        "status": "ok",
                        "source_page": state.source_url,
                    }
                )
            successes = sum(result["status"] == "ok" for result in results)
            payload = {
                "status": "ok"
                if successes == len(results)
                else "partial"
                if successes
                else "error",
                "doi": state.doi,
                "provider": state.provider,
                "source_url": state.source_url,
                "discovery_complete": state.discovery_complete,
                "results": results,
                "temporary": output_dir is None,
            }
            state.results.append(payload)
            return payload
    finally:
        if owns_runtime:
            runtime.close()


def context_from_manifest(path: Path) -> AssetContext:
    """Restore durable identity and image descriptors without resolving or fetching a body."""
    path = path.expanduser()
    record = parse_manifest_record(json.loads(path.read_text(encoding="utf-8")))
    artifact = next(
        (item for item in record.output_artifacts if item.kind == "image_index"), None
    )
    if artifact is None:
        raise ValueError("Manifest has no image index.")
    index_path = Path(artifact.path)
    if not index_path.is_absolute():
        index_path = path.parent / index_path
    data = json.loads(index_path.read_text(encoding="utf-8"))
    doi = record.acceptance.identity.doi
    if data.get("doi") != doi:
        raise ValueError("Image index identity does not match manifest.")
    return AssetContext(
        doi=doi,
        provider=data["provider"],
        source_url=data["source_url"],
        assets=image_index(data.get("assets", [])),
        metadata=data.get("metadata", {}),
        route_kind=data.get("route_kind", "html"),
        discovery_complete=True,
        cleanup_temporary=False,
    )
