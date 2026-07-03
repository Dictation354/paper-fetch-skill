# Provider Runtime 优化建议

本文汇总对当前 provider runtime 模块的优化分析，范围聚焦 browser runtime、browser workflow、provider 运行时依赖注入、CDP 生命周期、storage-state、preflight/auth 和 browser-backed 资产下载。本文不覆盖具体出版社 HTML 清洗规则、Markdown 渲染细节或单个 provider 的内容抽取质量问题。

## 当前结构判断

当前实现已经具备比较清晰的主干：

- `src/paper_fetch/runtime.py` 提供 `RuntimeContext`，负责 HTTP transport、parse/session cache、artifact store 和跨调用 browser manager 复用。
- `src/paper_fetch/runtime_browser.py` 提供 `BrowserContextManager`，负责 managed Chrome 启动、external CDP 连接、profile lock 和 context 创建。
- `src/paper_fetch/providers/browser_runtime/` 对外暴露 browser-neutral runtime facade 和数据类型。
- `src/paper_fetch/providers/_cloakbrowser.py` 实际承载 CloakBrowser runtime 配置、依赖检查、HTML/image payload 抓取、storage-state 保存和 runtime status。
- `src/paper_fetch/providers/browser_workflow/` 承载 browser-backed provider 的 HTML bootstrap、PDF fallback、asset download、article finalize 和 dependency injection。
- `src/paper_fetch/auth.py` 与 `src/paper_fetch/browser_preflight.py` 复用部分 browser runtime 配置和 workflow bootstrap，用于人工 auth 与批量 preflight。

整体方向是正确的：provider client 负责编排，runtime context 负责生命周期，browser workflow 负责共享 HTML/PDF/assets 行为。后续优化不建议重写，而应围绕边界收紧、重复逻辑收敛、类型化、观测性和长任务可靠性推进。

## P0 优先级

### 1. 将 `browser_runtime` 做成真正的后端抽象

现状：

- `src/paper_fetch/providers/browser_runtime/api.py` 目前基本只是 `_cloakbrowser` 的薄封装。
- `_cloakbrowser.py` 同时包含 runtime config、依赖检查、HTML 抓取、image payload、storage-state、status probe 等多类职责。
- `auth.py` 仍直接调用 `_cloakbrowser` 的私有 helper，例如 `_storage_state_path()`、`_storage_context_options()` 和 `_save_storage_state()`。

建议：

- 新增 `src/paper_fetch/providers/browser_runtime/backends/cloakbrowser.py`，把 `_cloakbrowser.py` 中后端相关实现迁入或通过兼容层逐步迁移。
- 在 `browser_runtime` 中定义明确的 `BrowserRuntimeBackend` 协议，覆盖：
  - `load_runtime_config()`
  - `ensure_runtime_ready()`
  - `probe_runtime_status()`
  - `fetch_html()`
  - `warm_context()`
  - `storage_state_path()`
  - `save_storage_state()`
- 让 `auth.py`、`browser_preflight.py`、`browser_workflow` 只依赖 `browser_runtime` 公共 API，不再调用 `_cloakbrowser` 私有函数。

收益：

- 后续如果替换或并存其他 browser backend，不需要改 provider workflow。
- 减少私有 helper 外泄造成的维护成本。
- 文档里“browser-neutral runtime API”的承诺和代码结构一致。

### 2. 统一 storage-state/profile 路径管理

现状：

- storage-state 路径逻辑散落在多个文件：
  - `_cloakbrowser._storage_state_path()`
  - `browser_preflight._storage_state_path()`
  - `auth._runtime_with_auth_storage()`
  - `browser_workflow/pdf_fallback._runtime_storage_state_path()`
- 默认 provider profile 目录逻辑也在 `_cloakbrowser.py` 和 `browser_preflight.py` 各有一份。
- storage-state 保存直接 `write_text()`，缺少明确的 atomic write 和跨进程写锁。

建议：

- 引入 `BrowserRuntimePaths` 或 `StorageStateManager`，集中处理：
  - provider 默认 `user_data_dir`
  - 显式 `profile_dir`
  - 显式 `user_data_dir`
  - legacy provider env，例如 Wiley 专用 storage env
  - storage-state JSON 路径解析
  - filtered storage-state 保存
  - atomic write
  - storage-state 写锁
- `auth`、`preflight`、PDF fallback 和 `_cloakbrowser` 统一调用该模块。

收益：

- 避免 auth、preflight、fetch 对同一 provider 生成不同 storage 路径。
- 降低批量并发任务写坏 `storage-state.json` 的概率。
- 更容易在 status/preflight 输出中解释当前实际使用的 profile 与 storage 文件。

### 3. 清理旧 fast browser 路径

现状：

