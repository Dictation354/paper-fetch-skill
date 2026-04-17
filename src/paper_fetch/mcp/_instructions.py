"""Canonical MCP and skill-facing instruction snippets."""

from __future__ import annotations

DEFAULT_FETCH_VALUES: tuple[tuple[str, str], ...] = (
    ("modes", '["article", "markdown"]'),
    ("strategy.asset_profile", '"none"'),
    ("strategy.allow_html_fallback", "true"),
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
    ("FLARESOLVERR_URL", "Optional override for the local Elsevier/Wiley/Science/PNAS FlareSolverr endpoint; defaults to http://127.0.0.1:8191/v1."),
    ("FLARESOLVERR_ENV_FILE", "Required for Elsevier browser fallback and Wiley/Science/PNAS; points at a repo-local vendor/flaresolverr preset file."),
    ("FLARESOLVERR_SOURCE_DIR", "Optional override for the repo-local vendor/flaresolverr directory."),
    ("FLARESOLVERR_MIN_INTERVAL_SECONDS", "Required local minimum spacing between Elsevier browser fallback and Wiley/Science/PNAS requests."),
    ("FLARESOLVERR_MAX_REQUESTS_PER_HOUR", "Required local hourly cap for Elsevier browser fallback and Wiley/Science/PNAS requests."),
    ("FLARESOLVERR_MAX_REQUESTS_PER_DAY", "Required local daily cap for Elsevier browser fallback and Wiley/Science/PNAS requests."),
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
    lines.append("- These fields appear in both MCP `structuredContent` and CLI stderr JSON.")
    lines.append("- MCP error payloads may also include `missing_env=[...]` when credentials or required env vars are known.")
    lines.append("- CLI exit codes remain `ambiguous=2`, `no_access=3`, `rate_limited=4`.")
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
        "Defaults: modes=['article','markdown'], strategy.asset_profile='none', "
        "strategy.allow_html_fallback=true, strategy.allow_metadata_only_fallback=true, "
        "include_refs=null, max_tokens='full_text'. In full_text mode include_refs=null "
        "behaves like 'all'. When asset_profile is body/all, optional "
        "strategy.inline_image_budget can tune the default inline ImageContent caps of "
        "3 figures, 2 MiB each, and 8 MiB total. `provider_hint` and "
        "`preferred_providers` may include `elsevier`, `wiley`, `science`, or `pnas`. "
        "`elsevier` keeps an official XML/API route first and may then fall back to "
        "repo-local FlareSolverr HTML before degrading to metadata-only, publishing "
        "`elsevier_xml` or `elsevier_browser`. `springer` keeps a provider-managed direct HTML route "
        "with direct HTTP PDF fallback and publishes `springer_html`. `wiley` keeps "
        "the repo-local FlareSolverr HTML route, may then use the official Wiley "
        "TDM API PDF lane when `WILEY_TDM_CLIENT_TOKEN` is configured, and may still "
        "continue into seeded-browser publisher PDF/ePDF fallback while publishing "
        "`wiley_browser`. `science` "
        "and `pnas` require repo-local FlareSolverr plus "
        "explicit local rate-limit env vars and keep their existing public source names. "
        "Elsevier browser fallback plus Wiley/Science/PNAS currently return text-only "
        "markdown even when `asset_profile` is `body` or `all`, and Springer PDF "
        "fallback is also text-only in this version. "
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
        "Defaults: modes=['article','markdown'], strategy.asset_profile='none', "
        "strategy.allow_html_fallback=true, strategy.allow_metadata_only_fallback=true, "
        "include_refs=null, max_tokens='full_text', prefer_cache=false. Set "
        "prefer_cache=true to try a local cached FetchEnvelope sidecar before hitting the "
        "network. Use strategy.asset_profile='body' or 'all' to include local assets. "
        "With body/all profiles, key local figures may be returned as ImageContent "
        "alongside the JSON result; strategy.inline_image_budget can override the default "
        "caps of 3 figures, 2 MiB each, and 8 MiB total, and any resulting zero disables "
        "inline images. `elsevier` keeps an official XML/API route and may fall back to "
        "repo-local FlareSolverr HTML before degrading to metadata-only, publishing "
        "`elsevier_xml` or `elsevier_browser`. `springer` uses provider-managed direct HTML and direct "
        "HTTP PDF fallback while keeping public source `springer_html`. `wiley` keeps "
        "repo-local FlareSolverr HTML first, may then use the official Wiley TDM "
        "API PDF lane when `WILEY_TDM_CLIENT_TOKEN` is configured, and may still "
        "continue into seeded-browser publisher PDF/ePDF fallback while publishing "
        "source `wiley_browser` on success. `science` and `pnas` routes use "
        "provider-managed FlareSolverr HTML plus seeded-browser publisher PDF/ePDF repo-local "
        "workflows and keep their existing public source names. Elsevier browser "
        "fallback plus Wiley/Science/PNAS downgrade body/all requests to text-only "
        "with warnings, and Springer PDF fallback is also text-only in this version. Set "
        "download_dir to isolate task-local downloads; the MCP server can also surface "
        "scoped cache resources for that directory during the current session."
    )
