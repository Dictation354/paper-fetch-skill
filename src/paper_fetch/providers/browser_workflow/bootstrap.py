"""HTML bootstrap orchestration for provider browser workflows."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING

from ...extraction.html.signals import HtmlExtractionFailure
from ...metadata.types import ProviderMetadata
from ...publisher_identity import normalize_doi
from ...runtime import RuntimeContext
from . import html_extraction as _html_extraction
from .shared import (
    BrowserWorkflowDeps,
    default_browser_workflow_deps,
    preferred_html_candidate_from_landing_page as _preferred_html_candidate_from_landing_page,
)
from .._pdf_candidates import extract_pdf_candidate_urls_from_html
from ..browser_runtime.types import BrowserRuntimeFailure
from ..base import ProviderFailure
from ...reason_codes import NOT_SUPPORTED
from .profile import BrowserWorkflowBootstrapResult

if TYPE_CHECKING:
    from .client import BrowserWorkflowClient

logger = logging.getLogger("paper_fetch.providers.browser_workflow")
_BROWSER_FAILURE_MESSAGE_MAX_CHARS = 4096


def _structured_browser_failure_message(exc: BrowserRuntimeFailure) -> str:
    details = dict(exc.details or {})
    browser_failure = details.get("browser_failure")
    failure_payload = (
        dict(browser_failure) if isinstance(browser_failure, Mapping) else details
    )
    stage = str(failure_payload.get("stage") or "").strip()
    stderr_summary = str(failure_payload.get("stderr_summary") or "").strip()
    parts = [f"{stage}: {exc.message}" if stage else exc.message]
    if stderr_summary:
        parts.append(f"Chrome stderr: {stderr_summary}")
    message = " ".join(part for part in parts if part).strip()
    if len(message) > _BROWSER_FAILURE_MESSAGE_MAX_CHARS:
        message = "..." + message[-_BROWSER_FAILURE_MESSAGE_MAX_CHARS:]
    return message


def _fetch_browser_html_payload(
    *args, deps: BrowserWorkflowDeps | None = None, **kwargs
):
    deps = deps or default_browser_workflow_deps()
    kwargs.setdefault(
        "html_fetcher",
        deps.fetch_html_with_browser,
    )
    return _html_extraction._fetch_browser_html_payload(*args, **kwargs)


def _fetch_browser_html_payload_with_fast_path(
    *args,
    deps: BrowserWorkflowDeps | None = None,
    **kwargs,
):
    deps = deps or default_browser_workflow_deps()
    kwargs.setdefault(
        "html_fetcher",
        deps.fetch_html_with_browser,
    )
    return _html_extraction._fetch_browser_html_payload_with_fast_path(*args, **kwargs)


def bootstrap_browser_workflow(
    client: BrowserWorkflowClient,
    doi: str,
    metadata: ProviderMetadata,
    *,
    allow_runtime_failure: bool = False,
    context: RuntimeContext | None = None,
    deps: BrowserWorkflowDeps | None = None,
) -> BrowserWorkflowBootstrapResult:
    deps = deps or default_browser_workflow_deps()
    context = client._runtime_context(context)
    normalized_doi = normalize_doi(doi)
    if not normalized_doi:
        raise ProviderFailure(
            NOT_SUPPORTED, f"{client.name} full-text retrieval requires a DOI."
        )

    landing_page_url = str(metadata.get("landing_page_url") or "") or None
    html_candidates = client.html_candidates(normalized_doi, metadata)
    pdf_candidates = client.pdf_candidates(normalized_doi, metadata)
    result = BrowserWorkflowBootstrapResult(
        normalized_doi=normalized_doi,
        runtime=None,
        landing_page_url=landing_page_url,
        html_candidates=html_candidates,
        pdf_candidates=pdf_candidates,
    )

    profile = client.require_profile()
    preferred_html_candidate = _preferred_html_candidate_from_landing_page(
        normalized_doi,
        landing_page_url,
        hosts=profile.hosts,
    )
    logger.debug(
        "browser_workflow_candidates provider=%s doi=%s preferred_hit=%s first_candidate=%s candidate_count=%s",
        client.name,
        normalized_doi,
        bool(
            preferred_html_candidate
            and html_candidates
            and html_candidates[0] == preferred_html_candidate
        ),
        html_candidates[0] if html_candidates else None,
        len(html_candidates),
    )

    try:
        if result.runtime is None:
            result.runtime = deps.load_runtime_config(
                client.env,
                provider=client.name,
                doi=normalized_doi,
            )
            deps.ensure_runtime_ready(result.runtime)
    except ProviderFailure as exc:
        if not allow_runtime_failure:
            raise
        result.runtime_failure = exc
        result.html_failure_reason = exc.code
        result.html_failure_message = exc.message
        return result

    try:
        html_result, html_payload = _fetch_browser_html_payload_with_fast_path(
            client,
            html_candidates,
            runtime=result.runtime,
            metadata=metadata,
            context=context,
            warnings=result.warnings,
            deps=deps,
        )
        result.browser_context_seed = html_result.browser_context_seed
        result.html_payload = html_payload
        return result
    except BrowserRuntimeFailure as exc:
        result.browser_context_seed = (
            exc.browser_context_seed or result.browser_context_seed
        )
        result.html_failure_reason = exc.kind
        result.html_failure_message = _structured_browser_failure_message(exc)
        result.html_failure_diagnostics = dict(exc.details or {})
    except HtmlExtractionFailure as exc:
        extraction_html_result = getattr(exc, "html_result", None)
        if extraction_html_result is not None:
            result.browser_context_seed = (
                getattr(extraction_html_result, "browser_context_seed", None)
                or result.browser_context_seed
            )
            for pdf_candidate in reversed(
                extract_pdf_candidate_urls_from_html(
                    getattr(extraction_html_result, "html", "") or "",
                    getattr(extraction_html_result, "final_url", "") or "",
                )
            ):
                if pdf_candidate and pdf_candidate not in result.pdf_candidates:
                    result.pdf_candidates.insert(0, pdf_candidate)
        result.html_failure_reason = exc.reason
        result.html_failure_message = exc.message

    return result
