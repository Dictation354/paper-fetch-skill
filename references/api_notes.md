# Official API Notes

This file is the manual source of truth for which publisher routes count as supported official APIs in v1.

## Springer

- Official source: Springer Nature Developer Portal and Link API documentation.
- Status: actively maintained official publisher access path for metadata and content workflows.
- Current implementation:
  - Metadata: `https://api.springernature.com/meta/v2/json`
  - Open-access full text: `https://api.springernature.com/openaccess/jats`
  - Full text: configurable via `SPRINGER_FULLTEXT_URL_TEMPLATE`
  - When Springer returns XML with `graphic` or `media` references and an output directory is provided, the fetcher also downloads linked images and supplementary files from `static-content.springer.com`.
  - Required env:
    - `SPRINGER_META_API_KEY` for Meta API
    - `SPRINGER_OPENACCESS_API_KEY` for Open Access API
    - `SPRINGER_FULLTEXT_API_KEY` plus `SPRINGER_FULLTEXT_URL_TEMPLATE` for Full Text API
  - Optional Full Text env:
    - `SPRINGER_FULLTEXT_AUTH_HEADER`
    - `SPRINGER_FULLTEXT_ACCEPT`
- Route when:
  - The journal record declares `official_provider: springer`, or
  - The DOI uses a supported Springer-pattern prefix such as `10.1038/`, `10.1007/`, or `10.1186/`.
- Common constraints:
  - Meta API, Open Access API, and Full Text API are distinct product lines and may require different credentials or entitlements.
  - Not every Springer Nature imprint should be inferred from DOI alone.
- Reference URLs:
  - `https://dev.springernature.com/`
  - `https://support.springernature.com/en/support/solutions/articles/6000195668-springer-nature-api-portal`

## Elsevier

- Official source: Elsevier Developer Portal and related Search/Article APIs.
- Status: actively maintained official publisher access path for metadata retrieval.
- Current implementation:
  - Metadata: `https://api.elsevier.com/content/abstract/doi/{doi}`
  - Full text: `https://api.elsevier.com/content/article/doi/{doi}`
  - Full-text retrieval now requests `text/xml` first so the fetcher can parse Elsevier `objects` and `attachment-metadata-doc` sections.
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

## Wiley

- Official source: Wiley Online Library text and data mining access flow.
- Status: official access path, but entitlement and token requirements are usually stricter than generic metadata APIs.
- Current implementation:
  - Metadata endpoint is not inferred automatically.
  - Full text can be enabled with `WILEY_TDM_URL_TEMPLATE` and `WILEY_TDM_TOKEN`.
  - The public TDM endpoint currently returns PDF by default in this project verification.
  - Optional header override: `WILEY_TDM_AUTH_HEADER`
- Route when:
  - The journal record declares `official_provider: wiley`, or
  - The DOI uses a strongly indicative Wiley prefix such as `10.1002/` or `10.1111/`.
- Common constraints:
  - Token, institution, or license requirements may apply.
  - Wiley's public TDM guidance and package updates emphasize PDF download workflows.
  - XML, JATS, or other formats should not be assumed from the public endpoint; treat them as separately enabled capabilities that require explicit Wiley documentation or support confirmation.
  - Treat Wiley as supported only for journals explicitly mapped or DOI patterns that the router considers reliable.
- Reference domains:
  - `https://onlinelibrary.wiley.com/`
  - `https://www.wiley.com/`

## Crossref

- Official source: Crossref REST API documentation.
- Role in this skill: universal fallback provider, not the primary route when a supported official API is available.
- Current implementation:
  - Metadata: `https://api.crossref.org/works/{doi}` or `https://api.crossref.org/works`
  - Recommended env: `CROSSREF_MAILTO`
  - Crossref metadata links may be used for a secondary full-text download attempt when official full-text access is unavailable.
- Route when:
  - No supported official provider can be chosen with enough confidence.
  - The preferred official provider returns `no_access`, `no_result`, or `error`.
- Reference URL:
  - `https://www.crossref.org/documentation/retrieve-metadata/rest-api/`
