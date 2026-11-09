# Paper Fetch Skill 架构与业务流程

本文说明可复用核心库、CLI、MCP adapter 和 thin skill 的职责、数据契约及扩展边界。
稳定入口为 `paper-fetch` 和 `paper-fetch-mcp`；运行时代码位于 `src/paper_fetch/`，
静态 skill 位于 `skills/paper-fetch-skill/`。provider 配置与获取顺序见
[provider 指南](../providers.md)，提取语义见[规则文档](../extraction-rules.md)。

## 当前系统分层

### 1. CLI 层

入口：`src/paper_fetch/cli.py`

- 解析命令行参数，组装 `FetchStrategy` 与 `RenderOptions`
- 创建/关闭 `RuntimeContext`，通过 `FetchPipeline` 调用 service 层，并负责 CLI 输出与 Markdown 保存生命周期
- 控制 stdout / stderr / 输出文件 / 退出码

不负责 provider 选择、正文抓取策略、MCP 序列化。

### 2. MCP 层

入口：`src/paper_fetch/mcp/`

- 暴露 MCP tools 与静态 provider-catalog resource，校验工具参数
- 把 service 结果序列化成 JSON-safe payload
- 通过 `FetchCache` 管理 fetch-envelope sidecar，供 `list_cached` / `get_cached` 查询，并管理 Markdown 注册和 cancellation commit guard；`FetchPipeline` 只复用 service 调用
- 管理 progress、structured log、cancellation

实现边界：

- MCP runtime 基于官方 Python SDK 2.x 的 `MCPServer` 与 stdio transport；server 同时服务 2025 握手协议与 2026-07-28 无状态协议，只保留静态 provider catalog resource。
- payload/tool 入口通过 `paper_fetch.mcp._deps.MCPDeps` 显式注入 runtime env、service、provider registry 与 cache index 依赖；生产默认由 `default_mcp_deps()` 装配，测试通过构造定制 deps 注入。
- 所有 MCP tool JSON payload 顶层都带 `schema_version=2`；错误 payload 保留兼容字段 `status` / `reason`，并补充 `code`、`http_status`、`error_category`、`retry_after_seconds`、`provider`、`warnings`、顶层唯一完整 `trace` 和 `source_trail` 供 host 做机器判断。v2 的 `quality` 不复制完整 trace。
- 当前九个工具都不在 `tools/list` 发布协议级 `outputSchema`。工具结果继续通过 `CallToolResult.structured_content` 返回带 `schema_version=2` 的既有 payload；该版本化 payload 契约不等同于 MCP output schema。
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

只保留公共入口与兼容导出：`FetchStrategy`、`PaperFetchFailure`、`RuntimeContext`，以及 `resolve_paper()`、`probe_has_fulltext()`、`fetch_paper()`。provider route 判断、HTML 提取、payload 写盘策略都由 workflow / provider / artifact 层负责。

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
- lane key 由调用方在调度前提供。worker 通过结构化 failure/result classifier 报告既有 `rate_limited` reason code 和可选 `retry_after_seconds`；runner 不解析 warning 文案。观察到限流后，该 lane 在本次 run 内不提交新项，并用可注入的单调 clock 记录 `limited_at`、解析后的 cooldown 与 `cooldown_until`；其他 lane 继续运行。本模块不跨 run 学习或维护全局限流服务。
- `BatchRunResult.results` 始终按输入 index 排列且每项只有一个终态；真实完成、worker 异常、协作式取消以及从未提交的项分别表示为 `succeeded`、`failed/rate_limited`、`cancelled` 和 `not_scheduled`。`completion_events` 与 completion/progress callback 独立保留终态被观察到的顺序，流式消费者不能把它误当输入顺序。
- stop predicate 或 cancel event 只阻止新的增量提交；已在途 worker 依靠 `RuntimeContext.cancel_check` 协作退出。取消超过宽限期且仍有 pending worker 时，runner 只调用一次显式 escalation callback 关闭共享 browser manager，随后仍等待 worker 收敛。worker 已观察到的异常和取消、以及因 stop/cancel/lane cooldown 未调度的输入，都会生成结构化终态，避免批次尾部静默丢失。
- 每个终态（包括 `not_scheduled`）依次触发一次 completion callback 和一次 progress callback；两者都可同步或异步。callback 是观察者：异常写入 `BatchRunResult.callback_failures`，不覆盖 item 终态，也不隐式改变停止策略；需要把 callback 失败升级为 run 失败的 adapter 必须显式检查该字段。callback 内设置 cancel event 会在下一次增量提交前生效。

