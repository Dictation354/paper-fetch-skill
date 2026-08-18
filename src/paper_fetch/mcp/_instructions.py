"""Canonical MCP and skill-facing instruction snippets."""

from __future__ import annotations

from ..reason_codes import ERROR, NO_ACCESS, RATE_LIMITED
from .provider_catalog import PROVIDER_CATALOG_RESOURCE_URI

DEFAULT_FETCH_VALUES: tuple[tuple[str, str], ...] = (
    ("modes", '["article", "markdown"]'),
    ("strategy.asset_profile", "null (provider default)"),
    ("strategy.allow_metadata_only_fallback", "true"),
    ("include_refs", "null"),
    ("max_tokens", '"full_text"'),
    ("prefer_cache", "false"),
    ("no_download", "false"),
    ("artifact_mode", '"markdown-assets"'),
    ("save_markdown", "false"),
    ("markdown_output_dir", "null"),
    ("markdown_filename", "null"),
)

DEFAULT_FETCH_NOTES: tuple[str, ...] = (
    '`include_refs=null` behaves like `all` when `max_tokens="full_text"`.',
    "When `max_tokens` is a positive integer, `include_refs=null` behaves like `top10`.",
)

SKILL_ENVIRONMENT_VARIABLES: tuple[tuple[str, str], ...] = (
    (
        "PAPER_FETCH_BROWSER_BACKEND",
        "Selects the Camoufox browser backend; any other value is rejected.",
    ),
    (
        "PAPER_FETCH_BROWSER_HEADLESS",
        "Generic headed/headless setting for the selected managed browser backend.",
    ),
    (
        "PAPER_FETCH_BROWSER_BINARY_PATH",
        "Optional executable override for the selected browser backend.",
    ),
    (
        "PAPER_FETCH_BROWSER_PROFILE_DIR",
        "Optional provider storage/profile directory override for the selected backend.",
    ),
    (
        "PAPER_FETCH_BROWSER_USER_DATA_DIR",
        "Optional fallback provider storage/profile directory override for the selected backend.",
    ),
    (
        "PAPER_FETCH_BROWSER_TIMEOUT_MS",
        "Generic browser navigation timeout in milliseconds. Defaults to 120000.",
    ),
    ("ELSEVIER_API_KEY", "Required for official Elsevier full-text access."),
    (
        "WILEY_TDM_CLIENT_TOKEN",
        "Optional Wiley Text and Data Mining client token for the official Wiley PDF lane; browser PDF/ePDF fallback can still run without it when the local runtime is ready.",
    ),
    (
        "PAPER_FETCH_WILEY_STORAGE_STATE_JSON",
        "Optional Wiley browser storage-state JSON override; the managed default uses provider-scoped storage-state.",
    ),
    (
        "PAPER_FETCH_WILEY_PROFILE_DIR",
        "Optional Wiley profile override for provider-scoped storage state.",
    ),
    (
        "PAPER_FETCH_BROWSER_USER_AGENT",
        "Optional publisher direct-request User-Agent override. Camoufox ignores it to preserve a consistent generated Firefox fingerprint.",
    ),
    ("PAPER_FETCH_DOWNLOAD_DIR", "Overrides the default CLI/MCP download directory."),
    ("PAPER_FETCH_RUN_LIVE", "Test-only flag for live publisher integration checks."),
)

ERROR_CONTRACT: tuple[tuple[str, str], ...] = (
    ("ambiguous", "Contains `candidates`; prompt the user to choose and retry."),
    (
        NO_ACCESS,
        "Credentials or entitlements are missing; retry only after auth or entitlement state changes.",
    ),
    (RATE_LIMITED, "Back off and retry later."),
    (ERROR, "Any other failure; inspect `reason`."),
)


def server_instructions() -> str:
    return (
        "Resolve, inspect, cache, or fetch papers by DOI, landing URL, or title. Resolve "
        "ambiguous identities before fetching; use compact request-sensitive cache checks "
        "before network work. Tool payloads have schema_version=2 and structured errors. "
        "fetch_paper defaults to article+markdown, provider-default assets, metadata-only "
        "fallback enabled, full text, cache preference off, downloads on, and "
        "artifact_mode=markdown-assets. Fetch and batch calls may access remote services; "
        "fetch_paper and batch_fetch may write provider artifacts/cache or explicit outputs, "
        "while browser_preflight may open publisher pages and save filtered storage-state. "
        "Managed Camoufox preparation is disabled by default for MCP; set "
        "browser_auto_prepare=true on a browser-triggering request, or configure the "
        "matching environment policy, to permit installation, repair, or update. "
        "provider_status is local/static; "
        "browser_preflight is live and never performs PDF fallback or automatic auth. Do not "
        "bypass login, challenge, paywall, or entitlement boundaries. Read current provider, "
        f"source, runtime, preflight, and asset-default facts from {PROVIDER_CATALOG_RESOURCE_URI}. "
        "summarize_paper and verify_citation_list are prompt templates. Supporting clients "
        "receive progress/log updates for fetch, browser preflight, and batch work."
    )


def fetch_tool_description() -> str:
    return (
        "Fetch one paper as structured article, Markdown, and/or metadata with provenance, "
        "quality, trace, and token estimates. Defaults are modes=article+markdown, "
        "provider-default assets, metadata-only fallback enabled, include_refs=null, "
        "max_tokens=full_text, prefer_cache=false, no_download=false, "
        "artifact_mode=markdown-assets, save_markdown=false, and "
        "browser_auto_prepare=null (MCP default disabled). The call may access remote "
        "services and write provider artifacts, assets, and an MCP cache sidecar. "
        "no_download=true suppresses those writes; save_markdown=true is an explicit separate "
        "write and returns a path instead of inline full text. artifact_mode=none suppresses "
        "provider artifacts but retains MCP cache semantics. asset_profile=none|body|all "
        "controls local assets; body/all may return bounded ImageContent. Use prefer_cache=true "
        "only with matching request semantics. Current provider/source/runtime/asset-default "
        f"facts are at {PROVIDER_CATALOG_RESOURCE_URI}. Access controls and manual-auth "
        "boundaries are never bypassed."
    )
