# Paper Fetch Skill 架构与业务流程

Date: 2026-07-29

## 状态说明

本文件描述当前分支已落地的系统架构，应视为这套架构的基线，而不是规划目标。

- 代码主体位于 `src/paper_fetch/`
- `paper-fetch` 是稳定 CLI 入口
- `paper-fetch-mcp` 是稳定 stdio MCP server 入口
- `skills/paper-fetch-skill/` 是静态 thin skill bundle

公共变更历史统一记在 `CHANGELOG.md`。这份文档只描述系统当前如何工作、层次如何分工，以及扩展时应遵守的边界；兼容边界由架构测试强制（见 §10）。

## Decision

这个仓库的最佳形态是：

```text
可复用核心库 + CLI + MCP adapter + thin skill
```

原因：

- 核心价值在论文抓取与转换逻辑，而不是某一种 agent transport
- CLI 是最直接的人工调试与 smoke 入口
- MCP 适合作结构化工具层，但不应持有业务逻辑
- skill 只引导 agent 使用工具，不承载运行时实现

## 这份文档解决什么

解决：当前有哪些层、从输入到输出的端到端流程、关键数据契约的角色、调用方容易误解的例外、新增能力时该改哪一层。

不解决：每个 provider 的全部配置变量与运行时细节（见 [`../providers.md`](../providers.md)）、历史设计演进过程（见 `CHANGELOG.md`）。

## 当前系统分层

### 1. CLI 层

入口：`src/paper_fetch/cli.py`

- 解析命令行参数，组装 `FetchStrategy` 与 `RenderOptions`
- 创建/关闭 `RuntimeContext`，通过 `FetchPipeline` 调用 service 层，并负责 CLI 输出与 Markdown 保存生命周期
- 控制 stdout / stderr / 输出文件 / 退出码

不负责 provider 选择、正文抓取策略、MCP 序列化。

### 2. MCP 层

入口：`src/paper_fetch/mcp/`（`server.py`、`fetch_tool.py`、`cache_payloads.py`、`batch.py`、`results.py`、`log_bridge.py`）

- 暴露 MCP tools 与静态 provider-catalog resource，校验工具参数
- 把 service 结果序列化成 JSON-safe payload
- 通过 `FetchCache` 管理 fetch-envelope sidecar，并由 `list_cached` / `get_cached` 查询
- 在 MCP adapter 内管理 fetch-envelope cache、Markdown 注册和 cancellation commit guard；`FetchPipeline` 只复用 service 调用
- 管理 progress、structured log、cancellation

实现边界：

- MCP runtime 基于官方 Python SDK 2.x 的 `MCPServer` 与 stdio transport，不再维护自定义 stdin reader/stream pump；server 同时服务 2025 握手协议与 2026-07-28 无状态协议，只保留静态 provider catalog resource。
- payload/tool 入口通过 `paper_fetch.mcp._deps.MCPDeps` 显式注入 runtime env、service、provider registry 与 cache index 依赖；生产默认由 `default_mcp_deps()` 装配，测试通过构造定制 deps 注入。
- 所有 MCP tool JSON payload 顶层都带 `schema_version=2`；错误 payload 保留兼容字段 `status` / `reason`，并补充 `code`、`http_status`、`error_category`、`retry_after_seconds`、`provider`、`warnings`、顶层唯一完整 `trace` 和 `source_trail` 供 host 做机器判断。v2 的 `quality` 不再复制完整 trace。
- 当前十个工具都不在 `tools/list` 发布协议级 `outputSchema`。工具结果继续通过 `CallToolResult.structured_content` 返回带 `schema_version=2` 的既有 payload；该版本化 payload 契约不等同于 MCP output schema。
- `resource://paper-fetch/provider-catalog` 由轻量 MCP catalog adapter 在读取时直接投影 runtime `ProviderSpec` 和 `SOURCE_PROVIDER_MAP`；provider/source、browser/runtime、status/preflight 与资产默认不在 server instructions、tool description 或 skill contract 中维护第二张静态表。
- `fetch_paper` 和批量工具把阻塞抓取放到有界 `ThreadPoolExecutor`，事件循环继续处理 progress / log / cancellation；批量工具保持输入顺序，遇到 rate-limit status/code/category、HTTP 429 或 retry-after 后停止对应 provider/resource lane 的新提交。
- async `fetch_paper` 用 `RuntimeContext(cancel_check=...)` 创建 cancel-aware `HttpTransport`，service/workflow 只消费 transport。

不负责 provider 路由决策、正文抓取瀑布、Markdown 转换细节。

### 3. Skill 层

入口：`skills/paper-fetch-skill/`

- 告诉 agent 什么时候调用哪些 MCP 工具，提供薄说明和渐进式引用文档
- `scripts/skill_integrity.py` 由构建器和安装器调用，对路径排序后的完整 regular-file inventory 计算稳定 aggregate SHA-256/version；offline staging/manifest 与 host 安装副本共用该语义，missing/extra/symlink/special 均 fail closed
- `agents/openai.yaml` 是仓库内 canonical 静态模板，随 bundle 一起哈希和发布，不在安装时动态生成

不负责安装依赖、抓取逻辑、provider 配置。

### 4. Service Facade 层

入口：`src/paper_fetch/service.py`

只保留公共入口与兼容导出：`FetchStrategy`、`PaperFetchFailure`、`RuntimeContext`，以及 `resolve_paper()`、`probe_has_fulltext()`、`fetch_paper()` 和测试/外层需要的 helper re-export。provider route 判断、HTML 提取、payload 写盘策略都已下沉到 workflow / provider / artifact 层。

### 5. Workflow 编排层

入口：`src/paper_fetch/workflow/`

业务编排主脑，拆成子职责：

- `resolution`：resolve、歧义处理、DOI 归一化
- `metadata`：Crossref / publisher metadata merge（底层 Crossref lookup owner 是 `paper_fetch.metadata.crossref.CrossrefLookupClient`）
- `routing`：provider 候选、probe、fallback eligibility
- `fulltext`：provider 主链与 abstract-only / metadata-only fallback，并通过 `ArtifactStore` 应用 artifact 写盘策略
- `rendering`：`FetchEnvelope`、`source_trail` 派生、最终结果组装
- `pipeline`：在调用方提供的 `RuntimeContext` 中执行 CLI/MCP 真正共享的 service 调用

#### 增量 batch runner 与 provider lane

`paper_fetch.workflow.batch_runner` 是面向 CLI/MCP 的共享批量调度状态机，新增批量入口必须复用它。单项 worker 仍按 resolution → metadata/routing → fulltext → rendering 的阶段顺序执行；runner 只在同一批的项之间提供受控并发，不把单篇抓取的阶段拆散或乱序。现有 MCP batch 和 CLI batch 都复用这一 runner；执行面 adapter 只负责把共享终态转换为各自的 response 或 manifest record。

