"""Canonical MCP and skill-facing instruction snippets."""

from __future__ import annotations

from ..provider_catalog import PROVIDER_CATALOG, SOURCE_PROVIDER_MAP, provider_names
from ..reason_codes import ERROR, NO_ACCESS, RATE_LIMITED

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
    ("ELSEVIER_API_KEY", "Required for official Elsevier full-text access."),
    (
        "WILEY_TDM_CLIENT_TOKEN",
        "Optional Wiley Text and Data Mining client token for the official Wiley PDF lane; browser PDF/ePDF fallback can still run without it when the local runtime is ready.",
    ),
    (
        "PAPER_FETCH_WILEY_STORAGE_STATE_JSON",
        "Optional Wiley browser storage-state JSON override; managed default uses provider-scoped storage-state, while external CDP mode uses the existing browser context state.",
    ),
    (
        "PAPER_FETCH_WILEY_PROFILE_DIR",
        "Optional Wiley profile override; managed default uses provider-scoped storage-state; use CLOAKBROWSER_PROFILE_DIR only to override the managed Chrome startup/storage-state directory or CLOAKBROWSER_CDP_ENDPOINT for an external browser.",
    ),
    (
        "CLOAKBROWSER_PROFILE_DIR",
        "Optional startup/storage-state directory for the managed CloakBrowser Chrome when CLOAKBROWSER_CDP_ENDPOINT is unset.",
    ),
    (
        "CLOAKBROWSER_BINARY_PATH",
        "Optional preinstalled Chrome/CloakBrowser binary path; cloakbrowser uses it instead of downloading Chromium.",
    ),
    (
        "CLOAKBROWSER_USER_DATA_DIR",
        "Optional fallback startup/storage-state directory for the managed CloakBrowser Chrome when CLOAKBROWSER_PROFILE_DIR is unset.",
    ),
    (
        "CLOAKBROWSER_CDP_ENDPOINT",
        "Optional Chrome DevTools Protocol endpoint for browser workflows; when set, the existing browser context state wins over new context options and browser-backed asset downloads are serialized; when unset, paper-fetch downloads/starts a managed CloakBrowser Chrome and reuses one keyed browser manager with isolated contexts/pages while keeping runtime-shared browser-backed asset downloads serialized.",
    ),
    (
        "CLOAKBROWSER_HEADLESS",
        "Optional headed/headless override for the managed CloakBrowser Chrome when CLOAKBROWSER_CDP_ENDPOINT is unset.",
    ),
    (
        "CLOAKBROWSER_TIMEOUT_MS",
        "Optional override for CloakBrowser per-request timeout. Defaults to 120000.",
    ),
    (
        "PAPER_FETCH_BROWSER_USER_AGENT",
        "Optional browser-only User-Agent override for managed Chromium/Playwright contexts; use a normal Chrome UA for AGU/Wiley Cloudflare challenge issues.",
    ),
    ("PAPER_FETCH_DOWNLOAD_DIR", "Overrides the default CLI/MCP download directory."),
    ("PAPER_FETCH_RUN_LIVE", "Test-only flag for live publisher integration checks."),
)

ERROR_CONTRACT: tuple[tuple[str, str], ...] = (
    ("ambiguous", "Contains `candidates`; prompt the user to choose and retry."),
    (
        NO_ACCESS,
        "Credentials or entitlements are missing; inspect `missing_env` when present, then retry.",
    ),
    (RATE_LIMITED, "Back off and retry later."),
    (ERROR, "Any other failure; inspect `reason`."),
)


def _backtick_join(values: tuple[str, ...] | list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values)


def _browser_runtime_provider_names() -> tuple[str, ...]:
    return tuple(
        spec.name
        for spec in sorted(PROVIDER_CATALOG.values(), key=lambda item: item.status_order)
        if spec.requires_browser_runtime
    )


def _preferred_provider_sentence() -> str:
    return (
        "`provider_hint` and `preferred_providers` accept the runtime provider catalog "
        f"({_backtick_join(provider_names())}). "
    )


def _browser_runtime_sentence() -> str:
    return (
        "Browser runtime providers are catalog-derived from "
        "`ProviderSpec.requires_browser_runtime=True` "
        f"({_backtick_join(_browser_runtime_provider_names())}). "
    )