MCP `batch_resolve` / `batch_check` 保持既有兼容调度；`batch_fetch` 在提交前只调用 catalog-backed URL/DOI 身份 helper 推断 provider lane，一个 lane 限流后把该 lane 的后续输入终态化为未调度，其他 lane 继续。它的 `results` 按原 1-based input index 返回，`completion_order` 单独投影完成顺序，progress 使用完整终态计数。

`RuntimeContext` 显式提供 env、transport、clients、下载目录、取消与 artifact store，以及当前抓取的 parse/session cache。公共 service 入口未收到 context 时自行创建并关闭；内部 workflow 要求显式传入。所有权见 [Runtime / Artifact / Cache 边界](#8-runtime--artifact--cache-边界)。

#### 统一抓取验收模型

`paper_fetch.workflow.acceptance` 是 CLI、MCP、cache 和 manifest 唯一可复用的抓取验收语义。`evaluate_fetch_acceptance()` 是纯函数：它只消费 `FetchEnvelope` / 结构化失败 code、请求的 `asset_profile`、请求输出集合和可选的 `AssetAcceptanceSummary`，不联网、不访问或写入文件，也不重新运行 provider 质量判断。文件存在性、hash、MIME 等 I/O 事实由外层 adapter 收集后再以结构化事实传入；验收层不解析 warning 文案。

`FetchAcceptanceReport` 固定包含七个分面：

| 分面 | 事实与边界 |
| --- | --- |
| `overall` | 稳定枚举 `complete`、`degraded`、`limited`、`failed`、`action_required`。 |
| `identity` | 归一化 DOI、期望 DOI、标题、候选数和 `resolved/ambiguous/mismatch/unavailable`；DOI 归一化复用 `publisher_identity.normalize_doi()`。 |
| `fetch` | `ok` 只表示调用已完成；歧义、无访问权限或配置缺失是 `action_required`，其他未产出 envelope 的错误是 `failed`。 |
| `content` | 只使用 `fulltext`、`abstract_only`、`metadata_only`、`unavailable`，同时保留 `has_fulltext`、`has_abstract`、confidence 和 flags。表格布局降级、表格语义损失、公式 fallback/missing 保持独立计数。 |
| `asset` | 显式记录 profile、`requested`、本地/远程、full-size、preview、failure、placeholder suspected 和 not-archived。v2 字段记录正文逻辑资产的 discovered/attempted/local/full-size/preview/failed/not-archived/remote-only 计数，以及两个严格约束和 satisfaction。`asset_profile=none` 必须得到 `requested=false/status=not_requested`，未完成 fetch 时已请求资产是 `unavailable`；仍保留的远程链接由 `remote_link_count`、`remote_only_count` 和 `remote_links_preserved` 单独表达。 |
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

因此 transport/adapter 的 `status=ok`、正文事实 `has_fulltext` 和任务级 `overall` 是三个不同维度，任何调用方都不得互相替代解释。metadata-only 可以同时是 `status=ok`、`fetch.status=ok`、`has_fulltext=false`、`overall=limited`。

验收 schema 当前为 v2。每份报告都必须序列化 `schema_version=2` 和 `minimum_reader_schema_version=2`。v2 包含 `accepted_preview`、`fallback_preview`、稳定 `issue_codes`、正文资产计数与 `require_local_body_assets` / `require_full_size_body_assets`（后者隐含前者），并要求 `preview == accepted_preview + fallback_preview`。严格分母只包含需要独立归档文件的正文逻辑资产；已经以内联语义完成且没有 binary payload/remote/failure 的 table、formula 或 figure 不会被误算为缺少本地文件。两项约束默认关闭且只适用于 `body|all`；未满足时 asset/overall 降为 `degraded`，已经取得的全文仍保持 `fetch=ok`。reader 可忽略未知 additive field，但缺少版本、v1 或未来不支持的版本必须拒绝，不能猜测迁移。`FetchAcceptanceReport.model_json_schema()` / `fetch_acceptance_json_schema()` 是 JSON Schema 唯一生成入口。

`FetchEnvelope.trace` 是一次 fetch 的唯一完整 trace owner。provider/waterfall 先在局部列表累积事件，workflow 最终只写入 envelope 一次；`Quality` 仅保留去重后的 article source-trail 摘要。acceptance、manifest 与 MCP 都只投影 envelope 顶层 trace，两个不同 attempt 的同 code 会保留为两条真实事件。

#### 版本化 manifest record

`paper_fetch.manifest` 是单篇 CLI、CLI batch 和 MCP `batch_fetch` 共用的 manifest record owner。adapter 只向 `build_manifest_record()` 提交原 query、JSON-safe 请求参数、`FetchEnvelope` 或结构化 error、输出文件声明和 run/index/attempt；schema 字段、验收摘要、trace 与文件快照均由 builder 统一派生。builder 保持纯逻辑，不写输出文件。

manifest record schema 当前为 v2，`schema_version=2` 和 `minimum_reader_schema_version=2` 都是必填常量。每条记录以 `record_status` 表示 `completed/failed/aborted`，以 `error.status` 表示失败分类，以 `output_artifacts` 记录最终文件；完整度读取同一 record 内的 `acceptance.overall/content/asset`。

关键不变量如下：

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
- arXiv official HTML 系列集中使用 `paper_fetch.providers._arxiv_parsing.ARXIV_HTML_PARSER`，当前取 `choose_parser()`。必须重解析字符串片段的 AMS MathML script 例外保留在 provider DOM helper 内，并在代码旁注明原因。

<a id="extraction-stage-module-map"></a>

#### Extraction 阶段映射

`docs/extraction-rules.md` 中的受控阶段 token 与 canonical owner 的映射如下。新增提取 / 渲染规则时，优先把行为挂到这里列出的 owner；provider 层只做 publisher adapter，不新增平行 helper 入口。

| 阶段 token | Canonical module / owner | 规则范围 |
| --- | --- | --- |
| `metadata` | `paper_fetch.extraction.html._metadata`、provider metadata adapters、`paper_fetch.metadata.crossref` | 标题、作者、摘要、provider-owned 信号和 redirect stub lookup metadata。 |
| `provider-html-or-xml-extraction` | `paper_fetch.extraction.html.renderer`、provider HTML/XML adapters | publisher HTML/XML 到中间结构；adapter 传入 container、profile 与 postprocess，复用共享渲染。 |
| `html-cleanup` | `paper_fetch.extraction.html.cleanup_policy.CleanupPolicy`、`_runtime`、`inline`、provider cleanup policy | 站点 chrome、UI 噪声、caption fallback 和正文清洗。 |
| `availability-quality` | `paper_fetch.extraction.html.availability_policy.AvailabilityPolicy`、`paper_fetch.quality.html_availability`、`html_signals` | fulltext / abstract-only 判定、availability container cleanup、正文充分性度量。 |
| `section-classification` | `paper_fetch.extraction.section_hints`、`paper_fetch.extraction.html.semantics` | section kind、frontmatter、back matter、availability 与 section hints。 |
| `article-assembly` | `paper_fetch.models`、`models.builders`、`models.schema` | 中间结构合并成 `ArticleModel`。 |
| `asset-discovery` | `paper_fetch.extraction.html.assets`、`providers._html_asset_engine`、`extraction.html.figure_links`、`provider_rules`、provider asset policies | figure、table、formula、supplementary 资产候选识别。 |
| `asset-download` | `paper_fetch.extraction.html.assets.download` / `state` / `requester`、`providers.browser_workflow.fetchers`、provider asset clients | 资产候选下载、状态机、cookie-aware opener 和 provider-owned 下载链路。 |
| `asset-validation` | `paper_fetch.extraction.image_payloads`、`extraction.html.assets`、`models.Quality` | 真实图片校验、尺寸阈值、preview acceptance 和失败诊断。 |
| `asset-link-rewrite` | `paper_fetch.extraction.html.figure_links`、`extraction.html.object_links`、CLI / model asset link rewrite helpers | 远程 / 绝对资产链接改写为本地 Markdown 链接；按原 DOM 核验来源页对象链接。 |
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
- provider-owned DOM / Markdown 后处理通过 `ProviderHtmlRules.dom_hooks` / `markdown_hooks` 注册 typed callable。正文清理、资产发现与 availability 保持各自作用域，HTML/XML 规则不处理 PDF 转换结果。


### 7. Provider 层

入口：`src/paper_fetch/providers/`

- 各 provider 的 metadata / fulltext / asset 下载适配，以及 provider 格式到 `ArticleModel` 的转换
- 返回 typed provider result（`ProviderContent`、`ProviderArtifacts`、`ProviderFetchResult`），而不是用无类型 metadata 口袋回传内部状态

能力边界由 `paper_fetch.providers.protocols` 表达：`MetadataProvider`、`FulltextProvider`、`RawFulltextProvider`、`AssetProvider` 用于 workflow typing；`ProviderClient` 是 provider 可继承的 convenience base class。

provider fulltext 内部链路统一接收同一个 `RuntimeContext`：workflow 调用 `FulltextProvider.fetch_result()` 时传入 `artifact_store=` 与 `context=`，context 继续传给 raw fulltext、abstract-only recovery、related assets 和 `to_article_model`，使同一次 fetch 内可 memo 派生 payload 并复用 runtime browser。需要原始 payload 用 `fetch_raw_fulltext()`，需要完整结果用 `fetch_result()`。`RawFulltextPayload` 不提供 `metadata` 兼容视图；route、markdown_text、warnings、trace、diagnostics 等结构化字段必须由 typed fields 传入。`ProviderContent` 唯一持有正文 URL、类型、字节、合并 metadata 与本地复制状态；raw payload 上的同名扩展兼容属性只是投影，不保存副本。

provider 身份与能力配置统一来自 provider entry module 导出的 `PROVIDER_BUNDLE`。内置 provider entry 只由 `paper_fetch.providers._BUILTIN_PROVIDER_ENTRY_MODULES` 显式清单加载；固定 loader 在启动时一次构造按 status 排序的不可变 bundle tuple、provider map、`PROVIDER_CATALOG` 与 source map，并立即验证 provider name/status order/client factory/source 及 alias、DOI prefix、exact/suffix domain 无冲突。运行时没有 mutable registry、导入协调、cache invalidation、源码扫描或第三方 bundle 注入。routing、默认资产策略、MCP status 顺序和 client registry 都从这些不可变映射派生，不维护第二份 provider 行为字典。Crossref 的 provider adapter 是 `paper_fetch.providers.crossref.CrossrefClient`，与 resolve 共同依赖 `paper_fetch.metadata.crossref.CrossrefLookupClient`。

`compile_route_execution_policy()` 是 catalog 到 runtime 的唯一非授权执行策略边界。Catalog 合并并公开 exact/suffix/base、API/template/route host 供 routing 与诊断使用，但 `provider_request_policy()` 不把这些 host 或 catalog sensitive headers 自动接入 HTTP/PDF/body/supplementary allowlist；它投影 transport 实际读取的 timeout、transient/rate retry、QPS/minimum interval 与 rate-wait budget，并仅为 HTML/XML/PDF 正文 route 设置可选的 `body_access_provider`，供 HTTP 失败重试前检查同篇访问限制；资产与 metadata route 不启用该检查，也不从 cooldown 名称推断 provider。调用方显式提供的 `HttpRequestPolicy.allowed_hosts` / `SafeRemoteUrlPolicy.allowed_hosts` 仍逐跳 fail closed。minimum interval 通过每 scope 串行 start gate 执行；未显式提供 asset profile 时，compiled route 的 `asset_scope` 选择执行范围，acceptance owner 使用 compiled `acceptance_policy` 验证真实 representation。固定 catalog 的身份重叠直接拒绝，不保留未被内置 provider 使用的 priority/reason 豁免。

### 8. Runtime / Artifact / Cache 边界

`RuntimeContext` 是单次抓取的运行时 owner。根 context 拥有并关闭 transport，batch child 借用线程安全 transport 与不可变 env，独立持有 clients、session、CookieJar、预算、trace、timing、diagnostics、缓存和提交屏障。同名 client 并发只构造一次，工厂失败由占位 client 隔离。`BatchExecutionSession` 管理 child 所有权、规范 DOI 分组、representative 结果复制及取消屏障；去重仅限当前批次，每个输入仍有终态。

- `parse_cache` 按内容摘要、parser 与配置缓存派生结构；同 key supplier 原子执行一次，可变结果返回副本。`session_cache` 复用 resolution、metadata 与 landing probe 结果；缓存只存在于当前 context，不共享可变 DOM。
- browser provider 经 `browser_runtime` facade 使用受管 Byparr；Windows/Linux x64 选择 Invisible，macOS/ARM 选择 Camoufox。同出版社各阶段复用 context，每阶段管理自己的 page；浏览器对象绑定所属线程，在 worker 终态清理中先关闭 manager，外层再幂等关闭 session cache 和 transport。成功、失败与协作取消共用关闭路径，详见 [浏览器 runtime](../browser-runtime.md)。
- 异步取消先设置 cooperative event 与 commit fence，再等待有界 grace；重复取消不会跳过等待。未调度、重复输入及已运行 child 都会幂等关闭。
- `RuntimeContext.asset_budget` 是同篇所有二进制资产的共享边界；默认单文件 32 MiB、累计 256 MiB、64,000,000 像素，worker 还受 route cap 限制。流式读取、转换输出及临时 staging 共用 reservation；失败回滚，发布成功才 commit。具体资产候选与调度见 [provider 指南](../providers.md#资产调度与资源边界)。
- `ArtifactStore` / `DownloadPolicy` 管理 provider payload、Markdown、资产、诊断和 cache JSON。所有 writer 使用目标 path lock、同目录唯一 staging、flush/fsync 与原子 replace；取消 fence 与最终 replace 在同一临界区线性化。`overwrite=false` 时相同字节幂等，不同字节冲突；显式 overwrite 允许原子替换。
- `artifact_mode=all` 下失败页面保留隐私清洗后的 HTML 与诊断 JSON，manifest 对其记录 size/hash；不自动保存原始失败 HTML 或截图。逐资产 timing 属于资产结果，请求墙钟由调用方观察。

`FetchCache` 拥有 MCP fetch-envelope sidecar 的匹配和写入，`models.codec` 负责结构编码/解码并保持 wire shape；两者均不修复 PDF。当前 sidecar version 为 5，要求完整 acquisition。旧 sidecar 以 `version_mismatch` 失效并重新抓取，既有 Markdown 不删除。cache index 只信任显式注册且仍通过 DOI/hash/scope 校验的条目，不扫描文件名推断身份，也不自动迁移或修复。

`CapabilityScopeBuilder` 统一构造 credential scope。browser state 只在成功注入 context 后记录实际 use，绑定 provider、backend、canonical 路径及最终内容摘要；空配置不制造 private scope，状态后续消失也不降为 public。loader、inspector 和 compact projection 只查当前请求的精确 variant，再单向回退 canonical/public；public 与不同 private scope 不能横向读取。`get_cached(detail="compact")` 通过 `cached_request_matches()` 判断请求兼容，质量摘要复用统一 acceptance。

本地转换工具复用有界的探测、公式与 PDF 渲染缓存；缓存只减少重复调用，不改变转换输出。PDF 文本透传边界见 [PDF 规则](../extraction-rules.md#rule-pdf-conversion-boundary)。

### 9. Transport 层

入口：`src/paper_fetch/http/`

- HTTP 请求、连接复用与同 host 有界并发、进程内短 TTL GET 缓存、响应体大小限制、有限短重试、协作式取消检查

`HttpTransport` 保持 public request options、structured logs、cancel checks、`Retry-After` 最大等待和 `RequestFailure` 形状；瞬时错误与 429 retry policy 由 `urllib3.util.Retry` 表达，连接池由 `PoolManager(num_pools, maxsize, block=True)` 配置并按 hostname 复用。`SafeRemoteUrlPolicy` 在每个 redirect hop 检查 HTTP(S)、标准端口、无 userinfo、无 HTTPS 降级以及全部 DNS 答案均为公网地址，然后由共享 pool 按原 hostname 连接。跨 origin redirect 始终剥离 Authorization/Cookie/Proxy-Authorization/Referer；额外敏感 header 和 host allowlist 只有调用方显式放入 request policy 时才生效。HTTP cache 仅在当前进程内按请求 key、TTL、条数和总字节上限复用，不写磁盘、不做 conditional 304、reconcile 或 prune。

Route QPS 使用同一个 transport cooldown lock 与 scope 做跨 worker 原子时隙预留；服务端 `Retry-After` 与既有 minimum interval 总是取更晚 deadline。arXiv atom_metadata 与 source_assets route 分别使用独立 scope，在同一共享 transport 上各自至少间隔一秒，资产并发上限保持为 2，batch child context 共享该 transport 但不共享可变请求状态。

Fulltext provider identity evidence 保留 domain、publisher、DOI 的一致与冲突事实。DOI prefix 或两个独立信号一致才属于 strong；只有 strong provider 的 `NO_ACCESS` 能终止 provider waterfall，weak access boundary 会保留 diagnostics 后继续严格 identity-checked candidate。Acceptance 不用 title 证明 DOI-less identity；只有 DOI，或同时声明 URL、verified、unique 的 canonical landing fact，才会得到 `identity=resolved`。

两种平台引擎的 navigation、redirect、子资源与 service worker 使用浏览器原生行为；项目不安装 BrowserContext-wide URL/DNS interceptor，也不把带 cookie 或 storage state 的 context 绑定到单一 origin。Provider image/font/media 优化只在 page scope 按资源类型生效。Browser 资产恢复可以直接返回 browser-owned image/file/PDF bytes，再进入统一预算与 staging。

日志出口与 MCP bridge 使用同一递归 scanner，过滤 URL query/fragment、header map、query map 和文本中的标准/provider secret。MCP 只安装一个 ref-counted process-global router handler，当前 request target 存在 `ContextVar`，并显式传播到项目创建的 worker context。Target 自身用锁线性化 emit 与失效：bridge 退出会先将自己的 target 标记 inactive，再恢复 ContextVar、递减 handler 引用；因此保留 copied context 的迟到 worker 既不能写入已结束 session，也不能串到仍活跃的其它请求。Handler 在构造 notification coroutine 前同时拒绝 inactive target 与停止/关闭的 loop，重叠请求不会互收日志或乱序恢复 logger level。

### 10. CI / 回归验证边界

运行时 registry、公开入口与行为测试验证架构边界，不把私有模块布局或文档措辞当作契约。测试分层、命令与证据台账见 [测试说明](../../tests/README.md)，CI 与发布平台门禁见 [部署指南](../deployment.md#ci--github-actions)。

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

`resolve_paper()` 把 DOI / URL / 标题输入标准化成 `ResolvedQuery`，产出 `query_kind`、`doi`、`landing_url`、`provider_hint`、`candidates`、`title`。MCP structured `title` / `authors` / `year` 以结构化 request 进入 resolver：Crossref bibliographic search 只使用 title，authors 用 canonical author key 做独立相似度，year 从候选 `published` 字段提取后参与加权消歧。DOI cleanup 保留宽松输入清理后用 `idutils` 校验/规范化；标题候选用 token Jaccard + `rapidfuzz.fuzz.ratio` 评分，confidence threshold 和 ambiguity margin 控制。候选不够确定时保留 `candidates`，由上层返回 `ambiguous`，不猜测性继续抓取。

### 2. routing signal

路由优先级固定是 `domain > publisher > DOI fallback`，信号来源为 URL 域名、Crossref `landing_page_url`、Crossref `publisher`、DOI 前缀。`provider_hint` 表示最优提示，不是最终来源承诺。

### 3. metadata merge

workflow 按 catalog 能力取得 Crossref 与 provider metadata，再执行 primary / secondary
merge。事实源是 `paper_fetch.metadata.types.PRIMARY_SECONDARY_METADATA_MERGE_RULE`
和 `merge_primary_secondary_metadata()`：显式 blank primary scalar 阻止回填并输出
`None`，authors 使用 semantic author key 去重，keywords 按大小写无关文本去重，
`fulltext_links` 按 URL 去重，references 优先 DOI、否则 raw 文本去重。provider 内部
多层 enrichment 使用 `MetadataMergeRule` / `merge_metadata_layers()`，局部 DOI/author
规范化留在 adapter；arXiv 的延后 enrichment 和有序作者规则见 [provider 主路径](../providers.md#3-provider-全文主路径)。

### 4. provider fulltext

`workflow.fulltext` 调用获选 provider 的主路径。provider 自管 HTML/XML/PDF/browser
顺序，共享 `_waterfall` 负责步骤、warnings、失败聚合与 trace，`ProviderClient.fetch_result`
负责 raw payload、资产、文章和 artifact 组装。共享浏览器实现位于
`providers.browser_workflow`，publisher 差异由 profile callback 与 provider adapter 承载。

路由顺序、配置和公开来源统一见 [Provider 能力矩阵](../providers.md#provider-能力矩阵)
与 [全文主路径](../providers.md#3-provider-全文主路径)。只有强 provider 身份证据支持的同篇正文付费墙才停止后续候选、重试、PDF 和资产请求；只有已取得的摘要/元数据可用于降级。Elsevier API `NOT_ENTITLED` 仅终止该 API 路线，网页确认无权限才终止全文 waterfall。

### 5. abstract-only / metadata-only fallback

official provider 不可用时，只返回其自管的摘要结果或进入统一 metadata fallback，
不尝试通用 HTML 正文抓取；`preferred_providers` 控制允许进入的全文 provider。
未命中 official provider 时仍可解析 DOI / Crossref metadata。
`allow_metadata_only_fallback=true` 允许降级，否则抛 `PaperFetchFailure`；
PDF 已取得但无法转成 Markdown 时保留 PDF 来源和允许保存的 artifact。

metadata fallback 的 `has_fulltext=false`，`source_trail` 包含
`fallback:metadata_only`，public `source` 为 `metadata_only`；若 metadata 含摘要，
`content_kind` 可为 `abstract_only`。Crossref 仅作路由 signal 时不表示结果来自 Crossref；
作为元数据来源时 `ArticleModel.source` 可为 `crossref_meta`，降级 envelope 仍使用 `metadata_only`。
逐 provider 例外见
[回退语义](../providers.md#4-abstract-only--metadata-only-fallback)。

### 6. render / envelope / cache / MCP 暴露

拿到最终 `ArticleModel` 后，workflow.rendering 构造 `FetchEnvelope`，对外结果含 `trace: list[TraceEvent]`、与 trace 同步的兼容字段 `source_trail` 和 `warnings`。质量状态只由 `Quality` 实例持有；有 article 时 `FetchEnvelope.quality` 与 `ArticleModel.quality` 引用同一实例，envelope 顶层质量字段是兼容投影。随后 `ArtifactStore` 已处理 provider payload / HTML copy / asset 诊断；CLI adapter 决定是否写 Markdown、overwrite 和相对资源链接改写；MCP adapter 负责 `FetchCache` 复用/写入、credential scope、Markdown 注册和 inline images。两者都只通过 `FetchPipeline` 共享显式 context 下的 service 调用。

## 数据契约与角色边界

### `ResolvedQuery`

表达「输入被解析成什么论文候选」，为 routing 与 metadata 拉取提供标准化入口。不决定输出格式或正文抓取成功与否。

### `FetchStrategy`

表达「怎么抓」。最重要的字段是 `allow_metadata_only_fallback`、`preferred_providers`、`asset_profile`。它不决定返回哪些 payload（那是 `modes` 的职责）。

### `FetchEnvelope`

固定返回形状的公开抓取结果。始终承载 `doi`、兼容 `source`、可空的结构化 `acquisition`、`has_fulltext`、`warnings`、`source_trail`、`token_estimate`、`token_estimate_breakdown`；这些顶层质量字段保持公开 Python API 和 wire shape，但直接投影 canonical `quality`，不另存可变副本。按 `modes` 决定是否附带 `article` / `markdown` / `metadata`。无法从 provider 原点确认 acquisition 时保持 `null`，不做启发式补全。

MCP tool 与 sidecar 业务 payload 使用 `schema_version=2` 的 JSON-safe 形状；sidecar wrapper 版本与匹配规则见 [Runtime / Artifact / Cache 边界](#8-runtime--artifact--cache-边界)。reader 接受兼容的重复质量字段，并解码到单个 `Quality` 实例。失败时 `status` 是兼容客户端可读的粗粒度状态，细粒度失败原因放在 `code` / `error_category`，HTTP 与限流细节放在 `http_status` / `retry_after_seconds`。

### `ArticleModel`

表达 provider 已转换好的正文、资产、references 和质量诊断，并统一负责最终 Markdown 渲染的 token budget、资产附录、references 输出和质量 warnings。重要边界：

- `assets[*].render_state` 决定资产是否追加到尾部附录（`inline`/`suppressed` 不追加，`appendix` 可追加）；正文已内联图片按 URL/相对路径/后缀/basename 做等价比较避免重复渲染。
- HTML/XML 文章组装先改写已下载资产链接，再规范图片块边界和短 alt；caption 不进入 `![alt]`。PDF 正文只允许改写实际导出资产路径，保留转换器原始 alt、顺序与文本，见 [PDF 转换边界](../extraction-rules.md#rule-pdf-conversion-boundary)。
- structured metadata 进 front matter 前解开 HTML entity，避免 `&amp;` 泄漏。
- `assets[*].download_tier` / `download_url` / `content_type` / `downloaded_bytes` / `width` / `height` 是下载诊断，不应被下游丢弃。
- `quality.semantic_losses.table_layout_degraded_count` 表示源表 span/列定义异常导致布局无法可靠验证；合法合并单元格成功展开只记录规范化 reason，`table_semantic_loss_count` 才表示语义内容丢失。

### `provider_status`

在抓取前报告本地环境是否就绪。本地检查边界与各 provider check 名称以 [`../providers.md`](../providers.md#provider-status-local-boundary) 为准；IEEE 的 direct 路线与可选 `browser_fallback` 分开报告。

`paper_fetch.diagnostics` 是 CLI `doctor` 与 MCP `provider_status` 的共享 owner：provider/group/detail 筛选先由 catalog-backed schema 校验，随后只构建目标 provider 的静态状态。full 报告复用 `config.resolve_runtime_env()` 的来源元数据、`browser_preflight.static_browser_capabilities()` 的非 live 浏览器能力和 `image_tools.probe_image_conversion_backends()` 的本地可执行文件探测；compact 只保留路由字段。该层可以构造 transport 供 provider client 保持原接口，但禁止调用 transport、启动/连接浏览器或检查远端页面。

CLI 与 MCP live 入口都以 `paper_fetch.browser_preflight.run_browser_provider_preflight()` 为唯一 orchestration owner；`paper_fetch.mcp.browser_preflight` 只做 Pydantic 入参、状态分类、progress/cancel 转接和 JSON-safe structured output。共享核心串行保留逐 provider 结果，把 `RuntimeContext.cancel_check` 传入现有 browser HTML bootstrap，并通过 `BrowserRuntimeConfig.persist_storage_state` 控制是否保存；不得复制 provider workflow 或转入 PDF fallback。

诊断语义分三层：`provider_status` / `doctor` 只证明静态配置与本地依赖；CLI `browser-preflight` / MCP `browser_preflight` 才证明一次真实样例页面链路并可能写 storage-state；auth 是明确的人工副作用入口。三层结果不得相互冒充。

### `has_fulltext`

区分两个层面：`fetch_paper().has_fulltext` 是完整抓取瀑布后的最终 verdict；MCP 的 `batch_check(queries=[query])` 是只用更弱信号的廉价 probe，`mode` 默认且仅允许 `"metadata"`。真实批量抓取使用 `batch_fetch` 并读取 acceptance。两者不要求逐案完全一致（见 [`probe-semantics.md`](probe-semantics.md)）。

## 输出与可观测性

- **`warnings`** 常见内容：abstract-only / metadata-only 降级、HTML / provider fallback 提示、资产部分下载失败、preview 资产可接受降级或不可接受 fallback、表格版式降级 / 语义丢失、公式 fallback / missing、token 截断。
- **`source_trail`** 常见轨迹：`resolve:*`、`route:*`、`metadata:*`、`fulltext:*`、`fallback:*`、`download:*`。
- **`token_estimate_breakdown`** 拆成 `abstract` / `body` / `refs`，帮 host 决定是否截断、哪段最占预算、是否改 metadata-only / summary-first。
- **MCP cache tools**：`list_cached` / `get_cached` 在显式 `download_dir` scope 内查询索引与条目。`FetchCache` 匹配 `prefer_cache=true` 请求（按 modes、strategy、`include_refs`、`max_tokens`、sidecar version 和 `EXTRACTION_REVISION` 复用本地 fetch-envelope）；cache 不镜像为动态 MCP resources。

## 扩展点：新增能力时应改哪一层

- **新增 provider**：主要改 `src/paper_fetch/providers/`，必要时更新 provider-specific extraction / metadata adapter；entry module 导出 `PROVIDER_BUNDLE` 并加入固定模块清单，不手工编辑 `provider_catalog.py`、`provider_rules.py`、`quality/html_signals.py` 或 `quality/html_availability.py`，也不把 provider 逻辑塞进 CLI / MCP。
- **新增 MCP surface**：主要改 `src/paper_fetch/mcp/`（`schemas.py`、`fetch_tool.py`、`cache_payloads.py`、`batch.py`、`batch_fetch.py`、`server.py`）；需要真正的新抓取逻辑要先落到 service / workflow 层。批量抓取入口复用 `workflow.batch_runner`、`manifest.build_manifest_record` 与 `manifest_writer.serialize_manifest_record`，最终 JSONL 由 `ArtifactStore.write_text_file` 原子写入。
- **新增渲染能力**：正文渲染或资产展示能力优先改 `src/paper_fetch/models/` 与 provider 到 `ArticleModel` 的转换，而不是让 CLI / MCP 自己拼装业务结果。

## 相关文档

- [`../../README.md`](../../README.md)
- [`../providers.md`](../providers.md)
- [`../deployment.md`](../deployment.md)
- [`probe-semantics.md`](probe-semantics.md)
