# Paper Fetch Skill Target Architecture

Date: 2026-04-10 (revision 7)

## Status

**Status:** the current branch should be treated as the closed-out baseline for this architecture. The package layout under `src/paper_fetch/`, the `paper-fetch` CLI, the `paper-fetch-mcp` stdio server, the static thin skill, and the thin install scripts are all already landed and covered by the test suite.

**Migration status:** the migration-order steps below are complete on the current branch:

- step 1 complete: the codebase is packaged under `src/paper_fetch/` and exposed via `pyproject.toml`
- step 2 complete: `paper-fetch` routes through the service layer and preserves the CLI contract
- step 3 complete: the MCP server exposes `resolve_paper` and `fetch_paper`
- step 4 complete: the repo skill source is static `skills/paper-fetch-skill/SKILL.md`
- step 5 complete: install scripts are thin, and the Codex manifest is generated only at install time

For current operational backlog, including any post-closeout follow-up work, use `problems.md`. This document is architecture rationale and baseline contract only.

## Decision

This repository is a better fit for `CLI + MCP + thin skill` than for `pure MCP`.

## Why This Is The Better Fit

1. The current repository already has a real command-line entrypoint, not just prompt text.
   `paper-fetch` is exposed via `src/paper_fetch/cli.py`, and the tests already exercise the public CLI entrypoint directly.

2. The core value of the project is reusable fetch logic, not the transport layer.
   DOI resolution, provider routing, metadata merge, HTML fallback, and Markdown rendering should remain callable outside any agent runtime.

3. A pure MCP design would make manual debugging and shell validation worse.
   This project is often going to be verified by running one DOI from the terminal, saving payloads, and inspecting files.

4. MCP is still a strong fit, but as an adapter layer.
   The tool naturally exposes structured operations such as `resolve`, `fetch full text`, and `metadata only`, which map well to MCP tools.

5. A thin skill remains useful for agent discovery, but it should not own environment bootstrapping.
   The current heavy install flow comes from the skill pointing at repo-local absolute paths and a repo-local `.venv`.

## Target Shape

The target should be:

- `core library`: all fetch logic and models live in importable Python modules
- `CLI`: stable command for humans, CI, and quick smoke tests
- `MCP server`: structured tool interface for Codex/Claude/other MCP clients
- `thin skill`: static skill directory that only teaches the model when to use the MCP tools

## Recommended Directory Layout

The layout below describes the stable architectural shape.

```text
paper-fetch-skill/
├── pyproject.toml
├── README.md
├── .gitignore
├── .env.example
├── docs/
│   ├── providers.md
│   └── architecture/
│       └── target-architecture.md
├── scripts/
│   ├── install-codex-skill.sh
│   ├── install-claude-skill.sh
│   └── dev-smoke-fetch.sh
├── skills/
│   └── paper-fetch-skill/
│       └── SKILL.md
├── src/
│   └── paper_fetch/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── models.py
│       ├── service.py
│       ├── outputs.py
│       ├── resources/
│       │   ├── journal_lists.yaml
│       │   ├── routing_rules.yaml
│       │   └── elsevier_markdown_mapping.md
│       ├── resolve/
│       │   ├── __init__.py
│       │   ├── query.py
│       │   └── normalize.py
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── registry.py
│       │   ├── base.py
│       │   ├── crossref.py
│       │   ├── elsevier.py
│       │   ├── springer.py
│       │   ├── wiley.py
│       │   └── html_generic.py
│       ├── formula/
│       │   ├── __init__.py
│       │   ├── convert.py
│       │   └── backends.py
│       └── mcp/
│           ├── __init__.py
│           ├── server.py
│           ├── tools.py
│           └── schemas.py
├── tests/
│   ├── fixtures/
│   ├── unit/
│   ├── integration/
│   └── live/
└── live-downloads/
```

## Responsibilities By Layer

### `src/paper_fetch/service.py`

Own the main orchestration shared by the CLI and MCP adapters.

Suggested public functions:

- `resolve_paper(query: str, ...) -> ResolvedQuery`
- `fetch_paper(query: str, *, modes: set[OutputMode], strategy: FetchStrategy, ...) -> FetchEnvelope` — see the contract below
- `fetch_raw_payload(query: str, ...) -> RawFetchResult` — internal helper used by the above; not necessarily exposed via MCP initially

