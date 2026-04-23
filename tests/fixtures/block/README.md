This directory is the canonical home for real blocked / abstract-only HTML samples.

Conventions:

- DOI-backed samples live under `tests/fixtures/block/<doi_slug>/`.
- The DOI slug uses `/` replaced with `_`.
- Block fixtures use stable names such as `raw.html` and optional `extracted.md`.
- Sample ownership and provenance metadata are registered in `tests/fixtures/golden_criteria/manifest.json` with `fixture_family: "block"`.

Contract:

- Availability and fallback tests should read negative real-article fixtures from this directory.
- These samples model access gates, abstract-only pages, and paywalled browser captures; they are not fulltext goldens.
