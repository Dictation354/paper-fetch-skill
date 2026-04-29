# 项目优化分析

Date: 2026-04-29
Status: first-round completed
Scope: `paper-fetch-skill` 当前工作区代码；本文记录优化点与第一轮落地状态。

本次分析基于 `README.md`、`docs/architecture/*`、`docs/deployment.md`、`todo.md`、`pyproject.toml`、`.github/workflows/ci.yml`、`src/paper_fetch/`、`src/paper_fetch_devtools/` 和测试目录的静态阅读。

---

## 第一轮完成状态

已完成“正确性 + MCP 瘦身”范围：

- 仓库卫生：`rollout-*.jsonl` 从版本库移除并加入 `.gitignore`，新增 ignored 本地产物清理脚本。
- HTTP 缓存正确性：敏感 header 使用短 SHA-256 digest 参与 cache key，避免不同凭据共享 memory / disk cache，同时不泄露 token 原文。
- MCP 层拆分：`mcp/tools.py` 保留兼容 facade，结果封装、log bridge、cache payload、fetch payload、batch runner 和 FastMCP compat 分拆到独立模块。
- MCP async runner：统一使用有界 `ThreadPoolExecutor`，保留输入顺序、rate-limit abort、progress、structured log 和 cancellation 语义。
- CI / packaging：dev extra 补齐 `pytest` / `build`，GitHub CI 增加 sdist / wheel build 与 wheel 安装 smoke。
- 文档同步：README、provider 文档、架构文档和部署文档已记录缓存隔离、MCP 模块边界、bounded runner、server compat 和 CI smoke。

暂未实施后续大范围优化：provider/browser workflow 大拆分、HTTP 模块拆包、磁盘缓存容量管理、新 provider、`batch_fetch` 或 markdown resource-first 功能。

---

## 0. 当前基线

- 核心库 `src/paper_fetch` 约 37K 行 Python，devtools 约 2.2K 行，测试代码约 27.8K 行。
- 测试文件 52 个；`tests/fixtures` 约 44 MB；本地 `live-downloads/` 约 5.2 GB，`.paper-fetch-runs/` 约 102 MB。
- 最大源码热点：
  - `providers/_browser_workflow_fetchers.py` 1498 行
  - `providers/browser_workflow.py` 1351 行
  - `providers/springer.py` 1262 行
  - `mcp/tools.py` 1223 行
  - `quality/html_availability.py` 1229 行
  - `extraction/html/assets/download.py` 1139 行
  - `http.py` 1006 行
  - `formula/convert.py` 978 行
  - `providers/_flaresolverr.py` 971 行
  - `providers/_article_markdown_elsevier.py` 959 行
  - `providers/elsevier.py` 948 行
- 架构基线已经落地：`service.py` 是薄 facade，核心编排在 `workflow/`；provider 身份集中在 `provider_catalog.py`；CI 已有 lint、unit、integration、offline package、手动 full-golden、手动 live-mcp。

这说明优化重点不再是“有没有分层”，而是：收束兼容层、降低热点模块耦合、统一运行时设施、提高发布/缓存/质量门禁的确定性。

---

## 1. 立刻处理的仓库卫生

### 1.1 删除或忽略本地运行产物

当前 `rollout-2026-04-28T19-46-52-019dd3e9-df6e-7f91-9bb1-2d0093b7ba11.jsonl` 约 933 KB，且被 git 跟踪。它是 agent 运行日志，不属于产品代码或文档，应从版本库移除，并在 `.gitignore` 加：

```gitignore
rollout-*.jsonl
*.local.md
```

`live-downloads/`、`.paper-fetch/`、`.paper-fetch-runs/` 已被 ignore，但本地体积大，建议补 `scripts/clean-local-artifacts.sh`，支持按目录和 mtime 清理，避免手动 `rm -rf`。

### 1.2 处理已完成计划文档和 todo

`plan-extract-live-tooling.md` 当前在工作区是删除状态，且架构文档已经记录当前基线。建议确认是否正式删除；若仍有历史价值，迁到 `docs/architecture/history/`，不要留在根目录。

`todo.md` 已完成项仍和未完成项混在一起。建议拆成：

- `todo.md`：只保留未完成工作。
- `docs/architecture/history/` 或 `CHANGELOG.md`：记录已完成事项。

这样后续排期不会把“已完成但未清理”的内容误判成待办。

---

## 2. 运行时与兼容层优化

### 2.1 收束 legacy keyword / context 双路径

当前状态：本轮已收束 MCP/service 内部调用和 provider fulltext 主链；公开 service 入口仍保留旧 keyword 参数兼容。

