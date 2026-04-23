# CLI Fallback

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

Output contract:

- `--format markdown`: prints AI-friendly Markdown.
- `--format json`: prints `ArticleModel` JSON.
- `--format both`: prints `{"article": ..., "markdown": ...}`.
- On failure, `stderr` is always JSON.
