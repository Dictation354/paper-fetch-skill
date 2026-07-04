# Paper Fetch Skill 架构与业务流程

Date: 2026-06-18

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

- stdio transport 用后台 stdin reader + async stream pump，避免同步 stdin 阻塞事件循环。
- payload/tool 入口通过 `paper_fetch.mcp._deps.MCPDeps` 显式注入 runtime env、service、provider registry 与 cache index 依赖；生产默认由 `default_mcp_deps()` 装配，测试通过构造定制 deps 注入。
- 所有 MCP tool JSON payload 顶层都带 `schema_version=1`；错误 payload 保留兼容字段 `status` / `reason`，并补充 `code`、`http_status`、`error_category`、`retry_after_seconds`、`provider`、`warnings` 和 `source_trail` 供 host 做机器判断。
- `fetch_paper` 和批量工具把阻塞抓取放到有界 `ThreadPoolExecutor`，事件循环继续处理 progress / log / cancellation；批量工具保持输入顺序，遇到 rate-limit status/code/category、HTTP 429 或 retry-after 后停止提交新任务。
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

`RuntimeContext` 是 service/workflow 的显式运行时依赖容器，持有 `env`、`transport`、`clients`、`download_dir`、`cancel_check`、`artifact_store`、可选 `fetch_cache`，以及单次 fetch 生命周期内的 `parse_cache`、`session_cache` 和 `stage_timings`。Browser provider 只依赖 `paper_fetch.providers.browser_runtime` facade；生产 backend 是 CloakBrowser，storage/profile 路径由 `browser_runtime.paths` 统一解析。Browser 生命周期由 CDP-only `paper_fetch.runtime_browser.BrowserContextManager` 管理；managed Chrome manager 会按 browser 配置在同一进程内共享引用，具体 context/page 使用调用线程自己的 CDP 连接，最后一个引用释放或进程退出时清理。公开 service API 只接受 `context=`；调用方必须先构造 `RuntimeContext`，再交给 `paper_fetch.workflow.pipeline.FetchPipeline`。

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
| `table-rendering` | `paper_fetch.extraction.markdown_render.table_format`、`paper_fetch.extraction.html.tables`、`_article_markdown_elsevier_document` | HTML/XML 表格展平、pipe-table 格式化、降级和语义损失标记。 |
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
- Browser runtime 使用 backend facade 和集中 storage-state manager；auth、preflight、HTML fetch、seeded PDF fallback 共享 provider-scoped `storage-state.json` 路径、写锁和 atomic write。Browser-backed image fetch 对单图 seed warm、page fetch、request-context fetch、直接导航和 image wait 共用一个 wall-clock budget；PDF fallback 只用 lightweight browser warm 采集 cookies/user-agent/final URL，已有 cookie seed 时不再对同一 seed URL 做第二次 browser navigation。External CDP 默认借用既有 context，并在 diagnostics 中报告被忽略的 context options；`PAPER_FETCH_CDP_EXTERNAL_NEW_CONTEXT=1` 可要求在外部浏览器中创建新 context。
- 本地转换工具链使用进程内有界缓存降低重复探测：Ghostscript/libvips 候选路径、`--version` probe 和工具 env overlay 按相关 env/目录/文件指纹失效；公式转换保留 MathML 结果缓存和 `mathml-to-latex` worker 复用；PDF fallback 对无图片导出路径的同一 PDF hash 复用 Markdown 渲染结果，并在成功结果 diagnostics 中记录 hash、字节数、页数、cache status 和耗时。
- `ArtifactStore` / `DownloadPolicy` 管理 artifact mode：provider PDF/binary local copy、PDF fallback 源文件、provider 原始 HTML、Markdown 保存、asset 诊断、HTTP textual cache 开关，以及 fetch-envelope/cache-index JSON 的原子写入。
- `FetchCache` 管理 MCP fetch-envelope sidecar reuse/write 语义与 cache index refresh；sidecar version、`EXTRACTION_REVISION` 校验、resource URI 与 scoped cache resource 语义稳定，实际 JSON materialization 委托给 `ArtifactStore`。MCP cache index 读取会校验 `INDEX_VERSION`；旧版/坏 schema 默认拒绝作为可信 manifest，`list_cached(cache_mode="index")` 只读 manifest，`refresh` 只校验/修剪现有 manifest，`rescan` 只从可证明 DOI 归属的 fetch-envelope sidecar 重建。

