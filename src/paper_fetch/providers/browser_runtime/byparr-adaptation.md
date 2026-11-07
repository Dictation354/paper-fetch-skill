# Byparr component adaptation

Source: ThePhaseless/Byparr v2.1.0, commit
`1e726296a3143cbce0982cf4fd47a9a3224094e9` (GPL-3.0-only).
The verified component retains the complete upstream source and LICENSE. Its
`.dockerignore` symlink to `.gitignore` is materialized as a regular file with
the same content for portable offline inventories.

The private `byparr_adapter.py` separates navigation, supported Cloudflare
interstitial detection and solving. It reuses the locked upstream ClickSolver,
MAX_ATTEMPTS and solve arguments, without the unconditional networkidle wait or
rewriting response statuses in `read_item`. URL readiness/deadlines remain owned
by the caller. An authenticated loopback service shares the host Playwright
Node installation (`>=1.58,<1.64`, `_sharedBrowser: true`) between async Byparr and
synchronous extraction. Native state also uses `_userDataDir` (available since
Playwright 1.58) under the existing PublisherProfileManager lease. JSON sessions
retain their old directory/acceptance ownership. No state is auto-migrated.

The locked unlockShadowRoot addon script is registered before Firefox starts,
matching upstream preparation before navigation, including future popups/iframes.
Solver initialization is not a solve call. A cleared real document/download stops
solver retries even when a normal page retains a Cloudflare JSD script.

Operation monitors are armed before clicks and follow original pages, popups,
iframes and redirects; they never replay clicks. Context-local solving is
serialized and repeated request observations reuse a task. Navigation modes do
not impose HTML body/networkidle waits on image/download responses. Challenged
GETs are recovered in the same context with at most one bounded retry. Structured
evidence distinguishes management, detection, solver invocation, actual checkbox
click logs and outcomes; auto-validation is never recorded as a solver click.

The host supplies its installed Playwright, Camoufox, Pydantic and their shared
HTTP dependencies. Pure Python Byparr/captcha dependencies are separately locked
in component-manifest.json and installed privately; no Selenium, Chrome or
ChromeDriver is used. The upstream Python 3.14 packaging restriction and
Camoufox 0.4 constraint apply to its standalone distribution; this adapter runs
its source on the project's CPython 3.11–3.14 matrix with Camoufox 0.5.9.
The captcha package is copied to a request-private directory before import,
including its writable addon registry. The verified component is never mutated.
The parent owns request deadlines, cancellation and process-tree cleanup;
filtered JSON storage state is committed only by the existing acceptance owner.
Actual document responses and
project acceptance decide success. No external captcha API credentials are used.
