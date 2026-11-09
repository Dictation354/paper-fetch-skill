# Byparr component adaptation

Source: ThePhaseless/Byparr v3.1.1, commit
`b041dd2998110fc61789ae65e2506bd5b79edba5` (GPL-3.0-only).
The verified component retains the complete upstream source and LICENSE. Its
`.dockerignore` symlink is materialized from the in-archive `.gitignore`.

The component and private pure-Python dependencies remain SHA-256 locked.
InvisiblePlaywright 0.47.1 and its required invisible-core 58.56.0 are installed
with the browser/full extra. The core's release seal verifies its Firefox engine.
Windows/Linux x64 use Invisible's native Python protocol transport. macOS and
ARM retain Camoufox 0.5.9 and the host Playwright shared-browser transport; no
unsupported Invisible binary is downloaded. Host Playwright stays >=1.58,<1.63
for Camoufox compatibility; it is not Invisible's browser protocol client.

Both engines use the pinned upstream `src/challenge.py`: locator-based widget
measurement and bounded polling replace the old ClickSolver/closed-shadow addon.
No runtime source, dependency or browser cache is modified. The async controller
binds imports to its deadline/logger/protocol. Invisible executes a compiled sync
form on the existing owning thread: async/await are removed, sleep pumps that
thread's browser loop, and the detection function is converted the same way.
The standalone FastAPI/geo module's Python 3.14-only syntax is not imported on
CPython 3.11–3.14. The solver algorithm, selectors and cooldowns are unchanged.

Invisible owns one browser/context directly. Initial navigation pumps the same
owner loop so request cancellation can close it without crossing threads. Native
profiles retain their PublisherProfileManager lease and directories; filtered
JSON state retains its existing provider/acceptance owner. No state migration is
performed. Invisible's export-only cookie size/session fields are omitted on
cookie import. Its unsupported APIRequestContext is supplied by the existing
host HTTP lane with synchronized cookies; challenged GET recovery still happens
in the same browser context, with the same one-retry policy.

The Camoufox controller identifies pages by their position in its request-owned
context, without evaluating scripts on a challenge page. It does not install the
old unlockShadowRoot addon. Only Camoufox uses its `mw:` evaluation prefix.

Existing readiness, request deadlines, asset policy and unified acceptance remain
authoritative. Operation evidence distinguishes detection, solver invocation,
actual clicks, automatic verification and real response/download success. A DOM
transition without a successful response is `awaiting_response`, not `cleared`.
POSIX uses a request-owned exec shim to map Juggler pipe descriptors after
CPython closes unrelated descriptors; no existing parent descriptor is replaced.
Raw HTTP statuses are retained. No external captcha API credentials are used.
