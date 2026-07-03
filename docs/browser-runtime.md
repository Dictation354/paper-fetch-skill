# Browser Runtime

The supported browser runtime is the browser-neutral CDP facade in
`paper_fetch.providers.browser_runtime`. The production backend is
`cloakbrowser`, but provider workflow code should depend on the public facade
instead of importing `_cloakbrowser` helpers directly.

## Ownership

- `RuntimeContext` owns process-shared `BrowserContextManager` leases keyed by
  binary path, CDP endpoint, external-new-context mode, profile dir, and user
  data dir. Leases are closed by `RuntimeContext.close()` and by an `atexit`
  fallback.
- `browser_runtime.paths` owns provider profile and storage-state resolution,
  including provider defaults, explicit profile/user-data dirs, Wiley legacy
  storage env, atomic storage-state writes, and the write lock.
- `browser_workflow` owns shared HTML bootstrap, seeded PDF fallback, article
  assembly, and browser-backed asset download.

## Storage State

When no explicit profile or user data dir is configured, browser-backed
providers use `publisher-browser-profiles/<provider>/storage-state.json` under
the paper-fetch user data directory. Saves are filtered to the active publisher
URL when possible and written atomically behind a file lock.

`paper-fetch auth <provider>` and `paper-fetch browser-preflight` use the same
path resolver as fetches, so auth, preflight, HTML fetch, and PDF fallback agree
on the storage-state file.

## External CDP

`CLOAKBROWSER_CDP_ENDPOINT` connects to an existing browser. By default,
paper-fetch borrows the first existing browser context, injects storage-state
cookies when possible, and reports ignored context options such as user-agent or
viewport in diagnostics.

Set `PAPER_FETCH_CDP_EXTERNAL_NEW_CONTEXT=1` to create a fresh context inside
the external browser instead of borrowing the existing one.

Use [`providers.md`](providers.md), [`deployment.md`](deployment.md), and
[`architecture/overview.md`](architecture/overview.md) for provider-specific
browser routes, environment variables, and runtime ownership boundaries.
