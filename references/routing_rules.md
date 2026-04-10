# Routing Rules

This file is a historical design sketch for routing heuristics. It is not loaded by the runtime, and it is not the source of truth for current provider routing.

Current runtime behavior lives in `src/paper_fetch/publisher_identity.py` plus the resolve/service flow that uses those conservative DOI and publisher-name inferences.

## Goal

Choose the most appropriate metadata lookup provider with this fixed priority:

1. Supported official publisher API
2. `Crossref` fallback

## Supported Official Providers

Current v1 support is limited to:

- `springer`
- `elsevier`
- `wiley`

If a journal belongs to a publisher with another official API, do not infer support until that provider is explicitly added to both `api_notes.md` and the router logic.

## Decision Order

1. Parse `doi`, `journal_title`, and `article_title`.
2. Normalize `journal_title`.
3. Optionally match the normalized title against a curated journal list.
4. If the matched record declares a supported `official_provider`, choose it.
5. If there is no matched record, try a conservative DOI-prefix inference for supported publishers.
6. If there is still no supported official route, choose `crossref`.
7. If the chosen official provider fails because of `no_access`, `no_result`, or `error`, fall back to `crossref`.

## Conflict Policy

Input precedence is fixed:

1. `doi`
2. `journal_title`
3. `article_title`

When DOI-derived routing conflicts with the journal-list match, keep the DOI route and explain the override in `reason`.

## Failure Semantics

`fallback_used` is `true` only when the router first chooses an official provider and then degrades to `crossref`.

If the router chooses `crossref` directly because there is no supported official path, `fallback_used` stays `false`.
