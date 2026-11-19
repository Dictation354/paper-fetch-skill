"""Provider interfaces, diagnostics, and shared error types."""

from __future__ import annotations

import importlib.util
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ..http import RequestFailure
from ..provider_catalog import PROVIDER_CATALOG, sources_by_provider
from ..publisher_identity import normalize_doi, validate_extracted_identity
from ..quality.access_boundary import CONFIRMED_PAYWALL
from ..reason_codes import (
    ERROR,
    IDENTITY_MISMATCH,
    NOT_CONFIGURED,
    NOT_SUPPORTED,
    OK,
    PARTIAL,
    READY,
)
from ..tracing import TraceEvent, trace_event
from ..utils import empty_asset_results, normalize_text, provider_display_name
from ._errors import (
    PreparedFetchResultPayload,
    ProviderArtifacts,
    ProviderContent,
    ProviderFailure,
    ProviderFetchResult,
    ProviderStatusCheck,
    ProviderStatusResult,
    RawFulltextPayload,
    build_provider_status_check,
    combine_provider_failures,
    map_request_failure,
    provider_status_check_from_failure,
    summarize_capability_status,
)

if TYPE_CHECKING:
    from ..artifacts import ArtifactStore
    from ..metadata.types import ProviderMetadata
    from ..models import ArticleModel, AssetProfile
    from ..runtime import RuntimeContext
    from ._result import ResultAssemblyPolicy
    from ._waterfall import WaterfallStep


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def restricted_provider_result(
    provider: str, metadata: Mapping[str, Any], failure: Any
) -> ProviderFetchResult:
    from ..models import metadata_only_article
    from ..models.quality import apply_quality_assessment
    from ..models.schema import SourceKind

    details = dict(failure.diagnostics.details)
    received_html = str(details.pop("received_html", "") or "")
    merged = dict(metadata)
    merged.update(
        {
            key: value
            for key, value in details.get("received_metadata", {}).items()
            if value
        }
    )
    sources = sorted(sources_by_provider().get(provider, {"crossref_meta"}))
    source = next(
        (candidate for candidate in sources if not candidate.endswith("_pdf")),
        sources[0],
    )
    trace = [
        *failure.trace,
        trace_event(
            "fulltext", provider, "fail", code="no_access", message=failure.message
        ),
    ]
    article = metadata_only_article(
        source=cast(SourceKind, source),
        metadata=merged,
        doi=merged.get("doi"),
        warnings=[*failure.warnings, failure.message],
        trace=trace,
    )
    apply_quality_assessment(article, availability_diagnostics=details)
    article.trace.append(
        trace_event("fulltext", provider, "fail", code=CONFIRMED_PAYWALL)
    )
    evidence = details[CONFIRMED_PAYWALL]
    content = ProviderContent(
        route_kind="html" if received_html else "metadata",
        source_url=evidence.get("source_url") or "",
        content_type="text/html" if received_html else "application/json",
        body=received_html.encode("utf-8"),
        merged_metadata=merged,
        diagnostics=details,
    )
    return ProviderFetchResult(
        provider=provider,
        article=article,
        content=content,
        warnings=list(article.quality.warnings),
        trace=trace,
        artifacts=ProviderArtifacts(allow_related_assets=False),
    )


