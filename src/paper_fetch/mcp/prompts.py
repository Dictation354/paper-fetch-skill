"""Thin MCP prompt templates for common paper-fetch workflows."""

from __future__ import annotations

from ..utils import normalize_text


_FAILURE_POLICY = (
    "For failures, use the paper-fetch skill's `references/failure-handling.md` "
    "as the canonical decision table. Classify structured categories as `ambiguous`; "
    "`validation_error`; deterministic `no_result`/`not_supported`; `no_access`/"
    "`not_configured`; `rate_limited`; `network_error`/`timeout`/`tls_error`/"
    "`dns_error`/`connection_reset`/`connection_closed`; `response_too_large`/"
    "`unsupported_url_scheme`/`unsafe_redirect`; `invalid_json`/"
    "`response_schema_mismatch`; browser transient; "
    "`cancelled`/`request_cancelled`; or unclassified `error`. Make one initial "
    "attempt and at most two meaningful agent retries. Do not blindly retry ambiguity, "
    "validation errors, or deterministic parse failures; retry no-access only after "
    "auth state changes; honor Retry-After and stop new submissions to the same "
    "rate-limited provider; retry network or browser transients only after parameters, "
    "state, or environment change; and resume cancellation only when requested. "
    "An unchanged `prefer_cache=false` rerun is not a cache bypass."
)


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
        '2. If you already have a DOI and an explicit cache scope, call `get_cached(doi, download_dir=<scope>, detail="compact", preferred_only=true, modes=["article", "markdown"], include_refs=null, max_tokens="full_text")` before refetching; pass the same strategy and do not scan the whole cache. A top-level hit only proves entries exist; reuse the sidecar only when request_satisfied=true.\n'
        '3. When a fetch is still needed, call `fetch_paper(query, modes=["article", "markdown"], prefer_cache=true)` with the same cache scope and task parameters. A cache miss or request mismatch is normal routing, not a terminal failure.\n'
        "4. Use top-level `source`, `warnings`, `token_estimate`, and `token_estimate_breakdown={abstract, body, refs}` when deciding whether the result is complete enough.\n"
        "5. If `token_estimate_breakdown.refs` is large and the summary focus does not need references, a retry with a stricter `include_refs` or smaller numeric `max_tokens` is meaningful, but it still counts toward the agent retry limit.\n"
        '6. If `has_fulltext=false` or `source="metadata_only"`, state clearly that the summary is based on metadata or abstract only.\n\n'
        f"{_FAILURE_POLICY}\n\n"
        f"Paper query: {normalized_query}\n"
        f"Summary focus: {normalized_focus}"
    )


def verify_citation_list_prompt(citations: str, mode: str = "metadata") -> str:
    normalized_citations = _clean_multiline_input(citations) or "<citation list>"
    normalized_mode = normalize_text(mode) or "metadata"
    return (
        "Check a citation list for readability and follow-up fetchability.\n\n"
        "Preferred workflow:\n"
        "1. Split the citation list into one query per item and retain its original 1-based index.\n"
        f'2. Use `batch_check(queries, mode="{normalized_mode}")`; default to `mode="metadata"` unless real article fetches are explicitly needed. Metadata mode is a lower-cost likely probe, while article mode performs real fetches and still requires acceptance.\n'
        "3. Each batch call accepts at most 50 queries. For a longer list, make contiguous index chunks of at most 50, map every result back to its original index, and sort by that index when merging.\n"
        "4. Keep resolve, probe/fetch, and acceptance stages in dependency order. Within one stage, use an explicit supported `concurrency=1..8` chosen for the provider and host; do not assume a default of 3.\n"
        "5. In metadata mode, treat `probe_state` as authoritative: `likely_yes` is only a readability signal and `unknown` is insufficient evidence. Never report either as fetched full text or verified `has_fulltext=true`, even if a compatibility field is present.\n"
        "6. In article mode, report the actual `has_fulltext`, `content_kind`, source, warnings, and acceptance result; a fetch attempt alone is not acceptance.\n"
        "7. Only follow up with `resolve_paper(...)` or `fetch_paper(...)` for ambiguous, user-selected, or still-required items, preserving the original index and task parameters.\n"
        "8. Do not mark an item unreadable just because there is no local cached file yet.\n\n"
        f"{_FAILURE_POLICY}\n\n"
        "Citation list:\n"
        f"{normalized_citations}"
    )
