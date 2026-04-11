---
name: paper-fetch-skill
description: Fetch the AI-friendly full text of one specific paper by DOI, URL, or title, or verify full-text availability for identifiable papers in a citation list. Use when the user wants to read, summarize, analyze, translate, or extract information from a known paper and you do not already have its text. Not for topic surveys, literature discovery, or recommendation queries.
---

# Paper Fetch Skill

## When to Use

Use this skill when an agent needs the contents of one specific paper, not just a topic overview or recommendation list.

Typical triggers:
- The user gives a `doi`, paper `url`, or only a paper `title`.
- The user asks to read, summarize, compare, critique, translate, or extract methods/results from a specific paper.
- The user gives a citation list or bibliography and asks which specific papers are readable, fetchable, or available in full text.
- You need compact Markdown or structured metadata that can go directly into model context.

## When NOT to Use

Do not use this skill when:
- The user is asking for a broad literature survey like "最近有哪些论文讲 X".
- The user wants recommendations or paper discovery across a topic rather than one identifiable paper.
- You already have the verified full paper text in the conversation or workspace and do not need to confirm availability again.

## Workflow

1. Prefer the MCP tools when they are available.
2. If the task is "Can you read this paper?" or "Which entries in this citation list are readable?", do not conclude "unreadable" just because there is no local PDF. Verify with MCP first for each identifiable paper that lacks verified local full text.
3. For bibliography or citation-list tasks, process the papers one by one. Reuse local PDFs when they are already present, but use MCP to verify entries that are only represented by title, DOI, URL, or incomplete local artifacts.
4. Call `resolve_paper(query)` first if the query may be ambiguous.
5. Call `fetch_paper(query, modes, strategy, include_refs, max_tokens)` to retrieve AI-friendly Markdown, structured article data, or metadata.
6. If the MCP tools are unavailable in the current runtime, fall back to the CLI:

   ```bash
   paper-fetch --query "<user input>"
   ```

7. If full text is unavailable, continue with the metadata-only result and tell the user they are working from metadata / abstract only.

## MCP Tools

### `resolve_paper(query)`

Use this when the input may resolve to multiple papers. It returns a normalized candidate object and can surface ambiguity before a fetch.

### `fetch_paper(query, modes, strategy, include_refs, max_tokens)`

Use this when you need the paper contents. Important behavior:
- The return shape is always a fixed JSON object.
- Top-level provenance fields such as `source`, `warnings`, `source_trail`, `has_fulltext`, and `token_estimate` are always present.
- Unrequested payload fields (`article`, `markdown`, `metadata`) come back as `null`.

Recommended defaults:
- `modes=["article", "markdown"]`
- `strategy.allow_html_fallback=true`
- `strategy.allow_metadata_only_fallback=true`
- `include_refs="top10"`

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
- continue from the metadata / abstract if that still helps

If a paper is not present as a local PDF or text file:
- do not treat "missing local file" as proof that the paper is unreadable
- verify with MCP or CLI before concluding it is unavailable

## Parallel-use Notes

- Avoid firing many parallel requests for the same paper in the same session.
- Prefer one fetch per DOI / URL, then reuse the returned Markdown or JSON.
- If the first call returns `ambiguous`, resolve the DOI before retrying.
- If you wrap the CLI in your own threaded caller, use one process / worker per fetch. The internal HTTP cache transport is not thread-safe.