- `runtime.resolve_runtime_context()` 文档直接标注“Merge explicit legacy keyword arguments”。
- 已完成：`mcp/fetch_tool.py` 的 `_call_service_*` 不再捕获 `TypeError` 回退旧签名，统一通过 `RuntimeContext` 调用 service。
- 已完成：`workflow/fulltext.py` 删除 `_fetch_result_accepts_artifact_store()` 和 `inspect.signature()` 分支，内部 `FulltextProvider.fetch_result()` 调用总是传入 `artifact_store=` 与 `context=`。
- 已完成：MCP unit/integration fake 已迁到当前 service 签名。

后续建议：

1. 给公开 service legacy keyword 兼容设一个明确移除版本。
2. 评估 `runtime.resolve_runtime_context()` 文档是否从 legacy 语言改成 public compatibility 语言。

收益是减少异常控制流、减少动态签名判断，也让类型检查能真正覆盖 service/provider 交界。

### 2.2 收束 `RawFulltextPayload.metadata` 兼容口袋

`ProviderContent`、`ProviderArtifacts`、`ProviderFetchResult` 已经是 typed contract，但 `RawFulltextPayload.metadata` 还会把兼容字段导出成 dict。当前 docs 已说明它是只读兼容导出。

本轮已完成：

1. 生产 workflow 与重点 provider/service/MCP 测试迁到 typed fields：`ProviderContent.route_kind`、`markdown_text`、`diagnostics`、`fetcher`、`browser_context_seed`、`warnings`、`trace`。
2. `RawFulltextPayload.metadata` property 已标注为 legacy read-only compatibility view，并集中保留 compatibility test 覆盖合成 shape。
3. 测试 helper 不再通过 `metadata["route"]` 判定 artifact policy。

后续建议：

1. 新测试继续只断言 typed fields，避免新增对 `raw_payload.metadata[...]` 的依赖。
2. 可补架构测试，防止生产路径重新读取 legacy metadata magic keys。

风险主要是旧测试和第三方脚本；可通过一个版本周期的文档说明缓冲。

### 2.3 `fetch_fulltext()` dict 旧接口下线

`ProviderClient` 仍保留 `fetch_fulltext()`，`elsevier.py` 和 `springer.py` 也有旧 dict 结果入口，但主链已经走 `fetch_result()` template-method。

当前状态：本轮确认 CLI/MCP/service 主链不依赖 `fetch_fulltext()` dict 接口，公开方法暂不删除。

后续建议：

- 将 provider 旧接口改为测试专用或显式 deprecated。
- 迁移测试到 `fetch_result()` / `fetch_raw_fulltext()`。

这能减少 provider 需要维护的返回形状数量。

---

## 3. MCP 层优化

### 3.1 拆分 `mcp/tools.py`

`mcp/tools.py` 当前 1223 行，同时负责：

- Pydantic request 到 service 参数转换
- payload shape
- cache envelope 读写桥接
- batch runner
- inline image 输出
- structured log bridge
- sync/async tool wrappers

建议拆成子模块，而不是只做机械切文件：

- `mcp/results.py`：`_tool_result()`、错误 payload、validation reason。
- `mcp/fetch_tool.py`：`fetch_paper` payload、inline image、envelope shaping。
- `mcp/batch.py`：同步/异步 batch runner、rate-limit abort 语义。
- `mcp/log_bridge.py`：structured log parsing 和 notification handler。
- `mcp/cache_payloads.py`：`list_cached`、`get_cached` 的 payload glue。

拆分验收标准：`server.py` 只 import tool-level 函数；每个子模块都有对应 unit tests；原有 MCP integration tests 不改公开行为。

### 3.2 统一 async blocking runner

当前 `_run_blocking_call()` 每次调用创建一个 daemon thread；`_run_batch_async()` 再用 `asyncio.create_task(_run_blocking_call(...))` 做并发。对于 50 条 batch query，这会短时间创建多条线程，且取消只能通过 `RuntimeContext.cancel_check` 间接生效。

建议改为：

- 每次 MCP tool 调用创建一个 bounded `ThreadPoolExecutor(max_workers=concurrency)`。
- async 侧用 `loop.run_in_executor()` 或 `asyncio.to_thread()` 加 semaphore。
- 取消时设置 shared `threading.Event`，同时停止提交新任务。
- 保留当前“已提交任务完成后返回已有结果，rate_limited 停止继续提交”的语义。

收益是线程数量可控，batch 和单篇 fetch 共用同一套实现。

### 3.3 减少对 FastMCP 私有字段的依赖

