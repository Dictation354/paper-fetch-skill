"""Wiley provisional HTTP access-status review and candidate continuation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from bs4 import BeautifulSoup

from ..runtime import RuntimeContext
from ..quality.html_availability import HtmlQualityAssessor
from ..publisher_identity import extract_doi, extract_doi_from_url, normalize_doi
from ..utils import normalize_text
from ..extraction.html.parsing import choose_parser
from .browser_runtime import BrowserFetchedHtml
from .browser_workflow.shared import normalize_browser_url
from .browser_workflow.html_extraction import _browser_runtime_trace

_HTTP_ACCESS_STATUS_REVIEW_KEY = "http_access_status_review"
_WILEY_REVIEWABLE_HTTP_STATUSES = frozenset({401, 403})
_WILEY_DOI_META_NAMES = frozenset(
    {"citation_doi", "dc.identifier", "dc.identifier.doi", "prism.doi"}
)


def _wiley_document_doi_evidence(html_text: str) -> list[tuple[str, str]]:
    """Return normalized DOI evidence from Wiley-owned identity nodes."""

    try:
        soup = BeautifulSoup(html_text, choose_parser())
    except Exception:
        return []

    evidence: list[tuple[str, str]] = []

    def add(source: str, value: Any, *, from_url: bool = False) -> None:
        raw_value = normalize_text(str(value or ""))
        if not raw_value:
            return
        doi = extract_doi_from_url(raw_value) if from_url else extract_doi(raw_value)
        normalized = normalize_doi(doi or "")
        item = (source, normalized)
        if normalized and item not in evidence:
            evidence.append(item)

    for node in soup.find_all("meta"):
        attrs = getattr(node, "attrs", None) or {}
        name = normalize_text(
            str(attrs.get("name") or attrs.get("property") or "")
        ).lower()
        if name in _WILEY_DOI_META_NAMES:
            add("citation_meta", attrs.get("content"))

    for node in soup.select("link[rel~='canonical']"):
        attrs = getattr(node, "attrs", None) or {}
        add("canonical", attrs.get("href"), from_url=True)

    for node in soup.select(".epub-doi"):
        add("epub_doi", node.get_text(" ", strip=True))
        attrs = getattr(node, "attrs", None) or {}
        add("epub_doi", attrs.get("href"), from_url=True)
        for link in node.select("a[href]"):
            add(
                "epub_doi",
                (getattr(link, "attrs", None) or {}).get("href"),
                from_url=True,
            )
    return evidence


def _wiley_http_access_status_review(
    *,
    return_image_payload: bool,
    status: int | None,
    requested_doi: str,
    requested_url: str,
    final_url: str,
    html_text: str,
    title: str,
    body_ready: bool,
    runtime_context: RuntimeContext | None = None,
) -> dict[str, Any] | None:
    if status not in _WILEY_REVIEWABLE_HTTP_STATUSES or return_image_payload:
        return None

    expected_doi = normalize_doi(requested_doi)
    doi_evidence = _wiley_document_doi_evidence(html_text)
    matching_sources = [
        source for source, observed_doi in doi_evidence if observed_doi == expected_doi
    ]
    evidence_sources = list(dict.fromkeys(source for source, _doi in doi_evidence))

    preliminary = HtmlQualityAssessor("wiley").assess(
        "",
        {"doi": expected_doi},
        html_text=html_text,
        structure_html_text=html_text,
        title=title or None,
        response_status=None,
        requested_url=requested_url,
        final_url=final_url,
        context=runtime_context,
    )
    blocking_signals = list(
        dict.fromkeys(
            [
                *preliminary.hard_negative_signals,
                *preliminary.blocking_fallback_signals,
            ]
        )
    )
    doi_match = bool(expected_doi and matching_sources)
    candidate_confirmed = bool(body_ready and doi_match and not blocking_signals)
    if not body_ready:
        reason = "body_not_ready"
    elif not expected_doi:
        reason = "requested_doi_missing"
    elif not doi_evidence:
        reason = "doi_evidence_missing"
    elif not doi_match:
        reason = "doi_mismatch"
    elif blocking_signals:
        reason = "blocking_signal"
    else:
        reason = "pending_fulltext_acceptance"

    return {
        "status": status,
        "body_ready": bool(body_ready),
        "doi_evidence_present": bool(doi_evidence),
        "doi_evidence_sources": evidence_sources,
        "doi_match": doi_match,
        "doi_match_sources": list(dict.fromkeys(matching_sources)),
        "blocking_signals": blocking_signals,
        "candidate_confirmed": candidate_confirmed,
        "status_override_applied": False,
        "fulltext_acceptance": "pending" if candidate_confirmed else "not_attempted",
        "accepted": False,
        "reason": reason,
    }


def _remaining_wiley_review_candidates(
    html_candidates: Sequence[str],
    html_result: BrowserFetchedHtml,
) -> list[str]:
    if html_result.response_status not in {401, 403}:
        return []
    trace = _browser_runtime_trace(html_result.diagnostics)
    candidates = trace.get("candidates")
    if not isinstance(candidates, list):
        return []
    confirmed_review = False
    for candidate in reversed(candidates):
        if not isinstance(candidate, Mapping):
            continue
        review = candidate.get(_HTTP_ACCESS_STATUS_REVIEW_KEY)
        if not isinstance(review, Mapping):
            continue
        if (
            review.get("candidate_confirmed") is True
            and review.get("fulltext_acceptance") == "rejected"
        ):
            confirmed_review = True
            break
    if not confirmed_review:
        return []

    failed_source = normalize_browser_url(html_result.source_url)
    if not failed_source:
        return []
    normalized_candidates = [
        normalize_browser_url(candidate) or normalize_text(candidate)
        for candidate in html_candidates
    ]
    try:
        failed_index = normalized_candidates.index(failed_source)
    except ValueError:
        return []
    return list(html_candidates[failed_index + 1 :])
