# Changelog

All notable public changes to `paper-fetch-skill` are documented in this file.

## Unreleased

<!-- SCAFFOLD: changelog-unreleased -->

## 4.0.0 - 2026-07-26

### Breaking

- Removed the deprecated CloakBrowser backend and all `CLOAKBROWSER_*` compatibility settings. Camoufox is now the only supported browser backend.
- Made the default installation a lightweight core. Browser extraction and PDF conversion now require the `browser`, `pdf`, or `full` extra.

### Changed

- Added branch-aware global and risk-focused coverage reporting, full-package typing, isolated unit-test runtime state, bounded cookie-aware downloads, and hardened XML parsing.
- Consolidated project version metadata around `pyproject.toml`, adopted SPDX license metadata, and expanded release and supply-chain metadata.

### Fixed

- Stabilized shared PDF Markdown structure under `pymupdf4llm` 1.28.0 by repairing deterministic heading drift without provider- or DOI-specific rules.
- Deduplicated Royal Society Silverchair figures across `view-large` and CDN URL variants while preserving the preferred full-size URL, preview URL, label, and caption.
- Refreshed and agent-reviewed all 26 affected golden snapshots after removing duplicate HTML title sections and applying the PDF and Royal Society fixes.

## 3.2.1 - 2026-07-25

### Changed

- Updated all GitHub Actions Python setup steps from `actions/setup-python@v6` to `actions/setup-python@v7`.
- Expanded the deprecated CloakBrowser compatibility range from `>=0.4,<0.5` to `>=0.4,<0.6`, covering the 0.5.x Python wrapper while keeping Camoufox as the sole default browser backend.
- Upgraded KaTeX from `0.17.0` to `0.18.1` and synchronized the root and bundled formula-tool manifests and lockfiles.

## 3.2.0 - 2026-07-22

### Added

- Added browser-neutral runtime context/session contracts for native Firefox/Juggler Camoufox and deprecated CloakBrowser, with provider-scoped state and a formal backend guide.
- Added direct-first selected-browser recovery across IEEE landing, REST HTML, PDF, figure/table/formula assets, multimedia discovery, and supplementary files; recovery is limited to eligible authentication, HTML-challenge, and network failures.
- Added a daily `dependency-latest` rolling prerelease that resolves the full direct/transitive Python runtime dependency matrix from the latest stable `v*` release, rebuilds all nine offline installers only when the source or resolved wheel set changes, and supports an explicit `force_refresh` recovery run.
- Added dependency snapshot tooling and contracts for per-target wheel inventories, deterministic cross-platform manifests, dependency-set comparison, and pre-build wheel filename/SHA256 verification.

### Changed

- Made Camoufox the sole default browser backend. CloakBrowser remains available throughout 3.x only when explicitly selected, emits a one-time `FutureWarning`, and may be removed in 4.0.0; legacy `CLOAKBROWSER_*` variables no longer select it implicitly.
- Kept backend selection strict with no automatic cross-backend fallback, required every runtime config to carry its backend, and separated Camoufox/CloakBrowser profile state.
- Constrained Playwright to `<1.61` for the supported `camoufox>=0.5.4,<0.6` combination, reused one thread-affine Camoufox process per runtime context, and optimized full HTML navigation around `commit` plus provider DOM readiness without global image/font/style blocking.
- Reused the existing Linux, macOS, and Windows offline build jobs for rolling updates with frozen wheelhouses; publishing retargets the fixed prerelease, replaces and verifies its exact installer/manifest/checksum asset set, and treats incomplete or invalid prior assets as a rebuild trigger without changing the stable latest release.

### Fixed

- Fixed IEEE large/preview media duplication so each normalized inline asset renders once, and distinguished partial asset downloads from batches where every asset failed.
- Fixed rolling offline builds failing before packaging when clean `setup-python` environments lacked the resolver-only `packaging` dependency; `merge`, `compare`, and pre-build `verify` now remain standard-library bootstrap paths.
- Fixed rolling prerelease publication against an older stable source commit by using a repository-scoped `ROLLING_RELEASE_TOKEN` for tag and Release mutations while keeping the built-in job token read-only.
- Fixed trailing commas in Windows offline-installer environment arrays that caused PowerShell parser errors before packaging began, with a static regression contract covering all three release scripts.
- Fixed stable release publication being skipped by GitHub's implicit `success()` status check when the dependency chain contained intentionally skipped refresh jobs; the release condition now always evaluates and explicitly requires every direct quality gate and offline build to succeed.

## 3.1.3 - 2026-07-15

### Added

- Added stable browser lifecycle failure codes for managed Chrome profile, startup, CDP, context, and page stages, with bounded redacted stderr diagnostics propagated through browser preflight, provider traces, fallback payloads, CLI manifests, and agent guidance.

### Changed

- Changed CLI and MCP batch execution to retain one shared browser manager across item gaps and use cooperative cancellation with a grace period, one-time browser shutdown escalation, and first/second Ctrl-C handling in the CLI.
- Expanded the macOS offline browser smoke and unit contracts to cover conservative stale-profile recovery, four-worker/50-context reuse, cancellation convergence, diagnostic redaction, and fallback provenance.

### Fixed

- Fixed managed Chrome profile reuse after abnormal exits by validating singleton ownership, host, PID/profile, and socket state; only proven-stale links are archived with recovery metadata, and a failed launch is retried at most once after a newly stale set is recovered.
- Fixed browser/PDF and metadata fallbacks so precise HTML/browser failure traces survive a successful fallback and keep acceptance degraded; browser runtime failures now direct users to repair local runtime state instead of incorrectly suggesting publisher authentication.

## 3.1.2 - 2026-07-14

### Changed

- Changed HTML full-text acceptance to require a trusted article/body container scope plus substantive body evidence, preserved the original scope through synthetic `<article>` normalization, and raised `EXTRACTION_REVISION` to 3 so stale false-positive sidecars are refetched.
- Added a focused offline CI gate and a real Annual Reviews empty-shell replay for shared availability, provider fallback, and block-corpus regressions.

### Fixed

- Fixed landing pages with empty full-text markers and large Most Read, Most Cited, Recommended, or Related modules being promoted to full text solely by page text volume.
- Fixed Annual Reviews empty landing shells so they fail HTML quality assessment and continue through the existing PDF fallback; retained Wiley abstract datalayer blocking for `10.1002/joc.3370130706`.

## 3.1.1 - 2026-07-14

### Added

- Added bounded IOP supplementary expansion for `asset_profile=all`, resolving same-DOI `/data` indexes to `SM`-numbered attachments with browser cookie/Referer reuse.
- Added a focused CI contract gate for IOP supplementary extraction, explicit asset Referer forwarding, signed-URL redaction, and browser challenge regression coverage.

### Fixed

- Fixed IOP supplementary discovery so `/data` index HTML, figure download controls, QR images, mismatched parent DOIs, blocked indexes, and empty scopes cannot be accepted as supplementary files; unresolved declared indexes now surface structured asset failures.
- Fixed browser-backed supplementary file requests to forward their explicit Referer and redact AWS `X-Amz-*`, `Signature`, and `AWSAccessKeyId` query values from cache keys and retained asset diagnostics.

## 3.1.0 - 2026-07-13

### Added

- Added canonical asset acceptance and manifest-v2 records across CLI, MCP, cache, and durable batch runs, including deterministic output hashes, audit/reconcile/resume support, bounded concurrent execution, cancellation, and rate-limit stop semantics.
- Added network-free provider/runtime diagnostics, browser preflight and provider catalog MCP resources/tools, compact cache inspection, and the structured `batch_fetch` MCP tool with explicit persistence and resume modes.
- Added machine-readable installation provenance to `paper-fetch doctor --json`, covering source and distribution versions, the default User-Agent, PATH entrypoint, offline target/revision/build metadata, installed runtime metadata, and all three host skill copies.

### Changed

- Changed the static skill into a thin, self-contained workflow entrypoint with dedicated workflow, presets, acceptance, CLI, environment, tool-contract, and failure-handling references whose links are parser-validated in source, staging, and installer copies.
- Changed offline manifest schema to version 3 so Linux, macOS, and Windows bundles carry the complete skill file list and a SHA256 for every file; installers now reject missing, extra, symlinked, or hash-drifted skill content before and after host installation.
- Prepared the backward-compatible feature set as the SemVer minor release `3.1.0`, synchronizing package metadata, the stable tool User-Agent, Windows installer fallback version, deployment guidance, and both changelogs.
- Added a lightweight cross-CLI/MCP/cache/manifest CI contract gate; package smoke now builds outside the checkout and verifies version consistency, every console script, MCP EOF, and static installation provenance while keeping live/offline heavy jobs opt-in.

### Fixed

