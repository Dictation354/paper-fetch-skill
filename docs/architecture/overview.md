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
- 通过 `FetchPipeline` 创建/关闭 `RuntimeContext` 并调用 service 层
- 控制 stdout / stderr / 输出文件 / 退出码

不负责 provider 选择、正文抓取策略、MCP 序列化。

### 2. MCP 层

入口：`src/paper_fetch/mcp/`（`server.py`、`fetch_tool.py`、`cache_payloads.py`、`batch.py`、`results.py`、`log_bridge.py`）

- 暴露 MCP tools、prompts 与 resources，校验工具参数
- 把 service 结果序列化成 JSON-safe payload
- 通过 `FetchCache` 管理 fetch-envelope sidecar / cache resources
- 通过 `FetchPipeline` cache hooks 复用 CLI/MCP 共享的 fetch lifecycle
- 管理 progress、structured log、cancellation

实现边界：

- MCP runtime 基于官方 Python SDK 2.x 的 `MCPServer` 与 stdio transport，不再维护自定义 stdin reader/stream pump；server 同时服务 2025 握手协议与 2026-07-28 无状态协议，动态 resource 变更在旧协议走 `notifications/resources/list_changed`，在新协议走 `subscriptions/listen` bus。
- payload/tool 入口通过 `paper_fetch.mcp._deps.MCPDeps` 显式注入 runtime env、service、provider registry 与 cache index 依赖；生产默认由 `default_mcp_deps()` 装配，测试通过构造定制 deps 注入。
- 所有 MCP tool JSON payload 顶层都带 `schema_version=2`；错误 payload 保留兼容字段 `status` / `reason`，并补充 `code`、`http_status`、`error_category`、`retry_after_seconds`、`provider`、`warnings`、顶层唯一完整 `trace` 和 `source_trail` 供 host 做机器判断。v2 的 `quality` 不再复制完整 trace。
- MCPServer/Pydantic 仍生成并保留完整 typed output contract；注册工具时只从发布到 `tools/list` 的 output schema 移除展示性 `title` 注解和可选字段的 `default: null`。压缩器识别 `properties`、`$defs` 等命名 schema 映射，真实的 `title`/`default` 字段名与全部验证约束保持不变。
- `resource://paper-fetch/provider-catalog` 由轻量 MCP catalog adapter 在读取时直接投影 runtime `ProviderSpec` 和 `SOURCE_PROVIDER_MAP`；provider/source、browser/runtime、status/preflight 与资产默认不在 server instructions、tool description 或 skill contract 中维护第二张静态表。
- MCP 上下文有独立回归预算：server instructions 不超过 1500 字符，`fetch_paper` description 不超过 1200 字符，全部 tool description 合计不超过 5000 字符，`tool_count * instructions_length + descriptions_length` 宿主 narrative 不超过 24000 字符。Native tools/list 总字节和 input/output schema 字节分别快照，新工具需单独说明并更新基线，不把 schema 体积混入文案预算。十工具契约在压缩展示性 output-schema 元数据、同时保留命名字段后的基线分别为 `69459` / `65961` bytes，当前 instructions/fetch description/全部 descriptions/host narrative 为 `1093/985/2601/13531` 字符。
- `fetch_paper` 和批量工具把阻塞抓取放到有界 `ThreadPoolExecutor`，事件循环继续处理 progress / log / cancellation；批量工具保持输入顺序，遇到 rate-limit status/code/category、HTTP 429 或 retry-after 后停止对应 provider/resource lane 的新提交。
- async `fetch_paper` 用 `RuntimeContext(cancel_check=...)` 创建 cancel-aware `HttpTransport`，service/workflow 只消费 transport。

不负责 provider 路由决策、正文抓取瀑布、Markdown 转换细节。

### 3. Skill 层

入口：`skills/paper-fetch-skill/`

- 告诉 agent 什么时候调用哪些 MCP 工具，提供薄说明和引用文档

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
- `pipeline`：CLI/MCP 共享的 `RuntimeContext` 生命周期、service 调用、可选 cache hook 与 Markdown 保存 hook
- `request_builder`：CLI/MCP 共享的 `FetchPipelineRequest` 装配

#### 增量 batch runner 与 provider lane