### 9. Transport 层

入口：`src/paper_fetch/http/`

- HTTP 请求、连接复用与同 host 有界并发、进程内短 TTL GET 缓存与可选磁盘 textual GET 缓存、响应体大小限制、有限短重试、协作式取消检查

`HttpTransport` 保持 public request options、structured logs、cancel checks、`Retry-After` 最大等待和 `RequestFailure` 形状；瞬时错误与 429 retry policy 由 `urllib3.util.Retry` 表达，连接池由 `PoolManager(num_pools, maxsize, block=True)` 配置。磁盘 textual GET 缓存使用脱敏 cache key（敏感 header 用短 SHA-256 digest 区分凭据且不落原文），默认按 `4096` 条、`512 MiB`、`30` 天清理，三项上限可用环境变量独立覆盖。内部子模块：`transport.py`（request loop / pool / semaphore / log）、`cache.py`（cache key / digest / memory+disk cache / stats / prune）、`retry.py`（retry policy / backoff）、`body.py`（读取 / 解压 / content-type / preview）、`errors.py`（异常类型）。`paper_fetch.http` 是兼容 facade。

### 10. CI / 回归验证边界

`.github/workflows/ci.yml` 是 CI 命令事实来源：普通 `push` / `pull_request` 运行 `lint`、`integration` 和 `package-smoke`，完整 `unit` / `devtools` / unit coverage 留给本地 `scripts/dev-preflight.sh`。CI integration 与本地 unit / integration / devtools 默认复用 `pyproject.toml` 的 `pytest-xdist` 并行配置，不传 `-n 0`。重型 offline/release job 只在 `v*` tag 或手动 `workflow_dispatch` 路径运行。只有 live MCP、browser provider smoke、共享真实 publisher/API 状态或专门排查顺序问题的测试可串行，并在命令旁说明原因。

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

workflow 尽量拿到 Crossref metadata 与 publisher metadata（`elsevier` 仍参与 publisher metadata probe；`springer`/`wiley`/`science`/`pnas`/`ieee`/`copernicus`/`ams`/`mdpi`/`royalsocietypublishing`/`annualreviews`/`plos`/`frontiers`/`oxfordacademic`/`acs`/`iop`/`aip` 不做 publisher metadata probe），再执行 primary / secondary merge，得到统一 metadata 视图，决定更准确的 `landing_page_url`、更稳定的 provider 选择和 metadata-only 结果内容。provider/Crossref primary-secondary merge 的事实源是 `paper_fetch.metadata.types.PRIMARY_SECONDARY_METADATA_MERGE_RULE` 与 `merge_primary_secondary_metadata()`：显式 blank primary scalar 阻止 secondary 回填并最终输出 `None`，authors 使用 semantic author key 去重，keywords 按大小写无关文本去重，`fulltext_links` 按 URL 去重，`references` 优先 DOI、否则 raw 文本去重。provider 内部多层 enrichment 用 `paper_fetch.metadata.types.MetadataMergeRule` / `merge_metadata_layers()` 描述字段优先级，provider-specific 的 DOI/author 规范化在 adapter 边界完成。

### 4. provider fulltext