- Fixed version ambiguity that could leave source, installed distribution metadata, and the PATH CLI at different releases without exposing their concrete paths; source development without an offline manifest is now reported as not applicable instead of an installation failure.

## 3.0.1 - 2026-07-04

### Changed

- Changed the built-in Wiley and Science samples used by `paper-fetch browser-preflight` and `paper-fetch auth` to lighter full-text pages already covered by fixtures, reducing slow parsing time in the default browser preflight.
- Added a built-in Royal Society Publishing sample for `paper-fetch browser-preflight` and `paper-fetch auth royalsocietypublishing`, so the default browser preflight now covers that browser-backed provider.
- Removed the full GitHub Actions unit/devtools/coverage job from the default CI gate; local `scripts/dev-preflight.sh` still runs the complete unit, devtools, and optional coverage checks.
- Refreshed user and agent documentation: restored the README showcase and example screenshots while keeping the quick-start path compact, corrected AMS direct-HTTP/browser-runtime wording, aligned CLI `--output-dir` filename descriptions with paper-stem output naming, and replaced completed-provider onboarding examples with placeholder provider examples.

## 3.0.0 - 2026-07-03

### Changed

- Changed browser-backed providers to use the public `browser_runtime` backend facade, centralizing CloakBrowser storage/profile path resolution, storage-state locking, and atomic storage-state writes across auth, preflight, HTML fetch, and seeded PDF fallback.
- Changed external CDP handling to report borrowed-context diagnostics and support `PAPER_FETCH_CDP_EXTERNAL_NEW_CONTEXT=1` for creating a fresh context in an existing browser.
- Changed browser-backed asset downloads to reuse a scoped thread-local page/context during safe caller-thread attempts, with automatic fallback to per-call close on Playwright thread-ownership errors.
- Changed browser image fetches to use a single per-image wall-clock budget across seed warming, page fetch, request-context fetch, direct navigation, and image wait; PDF fallback browser seeding now uses a lightweight warm path and skips duplicate seed navigation when cookies were already collected.
- Changed local conversion paths to cache Ghostscript/libvips candidate and `--version` probes, keep existing formula result/worker reuse under subprocess-call tests, and reuse no-image PDF Markdown rendering by PDF hash with byte/page guards and render diagnostics.
- Added cooperative cancellation checks to browser HTML, seeded PDF fallback, browser asset retry, and browser preflight loops.
- Changed `paper-fetch browser-preflight` to reuse each browser-backed provider's normal HTML candidates and HTML bootstrap retry semantics for built-in samples while still skipping PDF fallback.
- Removed the PNAS fast browser HTML preflight special case; PNAS now uses the standard browser workflow HTML bootstrap before seeded PDF fallback.
- Changed AMS to a no-browser direct HTTP HTML provider with direct HTTP PDF fallback, publishing `ams_html` or `ams_pdf` while still skipping browser auth/preflight/status and seeded-browser PDF fallback.
- Changed CI offline package jobs to run only on `v*` tag pushes or manual dispatch, leaving ordinary push/PR runs to the regular quality gates.
- Changed quality gates to expand mypy coverage to runtime/config/quality/PDF fallback/browser-runtime/formula core paths, configure mypy with `no_site_packages`, enforce a unit coverage baseline of 40 in CI and local coverage preflight, and remove the global `tests/**` `B023` ruff ignore.
- Changed offline installers to derive MCP, `offline.env`, shell, and activation runtime environment keys from `installer/manifest.json`, propagate bundled Node/Python encoding consistently, register Antigravity MCP in verifier coverage, and parse `activate-offline.sh` env files without executing shell code.
- Changed `RuntimeContext.parse_cache` accessors to use a lock and same-key in-flight coordination so concurrent parser memoization runs each supplier once.
- Changed MCP tool outputs to include top-level `schema_version=1`, preserve provider/HTTP error details in machine-readable fields, and stop batch submission on rate-limit categories, HTTP 429, or retry-after hints while retaining `abort_reason.retry_after_seconds`.
- Changed MCP cache-index reads to validate `INDEX_VERSION`, reject stale/invalid manifests unless explicitly rescanned, expose `list_cached(cache_mode="index"|"refresh"|"rescan")`, keep structured resolve `title`/`authors`/`year` as independent resolver signals, and move provider/Crossref primary-secondary metadata merge semantics into one rule-backed helper.
- Changed provider waterfalls to continue fallback routes consistently for access, rate-limit, no-result, and generic provider failures while deduplicating aggregated warnings/source trail and preserving retry-after details in final failures.
- Changed provider registry cold-start behavior so root `paper_fetch` imports no longer load provider entry modules, `trafilatura`, or `idutils`; provider discovery now uses an explicit built-in entry list plus cached AST checks for dynamic entries, and browser workflow route labels live in `route_order` instead of string-valued `waterfall_steps`.
- Changed shared Markdown table rendering to use one canonical pipe-table formatter across IR and HTML paths, preserving explicit headers, escaping pipes/newlines, padding ragged rows, and rendering fallback messages.
- Changed HTML-derived formula and citation rendering to keep inline TeX math delimited, prefer explicit figure context before formula-image URL heuristics, and share one numeric citation payload helper across section and Atypon renderers.
- Updated README, CLI/MCP instructions, provider/runtime/deployment/extraction docs, AMS onboarding manifest/access-review/cleaning-chain evidence, and the provider runtime optimization plan to match the new browser-runtime and AMS direct-HTTP ownership boundaries.
- Expanded unit and integration coverage for AMS direct HTTP HTML/PDF fallback, browser-preflight provider candidates/no-PDF behavior, external-CDP new-context diagnostics, browser runtime facade wiring, and browser workflow dependency grouping.

## 2.8.0 - 2026-07-02

### Added

- Added provider-template-aware DOI extraction for DOI-bearing publisher URLs, including query-parameter DOIs, known route/extension suffix stripping, and AMS old-style SICI `view` / `downloadpdf` slug support, so many URL queries resolve directly without fetching a landing page first.
- Added `scripts/dev-preflight.sh --coverage` plus CI unit coverage reports (`term-missing` and `coverage.xml`) as a baseline signal without enforcing a coverage threshold.

### Changed

- Changed publisher-facing landing/PDF requests and browser workflows to use browser-shaped user agents through `build_publisher_user_agent`; `PAPER_FETCH_USER_AGENT` remains the tool/API user agent and no longer becomes the default browser context user agent.
- Changed Royal Society Publishing from direct HTTP DOI/PDF fetching to the shared CDP browser HTML plus seeded-browser PDF workflow while keeping `royalsocietypublishing_html` / `royalsocietypublishing_pdf` sources and the no-XML route contract.
- Changed title-query resolution to prefer a formal journal publication over a near-tie preprint when Crossref metadata identifies a clear formal publication candidate.
- Expanded mypy coverage to 136 project source files, including HTML extraction, browser workflow, Atypon browser workflow, shared JATS/common Markdown helpers, the CloakBrowser helper, service, artifacts, image conversion, and resolver modules.
- Changed local and CI quality gates to enforce `ruff format --check`, keep ruff linting, prefer repo-local `.venv/bin/python` or explicit `PYTHON_BIN`, report missing dev dependencies early, and run local preflight type checks with `mypy --no-site-packages`.
- Applied `ruff format` across the Python codebase and updated module-layout and asset-contract guard tests for the formatted source shape.

### Fixed

- Fixed the expanded mypy contract suite by normalizing BeautifulSoup attribute values before helper calls, preserving optional HTML dependency fallbacks under type checking, and aligning MCP request/resource/result types with the current SDK signatures.
- Fixed browser-backed batch concurrency so managed CDP browser managers are shared process-wide by provider/browser config, preventing concurrent CLI/MCP fetches for the same provider profile from racing on `.paper-fetch-profile.lock`; isolated contexts now use thread-owned CDP connections to avoid cross-thread Playwright sync object reuse.
- Fixed SICI DOI normalization and URL DOI suffix handling so DOI suffixes such as `<...>` / `;` are preserved, while provider route tokens such as Frontiers `/full`, IOP `/pdf`, Wiley `/fullpdf`, and Springer `.pdf` are stripped only when provider catalog templates make that safe.
- Fixed official PDF fallback degradation for scanned/PDF-only provider results: real downloaded PDFs are retained with explicit warnings and provider source trail instead of being replaced by Crossref/general metadata-only results when Markdown extraction is unusable.
- Fixed publisher landing/probe requests that previously sent the stable `paper-fetch-skill/<version>` tool user agent to browser-facing publisher routes.
- Fixed docs and contract drift around `PdfFallbackStrategy`, browser runtime ownership, provider URL/route behavior, and asset-download contract marker scanning after repository-wide ruff formatting.

## 2.7.1 - 2026-07-01

### Added