`mcp/server.py` 直接访问：

- `server._resource_manager._resources`
- `server._mcp_server.create_initialization_options`
- `server._mcp_server.run`

这让项目对 MCP SDK 内部结构比较敏感。短期可接受，但建议把这些访问集中到 `mcp/server_compat.py`，并补一个小的 compatibility test，锁住 SDK 升级失败时的报错位置。

如果 SDK 已提供公开 API，应优先迁过去；如果没有，compat 模块至少能把风险隔离在一处。

---

## 4. HTTP、缓存与安全边界

### 4.1 HTTP cache key 不应把不同凭据折叠成同一个 key

`HttpTransport` 的 cache key 会包含敏感 header 名称，但值统一替换为 `***`。这避免泄露 token，但也意味着同 URL、同 Accept、不同 API key / token 的 GET 响应可能命中同一缓存项。

涉及 header 包括：

- `authorization`
- `wiley-tdm-client-token`
- `x-els-apikey`
- `x-els-insttoken`
- `cr-clickthrough-client-token`

建议二选一：

1. 只要请求含敏感 header，就禁用 memory/disk cache。
2. 用不泄露原文的 keyed digest 参与 cache key，例如 `sha256("header-name\0value")[:16]`。

优先级高于文件拆分，因为这是跨凭据正确性和隔离问题。

### 4.2 拆分 `http.py`

`http.py` 1006 行，职责包含请求、retry、body 限制、gzip、memory cache、disk cache、cache stats、错误映射。建议拆成：

- `http/transport.py`：public `HttpTransport.request()`。
- `http/cache.py`：cache key、memory/disk cache、stats。
- `http/retry.py`：429 / transient retry policy。
- `http/body.py`：body read、gzip、preview、content-type helper。
- `http/errors.py`：`RequestFailure`、cancel、network detail。

拆分前先加或保留 `test_http_cache.py` 的缓存/限流/重试测试，避免拆分时改变 request option 语义。

### 4.3 磁盘缓存缺少容量和生命周期管理

HTTP textual disk cache 目前按 sha256 路径写入，没有看到全局大小、条目数或 TTL 清理；MCP fetch-envelope/cache index 也只随 DOI refresh 更新。

建议：

- 给 HTTP disk cache 增加 `max_entries` / `max_bytes` / `max_age_days`。
- 给 `paper-fetch` CLI 或脚本暴露 `clean-cache` 能力。
- 在 live review 报告里记录 cache dir size，避免 5 GB 级下载目录继续膨胀。

---

## 5. Provider 与资产下载热点

### 5.1 将 `providers/browser_workflow.py` 变成真正 facade

`browser_workflow.py` 当前既是 facade，又包含 bootstrap、PDF fallback、article assembly、asset retry merge、abstract-only recovery、profile 基类等逻辑。

建议迁移为包：

```text
providers/browser_workflow/
  __init__.py              # re-export stable patch points
  profile.py               # ProviderBrowserProfile
  bootstrap.py             # HTML preflight / FlareSolverr bootstrap
  pdf_fallback.py          # seeded browser PDF/ePDF
  article.py               # browser_workflow_article_from_payload
  assets.py                # related asset orchestration
  client.py                # BrowserWorkflowClient
```

保留 `providers/browser_workflow.py` 一轮兼容 re-export，等测试和 provider import 全部迁移后删除。

### 5.2 拆 `_browser_workflow_fetchers.py`

该文件 1498 行，含 Playwright JS、context 创建、image/file document fetcher、thread-local fetcher、memoization、Cloudflare recovery 诊断。建议拆成：

- `fetchers/context.py`：`_new_playwright_context` 与 seed/cookie warmup。
- `fetchers/image.py`：image response、canvas recovery、image payload validation。
- `fetchers/file.py`：supplementary file document fetcher。
- `fetchers/memo.py`：`_MemoizedImageDocumentFetcher`、`_MemoizedFigurePageFetcher`。
- `fetchers/diagnostics.py`：failure/recovery diagnostic helpers。

同时把大段 JS 字符串迁到资源文件或至少集中到单独模块，降低 Python 文件噪音。

### 5.3 抽象 `extraction/html/assets/download.py` 的重复下载循环

`download.py` 中 figure 与 supplementary 下载都在做：

- 候选 URL 列表生成
- URL scheme 校验
- HTTP / opener / Playwright fallback
- block reason 判断
- failure diagnostic
- 并发 resolve、串行落盘

建议引入小型内部模型：

- `AssetDownloadCandidate`
- `AssetDownloadAttempt`
- `AssetDownloadResult`
- `AssetDownloadFailure`