`paper_fetch.workflow.batch_runner` 是面向 CLI/MCP 的共享批量调度状态机，新增批量入口必须复用它。单项 worker 仍按 resolution → metadata/routing → fulltext → rendering 的阶段顺序执行；runner 只在同一批的项之间提供受控并发，不把单篇抓取的阶段拆散或乱序。现有 MCP batch 和 CLI batch 都复用这一 runner；执行面 adapter 只负责把共享终态转换为各自的 response 或 manifest record。

- 全局 worker 与每个 provider/resource lane 的并发上限都限制在公开范围 `1..8`。runner 最多只维持全局上限数量的 in-flight future，并在每次完成后增量扫描未提交输入；某个 lane 暂时占满时，其他可运行 lane 不会被队首阻塞。
- lane key 由调用方在调度前提供。worker 通过结构化 failure/result classifier 报告既有 `rate_limited` reason code 和可选 `retry_after_seconds`；runner 不解析 warning 文案。观察到限流后，该 lane 在本次 run 内不再提交新项，并用可注入的单调 clock 记录 `limited_at`、解析后的 cooldown 与 `cooldown_until`；其他 lane 继续运行。本模块不跨 run 学习或维护全局限流服务。
- `BatchRunResult.results` 始终按输入 index 排列且每项只有一个终态；真实完成、worker 异常、协作式取消以及从未提交的项分别表示为 `succeeded`、`failed/rate_limited`、`cancelled` 和 `not_scheduled`。`completion_events` 与 completion/progress callback 独立保留终态被观察到的顺序，流式消费者不能把它误当输入顺序。
- stop predicate 或 cancel event 只阻止新的增量提交；已在途 worker 依靠 `RuntimeContext.cancel_check` 协作退出。取消超过宽限期且仍有 pending worker 时，runner 只调用一次显式 escalation callback 关闭共享 browser manager，随后仍等待 worker 收敛。worker 已观察到的异常和取消、以及因 stop/cancel/lane cooldown 未调度的输入，都会生成结构化终态，避免批次尾部静默丢失。
- 每个终态（包括 `not_scheduled`）依次触发一次 completion callback 和一次 progress callback；两者都可同步或异步。callback 是观察者：异常写入 `BatchRunResult.callback_failures`，不覆盖 item 终态，也不隐式改变停止策略；需要把 callback 失败升级为 run 失败的 adapter 必须显式检查该字段。callback 内设置 cancel event 会在下一次增量提交前生效。

现有 MCP `batch_resolve` / `batch_check` / `batch_fetch` 与 CLI batch 都通过这个 runner 调度。前两个 probe/resolve 工具保持既有兼容调度；`batch_fetch` 在提交前只调用 catalog-backed URL/DOI 身份 helper 推断 provider lane，一个 lane 限流后把该 lane 的后续输入终态化为未调度，其他 lane 继续。它的 `results` 按原 1-based input index 返回，`completion_order` 单独投影完成顺序，progress 使用完整终态计数。

`RuntimeContext` 是 service/workflow 的显式运行时依赖容器，持有 `env`、`transport`、`clients`、`download_dir`、`cancel_check`、`artifact_store`、可选 `fetch_cache`，以及单次 fetch 生命周期内的 `parse_cache`、`session_cache` 和 `stage_timings`。Browser provider 只依赖 `paper_fetch.providers.browser_runtime` facade；生产 backend 是 Camoufox，storage/profile 路径由 `browser_runtime.paths` 统一解析。同一 owning thread 在一个 `RuntimeContext` 内复用 Camoufox process，每项操作创建隔离 context/page，batch/进程退出时统一清理。公开 service API 只接受 `context=`；调用方必须先构造 `RuntimeContext`，再交给 `paper_fetch.workflow.pipeline.FetchPipeline`。

#### 统一抓取验收模型

`paper_fetch.workflow.acceptance` 是 CLI、MCP、cache 和 manifest 唯一可复用的抓取验收语义。`evaluate_fetch_acceptance()` 是纯函数：它只消费 `FetchEnvelope` / 结构化失败 code、请求的 `asset_profile`、请求输出集合和可选的 `AssetAcceptanceSummary`，不联网、不访问或写入文件，也不重新运行 provider 质量判断。文件存在性、hash、MIME 等 I/O 事实由外层 adapter 收集后再以结构化事实传入；验收层不解析 warning 文案。

`FetchAcceptanceReport` 固定包含七个分面：

