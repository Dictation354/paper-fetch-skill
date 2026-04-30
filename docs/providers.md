# Provider 能力与运行时行为

这份文档解决：

- 各 provider 能做什么、不能做什么
- 运行时如何做路由和回退
- 默认输出策略与下载行为
- 配置项、环境变量、限速与缓存护栏

这份文档不解决：

- agent runtime 的安装与 MCP 注册
- Wiley / Science / PNAS 的具体启动脚本与运维排障
- 架构分层和数据契约的完整背景

部署入口见 [`deployment.md`](deployment.md)，Wiley / Science / PNAS 运维细节见 [`flaresolverr.md`](flaresolverr.md)，架构说明见 [`architecture/target-architecture.md`](architecture/target-architecture.md)。

## Provider 能力矩阵

| Provider | 元数据 | 全文主路径 | 资产下载 | Markdown 能力 | 备注 |
| --- | --- | --- | --- | --- | --- |
| `crossref` | 支持 | 不负责 publisher fulltext | 不支持 | 不适用 | 负责 resolve、routing signal、metadata merge 与 metadata-only fallback |
| `elsevier` | 官方 API | `官方 XML/API -> 官方 API PDF fallback` | XML 路线支持 `none` / `body` / `all`；PDF fallback 当前 text-only | 强 | XML 成功时公开为 `elsevier_xml`；PDF fallback 成功时公开为 `elsevier_pdf` |
| `springer` | 依赖 Crossref merge | `direct HTML -> direct HTTP PDF` | HTML 路线支持 `none` / `body` / `all`；PDF fallback 当前 text-only | 强 | `nature.com` 继续挂在 `springer` provider / `springer_html` source 下；必要时可返回 provider `abstract_only` |
| `wiley` | 依赖 Crossref merge | `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> Wiley TDM API PDF` | HTML 路线支持 `none` / `body` / `all`；PDF/ePDF fallback 当前 text-only | 中 | HTML 与 browser PDF/ePDF 依赖 repo-local FlareSolverr；`WILEY_TDM_CLIENT_TOKEN` 可在 browser PDF/ePDF fallback 失败或 browser runtime 不可用时继续尝试官方 TDM PDF lane；必要时可返回 provider `abstract_only` |
| `science` | 依赖 Crossref | `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF` | HTML 路线支持 `none` / `body` / `all`；PDF/ePDF fallback 当前 text-only | 中 | 与 `wiley` 的 HTML / browser PDF/ePDF 路径共用浏览器工作流基座；AAAS access gate / entitlement 不满足时会停在 provider 内部并降级 `abstract_only` / `metadata_only` |
| `pnas` | 依赖 Crossref | `direct Playwright HTML preflight -> FlareSolverr HTML -> seeded-browser publisher PDF/ePDF` | HTML 路线支持 `none` / `body` / `all`；PDF/ePDF fallback 当前 text-only | 中 | direct Playwright preflight 成功时跳过 FlareSolverr；失败、challenge、正文不足或抽取失败时保持原 FlareSolverr/PDF 瀑布；较老文献常见 HTML 仅摘要，再继续走 provider 内部 PDF/ePDF fallback，必要时可返回 `abstract_only` |

说明：

- 这张矩阵描述的是“当前代码里已经实现的 provider-owned waterfall”，不是“任意 DOI、任意运行环境都必然能拿到 publisher 全文”的承诺。
- 尤其 `wiley` / `science` / `pnas` 的浏览器与 PDF/ePDF 路径，仍受 publisher 访问权限、paywall/challenge 与远端站点行为影响。
- `wiley` 的 HTML / browser PDF/ePDF 路径与 `science` / `pnas` 现在只保留一套 provider-owned 浏览器栈：canonical runtime 是 `paper_fetch.providers.browser_workflow` 包入口；bootstrap、PDF/ePDF fallback、article assembly、asset retry helper、client 基类和 Playwright fetchers 已拆到 `browser_workflow/` 与 `browser_workflow_fetchers/` 子模块。旧 `_science_pnas` 兼容 alias 已移除，`_browser_workflow_fetchers.py` 仅保留兼容 re-export wrapper，browser-PDF executor 继续共享 `_pdf_fallback`，不再存在单独的 Science path harness。
- browser-workflow 的 asset download Playwright fallback 在并发 worker 中使用线程私有 browser/context，不复用 `RuntimeContext` 持有的共享 browser；`RuntimeContext` 共享 browser 仍只保留给非 threaded 的主流程 Playwright 场景。
- 2020+ live / regression 基准样本集中维护在 [`../tests/provider_benchmark_samples.py`](../tests/provider_benchmark_samples.py)。
- 自然地理学 live-only 候选集中维护在 [`../tests/live/geography_samples.py`](../tests/live/geography_samples.py)，默认每家尝试前 `10` 条，并通过 [`../scripts/run_geography_live_report.py`](../scripts/run_geography_live_report.py) 产出 JSON/Markdown 报告。
- `geography` live runner 默认按 provider 轮转执行，保持单家样本顺序不变。
- `run_geography_live_report.py`、`export_geography_issue_artifacts.py`、`group_geography_issue_artifacts.py` 都属于 repo-local internal tooling：不新增 console script，不作为 MCP surface，对外产品面不变。
- geography live/report/export/group 仍受 `PAPER_FETCH_RUN_LIVE=1` 的 opt-in 边界保护；未启用 live 环境时，对应测试应稳定 skip。
- golden criteria live review 产物写入 `live-downloads/golden-criteria-review/`，由 [`../scripts/run_golden_criteria_live_review.py`](../scripts/run_golden_criteria_live_review.py) 生成；每条结果保留兼容的 `elapsed_seconds`，并新增 `stage_timings.fetch_seconds` / `materialize_seconds` / `total_seconds` / `resolve_seconds` / `metadata_seconds` / `fulltext_seconds` / `asset_seconds` / `formula_seconds` / `render_seconds`，同时在 `http_cache_stats` 中记录该 sample 相对执行前的 cache delta。`10.1016/S1575-1813(18)30261-4` 这类预期 metadata-only 样本，以及当前不支持的 TandF / Sage 样本，应通过 manifest 的 expected outcome 标记为 `skipped`，不进入 provider bug 修复队列。

