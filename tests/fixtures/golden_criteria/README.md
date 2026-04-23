This directory is the canonical home for extraction rule-test assets and their documentation links.

Conventions:

- DOI-backed samples live under `tests/fixtures/golden_criteria/<doi_slug>/`.
- Minimal non-DOI rule scenarios live under `tests/fixtures/golden_criteria/_scenarios/<scenario_slug>/`.
- The DOI slug uses `/` replaced with `_`.
- Canonical roles use stable names such as `original.html`, `original.xml`, `expected.json`, `abstract.html`, `commentary.html`, `extracted.md`, `article.html`, and `table1.html`.
- Rule coverage and sample ownership are registered in `tests/fixtures/golden_criteria/manifest.json`.

Contract:

- Rule tests should read positive article-content fixtures from this directory, and negative article-content fixtures from `tests/fixtures/block/`, not from scattered top-level files, `live-downloads/`, or `md_for_lc_body/`.
- `docs/extraction-rules.md` links should point here.
- The golden corpus now keeps both canonical raw HTML/XML and `expected.json` side by side in each DOI directory.