- Added `paper-fetch browser-preflight` to serially open browser-backed provider sample pages, save provider-scoped storage-state JSON on success, and report providers that need manual `paper-fetch auth`.

### Changed

- PDF/ePDF fallback image exports now use the same DOI-scoped `<doi>_assets/` directory as HTML/XML asset downloads when a DOI is available, while retaining the legacy `body_assets/` fallback for DOI-less internal calls.

### Fixed

- AMS formula image extraction now reads lazy `data-image-src` GIF URLs before `Blank.svg` placeholders, so image-only equations are rendered and downloaded from the real publisher formula assets.
- AMS direct HTTP HTML preflight now follows DOI 3xx redirects to the publisher full-text page before parsing while still rejecting challenge pages, so public AMS articles can stay on the no-browser `ams_html` path instead of falling through to browser/PDF fallback.
- PDF fallback source files now prefer merged provider payload metadata for artifact filenames, so arXiv paths that learn title, authors, and year after fetch no longer fall back to `unknown_unknown_<doi>.pdf`.

## 2.7.0 - 2026-07-01

### Added

- Added AMS direct HTTP HTML preflight with browser-equivalent headers before the CDP browser fallback, reducing browser startup for publicly reachable AMS article pages while preserving the existing browser/PDF recovery route.
- Added AMS `Download Figure` EPS/TIFF source-figure handling: body figure assets now prefer publisher source files, convert them to PNG through Ghostscript/libvips when available, preserve the original source files and conversion metadata, and fall back to webpage JPG/PNG candidates when conversion is unavailable or fails.
- Added optional image conversion tooling (`paper-fetch-install-image-tools`, `install-image-tools.sh`, `PAPER_FETCH_IMAGE_TOOLS_DIR`, `PAPER_FETCH_GHOSTSCRIPT_BIN`, `PAPER_FETCH_VIPS_BIN`, `PAPER_FETCH_EPS_DPI`, and `PAPER_FETCH_IMAGE_TOOL_TIMEOUT_SECONDS`) plus offline installer environment propagation.

### Changed

- Changed Linux, macOS, and Windows offline package builders to configure image-tools paths without bundling build-host `gs`/`vips` symlinks from `PATH`; Ghostscript/libvips remain optional runtime tools.
- Changed arXiv Atom API enrichment to use a 60 second timeout and two transient retries for timeout/5xx failures, and surfaced those settings in provider status diagnostics.

### Fixed

- Fixed direct HTTP browser-workflow asset downloads so a failed AMS asset does not attempt browser seed refresh when no browser runtime was started, and so supplementary downloads inherit the same seeded Referer behavior as body figure downloads.
- Ignored repo-local `.image-tools/` output so local Ghostscript/libvips staging artifacts are not accidentally committed.
- Updated README, provider, deployment, architecture, extraction-rule, offline installer, CI, and unit-test coverage for AMS source figures, image conversion fallback, and offline image-tools behavior.

## 2.6.2 - 2026-06-27

### Changed

- Refreshed the human- and agent-facing documentation to describe the current provider routing, browser runtime, artifact, cache, probe, onboarding, and extraction-rule contracts without stale migration wording, and renamed the browser runtime reference to `docs/browser-runtime.md`.
- Updated CLI and MCP help text for provider authentication and browser storage/profile overrides to describe the current provider-scoped storage-state behavior.

### Fixed

- Updated extraction-rule validation so compatibility-anchor redirects remain accepted after the refreshed extraction rules converted the old "compatible note" wording to current anchor wording.

### Removed

- Removed the stale `problems.md` implementation task draft and the obsolete `docs/legacy-browser-runtime.md` reference.

## 2.6.1 - 2026-06-27

### Fixed

- Fixed LaTeX normalization for MathJax `\unicode{...}` commands, including `\unicode{x2A7D}` -> `\leqslant`, so IOP Markdown output such as `10.1088/1748-9326/ad560b` no longer fails KaTeX parsing with an undefined control sequence.
- Fixed `MarkdownFormula` rendering to apply the shared LaTeX normalization path instead of only generic text normalization.
- Fixed browser-workflow image downloads to prefer explicit `download_url` candidates and reject lazy placeholder images such as `Blank.svg`, `Blank.png`, and `Blank.gif`, preventing Atypon/AMS pages from saving placeholder assets as body figures.
- Fixed seeded browser PDF fallback after async thread handoff to use a thread-local browser context manager while preserving configured profile and user-data directories, avoiding cross-thread runtime browser manager use.

## 2.6.0 - 2026-06-26

### Added

- Added Frontiers (`frontiers`) XML-first provider for `10.3389/` and `frontiersin.org`, with canonical article discovery, shared JATS rendering, figure URL rewriting, direct HTTP PDF fallback, `frontiers_xml` / `frontiers_pdf` sources, manifest, docs, and unit coverage.
- Added `paper-fetch --version` plus CLI help text for reference, asset, and token rendering options.

### Changed

- PDF fallback now honors `asset_profile=body|all` when artifact saving is enabled, exporting PDF-rendered body images to `body_assets/` and surfacing them in article assets/artifacts across direct HTTP and seeded-browser PDF routes.
- PDF fallback source files now use stable, source-derived filenames instead of a single `downloaded.pdf`, reducing collisions when multiple fallback PDFs are materialized in the same artifact directory.

### Fixed

- Fixed IOP figure asset extraction so standard `_lr` / `_online` CDN image links are upgraded to `_hr` high-resolution candidates before preview fallback, allowing IOP HTML fetches such as `10.1088/1748-9326/ad560b` to save full-size body figures when available.

## 2.5.2 - 2026-06-24

### Fixed

- Fixed shared HTML cleanup so semantic attributes such as `data-title`, `alt`, `title`, and `aria-*` no longer trigger chrome noise filtering. This preserves valid body figures whose captions contain words such as "related", including Nature articles where Fig. 2 was dropped from Springer/Nature HTML extraction.
- Added regression coverage to keep Springer/Nature body figure assets with semantic `data-title` text while continuing to remove real related/recommended article chrome identified by structural attributes.

## 2.5.1 - 2026-06-23

### Fixed

- Fixed browser PDF fallback after async thread handoff so it preserves the caller's runtime browser configuration, including provider profile and user-data directories, instead of forcing a fresh non-runtime browser context.
- Added regression coverage for the runtime-browser PDF fallback path to ensure thread handoff still reuses the configured runtime context.

## 2.5.0 - 2026-06-23

This release refactors the CloakBrowser browser path around CDP-managed Chrome reuse and improves anti-bot/challenge resilience through provider-scoped browser state, shared runtime context management, and safer external-browser attachment.

### Added

- Added optional `CLOAKBROWSER_CDP_ENDPOINT` support for attaching browser workflows to an already-running Chrome/CloakBrowser instance over CDP.
- Added managed Chrome startup through CloakBrowser when no endpoint is configured, including provider-scoped profile/storage-state reuse under `publisher-browser-profiles/<provider>`.
- Added provider-scoped browser authentication with `paper-fetch auth <provider>` for browser-backed providers, including built-in sample URLs, `--url` overrides, headed manual verification, and local storage-state saving without requiring `.env` writes.
- Added `CLOAKBROWSER_PROFILE_DIR` plus legacy Wiley storage/profile environment variable awareness so existing user configuration can be identified while the managed CDP path defaults to provider-scoped state.

### Changed

- Changed the browser backend from direct `cloakbrowser.launch()` ownership to a CDP-backed `BrowserContextManager`; HTML fetches, browser-backed asset downloads, fast HTML preflight, and seeded PDF/ePDF fallbacks now share the runtime keyed browser manager where possible.
- Changed managed browser startup to use `cloakbrowser.ensure_binary()` and a local Chrome CDP endpoint; `CLOAKBROWSER_HEADLESS`, `CLOAKBROWSER_BINARY_PATH`, `CLOAKBROWSER_PROFILE_DIR`, and `CLOAKBROWSER_USER_DATA_DIR` now apply to that managed path.
- Changed external CDP mode to borrow the browser's existing context, inject storage-state cookies where possible, and document that new-context options such as user agent and viewport may be ignored by the borrowed context.
- Changed runtime-shared browser-backed asset downloads to run serially in both managed and external CDP modes, opening isolated context/page instances without moving Playwright sync objects across worker threads; ordinary HTTP asset downloads still use the configured concurrency.
- Changed AMS authentication and fetching to use the same provider-scoped storage-state model as other browser-backed providers; `PAPER_FETCH_AMS_STORAGE_STATE_JSON` is now a legacy override instead of a required setup step.
- Changed `paper-fetch auth` legacy AMS-only options (`--state-json`, `--env-file`, `--no-env-write`, `--wait-seconds`) to unsupported compatibility stubs; profile/storage-state location is now controlled by the browser runtime directory configuration.
- Changed browser provider status checks and MCP/skill documentation from CloakBrowser launch terminology to CDP browser runtime / Playwright dependency terminology, including explicit external endpoint and managed-browser behavior.
- Changed offline installers, offline package builders, and CI smoke checks to validate Playwright, CloakBrowser `ensure_binary`, and `BrowserContextManager` instead of probing the removed direct `cloakbrowser.launch()` path.
- Changed generated offline environment files and installer messages to document `CLOAKBROWSER_CDP_ENDPOINT`, managed Chrome startup, default `CLOAKBROWSER_HEADLESS`, and browser user-agent defaults for browser-backed publishers.
- Changed the CloakBrowser dependency constraint to `cloakbrowser>=0.4,<0.5`.

