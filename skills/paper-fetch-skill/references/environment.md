# Environment

- `ELSEVIER_API_KEY`: Required for official Elsevier full-text access.
- `ELSEVIER_INSTTOKEN`: Optional institution token for Elsevier entitlement.
- `SPRINGER_META_API_KEY`: Enables Springer Meta API metadata lookups.
- `SPRINGER_OPENACCESS_API_KEY`: Enables Springer Open Access full-text fallback.
- `SPRINGER_FULLTEXT_API_KEY`: Enables Springer Full Text API when paired with its URL template.
- `SPRINGER_FULLTEXT_URL_TEMPLATE`: Required with `SPRINGER_FULLTEXT_API_KEY` for Springer Full Text API retrieval.
- `FLARESOLVERR_URL`: Optional override for the local Science/PNAS FlareSolverr endpoint; defaults to `http://127.0.0.1:8191/v1`.
- `FLARESOLVERR_ENV_FILE`: Required for Science/PNAS; points at a repo-local `vendor/flaresolverr` preset file.
- `FLARESOLVERR_SOURCE_DIR`: Optional override for the repo-local `vendor/flaresolverr` directory.
- `FLARESOLVERR_MIN_INTERVAL_SECONDS`: Required local minimum spacing between Science/PNAS requests.
- `FLARESOLVERR_MAX_REQUESTS_PER_HOUR`: Required local hourly cap for Science/PNAS requests.
- `FLARESOLVERR_MAX_REQUESTS_PER_DAY`: Required local daily cap for Science/PNAS requests.
- `WILEY_TDM_URL_TEMPLATE`: Required Wiley TDM endpoint template for official Wiley full-text retrieval.
- `WILEY_TDM_TOKEN`: Required Wiley TDM token for official Wiley full-text retrieval.
- `PAPER_FETCH_DOWNLOAD_DIR`: Overrides the default CLI or MCP download directory.
- `PAPER_FETCH_RUN_LIVE`: Test-only flag for live publisher integration checks.
- Without `PAPER_FETCH_DOWNLOAD_DIR`, the MCP default directory is `XDG_DATA_HOME/paper-fetch/downloads`, which defaults to `~/.local/share/paper-fetch/downloads`.
