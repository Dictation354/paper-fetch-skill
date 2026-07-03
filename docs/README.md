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
2. [`cli.md`](cli.md)
3. [`deployment.md`](deployment.md)

### 2. 配置 / 运维者

如果你要准备 API key、下载目录、CloakBrowser 或排障，按这个顺序看：

1. [`cli.md`](cli.md)
2. [`providers.md`](providers.md)
3. [`browser-runtime.md`](browser-runtime.md)
4. [`deployment.md`](deployment.md)

### 3. Agent / MCP 集成者

如果你要把它接进 Codex、Claude Code 或其他 MCP host，按这个顺序看：

1. [`../README.md`](../README.md)
2. [`deployment.md`](deployment.md)
3. [`architecture/overview.md`](architecture/overview.md)
4. [`architecture/probe-semantics.md`](architecture/probe-semantics.md)

### 4. 维护者

如果你要理解当前业务流程、边界和扩展点，按这个顺序看：

1. [`architecture/overview.md`](architecture/overview.md)
2. [`providers.md`](providers.md)
3. [`provider-development.md`](provider-development.md)
4. [`extraction-rules.md`](extraction-rules.md)
5. [`architecture/probe-semantics.md`](architecture/probe-semantics.md)
6. [`onboarding/README.md`](../onboarding/README.md)

## 文档分工

- [`../README.md`](../README.md)
  - 首页。讲项目动机、核心能力、边界和部署入口。
- [`../CHANGELOG.md`](../CHANGELOG.md)
  - 英文公共变更历史。记录对用户可见的新能力、限制和迁移提示。
- [`../CHANGELOG_CN.md`](../CHANGELOG_CN.md)
  - 中文公共变更历史对照版。
- [`../AGENTS.md`](../AGENTS.md)
  - 贡献者与 agent 协作约定。描述本仓库默认语言、测试和开发边界。
- [`cli.md`](cli.md)
  - 讲 `paper-fetch` CLI 的主输出、artifact、资产下载、常见参数组合和错误输出。
- [`providers.md`](providers.md)
  - 讲 provider 能力矩阵、路由规则、默认输出、环境变量、缓存和限速。
- [`browser-runtime.md`](browser-runtime.md)
  - 讲 browser workflow 使用的 CDP / `cloakbrowser` 运行时边界，并指向 provider、部署和架构文档。
- [`provider-development.md`](provider-development.md)
  - 讲新增出版社 provider 的标准开发流程、typed contract、waterfall、资产语义、测试和文档验收标准。
- [`onboarding/README.md`](../onboarding/README.md)
  - 普通用户入口和 authority index。AI/coordinator provider 行为事实源是 [`coordinator-spec.md`](../onboarding/coordinator-spec.md)、[`provider-manifest.md`](../onboarding/provider-manifest.md)、[`provider-manifest.schema.json`](../onboarding/provider-manifest.schema.json)、[`agent-task-brief.md`](../onboarding/agent-task-brief.md)、[`hard-constraints.md`](../onboarding/hard-constraints.md)、[`acceptance.md`](../onboarding/acceptance.md) 和 run records，不从 README 推断。
- [`extraction-rules.md`](extraction-rules.md)
  - 讲当前提取 / 组装 / 渲染规则、真实样本证据和对应测试，不负责运行时路由和部署说明。
  - 修改后运行 `python3 scripts/validate_extraction_rules.py` 校验 anchor、Owner、fixture、测试名、manifest 引用和未挂规则 fixture 清单。
- [`deployment.md`](deployment.md)
  - 讲安装、配置入口、MCP 注册、更新和最小验证。
  - 讲 Wiley / Science / PNAS / Annual Reviews / Royal Society Publishing / ACS / IOP / AIP / MDPI 的 repo-local 浏览器工作流、AMS direct HTTP HTML/PDF 路径、本地 `scripts/dev-preflight.sh` 门禁和 CI 测试耗时信号。
- [`architecture/overview.md`](architecture/overview.md)
  - 讲当前系统分层、端到端业务流程、数据契约和扩展点。
- [`architecture/probe-semantics.md`](architecture/probe-semantics.md)
  - 讲 `has_fulltext()` 的 probe 语义与边界。
- [`architecture/fixture-size-baseline.md`](architecture/fixture-size-baseline.md)
  - 记录 tracked fixture 体积治理基线，并区分本地 ignored 杂物和需要评估的 fixture 体积问题。

## 术语表

### `provider_hint`

- `resolve_paper()` 给出的最佳 provider 提示。
- 来自 `domain > publisher > DOI fallback` 的综合信号。
- 不是“最终一定成功的 provider”。

### `preferred_providers`

- `FetchStrategy` 中的 provider allow-list。
- 限制 provider fulltext 主链的候选范围。
- 不阻止系统内部用 `crossref` 做路由判断或 metadata-only fallback。
- 显式设为 `["crossref"]` 时会跳过 publisher fulltext probe，收敛成 Crossref-only / metadata-only。

### `source`