## 路由规则

当前 provider 决策统一按更强信号优先：

```text
domain > publisher > DOI fallback
```

具体含义：

- `domain`
  - 由落地页 URL 或 Crossref metadata 的 `landing_page_url` 推导。
- `publisher`
  - 由 Crossref metadata 的 `publisher` 推导。
- `DOI fallback`
  - 在前两类信号都不够时，才使用 DOI 前缀兜底。

这些 provider 身份与能力配置统一来自 `paper_fetch.provider_catalog.PROVIDER_CATALOG`。Catalog 固定记录 provider 名称、展示名、official 标记、domain / DOI prefix / publisher alias、默认 asset 策略、probe 能力、abstract-only 策略、client factory 路径和 MCP status 顺序；`publisher_identity`、workflow routing、默认 asset profile、registry 与 provider status 列表都从这里派生。

### `provider_hint` 的含义

- `resolve_paper().provider_hint` 表示“当前最可信的 provider 提示”。
- 它来自 domain、publisher、DOI 信号综合判断。
- 它不是“保证最终一定由该 provider 成功返回”的承诺。

### `crossref` 作为 signal 与 source 的区别

`crossref` 有两种角色：

1. 作为 routing signal
   - 用于拿 `publisher`、`landing_page_url`、`license`、`fulltext_links` 等信号。
   - 此时不会自动把最终结果的 `source` 变成 `crossref_meta`。
2. 作为 public source
   - 当调用方显式收敛到 Crossref-only 且没有进入 metadata fallback 时，底层文章来源可保持 `crossref_meta`。
   - 当 fulltext waterfall 失败并进入 metadata fallback 时，`FetchEnvelope.source` 会公开表现为 `metadata_only`；底层 `ArticleModel.source` 仍可能是 `crossref_meta`。

实现边界上，Crossref HTTP lookup 的底层 owner 是 `paper_fetch.metadata.crossref.CrossrefLookupClient`；`paper_fetch.providers.crossref.CrossrefClient` 只是 provider adapter，并继续保留 public import path。

### `preferred_providers` 的语义

- 它限制最终允许进入的五家 provider fulltext 主链候选。
- 它不阻止系统内部调用 `crossref` 做路由判断或 metadata-only fallback。
- 如果显式设为 `["crossref"]`，行为会收敛成 Crossref-only。
- 当前可显式指定的 provider 名包括：
  - `elsevier`
  - `springer`
  - `wiley`
  - `science`
  - `pnas`
  - `crossref`

## 抓取瀑布与回退语义

统一主线如下：

```text
resolve
-> metadata / routing
-> provider fulltext
-> abstract-only / metadata-only fallback
```

### 1. resolve

- 输入可以是 DOI、URL 或标题。
- 标题查询会走 Crossref 候选打分。
- 如果标题候选不够确定，会返回 `ambiguous`，而不是直接抓取错误论文。
- DOI cleanup 保留原宽松规则，再用 `idutils` 做校验/规范化辅助；标题候选仍用 token Jaccard 权重、既有 confidence threshold 和 ambiguity margin，字符串 ratio component 由 `rapidfuzz.fuzz.ratio` 提供。

### 2. metadata 与路由

- 系统会先尽可能拿到 Crossref metadata。
- 只有 `elsevier` 还会参加 publisher metadata probe。
- `springer`、`wiley`、`science`、`pnas` 在 `probe_official_provider()` 和 `has_fulltext()` 中都只依赖 Crossref / landing-page 信号，不再调用 publisher metadata API。
- 最终会合并 primary / secondary metadata，统一生成正文抓取需要的元数据。

### 3. provider 全文主路径

- `elsevier`
  - 固定顺序是 `官方 XML/API -> 官方 API PDF fallback -> metadata-only`。
  - XML/API 成功时公开 `source="elsevier_xml"`。
  - 官方 PDF fallback 成功时公开 `source="elsevier_pdf"`。