class ProviderClient:
    """Provider interface used by the fetch workflow."""

    name = "provider"
    official_provider = True
    waterfall_steps: tuple[WaterfallStep, ...] = ()

    def fetch_metadata(self, query: Mapping[str, str | None]) -> ProviderMetadata:
        raise ProviderFailure(
            NOT_SUPPORTED, f"{self.name} metadata retrieval is not available."
        )

    def fetch_supplementary(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        output_dir: Path | None,
        *,
        context: RuntimeContext,
    ):
        from .supplementary import fetch_provider_supplementary

        return fetch_provider_supplementary(
            self, doi, metadata, output_dir, context=context
        )

    def fetch_result(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        output_dir: Path | None,
        *,
        asset_profile: AssetProfile = "none",
        artifact_store: ArtifactStore | None = None,
        context: RuntimeContext | None = None,
    ) -> ProviderFetchResult:
        from ._result import assemble_provider_result

        return assemble_provider_result(
            self,
            doi,
            metadata,
            output_dir,
            asset_profile=asset_profile,
            artifact_store=artifact_store,
            context=context,
        )

    def result_assembly_policy(self) -> ResultAssemblyPolicy:
        from ._result import ResultAssemblyPolicy

        return ResultAssemblyPolicy()

    def result_provider_name(self, raw_payload: RawFulltextPayload) -> str:
        return raw_payload.provider or self.name

    def _runtime_context(
        self, context: RuntimeContext | None, *, output_dir: Path | None = None
    ) -> RuntimeContext:
        if context is not None:
            return context
        from ..runtime import RuntimeContext

        return RuntimeContext(
            env=getattr(self, "env", {}) or {},
            transport=getattr(self, "transport", None),
            download_dir=output_dir,
        )

    def html_to_markdown(
        self,
        html_text: str,
        source_url: str,
        *,
        metadata: Mapping[str, Any],
        context: RuntimeContext,
    ) -> tuple[str, Mapping[str, Any]]:
        del metadata, context
        from ..extraction.html import render_html_markdown

        return render_html_markdown(html_text, source_url), {
            "html_to_markdown": {
                "provider": self.name,
                "parser": "generic",
            }
        }

    def ensure_html_markdown(
        self,
        raw_payload: RawFulltextPayload,
        metadata: Mapping[str, Any],
        *,
        context: RuntimeContext,
    ) -> RawFulltextPayload:
        content = raw_payload.content
        payload_content_type = content.content_type
        content_type = normalize_text(payload_content_type).lower()
        if "html" not in content_type:
            return raw_payload
        if normalize_text(content.markdown_text):
            return raw_payload

        from ..extraction.html import decode_html

        html_text = decode_html(
            bytes(content.body or b""),
            content_type=payload_content_type,
        ).strip()
        if not html_text:
            return raw_payload

        try:
            markdown_text, extraction = self.html_to_markdown(
                html_text,
                content.source_url,
                metadata=metadata,
                context=context,
            )
        except Exception as exc:
            raw_payload.warnings.append(
                f"{self.name} HTML-to-Markdown conversion failed after full-text retrieval: {exc}"
            )
            return raw_payload

        markdown_text = str(markdown_text or "").strip()
        if not markdown_text:
            raw_payload.warnings.append(
                f"{self.name} HTML-to-Markdown conversion did not produce usable Markdown."
            )
            return raw_payload

        diagnostics = dict(content.diagnostics)
        if extraction:
            extraction_payload = dict(extraction)
            diagnostics.setdefault("extraction", extraction_payload)
            availability = extraction_payload.get("availability_diagnostics")
            if isinstance(availability, Mapping):
                diagnostics.setdefault("availability_diagnostics", dict(availability))
        diagnostics.setdefault(
            "html_to_markdown",
            {
                "provider": self.name,
                "automatic": True,
            },
        )
        raw_payload.content = replace(
            content,
            markdown_text=markdown_text,
            diagnostics=diagnostics,
        )
        return raw_payload

    def prepare_fetch_result_payload(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        asset_profile: AssetProfile = "none",
        context: RuntimeContext | None = None,
    ) -> PreparedFetchResultPayload:
        context = self._runtime_context(context)
        return PreparedFetchResultPayload(
            raw_payload=self.fetch_raw_fulltext(doi, metadata, context=context)
        )

    def validate_raw_payload_identity(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
    ) -> RawFulltextPayload:
        content = raw_payload.content
        merged = dict(content.merged_metadata or {})
        evidence: dict[str, Any] = (
            dict(merged.get("identity_evidence") or {})
            if isinstance(merged.get("identity_evidence"), Mapping)
            else {}
        )
        content_diagnostics = content.diagnostics
        diagnostic_evidence = content_diagnostics.get("identity_evidence")
        if isinstance(diagnostic_evidence, Mapping):
            evidence.update(diagnostic_evidence)
        for key in ("response_doi", "response_arxiv_id", "response_title"):
            if key in content_diagnostics and key not in merged:
                merged[key] = content_diagnostics[key]
        expected = dict(metadata)
        expected["doi"] = normalize_doi(doi) or normalize_doi(
            str(metadata.get("doi") or "")
        )
        result = validate_extracted_identity(expected, merged, evidence)
        diagnostics = dict(content.diagnostics)
        diagnostics["identity"] = result.to_dict()
        raw_payload.content = replace(content, diagnostics=diagnostics)
        if result.mismatch:
            raise ProviderFailure(
                IDENTITY_MISMATCH,
                result.reason or "Provider response identity mismatch.",
                trace=[
                    TraceEvent(
                        stage="identity",
                        component=self.name,
                        outcome="fail",
                        code=IDENTITY_MISMATCH,
                        message=result.reason,
                    )
                ],
            )
        return raw_payload

    def maybe_recover_fetch_result_payload(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        prepared: PreparedFetchResultPayload,
        *,
        asset_profile: AssetProfile = "none",
        context: RuntimeContext | None = None,
    ) -> PreparedFetchResultPayload:
        del context
        return prepared

    def should_download_related_assets_for_result(
        self,
        raw_payload: RawFulltextPayload,
        *,
        provisional_article: ArticleModel | None = None,
    ) -> bool:
        return True

    def finalize_fetch_result_article(
        self,
        article: ArticleModel,
        *,
        raw_payload: RawFulltextPayload,
        provisional_article: ArticleModel | None = None,
        finalize_warnings: list[str] | None = None,
    ) -> ArticleModel:
        return article

    def asset_download_failure_warning(
        self, exc: ProviderFailure | RequestFailure | OSError
    ) -> str:
        message = exc.message if isinstance(exc, ProviderFailure) else str(exc)
        return f"{provider_display_name(self.name)} related assets could not be downloaded: {message}"

    def describe_artifacts(
        self,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ) -> ProviderArtifacts:
        return ProviderArtifacts(
            assets=[dict(item) for item in (downloaded_assets or [])],
            asset_failures=[dict(item) for item in (asset_failures or [])],
        )

    def fetch_raw_fulltext(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        if self.waterfall_steps:
            from ._waterfall import run_provider_waterfall

            return run_provider_waterfall(
                self.waterfall_steps,
                doi,
                metadata,
                context=context,
                client=self,
                invoke_with_request=True,
            )
        raise NotImplementedError(
            f"{self.__class__.__name__} must override fetch_raw_fulltext() "
            "or declare waterfall_steps."
        )

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
        raise ProviderFailure(
            NOT_SUPPORTED, f"{self.name} article conversion is not available."
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
        del context
        return empty_asset_results()

    def probe_status(self) -> ProviderStatusResult:
        catalog = PROVIDER_CATALOG.get(str(self.name or "").strip().lower())
        if catalog is None:
            return ProviderStatusResult(
                provider=self.name,
                status=ERROR,
                available=False,
                official_provider=self.official_provider,
                notes=["Provider catalog entry was not found for this client."],
                checks=[
                    build_provider_status_check(
                        "provider_catalog",
                        ERROR,
                        f"Unknown provider bundle: {self.name!r}",
                    )
                ],
            )

        env = getattr(self, "env", {}) or {}
        checks: list[ProviderStatusCheck] = []
        env_requirements = tuple(catalog.env_requirements or ())
        missing_env = [
            env_name
            for env_name in env_requirements
            if not str(env.get(env_name, "")).strip()
        ]
        if env_requirements:
            checks.append(
                build_provider_status_check(
                    "environment",
                    NOT_CONFIGURED if missing_env else OK,
                    (
                        f"{catalog.display_name} required environment variables are configured."
                        if not missing_env
                        else f"{catalog.display_name} is missing required environment variables."
                    ),
                    missing_env=missing_env,
                    details={"env_requirements": list(env_requirements)},
                )
            )

        has_browser_route = any(
            route.browser_required or route.browser_optional for route in catalog.routes
        )
        browser_is_required = any(route.browser_required for route in catalog.routes)
        if has_browser_route:
            playwright_available = _module_available("playwright.sync_api")
            checks.append(
                build_provider_status_check(
                    "playwright",
                    (
                        OK
                        if playwright_available
                        else (NOT_CONFIGURED if browser_is_required else PARTIAL)
                    ),
                    (
                        "Playwright Python package is importable; browser installation is not probed."
                        if playwright_available
                        else "Playwright Python package is not installed."
                    ),
                    details={"probe": "importlib.find_spec"},
                )
            )

            from .browser_runtime.api import probe_runtime_status

            runtime_status = probe_runtime_status(env, provider=self.name)
            runtime_probe = "paper_fetch.providers.browser_runtime.probe_runtime_status"
            if runtime_status.status == ERROR:
                browser_runtime_status = ERROR
            elif runtime_status.status == READY:
                browser_runtime_status = OK
            else:
                browser_runtime_status = (
                    NOT_CONFIGURED if browser_is_required else PARTIAL
                )
            checks.append(
                build_provider_status_check(
                    "browser_runtime",
                    browser_runtime_status,
                    (
                        "Browser runtime is configured; no browser is launched."
                        if browser_runtime_status == OK
                        else "Browser runtime is not configured."
                    ),
                    missing_env=runtime_status.missing_env,
                    details={
                        "probe": runtime_probe,
                        "checks": [check.to_dict() for check in runtime_status.checks],
                    },
                ),
            )

        if any(route.requires_pdf_conversion for route in catalog.routes):
            pdf_packages = {
                "fitz": _module_available("fitz"),
                "pymupdf4llm": _module_available("pymupdf4llm"),
            }
            pdf_ready = all(pdf_packages.values())
            checks.append(
                build_provider_status_check(
                    "pdf_conversion",
                    OK if pdf_ready else PARTIAL,
                    (
                        "PDF validation and Markdown conversion packages are importable."
                        if pdf_ready
                        else "PDF fallback is only partially ready because PDF conversion packages are missing."
                    ),
                    details={
                        "packages": pdf_packages,
                        "missing_packages": [
                            name
                            for name, available in pdf_packages.items()
                            if not available
                        ],
                    },
                )
            )

        if not checks:
            checks.append(
                build_provider_status_check(
                    "local_requirements",
                    OK,
                    f"{catalog.display_name} has no local provider requirements.",
                )
            )

        result_missing_env: list[str] = []
        for check in checks:
            for env_name in check.missing_env:
                if env_name not in result_missing_env:
                    result_missing_env.append(env_name)
        if any(check.status == ERROR for check in checks):
            status = ERROR
        elif any(check.status == NOT_CONFIGURED for check in checks):
            status = NOT_CONFIGURED
        elif any(check.status == PARTIAL for check in checks):
            status = PARTIAL
        else:
            status = READY
        return ProviderStatusResult(
            provider=self.name,
            status=status,
            available=status in {READY, PARTIAL},
            official_provider=catalog.official,
            missing_env=result_missing_env,
            checks=checks,
        )


__all__ = [
    "PreparedFetchResultPayload",
    "ProviderArtifacts",
    "ProviderClient",
    "ProviderContent",
    "ProviderFailure",
    "ProviderFetchResult",
    "ProviderStatusCheck",
    "ProviderStatusResult",
    "RawFulltextPayload",
    "build_provider_status_check",
    "combine_provider_failures",
    "map_request_failure",
    "provider_status_check_from_failure",
    "restricted_provider_result",
    "summarize_capability_status",
]
