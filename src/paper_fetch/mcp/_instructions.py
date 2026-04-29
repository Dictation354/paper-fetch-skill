"""Canonical MCP and skill-facing instruction snippets."""

from __future__ import annotations

DEFAULT_FETCH_VALUES: tuple[tuple[str, str], ...] = (
    ("modes", '["article", "markdown"]'),
    ("strategy.asset_profile", "null (provider default)"),
    ("strategy.allow_metadata_only_fallback", "true"),
    ("include_refs", "null"),
    ("max_tokens", '"full_text"'),
    ("prefer_cache", "false"),
)

DEFAULT_FETCH_NOTES: tuple[str, ...] = (
    "`include_refs=null` behaves like `all` when `max_tokens=\"full_text\"`.",
    "When `max_tokens` is a positive integer, `include_refs=null` behaves like `top10`.",
)

SKILL_ENVIRONMENT_VARIABLES: tuple[tuple[str, str], ...] = (
    ("ELSEVIER_API_KEY", "Required for official Elsevier full-text access."),
    ("ELSEVIER_INSTTOKEN", "Optional institution token for Elsevier entitlement."),
    ("WILEY_TDM_CLIENT_TOKEN", "Optional Wiley Text and Data Mining client token for the official Wiley PDF lane; browser PDF/ePDF fallback can still run without it when the local runtime is ready."),
    ("FLARESOLVERR_URL", "Optional override for the local Wiley/Science/PNAS FlareSolverr endpoint; defaults to http://127.0.0.1:8191/v1."),
    ("FLARESOLVERR_ENV_FILE", "Required for Science/PNAS and for Wiley HTML/browser PDF routes; points at a repo-local vendor/flaresolverr preset file."),
    ("FLARESOLVERR_SOURCE_DIR", "Optional override for the repo-local vendor/flaresolverr directory."),
    ("PAPER_FETCH_DOWNLOAD_DIR", "Overrides the default CLI/MCP download directory."),
    ("PAPER_FETCH_RUN_LIVE", "Test-only flag for live publisher integration checks."),
)

ERROR_CONTRACT: tuple[tuple[str, str], ...] = (
    ("ambiguous", "Contains `candidates`; prompt the user to choose and retry."),
    ("no_access", "Credentials or entitlements are missing; inspect `missing_env` when present, then retry."),
    ("rate_limited", "Back off and retry later."),
    ("error", "Any other failure; inspect `reason`."),
)


def format_defaults_markdown() -> str:
    lines = ["Recommended defaults:"]
    lines.extend(f"- `{key}={value}`" for key, value in DEFAULT_FETCH_VALUES)
    lines.extend(f"- {note}" for note in DEFAULT_FETCH_NOTES)
    return "\n".join(lines)


def format_environment_markdown() -> str:
    lines = []
    for name, description in SKILL_ENVIRONMENT_VARIABLES:
        lines.append(f"- `{name}`: {description}")
    return "\n".join(lines)


def format_error_contract_markdown() -> str:
    lines = []
    for status, description in ERROR_CONTRACT:
        lines.append(f"- `{status}`: {description}")
    lines.append("- These fields appear in MCP `structuredContent` and in CLI stderr JSON for runtime fetch failures.")
    lines.append("- MCP error payloads may also include `missing_env=[...]` when credentials or required env vars are known.")
    lines.append("- CLI runtime fetch exit codes remain `ambiguous=2`, `no_access=3`, `rate_limited=4`; argparse validation errors also exit `2` but are not ambiguity results.")
    return "\n".join(lines)


