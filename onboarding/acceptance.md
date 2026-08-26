# AI Onboarding Acceptance

This file defines machine-verifiable merge-ready gates for AI/coordinator provider onboarding.

## Manifest Gates

- `onboarding/access-reviews/<provider>.yml` exists, passes `onboarding/access-review.schema.json`, has `status: approved`, and has `may_continue: true`.
- `PYTHONPATH=src uv run python -m pytest tests/unit/test_provider_manifest_schema.py -q`
- `PYTHONPATH=src uv run python -m pytest tests/unit/test_manifest_bundle_sync.py -q`
- Manifest status for merge-ready provider is `ready` or stricter sync-back status accepted by `tests/unit/_manifest_sync.py`.
- `onboarding/known-providers.yml` entry contains an existing `manifest_path`.

## Fixture Gates

- Every required DOI purpose in `onboarding/provider-manifest.schema.json` is present in `fixtures.doi_samples`.
- `structure`, `figure`, and `references` DOI values are non-null.
- Every `main_path` step has a `route_contract` entry with non-empty success requirements.
- `PYTHONPATH=src uv run python -m pytest tests/unit/test_provider_route_contract.py -q`
- Every manifest defines `asset_contract.figures`; non-null figure-capable routes use `inline: body` and `download: required`, while `not_applicable` is allowed only with a concrete exception reason.
- `PYTHONPATH=src uv run python -m pytest tests/unit/test_provider_asset_contract.py -q`
- Every non-null fixture purpose has a matching `markdown_contract` entry with positive and negative Markdown assertions.
- Capture failures use structured JSON stderr with `code` from `failure-recovery.md`.
- `UNSUITABLE_DOI_SAMPLE` changes only `fixtures.doi_samples.<purpose>` for the failed purpose.
- `propose-cleaning-chain` has generated `onboarding/cleaning-chain-proposals/<provider>.yml` and `<provider>.evidence.yml`; both are bound to current fixture digests.
- `python3 scripts/onboard_from_manifests.py check-cleaning-proposal --provider <provider>` passes before provider-local acceptance.

## Implementation Gates

- Provider-local pytest from `briefs/implement-provider.yml` passes.
- `python3 scripts/propose_cleaning_chain.py --provider <provider> --check-contract` passes; `MARKDOWN_CONTRACT_DRIFT` is retryable and must be resolved by refreshing stale proposal digests or by implementation/contract reconciliation.
- `PYTHONPATH=src uv run python -m pytest tests/unit/test_provider_markdown_review_contract.py -q`
- `PYTHONPATH=src uv run python -m pytest tests/unit/test_provider_route_contract.py -q`
- `PYTHONPATH=src uv run python -m pytest tests/unit/test_provider_bundle_completeness.py tests/unit/test_provider_owner_reuse.py -q`
- `PYTHONPATH=src uv run python -m pytest tests/unit/test_golden_corpus_adapters.py tests/unit/test_provider_benchmark_samples.py tests/devtools/test_golden_criteria_live.py -q`
- `python3 scripts/validate_extraction_rules.py`
- `manifest_sync_back.py` is the only writer for `extraction_hints` and `success_criteria` sync-back fields.
- New provider integration must be synchronized through the provider fact sources: register a golden corpus adapter when golden replay fixtures exist, expose MCP provider status through the bundle-derived catalog, keep benchmark samples covered for official providers, and default provider-local acceptance to one provider subset live assets review unless the provider is an existing low-risk exemption.
- Shared integration runs after provider implementation and before snapshot generation; coordinator-owned changes must be traced to manifest facts, bundle sync-back, fixture replay, or provider-local test evidence.
- Local operator acceptance may use `python3 scripts/onboard_from_manifests.py run-checks --provider <provider> --all-local`; this command does not trigger GitHub CI.
- Full local orchestration may use `python3 scripts/onboard_from_manifests.py run --manifest onboarding/manifests/<provider>.yml --until merge-ready`; worker dispatch must go only through the resolved local dispatcher: default `codex exec` or `PROVIDER_ONBOARDING_AGENT_CLI` operator override.

## Markdown Review Gates