- `browser_workflow/html_extraction.py` 中仍保留 `fetch_html_with_fast_browser()`，这是一套独立上下文创建、env 解析、route blocking 和 DOM readiness 逻辑。
- 当前 browser workflow bootstrap 的 fast path 实际已使用统一 `fetch_html_with_browser(..., disable_media=True, wait_seconds=0)`。
- 文档中也说明 PNAS 等 provider 不再有独立 fast browser preflight。

建议：

- 如果没有测试或调用方依赖旧函数，直接删除 `fetch_html_with_fast_browser()` 和 `_fast_browser_context_seed()`。
- 如果仍需兼容 import，则将其改为薄 wrapper，内部调用统一 `fetch_html_with_browser()`。
- 同步 `browser_workflow/__init__.py` 的 lazy exports 和相关测试。

收益：

- 避免两套 fast-path 行为漂移。
- 减少 runtime/env/profile 解析重复。
- 降低之后修改 browser context 生命周期时遗漏旧路径的风险。

## P1 优先级

### 4. 将 browser context seed 类型化

现状：

- `BrowserFetchedHtml.browser_context_seed` 目前是 `Mapping[str, Any]`。
- seed 字段依赖约定字符串：`browser_cookies`、`browser_user_agent`、`browser_final_url`。
- AMS direct HTTP asset mode 通过 seed 中的 `paper_fetch_html_fetcher` marker 判断。

建议：

- 定义 `BrowserContextSeed` TypedDict 或 frozen dataclass：
  - `cookies`
  - `user_agent`
  - `final_url`
  - `html_fetcher`
  - `metadata` 或 `diagnostics`
- 提供 `from_mapping()` 和 `to_mapping()`，兼容旧 payload。
- `merge_browser_context_seeds()` 返回类型化 seed，而不是裸 dict。
- 把 direct HTTP / browser-backed / external CDP 等模式放入明确字段，避免扩散 ad-hoc key。

收益：

- asset download、PDF fallback、preflight 的 seed 使用更可读。
- 单测可以围绕字段契约写，而不是字符串 key。
- 后续增加 seed 信息时不容易破坏旧调用方。

### 5. 拆小 `BrowserWorkflowDeps`

现状：

- `BrowserWorkflowDeps` 一次包含 19 个 callable。
- 字段同时覆盖 runtime、HTML extraction、PDF fallback、assets、缓存、私有 helper。
- 测试替换依赖时经常需要从 `default_browser_workflow_deps()` 复制整组依赖再 `replace()`。

建议：

- 拆成更小的依赖组：
  - `BrowserRuntimeDeps`
  - `BrowserHtmlDeps`
  - `BrowserPdfDeps`
  - `BrowserAssetDeps`
  - `BrowserCacheDeps`
- 或者定义 Protocol，以行为接口替代大号 dataclass。
- 保留 `BrowserWorkflowDeps` 作为短期聚合兼容层，但内部字段按子组组织。

收益：

- provider client 的真实依赖面更清楚。
- 单元测试更局部，mock 泄漏更少。
- 新增 browser workflow 能力时不会持续扩大一个全局依赖对象。

### 6. 增强 runtime 可观测性

现状：

- `_cloakbrowser.fetch_html_with_cloakbrowser()` 记录了部分 debug log，但最终对上层主要暴露最后一次 failure。
- `RuntimeContext.stage_timings` 已有基础，但 browser 阶段没有系统记录。
- preflight 返回字段较少，排查 managed browser 启动、CDP 连接、DOM readiness、storage 保存失败时信息有限。

建议：

- 为 browser fetch 增加结构化 trace：
  - candidate URL 数量
  - 每个 candidate 的 start/end/duration
  - response status
  - final URL
  - redirect/abstract/block reason
  - CDP connect duration
  - DOM readiness duration
  - storage-state save result
  - media blocking 是否启用
- 将上述信息写入 `ProviderContent.diagnostics` 或 `warnings/trace` 的结构化字段。
- `probe_runtime_status()` 增加可选深度探测模式，区分“依赖可 import”和“CDP 可连接/managed Chrome 可启动”。

收益：

- live publisher 失败时更容易归因到网络、challenge、storage、CDP 或 extractor。
- preflight/auth 的用户输出可以更准确。
- 后续性能优化有可量化基线。

### 7. 明确 shared browser manager 生命周期策略

现状：

- `RuntimeContext` 通过进程级 `_SHARED_BROWSER_MANAGERS` 和 ref_count 共享 `BrowserContextManager`。
- managed browser 在 headless 模式变化时会关闭并重启。
- 当前主要依赖 `RuntimeContext.close()` 与 `__del__()` 做清理。

建议：

- 增加 `atexit` cleanup，兜底关闭进程级 shared managers。
- 增加 manager dump 诊断，用于测试或 debug 输出当前 key、ref_count、managed/external 模式。
- 增加泄漏测试，覆盖异常路径下 ref_count 归零和 managed Chrome 终止。
- 在文档中明确同一批次不要混用 headed/headless，否则 managed browser 会重启。

收益：

