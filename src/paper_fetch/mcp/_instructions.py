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
        "Known papers only: DOI, URL or title; resolve ambiguity before fetching. "
        "Honor user files/sources, then valid session handles, then qualified local text. "
        "Use batch_fetch for multiple papers. Shared fetch presets: temporary_read (default) "
        "returns Markdown handles without paper/asset/cache writes; cacheable_read reuses/writes "
        "request-matching cache in download_dir or configured scope; archive saves Markdown in "
        "markdown_output_dir or download_dir, plus attachments/index for target=supplementary. "
        "Required paths must be supplied. Explicit options, including nested strategy fields and "
        "false values, override presets. Defaults: full_text, all references, metadata fallback, "
        "no body assets. body/all assets enable downloads and artifact_mode=markdown-assets "
        "unless explicitly overridden; they may add bounded ImageContent. Runtime preparation "
        "is independent of paper writes and on demand. Business payloads: schema_version=3 "
        "only in structuredContent; request article explicitly. Saved files appear in output_artifacts; "
        "body content stays in content_ref/read_content. Judge acquisition by acceptance, text by "
        "pagination/truncation, reading completion by consumed portions. Provider/platform facts: "
        f"{PROVIDER_CATALOG_RESOURCE_URI}. Respect access controls and manual-auth boundaries."
    )


def fetch_tool_description() -> str:
    return (
        "Fetch one known paper, or materials only with target=supplementary. Returns metadata, "
        "acceptance and content_ref for read_content, also after saving. Shared presets control "
        "cache/files; temporary_read writes neither."
    )
