This directory is the canonical home for real blocked / abstract-only HTML samples.

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
- These samples model access gates, abstract-only pages, and paywalled browser captures; they are not fulltext goldens.
