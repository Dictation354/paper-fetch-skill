# Changelog

All notable public changes to `paper-fetch-skill` are documented in this file.

## 2026-04-16

### Added

- Added a public `provider_status()` MCP tool that reports stable local diagnostics for `crossref`, `elsevier`, `springer`, `wiley`, `science`, and `pnas` without probing remote publisher APIs.
- Added provider-level status probing with stable `ready` / `partial` / `not_configured` / `rate_limited` / `error` semantics plus per-provider `checks=[...]` details.

### Changed

- Changed all 8 public MCP tools to expose `ToolAnnotations`; read-only tools now advertise `readOnlyHint=true`, while `fetch_paper` stays writable because it may refresh local cache files.
- Changed Science / PNAS local diagnostics so MCP can inspect FlareSolverr runtime readiness and local rate-limit windows without mutating the rate-limit tracking file.

### Docs

- Updated README, deployment docs, provider docs, and the bundled skill guide to document `provider_status()` and the new MCP tool-annotation hints.

## 2026-04-15

### Added

- Added a dedicated `has_fulltext(query)` MCP probe tool with cheap Crossref, provider-metadata, and landing-page HTML-meta signals.
- Added JSON output schemas for all 7 public MCP tools so schema-aware clients can validate tool results and surface stronger autocomplete.
- Added `fetch_paper(..., prefer_cache=true)` cache-first short-circuiting backed by an MCP-local cached FetchEnvelope sidecar.
- Added `missing_env=[...]` on MCP error payloads when missing credentials or required environment variables can be identified.
- Added two MCP prompt templates, `summarize_paper(query, focus)` and `verify_citation_list(citations, mode)`, for cache-first paper summaries and batch-first citation-list triage.
- Added `token_estimate_breakdown={abstract,body,refs}` to `fetch_paper` results, `article.quality`, and `batch_check(mode="article")` item payloads.

### Changed

- Changed `batch_check(mode="metadata")` to reuse the cheap probe path instead of running the full fetch waterfall.
- Changed the bundled skill layout to a thin `SKILL.md` entrypoint plus `references/` docs for environment variables, CLI fallback, and failure handling.
- Changed `batch_resolve` and `batch_check` to accept optional `concurrency`, allowing cross-host overlap while the shared HTTP transport still serializes same-host requests.
- Changed long-running MCP `fetch_paper` and `batch_*` tool calls to observe cancellation cooperatively so cancelled requests stop issuing follow-up network work.
- Changed MCP cache resources so explicit non-default `download_dir` values also register scoped cache-index and cached-entry resources for the current server session.
- Changed MCP `fetch_paper.strategy` to accept optional `inline_image_budget` controls for inline `ImageContent` limits without changing service-layer fetch behavior or cache eligibility.
- Changed `token_estimate` semantics to remain backward compatible as `abstract + body`, while the new `refs` budget now lives only in `token_estimate_breakdown`.
- Changed MCP cached FetchEnvelope sidecar loading to backfill missing token-breakdown fields when reading older cache entries that predate the new contract.

### Docs

- Updated README, deployment docs, the skill guide, and the probe-semantics note to document the shipped `has_fulltext` v1 behavior and the new `batch_check(mode="metadata")` semantics.
- Updated the static skill installer and architecture docs to treat `skills/paper-fetch-skill/` as a runtime-agnostic bundle that can include on-demand `references/` files.
- Updated MCP-facing docs to describe the new `concurrency` parameter and the "cross-host concurrent, same-host serial" behavior of `batch_*`.
- Updated the MCP-facing docs and skill notes to describe cooperative cancellation for `fetch_paper` and `batch_*`.
- Updated README, deployment docs, and MCP instruction text to document scoped cache resources for explicit isolated download directories.
- Updated README, deployment docs, skill notes, and MCP instruction text to document `strategy.inline_image_budget` and its default `3 / 2 MiB / 8 MiB` inline-image caps.
- Updated README, deployment docs, and the bundled skill guide to document the two published MCP prompts and the new `token_estimate_breakdown` budgeting hint.

## 2026-04-14

### Added

- Added public `science` and `pnas` provider routes, including direct `provider_hint`, `preferred_providers`, and final `source` support.
- Added repo-local Science / PNAS provider implementations in [`src/paper_fetch/providers/science.py`](src/paper_fetch/providers/science.py) and [`src/paper_fetch/providers/pnas.py`](src/paper_fetch/providers/pnas.py), backed by shared FlareSolverr, HTML cleanup, and Playwright PDF-fallback helpers.
- Added repo-local `vendor/flaresolverr/` workflow assets, thin wrapper scripts under [`scripts/`](scripts), and a dedicated operator guide in [`docs/flaresolverr.md`](docs/flaresolverr.md).
- Added offline Science / PNAS fixtures plus unit coverage for routing, FlareSolverr error handling, provider fallbacks, and public result provenance.
- Added opt-in live smoke coverage for one Science HTML DOI and one PNAS PDF-fallback DOI behind the existing `PAPER_FETCH_RUN_LIVE=1` gate.

### Changed