- 公开给调用方的粗粒度结果来源。
- 公开枚举与映射详见 [`providers.md` § 公开输出里最重要的字段](providers.md#public-output-fields)。
- `metadata_only` 只在 `FetchEnvelope.source` 出现，不是 `ArticleModel.source` 的合法值；它由 `workflow/rendering.py` 在渲染阶段根据 fallback marker 写入。

### `source_trail`

- 更细粒度的执行轨迹。
- 用于表达 route signal、probe、fallback、下载和降级细节。

### `modes`

- `fetch_paper()` 输出轴。
- 当前支持 `article`、`markdown`、`metadata`。
- 决定“返回什么”，不决定“如何抓”。
- MCP 默认 `modes=["article", "markdown"]`，因此默认会返回结构化 article 和 AI 可读 Markdown。

### `strategy`

- `fetch_paper()` 的抓取策略轴。
- 负责控制 `allow_metadata_only_fallback`、`preferred_providers`、`asset_profile` 等行为。
- MCP 的 `strategy.inline_image_budget` 只控制工具响应里附带的 inline `ImageContent` 上限，不参与 provider 抓取决策。

### `asset_profile`

- 资产下载层级。
- `none`：不下载本地资产；不主动清除 Markdown 中已有或 provider 可解析出的远程图片链接。
- `body`：正文 figure、正文表格原图和可识别的公式图片。
- `all`：当前 provider 可识别的全部相关资产。
- CLI 默认是 `body`；Python API / MCP 未显式指定时仍按 provider 默认策略解析。

### `render_state`

- `article.assets[*]` 上的资产渲染状态。
- `inline` 表示资产已经在正文中消费，文末不会重复追加。
- `appendix` 表示未被正文消费，可进入 `Figures` / `Tables` 或 `Additional Figures` / `Additional Tables`。
- `suppressed` 表示资产被显式抑制，不进入用户可见附录。

### `download_tier`

- `article.assets[*]` 上的资产下载层级诊断。
- 常见值包括 `full_size`、`preview`。非 browser-workflow 的 HTTP-first 路径可能保留 `playwright_canvas_fallback` 诊断；`wiley` / `science` / `pnas` / `annualreviews` / `acs` / `iop` / `aip` / `mdpi` 的 browser-backed HTML 资产主链路只输出 `full_size` 或 `preview`。AMS direct HTTP HTML 正文资产也使用 browser-equivalent headers，并只输出 `full_size` 或 `preview`。
- `preview` 不是天然错误；当宽高满足阈值且 `source_trail` 有 preview accepted 轨迹时，是可接受降级。
- preview 降级仍必须导出自包含 Markdown；如果正文图片链接能映射到已下载本地资产，最终 `.md` 不应残留远端图片 URL。
- `wiley` / `science` / `pnas` / `annualreviews` / `acs` / `iop` / `aip` / `mdpi` 的 challenge 恢复链路会先复用预热正文页中目标 `<img>` 的 canvas 导出；目标图存在但尚未加载时，会先在同一正文页执行带凭据的 `fetch()` 拉取原图字节，再退回图片 URL 直连候选；只接受能识别为图片的 CDP browser image payload，包括浏览器导出的 PNG 和原始 SVG；图片文档 screenshot 和 challenge HTML 不能作为正文图片资产。AMS direct HTTP HTML 成功时不启动 CDP browser，但正文图片请求必须继承浏览器 UA/Referer。
- live review 中，只有公式图片发生 preview fallback 时不自动归为 `asset_download_failure`；figure/table preview fallback 仍需要 accepted 轨迹或其它证据才能降噪。资产下载 warning、`asset_failures` 轨迹或 `quality.asset_failures` 会归为 `asset_download_failure`。

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
- `RuntimeContext` / `ArtifactStore` 通过 `artifact_mode` 控制 provider payload、原始 HTML、Markdown 保存、资产诊断、HTTP textual cache 与 provider structured sidecar 的落盘范围；CLI/MCP fetch 默认 `markdown-assets`，Python API/runtime 未显式设置时默认是 `all`。
- CLI/MCP fetch 入口通过 `FetchPipeline` 创建运行时并调用 service，MCP 的 fetch-envelope sidecar 和 cache index 仍由 `FetchCache` 管理语义，但原子 JSON 写入复用 `ArtifactStore`。
- Python service API 接收显式 `context=`；外层调用方需要先构造 `RuntimeContext(...)`，再传给 service / pipeline。
- 未显式设置时，CLI / MCP 优先使用用户数据目录下的 `paper-fetch/downloads`；CLI 创建失败才退回 `live-downloads`。
- `download_dir` 派生的 HTTP textual disk cache 只在 artifact mode 为 `all` 时启用，默认按 `4096` 条、`512 MiB`、`30` 天清理；详见 provider 文档中的 HTTP 缓存环境变量。

### MCP 下载和 Markdown 保存

`artifact_mode`、`prefer_cache`、`no_download`、`save_markdown`、`markdown_output_dir` 和 `markdown_filename` 的完整语义见 [`providers.md`](providers.md#mcp-download-and-markdown-save)。

### Live review timings

- golden criteria live review 的 `stage_timings` 包含 `fetch_seconds`、`materialize_seconds`、`total_seconds`、`resolve_seconds`、`metadata_seconds`、`fulltext_seconds`、`asset_seconds`、`formula_seconds`、`render_seconds`。
- 每个 sample 的 `http_cache_stats` 表示该 sample 执行前后差值；最终汇总日志仍可查看 `HttpTransport.cache_stats_snapshot()` 的累计快照。
- live runner supported provider 从 runtime `official_provider_names()` 派生，当前包含 `elsevier`、`springer`、`wiley`、`science`、`pnas`、`ieee`、`arxiv`、`copernicus`、`ams`、`mdpi`、`royalsocietypublishing`、`annualreviews`、`plos`、`oxfordacademic`、`acs`、`iop`、`aip`、`frontiers`；provider 路径和资产语义见 [`providers.md`](providers.md)。

## 一句话阅读建议

- 想快速上手：先看首页。
- 想用 CLI：看 [`cli.md`](cli.md)。
- 想改配置：看 provider 文档。
- 想部署到 agent：看 deployment。
- 想改实现：看 architecture。
