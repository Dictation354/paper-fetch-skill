# Browser Runtime

The supported browser runtime is the browser-neutral facade in
`paper_fetch.providers.browser_runtime`. `camoufox` is the sole default;
`cloakbrowser` is a deprecated compatibility backend selected only with
`PAPER_FETCH_BROWSER_BACKEND=cloakbrowser`. Provider workflow code must depend
on the public facade instead of importing backend helpers directly. Selection
is strict and failures never trigger an automatic cross-backend fallback.

## Ownership

- `RuntimeContext` owns process-shared `BrowserContextManager` leases keyed by
  binary path, CDP endpoint, external-new-context mode, profile dir, and user
  data dir. Leases are closed by `RuntimeContext.close()` and by an `atexit`
  fallback.
- Camoufox managers are thread-affine. A `RuntimeContext` reuses one native
  Camoufox process per owning thread/headless/binary key and creates a fresh
  fingerprinted context for each browser operation. Camoufox-backed assets are
  serialized rather than sharing sync Playwright objects across workers.
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

Camoufox uses
`publisher-browser-profiles/<provider>-camoufox/storage-state.json` by default,
so Firefox and Chromium state are not mixed. Headed Camoufox auth additionally
uses that provider directory as a persistent profile, then exports filtered
storage-state for ordinary isolated contexts.

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

External CDP is CloakBrowser-only. Camoufox v1 launches locally through native
Firefox/Juggler and does not use the experimental remote WebSocket server.

## Backend configuration

The generic variables are `PAPER_FETCH_BROWSER_BACKEND`,
`PAPER_FETCH_BROWSER_HEADLESS`, `PAPER_FETCH_BROWSER_TIMEOUT_MS`,
`PAPER_FETCH_BROWSER_BINARY_PATH`, `PAPER_FETCH_BROWSER_PROFILE_DIR`, and
`PAPER_FETCH_BROWSER_USER_DATA_DIR`. Generic values take precedence over the
legacy `CLOAKBROWSER_*` equivalents. Legacy values are read only by the
CloakBrowser backend; CDP variables are also CloakBrowser-only.

Camoufox never receives `PAPER_FETCH_BROWSER_USER_AGENT`, a Chrome UA, a fixed
viewport, or fingerprint-related overrides. Full HTML navigation waits for
`commit` and then the existing provider DOM readiness predicate. Its fast path
only blocks `media`, not images, fonts, stylesheets, or WebGL-related resources.
See [`browser-backends.md`](browser-backends.md) for selection, installation,
headed auth, offline runtime preparation, and live acceptance.

Use [`providers.md`](providers.md), [`deployment.md`](deployment.md), and
[`architecture/overview.md`](architecture/overview.md) for provider-specific
browser routes, environment variables, and runtime ownership boundaries.
