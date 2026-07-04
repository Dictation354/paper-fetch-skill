# CLI Fallback

If MCP is unavailable, use:

```bash
paper-fetch --query "<DOI | URL | title>"
```

For batch runs, put one DOI, URL, or title per line in a UTF-8 text file; blank lines and lines starting with `#` are ignored:

```bash
paper-fetch --query-file ./queries.txt --output-dir ./papers --batch-concurrency 4
```

Full CLI semantics are documented in [`docs/cli.md`](../../../docs/cli.md).

Useful options:

- `--query-file <path>`: batch mode, one query per line. Mutually exclusive with `--query`.
- `--batch-concurrency <1..8>`: batch concurrency (default: `1`).
- `--batch-results <path>`: JSONL batch summary path (default: `<output-dir>/batch-results.jsonl`).
- `--format markdown|json|both`: serialization format for stdout, `--output`, or the default primary output under `--output-dir` (default: `markdown`).
- `--output -|<path>`: formatted output destination. Explicit `-` means stdout.
- `--output-dir <dir>`: default primary output, Markdown, PDF fallback source, and asset directory. When `--output` is omitted, the CLI writes the primary output here using a sanitized paper stem plus the selected format suffix and does not print the body to stdout.
- `--artifact-mode markdown-assets|all|none`: local artifact retention (default: `markdown-assets`).
- `--no-download`
- `--save-markdown`: extra full-text Markdown save step; only writes when full text was retrieved.
- `--include-refs none|top10|all`
- `--asset-profile none|body|all`
- `--max-tokens full_text|<positive-int>` (default `full_text`)

Output contract:

- `--format markdown`: emits AI-friendly Markdown.
- `--format json`: emits `ArticleModel` JSON.
- `--format both`: emits `{"article": ..., "markdown": ...}`.
- With `--output-dir` and no explicit `--output`, the primary output is written under `--output-dir` instead of stdout.
- Explicit `--output -` keeps stdout output even when `--output-dir` is set.
- With `--query-file`, per-paper body output is never printed to stdout; each item writes its primary output under `--output-dir`, and every item writes one JSON object to the batch JSONL summary.
- Runtime fetch failures from `PaperFetchFailure` or `ProviderFailure` write JSON to `stderr`; argument parsing errors still use argparse's standard stderr format.
