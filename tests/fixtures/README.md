# Fixture conventions

Current real cases, publisher coverage, and remaining acquisition work are maintained in
[`docs/fixture-content-coverage.md`](../../docs/fixture-content-coverage.md).
This file defines fixture conventions; per-sample assets and provenance belong in the
[manifest](golden_criteria/manifest.json) and the corresponding DOI directory.

Policy:

- PDF parsing/conversion quality is outside fixture-completion and acceptance goals. No formatting cleanup or content repair may be applied on top of the existing `pymupdf4llm` output at any layer; existing cleanup tests are not exceptions. PDF acquisition, access/fallback, file identity/completeness, artifact storage, and provenance remain in scope. See the [PDF conversion boundary](../../docs/extraction-rules.md#rule-pdf-conversion-boundary).
- `content` tests must use fixtures registered in `tests/fixture_catalog.py`.
- Rule-test fixtures should use canonical assets registered in `tests/fixtures/golden_criteria/manifest.json`.
- Original-source `content` tests require `real_replay` or direct `real_excerpt` primary inputs. `contract_scenario` and derived snapshots support explicitly scoped mechanism contracts only.
- `synthetic` fixtures are reserved for infrastructure or narrowly scoped mechanism tests that do not assert article-content semantics.
- Handwritten markdown or paraphrased article-body fixtures are not allowed in the default content-test path.

Origin kinds:

- `real_replay`: raw publisher HTML/XML or final browser replay captured from a real article page.
- `real_excerpt`: a direct, traceable excerpt from a captured real source. Paraphrases and generated Markdown are not original-source evidence.
- `contract_scenario`: minimal rule scenario stored under `golden_criteria/_scenarios/` and documented in `docs/extraction-rules.md`.
- `synthetic`: only for transport/cache/config/service/MCP-style tests, or tightly scoped parser mechanics that are not claiming end-to-end article realism.
- `unverified`: source identity/history has not been verified; excluded from real-source coverage.

Raw fixture HTML/XML and acquisition files retain upstream bytes and whitespace; Git attributes disable checkout newline conversion for these hashed inputs.

Origin labels are declarations, not proof of network acquisition. The [source audit](../../docs/fixture-records/source-origin-audit-2026-09-17.json) distinguishes exact captured entities, unverified historical files, derived output and mechanism inputs. Known synthetic/unverified hashes in the [correction register](../../docs/fixture-records/source-origin-corrections-2026-09-17.json) cannot be promoted by renaming or changing a manifest label. Captured challenge/abstract responses are real bytes, not fulltext evidence.

Primary offline baselines:

- `tests/fixtures/golden_criteria/`
  The canonical positive corpus: rule-test assets, executable real golden corpus replays, rule scenarios, and documentation-linked HTML/XML/Markdown samples. The replay count comes from `golden_corpus_replay_inventory()` and excludes manifest-only inputs and synthetic scenarios. The golden corpus includes IEEE real dynamic HTML replays; synthetic IEEE PDF fallback fixtures remain scoped to provider mechanism tests.
- `tests/fixtures/block/`
  The canonical negative corpus: real paywall / abstract-only / empty-shell / empty-body XML / denied article responses registered with `fixture_family=block` in the manifest and used by availability and fallback tests.
- `tests/fixtures/golden_criteria/_scenarios/`
  Minimal contract scenarios that exercise narrow parser behaviors without introducing extra real-article variance.

Synthetic fixtures may exist in the tree for isolated mechanism tests, but content-oriented tests should use provenance-tracked real fixtures and the provenance audit rejects synthetic fixture use in the registered content-test modules.

Sample-type audit checklist:

| Test area | Decision | Rationale |
| --- | --- | --- |
| `test_atypon_browser_workflow_markdown.py` provider extraction over Science, PNAS, and Wiley article HTML | real fixture required | These tests assert article body, abstract, figure, table, formula, collateral noise, and availability behavior that depends on publisher DOM structure. Use `golden_criteria` or provider benchmark fixtures. |
| `test_springer_html_regressions.py` Nature/Springer article extraction, main-content traversal, figure/formula/table/back-matter behavior | real fixture required | These tests guard real Springer/Nature HTML layouts and should read canonical HTML fixtures whenever the assertion is about publisher structure. |
| `test_springer_html_tables.py` table page parsing and inline table injection | real fixture required for successful publisher table extraction; synthetic retained for transport/error contracts | Real table HTML covers flattening and publisher structure. Fake transport responses are retained where the behavior is a minimal response contract, such as image response fallback, missing table degradation, and non-Extended Data Table guardrails. |
| `test_html_availability.py` paywall/fulltext/abstract-only acceptance for provider pages | real fixture required | Provider availability outcomes must use block or golden fixtures so thresholds are calibrated against real access states. |
| `test_html_availability.py` threshold-only and plain text fallback cases | synthetic preferred | These tests exercise pure scoring thresholds, metadata comparison, and structured-article contracts without claiming publisher HTML realism. |
| `test_html_shared_helpers.py` shared HTML parser rules tied to publisher markup | real fixture required | Formula image recognition, Source Data retention, and chrome section filtering use canonical real HTML because they depend on observed DOM conventions. |
| `test_html_shared_helpers.py` metadata, URL joining, Cloudflare/challenge detection, noise-profile switches, and single helper inputs | synthetic preferred | These are isolated helper contracts where a real article would add irrelevant variance. |
| `test_html_semantics.py` heading taxonomy for known publisher headings | real fixture required for publisher-specific heading evidence; synthetic preferred for canonical token mapping | Known back matter and auxiliary headings are sampled from real fixtures. Basic category/token mapping remains synthetic because it tests pure taxonomy lookup. |
| `test_models_render.py` token budgets, rendering options, asset rewrite, section-kind classification, diagnostics merge, and model contract behavior | synthetic preferred | These tests target internal model/rendering contracts, not publisher HTML extraction. Real fixtures are used only when validating a real extracted markdown regression, such as old Nature Methods Summary handling. |
| MCP, service, provider request, HTTP cache, CLI, and provider/service orchestration tests | synthetic preferred | Mocked transports, cache entries, request options, MCP payloads, and CLI save behavior are infrastructure contracts and should not depend on live or captured publisher HTML unless the test explicitly claims extraction realism. |

Synthetic retained because no stable fixture currently covers the behavior:

- `test_springer_html_regressions.py::test_springer_markdown_preserves_subscripts_in_section_headings` keeps a minimal Springer section because the docs do not yet point to a stable Springer/Nature DOI sample with the exact section-heading subscript shape.
- `test_springer_html_regressions.py::test_springer_mathjax_tex_normalizes_upgreek_macros` keeps a minimal MathJax block because the rule is macro normalization, not article layout.
- `test_atypon_browser_workflow_markdown.py` multilingual/nested article/browser-workflow tests keep small synthetic articles because they isolate language scoping, nested roots, and section-hint contracts that are hard to cover with one stable publisher replay.
- `test_html_shared_helpers.py` metadata and challenge-detection tests keep minimal snippets because they target hidden fields, redirect stubs, and HTTP response bodies rather than article-content semantics.

## Test layers

Full original HTML/XML/PDF replay, reviewed content, captured responses and complete
asset collections run under `tests/golden/`. Unit tests use minimal real excerpts
or the existing `_scenarios` catalog; provider/service/CLI/MCP wiring, acceptance,
cache/artifact, installer/process and real browser contracts run in integration.
See [test commands and migration evidence](../README.md).

HTML/XML canonical replay metadata uses only a declared bibliographic title; the DOI
fallback in `GoldenCorpusFixture.title` is for display and must not enter trusted
metadata. Elsevier XML coredata and Springer HTML fill missing titles through the
existing source parsers and base-first metadata merge. A source DOI conflicting
with the requested fixture DOI is rejected before conversion. When neither the
fixture nor source provides a title, it remains missing instead of becoming the
DOI. `tests/golden/test_replay_source_titles.py` covers JSON, YAML and H1 using
verified original bytes through the legacy adapter without prefilling a title.
PDF fallback replay metadata retains its existing behavior.

The four `ams_caption_*` scenarios contain only original paragraphs from the four
AMS caption regressions, with the source DOI recorded in the same manifest. They
preserve the original inline/formula assertions in unit; the full papers and their
original assertions remain in golden. They are excerpts, not additional papers.
PDF content anchors, page ordering and bibliography/layout quality are not test
contracts; real conversions verify opaque result passage and acquisition evidence.

## Per-asset origins and test evidence

`assets` remains the sole path inventory. Optional `asset_origins` maps existing
asset keys to the same four origin kinds and takes precedence over the sample
default. Unknown keys and conflicting origins for the same path are errors.
IEEE PGEC's acquired responses have explicit overrides; its historical synthetic
files remain synthetic. A captured HTML source does not authenticate placeholder
image bytes or injected transport responses.

`tests/test-evidence.json` classifies every test definition in unit, integration,
golden and live. Module defaults apply only to the explicitly enumerated
`definitions`; mixed modules use `overrides`. New/deleted definitions and stale
overrides fail collection. Content entries describe scope and primary evidence
roles (`source`, `asset`); mechanism entries explain their controlled inputs and
record publisher template gaps separately. Inline scenarios and derived snapshots
prove their stated mechanism contracts, not original article coverage.

Historical `template_gap` annotations are retained. Each must now have a
`template_review` with `status`, `scope`, `evidence_tests` and `remaining`:
`mechanism` explains a controlled contract without claiming original coverage;
`covered` links to offline content test definitions for the stated scope;
`partial` lists concrete remaining evidence gaps. A review does not change the
test's `kind` or any asset's origin. References must resolve to registered content
definitions, and only `partial` may have nonempty `remaining`. Unreviewed entries,
stale references, mechanism/live evidence targets and contradictory states fail
collection. Content tests still undergo actual-read verification independently.

Use `tests.support.captured_images.download_captured_images` to replay registered
same-paper image responses. It checks recorded SHA-256 and size, matches source
URLs while ignoring only expiring signature parameters, uses the captured HTTP
envelope, and verifies downloaded bytes. This isolates storage/localization from
live-browser behavior and does not prove a provider's complete candidate order.

Online template acquisitions retain response bytes, requested/final URLs, response
status/MIME, timestamp and SHA-256 in the existing sample's acquisition provenance.
Browser DOM, HTTP entities and canvas exports have distinct capture kinds; a canvas
export has no fabricated HTTP status. A successful direct image response cannot
prove a challenged-HTTP recovery branch. New captures do not change older failed
responses or synthetic origins. Source archives use their actual binary container
extension and count as asset evidence; failure injection in original HTML remains
an explicitly scoped mechanism even when its archive bytes are real.

`tests.support.test_evidence` checks actual fixture reads, module loading,
parameterization and shared fixtures. Reusable test helpers use `evidence_cache`;
canonical golden build caches carry read sets across workers. The manifest/catalog
is the only origin authority. Primary synthetic/scenario evidence is rejected for
content tests; snapshots are auxiliary, and asset-byte claims must explicitly
include `asset` as primary. The check cannot determine assertion meaning or detect
arbitrary fabricated inline strings: review each assertion scope and evidence role
when adding tests. Passing the audit is not a claim of word-for-word verification.

The nine historical one-pixel Annual Reviews `body_assets/annualreviews-figure-*`
files have `synthetic` asset overrides. They remain available for localization
mechanisms; real-download regressions use the already captured same-paper `.bin`
image responses. Binary response roles follow provenance media types and asset
kinds, not merely filename extensions. Every declared primary role must have its
own observed read; a source read cannot satisfy an asset-byte requirement.

Live definitions declare `live_response` evidence and are classified during
collection. Offline file auditing does not authenticate live responses; this
change collects live tests without running them.

后续路由收敛记录见 `docs/fixture-records/fixture-route-removals-2026-09-16.json`。`template-browser-user-retry-2026-09-16` 分别保存 Science 原始 JPEG 与浏览器导出 PNG；PNG 不冒充原始响应。挑战脚本含临时令牌时只保存安全诊断、响应哈希和尺寸，不将原始挑战脚本作为论文原文登记。文章中的图片包装 URL 与独立 viewer 的直链必须分别审阅，不可互相替代。