- `springer`
  - 固定顺序是 `direct HTML -> direct HTTP PDF -> abstract-only / metadata-only`。
  - 优先抓取 publisher landing HTML，不足正文时再走 direct HTTP PDF。
  - 优先使用 merged metadata 中的 `landing_page_url`，缺失时回退 DOI 解析。
  - 成功时公开 `source="springer_html"`。
- `wiley`
  - 使用 provider 自管 HTML + 官方 API PDF + publisher PDF/ePDF waterfall。
  - 固定顺序是 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> Wiley TDM API PDF -> abstract-only / metadata-only`。
  - 不做 direct Playwright HTML preflight，避免低成功率路径增加固定开销。
  - FlareSolverr HTML 正文首轮使用 `waitInSeconds=0` + `disableMedia=true` 的快速路径；challenge、访问拦截、摘要页或正文抽取不足时回退到原保守等待参数。
  - `WILEY_TDM_CLIENT_TOKEN` 是官方 TDM API PDF lane；缺失时仍可继续尝试 browser PDF/ePDF，配置后会在 browser PDF/ePDF fallback 失败或 browser runtime 不可用时继续尝试 TDM PDF。
  - 成功时公开 `source="wiley_browser"`。
- `science`
  - 固定顺序是 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> abstract-only / metadata-only`。
  - 与 `wiley` 的 HTML / browser PDF/ePDF 路径共享同一套浏览器工作流基座。
  - 不做 direct Playwright HTML preflight，避免低成功率路径增加固定开销。
  - FlareSolverr HTML 正文首轮使用同一快速路径，并在 challenge、访问拦截、摘要页或正文抽取不足时保守重试。
  - 如果落到 AAAS 的 `Check access` / paywall 页面，应优先解读为 `institution not entitled / no access`，而不是 generic HTML fallback 缺失。
  - 成功时公开 `source="science"`。
- `pnas`
  - 固定顺序是 `direct Playwright HTML preflight -> FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> abstract-only / metadata-only`。
  - direct Playwright preflight 使用 `domcontentloaded` 并阻断 image/font/stylesheet/media；成功 payload 会标记 `html_fetcher="playwright_direct"`。
  - preflight 失败、遇到 challenge、正文不足或抽取失败时不改变旧语义，继续走 FlareSolverr HTML；FlareSolverr HTML 自身先尝试快速路径，再在失败或抽取不足时保守重试；成功 payload 标记 `html_fetcher="flaresolverr"`。
  - 较老文献常见 HTML 只到摘要页，此时 provider 会继续尝试 publisher PDF/ePDF fallback。
  - 成功时公开 `source="pnas"`。

### 4. abstract-only / metadata-only fallback

如果命中了 `elsevier`、`springer`、`wiley`、`science`、`pnas` 之一：

- 系统只会走该 provider 自己管理的 HTML/PDF waterfall
- provider 主链不可用或返回 `None` 后直接进入 metadata-only fallback
- `springer` / `wiley` / `science` / `pnas` 如果只能确认摘要级内容，会返回 provider 自己的 `abstract_only` 结果，而不是再绕去通用 HTML

如果没有命中这五家 provider：

- 系统仍会继续做 DOI / Crossref metadata 解析
- 不再尝试任何通用 HTML 正文提取
- `strategy.allow_metadata_only_fallback=true` 时返回 metadata + abstract
- 否则直接抛错

如果没有可返回的 provider `abstract_only` 结果，而 `strategy.allow_metadata_only_fallback=true`：

- 返回 metadata + abstract
- `has_fulltext=false`
- `warnings` 中显式说明已降级
- `source_trail` 中会带 `fallback:metadata_only`
- public `source` 通常会表现为 `metadata_only`；如果元数据里有摘要，模型质量层的 `content_kind` 可能归类为 `abstract_only`

如果关闭这个开关，正文不可得会直接抛错。

## Elsevier / Springer / Wiley / Science / PNAS 的特殊语义

这五个 provider 的共同点是：

- metadata 先尽量来自 Crossref；只有 `elsevier` 可能用 publisher metadata probe 作为 primary 覆盖 / 补充
- fulltext 主路径由 provider 自己控制
- 主链不可用时不走通用 HTML；不可用 / `None` 结果进入 metadata-only fallback，provider-managed `abstract_only` 结果可直接返回
- XML / HTML / PDF / TDM / browser PDF fallback 的顺序由内部 `paper_fetch.providers._waterfall` runner 编排；各 provider step 仍保留自己的 payload 结构、warning 文案和 `fulltext:*` source trail marker
- `ProviderClient.fetch_result` 负责通用 raw payload、本地副本标记、资产下载、warning/trace 和 artifact 组装；workflow 内部调用时必须传入 `artifact_store=` 与 `context=`，Browser workflow 与 Springer 只通过 hook 处理 abstract-only 后 PDF recovery 或 provider-managed abstract-only 返回

但它们的 fulltext 形态不同：

