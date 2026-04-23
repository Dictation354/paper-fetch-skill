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
  The canonical positive corpus: rule-test assets, 50-sample golden corpus replays, rule scenarios, and documentation-linked HTML/XML/Markdown samples.
- `tests/fixtures/block/`
  The canonical negative corpus: 16 real paywall / abstract-only captures used by availability and fallback tests.
- `tests/fixtures/golden_criteria/_scenarios/`
  Minimal contract scenarios that exercise narrow parser behaviors without introducing extra real-article variance.

Legacy synthetic fixtures may still exist in the tree for isolated mechanism tests, but content-oriented tests should migrate away from them and the provenance audit will reject synthetic fixture use in the registered content-test modules.
