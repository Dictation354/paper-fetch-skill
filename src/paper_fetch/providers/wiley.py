"""Wiley provider client with browser HTML and official TDM PDF fallbacks."""

from __future__ import annotations

import urllib.parse
from typing import Any, Mapping

from ..http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, RequestFailure
from ..utils import normalize_text
from . import _science_pnas
from ._pdf_fallback import PdfFallbackFailure, fetch_pdf_over_http
from ._pdf_common import PdfFetchResult, filename_from_headers, looks_like_pdf_payload, pdf_fetch_result_from_bytes
from .base import (
    ProviderFailure,
    ProviderStatusResult,
    RawFulltextPayload,
    build_provider_status_check,
    summarize_capability_status,
)

WILEY_TDM_CLIENT_TOKEN_ENV_VAR = "WILEY_TDM_CLIENT_TOKEN"
WILEY_TDM_API_URL_TEMPLATE = "https://api.wiley.com/onlinelibrary/tdm/v1/articles/{doi}"


def _fetch_wiley_tdm_pdf_result(
    transport,
    *,
    api_url: str,
    headers: Mapping[str, str],
    artifact_dir=None,
    timeout: int = DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
) -> PdfFetchResult:
    request_headers = {"Accept": "application/pdf,*/*;q=0.8", **dict(headers)}
    try:
        response = transport.request(
            "GET",
            api_url,
            headers=request_headers,
            timeout=timeout,
            retry_on_transient=True,
        )
    except RequestFailure as exc:
        raise PdfFallbackFailure(
            "pdf_download_failed",
            f"Failed to download Wiley API PDF fallback candidate: {exc}",
            details={"source_url": api_url},
        ) from exc

    response_headers = {str(key).lower(): str(value) for key, value in (response.get("headers") or {}).items()}
    final_url = str(response.get("url") or api_url)
    location = normalize_text(response_headers.get("location"))
    if int(response.get("status_code") or 0) in {301, 302, 303, 307, 308} and location:
        redirected_url = urllib.parse.urljoin(api_url, location)
        return fetch_pdf_over_http(
            transport,
            [redirected_url],
            headers=request_headers,
            timeout=timeout,
            artifact_dir=artifact_dir,
        )

    pdf_bytes = bytes(response.get("body") or b"")
    if not looks_like_pdf_payload(str(response_headers.get("content-type") or ""), pdf_bytes, final_url):
        raise PdfFallbackFailure(
            "downloaded_file_not_pdf",
            "Wiley API PDF fallback did not return a PDF file.",
            details={"source_url": api_url, "final_url": final_url},
        )

    return pdf_fetch_result_from_bytes(
        artifact_dir=artifact_dir,
        source_url=api_url,
        final_url=final_url,
        pdf_bytes=pdf_bytes,
        suggested_filename=filename_from_headers(response_headers),
    )


