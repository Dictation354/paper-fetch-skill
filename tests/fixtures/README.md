This directory now treats article-content fixtures as provenance-tracked literature samples rather than minimized paraphrases.

Policy:

- `content` tests must use fixtures registered in `tests/fixture_catalog.py`.
- Rule-test fixtures should use canonical assets registered in `tests/fixtures/golden_criteria/manifest.json`.
- `content` fixtures must be `real_replay`, `real_excerpt`, or `contract_scenario`.
- `synthetic` fixtures are reserved for infrastructure or narrowly scoped mechanism tests that do not assert article-content semantics.
- Handwritten markdown or paraphrased article-body fixtures are not allowed in the default content-test path.

Origin kinds:

- `real_replay`: raw publisher HTML/XML or final browser replay captured from a real article page.
- `real_excerpt`: direct excerpt or derived snapshot from a real article, such as `.extracted.md`.
- `contract_scenario`: minimal rule scenario stored under `golden_criteria/_scenarios/` and documented in `docs/extraction-rules.md`.
- `synthetic`: only for transport/cache/config/service/MCP-style tests, or tightly scoped parser mechanics that are not claiming end-to-end article realism.

Primary offline baselines:

- `tests/fixtures/golden_criteria/`
  The canonical positive corpus: rule-test assets, 51-sample golden corpus replays, rule scenarios, and documentation-linked HTML/XML/Markdown samples.
- `tests/fixtures/block/`
  The canonical negative corpus: 16 real paywall / abstract-only captures used by availability and fallback tests.
- `tests/fixtures/golden_criteria/_scenarios/`
  Minimal contract scenarios that exercise narrow parser behaviors without introducing extra real-article variance.

Legacy synthetic fixtures may still exist in the tree for isolated mechanism tests, but content-oriented tests should migrate away from them and the provenance audit will reject synthetic fixture use in the registered content-test modules.

Sample-type audit checklist:

| Test area | Decision | Rationale |
| --- | --- | --- |
| `test_science_pnas_markdown.py` provider extraction over Science, PNAS, and Wiley article HTML | real fixture required | These tests assert article body, abstract, figure, table, formula, collateral noise, and availability behavior that depends on publisher DOM structure. Use `golden_criteria` or provider benchmark fixtures. |
| `test_springer_html_regressions.py` Nature/Springer article extraction, main-content traversal, figure/formula/table/back-matter behavior | real fixture required | These tests guard real Springer/Nature HTML layouts and should read canonical HTML fixtures whenever the assertion is about publisher structure. |
| `test_springer_html_tables.py` table page parsing and inline table injection | real fixture required for successful publisher table extraction; synthetic retained for transport/error contracts | Real table HTML covers flattening and publisher structure. Fake transport responses are retained where the behavior is a minimal response contract, such as image response fallback, missing table degradation, and non-Extended Data Table guardrails. |
| `test_html_availability.py` paywall/fulltext/abstract-only acceptance for provider pages | real fixture required | Provider availability outcomes must use block or golden fixtures so thresholds are calibrated against real access states. |
| `test_html_availability.py` threshold-only and plain text fallback cases | synthetic preferred | These tests exercise pure scoring thresholds, metadata comparison, and structured-article contracts without claiming publisher HTML realism. |
| `test_html_shared_helpers.py` shared HTML parser rules tied to publisher markup | real fixture required | Formula image recognition, Source Data retention, and chrome section filtering use canonical real HTML because they depend on observed DOM conventions. |
| `test_html_shared_helpers.py` metadata, URL joining, Cloudflare/challenge detection, noise-profile switches, and single helper inputs | synthetic preferred | These are isolated helper contracts where a real article would add irrelevant variance. |
| `test_html_semantics.py` heading taxonomy for known publisher headings | real fixture required for publisher-specific heading evidence; synthetic preferred for canonical token mapping | Known back matter and auxiliary headings are sampled from real fixtures. Basic category/token mapping remains synthetic because it tests pure taxonomy lookup. |
| `test_models_render.py` token budgets, rendering options, asset rewrite, section-kind classification, diagnostics merge, and model contract behavior | synthetic preferred | These tests target internal model/rendering contracts, not publisher HTML extraction. Real fixtures are used only when validating a real extracted markdown regression, such as old Nature Methods Summary handling. |
| `test_mcp.py`, `test_service.py`, `test_provider_request_options.py`, `test_http_cache.py`, `test_cli.py`, and provider/service orchestration tests | synthetic preferred | Mocked transports, cache entries, request options, MCP payloads, and CLI save behavior are infrastructure contracts and should not depend on live or captured publisher HTML unless the test explicitly claims extraction realism. |

Synthetic retained because no stable fixture currently covers the behavior:

- `test_springer_html_regressions.py::test_springer_markdown_preserves_subscripts_in_section_headings` keeps a minimal Springer section because the docs do not yet point to a stable Springer/Nature DOI sample with the exact section-heading subscript shape.
- `test_springer_html_regressions.py::test_springer_mathjax_tex_normalizes_upgreek_macros` keeps a minimal MathJax block because the rule is macro normalization, not article layout.
- `test_science_pnas_markdown.py` multilingual/nested article/browser-workflow tests keep small synthetic articles because they isolate language scoping, nested roots, and section-hint contracts that are hard to cover with one stable publisher replay.
- `test_html_shared_helpers.py` metadata and challenge-detection tests keep minimal snippets because they target hidden fields, redirect stubs, and HTTP response bodies rather than article-content semantics.
