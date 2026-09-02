# 添加一个 Provider：快速上手

新增 provider 只维护三类事实：运行时 `ProviderBundle`、provider-local 行为测试、golden fixture manifest。完整约束见 [`provider-development.md`](provider-development.md)。

## 1. 确认访问与路由

先确认 DOI/域名身份、合法的全文入口和需要的 fallback。只使用公开或当前用户已有权限的访问方式；不要自动登录、解 CAPTCHA、绕过 paywall/challenge，也不要从搜索候选或人工审批 YAML 生成运行时 route。

## 2. 实现 provider owner

在 `src/paper_fetch/providers/` 添加模块和 client，并导出不可变的 `PROVIDER_BUNDLE`。bundle 的 `client_factory` 直接引用 client 类或同模块的 typed callable，不写 `module:attribute` 字符串；需要先用 catalog 构造 browser profile 时，可先声明模块私有 `ProviderSpec`，再在 client 类之后组装 bundle。把模块加入 `paper_fetch.providers._BUILTIN_PROVIDER_ENTRY_MODULES`；固定 eager loader 会一次构造 bundle tuple、provider map 与 source map。route、source、身份和默认资产策略以该 bundle 为唯一运行时事实源。复用现有 HTTP/browser/PDF/JATS/HTML/asset/acceptance owner，不复制全局 waterfall 或错误分类。

## 3. 添加行为测试

在 `tests/unit/test_<provider>_provider.py` 覆盖：

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
PAPER_FETCH_RUN_FULL_GOLDEN=1 PYTHONPATH=src uv run python -m pytest tests/integration/test_golden_corpus.py -q
```

只有能力、配置或限制发生用户可见变化时才更新 [`providers.md`](providers.md)。不需要 scaffold、capture 状态机、provider manifest、review/signoff、sync-back、drift report 或 fixture 反向索引。
