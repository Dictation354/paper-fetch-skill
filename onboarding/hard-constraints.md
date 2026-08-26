# AI Onboarding Hard Constraints

Worker 和 coordinator 必须满足下列机器可判约束。

## Worker Scope

- `runtime` must be `coding-agent-subagent`.
- Worker must not commit.
- Worker may only modify paths listed in `files_allowed_to_modify`.
- Worker must not modify paths listed in `files_must_not_modify`.
- The current provider manifest may be listed in `files_allowed_to_modify` only for the `MARKDOWN_CONTRACT_DRIFT` exception: worker may adjust related `markdown_contract.<purpose>` entries, and must not edit routing, route contracts, fixtures, access policy, probe requirements, docs facts, or unrelated purposes.
- Worker must not edit `onboarding/known-providers.yml`.
- Worker must not edit shared docs: `docs/providers.md`, `docs/extraction-rules.md`, `CHANGELOG.md`.
- Worker must not write API keys, tokens, browser endpoint URLs, or local secret file paths into manifest, docs, tests, or task brief output.
- Worker must follow the approved access review. It must not automatically log in, solve CAPTCHA, bypass challenge/paywall controls, or invent temporary site policy.

## Provider Logic

- Provider-specific implementation belongs under `src/paper_fetch/providers/`.
- Provider-specific tests belong under `tests/unit/test_<provider>_provider.py`.
- Provider tests must not keep scaffold skipped placeholders or Markdown review-loop placeholders.
- Every non-null `fixtures.doi_samples.<purpose>` from the provider manifest must be named or asserted in `tests/unit/test_<provider>_provider.py`.
- Every non-null fixture and `extra_fixtures` item must be recorded in `onboarding/reviews/<provider>.yml` with `sample_representative: true` and `markdown_semantic_reviewed: true`; the preferred path is final batch signoff through `scripts/onboard_from_manifests.py finalize-review-artifact --confirmed-final-quality`, not manual per-fixture YAML editing.
- Every non-null `markdown_contract.<purpose>` from the provider manifest must be represented by provider-local Markdown assertions before extraction cleanup is changed.
- Every `main_path` step must have `route_contract.<step>` and provider-local success / rejection coverage before that route is accepted as implemented.
- Every runtime catalog route must expose `ProviderRouteSpec.transport` as `api`, `browser`, or `http`, and every successful provider payload must stamp `ProviderContent.route_name` with that exact catalog route; compatibility source labels and trace aliases do not replace either structured fact.
- Provider-local route coverage is checked by `tests/unit/test_provider_route_contract.py`; exact markers should use `route-contract: step=<step> condition=<condition>` when a route condition cannot be proven by an existing step/source/DOI assertion.
- The main success path must include both positive Markdown assertions and negative assertions for site chrome, access noise, or duplicate boilerplate.
- Markdown cleanup fixes discovered during review must land only in provider-owned implementation files and provider-local tests.
- Provider-specific functions must not be added to `src/paper_fetch/extraction/html/provider_rules.py`.
- Provider-specific functions must not be added to `src/paper_fetch/quality/html_signals.py`.
- Provider-specific functions must not be added to `src/paper_fetch/quality/html_availability.py`.
- Provider routing, asset profile, probe requirements, fixture purposes, and docs source name must come from the provider manifest.
- Golden corpus adapters, MCP provider status order, benchmark coverage, and live review support must stay synchronized with `ProviderBundle + manifest`; workers must not add a second provider constant table.
- Worker must not infer provider behavior from `docs/provider-development.md`, `docs/adding-a-provider.md`, README files, audit files, or chat history.

## Acceptance

- Provider-local pytest listed in the task brief must pass.
- `python3 scripts/onboard_from_manifests.py check-cleaning-proposal --provider <provider>` must pass.
- `python3 scripts/propose_cleaning_chain.py --provider <provider> --check-contract` must pass; warning-only sentinel/cross-route findings are allowed, while missing include, truly vacuous guard, or stale digest is `MARKDOWN_CONTRACT_DRIFT`.
- `PYTHONPATH=src uv run python -m pytest tests/unit/test_provider_markdown_review_contract.py -q` must pass.
- `PYTHONPATH=src uv run python -m pytest tests/unit/test_provider_route_contract.py -q` must pass.
- `onboarding/access-reviews/<provider>.yml` and `onboarding/reviews/<provider>.yml` must pass their schemas.
- `python3 scripts/validate_extraction_rules.py` must pass before merge-ready.
- `PYTHONPATH=src uv run python -m pytest tests/unit/test_manifest_bundle_sync.py -q` must pass before merge-ready.
- `PYTHONPATH=src uv run python -m pytest tests/unit/test_provider_bundle_completeness.py tests/unit/test_provider_owner_reuse.py -q` must pass before merge-ready.
- `PYTHONPATH=src uv run python -m pytest tests/unit/test_golden_corpus_adapters.py tests/unit/test_provider_benchmark_samples.py tests/devtools/test_golden_criteria_live.py -q` must pass before merge-ready.
- `PYTHONPATH=src uv run python -m pytest tests/unit/test_human_docs_drift.py -q` must pass before merge-ready.
- `manifest_sync_back.py` is the only allowed writer for sync-back fields in `extraction_hints` and `success_criteria`.

## Grep Must Be Empty

Implementation acceptance must run these forbidden-central-logic checks with the provider slug substituted for `<provider>`. Return code `0` means forbidden drift exists; return code `1` means no matches.

```bash
git grep -nE "<provider>" -- src/paper_fetch/extraction/html/provider_rules.py
git grep -nE "<provider>" -- src/paper_fetch/quality/html_signals.py
git grep -nE "<provider>" -- src/paper_fetch/quality/html_availability.py
git grep -nE "raw_payload\\.metadata\\[" -- src/paper_fetch/providers/
git grep -nE "BeautifulSoup is None|Tag is None" -- src/paper_fetch/providers/
```
