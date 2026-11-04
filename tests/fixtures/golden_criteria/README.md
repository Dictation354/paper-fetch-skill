This directory is the canonical home for extraction rule-test assets and their documentation links.

Conventions:

- DOI-backed samples live under `tests/fixtures/golden_criteria/<doi_slug>/`.
- Minimal non-DOI rule scenarios live under `tests/fixtures/golden_criteria/_scenarios/<scenario_slug>/`.
- The DOI slug uses `/` replaced with `_`.
- Canonical roles use stable names such as `original.html`, `original.xml`, `expected.json`, `abstract.html`, `commentary.html`, `extracted.md`, `article.html`, and `table1.html`.
- Rule coverage, sample ownership, and replay support files such as `body_assets/*` are registered in `tests/fixtures/golden_criteria/manifest.json`.

Contract:

- Full-paper golden replays read positive article-content fixtures from this directory and negative article-content fixtures from `tests/fixtures/block/`. Minimal unit scenarios belong in the unit layer; see [test layers](../../README.md).
- `docs/extraction-rules.md` links should point here.
- Provider regression fixtures keep `expected.json` for summary expectations and `extracted.md` as the human-reviewed golden Markdown baseline.
- Samples included in the golden corpus regression keep canonical raw HTML/XML/PDF or `article.html` replay assets plus `expected.json`; fixture-only replay assets may omit `expected.json`.

The current corpus and acceptance scope are recorded in [manifest.json](manifest.json)
and each sample’s `expected.json`. Captured PDF-only samples may retain limited
acceptance when the existing converter does not yield usable Markdown.

Canonical asset roles resolve through the manifest; the mapping reuses acquisition
bytes without copying them. Abstract pages, ancillary indexes and excerpts are
auxiliary inputs. Source classifications and sample scope follow the manifest.

Nature early access replays the authorized landing page (without full HTML
body), its official same-paper PDF, both failure/success trace markers, and
degraded acceptance. PDF assertions check identity and unchanged converter
output. Complete Markdown snapshots use `include_refs=all`,
`max_tokens=full_text` and persistent captured asset paths.
