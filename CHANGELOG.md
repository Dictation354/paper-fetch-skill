# Changelog

All notable public changes to `paper-fetch-skill` are documented in this file.

## Unreleased

<!-- SCAFFOLD: changelog-unreleased -->

## 7.4.2 - 2026-11-09

### Browser and PNAS fetching

- Upgrade managed Byparr to 3.1.1. Windows/Linux x64 use InvisiblePlaywright 0.47.1 with matching invisible-core 58.56.0; macOS and ARM retain Camoufox. Preserve native-profile/JSON state ownership, request deadlines, cancellation, and offline component verification.
- Try direct downloads first for PNAS body images, then request original image bytes from the existing browser context before page-image recovery. Read paragraph roles and text within the existing body-readiness budget. Retain matching popup navigations before page association so reentrant response or download events are not missed.

### Documentation and Skill

- Correct platform engine selection, backend compatibility values, and executable constraints against the code. Use the unified preparation entrypoint for the current platform engine and Byparr before offline use.
- Correct single-paper MCP Markdown overwrite defaults, supplementary-index naming, and compact acceptance fields in the Skill. Consolidate workflows, diagnostics, and rules while preserving the five presets, a self-contained Skill, and unchanged PDF converter output.
- Remove duplicated rules and procedural commentary from user, developer, test, and deployment documentation, keeping contracts and implementation indexes in their topic documents.

## 7.4.1 - 2026-11-08

This release includes the unified Byparr＋Camoufox browser routes and configuration migration recorded under 7.4.0, whose stable publication did not complete.

### macOS release gate fix

- Pass the prepared Camoufox dependency cache to isolated Byparr browser-test subprocesses, preventing native macOS gates from downloading the browser again on each launch and exhausting the request budget. Publisher profiles, cookies, and storage state remain isolated.
- Use two pytest workers in native macOS gates to bound concurrent browser and GPU-probe launches. Browser tests use the default runtime request budget while retaining navigation, original-response, persistent-state replay, and cancellation checks.
- Wait for real download events before clearing cookies and advancing popup/iframe automatic-validation tests, preventing the previous popup from overwriting the next stage's initial cookie state while retaining challenge-evidence and single-click assertions.
- Allow the native browser's graceful shutdown to finish after its protocol disconnect, so its owner does not terminate Firefox before profile cookies and localStorage reach disk.

## 7.4.0 - 2026-11-07

### Unified Byparr and Camoufox browser routes

- Use managed Byparr v2.1.0＋Camoufox for all browser publishers across articles, images, attachments, browser PDFs, preflight, and authentication, including Elsevier browser stages on macOS. Article and asset stages reuse the publisher context, manage their own pages, and release sessions on the owning thread.
- Handle supported Cloudflare interstitials automatically. Navigation and click monitors follow the original pages, popups, iframes, and redirects; solving is serialized within the same context, and GET recovery permits at most one bounded retry. Preserve actual Response/Download objects, operation events, request deadlines, and cancellation; login, payment, and other challenges retain their access restrictions.
- Prepare locked source and private dependencies on demand for source installs. Offline packages on supported platforms include complete upstream source, licenses, component manifests, digests, and adaptation notes in frozen snapshots, inventories, checksums, and SBOMs. Reuse Camoufox browser/fingerprint caches and provide unified post-install preparation and independent retries.

### Configuration migration

- Remove the FlareSolverr, system Chrome, and ChromeDriver routes. `PAPER_FETCH_<PROVIDER>_BROWSER_BACKEND=auto|camoufox|byparr` selects Byparr＋Camoufox; the old `flaresolverr` value fails explicitly and must become `auto` or `byparr`. Remove `PAPER_FETCH_CHROME_BINARY_PATH`; use `PAPER_FETCH_BROWSER_BINARY_PATH` for custom Camoufox executables. Replace old preparation options with `--prepare-byparr` or `--prepare-browsers byparr`.
- Preserve existing state ownership: PNAS and Elsevier on Windows/Linux x64 retain filtered JSON with `auto|byparr`; explicit `camoufox` and other supported platforms/providers use native persistent profiles. State mode is independent of the backend name, and authentication directories are never merged or migrated automatically. Existing FlareSolverr state and historical capture provenance remain intact.

### Dependencies and usage guidance

- Refresh compatible Python and formula Node locks, including cachetools 8.0.0, CycloneDX BOM 8.0.1, PyMuPDF/PyMuPDF4LLM/pymupdf-layout 2.1, Pydantic 2.14.3, and Ruff 0.17.4; widen cachetools and CycloneDX BOM compatibility ceilings. Update private browser components to playwright-captcha 0.1.5, FastAPI 0.162.0, and Starlette 1.10.0 with locked dependencies.
- Consolidate installation, browser, provider, extraction, and test guidance by topic. Correct Elsevier API-key/browser-state, arXiv enrichment, and AIP acquisition descriptions; streamline bilingual history and Skill guidance while retaining rule anchors, five presets, a self-contained Skill, and the PDF conversion-passthrough boundary.

## 7.3.6 - 2026-11-05

### Offline installation flow and logging fixes

- Prepare browsers automatically only once per installation. Limit terminal optional configuration and Windows component options to credentials, Ghostscript and libvips, keeping image tool installs off by default. Preserve the Windows five-line request protocol and explicit browser preparation for older callers.
- Keep the latest final result per component and display progress states only in real time. Report Python as ready or unsupported, remove resolved missing states from summaries and add a stable overall browser status that succeeds only when every selected supported backend is ready.
- Align Linux, macOS and Windows completion messages: clear stale results, show completion and result paths on success, preserve core installation and provide an independent retry command on failure or cancellation, and show a manual preparation command when skipped. Clarify that default browser preparation may use the network and that skipping affects installation only, preserving runtime on-demand preparation.
- Capture texmath `--version` output, remaining silent on success and showing diagnostics on failure. Report image tool readiness once with conversion evidence. Shorten only the known Canvas/WebGL random-readback warning during installation preparation, preserving fingerprint settings and other warnings.

## 7.3.5 - 2026-11-05

### Camoufox preparation fixes

- Fall back to the official GitHub Release API when the pinned fpgen model download request fails. Resolve the same tag and asset name and retain Camoufox's SHA-256 checks for the archive and every model file; checksum failures do not trigger fallback.
- Prepare the fingerprint model before starting Playwright for both ordinary and persistent contexts, including custom browser executables, so download failures do not leave a started Playwright connection to clean up.

## 7.3.4 - 2026-11-04

### Documentation and skill guidance

- Align CLI, MCP, browser backend and offline installation documentation with the implementation, correcting lazy browser preparation, successful-check reuse, bundled FlareSolverr components and state storage, Markdown save paths and cache persistence semantics.
- Simplify fixed preflight sequences, repeated confirmations and extra acceptance steps in the skill; consolidate duplicate rules while preserving the five presets, unified acceptance, provenance and lawful-access constraints.
- Remove version migration guides and historical closure records, describe current behavior throughout maintained documentation, and repair navigation and references while retaining the complete bilingual changelogs and regression evidence.

## 7.3.3 - 2026-11-04

### Browser preparation and offline components

- Prepare browser backends lazily when a provider actually needs them. Reuse successful online preparation checks for 24 hours while allowing failed or cancelled attempts to retry; prepare the Camoufox fingerprint model through the same managed path.
- Bundle pinned FlareSolverr source, private dependencies, licenses and component metadata in Windows/Linux x64 offline packages and frozen dependency snapshots. Validate bundled components locally instead of downloading replacement source at runtime; continue preparing browsers and matching ChromeDriver separately.
- Prepare all supported browser backends after installation, using shared dependency handling and the real backend for temporary blank-page checks. Add provider-declared backend selection and reuse common Playwright page operations across Camoufox and FlareSolverr.

- Build frozen browser components in a child process so Windows releases loaded native dependency files before temporary-directory cleanup.

- Preserve hidden upstream files when transferring frozen browser snapshots. Remove runtime-generated fingerprint model files and empty runtime directories during Windows uninstall while preserving user data and shared browser caches.

### Runtime and batch resource ownership

- Share CLI/MCP batch request ownership, DOI grouping, result fan-out and cancellation barriers through a common execution session. Keep child request state isolated, construct provider clients lazily and close browser sessions on their owning worker threads.

## 7.3.0 - 2026-11-03

### Publisher browser profiles and FlareSolverr

- Reuse publisher-scoped native Camoufox profiles across authentication, preflight and fetching, with exclusive profile locks, legacy JSON initialization and separate optional JSON exports. Reopen the same profile to verify authentication; bind capability caches to the browser state actually used and avoid reuse when its digest is unavailable.
- Add the system Chrome and pinned FlareSolverr backend for PNAS on Windows/Linux x64 and for Elsevier browser routes. Isolate source, private dependencies and version-matched ChromeDriver in the shared `flaresolverr/` cache, retain checksum/lock/atomic preparation, and clean up request-owned browser processes. macOS and other architectures retain Camoufox for PNAS and skip Elsevier browser routes.
- Prepare FlareSolverr after core installation on Windows/Linux x64, including upgrades and reinstalls. Add consent-based Debian/Ubuntu dependency and Chrome installation, noninteractive download preparation, a bounded temporary-state CDP/blank-page check, result summaries and an independent retry command. Failures or cancellation preserve core installation; online `--lite` and macOS skip this phase, while runtime repair remains available. Offline installers may use the network during this preparation phase.

### Elsevier acquisition and source fidelity

- Use API XML → FlareSolverr HTML → API PDF → FlareSolverr PDF acquisition while retaining actual response statuses, DOI/PII identity checks and shared-context article assets. Add ScienceDirect body, MathJax MathML, original-image and supplementary extraction with captured-source regression coverage.
- Preserve source section numbering, paragraph/list ownership, figure captions, bilingual abstracts, bibliography order and structural graphical abstracts across Elsevier HTML/XML output. Complete only missing reference DOIs after full-text acceptance through bounded, uniquely matched Crossref lookups; retain source citations and cancellation/deadline behavior.
- Advance extraction revision from 8 to 11 so prior extraction caches are reprocessed. Keep PDF output within the existing converter boundary and synchronize browser diagnostics, CLI/MCP contracts, bundled Skill guidance and the macOS adaptation contract.

## 7.2.6 - 2026-11-01

### Browser runtime selection

- Upgrade browser/full extras to `camoufox==0.5.9`. Let `official/prerelease` select the latest compatible stable or prerelease browser in upstream order; keep `official/stable` restricted to stable releases. Apply the same channel rule to local pinned builds while preserving version/SHA pins, custom executables, update intervals, locking and failure fallback.

### Dependency updates

- Refresh 23 compatible locked Python dependencies, including Pydantic 2.14.2, python-dateutil 4.0.0, PyObjC 13.0, pytest 9.2.0, mypy 2.4.1 and Ruff 0.17.3. Retain Playwright 1.62.0 and trafilatura 2.2.0 with their existing compatibility constraints.
- Allow the native dual-context gate to reuse compatible stable or prerelease builds, removing the obsolete addon-download hook while retaining runtime and fingerprint-model reuse.

## 7.2.5 - 2026-10-29

### Supplementary discovery and authentication fixes

- Preserve browser supplementary discovery failures with their original reason, message, details and source page. Continue the explicit-attachment fallback and download recovered files while keeping discovery incomplete; a missing article container remains compatible with attachment discovery on abstract and paywalled pages.
- Send the configured Elsevier API key for independent supplementary downloads only to the official HTTPS Object Retrieval endpoint. Filter candidate headers and remove sensitive credentials on cross-origin redirects in both ordinary and streaming downloads; retain per-file failures and discovery-only behavior.

### Reliable Linux and macOS updates

- Stage and validate the complete new runtime on the target filesystem before replacing managed components. Include the runtime marker, required installed-skill validation and enabled smoke checks before commit; restore the previous payload and original exit code on failure, and retain the backup location if rollback fails.
- Preserve papers, user files and environment files during runtime replacement. Clean backups and source/build leftovers after success, then update configuration and host integrations.

## 7.2.4 - 2026-10-27

### Independent supplementary acquisition