- `elsevier`
  - provider 自管 `官方 XML/API -> 官方 API PDF fallback`
  - 进入 PDF lane 时会组合 `fulltext:elsevier_xml_fail`、`fulltext:elsevier_pdf_api_ok`、`fulltext:elsevier_pdf_fallback_ok`
  - PDF lane 失败时会带 `fulltext:elsevier_pdf_api_fail`
- `springer`
  - provider 自管 `direct HTML -> direct HTTP PDF`
  - 成功轨迹是 `fulltext:springer_html_*`，PDF fallback 成功时会带 `fulltext:springer_pdf_fallback_ok`
- `wiley`
  - provider 自管 FlareSolverr HTML + Wiley TDM API PDF + seeded-browser publisher PDF/ePDF waterfall
  - 成功轨迹是 `fulltext:wiley_html_*` / `fulltext:wiley_pdf_api_ok` / `fulltext:wiley_pdf_browser_ok` / `fulltext:wiley_pdf_fallback_ok`
  - 失败时若 API lane 未产出 PDF，会保留 `fulltext:wiley_pdf_api_fail`；若 browser PDF/ePDF lane 已实际尝试但失败，会再带 `fulltext:wiley_pdf_browser_fail`
- `science`
  - provider 自管 `FlareSolverr HTML + seeded-browser publisher PDF/ePDF`
  - `fulltext:science_html_fail` / `fulltext:science_pdf_fallback_ok` 只描述 provider 主链的阶段切换；如果页面本身就是 access gate，更准确的业务解释应是 `institution not entitled / no access`
  - 继续保持现有 `science` 风格的公开来源与轨迹命名
- `pnas`
  - provider 自管 `direct Playwright HTML preflight + FlareSolverr HTML + seeded-browser publisher PDF/ePDF`
  - 较老文献可能先表现为 `fulltext:pnas_html_fail`，再进入 `fulltext:pnas_pdf_fallback_ok`
  - 继续保持现有 `pnas` 风格的公开来源与轨迹命名

因此：

- 不再存在 public HTML fallback 开关
- 对 `elsevier` 来说，系统始终按内部 `官方 XML/API -> 官方 API PDF fallback` waterfall 执行
- 对 `springer` 来说，系统始终按内部 `direct HTML -> direct HTTP PDF` waterfall 执行
- 对 `wiley` 来说，系统始终按内部 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> Wiley TDM API PDF` waterfall 执行
- 对 `science` 来说，系统始终按内部 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF` waterfall 执行
- 对 `pnas` 来说，系统始终按内部 `direct Playwright HTML preflight -> FlareSolverr HTML -> seeded-browser publisher PDF/ePDF` waterfall 执行；preflight 只做快速成功路径，不改变 FlareSolverr/PDF 回退语义

## 默认输出策略

CLI、Python API、MCP 当前统一采用这些默认值：

- `asset_profile=null (provider default)`
- `max_tokens="full_text"`
- `include_refs=null`

### `asset_profile`

- `null` / omitted
  - 使用 provider default
  - `springer` / `wiley` / `science` / `pnas` 默认等价于 `body`
  - 其他默认等价于 `none`
- `none`
  - 不下载资产
  - Markdown 保留 figure caption
  - 不输出 supplementary 链接
- `body`
  - 只从 provider-cleaned 正文 fragment 下载正文 figure
  - 下载正文表格原图
  - 下载可识别的正文公式图片 fallback
  - 不包含 supplementary
- `all`
  - 下载当前 provider 已识别的全部相关资产
  - 在 `body` 基础上额外下载 supplementary 文件附件
  - 包含 appendix / supplementary 等非正文资产；正文已经内联消费的图表仍会通过 `render_state` 从尾部重复附录中过滤

对 `elsevier` PDF fallback、`springer` PDF fallback、`wiley` / `science` / `pnas` 而言：

