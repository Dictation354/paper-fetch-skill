---
name: paper-fetch-skill
description: Use when: fetch one known paper by DOI, URL, or title, or verify a citation list serially. Not for: topic surveys, literature discovery, or recommendation-only requests.
---

# Paper Fetch Skill

## When to Use

Use this skill when an agent needs the contents or availability of one specific paper, not a broad topic overview.

Typical triggers:
- The user gives a `doi`, paper `url`, or paper `title`.
- The user asks to read, summarize, compare, critique, translate, or extract methods/results from a specific paper.
- The user gives a citation list or bibliography and asks which specific papers are readable or fetchable.
- You need compact Markdown or structured metadata that can go directly into model context.

## When NOT to Use

Do not use this skill when:
- The user wants a broad literature survey like "最近有哪些论文讲 X".
- The user wants topic recommendations or paper discovery rather than one identifiable paper.
- The verified full paper text is already in the conversation or workspace and does not need to be re-fetched.

## Call Discipline

- In multi-turn sessions, prefer `list_cached()` or `get_cached(doi)` before re-fetching.
- For bibliography or citation-list tasks, prefer `batch_check(queries, mode)` first.
- Avoid duplicate fetches for the same DOI or URL in one session; reuse the prior Markdown or JSON when possible.
- If a result is `ambiguous`, resolve the DOI first, then retry `fetch_paper`.

## Workflow

1. Prefer the MCP tools when they are available.
2. If the task is "Can you read this paper?" or "Which entries in this citation list are readable?", do not conclude "unreadable" just because there is no local PDF.
3. In multi-turn sessions, call `list_cached()` or `get_cached(doi)` first.
4. For bibliography or citation-list tasks, call `batch_check(queries, mode)` before doing per-paper full fetches.
5. Call `resolve_paper(query)` first if the query may be ambiguous.
6. Call `has_fulltext(query)` when you need a cheap readability probe rather than the full fetch waterfall.
7. Call `fetch_paper(query, modes, strategy, include_refs, max_tokens, download_dir)` when you need AI-friendly Markdown, structured article data, or metadata.
8. If the MCP tools are unavailable in the current runtime, fall back to the CLI:

   ```bash
   paper-fetch --query "<user input>"
   ```

9. If full text is unavailable, continue with the metadata-only result and tell the user they are working from metadata or abstract only.

## MCP Tools

### `resolve_paper(query | title, authors, year)`

Use this when the input may resolve to multiple papers. It accepts either:
- a raw `query`
- or structured `title` plus optional `authors` / `year`

It returns a normalized candidate object and can surface ambiguity before a fetch.

### `fetch_paper(query, modes, strategy, include_refs, max_tokens, download_dir)`

Use this when you need the paper contents. Important behavior:
- The return shape is always a fixed JSON object.
- Top-level provenance fields such as `source`, `warnings`, `source_trail`, `has_fulltext`, and `token_estimate` are always present.
- Unrequested payload fields (`article`, `markdown`, `metadata`) come back as `null`.
- `download_dir` is optional and lets you isolate one task's downloads from the shared MCP cache directory.
- When `strategy.asset_profile` is `body` or `all`, supporting MCP clients may also receive a few key local body figures as `ImageContent` after the JSON block.
- Supporting MCP clients may also receive `notifications/progress` and structured `notifications/message` updates while `fetch_paper`, `batch_check`, or `batch_resolve` is running.
- `provider_hint`, `preferred_providers`, and final `source` may also be `science` or `pnas`; those routes require repo-local FlareSolverr plus explicit local rate-limit env vars, and currently return text-only markdown even when `asset_profile` is `body` or `all`.

Recommended defaults:
- `modes=["article", "markdown"]`
- `strategy.asset_profile="none"`
- `strategy.allow_html_fallback=true`
- `strategy.allow_metadata_only_fallback=true`
- `include_refs=null`
- `max_tokens="full_text"`
- `include_refs=null` behaves like `all` when `max_tokens="full_text"`.
- When `max_tokens` is a positive integer, `include_refs=null` behaves like `top10`.

### `has_fulltext(query)`