| 分面 | 事实与边界 |
| --- | --- |
| `overall` | 稳定枚举 `complete`、`degraded`、`limited`、`failed`、`action_required`。 |
| `identity` | 归一化 DOI、期望 DOI、标题、候选数和 `resolved/ambiguous/mismatch/unavailable`；DOI 归一化复用 `publisher_identity.normalize_doi()`。 |
| `fetch` | `ok` 只表示调用已完成；歧义、无访问权限或配置缺失是 `action_required`，其他未产出 envelope 的错误是 `failed`。 |
| `content` | 只使用 `fulltext`、`abstract_only`、`metadata_only`、`unavailable`，同时保留 `has_fulltext`、`has_abstract`、confidence 和 flags。表格布局降级、表格语义损失、公式 fallback/missing 保持独立计数。 |
| `asset` | 显式记录 profile、`requested`、本地/远程、full-size、preview、failure、placeholder suspected 和 not-archived。`asset_profile=none` 必须得到 `requested=false/status=not_requested`，未完成 fetch 时已请求资产是 `unavailable`；仍保留的远程链接由 `remote_link_count`、`remote_only_count` 和 `remote_links_preserved` 单独表达，不是假失败。 |
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

验收 schema 当前为 v2。每份报告都必须序列化 `schema_version=2` 和 `minimum_reader_schema_version=2`。v2 增加 `accepted_preview`、`fallback_preview` 与稳定 `issue_codes`，并要求 `preview == accepted_preview + fallback_preview`；reader 可忽略未知 additive field，但缺少版本、v1 或未来不支持的版本必须拒绝，不能猜测迁移。`FetchAcceptanceReport.model_json_schema()` / `fetch_acceptance_json_schema()` 是 JSON Schema 唯一生成入口。

`FetchEnvelope.trace` 是一次 fetch 的唯一完整 trace owner。provider/waterfall 先在局部列表累积事件，workflow 最终只写入 envelope 一次；`Quality` 仅保留去重后的 article source-trail 摘要。acceptance、manifest 与 MCP 都只投影 envelope 顶层 trace，两个不同 attempt 的同 code 会保留为两条真实事件。旧 v1 FetchEnvelope cache 读取时按“顶层 trace → quality.trace → article.quality.trace”提升一次，新写入统一为 v2 且只写顶层。

#### 版本化 manifest record

`paper_fetch.manifest` 是单篇 CLI、CLI batch 和 MCP `batch_fetch` 共用的 manifest record owner。adapter 只向 `build_manifest_record()` 提交原 query、JSON-safe 请求参数、`FetchEnvelope` 或结构化 error、输出文件声明和 run/index/attempt；schema 字段、兼容字段、验收摘要、trace 与文件快照均由 builder 统一派生。builder 保持纯逻辑，不写 JSONL、run manifest 或任何输出文件，也不执行 audit/resume。

manifest record schema 当前为 v2，`schema_version=2` 和 `minimum_reader_schema_version=2` 都是必填常量。v2 是旧无版本 CLI JSONL 的首个版本化超集，仍在 record 顶层保留原九字段 `index/query/status/doi/source/output_path/saved_markdown_path/warnings/error`；`legacy_projection()` 可以直接返回且只返回这九个字段，CLI/MCP 不应各自维护兼容字段表。旧 `status=ok` 仍只表示调用未抛异常，完整度必须读取同一 record 内的 `acceptance.overall/content/asset`。

其余关键不变量如下：

- `index` 与 `attempt` 都从 1 开始；`run_id`、`record_id`、带时区的开始/结束时间、clock 与 UUID factory 均可注入；默认 clock 与 artifact mtime 使用 UTC。
- `request_fingerprint` 是原 query 和 JSON-safe request parameters 的 canonical JSON SHA-256；对象键顺序不会改变 fingerprint，数组顺序会保留。
- `identity`、`doi`、`source`、`fallback_codes`、`warning_codes`、`failure_codes`、`semantic_losses` 和 `asset_summary` 都直接来自 `FetchAcceptanceReport`，不会重新按 warning/message 文本分类。原 warning 文本只为兼容和人工诊断原样保留。
- `trace` 由既有 `TraceEvent` 或兼容 `source_trail` marker 转换；message 只是说明文字，不参与 fallback/warning/failure 分类。
- 每个 `output_artifacts[*]` 记录 path、kind、size、SHA-256、mtime、record completion time 和 `verified/missing/unreadable` 快照状态。stat 与 hash reader 可注入，builder 只读文件，不落盘。
- artifact facts 表示 record 完成时观察到的状态，不证明文件现在仍存在或内容未变。当前文件状态必须由只读 audit/reconcile 重新 stat/hash 后判断，禁止把历史 `verification_status=verified` 当作持续有效的文件锁或 resume 依据。

