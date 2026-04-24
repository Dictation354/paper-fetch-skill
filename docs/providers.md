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
| `wiley` | 依赖 Crossref merge | `FlareSolverr HTML -> Wiley TDM API PDF -> seeded-browser publisher PDF/ePDF` | HTML 路线支持 `none` / `body` / `all`；PDF/ePDF fallback 当前 text-only | 中 | HTML 与 browser PDF/ePDF 依赖 repo-local FlareSolverr；`WILEY_TDM_CLIENT_TOKEN` 可在 browser runtime 不可用时单独启用官方 TDM PDF lane；必要时可返回 provider `abstract_only` |
| `science` | 依赖 Crossref | `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF` | HTML 路线支持 `none` / `body` / `all`；PDF/ePDF fallback 当前 text-only | 中 | 与 `wiley` 的 HTML / browser PDF/ePDF 路径共用浏览器工作流基座；AAAS access gate / entitlement 不满足时会停在 provider 内部并降级 `abstract_only` / `metadata_only` |
| `pnas` | 依赖 Crossref | `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF` | HTML 路线支持 `none` / `body` / `all`；PDF/ePDF fallback 当前 text-only | 中 | 与 `wiley` 的 HTML / browser PDF/ePDF 路径共用浏览器工作流基座；较老文献常见 HTML 仅摘要，再继续走 provider 内部 PDF/ePDF fallback，必要时可返回 `abstract_only` |

说明：

- 这张矩阵描述的是“当前代码里已经实现的 provider-owned waterfall”，不是“任意 DOI、任意运行环境都必然能拿到 publisher 全文”的承诺。
- 尤其 `wiley` / `science` / `pnas` 的浏览器与 PDF/ePDF 路径，仍受 publisher 访问权限、paywall/challenge 与本地限速护栏影响。
- `wiley` 的 HTML / browser PDF/ePDF 路径与 `science` / `pnas` 现在只保留一套 provider-owned 浏览器栈：共享 `_science_pnas` bootstrap、共享 `_pdf_fallback` browser-PDF executor，不再存在单独的 Science path harness。
- 2020+ live / regression 基准样本集中维护在 [`../tests/provider_benchmark_samples.py`](../tests/provider_benchmark_samples.py)。
- 自然地理学 live-only 候选集中维护在 [`../tests/live/geography_samples.py`](../tests/live/geography_samples.py)，默认每家尝试前 `10` 条，并通过 [`../scripts/run_geography_live_report.py`](../scripts/run_geography_live_report.py) 产出 JSON/Markdown 报告。
- `geography` live runner 默认按 provider 轮转执行，保持单家样本顺序不变，同时尽量避免浏览器型 publisher 被本地最小间隔窗口连续判成 `rate_limited`。
- `run_geography_live_report.py`、`export_geography_issue_artifacts.py`、`group_geography_issue_artifacts.py` 都属于 repo-local internal tooling：不新增 console script，不作为 MCP surface，对外产品面不变。
- geography live/report/export/group 仍受 `PAPER_FETCH_RUN_LIVE=1` 的 opt-in 边界保护；未启用 live 环境时，对应测试应稳定 skip。
- golden criteria live review 产物写入 `live-downloads/golden-criteria-review/`，由 [`../scripts/run_golden_criteria_live_review.py`](../scripts/run_golden_criteria_live_review.py) 生成；`10.1016/S1575-1813(18)30261-4` 这类预期 metadata-only 样本，以及当前不支持的 TandF / Sage 样本，应通过 manifest 的 expected outcome 标记为 `skipped`，不进入 provider bug 修复队列。

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
  - 固定顺序是 `FlareSolverr HTML -> Wiley TDM API PDF -> seeded-browser publisher PDF/ePDF -> abstract-only / metadata-only`。
  - `WILEY_TDM_CLIENT_TOKEN` 是官方 TDM API PDF lane；缺失时仍可继续尝试 browser PDF/ePDF，配置后也可以在 browser runtime 不可用时单独尝试 TDM PDF。
  - 成功时公开 `source="wiley_browser"`。