- 全局 worker 与每个 provider/resource lane 的并发上限都限制在公开范围 `1..8`。runner 最多只维持全局上限数量的 in-flight future，并在每次完成后增量扫描未提交输入；某个 lane 暂时占满时，其他可运行 lane 不会被队首阻塞。
- lane key 由调用方在调度前提供。worker 通过结构化 failure/result classifier 报告既有 `rate_limited` reason code 和可选 `retry_after_seconds`；runner 不解析 warning 文案。观察到限流后，该 lane 在本次 run 内不再提交新项，并用可注入的单调 clock 记录 `limited_at`、解析后的 cooldown 与 `cooldown_until`；其他 lane 继续运行。本模块不跨 run 学习或维护全局限流服务。
- `BatchRunResult.results` 始终按输入 index 排列且每项只有一个终态；真实完成、worker 异常、协作式取消以及从未提交的项分别表示为 `succeeded`、`failed/rate_limited`、`cancelled` 和 `not_scheduled`。`completion_events` 与 completion/progress callback 独立保留终态被观察到的顺序，流式消费者不能把它误当输入顺序。
- stop predicate 或 cancel event 只阻止新的增量提交；已在途 worker 依靠 `RuntimeContext.cancel_check` 协作退出。取消超过宽限期且仍有 pending worker 时，runner 只调用一次显式 escalation callback 关闭共享 browser manager，随后仍等待 worker 收敛。worker 已观察到的异常和取消、以及因 stop/cancel/lane cooldown 未调度的输入，都会生成结构化终态，避免批次尾部静默丢失。
- 每个终态（包括 `not_scheduled`）依次触发一次 completion callback 和一次 progress callback；两者都可同步或异步。callback 是观察者：异常写入 `BatchRunResult.callback_failures`，不覆盖 item 终态，也不隐式改变停止策略；需要把 callback 失败升级为 run 失败的 adapter 必须显式检查该字段。callback 内设置 cancel event 会在下一次增量提交前生效。

现有 MCP `batch_resolve` / `batch_check` / `batch_fetch` 与 CLI batch 都通过这个 runner 调度。前两个 probe/resolve 工具保持既有兼容调度；`batch_fetch` 在提交前只调用 catalog-backed URL/DOI 身份 helper 推断 provider lane，一个 lane 限流后把该 lane 的后续输入终态化为未调度，其他 lane 继续。它的 `results` 按原 1-based input index 返回，`completion_order` 单独投影完成顺序，progress 使用完整终态计数。

`RuntimeContext` 是 service/workflow 的显式运行时依赖容器，持有 `env`、`transport`、`clients`、`download_dir`、`cancel_check`、`artifact_store`，以及单次 fetch 生命周期内的 `parse_cache`、`session_cache`。Browser provider 只依赖 `paper_fetch.providers.browser_runtime` facade；生产 backend 是 Camoufox，storage/profile 路径由 `browser_runtime.paths` 统一解析。同一 owning thread 在一个 `RuntimeContext` 内复用 Camoufox process，每项操作创建隔离 context/page，batch/进程退出时统一清理。公开 `service` helper 可接受 `context=None`，此时自行创建并关闭 context；pipeline/workflow 内部路径要求调用方显式传递 context。CLI/MCP adapter 按各自目录、artifact 和 cancellation 语义构造 `RuntimeContext`，再交给 `paper_fetch.workflow.pipeline.FetchPipeline`。

#### 统一抓取验收模型

`paper_fetch.workflow.acceptance` 是 CLI、MCP、cache 和 manifest 唯一可复用的抓取验收语义。`evaluate_fetch_acceptance()` 是纯函数：它只消费 `FetchEnvelope` / 结构化失败 code、请求的 `asset_profile`、请求输出集合和可选的 `AssetAcceptanceSummary`，不联网、不访问或写入文件，也不重新运行 provider 质量判断。文件存在性、hash、MIME 等 I/O 事实由外层 adapter 收集后再以结构化事实传入；验收层不解析 warning 文案。

`FetchAcceptanceReport` 固定包含七个分面：

| 分面 | 事实与边界 |
| --- | --- |
| `overall` | 稳定枚举 `complete`、`degraded`、`limited`、`failed`、`action_required`。 |
| `identity` | 归一化 DOI、期望 DOI、标题、候选数和 `resolved/ambiguous/mismatch/unavailable`；DOI 归一化复用 `publisher_identity.normalize_doi()`。 |
| `fetch` | `ok` 只表示调用已完成；歧义、无访问权限或配置缺失是 `action_required`，其他未产出 envelope 的错误是 `failed`。 |
| `content` | 只使用 `fulltext`、`abstract_only`、`metadata_only`、`unavailable`，同时保留 `has_fulltext`、`has_abstract`、confidence 和 flags。表格布局降级、表格语义损失、公式 fallback/missing 保持独立计数。 |
| `asset` | 显式记录 profile、`requested`、本地/远程、full-size、preview、failure、placeholder suspected 和 not-archived。v2 的增量字段另记录正文逻辑资产的 discovered/attempted/local/full-size/preview/failed/not-archived/remote-only 计数，以及两个严格约束和 satisfaction。`asset_profile=none` 必须得到 `requested=false/status=not_requested`，未完成 fetch 时已请求资产是 `unavailable`；仍保留的远程链接由 `remote_link_count`、`remote_only_count` 和 `remote_links_preserved` 单独表达。 |
| `output` | 只验收调用方声明请求的 article/Markdown/metadata；未请求是 `not_requested`，请求但缺失才是 `partial/missing`。 |
| `provenance` | 保留兼容 `source`，并校验结构化 `acquisition={provider,route,representation,transport,fallback_used}` 是否与 provider catalog、source owner 和 trace fallback 事实一致；同时从 trace、质量与 asset failure 派生 fallback/warning/failure codes。原 warning 只计数，不按消息子串分类。 |

常见状态组合是：

| 调用结果 | `fetch.status` | `content.status` | `overall` |
| --- | --- | --- | --- |
| 全文、请求输出和溯源均完整 | `ok` | `fulltext` | `complete` |
| 全文存在，但资产、表格、公式或 fallback 降级 | `ok` | `fulltext` | `degraded` |
| 只得到摘要或元数据 | `ok` | `abstract_only/metadata_only` | `limited` |
| 调用完成但请求输出缺失，或普通抓取失败 | `ok/failed` | 任意或 `unavailable` | `failed` |
| 身份歧义、DOI 不匹配、no-access 或缺配置 | `action_required` 或 `ok` | 任意 | `action_required` |

因此 transport/adapter 的旧 `status=ok`、正文事实 `has_fulltext` 和任务级 `overall` 是三个不同维度，任何调用方都不得互相替代解释。metadata-only 可以同时是 `status=ok`、`fetch.status=ok`、`has_fulltext=false`、`overall=limited`。

验收 schema 当前为 v2。每份报告都必须序列化 `schema_version=2` 和 `minimum_reader_schema_version=2`。v2 增加 `accepted_preview`、`fallback_preview`、稳定 `issue_codes`、正文资产计数与 `require_local_body_assets` / `require_full_size_body_assets`（后者隐含前者），并要求 `preview == accepted_preview + fallback_preview`。严格分母只包含需要独立归档文件的正文逻辑资产；已经以内联语义完成且没有 binary payload/remote/failure 的 table、formula 或 figure 不会被误算为缺少本地文件。两项约束默认关闭且只适用于 `body|all`；未满足时 asset/overall 降为 `degraded`，已经取得的全文仍保持 `fetch=ok`。reader 可忽略未知 additive field，但缺少版本、v1 或未来不支持的版本必须拒绝，不能猜测迁移。`FetchAcceptanceReport.model_json_schema()` / `fetch_acceptance_json_schema()` 是 JSON Schema 唯一生成入口。

