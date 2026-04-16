# Environment

- `ELSEVIER_API_KEY`: Required for official Elsevier full-text access.
- `ELSEVIER_INSTTOKEN`: Optional institution token for Elsevier entitlement.
- `FLARESOLVERR_URL`: Optional override for the local Wiley/Science/PNAS FlareSolverr endpoint; defaults to `http://127.0.0.1:8191/v1`.
- `FLARESOLVERR_ENV_FILE`: Required for Wiley/Science/PNAS; points at a repo-local `vendor/flaresolverr` preset file.
- `FLARESOLVERR_SOURCE_DIR`: Optional override for the repo-local `vendor/flaresolverr` directory.
- `FLARESOLVERR_MIN_INTERVAL_SECONDS`: Required local minimum spacing between Wiley/Science/PNAS requests.
- `FLARESOLVERR_MAX_REQUESTS_PER_HOUR`: Required local hourly cap for Wiley/Science/PNAS requests.
- `FLARESOLVERR_MAX_REQUESTS_PER_DAY`: Required local daily cap for Wiley/Science/PNAS requests.
- `PAPER_FETCH_DOWNLOAD_DIR`: Overrides the default CLI or MCP download directory.
- `PAPER_FETCH_RUN_LIVE`: Test-only flag for live publisher integration checks.
- Without `PAPER_FETCH_DOWNLOAD_DIR`, the MCP default directory is `XDG_DATA_HOME/paper-fetch/downloads`, which defaults to `~/.local/share/paper-fetch/downloads`.
