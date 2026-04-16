"""Wiley provider client with browser HTML and official TDM PDF fallbacks."""

from __future__ import annotations

import urllib.parse
from typing import Any, Mapping

from ..http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, RequestFailure
from ..publisher_identity import normalize_doi
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
        return summarize_capability_status(
            self.name,
            official_provider=self.official_provider,
            checks=[
                *browser_status.checks,
                build_provider_status_check(
                    "tdm_api_token",
                    "ok" if token_configured else "not_configured",
                    (
                        "Wiley TDM API client token is configured."
                        if token_configured
                        else f"{WILEY_TDM_CLIENT_TOKEN_ENV_VAR} is required for Wiley PDF fallback when HTML is not usable."
                    ),
                    missing_env=[] if token_configured else [WILEY_TDM_CLIENT_TOKEN_ENV_VAR],
                    details={"env_var": WILEY_TDM_CLIENT_TOKEN_ENV_VAR},
                ),
            ],
        )

    def fetch_raw_fulltext(self, doi: str, metadata: Mapping[str, Any]) -> RawFulltextPayload:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            raise ProviderFailure("not_supported", f"{self.name} full-text retrieval requires a DOI.")

        html_candidates = self.html_candidates(normalized_doi, metadata)

        html_failure_reason: str | None = None
        html_failure_message: str | None = None
        warnings: list[str] = []

        browser_runtime = None
        browser_runtime_failure: ProviderFailure | None = None
        try:
            browser_runtime = _science_pnas.load_runtime_config(self.env, provider=self.name, doi=normalized_doi)
            _science_pnas.ensure_runtime_ready(browser_runtime)
        except ProviderFailure as exc:
            browser_runtime_failure = exc
            html_failure_reason = exc.code
            html_failure_message = exc.message

        if browser_runtime is not None:
            try:
                html_result = _science_pnas.fetch_html_with_flaresolverr(
                    html_candidates,
                    publisher=self.name,
                    config=browser_runtime,
                )
                markdown_text, extraction = self.extract_markdown(
                    html_result.html,
                    html_result.final_url,
                    metadata=metadata,
                )
                return RawFulltextPayload(
                    provider=self.name,
                    source_url=html_result.final_url,
                    content_type="text/html",
                    body=html_result.html.encode("utf-8"),
                    metadata={
                        "route": "html",
                        "markdown_text": markdown_text,
                        "warnings": warnings,
                        "source_trail": [f"fulltext:{self.name}_html_ok"],
                        "html_fetcher": "flaresolverr",
                        "extraction": extraction,
                    },
                    needs_local_copy=False,
                )
            except _science_pnas.FlareSolverrFailure as exc:
                html_failure_reason = exc.kind
                html_failure_message = exc.message
            except _science_pnas.SciencePnasHtmlFailure as exc:
                html_failure_reason = exc.reason
                html_failure_message = exc.message

        warnings.append(
            f"{self.name} HTML route was not usable ({html_failure_reason or 'html_failed'}); attempting Wiley TDM API PDF fallback."
        )

        api_failure_message: str | None = None
        if self.tdm_client_token:
            api_url = self._tdm_api_url(normalized_doi)
            try:
                pdf_result = _fetch_wiley_tdm_pdf_result(
                    self.transport,
                    api_url=api_url,
                    headers=self._tdm_api_headers(),
                    artifact_dir=(browser_runtime.artifact_dir / "pdf_api_fallback") if browser_runtime is not None else None,
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
                        "html_failure_reason": html_failure_reason,
                        "html_failure_message": html_failure_message,
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
        else:
            api_failure_message = (
                f"Wiley TDM API PDF fallback is not configured because {WILEY_TDM_CLIENT_TOKEN_ENV_VAR} is missing."
            )

        failure_parts = [f"HTML failure: {html_failure_message or 'wiley HTML route failed.'}"]
        if api_failure_message:
            failure_parts.append(f"Wiley API PDF failure: {api_failure_message}")
        missing_env: list[str] = []
        if browser_runtime is None and browser_runtime_failure is not None:
            missing_env.extend(browser_runtime_failure.missing_env)
        if not self.tdm_client_token and WILEY_TDM_CLIENT_TOKEN_ENV_VAR not in missing_env:
            missing_env.append(WILEY_TDM_CLIENT_TOKEN_ENV_VAR)

        raise ProviderFailure(
            "not_configured" if browser_runtime is None and not self.tdm_client_token else "no_result",
            f"{self.name} full text could not be retrieved. " + " ".join(failure_parts),
            missing_env=missing_env,
            warnings=warnings + ([api_failure_message] if api_failure_message else []),
            source_trail=[
                f"fulltext:{self.name}_html_fail",
                f"fulltext:{self.name}_pdf_api_fail",
            ],
        )