打包资源 `paper_fetch.resources.manifest/manifest-record-v2.schema.json` 是对外稳定的 Draft 2020-12 schema；测试要求它与 `generated_manifest_record_json_schema()` 同步并能验证真实 round-trip payload。v2 reader 忽略 additive unknown fields；删除字段、改变必填性/含义或收窄既有值域属于不兼容变更，必须提升 manifest schema version，不能覆盖 v2 资源或猜测迁移。缺少版本、fingerprint 或违反派生字段一致性的 record 必须拒绝。

#### Run persistence、只读审计与恢复

`paper_fetch.manifest_writer` 是 durable manifest persistence 和只读审计的 owner，复用 `paper_fetch.manifest` 的 v2 record 与 `workflow.acceptance` 的质量事实，不建立第二套 record 或验收模型。`RunManifestStore` 原子维护 schema-v1 `run-manifest.json` 摘要；`ManifestJsonlWriter` 以 append-only JSONL 持久化 attempts。摘要包含完整有序输入、run 级 request fingerprint、工具版本、事件文件引用、时间、attempt 数和按最新 attempt 汇总的状态计数。

run 状态机为 `running -> completed|interrupted|cancelled|failed`。每个终态 event 先 flush/fsync，再原子 checkpoint 摘要；异常路径尽力写入对应终态而不掩盖原始异常。`index` 始终绑定有序输入，`attempt` 必须是每个 index 的连续 `1..N`；`record_id` 由 run/index/attempt 确定，因此完成顺序乱序不影响重建。run lock 串行化同一 run 的新建和恢复，artifact path lock、同目录 `.part` 与 `os.replace` 保护最终输出及 JSON 摘要；默认拒绝覆盖，调用方必须显式声明 overwrite。

`audit_manifest_path()` 同时接受 run 摘要和单篇 v2 manifest，全程只读且无网络。它校验 run/input/index/attempt/record id/request fingerprint/计数结构，并重新读取当前 artifact 的存在性、size、SHA256 和通过 PF-005 YAML helper 解析的 Markdown front matter DOI/source/content，再结合 record acceptance 判断是否可复用。稳定结果为 `ok`、`manifest_stale` 或 `invalid`；CLI 将其映射到退出码 `0/1/2`。`audit` 与 `reconcile` 当前共享同一审计引擎，二者都不修复或改写状态。

CLI 和 MCP `batch_fetch` resume 都必须提交原有序输入、同一工具版本和完全相同的关键请求参数。只有 audit 标记为 reusable 的最新 attempt 会被跳过；missing、stale、失败或低于请求质量的项进入共享 batch runner 并追加下一 attempt。输入或 fingerprint 变化、结构无效会在任何 run mutation 前拒绝；仍存在的 stale 输出必须显式 overwrite，已经缺失的输出可以安全重建。MCP adapter 只在显式 `run_manifest` / `batch_results` / `resume` 时创建 durable 状态；默认内存 run 保留相同 record/run fingerprint 但不写盘。取消和适配层异常分别尽力终态化完整 index 集合并写 `cancelled` / `interrupted`，不复制 persistence 状态机。

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
- availability verdict、reason code 集中在 `paper_fetch.quality.reason_codes` 与 `paper_fetch.reason_codes`；`models.schema.ContentKind` 保持显式 Literal 作为 public wire contract。
- provider-owned browser workflow 的 DOM / Markdown 后处理只能通过 `ProviderHtmlRules.dom_hooks` / `markdown_hooks` 的 typed callable 注册，不得恢复字符串 stage dispatch 或反射表。

### 7. Provider 层

入口：`src/paper_fetch/providers/`

- 各 provider 的 metadata / fulltext / asset 下载适配，以及 provider 格式到 `ArticleModel` 的转换
- 返回 typed provider result（`ProviderContent`、`ProviderArtifacts`、`ProviderFetchResult`），而不是用无类型 metadata 口袋回传内部状态

能力边界由 `paper_fetch.providers.protocols` 表达：`MetadataProvider`、`FulltextProvider`、`RawFulltextProvider`、`AssetProvider` 用于 workflow typing；`ProviderClient` 是 provider 可继承的 convenience base class。