- `elsevier` PDF fallback 仍会把 `asset_profile=body|all` 降级成 text-only
- `springer` PDF fallback 仍会把 `asset_profile=body|all` 降级成 text-only
- `wiley` / `science` / `pnas` 的 `FlareSolverr HTML` 成功路径支持正文 figure / table / formula 图片资产下载；这些 provider 以 shared Playwright browser context 为主链路，不再先走普通 HTTP 直连
- `wiley` / `science` / `pnas` 的 `asset_profile=all` 会把 supplementary 从正文图片链路拆开，作为独立文件附件下载；代码层不额外限制 supplementary 文件大小；首轮失败后只重试失败的原始 asset 子集，不会因为 supplementary 失败重新下载已成功的正文 figure
- `wiley` 的 supplementary 只从 `Supporting Information` 区块抽取，并且只接受 `downloadSupplement` 或 `sup-*` 这类真实 supporting file 链接；正文 `<figure>` 里的 `/cms/asset/...fig-*.jpg|png|webp` 只保留为 figure 资产；`downloadSupplement` query 里的 `file` / `filename` 会作为真实文件名优先用于落盘
- `science` / `pnas` 的 supplementary 只从 Atypon 真实 `Supplementary Material(s)` / `Supporting Information` section 子树抽取，并且只保留 publisher `/doi/suppl/.../suppl_file/...` 附件；正文 Data Availability 里的普通数据链接、页内 `#supplementary-materials` 导航或 section 内引用文献 PDF 不会再被当作 supplementary
- `wiley` / `science` / `pnas` 的图片候选仍优先 full-size/original；full-size 候选全部失败后才尝试 preview，preview 也通过同一个 seeded browser context 下载
- `wiley` / `science` / `pnas` 的 PDF/ePDF fallback 仍是 text-only
- `springer` HTML 成功路径也按相同语义处理：正文图片只从 cleaned body/content scope 抽取；普通 supplementary 只允许来自 `Supplementary information` / `Supplementary material(s)` / `Supporting information` / `Electronic supplementary material` / `Extended data` / `Extended data figures and tables` 这些 section 子树；`Source Data` 会独立识别并在下载时落到 `source_data/` 子目录，`Peer Review File` / `Peer reviewer reports` 不再当作 supplementary；PDF fallback 仍是 text-only
- `elsevier` XML 成功路径下，`body` 继续只下载 `image` / `table_asset`，`all` 会额外下载 `supplementary` references，并统一映射到 `kind="supplementary"` / `section="supplementary"` / `download_tier="supplementary_file"`
- 通用 HTML figure 与 supplementary 下载内部使用私有 asset download candidate/attempt/resolution 模型和共享 bounded executor：网络、opener 或浏览器 document fallback resolve 阶段可并发执行，结果按原 asset 顺序回收；文件写入、文件名去重、`source_data/` 分流和失败诊断收集仍串行执行。输出顺序、fallback 候选顺序、`article.assets[*]` 与 `quality.asset_failures` shape 保持稳定。Elsevier XML object references 也使用同样的“网络并发、写入串行”约束。并发 worker 上限由 `PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY` 控制，默认 `4`、最小 `1`。
- Provider fulltext 公开契约是 `fetch_result()` / `fetch_raw_fulltext()`；旧 `fetch_fulltext()` dict 入口已经删除。
- 同一次 provider fetch 内会复用 `RuntimeContext.parse_cache`：Elsevier XML root、Springer HTML extraction、Wiley/Science/PNAS browser-workflow Markdown extraction 和 HTML asset extraction 不跨阶段重复解析同一份 payload。
- 同一个 `RuntimeContext` 生命周期内还会复用 `session_cache`：`has_fulltext` 与后续 `fetch_paper` 可共享 query resolution、Crossref DOI metadata、Elsevier metadata probe 和 landing page `citation_pdf_url` probe；fetch 阶段命中 landing probe 时会把 citation PDF URL 合并到 metadata `fulltext_links`。
- 同一个 `RuntimeContext` 内会 lazy 复用 Playwright Chromium browser；PNAS direct HTML preflight、正文图片/文件 fetcher 与 PDF/ePDF fallback 仍按阶段创建独立 browser context/page，避免 cookie、route handler 和下载设置互相污染。
- `RawFulltextPayload.metadata` 只是 legacy/read-only compatibility view；provider 新逻辑应读写 `ProviderContent.route_kind`、`markdown_text`、`diagnostics`、`fetcher`、`browser_context_seed`、`warnings`、`trace` 和 `merged_metadata` 等 typed fields。

### 资产去重与诊断

- `render_state="inline"` 的资产表示正文已经渲染过，不会进入文末 `Figures` / `Tables`。
- `render_state="appendix"` 的资产仍可进入尾部兜底块；当同类资产全是 appendix 状态时，标题会显示为 `Additional Figures` / `Additional Tables`。
- 正文 Markdown 图片链接和资产路径会按 URL、路径、相对 `body_assets/...` 后缀和 basename 做等价比较，避免正文图在尾部重复。
- 文章组装阶段也会用 `article.assets[*]` 把正文里的远程 figure / table / formula image 链接改写为已下载本地路径，再做 Markdown 图片块边界归一化，避免图片和标题、正文句子或公式块粘连。
- 下载资产会保留 `download_tier`、`download_url`、`original_url`、`content_type`、`downloaded_bytes`、`width`、`height`。
- 下载失败的资产会保留到 `article.quality.asset_failures` 与顶层 `quality.asset_failures`，可见 `status`、`content_type`、`title_snippet`、`body_snippet`、`reason` 以及 asset-level recovery 轨迹。
- 图片 payload MIME 识别由 `filetype` 负责，JPEG/PNG/GIF/WebP 尺寸读取由 `imagesize` 负责；无法识别时仍按 unknown/空宽高处理，不引入 Pillow。
- `wiley` / `science` / `pnas` 的正文图片主链路只应输出 `download_tier="full_size"` 或 `download_tier="preview"`；supplementary 文件链路输出 `download_tier="supplementary_file"`；旧的 `playwright_canvas_fallback` tier 只可能来自仍保留 HTTP-first 语义的旧通用图片下载路径。
- `wiley` / `science` / `pnas` 的正文图片下载在单次 attempt 内会缓存重复的 figure page / 图片候选 URL，并按 `PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY` 控制的 worker 上限拉取 payload，默认 `4`；最终输出顺序仍与输入资产顺序一致。
- supplementary 文件下载失败时，`article.quality.asset_failures` 会保留 `status`、`content_type`、`title_snippet`、`body_snippet`、`reason` 和 recovery 轨迹，便于区分 Cloudflare challenge / login HTML / 普通网络失败；浏览器工作流的重试按失败诊断匹配 `heading`、`caption` 和 URL 字段，只重跑失败的 body 或 supplementary 资产。
- `download_tier="preview"` 只有在宽高满足当前阈值 `300x200` 时才会标记为可接受 preview；否则仍会进入 preview fallback / asset issue 诊断。
- live review 中，公式图片是公式语义的 fallback，因此 formula-only preview fallback 不自动归类为 `asset_download_failure`；figure/table preview fallback 仍按资产问题处理，除非已有 accepted 诊断。