`FetchEnvelope.trace` 是一次 fetch 的唯一完整 trace owner。provider/waterfall 先在局部列表累积事件，workflow 最终只写入 envelope 一次；`Quality` 仅保留去重后的 article source-trail 摘要。acceptance、manifest 与 MCP 都只投影 envelope 顶层 trace，两个不同 attempt 的同 code 会保留为两条真实事件。

#### 版本化 manifest record

`paper_fetch.manifest` 是单篇 CLI、CLI batch 和 MCP `batch_fetch` 共用的 manifest record owner。adapter 只向 `build_manifest_record()` 提交原 query、JSON-safe 请求参数、`FetchEnvelope` 或结构化 error、输出文件声明和 run/index/attempt；schema 字段、验收摘要、trace 与文件快照均由 builder 统一派生。builder 保持纯逻辑，不写输出文件。

manifest record schema 当前为 v2，`schema_version=2` 和 `minimum_reader_schema_version=2` 都是必填常量。每条记录以 `record_status` 表示 `completed/failed/aborted`，以 `error.status` 表示失败分类，以 `output_artifacts` 记录最终文件；完整度读取同一 record 内的 `acceptance.overall/content/asset`。

其余关键不变量如下：

- `index` 与 `attempt` 都从 1 开始；`run_id`、`record_id`、带时区的开始/结束时间、clock 与 UUID factory 均可注入；默认 clock 与 artifact mtime 使用 UTC。
- `request_fingerprint` 是原 query 和 JSON-safe request parameters 的 canonical JSON SHA-256；对象键顺序不会改变 fingerprint，数组顺序会保留。
- `identity`、`doi`、`source`、`fallback_codes`、`warning_codes`、`failure_codes`、`semantic_losses` 和 `asset_summary` 都直接来自 `FetchAcceptanceReport`，不会重新按 warning/message 文本分类。原 warning 文本只为兼容和人工诊断原样保留。
- `trace` 由既有 `TraceEvent` 或兼容 `source_trail` marker 转换；message 只是说明文字，不参与 fallback/warning/failure 分类。
- 每个 `output_artifacts[*]` 记录 path、kind、size、SHA-256、mtime、record completion time 和 `verified/missing/unreadable` 快照状态。stat 与 hash reader 可注入，builder 只读文件，不落盘。
- artifact facts 只表示 record 完成时观察到的状态，不证明文件现在仍存在或内容未变。

打包资源 `paper_fetch.resources.manifest/manifest-record-v2.schema.json` 是对外稳定的 Draft 2020-12 schema；测试要求它与 `generated_manifest_record_json_schema()` 同步并能验证真实 round-trip payload。v2 reader 忽略 additive unknown fields；删除字段、改变必填性/含义或收窄既有值域属于不兼容变更，必须提升 manifest schema version，不能覆盖 v2 资源或猜测迁移。缺少版本、fingerprint 或违反派生字段一致性的 record 必须拒绝。

#### 批量最终结果

CLI 的 `--batch-results` 与 MCP 的 `batch_results` 都只写一次最终 JSONL：每个输入恰好一条 schema-v2 record，并按输入 `index` 排列。写入复用 `ArtifactStore` 的同目录临时文件、flush/fsync、commit fence 与原子替换；默认拒绝覆盖，显式 `overwrite` 才允许替换。批处理不维护 run manifest、append-only journal、审计或恢复状态。

### 6. Extraction 层

入口：`src/paper_fetch/extraction/html/`

- 暴露通用 HTML 解析与 metadata 提取接口、provider 可复用的 shared extraction helpers
- 为 resolve 层提供纯 extraction 依赖边界
- 通过 `paper_fetch.extraction.html.landing.fetch_landing_html()` 统一 DOI/URL landing HTML fetch、decode、metadata extraction、final URL、status/header
- 通过 `paper_fetch.extraction.image_payloads` 统一图片 MIME 与尺寸识别
- HTML bytes 统一经 `paper_fetch.extraction.html._runtime.decode_html()` 解码：先处理 UTF-8 BOM / UTF-8，再读取 HTTP `Content-Type` charset、HTML meta charset，随后使用 `charset-normalizer` 检测，最后才 UTF-8 replacement fallback。provider、Springer/IEEE、browser workflow 和资产 HTML page 路径传递可用的 response content-type。
- 通用 HTML cleanup 先选择 `article` / `main` / `[role="main"]` 中文本量最大的内容根；无内容根时只执行 tag/selector/ORCID 级 cheap cleanup，不跑逐节点正文噪声分类。trafilatura 先尝试 cleaned HTML，raw HTML fallback 默认超过 `1_000_000` 字符时跳过并写 debug 日志，再继续 cleaned fallback parser。
- arXiv official HTML 系列集中使用 `paper_fetch.providers._arxiv_parsing.ARXIV_HTML_PARSER`，当前取 `choose_parser()`；现有 arxiv fixture 单测覆盖该取舍。必须重解析字符串片段的 AMS MathML script 例外保留在 provider DOM helper 内，并在代码旁注明原因。

<a id="extraction-stage-module-map"></a>

#### Extraction 阶段映射

`docs/extraction-rules.md` 中的受控阶段 token 与 canonical owner 的映射如下。新增提取 / 渲染规则时，优先把行为挂到这里列出的 owner；provider 层只做 publisher adapter，不新增平行 helper 入口。