- 批量任务异常退出时更少残留 Chrome 进程。
- 多 RuntimeContext 并发时更容易定位 profile lock 和 ref_count 问题。
- 生命周期行为更可预期。

## P2 优先级

### 8. 显式化 external CDP 语义

现状：

- external CDP 模式会借用已有 browser context。
- 如果已有 context 存在，`user_agent`、`viewport`、locale 等 context options 会被忽略，只 debug 记录。
- storage-state 只尽量注入 cookies，不能完整覆盖 external context 状态。

建议：

- 在 status/preflight 结果中明确输出：
  - external CDP endpoint 已配置
  - 是否借用了既有 context
  - 哪些 context options 被忽略
  - storage-state cookies 注入数量
- 可选增加 env 开关，例如 `PAPER_FETCH_CDP_EXTERNAL_NEW_CONTEXT=1`，允许在 external browser 中新建 context。

收益：

- 用户不会误以为 external CDP 下 UA/profile/storage-state 完全等价于 managed 模式。
- 更容易解释“auth 已保存但 external browser 仍失败”的情况。

### 9. 优化 browser-backed 资产下载批次复用

现状：

- asset 下载会根据 external CDP 串行化，managed 模式下按配置并发。
- 线程本地 browser document fetcher 为了 Playwright sync 对象线程所有权，在每次调用后立即关闭 fetcher。
- 这保证安全，但会损失同一批图片下载中的 warm cache 和页面复用。

建议：

- 增加 scoped batch fetcher 生命周期：
  - 每个 worker 线程在一次资产下载 attempt 内复用 context/page。
  - attempt 结束时由同一线程关闭。
  - 失败缓存仍同步到共享 failure cache。
- 保留当前 per-call close 作为 fallback，遇到 Playwright 线程所有权异常时自动降级。

收益：

- 大量 figure/full-size/preview candidate 的 browser round-trip 更少。
- Science/Wiley/ACS 等正文图较多时下载速度更稳定。
- 不牺牲现有线程安全策略。

### 10. 补齐长任务取消检查

现状：

- HTTP transport 已支持 `cancel_check`。
- browser navigation、candidate retry、PDF fallback、asset retry 中没有统一取消检查。
- 长批量任务取消时，browser 阶段可能明显滞后。

建议：

- 在以下位置插入轻量 cancel check：
  - HTML candidate 循环前后
  - DOM readiness 等待前后
  - PDF fallback warm seed 前后
  - asset download attempt 和 retry 前
  - browser preflight provider 循环前
- 统一抛出可识别的取消异常或 `ProviderFailure` reason code，避免被误归类为 provider failure。

收益：

- MCP/CLI 批量任务取消更及时。
- 避免取消后仍继续打开浏览器或下载资产。

## 建议落地顺序

1. 先清理旧 fast browser 路径，范围小，回归风险可控。
2. 抽 `BrowserRuntimePaths`/storage manager，并补 auth/preflight/fetch 的路径一致性测试。
3. 将 `_cloakbrowser` 后端化，保留兼容 re-export，逐步迁移调用方到 `browser_runtime` 公共 API。
4. 类型化 `BrowserContextSeed`，先保留 mapping 兼容，再逐步收紧调用点。
5. 拆分 `BrowserWorkflowDeps`，优先从 runtime/pdf/assets 三组开始。
6. 补 runtime 结构化 trace 和 stage timing。
7. 再做 external CDP 行为显式化、资产批次复用和取消检查。

## 测试建议

每个阶段建议至少覆盖：

- `PYTHONPATH=src python3 -m pytest tests/unit/test_runtime_browser.py tests/unit/test_cloakbrowser_backend.py tests/unit/test_browser_preflight.py tests/unit/test_auth.py -q`
- `PYTHONPATH=src python3 -m pytest tests/unit/test_browser_workflow_deps.py tests/unit/test_atypon_browser_workflow_provider_fallbacks.py tests/unit/test_atypon_browser_workflow_provider_asset_downloads.py -q`
- 涉及 storage/profile 行为时，增加临时目录下的 auth/preflight/fetch 路径一致性单元测试。
- 涉及 external CDP 行为时，继续使用 fake CDP browser/context，不在 unit 中启动真实浏览器。
- 涉及 live publisher 或真实 browser preflight 时，再单独运行 live/preflight 验证，并在结果中说明这是依赖外部状态的串行验证。

## 文档同步点

实现上述优化时需要同步：

- `README.md` 的 Browser workflow/runtime 段落。
- `docs/providers.md` 的环境变量、auth、preflight 和 browser-backed provider 行为说明。
- `docs/browser-runtime.md`，目前内容过短，适合作为 runtime ownership 和 backend contract 的入口。
- `docs/architecture/overview.md` 的 provider/browser workflow 分层说明。
- `CHANGELOG.md` 和 `CHANGELOG_CN.md`，按行为变化记录兼容性和迁移说明。