### `include_refs`

- `max_tokens="full_text"` 时，默认等价于 `all`
- `max_tokens=<整数>` 时，默认等价于 `top10`

### 下载行为

- `--no-download` 或 `download_dir=None` 优先级最高
- Provider payload、Springer HTML local copy 和 asset 诊断统一由 `ArtifactStore` 应用，保留既有 warning 与 `download:*` source trail marker
- 即使 `asset_profile` 是 `body` / `all`，也不会落盘
- 没有本地文件时，Markdown 会自动退回 captions-only 或不展示本地资源链接

<a id="springer-原始-html-artifact"></a>
### Springer 原始 HTML artifact

- 当 Springer 抓取链拿到 publisher article HTML 时，`ArtifactStore` 会把可信的原始正文 HTML 单独落盘。
- 如果 `download_dir` 本身就是 DOI slug 文章目录，文件名是 `original.html`；否则文件名是 `<doi_slug>_original.html`。
- `*_assets/` 目录仍可以包含 figure page、table page、redirect page 或辅助 HTML；这些文件不能被当成可信的正文原文源文件。
- 该行为由 [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_springer_html_route_saves_original_html_in_article_dir` 锁定。

## 公开输出里最重要的字段

这些字段最适合拿来判断结果质量和来源：

- `source`
  - 粗粒度公开来源，如 `elsevier_xml`、`elsevier_pdf`、`springer_html`、`wiley_browser`、`science`、`pnas`、`crossref_meta`、`metadata_only`
- `has_fulltext`
  - 最终抓取瀑布后的 verdict
- `warnings`
  - 降级、截断、资产部分失败等信息
- `source_trail`
  - 更细粒度的路由、probe、fallback、下载轨迹
- `token_estimate_breakdown`
  - `abstract`、`body`、`refs` 的 token 估算
- `article.assets[*]`
  - 对下载资产保留 `render_state`、`anchor_key`、`download_tier`、`download_url`、`original_url`、`content_type`、`downloaded_bytes`、`width`、`height` 等诊断字段
- `article.quality.semantic_losses`
  - 表格现在区分 `table_layout_degraded_count` 和 `table_semantic_loss_count`；前者表示 Markdown 版式降级，后者才表示语义内容丢失
- `article.quality.asset_failures`
  - 对失败资产保留 `status`、`content_type`、`title_snippet`、`body_snippet`、`reason` 与 `recovery_attempts`

### Markdown 与语义 normalize

- 公式输出会在公共公式 normalize 层处理 publisher-specific LaTeX 宏。
- `\updelta` 等 upright Greek 宏会改写成普通 KaTeX 可渲染宏；`\mspace{Nmu}` 会改写成 `\mkernNmu`，其它单位不改。
- HTML 公式如果能从 MathML 转成 LaTeX，会按行内或 display 语境渲染；如果只有站点提供的公式图片 fallback，会保留为 `![Formula](...)` 并进入资产下载/改写流程。
- HTML references 会去除 publisher 链接 chrome，如 `Google Scholar`、`Crossref`、相关链接和隐藏文本，并优先保留用户可见 citation body。
- Elsevier XML references 优先从结构化 bibliography 构建，保留编号、作者、题名、来源、页码、年份和 DOI；缺字段时保留原始 citation text 或显式 `[Reference text unavailable]` 占位，Crossref references 只作为兜底。

## 配置文件与环境变量入口

默认主配置文件：

```text
~/.config/paper-fetch/.env
```

该默认位置由 `platformdirs` 解析；上面是常见 Linux/XDG 布局。仓库内 `.env` 不会自动加载。

如果你在开发场景里要使用仓库外的某个配置文件，显式设置：

```bash
PAPER_FETCH_ENV_FILE=/path/to/.env
```

### 通用环境变量

#### `PAPER_FETCH_SKILL_USER_AGENT`

- 自定义请求用 `User-Agent`。
- 建议配置为稳定项目标识。

#### `CROSSREF_MAILTO`

- Crossref polite pool 建议携带的联系邮箱。
- 会被拼入 Crossref 请求参数。

#### `PAPER_FETCH_DOWNLOAD_DIR`

- 覆盖默认下载目录。
- CLI 与 MCP 都会优先使用它。

#### `XDG_DATA_HOME`

- 在未配置 `PAPER_FETCH_DOWNLOAD_DIR` 时，用来推导用户数据目录。
- CLI / MCP 的用户数据下载目录会落在 `<XDG_DATA_HOME>/paper-fetch/downloads`。
- 未设置时使用 `platformdirs` 提供的平台默认用户数据目录。
- CLI 只有在用户数据下载目录创建失败时才回退仓库相对的 `live-downloads`。

### 公式后端

#### `PAPER_FETCH_FORMULA_TOOLS_DIR`

- 可选。
- 覆盖运行时查找外部公式工具的目录。
- 未配置时，运行时会依次考虑 repo-local `.formula-tools` 和用户数据目录下的 `formula-tools`。

#### `MATHML_CONVERTER_BACKEND`

- 可选。
- 支持 `texmath`、`mathml-to-latex`、`mml2tex`、`auto`。
- `legacy` 是代码仍能识别的历史值，但当前会直接报不可用，不应在新配置中使用。
- 默认是 `texmath`；未显式指定时，如果 `texmath` 失败，会尝试 `mathml-to-latex` fallback。
- 显式指定某个 backend 时，失败会按该 backend 返回，不会自动隐藏错误。

#### `TEXMATH_BIN`

- 可选。
- 指定 `texmath` 可执行文件；未配置时先查找公式工具目录，再查找 `PATH`。

#### `MATHML_TO_LATEX_NODE_BIN`

- 可选。
- 指定 Node 可执行文件；默认是 `node`。

#### `MATHML_TO_LATEX_SCRIPT`

- 可选。
- 指定 `mathml-to-latex` wrapper 脚本；未配置时会查找公式工具目录、打包资源和仓库脚本。

#### `MATHML_TO_LATEX_WORKER`

- 可选。
- 默认启用；设为 `0` / `false` / `no` / `off` 时禁用常驻 Node worker，回到每次调用 wrapper CLI。
- worker 使用 JSONL stdin/stdout 协议，失败或超时时会回退到单次 CLI。

#### `MATHML_TO_LATEX_WORKER_SCRIPT`

- 可选。
- 指定 `mathml-to-latex` worker 脚本；未配置时会查找公式工具目录、打包资源和仓库 `scripts/mathml_to_latex_worker.mjs`。

#### `MATHML_CONVERSION_CACHE_SIZE`

- 可选。
- 公式转换 LRU 大小；默认 `1024`，设为 `0` 可禁用结果缓存。
- 缓存 key 包含 backend、原始 MathML、display mode 和关键 converter 配置。

#### `MML2TEX_*`

- 高级可选。
- 代码支持 `MML2TEX_JAVA_BIN`、`MML2TEX_CLASSPATH`、`MML2TEX_SAXON_JAR`、`MML2TEX_XMLRESOLVER_JAR`、`MML2TEX_XMLRESOLVER_DATA_JAR`、`MML2TEX_STYLESHEET`、`MML2TEX_CATALOG`。
- 默认安装脚本不准备这套 Java/XSLT 工具链；只有显式提供这些资产并选择 `MATHML_CONVERTER_BACKEND=mml2tex` 时才使用。

### Elsevier

#### `ELSEVIER_API_KEY`

- 必填。
- Elsevier metadata 和全文 API 的核心凭证。

#### `ELSEVIER_INSTTOKEN`

- 可选。
- 机构授权场景补充凭证。

#### `ELSEVIER_AUTHTOKEN`

- 可选。
- Bearer token 形式的补充凭证。

#### `ELSEVIER_CLICKTHROUGH_TOKEN`

- 可选。
- clickthrough 场景补充凭证。

### Springer

Springer direct HTML / direct HTTP PDF 路线当前没有额外必填 publisher env：

- `provider_status()` 中会稳定表现为本地 `html_route` 已就绪
- 不再需要任何 Springer publisher 凭证

### Wiley / Science / PNAS

#### `WILEY_TDM_CLIENT_TOKEN`

- 可选。
- 仅用于 `wiley` 的官方 TDM API PDF lane。
- 未配置时，`wiley` 仍可在 FlareSolverr / Playwright runtime 就绪时尝试 HTML 与 seeded-browser PDF/ePDF；已配置时，即使 browser runtime 不就绪，也可单独尝试 TDM PDF fallback。

#### `FLARESOLVERR_URL`

- 本地 FlareSolverr 服务地址。
- 默认 `http://127.0.0.1:8191/v1`。

#### `FLARESOLVERR_ENV_FILE`

- 对 `science` / `pnas` 必填。
- 对 `wiley` 的 FlareSolverr HTML 与 seeded-browser PDF/ePDF 路径必填；只使用 `WILEY_TDM_CLIENT_TOKEN` 的官方 TDM API PDF lane 时不需要。
- 必须显式指向当前仓库 `vendor/flaresolverr/` 下的 preset。

#### `FLARESOLVERR_SOURCE_DIR`

- 可选。
- 覆盖 repo-local FlareSolverr workflow 根目录。

本地 FlareSolverr 限速变量与账本已移除；browser workflow 不再读取 `FLARESOLVERR_MIN_INTERVAL_SECONDS`、`FLARESOLVERR_MAX_REQUESTS_PER_HOUR` 或 `FLARESOLVERR_MAX_REQUESTS_PER_DAY`。

更具体的启动与排障步骤见 [`flaresolverr.md`](flaresolverr.md)。

## 运行时护栏

### HTTP 连接池与缓存

`HttpTransport` 带短 TTL 的进程内 GET 缓存和可选磁盘 textual GET 缓存：

- 同一 DOI 的重复 Crossref / metadata 请求可直接命中缓存
- 只有小体积文本响应会入缓存
- PDF 和其他大体积二进制正文不会缓存
- 缓存 key 会脱敏 `api_key`、token、`mailto` 等敏感 query 字段；`Authorization`、`X-ELS-APIKey`、Wiley / Elsevier token header 等敏感 header 会用短 SHA-256 digest 区分不同凭据，不把原文写入 cache key、磁盘路径或 structured log
- `RuntimeContext(download_dir=...)` 会默认启用磁盘 textual GET 缓存，位置是 `<download_dir>/.paper-fetch-http-cache/`
- 磁盘缓存支持 `ETag` / `Last-Modified` 条件请求；stale 条目收到 `304` 时复用本地 body
- `PAPER_FETCH_HTTP_DISK_CACHE_DIR` 可显式指定磁盘 HTTP 缓存目录
- `PAPER_FETCH_HTTP_DISK_CACHE=1` 且未设置下载目录时，会使用用户数据目录下的 `http-cache`
- `PAPER_FETCH_HTTP_METADATA_CACHE_TTL` 控制磁盘缓存 freshness 秒数，默认 `86400`（1 day）；普通进程内 GET TTL 仍默认 `30` 秒
- `PAPER_FETCH_HTTP_DISK_CACHE_MAX_ENTRIES` 控制磁盘 textual GET cache 最大条目数，默认 `4096`；设为 `0` 表示不限制条目数
- `PAPER_FETCH_HTTP_DISK_CACHE_MAX_BYTES` 控制磁盘 textual GET cache 最大总字节数，默认 `536870912`（512 MiB）；设为 `0` 表示不限制总大小
- `PAPER_FETCH_HTTP_DISK_CACHE_MAX_AGE_DAYS` 控制磁盘 textual GET cache 最大保留天数，默认 `30`；设为 `0` 表示不按年龄清理
- `HttpTransport.cache_stats_snapshot()` 返回线程安全的累计计数：`memory_hit`、`disk_fresh_hit`、`disk_stale_revalidate`、`disk_304_refresh`、`miss`、`store`、`bypass`；golden criteria live review 的 sample 结果写入相对执行前的 delta，最终汇总日志保留累计快照

连接池与同 host 并发默认较保守：

- `PAPER_FETCH_HTTP_POOL_NUM_POOLS`：默认 `16`
- `PAPER_FETCH_HTTP_POOL_MAXSIZE`：默认 `4`
- `PAPER_FETCH_HTTP_PER_HOST_CONCURRENCY`：默认 `4`
- `PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY`：默认 `4`，最小 `1`，控制 HTML / browser workflow / Elsevier body asset 下载 worker 上限

### HTTP 重试与大小限制

默认护栏包括：

- `max_response_bytes=32 MiB`
- 对 `5xx` 和 timeout 级网络错误做有限短重试
- `429` 只按 `Retry-After` 处理，不混进瞬时错误重试
- 底层使用 `urllib3.PoolManager` 复用连接
- Retry policy 使用 `urllib3.util.Retry` 表达；本地 wrapper 继续保留 public request options、structured logs、cancel checks、最大等待时间和 `RequestFailure` 形状

### `provider_status()`

`provider_status()` 只检查本地条件，不主动探测远端 publisher API 连通性。

当前 provider 语义大致是：

- `elsevier`
  - 只检查官方全文 API key；`ELSEVIER_API_KEY` 配好即 `ready`，否则 `not_configured`。
- `springer`
  - 返回本地 direct HTML route 就绪状态；不依赖 FlareSolverr。
- `wiley`
  - 统一检查 `runtime_env`、`repo_local_workflow`、`flaresolverr_health`，以及可选的 `tdm_api_token`。
  - browser runtime ready 时，即使 `WILEY_TDM_CLIENT_TOKEN` 缺失，也应表现为 `ready`。
  - browser runtime 未配置但 `WILEY_TDM_CLIENT_TOKEN` 已配置时，通常表现为 `partial`，仍可尝试官方 TDM API PDF lane；如果 browser 检查本身报 `error`，provider 状态仍会反映该错误。
- `science` / `pnas`
  - 统一检查 `runtime_env`、`repo_local_workflow`、`flaresolverr_health`。
