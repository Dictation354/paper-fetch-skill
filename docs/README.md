# 文档总览

这份文档解决：

- `docs/` 目录怎么看
- 不同角色应该先读哪几篇
- 项目里的关键术语分别是什么意思

这份文档不解决：

- 具体安装命令和环境变量细节
- provider 差异与限速策略
- 架构实现细节

项目首页见 [`../README.md`](../README.md)。

## 推荐阅读路径

### 1. 快速使用者

如果你只想知道“这个项目做什么，怎么马上试一下”，按这个顺序看：

1. [`../README.md`](../README.md)
2. [`deployment.md`](deployment.md)

### 2. 配置 / 运维者

如果你要准备 API key、下载目录、FlareSolverr 或排障，按这个顺序看：

1. [`providers.md`](providers.md)
2. [`flaresolverr.md`](flaresolverr.md)
3. [`deployment.md`](deployment.md)

### 3. Agent / MCP 集成者

如果你要把它接进 Codex、Claude Code 或其他 MCP host，按这个顺序看：

1. [`../README.md`](../README.md)
2. [`deployment.md`](deployment.md)
3. [`architecture/target-architecture.md`](architecture/target-architecture.md)
4. [`architecture/probe-semantics.md`](architecture/probe-semantics.md)

### 4. 维护者

如果你要理解当前业务流程、边界和扩展点，按这个顺序看：

1. [`architecture/target-architecture.md`](architecture/target-architecture.md)
2. [`providers.md`](providers.md)
3. [`extraction-rules.md`](extraction-rules.md)
4. [`architecture/probe-semantics.md`](architecture/probe-semantics.md)

## 文档分工

- [`../README.md`](../README.md)
  - 首页。讲项目定位、核心能力、业务主线、快速开始和关键限制。
- [`providers.md`](providers.md)
  - 讲 provider 能力矩阵、路由规则、默认输出、环境变量、缓存和限速。
- [`extraction-rules.md`](extraction-rules.md)
  - 讲当前提取 / 组装 / 渲染规则、真实样本证据和对应测试，不负责运行时路由和部署说明。
  - 修改后运行 `python3 scripts/validate_extraction_rules.py` 校验 anchor、Owner、fixture、测试名、manifest 引用和未挂规则 fixture 清单。
- [`deployment.md`](deployment.md)
  - 讲安装、配置入口、MCP 注册、更新和最小验证。
- [`flaresolverr.md`](flaresolverr.md)
  - 讲 Wiley / Science / PNAS 的 repo-local 浏览器工作流。
- [`architecture/target-architecture.md`](architecture/target-architecture.md)
  - 讲当前系统分层、端到端业务流程、数据契约和扩展点。
- [`architecture/probe-semantics.md`](architecture/probe-semantics.md)
  - 讲 `has_fulltext()` 的 probe 语义与边界。

## 术语表

### `provider_hint`

- `resolve_paper()` 给出的最佳 provider 提示。
- 来自 `domain > publisher > DOI fallback` 的综合信号。
- 不是“最终一定成功的 provider”。

### `preferred_providers`

- `FetchStrategy` 中的 provider allow-list。
- 限制五家 provider fulltext 主链的候选范围。
- 不阻止系统内部用 `crossref` 做路由判断或 metadata-only fallback。
- 显式设为 `["crossref"]` 时会跳过 publisher fulltext probe，收敛成 Crossref-only / metadata-only。

### `source`

- 公开给调用方的粗粒度结果来源。
- 例如 `elsevier_xml`、`elsevier_pdf`、`springer_html`、`wiley_browser`、`science`、`pnas`、`crossref_meta`、`metadata_only`。

### `source_trail`

- 更细粒度的执行轨迹。
- 用于表达 route signal、probe、fallback、下载和降级细节。

### `modes`

- `fetch_paper()` 输出轴。
- 当前支持 `article`、`markdown`、`metadata`。
- 决定“返回什么”，不决定“如何抓”。

### `strategy`

