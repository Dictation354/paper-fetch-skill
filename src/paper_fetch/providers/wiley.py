"""Wiley provider client with browser HTML and official TDM PDF fallbacks."""

from __future__ import annotations

import urllib.parse
import math
from typing import Any
from collections.abc import Mapping

from ..failure import FailureDiagnostics
from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.provider_rules import (
    ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
    ProviderCleanupRules,
    ProviderFormulaRules,
    ProviderFrontMatterRules,
    ProviderHtmlRules,
    DomHooks,
    WILEY_FORMULA_CONTAINER_TOKENS,
    WILEY_FRONT_MATTER_EXACT_TEXTS,
    WILEY_SITE_RULE_OVERRIDES,
)
from ..http import (
    DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    HttpRequestPolicy,
    PDF_ACCEPT_HEADER,
    PDF_MIME_TYPE,
    RequestFailure,
    provider_request_policy,
)
from ..extraction.html.landing import REDIRECT_STATUS_CODES
from ..provider_catalog import (
    ATYPON_DEFAULT_PDF_PATH_TEMPLATES,
    ProviderRouteSpec,
    ProviderSpec,
    provider_api_url_template,
)
from ..pdf_limits import pdf_max_bytes
from ..quality.html_signals import WILEY_SIGNAL_SET
from ..runtime import RuntimeContext
from ..tracing import fulltext_marker, trace_event
from ..utils import normalize_text
from . import _wiley_html, browser_workflow
from .browser_workflow.shared import BrowserWorkflowDeps, default_browser_workflow_deps
from ._pdf_fallback import PdfFallbackFailure, PdfFallbackStrategy, fetch_pdf_over_http
from ._pdf_common import (
    PdfFetchResult,
    pdf_asset_output_dir,
    pdf_asset_profile_from_context,
    pdf_fetch_result_assets,
    pdf_fetch_result_warnings,
    pdf_fetch_result_from_response,
)
from ._waterfall import (
    ProviderWaterfallStep,
    ProviderWaterfallState,
    run_provider_waterfall,
)
from ._registry import ProviderBundle
from ..reason_codes import NO_RESULT, NOT_CONFIGURED, OK, PDF_FALLBACK
from .base import (
    ProviderContent,
    ProviderFailure,
    ProviderStatusResult,
    RawFulltextPayload,
    build_provider_status_check,
    summarize_capability_status,
)

_PROVIDER_SPEC = ProviderSpec(
    name="wiley",
    display_name="Wiley",
    official=True,
    domains=("onlinelibrary.wiley.com", "wiley.com", "www.wiley.com"),
    doi_prefixes=("10.1002/", "10.1111/"),
    publisher_aliases=(
        "wiley",
        "wiley blackwell",
        "john wiley and sons",
        "john wiley sons",
    ),
    asset_default="body",
    probe_capability="routing_signal",
    provider_managed_abstract_only=True,
    status_order=3,
    base_domains=("onlinelibrary.wiley.com",),
    html_path_templates=("/doi/{doi}", "/doi/full/{doi}"),
    pdf_path_templates=(
        *ATYPON_DEFAULT_PDF_PATH_TEMPLATES,
        "/doi/pdfdirect/{doi}",
        "/wol1/doi/{doi}/fullpdf",
    ),
    crossref_pdf_position=1,
    api_url_templates=(
        (
            "tdm_pdf",
            "https://api.wiley.com/onlinelibrary/tdm/v1/articles/{doi}",
        ),
    ),
    sensitive_headers=("wiley-tdm-client-token",),
    env_requirements=(),
    batch_concurrency=1,
    routes=(
        ProviderRouteSpec(name="metadata", kind="metadata"),
        ProviderRouteSpec(
            name="browser_html",
            kind="html",
            browser_optional=True,
            browser_preflight=True,
            auth_supported=True,
            requires_playwright=True,
            concurrency=1,
            timeout_seconds=120,
        ),
        ProviderRouteSpec(
            name="tdm_pdf",
            kind="pdf",
            transport="api",
            requires_pdf_conversion=True,
        ),
        ProviderRouteSpec(
            name="browser_pdf",
            kind="pdf",
            browser_optional=True,
            browser_preflight=True,
            requires_playwright=True,
            requires_pdf_conversion=True,
            concurrency=1,
            timeout_seconds=120,
        ),
        ProviderRouteSpec(
            name="assets",
            kind="assets",
            browser_optional=True,
            requires_playwright=True,
            timeout_seconds=20,
            concurrency=2,
            transient_retries=0,
        ),
    ),
)