### Fixed

- Fixed managed headless Chrome startup so paper-fetch appends Chrome's native `--headless=new` flag when CloakBrowser omits a headless argument, preventing ordinary browser-backed CLI fetches such as Wiley from opening a visible browser window.
- Fixed browser-backed image and file fetchers so managed CDP mode reuses the runtime keyed browser manager instead of starting independent Chrome instances, avoiding same-profile lock deadlocks while preserving isolated context/page use.
- Fixed browser-backed figure asset downloads in batch and single-paper CLI runs so runtime-shared Playwright/CDP objects stay on their owning caller thread, eliminating `greenlet`/`TargetClosed` failures and preserving local figure asset output for CloakBrowser-backed providers.
- Fixed managed browser profile locking to use a timeout instead of blocking forever when another managed browser already owns the profile directory.
- Fixed CDP startup polling so a responsive `/json/version` endpoint with a temporarily missing `webSocketDebuggerUrl` no longer spins without sleeping.
- Fixed fast HTML preflight, browser-backed asset fetchers, and browser PDF fallback to carry binary path, CDP endpoint, profile directory, user-data directory, and storage-state configuration consistently into the browser context manager.
- Fixed seeded PDF fallback HTTP retry cookies to request and filter cookies for the target URL before replaying the PDF request.
- Fixed provider status handling so managed browser mode can report browser-backed providers as ready without requiring a preconfigured external endpoint or AMS storage-state JSON, while still rejecting invalid managed binary paths and malformed CDP endpoints.
- Fixed offline installer activation and MCP environment registration so managed CDP browser variables are exported consistently and obsolete profile/binary variables are not propagated as MCP env keys.

## 2.4.1 - 2026-06-20

### Changed

- Bumped the CloakBrowser dependency floor to `0.3.32`, improving browser-route adaptation to publisher anti-bot and automation-detection changes; all users are encouraged to update.

## 2.4.0 - 2026-06-18

### Changed

- Refined the packaged skill instructions: paper-fetch now explicitly applies to DOI, URL, arXiv ID, title, citation, and search-generated candidate workflows that need reading, summarization, comparison, translation, critique, full-text fetch, or readability checks; ordinary read/summarize tasks default to no local save unless the user asks for archival output, and browser-runtime guidance now follows `ProviderSpec.requires_browser_runtime` instead of a hard-coded provider list.
- Hardened HTML byte decoding across provider and asset fetch paths: `decode_html()` now honors UTF-8 BOM/UTF-8, HTTP `Content-Type` charset, HTML meta charset, `charset-normalizer`, and UTF-8 replacement fallback, with Springer, IEEE, browser workflow, generic provider, and figure-page paths passing response content type where available.
- Reduced repeated HTML parsing and DOM cloning overhead in Annual Reviews, Royal Society Publishing, IOP, shared author/reference helpers, and arXiv helpers. Pure BeautifulSoup string-reparse clones now use bs4 node copies, while raw MathML fragment parsing remains explicit for AMS.
- Centralized arXiv official HTML parser selection through `ARXIV_HTML_PARSER = choose_parser()` after fixture tests confirmed the `lxml` parser path remains compatible.

### Fixed

- Made generic HTML cleanup cheaper on pages without `article`, `main`, or `role=main`: no-root cleanup now skips per-node noise classification while retaining tag, selector, and ORCID removal, and content-root selection avoids repeated full-subtree text extraction.
- Capped raw trafilatura fallback at `1_000_000` characters so large original HTML is no longer sent to trafilatura after cleaned HTML fails; cleaned fallback parsing still runs.

## 2.3.0 - 2026-06-14

### Added

- Added Antigravity CLI (`agy`) as a third install target alongside Codex and Claude Code. The new `scripts/install-antigravity-skill.sh` copies the static skill (user scope `~/.gemini/antigravity-cli/skills/`, project scope `./.agents/skills/`, overridable via `ANTIGRAVITY_HOME`) and, with `--register-mcp`, merges the local stdio server into the appropriate `mcp_config.json` (`command`/`args`/`env`) while preserving any existing server entries. The offline installers (`install-offline.sh`, `scripts/windows-installer-helper.ps1`) now install the Antigravity skill and `mcp_config.json` too, with matching uninstall handling and CI coverage.

### Changed

- Broadened the ruff lint ruleset from `E4,E7,E9,F,TID251` to additionally enforce `UP`, `B`, `SIM105`, and `RUF022`, and applied the resulting fixes across the codebase: `typing` ABC imports migrated to `collections.abc`, `datetime.timezone.utc` rewritten to `datetime.UTC`, `try`/`except`/`pass` blocks replaced with `contextlib.suppress`, an explicit exception chain added to `run_provider_waterfall` (`raise ... from exc`), and explicit `zip(..., strict=...)` at the sites the new rules surfaced. `B008` is ignored project-wide (the MCP `default_mcp_deps()` argument default is an intentional dependency-injection seam) and `B023` is ignored under `tests/`.
- Extended mypy `files` coverage beyond the model/workflow/mcp/http contract surface to additional foundational modules (`metadata`, `markdown`, `extraction/markdown_render`, `tracing`, `reason_codes`, `arxiv_id`, `normalize_journal_name`, `section_vocab`, `logging_utils`, `publisher_identity`, `provider_catalog`, `extraction/citation_anchors`), raising the analyzed set from 45 to 68 files, with the type fixes required to keep the check green.
- Stopped tracking the ad-hoc batch-debugging output under `failures/` and three unreferenced raw fetch artifacts under `figures/`, and added both to `.gitignore` to prevent re-committing them.
- Bumped the bundled `mathml-to-latex` formula backend from 1.5.0 to 1.8.0, syncing the version across the root and `src/paper_fetch/resources/formula/` package manifests and lockfiles.

## 2.2.1 - 2026-06-12

### Changed

- Disk cache entry iteration no longer reads each cache file's JSON payload to extract `stored_at`; `st_mtime` is used directly, removing O(n) file reads from every `_prune_disk_cache` call.
- Disk cache reads in `_load_disk_cached_entry` no longer hold the exclusive `_disk_cache_lock` during file I/O; concurrent cache reads no longer serialize behind a single lock.
- `_sensitive_cache_header_names` and `_cache_key_header_names` are now computed once per process via `@functools.cache` instead of calling `provider_sensitive_header_names()` on every HTTP request.
- `prepare_html_extraction_tree` eliminates the redundant second BeautifulSoup parse; the HTML tree is now pruned in place and serialized once instead of being serialized to string and re-parsed into a fresh soup object.
- `html_cleanup_rules` is now memoized with `@functools.lru_cache(maxsize=32)` so repeated calls with the same noise profile within a single extraction pipeline share a single `HtmlCleanupRules` instance.
- `choose_parser` evaluates `importlib.util.find_spec("lxml")` once at import time and returns a module-level constant on every call.
- `classify_dom_cleanup_node` now references a module-level `_HEADING_TAG_RE` constant instead of compiling `re.compile(r"^h[1-6]$")` twice on every element visit.
- `_inline_image_contents` performs a single `path.stat()` call per asset instead of a separate `path.is_file()` followed by `path.stat()`.
- `run_blocking_call` uses the default asyncio thread-pool executor instead of creating a dedicated per-call `ThreadPoolExecutor`; log bridge lifecycle in `batch_resolve_tool_async` and `batch_check_tool_async` now uses `ExitStack`.
- `mark_envelope_cached_with_current_revision` is now a `None`-returning mutation instead of returning the modified envelope.
- Expanded mypy coverage to include the `paper_fetch.mcp` and `paper_fetch.http` packages; added missing type annotations and `cast` calls to satisfy strict checking.
- Relaxed `mcp` version constraint from `>=1.27,<1.28` to `>=1.27,<2`.

### Fixed

- `parse_retry_after_seconds` now handles fractional `Retry-After` values such as `"0.5"` or `"1.5"` by parsing through `float()` before truncating to `int`; previously these fell through to the HTTP-date parser and were silently discarded.
- `_mcp_log_level` no longer returns `"debug"` as the fallback for log records with a level above `CRITICAL`; the fallback is now `"critical"`.

