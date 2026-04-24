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
6. Call `provider_status()` before the first fetch when provider credentials or Wiley / Science / PNAS local runtime readiness may matter.
7. Call `fetch_paper(query, modes, strategy, include_refs, max_tokens, prefer_cache, download_dir)` when you need AI-friendly Markdown, structured article data, or metadata.
8. Do not conclude "unreadable" just because there is no local PDF or cached text file.
9. If full text is unavailable, continue with the returned abstract-only or metadata-only result and tell the user they are working from metadata or abstract only.

## Tool Notes

- `resolve_paper(query | title, authors, year)`: normalize a DOI, URL, or title query before a fetch and surface ambiguity early.
- `summarize_paper(query, focus)` and `verify_citation_list(citations, mode)`: MCP prompt templates that hosts can surface directly for single-paper summaries and citation-list triage.
- `fetch_paper(...)`: returns one stable JSON payload with top-level provenance plus optional `article`, `markdown`, and `metadata` fields.
- `fetch_paper(...)`: top-level `token_estimate_breakdown={abstract,body,refs}` helps decide when to tighten `include_refs` or retry with a smaller numeric `max_tokens`.
- `fetch_paper(...)`: supporting MCP clients also see an `outputSchema`; `progress` and structured log notifications may arrive while `fetch_paper`, `batch_check`, or `batch_resolve` runs.
- `fetch_paper(...)`: recommended defaults are `modes=["article", "markdown"]`, `strategy.asset_profile=null (provider default)`, `strategy.allow_metadata_only_fallback=true`, `include_refs=null`, `max_tokens="full_text"`, and `prefer_cache=false`.
- `fetch_paper(...)`: `include_refs=null` behaves like `all` when `max_tokens="full_text"`.
- `fetch_paper(...)`: When `max_tokens` is a positive integer, `include_refs=null` behaves like `top10`.
- `fetch_paper(...)`: `prefer_cache=true` resolves the query to a DOI, then tries a matching local FetchEnvelope sidecar before running the full fetch waterfall.
- `fetch_paper(...)`: when you pass `download_dir`, the MCP server can also expose scoped cache resources for that isolated directory during the current session.
- `fetch_paper(...)`, `list_cached()`, and `get_cached()`: hosts that support MCP resource-list notifications may receive `resources/list_changed` when cache resource URIs are added or removed.
- `fetch_paper(...)`: `strategy.asset_profile="body"` or `all` may also emit a few key local figures as `ImageContent`.
- `fetch_paper(...)`: optional `strategy.inline_image_budget={max_images,max_bytes_per_image,max_total_bytes}` tunes the default inline image caps of `3` figures, `2 MiB` each, and `8 MiB` total; any resulting zero disables inline images.
- `fetch_paper(...)`: when assets are returned, inspect `article.assets[*].render_state`, `download_tier`, `content_type`, `downloaded_bytes`, `width`, and `height` before calling an image missing. A `preview` tier can be acceptable when dimensions meet the threshold and warnings/source trail say preview was accepted.
- `fetch_paper(...)`: `article.quality.semantic_losses.table_layout_degraded_count` means table layout was flattened for Markdown; `table_semantic_loss_count` is the stronger signal that content was actually lost.
- `fetch_paper(...)`: formula LaTeX is normalized for common publisher macros such as `\updelta` and `\mspace{Nmu}` before Markdown is returned.
- `fetch_paper(...)`: `science` and `pnas` require repo-local FlareSolverr plus explicit local rate-limit env vars. `wiley` uses the same runtime for HTML and seeded-browser PDF/ePDF, while `WILEY_TDM_CLIENT_TOKEN` can enable its official TDM API PDF lane without browser readiness. `wiley` publishes public source `wiley_browser`; `science` and `pnas` keep their existing public source names. Their HTML success paths support `asset_profile="body"` / `all` asset downloads; PDF/ePDF fallback remains text-only.
- `fetch_paper(...)` and the batch tools: supporting MCP hosts may cancel in-flight requests; the worker cooperatively stops issuing follow-up network requests after cancellation is observed.
- `has_fulltext(query)`: runs a cheap probe over resolution, Crossref metadata, the remaining lightweight Elsevier metadata probe, and landing-page HTML meta without triggering the full fetch waterfall.
- `has_fulltext(query)`: the success payload is `{query, doi, state, evidence, warnings}`; v1 only actively returns `likely_yes` or `unknown`, while `confirmed_yes` and `no` remain reserved states.
- `provider_status()`: returns stable local diagnostics for `crossref`, `elsevier`, `springer`, `wiley`, `science`, and `pnas` without calling remote publisher APIs.
- `provider_status()`: provider-level `status` uses `ready`, `partial`, `not_configured`, `rate_limited`, or `error`; inspect `checks=[...]` for capability-level or runtime-level details before choosing a fetch path.
- `batch_resolve(queries, concurrency)` and `batch_check(queries, mode, concurrency)`: default `concurrency=1`; accepted range is `1..8`; higher values let different hosts overlap while the shared transport still keeps the same host serialized, and each call accepts at most `50` queries.
- `batch_check(queries, mode, concurrency)`: `mode="metadata"` reuses the cheap probe and returns lightweight provenance fields; `mode="article"` still runs the full fetch path and reports the final full-text verdict.
- The read-only MCP tools now advertise `ToolAnnotations` hints (`readOnlyHint=true`), so capable hosts may auto-approve them more smoothly; `fetch_paper(...)` remains writable because it may refresh local cache files.

## References

- Read [`references/environment.md`](references/environment.md) when you need provider credentials, download-dir behavior, or Wiley / Science / PNAS runtime requirements.
- Read [`references/cli-fallback.md`](references/cli-fallback.md) when MCP is unavailable or the user explicitly wants shell commands.
- Read [`references/failure-handling.md`](references/failure-handling.md) when a result is `ambiguous`, `no_access`, `rate_limited`, or metadata-only.
