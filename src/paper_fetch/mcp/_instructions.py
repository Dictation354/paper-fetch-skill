"""Canonical MCP and skill-facing instruction snippets."""

from __future__ import annotations

from ..reason_codes import ERROR, NO_ACCESS, RATE_LIMITED
from .provider_catalog import PROVIDER_CATALOG_RESOURCE_URI

DEFAULT_FETCH_VALUES: tuple[tuple[str, str], ...] = (
    ("target", '"paper"'),
    ("preset", '"temporary_read"'),
    ("modes", '["markdown"]'),
    ("strategy.asset_profile", '"none"'),
    ("strategy.allow_metadata_only_fallback", "true"),
    ("include_refs", '"all"'),
    ("max_tokens", '"full_text"'),
    ("prefer_cache", "false"),
    ("no_download", "true"),
    ("artifact_mode", '"none"'),
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
        "Resolve, inspect, cache, or fetch known papers by DOI, URL, or title. "
        "Resolve ambiguous identities before fetching. Honor explicit user files/sources; "
        "otherwise reuse valid session content handles, then qualified local text. "
        "fetch_paper and batch_fetch share preset=temporary_read (default), cacheable_read, archive. "
        "Presets expand before explicit options, including nested strategy overrides and false values. "
        "temporary_read returns a Markdown handle without paper, asset, or cache writes. "
        "cacheable_read reuses/writes request-matching cache in an explicit or configured scope. "
        "archive saves Markdown and reports actual file snapshots; body assets default to none. "
        "archive may use markdown_output_dir as its scope. Required paths must be supplied. "
        "Tools return schema_version=3 business payloads only in structuredContent. "
        "Use content_ref and read_content with next_offset (Unicode code points), including after saving. "
        "Multiple papers use batch_fetch; same-execution aliases share handles. Request article explicitly. "
        "read_content is local and read-only; expired handles never refetch. "
        "Fetch defaults use full text, all references, metadata fallback and no body assets. "
        "Explicit body/all assets enable downloads and Markdown assets unless explicitly overridden. "
        "batch_results alone opts into batch JSONL. Fetch tools may access remote services and "
        "write explicitly selected cache/artifacts/outputs. Saved files appear in output_artifacts. "
        "target=supplementary discovers materials independently; archive downloads attachments and saves an index. "
        "batch_check(mode=metadata) only probes availability, including for one query. "
        "Judge acquisition by acceptance, returned text by pagination/truncation facts, and reading "
        "completion by portions actually consumed. provider_status is static; browser_preflight "
        "is live and shares the native publisher profile with auth and fetch. Runtime preparation "
        f"is on demand; selected platform engine facts are at {PROVIDER_CATALOG_RESOURCE_URI}. "
        "Do not bypass access controls or manual-auth boundaries."
    )


def fetch_tool_description() -> str:
    return (
        "Fetch a known paper with a paged Markdown handle, metadata and acceptance. "
        "preset=temporary_read is the default and writes no paper artifacts/cache. "
        "cacheable_read reuses and writes cache in download_dir or a configured scope. "
        "archive saves Markdown to markdown_output_dir or download_dir, returning actual output_artifacts. "
        "All presets default to full_text, all references, metadata fallback and asset_profile=none. "
        "Explicit options override preset defaults; body/all assets enable downloads and "
        "artifact_mode=markdown-assets unless those fields were explicitly supplied. "
        "Body content is always in content_ref/read_content, also when saving. "
        "Explicit body/all assets may add bounded ImageContent. target=supplementary retrieves "
        "materials without fetching the body; archive downloads attachments and saves a material index. "
        "Missing required paths are argument errors. Runtime preparation is independent of paper writes. "
        f"Provider and selected platform engine facts are at {PROVIDER_CATALOG_RESOURCE_URI}."
    )