The service layer is the single source of truth for dispatch. Both the CLI and the MCP adapter call the same `fetch_paper`, which means adding a new output format or a new fetch-strategy knob only requires editing the service once.

This module should not parse CLI flags and should not know anything about MCP message envelopes.

#### `fetch_paper` contract

**Output modes and fetch strategy are two separate axes.** Conflating them into a single `mode` parameter was the first draft of this document; review against the CLI contract showed that was wrong, because the current `paper-fetch` CLI already exposes `--no-html-fallback` as a genuine strategy knob that is independent of output format, and it already supports a `"both"` output (`article + markdown` in one response). The contract below preserves both of those existing capabilities.

**Axis 1 — output modes** (`modes: set[OutputMode]`, default `{"article", "markdown"}`):

- `"article"` — include the structured `ArticleModel` in the response
- `"markdown"` — include the rendered Markdown string in the response
- `"metadata"` — include only metadata fields of the article (no sections, no body)

Modes are composable. Asking for `{"article", "markdown"}` is the direct successor of today's `--format both` and is the recommended default for agent use: the agent gets the Markdown it will actually read, plus the structured model it needs to reason about provenance and quality. Asking for `{"metadata"}` alone is the successor of "metadata only".

**Axis 2 — fetch strategy** (`strategy: FetchStrategy`):

A dataclass with at least these fields, each mirroring a real capability in the current CLI:

- `allow_html_fallback: bool = True` — when `False`, do not attempt HTML-landing-page extraction after official-provider paths fail. Mirrors the existing `--no-html-fallback` flag.
- `allow_metadata_only_fallback: bool = True` — when `False`, failing to obtain a usable body is an error (`PaperFetchFailure`) rather than a degraded-but-successful metadata-only response. Mirrors the behavior a caller gets today when they want to know "is there formal full text available, yes or no".
- `preferred_providers: list[str] | None = None` — optional provider allow-list for callers who want to constrain the final official/fulltext/html path. Internal Crossref routing signals may still be used even when `crossref` is not in the allow-list.

The strategy dataclass is where all future "how to fetch" knobs accrue. Output modes are only about "what to return". A caller who wants "official full text only, give me both structured and Markdown, fail loudly if there's no body" expresses it as `modes={"article", "markdown"}, strategy=FetchStrategy(allow_html_fallback=False, allow_metadata_only_fallback=False)`. No second fetch, no adapter-layer branching.

**Return type — `FetchEnvelope`** (stable shape, never shape-switches on modes):

```python
@dataclass
class FetchEnvelope:
    # Provenance — ALWAYS populated, regardless of which modes were requested
    doi: str | None
    source: str                   # open, documented provenance string — see below
    has_fulltext: bool
    warnings: list[str]           # promoted from article.quality.warnings
    source_trail: list[str]       # promoted from article.quality.source_trail
    token_estimate: int

    # Payloads — present iff the corresponding mode was requested AND obtainable
    article: ArticleModel | None        # populated iff "article" in modes
    markdown: str | None                # populated iff "markdown" in modes
    metadata: Metadata | None           # populated iff "metadata" in modes — see rules below
```

The envelope shape is **fixed**. Requesting only `{"markdown"}` still returns a `FetchEnvelope` with `article=None`, not a bare string. This is the non-negotiable part of the contract: the MCP adapter must never switch response shape based on the request, because that forces every caller to write type-narrowing logic and weakens the "thin MCP" property.

**`metadata` field population rules** (the `"metadata"` mode is what decides, not `article`):

- If `"metadata" in modes`, then `envelope.metadata` **must** be populated.
- If `"metadata" not in modes`, then `envelope.metadata` **must** be `null`, *even if `article` is present and carries `article.metadata` internally*. Callers who already asked for `"article"` read `envelope.article.metadata`; callers who asked for `"metadata"` read `envelope.metadata`. There is no "free" metadata in the envelope.
- If both `"article" in modes` and `"metadata" in modes`, then `envelope.metadata` and `envelope.article.metadata` **must** be content-identical. The service layer populates both from the same source; the MCP adapter does not deduplicate or drop one.

Rationale: this preserves the ergonomic property that `modes={"metadata"}` callers read `.metadata` directly, without having to learn the reverse-intuitive rule "metadata mode actually lives under `.article.metadata`". The cost is a small amount of duplication when both modes are requested, which is deliberate and documented.

**`source` is an open, documented provenance string, not a closed enum.**

