#!/usr/bin/env python3
"""Resolve DOI, URL, or title queries into a single normalized lookup object."""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
from dataclasses import asdict, dataclass, field
from typing import Any
from collections.abc import Mapping

from rapidfuzz import fuzz

from ..arxiv_id import (
    arxiv_id_from_doi,
    arxiv_id_from_query,
    arxiv_id_from_url,
    canonical_arxiv_abs_url,
    canonical_arxiv_doi,
)
from ..config import build_publisher_user_agent, build_runtime_env
from ..elsevier_identifiers import extract_elsevier_pii_from_url
from ..errors import ProviderFailure
from ..extraction.html.landing import fetch_landing_html
from ..html_lookup import is_usable_html_lookup_title
from ..http import HttpTransport, RequestFailure
from ..metadata.crossref import CrossrefLookupClient
from ..metadata.types import CrossrefMetadata
from ..mdpi_url import mdpi_doi_from_landing_url
from ..publisher_identity import (
    extract_doi,
    extract_doi_from_url,
    infer_provider_from_signals,
    normalize_doi,
)
from ..reason_codes import ERROR, NO_RESULT, NOT_SUPPORTED

CONFIDENT_SCORE_MIN = 0.90
CONFIDENT_MARGIN_MIN = 0.05
MIN_HTML_TITLE_LOOKUP_CHARS = 24
MAX_URL_REDIRECTS = 3
FORMAL_PUBLICATION_RELAXED_SCORE_MIN = 0.84
FORMAL_PUBLICATION_FORMAL_MARGIN_MIN = 0.10
FORMAL_PUBLICATION_PREPRINT_SCORE_GAP_MAX = 0.20
PREPRINT_DOI_PREFIXES = (
    "10.1101/",
    "10.21203/",
    "10.22541/au.",
)
PREPRINT_HOST_TOKENS = (
    "authorea.com",
    "biorxiv.org",
    "medrxiv.org",
    "researchsquare.com",
)
AMS_OLD_STYLE_SLUG_PATTERN = re.compile(
    r"^(?P<issn>\d{4}-\d{4})_"
    r"(?P<year>\d{4})_"
    r"(?P<volume>\d{3})_"
    r"(?P<page>\d{4})_"
    r"(?P<code>[A-Za-z0-9]+)_2_0_co_2$",
    flags=re.IGNORECASE,
)


@dataclass
class ResolvedQuery:
    query: str
    query_kind: str
    doi: str | None = None
    landing_url: str | None = None
    provider_hint: str | None = None
    confidence: float = 0.0
    candidates: list[dict[str, Any]] = field(default_factory=list)
    title: str | None = None
    provider_identifiers: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _ams_sici_doi_from_url(value: str) -> str | None:
    parsed = urllib.parse.urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if hostname != "journals.ametsoc.org" and not hostname.endswith(
        ".journals.ametsoc.org"
    ):
        return None
    stem = urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1]).rsplit(".", 1)[0]
    match = AMS_OLD_STYLE_SLUG_PATTERN.match(stem)
    if not match:
        return None
    return normalize_doi(
        "10.1175/"
        f"{match.group('issn')}({match.group('year')})"
        f"{match.group('volume')}<{match.group('page')}:{match.group('code').upper()}>2.0.CO;2"
    )


