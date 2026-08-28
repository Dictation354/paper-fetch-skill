# /goal 通用执行说明：添加 Provider

适用于从零添加 provider，或基于 `onboarding/manifests/<provider>.yml` 继续实现到 merge-ready：

```text
/goal follow onboarding/instruction.md 添加 <provider> provider
```

执行者直接使用本仓库的 manifest、脚本和测试推进，不启动递归 `codex exec`，不创建私有 state/DAG，也不派发 onboarding worker。

## 1. 确认 manifest 与访问边界

1. 按 [`provider-manifest.schema.json`](./provider-manifest.schema.json) 创建或更新 `onboarding/manifests/<provider>.yml`，并登记 `known-providers.yml`。
2. 明确 routing、`main_path`、每步 `route_contract`、正交 fixture purpose、Markdown contract、asset profile 与 docs facts。
3. 读取 `onboarding/access-reviews/<provider>.yml`。只有 `status: approved` 且 `may_continue: true` 时，才能进行需要网络或浏览器的 capture/live 操作。
4. 不自动登录，不解决 CAPTCHA，不绕过 challenge/paywall，不把凭据或本地授权路径写入仓库。

验证：

```bash
PYTHONPATH=src uv run python -m pytest tests/unit/test_provider_manifest_schema.py tests/unit/test_provider_route_contract.py tests/unit/test_provider_asset_contract.py -q
```

## 2. 捕获 fixture 与生成 cleaning proposal

```bash
PYTHONPATH=src python scripts/capture_fixture.py \
  --from-manifest onboarding/manifests/<provider>.yml \
  --all --auto-via --fail-fast
python scripts/propose_cleaning_chain.py --provider <provider> --write
python scripts/propose_cleaning_chain.py --provider <provider> --check-contract
```

Cleaning proposal 只写 `onboarding/cleaning-chain-proposals/<provider>.yml`；它必须绑定当前 fixture digest。不要生成或要求 `.evidence.yml` sidecar。

## 3. Scaffold 与实现

```bash
python scripts/scaffold_provider.py \
  --from-manifest onboarding/manifests/<provider>.yml \
  --merge-existing=safe
```

- 新 provider 必须在 `paper_fetch.providers._BUILTIN_PROVIDER_ENTRY_MODULES` 显式登记一次；运行时不扫描源码发现 provider。
- 每条 capability 都由显式 `ProviderRouteSpec` 表达。不要在 `ProviderSpec` 增加浏览器或 Playwright 顶层事实。
- Provider 成功 payload 使用 typed `ProviderContent`、`ProviderArtifacts`、`trace`、`warnings` 与 `merged_metadata`，不得读写 `RawFulltextPayload.metadata`。
- Publisher 差异放在 provider-owned 模块；通用解析、资产、availability、公式与渲染逻辑复用现有 owner。
- 为每个 route success/reject 条件、每个 non-null fixture purpose、Markdown 正/负契约与资产下载行为增加 provider-local 测试。

## 4. Snapshot 与 Markdown 审核

对 manifest 中每个 non-null DOI 执行：

```bash
PYTHONPATH=src python scripts/snapshot_expected.py --doi <doi> --review
PYTHONPATH=src python scripts/snapshot_expected.py --doi <doi>
```

阅读生成的 `extracted.md` 与 `markdown-quality-prompt.md`，把 `markdown-quality.json` 写成真实 agent review 结果。不得把 pending 或 blocking report 当成通过。

生成 review 草稿：

```bash
PYTHONPATH=src python scripts/bootstrap_review_artifact.py \
  --provider <provider> \
  --manifest onboarding/manifests/<provider>.yml \
  --force
```

操作者确认全部最终 Markdown 后再签核：

```bash
PYTHONPATH=src python scripts/bootstrap_review_artifact.py \
  --provider <provider> \
  --manifest onboarding/manifests/<provider>.yml \
  --finalize --confirmed-final-quality --reviewed-by <reviewer>
```

该命令会重新计算 snapshot/quality hash，检查 Markdown contract 与 blocking quality issue，并写入 `onboarding/reviews/<provider>.yml`。不要手工伪造 `markdown_semantic_reviewed: true`。

## 5. 同步与验收

```bash
PYTHONPATH=src python scripts/manifest_sync_back.py \
  --provider <provider> \
  --manifest onboarding/manifests/<provider>.yml \
  --sync-docs
python scripts/check_provider_governance.py
python scripts/validate_extraction_rules.py
PYTHONPATH=src uv run python -m pytest tests/unit/test_<provider>_provider.py -q
PYTHONPATH=src uv run python -m pytest tests/unit/test_manifest_bundle_sync.py tests/unit/test_provider_markdown_review_contract.py tests/unit/test_provider_bundle_completeness.py tests/unit/test_provider_owner_reuse.py -q
PYTHONPATH=src uv run python -m pytest tests/unit/test_golden_corpus_adapters.py tests/unit/test_provider_benchmark_samples.py tests/devtools/test_golden_criteria_live.py -q
```

完整 merge-ready 条件见 [`acceptance.md`](./acceptance.md)。默认复用 `pyproject.toml` 的并行 pytest 配置；不运行 live，不触发 GitHub CI。
