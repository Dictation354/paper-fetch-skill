"""HTML bootstrap orchestration for provider browser workflows."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from ...extraction.html.signals import SciencePnasHtmlFailure
from ...metadata_types import ProviderMetadata
from ...publisher_identity import normalize_doi
from ...runtime import RuntimeContext
from ...utils import normalize_text
from .. import _browser_workflow_html_extraction as _html_extraction
from .._browser_workflow_html_extraction import (
    _browser_workflow_html_payload,
    _cached_browser_workflow_markdown,
    fetch_html_with_direct_playwright as _fetch_html_with_direct_playwright,
)
from .._browser_workflow_shared import (
    preferred_html_candidate_from_landing_page as _preferred_html_candidate_from_landing_page,
)
from .._flaresolverr import (
    FlareSolverrFailure,
    ensure_runtime_ready as _ensure_runtime_ready,
    fetch_html_with_flaresolverr as _fetch_html_with_flaresolverr,
    load_runtime_config as _load_runtime_config,
)
from ..base import ProviderFailure
from .profile import BrowserWorkflowBootstrapResult

if TYPE_CHECKING:
    from .client import BrowserWorkflowClient

logger = logging.getLogger("paper_fetch.providers.browser_workflow")


def _facade_attr(name: str, fallback):
    facade = sys.modules.get("paper_fetch.providers.browser_workflow")
    return getattr(facade, name, fallback) if facade is not None else fallback


def _fetch_flaresolverr_html_payload(*args, **kwargs):
    kwargs.setdefault(
        "html_fetcher",
        _facade_attr("fetch_html_with_flaresolverr", _fetch_html_with_flaresolverr),
    )
    return _html_extraction._fetch_flaresolverr_html_payload(*args, **kwargs)


def _fetch_flaresolverr_html_payload_with_fast_path(*args, **kwargs):
    kwargs.setdefault(
        "html_fetcher",
        _facade_attr("fetch_html_with_flaresolverr", _fetch_html_with_flaresolverr),
    )
    return _html_extraction._fetch_flaresolverr_html_payload_with_fast_path(
        *args, **kwargs
    )


def bootstrap_browser_workflow(
    client: "BrowserWorkflowClient",
    doi: str,
    metadata: ProviderMetadata,
    *,
    allow_runtime_failure: bool = False,
    context: RuntimeContext | None = None,
) -> BrowserWorkflowBootstrapResult:
    context = client._runtime_context(context)
    normalized_doi = normalize_doi(doi)
    if not normalized_doi:
        raise ProviderFailure(
            "not_supported", f"{client.name} full-text retrieval requires a DOI."
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

    if profile.direct_playwright_html_preflight:
        try:
            html_result = _facade_attr(
                "fetch_html_with_direct_playwright", _fetch_html_with_direct_playwright
            )(
                html_candidates,
                publisher=client.name,
                user_agent=client.user_agent,
                context=context,
            )
            result.browser_context_seed = html_result.browser_context_seed
            markdown_text, extraction = _cached_browser_workflow_markdown(
                client,
                html_result.html,
                html_result.final_url,
                metadata=metadata,
                context=context,
            )
            result.html_payload = _browser_workflow_html_payload(
                client,
                html_result,
                markdown_text=markdown_text,
                extraction=extraction,
                fetcher="playwright_direct",
                warnings=result.warnings,
            )
            return result
        except SciencePnasHtmlFailure as exc:
            logger.debug(
                "browser_workflow_direct_html_preflight provider=%s doi=%s action=fallback reason=%s message=%s",
                client.name,
                normalized_doi,
                exc.reason,
                exc.message,
            )
        except Exception as exc:
            logger.debug(
                "browser_workflow_direct_html_preflight provider=%s doi=%s action=fallback error=%s",
                client.name,
                normalized_doi,
                normalize_text(str(exc)) or exc.__class__.__name__,
            )

    try:
        result.runtime = _facade_attr("load_runtime_config", _load_runtime_config)(
            client.env,
            provider=client.name,
            doi=normalized_doi,
        )
        _facade_attr("ensure_runtime_ready", _ensure_runtime_ready)(result.runtime)
    except ProviderFailure as exc:
        if not allow_runtime_failure:
            raise
        result.runtime_failure = exc
        result.html_failure_reason = exc.code
        result.html_failure_message = exc.message
        return result

    try:
        html_result, html_payload = _fetch_flaresolverr_html_payload_with_fast_path(
            client,
            html_candidates,
            runtime=result.runtime,
            metadata=metadata,
            context=context,
            warnings=result.warnings,
        )
        result.browser_context_seed = html_result.browser_context_seed
        result.html_payload = html_payload
        return result
    except FlareSolverrFailure as exc:
        result.browser_context_seed = (
            exc.browser_context_seed or result.browser_context_seed
        )
        result.html_failure_reason = exc.kind
        result.html_failure_message = exc.message
    except SciencePnasHtmlFailure as exc:
        result.html_failure_reason = exc.reason
        result.html_failure_message = exc.message

    return result