provider fulltext 内部链路统一接收同一个 `RuntimeContext`：workflow 调用 `FulltextProvider.fetch_result()` 时传入 `artifact_store=` 与 `context=`，context 继续传给 raw fulltext、abstract-only recovery、related assets 和 `to_article_model`，使同一次 fetch 内可 memo 派生 payload 并复用 runtime browser。需要原始 payload 用 `fetch_raw_fulltext()`，需要完整结果用 `fetch_result()`。`RawFulltextPayload.metadata` 只作 read-only compatibility view；route、markdown_text、warnings、source_trail、diagnostics 等结构化字段必须由 typed fields 传入。

provider 身份与能力配置统一来自 provider entry module 顶部注册的 `ProviderBundle`：各入口导入时调用 `register_provider_bundle(ProviderBundle(...))`，`_registry.py` 只负责保存与查找。`paper_fetch.provider_catalog.PROVIDER_CATALOG` 与 source map 是 bundle discovery 的懒加载视图；根 `paper_fetch` import 不导入 provider entries 或 HTML 重依赖。内置 provider entry 由 `paper_fetch.providers` 的显式清单管理，额外 public entry file 只在 AST 看到真实 `register_provider_bundle(...)` 调用时才纳入，并按 provider 文件指纹缓存 discovery，避免注释/docstring 误触发和重复读盘。routing、默认资产策略、MCP status 顺序和 registry 都从 discovered bundle 派生，新 provider PR 不手工编辑静态字典。Crossref 的 provider adapter 是 `paper_fetch.providers.crossref.CrossrefClient`，与 resolve 共同依赖 `paper_fetch.metadata.crossref.CrossrefLookupClient`。

### 8. Runtime / Artifact / Cache 边界

入口：`src/paper_fetch/runtime.py`、`artifacts.py`、`mcp/fetch_cache.py`

- `RuntimeContext` 显式承载运行时依赖；`parse_cache` 是进程内、单 context 生命周期的解析 memo（key 含 provider、role、source、body sha256、parser 和配置指纹），访问器由 `RLock` 保护，`get_or_set` 对同 key 原子执行一次 supplier，dict/list 读取返回拷贝，XML root 只读复用。
- Browser runtime 使用 backend facade 和集中 storage-state manager；auth、preflight、HTML fetch、seeded PDF fallback 共享 provider-scoped `storage-state.json` 路径、写锁和 atomic write。preflight 的唯一状态契约为 `ready/challenge/auth_required/network_timeout/extraction_error/runtime_error/cancelled`，CLI/MCP 共用核心 reason-code 分类和 next action。managed Chrome stderr 使用有界脱敏尾部，启动、CDP 连接、context 和 page 阶段分别发布稳定 code，preflight、provider trace、manifest 与 PDF fallback acceptance 保留同一结构化失败事实。Browser-backed image fetch 对单图 seed warm、page fetch、request-context fetch、直接导航和 image wait 共用一个 wall-clock budget；PDF fallback 只用 lightweight browser warm 采集 cookies/user-agent/final URL，已有 cookie seed 时不再对同一 seed URL 做第二次 browser navigation。External CDP 默认借用既有 context，并在 diagnostics 中报告被忽略的 context options；`PAPER_FETCH_CDP_EXTERNAL_NEW_CONTEXT=1` 可要求在外部浏览器中创建新 context。
- `artifact_mode=all` 下，已到达页面但 extraction/availability 失败的 HTML route 会在 `diagnostics/<provider>/<doi-or-url-digest>/<route>-<attempt>/` 保存 `diagnostic.json` 与隐私清洗后的 `page-sanitized.html`。自动流程不保存原始失败 HTML 或截图；query、userinfo、email、表单、脚本及事件属性会被删除/脱敏，2 MiB 上限只在 DOM 节点边界截断。成功或终态失败的 CLI/MCP manifest 都把这些文件作为 `kind=diagnostic` additive artifact 快照保存 size/SHA-256。
- `RuntimeContext.stage_timings` 使用独立 monotonic 计时器记录 browser、DOM readiness、HTTP、retry、asset、formula 与 render；golden live 报告另保留总耗时，并按 `provider + route + stage` 聚合。单样本只输出 observed duration，至少两个样本才复用 tracing 的 nearest-rank 算法输出 p50/p95，禁止从 trace duration 求和。
- 本地转换工具链使用进程内有界缓存降低重复探测：Ghostscript/libvips 候选路径、`--version` probe 和工具 env overlay 按相关 env/目录/文件指纹失效；公式转换保留 MathML 结果缓存和 `mathml-to-latex` worker 复用；PDF fallback 对无图片导出路径的同一 PDF hash 复用 Markdown 渲染结果，并在成功结果 diagnostics 中记录 hash、字节数、页数、cache status 和耗时。
- `ArtifactStore` / `DownloadPolicy` 管理 artifact mode：provider PDF/binary local copy、PDF fallback 源文件、provider 原始 HTML、Markdown 保存、asset 诊断、HTTP textual cache 开关，以及 fetch-envelope/cache-index JSON 的原子写入。
- `FetchCache` 管理 MCP fetch-envelope sidecar reuse/write 语义与 cache index refresh；当前 sidecar version 为 5，并要求完整 acquisition，缺少该事实的 v4 sidecar 以 `version_mismatch` 失效后重新抓取，不删除既有 Markdown。sidecar version、`EXTRACTION_REVISION` 校验、resource URI 与 scoped cache resource 语义稳定，实际 JSON materialization 委托给 `ArtifactStore`。MCP cache index 读取会校验 `INDEX_VERSION`；旧版/坏 schema 默认拒绝作为可信 manifest，`list_cached(cache_mode="index")` 只读 manifest，`refresh` 只校验/修剪现有 manifest，`rescan` 只从可证明 DOI 归属的 fetch-envelope sidecar 重建。`get_cached(detail="compact")` 仍由该 facade 读取确定性 sidecar：请求兼容唯一调用 `cached_request_matches()`，质量摘要调用统一 `evaluate_fetch_acceptance()`，request fingerprint 复用 manifest canonical hash；adapter 只裁剪 full/preferred/compact 视图，不复制匹配或验收规则。查询先使用当前 runtime 的摘要化 `credential_scope`；带凭据 scope 在精确 sidecar 缺失或 scope 不匹配时可安全复用 public sidecar，public scope 绝不反向读取 API token 或 storage-state sidecar。

