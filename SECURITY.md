# Security Policy

## Supported versions

Security fixes are provided for the latest stable release of
`paper-fetch-skill`. Users should upgrade before reporting a problem that is
already fixed in the current release.

## Reporting a vulnerability

Please use the repository's private GitHub security-advisory form instead of a
public issue. Include affected versions, a minimal reproduction, impact, and
any suggested mitigation. Do not include credentials, publisher session data,
browser profiles, or copyrighted paper content.

The maintainers will acknowledge a complete report, validate its scope, and
coordinate a fix and disclosure timeline. Security boundaries around login,
paywalls, entitlements, and publisher access controls will not be bypassed.

## Network and diagnostic boundaries

Direct HTTP connections are pinned to the public IP addresses validated by the
remote-URL policy while retaining the original HTTP Host and TLS identity.
Redirects are revalidated hop by hop, and provider-declared credentials require
a route host allowlist and are stripped on cross-origin redirects. Browser
navigation and asset requests use the same URL/IP policy; credentialed browser
contexts are same-origin only, with cross-origin assets delegated to the
controlled direct transport. New contexts block service workers and install a
context-wide interceptor before credentials or pages are added; an external
context that cannot honor that boundary is not borrowed. Browser cookies retain their standard domain,
path, secure, and expiry scope when converted for direct requests.

Structured and human-readable logging centrally removes URL query data and
standard or provider-specific credentials. MCP requests share one routing
handler whose request target is isolated with context-local state.

## Dependency policy

CI audits the complete locked dependency graph. Every known finding fails the
gate unless `security/vulnerability-waivers.json` contains an exact
package/version/advisory match with a non-expired date and a documented reason.