def normalize_title(value: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return re.sub(r"\s+", " ", lowered).strip()


def token_jaccard_score(left: str, right: str) -> float:
    left_tokens = set(normalize_title(left).split())
    right_tokens = set(normalize_title(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def sequence_ratio(left: str, right: str) -> float:
    return fuzz.ratio(normalize_title(left), normalize_title(right)) / 100


def candidate_score(query: str, candidate_title: str) -> float:
    jaccard = token_jaccard_score(query, candidate_title)
    ratio = sequence_ratio(query, candidate_title)
    return round((0.7 * jaccard) + (0.3 * ratio), 6)


def is_preprint_candidate(candidate: Mapping[str, Any]) -> bool:
    doi = normalize_doi(str(candidate.get("doi") or "")) or ""
    landing_url = str(candidate.get("landing_page_url") or "").lower()
    if any(doi.startswith(prefix) for prefix in PREPRINT_DOI_PREFIXES):
        return True
    return any(token in landing_url for token in PREPRINT_HOST_TOKENS)


def is_formal_publication_candidate(candidate: Mapping[str, Any]) -> bool:
    return bool(
        str(candidate.get("journal_title") or "").strip()
    ) and not is_preprint_candidate(candidate)


def score_candidates(
    query: str, candidates: list[CrossrefMetadata]
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for item in candidates:
        title = str(item.get("title") or "")
        score = candidate_score(query, title)
        provider_hint = infer_provider_from_signals(
            landing_urls=[str(item.get("landing_page_url") or "")],
            publishers=[str(item.get("publisher") or "")],
            doi=str(item.get("doi") or ""),
        )
        scored.append(
            {
                "doi": item.get("doi"),
                "title": item.get("title"),
                "journal_title": item.get("journal_title"),
                "published": item.get("published"),
                "landing_page_url": item.get("landing_page_url"),
                "provider_hint": provider_hint,
                "score": score,
                "is_preprint": is_preprint_candidate(item),
                "is_formal_publication": is_formal_publication_candidate(item),
            }
        )
    return sorted(
        scored,
        key=lambda item: (
            item["score"],
            bool(item["is_formal_publication"]),
            not bool(item["is_preprint"]),
        ),
        reverse=True,
    )


def select_formal_publication_candidate(
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not candidates:
        return None
    formal_candidates = [
        item for item in candidates if item.get("is_formal_publication")
    ]
    if not formal_candidates:
        return None
    formal_candidates.sort(key=lambda item: item["score"], reverse=True)
    selected = formal_candidates[0]
    if selected["score"] < FORMAL_PUBLICATION_RELAXED_SCORE_MIN:
        return None
    runner_up_score = (
        formal_candidates[1]["score"] if len(formal_candidates) > 1 else 0.0
    )
    if selected["score"] - runner_up_score < FORMAL_PUBLICATION_FORMAL_MARGIN_MIN:
        return None
    if not any(item.get("is_preprint") for item in candidates):
        return selected if selected is candidates[0] else None
    if (
        candidates[0]["score"] - selected["score"]
        <= FORMAL_PUBLICATION_PREPRINT_SCORE_GAP_MAX
    ):
        return selected
    return None


def should_defer_preprint_for_formal_publication(
    candidates: list[dict[str, Any]],
) -> bool:
    if not candidates or not candidates[0].get("is_preprint"):
        return False
    top_score = candidates[0]["score"]
    return any(
        item.get("is_formal_publication")
        and item["score"] >= FORMAL_PUBLICATION_RELAXED_SCORE_MIN
        and top_score - item["score"] <= FORMAL_PUBLICATION_PREPRINT_SCORE_GAP_MAX
        for item in candidates
    )


def is_confident_top_candidate(candidates: list[dict[str, Any]]) -> bool:
    if not candidates:
        return False
    if should_defer_preprint_for_formal_publication(candidates):
        return False
    top_one = candidates[0]
    top_two_score = candidates[1]["score"] if len(candidates) > 1 else 0.0
    return (
        top_one["score"] >= CONFIDENT_SCORE_MIN
        and (top_one["score"] - top_two_score) >= CONFIDENT_MARGIN_MIN
    )


def resolve_query(
    query: str,
    *,
    transport: HttpTransport | None = None,
    env: Mapping[str, str] | None = None,
) -> ResolvedQuery:
    normalized_query = query.strip()
    if not normalized_query:
        raise ProviderFailure(NOT_SUPPORTED, "Query must not be empty.")

    direct_arxiv_id = arxiv_id_from_query(normalized_query)
    if direct_arxiv_id and (
        arxiv_id_from_url(normalized_query)
        or normalized_query.lower().startswith("arxiv:")
    ):
        return ResolvedQuery(
            query=normalized_query,
            query_kind="url" if is_url(normalized_query) else "arxiv_id",
            doi=canonical_arxiv_doi(direct_arxiv_id),
            landing_url=canonical_arxiv_abs_url(direct_arxiv_id),
            provider_hint="arxiv",
            confidence=1.0,
        )
    if direct_arxiv_id and not is_url(normalized_query):
        direct_arxiv_doi = canonical_arxiv_doi(direct_arxiv_id)
        return ResolvedQuery(
            query=normalized_query,
            query_kind="doi" if arxiv_id_from_doi(normalized_query) else "arxiv_id",
            doi=direct_arxiv_doi,
            landing_url=canonical_arxiv_abs_url(direct_arxiv_id),
            provider_hint="arxiv",
            confidence=1.0,
        )

    active_transport = transport or HttpTransport()
    active_env = env or build_runtime_env()
    crossref = CrossrefLookupClient(active_transport, active_env)

    if is_url(normalized_query):
        mdpi_doi = mdpi_doi_from_landing_url(normalized_query)
        if mdpi_doi:
            return ResolvedQuery(
                query=normalized_query,
                query_kind="url",
                doi=mdpi_doi,
                landing_url=normalized_query,
                provider_hint="mdpi",
                confidence=1.0,
            )

        direct_doi = extract_doi_from_url(normalized_query) or _ams_sici_doi_from_url(
            normalized_query
        )
        if direct_doi:
            direct_provider_hint = infer_provider_from_signals(
                landing_urls=[normalized_query],
                doi=direct_doi,
            )
            if direct_provider_hint is not None:
                return ResolvedQuery(
                    query=normalized_query,
                    query_kind="url",
                    doi=direct_doi,
                    landing_url=normalized_query,
                    provider_hint=direct_provider_hint,
                    confidence=1.0,
                )
        direct_provider_hint = infer_provider_from_signals(
            landing_urls=[normalized_query]
        )
        if direct_provider_hint == "elsevier":
            elsevier_pii = extract_elsevier_pii_from_url(normalized_query)
            if elsevier_pii:
                return ResolvedQuery(
                    query=normalized_query,
                    query_kind="url",
                    landing_url=normalized_query,
                    provider_hint="elsevier",
                    confidence=1.0,
                    provider_identifiers={"pii": elsevier_pii},
                )
        request_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": build_publisher_user_agent(active_env),
        }
        current_url = normalized_query
        try:
            landing_fetch = fetch_landing_html(
                current_url,
                transport=active_transport,
                headers=request_headers,
                max_redirects=MAX_URL_REDIRECTS,
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            if direct_doi:
                provider_hint = infer_provider_from_signals(
                    landing_urls=[normalized_query],
                    doi=direct_doi,
                )
                return ResolvedQuery(
                    query=normalized_query,
                    query_kind="url",
                    doi=direct_doi,
                    landing_url=normalized_query,
                    provider_hint=provider_hint,
                    confidence=1.0,
                )
            raise ProviderFailure(
                ERROR, f"Failed to fetch landing page: {exc}"
            ) from exc
        response_url = landing_fetch.final_url
        html_metadata = landing_fetch.metadata
        landing_url = urllib.parse.urljoin(
            response_url,
            str(html_metadata.get("landing_page_url") or response_url).strip()
            or response_url,
        )
        resolved_doi = (
            normalize_doi(str(html_metadata.get("doi") or direct_doi or "")) or None
        )
        provider_hint = infer_provider_from_signals(
            landing_urls=[response_url, landing_url],
            doi=resolved_doi,
        )
        html_title = str(html_metadata.get("title") or "").strip() or None
        lookup_title = str(html_metadata.get("lookup_title") or "").strip() or None
        title_for_lookup = (
            html_title
            if is_usable_html_lookup_title(
                html_title, min_normalized_chars=MIN_HTML_TITLE_LOOKUP_CHARS
            )
            else None
        )
        if title_for_lookup is None and is_usable_html_lookup_title(
            lookup_title,
            min_normalized_chars=MIN_HTML_TITLE_LOOKUP_CHARS,
        ):
            title_for_lookup = lookup_title
        selected_title = html_title or title_for_lookup
        url_candidates: list[dict[str, Any]] = []
        confidence = 1.0 if direct_doi else (0.95 if resolved_doi else 0.0)
        if title_for_lookup and (not resolved_doi or provider_hint is None):
            url_candidates = score_candidates(
                title_for_lookup,
                crossref.search_bibliographic_candidates(title_for_lookup, rows=5),
            )
            selected_candidate = select_formal_publication_candidate(url_candidates)
            if selected_candidate is not None or is_confident_top_candidate(
                url_candidates
            ):
                top_one = selected_candidate or url_candidates[0]
                if not resolved_doi:
                    resolved_doi = normalize_doi(str(top_one.get("doi") or "")) or None
                    confidence = top_one["score"]
                    selected_title = str(top_one.get("title") or "") or title_for_lookup
                    url_candidates = []
                if provider_hint is None:
                    provider_hint = top_one.get("provider_hint") or provider_hint
        return ResolvedQuery(
            query=normalized_query,
            query_kind="url",
            doi=resolved_doi,
            landing_url=landing_url,
            provider_hint=provider_hint,
            confidence=confidence,
            candidates=url_candidates,
            title=selected_title,
        )

    direct_doi = extract_doi(normalized_query)
    if direct_doi:
        provider_hint = infer_provider_from_signals(doi=direct_doi)
        if provider_hint is None:
            try:
                crossref_metadata = crossref.fetch_metadata({"doi": direct_doi})
            except ProviderFailure:
                crossref_metadata = None
            provider_hint = infer_provider_from_signals(
                landing_urls=[
                    str((crossref_metadata or {}).get("landing_page_url") or "")
                ],
                publishers=[str((crossref_metadata or {}).get("publisher") or "")],
                doi=direct_doi,
            )
        return ResolvedQuery(
            query=normalized_query,
            query_kind="doi",
            doi=direct_doi,
            landing_url=None,
            provider_hint=provider_hint,
            confidence=1.0,
        )

    candidates = crossref.search_bibliographic_candidates(normalized_query, rows=5)
    if not candidates:
        raise ProviderFailure(
            NO_RESULT, "Crossref returned no metadata results for the title query."
        )
    scored = score_candidates(normalized_query, candidates)
    top_one = scored[0]
    selected_candidate = select_formal_publication_candidate(scored)
    if selected_candidate is not None or is_confident_top_candidate(scored):
        top_one = selected_candidate or top_one
        return ResolvedQuery(
            query=normalized_query,
            query_kind="title",
            doi=normalize_doi(str(top_one.get("doi") or "")) or None,
            landing_url=top_one.get("landing_page_url"),
            provider_hint=top_one.get("provider_hint"),
            confidence=top_one["score"],
            candidates=[],
            title=top_one.get("title"),
        )

    return ResolvedQuery(
        query=normalized_query,
        query_kind="title",
        landing_url=top_one.get("landing_page_url"),
        provider_hint=top_one.get("provider_hint"),
        confidence=top_one["score"],
        candidates=scored,
        title=top_one.get("title"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve DOI, URL, or title queries.")
    parser.add_argument("--query", required=True, help="DOI, paper URL, or title query")
    args = parser.parse_args()
    print(json.dumps(resolve_query(args.query).to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
