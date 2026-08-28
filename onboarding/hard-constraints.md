# Provider Onboarding Hard Constraints

## 范围与访问

- Provider-specific 实现只放在 `src/paper_fetch/providers/`，对应测试放在 provider-local unit test。
- 不自动登录，不解决 CAPTCHA，不绕过 challenge/paywall，不伪造 access review 或最终 Markdown signoff。
- 不把 API key、token、browser endpoint、storage state 或本地秘密路径写入 manifest、文档、测试和 artifact。
- 只修改当前 provider 及其验收所需文件；不借 onboarding 重构无关 provider 或全局 workflow。

## 运行时契约

- Provider 必须在 `paper_fetch.providers._BUILTIN_PROVIDER_ENTRY_MODULES` 显式登记；不得恢复源码 AST discovery、fingerprint cache 或 discovery lock。
- `ProviderSpec.routes` 是 browser、Playwright、transport、timeout、concurrency、retry、acceptance 与 asset capability 的唯一运行时事实源。
- 每个成功 payload 的 `ProviderContent.route_name` 必须对应 catalog route；公开 source 与 trace marker 不能替代结构化 route。
- Provider payload 使用 typed content/artifacts/trace/warnings/merged metadata；不得恢复 `RawFulltextPayload.metadata` 兼容视图。
- Publisher 差异留在 provider-owned 模块；不得向通用 provider rules、HTML signals 或 availability owner 添加按 provider 名分支。
- 资产失败不得覆盖已成功正文，必须进入 warnings、quality 或 download trace。

## Fixture 与 review

- 每个 non-null fixture purpose 必须有 route/Markdown contract 和 provider-local 覆盖；不得保留 scaffold skip 或 review placeholder。
- 主成功路径至少有一个 Markdown 正断言和一个 site chrome/access noise/boilerplate 负断言。
- Cleaning proposal 必须通过当前 fixture digest 校验；不生成 `.evidence.yml` sidecar。
- 每个 non-null fixture 与 extra fixture 必须进入 `onboarding/reviews/<provider>.yml`，最终 `sample_representative` 与 `markdown_semantic_reviewed` 均为 true。
- 最终签核使用 `scripts/bootstrap_review_artifact.py --finalize --confirmed-final-quality`；不得手工伪造审核状态或 hash。

## 必需验证

```bash
python scripts/propose_cleaning_chain.py --provider <provider> --check-contract
python scripts/check_provider_governance.py
python scripts/validate_extraction_rules.py
PYTHONPATH=src uv run python -m pytest tests/unit/test_<provider>_provider.py -q
PYTHONPATH=src uv run python -m pytest tests/unit/test_manifest_bundle_sync.py tests/unit/test_provider_markdown_review_contract.py tests/unit/test_provider_route_contract.py tests/unit/test_provider_bundle_completeness.py tests/unit/test_provider_owner_reuse.py -q
```

默认复用项目并行 pytest 配置。Live 测试只在明确授权且依赖真实外部状态时串行运行，并说明原因。
