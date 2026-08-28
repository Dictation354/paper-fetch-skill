# Provider Onboarding Acceptance

本文定义 provider 的机器可验证 merge-ready 条件。所有命令直接运行现有脚本与测试，不依赖 coordinator、worker state、递归 agent 调度或 evidence sidecar。

## Manifest 与访问

- `onboarding/manifests/<provider>.yml` 通过 `provider-manifest.schema.json`，并由 `known-providers.yml` 登记。
- `onboarding/access-reviews/<provider>.yml` 通过 schema，且需要联网时必须是 `status: approved`、`may_continue: true`。
- 每个 `main_path` step 都有非空 `route_contract`；每个非空 fixture purpose 都有 Markdown 正、负契约。
- Runtime capability 只由 `ProviderSpec.routes` 提供；manifest probe 只用于 capture/scaffold 输入。

```bash
PYTHONPATH=src uv run python -m pytest tests/unit/test_provider_manifest_schema.py tests/unit/test_provider_route_contract.py tests/unit/test_provider_asset_contract.py tests/unit/test_manifest_bundle_sync.py -q
```

## Fixture、proposal 与实现

- 所有 fixture 位于 canonical golden/block 目录并登记在 golden manifest。
- `onboarding/cleaning-chain-proposals/<provider>.yml` 绑定当前 fixture digest；不要求 `.evidence.yml`。
- Provider 在显式模块清单中登记，routes、payload、source、asset 与 acceptance 行为有 provider-local 覆盖。
- `manifest_sync_back.py` 是 `extraction_hints` 与 `success_criteria` sync-back 字段的唯一写入者。

```bash
python scripts/propose_cleaning_chain.py --provider <provider> --check-contract
PYTHONPATH=src uv run python -m pytest tests/unit/test_<provider>_provider.py -q
PYTHONPATH=src uv run python -m pytest tests/unit/test_provider_bundle_completeness.py tests/unit/test_provider_owner_reuse.py tests/unit/test_provider_markdown_review_contract.py -q
PYTHONPATH=src uv run python -m pytest tests/unit/test_golden_corpus_adapters.py tests/unit/test_provider_benchmark_samples.py tests/devtools/test_golden_criteria_live.py -q
python scripts/check_provider_governance.py
python scripts/validate_extraction_rules.py
```

## Markdown review

- `onboarding/reviews/<provider>.yml` 通过 `provider-review.schema.json`。
- 每个 non-null fixture 与 extra fixture 都记录当前 `extracted.md`、`markdown-quality.json` 及其 SHA-256。
- Persistent quality 必须为 pass，Markdown contract 不得漂移，且没有 blocking issue。
- `sample_representative` 与 `markdown_semantic_reviewed` 均为 true；review 值不含 `TODO`、`TBD` 或 `unknown`。
- 最终签核只能在操作者完成语义审核后执行：

```bash
PYTHONPATH=src python scripts/bootstrap_review_artifact.py \
  --provider <provider> \
  --manifest onboarding/manifests/<provider>.yml \
  --finalize --confirmed-final-quality --reviewed-by <reviewer>
```

该命令必须在 snapshot 缺失、quality 非 pass、contract drift 或 blocking issue 时拒绝签核。

## Repository 验收

- Provider 文档、extraction rules、changelog 与 manifest sync-back 保持一致。
- 默认并行运行相关 unit、integration 与 devtools 测试。
- 普通验收不运行 live、不触发 GitHub CI。通用 golden live 仅在明确授权和 `PAPER_FETCH_RUN_LIVE=1` 下运行。