### 9. Transport 层

入口：`src/paper_fetch/http/`

- HTTP 请求、连接复用与同 host 有界并发、进程内短 TTL GET 缓存与可选磁盘 textual GET 缓存、响应体大小限制、有限短重试、协作式取消检查

`HttpTransport` 保持 public request options、structured logs、cancel checks、`Retry-After` 最大等待和 `RequestFailure` 形状；瞬时错误与 429 retry policy 由 `urllib3.util.Retry` 表达，连接池由 `PoolManager(num_pools, maxsize, block=True)` 配置。磁盘 textual GET 缓存使用脱敏 cache key（敏感 header 用短 SHA-256 digest 区分凭据且不落原文），默认按 `4096` 条、`512 MiB`、`30` 天清理，三项上限可用环境变量独立覆盖。内部子模块：`transport.py`（request loop / pool / semaphore / log）、`cache.py`（cache key / digest / memory+disk cache / stats / prune）、`retry.py`（retry policy / backoff）、`body.py`（读取 / 解压 / content-type / preview）、`errors.py`（异常类型）。`paper_fetch.http` 是兼容 facade。

### 10. CI / 回归验证边界

`.github/workflows/ci.yml` 是普通 CI 命令事实来源：`push` / `pull_request` 运行完整 unit branch coverage、integration、devtools、Ruff、完整生产包 mypy、复杂度、provider route/catalog/manifest/fixture/docs 治理、抽取规则、版本与依赖漏洞门禁，并对 Python 3.11 与 3.14 分别执行 core unit boundary 和 core/full wheel smoke；隔离 wheel smoke 还会校验安装出的 MCP SDK 主版本为 2 并可构建 `MCPServer`。provider governance 的 runtime 快照与自动路由文档由 `scripts/check_provider_governance.py --update` 生成，正常 CI 只校验，不自动改文件。CI 与本地 unit / integration / devtools 默认复用 `pyproject.toml` 的 `pytest-xdist` 并行配置，不传 `-n 0`。依赖刷新、离线构建和稳定发布各自位于独立 workflow；重型 offline/release 只在 `v*` tag 或手动 `workflow_dispatch` 路径运行。Live publisher/MCP、provider drift 与完整 golden corpus 仅保留本地显式入口，GitHub Actions 和 PR 都不接触这些外部状态或完整回放。只有 live provider、共享真实 publisher/API 状态或专门排查顺序问题的测试可串行，并在命令旁说明原因。