The field is typed as `str` rather than a sealed `SourceKind` enum. The MCP contract lists the canonical values known at the time of writing, but future revisions may add new values (new providers, new fallback paths) without a contract bump. Callers must not assume the set is closed and must not pattern-match exhaustively against it — unknown values should be treated as "some provenance the client doesn't recognize yet", not as an error.

Canonical `source` values as of this document:

- `"elsevier_xml"` — Elsevier official XML (TDM)
- `"springer_xml"` — Springer official XML
- `"wiley_tdm"` — Wiley TDM path
- `"crossref_meta"` — Crossref metadata only, no body attempted or obtained from a publisher
- `"html_fallback"` — landing-page HTML extraction after official paths failed or were skipped
- `"metadata_only"` — the `allow_metadata_only_fallback` degraded path; body not obtainable, metadata returned

Fine-grained diagnostics continue to live in `source_trail` (which today already carries markers like `fulltext:wiley_article_ok`, `fallback:html_disabled`, `fallback:metadata_only`). The split is: `source` is the coarse, agent-readable "where did this come from" string; `source_trail` is the ordered debug trace. Agents should branch on `source`; humans and tests should read `source_trail`.

Current repo note: `ArticleModel` still uses a narrower internal `SourceKind` literal with values like `"wiley"` and `"html_generic"` in `src/paper_fetch/models.py`, while the public MCP/CLI envelope exposes the open provenance string documented here. The reconciliation is already implemented at the envelope construction boundary in `src/paper_fetch/service.py`; the public `source` string is what the contract is anchored on, not the internal enum name.

**Why provenance is promoted to envelope top-level, not buried inside `article.quality`:**

Today's Markdown serializer (`ArticleModel.to_ai_markdown`) does not round-trip `quality.warnings` or `quality.source_trail` into the Markdown string. That is the correct behavior for the Markdown itself (agents read the Markdown as content), but it means a caller who only wants the Markdown string would lose provenance. Promoting `has_fulltext`, `warnings`, `source_trail`, `source` to the envelope top-level means every caller, regardless of which modes they asked for, can always answer "was this Wiley TDM, HTML fallback, or metadata-only?" without re-fetching and without reaching into `article.quality`. This is the concrete agent use case that justifies the envelope design.

**Metadata-only fallback semantics:**

When `strategy.allow_metadata_only_fallback=True` (default) and no usable body is obtainable, `fetch_paper` returns a `FetchEnvelope` with `has_fulltext=False`, `source="metadata_only"`, `article` populated with a metadata-only `ArticleModel` (if `"article" in modes`), `markdown` populated with a metadata-only rendered Markdown (if `"markdown" in modes`), and a warning in `warnings` describing the degradation. The existing `source_trail` marker `fallback:metadata_only` is preserved. When `allow_metadata_only_fallback=False`, the same condition raises `PaperFetchFailure` instead. Both branches exist today in the CLI's behavior and must survive the migration.

### `src/paper_fetch/cli.py`

Own only terminal-facing behavior:

- `argparse`
- stdout/stderr formatting
- exit codes
- optional file writes

The CLI should become the stable shell contract:

```bash
paper-fetch --query "10.1038/s41586-020-2649-2"
```

### `src/paper_fetch/mcp/`

Expose the same service layer as structured tools.

Recommended first MCP tools (hybrid granularity):

- `resolve_paper(query)` — returns a `ResolvedQuery`. Kept separate because its return shape is fundamentally different from fetch results (no article body, no provider payload), and agents often want to resolve without committing to a download.
- `fetch_paper(query, modes, strategy)` — returns a `FetchEnvelope` (see the service-layer contract above). `modes` is a set of output modes (`"article"`, `"markdown"`, `"metadata"`). `strategy` carries fetch-strategy knobs like `allow_html_fallback` and `allow_metadata_only_fallback`.

Rationale for the split: `resolve` and `fetch` are genuinely different operations, so they stay as separate tools. The historical three-way split of fetch into `_fulltext` / `_metadata` / `_markdown` collapses into a single `fetch_paper` because those three really only differed in *what the caller wanted back*, which is now expressed by composable `modes`. The result is a short tool list (two tools for the happy path) with explicit, orthogonal knobs.

