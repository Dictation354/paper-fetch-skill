# 添加 Provider：开发流程与契约

新增 provider 以运行时 `ProviderBundle`、provider-local 行为测试和 golden fixture manifest 为事实源。用户可见能力与限制统一维护在 [`providers.md`](providers.md)。

## 1. 确认访问与路由

先确认目标属于已知论文获取，再确认 DOI/域名身份、合法的全文入口和需要的 fallback；不得把猜测的私有接口作为 route。只使用公开或当前用户已有权限的访问方式；不要自动登录、解 CAPTCHA、绕过 paywall/challenge，也不要从搜索候选或人工审批 YAML 生成运行时 route。

## 2. 实现 provider owner

在 `src/paper_fetch/providers/` 添加模块和 client，并导出不可变的 `PROVIDER_BUNDLE`。bundle 的 `client_factory` 直接引用 client 类或同模块的 typed callable，不写 `module:attribute` 字符串；需要先用 catalog 构造 browser profile 时，可先声明模块私有 `ProviderSpec`，再在 client 类之后组装 bundle。把模块加入 `paper_fetch.providers._BUILTIN_PROVIDER_ENTRY_MODULES`；固定 eager loader 会一次构造 bundle tuple、provider map 与 source map。route、source、身份和默认资产策略以该 bundle 为唯一运行时事实源。复用现有 HTTP/browser/PDF/JATS/HTML/asset/acceptance owner，不复制全局 waterfall 或错误分类。

### Provider contract

Provider 必须返回现有 typed payload，并让统一 acceptance 决定最终结果。route/source trace 必须来自真实 acquisition；失败应使用现有 `ProviderFailure` 和 reason code。不要在 provider 内复制全局 retry、cache、browser、asset、acceptance 或 Markdown 渲染状态机。

内置模块由固定清单 eager import；bundle 的 callable 只供 runtime registry 构造 client，并由 registry 按 provider 隔离构造失败。`ProviderSpec` 只保存可描述的 catalog 事实，运行 callable 不进入 MCP provider catalog 或其它公开序列化 payload。

访问受限、challenge、正文不足、非 PDF wrapper 和身份不匹配必须 fail closed。敏感 header、cookie、token、带签名 URL 和本地凭据路径不得写入 fixture、artifact 或诊断文本。

正文请求的 `HttpRequestPolicy.body_access_provider` 默认为 `None`，由既有请求策略编译器为 HTML/XML/PDF route 赋值；手写正文策略需显式设置。它在 HTTP 失败重试前启用访问检查，不从 cooldown 字符串推断 provider，资产及 metadata 请求保持默认。付费墙选择器与信号放在 provider 的 `AvailabilityPolicy`，检测只产生证据；受限结果由现有 provider 结果层组装。正文检测输入不变时复用检查，组装后新增 diagnostics 仍必须验证。

`ProviderRenderPolicy.rewrite_asset_links` 默认为 `None`，沿用通用资产链接匹配。需要精确对象身份的 provider 可提供 `(markdown_text, assets, doi) -> str` 函数，在现有 builder 内直接改写；PLOS 以论文 DOI 和对象 ID 绑定本地路径或官方远程 URL。该 callable 不进入公开序列化结果。

## 3. 添加行为测试

最小片段与边界 mock 放在 `tests/unit/test_<provider>_provider.py`，真实进程和浏览器契约放在 `tests/integration/`，整篇内容回放放在 `tests/golden/`。至少覆盖：

- bundle 导出、身份和 route；
- 主全文路径与必要 fallback；
- 正文结构及适用的 figure/table/formula/supplementary/reference；
- challenge、非全文 wrapper、身份不匹配等 fail-closed 边界。

## 4. 添加代表性 golden replay

将脱敏后的真实响应放入 `tests/fixtures/golden_criteria/<fixture-id>/`，并只在 `tests/fixtures/golden_criteria/manifest.json` 登记 fixture 身份、用途、输入和预期结果。默认不覆盖现有 fixture；检查响应中没有 token、cookie、签名 URL 或本地路径。

## 5. 验证并记录用户可见变化

```bash
PYTHONPATH=src uv run python -m pytest tests/unit/test_<provider>_provider.py -q
PYTHONPATH=src uv run python -m pytest tests/unit/test_provider_bundle_registration.py tests/unit/test_provider_catalog.py -q
PYTHONPATH=src uv run python -m pytest tests/golden -q
```

只有能力、配置或限制发生用户可见变化时才更新 [`providers.md`](providers.md)。不需要 scaffold、capture 状态机、provider manifest、review/signoff、sync-back、drift report 或 fixture 反向索引。

真实 publisher live smoke 只在具备合法访问条件时显式运行，不能替代 committed fixture regression。完成条件是 runtime bundle、provider-local 行为、代表性 golden replay 和必要用户文档一致。