## 2.2.0 - 2026-06-10

### Added

- Reuse the warmed in-page article `<img>` via canvas export as the first browser-workflow image-recovery step; when the target image exists but has not finished loading, perform a credentialed in-page `fetch()` for the raw image bytes before falling back to direct URL request, page fetch, and navigation candidates (affects `wiley`, `science`, `pnas`, `ams`, `annualreviews`, `acs`, `iop`, `aip`, `mdpi`).

### Changed

- Derive Atypon/Wiley figure caption labels from explicit labels, the figure DOM id, the image URL basename, or a caption that starts with `Figure N`, and read the `.figure__title` selector; a mid-caption `Figure N` cross-reference can no longer override the figure's own number.
- Consolidate browser-workflow asset-download internals with no behavior change: a single generic per-thread document fetcher backs both the image and supplementary fetchers, image/file fetchers reuse the shared browser response-header/status helpers, the two attempt-fetcher builders collapse into one (dropping unused parameters), and a shared `dedupe_normalized` utility replaces four copies of ordered URL de-duplication.

### Fixed

- Stop formula images from masquerading as figures: a node whose only image is a formula image yields no figure asset, formula-image anchors rewrite only as formula assets, and when one image URL matches both a figure and a formula the formula semantics win, so formula images no longer consume inline figure slots.
- Key inline figure injection off both image alt text and image URL basename, and skip a body `Figure N` cross-reference when that figure already appears as a Markdown image, so a repeated or label-less figure can no longer trigger a second inline insertion.

## 2.1.0 - 2026-06-08

### Added

- Add `paper-fetch auth ams` to open a headed CloakBrowser session, save AMS storage-state JSON, and optionally write `PAPER_FETCH_AMS_STORAGE_STATE_JSON` to the paper-fetch user environment file.
- Add Elsevier PII URL resolution for ScienceDirect and LinkingHub `/pii/...` URLs, including provider identifier propagation and official Elsevier Abstract PII API metadata lookup before the normal DOI full-text path.

### Changed

- Require explicit `PAPER_FETCH_AMS_STORAGE_STATE_JSON` for AMS browser workflow and provider status checks; AMS no longer relies on stateless browser startup or `CLOAKBROWSER_USER_DATA_DIR` as its authentication source.

### Fixed

- Try Springer PDF fallback when accepted Springer HTML still renders to abstract-only Markdown, instead of returning abstract-only before PDF recovery.
- Prefer formally published Crossref title-query candidates over near-duplicate preprints when both appear in the candidate set.
- Detect Springer article-in-press notice text as an availability blocker when no post-abstract body is present, avoiding false full-text acceptance.
- Avoid duplicating IOP appendix figure captions and suppress repeated non-inline figure asset captions that are already present in rendered Markdown.

## 2.0.0 - 2026-05-28

### Changed

- Derive MCP provider guidance from the runtime provider catalog so accepted provider hints, browser-runtime providers, and public source names stay aligned with registered providers.
- Refresh public provider and extraction documentation for the current provider catalog, including Annual Reviews, Royal Society Publishing, PLOS, Oxford Academic, ACS, IOP, AIP, MDPI, AMS, Science, and PNAS route details.
- Mark browser-workflow providers through provider specs instead of maintaining separate hard-coded browser-runtime provider lists.
- Update Codex skill installation, offline installer, deployment, and onboarding documentation around the supported installation surface.

### Removed

- Remove the Gemini skill installer and legacy Codex MCP runner scripts from the shipped script surface.

### Fixed

- Keep CloakBrowser workflow labels, provider docs drift checks, offline install checks, and skill template tests synchronized with catalog-derived provider facts.

## 1.9.0 - 2026-05-27

### Added

- Add AIP Publishing (`aip`) provider routing for `10.1063/` and `pubs.aip.org`, with CloakBrowser article HTML, seeded-browser PDF fallback, `aip_html` / `aip_pdf` sources, body figure/table/formula/supplementary extraction, and provider-managed abstract-only degradation.
- Add two-step provider onboarding human gates with `prepare-human-preflight` and `finalize-review-artifact` so users review waterfall/access once, then batch-confirm final Markdown quality instead of editing every fixture review by hand.
- Add IOP Publishing (`iop`) provider routing for `10.1088/` and `iopscience.iop.org`, with CloakBrowser article HTML, seeded-browser PDF fallback, `iop_html` / `iop_pdf` sources, and Radware/hCaptcha challenge rejection.
- Add real IOP fixture coverage for table, formula, and PDF fallback purposes with `10.1088/2058-9565/ac3460` and `10.1088/1748-9326/aa9f73`.
- Add ACS (`acs`) provider routing for `10.1021/`, `www.acs.org` / `pubs.acs.org`, shared CloakBrowser HTML plus seeded publisher PDF/ePDF workflow, replay-backed table / formula / Supporting Information coverage, and direct public `/doi/pdf` fallback capture with seeded browser-navigation headers.

### Changed

- Tighten provider fixture discovery so Crossref candidate searches can be DOI-prefix filtered, off-provider DOI candidates are dropped before probing, and challenge/access/empty-shell probes cannot rank as high-confidence fulltext fixtures.

### Fixed

- Re-approve the IOP replay fixture coverage so the real `10.1088/1748-9326/ab7d02` capture now covers the supplementary purpose through the article-scoped `stacks.iop.org` media link.
- Require ACS body figure assets in the onboarding contract and preserve ACS figure image links through browser-workflow cleanup so downloaded body figures rewrite Markdown to local asset paths.

## 1.8.0 - 2026-05-26

### Added

- Add PLOS (`plos`) provider routing for `10.1371/` DOI and `journals.plos.org`, using public JATS XML first, direct HTTP PDF fallback, provider-managed metadata fallback, and `plos_xml` / `plos_pdf` sources.
- Add Oxford Academic (`oxfordacademic`) provider onboarding for public HTTP article HTML, validated article-PDF fallback, `oxfordacademic_html` / `oxfordacademic_pdf` sources, provider manifest, access review, cleaning proposal, and benchmark samples.
- Add PLOS and Oxford Academic golden corpus coverage with real replay fixtures, expected Markdown summaries, markdown-quality reports, and representative fixtures.

### Changed

- Extend onboarding automation, fixture capture, manifest sync-back, and cleaning-chain proposal tooling for the PLOS and Oxford Academic provider workflows.
- Refresh provider documentation, extraction-rule evidence, onboarding runbooks, and known-provider manifests for the new providers.
- Update Royal Society Publishing PDF fallback expected payloads and markdown-quality fixtures after shared PDF rendering cleanup.

### Fixed

- Follow PLOS signed figure-image redirects during asset downloads and rewrite refreshed PLOS figure golden replay Markdown to local `body_assets`.
- Render PLOS graphic-only JATS formulas as inline formula image assets instead of `Formula unavailable` placeholders.
- Preserve Oxford Academic Silverchair formula paragraphs and render references from visible reference-list text instead of raw `citation_reference` meta keys.
- Keep Oxford Academic golden corpus count guards in sync with the new provider fixtures and representative sample.

## 1.7.0 - 2026-05-24

### Added

- Add Annual Reviews (`annualreviews`) provider for `10.1146/` DOI routing, CloakBrowser-rendered HTML full text, seeded-browser PDF fallback, provider-managed abstract-only degradation, fixture replay, golden corpus coverage, and HTML body figure extraction.

- Add Royal Society Publishing direct HTTP HTML provider with strict PDF fallback.

### Fixed

- Wait for Annual Reviews dynamic full-text DOM containers during fast browser fixture capture, and stop treating institutional "access provided by" labels as paywall blockers while keeping them as Markdown cleanup noise.
- Classify browser PDF fixture downloads that return non-PDF payloads as `NON_PDF_FALLBACK_CONTENT` instead of a network transient, and require replacing the failed PDF sample before onboarding resumes.
- Refetch browser PDF fallback responses through the browser request context when Chromium exposes a PDF viewer shell instead of the underlying PDF bytes.
- Allow manifest-driven fixture capture to reuse an already registered DOI fixture when multiple onboarding purposes share the same article.
- Avoid classifying publisher access UI as an access gate during fixture capture when the captured page has a populated full-text container.
- Preserved Royal Society Publishing Silverchair figure captions and stripped Royal Society PDF fallback watermark/page placeholder noise from Markdown.
- Derived DOI values for known MDPI numeric article URLs before generic landing-page fetches, and derived MDPI article landing URLs from known MDPI DOI suffixes before falling back to `doi.org`.
- Synced the bundled formula Node workspace to `katex` 0.17.0 so root and formula package lockfiles stay aligned.
- Replaced invalid UTF-8 bytes from external formula converter subprocess output instead of letting Windows reader threads raise `UnicodeDecodeError`.
- Replaced invalid UTF-8 bytes from PyMuPDF's Windows Tesseract-probe subprocess output during PDF fallback Markdown conversion.

