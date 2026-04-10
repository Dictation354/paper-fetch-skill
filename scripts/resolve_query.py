#!/usr/bin/env python3
"""Resolve DOI, URL, or title queries into a single normalized lookup object."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from fetch_common import HttpTransport, ProviderFailure, build_runtime_env, build_user_agent
from providers.crossref import CrossrefClient
from providers.html_generic import decode_html, infer_provider_from_url, parse_html_metadata
from publisher_identity import infer_provider_from_doi, normalize_doi

DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+", flags=re.IGNORECASE)
CONFIDENT_SCORE_MIN = 0.90
CONFIDENT_MARGIN_MIN = 0.05
MIN_HTML_TITLE_LOOKUP_CHARS = 24
HTML_TITLE_LOOKUP_DENYLIST = (
    "sign in",
    "just a moment",
    "cookie",
    "subscribe",
    "access denied",
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_doi(text: str | None) -> str | None:
    if not text:
        return None
    match = DOI_PATTERN.search(text)
    if not match:
        return None
    return normalize_doi(match.group(0).rstrip(").,;"))


def is_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


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
    return SequenceMatcher(None, normalize_title(left), normalize_title(right)).ratio()


def candidate_score(query: str, candidate_title: str) -> float:
    jaccard = token_jaccard_score(query, candidate_title)
    ratio = sequence_ratio(query, candidate_title)
    return round((0.7 * jaccard) + (0.3 * ratio), 6)


def score_candidates(query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for item in candidates:
        title = str(item.get("title") or "")
        score = candidate_score(query, title)
        provider_hint = infer_provider_from_doi(item.get("doi"))
        scored.append(
            {
                "doi": item.get("doi"),
                "title": item.get("title"),
                "journal_title": item.get("journal_title"),
                "published": item.get("published"),
                "landing_page_url": item.get("landing_page_url"),
                "provider_hint": provider_hint,
                "score": score,
            }
        )
    return sorted(scored, key=lambda item: item["score"], reverse=True)


def is_confident_top_candidate(candidates: list[dict[str, Any]]) -> bool:
    if not candidates:
        return False
    top_one = candidates[0]
    top_two_score = candidates[1]["score"] if len(candidates) > 1 else 0.0
    return top_one["score"] >= CONFIDENT_SCORE_MIN and (top_one["score"] - top_two_score) >= CONFIDENT_MARGIN_MIN


def is_viable_html_title_for_lookup(value: str | None) -> bool:
    normalized = normalize_title(value or "")
    if len(normalized) < MIN_HTML_TITLE_LOOKUP_CHARS:
        return False
    return not any(token in normalized for token in HTML_TITLE_LOOKUP_DENYLIST)


def resolve_query(
    query: str,
    *,
    transport: HttpTransport | None = None,
    env: Mapping[str, str] | None = None,
) -> ResolvedQuery:
    normalized_query = query.strip()
    if not normalized_query:
        raise ProviderFailure("not_supported", "Query must not be empty.")

    active_transport = transport or HttpTransport()
    active_env = env or build_runtime_env()

    direct_doi = extract_doi(normalized_query)
    if direct_doi:
        landing_url = normalized_query if is_url(normalized_query) else None
        return ResolvedQuery(
            query=normalized_query,
            query_kind="url" if landing_url else "doi",
            doi=direct_doi,
            landing_url=landing_url,
            provider_hint=infer_provider_from_doi(direct_doi) or (infer_provider_from_url(landing_url) if landing_url else None),
            confidence=1.0,
        )

    if is_url(normalized_query):
        try:
            response = active_transport.request(
                "GET",
                normalized_query,
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "User-Agent": build_user_agent(active_env),
                },
            )
        except Exception as exc:
            if isinstance(exc, ProviderFailure):
                raise
            raise ProviderFailure("error", f"Failed to fetch landing page: {exc}") from exc
        html_metadata = parse_html_metadata(decode_html(response["body"]), response["url"])
        resolved_doi = normalize_doi(str(html_metadata.get("doi") or "")) or None
        provider_hint = infer_provider_from_doi(resolved_doi) if resolved_doi else infer_provider_from_url(response["url"])
        html_title = str(html_metadata.get("title") or "").strip() or None
        lookup_title = str(html_metadata.get("lookup_title") or "").strip() or None
        title_for_lookup = html_title if is_viable_html_title_for_lookup(html_title) else None
        if title_for_lookup is None and is_viable_html_title_for_lookup(lookup_title):
            title_for_lookup = lookup_title
        selected_title = html_title if resolved_doi else title_for_lookup
        candidates: list[dict[str, Any]] = []
        confidence = 0.95 if resolved_doi else 0.0
        if not resolved_doi and title_for_lookup:
            crossref = CrossrefClient(active_transport, active_env)
            candidates = score_candidates(
                title_for_lookup,
                crossref.search_bibliographic_candidates(title_for_lookup, rows=5),
            )
            if is_confident_top_candidate(candidates):
                top_one = candidates[0]
                resolved_doi = normalize_doi(str(top_one.get("doi") or "")) or None
                provider_hint = top_one.get("provider_hint") or provider_hint
                confidence = top_one["score"]
                selected_title = str(top_one.get("title") or "") or title_for_lookup
                candidates = []
        return ResolvedQuery(
            query=normalized_query,
            query_kind="url",
            doi=resolved_doi,
            landing_url=str(html_metadata.get("landing_page_url") or response["url"]),
            provider_hint=provider_hint,
            confidence=confidence,
            candidates=candidates,
            title=selected_title,
        )

    crossref = CrossrefClient(active_transport, active_env)
    candidates = crossref.search_bibliographic_candidates(normalized_query, rows=5)
    if not candidates:
        raise ProviderFailure("no_result", "Crossref returned no metadata results for the title query.")
    scored = score_candidates(normalized_query, candidates)
    top_one = scored[0]
    if is_confident_top_candidate(scored):
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