- `fetch_paper()` 的抓取策略轴。
- 负责控制 `allow_metadata_only_fallback`、`preferred_providers`、`asset_profile` 等行为。
- MCP 的 `strategy.inline_image_budget` 只控制工具响应里附带的 inline `ImageContent` 上限，不参与 provider 抓取决策。

### `asset_profile`

- 资产下载层级。
- `none`：不下载资产。
- `body`：正文 figure、正文表格原图和可识别的公式图片。
- `all`：当前 provider 可识别的全部相关资产。

### `render_state`

- `article.assets[*]` 上的资产渲染状态。
- `inline` 表示资产已经在正文中消费，文末不会重复追加。
- `appendix` 表示未被正文消费，可进入 `Figures` / `Tables` 或 `Additional Figures` / `Additional Tables`。
- `suppressed` 表示资产被显式抑制，不进入用户可见附录。

### `download_tier`

- `article.assets[*]` 上的资产下载层级诊断。
- 常见值包括 `full_size`、`preview`。旧的通用 HTTP-first 路径仍可能保留 `playwright_canvas_fallback` 诊断，但 `wiley` / `science` / `pnas` 的 HTML 资产主链路不再输出这个 tier。
- `preview` 不是天然错误；当宽高满足阈值且 `source_trail` 有 preview accepted 轨迹时，是可接受降级。
- `wiley` / `science` / `pnas` 的 challenge 恢复链路只接受 FlareSolverr `solution.imagePayload`；不会再把图片文档 screenshot 裁剪成正文图片资产。
- live review 中，只有公式图片发生 preview fallback 时不自动归为 `asset_download_failure`；figure/table preview fallback 仍需要 accepted 轨迹或其它证据才能降噪。

### `semantic_losses`

- `ArticleModel.quality` 下的语义降级计数。
- `table_layout_degraded_count` 表示 Markdown 版式降级，但单元格语义仍保留。
- `table_semantic_loss_count` 才表示表格语义内容发生丢失。

### `asset_failures`

- `ArticleModel.quality.asset_failures` 与顶层 `quality.asset_failures` 下的失败资产诊断。
- 会保留 `status`、`content_type`、`title_snippet`、`body_snippet`、`reason`，以及 asset-level challenge recovery 的 `recovery_attempts`。

### `max_tokens`

- 渲染预算。
- `full_text` 表示尽量保留完整正文。
- 数值模式表示进入硬上限截断。

### `download_dir`

- 抓取时的落盘目录。
- 可覆盖默认下载目录，也会影响 MCP scoped cache resources。
- Provider PDF/binary、Springer `original.html` 和 asset 诊断由 `RuntimeContext` / `ArtifactStore` 应用；MCP 内部通过 `RuntimeContext` 调用 service，fetch-envelope sidecar 和 cache index 由 `FetchCache` 管理。
- Python service API 不再接收 `download_dir` / `env` / `transport` / `clients` keyword；外层调用方需要先构造 `RuntimeContext(...)`，再传 `context=`。
- 未显式设置时，CLI / MCP 优先使用用户数据目录下的 `paper-fetch/downloads`；CLI 创建失败才退回 `live-downloads`。
- `download_dir` 派生的 HTTP textual disk cache 默认按 `4096` 条、`512 MiB`、`30` 天清理；详见 provider 文档中的 HTTP 缓存环境变量。

### Live review timings

- golden criteria live review 的 `stage_timings` 包含 `fetch_seconds`、`materialize_seconds`、`total_seconds`、`resolve_seconds`、`metadata_seconds`、`fulltext_seconds`、`asset_seconds`、`formula_seconds`、`render_seconds`。
- 每个 sample 的 `http_cache_stats` 表示该 sample 执行前后差值；最终汇总日志仍可查看 `HttpTransport.cache_stats_snapshot()` 的累计快照。

## 一句话阅读建议

- 想快速上手：先看首页。
- 想改配置：看 provider 文档。
- 想部署到 agent：看 deployment。
- 想改实现：看 architecture。