WILEY_TDM_CLIENT_TOKEN_ENV_VAR = "WILEY_TDM_CLIENT_TOKEN"
WILEY_TDM_API_TEMPLATE_NAME = "tdm_pdf"

WILEY_BROWSER_PROFILE = browser_workflow.make_atypon_browser_profile(
    "wiley",
    catalog=_PROVIDER_SPEC,
    fallback_author_extractor=_wiley_html.extract_authors,
    policy=browser_workflow.BrowserWorkflowPolicy(),
)


def _fetch_wiley_tdm_pdf_result(
    transport,
    *,
    api_url: str,
    headers: Mapping[str, str],
    artifact_dir=None,
    asset_profile="none",
    asset_output_dir=None,
    expected_identity: Mapping[str, Any] | None = None,
    timeout: int = DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    context: RuntimeContext | None = None,
) -> PdfFetchResult:
    del timeout
    maximum_pdf_bytes = pdf_max_bytes()
    route_policy = provider_request_policy(
        "wiley",
        "tdm_pdf",
        base=HttpRequestPolicy(
            max_response_bytes=maximum_pdf_bytes,
            max_compressed_response_bytes=maximum_pdf_bytes,
        ),
    )
    active_timeout = int(route_policy.timeout_seconds or 1)
    if context is not None:
        context.initialize_deadline(active_timeout)
        active_timeout = max(
            1,
            int(math.ceil(context.remaining_seconds(active_timeout))),
        )
    request_headers = {"Accept": PDF_ACCEPT_HEADER, **dict(headers)}
    try:
        response = transport.request(
            "GET",
            api_url,
            headers=request_headers,
            timeout=active_timeout,
            request_policy=route_policy,
        )
    except RequestFailure as exc:
        raise PdfFallbackFailure(
            "pdf_download_failed",
            f"Failed to download Wiley API PDF fallback candidate: {exc}",
            details={
                "source_url": api_url,
                "status": exc.status_code,
                "error_category": str(exc.error_category or "") or None,
                "retry_after_seconds": exc.retry_after_seconds,
            },
        ) from exc

    response_headers = {
        str(key).lower(): str(value)
        for key, value in (response.get("headers") or {}).items()
    }
    final_url = str(response.get("url") or api_url)
    location = normalize_text(response_headers.get("location"))
    if int(response.get("status_code") or 0) in REDIRECT_STATUS_CODES and location:
        redirected_url = urllib.parse.urljoin(api_url, location)
        return PdfFallbackStrategy(
            transport=transport,
            provider_name="wiley",
            headers=request_headers,
            timeout=int(route_policy.timeout_seconds or 1),
            artifact_dir=artifact_dir,
            asset_profile=asset_profile,
            asset_output_dir=asset_output_dir,
            expected_identity=expected_identity,
            context=context,
            fetcher=fetch_pdf_over_http,
        ).fetch([redirected_url])

    return pdf_fetch_result_from_response(
        response,
        artifact_dir=artifact_dir,
        asset_profile=asset_profile,
        asset_output_dir=asset_output_dir,
        source_url=api_url,
        final_url=final_url,
        not_pdf_message="Wiley API PDF fallback did not return a PDF file.",
        allow_pdf_only=True,
        expected_identity=expected_identity,
    )