- Add `target="supplementary"` to the Python API and MCP single/batch fetch, and `--target supplementary` to the CLI. Verify paper identity and discover and download publisher-defined supplementary files, Source Data, Extended Data and multimedia without requiring article text or fetching the article PDF.
- Return structured material lists, per-file failures, discovery completeness and source provenance, with a separate Markdown index. Distinguish complete empty discovery from discovery failures and preserve unarchived lists when downloads are disabled. Isolate paper and supplementary cache requests and verify required local files before cache reuse.
- Allow supplementary browser indexes on abstract and paywalled article pages while preserving attachment access restrictions and the existing browser click-download path.

### Official installation updates

- Add `paper-fetch update` for official installations. Select the latest stable GitHub Release installer for the current platform and CPython ABI and verify its SHA256 before execution; current or newer installations skip the download.
- Upgrade Linux/macOS installations in place through the existing installer, reusing the current Python and configuration. Preflight macOS archives before extraction. On Windows, launch the verified graphical installer with the current installation directory preselected. Source and pip environments receive their existing update commands.

## 7.2.3 - 2026-10-25

### HTML capture and selection performance

- Capture ready PNAS, Science and Wiley HTML, title and URL together in the browser's main context on its owning thread. Recapture after provider page preparation, fall back to native capture on navigation races, and preserve cancellation and access-boundary handling.
- Reuse container scores and ancestor selections within one read-only DOM selection phase. Preserve stable ties and invalidate scores around refiners that can mutate the document.
- Set independent arXiv Atom metadata and source-asset request intervals to one second while retaining shared-worker pacing and Retry-After handling.

### Maintenance

- Streamline the bundled Skill and focused references with section-level guidance for presets, tool contracts and acceptance.
- Separate live browser preflight timing from fetch timing, preserve isolated MCP environments, and recognize explicit Elsevier access restrictions in the legacy-DOI live check. Add offline snapshot and scoring-reuse coverage and synchronize the macOS adaptation contract.

## 7.2.2 - 2026-10-24

### Browser update interval

- Share a rolling 24-hour managed Camoufox update-check record across fetch, authentication, preflight and direct preparation. Reuse a valid local browser within the interval; missing, damaged or incompatible runtimes are prepared immediately. Failed checks also count toward the interval, skipped checks do not extend it, and cancellation does not record completion. Recheck when the channel, version/SHA pin or Camoufox Python package changes.
- Validate the update record under the existing cache lock, including path ownership and timestamps. Invalid or missing records trigger a fresh check; record-write failures retain the preparation result and report diagnostics to stderr.

### PDF dependency compatibility

- Upgrade PDF extras to PyMuPDF 2.x and PyMuPDF4LLM 2.x, with PyMuPDF, PyMuPDF4LLM and pymupdf-layout locked to 2.0. Preserve upstream conversion output and existing asset-path handling without project-level formatting cleanup or content repair.

### Maintenance

- Refresh 25 compatible locked Python dependencies, including cachetools 7.2.4, filelock 4.2.4, idutils 1.7.1, platformdirs 4.13.5, Pydantic 2.14.1 / pydantic-core 2.50.1, python-dateutil 3.0.0, httpx2 / httpcore2 2.16.0 and Ruff 0.17.2. Retain trafilatura 2.2.0 and the Camoufox-compatible Playwright 1.62.0 lock. Resolve SoupSieve to 3.0.4 on Python 3.11.5+ and 2.10 on earlier Python 3.11 patch releases.
- Update pinned GitHub Actions to setup-python 7.1.0 and setup-uv 10.3.2.

## 7.2.1 - 2026-10-23

### Browser runtime updates

- Pin browser/full extras to `camoufox==0.5.8` and default managed browsers to `official/prerelease`. Select the latest compatible build for the current platform through Camoufox's official discovery, without upgrading the Python package. Preserve explicit channels, version/SHA pins and custom executables; migrate old active-only configurations under the existing cache lock.
- Check and prepare the browser at the start of every CLI, MCP and Python API fetch, including HTTP-only requests and cache hits. Prepare once before batch scheduling and reuse the result across children and browser launches; independent calls check again. Reuse a valid local browser when updates fail. Without a usable browser, retain the preparation error while allowing HTTP/cache work to continue, and report it if a browser is needed. Skip managed updates for core installs without browser dependencies and for custom executables; keep static diagnostics read-only and preserve cancellation and batch terminal records.

### Oxford inline figures

- Preserve Oxford figures at their source positions, including identifiers, captions and subpanels, without appending duplicate figure assets. Download each original image once, use available previews when original downloads fail, and retain explicit diagnostics and degraded acceptance for unavailable assets.
- Prepare a compatible prerelease browser and fingerprint model through the project preparer for the native dual-context gate.

## 7.2.0 - 2026-10-23

### Source fidelity and formula validation

- Validate source TeX with the bundled MathJax 4.1.3 engine before rendering. Preserve valid source commands, whitespace and environments; when validation fails, convert only the uniquely paired MathML from the same formula node and validate the result. Retain the original TeX and diagnostics when no valid fallback is available. Record validation errors, conversion backends and style degradations through existing quality and acceptance results.
- Bundle the validation worker, offline fonts, bbm and textcomp support with formula tools and offline installers. Keep the LitRoot reader and independent Markdown checker synchronized with the same engine. Preserve nested dollar signs, aligned equations, MathML spacing and control-word boundaries; render simple currency amounts as ordinary escaped text.
- Preserve HTML/XML source structure across headings, multilingual abstracts, paragraphs, lists, tables and notes, captions, scientific inline formatting, authors, references and back matter. Resolve retained citations and object links against verified source IDs and explicit aliases before DOM cleanup, keeping valid source-page targets when local anchors are omitted.
- Keep PDF Markdown within the existing pymupdf4llm conversion boundary, without project-level formatting cleanup or content repair. Refresh captured-source baselines and advance the extraction revision to 8 so prior extraction results are not reused as current output.

### Codex skill installation

- Install Codex skills under `~/.agents/skills/paper-fetch-skill` for user scope and `.agents/skills/paper-fetch-skill` for project scope; Windows uses the corresponding user profile directory. `CODEX_HOME` no longer selects the new skill destination, while MCP configuration keeps its existing location.
- Verify the new bundle before removing legacy copies in the same scope. Source installs also migrate the former custom `CODEX_HOME` skill path; uninstall handles new and legacy paths, and `--check` remains a read-only check of the new destination.
- Shorten skill discovery and entrypoint instructions, update UI metadata and browser preparation guidance, and retain a self-contained bundle with seven focused references and implicit invocation enabled.

### Maintenance

- Update locked certifi to 2026.10.19 to address PYSEC-2026-4320 reported by the release dependency audit.

## 7.1.1 - 2026-10-15

### Fixed — browser readiness and asset recovery

- Science uses one normal HTML attempt and checks actual reference target IDs for nonempty, extractable text. Batch reference and expansion-control reads within the existing 10-second preparation budget; retain missing-reference diagnostics when the budget expires.
- End AIP body polling when the governor validation URL and visible validation evidence both confirm a terminal challenge, preserving diagnostics in headed and headless modes.
- Download IOP body assets with at most two HTTP workers while keeping browser recovery and cleanup on the owning thread. After successful recovery, route pending assets on the same host through the verified browser path; retain cancellation and download-budget cleanup.
- Reuse IEEE original-image link indexes only within the same article document and invalidate them on navigation. Batch Taylor & Francis table-control reads and DOM injection while preserving per-table failures and existing limits.

### Maintenance

- Bound optional arXiv Atom enrichment to one request attempt with a 10-second I/O timeout; ordinary network failures preserve the fetched full text, while cancellation and access restrictions still propagate. Independent metadata queries retain their existing policy.
- Reuse HTML availability and paywall analysis within the current fetch, add request and browser-stage timing diagnostics, and hide runtime environment values from object representations.

## 7.1.0 - 2026-10-11

### Changed — browser supplementary downloads

- Science, Wiley, PNAS, IEEE, AMS, MDPI, Royal Society, Annual Reviews, ACS, IOP, AIP, and Taylor & Francis now download browser supplementary files by serially clicking existing article or attachment-directory controls. Click failures retain per-file diagnostics without falling back to direct HTTP or browser context requests. HTTP-only routes and body-image download policies retain their existing behavior.
- Accept download events and inline file responses only when they match the selected control target and its redirect chain. Record the click page, original link, and final URL; retain shared request deadlines, cancellation, byte/type checks, download budgets, and atomic file writes. Restore the article page, close owned popups, and remove listeners after each attempt.
- Preserve publisher-specific controls: Wiley supporting accordions, IOP attachment directories and IDs, IEEE media tabs and filename/attachment-DOI controls, Annual Reviews supplemental tabs, and MDPI visible links or supplementary modals. Reconcile IEEE tracking-query variants with the discovered attachment and retain MDPI's original versioned modal link.

### Maintenance

- Refresh compatible locked Python dependencies, including filelock 4.1.0, platformdirs 4.13.0, Pydantic 2.14.0 / pydantic-core 2.50.0, Ruff 0.17.0, SoupSieve 3.0.1, jsonpointer 3.2.1, pycparser 3.11, NumPy 2.5.4 on Python 3.12+, and ONNX Runtime 1.31.0. Keep trafilatura at 2.2.0 and preserve the Camoufox-compatible Playwright 1.62.0 lock.
- Update pinned GitHub Actions to upload-artifact 7.0.2, download-artifact 8.0.2, and setup-uv 10.3.0.

## 7.0.4 - 2026-10-08

### Fixed — Science reference loading

- Wait for delayed Science bibliographies and reference batches using DOM coverage checks and one native scroll. Keep expansion controls and polling within the remaining request budget, capped at 10 seconds; recover from expansion timeouts and report the actual missing reference targets when the budget expires.

### Maintenance

- Update locked Camoufox to 0.5.8 and document its paired browser, `official/156.0.1-beta.36`. Refresh compatible locked dependencies to cachetools 7.2.1, filelock 4.0.12, platformdirs 4.12.4, iniconfig 2.3.1, jsonpointer 3.2.0, opentelemetry-api 1.45.1, orjson 3.13.0, and tomli 2.5.0.
- Keep trafilatura at 2.2.0 with the existing `<2.3` limit: isolated checks confirm that 2.3.1 still changes Markdown escaping in inline LaTeX formulas and table references.

## 7.0.3 - 2026-10-05

### Browser runtime compatibility

- Update locked Camoufox to 0.5.7 and prepare the browser paired with the Python package (`official/156.0.1-beta.34` by default). Reuse an installed paired build without querying releases; a missing paired build no longer falls back to an older active browser. Explicit channel and version choices continue to override the default pairing.
- Keep browser probes read-only when selecting the paired runtime. The native macOS gate now prepares the paired browser and fpgen fingerprint model before validating both context modes. The model is downloaded into the fpgen package directory rather than bundled in Python wheels; complete preparation while that directory is writable before using the browser offline.

### Maintenance

- Retry `cabal update` up to three times when preparing texmath, waiting 2 and 4 seconds between attempts. Repeated update failures still stop Cabal compilation and prevent offline builds from accepting a missing texmath binary; compilation itself is not retried. Failed external tools now print a bounded log tail while retaining the complete temporary build log for release diagnostics.
- Refresh locked Python dependencies, including MCP 2.3.0, filelock 4.0.11, Ruff 0.16.10, and mypy 2.4.0. Camoufox now uses fpgen in place of BrowserForge. Restrict trafilatura to `>=2.0,<2.3` (locked to 2.2.0) because 2.3.0 changes Markdown escaping in existing formulas and table citations.

## 7.0.2 - 2026-09-27

### Dependency compatibility

- Allow filelock 4.x and Playwright below 1.64; update the development lock to filelock 4.0.4, Camoufox 0.5.6, and Playwright 1.62.0. Camoufox currently requires Playwright below 1.63. With Playwright 1.61 or newer, prepare Camoufox browser beta.30 or newer; reject incompatible browser candidates before download, and explicitly repin older pinned bundles. The native macOS gate now stages beta.30.
- Update the pinned Haskell setup action to 2.12.1.
- Refresh all resolvable Python dependencies and the npm lockfile, including MCP 2.2.0, Pydantic 2.13.5, urllib3 2.8.0, and xmldom 0.9.12. Upgrade setup-uv to 10.2.0, texmath to 0.13.3 with GHC 9.14.1 / Cabal 3.18.1.0, and the verified Windows embedded CPython / libvips assets to 3.13.15 / 8.18.7.