**MCP JSON shape:** `fetch_paper` always returns a JSON object with the same top-level keys as `FetchEnvelope` — never a bare string, never a shape-switching union. Fields corresponding to un-requested modes are present as `null`. This is load-bearing for the "thin MCP" property: the adapter's job is serialization, not branching.

**Agent-visible defaults:** the MCP tool's default `modes` is `["article", "markdown"]` and its default `strategy` is "allow HTML fallback, allow metadata-only fallback, no provider allow-list". This matches the most common agent use case ("give me the paper and tell me where it came from") and avoids forcing every caller to spell out the defaults.

Optional later MCP tools:

- `fetch_saved_payload`
- `list_supported_providers`
- `validate_provider_config`

The MCP layer should be thin. It should translate MCP inputs to service calls and serialize `FetchEnvelope` to JSON-safe output. It should not contain business logic — if a new mode or a new strategy knob needs non-trivial branching, that branching belongs in `service.py`.

### `src/paper_fetch/formula/`

Kept as its own subpackage because formula conversion already has two backends:

- `texmath` is the primary backend
- `mathml-to-latex` is the Node-based fallback when `texmath` is unavailable

`formula/convert.py` owns the public entry point and the fallback chain. `formula/backends.py` owns the per-backend adapters and availability probing. Backend selection is global (service-wide), not per-provider — a provider returns MathML, and the formula layer decides how to render it based on which backends are installed at runtime.

If in the future we collapse to a single backend, this subpackage should be demoted to a single `outputs/formula.py` module. Until then, the two-backend fallback logic is enough complexity to justify the split.

### `skills/paper-fetch-skill/`

Make this a real static skill directory that can be copied directly into `~/.codex/skills/`.

Its job should be:

- explain when the paper-fetch tools are appropriate
- tell the model to call the MCP tool first
- optionally mention the CLI as a fallback for non-MCP contexts

Its job should not be:

- creating a virtual environment
- rendering absolute paths
- owning `.env` bootstrap
- deciding install location of the codebase
- carrying runtime-specific manifest files in the repo source tree

**Codex compatibility is handled at install time, not in the skill source.**

Codex expects each skill directory to contain an `agents/openai.yaml` manifest. That file is a Codex-specific requirement, not a generic skill asset, so it does not belong in `skills/paper-fetch-skill/` in the repo. Instead, `scripts/install-codex-skill.sh` generates or copies `agents/openai.yaml` into the *installed* skill directory (typically `~/.codex/skills/paper-fetch-skill/agents/openai.yaml`) as a one-shot compatibility shim. This keeps the in-repo skill source runtime-agnostic and makes it trivial to add other runtimes later — each new runtime gets its own install script, and the skill source itself never grows per-runtime branches.

If a future runtime needs a second manifest format (e.g. Claude skills add their own file), add a second install script. Do not put both manifests side by side in the repo skill directory.

## Recommended Config Strategy

Move away from "repo root `.env` is the runtime contract".

Recommended load order:

1. process environment variables
2. `PAPER_FETCH_ENV_FILE`
3. `~/.config/paper-fetch/.env`

Repo-local `.env` should only be used in development via an explicit `PAPER_FETCH_ENV_FILE=/path/to/.env` override.

Recommended writable runtime paths:

- cache: `~/.cache/paper-fetch/`
- logs: `~/.local/state/paper-fetch/`
- downloads: configurable, with **different defaults per adapter**:
  - CLI default: `PAPER_FETCH_DOWNLOAD_DIR` first, otherwise XDG data dir `paper-fetch/downloads`, with `./live-downloads` only as a creation fallback
  - MCP default: `~/.local/share/paper-fetch/downloads/` (XDG data dir — avoids scattering files wherever the MCP server happens to be launched from)
  - Both can be overridden by `PAPER_FETCH_DOWNLOAD_DIR` env var or an explicit argument.

**Where the split is enforced:** `service.py` must have *no default* for the download directory. It takes a required `download_dir` argument (or `None` meaning "don't write to disk"). Each adapter is responsible for resolving its own default:

- `cli.py` resolves `PAPER_FETCH_DOWNLOAD_DIR` or the XDG default before calling the service, and only falls back to `./live-downloads` if the user-data directory cannot be created
- `mcp/server.py` resolves `~/.local/share/paper-fetch/downloads/` before calling the service

This keeps the service layer cwd-agnostic and makes the per-adapter behavior explicit and testable. A service-layer default would either be wrong for one of the two adapters or require the service to know which adapter called it — both are bad.