| 阶段 token | Canonical module / owner | 规则范围 |
| --- | --- | --- |
| `metadata` | `paper_fetch.extraction.html._metadata`、provider metadata adapters、`paper_fetch.metadata.crossref` | 标题、作者、摘要、provider-owned 信号和 redirect stub lookup metadata。 |
| `provider-html-or-xml-extraction` | `paper_fetch.extraction.html.renderer`、各 provider HTML/XML 模块（`_article_markdown_elsevier_document`、Springer split helpers: `_springer_html` facade / `_springer_dom` / `_springer_assets` / `_springer_markdown` / `_springer_authors` / `_springer_references`、`html_springer_nature`、`_science_html`、`_pnas_html`、`atypon_browser_workflow`、`_wiley_html`、AMS split helpers: `_ams_html` facade / `_ams_dom` / `_ams_assets` / `_ams_markdown` / `_ams_authors` / `_ams_references`、`_iop_html`、MDPI split helpers: `_mdpi_html` facade / `_mdpi_dom` / `_mdpi_assets` / `_mdpi_markdown` / `_mdpi_authors` / `_mdpi_references`、`ieee`） | publisher HTML/XML 到中间结构的提取；HTML provider 通过 renderer facade 复用 Markdown 渲染 / sidecar 编排，provider 层只保留 container/profile/postprocess 差异。 |
| `html-cleanup` | `paper_fetch.extraction.html.cleanup_policy.CleanupPolicy`、`_runtime`、`inline`、provider cleanup policy | 站点 chrome、UI 噪声、caption fallback 和正文清洗。 |
| `availability-quality` | `paper_fetch.extraction.html.availability_policy.AvailabilityPolicy`、`paper_fetch.quality.html_availability`、`html_signals` | fulltext / abstract-only 判定、availability container cleanup、正文充分性度量。 |
| `section-classification` | `paper_fetch.extraction.section_hints`、`paper_fetch.extraction.html.semantics` | section kind、frontmatter、back matter、availability 与 section hints。 |
| `article-assembly` | `paper_fetch.models`、`models.builders`、`models.schema` | 中间结构合并成 `ArticleModel`。 |
| `asset-discovery` | `paper_fetch.extraction.html.assets`、`providers._html_asset_engine`、`extraction.html.figure_links`、`provider_rules`、provider asset policies | figure、table、formula、supplementary 资产候选识别。 |
| `asset-download` | `paper_fetch.extraction.html.assets.download` / `state` / `requester`、`providers.browser_workflow.fetchers`、provider asset clients | 资产候选下载、状态机、cookie-aware opener 和 provider-owned 下载链路。 |
| `asset-validation` | `paper_fetch.extraction.image_payloads`、`extraction.html.assets`、`models.Quality` | 真实图片校验、尺寸阈值、preview acceptance 和失败诊断。 |
| `asset-link-rewrite` | `paper_fetch.extraction.html.figure_links`、CLI / model asset link rewrite helpers | 远程 / 绝对资产链接改写为本地 Markdown 链接。 |
| `table-rendering` | `paper_fetch.extraction.table_grid`、`paper_fetch.extraction.xml_tables`、`paper_fetch.extraction.markdown_render.table_format`、HTML/provider adapters | provider-neutral cell/row IR、HTML/JATS/CALS 网格规范化、pipe-table/列表投影、降级和语义损失标记。 |
| `formula-rendering` | `paper_fetch.extraction.markdown_render.formulas`、`paper_fetch.extraction.html.formula_rules`、`provider_rules`、`_article_markdown_math`、`paper_fetch.formula.convert` | MathML / LaTeX / 公式图片 fallback 渲染。 |
| `markdown-normalization` | `paper_fetch.models.markdown`、provider postprocess、`extraction.html._runtime` / `renderer` | Markdown 块边界、空白、行内语义和去重。 |
| `references-rendering` | `providers._html_references`、`_article_markdown_elsevier_document`、`paper_fetch.markdown.citations` | 参考文献抽取与渲染。 |
| `final-rendering` | `paper_fetch.models.render`、`ArticleModel.to_ai_markdown`、`paper_fetch.mcp.schemas` | 最终 Markdown / MCP payload 输出。 |
| `artifact-storage` | `paper_fetch.artifacts.ArtifactStore`、`paper_fetch.mcp.fetch_cache` | 原始 payload、publisher HTML、下载资产和 fetch-envelope sidecar 落盘。 |

核心约束：

- `resolve/query.py` 不 import `providers.*`；HTML parsing / markdown extraction 不通过 provider 模块向上泄漏。
- HTML-to-Markdown 的通用编排入口是 `paper_fetch.extraction.html.renderer`；provider-specific 模块只能传入已选定的 HTML fragment、noise profile、renderer/postprocess hook 和 sidecar 策略。
- provider-neutral 的 access signals、section semantics、language filtering 固定在 `extraction.html.signals` / `semantics` / `language`；landing fetch helper 是 provider-neutral。
- table 展开、formula 默认 token/selector、inline TeX 渲染、citation cleanup / numeric payload 等通用能力位于各自 canonical owner；publisher-specific class/selector/pattern 必须通过 `ProviderHtmlRules` 与调用方 `noise_profile` 注入，不进入通用默认规则。
- availability verdict 位于 quality 层，reason code 的 canonical owner 是 `paper_fetch.reason_codes`；`paper_fetch.quality.reason_codes` 仅保留为公开兼容导入路径，生产代码统一依赖 canonical owner。`models.schema.ContentKind` 保持显式 Literal 作为 public wire contract。
- provider-owned browser workflow 的 DOM / Markdown 后处理只能通过 `ProviderHtmlRules.dom_hooks` / `markdown_hooks` 的 typed callable 注册，不得恢复字符串 stage dispatch 或反射表。

### 7. Provider 层

入口：`src/paper_fetch/providers/`

- 各 provider 的 metadata / fulltext / asset 下载适配，以及 provider 格式到 `ArticleModel` 的转换
- 返回 typed provider result（`ProviderContent`、`ProviderArtifacts`、`ProviderFetchResult`），而不是用无类型 metadata 口袋回传内部状态

能力边界由 `paper_fetch.providers.protocols` 表达：`MetadataProvider`、`FulltextProvider`、`RawFulltextProvider`、`AssetProvider` 用于 workflow typing；`ProviderClient` 是 provider 可继承的 convenience base class。

provider fulltext 内部链路统一接收同一个 `RuntimeContext`：workflow 调用 `FulltextProvider.fetch_result()` 时传入 `artifact_store=` 与 `context=`，context 继续传给 raw fulltext、abstract-only recovery、related assets 和 `to_article_model`，使同一次 fetch 内可 memo 派生 payload 并复用 runtime browser。需要原始 payload 用 `fetch_raw_fulltext()`，需要完整结果用 `fetch_result()`。`RawFulltextPayload` 不提供 `metadata` 兼容视图；route、markdown_text、warnings、trace、diagnostics 等结构化字段必须由 typed fields 传入。`ProviderContent` 唯一持有正文 URL、类型、字节、合并 metadata 与本地复制状态；raw payload 上的同名扩展兼容属性只是投影，不保存副本。

provider 身份与能力配置统一来自 provider entry module 导出的 `PROVIDER_BUNDLE`。内置 provider entry 只由 `paper_fetch.providers._BUILTIN_PROVIDER_ENTRY_MODULES` 显式清单加载；固定 loader 在启动时一次构造按 status 排序的不可变 bundle tuple、provider map、`PROVIDER_CATALOG` 与 source map，并立即验证 provider name/status order/client factory/source 及 alias、DOI prefix、exact/suffix domain 无冲突。运行时没有 mutable registry、导入协调、cache invalidation、源码扫描或第三方 bundle 注入。routing、默认资产策略、MCP status 顺序和 client registry 都从这些不可变映射派生，不维护第二份 provider 行为字典。Crossref 的 provider adapter 是 `paper_fetch.providers.crossref.CrossrefClient`，与 resolve 共同依赖 `paper_fetch.metadata.crossref.CrossrefLookupClient`。

`compile_route_execution_policy()` 是 catalog 到 runtime 的唯一非授权执行策略边界。Catalog 合并并公开 exact/suffix/base、API/template/route host 供 routing 与诊断使用，但 `provider_request_policy()` 不把这些 host 或 catalog sensitive headers 自动接入 HTTP/PDF/body/supplementary allowlist；它只投影 transport 实际读取的 timeout、transient/rate retry、QPS/minimum interval 与 rate-wait budget。调用方显式提供的 `HttpRequestPolicy.allowed_hosts` / `SafeRemoteUrlPolicy.allowed_hosts` 仍逐跳 fail closed。minimum interval 通过每 scope 串行 start gate 执行；未显式提供 asset profile 时，compiled route 的 `asset_scope` 选择执行范围，acceptance owner 使用 compiled `acceptance_policy` 验证真实 representation。固定 catalog 的身份重叠直接拒绝，不保留未被内置 provider 使用的 priority/reason 豁免。