## 1.6 - 2026-05-22

### Added

- Added experimental macOS offline release tarballs for CPython 3.11, 3.12, 3.13, and 3.14, with CI installation checks, headful layout validation, and CloakBrowser smoke coverage.
- Added the MDPI CloakBrowser HTML provider with browser PDF fallback, recorded replay fixtures, Markdown cleanup coverage, and `mdpi_html` / `mdpi_pdf` sources.
- Added operator access-review and provider Markdown-review artifacts for AI provider onboarding, with schema-backed gates before discovery and acceptance.
- Added a local `scripts/dev-preflight.sh` gate plus low-strength contract-layer `mypy` checking, formula Node package sync tests, and golden corpus provider adapters for easier provider onboarding.

### Changed

- Changed manifest-driven fixture capture to support `--all` batch capture and changed provider scaffold replay to return merge-plan JSON when generated files already exist.
- Tightened live review to compare provider sources against manifest `route_sources` and reuse manifest Markdown contracts for automatic issue classification.
- Enabled the normal Chrome browser User-Agent in offline installer-managed `offline.env` blocks by default so CloakBrowser-backed AGU/Wiley fetches are less likely to stop at Cloudflare challenge pages.
- Derived MCP status, live review support, and golden corpus representative coverage from provider facts instead of hard-coded provider lists where possible.

## 1.5.6 - 2026-05-18

### Fixed

- Fixed Windows offline installer smoke checks by running bundled Python probes from temporary `.py` files instead of passing multi-line scripts through `python.exe -c`, avoiding PowerShell native-command quote stripping around CloakBrowser checks.

## 1.5.5 - 2026-05-17

### Fixed

- Restored the Wiley full-text waterfall after Cloudflare/challenge HTML failures so browser PDF/ePDF fallback and then the optional Wiley TDM API PDF lane are still attempted before provider-managed metadata-only fallback.
- Kept the AGU/Wiley Cloudflare workaround centered on `PAPER_FETCH_BROWSER_USER_AGENT` with headless CloakBrowser as the usual runtime path.

## 1.5.4 - 2026-05-17

### Changed

- Changed Linux offline release assets from `.tar.gz` bundles to single self-extracting `.sh` installers with `--install-dir <path>` support and the default install root `~/.local/share/paper-fetch-skill`.
- Changed Linux and Windows offline upgrades to clear the old runtime payload before installing the new runtime-only payload while preserving user-authored `offline.env` content and refreshing managed environment, PATH, skill, and MCP registration blocks.
- Changed Linux offline uninstall semantics so `--uninstall` removes only user-level shell/skill/MCP integration and `--purge` explicitly deletes the fixed install directory.

### Fixed

- Prevented the Windows offline installer from aborting after runtime files are installed when optional post-install integration or smoke checks fail on a user machine; warnings are now logged to `install-helper.log`.
- Fixed Linux offline installer CloakBrowser checks and Claude MCP registration arguments for current host CLIs.
- Fixed browser PDF fallback so CloakBrowser/Playwright sync work is handed to a worker thread when the caller is already inside an asyncio loop.

## 1.5.3 - 2026-05-17

### Changed

- Changed the Windows offline installer to package only the embedded runtime, installed packages, command wrappers, static skill, formula tools, and installer metadata, removing the repository source snapshot and build wheelhouse from the installed payload.

## 1.5.2 - 2026-05-17

### Changed

- Changed Linux offline tarballs into preinstalled runtime packages with `bin/` launchers and `runtime/site-packages/`, without the repository source snapshot or target-machine wheelhouse; installation no longer runs pip.

### Fixed

- Prevented Atypon browser HTML routes for Wiley, Science, PNAS, and AMS from treating residual Cloudflare/challenge text as an HTML-route failure once a stable full-text DOM is already present.

## 1.5.1 - 2026-05-17

### Fixed

- Updated browser workflow User-Agent handling so CloakBrowser/Playwright contexts no longer inherit the default `paper-fetch-skill/<version>` HTTP UA unless users explicitly configure a browser UA.
- Added `PAPER_FETCH_BROWSER_USER_AGENT` for browser-only UA overrides while keeping explicit `PAPER_FETCH_SKILL_USER_AGENT` as a compatibility fallback for browser contexts.
- Documented the AGU/Wiley Cloudflare challenge workaround using a normal Chrome browser UA with headless CloakBrowser.

## 1.5 - 2026-05-16

### Added

- Added the CloakBrowser-backed browser runtime abstraction and provider status diagnostics, replacing the FlareSolverr runtime path.
- Added browser image payload and runtime smoke coverage for the migrated browser workflow.

### Changed

- Migrated Science, PNAS, Wiley, AMS, IEEE browser/PDF flows, MCP diagnostics, live runners, installers, offline packages, and CI from FlareSolverr-specific paths to the shared CloakBrowser/browser runtime path.
- Removed bundled FlareSolverr source, setup scripts, vendor patches, docs, and release-package runtime assets; offline packages now ship the `cloakbrowser` Python package and document that the browser binary is not redistributed.
- arXiv HTML asset handling now recovers figure assets from the arXiv e-print source package when official HTML exposes only missing-image placeholders; source PDF figures are rendered to PNG assets and inserted back near their figure captions while full-text extraction remains official-HTML first.
- Browser workflow concurrent asset downloads now use thread-private browser/context/page instances instead of sharing the `RuntimeContext` browser across worker threads.
- Optimized browser workflow fetching, CLI output-directory handling, provider request options, MCP cache payload handling, and fixture/scaffold docs around the new runtime contract.

### Fixed

- Fixed the Windows offline package builder so the MCP command wrapper PowerShell here-string closes correctly before writing `README.offline.md`.
- Suppressed CloakBrowser's first-launch promotional stderr banner during browser-backed fetches.

## 1.4.1 - 2026-05-15

### Added

- Added native CLI batch fetching with `--query-file`, per-item output files, JSONL batch summaries, bounded `--batch-concurrency`, and per-item failure reporting without aborting the whole batch.
- Added dedicated CLI documentation for output routing, artifact modes, asset profiles, `--save-markdown`, and batch-mode behavior.

### Changed

- Release 1.4.1: native batch CLI and provider/MCP refinements.
- Refined CLI output/artifact semantics so batch and single-query runs consistently separate primary output files from saved Markdown and provider artifacts.
- Updated MCP fetch/cache payload behavior for inline image budgets, cache resource visibility, and schema coverage.
- Hardened Elsevier Markdown and Springer HTML extraction around tables, figures, asset rewriting, and provider-specific cleanup.
- Fixed offline installer smoke checks to use the current MCP provider-status entrypoint during Linux and PowerShell installs.
- Refreshed README, provider, deployment, bundled skill, and tool-contract documentation to match the new CLI and MCP/provider behavior.

## 1.4 - 2026-05-12

### Added

- Added the `arxiv` provider for `arxiv.org` and DOI prefix `10.48550/`, publishing `arxiv_html` on official HTML success with text-only PDF fallback as `arxiv_pdf`.
- Added 10 real arXiv replay fixtures: 8 official HTML success samples and 2 official HTML 404 -> real PDF fallback samples, each with arXiv API metadata replay.

### Changed