- `science`
  - 固定顺序是 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> abstract-only / metadata-only`。
  - 与 `wiley` 的 HTML / browser PDF/ePDF 路径共享同一套浏览器工作流基座。
  - 如果落到 AAAS 的 `Check access` / paywall 页面，应优先解读为 `institution not entitled / no access`，而不是 generic HTML fallback 缺失。
  - 成功时公开 `source="science"`。
- `pnas`
  - 固定顺序是 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> abstract-only / metadata-only`。
  - 与 `wiley` 的 HTML / browser PDF/ePDF 路径共享同一套浏览器工作流基座。
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

但它们的 fulltext 形态不同：

- `elsevier`
  - provider 自管 `官方 XML/API -> 官方 API PDF fallback`
  - 进入 PDF lane 时会组合 `fulltext:elsevier_xml_fail`、`fulltext:elsevier_pdf_api_ok`、`fulltext:elsevier_pdf_fallback_ok`
  - PDF lane 失败时会带 `fulltext:elsevier_pdf_api_fail`
- `springer`
  - provider 自管 `direct HTML -> direct HTTP PDF`
  - 成功轨迹是 `fulltext:springer_html_*`，PDF fallback 成功时会带 `fulltext:springer_pdf_fallback_ok`
- `wiley`
  - provider 自管 HTML + Wiley TDM API PDF + seeded-browser publisher PDF/ePDF waterfall
  - 成功轨迹是 `fulltext:wiley_html_*` / `fulltext:wiley_pdf_api_ok` / `fulltext:wiley_pdf_browser_ok` / `fulltext:wiley_pdf_fallback_ok`
  - 失败时若 API lane 未产出 PDF，会保留 `fulltext:wiley_pdf_api_fail`；若 browser PDF/ePDF lane 已实际尝试但失败，会再带 `fulltext:wiley_pdf_browser_fail`
- `science`
  - provider 自管 `FlareSolverr HTML + seeded-browser publisher PDF/ePDF`
  - `fulltext:science_html_fail` / `fulltext:science_pdf_fallback_ok` 只描述 provider 主链的阶段切换；如果页面本身就是 access gate，更准确的业务解释应是 `institution not entitled / no access`
  - 继续保持现有 `science` 风格的公开来源与轨迹命名
- `pnas`
  - provider 自管 `FlareSolverr HTML + seeded-browser publisher PDF/ePDF`
  - 较老文献可能先表现为 `fulltext:pnas_html_fail`，再进入 `fulltext:pnas_pdf_fallback_ok`
  - 继续保持现有 `pnas` 风格的公开来源与轨迹命名

因此：