def server_instructions() -> str:
    return (
        "Resolve or fetch a specific paper by DOI, landing URL, or title query. "
        "Use resolve_paper when the query may be ambiguous; it accepts either a raw query or "
        "structured title/authors/year fields. Use fetch_paper when you need "
        "structured article metadata, AI-friendly markdown, or both. "
        "The server also publishes `summarize_paper` and `verify_citation_list` prompt templates "
        "for cache-first single-paper summaries and bibliography triage workflows. "
        "All MCP tools now publish JSON output schemas for clients that support tool-result "
        "validation and autocomplete. "
        "Defaults: modes=['article','markdown'], strategy.asset_profile omitted (provider default), "
        "strategy.allow_metadata_only_fallback=true, "
        "include_refs=null, max_tokens='full_text'. In full_text mode include_refs=null "
        "behaves like 'all'. When asset_profile is body/all, optional "
        "strategy.inline_image_budget can tune the default inline ImageContent caps of "
        "3 figures, 2 MiB each, and 8 MiB total. `provider_hint` and "
        "`preferred_providers` may include `elsevier`, `springer`, `wiley`, `science`, `pnas`, or `crossref`. "
        "`elsevier` keeps an official XML route first and may then fall back to the "
        "official Elsevier API PDF lane before degrading to metadata-only, publishing "
        "`elsevier_xml` on XML success and `elsevier_pdf` on PDF fallback success. `springer` keeps a provider-managed direct HTML route "
        "with direct HTTP PDF fallback and publishes `springer_html`. `wiley` keeps "
        "the repo-local FlareSolverr HTML route, then seeded-browser publisher PDF/ePDF "
        "fallback, and may still continue into the official Wiley TDM API PDF lane "
        "when `WILEY_TDM_CLIENT_TOKEN` is configured while publishing `wiley_browser`. `science` "
        "and `pnas` require repo-local FlareSolverr/browser runtime but no legacy local "
        "rate-limit env vars, and keep their existing public source names. "
        "Elsevier PDF fallback currently returns text-only markdown even when "
        "`asset_profile` is `body` or `all`. On successful HTML/XML routes, "
        "`asset_profile='body'` means provider-cleaned body figure/table/formula assets only, "
        "while `asset_profile='all'` additionally downloads supplementary files. "
        "Inline ImageContent still only comes from body figures. Wiley/Science/PNAS support "
        "`asset_profile=body|all` on successful FlareSolverr HTML routes and "
        "prefer full-size/original figures before falling back to previews, while "
        "their PDF/ePDF fallback routes remain text-only. Springer PDF fallback "
        "is also text-only in this version. "
        "On supporting clients, fetch_paper and batch tools also emit progress updates "
        "and structured log notifications."
    )


def fetch_tool_description() -> str:
    return (
        "Fetch AI-friendly paper content. Returns a fixed FetchEnvelope-style object with "
        "top-level provenance, `token_estimate_breakdown={abstract,body,refs}`, and optional "
        "article/markdown/metadata payloads. "
        "The MCP tool also publishes an output schema for clients that support structured "
        "result validation. "
        "Defaults: modes=['article','markdown'], strategy.asset_profile omitted (provider default), "
        "strategy.allow_metadata_only_fallback=true, "
        "include_refs=null, max_tokens='full_text', prefer_cache=false. Set "
        "prefer_cache=true to resolve the query to a DOI, then try a matching local cached "
        "FetchEnvelope sidecar before running the full fetch waterfall. Use "
        "strategy.asset_profile='body' or 'all' to include local assets. "
        "With body/all profiles, key local figures may be returned as ImageContent "
        "alongside the JSON result; strategy.inline_image_budget can override the default "
        "caps of 3 figures, 2 MiB each, and 8 MiB total, and any resulting zero disables "
        "inline images. `elsevier` keeps an official XML route and may fall back to "
        "the official Elsevier API PDF lane before degrading to metadata-only, publishing "
        "`elsevier_xml` on XML success and `elsevier_pdf` on PDF fallback success. `springer` uses provider-managed direct HTML and direct "
        "HTTP PDF fallback while keeping public source `springer_html`. `wiley` keeps "
        "repo-local FlareSolverr HTML first, then seeded-browser publisher PDF/ePDF "
        "fallback, and may still continue into the official Wiley TDM API PDF lane "
        "when `WILEY_TDM_CLIENT_TOKEN` is configured while publishing source "
        "`wiley_browser` on success. `science` and `pnas` routes use "
        "provider-managed FlareSolverr HTML plus seeded-browser publisher PDF/ePDF repo-local "
        "workflows and keep their existing public source names. Elsevier PDF "
        "fallback keeps body/all requests text-only. On successful HTML/XML routes, "
        "`asset_profile='body'` means provider-cleaned body figure/table/formula assets only, "
        "while `asset_profile='all'` additionally downloads supplementary files; "
        "supplementary files are saved as assets but are not emitted as ImageContent. "
        "Wiley/Science/PNAS support body/all assets on successful FlareSolverr HTML routes while keeping "
        "PDF/ePDF fallback text-only, and Springer PDF fallback is also text-only "
        "in this version. Set "
        "download_dir to isolate task-local downloads; the MCP server can also surface "
        "scoped cache resources for that directory during the current session."
    )
