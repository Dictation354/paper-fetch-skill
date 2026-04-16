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
3. [`architecture/probe-semantics.md`](architecture/probe-semantics.md)

## 文档分工

- [`../README.md`](../README.md)
  - 首页。讲项目定位、核心能力、业务主线、快速开始和关键限制。
- [`providers.md`](providers.md)
  - 讲 provider 能力矩阵、路由规则、默认输出、环境变量、缓存和限速。
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
- 限制最终允许使用的 provider-owned fulltext 或 generic HTML 路径。
- 不阻止系统内部用 `crossref` 做路由判断。

### `source`

- 公开给调用方的粗粒度结果来源。
- 例如 `elsevier_xml`、`springer_html`、`wiley_browser`、`science`、`pnas`、`html_fallback`、`crossref_meta`、`metadata_only`。

### `source_trail`

- 更细粒度的执行轨迹。
- 用于表达 route signal、probe、fallback、下载和降级细节。

### `modes`

- `fetch_paper()` 输出轴。
- 当前支持 `article`、`markdown`、`metadata`。
- 决定“返回什么”，不决定“如何抓”。

### `strategy`

- `fetch_paper()` 的抓取策略轴。
- 负责控制 `allow_html_fallback`、`allow_metadata_only_fallback`、`preferred_providers`、`asset_profile` 等行为。

### `asset_profile`

- 资产下载层级。
- `none`：不下载资产。
- `body`：正文 figure 和正文表格原图。
- `all`：当前 provider 可识别的全部相关资产。

### `max_tokens`

- 渲染预算。
- `full_text` 表示尽量保留完整正文。
- 数值模式表示进入硬上限截断。

### `download_dir`

- 抓取时的落盘目录。
- 可覆盖默认下载目录，也会影响 MCP scoped cache resources。

## 一句话阅读建议

- 想快速上手：先看首页。
- 想改配置：看 provider 文档。
- 想部署到 agent：看 deployment。
- 想改实现：看 architecture。