Use this when you only need a cheap probe. Important behavior:
- It checks resolution, Crossref metadata, lightweight official metadata probes, and landing-page HTML meta.
- It does not run the full `fetch_paper` waterfall.
- The success payload is `{query, doi, state, evidence, warnings}`.
- Current v1 states are practically `likely_yes` or `unknown`; `confirmed_yes` and `no` are reserved for future iterations.

### `list_cached(download_dir)`

Use this to inspect the MCP cache index without hitting the network. If `download_dir` is omitted, it reads the default shared MCP download directory.

### `get_cached(doi, download_dir)`

Use this to look up cached local files for one DOI and get preferred local paths for Markdown, the primary payload, and assets.

### `batch_resolve(queries)`

Use this to resolve multiple DOI, URL, or title queries serially while reusing one shared HTTP transport.

### `batch_check(queries, mode)`

Use this to check many identifiable papers serially without returning full bodies.
- `mode="metadata"` now reuses the cheap `has_fulltext` probe and returns lightweight fields such as `doi`, `title`, `has_fulltext`, `probe_state`, `evidence`, and `warnings`.
- `mode="article"` still runs the full fetch path and returns the final full-text verdict fields without embedding article bodies.

## Environment

- `ELSEVIER_API_KEY`: Required for official Elsevier full-text access.
- `ELSEVIER_INSTTOKEN`: Optional institution token for Elsevier entitlement.
- `SPRINGER_META_API_KEY`: Enables Springer Meta API metadata lookups.
- `SPRINGER_OPENACCESS_API_KEY`: Enables Springer Open Access full-text fallback.
- `SPRINGER_FULLTEXT_API_KEY`: Enables Springer Full Text API when paired with its URL template.
- `FLARESOLVERR_URL`: Optional override for the local Science/PNAS FlareSolverr endpoint; defaults to `http://127.0.0.1:8191/v1`.
- `FLARESOLVERR_ENV_FILE`: Required for Science/PNAS; points at a repo-local `vendor/flaresolverr` preset file.
- `FLARESOLVERR_SOURCE_DIR`: Optional override for the repo-local `vendor/flaresolverr` directory.
- `FLARESOLVERR_MIN_INTERVAL_SECONDS`: Required local minimum spacing between Science/PNAS requests.
- `FLARESOLVERR_MAX_REQUESTS_PER_HOUR`: Required local hourly cap for Science/PNAS requests.
- `FLARESOLVERR_MAX_REQUESTS_PER_DAY`: Required local daily cap for Science/PNAS requests.
- `PAPER_FETCH_DOWNLOAD_DIR`: Overrides the default CLI or MCP download directory.
- `PAPER_FETCH_RUN_LIVE`: Test-only flag for live publisher integration checks.
- Without `PAPER_FETCH_DOWNLOAD_DIR`, the MCP default directory is `XDG_DATA_HOME/paper-fetch/downloads`, which defaults to `~/.local/share/paper-fetch/downloads`.

## Error Contract

- `ambiguous`: Contains `candidates`; prompt the user to choose and retry.
- `no_access`: Credentials or entitlements are missing; check environment and retry.
- `rate_limited`: Back off and retry later.
- `error`: Any other failure; inspect `reason`.
- These fields appear in both MCP `structuredContent` and CLI stderr JSON.
- CLI exit codes remain `ambiguous=2`, `no_access=3`, `rate_limited=4`.

## CLI Fallback

If MCP is unavailable, use:

```bash
paper-fetch --query "<DOI | URL | title>"
```

Useful options:
- `--format markdown|json|both`
- `--output -|<path>`
- `--output-dir <dir>`
- `--no-download`
- `--save-markdown`
- `--include-refs none|top10|all`
- `--max-tokens 8000`
- `--no-html-fallback`

Output contract:
- `--format markdown`: prints AI-friendly Markdown
- `--format json`: prints `ArticleModel` JSON
- `--format both`: prints `{"article": ..., "markdown": ...}`
- On failure, `stderr` is always JSON

## Failure Handling

If `resolve_paper` or CLI resolution is ambiguous:
- show the candidates to the user
- ask which paper they meant
- retry with the selected DOI

If `fetch_paper` returns metadata only:
- tell the user full text was not available
- continue from the metadata or abstract if that still helps

If a paper is not present as a local PDF or text file:
- do not treat "missing local file" as proof that the paper is unreadable
- verify with MCP or CLI before concluding it is unavailable
