"""Canonical MCP and skill-facing instruction snippets."""

from __future__ import annotations

DEFAULT_FETCH_VALUES: tuple[tuple[str, str], ...] = (
    ("modes", '["article", "markdown"]'),
    ("strategy.asset_profile", '"none"'),
    ("strategy.allow_html_fallback", "true"),
    ("strategy.allow_metadata_only_fallback", "true"),
    ("include_refs", "null"),
    ("max_tokens", '"full_text"'),
)

DEFAULT_FETCH_NOTES: tuple[str, ...] = (
    "`include_refs=null` behaves like `all` when `max_tokens=\"full_text\"`.",
    "When `max_tokens` is a positive integer, `include_refs=null` behaves like `top10`.",
)

SKILL_ENVIRONMENT_VARIABLES: tuple[tuple[str, str], ...] = (
    ("ELSEVIER_API_KEY", "Required for official Elsevier full-text access."),
    ("ELSEVIER_INSTTOKEN", "Optional institution token for Elsevier entitlement."),
    ("SPRINGER_META_API_KEY", "Enables Springer Meta API metadata lookups."),
    ("SPRINGER_OPENACCESS_API_KEY", "Enables Springer Open Access full-text fallback."),
    ("SPRINGER_FULLTEXT_API_KEY", "Enables Springer Full Text API when paired with its URL template."),
    ("FLARESOLVERR_URL", "Optional override for the local Science/PNAS FlareSolverr endpoint; defaults to http://127.0.0.1:8191/v1."),
    ("FLARESOLVERR_ENV_FILE", "Required for Science/PNAS; points at a repo-local vendor/flaresolverr preset file."),
    ("FLARESOLVERR_SOURCE_DIR", "Optional override for the repo-local vendor/flaresolverr directory."),
    ("FLARESOLVERR_MIN_INTERVAL_SECONDS", "Required local minimum spacing between Science/PNAS requests."),
    ("FLARESOLVERR_MAX_REQUESTS_PER_HOUR", "Required local hourly cap for Science/PNAS requests."),
    ("FLARESOLVERR_MAX_REQUESTS_PER_DAY", "Required local daily cap for Science/PNAS requests."),
    ("PAPER_FETCH_DOWNLOAD_DIR", "Overrides the default CLI/MCP download directory."),
    ("PAPER_FETCH_RUN_LIVE", "Test-only flag for live publisher integration checks."),
)

ERROR_CONTRACT: tuple[tuple[str, str], ...] = (
    ("ambiguous", "Contains `candidates`; prompt the user to choose and retry."),
    ("no_access", "Credentials or entitlements are missing; check env and retry."),
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
    lines.append("- CLI exit codes remain `ambiguous=2`, `no_access=3`, `rate_limited=4`.")
    return "\n".join(lines)


def server_instructions() -> str:
    return (
        "Resolve or fetch a specific paper by DOI, landing URL, or title query. "
        "Use resolve_paper when the query may be ambiguous; it accepts either a raw query or "
        "structured title/authors/year fields. Use fetch_paper when you need "
        "structured article metadata, AI-friendly markdown, or both. "
        "Defaults: modes=['article','markdown'], strategy.asset_profile='none', "
        "strategy.allow_html_fallback=true, strategy.allow_metadata_only_fallback=true, "
        "include_refs=null, max_tokens='full_text'. In full_text mode include_refs=null "
        "behaves like 'all'. `provider_hint`, `preferred_providers`, and final `source` may "
        "also be `science` or `pnas`; those routes require repo-local FlareSolverr plus "
        "explicit local rate-limit env vars, and currently return text-only markdown even "
        "when `asset_profile` is `body` or `all`. On supporting clients, fetch_paper and "
        "batch tools also emit progress updates and structured log notifications."
    )


def fetch_tool_description() -> str:
    return (
        "Fetch AI-friendly paper content. Returns a fixed FetchEnvelope-style object with "
        "top-level provenance and optional article/markdown/metadata payloads. "
        "Defaults: modes=['article','markdown'], strategy.asset_profile='none', "
        "strategy.allow_html_fallback=true, strategy.allow_metadata_only_fallback=true, "
        "include_refs=null, max_tokens='full_text'. Use strategy.asset_profile='body' or "
        "'all' to include local assets. With body/all profiles, key local figures may be "
        "returned as ImageContent alongside the JSON result. `science` and `pnas` routes use "
        "a provider-managed HTML-first, PDF-second repo-local workflow and downgrade "
        "body/all requests to text-only with warnings. Set download_dir to isolate "
        "task-local downloads."
    )
