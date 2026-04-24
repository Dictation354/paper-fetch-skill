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
- `--asset-profile none|body|all`
- `--max-tokens full_text|<positive-int>` (default `full_text`)

Output contract:

- `--format markdown`: prints AI-friendly Markdown.
- `--format json`: prints `ArticleModel` JSON.
- `--format both`: prints `{"article": ..., "markdown": ...}`.
- Runtime fetch failures from `PaperFetchFailure` or `ProviderFailure` write JSON to `stderr`; argument parsing errors still use argparse's standard stderr format.