### 8. Runtime / Artifact / Cache 边界

入口：`src/paper_fetch/runtime.py`、`artifacts.py`、`mcp/fetch_cache.py`

- `RuntimeContext` 显式承载运行时依赖；`parse_cache` 是进程内、单 context 生命周期的解析 memo（key 含 provider、role、source、body sha256、parser 和配置指纹），访问器由 `RLock` 保护，`get_or_set` 对同 key 原子执行一次 supplier，dict/list 读取返回拷贝，XML root 只读复用。
- Browser runtime 统一使用 Camoufox facade 和集中 storage-state manager；auth、preflight、HTML fetch、seeded PDF fallback 共享 provider-scoped `storage-state.json` 路径、写锁和 atomic write。preflight 的状态契约为 `ready/challenge/auth_required/network_timeout/extraction_error/runtime_error/cancelled`，CLI/MCP 共用 reason-code 分类和 next action。Browser-backed image fetch 共用一个 wall-clock budget；PDF fallback 只用 lightweight browser warm 采集 cookies、user-agent 和 final URL。
- `artifact_mode=all` 下，已到达页面但 extraction/availability 失败的 HTML route 会在 `diagnostics/<provider>/<doi-or-url-digest>/<route>-<attempt>/` 保存 `diagnostic.json` 与隐私清洗后的 `page-sanitized.html`。自动流程不保存原始失败 HTML 或截图；query、userinfo、email、表单、脚本及事件属性会被删除/脱敏，2 MiB 上限只在 DOM 节点边界截断。成功或终态失败的 CLI/MCP manifest 都把这些文件作为 `kind=diagnostic` additive artifact 快照保存 size/SHA-256。
- 每个资产/失败项保留 `asset_timing={queue,candidate_resolution,dns_policy_validation,connect_to_headers_ttfb,body_stream,browser_recovery,retry_wait,conversion,save,total}_ms` 和终态，不保存签名 URL；请求级耗时由 trace event 与外层调用者墙钟观察，不在 runtime 聚合第二份统计。
- 本地转换工具链使用进程内有界缓存降低重复探测：Ghostscript/libvips 候选路径、`--version` probe 和工具 env overlay 按相关 env/目录/文件指纹失效；公式转换保留 MathML 结果缓存和 `mathml-to-latex` worker 复用；PDF fallback 对无图片导出路径的同一 PDF hash 复用 Markdown 渲染结果，并在成功结果 diagnostics 中记录 hash、字节数、页数、cache status 和耗时。
- `ArtifactStore` / `DownloadPolicy` 管理 artifact mode：provider PDF/binary local copy、PDF fallback 源文件、provider 原始 HTML、Markdown 保存、asset 诊断，以及 fetch-envelope/cache-index JSON 的原子写入。
- `RuntimeContext.asset_budget` 是同一篇论文所有二进制资产的唯一资源边界；正文图与 supplementary 即使分两次 provider 调用，也共享默认 128 文件、单文件 32 MiB、累计 256 MiB、64,000,000 像素和最多 4 个（再受 route cap 限制）的 worker。Content-Length 先验、未知长度 chunk、gzip 压缩/解压、图片尺寸、转换输出、arXiv source archive 成员及临时 staging 都进入 rollback-safe reservation；失败候选回滚，成功发布后才 commit。
- `asset_default != none` 的 provider 必须声明显式 `assets` route；正文资源策略从 catalog 编译为 direct 单次 `20` 秒、route cap `2`，具有可靠 browser byte recovery 的 provider 使用零 transient direct retry。资产首先按 URL 使用共享 hostname 连接池进行有界 direct stream；每篇论文的每个 host 只有一个首资源 direct probe，并发请求等待 probe 结论。direct 超时/拒绝且 browser recovery 真正成功后，同篇剩余同源资源才直接复用已验证 browser 路径；不同 host 独立决策，熔断状态通过 provider/article key 限定在当前 `RuntimeContext`，不跨论文持久化。Browser 可从 `response.body()`、page-context `arrayBuffer()`、canvas、download/file 或 viewer PDF response 交付字节。无论来源，Content-Length/实际字节、MIME、像素、取消、同目录唯一 staging、flush/fsync 和原子发布均复用同一 `AssetBudget`/`ArtifactStore` 边界。EPS/TIFF、PDF screenshot copy 与 arXiv source figure 继续采用 path-to-path 处理。
- 资产 future 以 `as_completed` 顺序立即保存或释放 staging/reservation，最终只把轻量结果恢复为输入顺序。caller-thread browser 路径先同步探测首资源，再让剩余 HTTP 工作按 route cap 并发；IEEE 等自定义恢复在合并逻辑记录时保留统一逐资源 timing/route。致命文件/字节/像素超限会保留首个稳定 reason、删除所有登记 staging、设置 cooperative stop fence 并取消 pending future；来自 `RuntimeContext` 的外部取消不会被内部 budget stop 合并掉。资产 HTTP 使用共享 hostname pool；全局 worker 上限仍为 4，显式 assets route cap 通常为 2，HTML/PDF 的串行限制不再误降资产 worker。
- arXiv source archive 的流式解包、regular-member 遍历门禁和 LaTeX figure 引用解析集中在 `_arxiv_source_archive.py`；重复或非法名称也计入最多 128 个检查成员，保留成员继续使用共享 `AssetBudget` 的单文件/累计字节 reservation。
- `FetchCache` 管理 MCP fetch-envelope sidecar reuse/write 语义；当前 sidecar version 为 5，并要求完整 acquisition，旧 sidecar 以 `version_mismatch` 失效后重新抓取，不删除既有 Markdown。MCP cache index 只信任当前版本以及显式注册、仍通过 DOI/hash/scope 校验的条目，不自动迁移、修复或全目录重扫。`get_cached(detail="compact")` 的请求兼容唯一调用 `cached_request_matches()`，质量摘要调用统一 `evaluate_fetch_acceptance()`；public scope 绝不反向读取 API token 或 storage-state sidecar。
- `CapabilityScopeBuilder` 是 cache capability identity 的唯一 owner。当前 scope digest 绑定版本化 credential facts；成功注入 browser context 的状态另绑定 provider、backend、最终 canonical storage-state 路径和写 sidecar 时的最终内容 SHA-256。`RuntimeContext` 只在 context 创建成功且确实传入 `storage_state` 后记录 use；配置了空 profile/path 不会制造 private scope，实际 use 即使文件随后消失也不会降级成 public。
- Cache sidecar 的 loader、inspector 与 compact projection 只检查当前请求在可读 scope 中的精确 variant，再单向回退 canonical/public；不会 glob 或自动选择其它历史 variant。public 以及不同 private scope 不能横向读取。旧版本、无 scope、损坏或 DOI/scope 不匹配条目 fail closed。相同 visibility filter 同时约束 cache index、`list_cached`、`get_cached` entry 和 entry template；动态 cache MCP resource 已移除。
- Cache index 写入在 artifact 成功提交后按 DOI 增量注册，并在锁内原子合并；读取会复核 scope 与文件事实。Loose Markdown 只有在保存时凭 envelope DOI 显式注册后才可命中，文件名或正文 DOI 文本不作为身份凭据。
- Artifact、fetch-envelope variant/canonical sidecar、Markdown、cache index 与 batch results 使用同一提交协议：目标路径对应进程/跨进程 `FileLock`，每个 writer 在目标同目录创建唯一 staging file，写完 flush/fsync，再在 `RuntimeContext.commit_guard` 的最终临界区内 `os.replace` 并 fsync 目录。取消 fence 与最终 replace 由同一锁线性化；fence 返回后，后台 worker 即使晚返回也不能提交。`overwrite=false` 时相同字节是无改写的幂等成功、不同字节是显式冲突；`overwrite=true` 允许串行原子替换。
- 单篇 sync/async 入口从 fetch、cache、Markdown 到最终 CLI/MCP 输出贯穿一个 `RuntimeContext`。异步取消先设置 cooperative event 和 commit fence，再用独立 task 等待有界 grace；重复 `CancelledError` 不会跳过该等待。Batch 每个 logical item 使用独立 child context，只共享线程安全 HTTP transport 与 immutable env，不共享 provider client、session、CookieJar、trace/timing/cache；duplicate 与未调度 item 也会幂等关闭。
- Batch resolve/check 始终保留输入等长、原顺序的终态数组，以及稳定 1-based `index/query/status/error/provider_lane`；progress 区分 `terminal/completed/not_scheduled`。`batch_check` 对 title/generic 输入先在 child context 解析并缓存 provider identity，再按 resolved lane 调度；已知 DOI 只用无网络 initial lane。`batch_resolve` 本身在执行解析前无法预知 title provider，故预解析阶段是 generic，但成功结果会报告本轮解析出的 provider。
- Batch fetch 在 resolve 后以规范 DOI 建 canonical target table，只执行 representative，并按原 index fan-out；该去重仅限当前批次。每个输入仍得到一个终态 record，最终结果按输入顺序原子写入。