- Reworked Phase 1 routing/extraction internals: Copernicus URL identity now uses catalog `domain_suffixes`, early metadata probes are driven by `ProviderSpec.probe_capability`, reference-anchor detection is centralized in HTML semantics, Wiley supplementary data attributes are handled by the Wiley extractor, and Science/PNAS figure teaser filtering now receives the actual publisher.
- Centralized provider source ownership, including Springer HTML/PDF source ownership, API-like hosts, Wiley TDM URL template, Springer/Nature domain matching, workflow HTML-managed fallback markers, and body-text thresholds in `ProviderSpec` / `SOURCE_PROVIDER_MAP`.
- Tightened Phase 4 generic extraction boundaries: Springer/Nature citation cleanup patterns now live in the provider layer, provider formula tokens require explicit `ProviderHtmlRules` profile injection, and Research Briefing authorless signatures live with quality signals.
- Completed Phase 4 duplicate-source cleanup: `FRONT_MATTER_PUBLICATION_KEYWORDS` now has one generic source with Science/PNAS publication tokens scoped to provider rules, `SourceKind` is checked against catalog sources at import time, Cloudflare cookie filters share the FlareSolverr constants, and Science reuses the shared AAAS datalayer pattern.
- Centralized Phase 3 HTML availability overrides and access-gate signals through provider rules and shared signal patterns, including Science perspective, Elsevier canonical abstract, and Springer preview-wall body-run handling.
- Hardened Phase 6 provider-specific contracts: IEEE article-number URL parsing now only accepts `/document/{article_number}/` landing paths, Springer/Nature Creative Commons cleanup no longer removes article roots, and HTML asset helpers avoid importing the public models package during package initialization.
- Completed Phase 7 cleanup: generic browser HTML failures are now `HtmlExtractionFailure`, FlareSolverr status probes use a non-DOI sentinel, landing-page redirect resolution has one request-URL-based semantic, and old FlareSolverr rate-limit env cleanup code was removed.
- Moved Atypon browser HTML/PDF candidate templates into `ProviderSpec` and removed the `paper_fetch.providers.science_html`, `paper_fetch.providers.pnas_html`, and `paper_fetch.providers.wiley_html` compatibility facades.
- Completed Phase 5 Atypon/Wiley cleanup: Wiley owns abbreviations and supplementary filename contracts, datalayer signal parsing uses schema field maps, and Atypon browser workflow scope is documented as Science/PNAS/Wiley catalog entries only.
- Golden criteria live review now includes `copernicus` in the supported provider rotation and provider-status diagnostics.
- Documented Phase 8 CI/test policy updates: regular unit/integration jobs and full golden regression continue to use pytest-xdist defaults, while live FlareSolverr/MCP paths document their required serial execution.
- Clarified CLI output semantics: explicit `--format` with `--output-dir` and stdout output now also writes a same-format document copy under `--output-dir`, while `--output` remains the explicit formatted-output file path.
- Golden criteria live review now treats `arxiv` as a supported provider, records arXiv provider status, preserves derived-URL fallback when arXiv API metadata has transient failures, and classifies arXiv asset partial-download diagnostics as `asset_download_failure`.
- arXiv metadata enrichment now uses a small internal Atom API client for ID lookup and no longer depends on the PyPI `arxiv` / `feedparser` dependency chain.
- arXiv HTML asset downloads now use a provider-specific lower concurrency cap and retry network-exception failures once sequentially while preserving non-retryable failures in `quality.asset_failures`.
- arXiv fulltext routing is now fixed to official HTML first with direct text-only PDF fallback; retired local source-conversion fallback code and related asset handling are no longer part of the supported route.
- arXiv official HTML Markdown cleanup now folds ordinary prose hard line breaks, sanitizes nested `$...$` delimiters inside LaTeXML TeX annotations, and lifts full-width table title rows out of GFM pipe table headers.
- Completed Phase 2 callback cleanup: Atypon DOM postprocess and scoped asset extraction are now provider-registered callbacks, and provider display names resolve through the catalog-backed `provider_display_name()` helper.
- Completed Phase 3 catalog field cleanup: Springer/Nature PDF candidates, arXiv metadata probe short-circuiting, provider HTML artifact persistence, XML source inference, provider-managed abstract-only handling, and PDF URL token semantics are now catalog/callback driven instead of provider-name hardcoded.
- Completed Phase 5 Atypon browser workflow rename: the old Science/PNAS package/profile/postprocess names were moved to `atypon_browser_workflow`, the legacy profiles facade was removed, Atypon profile dispatch now dynamically imports provider HTML modules from `ATYPON_BROWSER_WORKFLOW_PROVIDER_NAMES`, shared figure-link and abstract-redirect helpers live in neutral modules, and Science citation-italic repair now belongs to `_science_html.py`.
- Elsevier XML body asset downloads now retry only failed transient network items once sequentially and remove the original asset failure when the retry succeeds.
- Wiley formula image discovery now includes `data-altimg` fallback spans and display formula containers, so image-only formulas can enter the `kind="formula"` asset download path instead of requiring an `<img>` tag.

## 1.3 - 2026-05-09

### Added

- Added the `copernicus` XML-first provider for Copernicus Publications DOI prefix `10.5194/`, publishing `copernicus_xml` on NLM/JATS XML success with text-only PDF fallback as `copernicus_pdf`.
- Added 8 Copernicus XML golden fixtures across ACP, HESS, GMD, TC, ESSD, NHESS, AMT, and BG, plus 4 older Copernicus PDF-fallback golden fixtures whose XML is abstract-level only; live smoke sample coverage remains behind `PAPER_FETCH_RUN_LIVE=1`.
- Hardened Copernicus fallback handling for older articles whose XML only exposes abstract-level content: those XML failures now continue directly to text-only PDF fallback, and PDF discovery includes DOI-derived `.pdf` candidates when the landing page omits PDF metadata.

### Refactor

- Split `paper_fetch.http` from a single module into a package facade plus internal transport, cache, retry, body, and error modules while preserving the existing public import path.
- Move dev-only `geography_live`, `geography_issue_artifacts`, and `golden_criteria_live*` modules from `paper_fetch.*` to source-tree-only `paper_fetch_devtools.*`; wheels no longer ship those modules, while the existing repo-local script CLIs keep the same behavior.

### Changed

- Copernicus XML extraction now reuses the parsed XML root through validation and article assembly, validates usable body paragraphs with a named threshold, and continues with DOI-derived XML/PDF URLs when landing HTML cannot be fetched.
- Copernicus XML assets now use `original_url` as the canonical remote URL while shared asset download mirrors the compatibility URL fields after download; table assets are emitted directly as `kind="table"` with `table_render_kind`.
- Installer completion summaries now explicitly prompt users to request and configure `ELSEVIER_API_KEY` from <https://dev.elsevier.com/> before Elsevier full-text fetching, and point to the relevant `.env` file.
- Windows offline release artifacts now use `paper-fetch-skill-windows-x86_64-setup.exe` and bundle CPython 3.13 x64, Python dependencies, Playwright Chromium, formula tools, the FlareSolverr runtime, Codex / Claude Code skills, and MCP registration helpers.
- GitHub Actions now creates a GitHub Release on `v*` tag pushes or explicit manual releases after regular validation, the full Linux offline package matrix, and the Windows x86_64 setup exe succeed, uploading 4 Linux tarballs plus 1 Windows installer release asset.
- Expanded body-image payload recognition and persistence formats: in addition to PNG/JPEG/GIF/WebP/AVIF/TIFF, SVG text, BMP, ICO, APNG, and HEIC/HEIF MIME/extension mappings are supported; body images are verified for image magic bytes or top-level SVG document signatures before being saved, avoiding challenge HTML being persisted as images.
- Added Science `10.1126/science.adz3492` to the golden fixtures with real SVG body-image assets to guard against Science/PNAS SVG image persistence regressions.
- Added a fast initial FlareSolverr HTML pass for Wiley / Science / PNAS full-text fetching: primary HTML requests use `waitInSeconds=0` and `disableMedia=true`, then automatically fall back to the original conservative wait strategy on challenges, access blocks, abstract redirects, or insufficient body extraction.
- Image recovery, body/supplementary asset downloads, and figure-page HTML discovery continue to use media-enabled paths so `disableMedia` does not block full-size image discovery or downloads.
- Consolidated duplicate implementations for HTML availability/container handling, section hints, browser-workflow Markdown profiles, author fallback, Crossref resolve forwarding, and HTML heading/table helpers; canonical owners are now `quality.html_availability`, `extraction.section_hints` / `extraction.html.semantics`, `ProviderBrowserProfile` / `_html_authors.py`, and `metadata.crossref`.
- Clarified that the shared Science / PNAS / Wiley browser extraction is an Atypon-only profile, and consolidated asset scope, Wiley abbreviations, Wiley author noise, supplementary URL/filename rules, and AAAS/PNAS/Wiley datalayer detection into provider-owned callbacks/schemas.
- Moved the HTML asset canonical owner to the `paper_fetch.extraction.html.assets` package, removed the `paper_fetch.extraction.html._assets` and `paper_fetch.providers.html_assets` compatibility facades, and made download hooks patch from the extraction asset package or `paper_fetch.extraction.html.assets.download`.
- Materialized `paper_fetch.models` as a package split by schema, markdown, tokens, quality, render, sections, and builders while keeping `from paper_fetch.models import ...` compatible.
- Materialized the Science/PNAS browser-workflow HTML implementation as the `paper_fetch.providers.science_pnas` package, removed the `paper_fetch.providers._science_pnas_html` compatibility facade, and extracted the provider HTML asset policy engine plus Playwright document fetcher base class.

## 1.0.0 - 2026-04-26

### Changed

