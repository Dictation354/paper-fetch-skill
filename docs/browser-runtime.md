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
- CLI/MCP batch wrappers retain an idle shared manager until the overlapping
  batch scope ends. Individual fetch runtimes can therefore close between
  items without repeatedly restarting the provider Chrome process.
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

## Managed Profile Safety

Managed Chrome still takes paper-fetch's `.paper-fetch-profile.lock`, then
conservatively inspects Chromium's `SingletonLock`, `SingletonSocket`, and
`SingletonCookie`. A singleton set is recovered only when it belongs to the
current user and the local lock PID/profile plus socket checks prove that it is
stale. Active, foreign-host, foreign-owner, or otherwise unverifiable state is
left untouched and reported as `managed_chrome_profile_in_use`.

Confirmed stale singleton links are moved, rather than blindly deleted, into
`<profile>/.paper-fetch-browser-diagnostics/singleton-recovery-*/`. The move and
its `recovery.json` record happen before launch. If a failed first launch leaves
a newly stale singleton set, the manager performs this recovery and retries the
launch at most once.

## Failure Diagnostics

Managed Chrome stderr is drained continuously into a bounded 64 KiB tail.
Startup failures write a redacted `chrome-stderr.log` plus `diagnostic.json`
under `<profile>/.paper-fetch-browser-diagnostics/`; only a redacted, truncated
summary is propagated through preflight, provider trace, and manifests.

Browser lifecycle failures use these stable codes:

- `managed_chrome_profile_in_use`
- `managed_chrome_exited_before_cdp`
- `managed_chrome_cdp_timeout`
- `cdp_connect_failed`
- `browser_context_create_failed`
- `browser_page_create_failed`

The structured failure keeps its `stage`, exit code when available, stderr
summary, and diagnostic path. A successful provider PDF fallback does not erase
the preceding HTML browser failure: the result remains successful at the fetch
level but its trace and acceptance remain degraded.

## Batch Shutdown

Cancellation first stops new submissions and lets in-flight workers observe the
shared cancel check. After the configured grace period the batch runner closes
shared browser managers once, then still waits for worker terminal states. The
CLI treats the first Ctrl-C as cooperative cancellation and a second Ctrl-C as
forced browser shutdown.

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
