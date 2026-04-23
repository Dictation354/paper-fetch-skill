# Paper Fetch Skill 当前架构与业务流程

Date: 2026-04-16

## 状态说明

当前分支应视为这套架构的已落地基线。

- 代码主体位于 `src/paper_fetch/`
- `paper-fetch` 是稳定 CLI 入口
- `paper-fetch-mcp` 是稳定 stdio MCP server 入口
- `skills/paper-fetch-skill/` 是静态 thin skill bundle

公共变更历史统一记在 `CHANGELOG.md`。这份文档只描述当前系统如何工作、层次如何分工，以及后续扩展时应遵守的边界。

## Decision

这个仓库的最佳形态仍然是：

```text
可复用核心库 + CLI + MCP adapter + thin skill
```

原因很直接：

- 核心价值在于论文抓取与转换逻辑，而不是某一种 agent transport
- CLI 仍然是最直接的人工调试和 smoke 入口
- MCP 很适合作为结构化工具层，但不应该持有业务逻辑
- skill 应只负责引导 agent 使用工具，而不是承载运行时实现

## 这份文档解决什么，不解决什么

这份文档解决：

- 当前系统有哪些层
- 从输入到输出的端到端业务流程
- 关键数据契约各自扮演什么角色
- 哪些例外会影响调用方理解结果
- 新增能力时应该改哪一层

这份文档不解决：

- 每个 provider 的全部配置变量
- FlareSolverr 的操作细节
- 所有历史设计演进过程

## 当前系统分层

### 1. CLI 层

入口：`src/paper_fetch/cli.py`

职责：

- 解析命令行参数
- 组装 `FetchStrategy` 与 `RenderOptions`
- 调用 service 层
- 控制 stdout / stderr / 输出文件 / 退出码

不负责：

- provider 选择
- 正文抓取策略
- MCP 序列化

### 2. MCP 层

入口：`src/paper_fetch/mcp/server.py`、`src/paper_fetch/mcp/tools.py`

职责：

- 暴露 MCP tools、prompts 与 resources
- 校验工具参数
- 把 service 结果序列化成 JSON-safe payload
- 管理 cache resources、progress、structured log、cancellation

不负责：

- provider 路由决策
- 正文抓取瀑布
- Markdown 转换细节

### 3. Skill 层

入口：`skills/paper-fetch-skill/`

职责：

- 告诉 agent 什么时候调用哪些 MCP 工具
- 提供薄说明和引用文档

不负责：

- 安装依赖
- 实际抓取逻辑
- provider 配置

### 4. Service Facade 层

入口：`src/paper_fetch/service.py`

当前 `service.py` 只保留公共入口与兼容导出：

- 暴露 `FetchStrategy`、`PaperFetchFailure`
- 暴露 `resolve_paper()`、`probe_has_fulltext()`、`fetch_paper()`
- 兼容测试与外层调用方需要的 helper re-export

不再负责：

- provider route 细节判断
- `raw_payload.metadata[...]` 这种 magic key 协议
- 通用 HTML 提取细节

### 5. Workflow 编排层

入口：`src/paper_fetch/workflow/`

这是新的业务编排主脑，明确拆成 5 个子职责：

- `resolution`
  - 负责 resolve、歧义处理、DOI 归一化
- `metadata`
  - 负责 Crossref / publisher metadata merge
- `routing`
  - 负责 provider 候选、probe、fallback eligibility
- `fulltext`
  - 负责 provider 主链与 metadata-only fallback
- `rendering`
  - 负责 `FetchEnvelope`、`source_trail` 派生、最终结果组装

### 6. Extraction 层

入口：`src/paper_fetch/extraction/html/`

职责：

- 暴露通用 HTML 解析与 metadata 提取接口
- 暴露 provider 可复用的 shared extraction helpers
- 为 resolve 层提供纯 extraction 依赖边界

关键约束：

- `resolve/query.py` 不再 import `providers.*`
- HTML parsing / markdown extraction 不应再通过 provider 模块向上泄漏

### 7. Provider 层

入口：`src/paper_fetch/providers/`

职责：

- 各 provider 的 metadata / fulltext / asset 下载适配
- provider 自身格式到 `ArticleModel` 的转换
- provider 本地可用性诊断
- 返回 typed provider result，而不是依赖无类型 metadata 口袋回传内部状态