### 9. Transport 层

入口：`src/paper_fetch/http/`

- HTTP 请求、连接复用与同 host 有界并发、进程内短 TTL GET 缓存、响应体大小限制、有限短重试、协作式取消检查

`HttpTransport` 保持 public request options、structured logs、cancel checks、`Retry-After` 最大等待和 `RequestFailure` 形状；瞬时错误与 429 retry policy 由 `urllib3.util.Retry` 表达，连接池由 `PoolManager(num_pools, maxsize, block=True)` 配置并按 hostname 复用。`SafeRemoteUrlPolicy` 在每个 redirect hop 检查 HTTP(S)、标准端口、无 userinfo、无 HTTPS 降级以及全部 DNS 答案均为公网地址，然后由共享 pool 按原 hostname 连接。跨 origin redirect 始终剥离 Authorization/Cookie/Proxy-Authorization/Referer；额外敏感 header 和 host allowlist 只有调用方显式放入 request policy 时才生效。HTTP cache 仅在当前进程内按请求 key、TTL、条数和总字节上限复用，不写磁盘、不做 conditional 304、reconcile 或 prune。内部子模块：`transport.py`（request loop / pool / semaphore / log）、`url_policy.py`（direct URL、DNS/IP 与 redirect 安全）、`provider_policy.py`、`cache.py`（memory cache key / bounds / stats）、`retry.py`、`body.py`、`errors.py`。

Route QPS 使用同一个 transport cooldown lock 与 scope 做跨 worker 原子时隙预留；服务端 `Retry-After` 与既有 minimum interval 总是取更晚 deadline。arXiv Atom route 因而在同一共享 transport 上至少间隔三秒，batch child context 共享该 transport 但不共享可变请求状态。测试使用 fake clock/barrier，不依赖真实等待。

Fulltext provider identity evidence 保留 domain、publisher、DOI 的一致与冲突事实。DOI prefix 或两个独立信号一致才属于 strong；只有 strong provider 的 `NO_ACCESS` 能终止 provider waterfall，weak access boundary 会保留 diagnostics 后继续严格 identity-checked candidate。Acceptance 不再用 title 证明 DOI-less identity；只有 DOI，或同时声明 URL、verified、unique 的 canonical landing fact，才会得到 `identity=resolved`。

Camoufox/Playwright 的 navigation、redirect、子资源与 service worker 使用浏览器原生行为；项目不安装 BrowserContext-wide URL/DNS interceptor，也不把带 cookie 或 storage state 的 context 绑定到单一 origin。Provider image/font/media 优化只在 page scope 按资源类型生效。Browser 资产恢复可以直接返回 browser-owned image/file/PDF bytes，再进入统一预算与 staging。

日志出口对 URL query/fragment、header map、query map 和任意文本中的标准/provider secret 使用同一递归 scanner；MCP bridge 再执行一次防御性过滤。MCP 只安装一个 ref-counted process-global router handler，当前 request target 存在 `ContextVar`，并显式传播到项目创建的 worker context。Target 自身用锁线性化 emit 与失效：bridge 退出会先将自己的 target 标记 inactive，再恢复 ContextVar、递减 handler 引用；因此保留 copied context 的迟到 worker 既不能写入已结束 session，也不能串到仍活跃的其它请求。Handler 在构造 notification coroutine 前同时拒绝 inactive target 与停止/关闭的 loop，重叠请求不会互收日志或乱序恢复 logger level。

### 10. CI / 回归验证边界

`.github/workflows/ci.yml` 是默认分支 push / pull request 的薄触发器，完整命令事实来源是 reusable `.github/workflows/verify.yml`。CI 运行一次完整 unit、integration、Ruff、生产包 mypy、版本与依赖漏洞门禁，并把全部可执行 exact fixture 按 provider 稳定分成四个 shard。已删除的 devtools 不属于当前验证命令。wheel/sdist 仍分别进入隔离 venv 执行 CLI/import/MCP/resource smoke；release 继续验证依赖、inventory、SBOM、checksum 与 provenance。

pytest 在收集前验证锁定 MCP major 与 trafilatura API 行为；ambient 环境不兼容时会提示先执行 `uv sync --frozen --extra dev --extra full`，常规验证统一通过 `PYTHONPATH=src uv run python -m pytest ...`。运行时 registry、公开入口和行为测试负责验证架构边界，不以私有模块布局或文档措辞作为契约。

## 端到端业务流程

```text
service facade
-> workflow.resolution
-> workflow.metadata (uses workflow.routing for route signals and probes)
-> workflow.fulltext
-> workflow.rendering
-> CLI / MCP / cache
```

### 1. resolve

`resolve_paper()` 把 DOI / URL / 标题输入标准化成 `ResolvedQuery`，产出 `query_kind`、`doi`、`landing_url`、`provider_hint`、`candidates`、`title`。MCP structured `title` / `authors` / `year` 会以结构化 request 进入 resolver：Crossref bibliographic search 只使用 title，authors 用 canonical author key 做独立相似度，year 从候选 `published` 字段提取后参与加权消歧，不再拼进同一个标题字符串。DOI cleanup 保留宽松输入清理后用 `idutils` 校验/规范化；标题候选用 token Jaccard + `rapidfuzz.fuzz.ratio` 评分，confidence threshold 和 ambiguity margin 控制。候选不够确定时保留 `candidates`，由上层返回 `ambiguous`，不猜测性继续抓取。

### 2. routing signal

路由优先级固定是 `domain > publisher > DOI fallback`，信号来源为 URL 域名、Crossref `landing_page_url`、Crossref `publisher`、DOI 前缀。`provider_hint` 表示最优提示，不是最终来源承诺。

