# Publisher Route Notes

This file is a human-maintained route reference for v1. Runtime behavior is authoritative in `src/paper_fetch/providers/`, `src/paper_fetch/publisher_identity.py`, and `src/paper_fetch/workflow/`. Provider fallback order is now composed through the internal `_waterfall` runner, while provider steps keep their own payloads, warnings, and source markers. Elsevier is the primary structured XML/API full-text route; Wiley additionally has an optional TDM API PDF lane. Springer, Wiley HTML/browser PDF, Science, and PNAS are provider-managed routes with the constraints below.

## Elsevier

- Official source: Elsevier Developer Portal and related Search/Article APIs.
- Status: the primary publisher XML/API full-text route in this runtime.
- Current implementation:
  - Metadata: `https://api.elsevier.com/content/abstract/doi/{doi}`
  - Full text: `https://api.elsevier.com/content/article/doi/{doi}`
  - Full-text retrieval requests `text/xml` first so the fetcher can parse Elsevier `objects` and `attachment-metadata-doc` sections.
  - When Elsevier XML contains object or attachment metadata and an output directory is provided, the fetcher also downloads linked figures and supplementary files.
  - Structured Elsevier bibliography is preferred over Crossref reference fallback when available; numbered labels, authors, titles, source, pages, year, and DOI are preserved as far as the XML provides them.
  - Complex table spans are semantically expanded into rectangular Markdown cells; layout degradation is reported separately from semantic content loss.
  - Formula LaTeX is normalized after conversion, including upright Greek aliases and `\mspace{Nmu}` spacing macros.
  - Required env: `ELSEVIER_API_KEY`
  - Optional entitlement env: `ELSEVIER_INSTTOKEN`, `ELSEVIER_AUTHTOKEN`, `ELSEVIER_CLICKTHROUGH_TOKEN`
- Route when:
  - The landing-page domain or Crossref publisher-name signal maps to `elsevier`, or
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
  - Springer / Nature HTML cleanup removes site chrome such as save actions, aims/scope blocks, duplicate title headings, preview notices, and figure download-control text.
  - Nature / Springer inline table pages are injected back into the body; known image-only Extended Data Tables can be retained as table image assets or explicit `[Table body unavailable: ...]` placeholders.
  - Raw `span.mathjax-tex` content is normalized through the shared LaTeX macro normalizer before Markdown rendering.
- Route when:
  - The landing-page domain or Crossref publisher-name signal maps to `springer`, or
  - The DOI uses a supported Springer-pattern prefix such as `10.1038/`, `10.1007/`, or `10.1186/`.
- Common constraints:
  - The runtime does not use Springer publisher endpoints or credentials.
  - Springer full-text success depends on the landing HTML being directly readable enough for extraction.

## Wiley

- Runtime status: supported via provider-managed HTML plus an optional Wiley TDM API PDF lane.
- Current implementation:
  - Metadata comes from Crossref merge and landing-page signals.
  - Full text uses provider-managed `FlareSolverr HTML -> Wiley TDM API PDF -> seeded-browser publisher PDF/ePDF -> abstract-only / metadata-only`.
  - Candidate URLs prefer Crossref or landing-page URLs and fall back to DOI resolution when needed.
  - HTML is fetched through repo-local FlareSolverr; the optional Wiley TDM API lane uses `WILEY_TDM_CLIENT_TOKEN`; publisher PDF/ePDF fallback uses Playwright.
- Route when:
  - The landing-page domain or Crossref publisher-name signal maps to `wiley`, or
  - The DOI uses a strongly indicative Wiley prefix such as `10.1002/` or `10.1111/`.
- Common constraints:
  - The HTML and browser PDF/ePDF paths depend on repo-local FlareSolverr readiness and explicit local rate-limit settings.
  - The Wiley TDM API PDF lane is optional; if no token is configured, the runtime can still attempt browser PDF/ePDF when the local runtime is ready.
  - If `WILEY_TDM_CLIENT_TOKEN` is configured, the TDM API PDF lane can still be attempted when the local browser runtime is not ready.

## Science / PNAS

- Runtime status: supported via the same local browser workflow family as Wiley.
- Current implementation:
  - Metadata comes from Crossref merge and landing-page signals.
  - Full text uses provider-managed `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> abstract-only / metadata-only`.
  - HTML is fetched through repo-local FlareSolverr; publisher PDF/ePDF fallback uses Playwright.
  - HTML asset downloads prefer full-size/original images. If direct image fetch returns challenge HTML or a browser image shell, Science / PNAS may use Playwright image-document canvas export before accepting preview fallback.
  - Preview images are only treated as acceptable degradation when saved dimensions meet the runtime threshold; otherwise they remain asset-download issues in warnings/source trail.
- Common constraints:
  - The runtime does not use publisher APIs for these providers.
  - These routes depend on repo-local FlareSolverr readiness and explicit local rate-limit settings.

## Crossref

- Official source: Crossref REST API documentation.
- Role in this skill: universal metadata provider, routing signal source, and metadata-only fallback provider.
- Current implementation:
  - Metadata: `https://api.crossref.org/works/{doi}` or `https://api.crossref.org/works`
  - Recommended env: `CROSSREF_MAILTO`
  - Crossref metadata links may be used for routing and provider handoff; unsupported publishers do not fall through to a generic full-text downloader.
- Route when:
  - No supported publisher route can be chosen with enough confidence.
  - A metadata-only or abstract-level degraded result is still useful after publisher full-text retrieval fails.
- Reference URL:
  - `https://www.crossref.org/documentation/retrieve-metadata/rest-api/`
