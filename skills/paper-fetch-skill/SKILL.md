---
name: paper-fetch-skill
description: Use when: fetch one known paper by DOI, URL, or title, or verify a citation list of identifiable papers. Not for: topic surveys, literature discovery, or recommendation-only requests.
---

# Paper Fetch Skill

Use this skill when an agent needs the contents or full-text availability of one specific paper, not a broad topic overview.

## Use This When

- The user gives a `doi`, paper `url`, or paper `title`.
- The user asks to read, summarize, compare, critique, translate, or extract methods/results from a specific paper.
- The user gives a citation list or bibliography and asks which specific papers are readable or fetchable.
- You need compact Markdown or structured metadata that can go directly into model context.

## Avoid This When

- The user wants a broad literature survey or paper discovery.
- The verified full paper text is already in the conversation or workspace and does not need to be re-fetched.

## Workflow

1. Prefer the MCP tools when they are available.
2. In multi-turn sessions, call `list_cached()` or `get_cached(doi)` before re-fetching.
3. If the query may be ambiguous, call `resolve_paper(query | title, authors, year)` first.
4. For bibliography or citation-list tasks, call `batch_check(queries, mode, concurrency)` before per-paper full fetches.
5. Call `has_fulltext(query)` when you only need a cheap readability probe.
6. Call `fetch_paper(query, modes, strategy, include_refs, max_tokens, prefer_cache, download_dir)` when you need AI-friendly Markdown, structured article data, or metadata.
7. Do not conclude "unreadable" just because there is no local PDF or cached text file.
8. If full text is unavailable, continue with the metadata-only result and tell the user they are working from metadata or abstract only.

## Tool Notes

- `resolve_paper(query | title, authors, year)`: normalize a DOI, URL, or title query before a fetch and surface ambiguity early.
- `fetch_paper(...)`: returns one stable JSON payload with top-level provenance plus optional `article`, `markdown`, and `metadata` fields.
- `fetch_paper(...)`: supporting MCP clients also see an `outputSchema`; `progress` and structured log notifications may arrive while `fetch_paper`, `batch_check`, or `batch_resolve` runs.
- `fetch_paper(...)`: recommended defaults are `modes=["article", "markdown"]`, `strategy.asset_profile="none"`, `strategy.allow_html_fallback=true`, `strategy.allow_metadata_only_fallback=true`, `include_refs=null`, `max_tokens="full_text"`, and `prefer_cache=false`.
- `fetch_paper(...)`: `include_refs=null` behaves like `all` when `max_tokens="full_text"`.
- `fetch_paper(...)`: When `max_tokens` is a positive integer, `include_refs=null` behaves like `top10`.
- `fetch_paper(...)`: `prefer_cache=true` tries a local cached FetchEnvelope sidecar before hitting the network.
- `fetch_paper(...)`: when you pass `download_dir`, the MCP server can also expose scoped cache resources for that isolated directory during the current session.
- `fetch_paper(...)`: `strategy.asset_profile="body"` or `all` may also emit a few key local figures as `ImageContent`.
- `fetch_paper(...)`: `science` and `pnas` routes require repo-local FlareSolverr plus explicit local rate-limit env vars, and currently return text-only markdown even when `asset_profile` is `body` or `all`.
- `fetch_paper(...)` and the batch tools: supporting MCP hosts may cancel in-flight requests; the worker cooperatively stops issuing follow-up network requests after cancellation is observed.
- `has_fulltext(query)`: runs a cheap probe over resolution, Crossref metadata, lightweight official metadata probes, and landing-page HTML meta without triggering the full fetch waterfall.
- `has_fulltext(query)`: the success payload is `{query, doi, state, evidence, warnings}`; v1 only actively returns `likely_yes` or `unknown`, while `confirmed_yes` and `no` remain reserved states.
- `batch_resolve(queries, concurrency)` and `batch_check(queries, mode, concurrency)`: default `concurrency=1`; higher values let different hosts overlap while the shared transport still keeps the same host serialized.
- `batch_check(queries, mode, concurrency)`: `mode="metadata"` reuses the cheap probe and returns lightweight provenance fields; `mode="article"` still runs the full fetch path and reports the final full-text verdict.

## References

- Read [`references/environment.md`](references/environment.md) when you need provider credentials, download-dir behavior, or Science / PNAS runtime requirements.
- Read [`references/cli-fallback.md`](references/cli-fallback.md) when MCP is unavailable or the user explicitly wants shell commands.
- Read [`references/failure-handling.md`](references/failure-handling.md) when a result is `ambiguous`, `no_access`, `rate_limited`, or metadata-only.
