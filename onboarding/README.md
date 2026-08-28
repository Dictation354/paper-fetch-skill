# Provider onboarding

本目录保存新增或维护 provider 所需的机器输入与审核产物。流程是确定性的本地开发流程，不维护私有 DAG、worker state、递归 agent 调度或重试编排。

paper-fetch 只处理已知论文的身份解析、全文获取、验收与报告。新增 provider 不得绕过付费墙、自动登录、处理 CAPTCHA/challenge 或替操作者批准访问策略；默认也不触发 GitHub CI。

## 权威输入

- [`provider-manifest.schema.json`](./provider-manifest.schema.json) 与 [`provider-manifest.md`](./provider-manifest.md)：manifest 结构与字段说明。
- [`manifests/`](./manifests/) 与 [`known-providers.yml`](./known-providers.yml)：provider 输入与索引。
- [`access-review.schema.json`](./access-review.schema.json) 与 [`access-reviews/`](./access-reviews/)：合法访问、运行时和 challenge 策略的人工批准记录。
- [`provider-review.schema.json`](./provider-review.schema.json) 与 [`reviews/`](./reviews/)：fixture 代表性与最终 Markdown 语义审核。
- [`hard-constraints.md`](./hard-constraints.md) 与 [`acceptance.md`](./acceptance.md)：实现边界和 merge-ready 验收。

运行时 capability 的唯一事实源是 `ProviderSpec.routes`。Manifest 中的 `probe` 字段只用于新 provider 的 capture/scaffold 输入；已登记 provider 的浏览器与 Playwright 能力必须从 routes 派生。

## 本地流程

以 `onboarding/manifests/<provider>.yml` 为输入依次执行：

```bash
PYTHONPATH=src uv run python -m pytest tests/unit/test_provider_manifest_schema.py -q
PYTHONPATH=src python scripts/capture_fixture.py --from-manifest onboarding/manifests/<provider>.yml --all --auto-via --fail-fast
python scripts/propose_cleaning_chain.py --provider <provider> --write
python scripts/propose_cleaning_chain.py --provider <provider> --check-contract
python scripts/scaffold_provider.py --from-manifest onboarding/manifests/<provider>.yml --merge-existing=safe
```

完成 provider-owned 实现与测试后，为每个 non-null DOI 先审阅、再写入 snapshot：

```bash
PYTHONPATH=src python scripts/snapshot_expected.py --doi <doi> --review
PYTHONPATH=src python scripts/snapshot_expected.py --doi <doi>
```

根据 `markdown-quality-prompt.md` 阅读 `extracted.md`，写回通过 schema 的 `markdown-quality.json`。可用下列命令生成待人工确认的 review artifact：

```bash
PYTHONPATH=src python scripts/bootstrap_review_artifact.py \
  --provider <provider> \
  --manifest onboarding/manifests/<provider>.yml \
  --force
```

操作者完成最终 Markdown 语义审核后，直接由同一脚本做 digest、quality、contract 与 signoff 校验：

```bash
PYTHONPATH=src python scripts/bootstrap_review_artifact.py \
  --provider <provider> \
  --manifest onboarding/manifests/<provider>.yml \
  --finalize --confirmed-final-quality --reviewed-by <reviewer>
```

最后同步运行时事实与文档，并执行 [`acceptance.md`](./acceptance.md) 中的相关测试：

```bash
PYTHONPATH=src python scripts/manifest_sync_back.py \
  --provider <provider> \
  --manifest onboarding/manifests/<provider>.yml \
  --sync-docs
```

通用 golden live 是唯一 repo-local live 生命周期；仅在明确授权、设置 `PAPER_FETCH_RUN_LIVE=1` 且具备合法访问条件时运行。常规 onboarding 验收不运行 live，也不自动触发 GitHub CI。