### 3. metadata merge

workflow 尽量拿到 Crossref metadata 与 publisher metadata（`elsevier` 仍参与 publisher metadata probe；`springer`/`wiley`/`science`/`pnas`/`ieee`/`copernicus`/`ams`/`mdpi`/`royalsocietypublishing`/`annualreviews`/`plos`/`frontiers`/`oxfordacademic`/`acs`/`iop`/`aip`/`tandf` 不做 publisher metadata probe），再执行 primary / secondary merge，得到统一 metadata 视图，决定更准确的 `landing_page_url`、更稳定的 provider 选择和 metadata-only 结果内容。provider/Crossref primary-secondary merge 的事实源是 `paper_fetch.metadata.types.PRIMARY_SECONDARY_METADATA_MERGE_RULE` 与 `merge_primary_secondary_metadata()`：显式 blank primary scalar 阻止 secondary 回填并最终输出 `None`，authors 使用 semantic author key 去重，keywords 按大小写无关文本去重，`fulltext_links` 按 URL 去重，`references` 优先 DOI、否则 raw 文本去重。provider 内部多层 enrichment 用 `paper_fetch.metadata.types.MetadataMergeRule` / `merge_metadata_layers()` 描述字段优先级，provider-specific 的 DOI/author 规范化在 adapter 边界完成。

### 4. provider fulltext