class WileyClient(_science_pnas.BrowserWorkflowClient):
    name = "wiley"
    article_source_name = "wiley_browser"

    def __init__(self, transport, env: Mapping[str, str]) -> None:
        super().__init__(transport, env)
        self.tdm_client_token = str(self.env.get(WILEY_TDM_CLIENT_TOKEN_ENV_VAR, "")).strip()

    def _tdm_api_url(self, doi: str) -> str:
        return WILEY_TDM_API_URL_TEMPLATE.format(doi=urllib.parse.quote(doi, safe=""))

    def _tdm_api_headers(self) -> dict[str, str]:
        return {
            "Wiley-TDM-Client-Token": self.tdm_client_token,
            "User-Agent": self.user_agent,
        }

    def probe_status(self) -> ProviderStatusResult:
        browser_status = _science_pnas.probe_runtime_status(self.env, provider=self.name)
        token_configured = bool(self.tdm_client_token)
        browser_ready = bool(browser_status.checks) and all(check.status == "ok" for check in browser_status.checks)
        return summarize_capability_status(
            self.name,
            official_provider=self.official_provider,
            checks=[
                *browser_status.checks,
                build_provider_status_check(
                    "tdm_api_token",
                    "ok" if token_configured or browser_ready else "not_configured",
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
                    missing_env=[] if token_configured or browser_ready else [WILEY_TDM_CLIENT_TOKEN_ENV_VAR],
                    details={"env_var": WILEY_TDM_CLIENT_TOKEN_ENV_VAR},
                ),
            ],
        )

    def fetch_raw_fulltext(self, doi: str, metadata: Mapping[str, Any]) -> RawFulltextPayload:
        bootstrap = _science_pnas.bootstrap_browser_workflow(self, doi, metadata, allow_runtime_failure=True)
        if bootstrap.html_payload is not None:
            return bootstrap.html_payload

        warnings = bootstrap.warnings
        warnings.append(
            (
                f"{self.name} HTML route was not usable "
                f"({bootstrap.html_failure_reason or 'html_failed'}); attempting Wiley TDM API PDF fallback."
            )
        )

        api_failure_message: str | None = None
        if self.tdm_client_token:
            api_url = self._tdm_api_url(bootstrap.normalized_doi)
            try:
                pdf_result = _fetch_wiley_tdm_pdf_result(
                    self.transport,
                    api_url=api_url,
                    headers=self._tdm_api_headers(),
                    artifact_dir=(bootstrap.runtime.artifact_dir / "pdf_api_fallback") if bootstrap.runtime is not None else None,
                )
                warnings.append("Full text was extracted from the Wiley TDM API PDF fallback after the HTML path was not usable.")
                return RawFulltextPayload(
                    provider=self.name,
                    source_url=pdf_result.final_url,
                    content_type="application/pdf",
                    body=pdf_result.pdf_bytes,
                    metadata={
                        "route": "pdf_fallback",
                        "markdown_text": pdf_result.markdown_text,
                        "warnings": warnings,
                        "html_failure_reason": bootstrap.html_failure_reason,
                        "html_failure_message": bootstrap.html_failure_message,
                        "source_trail": [
                            f"fulltext:{self.name}_html_fail",
                            f"fulltext:{self.name}_pdf_api_ok",
                            f"fulltext:{self.name}_pdf_fallback_ok",
                        ],
                        "suggested_filename": pdf_result.suggested_filename,
                    },
                    needs_local_copy=True,
                )
            except PdfFallbackFailure as exc:
                api_failure_message = exc.message
                warnings.append(
                    f"Wiley TDM API PDF fallback was not usable ({exc.message}); attempting publisher PDF/ePDF fallback."
                )
        else:
            api_failure_message = (
                f"Wiley TDM API PDF fallback is not configured because {WILEY_TDM_CLIENT_TOKEN_ENV_VAR} is missing."
            )
            warnings.append(f"{api_failure_message} Attempting publisher PDF/ePDF fallback.")

        browser_pdf_failure_message: str | None = None
        if bootstrap.runtime is not None:
            try:
                return _science_pnas.fetch_seeded_browser_pdf_payload(
                    provider=self.name,
                    runtime=bootstrap.runtime,
                    pdf_candidates=bootstrap.pdf_candidates,
                    html_candidates=bootstrap.html_candidates,
                    landing_page_url=bootstrap.landing_page_url,
                    user_agent=self.user_agent,
                    browser_context_seed=bootstrap.browser_context_seed,
                    html_failure_reason=bootstrap.html_failure_reason,
                    html_failure_message=bootstrap.html_failure_message,
                    warnings=warnings,
                    success_source_trail=[
                        f"fulltext:{self.name}_html_fail",
                        f"fulltext:{self.name}_pdf_browser_ok",
                        f"fulltext:{self.name}_pdf_fallback_ok",
                    ],
                    success_warning=(
                        "Full text was extracted from the Wiley publisher PDF/ePDF fallback after the HTML path was not usable."
                    ),
                    artifact_subdir="browser_pdf_fallback",
                )
            except PdfFallbackFailure as exc:
                browser_pdf_failure_message = exc.message
                warnings.append(f"Wiley publisher PDF/ePDF fallback was not usable ({exc.message}).")
        elif bootstrap.runtime_failure is not None:
            browser_pdf_failure_message = bootstrap.runtime_failure.message
            warnings.append(
                f"Wiley browser PDF/ePDF fallback was not attempted because {bootstrap.runtime_failure.message}"
            )

        failure_parts = [f"HTML failure: {bootstrap.html_failure_message or 'wiley HTML route failed.'}"]
        if api_failure_message:
            failure_parts.append(f"Wiley API PDF failure: {api_failure_message}")
        if browser_pdf_failure_message:
            failure_parts.append(f"Wiley browser PDF failure: {browser_pdf_failure_message}")
        missing_env: list[str] = []
        if bootstrap.runtime is None and bootstrap.runtime_failure is not None:
            missing_env.extend(bootstrap.runtime_failure.missing_env)
        if bootstrap.runtime is None and not self.tdm_client_token and WILEY_TDM_CLIENT_TOKEN_ENV_VAR not in missing_env:
            missing_env.append(WILEY_TDM_CLIENT_TOKEN_ENV_VAR)

        raise ProviderFailure(
            "not_configured" if bootstrap.runtime is None and not self.tdm_client_token else "no_result",
            f"{self.name} full text could not be retrieved. " + " ".join(failure_parts),
            missing_env=missing_env,
            warnings=warnings,
            source_trail=[
                f"fulltext:{self.name}_html_fail",
                f"fulltext:{self.name}_pdf_api_fail",
                *([f"fulltext:{self.name}_pdf_browser_fail"] if bootstrap.runtime is not None else []),
            ],
        )