def _public_source_sentence() -> str:
    source_pairs = tuple(
        f"`{source}`->`{provider}`"
        for source, provider in sorted(SOURCE_PROVIDER_MAP.items())
    )
    return (
        "Public article sources are catalog-derived from `SOURCE_PROVIDER_MAP`: "
        + ", ".join(source_pairs)
        + ". "
    )


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
        "include_refs=null, max_tokens='full_text', prefer_cache=false, no_download=false, artifact_mode='markdown-assets', "
        "save_markdown=false. In full_text mode include_refs=null "
        "behaves like 'all'. When asset_profile is body/all, optional "
        "strategy.inline_image_budget can tune the default inline ImageContent caps of "
        "3 figures, 2 MiB each, and 8 MiB total. "
        + _preferred_provider_sentence()
        + _browser_runtime_sentence()
        + _public_source_sentence()
        +
        "`elsevier` keeps an official XML route first and may then fall back to the "
        "official Elsevier API PDF lane before degrading to metadata-only, publishing "
        "`elsevier_xml` on XML success and `elsevier_pdf` on PDF fallback success. `springer` keeps a provider-managed direct HTML route "
        "with direct HTTP PDF fallback, publishing `springer_html` on HTML success and `springer_pdf` on PDF fallback success. `wiley` keeps "
        "the CDP browser HTML route, then CDP browser-seeded publisher PDF/ePDF "
        "fallback, and may still continue into the official Wiley TDM API PDF lane "
        "when `WILEY_TDM_CLIENT_TOKEN` is configured while publishing `wiley_browser`. `science`, "
        "`pnas`, `ams`, `annualreviews`, `acs`, `iop`, `aip`, and `mdpi` require the local browser runtime but no provider-specific local "
        "rate-limit env vars; AMS publishes `ams_html` or `ams_pdf` and ignores `citation_xml_url`; Annual Reviews publishes `annualreviews_html` or `annualreviews_pdf`; ACS publishes `acs`; IOP publishes `iop_html` or `iop_pdf` and rejects Radware/hCaptcha challenge pages; AIP publishes `aip_html` or `aip_pdf`; MDPI publishes `mdpi_html` or `mdpi_pdf` and does not use an XML route. `ieee` uses "
        "landing metadata, the Xplore dynamic HTML endpoint, and direct HTTP PDF fallback, "
        "publishing `ieee_html` or `ieee_pdf` when those routes return usable full text. `arxiv` uses "
        "arXiv ID-derived HTML first, optional API/HTML metadata merge, and PDF fallback while publishing "
        "`arxiv_html` or `arxiv_pdf`. `copernicus` uses "
        "direct landing HTML to discover public NLM/JATS XML, then falls back to PDF before metadata fallback, "
        "requires no browser runtime or provider credentials, and publishes `copernicus_xml` or `copernicus_pdf`. "
        "`royalsocietypublishing` uses direct DOI HTML with direct HTTP PDF fallback, publishing `royalsocietypublishing_html` or `royalsocietypublishing_pdf`. "
        "`plos` uses public JATS XML with direct HTTP PDF fallback, publishing `plos_xml` or `plos_pdf`. "
        "`frontiers` discovers canonical Frontiers article routes from landing HTML, then uses public JATS XML with direct HTTP PDF fallback, publishing `frontiers_xml` or `frontiers_pdf`. "
        "`oxfordacademic` uses direct HTTP article HTML with direct HTTP PDF fallback, publishing `oxfordacademic_html` or `oxfordacademic_pdf`. "
        "PDF fallback uses shared pymupdf4llm Markdown conversion and, when `asset_profile` is `body` or `all` "
        "and artifact saving is enabled, saves exported PDF images to `<doi>_assets/`. On successful HTML/XML routes, "
        "`asset_profile='none'` disables local asset downloads but does not remove "
        "remote image links already present in rendered Markdown. "
        "`asset_profile='body'` means provider-cleaned body figure/table/formula assets only, "
        "while `asset_profile='all'` additionally downloads supplementary files. "
        "Inline ImageContent still only comes from body figures. Wiley/Science/PNAS/AMS/Annual Reviews/ACS/IOP/AIP/MDPI support "
        "`asset_profile=body|all` on successful CDP browser HTML routes and "
        "prefer full-size/original figures before falling back to previews, while "
        "their PDF/ePDF fallback routes share the same PDF image export behavior. Springer, IEEE, arXiv, and Copernicus PDF fallback "
        "routes use the same shared PDF conversion path. "
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
        "include_refs=null, max_tokens='full_text', prefer_cache=false, no_download=false, artifact_mode='markdown-assets', "
        "save_markdown=false, markdown_output_dir=null, markdown_filename=null. Set "
        "prefer_cache=true to resolve the query to a DOI, then try a matching local cached "
        "FetchEnvelope sidecar before running the full fetch waterfall. Use artifact_mode='none' "
        "to disable provider artifacts and assets while keeping MCP fetch-envelope cache sidecars. Use "
        "no_download=true to avoid writing provider payloads, PDFs, HTML, assets, and "
        "fetch-envelope sidecars. Set save_markdown=true to write the rendered Markdown "
        "full text to disk; successful saves return saved_markdown_path, while "
        "metadata-only or abstract-only results add a warning and "
        "download:markdown_skipped_no_fulltext. Use strategy.asset_profile='none', "
        "'body', or 'all' to control local asset downloads; 'none' does not remove "
        "remote image links already present in rendered Markdown. "
        "With body/all profiles, key local figures may be returned as ImageContent "
        "alongside the JSON result; strategy.inline_image_budget can override the default "
        "caps of 3 figures, 2 MiB each, and 8 MiB total, and any resulting zero disables "
        "inline images. "
        + _preferred_provider_sentence()
        + _browser_runtime_sentence()
        + _public_source_sentence()
        +
        "`elsevier` keeps an official XML route and may fall back to "
        "the official Elsevier API PDF lane before degrading to metadata-only, publishing "
        "`elsevier_xml` on XML success and `elsevier_pdf` on PDF fallback success. `springer` uses provider-managed direct HTML and direct "
        "HTTP PDF fallback, publishing `springer_html` or `springer_pdf`. `wiley` keeps "
        "CDP browser HTML first, then CDP browser-seeded publisher PDF/ePDF "
        "fallback, and may still continue into the official Wiley TDM API PDF lane "
        "when `WILEY_TDM_CLIENT_TOKEN` is configured while publishing source "
        "`wiley_browser` on success. `science`, `pnas`, `ams`, `annualreviews`, `acs`, `iop`, `aip`, and `mdpi` routes use "
        "provider-managed browser runtime HTML plus seeded-browser publisher PDF/ePDF repo-local "
        "workflows; AMS publishes `ams_html` or `ams_pdf` and does not request `citation_xml_url` / `/doc/...xml`; Annual Reviews publishes `annualreviews_html` or `annualreviews_pdf`; ACS publishes `acs`; IOP publishes `iop_html` or `iop_pdf`, rejects Radware/hCaptcha challenge pages, and does not implement unauthenticated TDM XML/PDF; AIP publishes `aip_html` or `aip_pdf`; MDPI publishes `mdpi_html` or `mdpi_pdf` and does not use an XML route. `ieee` uses landing metadata, "
        "the Xplore dynamic HTML endpoint, and direct HTTP PDF fallback while publishing "
        "`ieee_html` or `ieee_pdf`. `arxiv` uses ID-derived official HTML first, optional API/HTML metadata merge, and PDF "
        "fallback while publishing `arxiv_html` or `arxiv_pdf`. `copernicus` uses direct HTTP landing discovery, public NLM/JATS XML, "
        "and PDF fallback before metadata fallback while publishing `copernicus_xml` or `copernicus_pdf`; it does not need browser runtime or credentials. "
        "`royalsocietypublishing` uses direct DOI HTML with direct HTTP PDF fallback while publishing `royalsocietypublishing_html` or `royalsocietypublishing_pdf`. "
        "`plos` uses public JATS XML with direct HTTP PDF fallback while publishing `plos_xml` or `plos_pdf`. "
        "`frontiers` discovers canonical Frontiers article routes from landing HTML, then uses public JATS XML with direct HTTP PDF fallback while publishing `frontiers_xml` or `frontiers_pdf`. "
        "`oxfordacademic` uses direct HTTP article HTML with direct HTTP PDF fallback while publishing `oxfordacademic_html` or `oxfordacademic_pdf`. PDF "
        "fallback saves exported PDF images for body/all requests when artifact saving is enabled. On successful HTML/XML routes, "
        "`asset_profile='none'` disables local asset downloads but keeps rendered "
        "remote Markdown image links when the provider can resolve them. "
        "`asset_profile='body'` means provider-cleaned body figure/table/formula assets only, "
        "while `asset_profile='all'` additionally downloads supplementary files; "
        "supplementary files are saved as assets but are not emitted as ImageContent. "
        "Wiley/Science/PNAS/AMS/Annual Reviews/ACS/IOP/AIP/MDPI support body/all assets on successful CDP browser HTML routes and share "
        "the PDF/ePDF fallback image export behavior with Springer/IEEE/arXiv/Copernicus. Set "
        "download_dir to isolate task-local downloads; the MCP server can also surface "
        "scoped cache resources for that directory during the current session."
    )