选中 provider 后，workflow.fulltext 先尝试 provider 主路径。每个 official provider 自管 HTML/XML/PDF/browser 瀑布，成功时公开为各自的 source（如 `elsevier_xml`/`elsevier_pdf`、`springer_html`/`springer_pdf`、`wiley_browser`、`science`/`pnas`、`ieee_html`/`ieee_pdf`、`arxiv_html`/`arxiv_pdf`、`copernicus_xml`/`copernicus_pdf`、`ams_html`/`ams_pdf`、`mdpi_html`/`mdpi_pdf`、`royalsocietypublishing_html`/`royalsocietypublishing_pdf`、`annualreviews_html`/`annualreviews_pdf`、`plos_xml`/`plos_pdf`、`frontiers_xml`/`frontiers_pdf`、`oxfordacademic_html`/`oxfordacademic_pdf`、`acs`、`iop_html`/`iop_pdf`、`aip_html`/`aip_pdf`、`tandf_html`/`tandf_pdf`）。**各 provider 的完整 waterfall 顺序、env 依赖和 source 细节以 [`../providers.md`](../providers.md#wiley-science-pnas-browser-workflow) 为准**，本文不复制。

实现要点：

- Wiley / Science / PNAS / AMS / Annual Reviews / Royal Society Publishing / ACS / IOP / AIP / MDPI / Taylor & Francis Online 共用 `paper_fetch.providers.browser_workflow` 这套 canonical browser workflow facade（profile / bootstrap / pdf_fallback / article / assets / client / shared / html_extraction / fetchers），通过 `shared.BrowserWorkflowDeps` 注入依赖。AMS 使用 selected-browser HTML 和 browser-seeded PDF fallback，并保留自己的 `downloadpdf` candidate 规则与 `ams_html` / `ams_pdf` source。
- Atypon 候选路由通过 `_atypon_browser_workflow_profiles` 分派，publisher 差异走 profile callback。
- provider-owned author 抽取统一用 `_html_authors.AuthorExtractionPipeline`，每个 provider 只注册命名 `AuthorStep`。
- 这些 waterfall 由 `_waterfall` 做轻量编排（按 step 顺序执行、累积 warnings、组合失败、写成功/失败 source markers）；step 默认会对 `NO_RESULT`、`NO_ACCESS`、`RATE_LIMITED`、`ERROR` 等 provider 失败码继续后续 fallback，最终失败会稳定聚合 retry-after、warnings、source trail 和缺失 env。`ProviderClient.fetch_result` 是 template-method，base 统一完成 raw payload、related assets、`to_article_model`、artifacts 和 trace/warning 组装。
- 通用 HTTP-first 资产下载保留给非目标 provider，由 `extraction.html.assets.download_assets(kind, ...)` 基于 `AssetDownloadKind` 统一处理 resolve/fallback；asset retry 只针对网络、超时、browser context/fetch error 或 Cloudflare challenge 触发，404/410、非目标 content type、unsupported scheme 只记诊断不重试。

正文足够可用时流程在此结束。

### 5. abstract-only / metadata-only fallback

命中 official provider 时，workflow.fulltext 只执行该 provider 自管的 HTML/XML/PDF/browser waterfall；`springer`/`wiley`/`science`/`pnas`/`ams`/`annualreviews`/`acs`/`iop`/`aip`/`tandf`/`ieee` 只能确认摘要级内容时直接返回 provider `abstract_only`，`arxiv`/`copernicus`/`elsevier`/`mdpi`/`royalsocietypublishing`/`plos`/`frontiers`/`oxfordacademic` 在 HTML/XML/PDF 都不可用时进入 metadata-only fallback。

没命中 official provider 时，系统仍允许 DOI / Crossref metadata 解析，但跳过通用 HTML 正文提取：`strategy.allow_metadata_only_fallback=true` 返回 metadata-only 结果，否则抛 `PaperFetchFailure`。metadata fallback 时 `has_fulltext=false`，`warnings` 提示降级，`source_trail` 带 `fallback:metadata_only`，public `source` 通常表现为 `metadata_only`（若 metadata 含摘要，`content_kind` 可能是 `abstract_only`）。

### 6. render / envelope / cache / MCP 暴露

拿到最终 `ArticleModel` 后，workflow.rendering 构造 `FetchEnvelope`，对外结果含 `trace: list[TraceEvent]`、与 trace 同步的兼容字段 `source_trail` 和 `warnings`。质量状态只由 `Quality` 实例持有；有 article 时 `FetchEnvelope.quality` 与 `ArticleModel.quality` 引用同一实例，envelope 顶层质量字段是兼容投影。随后 `ArtifactStore` 已处理 provider payload / HTML copy / asset 诊断；CLI adapter 决定是否写 Markdown、overwrite 和相对资源链接改写；MCP adapter 负责 `FetchCache` 复用/写入、credential scope、Markdown 注册和 inline images。两者都只通过 `FetchPipeline` 共享显式 context 下的 service 调用。

## 数据契约与角色边界

### `ResolvedQuery`

表达「输入被解析成什么论文候选」，为 routing 与 metadata 拉取提供标准化入口。不决定输出格式或正文抓取成功与否。

### `FetchStrategy`

表达「怎么抓」。最重要的字段是 `allow_metadata_only_fallback`、`preferred_providers`、`asset_profile`。它不决定返回哪些 payload（那是 `modes` 的职责）。

### `FetchEnvelope`

固定返回形状的公开抓取结果。始终承载 `doi`、兼容 `source`、可空的结构化 `acquisition`、`has_fulltext`、`warnings`、`source_trail`、`token_estimate`、`token_estimate_breakdown`；这些顶层质量字段保持旧 Python API 和 wire shape，但直接投影 canonical `quality`，不另存可变副本。按 `modes` 决定是否附带 `article` / `markdown` / `metadata`。`source` 不因新增字段改值；无法从 provider 原点确认 acquisition 时保持 `null`，不做启发式补全。

MCP tool 返回的是在业务 payload 顶层追加 `schema_version=2` 的 JSON-safe 形状；FetchEnvelope sidecar 内的业务 payload 也保持该 v2 形状，其缓存 wrapper 版本独立保持 `version=5`，旧 v5 sidecar reader 继续接收历史重复字段并迁移到单个 `Quality` 实例。失败时 `status` 仍是旧客户端可读的粗粒度状态，细粒度失败原因放在 `code` / `error_category`，HTTP 与限流细节放在 `http_status` / `retry_after_seconds`。

### `ArticleModel`

表达 provider 已转换好的正文、资产、references 和质量诊断，并统一负责最终 Markdown 渲染的 token budget、资产附录、references 输出和质量 warnings。重要边界：

- `assets[*].render_state` 决定资产是否追加到尾部附录（`inline`/`suppressed` 不追加，`appendix` 可追加）；正文已内联图片按 URL/相对路径/后缀/basename 做等价比较避免重复渲染。
- 文章组装先用已下载资产把正文远程 figure/table/formula 链接改写成本地路径，再做 Markdown 图片块边界和短 alt 归一化；image alt 由 `paper_fetch.markdown.images` 生成，caption 不进入 `![alt]`。
- structured metadata 进 front matter 前解开 HTML entity，避免 `&amp;` 泄漏。
- `assets[*].download_tier` / `download_url` / `content_type` / `downloaded_bytes` / `width` / `height` 是下载诊断，不应被下游丢弃。
- `quality.semantic_losses.table_layout_degraded_count` 表示源表 span/列定义异常导致布局无法可靠验证；合法合并单元格成功展开只记录规范化 reason，`table_semantic_loss_count` 才表示语义内容丢失。

### `provider_status`

在抓取前报告本地环境是否就绪。本地检查边界与各 provider check 名称以 [`../providers.md`](../providers.md#provider-status-local-boundary) 为准；IEEE 当前返回 `html_route` 与 `pdf_fallback` 两条 check。

`paper_fetch.diagnostics` 是 CLI `doctor` 与 MCP `provider_status` 的共享 owner：provider/group/detail 筛选先由 catalog-backed schema 校验，随后只构建目标 provider 的静态状态。full 报告复用 `config.resolve_runtime_env()` 的来源元数据、`browser_preflight.static_browser_capabilities()` 的非 live 浏览器能力和 `image_tools.probe_image_conversion_backends()` 的本地可执行文件探测；compact 只保留路由字段。该层可以构造 transport 供 provider client 保持原接口，但禁止调用 transport、启动/连接浏览器或检查远端页面。

CLI 与 MCP live 入口都以 `paper_fetch.browser_preflight.run_browser_provider_preflight()` 为唯一 orchestration owner；`paper_fetch.mcp.browser_preflight` 只做 Pydantic 入参、状态分类、progress/cancel 转接和 JSON-safe structured output。共享核心串行保留逐 provider 结果，把 `RuntimeContext.cancel_check` 传入现有 browser HTML bootstrap，并通过 `BrowserRuntimeConfig.persist_storage_state` 控制是否保存；不得复制 provider workflow 或转入 PDF fallback。

诊断语义分三层：`provider_status` / `doctor` 只证明静态配置与本地依赖；CLI `browser-preflight` / MCP `browser_preflight` 才证明一次真实样例页面链路并可能写 storage-state；auth 是明确的人工副作用入口。三层结果不得相互冒充。

### `has_fulltext`

区分两个层面：`fetch_paper().has_fulltext` 是完整抓取瀑布后的最终 verdict；MCP 的 `has_fulltext()` 是只用更弱信号的廉价 probe。两者不要求逐案完全一致（见 [`probe-semantics.md`](probe-semantics.md)）。

## 关键例外与调用方容易误解的点

### official provider 不走通用 HTML fallback

`elsevier`/`springer`/`wiley`/`science`/`pnas`/`ieee`/`arxiv`/`copernicus`/`ams`/`mdpi`/`royalsocietypublishing`/`annualreviews`/`plos`/`frontiers`/`oxfordacademic`/`acs`/`iop`/`aip`/`tandf` 的 HTML/XML/PDF/browser 逻辑由 provider 内部管理：不存在 public HTML fallback 开关，是否尝试主路径由 provider 路由和 `preferred_providers` 控制，更细的成功细节看 `source_trail`。

### `crossref` 既可能是 source，也可能只是 signal

作为 signal 时用来路由，不代表结果来自 Crossref；作为底层来源时 `ArticleModel.source` 可表现成 `crossref_meta`；fulltext 失败走 metadata fallback 时 `FetchEnvelope.source` 映射为 `metadata_only`。

### `warnings` 与 `source_trail` 都是契约的一部分

`warnings` 告诉调用方发生了什么降级或限制，`source_trail` 告诉维护者每一步怎么走。只看正文而忽略它们会误读结果质量。

## 输出与可观测性

- **`warnings`** 常见内容：abstract-only / metadata-only 降级、HTML / provider fallback 提示、资产部分下载失败、preview 资产可接受降级或不可接受 fallback、表格版式降级 / 语义丢失、公式 fallback / missing、token 截断。
- **`source_trail`** 常见轨迹：`resolve:*`、`route:*`、`metadata:*`、`fulltext:*`、`fallback:*`、`download:*`。
- **`token_estimate_breakdown`** 拆成 `abstract` / `body` / `refs`，帮 host 决定是否截断、哪段最占预算、是否改 metadata-only / summary-first。
- **MCP cache tools**：`list_cached` / `get_cached` 在显式 `download_dir` scope 内查询索引与条目。`FetchCache` 匹配 `prefer_cache=true` 请求（按 modes、strategy、`include_refs`、`max_tokens`、sidecar version 和 `EXTRACTION_REVISION` 复用本地 fetch-envelope）；cache 不再镜像为动态 MCP resources。

## 扩展点：新增能力时应改哪一层

- **新增 provider**：主要改 `src/paper_fetch/providers/`，必要时更新 provider-specific extraction / metadata adapter；entry module 导出 `PROVIDER_BUNDLE` 并加入固定模块清单，不手工编辑 `provider_catalog.py`、`provider_rules.py`、`quality/html_signals.py` 或 `quality/html_availability.py`，也不把 provider 逻辑塞进 CLI / MCP。
- **新增 MCP surface**：主要改 `src/paper_fetch/mcp/`（`schemas.py`、`fetch_tool.py`、`cache_payloads.py`、`batch.py`、`batch_fetch.py`、`server.py`）；需要真正的新抓取逻辑要先落到 service / workflow 层。新的批量抓取入口必须继续复用 `workflow.batch_runner`、`manifest.build_manifest_record` 和 `manifest_writer.RunManifestStore`。
- **新增渲染能力**：正文渲染或资产展示能力优先改 `src/paper_fetch/models/` 与 provider 到 `ArticleModel` 的转换，而不是让 CLI / MCP 自己拼装业务结果。

## 相关文档

- [`../../README.md`](../../README.md)
- [`../providers.md`](../providers.md)
- [`../deployment.md`](../deployment.md)
- [`probe-semantics.md`](probe-semantics.md)
