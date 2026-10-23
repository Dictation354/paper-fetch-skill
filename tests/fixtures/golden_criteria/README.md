This directory is the canonical home for extraction rule-test assets and their documentation links.

Conventions:

- DOI-backed samples live under `tests/fixtures/golden_criteria/<doi_slug>/`.
- Minimal non-DOI rule scenarios live under `tests/fixtures/golden_criteria/_scenarios/<scenario_slug>/`.
- The DOI slug uses `/` replaced with `_`.
- Canonical roles use stable names such as `original.html`, `original.xml`, `expected.json`, `abstract.html`, `commentary.html`, `extracted.md`, `article.html`, and `table1.html`.
- Rule coverage, sample ownership, and replay support files such as `body_assets/*` are registered in `tests/fixtures/golden_criteria/manifest.json`.

Contract:

- Rule tests should read positive article-content fixtures from this directory, and negative article-content fixtures from `tests/fixtures/block/`, not from scattered top-level files, `live-downloads/`, or `md_for_lc_body/`.
- `docs/extraction-rules.md` links should point here.
- Provider regression fixtures keep `expected.json` for summary expectations and `extracted.md` as the human-reviewed golden Markdown baseline.
- Samples included in the golden corpus regression keep canonical raw HTML/XML/PDF or `article.html` replay assets plus `expected.json`; fixture-only replay assets may omit `expected.json`.

The 2026-10-21 completion adds 33 executable full-paper baselines: 29 existing
fulltext papers, the Nature early-access paper, and three fixed-version arXiv
papers. There are 188 canonical `extracted.md` files, counting the 155 retained
files. The intended 34th addition, `10.1080/01431169308904370`, remains PDF-only:
its official 13-page scanned PDF does not yield usable Markdown through the
existing converter. Its capture and limited acceptance are retained without a
fulltext `expected.json` claim. See `quality/fulltext-baselines-2026-10-21.json`.

Canonical asset roles resolve through the manifest before historical filenames;
the mapping reuses acquisition bytes without copying them. The nine arXiv
page/excerpt declarations are consolidated into three paper records, with
abstract pages, ancillary indexes and original excerpts retained as auxiliary
inputs. The real bilingual Elsevier XML is `10.1016/j.edumed.2018.09.002`; the
disproven synthetic XML remains classified as scenario infrastructure.

Nature early access replays the authorized landing page (without full HTML
body), its official same-paper PDF, both failure/success trace markers, and
degraded acceptance. PDF assertions check identity and unchanged converter
output. Complete Markdown snapshots use `include_refs=all`,
`max_tokens=full_text` and persistent captured asset paths.
