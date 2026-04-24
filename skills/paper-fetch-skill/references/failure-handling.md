# Failure Handling

## Error Contract

- `ambiguous`: Contains `candidates`; prompt the user to choose and retry.
- `no_access`: Credentials or entitlements are missing; inspect `missing_env` when present, then retry.
- `rate_limited`: Back off and retry later.
- `error`: Any other failure; inspect `reason`.
- These fields appear in MCP `structuredContent` and in CLI stderr JSON for runtime fetch failures.
- MCP error payloads may also include `missing_env=[...]` when credentials or required env vars are known.
- CLI runtime fetch exit codes remain `ambiguous=2`, `no_access=3`, `rate_limited=4`; argparse validation errors also exit `2` but are not ambiguity results.

If `resolve_paper` or CLI resolution is ambiguous:

- Show the candidates to the user.
- Ask which paper they meant.
- Retry with the selected DOI.

If `fetch_paper` returns abstract-only or metadata-only:

- Tell the user full text was not available.
- Continue from the metadata or abstract if that still helps.

If `asset_profile=body|all` returns assets but a figure appears missing:

- Inspect `article.assets[*].download_tier`, `width`, `height`, `content_type`, and `source_trail` before treating it as a failure.
- `download_tier=preview` can be acceptable when dimensions meet the threshold and preview accepted appears in the source trail.
- `download_tier=playwright_canvas_fallback` means the browser preserved the visible image after direct image fetch failed.

If table quality warnings appear:

- Treat `table_layout_degraded_count` as a layout-fidelity warning.
- Treat `table_semantic_loss_count` as the stronger signal that table content may be incomplete.

If a paper is not present as a local PDF or text file:

- Do not treat "missing local file" as proof that the paper is unreadable.
- Verify with MCP or CLI before concluding it is unavailable.