然后把 figure、table/formula image、supplementary 的差异收敛到策略函数。这样新增 provider 资产逻辑时不需要继续复制 `_resolve_*_download()`。

### 5.4 资产下载并发需要统一预算

当前并发预算分散在：

- MCP batch `concurrency`
- `HttpTransport.per_host_concurrency`
- `PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY`
- `workflow.metadata` / `workflow.routing` 内部 `ThreadPoolExecutor`
- browser workflow thread-local Playwright fetcher

建议形成一个文档化的“并发预算矩阵”：

| 层级 | 当前默认 | 优化方向 |
| --- | --- | --- |
| batch query | 1，最大 8 | 继续由 MCP schema 限制 |
| HTTP same host | 4 | 保留 transport 层限流 |
| asset download | 4 | 与 provider/browser worker 数联动 |
| metadata/probe | 固定 3 或候选数 | 改成 RuntimeContext executor 或明确上限 |
| Playwright context | worker thread local | 加总数上限，避免 batch+assets 双重放大 |

关键是防止 `batch_check(article, concurrency=8)` 再叠加每篇 4 个资产 worker，导致同一进程瞬间创建过多网络/浏览器工作。

---

## 6. 数据模型与输出语义

### 6.1 统一 dict 诊断为 typed model

大量资产、诊断和 availability 数据仍以 `dict[str, Any]` 流动。短期灵活，但重构时难发现字段拼写或 shape 漂移。

建议先从高价值边界开始：

- `AssetFailureDiagnostic`
- `AvailabilityDiagnostics`
- `ProviderContent.diagnostics`
- `FetchCache` sidecar payload

项目已经依赖 `pydantic>=2`，可以用 `BaseModel` / `TypeAdapter` 做边界校验，而内部仍保留 dataclass。不要新增序列化框架。

### 6.2 让 `trace` 成为唯一内部来源

当前 `warnings`、`source_trail`、`trace` 三套信息并存，`Quality.__post_init__()` 和 `FetchEnvelope` 会互相派生。兼容合理，但内部新增逻辑应优先写 `TraceEvent`。

建议：

- 新代码不再直接拼 `source_trail` 字符串，统一用 `trace_event()`。
- `source_trail` 只在输出边界派生。
- 架构测试允许旧 marker，但禁止新增 provider/workflow 中的裸字符串 marker。

这样可以降低“同一事件 warnings/source_trail/trace 三处不同步”的概率。

### 6.3 明确 `source` 与 `content_kind` 矩阵

文档已经说明 metadata fallback 时 public `source` 可能是 `metadata_only`，但 `content_kind` 可能是 `abstract_only`。建议在 README 或架构文档增加一张矩阵：

| 场景 | `source` | `content_kind` | `has_fulltext` |
| --- | --- | --- | --- |
| provider fulltext | provider source | `fulltext` | true |
| provider abstract-only | provider source | `abstract_only` | false |
| Crossref/metadata 有摘要 | `metadata_only` | `abstract_only` | false |
| 纯 metadata | `metadata_only` | `metadata_only` | false |

这能减少 MCP host 和下游脚本误读结果。

---

## 7. 测试、CI 与发布

### 7.1 CI 已有，但还缺三类门禁

当前 CI 已有：

- `ruff check .`
- unit + devtools
- integration
- offline linux package build/verify
- 手动 full golden
- 手动 live MCP

建议补：

1. `python -m build` + wheel install smoke，验证 PyPI 包内容。
2. `pytest --cov=paper_fetch --cov-report=xml`，先设低阈值，只用于观察重构风险。
3. `mypy` 或 `pyright` 分阶段接入，先覆盖 `models`、`workflow`、`provider_catalog`、`mcp/schemas`。

`pyproject.toml` 的 `dev` extras 也应补 `pytest`、`pytest-cov`、`build`、类型检查工具，避免依赖外部环境隐式带入。

### 7.2 Golden / live 验证应有固定节奏

full golden 目前是手动 workflow_dispatch。建议加 nightly 或 weekly schedule，但只跑离线 fixtures，不碰 live provider。live MCP 保持手动和 secrets gate。

这样 provider/extraction 重构后能更早发现 fixture 回归，同时不增加 publisher 侧压力。

### 7.3 发布元数据与依赖 extras

PyPI 发布前建议补：

- `[project.urls]`
- `license` / classifiers
- sdist/wheel 构建检查
- README 中明确 extras 选择

依赖可分层：

