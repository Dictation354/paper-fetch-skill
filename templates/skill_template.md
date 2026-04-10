---
name: paper-fetch-skill
description: Fetch the AI-friendly full text of one specific paper by DOI, URL, or title. Use when the user wants to read, summarize, analyze, translate, or extract information from a known paper and you do not already have its text. Not for topic surveys, literature discovery, or recommendation queries.
---

# Paper Fetch Skill

## When to Use

Use this skill when an agent needs the contents of one specific paper, not just a route decision or a topic overview.

Typical triggers:
- The user gives a `doi`, paper `url`, or only a paper `title`.
- The user asks to read, summarize, compare, critique, translate, or extract methods/results from a specific paper.
- You need compact Markdown or JSON that can go directly into model context.

## When NOT to Use

Do not use this skill when:
- The user is asking for a broad literature survey like "最近有哪些论文讲 X".
- The user wants recommendations or paper discovery across a topic rather than one identifiable paper.
- You already have the full paper text in the conversation or workspace.

## Workflow

1. Run the command below. The paths are absolute, so the current working directory does not matter.

   ```bash
   ${PY_BIN} ${SCRIPT} --query "<user input>"
   ```

2. Let the tool resolve DOI / URL / title into a normalized lookup target.
3. Prefer official publisher full text when available.
4. If official full text is unavailable or incomplete, let the tool try HTML fallback.
5. If full text still is not available, use the metadata-only result and tell the user you are working from metadata / abstract only.

## Inputs

- `doi` such as `10.1038/s41586-020-2649-2`
- `url` such as a publisher landing page
- `title` or a distinctive title fragment

## Options

- `--format markdown` (default) / `json` / `both`
- `--include-refs top10` (default) / `none` / `all`
- `--max-tokens 8000` (default) caps AI Markdown size
- `--output -` (default, stdout) or a file path
- `--output-dir <dir>` for saving raw provider downloads such as Wiley PDFs
- `--no-download` to prevent binary/PDF payloads from being written to disk
- `--no-html-fallback` to disable the trafilatura HTML path

## Outputs

- `--format markdown`: AI-friendly Markdown on `stdout`
- `--format json`: `ArticleModel` JSON on `stdout`
- `--format both`: JSON envelope `{"article": ..., "markdown": ...}` on `stdout`
- On failure, `stderr` always emits JSON

## stderr JSON Schema

```json
{
  "status": "error | ambiguous",
  "reason": "human-readable explanation",
  "candidates": [
    {
      "doi": "10....",
      "title": "candidate title",
      "journal_title": "journal",
      "published": "YYYY-MM-DD",
      "landing_page_url": "https://...",
      "provider_hint": "elsevier | springer | wiley | crossref",
      "score": 0.0
    }
  ]
}
```

Field notes:
- `status` is always present.
- `reason` is always present.
- `candidates` is present for `status: ambiguous`; otherwise it may be `null`.
- Exit code is `2` for `ambiguous`, `1` for other failures.

## Examples

### DOI success

```bash
${PY_BIN} ${SCRIPT} --query "10.1038/s41586-020-2649-2"
```

Typical `stdout` prefix:

```text
---
title: "..."
source: "..."
has_fulltext: true
---
```

### Ambiguous title

```bash
${PY_BIN} ${SCRIPT} --query "Deep learning for land cover classification"
```

Typical `stderr`:

```json
{"status":"ambiguous","reason":"Query resolution is ambiguous; choose one of the DOI candidates.","candidates":[...]}
```

Action:
- Show the candidates to the user.
- Ask which paper they meant.
- Re-run with the selected DOI.

### Metadata-only fallback

```bash
${PY_BIN} ${SCRIPT} --query "10.1111/example" --format json
```

Typical `stdout` fields:

```json
{"source":"crossref_meta","quality":{"has_fulltext":false,"warnings":[...]}}
```

Action:
- Tell the user the workflow could only recover metadata / abstract.
- Offer to continue from the abstract or try a different source they provide.

## Parallel-use Notes

- Avoid firing many parallel requests for the same paper in the same session.
- Prefer one fetch per DOI / URL, then reuse the returned Markdown or JSON.
- If the first call returns `ambiguous`, resolve the DOI before retrying.
- If you wrap the script in your own threaded caller, use one process / worker per fetch. The internal HTTP cache transport is not thread-safe.

## Local Resources

Use these repository files directly if you need implementation details:
- `${SCRIPT}`
- `${RESOLVE_SCRIPT}`
- `${MODEL_SCRIPT}`
- `${HTML_PROVIDER}`
- `${IDENTITY_SCRIPT}`
- `${CLIENT_REGISTRY_SCRIPT}`

## Installation Location

- Skill directory: `${SKILL_DIR}`
- Code + `.env`: `${REPO_DIR}`
- Python venv: `${VENV_DIR}`
- If this repo is moved, re-run the installer so the absolute paths inside `SKILL.md` are refreshed.