- Extended `SourceKind` and the service provider registry so `science` and `pnas` are first-class public provenance values instead of envelope-only aliases.
- Made Science / PNAS use a provider-managed `HTML first -> PDF fallback -> metadata-only fallback` chain, while explicitly skipping the generic `html_generic` fallback after those providers are selected.
- Moved Science / PNAS HTML extraction onto provider-specific cleanup rules, then fed the cleaned HTML back through the existing HTML-to-Markdown pipeline for final rendering.
- Added explicit repo-local runtime checks for `vendor/flaresolverr`, `FLARESOLVERR_ENV_FILE`, local FlareSolverr health, and required local rate-limit settings before Science / PNAS full-text retrieval proceeds.
- Added local Science / PNAS rate-limit accounting in the user data directory and kept `asset_profile=body|all` on those routes as text-only downgrades with warnings instead of hard failures.
- Expanded `install-formula-tools.sh` so repo-local development can bootstrap FlareSolverr source setup, Playwright Chromium, and headless `Xvfb` prerequisites from one entrypoint.

### Docs

- Updated README, deployment guidance, provider docs, MCP instruction snippets, and FlareSolverr workflow docs to describe the new Science / PNAS route, repo-local-only support boundary, required environment variables, and operator-owned ToS risk.

### Validation

- `python3 -m compileall src/paper_fetch`
- `ruff check src/paper_fetch tests/unit`
- `PYTHONPATH=src python3 -m unittest -q tests.unit.test_publisher_identity tests.unit.test_resolve_query tests.unit.test_science_pnas_html tests.unit.test_science_pnas_flaresolverr tests.unit.test_science_pnas_provider tests.unit.test_service`

## 2026-04-13

### Added

- Added MCP cache indexing with `list_cached()` / `get_cached()` plus `resource://paper-fetch/cache-index` and `resource://paper-fetch/cached/{entry_id}` resources for the default shared download directory.
- Added `batch_resolve(queries)` and `batch_check(queries, mode)` MCP tools so citation-list workflows can stay serial, transport-reusing, and context-light.
- Added canonical MCP/skill-facing instruction helpers in [`src/paper_fetch/mcp/_instructions.py`](src/paper_fetch/mcp/_instructions.py) to keep defaults, environment notes, and error-contract wording aligned.
- Added inline `ImageContent` support for a few local body figures when `strategy.asset_profile` is `body` or `all`.
- Added structured MCP progress updates and structured log notifications for `fetch_paper`, `batch_check`, and `batch_resolve`.
- Added live MCP end-to-end smoke coverage for representative Elsevier and HTML-fallback flows.
- Added a probe-semantics design note in [`docs/architecture/probe-semantics.md`](docs/architecture/probe-semantics.md) to define the future `has_fulltext(query)` direction.

### Changed

- Moved public change history and shipped-surface notes out of ad hoc backlog docs into this changelog.
- Exposed `download_dir` on the MCP `fetch_paper` surface so task-local directories can override `PAPER_FETCH_DOWNLOAD_DIR` and XDG defaults.
- Expanded MCP `resolve_paper` to accept either a raw `query` or structured `title` plus optional `authors` / `year`.
- Updated the static skill to document the real defaults, the environment variables that affect behavior, the error contract, cache-first call discipline, and the batch-first bibliography workflow.
- Clarified that `include_refs=null` behaves like `all` for `max_tokens="full_text"` and like `top10` for numeric token budgets.
- Reworked the skill frontmatter into a shorter trigger-style description and moved call-discipline guidance ahead of the main workflow.
- Shifted provider routing toward Crossref/domain-first hints with DOI-prefix fallback only when needed, and added route diagnostics to `source_trail`.
- Unified text-normalization, DOI extraction, metadata merge helpers, and HTML lookup heuristics around shared utilities to reduce duplicate logic.
- Split large renderer and HTML modules into thinner facades backed by focused helpers while preserving public compatibility entrypoints.
- Refined CLI exit codes, Markdown asset-link handling, render budgeting, and token-estimation internals without changing the public fetch contract.

### Fixed

- Protected in-process HTTP GET caching with `threading.RLock`.
- Switched the HTTP transport to `urllib3.PoolManager` for connection reuse without changing the public request contract.
- Added response-size guards, gzip pre-decompression size checks, cache-budget eviction, and safer retry behavior for timeout/transient errors.
- Converted payload and asset writes to atomic `.part -> replace` flows so failed writes do not corrupt final files.
- Tightened exception handling so programming errors are no longer silently downgraded into partial-download or fallback paths.
- Prevented `batch_check()` from writing payloads to disk by forcing `download_dir=None`.
- Preserved top-level fetch provenance fields even when `article`, `markdown`, or `metadata` are unrequested and therefore returned as `null`.

### Docs

- Kept architecture rationale in [`docs/architecture/target-architecture.md`](docs/architecture/target-architecture.md) and moved shipped changes to this file.
- Updated deployment, provider, MCP, and skill-facing documentation to match the landed MCP surface and environment behavior.

### Validation

- `ruff check .`
- `python -m pytest tests/unit tests/integration -q`
- `python -m pytest tests/live/test_live_mcp.py -q` skips cleanly when live env is not enabled

### Follow-up

- The dedicated MCP probe tool `has_fulltext(query)` is intentionally not shipped yet; only its semantics note is landed in [`docs/architecture/probe-semantics.md`](docs/architecture/probe-semantics.md).
