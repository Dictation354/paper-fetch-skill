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

Direct HTTP requests accept only HTTP(S), standard ports, no URL userinfo, no
HTTPS-to-HTTP downgrade, and public DNS answers. Every redirect hop is validated
again; standard sensitive headers are stripped on cross-origin redirects. After
validation, requests use the shared hostname connection pool. Provider catalog
domains and sensitive-header declarations describe routing and execution policy,
but are not an implicit network authorization allowlist. A caller-supplied
`SafeRemoteUrlPolicy.allowed_hosts` remains fail-closed and is enforced on every
hop.

Browser navigation, redirects, and subresources follow the selected browser
runtime's native networking behavior. Browser-owned image, file, and PDF bytes
may be used for one recovery after a direct 401/403; those bytes still pass
Content-Length/actual-byte, MIME, pixel, per-article budget, cancellation,
exclusive staging, and atomic-publication checks. Browser cookies retain their
standard domain, path, secure, and expiry scope when converted for a controlled
direct request.

Structured and human-readable logging centrally removes URL query data and
standard or provider-specific credentials. MCP requests share one routing
handler whose request target is isolated with context-local state.
Live-test environment mappings render names only. CI scans every artifact and
release upload candidate for raw and URL-encoded configured secret values; a
match reports only the variable name and file path and blocks publication.

## Dependency policy

CI audits the complete locked dependency graph. Every known finding fails the
gate unless `security/vulnerability-waivers.json` contains an exact
package/version/advisory match with a non-expired date and a documented reason.