当前固定契约包括：

- `ProviderContent`
- `ProviderArtifacts`
- `ProviderFetchResult`

### 8. Transport / Cache 层

入口：`src/paper_fetch/http.py`

职责：

- HTTP 请求
- 连接复用
- 进程内短 TTL GET 缓存
- 响应体大小限制
- 有限短重试
- 协作式取消检查

## 端到端业务流程

统一主线如下：

```text
service facade
-> workflow.resolution
-> workflow.routing
-> workflow.metadata
-> workflow.fulltext
-> workflow.rendering
-> CLI / MCP / cache
```

### 1. resolve

`resolve_paper()` 负责把输入标准化成 `ResolvedQuery`。

支持三类输入：

- DOI
- URL
- 标题

它会产出这些关键信息：

- `query_kind`
- `doi`
- `landing_url`
- `provider_hint`
- `candidates`
- `title`

如果标题查询候选不够确定，系统会保留 `candidates`，并由上层返回 `ambiguous`，而不是猜测性继续抓取。

### 2. routing signal

路由优先级固定是：

```text
domain > publisher > DOI fallback
```

信号来源包括：

- URL 域名
- Crossref `landing_page_url`
- Crossref `publisher`
- DOI 前缀

`provider_hint` 表示最优提示，而不是最终来源承诺。

### 3. metadata merge

workflow 会尽可能拿到两类元数据：

- Crossref metadata
- publisher metadata

其中：

- `elsevier` 仍会参与 publisher metadata probe
- `springer`、`wiley`、`science`、`pnas` 不再做 publisher metadata probe

然后执行 primary / secondary merge，得到后续正文抓取所需的统一 metadata 视图。

这一步的结果同时决定：

- 更准确的 `landing_page_url`
- 更稳定的 provider 选择
- metadata-only 结果的最终内容

### 4. provider fulltext

如果选中了 provider，workflow.fulltext 会先尝试 provider 主路径。

典型行为：

- `elsevier`
  - 继续走 `官方 XML/API -> 官方 API PDF fallback`
- `springer`
  - 走 provider 自管 `direct HTML -> direct HTTP PDF`
- `wiley`
  - 走 provider 自管浏览器工作流 `FlareSolverr HTML -> Wiley TDM API PDF -> seeded-browser publisher PDF/ePDF`
- `science` / `pnas`
  - 与 `wiley` 共用浏览器工作流基座
  - 当前只剩 provider-owned 单栈；不再保留额外的 Science-only live harness 或第二套 browser-PDF 实现

如果正文足够可用，流程在这里结束。

### 5. metadata-only fallback

如果命中了 `elsevier`、`springer`、`wiley`、`science`、`pnas` 五家 provider 之一：

- workflow.fulltext 只执行该 provider 自己管理的 HTML/PDF waterfall
- provider 返回 `None` 后直接进入 metadata-only fallback

如果没有命中这五家 provider：

- 系统仍允许 DOI / Crossref metadata 解析
- 不再尝试任何通用 HTML 正文提取
- `strategy.allow_metadata_only_fallback=true` 时返回 metadata-only 结果
- 否则抛 `PaperFetchFailure`

如果正文仍不可得，并且 `strategy.allow_metadata_only_fallback=true`：

- service 返回 metadata-only 文章
- `has_fulltext=false`
- `warnings` 中明确提示已降级
- `source_trail` 中带 `fallback:metadata_only`

如果关闭这个开关，则抛 `PaperFetchFailure`。

### 7. render / envelope / cache / MCP 暴露

拿到最终 `ArticleModel` 后，workflow.rendering 会构造 `FetchEnvelope`。

当前对外结果新增：

- `trace: list[TraceEvent]`
- `source_trail`
  - 作为兼容字段保留，但由 `trace` 统一派生
- `warnings`
  - 只在最终结果层聚合，不再由 service/provider/CLI 多层共享可变列表

随后：

- CLI 决定是否写文件、是否改写相对资源链接
- MCP 决定是否写 cache sidecar、是否暴露 resources、是否附带 inline images

## 数据契约与角色边界

### `ResolvedQuery`

