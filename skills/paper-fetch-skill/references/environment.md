# Environment

- `ELSEVIER_API_KEY`: Required for official Elsevier full-text access.
- `ELSEVIER_INSTTOKEN`: Optional institution token for Elsevier entitlement.
- `WILEY_TDM_CLIENT_TOKEN`: Optional Wiley Text and Data Mining client token for the official Wiley PDF lane; browser PDF/ePDF fallback can still run without it when the local runtime is ready.
- `FLARESOLVERR_URL`: Optional override for the local Elsevier/Wiley/Science/PNAS FlareSolverr endpoint; defaults to `http://127.0.0.1:8191/v1`.
- `FLARESOLVERR_ENV_FILE`: Required for Elsevier browser fallback and Wiley/Science/PNAS; points at a repo-local `vendor/flaresolverr` preset file.
- `FLARESOLVERR_SOURCE_DIR`: Optional override for the repo-local `vendor/flaresolverr` directory.
- `FLARESOLVERR_MIN_INTERVAL_SECONDS`: Required local minimum spacing between Elsevier browser fallback and Wiley/Science/PNAS requests.
- `FLARESOLVERR_MAX_REQUESTS_PER_HOUR`: Required local hourly cap for Elsevier browser fallback and Wiley/Science/PNAS requests.
- `FLARESOLVERR_MAX_REQUESTS_PER_DAY`: Required local daily cap for Elsevier browser fallback and Wiley/Science/PNAS requests.
- `PAPER_FETCH_DOWNLOAD_DIR`: Overrides the default CLI/MCP download directory.
- `PAPER_FETCH_RUN_LIVE`: Test-only flag for live publisher integration checks.