- `onboarding/reviews/<provider>.yml` exists and passes `onboarding/provider-review.schema.json`.
- `scripts/bootstrap_review_artifact.py` output is only a draft gate helper; acceptance still requires `markdown_semantic_reviewed: true` after real semantic review.
- The preferred signoff path is one final batch review: the operator reviews current `extracted.md` / `markdown-quality.json` / fresh review output, then runs `python3 scripts/onboard_from_manifests.py finalize-review-artifact --provider <provider> --confirmed-final-quality`.
- `finalize-review-artifact` must refuse to sign if any registered fixture has missing snapshot assets, non-pass persistent quality, fresh blocking issues, or `markdown_contract` drift.
- Every non-null `fixtures.doi_samples.<purpose>` and every `extra_fixtures` item has a review artifact entry with `baseline_markdown_path` pointing to `extracted.md`, `baseline_markdown_sha256`, `markdown_quality_path`, `markdown_quality_sha256`, `review_notes`, `sample_representative: true`, `markdown_semantic_reviewed: true`, `issues`, `assertions`, and `fixes`.
- `issues` and `fixes` use stable object ids when present; every fix references existing `issue_ids` and names at least one provider-local test.
- Review artifact values must not contain `TODO`, `TBD`, or `unknown` placeholders.
- Every non-null `fixtures.doi_samples.<purpose>` is represented in `tests/unit/test_<provider>_provider.py` by purpose name or DOI slug.
- Provider-local tests should prefer exact markers of the form `markdown-review: purpose=<purpose> doi=<doi>` next to the assertions generated from `markdown_contract`.
- Provider-local tests do not contain scaffold skipped placeholders or Markdown review-loop placeholders.
- Provider-local tests include at least one positive Markdown assertion and at least one negative site-chrome / access-noise / boilerplate assertion.
- For `asset_contract.figures.inline: body`, `extracted.md` must include a body Markdown image before References/Figures/Supplementary tail sections; a caption-only `## Figures` section is blocking.
- For `asset_contract.figures.download: required`, provider-local tests must include marker `asset-download-contract: provider=<provider>` and assert actual local file path/bytes plus asset result state.
- When references are expected, the `## References` list must retain recognizable reference numbers or labels such as `[1]`, `1.`, `1)`, or publisher-native labels; unnumbered/unlabeled reference lists are blocking.
- Worker completion summary is secondary; acceptance uses `onboarding/reviews/<provider>.yml` as the durable source. Operator does not need to hand-edit one review entry per fixture when the final batch signoff command can derive the entries from current artifacts.

## Live Review Gates

- Future providers run one provider subset live assets review by default during provider-local acceptance, for example `PAPER_FETCH_RUN_LIVE=1 python3 scripts/run_golden_criteria_live_review.py --providers mdpi`; existing low-risk providers may be exempt.
- Live review validates `FetchEnvelope.source` against manifest `route_sources`; silent degradation from an expected HTML/XML source to PDF fallback is an acceptance issue unless that sample is explicitly a fallback sample.
- Live review reuses manifest `markdown_contract` positive and negative assertions to auto-classify content-missing and noise-leak issues before manual semantic signoff.

## Automation Gates

- `onboarding/automation-roadmap.md` documents which onboarding steps are automatable and which remain operator-controlled.
- `capture-fixtures` uses `--auto-via --fail-fast`; browser route selection must be allowed by access review.
- `scaffold` uses `--merge-existing=safe` and must not overwrite divergent existing provider files.
- `manifest-sync-back` uses `--sync-docs` and only updates known marker/provider entries, not unmarked human prose.
- Worker forbidden-path changes fail with `WORKER_MODIFIED_FORBIDDEN_FILE`.

## Drift Gates

- `PYTHONPATH=src uv run python -m pytest tests/unit/test_human_docs_drift.py -q`
- `git grep -n "Human reference only" -- docs/provider-development.md docs/adding-a-provider.md`
- `git grep -n "onboarding" -- docs/provider-development.md docs/adding-a-provider.md`
- Human-guide banned-token grep over `onboarding/` returns no matches.

## Structured Error Gates

Acceptance fails when any tool reports a JSON stderr `code` that maps to `retryable: false` in `failure-recovery.md`.

Acceptance remains blocked after retry budget exhaustion for:

- `DISCOVERY_RETRY_EXHAUSTED`
- `TASK_RETRY_EXHAUSTED`
- `MANIFEST_PROVIDER_CONFLICT`
- `BROWSER_RUNTIME_REQUIRED`
