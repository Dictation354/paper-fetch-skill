# 新增 Provider 开发标准

paper-fetch 的 provider 开发以运行时代码、provider-local 行为测试和 golden replay 为事实源。仓库不维护第二份 provider manifest、访问审批 YAML、review signoff、能力镜像或双向同步状态。

## 事实边界

- Runtime 能力、身份、route、source 和资产默认值由 provider 模块中的 `ProviderBundle` / `ProviderSpec` 声明。
- 提取、fallback、访问边界和用户可见 Markdown 由 provider-local unit/integration test 验证。
- fixture 身份、输入资产和预期结果由 `tests/fixtures/golden_criteria/manifest.json` 及对应目录保存。
- 用户可见能力和限制只在 [`providers.md`](providers.md) 维护；实现细节不复制成机器治理清单。

## 最小开发流程

1. 确认目标属于已知论文获取，并记录合法的公开或已授权访问路径。不得自动登录、解 CAPTCHA、绕过 challenge/paywall，或把猜测的私有接口作为 route。
2. 在 `src/paper_fetch/providers/` 添加 provider owner，并声明完整 `ProviderBundle`。优先复用现有 resolver、HTTP policy、HTML/JATS/PDF 提取、browser facade、asset budget 和 acceptance owner。
3. 为每个新行为添加 provider-local 测试。至少覆盖身份/路由、主全文路径、必要 fallback、正文结构和适用的图表/公式/补充材料语义。
4. 把代表性真实样本加入 golden fixture 目录和 `tests/fixtures/golden_criteria/manifest.json`，保留来源与用途；不要再同步另一份 YAML 能力清单。
5. 仅在用户可见能力、配置或限制变化时更新 [`providers.md`](providers.md) 和必要的提取说明。

## Provider contract

Provider 必须返回现有 typed payload，并让统一 acceptance 决定最终结果。route/source trace 必须来自真实 acquisition；失败应使用现有 `ProviderFailure` 和 reason code。不要在 provider 内复制全局 retry、cache、browser、asset、acceptance 或 Markdown 渲染状态机。

访问受限、challenge、正文不足、非 PDF wrapper 和身份不匹配必须 fail closed。敏感 header、cookie、token、带签名 URL 和本地凭据路径不得写入 fixture、artifact 或诊断文本。

## 验证

先运行 provider-local 测试和相关 golden replay，再运行 catalog/identity 与 integration 验证：

```bash
PYTHONPATH=src uv run python -m pytest tests/unit/test_<provider>_provider.py -q
PYTHONPATH=src uv run python -m pytest tests/unit/test_provider_bundle_registration.py tests/unit/test_provider_catalog.py -q
PAPER_FETCH_RUN_FULL_GOLDEN=1 PYTHONPATH=src uv run python -m pytest tests/integration/test_golden_corpus.py -q
```

真实 publisher live smoke 只在具备合法访问条件时显式运行，不能替代 committed fixture regression。新增 provider 的完成条件是 runtime bundle、provider-local 行为、代表性 golden replay 和必要用户文档一致；不要求 review artifact、hash signoff、drift report 或文档反向索引。
