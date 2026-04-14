# Upstream Reference

- Source path: `/home/dictation/test`
- Copied on: `2026-04-14`
- Purpose: repo-local FlareSolverr workflow and Science/PNAS reference implementation

Update rule:

- Refresh `vendor/flaresolverr/` from `/home/dictation/test` first.
- Then update extracted runtime code under `src/paper_fetch/providers/`.
- Runtime code must not read `/home/dictation/test` directly.
