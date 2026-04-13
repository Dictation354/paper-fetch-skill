# Changelog

All notable public changes to `paper-fetch-skill` are documented in this file.

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