## 7.0.1 - 2026-09-27

### Fixed — publisher images and asset diagnostics

- Wiley body images and formula bitmaps now use serial image navigation in one dedicated Camoufox session, preserving original response bytes and matching each response to its navigation and loaded image. Formula assets run first; candidates share per-asset and request budgets, retain challenge recovery and preview-fallback evidence, and clean up on cancellation. This path no longer adds direct HTTP retries, canvas exports, or separate figure-page discovery. Existing formula semantics and acceptance criteria remain unchanged.
- Taylor & Francis image navigation now waits for response commit before validating image bytes, avoiding repeated `DOMContentLoaded` timeouts that could discard the original response and fall back to canvas output.
- Elsevier XML assembly now preserves downloaded figure, table, and supplementary-file timing, dimensions, download tier, fetcher, and provenance. Browser image diagnostics report the actual Camoufox backend instead of the string `"None"`.

## 7.0.0 - 2026-09-19

### Upgrade behavior

- Confirmed same-article paywalls and official full-text API entitlement denials now stop subsequent candidates, retries, PDF recovery, and asset downloads. When fallback is allowed, received abstracts and metadata retain their source and access diagnostics. Hidden notices, other-article notices, ordinary 403 responses, and individual asset denials do not establish a body restriction.
- PDF body content now follows the existing `pymupdf4llm` output without project-level formatting cleanup or content repair. Consumers should not depend on the previous adjustments to headings, whitespace, references, or tables. Supported local asset-path rewriting remains available.
- Extraction revision advances from 5 to 6. Results cached by 6.2.4 or older revisions no longer count as current extraction results; the first request after upgrade may fetch the paper again. Existing files are not proactively deleted. See the [7.0 migration guide](https://github.com/Dictation354/paper-fetch-skill/blob/v7.0.0/docs/migration-v7.md).

### Article and asset fixes

- Preserve HTML/XML inline semantics, headings, references, figures, tables, formulas, and back matter across supported publishers, fixing lost, duplicated, or misplaced content while retaining source identity and order. PLOS binds downloaded objects by article DOI and object ID; undownloaded objects retain official remote URLs, and partial downloads do not reduce the acceptance denominator.
- Tighten provider-local recovery for IEEE PDF wrappers, PNAS body readiness, Science reference expansion, and publisher image candidates within existing request budgets, access boundaries, and provenance contracts.

### Maintenance and compatibility

- Existing CLI/MCP parameters, five presets, and public result formats remain supported. The major-version behavior changes concern access termination, PDF output, and cache upgrades.

## 6.2.4 - 2026-09-13

### Added — optional offline setup

- Linux/macOS offline installers and the Windows EXE now offer an optional setup wizard after core installation succeeds: securely save Elsevier/Wiley credentials, detect or install supported system/image tools, and prepare Camoufox with a local blank-page launch check. Downloads and installations default to off; non-interactive and silent installs skip the wizard, and optional failures preserve the successful core installation.
- Linux supports separate APT choices for browser libraries and image tools; macOS reuses existing Homebrew. Windows pins verified official Ghostscript EXE and libvips ZIP assets, validates actual image conversion, and records tool ownership. Upgrades preserve credentials and optional tools; optional uninstall cleanup preserves user-added files and shared caches. Skipping Camoufox retains its existing launch-time preparation behavior.

### Fixed — Taylor & Francis formulas and figures

- HTML extraction now distinguishes formula references from inline math using explicit DOM semantics, preserves equation labels and subitem headings, and reports conversion losses through acceptance. Full-size official figures replace matching previews; the extraction revision advances to invalidate outdated cached extraction results.

## 6.2.3 - 2026-09-12

### Fixed — Wiley supplementary downloads

- Supporting-file links now activate through the page DOM as soon as they become visible, avoiding download stalls when the panel hides again during its opening animation. Downloads retain browser events, matching response metadata, and the shared request budget.

### Fixed — publication years in output filenames

- CLI and MCP automatic filenames now extract the first four-digit year not adjacent to other digits anywhere in the publication date, including `20 October 2020` and `October 20, 2020`. Missing or unrecognized years still use `unknown`; publication-date metadata retains its original value.

## 6.2.2 - 2026-09-09

### Changed — automatic Camoufox runtime preparation

- CLI, MCP, and library browser routes, browser preflight, and interactive authentication now prepare managed Camoufox immediately before browser launch. Unpinned runtimes check the selected channel for the latest compatible release; pinned runtimes only prepare the requested version and reuse a valid local copy without querying releases. Browser reuse does not repeat preparation, and browser-free requests do not check for updates.
- Failed update checks or installations retain a validated local runtime; a missing or unusable runtime reports preparation failure through existing provider error handling. Explicit executable paths remain user-managed, and missing Python dependencies still require installation by the user.

### Fixed — managed runtime safety and protocol output

- Preparation serializes shared-cache changes across processes, rechecks local state under the lock, and only repairs the validated target version directory. Failed updates restore the previous active configuration without purging the cache. Corrupt configuration, unsafe paths, and symlink/reparse points fail explicitly; managed macOS bundles retain their native launch layout.
- Download and preparation output goes to stderr, preserving MCP JSON-RPC stdout. `doctor` and `provider_status` remain read-only; installers still do not download browser runtimes, and offline packages do not include browser binaries. Browser documentation, agent/MCP guidance, and the macOS contract now reflect launch-time preparation.

## 6.2.1 - 2026-09-08

### Added — arXiv ancillary files

- `asset_profile=all` now downloads official ancillary files for the same paper and version on both HTML and PDF routes. Abstract-page identity checks pin unversioned inputs to an explicit version; later metadata enrichment preserves it. Attachments appear once in `Supplementary Materials`, with provenance and per-file failure evidence. The default `body` profile and requests that disable asset output do not perform ancillary discovery.

### Fixed — publisher supplementary downloads

- Wiley supporting files now download by clicking the matching link in the article browser session. Collapsed or redrawn panels are reopened within bounded waits; download events and matching responses supply file bytes and metadata. Missing links, blocked pages, and timeouts retain diagnostics within the shared request budget.
- Annual Reviews now retrieves official PDF and MPG attachments from the supplementary section after checking the parent DOI. Frontiers resolves relative supplementary filenames through the same article's supplemental-data API only when there is a unique match; unmatched files remain explicitly unarchived.
- AMS includes same-article supplementary links cited in the body and removes duplicate URLs. IOP accepts both `SM` and `supp` numbered attachment links. AIP ZIP links and Taylor & Francis download links now supply the intended attachment filename.
- Oxford Academic prefers links from the attachment section, excludes article PDFs and non-HTTP navigation, and deduplicates equivalent signed CDN links while retaining the complete download URL.
- Elsevier no longer downloads formula bitmaps already represented by MathML, merges duplicate accepted-manuscript PDF references, and uses the matched supplementary asset's local path when rendering links.

### Fixed — browser readiness and asset execution

- AIP article readiness can now wait up to 90 seconds within the remaining request budget, ending early when the body is stable and preserving timeout diagnostics and the remaining PDF fallback budget.
- Browser asset planning now receives the provider client, and Silverchair figure-page recovery stays on the caller thread for either supported browser backend.

## 6.2.0 - 2026-09-07

### Added — CLI progress and cooperative cancellation

- Single and batch fetches now support `--progress auto|text|jsonl|none` on stderr, preserving stdout for paper content or JSON. The default `auto` displays text only in a terminal; JSONL reports input-indexed stages, asset counts, and terminal manifest records.
- `--progress jsonl --control-stdin` accepts commands to cancel one input or the entire batch. Cancellation preserves completed results and original input order; duplicate DOI inputs retain shared work until all dependent inputs are cancelled. Terminal events follow output submission and worker cleanup, while final batch JSONL remains a single input-ordered result file.

### Fixed — Oxford Academic inline images

- Oxford Academic HTML now rewrites downloaded preview-image links to local asset paths before article-model conversion, keeping figures inline without duplicate images. Undownloaded images retain their remote links, and partial failures retain their acceptance evidence.

### Changed — paper skill discovery and reading guidance

- Skill descriptions now cover full-text retrieval and availability probes, including explicit paper candidates found by an agent searching for evidence to answer a question. The existing five presets now state their selection criteria.
- Batch guidance applies the 50-input limit before identity resolution, preserves original indices, and deduplicates canonical DOIs across chunks. Full reading and comparison tasks reuse qualified local text or fetch each paper with the existing reading preset; compact results and truncated bounded excerpts do not count as having read the full text.
- Availability-only tasks report per-item probe evidence, errors, and unscheduled states without requiring full-text acceptance or automatically fetching the paper. Fetch/cache examples explicitly select supported reference parameters; existing authorization, cache scope, output, and provenance boundaries remain unchanged.

## 6.1.6 - 2026-09-07

### Fixed — Nature extended assets and Wiley image retrieval

- Nature Extended Data tables and figures now belong to supplementary scope: `body` excludes them, while `all` retrieves them through the existing image download path. Table matching no longer assumes that the displayed table number equals the page URL number; legacy table images require matching page labels, article backlinks, image DOI, and table content context. Image tables retain their Markdown references, and missing extended assets retain provenance and structured failure evidence for acceptance.
- Wiley formula bitmaps now accept positive natural dimensions and require an exact match to the requested image URL, avoiding substitution with unrelated page images. Formula and figure image navigation waits for navigation commit and image readiness instead of image-document `DOMContentLoaded`.
- Wiley figures now prefer the publisher's full-size candidates and require the loaded image URL to match the current target during page export and image navigation. Preview fallback retains its source, dimensions, and full-size failure evidence, with `download_tier=preview` and `preview_accepted=false` so unified acceptance reports the quality downgrade.

## 6.1.5 - 2026-09-05

### Breaking — unified MCP probe entry point

- Removed the standalone `has_fulltext` MCP tool without an alias, reducing the tool count from ten to nine. Use `batch_check(queries=[query])` for a single paper and read `probe_state`, evidence, warnings, and item errors from `results[0]`; ambiguous candidates now live in the item error instead of the former single-tool top-level error.
- `batch_check` now accepts only `mode="metadata"`, which remains the default. Removed its article-fetch path while preserving schema-v2 metadata fields, input order, canonical-DOI deduplication, isolated item contexts, shared transport, provider-lane limits, cancellation, and progress. The Python `probe_has_fulltext` service and provider-catalog resource remain unchanged.
- Replace article checks with `batch_fetch` and judge each result by `acceptance`. For body checks without disk output, explicitly use `modes=["article"]`, `detail="compact"`, `save_markdown=false`, `no_download=true`, `prefer_cache=false`, `artifact_mode="none"`, and `strategy={"asset_profile":"none"}`, without `batch_results`. Existing `batch_fetch` defaults are unchanged.

### Changed — skill workflow guidance

- Determine task intent and request parameters before local/cache checks; temporary reading does not require selecting a cache directory. Preserve the five presets and reuse explicit user choices and existing authorization without repeated confirmation.
- Make reference reading and acceptance reporting depend on the task, clarify runtime preparation and access boundaries, and continue the requested summary, comparison, translation, or extraction after obtaining verified text.

## 6.1.4 - 2026-09-05

### Fixed — publisher browser and asset retrieval

- AIP now uses the normal HTML attempt without media interception or the Adzerk/Crossmark empty-script responses, preserving its existing non-persistent session and article readiness checks.
- IEEE original-image recovery now follows the matching article link in the shared browser session. Figures use the publisher viewer; table-image links open a temporary browser tab. Recovery validates the original response bytes and retains per-asset failure reporting and preview fallback.
- Springer/Nature now downloads known original-image candidates before requesting figure pages. Figure-page discovery runs only when needed, within the same asset resolution and budget; table-page completion and preview provenance remain intact.
- Science now associates the final page with the latest completed main-frame navigation response for the current candidate, matching URL and DOI. An initial denied response no longer overrides a subsequently loaded article; iframe and unrelated responses cannot replace the article status.
- PNAS now blocks only the exact sidebar metrics endpoint and reports `blocked_sidebar_metrics_count`. Three cold-session comparisons did not demonstrate a consistent speedup; browser page processing remains a performance limitation. The documented PMC browser-free experiment is not an implemented retrieval route.

## 6.1.3 - 2026-09-04

### Changed — provider and browser ownership

- Article provenance now resolves from each catalog route's declared source, with exact route-name selection and a compatibility path for PDF recovery payloads that only identify the route kind. Existing generic ACS, Science, and PNAS sources and the shared Wiley browser source remain unchanged.
- Browser landing-page, provider, and asset URL checks now reuse the catalog hostname matcher while preserving the distinct provider-domain, route-host, candidate-construction, and exact MDPI/Frontiers network boundaries.

### Changed — schema and repository maintenance

- MCP request schemas now share one exact optional-string normalization helper across fetch, batch, cache, and browser-preflight path fields; path values still trim only leading and trailing whitespace. Removed an equivalent no-op article-source rendering branch.

## 6.1.2 - 2026-09-03

### Fixed — asset completeness and provider pagination

- Standard provider fetches no longer impose a default 128-file asset cap; the per-file, aggregate-byte, pixel, and worker limits remain in force, and arXiv source archives retain their independent 128-regular-member traversal guard. Explicit finite file budgets are still enforced, fatal budget stops now return a timed failure for every admitted unfinished asset, and ordinary streamed figures no longer reserve a conversion output slot unless their payload is actually EPS or TIFF.
- IEEE reference retrieval now continues beyond 20 pages, stopping at the advertised count or on an empty, short, or duplicate page while respecting one wall-clock deadline. Landing pages that advertise references without a count now fetch them as well.
- Taylor & Francis dynamic CSV and embedded tables are hydrated in batches of 24 until all discovered tables are processed or the page deadline expires. Deadline truncation now reports the unfinished table count, and offline replay restores all bounded same-page table payloads.
- Async MCP fetches close each Camoufox manager on its owner worker thread on success, provider failure, and cooperative cancellation.
- Article rendering now recognizes metadata titles containing HTML emphasis as equivalent to Markdown-emphasized leading headings, preventing duplicate article titles.
- Offline package verification now uses the supported `paper-fetch fetch` subcommand for its DOI smoke test.

## 6.1.1 - 2026-09-02

### Fixed — ACS assets and AIP browser stability

- ACS HTML extraction now restores publisher figure-download links from the raw Silverchair body before asset discovery and deduplicates the resulting assets by identity, preserving access to the official image rendition when the cleaned article body omits those links.
- AIP browser attempts now neutralize the exact Adzerk and Crossmark widget script URLs with empty JavaScript responses. Other URLs and resource types continue normally, and a failed fulfill safely falls through, preventing intermittent third-party TLS stalls from blocking article readiness or producing insufficient-body results.

## 6.1.0 - 2026-09-02

### Fixed — audit consistency

- Batch MCP fetches now normalize optional string fields exactly like single fetches, including treating whitespace-only shared Markdown filenames as unspecified and recording the normalized request in manifests.
- Async inline-image fetches retain the existing internal article field in cache only when needed to reproduce requested images; old insufficient sidecars safely miss, while public structured content still hides unrequested articles.
- Provider results now propagate content updates made by asset hooks through article construction, workflow persistence, acquisition, and the returned provider content.
- Removed the unused KaTeX runtime dependency and installation check; the packaged Node workspace now contains only the MathML-to-LaTeX converter and its transitive dependencies while retaining KaTeX-compatible normalization goals.

### Breaking — command, MCP, batch, and manifest surfaces

- The CLI is now command-only: use `paper-fetch fetch ...`. The legacy root-level fetch flags, CLI `--no-download`, durable `--run-manifest` / `--resume`, and the `manifest audit|reconcile` commands were removed. Use `--artifact-mode none` when provider artifacts and assets should not be retained.
- CLI and MCP batches may write one final `batch-results.jsonl`; it is assembled in input order and committed atomically only after every input reaches a terminal state. Append-only attempts, run summaries, audit/reconcile, and resume semantics were removed, while in-batch canonical-DOI fan-out remains. Existing differing result files still require explicit `--overwrite` / `overwrite=true`.
- Schema-v2 manifest records now expose only the current `record_status`, `acceptance`, and `output_artifacts` contract. The legacy top-level `status`, `output_path`, and `saved_markdown_path` projection and legacy acceptance/cache migration shims were removed; old, unknown, or incomplete records now fail closed instead of being guessed or upgraded.
- Removed the `summarize_paper` and `verify_citation_list` MCP prompt templates. The fetch, resolve, check, and cache tools, static provider-catalog resource, and schema-v2 payload contract remain unchanged.

### Changed — browser and transport runtime

- Camoufox is now the single browser backend. Removed the backend selector, generic Chrome/CDP runtime path, automatic browser installation/repair/update, and the CLI/MCP/environment `browser_auto_prepare` controls. Fetch, auth, and preflight only use an already prepared runtime; run `python -m camoufox fetch` explicitly when setup is needed.
- Browser preflight no longer publishes short-lived HTML or route hints for a later fetch. Every fetch performs its own navigation and repeats identity, access-boundary, body, and asset acceptance; storage state remains the intentional reusable browser capability.
- Removed the `download_dir`-backed HTTP text cache, conditional disk revalidation, cache-stat/timing collectors, and their environment controls. HTTP GET reuse is now bounded to the current process, while request safety, redirect checks, retry policy, and asset limits remain enforced.

### Changed — MCP cache access

- Removed dynamic cache index/entry resources, cache resource-list notifications, and `batch_fetch` cache `resource_uri` fields. Cache access now uses `list_cached` / `get_cached` within an explicit `download_dir` scope; the static provider catalog resource remains available.
- Removed cache `refresh` / `rescan` modes and loose-file discovery. Sidecars, Markdown, and assets are registered incrementally when written; reads trust only the current scoped index plus current DOI, capability-scope, stat, and hash evidence, without silently migrating an old or damaged index.

### Changed — provider and library contracts

- Built-in providers now load from one fixed, validated bundle list. Dynamic registration, import-order precedence, overlapping identity priorities, route-union compilation, and the generated provider catalog/route governance layer were removed; runtime network policy is compiled from an exact declared route.
- Removed compatibility-only positional constructors, broad keyword adapters, legacy urllib asset request injection, generic browser/PDF launch arguments, cross-request singleflight, and other private wrapper imports. Current typed request/options objects and one-batch DOI deduplication remain the supported paths.

### Changed — maintainer tooling and verification

- Replaced the manifest/review/scaffold onboarding tree with the smaller `docs/adding-a-provider.md` workflow: define a runtime bundle, add provider-local tests, and add representative golden replay evidence. Removed provider governance/drift/canary generators, recursive onboarding automation, Markdown-review sidecars, live benchmark tooling, and generated route documentation.
- Removed the repository coverage-focus and complexity-budget gates and the packaged `paper_fetch_devtools` quality layer. Deterministic unit, integration, provider replay, package, platform, and live-test entry points remain in their respective scopes.

### Changed — release and dependency CI

- Removed the mutable `dependency-latest` rolling release, its dedicated token path, and cross-revision release-tooling overlays. Stable `v*` releases continue to publish the nine offline installers with `SHA256SUMS`, frozen dependency evidence, SBOMs, secret scanning, and provenance attestation.
- Removed the non-gating provider canary state machine; explicit legally authorized checks remain available under `tests/live`.
- Locked dependency audits now export all extras and fail directly on every `pip-audit` finding, without an empty waiver framework.
- Python 3.11 and 3.14 boundary jobs now build one wheel per Python version and smoke both isolated core and full installs.
- Python distribution verification now checks archive safety, required package/Skill payloads, metadata, entry points, and complete wheel `RECORD` coverage without maintaining a checked-in exact source inventory. The legacy repository-root Windows PowerShell bundle installer was removed; the supported Windows release artifact remains the native setup executable.
- Offline builders/installers verify bundled and installed Skill copies through `scripts/skill_integrity.py`. `doctor` now reports runtime/provider health only; `--install-root` and installation-provenance status were removed.

## 6.0.4 - 2026-08-29

### Fixed — release metadata

- Synchronize the generated provider catalog's tool version with 6.0.4 project metadata, preserving the XML whitespace behavior introduced in 6.0.3.

## 6.0.3 - 2026-08-29

### Fixed — XML inline whitespace rendering

- The shared Elsevier/JATS inline renderer now collapses publisher XML source-formatting whitespace before assembling Markdown. Line wrapping around operators and emphasis no longer produces malformed emphasis or unintended block parsing, while explicit break elements and the existing split-italic subscript repair keep their established behavior.
- JATS paragraphs containing embedded blocks apply the same whitespace rule.

## 6.0.2 - 2026-08-29

### Fixed — Frontiers original figures and rolling releases

- Frontiers body figures and formula images now discover and prefer the publisher's exact original `xml-images` URLs from the canonical landing page. Graphic-stem matching keeps downloaded full-size assets and rendered Markdown aligned while avoiding incorrect article-directory URLs derived from DOI suffixes.
- The rolling dependency release `publish` job now checks out the triggering workflow commit before invoking repository release scripts. The checkout is pinned, shallow, and credential-free, preventing `prepare_release_assets.py` from failing with `Errno 2`; a structured workflow contract protects the ordering and trust boundary.

## 6.0.1 - 2026-08-28

### Fixed — release publication

- Stable publication now relies on the already verified remote tag instead of redundantly passing its commit as `target_commitish`, avoiding GitHub's workflow-permission rejection when the default branch advances while an immutable-tag release is building.

## 6.0.0 - 2026-08-28

### Changed — explicit capabilities and smaller public surfaces

- Provider routes are now the sole capability source. Provider-level browser flags, automatic route synthesis, source-tree discovery, and dynamic registry monkeypatching were removed; built-in providers use one explicit lazy module list.
- MCP tools keep their existing `CallToolResult.structured_content` success and error payloads, but `tools/list` no longer publishes `outputSchema`. Browser capability and preflight status are derived from runtime owners, and unknown preflight states now fail closed.

### Changed — repository tooling and releases

- Removed recursive onboarding agent orchestration, private DAG/state/retry machinery, evidence sidecars, geography-only live/report tooling, and production-wheel Markdown review/quality diagnostics. Deterministic review bootstrap/finalization and golden fixture manifests remain the repository-owned workflow.
- Stable releases now publish exactly nine installers plus `SHA256SUMS`. Rolling prereleases publish those installers, `dependency-manifest.json`, and `SHA256SUMS`; wheel, sdist, inventory, SBOM, and per-target evidence remain build-time verification inputs.
- Replaced the historical macOS ledger with a compact support, safety, and evidence contract derived from project metadata, workflows, the installer manifest, and the release asset owner.

See [docs/migration-v6.md](https://github.com/Dictation354/paper-fetch-skill/blob/v6.0.0/docs/migration-v6.md) for incompatible import and protocol changes.

## 5.6.1 - 2026-08-27

### Fixed — Windows release lifecycle

- Fixed the native Windows release failure caused by Inno Setup's two-phase uninstaller: the first process could return while its TEMP-hosted second phase still owned `unins000.exe`, so the overwrite upgrade created `unins001.exe` and the final residue check raced that delayed cleanup.
- Replaced the installer-side registry/command-line parsing with the official UninsIS 1.7.0 helper pinned by release, DLL, and license digests. The Windows builder verifies those files before Inno compilation and records the setup-time component in the offline manifest, dependency evidence, and CycloneDX SBOM. Upgrade now fails closed until the old uninstaller has completed and deleted its original executable, while preserving `offline.env` and other user-owned content; the LGPL license and provenance notice ship with the installer.
- Strengthened the native lifecycle gate to require exactly one post-upgrade `unins000.exe`, then wait up to 60 seconds for both the Inno success log marker and every `unins*.exe/.dat/.msg` file to disappear before applying the exact uninstall residue allowlist.

## 5.6.0 - 2026-08-27

### Skill integrity and release builds

- Address the static Skill bundle by the SHA-256 of its sorted regular-file inventory. Source, staging, offline manifests, and host installs reject missing, extra, changed, symlink, and special entries; the canonical `agents/openai.yaml` ships directly.
- Add read-only installer `--check` for Codex/Claude/Antigravity and expected/actual Skill versions to `doctor`, with readiness failure for missing or drifted active copies.
- Build wheel/sdist through reusable `package.yml` with exact inventory and independent install smokes. Stable release runs artifact builds rather than ordinary CI, in parallel with the nine-target frozen resolver; it neither runs nor waits for remote unit/ordinary CI. Full local unit verification remains the release-operator prerequisite. Ordinary CI uses reusable `verify.yml`, and Dependency refresh runs the full unit suite.
- Peel stable tags to one immutable SHA used by packaging, dependency resolution, offline builds, checkout, attestation, and publication, and reject tag drift before publication.
- Resolve frozen Linux x86_64 and macOS arm64 CPython 3.11–3.14 plus Windows x86_64 CPython 3.13 snapshots. Record actual staged dependencies and content digests in per-target manifests and CycloneDX 1.6 SBOMs; use the locked project venv for evidence generation.
- Pin and verify the Windows CPython 3.13.13 embeddable archive. Validate the exact stable asset set: wheel/sdist and inventory, nine installers, eighteen target evidence files, merged dependency manifest, and basename-only `SHA256SUMS`.
- Verify final Windows EXE install, overwrite upgrade, user-data preservation, and uninstall; only `offline.env`, `downloads/`, and the owned user-data sample may remain. Keep the Windows tooling overlay pinned as one revision.
- Refresh compatible dependencies including MCP 2.1.1, imagesize 2.0.1, and PyMuPDF4LLM 1.28.2; declarations retain rolling compatibility ranges while lockfiles retain exact resolution.

### Network, cache, and output behavior

- Restore hostname-based urllib3 pools with public HTTP(S) URL checks, safe redirects, sensitive-header stripping, and standard cookie-jar scope. Provider catalog hosts do not grant implicit network authorization; explicit caller allowlists remain enforced.
- Redact secrets in human/MCP logs and artifact uploads. Route notifications by request ownership and prevent late workers from logging into closed or overlapping sessions.
- Bind private caches to credentials and browser state actually used, including provider, backend, canonical state path, and final digest. Check local DOI sidecars before enrichment, enforce private-to-public fallback only, and re-evaluate capabilities on resource reads. Reuse unchanged-file fingerprints and incrementally update cache indexes.
- Publish artifacts, sidecars, Markdown, indexes, and run summaries with path locks, unique staging, fsync, and atomic replacement. Equal non-overwrite writes are idempotent; differing content requires overwrite. Cancellation fences later commits and progress.
- Preserve input order, indices, provider lanes, and terminal/not-scheduled states in batches. Share canonical-DOI work with cancellation-isolated waiters. Resume manifests keep fetch/output semantics immutable while permitting execution-policy changes.
- Share an article asset budget: 128 files, 32 MiB per file, 256 MiB total, 64 million pixels, and at most four workers. Bound browser-returned bytes, archive traversal, conversion, and atomic writes; stop and clean staging on fatal budget failures.
- Declare body-asset routes with a 20-second direct attempt and two-worker route cap. After one direct probe per host, reuse a verified browser path within that article. Preserve per-asset timing, original/preview provenance, and explicit degradation reasons.
- Add optional `require_local_body_assets` and `require_full_size_body_assets` across Python, CLI, MCP, cache, and manifests. Both default false; full-size implies local, and unmet requirements degrade acceptance without discarding acquired full text.
- Accept Wiley 401/403 candidates only after stable body readiness, exact DOI match, no challenge/no-access signal, and full-text acceptance; preserve the actual HTTP status. Align PNAS readiness with its body parser and retain bounded ACS empty-shell diagnostics.
- Compile route timeout, retry, pacing, acceptance, and concurrency policies from the catalog. Pace arXiv Atom/source requests at one per three seconds within a shared transport scope. Strong identity evidence controls access-boundary termination; DOI-less acceptance requires a verified unique canonical landing identity.
- Complete MCP v2 cache asset facets and batch `route`/`failure_code` fields. Add provider replay shards, route-specific evidence waivers, coverage gates, and a non-blocking scheduled canary for four public direct routes.

## 5.5.0 - 2026-08-25

### Added — exact acquisition provenance

- Kept the legacy `source` scalar unchanged and added `acquisition={provider,route,representation,transport,fallback_used}` to fetch envelopes, articles, Markdown front matter, acceptance, manifest v2, MCP fetch/cache/batch payloads, and cache-index entries. Exact route and transport facts come from the provider route catalog; unavailable facts remain `null` and make provenance partial instead of being guessed from `source`.
- Raised the fetch-envelope sidecar version to 5 so pre-acquisition v4 sidecars are reported as stale and refetched, while existing Markdown files remain readable with `acquisition=null`. Provider waterfalls now stamp the winning catalog route without changing established public `source` values or legacy source-trail markers.
- Required complete provenance to agree with the catalog route, source owner, and structured fallback trace; manifest auditing now detects Markdown acquisition drift. Generated route documentation exposes `api|browser|http`, success traces retain the exact winning route, and the additive contract is covered by core CI without changing manifest or MCP schema v2.

### Fixed — formula assets, equation fallbacks, and Markdown links

- Fixed Wiley/Atypon display equations whose empty MathML exposed only a numbered label: structured TeX still wins, otherwise the official formula image is used before visible text; label-only equations remain explicitly unavailable instead of becoming pseudo-math, and complete display-math blocks survive Markdown post-processing.
- Allowed explicit formula URLs such as `math-N`, `_IEqN`, and `_EquN` inside figure captions to enter formula asset discovery while preserving the main figure and leaving ordinary equation-related graphics classified as figures. Publisher-supplied bitmap-only formulas remain truthful `download_tier="preview"` assets but are accepted previews, so intrinsically small or duplicate formulas no longer raise placeholder or fidelity-degradation issues; real payload and path defects remain diagnostic.
- Reconciled Springer/Nature `media.springernature.com/lwNN/...` rendition aliases with their `/full/...` downloads before asset acceptance. A successfully archived formula or figure is now counted once as a local logical asset instead of leaving a duplicate remote-only record that falsely degrades Manifest audit with `missing_path` and `asset_below_request`.
- Stopped root-relative publisher assets from being rewritten as nonexistent `../../cms/...` paths. Only existing local files become relative links, downloaded assets still take precedence, and unmatched `/cms/...` links use a valid publisher landing page to remain complete remote URLs or stay unchanged when no valid base exists. Preview fallback warnings are now asset-neutral.

## 5.4.1 - 2026-08-19

### Fixed — compatible Camoufox offline snapshots

- Raised the supported Camoufox line to `>=0.5.5,<0.6` and refreshed the development/CI lock to 0.5.5.
- Removed the POSIX offline builder's Camoufox-only exact `uv.lock` override. Offline builds now derive the selected version from the resolved wheelhouse while still requiring one Camoufox wheel and verifying wheel metadata, the installed distribution, and the recorded manifest version agree. This prevents frozen rolling snapshots containing a newer compatible Camoufox wheel from being rejected by an older source lock.

## 5.4.0 - 2026-08-18

### Added — on-demand Camoufox runtime preparation

- Added first-use preparation for the managed Camoufox browser runtime on CLI browser paths. `paper-fetch fetch`, `paper-fetch auth`, and `paper-fetch browser-preflight` now prepare a missing runtime only when browser work is actually requested, using the official Camoufox CLI for installation, repair, and update checks. Valid runtimes are checked at most once every 24 hours, and a failed update continues with the existing valid runtime.
- Added structured preparation progress, a 900-second child-process deadline, cooperative cancellation, failure cooldowns, and a cross-process file lock so concurrent commands share one installation attempt. Runtime probing rejects managed paths that escape the Camoufox root or traverse symlinks/junctions before any repair is attempted.

### Changed — explicit browser networking policy

- Added `--browser-auto-prepare` / `--no-browser-auto-prepare`, `PAPER_FETCH_BROWSER_AUTO_PREPARE`, and MCP request-level `browser_auto_prepare` controls. CLI browser commands default to enabled; MCP tools and direct library calls default to disabled so service and embedded modes never acquire browser binaries merely by being invoked.
- Kept explicit custom browser binaries outside managed-runtime mutation, and kept static diagnostics, `provider_status`, offline installers, and offline package verification free of browser downloads. Synchronized the Linux, Windows, and native macOS CI contracts, regression coverage, operator documentation, and bundled skill guidance with the new boundary.

## 5.3.2 - 2026-08-17

### Changed — formula and release integrity

- Updated KaTeX from 0.18.1 to 0.18.4 in both development and bundled formula manifests and lockfiles, incorporating settings-object prototype-pollution hardening and parser fixes. The machine contract and unit tests now reject declaration or lock drift between the two copies.
- Update pinned `actions/attest-build-provenance` from v4.1.1 to v4.2.2, retaining its subject-path interface.

## 5.3.1 - 2026-08-10

### Fixed — Wiley browser access detection

- Fixed Wiley full-text and Open Access pages being classified as `publisher_paywall` solely because the current header places `Institutional login` within the first 1,000 visible characters. Once the existing provider body-readiness check confirms substantive article content, navigation-only paywall and not-found text is deferred to the body-aware availability assessor; challenge pages, HTTP 401/402/403, HTTP 404, explicit access denial, and abstract redirects still fail closed.
- Kept `Institutional login` as a generic access-gate signal for pages without substantive body readiness, and added end-to-end Wiley browser-preflight, shared signal, Linux CI, native `macos-15`, and macOS adaptation-contract regressions.

## 5.3.0 - 2026-08-10

### Added — browser reuse and observability

- Added bounded, one-shot in-process reuse of accepted preflight HTML for PNAS, AMS, MDPI, Royal Society Publishing, Annual Reviews, ACS, IOP, and Taylor & Francis. Cache entries are bound to the provider, normalized DOI, candidate URL, and browser runtime fingerprint; formal fetches still re-run metadata, Markdown/asset extraction, and acceptance, while challenges, empty shells, PDF fallbacks, failed pages, and uncommitted storage state are never reused. PNAS and AMS also retain short-lived, DOI-scoped hints for the last accepted provider route.
- Added browser diagnostics for navigation counts, blocked resource types and requests, readiness budgets/results, preflight reuse, and candidate reordering. Catalog live tests now retain matching timing evidence and an observational PNAS preflight-plus-fetch target without turning performance variance into an access-boundary failure.

### Changed — browser and asset performance

- Made browser loading policy provider-specific: the eight opted-in providers block only image, font, and media requests while preserving document, stylesheet, JavaScript, and API traffic. PNAS now uses one complete navigation with canonical candidate ordering and an eight-second body-readiness budget; MDPI retries incomplete intermediate HTML candidates before PDF fallback, and Royal Society Publishing recognizes its current Silverchair article containers without a fixed wait.
- Preferred direct high-resolution figure URLs from download/media links, `srcset`, and original-image attributes for ACS, Annual Reviews, and Royal Society Publishing. Missing originals are discovered serially through one runtime-owned Camoufox figure page with a two-second wait and URL memoization, after which direct asset downloads retain their normal concurrency.
- Batched same-origin Taylor & Francis CSV table hydration with four bounded workers, a shared total deadline, stable input ordering, and per-table embedded-data fallback instead of issuing each table request sequentially.
- Extended regular Linux and native `macos-15` CI with the same non-Science browser performance and asset-regression gate, and synchronized the macOS adaptation contract, audit, and maintenance documentation.

### Fixed — runtime isolation and supplementary assets

- Kept AIP Camoufox cookies and storage state within the owning `RuntimeContext`; cold HTML retries can reuse their transient seed inside one fetch, but preflight HTML, cookies, and storage state are no longer published across runtime-fingerprint boundaries.
- Memoized IEEE multimedia discovery and IOP supplementary-index resolution within each request context using canonical, redacted URLs. Rotated signing parameters no longer trigger duplicate discovery/download work or leak into cache keys, and IOP deterministically reuses both successful index parsing and stable extraction failures.

## 5.2.1 - 2026-08-08

### Changed — build and release integrity

- Added an independent `uv lock --check` quality gate so stale project-version, dependency-declaration, or lock metadata changes fail CI before the remaining static checks.
- Update pinned `haskell-actions/setup` from v2.11.0 to v2.12.0, including GHCup 0.2.6.2 while retaining GHC 9.10.3, Cabal 3.12.1.0, and texmath 0.13.2.

## 5.2.0 - 2026-08-07

### Added — Taylor & Francis Online

- Added Taylor & Francis Online (`tandf`) support with browser-rendered article HTML, bounded same-origin CSV and already-loaded same-page table-payload hydration, browser-seeded PDF fallback, provider-managed abstract-only degradation, figures, MathML formulas, supplementary material, and references.

### Fixed — Taylor & Francis browser setup

- Added a verified open-article target for `paper-fetch auth tandf` and `paper-fetch browser-preflight --provider tandf`, so their default invocation no longer fails during target resolution when `--url` is omitted.
- Classified article-scoped Taylor & Francis CMS figure renditions as accepted previews, including valid wide figures that fall outside the shared dimension threshold, so body-asset acceptance does not report a false fidelity loss.

## 5.1.1 - 2026-08-06

### Fixed — Elsevier XML fidelity

- Restored Elsevier formulas that expose only a `link` locator by resolving the
  highest-fidelity official object image at the formula position. Downloaded
  local assets remain preferred, remote official URLs support no-asset mode,
  and image fallbacks retain explicit degraded-quality accounting without OCR.
- Parsed each CALS `tgroup` with its own column model across the Elsevier and
  shared JATS paths. Multiple source groups now render in order under one
  caption, preserve source prefixes and rows, and report degradation only for
  groups that actually require a readable-list fallback.

## 5.1.0 - 2026-08-06

### Fixed — batch request deadlines

- Fixed CLI and MCP batches consuming each paper's request deadline during
  upfront identity resolution and provider-lane queueing. Each fetch worker now
  starts with a fresh request budget while retaining its item-local resolution
  cache and shared transport, preventing browser routes from incorrectly
  falling back to metadata-only solely because the batch waited before fetch.

## 5.0.1 - 2026-08-04

### Changed — dependency compatibility

- Upgraded the locked `trafilatura` release to 2.2.0 and synchronized the Royal
  Society Publishing table golden contract. Literal pipes in statistical table
  headers now remain valid GFM `\|` escapes instead of being parsed as extra
  columns.
- Refreshed the locked compatible dependency graph to
  `apify-fingerprint-datapoints` 0.14.0, `cachetools` 7.1.7, `cffi` 2.1.1,
  `coverage` 7.15.3, `cryptography` 50.0.0, `filelock` 3.32.2, `isbnlib2`
  3.11.21, `pip` 26.2, `ruff` 0.16.1, and `uvicorn` 0.52.1. The
  `cryptography` update fixes `CVE-2026-69247` and restores a clean audit of
  the fully locked dependency graph.

## 5.0.0 - 2026-08-03

### Added and breaking changes

- Rebuild the macOS adaptation against v4.1.0 (`fc3bd96e8d781667a2e86e90dc6e8e35a8a26fa7`), with a machine-readable contract and portable Windows/WSL gates. `/mnt/*` WSL checkouts provide static evidence only.

- Upgrade MCP success/error and acceptance payloads to schema v2. `FetchEnvelope.trace` becomes the sole complete trace owner; retain `article_type`, `preview_accepted`, and stable asset issue codes. Schema-v1 consumers must upgrade; old v1 fetch-envelope caches remain read-only migratable.

- Remove the advertised but unimplemented IOP XML/TDM route; expose executable HTML, PDF, metadata, and supplementary capabilities only.

### macOS and offline packaging

- Require macOS 15.0, standard-GIL CPython ABI/architecture, exact checksummed regular-file inventories, and recursive quarantine checks before user integrations change. Reject payload symlinks, unlisted files, unsafe staging/purge targets, and unowned upgrades; preserve user configuration and Zsh symlinks, and publish artifacts atomically.

- Build macOS arm64 CPython 3.11–3.14 on `macos-15`, verifying native installs, relocatable texmath Mach-O closure, ad-hoc signing, safe archive extraction, canonical `LC_RPATH`, recursive `xattr`, and bundled Playwright Node execution. Portable Windows/WSL results do not replace native macOS evidence.

- Regular native CI prepares official Camoufox `152.0.4-beta.28`, checks filesystem aliases, and serially starts temporary/persistent contexts after managed-cache validation. Authenticate release discovery with the workflow read-only GitHub token to avoid anonymous API limits.

- Keep `camoufox>=0.5.4,<0.6` with concrete versions from `uv.lock`; verify wheel/installed metadata and record the version. Immutable-tag rebuilds must pass the source Mac contract. Tooling overlays require full commit SHAs, copy exact packaging paths without wheel source, and record source/tooling revisions separately.

- Declare core `packaging` and run contract validation in the locked environment. Fix prepared official macOS app launches by keeping managed bundles out of custom-executable handling; explicit executable overrides remain supported.

- Unify `/var` and `/tmp` cache scopes with their `/private/...` aliases while rejecting in-scope symlinks and out-of-scope files. Use a 16-character normalized-query SHA-256 filename fallback when CLI batch results lack title/DOI, avoiding `unknown_unknown_article.*` collisions without exposing query URLs.

### Runtime and providers

- Remove scheduled/manual live publisher/MCP, provider-drift, and full golden workflows; keep local opt-in entry points. Publisher live acceptance requires body assets and declared source/trail outcomes; protected IEEE GIF checks remain a separate authorized suite, and shared external state runs serially.

- Preserve confirmed challenge/paywall/access-boundary reasons through later navigation failures, exhausted deadlines, and provider PDF waterfalls. Reject Springer/Nature `Client Challenge` shells (including `_fs-ch-`) as provisional articles and wait for stable MDPI body DOM before accepting HTTP-200 pages.

- Wait up to 15 seconds for a matching IEEE `#article`; classify persistent AWS WAF HTTP 202 as `aws_waf_challenge` without rejecting recovered pages. Ignore `captcha` and access tokens in hidden script/template content, retain visible challenges, and leave page REST requests enabled.

- Carry provider-scoped transient cookies from AIP fast HTML to normal retries without persisting unaccepted state. Retry the next existing URL after `empty_article_shell`; preserve attempt/readiness diagnostics and leave the remaining deadline for PDF fallback. Fix deadline initialization and AIP/Science/preflight readiness classification.

- Read nested `browser_runtime.available` in live gating, isolate provider state, and reuse prepared Camoufox dependencies across test isolation. Keep startup progress off MCP stdout and retain privacy-safe diagnostics even before page creation or on terminal failure. Propagate request-scoped formula configuration to implicit MathML conversion.

- Return `status=ok` and compact seven-facet acceptance for single MCP fetches. Correct body-only asset accounting, reconcile IEEE small/large variants by logical identity, recover Silverchair originals without cross-thread page access, and distinguish download, fidelity, placeholder, and remote-only asset outcomes.

- Treat safely expanded HTML/JATS/CALS spans as table normalization without false layout warnings; preserve malformed-grid degradation and invalidate old extraction caches. Reuse cookie-aware Springer/Nature HTTP with one fresh-session `cookies_not_supported` retry, preserving Research Briefing type and valid authorless articles.

- Remove trace triplication and warning-count quality downgrades, retaining ordered real retry codes. Diagnose inactive source `.venv` and incompatible MCP versions. Add separate browser/DOM/HTTP/retry/asset/render timings and nearest-rank summaries: observed for one sample, p50/p95 for repeated samples.

### Offline browser boundary

- Offline packages contain Camoufox/Playwright Python dependencies, not browser binaries. Fetch does not download them automatically in this release: prepare with `python -m camoufox fetch` while online and run `paper-fetch browser-preflight` before restricted-network use. Fully network-isolated native macOS browser operation is not claimed.

## 4.1.0 - 2026-07-29

### Added

- Introduced route-level provider contracts and governance: the runtime catalog now records route order, availability, browser requirements, timeouts, concurrency, rate policy, acceptance, and asset scope; generated route/catalog snapshots, route-family golden replay coverage, expiring evidence waivers, and scheduled corpus/provider-drift checks keep code, manifests, fixtures, and docs aligned.
- Added shared typed failure diagnostics, route-attempt timing summaries, remote JSON root/schema guards, fail-closed public URL validation, and a configurable PDF transfer ceiling so provider, HTTP, workflow, CLI, manifest, and MCP surfaces retain the same machine-readable failure facts.

### Changed

- Upgraded the required MCP Python SDK from 1.x to `mcp>=2,<3`, migrated the server and protocol-model accessors to the v2 `MCPServer` API, replaced the custom stdio pump with the official transport, and retained both legacy 2025 handshake compatibility and modern 2026-07-28 protocol/resource-subscription support.
- Reworked FetchEnvelope caching around DOI plus request fingerprint variants and one-way credential-capability scopes; public, token, and browser-state requests can coexist without overwriting or leaking into one another, while compact cache projections retain deterministic request and acceptance evidence.
- Centralized publisher identity, route discovery, batch lane concurrency, browser capability, and source ownership in the runtime provider catalog; versioned PLOS journal routes, Springer site-family profiles, and direct-first Frontiers canonical routes now expose explicit diagnostics instead of relying on scattered heuristics.
- Hardened the shared HTTP/cache runtime with credential-scoped identities, non-persistence of sensitive/private responses, redacted redirect diagnostics, indexed disk-cache reconciliation and pruning, bounded transient retry categories, and host/provider cooldown waits that release concurrency slots.
- Expanded provider extraction and asset handling across Frontiers, Oxford Academic, IEEE, IOP, PLOS, Springer, and Wiley, including stronger JATS identity/body validation, direct-first assets, explicit unarchived supplementary records, selected-browser state propagation, and route-specific PDF recovery.

### Fixed

- Prevented browser/PDF fallbacks from accepting challenge or non-PDF responses, exceeding shared deadlines and transfer limits, crossing origin or credential boundaries, or leaving partial artifacts after cancellation and failed downloads.
- Corrected JATS formula, table, figure, reference, and supplementary rendering so provider identity mismatches fail closed, semantic losses remain visible, and content/assets cannot be promoted to complete acceptance without the required evidence.
- Returned discarded redirect and failed HTTP responses to the blocking connection pool after closing them, preventing concurrent Springer figure discovery from exhausting every connection slot and hanging fetch or offline-release smoke checks.

## 4.0.2 - 2026-07-28

### Fixed

- Unified HTML, JATS, and Elsevier/CALS table conversion behind a provider-neutral cell/grid normalizer; flattened multi-row headers, supported named CALS spans, preserved full-width groups, expanded safe rowspan/colspan semantics, and retained irregular grids as readable lists with accurate fallback/layout diagnostics instead of semantic-loss misclassification.
- Corrected Royal Society Publishing Silverchair figure extraction to preserve signed CDN originals from `DownloadImage.aspx`, model `/view-large/figure/` as an HTML discovery page instead of an image, reject cross-figure grouped-slide URLs, and use selector-driven viewer fallback before preview degradation.
- Follow bounded PLOS manuscript redirects to signed Google Cloud Storage XML, while redacting all `X-Goog-*` query values and excluding credential-bearing redirect responses from HTTP caches.
- Restored AMS to the shared Camoufox HTML and browser-seeded PDF workflow so AWS WAF HTTP 202 verification pages are classified as challenges; stateless fetch remains allowed, while `paper-fetch auth ams` and `PAPER_FETCH_AMS_STORAGE_STATE_JSON` provide optional reusable browser state.
- Migrated ACS extraction to the current Silverchair article structure, preserving the complete `.article-body`, tables, figures, MathML formulas, structured references, and stable article-supplement links while excluding embedded Figshare viewer content and figure UI chrome; refreshed all three ACS golden fixtures, made fixture PDF capture reuse the selected browser runtime, and stopped full-size figure pages from waiting for article-body readiness.
- Reused one ready IEEE article browser context/page for protected full-size figures, tables, multimedia, and supplementary assets, preserving current cookies and the article Referer without navigating the shared page to asset URLs; aligned HTTP 403/HTML challenge retry selection with the existing browser recovery policy.

## 4.0.1 - 2026-07-27

### Fixed

- Restored native texmath 0.13.2 as the preferred formula backend in Linux, macOS, and Windows offline packages, copied reused POSIX binaries instead of preserving build-host symlinks, and retained the locked `mathml-to-latex` package as the secondary fallback.
- Normalized relative Windows installer output directories before invoking Inno Setup, and allowed stable-release retries to overlay trusted packaging tooling without moving an immutable source tag.
- Restored the daily `dependency-latest` rolling prerelease after the 4.0 CI split, resolved the `full` extra for all nine frozen platform/ABI snapshots, reused the shared offline workflow for verified wheelhouse builds, and reinstated exact asset replacement and post-publication integrity checks.
- Made Chinese the sole language for future release notes: stable releases extract their version section from `CHANGELOG_CN.md`, while rolling prereleases use the Chinese status template instead of generating English notes.

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

- Added a lightweight cross-CLI/MCP/cache/manifest CI contract gate; package smoke now builds outside the checkout and verifies version consistency, every console script, MCP EOF, and static installation provenance while keeping live/offline heavy jobs opt-in.

### Fixed

- Fixed version ambiguity that could leave source, installed distribution metadata, and the PATH CLI at different releases without exposing their concrete paths; source development without an offline manifest is now reported as not applicable instead of an installation failure.

## 3.0.1 - 2026-07-04

### Changed

- Changed the built-in Wiley and Science samples used by `paper-fetch browser-preflight` and `paper-fetch auth` to lighter full-text pages already covered by fixtures, reducing slow parsing time in the default browser preflight.
- Added a built-in Royal Society Publishing sample for `paper-fetch browser-preflight` and `paper-fetch auth royalsocietypublishing`, so the default browser preflight now covers that browser-backed provider.
- Removed the full GitHub Actions unit/devtools/coverage job from the default CI gate; local `scripts/dev-preflight.sh` still runs the complete unit, devtools, and optional coverage checks.

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

## 2.8.0 - 2026-07-02

### Added

- Added provider-template-aware DOI extraction for DOI-bearing publisher URLs, including query-parameter DOIs, known route/extension suffix stripping, and AMS old-style SICI `view` / `downloadpdf` slug support, so many URL queries resolve directly without fetching a landing page first.

### Changed

- Changed publisher-facing landing/PDF requests and browser workflows to use browser-shaped user agents through `build_publisher_user_agent`; `PAPER_FETCH_USER_AGENT` remains the tool/API user agent and no longer becomes the default browser context user agent.
- Changed Royal Society Publishing from direct HTTP DOI/PDF fetching to the shared CDP browser HTML plus seeded-browser PDF workflow while keeping `royalsocietypublishing_html` / `royalsocietypublishing_pdf` sources and the no-XML route contract.
- Changed title-query resolution to prefer a formal journal publication over a near-tie preprint when Crossref metadata identifies a clear formal publication candidate.

- Changed local and CI quality gates to enforce `ruff format --check`, keep ruff linting, prefer repo-local `.venv/bin/python` or explicit `PYTHON_BIN`, report missing dev dependencies early, and run local preflight type checks with `mypy --no-site-packages`.

### Fixed

- Fixed the expanded mypy contract suite by normalizing BeautifulSoup attribute values before helper calls, preserving optional HTML dependency fallbacks under type checking, and aligning MCP request/resource/result types with the current SDK signatures.
- Fixed browser-backed batch concurrency so managed CDP browser managers are shared process-wide by provider/browser config, preventing concurrent CLI/MCP fetches for the same provider profile from racing on `.paper-fetch-profile.lock`; isolated contexts now use thread-owned CDP connections to avoid cross-thread Playwright sync object reuse.
- Fixed SICI DOI normalization and URL DOI suffix handling so DOI suffixes such as `<...>` / `;` are preserved, while provider route tokens such as Frontiers `/full`, IOP `/pdf`, Wiley `/fullpdf`, and Springer `.pdf` are stripped only when provider catalog templates make that safe.
- Fixed official PDF fallback degradation for scanned/PDF-only provider results: real downloaded PDFs are retained with explicit warnings and provider source trail instead of being replaced by Crossref/general metadata-only results when Markdown extraction is unusable.
- Fixed publisher landing/probe requests that previously sent the stable `paper-fetch-skill/<version>` tool user agent to browser-facing publisher routes.
- Fixed docs and contract drift around `PdfFallbackStrategy`, browser runtime ownership, provider URL/route behavior, and asset-download contract marker scanning after repository-wide ruff formatting.
- Add `scripts/dev-preflight.sh --coverage` and CI `term-missing` / `coverage.xml` reports without a coverage threshold.

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

- Added `paper-fetch --version` plus CLI help text for reference, asset, and token rendering options.

### Changed

- PDF fallback now honors `asset_profile=body|all` when artifact saving is enabled, exporting PDF-rendered body images to `body_assets/` and surfacing them in article assets/artifacts across direct HTTP and seeded-browser PDF routes.
- PDF fallback source files now use stable, source-derived filenames instead of a single `downloaded.pdf`, reducing collisions when multiple fallback PDFs are materialized in the same artifact directory.

### Fixed

- Fixed IOP figure asset extraction so standard `_lr` / `_online` CDN image links are upgraded to `_hr` high-resolution candidates before preview fallback, allowing IOP HTML fetches such as `10.1088/1748-9326/ad560b` to save full-size body figures when available.
- Add Frontiers (`frontiers`) XML-first routing for `10.3389/` and `frontiersin.org`, with canonical article discovery, shared JATS rendering, figure URL rewriting, direct HTTP PDF fallback, and `frontiers_xml` / `frontiers_pdf` sources.

## 2.5.2 - 2026-06-24

### Fixed

- Fixed shared HTML cleanup so semantic attributes such as `data-title`, `alt`, `title`, and `aria-*` no longer trigger chrome noise filtering. This preserves valid body figures whose captions contain words such as "related", including Nature articles where Fig. 2 was dropped from Springer/Nature HTML extraction.

## 2.5.1 - 2026-06-23

### Fixed

- Fixed browser PDF fallback after async thread handoff so it preserves the caller's runtime browser configuration, including provider profile and user-data directories, instead of forcing a fresh non-runtime browser context.

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

- Extended mypy `files` coverage beyond the model/workflow/mcp/http contract surface to additional foundational modules (`metadata`, `markdown`, `extraction/markdown_render`, `tracing`, `reason_codes`, `arxiv_id`, `normalize_journal_name`, `section_vocab`, `logging_utils`, `publisher_identity`, `provider_catalog`, `extraction/citation_anchors`), raising the analyzed set from 45 to 68 files, with the type fixes required to keep the check green.

- Bumped the bundled `mathml-to-latex` formula backend from 1.5.0 to 1.8.0, syncing the version across the root and `src/paper_fetch/resources/formula/` package manifests and lockfiles.

## 2.2.1 - 2026-06-12

### Changed

- Reduce repeated disk-cache reads, lock contention, HTML parsing, filesystem probes, and thread-pool creation while retaining existing request and extraction behavior.
- Relax the MCP compatibility range from `>=1.27,<1.28` to `>=1.27,<2`.

### Fixed

- Parse fractional `Retry-After` values through `float()` before truncating to seconds, rather than silently discarding them as invalid dates.
- Map log levels above `CRITICAL` to `critical` instead of `debug`.

## 2.2.0 - 2026-06-10

### Added

- Reuse the warmed in-page article `<img>` via canvas export as the first browser-workflow image-recovery step; when the target image exists but has not finished loading, perform a credentialed in-page `fetch()` for the raw image bytes before falling back to direct URL request, page fetch, and navigation candidates (affects `wiley`, `science`, `pnas`, `ams`, `annualreviews`, `acs`, `iop`, `aip`, `mdpi`).

### Changed

- Derive Atypon/Wiley figure caption labels from explicit labels, the figure DOM id, the image URL basename, or a caption that starts with `Figure N`, and read the `.figure__title` selector; a mid-caption `Figure N` cross-reference can no longer override the figure's own number.

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

- Mark browser-workflow providers through provider specs instead of maintaining separate hard-coded browser-runtime provider lists.

### Removed

- Remove the Gemini skill installer and legacy Codex MCP runner scripts from the shipped script surface.

## 1.9.0 - 2026-05-27

### Added

- Add AIP Publishing (`aip`), IOP Publishing (`iop`), and ACS (`acs`) providers with DOI/domain routing, CloakBrowser HTML, seeded-browser PDF fallback, body assets, and provider-managed metadata/abstract fallback. AIP and IOP expose `aip_html` / `aip_pdf` and `iop_html` / `iop_pdf`; IOP rejects Radware/hCaptcha challenges.
- Add two-step provider onboarding human gates with `prepare-human-preflight` and `finalize-review-artifact` for waterfall/access review and batch Markdown approval.

### Changed and fixed

- Filter fixture discovery by DOI prefix and reject off-provider, challenge, access-blocked, and empty-shell candidates as high-confidence full text.
- Preserve ACS body figure image links and rewrite downloaded figures to local Markdown paths.

## 1.8.0 - 2026-05-26

### Added

- Add PLOS (`plos`) routing for `10.1371/` and `journals.plos.org`, with public JATS XML first, direct HTTP PDF and metadata fallback, and `plos_xml` / `plos_pdf` sources.
- Add Oxford Academic (`oxfordacademic`) public HTTP HTML and validated article-PDF fallback with `oxfordacademic_html` / `oxfordacademic_pdf` sources.

### Fixed

- Follow PLOS signed image redirects and rewrite downloaded images to local paths; preserve graphic-only JATS formulas as formula images.
- Preserve Oxford Academic Silverchair formula paragraphs and render references from visible reference-list text.
- Update Royal Society Publishing PDF fallback rendering.

## 1.7.0 - 2026-05-24

### Added

- Add Annual Reviews (`annualreviews`) for `10.1146/`, CloakBrowser HTML, seeded-browser PDF fallback, abstract-only degradation, and body figures.
- Add Royal Society Publishing direct HTTP HTML with strict PDF fallback.

### Fixed

- Wait for Annual Reviews dynamic full-text containers and stop treating institutional “access provided by” labels as paywall blockers.
- Report non-PDF browser downloads as `NON_PDF_FALLBACK_CONTENT`; refetch real PDF bytes through the same browser request context when Chromium returns a PDF viewer shell.
- Reuse one DOI fixture across capture purposes and avoid treating access UI as a gate when a populated full-text container is present.
- Preserve Royal Society Publishing Silverchair captions and clean PDF fallback watermark/page placeholder noise.
- Derive DOI values from known MDPI numeric article URLs and landing URLs from known MDPI DOI suffixes.
- Synchronize the formula Node workspace to `katex` 0.17.0.
- Decode invalid UTF-8 from formula converters and PyMuPDF's Windows Tesseract probe with replacement characters, avoiding reader-thread `UnicodeDecodeError`.

## 1.6 - 2026-05-22

### Added

- Added experimental macOS offline release tarballs for CPython 3.11, 3.12, 3.13, and 3.14, with CI installation checks, headful layout validation, and CloakBrowser smoke coverage.

- Added operator access-review and provider Markdown-review artifacts for AI provider onboarding, with schema-backed gates before discovery and acceptance.
- Added a local `scripts/dev-preflight.sh` gate plus low-strength contract-layer `mypy` checking, formula Node package sync tests, and golden corpus provider adapters for easier provider onboarding.

### Changed

- Changed manifest-driven fixture capture to support `--all` batch capture and changed provider scaffold replay to return merge-plan JSON when generated files already exist.
- Tightened live review to compare provider sources against manifest `route_sources` and reuse manifest Markdown contracts for automatic issue classification.
- Enabled the normal Chrome browser User-Agent in offline installer-managed `offline.env` blocks by default so CloakBrowser-backed AGU/Wiley fetches are less likely to stop at Cloudflare challenge pages.
- Derived MCP status, live review support, and golden corpus representative coverage from provider facts instead of hard-coded provider lists where possible.
- Add MDPI CloakBrowser HTML with browser PDF fallback and `mdpi_html` / `mdpi_pdf` sources.

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

- Refined CLI output/artifact semantics so batch and single-query runs consistently separate primary output files from saved Markdown and provider artifacts.
- Updated MCP fetch/cache payload behavior for inline image budgets, cache resource visibility, and schema coverage.
- Hardened Elsevier Markdown and Springer HTML extraction around tables, figures, asset rewriting, and provider-specific cleanup.
- Fixed offline installer smoke checks to use the current MCP provider-status entrypoint during Linux and PowerShell installs.

## 1.4 - 2026-05-12

### Added

- Added the `arxiv` provider for `arxiv.org` and DOI prefix `10.48550/`, publishing `arxiv_html` on official HTML success with text-only PDF fallback as `arxiv_pdf`.

### Changed

- Centralized provider source ownership, including Springer HTML/PDF source ownership, API-like hosts, Wiley TDM URL template, Springer/Nature domain matching, workflow HTML-managed fallback markers, and body-text thresholds in `ProviderSpec` / `SOURCE_PROVIDER_MAP`.

- Golden criteria live review now includes `copernicus` in the supported provider rotation and provider-status diagnostics.

- Clarified CLI output semantics: explicit `--format` with `--output-dir` and stdout output now also writes a same-format document copy under `--output-dir`, while `--output` remains the explicit formatted-output file path.
- Golden criteria live review now treats `arxiv` as a supported provider, records arXiv provider status, preserves derived-URL fallback when arXiv API metadata has transient failures, and classifies arXiv asset partial-download diagnostics as `asset_download_failure`.
- arXiv metadata enrichment now uses a small internal Atom API client for ID lookup and no longer depends on the PyPI `arxiv` / `feedparser` dependency chain.
- arXiv HTML asset downloads now use a provider-specific lower concurrency cap and retry network-exception failures once sequentially while preserving non-retryable failures in `quality.asset_failures`.
- arXiv fulltext routing is now fixed to official HTML first with direct text-only PDF fallback; retired local source-conversion fallback code and related asset handling are no longer part of the supported route.
- arXiv official HTML Markdown cleanup now folds ordinary prose hard line breaks, sanitizes nested `$...$` delimiters inside LaTeXML TeX annotations, and lifts full-width table title rows out of GFM pipe table headers.

- Elsevier XML body asset downloads now retry only failed transient network items once sequentially and remove the original asset failure when the retry succeeds.
- Wiley formula image discovery now includes `data-altimg` fallback spans and display formula containers, so image-only formulas can enter the `kind="formula"` asset download path instead of requiring an `<img>` tag.
- Restrict IEEE article-number parsing to `/document/{article_number}/` landing paths and preserve Springer/Nature article roots during Creative Commons cleanup.

## 1.3 - 2026-05-09

### Added

- Added the `copernicus` XML-first provider for Copernicus Publications DOI prefix `10.5194/`, publishing `copernicus_xml` on NLM/JATS XML success with text-only PDF fallback as `copernicus_pdf`.

- Hardened Copernicus fallback handling for older articles whose XML only exposes abstract-level content: those XML failures now continue directly to text-only PDF fallback, and PDF discovery includes DOI-derived `.pdf` candidates when the landing page omits PDF metadata.

### Refactor

- Move dev-only `geography_live`, `geography_issue_artifacts`, and `golden_criteria_live*` modules from `paper_fetch.*` to source-tree-only `paper_fetch_devtools.*`; wheels no longer ship those modules, while the existing repo-local script CLIs keep the same behavior.

### Changed

- Copernicus XML extraction now reuses the parsed XML root through validation and article assembly, validates usable body paragraphs with a named threshold, and continues with DOI-derived XML/PDF URLs when landing HTML cannot be fetched.
- Copernicus XML assets now use `original_url` as the canonical remote URL while shared asset download mirrors the compatibility URL fields after download; table assets are emitted directly as `kind="table"` with `table_render_kind`.
- Installer completion summaries now explicitly prompt users to request and configure `ELSEVIER_API_KEY` from <https://dev.elsevier.com/> before Elsevier full-text fetching, and point to the relevant `.env` file.
- Windows offline release artifacts now use `paper-fetch-skill-windows-x86_64-setup.exe` and bundle CPython 3.13 x64, Python dependencies, Playwright Chromium, formula tools, the FlareSolverr runtime, Codex / Claude Code skills, and MCP registration helpers.
- GitHub Actions now creates a GitHub Release on `v*` tag pushes or explicit manual releases after regular validation, the full Linux offline package matrix, and the Windows x86_64 setup exe succeed, uploading 4 Linux tarballs plus 1 Windows installer release asset.
- Expanded body-image payload recognition and persistence formats: in addition to PNG/JPEG/GIF/WebP/AVIF/TIFF, SVG text, BMP, ICO, APNG, and HEIC/HEIF MIME/extension mappings are supported; body images are verified for image magic bytes or top-level SVG document signatures before being saved, avoiding challenge HTML being persisted as images.

- Added a fast initial FlareSolverr HTML pass for Wiley / Science / PNAS full-text fetching: primary HTML requests use `waitInSeconds=0` and `disableMedia=true`, then automatically fall back to the original conservative wait strategy on challenges, access blocks, abstract redirects, or insufficient body extraction.
- Image recovery, body/supplementary asset downloads, and figure-page HTML discovery continue to use media-enabled paths so `disableMedia` does not block full-size image discovery or downloads.

## 1.0.0 - 2026-04-26

### Changed

- Released the package as `1.0.0` and updated the default `paper-fetch-skill/1.0` User-Agent.
- Hardened Wiley / Science / PNAS seeded Playwright image fetching so Cloudflare challenge pages and non-image responses fail quickly instead of stalling a live review.
- Reordered the Wiley full-text waterfall so browser PDF/ePDF fallback now runs before the optional TDM API PDF lane whenever the local browser runtime is ready, keeping `wiley_browser` as the default successful route.
- Added `code_availability` as a first-class section kind. Elsevier, Springer / Nature, Wiley, Science, and PNAS now share data/code/software availability classification, retain those sections in final Markdown/ArticleModel output, and exclude them from body sufficiency metrics.

## 2026-04-25

### Changed

- Promoted the Wiley / Science / PNAS HTML asset downloader to a shared Playwright primary path. Figure, table, and formula image candidates now reuse one seeded browser context per download attempt instead of trying direct HTTP first.
- Kept full-size/original candidates ahead of preview candidates, but now fetches both tiers through the same shared browser context. Target-provider downloads report `download_tier="full_size"` or `download_tier="preview"` rather than `playwright_canvas_fallback`.
- Tightened the browser-workflow image recovery path: repeated figure-page / image-candidate URLs are cached per attempt, body-image payload downloads now use fixed limited parallelism with stable output ordering, and FlareSolverr recovery no longer falls back to screenshot cropping when `solution.imagePayload` is missing or invalid.
- Preserved the FlareSolverr seed refresh retry for partial asset failures, while keeping the generic HTTP-first asset downloader unchanged for non-target providers such as Springer.
- Expanded HTML formula handling so Wiley, Science / PNAS shared HTML, and Springer / Nature paths preserve MathML when possible and retain formula image fallbacks as `![Formula](...)` assets when MathML is absent or unusable.
- Normalized final Markdown after asset-link rewrites so downloaded figure / table / formula links replace remote URLs before section parsing, block images are separated from adjacent headings/text/math fences, and empty body parent headings remain visible.
- Hardened structured metadata and references: front matter unescapes HTML entities, Elsevier XML references no longer skip sparse bibliography entries, and Wiley / Springer-style HTML references remove link chrome while preferring visible citation text over DOI-only snippets.
- Tightened Springer / Nature HTML cleanup by pruning more article chrome and license sections, preserving scientific back matter outside the main body, extracting formula image assets, and emitting explicit table-body-unavailable placeholders when table-page parsing fails.
- Adjusted golden-criteria live issue classification so formula-only preview fallback is not treated as an asset-download failure, while non-formula preview fallback still remains an asset issue unless explicitly accepted.

## 2026-04-19

### Changed

- Add repository-local geography report/export/group scripts without adding installed CLI commands or MCP tools.

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

## 2026-04-14

### Added

- Added public `science` and `pnas` provider routes, including direct `provider_hint`, `preferred_providers`, and final `source` support.
- Added repo-local Science / PNAS provider implementations in [`src/paper_fetch/providers/science.py`](src/paper_fetch/providers/science.py) and [`src/paper_fetch/providers/pnas.py`](src/paper_fetch/providers/pnas.py), backed by shared FlareSolverr, HTML cleanup, and Playwright PDF-fallback helpers.
- Added repo-local `vendor/flaresolverr/` workflow assets, thin wrapper scripts under [`scripts/`](scripts), and a dedicated operator guide in `docs/flaresolverr.md`.

### Changed

- Extended `SourceKind` and the service provider registry so `science` and `pnas` are first-class public provenance values instead of envelope-only aliases.
- Made Science / PNAS use a provider-managed `HTML first -> PDF fallback -> metadata-only fallback` chain, while explicitly skipping the generic `html_generic` fallback after those providers are selected.

- Added explicit repo-local runtime checks for `vendor/flaresolverr`, `FLARESOLVERR_ENV_FILE`, local FlareSolverr health, and required local rate-limit settings before Science / PNAS full-text retrieval proceeds.
- Added local Science / PNAS rate-limit accounting in the user data directory and kept `asset_profile=body|all` on those routes as text-only downgrades with warnings instead of hard failures.
- Expanded `install-formula-tools.sh` so repo-local development can bootstrap FlareSolverr source setup, Playwright Chromium, and headless `Xvfb` prerequisites from one entrypoint.

## 2026-04-13

### Added

- Added MCP cache indexing with `list_cached()` / `get_cached()` plus `resource://paper-fetch/cache-index` and `resource://paper-fetch/cached/{entry_id}` resources for the default shared download directory.
- Added `batch_resolve(queries)` and `batch_check(queries, mode)` MCP tools so citation-list workflows can stay serial, transport-reusing, and context-light.

- Added inline `ImageContent` support for a few local body figures when `strategy.asset_profile` is `body` or `all`.
- Added structured MCP progress updates and structured log notifications for `fetch_paper`, `batch_check`, and `batch_resolve`.

- Added a probe-semantics design note in [`docs/architecture/probe-semantics.md`](docs/architecture/probe-semantics.md) to define the future `has_fulltext(query)` direction.

### Changed

- Exposed `download_dir` on the MCP `fetch_paper` surface so task-local directories can override `PAPER_FETCH_DOWNLOAD_DIR` and XDG defaults.
- Expanded MCP `resolve_paper` to accept either a raw `query` or structured `title` plus optional `authors` / `year`.
- Updated the static skill to document the real defaults, the environment variables that affect behavior, the error contract, cache-first call discipline, and the batch-first bibliography workflow.
- Clarified that `include_refs=null` behaves like `all` for `max_tokens="full_text"` and like `top10` for numeric token budgets.

- Shifted provider routing toward Crossref/domain-first hints with DOI-prefix fallback only when needed, and added route diagnostics to `source_trail`.

- Refined CLI exit codes, Markdown asset-link handling, render budgeting, and token-estimation internals without changing the public fetch contract.

### Fixed

- Protected in-process HTTP GET caching with `threading.RLock`.
- Switched the HTTP transport to `urllib3.PoolManager` for connection reuse without changing the public request contract.
- Added response-size guards, gzip pre-decompression size checks, cache-budget eviction, and safer retry behavior for timeout/transient errors.
- Converted payload and asset writes to atomic `.part -> replace` flows so failed writes do not corrupt final files.
- Tightened exception handling so programming errors are no longer silently downgraded into partial-download or fallback paths.
- Prevented `batch_check()` from writing payloads to disk by forcing `download_dir=None`.
- Preserved top-level fetch provenance fields even when `article`, `markdown`, or `metadata` are unrequested and therefore returned as `null`.