架构边界由测试强制，而非仅靠文档约定：`tests/unit/test_import_boundaries.py` 阻止 provider-neutral 层 import `providers._*` 与 compat module，`tests/integration/test_architecture_closeout.py` 锁定 service facade、magic-key 契约、import-cycle 和兼容表面边界。更新提取规则文档后先运行 `python3 scripts/validate_extraction_rules.py`，再按变更范围运行并行 unit / integration。

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

拿到最终 `ArticleModel` 后，workflow.rendering 构造 `FetchEnvelope`，对外结果含 `trace: list[TraceEvent]`、与 trace 同步的兼容字段 `source_trail`、聚合到 `ArticleModel.quality` 与 `FetchEnvelope` 的 `warnings`。随后 `ArtifactStore` 已处理 provider payload / HTML copy / asset 诊断；CLI 决定是否写 Markdown、是否改写相对资源链接（通过 `FetchPipeline` 的 `MarkdownSaveSpec` 执行）；MCP 通过 `FetchCache` hooks 决定是否复用/写入 sidecar、暴露 resources、附带 inline images。

## 数据契约与角色边界

### `ResolvedQuery`

表达「输入被解析成什么论文候选」，为 routing 与 metadata 拉取提供标准化入口。不决定输出格式或正文抓取成功与否。

### `FetchStrategy`

表达「怎么抓」。最重要的字段是 `allow_metadata_only_fallback`、`preferred_providers`、`asset_profile`。它不决定返回哪些 payload（那是 `modes` 的职责）。

### `FetchEnvelope`

固定返回形状的公开抓取结果。始终承载 `doi`、兼容 `source`、可空的结构化 `acquisition`、`has_fulltext`、`warnings`、`source_trail`、`token_estimate`、`token_estimate_breakdown`；按 `modes` 决定是否附带 `article` / `markdown` / `metadata`。`source` 不因新增字段改值；无法从 provider 原点确认 acquisition 时保持 `null`，不做启发式补全。

MCP tool 返回的是在业务 payload 顶层追加 `schema_version=2` 的 JSON-safe 形状；FetchEnvelope sidecar 新写入也使用 v2，但两者仍是不同契约。失败时 `status` 仍是旧客户端可读的粗粒度状态，细粒度失败原因放在 `code` / `error_category`，HTTP 与限流细节放在 `http_status` / `retry_after_seconds`。

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
- **MCP cache resources**：默认共享缓存索引与条目，显式 `download_dir` 时有 scoped cache resources。`FetchCache` 匹配 `prefer_cache=true` 请求（按 modes、strategy、`include_refs`、`max_tokens`、sidecar version 和 `EXTRACTION_REVISION` 复用本地 fetch-envelope），只在 fetch 实际使用下载目录或 Markdown 保存成功落盘后刷新 resources。

## 扩展点：新增能力时应改哪一层

- **新增 provider**：主要改 `src/paper_fetch/providers/`，必要时更新 provider-specific extraction / metadata adapter，并在 provider entry module 顶部注册 `ProviderBundle`；不要手工编辑 `provider_catalog.py`、`provider_rules.py`、`quality/html_signals.py` 或 `quality/html_availability.py`，不要把 provider 逻辑塞进 CLI / MCP。
- **新增 MCP surface**：主要改 `src/paper_fetch/mcp/`（`schemas.py`、`fetch_tool.py`、`cache_payloads.py`、`batch.py`、`batch_fetch.py`、`server.py`）；需要真正的新抓取逻辑要先落到 service / workflow 层。新的批量抓取入口必须继续复用 `workflow.batch_runner`、`manifest.build_manifest_record` 和 `manifest_writer.RunManifestStore`。
- **新增渲染能力**：正文渲染或资产展示能力优先改 `src/paper_fetch/models/` 与 provider 到 `ArticleModel` 的转换，而不是让 CLI / MCP 自己拼装业务结果。

## 相关文档

- [`../../README.md`](../../README.md)
- [`../providers.md`](../providers.md)
- [`../deployment.md`](../deployment.md)
- [`probe-semantics.md`](probe-semantics.md)