This change is important because MCP servers should not depend on the caller's current working directory.

## Packaging Direction

Add a standard `pyproject.toml` and expose console scripts.

Recommended entry points:

```toml
[project.scripts]
paper-fetch = "paper_fetch.cli:main"
paper-fetch-mcp = "paper_fetch.mcp.server:main"
```

This gives three usable surfaces from one codebase:

- `paper-fetch` for humans
- `paper-fetch-mcp` for agent clients
- `skills/paper-fetch-skill/` for thin discovery prompts

## Mapping From Current Files

Suggested migration map:

- `scripts/paper_fetch.py` -> split into `src/paper_fetch/service.py` and `src/paper_fetch/cli.py`
- `scripts/resolve_query.py` -> `src/paper_fetch/resolve/query.py`
- `scripts/article_model.py` -> `src/paper_fetch/models.py`
- `scripts/fetch_common.py` -> `src/paper_fetch/config.py` and shared utility modules
- `scripts/provider_clients.py` -> `src/paper_fetch/providers/registry.py`
- `scripts/providers/*` -> `src/paper_fetch/providers/*`
- `scripts/formula_conversion.py` -> `src/paper_fetch/formula/convert.py`
- `references/journal_lists.yaml` -> `src/paper_fetch/resources/journal_lists.yaml`
- `references/routing_rules.md` -> convert to machine-readable `src/paper_fetch/resources/routing_rules.yaml`. **The YAML becomes the source of truth.** Do not keep a parallel prose version that duplicates the rules — prose and YAML will drift. Instead, either (a) delete the Markdown entirely and let the YAML + schema comments self-document, or (b) keep a short `docs/routing_rules.md` that only explains the *schema and rationale*, not the individual rules. The individual rules live in YAML only.
- `templates/skill_template.md` -> replace with static `skills/paper-fetch-skill/SKILL.md`
- `install-codex.sh` -> shrink into `scripts/install-codex-skill.sh`

## Why Not Pure MCP

Pure MCP would remove a useful interface you already have.

That would cost you:

- easy terminal smoke tests
- non-agent batch usage
- simpler regression debugging
- a clean interface for CI and local scripts
- a transport-neutral core for future integrations

Pure MCP only becomes the best option when the product is primarily a long-running service and almost nobody needs to call it directly from a shell. This repository is not there today.

## Migration Order

**Strategy: one-shot cutover, no shim period.**

Status on the current branch: the one-shot cutover is already complete. The sequence below is kept as the migration record and acceptance reference for future archaeology; new work should start from the closed-out architecture above rather than reopen the `scripts/` move.

Recommended sequence:

