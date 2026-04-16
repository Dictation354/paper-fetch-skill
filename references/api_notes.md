# Official API Notes

This file is the manual source of truth for which publisher routes count as supported official APIs in v1.

## Elsevier

- Official source: Elsevier Developer Portal and related Search/Article APIs.
- Status: the only publisher full-text route in this runtime that still uses an official publisher API.
- Current implementation:
  - Metadata: `https://api.elsevier.com/content/abstract/doi/{doi}`
  - Full text: `https://api.elsevier.com/content/article/doi/{doi}`
  - Full-text retrieval requests `text/xml` first so the fetcher can parse Elsevier `objects` and `attachment-metadata-doc` sections.
  - When Elsevier XML contains object or attachment metadata and an output directory is provided, the fetcher also downloads linked figures and supplementary files.
  - Required env: `ELSEVIER_API_KEY`
  - Optional entitlement env: `ELSEVIER_INSTTOKEN`, `ELSEVIER_AUTHTOKEN`, `ELSEVIER_CLICKTHROUGH_TOKEN`
- Route when:
  - The journal record declares `official_provider: elsevier`, or
  - The DOI uses the strongly indicative prefix `10.1016/`.
- Common constraints:
  - API key is typically required.
  - Some endpoints are entitlement-gated.
- Reference URL:
  - `https://dev.elsevier.com/`

## Springer

- Runtime status: supported, but not through Springer Nature publisher APIs.
- Current implementation:
  - Metadata comes from Crossref merge and landing-page signals.
  - Full text is fetched from the publisher landing page HTML.
  - Preferred landing URL comes from merged metadata; if missing, the runtime resolves `https://doi.org/{doi}` and follows the final landing page.
  - HTML extraction is provider-owned and reuses the existing HTML parsing stack internally.
- Route when:
  - The journal record declares `official_provider: springer`, or
  - The DOI uses a supported Springer-pattern prefix such as `10.1038/`, `10.1007/`, or `10.1186/`.
- Common constraints:
  - The runtime does not use Springer publisher endpoints or credentials.
  - Springer full-text success depends on the landing HTML being directly readable enough for extraction.

## Wiley

- Runtime status: supported, but not through Wiley publisher APIs or TDM tokens.
- Current implementation:
  - Metadata comes from Crossref merge and landing-page signals.
  - Full text uses a local browser workflow: `HTML -> PDF fallback -> metadata-only`.
  - Candidate URLs prefer Crossref or landing-page URLs and fall back to DOI resolution when needed.
  - HTML is fetched through repo-local FlareSolverr; PDF fallback uses Playwright.
- Route when:
  - The journal record declares `official_provider: wiley`, or
  - The DOI uses a strongly indicative Wiley prefix such as `10.1002/` or `10.1111/`.
- Common constraints:
  - The runtime does not use Wiley publisher tokens or API endpoints.
  - This route depends on repo-local FlareSolverr readiness and explicit local rate-limit settings.

## Science / PNAS

- Runtime status: supported via the same local browser workflow family as Wiley.
- Current implementation:
  - Metadata comes from Crossref merge and landing-page signals.
  - Full text uses provider-managed `HTML -> PDF fallback -> metadata-only`.
  - HTML is fetched through repo-local FlareSolverr; PDF fallback uses Playwright.
- Common constraints:
  - The runtime does not use publisher APIs for these providers.
  - These routes depend on repo-local FlareSolverr readiness and explicit local rate-limit settings.

## Crossref

- Official source: Crossref REST API documentation.
- Role in this skill: universal metadata provider, routing signal source, and metadata-only fallback provider.
- Current implementation:
  - Metadata: `https://api.crossref.org/works/{doi}` or `https://api.crossref.org/works`
  - Recommended env: `CROSSREF_MAILTO`
  - Crossref metadata links may be used for routing or a secondary full-text download attempt when publisher-managed retrieval is unavailable.
- Route when:
  - No supported publisher route can be chosen with enough confidence.
  - A metadata-only result is still useful after publisher full-text retrieval fails.
- Reference URL:
  - `https://www.crossref.org/documentation/retrieve-metadata/rest-api/`