- 不再存在 public HTML fallback 开关
- 对 `elsevier` 来说，系统始终按内部 `官方 XML/API -> 官方 API PDF fallback` waterfall 执行
- 对 `springer` 来说，系统始终按内部 `direct HTML -> direct HTTP PDF` waterfall 执行
- 对 `wiley` 来说，系统始终按内部 `FlareSolverr HTML -> Wiley TDM API PDF -> seeded-browser publisher PDF/ePDF` waterfall 执行
- 对 `science` / `pnas` 来说，系统始终按内部 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF` waterfall 执行

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
  - 下载正文 figure
  - 下载正文表格原图
  - 不包含 supplementary
- `all`
  - 下载当前 provider 已识别的全部相关资产
  - 包含 appendix / supplementary 等非正文资产；正文已经内联消费的图表仍会通过 `render_state` 从尾部重复附录中过滤

对 `elsevier` PDF fallback、`springer` PDF fallback、`wiley` / `science` / `pnas` 而言：

- `elsevier` PDF fallback 仍会把 `asset_profile=body|all` 降级成 text-only
- `springer` PDF fallback 仍会把 `asset_profile=body|all` 降级成 text-only
- `wiley` / `science` / `pnas` 的 `FlareSolverr HTML` 成功路径支持资产下载；figure 会优先尝试 full-size/original，直接请求被 challenge 或返回非图片时可走 Playwright image-document / canvas fallback，最后才按尺寸阈值接受 preview
- `wiley` / `science` / `pnas` 的 PDF/ePDF fallback 仍是 text-only

### 资产去重与诊断

- `render_state="inline"` 的资产表示正文已经渲染过，不会进入文末 `Figures` / `Tables`。
- `render_state="appendix"` 的资产仍可进入尾部兜底块；当同类资产全是 appendix 状态时，标题会显示为 `Additional Figures` / `Additional Tables`。
- 正文 Markdown 图片链接和资产路径会按 URL、路径、相对 `body_assets/...` 后缀和 basename 做等价比较，避免正文图在尾部重复。
- 下载资产会保留 `download_tier`、`download_url`、`original_url`、`content_type`、`downloaded_bytes`、`width`、`height`。
- `download_tier="playwright_canvas_fallback"` 表示普通 HTTP 没拿到真实图片，但浏览器 image document / canvas 导出保留了可视图片。
- `download_tier="preview"` 只有在宽高满足当前阈值 `300x200` 时才会标记为可接受 preview；否则仍会进入 preview fallback / asset issue 诊断。

### `include_refs`

- `max_tokens="full_text"` 时，默认等价于 `all`
- `max_tokens=<整数>` 时，默认等价于 `top10`

### 下载行为

- `--no-download` 或 `download_dir=None` 优先级最高
- 即使 `asset_profile` 是 `body` / `all`，也不会落盘
- 没有本地文件时，Markdown 会自动退回 captions-only 或不展示本地资源链接

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

### Markdown 与语义 normalize

- 公式输出会在公共公式 normalize 层处理 publisher-specific LaTeX 宏。
- `\updelta` 等 upright Greek 宏会改写成普通 KaTeX 可渲染宏；`\mspace{Nmu}` 会改写成 `\mkernNmu`，其它单位不改。
- Elsevier XML references 优先从结构化 bibliography 构建，保留编号、作者、题名、来源、页码、年份和 DOI；Crossref references 只作为兜底。

## 配置文件与环境变量入口

默认主配置文件：

```text
~/.config/paper-fetch/.env
```

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

#### `FLARESOLVERR_MIN_INTERVAL_SECONDS`

- browser 路径必填。
- Wiley / Science / PNAS 本地最小请求间隔。

#### `FLARESOLVERR_MAX_REQUESTS_PER_HOUR`

- browser 路径必填。
- Wiley / Science / PNAS 每小时上限。

#### `FLARESOLVERR_MAX_REQUESTS_PER_DAY`

- browser 路径必填。
- Wiley / Science / PNAS 每日上限。

更具体的启动与排障步骤见 [`flaresolverr.md`](flaresolverr.md)。

## 运行时护栏

### 进程内 HTTP 缓存

`HttpTransport` 带短 TTL 的进程内 GET 缓存：

- 同一 DOI 的重复 Crossref / metadata 请求可直接命中缓存
- 只有小体积文本响应会入缓存
- PDF 和其他大体积二进制正文不会缓存
- 缓存 key 会脱敏 `api_key`、token、`mailto` 等敏感字段

### HTTP 重试与大小限制

默认护栏包括：

- `max_response_bytes=32 MiB`
- 对 `5xx` 和 timeout 级网络错误做有限短重试
- `429` 只按 `Retry-After` 处理，不混进瞬时错误重试
- 底层使用 `urllib3.PoolManager` 复用连接

### `provider_status()`

`provider_status()` 只检查本地条件，不主动探测远端 publisher API 连通性。

当前 provider 语义大致是：

- `elsevier`
  - 只检查官方全文 API key；`ELSEVIER_API_KEY` 配好即 `ready`，否则 `not_configured`。
- `springer`
  - 返回本地 direct HTML route 就绪状态；不依赖 FlareSolverr。
- `wiley`
  - 统一检查 `runtime_env`、`repo_local_workflow`、`flaresolverr_health`、`rate_limit_window`，以及可选的 `tdm_api_token`。
  - browser runtime ready 时，即使 `WILEY_TDM_CLIENT_TOKEN` 缺失，也应表现为 `ready`。
  - browser runtime 未配置但 `WILEY_TDM_CLIENT_TOKEN` 已配置时，通常表现为 `partial`，仍可尝试官方 TDM API PDF lane；如果 browser 检查本身报 `error`，provider 状态仍会反映该错误。
- `science` / `pnas`
  - 统一检查 `runtime_env`、`repo_local_workflow`、`flaresolverr_health`、`rate_limit_window`。