- `core`：metadata、HTML/XML 解析、基础 CLI
- `mcp`：`mcp`
- `pdf`：`PyMuPDF`、`pymupdf4llm`
- `browser`：`playwright`
- `dev`：测试、lint、type、build

是否真的拆 extras 要结合安装脚本和离线包一起做；不要只改 `pyproject.toml`，否则 `install.sh`、offline package、CI 都会漂移。

---

## 8. 用户可见功能优化

### 8.1 “下载 md 时不让文档全部进入上下文”

这是 `todo.md` 中最高用户价值项。建议走 MCP resource-first 方案：

1. `fetch_paper(modes=["metadata"], prefer_cache=true)` 返回轻量 envelope。
2. 完整 Markdown 写入 cache sidecar / `.md` 文件。
3. MCP payload 返回 `resource_uri`、token breakdown、section index。
4. 新增 `read_cached_section(entry_id, section, max_tokens)` 或复用 resource template 让 host 分段读取。

这样比在 tool result 里返回巨大 markdown 更适合长文和多图论文。

### 8.2 文献抓取并行化

`batch_resolve` / `batch_check` 已有并发；`fetch_paper` 仍是单篇工具。若要做“多篇完整抓取”，建议新增 `batch_fetch`，但默认只返回轻量结果和 cache resource URI，不把每篇正文都放进一次 MCP result。

关键参数：

- `queries`
- `concurrency`
- `modes`
- `strategy`
- `max_result_tokens_per_item`
- `return_mode = "summary" | "cache_refs"`

不要复用 `batch_check(mode="article")` 承担完整下载产品语义，它现在更像批量检查。

### 8.3 新 provider 支持

`provider_catalog.py` 已是 single source，新增 provider 的路径清晰。建议优先顺序：

1. Copernicus：XML/JATS 路径，稳定性可能最好。
2. MDPI：HTML + Playwright fallback，注意页面 chrome 和公式。
3. AMS / AIP / APS / JPX：先做 metadata + PDF fallback，再逐步做 HTML。

每个 provider 的最小交付：

- catalog spec
- provider client
- status probe
- 2-3 个 fixture regression
- docs/providers.md 能力矩阵
- README provider 概览更新

### 8.4 Gemini CLI 支持

已有 `install-codex-skill.sh` 和 `install-claude-skill.sh`。Gemini CLI 支持建议做成第三个安装脚本，不要改 skill 内容：

- `scripts/install-gemini-skill.sh`
- 复用 `scripts/run-codex-paper-fetch-mcp.sh` 或抽象成通用 MCP launcher
- 更新 `docs/deployment.md`

---

## 9. 建议执行顺序

### Phase 0：低风险清理（0.5 天）

- 从 git 移除 `rollout-*.jsonl`，补 `.gitignore`。
- 确认 `plan-extract-live-tooling.md` 是删除还是归档。
- 修剪 `todo.md` 已完成项。
- 增加本地 artifact/cache 清理脚本。

### Phase 1：正确性优先（1 天）

- 修正 HTTP cache key 的敏感 header 折叠问题。
- 为该问题补 unit tests：不同 token 不共享缓存；日志和 index 不泄露 token。
- 补 wheel build smoke CI。

### Phase 2：MCP 层瘦身（1-2 天）

- 拆 `mcp/tools.py`。
- 统一 sync/async batch runner。
- 把 FastMCP 私有 API 访问集中到 compat 模块。

### Phase 3：Provider / asset 下载重构（3-5 天）

- 先拆 browser workflow package。
- 再拆 `_browser_workflow_fetchers.py`。
- 最后抽象 `assets/download.py` 的通用下载 plan/result。

### Phase 4：质量门禁与类型化（2-4 天）

- 引入 coverage baseline。
- 对 `models`、`workflow`、`provider_catalog` 开启类型检查。
- 给关键 dict diagnostics 加 Pydantic TypeAdapter 或 dataclass coercion。

### Phase 5：用户可见能力（按业务优先级）

- Markdown resource-first / section read。
- `batch_fetch`。
- 新 provider。
- Gemini CLI installer。

---

## 10. 风险提示

- 不建议先大规模改 provider 文件结构再修 HTTP cache key；后者是跨凭据正确性问题，优先级更高。
- 不建议把 `batch_check(mode="article")` 直接包装成完整多篇抓取产品接口；它的返回 shape 是轻量检查，不适合承载全文。
- 不建议一次性删除所有 compatibility layer；先加 deprecation 和架构测试，再逐步收口。
- 不建议只拆文件不改契约；真正降低复杂度的是统一 `RuntimeContext`、typed provider result、batch runner 和 asset download result。
