# Publisher API Notes

This file is a compact API and endpoint constraint reference. It is not the canonical source for provider routing or waterfall order.

Canonical runtime behavior lives in [`docs/providers.md`](../docs/providers.md), `paper_fetch.provider_catalog.PROVIDER_CATALOG`, and `src/paper_fetch/providers/`. Copernicus and MDPI runtime behavior is documented with the supported providers.

## Elsevier

- Official source: Elsevier Developer Portal and related Search / Article APIs.
- Runtime role: primary structured XML/API full-text provider.
- Endpoints:
  - Metadata: `https://api.elsevier.com/content/abstract/doi/{doi}`
  - Full text: `https://api.elsevier.com/content/article/doi/{doi}`
  - PII fallback full text: `https://api.elsevier.com/content/article/pii/{pii}` when merged metadata exposes a LinkingHub or ScienceDirect PII URL.
- Required env: `ELSEVIER_API_KEY`
- Optional entitlement env: `ELSEVIER_INSTTOKEN`, `ELSEVIER_AUTHTOKEN`, `ELSEVIER_CLICKTHROUGH_TOKEN`
- Constraints:
  - Full-text retrieval requests `text/xml` first so the fetcher can parse article XML, object metadata, attachments, figures, supplementary files, bibliography, tables, and formula nodes.
  - DOI XML transient or rate-limit failures may use the PII article endpoint before the API PDF fallback; this still requires Elsevier API credentials and does not use generic HTML scraping.
  - Structured Elsevier bibliography is preferred over metadata fallback when present.
  - Some endpoints are entitlement-gated even with an API key.
- Reference URL: `https://dev.elsevier.com/`

## Wiley TDM API

- Official source: Wiley TDM API.
- Runtime role: optional Wiley PDF lane; Wiley HTML and browser PDF/ePDF behavior is documented in [`docs/providers.md`](../docs/providers.md#wiley-science-pnas-browser-workflow).
- Env: `WILEY_TDM_CLIENT_TOKEN`
- Constraints:
  - Absence of this token does not disable Wiley HTML or browser PDF/ePDF attempts when local browser workflow prerequisites are ready.
  - When configured, the TDM API lane may still be attempted after publisher PDF/ePDF fallback failure or when the local browser runtime is not ready.

## IEEE Xplore Endpoints

- Runtime status: supported through provider-managed IEEE Xplore dynamic HTML plus PDF fallback; no IEEE API key is required.
- Endpoint shapes:
  - Dynamic article HTML: `https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true`
  - References payload: `/rest/document/{article_number}/references`
  - Multimedia payload: `/rest/document/{article_number}/multimedia`
  - PDF candidates include `pdfUrl`, `pdfPath`, and `/stamp/stamp.jsp?arnumber={article_number}`.
- Constraints:
  - The dynamic article endpoint is parsed as HTML even though it looks like a REST path; successful responses have been observed as `text/html;charset=utf-8`.
  - Requests keep page-context headers such as document `Referer`, browser-like UA, `x-security-request: required`, and compatible `Accept`.
  - Full-text validation must reject login pages, challenge pages, access gates, abstract-only pages, empty shells, and unrelated error HTML before Markdown conversion.
  - Do not bypass access controls, solve CAPTCHA flows, automate login, or fabricate entitlement state.
  - IEEE supplementary / multimedia files are recognized only from explicit attachment scope or landing metadata plus multimedia payload; body data/code/repository links and file suffixes are not enough.

## Springer / Science / PNAS / Copernicus / Browser Workflow Providers

- Springer is supported through publisher landing HTML and direct HTTP PDF fallback, not through Springer Nature publisher APIs.
- Science and PNAS are supported through the shared browser workflow family documented in [`docs/providers.md`](../docs/providers.md#elsevier--springer--wiley--science--pnas--ieee--arxiv--copernicus--ams--mdpi--royal-society-publishing--annual-reviews--plos--oxford-academic--acs--iop--aip--tf-的特殊语义).
- Copernicus is supported through public landing HTML discovery and NLM/JATS XML, with text-only PDF fallback before metadata fallback.
- These routes do not have publisher API credentials in this runtime.
- Asset downloads, supplementary scopes, image validation, and PDF text-only fallback behavior are canonical in [`docs/providers.md`](../docs/providers.md#默认输出策略) and [`docs/extraction-rules.md`](../docs/extraction-rules.md).

## Crossref

- Official source: Crossref REST API.
- Runtime role: universal metadata provider, routing signal source, and metadata-only fallback provider.
- Endpoints:
  - DOI lookup: `https://api.crossref.org/works/{doi}`
  - Search: `https://api.crossref.org/works`
- Recommended env: `CROSSREF_MAILTO`
- Constraints:
  - Crossref metadata links may be used for routing and provider handoff.
  - Unsupported publishers do not fall through to a generic full-text downloader.
- Reference URL: `https://www.crossref.org/documentation/retrieve-metadata/rest-api/`
