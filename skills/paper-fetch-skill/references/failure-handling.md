# Failure Handling

## Error Contract

- `ambiguous`: Contains `candidates`; prompt the user to choose and retry.
- `no_access`: Credentials or entitlements are missing; inspect `missing_env` when present, then retry.
- `rate_limited`: Back off and retry later.
- `error`: Any other failure; inspect `reason`.
- These fields appear in both MCP `structuredContent` and CLI stderr JSON.
- MCP error payloads may also include `missing_env=[...]` when credentials or required env vars are known.
- CLI exit codes remain `ambiguous=2`, `no_access=3`, `rate_limited=4`.

If `resolve_paper` or CLI resolution is ambiguous:

- Show the candidates to the user.
- Ask which paper they meant.
- Retry with the selected DOI.

If `fetch_paper` returns metadata only:

- Tell the user full text was not available.
- Continue from the metadata or abstract if that still helps.

If a paper is not present as a local PDF or text file:

- Do not treat "missing local file" as proof that the paper is unreadable.
- Verify with MCP or CLI before concluding it is unavailable.