class WileyClient(browser_workflow.BrowserWorkflowClient):
    name = WILEY_BROWSER_PROFILE.name
    profile = WILEY_BROWSER_PROFILE

    def __init__(
        self,
        transport,
        env: Mapping[str, str],
        deps: BrowserWorkflowDeps = default_browser_workflow_deps(),
    ) -> None:
        super().__init__(transport, env, deps=deps)
        self.tdm_client_token = str(
            self.env.get(WILEY_TDM_CLIENT_TOKEN_ENV_VAR, "")
        ).strip()

    def _tdm_api_url(self, doi: str) -> str:
        template = provider_api_url_template(self.name, WILEY_TDM_API_TEMPLATE_NAME)
        if template is None:
            raise ProviderFailure(
                NOT_CONFIGURED,
                "Wiley TDM API URL template is not declared in provider catalog.",
            )
        return template.format(doi=urllib.parse.quote(doi, safe=""))

    def _tdm_api_headers(self) -> dict[str, str]:
        return {
            "Wiley-TDM-Client-Token": self.tdm_client_token,
            "User-Agent": self.user_agent,
        }

    def probe_status(self) -> ProviderStatusResult:
        browser_status = self.deps.probe_runtime_status(self.env, provider=self.name)
        token_configured = bool(self.tdm_client_token)
        browser_ready = bool(browser_status.checks) and all(
            check.status == OK for check in browser_status.checks
        )
        return summarize_capability_status(
            self.name,
            official_provider=self.official_provider,
            checks=[
                *browser_status.checks,
                build_provider_status_check(
                    "tdm_api_token",
                    OK if token_configured or browser_ready else NOT_CONFIGURED,
                    (
                        "Wiley TDM API client token is configured."
                        if token_configured
                        else (
                            "Wiley TDM API client token is optional when the browser workflow runtime is ready."
                            if browser_ready
                            else (
                                f"{WILEY_TDM_CLIENT_TOKEN_ENV_VAR} enables the official Wiley PDF lane when browser PDF fallback "
                                "is unavailable."
                            )
                        )
                    ),
                    missing_env=[]
                    if token_configured or browser_ready
                    else [WILEY_TDM_CLIENT_TOKEN_ENV_VAR],
                    details={"env_var": WILEY_TDM_CLIENT_TOKEN_ENV_VAR},
                ),
            ],
        )

    def fetch_raw_fulltext(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        context = self._runtime_context(context)
        bootstrap = self.deps.bootstrap_browser_workflow(
            self,
            doi,
            metadata,
            allow_runtime_failure=True,
            context=context,
            deps=self.deps,
        )
        if bootstrap.html_payload is not None:
            return bootstrap.html_payload

        initial_warnings = [*bootstrap.warnings]
        if self.tdm_client_token:
            initial_warnings.append(
                f"{self.name} HTML route was not usable "
                f"({bootstrap.html_failure_reason or 'html_failed'}); attempting Wiley TDM API PDF fallback first."
            )
        elif bootstrap.runtime is not None:
            initial_warnings.append(
                f"{self.name} HTML route was not usable "
                f"({bootstrap.html_failure_reason or 'html_failed'}); attempting Wiley publisher PDF/ePDF fallback."
            )
        else:
            initial_warnings.append(
                f"{self.name} HTML route was not usable "
                f"({bootstrap.html_failure_reason or 'html_failed'}); attempting Wiley TDM API PDF fallback."
            )
        if bootstrap.runtime is None and bootstrap.runtime_failure is not None:
            initial_warnings.append(
                f"Wiley browser PDF/ePDF fallback was not attempted because {bootstrap.runtime_failure.message}"
            )

        def run_tdm_api(_state: ProviderWaterfallState) -> RawFulltextPayload:
            if not self.tdm_client_token:
                raise ProviderFailure(
                    NOT_CONFIGURED,
                    f"Wiley TDM API PDF fallback is not configured because {WILEY_TDM_CLIENT_TOKEN_ENV_VAR} is missing.",
                    missing_env=[WILEY_TDM_CLIENT_TOKEN_ENV_VAR],
                )

            api_url = self._tdm_api_url(bootstrap.normalized_doi)
            try:
                effective_asset_profile = pdf_asset_profile_from_context(context)
                pdf_result = _fetch_wiley_tdm_pdf_result(
                    self.transport,
                    api_url=api_url,
                    headers=self._tdm_api_headers(),
                    artifact_dir=(bootstrap.runtime.artifact_dir / "pdf_api_fallback")
                    if bootstrap.runtime is not None
                    else None,
                    asset_profile=effective_asset_profile,
                    asset_output_dir=pdf_asset_output_dir(
                        context,
                        asset_profile=effective_asset_profile,
                        doi=bootstrap.normalized_doi,
                    ),
                    expected_identity={
                        "doi": bootstrap.normalized_doi,
                        "title": metadata.get("title"),
                    },
                    context=context,
                )
            except PdfFallbackFailure as exc:
                raise ProviderFailure(
                    NO_RESULT,
                    exc.message,
                    diagnostics=FailureDiagnostics(
                        route="pdf_api",
                        stage="download",
                        http_status=exc.details.get("status"),
                        error_category=exc.kind,
                        retryable=True,
                        details=exc.details,
                    ),
                ) from exc

            return RawFulltextPayload(
                provider=self.name,
                content=ProviderContent(
                    route_kind=PDF_FALLBACK,
                    source_url=pdf_result.final_url,
                    content_type=PDF_MIME_TYPE,
                    body=pdf_result.pdf_bytes,
                    markdown_text=pdf_result.markdown_text,
                    diagnostics=(
                        {"html_failure": dict(bootstrap.html_failure_diagnostics)}
                        if bootstrap.html_failure_diagnostics
                        else {}
                    ),
                    html_failure_reason=bootstrap.html_failure_reason,
                    html_failure_message=bootstrap.html_failure_message,
                    suggested_filename=pdf_result.suggested_filename,
                    extracted_assets=pdf_fetch_result_assets(pdf_result),
                    needs_local_copy=True,
                ),
                warnings=pdf_fetch_result_warnings(pdf_result),
                trace=(
                    [
                        trace_event(
                            "fulltext",
                            f"{self.name}_html",
                            "fail",
                            code=bootstrap.html_failure_reason,
                            message=bootstrap.html_failure_message,
                        )
                    ]
                    if bootstrap.html_failure_reason
                    else []
                ),
            )

        def run_browser_pdf(_state: ProviderWaterfallState) -> RawFulltextPayload:
            if bootstrap.runtime is None:
                raise ProviderFailure(
                    NOT_CONFIGURED,
                    bootstrap.runtime_failure.message
                    if bootstrap.runtime_failure is not None
                    else "Wiley browser runtime is not configured.",
                    missing_env=bootstrap.runtime_failure.missing_env
                    if bootstrap.runtime_failure is not None
                    else [],
                )
            try:
                return self.deps.fetch_seeded_browser_pdf_payload(
                    provider=self.name,
                    doi=bootstrap.normalized_doi,
                    runtime=bootstrap.runtime,
                    pdf_candidates=bootstrap.pdf_candidates,
                    html_candidates=bootstrap.html_candidates,
                    landing_page_url=bootstrap.landing_page_url,
                    user_agent=self.user_agent,
                    browser_context_seed=bootstrap.browser_context_seed,
                    html_failure_reason=bootstrap.html_failure_reason,
                    html_failure_message=bootstrap.html_failure_message,
                    html_failure_diagnostics=bootstrap.html_failure_diagnostics,
                    warnings=[],
                    success_source_trail=[],
                    success_warning=(
                        "Full text was extracted from the Wiley publisher PDF/ePDF fallback after the HTML path was not usable."
                    ),
                    artifact_subdir="browser_pdf_fallback",
                    context=context,
                    deps=self.deps,
                )
            except PdfFallbackFailure as exc:
                raise ProviderFailure(NO_RESULT, exc.message) from exc

        def browser_failure_warning(
            failure: ProviderFailure, _state: ProviderWaterfallState
        ) -> str:
            return (
                f"Wiley publisher PDF/ePDF fallback was not usable ({failure.message})."
            )

        def tdm_failure_warning(
            failure: ProviderFailure, _state: ProviderWaterfallState
        ) -> str:
            if failure.code == NOT_CONFIGURED:
                return failure.message
            suffix = (
                "; attempting Wiley browser PDF/ePDF fallback."
                if bootstrap.runtime is not None
                else "."
            )
            return (
                f"Wiley TDM API PDF fallback was not usable ({failure.message}){suffix}"
            )

        def final_failure(state: ProviderWaterfallState) -> ProviderFailure:
            api_failure = next(
                (failure for label, failure in state.failures if label == "pdf_api"),
                None,
            )
            browser_failure = next(
                (
                    failure
                    for label, failure in state.failures
                    if label == "browser_pdf"
                ),
                None,
            )
            failure_parts = [
                f"HTML failure: {bootstrap.html_failure_message or 'wiley HTML route failed.'}"
            ]
            if browser_failure is not None:
                failure_parts.append(
                    f"Wiley browser PDF failure: {browser_failure.message}"
                )
            elif bootstrap.runtime is None and bootstrap.runtime_failure is not None:
                failure_parts.append(
                    f"Wiley browser PDF failure: {bootstrap.runtime_failure.message}"
                )
            if api_failure is not None:
                failure_parts.append(f"Wiley API PDF failure: {api_failure.message}")

            missing_env: list[str] = []
            if bootstrap.runtime is None and bootstrap.runtime_failure is not None:
                missing_env.extend(bootstrap.runtime_failure.missing_env)
            if (
                bootstrap.runtime is None
                and not self.tdm_client_token
                and WILEY_TDM_CLIENT_TOKEN_ENV_VAR not in missing_env
            ):
                missing_env.append(WILEY_TDM_CLIENT_TOKEN_ENV_VAR)

            return ProviderFailure(
                NOT_CONFIGURED
                if bootstrap.runtime is None and not self.tdm_client_token
                else self._html_failure_code(bootstrap.html_failure_reason),
                f"{self.name} full text could not be retrieved. "
                + " ".join(failure_parts),
                missing_env=missing_env,
                warnings=state.warnings,
                source_trail=state.source_trail,
                trace=(
                    [
                        trace_event(
                            "fulltext",
                            f"{self.name}_html",
                            "fail",
                            code=bootstrap.html_failure_reason,
                            message=bootstrap.html_failure_message,
                        )
                    ]
                    if bootstrap.html_failure_reason
                    else []
                ),
            )

        browser_step = ProviderWaterfallStep(
            label="browser_pdf",
            route_name="browser_pdf",
            run=run_browser_pdf,
            failure_marker=fulltext_marker(self.name, "fail", route="pdf_browser"),
            success_markers=(
                fulltext_marker(self.name, "ok", route="pdf_browser"),
                fulltext_marker(self.name, "ok", route=PDF_FALLBACK),
            ),
            failure_warning=browser_failure_warning,
        )
        api_step = ProviderWaterfallStep(
            label="pdf_api",
            route_name="tdm_pdf",
            run=run_tdm_api,
            failure_marker=fulltext_marker(self.name, "fail", route="pdf_api"),
            success_markers=(
                fulltext_marker(self.name, "ok", route="pdf_api"),
                fulltext_marker(self.name, "ok", route=PDF_FALLBACK),
            ),
            continue_codes=(NO_RESULT, NOT_CONFIGURED),
            failure_warning=tdm_failure_warning,
            success_warning="Full text was extracted from the Wiley TDM API PDF fallback after the HTML path was not usable.",
        )
        steps = (
            [api_step, browser_step]
            if self.tdm_client_token and bootstrap.runtime is not None
            else (
                [api_step]
                if self.tdm_client_token
                else (
                    [browser_step, api_step]
                    if bootstrap.runtime is not None
                    else [api_step]
                )
            )
        )

        return run_provider_waterfall(
            steps,
            doi=doi,
            metadata=metadata,
            context=context,
            client=self,
            initial_warnings=initial_warnings,
            initial_source_trail=[fulltext_marker(self.name, "fail", route="html")],
            final_failure_factory=final_failure,
        )


PROVIDER_BUNDLE = ProviderBundle(
    client_factory=WileyClient,
    catalog=_PROVIDER_SPEC,
    html_rules=ProviderHtmlRules(
        name="wiley",
        cleanup=ProviderCleanupRules(
            extraction_drop_keywords=("citation-tools", "publicationhistory"),
        ),
        formula=ProviderFormulaRules(
            container_tokens=WILEY_FORMULA_CONTAINER_TOKENS,
        ),
        availability=AvailabilityPolicy(
            name="wiley",
            site_rule_overrides=WILEY_SITE_RULE_OVERRIDES,
            datalayer_signal_set=WILEY_SIGNAL_SET,
        ),
        front_matter=ProviderFrontMatterRules(
            exact_texts=WILEY_FRONT_MATTER_EXACT_TEXTS,
            contains_tokens=ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
        ),
        dom_hooks=DomHooks(
            before_block_normalization=_wiley_html.wiley_before_block_normalization,
            after_block_normalization=_wiley_html.wiley_after_block_normalization,
            body_container=_wiley_html.wiley_body_container,
            asset_body_container=_wiley_html.wiley_asset_body_container,
        ),
    ),
    sources=("wiley_browser",),
)
