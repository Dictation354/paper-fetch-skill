# `has_fulltext` Probe Semantics Note

## Context

`fetch_paper.has_fulltext` is currently the result of the full service waterfall:

1. resolve query
2. fetch metadata
3. try the official provider full-text path
4. fall back to HTML when allowed
5. fall back to metadata-only when allowed

That makes it a good final answer, but not a cheap probe. This note now serves two roles:

- it records the semantics decisions made before implementation
- it documents the current v1 `has_fulltext(query)` MCP tool that landed from those decisions

## Decision

We shipped a dedicated `has_fulltext(query)` MCP tool rather than `fetch_paper(probe_only=true)`.

Reasoning:

- A probe will necessarily use cheaper and weaker signals than the full fetch waterfall.
- Because of that, a probe result cannot promise exact numerical agreement with `fetch_paper.has_fulltext`.
- A separate tool keeps the current `fetch_paper` contract simple and avoids mixing "probe semantics" with "final fetch semantics" inside one envelope.

Current v1 scope:

- Uses resolution, Crossref metadata, lightweight official metadata probes, and landing-page HTML meta.
- Does not call the full `_fetch_article` waterfall.
- Reuses the same cheap probe path for `batch_check(mode="metadata")`.
- Publicly exposes four states in the contract, but v1 only actively returns `likely_yes` and `unknown`.

## Probe Questions

### 1. Does Crossref metadata with `license` or `link` imply `has_fulltext=true`?

No. Crossref metadata alone is not sufficient to claim confirmed full text.

- A Crossref `license` field is useful evidence that the record is open or machine-readable.
- A Crossref `link` field is useful evidence that a downloadable representation may exist.
- Neither guarantees that the concrete full-text payload is still reachable, authorized, or compatible with our current fetch adapters.

Future probe policy:

- treat these as `likely_yes`
- do not treat them as `confirmed_yes`

### 2. Do provider HEAD or OPTIONS probes count?

Only as provider-specific hints, not as global truth.

- Some providers do not offer a stable HEAD or OPTIONS contract for the same endpoint that serves usable full text.
- Authorization and content negotiation may differ between HEAD and GET.
- A successful HEAD can still overstate the eventual success of the real fetch path.

Future probe policy:

- allow provider-specific HEAD or lightweight metadata checks where a provider contract is known and tested
- classify positive results as `likely_yes` unless the provider contract is strong enough to guarantee the same full-text object that the fetch path will consume

### 3. Does `citation_pdf_url` on an HTML landing page count?

It counts as `likely_yes`, not `confirmed_yes`.

- Landing-page metadata can be stale or point to a gated or broken asset.
- A real GET remains the only reliable proof that the asset is accessible and usable.

Future probe policy:

- HTML metadata such as `citation_pdf_url`, `og:url`, or publisher-specific download hints should increase confidence
- `confirmed_yes` requires successfully reaching a concrete payload or an equivalent provider guarantee

### 4. Must probe results match `fetch_paper.has_fulltext` exactly?

No.

- `fetch_paper.has_fulltext` is a final, expensive verdict after executing the real fallback chain.
- A probe is intentionally cheaper and earlier.
- Requiring strict equality would push the probe toward doing the full fetch, which defeats the purpose.

Future probe policy:

- `confirmed_yes` should be a subset of papers that `fetch_paper` is very likely to return with `has_fulltext=true`
- `likely_yes` may include cases that later fail during the real fetch
- `unknown` is acceptable and preferable to an overconfident false negative

### 5. Should the probe use more than three states?

Yes. Use four states:

- `confirmed_yes`
- `likely_yes`
- `unknown`
- `no`

Rationale:

- `confirmed_yes` captures cases where the probe has strong evidence
- `likely_yes` captures weaker but still useful evidence such as Crossref links or landing-page PDF metadata
- `unknown` prevents us from collapsing transient errors, missing credentials, and unsupported provider paths into false negatives
- `no` is reserved for cases where the probe has an explicit negative signal, not just a lack of positive evidence

## Follow-up Shape

The follow-up interface should be a dedicated MCP tool:

- `has_fulltext(query)` returning `{query, doi, state, evidence, warnings}`

Why not `fetch_paper(probe_only=true)`:

- it would overload one tool with two different truth models
- it would make `FetchEnvelope.has_fulltext` easier to misread as a probe answer
- it would force more branching into the thin MCP layer for what should remain a separate intent

## Non-goals For This Round

- No new CLI `has_fulltext` command
- No change to `fetch_paper.has_fulltext`
- No provider-specific HEAD/OPTIONS implementation work
- No active production use of `confirmed_yes` or `no` yet
