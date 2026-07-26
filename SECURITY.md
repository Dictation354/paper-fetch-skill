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

## Dependency policy

CI audits the complete locked dependency graph. Every known finding fails the
gate unless `security/vulnerability-waivers.json` contains an exact
package/version/advisory match with a non-expired date and a documented reason.