1. Package the existing logic without changing behavior.
   Move modules from `scripts/` into `src/paper_fetch/` and delete the `scripts/` copies in the same commit. See the [Migration Checklist](#migration-checklist) below for the ordered sub-steps — step 1 is the riskiest and most mechanical.

2. Stabilize the CLI.
   Make `paper-fetch` call the new service layer and preserve current stdout/stderr contracts. Snapshot current `--help` output and a sample DOI fetch before step 1 starts, diff after step 2 finishes.

3. Add the MCP server.
   Implement MCP tools as thin wrappers around the same service functions. Start with `resolve_paper` and `fetch_paper(mode=...)`; defer the optional tools.

4. Replace the generated skill with a static thin skill.
   Make the skill reference MCP tools instead of absolute repo paths. The repo skill source should contain only `SKILL.md`.

5. Shrink installation scripts.
   The install step should become "install package + copy skill + (Codex only) drop the `agents/openai.yaml` shim". No venv creation, no `.env` bootstrap in the skill installer — those move to a separate `scripts/dev-bootstrap.sh` that developers run, not end users.

## Migration Checklist

Step 1 ("package without changing behavior") is where most migrations of this shape go wrong. Do it in this order to keep each commit individually green:

1. **Freeze the behavior snapshot.** Before touching imports, capture golden outputs:
   - `paper-fetch --help` stdout
   - one successful DOI fetch's stdout + the contents of the saved payload file
   - the full `pytest` pass list
   These become the acceptance criteria for step 1.

2. **Decouple tests from internal module paths first.** The current test suite couples to `scripts/` in at least three different ways, and a naive `from scripts.` grep will miss most of them. Audit `tests/` for all of these patterns:

   - **Explicit `sys.path` injection** — `sys.path.insert(0, .../scripts)` followed by bare `from paper_fetch import ...` or `from fetch_common import ...`. Example today: [tests/live/test_live_publishers.py:9-14](../../tests/live/test_live_publishers.py#L9-L14).
   - **`importlib.util.spec_from_file_location` loading** — manually loading `scripts/paper_fetch.py` as a module and registering it in `sys.modules` under a chosen name, then relying on that registration for subsequent bare imports. Historical example before the test-suite split lived in the old combined `tests/unit/test_paper_fetch.py`.
   - **Bare top-level imports that silently depend on the above side effects** — `from article_model import ...`, `from fetch_common import ...`, `from providers.wiley import ...`. These look like ordinary imports but only resolve because an earlier line in the same file put `scripts/` on `sys.path` or because `paper_fetch.py`'s own import machinery did. Historical example before the test-suite split also lived in the old combined `tests/unit/test_paper_fetch.py`.

   Search patterns to actually use (not just `from scripts.`):

   - `sys.path.insert` and `sys.path.append` anywhere under `tests/`
   - `spec_from_file_location` anywhere under `tests/`
   - `sys.modules[` assignments in `tests/`
   - Any bare `from article_model`, `from fetch_common`, `from providers.`, `from paper_fetch` import in `tests/` — every one of these is load-bearing on a `sys.path` side effect today and must be rewritten

   Replace all of them with calls through the intended public surface (`from paper_fetch.service import ...`, `from paper_fetch.models import ...`, etc. once those modules exist). If a test reaches into a private helper, either promote the helper to public or rewrite the test to go through the public path. **Do this before moving any files** — otherwise every file move breaks every test at once, and you lose the ability to bisect.

   Closeout acceptance criterion: `tests/integration/test_architecture_closeout.py` passes, which bans `sys.path` mutation, `spec_from_file_location`, `sys.modules[...]` injection, and bare legacy imports such as `from article_model ...`, `from fetch_common ...`, or `from providers...`, while explicitly allowing `from paper_fetch...` imports through the public package surface.

3. **Add `pyproject.toml` and an empty `src/paper_fetch/` package.** Register the package so `pip install -e .` works. At this point nothing imports from it yet.

4. **Move modules one layer at a time**, in dependency order (leaves first):
   - `models.py` (no internal deps)
   - `config.py` (depends on stdlib only)
   - `resolve/` (depends on models + config)
   - `providers/base.py`, then individual providers
   - `formula/` subpackage
   - `service.py` (depends on everything above)
   - `cli.py` last (depends on service)

   After each move, run the full test suite. If a move breaks tests, revert just that move and investigate before proceeding.

5. **Delete `scripts/paper_fetch.py` and friends in the same commit as the final move.** Do not leave a shim. The console script `paper-fetch` defined in `pyproject.toml` replaces it.

6. **Verify against the frozen snapshot from step 1.** Diff `--help` output, diff a real DOI fetch, confirm the test pass list is identical.

7. **Only now** update `install-codex.sh` to point at the new package layout. Keeping this for last means the install flow can't mask a broken package build during migration.

Do not start step 2 (CLI stabilization) until every sub-step above is green.

## Decision Revisit Triggers

Each of the major decisions in this document has a condition under which it should be revisited. If none of these conditions fire, stay the course. If one does, that's the signal to pull this document back up and reconsider — not just patch around it.

- **`CLI + MCP + thin skill` shape** → revisit if CLI usage drops to essentially zero for more than a quarter (no human terminal runs, no CI smoke tests, no debugging sessions). At that point `pure MCP` becomes cheaper to maintain.
- **Hybrid MCP tool granularity (`resolve_paper` + `fetch_paper(modes, strategy)`)** → revisit if any of these signals appear: (a) agents consistently misuse `modes` (e.g. always ask for all three, or never learn to combine `article`+`markdown`); (b) a new output mode needs side effects that other modes must not see, meaning the envelope no longer expresses orthogonal axes; (c) `strategy` grows past ~5 fields and starts needing its own sub-objects, at which point `fetch_paper` should probably split into `fetch_paper_strict` / `fetch_paper_lenient` or similar. The non-negotiable part is the fixed envelope shape — if we ever find ourselves wanting to shape-switch the return based on `modes`, that is the signal the whole contract needs rethinking, not a local patch.
- **`formula/` as its own subpackage** → revisit if we collapse to a single backend (demote to `outputs/formula.py`) or if a third backend lands with per-provider selection rules (may need a `formula/policy.py` on top).
- **Skill source contains only `SKILL.md`, runtime manifests generated at install** → revisit if a runtime appears whose manifest depends on build-time information the install script can't produce (e.g. requires signing, or references content hashes of the skill). At that point the manifest has to live in the repo.
- **Per-adapter download-dir defaults, service has no default** → revisit if a third adapter appears (HTTP server, library embedding) and the two defaults stop covering the space. The rule to preserve is "service layer is cwd-agnostic", not the specific two defaults.
- **YAML as source of truth for routing rules** → revisit only if a non-developer stakeholder needs to edit routing rules directly. At that point a prose-authored format with a generator might be worth the drift risk.
- **One-shot migration with no `scripts/` shim** → this decision is only valid as long as no external caller depends on `scripts/paper_fetch.py`. If you discover such a caller mid-migration, stop and add a shim before proceeding.

## Bottom Line

Recommended target: `CLI + MCP + thin skill`

Reason in one sentence:

This repository already has a valuable command-line product surface and testable fetch core, so MCP should be added as the structured agent interface above that core, not as a replacement for it.

## Revision History

**Revision 7 (2026-04-12)** — backlog closeout follow-through:

- Documented the post-closeout unit-test layout as the active repo-local acceptance baseline in the README, including the split `test_cli` / `test_service` / `test_models_render` / `test_html_generic` / `test_http_cache` entrypoints plus the MCP and provider request-option guards.
- Recorded the fact that the large combined `tests/unit/test_paper_fetch.py` example referenced by older migration notes is now historical context only; ongoing implementation and acceptance work should use the split test modules and the compatibility facades that back them.

**Revision 6 (2026-04-10)** — test-suite layering landed:

- Removed test-directory reshuffling from **Remaining Deltas** because the suite now lives under `tests/unit`, `tests/integration`, and `tests/live`.
- Updated architecture-closeout references to the layered test paths, including `tests/integration/test_architecture_closeout.py`, `tests/live/test_live_publishers.py`, `tests/unit/test_cli.py`, `tests/unit/test_service.py`, and `tests/unit/test_models_render.py`.

**Revision 5 (2026-04-10)** — architecture closeout status made explicit:

- Added a top-level **Status / Remaining Deltas** section that treats the current branch as the closed-out baseline for `core library + CLI + MCP + thin skill`.
- Marked migration-order steps 1-5 as complete on the current branch and reframed the remaining items (`resources/`, `outputs.py`, `formula/backends.py`, test-directory reshuffling) as optional follow-on refinements rather than required next steps.
- Updated the live contract wording to reference the current package entrypoints (`src/paper_fetch/cli.py`, `src/paper_fetch/service.py`) instead of describing the repo as if `scripts/paper_fetch.py` were still the active product surface.
- Replaced the old test-decoupling grep acceptance criterion with the implemented closeout guard in `tests/integration/test_architecture_closeout.py`, which bans legacy import hacks while explicitly allowing `from paper_fetch...` imports through the public package surface.

**Revision 4 (2026-04-10)** — two contract tightenings, no direction changes:

- **`FetchEnvelope.metadata` population rules written as hard invariants.** Revision 3 left an "or always, as a subset" escape hatch that would have let implementers silently populate `metadata` even when it wasn't in `modes`, which would erode the ergonomic property the field exists for. The rules are now: `"metadata" in modes` ⟹ `metadata` is populated; `"metadata" not in modes` ⟹ `metadata` is `null` even if `article` is present; both requested ⟹ `metadata` content equals `article.metadata`. The small amount of duplication when both modes are requested is deliberate and documented.
- **`source` explicitly downgraded from a closed-enum `SourceKind` to an open, documented provenance string.** Revision 3 wrote the field as `SourceKind` but never listed the full set, which would have been worse than either option: implementers would have had to guess whether the type was sealed, and the example values in the doc were already inconsistent with the current internal `ArticleModel.SourceKind` literal ([scripts/article_model.py:11](../../scripts/article_model.py#L11)). The field is now typed `str`, the current canonical values are listed (`elsevier_xml`, `springer_xml`, `wiley_tdm`, `crossref_meta`, `html_fallback`, `metadata_only`), and the doc states explicitly that the set is open and may grow without a contract bump. Fine-grained diagnostics continue to live in `source_trail`; `source` is the coarse agent-readable provenance string. Also added a note that the internal `SourceKind` enum will need reconciling (renaming or mapping at the envelope boundary) as part of step-2 CLI stabilization — the public string is what the contract is anchored on, not the internal name.

**Revision 3 (2026-04-10)** — resolved three issues found by reading this document against the current code:

- **`fetch_paper` return contract rewritten as a fixed `FetchEnvelope`, not a shape-switching union.** The revision-2 signature `fetch_paper(mode) -> ArticleModel | str` would have lost the existing "structured + markdown together" capability that today's CLI already provides via `--format both` ([scripts/paper_fetch.py:361](../../scripts/paper_fetch.py#L361)), and would have forced agents into a double-fetch whenever they needed both the Markdown body and its provenance. The envelope always carries `doi`, `source`, `has_fulltext`, `warnings`, `source_trail`, `token_estimate` at the top level, regardless of which modes were requested. `article`, `markdown`, `metadata` are present as optional payloads. Agents always get provenance without having to dig into `article.quality`, and `ArticleModel.to_ai_markdown` does not need to change to round-trip warnings through the Markdown string.
- **Output modes and fetch strategy separated into two orthogonal axes.** The revision-2 `mode` parameter conflated "what to return" with "how to fetch", which would have erased the existing `--no-html-fallback` capability ([scripts/paper_fetch.py:301](../../scripts/paper_fetch.py#L301)) and left the metadata-only-fallback semantics ambiguous. Output format is now a composable `modes: set[OutputMode]`; fetch behavior is a `strategy: FetchStrategy` dataclass containing `allow_html_fallback`, `allow_metadata_only_fallback`, and `preferred_providers`. The concrete use case "official link only, no HTML fallback, fail loudly if there's no formal full text" now has a single direct expression, with no adapter-layer branching.
- **Migration checklist step 2 expanded** to call out the three real coupling patterns that existed during the closeout work: explicit `sys.path.insert` ([tests/live/test_live_publishers.py:9-14](../../tests/live/test_live_publishers.py#L9-L14)), `importlib.util.spec_from_file_location` loading with `sys.modules` registration (historically in the old combined `tests/unit/test_paper_fetch.py`), and bare imports that depended on those side effects (also historically in that file). The previous "grep `from scripts.`" hint would have missed all three. Added a concrete acceptance-criterion grep.
- Decision Revisit Triggers updated for the new envelope/strategy shape. The non-negotiable invariant is now explicit: the envelope shape is fixed; if we ever want to shape-switch on `modes`, the whole contract needs rethinking, not a local patch.

**Revision 2 (2026-04-10)** — resolved open questions from the initial draft review:

- MCP tool granularity changed from four flat tools to a hybrid: `resolve_paper` stays separate (different return shape, different intent), and `fetch_paper_fulltext` / `fetch_paper_metadata` / `fetch_paper_markdown` merge into `fetch_paper(query, mode=...)`. Service-layer signature updated to match.
- `formula/` confirmed as its own subpackage because two backends (`texmath` primary, `mathml-to-latex` fallback) already exist; documented that backend selection is global with fallback, not per-provider.
- `skills/paper-fetch-skill/agents/openai.yaml` removed from the repo skill source. Codex's manifest is now explicitly framed as an install-time compatibility shim produced by `scripts/install-codex-skill.sh`, not a committed artifact. Repo skill source is `SKILL.md` only.
- Download directory defaults remain adapter-owned: CLI resolves `PAPER_FETCH_DOWNLOAD_DIR` first, then XDG `paper-fetch/downloads`, and only falls back to `./live-downloads` if the user-data path cannot be created; MCP stays on the XDG data dir default. Service layer still has no default.
- Migration is now explicitly one-shot: no `scripts/` compatibility shim, old paths deleted in the same commit as the corresponding move.
- Routing drafts remain documentation only. Current runtime routing truth lives in the conservative code path under `publisher_identity.py` and the resolve/service flow that consumes it.
- Added a **Migration Checklist** expanding step 1 of the migration order into seven ordered sub-steps, with the explicit instruction to decouple tests from `scripts.*` imports *before* moving any files.
- Added a **Decision Revisit Triggers** section listing the conditions under which each major decision should be reopened.

**Revision 1 (2026-04-10)** — initial draft.