- Released the package as `1.0.0` and updated the default `paper-fetch-skill/1.0` User-Agent.
- Hardened Wiley / Science / PNAS seeded Playwright image fetching so Cloudflare challenge pages and non-image responses fail quickly instead of stalling a live review.
- Reordered the Wiley full-text waterfall so browser PDF/ePDF fallback now runs before the optional TDM API PDF lane whenever the local browser runtime is ready, keeping `wiley_browser` as the default successful route.
- Added `code_availability` as a first-class section kind. Elsevier, Springer / Nature, Wiley, Science, and PNAS now share data/code/software availability classification, retain those sections in final Markdown/ArticleModel output, and exclude them from body sufficiency metrics.

### Docs

- Documented the short-timeout behavior for seeded Playwright image fetches in the FlareSolverr workflow notes.
- Documented the unified data/code availability retention and quality-metric exclusion rules.

### Validation

- `PYTHONPATH=src python3 -m pytest tests/unit/test_provider_request_options.py`
- `PYTHONPATH=src python3 -m pytest tests/unit/test_science_pnas_provider.py -k 'download_related_assets or image'`
- Live smoke: Wiley `10.1111/gcb.16414`, Science `10.1126/science.ady3136`, and PNAS `10.1073/pnas.2406303121` produced full-text Markdown with full-size body images using the WSLg FlareSolverr preset.

## 2026-04-25

### Changed

- Promoted the Wiley / Science / PNAS browser workflow runtime to [`src/paper_fetch/providers/browser_workflow.py`](src/paper_fetch/providers/browser_workflow.py). Science, PNAS, and Wiley now declare `ProviderBrowserProfile` objects for URL candidates, Markdown extraction, author fallback, public source, labels, and browser asset behavior; `_science_pnas.py` remains a compatibility alias.
- Promoted the Wiley / Science / PNAS HTML asset downloader to a shared Playwright primary path. Figure, table, and formula image candidates now reuse one seeded browser context per download attempt instead of trying direct HTTP first.
- Kept full-size/original candidates ahead of preview candidates, but now fetches both tiers through the same shared browser context. Target-provider downloads report `download_tier="full_size"` or `download_tier="preview"` rather than `playwright_canvas_fallback`.
- Tightened the browser-workflow image recovery path: repeated figure-page / image-candidate URLs are cached per attempt, body-image payload downloads now use fixed limited parallelism with stable output ordering, and FlareSolverr recovery no longer falls back to screenshot cropping when `solution.imagePayload` is missing or invalid.
- Preserved the FlareSolverr seed refresh retry for partial asset failures, while keeping the generic HTTP-first asset downloader unchanged for non-target providers such as Springer.
- Expanded HTML formula handling so Wiley, Science / PNAS shared HTML, and Springer / Nature paths preserve MathML when possible and retain formula image fallbacks as `![Formula](...)` assets when MathML is absent or unusable.
- Normalized final Markdown after asset-link rewrites so downloaded figure / table / formula links replace remote URLs before section parsing, block images are separated from adjacent headings/text/math fences, and empty body parent headings remain visible.
- Hardened structured metadata and references: front matter unescapes HTML entities, Elsevier XML references no longer skip sparse bibliography entries, and Wiley / Springer-style HTML references remove link chrome while preferring visible citation text over DOI-only snippets.
- Tightened Springer / Nature HTML cleanup by pruning more article chrome and license sections, preserving scientific back matter outside the main body, extracting formula image assets, and emitting explicit table-body-unavailable placeholders when table-page parsing fails.
- Adjusted golden-criteria live issue classification so formula-only preview fallback is not treated as an asset-download failure, while non-formula preview fallback still remains an asset issue unless explicitly accepted.

### Docs

- Updated README, provider, FlareSolverr, extraction-rule, deployment, architecture, and schema notes to describe the shared Playwright primary asset path, formula image preservation, Markdown asset-link rewrites, reference fallback behavior, and target-provider `download_tier` semantics.

### Validation

- `pytest tests/unit/test_science_pnas_provider.py tests/unit/test_provider_waterfalls.py tests/unit/test_provider_request_options.py tests/unit/test_html_shared_helpers.py -q`
- `pytest tests/unit/test_elsevier_markdown.py tests/unit/test_golden_criteria_live.py tests/unit/test_models_render.py tests/unit/test_science_pnas_markdown.py tests/unit/test_springer_html_regressions.py -q`
- Live smoke: Wiley `10.1111/gcb.16455` downloaded 5/5 full-size body figures, Science `10.1126/science.ady3136` downloaded 6/6 full-size body figures, and PNAS `10.1073/pnas.2406303121` downloaded 4/4 full-size body figures; all local files had image magic bytes, dimensions, and Markdown links rewritten to local paths.

## 2026-04-19

### Changed

- Moved shared HTML full-text diagnostics into [`src/paper_fetch/providers/_html_availability.py`](src/paper_fetch/providers/_html_availability.py) and switched `html_generic`, `elsevier`, `springer`, FlareSolverr, and PDF fallback helpers to import the shared availability/access-signal layers directly instead of reaching through `_science_pnas_html.py`.
- Added internal `PublisherProfile` plumbing in [`src/paper_fetch/providers/_science_pnas_profiles.py`](src/paper_fetch/providers/_science_pnas_profiles.py) so browser-workflow candidate builders, noise-profile selection, and provider-specific postprocess hooks live outside `_science_pnas_html.py`.
- Removed the `_article_markdown_document.py` compatibility wrapper; direct Elsevier document assembly now lives only in [`src/paper_fetch/providers/_article_markdown_elsevier_document.py`](src/paper_fetch/providers/_article_markdown_elsevier_document.py), while [`src/paper_fetch/providers/_article_markdown.py`](src/paper_fetch/providers/_article_markdown.py) remains the intentional aggregate entrypoint.
- Split the oversized `tests/unit/test_science_pnas_html.py` coverage into focused candidate, availability, markdown, and postprocess test files, while keeping `detect_html_block()` coverage in `tests/unit/test_html_access_signals.py`.
- Promoted the geography report/export/group scripts plus their supporting modules and tests into tracked repo-local internal tooling without adding new CLI install surfaces or MCP tools.

### Docs

- Updated README, provider docs, and backlog notes to describe geography report/export/group as live-only internal tooling behind `PAPER_FETCH_RUN_LIVE=1`.

### Validation

- `pytest tests/unit/test_science_pnas_candidates.py tests/unit/test_html_availability.py tests/unit/test_science_pnas_markdown.py tests/unit/test_science_pnas_postprocess.py tests/unit/test_html_access_signals.py tests/unit/test_elsevier_markdown.py -q`
- `pytest tests/unit/test_geography_live.py tests/unit/test_geography_issue_artifacts.py -q`
- `python3 scripts/run_geography_live_report.py --help`
- `python3 scripts/export_geography_issue_artifacts.py --help`
- `python3 scripts/group_geography_issue_artifacts.py --help`

## 2026-04-16

### Added

- Added a public `provider_status()` MCP tool that reports stable local diagnostics for `crossref`, `elsevier`, `springer`, `wiley`, `science`, and `pnas` without probing remote publisher APIs.
- Added provider-level status probing with stable `ready` / `partial` / `not_configured` / `rate_limited` / `error` semantics plus per-provider `checks=[...]` details.
- Added MCP `resources/list_changed` support for cache resources when `fetch_paper()`, `list_cached()`, or `get_cached()` changes the visible cache-resource URI set for the current session.

### Changed

- Changed all 8 public MCP tools to expose `ToolAnnotations`; read-only tools now advertise `readOnlyHint=true`, while `fetch_paper` stays writable because it may refresh local cache files.
- Changed Science / PNAS local diagnostics so MCP can inspect FlareSolverr runtime readiness and local rate-limit windows without mutating the rate-limit tracking file.
- Changed `batch_resolve()` and `batch_check()` to reject requests with more than `50` queries instead of attempting oversized batch runs.
- Changed MCP initialization so the server now advertises `capabilities.resources.listChanged=true` across supported transports.

### Docs

- Updated README, deployment docs, provider docs, and the bundled skill guide to document `provider_status()` and the new MCP tool-annotation hints.
- Updated README, deployment docs, and the bundled skill guide to document the `50`-query batch limit and the new cache-resource list-change notifications.

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

- Kept architecture rationale in [`docs/architecture/overview.md`](docs/architecture/overview.md) and moved shipped changes to this file.
- Updated deployment, provider, MCP, and skill-facing documentation to match the landed MCP surface and environment behavior.

### Validation

- `ruff check .`
- `PYTHONPATH=src python3 -m pytest tests/unit tests/integration -q`
- `PYTHONPATH=src python3 -m pytest -n 0 tests/live/test_live_mcp.py -q` skips cleanly when live env is not enabled; `-n 0` is required because live MCP shares external publisher/API state and secrets.

### Follow-up

- The dedicated MCP probe tool `has_fulltext(query)` is intentionally not shipped yet; only its semantics note is landed in [`docs/architecture/probe-semantics.md`](docs/architecture/probe-semantics.md).