选中 provider 后，workflow.fulltext 先尝试 provider 主路径。每个 official provider 自管 HTML/XML/PDF/browser 瀑布，成功时公开为各自的 source（如 `elsevier_xml`/`elsevier_pdf`、`springer_html`/`springer_pdf`、`wiley_browser`、`science`/`pnas`、`ieee_html`/`ieee_pdf`、`arxiv_html`/`arxiv_pdf`、`copernicus_xml`/`copernicus_pdf`、`ams_html`/`ams_pdf`、`mdpi_html`/`mdpi_pdf`、`royalsocietypublishing_html`/`royalsocietypublishing_pdf`、`annualreviews_html`/`annualreviews_pdf`、`plos_xml`/`plos_pdf`、`frontiers_xml`/`frontiers_pdf`、`oxfordacademic_html`/`oxfordacademic_pdf`、`acs`、`iop_html`/`iop_pdf`、`aip_html`/`aip_pdf`）。**各 provider 的完整 waterfall 顺序、env 依赖和 source 细节以 [`../providers.md`](../providers.md#wiley-science-pnas-browser-workflow) 为准**，本文不复制。

实现要点：

- Wiley / Science / PNAS / Annual Reviews / Royal Society Publishing / ACS / IOP / AIP / MDPI 共用 `paper_fetch.providers.browser_workflow` 这套 canonical browser workflow facade（profile / bootstrap / pdf_fallback / article / assets / client / shared / html_extraction / fetchers），通过 `shared.BrowserWorkflowDeps` 注入依赖。AMS 使用 provider-owned direct HTTP HTML/PDF 路径，不参与 browser workflow bootstrap 或 seeded-browser PDF fallback。
- Atypon 候选路由通过 `_atypon_browser_workflow_profiles` 分派，publisher 差异走 profile callback。
- provider-owned author 抽取统一用 `_html_authors.AuthorExtractionPipeline`，每个 provider 只注册命名 `AuthorStep`。
- 这些 waterfall 由 `_waterfall` 做轻量编排（按 step 顺序执行、累积 warnings、组合失败、写成功/失败 source markers）；step 默认会对 `NO_RESULT`、`NO_ACCESS`、`RATE_LIMITED`、`ERROR` 等 provider 失败码继续后续 fallback，最终失败会稳定聚合 retry-after、warnings、source trail 和缺失 env。`ProviderClient.fetch_result` 是 template-method，base 统一完成 raw payload、related assets、`to_article_model`、artifacts 和 trace/warning 组装。
- 通用 HTTP-first 资产下载保留给非目标 provider，由 `extraction.html.assets.download_assets(kind, ...)` 基于 `AssetDownloadKind` 统一处理 resolve/fallback；asset retry 只针对网络、超时、browser context/fetch error 或 Cloudflare challenge 触发，404/410、非目标 content type、unsupported scheme 只记诊断不重试。

正文足够可用时流程在此结束。

### 5. abstract-only / metadata-only fallback

命中 official provider 时，workflow.fulltext 只执行该 provider 自管的 HTML/XML/PDF/browser waterfall；`springer`/`wiley`/`science`/`pnas`/`ams`/`annualreviews`/`acs`/`iop`/`aip`/`ieee` 只能确认摘要级内容时直接返回 provider `abstract_only`，`arxiv`/`copernicus`/`elsevier`/`mdpi`/`royalsocietypublishing`/`plos`/`frontiers`/`oxfordacademic` 在 HTML/XML/PDF 都不可用时进入 metadata-only fallback。

没命中 official provider 时，系统仍允许 DOI / Crossref metadata 解析，但跳过通用 HTML 正文提取：`strategy.allow_metadata_only_fallback=true` 返回 metadata-only 结果，否则抛 `PaperFetchFailure`。metadata fallback 时 `has_fulltext=false`，`warnings` 提示降级，`source_trail` 带 `fallback:metadata_only`，public `source` 通常表现为 `metadata_only`（若 metadata 含摘要，`content_kind` 可能是 `abstract_only`）。

### 6. render / envelope / cache / MCP 暴露

拿到最终 `ArticleModel` 后，workflow.rendering 构造 `FetchEnvelope`，对外结果含 `trace: list[TraceEvent]`、与 trace 同步的兼容字段 `source_trail`、聚合到 `ArticleModel.quality` 与 `FetchEnvelope` 的 `warnings`。随后 `ArtifactStore` 已处理 provider payload / HTML copy / asset 诊断；CLI 决定是否写 Markdown、是否改写相对资源链接（通过 `FetchPipeline` 的 `MarkdownSaveSpec` 执行）；MCP 通过 `FetchCache` hooks 决定是否复用/写入 sidecar、暴露 resources、附带 inline images。

## 数据契约与角色边界

### `ResolvedQuery`

表达「输入被解析成什么论文候选」，为 routing 与 metadata 拉取提供标准化入口。不决定输出格式或正文抓取成功与否。

### `FetchStrategy`

表达「怎么抓」。最重要的字段是 `allow_metadata_only_fallback`、`preferred_providers`、`asset_profile`。它不决定返回哪些 payload（那是 `modes` 的职责）。

### `FetchEnvelope`

固定返回形状的公开抓取结果。始终承载 `doi`、`source`、`has_fulltext`、`warnings`、`source_trail`、`token_estimate`、`token_estimate_breakdown`；按 `modes` 决定是否附带 `article` / `markdown` / `metadata`。

MCP tool 返回的是在业务 payload 顶层追加 `schema_version=1` 的 JSON-safe 形状；这不是 `FetchEnvelope` sidecar 的缓存版本。失败时 `status` 仍是旧客户端可读的粗粒度状态，细粒度失败原因放在 `code` / `error_category`，HTTP 与限流细节放在 `http_status` / `retry_after_seconds`。

### `ArticleModel`

表达 provider 已转换好的正文、资产、references 和质量诊断，并统一负责最终 Markdown 渲染的 token budget、资产附录、references 输出和质量 warnings。重要边界：

- `assets[*].render_state` 决定资产是否追加到尾部附录（`inline`/`suppressed` 不追加，`appendix` 可追加）；正文已内联图片按 URL/相对路径/后缀/basename 做等价比较避免重复渲染。
- 文章组装先用已下载资产把正文远程 figure/table/formula 链接改写成本地路径，再做 Markdown 图片块边界和短 alt 归一化；image alt 由 `paper_fetch.markdown.images` 生成，caption 不进入 `![alt]`。
- structured metadata 进 front matter 前解开 HTML entity，避免 `&amp;` 泄漏。
- `assets[*].download_tier` / `download_url` / `content_type` / `downloaded_bytes` / `width` / `height` 是下载诊断，不应被下游丢弃。
- `quality.semantic_losses.table_layout_degraded_count` 表示版式降级，`table_semantic_loss_count` 才表示语义内容丢失。

### `provider_status`

在抓取前报告本地环境是否就绪。本地检查边界与各 provider check 名称以 [`../providers.md`](../providers.md#provider-status-local-boundary) 为准；IEEE 当前返回 `html_route` 与 `pdf_fallback` 两条 check。

### `has_fulltext`

区分两个层面：`fetch_paper().has_fulltext` 是完整抓取瀑布后的最终 verdict；MCP 的 `has_fulltext()` 是只用更弱信号的廉价 probe。两者不要求逐案完全一致（见 [`probe-semantics.md`](probe-semantics.md)）。

## 关键例外与调用方容易误解的点

### official provider 不走通用 HTML fallback

`elsevier`/`springer`/`wiley`/`science`/`pnas`/`ieee`/`arxiv`/`copernicus`/`ams`/`mdpi`/`royalsocietypublishing`/`annualreviews`/`plos`/`frontiers`/`oxfordacademic`/`acs`/`iop`/`aip` 的 HTML/XML/PDF/browser 逻辑由 provider 内部管理：不存在 public HTML fallback 开关，是否尝试主路径由 provider 路由和 `preferred_providers` 控制，更细的成功细节看 `source_trail`。

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
- **新增 MCP surface**：主要改 `src/paper_fetch/mcp/`（`schemas.py`、`fetch_tool.py`、`cache_payloads.py`、`batch.py`、`server.py`）；需要真正的新抓取逻辑要先落到 service / workflow 层。
- **新增渲染能力**：正文渲染或资产展示能力优先改 `src/paper_fetch/models/` 与 provider 到 `ArticleModel` 的转换，而不是让 CLI / MCP 自己拼装业务结果。

## 相关文档

- [`../../README.md`](../../README.md)
- [`../providers.md`](../providers.md)
- [`../deployment.md`](../deployment.md)
- [`probe-semantics.md`](probe-semantics.md)
