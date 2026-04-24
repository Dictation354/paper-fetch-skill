# Routing Rules

This file is a historical design sketch for routing heuristics. It is not loaded by the runtime, and it is not the source of truth for current provider routing.

Current runtime behavior lives in `src/paper_fetch/publisher_identity.py` and `src/paper_fetch/workflow/routing.py`, then flows through `workflow.metadata` and `workflow.fulltext`.

## Current Runtime Shape

Current runtime routing is conservative and signal-based:

1. URL / landing-page domain signal
2. Crossref publisher-name signal
3. DOI-prefix fallback signal

Crossref is always allowed to contribute metadata and route signals. It is not a generic full-text downloader.

## Supported Provider Routes

Current runtime provider routing recognizes:

- `springer`
- `elsevier`
- `wiley`
- `science`
- `pnas`

If a journal belongs to another publisher, do not infer full-text support until that provider is explicitly added to both `api_notes.md` and the router logic.

## Decision Order

1. Resolve the query to a DOI / title / landing URL candidate.
2. Fetch Crossref metadata when a DOI is available.
3. Build official provider candidates in `domain > publisher > DOI fallback` order.
4. Run the lightweight route probe for candidates.
   - `elsevier` may perform a metadata probe.
   - `springer`, `wiley`, `science`, and `pnas` route probes are conservative `unknown` signals.
5. Select the first positive probe, otherwise the first unknown probe, otherwise the first negative probe.
6. If no official provider candidate is selected but Crossref metadata exists, use `crossref` as the metadata source.
7. Full-text retrieval then runs only the selected provider's own waterfall. If it cannot produce usable full text, provider-managed `abstract_only` may be returned when available; otherwise the workflow returns metadata fallback when `allow_metadata_only_fallback=true`. That fallback publishes `FetchEnvelope.source="metadata_only"`; the underlying article source may still be `crossref_meta`, and its quality `content_kind` may be `abstract_only` when an abstract is present.

## Conflict Policy

Signal precedence is fixed:

1. landing-page / URL domain
2. publisher name
3. DOI prefix

Earlier signals win. DOI-prefix inference is intentionally a fallback, not an override.

## Failure Semantics

Current public traces represent this through `source_trail`, for example `route:signal_*`, `route:provider_selected_*`, `fulltext:*`, and `fallback:metadata_only`.

If the router chooses `crossref` directly because there is no supported official path, Crossref remains a metadata-only source. If an official provider is selected and later cannot provide full text, the workflow returns provider-managed `abstract_only` when available, otherwise uses metadata fallback rather than trying a separate generic full-text route.