作用：

- 表达“输入已经被解析成什么论文候选”
- 为后续 routing 与 metadata 拉取提供标准化入口

不作用于：

- 最终输出格式
- 正文抓取成功与否

### `FetchStrategy`

作用：

- 表达“怎么抓”

当前最重要的字段：

- `allow_metadata_only_fallback`
- `preferred_providers`
- `asset_profile`

它不决定返回哪些 payload；那是 `modes` 的职责。

### `FetchEnvelope`

作用：

- 固定返回形状的公开抓取结果

它始终承载：

- `doi`
- `source`
- `has_fulltext`
- `warnings`
- `source_trail`
- `token_estimate`
- `token_estimate_breakdown`

按 `modes` 决定是否附带：

- `article`
- `markdown`
- `metadata`

### `provider_status`

作用：

- 在真正抓取前报告本地环境是否就绪

边界：

- 只检查本地条件
- 不主动打远端 publisher 可用性探测

### `has_fulltext`

这里要区分两个层面：

1. `fetch_paper().has_fulltext`
   - 完整抓取瀑布之后的最终 verdict
2. `has_fulltext()`
   - MCP 暴露的廉价 probe
   - 只使用更便宜、更弱的信号

这两个值不要求逐案完全一致。

## 关键例外与调用方容易误解的点

### `elsevier` / `springer` / `wiley` / `science` / `pnas` 不走通用 HTML fallback

这些 provider 的 HTML 逻辑由 provider 内部管理，因此：

- 通用 HTML fallback 开关不会关闭它们自己的主路径
- `elsevier` 成功时公开为 `elsevier_xml` 或 `elsevier_pdf`
- `springer` 成功时公开为 `springer_html`
- `wiley` 成功时公开为 `wiley_browser`
- `science` / `pnas` 仍然公开为 `science` / `pnas`
- 更细的成功细节要看 `source_trail`

### `crossref` 既可能是 source，也可能只是 signal

- 作为 signal 时，用来路由，不代表最终结果来自 Crossref
- 作为 source 时，才会对外表现成 `crossref_meta` 或 metadata-only 路径

### `warnings` 与 `source_trail` 都是契约的一部分

- `warnings` 用于告诉调用方发生了什么降级或限制
- `source_trail` 用于告诉维护者和高级调用方每一步是怎么走的

如果只看正文内容而忽略它们，会误读结果质量。

## 输出与可观测性

### `warnings`

常见内容包括：

- metadata-only 降级
- HTML / provider fallback 提示
- 资产部分下载失败
- token 截断

### `source_trail`

常见轨迹包括：

- `resolve:*`
- `route:*`
- `metadata:*`
- `fulltext:*`
- `fallback:*`
- `download:*`

### `token_estimate_breakdown`

当前拆成三段：

- `abstract`
- `body`
- `refs`

它帮助 host 决定：

- 要不要截断
- 哪一段最占预算
- 是否要改成 metadata-only / summary-first 策略

### MCP cache resources

MCP 层会把缓存暴露成 resources：

- 默认共享缓存索引
- 默认共享缓存条目
- 显式 `download_dir` 时的 scoped cache resources

这让 host 不需要重复抓取相同论文。

## 扩展点：新增能力时应改哪一层

### 新增 provider

应该主要改：

- `src/paper_fetch/providers/`
- `src/paper_fetch/providers/registry.py`
- 必要时更新 `publisher_identity.py`

不应该把 provider 逻辑塞进 CLI 或 MCP 层。

### 新增 MCP surface

应该主要改：

- `src/paper_fetch/mcp/schemas.py`
- `src/paper_fetch/mcp/tools.py`
- `src/paper_fetch/mcp/server.py`

如果需要真正的新抓取逻辑，应先落到 service 层。

### 新增渲染能力

如果是正文渲染或资产展示能力，应优先改：

- `src/paper_fetch/models.py`
- provider 到 `ArticleModel` 的转换逻辑

而不是让 CLI 或 MCP 自己拼装业务结果。

## 相关文档

- [`../../README.md`](../../README.md)
- [`../providers.md`](../providers.md)
- [`../deployment.md`](../deployment.md)
- [`probe-semantics.md`](probe-semantics.md)
