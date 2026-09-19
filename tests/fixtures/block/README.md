# Block fixture conventions

This directory contains canonical real article responses or captured browser DOMs
rejected as full text, including subscription previews, abstract-only pages,
challenges, access denials, empty shells, and empty-body XML.
Current cases and remaining work are listed in the
[real-case inventory](../../../docs/fixture-content-coverage.md).

Conventions:

- DOI-backed samples live under `tests/fixtures/block/<doi_slug>/`.
- The DOI slug uses `/` replaced with `_`.
- Block fixtures declare exactly one canonical `raw.html` or `raw.xml`. Historical
  `extracted.md` files may remain for human review, but no test or governance claim
  may use them as executable evidence.
- Sample ownership and provenance metadata are registered in
  `tests/fixtures/golden_criteria/manifest.json` with
  `fixture_family: "block"`, `origin_kind: "real_replay"`,
  `negative_case_kind`, exact provider `provider_route` / `source_identity`, and
  expected rejection reason, failure code, and content kind.

Contract:

- Availability and fallback tests must send the canonical raw response through the
  current provider extractor and current availability chain, then compare the full
  negative contract. An unsupported raw format is unexecutable and cannot count as
  route coverage.
- These samples model rejected full-text inputs; they are not fulltext goldens.

Evidence boundaries:

- Subscription restrictions, challenges, and empty content are distinct evidence.
  An `abstract_only` extraction result alone does not establish a paywall.
- A captured response and a final browser DOM retain separate provenance; unknown
  HTTP status or headers remain unknown.
- Replaying real input with injected PDF failures verifies fallback behavior,
  not a live failure of all access routes.
- A purchase landing page is insufficient when another provider route returns
  full text. IEEE purchase-page evidence stays auxiliary; Elsevier acquisition
  evidence uses its API-key route.
- Open-access targets do not require paywall examples, and challenge counts are
  not acquisition quotas.
