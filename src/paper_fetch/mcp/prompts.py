"""Thin MCP prompt templates for common paper-fetch workflows."""

from __future__ import annotations

from ..utils import normalize_text


def _clean_multiline_input(value: str) -> str:
    lines = [line.rstrip() for line in (value or "").splitlines()]
    trimmed = "\n".join(line for line in lines if line.strip())
    return trimmed or normalize_text(value)


def summarize_paper_prompt(query: str, focus: str = "general") -> str:
    normalized_query = normalize_text(query) or "<paper query>"
    normalized_focus = normalize_text(focus) or "general"
    return (
        "Summarize one specific paper.\n\n"
        "Preferred workflow:\n"
        "1. If the query might be ambiguous, call `resolve_paper(query)` first.\n"
        "2. If you already have a DOI from earlier turns, prefer `get_cached(doi)` or `list_cached()` before refetching.\n"
        "3. Call `fetch_paper(query, modes=[\"article\", \"markdown\"], prefer_cache=true)`.\n"
        "4. Use top-level `source`, `warnings`, `token_estimate`, and `token_estimate_breakdown={abstract, body, refs}` when deciding whether the result is complete enough.\n"
        "5. If `token_estimate_breakdown.refs` is large and the summary focus does not need references, retry with a stricter `include_refs` or smaller numeric `max_tokens`.\n"
        "6. If `has_fulltext=false` or `source=\"metadata_only\"`, state clearly that the summary is based on metadata or abstract only.\n\n"
        f"Paper query: {normalized_query}\n"
        f"Summary focus: {normalized_focus}"
    )


def verify_citation_list_prompt(citations: str, mode: str = "metadata") -> str:
    normalized_citations = _clean_multiline_input(citations) or "<citation list>"
    normalized_mode = normalize_text(mode) or "metadata"
    return (
        "Check a citation list for readability and follow-up fetchability.\n\n"
        "Preferred workflow:\n"
        "1. Split the citation list into one query per item.\n"
        f"2. Start with `batch_check(queries, mode=\"{normalized_mode}\")`; default to `mode=\"metadata\"` unless you explicitly need full fetch verdicts.\n"
        "3. Only follow up with `resolve_paper(...)` or `fetch_paper(..., prefer_cache=true)` for promising, ambiguous, or user-selected items.\n"
        "4. Report which entries are likely readable now, which are ambiguous, and which remain metadata-only or unknown.\n"
        "5. Do not mark an item unreadable just because there is no local cached file yet.\n\n"
        "Citation list:\n"
        f"{normalized_citations}"
    )
