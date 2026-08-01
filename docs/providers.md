# Provider 能力与运行时行为

这份文档解决：

- 各 provider 能做什么、不能做什么
- 运行时如何做路由和回退
- 默认输出策略与下载行为
- 配置项、环境变量、限速与缓存护栏

这份文档不解决：

- agent runtime 的安装与 MCP 注册
- Wiley / Science / PNAS / Annual Reviews / Royal Society Publishing / ACS / IOP / AIP / MDPI 的 selected-browser runtime 运维边界
- 架构分层和数据契约的完整背景

部署入口见 [`deployment.md`](deployment.md)，架构说明见 [`architecture/overview.md`](architecture/overview.md)。安装后自包含的配置优先级、Chrome/CDP、公式/图片工具和诊断入口见 skill 的 [`environment.md`](../skills/paper-fetch-skill/references/environment.md)；agent 需要 provider/source/capability 名单时只读取动态 `resource://paper-fetch/provider-catalog`，不复制本页矩阵。逐 route 的顺序、runtime、并发、超时、acceptance 与资产范围见自动生成的 [`provider-routes.generated.md`](provider-routes.generated.md)。

<a id="provider-canonical-sources"></a>
`references/api_notes.md` 和 `references/routing_rules.md` 只保留 API 约束和补充说明；provider/routing/waterfall 的 canonical 事实来源是本文档和 `paper_fetch.provider_catalog.PROVIDER_CATALOG`。

## Provider 能力矩阵

<!-- SCAFFOLD: providers-capability-matrix -->
| Provider | 元数据 | 全文主路径 | 资产下载 | Markdown 能力 | 备注 |
| --- | --- | --- | --- | --- | --- |
| `crossref` | 支持 | 不负责 publisher fulltext | 不支持 | 不适用 | 负责 resolve、routing signal、metadata merge 与 metadata-only fallback |
| `elsevier` | 官方 API | `官方 DOI XML/API -> PII XML/API fallback -> 官方 API PDF fallback` | XML 路线支持 `none` / `body` / `all`；PDF fallback 在 `body/all` 且允许落盘时提取 PDF 图片到 `<doi>_assets/` | 强 | XML 成功时公开为 `elsevier_xml`；PDF fallback 成功时公开为 `elsevier_pdf`；PII fallback 来自 Crossref/landing metadata 中的 LinkingHub 或 ScienceDirect PII URL |
| `springer` | 依赖 Crossref merge | `direct HTML -> direct HTTP PDF` | HTML 路线支持 `none` / `body` / `all`；PDF fallback 在 `body/all` 且允许落盘时提取 PDF 图片到 `<doi>_assets/` | 强 | 对外保持单一 `springer` provider，内部按 `nature` / `springerlink` / `bmc` site-family profile 分类；HTML 成功公开 `springer_html`，PDF fallback 成功公开 `springer_pdf`；必要时可返回 provider `abstract_only` |
| `wiley` | 依赖 Crossref merge | `selected-browser HTML -> browser-seeded publisher PDF/ePDF -> Wiley TDM API PDF` | HTML 路线支持 `none` / `body` / `all`；PDF/ePDF fallback 可提取 PDF 图片 | 中 | HTML 默认通过 Camoufox；TDM token 可在 browser runtime 不可用时继续官方 PDF lane |
| `science` | 依赖 Crossref | `selected-browser HTML -> browser-seeded publisher PDF/ePDF` | HTML 路线支持 `none` / `body` / `all`；PDF/ePDF fallback 可提取 PDF 图片 | 中 | 与 Wiley 共用 selected-browser workflow；access gate 不满足时可降级 |
| `pnas` | 依赖 Crossref | `selected-browser HTML -> browser-seeded publisher PDF/ePDF` | HTML 路线支持 `none` / `body` / `all`；PDF/ePDF fallback 可提取 PDF 图片 | 中 | PNAS 走普通 selected-browser HTML bootstrap，老文献可继续 PDF/ePDF fallback |
| `ams` | 依赖 Crossref | `DOI landing -> selected-browser HTML -> browser-seeded PDF fallback` | HTML 路线支持 `none` / `body` / `all`；正文 figure 优先 AMS `Download Figure` EPS/TIFF 源图并转 PNG，失败回退网页 JPG/PNG；PDF fallback 在 `body/all` 且允许落盘时提取 PDF 图片到 `<doi>_assets/` | 中 | AMS 默认用 Camoufox 打开 `journals.ametsoc.org/view/...xml` 并允许站点静默完成 JavaScript/WAF 验证；无保存状态也会尝试，有 provider storage-state 时自动复用；HTML 不可用时用同一 browser seed 尝试 `downloadpdf` PDF；通用 SICI DOI 提取会保留 `<...>` / `;` 后缀；显式忽略 `citation_xml_url`，不请求 `/doc/...xml`，不暴露 XML/JATS source；HTML 成功公开 `ams_html`，PDF fallback 成功公开 `ams_pdf` |
| `mdpi` | 依赖 Crossref merge | `selected-browser HTML -> browser-seeded article PDF` | HTML 路线支持 `none` / `body` / `all`；PDF fallback 可提取 PDF 图片 | 中 | MDPI direct HTTP 常受 CDN 策略影响，主路径使用所选浏览器捕获公开 article HTML |
| `ieee` | 依赖 Crossref merge + landing metadata | `direct landing -> selected-browser landing -> direct REST HTML -> selected-browser HTML -> direct PDF -> selected-browser PDF` | HTML 路线支持 `none` / `body` / `all`，figure/table/formula 和补充文件 direct-first browser recovery；PDF fallback 在 `body/all` 且允许落盘时提取 PDF 图片 | 中 | direct 成功不启动浏览器；eligible asset failure 在同一论文页 context/page 中串行恢复并复用最新 cookie/Referer；不对 `404/410/429` 做 browser recovery，不处理 CAPTCHA、登录自动化或权限绕过 |
| `arxiv` | arXiv ID + 默认 Atom API enrichment | `ID 解析 -> arXiv official HTML -> direct HTTP PDF -> metadata fallback` | HTML 路线支持正文 figure 资产下载；official HTML 只给缺失图片占位符时，会尝试从 arXiv e-print source 包恢复图资产；PDF fallback 在 `body/all` 且允许落盘时提取 PDF 图片到 `<doi>_assets/` | 中 | HTML front matter 在主路径内合并；默认使用内部 arXiv Atom API client 在 HTML/PDF 主链结束后补齐 metadata，失败只追加 warning、不影响已得到的 fulltext payload；HTML 成功公开为 `arxiv_html`，PDF fallback 公开为 `arxiv_pdf`；可识别的 ID 形态（含 `vN` 版本、`10.48550/arXiv.*` 等）见后文 arXiv 小节 |
| `copernicus` | 依赖 Crossref merge + landing metadata | `landing HTML / DOI-derived URL -> NLM/JATS XML -> direct HTTP PDF -> metadata fallback` | XML 路线支持 `none` / `body` / `all`；PDF fallback 在 `body/all` 且允许落盘时提取 PDF 图片到 `<doi>_assets/` | 强 | 开放获取 direct HTTP 路线，不需要登录态或本地浏览器运行时；XML 成功公开为 `copernicus_xml`，PDF fallback 公开为 `copernicus_pdf` |
| `royalsocietypublishing` | Crossref/DOI browser HTML metadata merge | `selected-browser DOI HTML -> browser-seeded PDF -> metadata fallback` | HTML 路线支持 `none` / `body` / `all`；PDF fallback 在 `body/all` 且允许落盘时提取 PDF 图片到 `<doi>_assets/` | 强 | Royal Society Publishing 通过 `10.1098/` DOI 和 `royalsocietypublishing.org` 路由；HTML 成功公开为 `royalsocietypublishing_html`，PDF fallback 公开为 `royalsocietypublishing_pdf`；需要 Playwright/browser runtime；显式不把 `citation_xml_url` 当作 XML/JATS 路线 |
| `annualreviews` | 依赖 Crossref routing | `selected-browser landing/full-text HTML -> browser-seeded PDF -> provider-managed abstract_only -> metadata fallback` | HTML 路线支持 `none` / `body` / `all`；PDF fallback 在 `body/all` 且允许落盘时提取 PDF 图片到 `<doi>_assets/` | 中 | Annual Reviews 通过 `10.1146/` DOI 和 `annualreviews.org` 域名路由，排除 Knowable Magazine / 非 article 样本；HTML 成功公开为 `annualreviews_html`，PDF fallback 公开为 `annualreviews_pdf`；需要 Playwright/browser runtime |
| `plos` | 依赖 Crossref routing | `public JATS XML -> direct HTTP PDF -> metadata fallback` | XML 路线支持 `none` / `body` / `all`；PDF fallback 在 `body/all` 且允许落盘时提取 PDF 图片到 `<doi>_assets/` | 强 | PLOS 通过 `10.1371/` DOI prefix 和 `journals.plos.org` 路由；XML 成功公开为 `plos_xml`，PDF fallback 公开为 `plos_pdf`；按 access review 不把 HTML 作为全文路线 |
| `frontiers` | Frontiers domain / DOI routing | `canonical JATS XML -> canonical PDF -> landing discovery -> JATS XML/PDF -> metadata fallback` | XML 路线支持 `none` / `body` / `all`：正文图 direct-first；绝对 supplementary URL 仅在 `all` 归档，未发布直链的相对附件明确标为 `not_archived`；PDF fallback 可导出 PDF 图片 | 强 | Frontiers 通过 `10.3389/` DOI prefix 和 `www.frontiersin.org` 路由；XML 成功公开为 `frontiers_xml`，PDF fallback 公开为 `frontiers_pdf` |
| `oxfordacademic` | DOI prefix/domain routing for Oxford Academic public articles | `direct HTTP article HTML -> direct HTTP PDF fallback -> metadata fallback` | HTML 路线支持 `none` / `body` / `all`，正文 figure/formula 和 supplementary 使用 Silverchair 共享资产下载器并 direct-first；下载后改写本地链接。PDF fallback 使用稳定 article-pdf URL，只接受已验证 PDF，并可导出 PDF 图片 | 中 | `oxfordacademic_html` / `oxfordacademic_pdf` |
| `acs` | 依赖 Crossref routing | `selected-browser Silverchair HTML -> browser-seeded publisher PDF/ePDF with browser-navigation direct PDF preflight -> provider-managed abstract_only` | HTML 路线支持 `none` / `body` / `all`，识别当前 `.article-body` / `.widget-ArticleFulltext`、`.fig.fig-section`、`.ref-list` 和 `.widget-ArticleDataSupplements`；PDF/ePDF fallback 在 `body/all` 且允许落盘时提取 PDF 图片到 `<doi>_assets/` | 中 | ACS 通过 `10.1021/` DOI、用户指定的 `www.acs.org` 域和实际文章 host `pubs.acs.org` 路由，公开 source 为 `acs` |
| `iop` | Crossref routing | selected-browser article HTML -> browser-seeded IOP PDF -> provider-managed abstract_only -> metadata fallback | HTML body figures plus two-stage supplementary downloads; PDF fallback assets | 中 | IOP uses 10.1088/ routing; Radware/hCaptcha pages are rejected; public sources `iop_html` / `iop_pdf`; catalog 单独声明经 access review 后暂无稳定公共 TDM XML/API route |
| `aip` | 依赖 Crossref routing | `selected-browser AIP article HTML -> browser-seeded AIP PDF -> provider-managed abstract_only -> metadata fallback` | HTML 路线支持 `none` / `body` / `all`；PDF fallback 在 `body/all` 且允许落盘时提取 PDF 图片到 `<doi>_assets/` | 中 | AIP 通过 `10.1063/` DOI 和 `pubs.aip.org` 路由；HTML 成功公开 `aip_html`，PDF fallback 公开 `aip_pdf` |

说明：

- 这张矩阵描述的是“当前代码里已经实现的 provider-owned waterfall”，不是“任意 DOI、任意运行环境都必然能拿到 publisher 全文”的承诺。
- 尤其 `wiley` / `science` / `pnas` / `ams` / `annualreviews` / `acs` / `iop` / `aip` / `mdpi` 的浏览器与 PDF/ePDF 路径，仍受 publisher 访问权限、paywall/challenge 与远端站点行为影响。
- Provider/source/domain/API/fallback marker、候选 URL 模板、HTML artifact 持久化、XML provider 推断与正文阈值的事实来源是 `paper_fetch.provider_catalog.ProviderSpec`。`SOURCE_PROVIDER_MAP` 登记实际 envelope / `ArticleModel.source` 值；例如 Springer HTML / PDF fallback 分别公开 `springer_html` / `springer_pdf`，二者都映射到 `springer` provider。
- MCP 宿主不应从工具 description 或本文抽取静态名单；请通过 `resources/list` 发现并用 `resources/read` 读取 `resource://paper-fetch/provider-catalog`。该 JSON 每次直接从 runtime catalog/source map 生成，包含版本、provider/source、逐 route runtime/timeout/concurrency/rate/acceptance/assets、status/preflight 能力和资产默认值；它是机器可读 catalog 的权威入口，但不是本地就绪或远端可访证明。仓库同时提交 [`../quality/provider-catalog.json`](../quality/provider-catalog.json) 快照，CI 用它检查 runtime 与文档漂移。
- `wiley` / `science` / `pnas` / `ams` / `annualreviews` / `royalsocietypublishing` / `acs` / `iop` / `aip` / `mdpi` 只保留一套 provider-owned 浏览器栈，canonical runtime 是 `paper_fetch.providers.browser_workflow` 包入口。
- browser workflow 的 bootstrap、PDF/ePDF fallback、article assembly、asset retry helper、client 基类和 browser fetchers 由 `browser_workflow/` 子包维护；storage-state 默认面向 provider catalog 中的浏览器 provider。
- publisher 差异通过各 provider 模块 callback 下沉；browser-PDF executor 继续共享 `_pdf_fallback`，公开入口使用 `browser_workflow` 包。
- browser-workflow 的 HTML bootstrap 通过 `RuntimeContext` 复用所选 backend manager；每次操作使用隔离 context，Camoufox 同步对象保持 caller-thread 绑定。
- 2020+ live / regression 基准样本集中维护在 [`../tests/provider_benchmark_samples.py`](../tests/provider_benchmark_samples.py)。
- 自然地理学 live-only 候选集中维护在 [`../tests/live/geography_samples.py`](../tests/live/geography_samples.py)，默认每家尝试前 `10` 条，并通过 [`../scripts/run_geography_live_report.py`](../scripts/run_geography_live_report.py) 产出 JSON/Markdown 报告。
- `geography` live runner 默认按 provider 轮转执行，保持单家样本顺序不变。
- `run_geography_live_report.py`、`export_geography_issue_artifacts.py`、`group_geography_issue_artifacts.py` 都属于 repo-local internal tooling：不新增 console script，不作为 MCP surface，对外产品面不变。
- geography live/report/export/group 仍受 `PAPER_FETCH_RUN_LIVE=1` 的 opt-in 边界保护；未启用 live 环境时，对应测试应稳定 skip。
- golden criteria live review 产物写入 `live-downloads/golden-criteria-review/`，由 [`../scripts/run_golden_criteria_live_review.py`](../scripts/run_golden_criteria_live_review.py) 生成；每条结果包含 `elapsed_seconds`、`stage_timings.fetch_seconds` / `materialize_seconds` / `total_seconds` / `resolve_seconds` / `metadata_seconds` / `fulltext_seconds` / `asset_seconds` / `formula_seconds` / `render_seconds`，同时在 `http_cache_stats` 中记录该 sample 相对执行前的 cache delta。golden criteria live review 的 supported provider 从 runtime `official_provider_names()` 派生，覆盖 `elsevier`、`springer`、`wiley`、`science`、`pnas`、`ieee`、`arxiv`、`copernicus`、`ams`、`mdpi`、`royalsocietypublishing`、`annualreviews`、`plos`、`oxfordacademic`、`acs`、`iop`、`aip` 和 `frontiers`；`provider-status.json` 会包含这些 provider 的本地诊断。`10.1016/S1575-1813(18)30261-4` 这类预期 metadata-only 样本，以及不受支持的 TandF / Sage 样本，应通过 manifest 的 expected outcome 标记为 `skipped`，不进入 provider bug 修复队列。IEEE golden live 样本面向具备合法 IEEE Xplore 授权上下文的机器，预期为 `fulltext`；降级成 metadata-only、blocked fetch 或非 PDF payload 应作为 `live_fetch_blocked` 问题进入修复队列。

### Copernicus

`copernicus` 已接入当前 runtime，默认语义是 `fulltext_first`。Copernicus Publications 是开放获取出版社，正常情况下不需要登录态、机构授权或本地浏览器运行时。

固定主路径：

```text
resolve DOI / landing URL
-> direct landing HTML, or DOI-derived XML/PDF candidates if landing is unavailable
-> discover citation_xml_url / article XML link
-> NLM/JATS XML -> Markdown
-> direct HTTP PDF fallback
-> metadata-only fallback
```

实现细节：

- 路由信号来自 `ProviderSpec.domain_suffixes=("copernicus.org",)`、Crossref publisher alias `Copernicus Publications`，以及 DOI prefix `10.5194/`。
- 优先从 landing HTML 的 `citation_xml_url` 或正文下载链接发现 XML；如果 landing 抓取失败，会记录 warning 并继续尝试 DOI 形态拼出的 XML/PDF URL。PDF fallback 也优先使用 landing 暴露的 `citation_pdf_url` / `.pdf` 链接，最后再尝试 DOI 形态拼出的 `.pdf` URL，以覆盖早期 landing 缺少 PDF meta 的文章。
- XML 必须校验 NLM/JATS article root、`front/article-meta`、正文 `body/sec`、非空摘要，以及至少一个含 `<p>` 的正文 section 和足够正文字符数，不能只按 HTTP 200 判定成功；正文字符阈值来自 `ProviderSpec.body_text_thresholds`，Copernicus 只覆盖 `min_chars=500`。
- 早期 Copernicus XML 可能返回 `200 application/xml` 且有 `front/article-meta`，但 `body` 为空、没有 `sec`，实际只包含摘要级内容；这类 XML 必须失败并继续 PDF fallback，不经过 HTML 全文 fallback。
- XML 成功时公开 `source="copernicus_xml"`，source trail 为 `fulltext:copernicus_xml_ok`；PDF fallback 成功公开 `copernicus_pdf`。
- XML renderer 复用 `paper_fetch.providers._article_markdown_jats` 的通用 JATS 层覆盖标题、作者、摘要、正文 section、图表 caption、OASIS/HTML 表格、MathML display formula、references、data/code availability 和 supplementary links；table / figure / formula / list 的最终 Markdown 行渲染统一走 `paper_fetch.extraction.markdown_render`，Copernicus 模块只保留该路线的 provider 适配入口。
- Copernicus 没有 provider-owned HTML fallback，也不注册 HTML cleanup / availability hook；XML 不可用时直接进入 PDF fallback，再失败才进入 metadata-only fallback。
- `asset_profile=body` 默认保留正文 figure / table / formula 资产；`asset_profile=all` 额外允许明确 supplementary scope 的附件。PDF fallback 在 `body/all` 且允许 artifact 落盘时会保存 `pymupdf4llm` 导出的 PDF 正文图片到 `<doi>_assets/`。
- Golden corpus 覆盖 8 篇现代 XML 主路径样本，以及 4 篇早期 abstract-only XML 落到 PDF fallback 的样本。
- `probe_status()` 只做本地能力说明，返回 direct XML/PDF fallback ready，不探测远端 Copernicus 站点。
- Copernicus 同时提供 OAI-PMH；它适合批量或补充发现，不作为单篇 DOI 的首个必需网络步骤。

### PLOS

`plos` 已接入当前 runtime，默认语义是 `fulltext_first`。PLOS 文章主路线使用公开 JATS XML，不需要登录态、机构授权或本地浏览器运行时。

固定主路径：

```text
resolve DOI / landing URL
-> 已知 journal code 使用版本化 route resource；未知 code 通过 DOI/canonical landing 发现
-> public JATS XML -> Markdown
-> direct HTTP PDF fallback
-> metadata-only fallback
```

实现细节：

- 路由信号来自 `journals.plos.org`、`ProviderSpec.domain_suffixes=("plos.org",)`、Crossref publisher alias `Public Library of Science (PLoS)`，以及 DOI prefix `10.1371/`。
- XML URL 优先使用 `src/paper_fetch/resources/journal_routes/plos.json` 的版本化 DOI journal-code 映射，例如 `journal.pone` -> `plosone`、`journal.pbio` -> `plosbiology`、`journal.pcbi` -> `ploscompbiol`，并请求 `article/file?id={doi}&type=manuscript`。未知但合法的 journal code 不再直接失败，而是经 DOI resolver/canonical landing metadata 发现同一 PLOS article base；发现结果只进入当前 attempt diagnostics，不静默修改生产 route resource。该公开 endpoint 返回 3xx 时会受控跟随最多 4 次 HTTP(S) 重定向，包括 PLOS 临时签发的 Google Cloud Storage XML URL；全部 `X-Goog-*` 查询值在 cache key、日志和保留的 source URL 中脱敏，包含签名 Location 的重定向响应不进入内存或磁盘 HTTP cache。
- XML 成功时公开 `source="plos_xml"`，source trail 为 `fulltext:plos_xml_ok`；XML 不可用或返回 HTML wrapper 时继续尝试 printable PDF，成功时公开 `source="plos_pdf"`。
- XML renderer 复用 `paper_fetch.providers._article_markdown_jats` 的通用 JATS 层覆盖标题、作者、摘要、正文 section、图表 caption、MathML display formula、references 和 supplementary links。
- `asset_profile=body` 默认下载正文 figure 和 graphic-only formula image；`asset_profile=all` 额外尝试下载 supplementary files。PLOS 的 `info:doi/...g001` figure 链接会解析为 `article/figure/image?size=large&id=...`，`info:doi/...e001` formula 链接会解析为 `article/file?id=...&type=thumbnail`，并跟随 PLOS 返回的签名图片重定向保存真实 PNG 后再改写 Markdown 本地路径。PDF fallback 在 `body/all` 且允许 artifact 落盘时会保存 `pymupdf4llm` 导出的 PDF 正文图片到 `<doi>_assets/`。
- PLOS 没有 provider-owned HTML fallback；XML 和 PDF 都不可用时直接进入 metadata-only fallback。

### Frontiers

`frontiers` 已接入当前 runtime，默认语义是 `fulltext_first`。Frontiers 文章主路线使用公开 JATS XML，不需要登录态、机构授权或本地浏览器运行时。

固定主路径：

```text
resolve DOI / landing URL
-> metadata/canonical URL 已含 journal slug：直试 canonical JATS XML
-> canonical direct HTTP PDF fallback
-> direct routes 不可用或缺 journal slug 时才请求 landing 做 route discovery
-> discovered JATS XML / PDF
-> metadata-only fallback
```

实现细节：

- 路由信号来自 `www.frontiersin.org` / `frontiersin.org` 域名、Crossref publisher alias `Frontiers Media S.A.`，以及 DOI prefix `10.3389/`。
- Frontiers canonical XML 路径需要 journal slug，例如 `/journals/marine-science/articles/10.3389/fmars.2023.1101972/xml`。metadata、source URL 或 fulltext link 已含 canonical `/journals/{journal}/articles/{doi}` 时，provider 直接按 `/xml -> /pdf` 顺序尝试，不请求 landing；只有 direct route 不可用、旧 URL 或缺 journal slug 时，才通过 landing redirect/metadata 发现 route。diagnostics 的 `route_discovery.reason` 与 `landing_requested` 会解释为何进入 landing。
- XML 成功时公开 `source="frontiers_xml"`，source trail 为 `fulltext:frontiers_xml_ok`；XML 不可用、返回 HTML wrapper 或正文不可用时继续尝试 direct HTTP PDF，成功时公开 `source="frontiers_pdf"`。
- XML renderer 复用 `paper_fetch.providers._article_markdown_jats` 的通用 JATS 层覆盖标题、作者、摘要、正文 section、图表 caption、tables、references 和 supplementary links。JATS 的 HTML-like table 与 CALS `tgroup/colspec` 都进入共享 XML adapter：表头前的整表宽度分组提升为普通文本，正文分组保留为首列行，多层表头按列扁平化，rowspan/局部 colspan/`namest`/`nameend` 做语义展开并以 `table_layout_degraded` 标记 Markdown 无法保留的合并布局。
- Frontiers XML 的 figure `xlink:href` 通常是相对 `.tif` 文件名；provider 会把可识别文件名改写为 `/files/Articles/{article_id}/xml-images/{stem}.webp`，再用共享 direct-first asset download。JATS 资产保留原始 `source_href`：明确的绝对 HTTP(S) supplementary URL 可下载；仅由 XML base URL 拼接出来的相对文件名不猜测附件路径，而是指向 canonical full page 的 `#supplementary-material`，并记录 `archive_state=not_archived` 与逐资产失败原因。
- `asset_profile=body` 默认下载正文 figure 且忽略 supplementary；`asset_profile=all` 额外归档明确绝对 supplementary URL，并把无法归档的条目显式报告为 partial asset failure。PDF fallback 在 `body/all` 且允许 artifact 落盘时会保存 `pymupdf4llm` 导出的 PDF 正文图片到 `<doi>_assets/`。
- Frontiers 没有 provider-owned HTML fallback；XML 和 PDF 都不可用时直接进入 metadata-only fallback。

### MDPI

`mdpi` 已接入当前 runtime，默认语义是 `fulltext_first`。MDPI 公开文章 direct HTTP 常返回 CDN 级拒绝或空壳，因此 provider 主路径固定走 selected browser 捕获公开 article HTML，不把 CDN 传输失败误判成无全文权限。

固定主路径：

```text
resolve DOI / landing URL
-> selected-browser article HTML
-> provider-owned MDPI HTML -> Markdown
-> browser-seeded article PDF fallback
-> metadata-only fallback
```

实现细节：

- 路由信号来自 `www.mdpi.com` / `mdpi.com` 域名、Crossref publisher alias `MDPI AG`，以及 DOI prefix `10.3390/`。MDPI 经典数字 article URL 会在解析阶段按 provider-owned ISSN 映射推导 DOI（例如 `2072-4292/18/10/1673` -> `10.3390/rs18101673`），MDPI DOI / DOI URL 会在 provider 阶段反推对应数字 article URL，这样已知期刊 URL 不需要先用普通 HTTP 抓 landing page，Crossref landing 缺失时也不只剩 `doi.org` 候选。
- HTML 成功公开 `source="mdpi_html"`；PDF fallback 成功公开 `source="mdpi_pdf"`。
- MDPI HTML cleanup 由 `paper_fetch.providers._mdpi_html` compatibility facade 暴露，canonical owner 分拆到 `_mdpi_dom`、`_mdpi_markdown`、`_mdpi_assets`、`_mdpi_authors` 和 `_mdpi_references`，去掉页面导航、SciProfiles 弹层、分享/引用/metrics chrome、Google Scholar / CrossRef / PubMed / Green Version reference linkout UI，同时保留正文 section、references、figures、tables、formula 和 supplementary section；MDPI reference `li data-content` 中的出版社编号会写回 raw citation，使最终 References 保持编号列表。HTML MathML 在该阶段复用共享转换器输出 `$...$` / `$$...$$` LaTeX Markdown，并保留源站公式编号。`.html-disp-formula-info` / `math[display=block]` 保持 display 公式块；段落内只承载变量、inline MathML、citation、`<sub>` / `<sup>` 或 `html-italic` / `html-bold` 的 MDPI wrapper 会转为 inline，避免变量解释被空行切碎。没有 MathML 的 HTML-only 化学式 / 反应式会保留 `<sub>` / `<sup>` 行内语义，压缩成单个公式块，不输出碎片行。
- MDPI HTML renderer 会把正文 figure / table display object 按正文首次 `Figure N` / `Fig. N` / `Table N` 引用锚定；无正文引用的对象按源顺序插入 References 前。caption、label 和 popup display 副本在 DOM 阶段去重，避免裸 `Figure N.` / `Table N.` 或重复 caption 泄漏到 Markdown。
- MDPI HTML `<table>` 复用共享 HTML table renderer 输出 Markdown table；复杂表格展不平时降级为单个去重文本块，不拆成散乱字段。正文 figure / table / formula 图片统一使用短 alt Markdown 图片行，例如 `![Figure 1](...)`；完整 caption 只保留在下一段或结构化表格标题中。
- MDPI `#html-keywords` 会写入 extraction payload 的 `keywords` 并合并进 `metadata.keywords`，不会作为独立 Markdown section，也不会混入 Abstract。
- PDF fallback 的正文 Markdown 仍由共享 PDF 转换生成；在 `body/all` 且允许 artifact 落盘时，会保存 PDF 中可导出的正文图片到 `<doi>_assets/`。Supplementary 下载仅对 HTML 路径启用。
- `asset_profile=body` 发现正文 figure / formula / table 图片；`asset_profile=all` 额外包含 MDPI article `/s1` 等 supplementary link。MDPI HTML 资产下载复用 browser workflow 的 shared browser image/file fetcher、seed refresh 与 retry 机制，以覆盖 direct HTTP 图片 403/CDN HTML 响应；下载后正文图片链接会改写到 `body_assets/...`，并把已匹配的 MDPI body image 资产标记为 `render_state="inline"`，避免文末 `Figures` / `Tables` 重复追加。
- MDPI 已纳入 golden criteria live review；HTML 主路径必须保留 Markdown 块边界和结构化正文，只有 HTML 不可用时才进入 `mdpi_pdf` 降级。
- Golden corpus 覆盖 8 个真实 selected-browser HTML DOI fixture，以及 1 个真实 browser PDF fallback fixture；`abstract_only` / `access_gate` / `empty_shell` 在 manifest 中记录为无稳定样本，因为当前 MDPI 路线按开放获取文章接入。

### IEEE

`ieee` 已接入当前 runtime，默认语义是 `fulltext_first`：

- 默认尝试获取全文，而不是默认停在摘要或元数据。
- 该默认行为假设操作者运行环境已经具备 IEEE Xplore 的合法访问权限，例如机构 IP、VPN、已登录浏览器态或个人订阅。
- 默认尝试不等于保证全文；如果授权、网络、站点状态或返回内容不满足全文条件，必须自动降级到 provider-managed `abstract_only` 或通用 `metadata_only` fallback。
- 不绕过 IEEE access gate，不处理验证码，不伪造授权状态；只能使用操作者已经具备的访问上下文。

固定主路径：

```text
resolve DOI / landing URL
-> extract IEEE article number
-> GET https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true
-> validate dynamic full-text HTML
-> if direct REST HTML is not usable, open the Xplore document page with the selected browser and capture REST/DOM HTML
-> validate browser-captured full-text HTML
-> provider-owned IEEE HTML -> Markdown
-> direct HTTP PDF fallback
-> selected-browser PDF fallback
-> abstract-only / metadata-only fallback
```

实现细节：

- 路由信号应来自 `ieeexplore.ieee.org` 域名、Crossref publisher alias `IEEE` / `Institute of Electrical and Electronics Engineers`，以及 DOI prefix `10.1109/`。
- article number 可从 IEEE landing URL、DOI 落地页中的页面元数据或 Crossref landing URL 推导；URL 解析只接受 `https://ieeexplore.ieee.org/document/{article_number}/` 这类 landing path，`/rest/document/...`、`stamp.jsp?arnumber=...` 等内部 route 不作为 landing URL contract。
- 动态全文端点返回的是 HTML fragment，常见 `content-type` 是 `text/html;charset=utf-8`，不能按 JSON API 处理。
- 请求头至少应保留 publisher 页面上下文，例如 `Accept: application/json, text/plain, */*`、对应 document URL 的 `Referer`、`x-security-request: required` 和浏览器 UA。
- 成功判定不能只看 HTTP `200`；需要校验返回体包含 `#article`、章节节点、足够正文段落或其他 IEEE full-text marker，并排除登录页、拦截页、摘要页、空壳和错误 HTML。
- IEEE access-block 检测复用 `COMMON_ACCESS_BLOCK_TOKENS` 中的通用 challenge / block 文本，只在 `IEEE_ACCESS_BLOCK_TEXT_TOKENS` 中追加 `institutional sign in`、`purchase access` 等 Xplore 专属访问入口，避免把通用反爬语义重复编码到 IEEE。
- 动态 HTML 成功时公开 `source="ieee_html"`；PDF fallback 成功时公开 `source="ieee_pdf"`。
- PDF fallback 先保留 direct HTTP 尝试；如果 IEEE `stamp.jsp` / `pdfPath` 返回 HTML/JS wrapper、网络错误、redirect loop 或 access page，会用 document landing seed 进入 selected-browser PDF fallback；明确 HTTP `404/410/429` 不启动浏览器。
- selected-browser PDF fallback 只复用操作者当前运行环境可合法取得的页面上下文和 cookies；不会处理 CAPTCHA、登录自动化或权限绕过。
- PDF fallback 只接受真实 PDF payload；如果 browser route 仍返回 access gate、challenge、APM/temporary unavailable 页面或非 PDF wrapper，会被拒绝并继续降级。失败诊断会记录 candidate URL、final URL、status、content-type、title/body 摘要；配置了 `download_dir` 且 artifact mode 为 `all` 时会在 `ieee_pdf_fallback/pdf.failure.html` 留下最后的非 PDF HTML 产物。
- 动态 HTML 的正文清洗会删除裸露 `SECTION I.` 这类 Xplore section marker；`div.section` / `div.section_2` 按嵌套层级输出 Markdown heading，主节为 `##`，`A.` / `B.` 子节为 `###`，`1)` 子节为 `####`。
- IEEE HTML cleanup 只声明 Xplore REST fragment 或站点专属增量，例如 `accesstype`、`select` / `textarea`、`.zoom-container`、`.document-actions`、`button[data-docId]` 和 `javascript:` action 链接；`script` / `style` / `noscript` / `iframe` / `button` / `input` 等通用 chrome 继续由默认站点规则和 browser workflow 负责。
- IEEE `tex-math` / `disp-formula` 会复用共享公式规则输出 LaTeX，不应退化成 `[Formula unavailable]`；如果仍然缺公式，`article.quality.semantic_losses.formula_missing_count` 会反映 Markdown 中的缺失占位数量。
- IEEE `ref-type="bibr"` 数字引用会进入共享 citation sentinel/normalize 链路，清理后不应遗留 `,,`、`(e.g., and)` 这类标点残留。
- 动态 HTML 中 IEEE `figure-full` / `figure-full table` 块里的 `/mediastore/IEEE/content/media/...` 正文图片和表格图片会先按 Xplore 域名绝对化，作为内联图片锚定在首次 caption 位置，并统一用 `https://ieeexplore.ieee.org/document/{article_number}/` 作为 seed 与 mediastore `Referer` 下载正文资产；full-size direct 候选遇到 `401/403`、HTML challenge 或可恢复网络错误后，图片、表格、multimedia 和 supplementary browser fetcher 会串行复用同一论文页 context/page，等待 HTTP 202 验证完成并取得最新 cookie 后从页面内发起请求，且不会把共享 page 导航到资产 URL。browser full-size 仍失败时才降级 preview。已内联图表通过 `render_state=inline` 避免在尾部 Figures / Tables 附录重复追加。`/assets/img/icon.support.gif` 这类 Xplore UI / 占位图标会在 HTML 清洗和资产列表中被过滤，不作为论文资产下载。
- IEEE 资产去重以 Xplore 页面结构为更强语义信号；当同一 mediastore URL 同时被识别为 table / figure 和通用 formula 图片时，保留 table / figure，并把下载结果回填到高优先级资产上。
- IEEE landing metadata 中的 Index Terms / Author Keywords / IEEE Keywords 会合并到 `metadata.keywords`；references 优先从 IEEE `/rest/document/{article_number}/references` 的可见 citation text 构建。该 route 成功返回非空 references 时会完全覆盖 Crossref / metadata fallback，不追加未匹配的 DOI-only 或 title-only 条目；只有该 route 不可用或返回空 references 时才保留 fallback references。
- 动态 HTML 中的正文图片、表格图片和公式节点按普通 `asset_profile=body|all` 语义接入；`asset_profile=all` 会额外下载明确 Supplementary / Supporting Material / Multimedia 附件区域中的文件，或 landing metadata 明确暴露 `sections.multimedia=true` 后从 `/rest/document/{article_number}/multimedia` payload 识别出的文件，且不局限于图片 content-type；普通正文里的 `data` / `dataset` / `code` / `media` 链接不会仅凭文本或后缀被归类为 supplementary。
- IEEE PDF fallback 的正文 Markdown 仍来自共享 PDF 转换；`body/all` 且允许 artifact 落盘时可保存 PDF 导出的正文图片。资产下载失败不应把已成功的正文 Markdown 判为失败。

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
- 当 MCP 使用 structured `title` / `authors` / `year` resolve 时，Crossref title query 只包含 title；authors/year 分别作为候选消歧信号，不拼入标题字符串。

### `crossref` 作为 signal 与 source 的区别

`crossref` 有两种角色：

1. 作为 routing signal
   - 用于拿 `publisher`、`landing_page_url`、`license`、`fulltext_links` 等信号。
   - 此时不会自动把最终结果的 `source` 变成 `crossref_meta`。
2. 作为 public source
   - 当调用方显式收敛到 Crossref-only 且没有进入 metadata fallback 时，底层文章来源可保持 `crossref_meta`。
   - 当 fulltext waterfall 失败并进入 metadata fallback 时，`FetchEnvelope.source` 会公开表现为 `metadata_only`；底层 `ArticleModel.source` 仍可能是 `crossref_meta`。

实现边界上，Crossref HTTP lookup 的底层 owner 是 `paper_fetch.metadata.crossref.CrossrefLookupClient`；`paper_fetch.providers.crossref.CrossrefClient` 只是 provider adapter，并继续保留 public import path。provider metadata 与 Crossref metadata 的 primary-secondary merge 规则由 `paper_fetch.metadata.types.PRIMARY_SECONDARY_METADATA_MERGE_RULE` / `merge_primary_secondary_metadata()` 统一承载。

### `preferred_providers` 的语义

- 它限制最终允许进入的 provider fulltext 主链候选。
- 它不阻止系统内部调用 `crossref` 做路由判断或 metadata-only fallback。
- 如果显式设为 `["crossref"]`，行为会收敛成 Crossref-only。
- 当前可显式指定的 provider 名包括：
  - `elsevier`
  - `springer`
  - `wiley`
  - `science`
  - `pnas`
  - `ams`
  - `acs`
  - `iop`
  - `aip`
  - `mdpi`
  - `ieee`
  - `arxiv`
  - `copernicus`
  - `plos`
  - `frontiers`
  - `annualreviews`
  - `royalsocietypublishing`
  - `oxfordacademic`
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
- `elsevier` 和 `arxiv` 会参加 provider metadata probe；`arxiv` 通过项目内部 Atom API client 调用官方 arXiv API，使用 60 秒专用超时并对 timeout / 5xx 做 2 次 transient retry，获取 title、authors、abstract、published、categories、arXiv DOI、abs URL 和 PDF URL。
- `springer`、`wiley`、`science`、`pnas`、`ieee`、`copernicus`、`ams`、`mdpi`、`royalsocietypublishing`、`annualreviews`、`plos`、`frontiers`、`oxfordacademic`、`acs`、`iop`、`aip` 在 `probe_official_provider()` 和 `has_fulltext()` 中都只依赖 Crossref / landing-page / DOI 信号，不调用 publisher metadata API。
- 最终会合并 primary / secondary metadata，统一生成正文抓取需要的元数据。

### 3. provider 全文主路径

- `elsevier`
  - 固定顺序是 `官方 DOI XML/API -> PII XML/API fallback -> 官方 API PDF fallback -> metadata-only`。
  - 直接输入 LinkingHub 或 ScienceDirect 的 `/pii/{PII}` URL 时，resolve 阶段会提取 PII 并跳过 publisher landing 抓取；metadata 阶段改用 Elsevier Abstract PII API 补 DOI，再进入官方全文主路径。
  - PII XML/API fallback 只在 DOI XML/API 出现 transient / rate-limit 类失败，且 merged metadata 中能从 LinkingHub 或 ScienceDirect URL 提取 PII 时启用；它仍使用 Elsevier 官方 Article API，不走通用 HTML 抓取。
  - XML/API 成功时公开 `source="elsevier_xml"`。
  - CALS 表格通过共享 XML/grid normalizer 解析 `colspec`、多层 `<thead>`、`colname`、`namest/nameend` 和 `morerows`；可展开跨度生成组合列名并记录布局降级，冲突/不规则网格保留为可读列表且不计语义丢失。
  - 官方 PDF fallback 成功时公开 `source="elsevier_pdf"`。
- `springer`
  - 固定顺序是 `direct HTML -> direct HTTP PDF -> abstract-only / metadata-only`。
  - 优先抓取 publisher landing HTML，不足正文时再走 direct HTTP PDF。
  - 优先使用 merged metadata 中的 `landing_page_url`，缺失时回退 DOI 解析。
  - 对外 provider/source 保持 `springer`、`springer_html`、`springer_pdf` 不变；内部先用 `springer_site_family_profile()` 将 route 分类为 `nature`、`springerlink` 或 `bmc`，并把 family 写入 diagnostics，避免三类站点逻辑继续以隐式条件混合。
  - HTML 成功时公开 `source="springer_html"`；PDF fallback 成功时公开 `source="springer_pdf"`。
  - Springer HTML cleanup / payload 由 `paper_fetch.providers._springer_html` compatibility facade 暴露；canonical owner 拆到 `_springer_dom`、`_springer_markdown`、`_springer_assets`、`_springer_authors` 和 `_springer_references`。
- `wiley`
  - 使用 provider 自管 HTML + 官方 API PDF + publisher PDF/ePDF waterfall。
  - 固定顺序是 `selected-browser HTML -> browser-seeded publisher PDF/ePDF -> Wiley TDM API PDF -> abstract-only / metadata-only`。
  - 不做额外 fast HTML preflight，避免低成功率路径增加固定开销。
  - selected-browser HTML 正文首轮使用快速路径并阻断 media 资源；challenge、访问拦截、摘要页或正文抽取不足时回退到保守等待参数。
  - Atypon/Wiley figure label 只从显式 label、figure DOM id、图片 URL basename 或 caption 起始 `Figure N` 推断；caption 正文里的 `Figure N` 交叉引用不能覆盖当前图号。
  - `WILEY_TDM_CLIENT_TOKEN` 是官方 TDM API PDF lane；缺失时仍可继续尝试 browser PDF/ePDF，配置后会在 browser PDF/ePDF fallback 失败或 browser runtime 不可用时继续尝试 TDM PDF。TDM URL template 声明在 `ProviderSpec.api_url_templates`，provider 只负责填充 DOI。
  - Atypon 默认 PDF/ePDF 路径模板只在 `provider_catalog.ATYPON_DEFAULT_PDF_PATH_TEMPLATES` 维护；Wiley 在此基础上追加 `pdfdirect` / `wol1` 专属模板。
  - 成功时公开 `source="wiley_browser"`。
- `science`
  - 固定顺序是 `selected-browser HTML -> browser-seeded publisher PDF/ePDF -> abstract-only / metadata-only`。
  - 与 `wiley` 的 HTML / browser PDF/ePDF 路径共享同一套浏览器工作流基座。
  - 不做额外 fast HTML preflight，避免低成功率路径增加固定开销。
  - selected-browser HTML 正文首轮使用同一快速路径，并在 challenge、访问拦截、摘要页或正文抽取不足时保守重试。
  - 如果落到 AAAS 的 `Check access` / paywall 页面，应优先解读为 `institution not entitled / no access`，而不是 generic HTML fallback 缺失。
  - Atypon boxed text（如 `Box 1`）在 HTML 归一化时作为普通正文块保留；figure label 只来自 caption / label 起始结构，不能从 boxed text 正文里的 `Fig. N` 交叉引用推断，避免错误注入重复 figure 图片。
  - Atypon 默认 PDF/ePDF 路径模板只在 `provider_catalog.ATYPON_DEFAULT_PDF_PATH_TEMPLATES` 维护；Science 仅追加自己的 download query 模板。
  - 成功时公开 `source="science"`。
- `pnas`
  - 固定顺序是 `selected-browser HTML -> browser-seeded publisher PDF/ePDF -> abstract-only / metadata-only`。
  - HTML route 统一走 browser workflow bootstrap 和 `fetch_html_with_browser()`；不再有独立 fast browser preflight。
  - 较老文献常见 HTML 只到摘要页，此时 provider 会继续尝试 publisher PDF/ePDF fallback。
  - Atypon 默认 PDF/ePDF 路径模板只在 `provider_catalog.ATYPON_DEFAULT_PDF_PATH_TEMPLATES` 维护；PNAS 仅追加自己的 download query 模板。
  - 成功时公开 `source="pnas"`。
- `ams`
  - 固定顺序是 `Crossref/DOI landing -> selected-browser HTML -> browser-seeded AMS PDF fallback -> abstract-only / metadata-only`。
  - HTML 主路径直接启动 Camoufox 请求 Crossref / DOI landing 的 `journals.ametsoc.org/view/journals/.../*.xml` 页面，让站点正常执行 JavaScript 并静默完成 AWS WAF 验证；不再先发 direct HTTP article 请求。
  - 无保存状态时仍会启动 provider-scoped 浏览器 profile；存在默认 profile storage-state 或显式 `PAPER_FETCH_AMS_STORAGE_STATE_JSON` 时自动复用。静默验证失败时可运行 `paper-fetch auth ams [--url ...]`，`paper-fetch browser-preflight --provider ams` 也会检查并保存相同 provider 状态。
  - Browser HTML 失败、challenge、非 HTML 或正文不足时，provider 从 Crossref `citation_pdf_url`、landing/source URL 和已加载 HTML metadata 中收集 `downloadpdf` PDF candidate，再以同一 runtime/storage-state 和 browser context seed 获取真实 PDF。
  - 页面声明的 `citation_xml_url` 被显式忽略：不解析、不请求 `/doc/journals/.../*.xml`，也不注册 XML 诊断或 `ams_xml` source。
  - HTML 正文通过 AMS HTML extractor 与质量门槛；正文不足时先尝试 browser-seeded PDF fallback，PDF 仍不可用时返回 provider failure 并交给上层 abstract-only / metadata fallback。
  - HTML extractor 优先保留 `#articleBody` / `.container-fulltext-display` 下完整正文，并清理下载按钮、citation、gallery 控件等页面 chrome。
  - AMS figure / image-only table 会回填到正文原始位置；无 HTML `<table>` 的 `.tableWrap` 降级为 `kind="table"` 图片资产，保留 caption 和 full-size 图片链接。
  - AMS figure 会优先读取原始页面的 `Download Figure` 菜单；EPS/TIFF 源文件作为 `download_url` 放在网页 full-size JPG/PNG 前面，PowerPoint 下载项不作为图片资产。源图下载成功后用 Ghostscript/libvips 转成 PNG 保存，原始 EPS/TIFF 同时保留用于溯源；转换失败时继续尝试 full-size JPG/PNG。
  - AMS 虽然是 Atypon-hosted provider，但不使用 `ATYPON_DEFAULT_PDF_PATH_TEMPLATES` 的 `/doi/pdf` 路径；browser-seeded PDF fallback 只接受 AMS `downloadpdf` 或明确 PDF metadata URL，成功时发布 `ams_pdf`。
  - Atypon 共享 asset extractor 负责图、公式和补充材料；AMS 只在专用 `tableWrap` 补充步骤发出 image-only table，并按 URL 去掉 generic figure 重复项。
  - 已回填正文的 AMS figure / table 下载后会改写为本地图片链接，并从尾部 `Figures` / `Tables` 附录去重；共享 figure 链接注入不会把 `Table` / `Extended Data Table` / `Supplementary Table` 图片块按 figure 顺序 fallback 改写。
  - AMS MathJax/MathML 归一化优先保留结构化公式，`inline-formula` / `script[type="math/mml"]` 中的行内 MathML 会先暴露给 AMS 专用 inline renderer 和共享公式转换器，再移除旁边的 MathJax 渲染 chrome；无 MathML 的 AMS lazy formula image 会读取 `data-image-src` 中的真实 GIF，不把 `Blank.svg` 占位图写入正文或公式资产；MathML script type 判定只在 `extraction/html/formula_rules.py` 维护并由 availability 诊断复用；display equation 编号只取源站明确 label 或 AMS `E...` 公式 id，`UE...` 无编号公式不合成 `Equation n.`，子公式编号按源站 `7a` / `9b` 等原样保留。
  - AMS figure / table caption 和正文短 inline markup 使用 AMS 专用 inline renderer 生成文本，caption 里的 `<sub>` / `<sup>`、斜体变量、行内 MathML、连续下标和上下标后的 prose 空格会尽量保留；`</sub>(i.e.`、`</sub>(Fig.` 这类 prose 括注会补空格，但 `*K*<sub>DP</sub>`、`10<sup>−5</sup>`、`H<sub>2</sub>O` 等数学/化学紧贴写法不改；image-only table 以图片表格降级并保留 caption 语义。
  - AMS Markdown 后处理会把误落在 appendix 后的 `Data availability statement` 移到 Acknowledgments 之后、首个 Appendix 之前，不移动 References、Footnotes 或 appendix 内图表。
  - BAMS/AMS `.footnoteGroup` 会集中渲染为 `## Footnotes`，正文保留 `<sup>n</sup>` 标记，脚注条目输出为 `<sup>n</sup> text`，避免 URL 或脚注段落散落在正文末尾。
  - HTML 成功时公开 `source="ams_html"`；PDF fallback 成功时公开 `source="ams_pdf"`。
- `acs`
  - 固定顺序是 `selected-browser HTML -> browser-seeded publisher PDF/ePDF -> abstract-only / metadata-only`。
  - 通过 `10.1021/` DOI、`www.acs.org` / `pubs.acs.org` 域名和 American Chemical Society publisher alias 路由；`/doi/full/{doi}` / `/doi/{doi}` 候选会跟随站点重定向到当前 `/acsodf/article/...` Silverchair 页面。
  - HTML 抽取以当前 `.article-body` 为完整根，并等待 `.article-body` / `.widget-ArticleFulltext` 稳定；嵌入 Supporting Information 的 Figshare `<article>` 不能覆盖正文根。清洗移除 metadata panel、graphical abstract 占位、figure modal/viewer、references 原始 DOM 和 supplementary widget，再单独渲染结构化 references 和 scoped assets。
  - 正文保留 section、Markdown table、MathML/LaTeX formula 与 `.fig.fig-section` 图文；`.ref-list .ref` 提取可见 citation、label、year 和 DOI。`asset_profile=body` 下载正文 figure，并通过 `/view-large/figure/` 页面解析首选大图候选后改写正文链接；图页抓取显式跳过 article-body readiness，最多等待 5 秒直至 `img.content-image` 出现并在就绪后立即返回。
  - `asset_profile=all` 只从原始 `.widget-ArticleDataSupplements` 接受稳定的 `/article-supplement/` 附件；嵌入的 Figshare viewer/downloader 不作为 canonical supplementary URL。
  - PDF fallback 优先用 article seed URL 发起带浏览器导航头的公共 `/doi/pdf/{doi}` 直链请求，只接受真实 PDF magic bytes；失败后继续原 seeded-browser PDF/ePDF 路径。
  - 成功时公开 `source="acs"`。
- `iop`
  - 固定顺序是 `selected-browser article HTML -> browser-seeded IOP PDF -> abstract-only / metadata-only`。
  - 通过 `10.1088/` DOI、`iopscience.iop.org` 域名和 IOP Publishing publisher alias 路由；HTML 候选使用 `https://iopscience.iop.org/article/{doi}`，PDF 候选使用同 article URL 的 `/pdf` 变体和页面 `citation_pdf_url`。
  - HTML cleanup 复用 browser workflow，并注册 IOPScience article chrome 清理、author metadata、figure caption cleanup、citation_reference references fallback 和 PDF 候选回填。
  - 已提交 replay 覆盖 HTML body table、formula image、figure caption、references、supplementary media link，以及 seeded-browser `iop_pdf` fallback。
  - selected-browser HTML fetch 会等待 IOP `articleBody` / `.article-content` 正文 DOM；正文已稳定时，页面外层残留的 Radware/PerfDrive shell 信号不会覆盖正文判定。
  - Radware Bot Manager、PerfDrive 与 hCaptcha 独立挑战页会作为 access/challenge signal fail closed，不会保存为正文或图片资产。经 access review，没有确认可用于此单篇抓取产品面的稳定公共 TDM XML/API endpoint；catalog 因而把该 route 明确登记为 `unsupported`，不会用猜测 URL 替代。后续接入必须先完成授权、quota/429 和 schema drift 验证。参考 IOP 的 [data availability policy](https://publishingsupport.iopscience.iop.org/iop-publishing-data-availability-policy/) 与 [supplementary material guidance](https://publishingsupport.iopscience.iop.org/questions/supplementary-material-and-data-in-journal-articles/)。
  - `asset_profile=body` / `all` 会使用 provider-neutral scoped asset discovery 发现正文资源；PDF fallback 在 `body/all` 且允许 artifact 落盘时会保存 PDF 导出的正文图片，committed replay 里资源合约按 best-effort 记录。
  - 成功时公开 `source="iop_html"` 或 `source="iop_pdf"`。
- `aip`
  - 固定顺序是 `selected-browser AIP article HTML -> browser-seeded AIP PDF -> abstract-only / metadata-only`。
  - 通过 `10.1063/` DOI、`pubs.aip.org` 域名和 AIP Publishing publisher alias 路由；HTML 候选使用 `/doi/full/{doi}` / `/doi/{doi}`，PDF 候选使用 Atypon `/doi/epdf/{doi}` / `/doi/pdf/{doi}`。
  - HTML cleanup 复用 browser workflow，并注册 AIP article/citation/download/metrics chrome 清理、author metadata、retained back matter、figure modal duplicate cleanup、citation_reference references fallback 和 PDF 候选回填。
  - 已提交 replay 覆盖 HTML body sections、body figure assets、Markdown table、MathML/LaTeX formula、supplementary material、references，以及 seeded-browser `aip_pdf` fallback route tests。
  - `asset_profile=body` / `all` 会使用 provider-neutral scoped asset discovery 发现正文资源；PDF fallback 在 `body/all` 且允许 artifact 落盘时会保存 PDF 导出的正文图片。
  - 成功时公开 `source="aip_html"` 或 `source="aip_pdf"`。
- `mdpi`
  - 固定顺序是 `selected-browser HTML -> browser-seeded article PDF fallback -> metadata-only`。
  - HTML 候选优先使用 Crossref/metadata 中的 MDPI landing page；如果 metadata 只有 MDPI DOI 或 `doi.org` URL，会按已知 journal code 反推 MDPI 数字段 article URL，再回退 DOI resolver；MDPI 数字段 article URL 对已知 ISSN 会先推导 DOI，避免普通 HTTP landing probe 遇到 CDN 403；MDPI 页面里的 XML 链接不作为 provider success route。
  - HTML extractor 从 MDPI article container 中重建正文，清理 article menu、分享/引用/metrics、SciProfiles、Google Scholar / CrossRef / PubMed / Green Version reference linkout UI，保留摘要、正文 section、references、figures、tables、formula 和 supplementary section；reference `li data-content` 编号必须保留，metadata / Crossref fallback 不人工补号；`#html-keywords` 只进入 metadata keywords，不进入 Abstract 或 Markdown 正文。
  - MDPI 正文 figure / table display object 按首次正文引用锚定，未引用对象保留源顺序并插到 References 前；popup display 副本、重复 label 和重复 caption 必须在 DOM 阶段去重。
  - MDPI 正文 figure / table / formula 图片会在正文附近内联成短 alt Markdown 图片行；caption 不进入 alt，下载后本地化到 `body_assets/...` 并通过 `render_state="inline"` 避免尾部重复资产块。HTML `<table>` 走共享表格 renderer；HTML-only 公式保留 `<sub>` / `<sup>` 语义并作为单块输出。
  - PDF fallback 的正文 Markdown 仍来自共享 PDF 转换；`body/all` 且允许 artifact 落盘时会保存 PDF 导出的正文图片。Supplementary 下载仅在 HTML 路径启用。
  - `asset_profile=body` 只发现正文 figure / table / formula 资产；`asset_profile=all` 额外从明确 supplementary/app section 中发现 `/s1` 等 MDPI 附件链接；下载阶段复用 browser workflow 的 browser-backed image/file fetcher 和 seed refresh retry，失败诊断保留在 `quality.asset_failures`，partial-download warning 由 artifact 层统一生成。
  - 成功时公开 `source="mdpi_html"` 或 `source="mdpi_pdf"`。
- `royalsocietypublishing`
  - 固定顺序是 `selected-browser DOI HTML -> browser-seeded PDF fallback -> metadata-only`。
  - HTML 成功公开 `source="royalsocietypublishing_html"`；PDF fallback 成功公开 `source="royalsocietypublishing_pdf"`。
  - 需要 `ProviderSpec.requires_browser_runtime=True` 的本地 browser runtime；`citation_xml_url` 不作为 XML/JATS 路线；PDF fallback 在 `body/all` 且允许 artifact 落盘时会保存 PDF 导出的正文图片。
  - Silverchair `DownloadImage.aspx` 的嵌套签名 CDN 图片作为 `full_size_url`，`/view-large/figure/...` 只作为 `figure_page_url`，`m_*` 图片作为 `preview_url`；三者按 DOM id 和规范化 figure basename 合并。嵌套原图必须来自 Silverchair CDN 且 basename 与当前 figure 一致，避免分组 slide 串图；无直接原图时，查看页最多等待 5 秒直至 `img.content-image` 就绪，再降级 preview。
- `annualreviews`
  - 固定顺序是 `selected-browser landing/full-text HTML -> browser-seeded PDF -> provider-managed abstract_only -> metadata-only`。
  - 需要 `ProviderSpec.requires_browser_runtime=True` 的本地 browser runtime；HTML 成功公开 `source="annualreviews_html"`，PDF fallback 成功公开 `source="annualreviews_pdf"`。
  - HTML 正文表格复用共享 table renderer，支持多层表头、rowspan/colspan 展开、统一 pipe escaping 和不规则网格列表降级；provider 只保留 table container 与 footnote 适配。
- `oxfordacademic`
  - 固定顺序是 `direct HTTP article HTML -> direct HTTP PDF fallback -> metadata-only`。
  - HTML 成功公开 `source="oxfordacademic_html"`；PDF fallback 成功公开 `source="oxfordacademic_pdf"`。
  - HTML 资产下载已复用共享 Silverchair 语义：`none` 不下载，`body` 下载正文 figure/formula，`all` 再包含明确 supplementary；两类资产均 direct-first、校验响应并把成功链接改写到本地路径。PDF fallback 在 `body/all` 且允许 artifact 落盘时会保存 PDF 导出的正文图片。
- `ieee`
  - 固定顺序是 `direct landing -> selected-browser landing recovery -> direct REST HTML -> selected-browser HTML -> direct HTTP PDF -> selected-browser PDF -> abstract-only / metadata-only`。
  - dynamic HTML 请求使用 document `Referer`、浏览器 UA、`x-security-request: required` 和兼容 `Accept`。
  - selected-browser HTML 保留 REST response listener，优先捕获同一个 full-text 响应，未捕获时回退 `#article` DOM；失败后继续 PDF fallback。
  - 正文 figure/table/formula、multimedia discovery 和 supplementary file 都 direct-first；只有 `401/403`、HTML challenge 或网络失败使用浏览器，`404/410/429` 不使用。
  - HTML 成功必须包含 `#article`、章节/段落结构，并通过正文充分性诊断；登录页、418/unable page、access gate、验证码、摘要页和空壳 HTML 都会被拒绝。
  - PDF fallback 的正文 Markdown 来自共享 PDF 转换；`body/all` 且允许 artifact 落盘时会保存 PDF 导出的正文图片。
  - 成功时公开 `source="ieee_html"` 或 `source="ieee_pdf"`。
- `arxiv`
  - 固定顺序是 `arXiv ID 解析 -> arXiv official HTML -> direct HTTP PDF fallback -> metadata-only`。
  - resolve 支持 `https://arxiv.org/abs/{id}`、`/html/{id}`、`/pdf/{id}`、`arXiv:{id}`、裸 `{id}` / `{id}vN`，以及 `10.48550/arXiv.{id}`。
  - DOI、URL、裸 ID 或已有 metadata 中能可靠推导 arXiv ID 时，会先构造最小 metadata：`doi`、`arxiv_id`、`landing_page_url`、`html_url`、`pdf_url`、`provider=arxiv`，并立即执行 HTML -> PDF waterfall；主链结束后默认通过内部 Atom API client 执行 arXiv API metadata enrichment，Atom API 使用 60 秒专用超时并对 timeout / 5xx 做 2 次 transient retry，最终失败或 429 只记录 warning/diagnostic，不会阻塞全文获取。
  - official HTML front matter 会补齐 `title`、`authors`、`abstract`、`published`、`primary_category`、canonical DOI、HTML/PDF URL；合并优先级是 arXiv API metadata > HTML front matter > derived arXiv URLs，因此 API 不可用时也不应出现 `Untitled Article` 或 authorless arXiv fulltext。
  - official HTML 是主路径，直接请求 `https://arxiv.org/html/{id}`，抽取 Markdown、官方 bibliography references 和正文 figure 资产候选；可匹配到下载 URL 的正文 figure 会在原 caption 附近先以内联图片 Markdown 表达，下载后改写为 `body_assets/...` 本地链接；如果 official HTML 只有 `ltx_missing_image` 这类缺失图片占位符，会读取 `https://arxiv.org/e-print/{id}` source 包，按 LaTeX figure 顺序 / caption 匹配恢复图片或将 source PDF 图渲染为 PNG，再插回对应 figure caption 前；HTML 正文不足、非 HTML、不可访问或质量门控失败时直接继续 PDF fallback。
  - official HTML 渲染前会做 arXiv/LaTeXML 专用语义块预处理：`figure.ltx_table` 和裸 `table.ltx_tabular` 复用共享 HTML table renderer 输出 Markdown 表格或 key-value 行，单个全宽 `colspan` 标题行会提升为表格前普通文本，`ltx_listing` / algorithm block 输出标题和 fenced pseudo-code，并用 placeholder 保持原文位置；无法插回的位置会追加到文末并记录 warning。
  - official HTML 的 section kind 由清洗后的 `article.ltx_document` DOM 结构 hint 驱动：`References` / `Bibliography` 与 Data / Code Availability 继续按共享语义分类，其它由正文渲染链路输出的 article 标题默认作为正文；页面外部 metrics / citation chrome 不进入 arXiv HTML 解析范围。
  - official HTML 会清理仅表示未定义宏的 `.ltx_ERROR.undefined` 节点（例如 `\addsec`）、图片 `alt="Refer to caption"` 占位噪声和 TeX annotation 内部嵌套 `$...$` 定界符；普通段落、list item 和 caption 的源 HTML 硬换行会折叠为空格，但 display math、Markdown 表格、列表边界、代码块和独立图片块仍保留必要换行。正常 caption、图片 URL 和正文 figure 下载链路不受影响。语义块渲染失败会写入 `semantic_losses.table_semantic_loss_count` / `table_fallback_count`，便于质量诊断。
  - PDF fallback 的正文 Markdown 来自共享 PDF 转换；`body/all` 且允许 artifact 落盘时会保存 PDF 导出的正文图片。
  - 成功时公开 `source="arxiv_html"` 或 `source="arxiv_pdf"`；HTML route 使用项目自研 HTML Markdown 渲染链路和全文质量检测，不依赖本机转换器。
- `copernicus`
  - 固定顺序是 `landing HTML -> citation_xml_url / XML link -> NLM/JATS XML -> direct HTTP PDF fallback -> metadata-only`。
  - landing HTML 和 XML/PDF 下载都走 direct HTTP，不需要本地浏览器运行时或登录态。
  - XML 成功必须通过 JATS 结构、摘要和正文充分性校验；失败后才进入 PDF fallback。早期 abstract-only XML 不会被标记成成功全文，会继续尝试 PDF。
  - PDF 候选优先来自 landing meta/link，最后使用 DOI 形态推导的 `.pdf` URL；如果 PDF payload 不是可抽取文本的真实全文，继续降级 metadata-only。
  - PDF fallback 的正文 Markdown 来自共享 PDF 转换；`body/all` 且允许 artifact 落盘时会保存 PDF 导出的正文图片。
  - 成功时公开 `source="copernicus_xml"` 或 `source="copernicus_pdf"`。
- `plos`
  - 固定顺序是 `public JATS XML -> direct HTTP PDF fallback -> metadata-only`。
  - XML/PDF URL 由 DOI journal code 推导 PLOS journal path，下载都走 direct HTTP，不需要本地浏览器运行时或登录态。
  - XML 成功必须解析为 JATS `article`，HTML wrapper、challenge、空 payload 或没有正文/摘要/参考文献的 XML 都会失败并继续 PDF fallback。
  - PDF fallback 的正文 Markdown 来自共享 PDF 转换；`body/all` 且允许 artifact 落盘时会保存 PDF 导出的正文图片。
  - 成功时公开 `source="plos_xml"` 或 `source="plos_pdf"`。
- `frontiers`
  - 固定顺序是 `landing HTML -> public JATS XML -> direct HTTP PDF fallback -> metadata-only`。
  - canonical XML/PDF URL 由 Frontiers landing redirect 或 landing metadata 发现，下载都走 direct HTTP，不需要本地浏览器运行时或登录态。
  - XML 成功必须解析为 JATS `article`，HTML wrapper、challenge、空 payload 或没有正文/摘要/参考文献的 XML 都会失败并继续 PDF fallback。
  - XML figure 文件名会重写为 `/files/Articles/{article_id}/xml-images/*.webp` 下载 URL；supplementary 只保留 canonical full page anchor，不强拼附件直链。
  - PDF fallback 的正文 Markdown 来自共享 PDF 转换；`body/all` 且允许 artifact 落盘时会保存 PDF 导出的正文图片。
  - 成功时公开 `source="frontiers_xml"` 或 `source="frontiers_pdf"`。

URL query 解析 DOI 时会优先使用 URL 专用抽取：先读取 query parameter 中的 DOI 值，再从 path 抽取 DOI，并根据 provider catalog 的 `{doi}` / `{doi_quoted}` path templates 剥离 DOI 后面的固定 route token 或扩展名，例如 Frontiers `/full` / `/pdf` / `/xml`、IOP `/pdf`、Wiley `/fullpdf`、Springer `.pdf`。无法从 provider catalog 或显式 override 识别的后缀会保留，避免把未知 DOI suffix 当成 URL route 误删。

### 4. abstract-only / metadata-only fallback

如果命中了 `elsevier`、`springer`、`wiley`、`science`、`pnas`、`ieee`、`arxiv`、`copernicus`、`ams`、`mdpi`、`royalsocietypublishing`、`annualreviews`、`plos`、`frontiers`、`oxfordacademic`、`acs`、`iop`、`aip` 之一：

- 系统只会走该 provider 自己管理的 fulltext waterfall
- provider 主链不可用或返回 `None` 后直接进入 metadata-only fallback
- `springer` / `wiley` / `science` / `pnas` / `ams` / `annualreviews` / `acs` / `iop` / `aip` / `ieee` 如果只能确认摘要级内容，会返回 provider 自己的 `abstract_only` 结果，而不是再绕去通用 HTML；`mdpi`、`royalsocietypublishing`、`oxfordacademic`、`arxiv`、`copernicus`、`plos`、`frontiers` 与 `elsevier` 保持一致，HTML/XML/PDF 都不可用时进入通用 metadata-only fallback

如果没有命中这些 official provider：

- 系统仍会继续做 DOI / Crossref metadata 解析
- 跳过通用 HTML 正文提取
- `strategy.allow_metadata_only_fallback=true` 时返回 metadata + abstract
- 否则直接抛错

如果 provider 主链已经拿到 fulltext HTML：

- provider fetch result 组装层会在构造 `ArticleModel` 前自动触发 HTML -> Markdown
- `springer`、`wiley`、`science`、`pnas`、`ams`、`mdpi`、`royalsocietypublishing`、`annualreviews`、`oxfordacademic`、`acs`、`iop`、`aip`、`ieee`、`arxiv` 会优先复用各自 provider 专用的 HTML 解析器；`copernicus`、`plos` 和 `frontiers` 只在 XML 主路径使用专用 XML 解析器
- 通用 HTML 转换只作为“已确认 fulltext HTML 但 provider 没有提供 Markdown”的兜底，不会变成任意 URL 的全文 fallback

如果 provider PDF fallback 已经下载到真实 PDF，但 PDF Markdown 转换失败或结果为空：

- 保留 provider PDF 结果和本地 PDF artifact，不再替换为 Crossref/general `metadata_only` source
- `has_fulltext=false`，warnings 会说明 PDF 已下载但 Markdown extraction 不可用
- 非 PDF payload、HTML challenge、登录页或错误页仍按 PDF fallback 失败处理

如果没有可返回的 provider `abstract_only` 结果，而 `strategy.allow_metadata_only_fallback=true`：

- 返回 metadata + abstract
- `has_fulltext=false`
- `warnings` 中显式说明已降级
- `source_trail` 中会带 `fallback:metadata_only`
- public `source` 通常会表现为 `metadata_only`；如果元数据里有摘要，模型质量层的 `content_kind` 可能归类为 `abstract_only`

如果关闭这个开关，正文不可得会直接抛错。

## Elsevier / Springer / Wiley / Science / PNAS / IEEE / arXiv / Copernicus / AMS / MDPI / Royal Society Publishing / Annual Reviews / PLOS / Oxford Academic / ACS / IOP / AIP 的特殊语义

这些 provider 的共同点是：

- metadata 先尽量来自 Crossref；`elsevier` 可能用 publisher metadata probe 作为 primary 覆盖 / 补充，`arxiv` 先用 ID 构造可抓取 HTML 的最小 metadata，HTML 成功后再按 arXiv API metadata > HTML front matter > derived URLs 合并
- fulltext 主路径由 provider 自己控制
- 主链不可用时不走通用 HTML；不可用 / `None` 结果进入 metadata-only fallback，provider-managed `abstract_only` 结果可直接返回
- XML / HTML / PDF / TDM / browser PDF fallback 的顺序由内部 `paper_fetch.providers._waterfall` runner 编排；各 provider step 仍保留自己的 payload 结构、warning 文案和 `fulltext:*` source trail marker
- `ProviderClient.fetch_result` 负责通用 raw payload、本地副本标记、资产下载、warning/trace 和 artifact 组装；workflow 内部调用时必须传入 `artifact_store=` 与 `context=`，Browser workflow 与 Springer 只通过 hook 处理 abstract-only 后 PDF recovery 或 provider-managed abstract-only 返回

但它们的 fulltext 形态不同：

- `elsevier`
  - provider 自管 `官方 DOI XML/API -> PII XML/API fallback -> 官方 API PDF fallback`
  - 直接输入 ScienceDirect / LinkingHub PII URL 时不抓 publisher landing HTML，避免被站点级 403/challenge 卡住；PII 先走官方 Abstract API 转 DOI，再按 DOI XML/API 主链处理
  - XML article document builder 通过 provider dispatch table 进入 Elsevier renderer；未知 provider 不会落入半成品分支
  - XML attachment MIME 优先使用 publisher 响应/节点声明；缺失时用 Python `mimetypes.guess_type` 按文件扩展推断
  - XML/PDF 官方 representation 的 `404/406/415` 统一经 `providers.base.map_request_failure` 映射为 `no_result`
  - DOI XML/API 的 transient / rate-limit 类失败会优先尝试从 public landing URL 提取 PII，并请求 `content/article/pii/{pii}`；PII XML 成功时会带 `fulltext:elsevier_xml_pii_ok`
  - 进入 PDF lane 时会组合 `fulltext:elsevier_xml_fail`、`fulltext:elsevier_pdf_api_ok`、`fulltext:elsevier_pdf_fallback_ok`
  - PDF lane 失败时会带 `fulltext:elsevier_pdf_api_fail`
- `springer`
  - provider 自管 `direct HTML -> direct HTTP PDF`
  - Springer/Nature chrome 清理以结构信号为主：AI alt disclaimer 只按 `ai-alt-disclaimer` ID/ARIA 关系删除，license 段落以 `creativecommons.org/licenses/*` 链接为主、短文本阈值为辅助
  - Nature heading cosmetic normalization 注册在 provider rule profile；例如 `Online Methods` 规范为 `Methods`
  - `Extended Data Table` 页缺少 HTML `<table>` 时，只从表格页正文/表格容器和可信表格 meta 图片提取图片 fallback；header、logo、nav、footer、advert 等站点资源不会生成 `kind="table"` 资产
  - 成功轨迹是 `fulltext:springer_html_*`，PDF fallback 成功时会带 `fulltext:springer_pdf_fallback_ok`
- `wiley`
  - provider 自管 selected-browser HTML + Wiley TDM API PDF + browser-seeded publisher PDF/ePDF waterfall
  - 成功轨迹是 `fulltext:wiley_html_*` / `fulltext:wiley_pdf_api_ok` / `fulltext:wiley_pdf_browser_ok` / `fulltext:wiley_pdf_fallback_ok`
  - 失败时若 API lane 未产出 PDF，会保留 `fulltext:wiley_pdf_api_fail`；若 browser PDF/ePDF lane 已实际尝试但失败，会再带 `fulltext:wiley_pdf_browser_fail`
- `science`
  - provider 自管 `selected-browser HTML + browser-seeded publisher PDF/ePDF`
  - `fulltext:science_html_fail` / `fulltext:science_pdf_fallback_ok` 只描述 provider 主链的阶段切换；如果页面本身就是 access gate，更准确的业务解释应是 `institution not entitled / no access`
  - 继续保持现有 `science` 风格的公开来源与轨迹命名
- `pnas`
  - provider 自管 `selected-browser HTML + browser-seeded publisher PDF/ePDF`
  - 较老文献可能先表现为 `fulltext:pnas_html_fail`，再进入 `fulltext:pnas_pdf_fallback_ok`
  - 继续保持现有 `pnas` 风格的公开来源与轨迹命名
- `ams`
  - provider 自管 `Crossref/DOI landing -> direct HTTP HTML -> direct HTTP PDF fallback`
  - `citation_xml_url` 不是 AMS 正文路径：不请求 `/doc/...xml`，不走 JATS renderer，不产生 `ams_xml` source 或 XML warning
  - 正文 figure 资产优先使用页面 `Download Figure` 暴露的 EPS/TIFF 源图；下载请求继承浏览器 UA 和正文 Referer，转换成功后 Markdown 使用 PNG，本地资产保留原始源文件和转换元数据，转换不可用或失败时再用网页 JPG/PNG 候选
  - HTML 成功轨迹是 `fulltext:ams_html_ok`
  - PDF fallback 成功轨迹是 `fulltext:ams_pdf_fallback_ok`
  - 公开 source 为 `ams_html` / `ams_pdf`
- `acs`
  - provider 自管 `selected-browser HTML -> browser-seeded publisher PDF/ePDF -> abstract/metadata fallback`
  - HTML 成功轨迹是 `fulltext:acs_html_ok`，PDF fallback 成功轨迹是 `fulltext:acs_pdf_fallback_ok`
  - HTML 和 PDF/ePDF fallback 都公开为 `acs`
- `iop`
  - provider 自管 `selected-browser article HTML -> browser-seeded IOP PDF -> abstract/metadata fallback`
  - HTML 成功轨迹是 `fulltext:iop_html_ok`，PDF fallback 成功轨迹是 `fulltext:iop_pdf_fallback_ok`
  - HTML 公开为 `iop_html`，PDF fallback 公开为 `iop_pdf`；正文 DOM 未加载的 Radware/hCaptcha challenge 页面必须 fail closed
- `aip`
  - provider 自管 `selected-browser AIP article HTML -> browser-seeded AIP PDF -> abstract/metadata fallback`
  - HTML 成功轨迹是 `fulltext:aip_html_ok`，PDF fallback 成功轨迹是 `fulltext:aip_pdf_fallback_ok`
  - HTML 公开为 `aip_html`，PDF fallback 公开为 `aip_pdf`
- `mdpi`
  - provider 自管 `selected-browser HTML -> browser-seeded article PDF -> metadata fallback`
  - HTML 成功轨迹是 `fulltext:mdpi_html_ok`，PDF fallback 成功轨迹是 `fulltext:mdpi_pdf_fallback_ok`
  - HTML 公开为 `mdpi_html`，PDF fallback 公开为 `mdpi_pdf`
- `ieee`
  - provider 自管 `direct landing -> selected-browser landing -> direct REST HTML -> selected-browser HTML -> direct PDF -> selected-browser PDF -> abstract/metadata fallback`
  - article number URL parser 只承诺 IEEE Xplore `/document/{article_number}/` landing URL；REST、stamp 和 query-string 形态由 metadata 或 route builder 处理
  - 支持图标过滤优先使用 DOM/资产结构、尺寸和 alt/title 语义，`/assets/img/icon.support.gif` 路径只作为兜底信号
  - 裸 `SECTION I` / `Section 1.` 等 Xplore marker 变体会在 leaf/kicker 节点中清除，不作为正文标题输出
  - 现代文章成功轨迹是 `fulltext:ieee_html_ok`
  - direct landing/REST 被可恢复失败拒绝时，所选后端打开 Xplore document 页并保留 REST response listener；浏览器 seed 继续供 PDF 和资产使用，不自动登录、处理验证码或绕过权限
  - 老文献、无动态 HTML 或 selected-browser HTML 仍不可用时，可能先表现为 `fulltext:ieee_html_fail` / `fulltext:ieee_browser_html_fail`，再进入 `fulltext:ieee_pdf_fallback_ok`
  - PDF fallback 公开为 `ieee_pdf`，HTML 公开为 `ieee_html`
- `arxiv`
  - provider 自管 `arXiv ID 解析 -> arXiv official HTML -> direct HTTP PDF fallback -> metadata fallback`
  - optional arXiv API / HTML metadata merge 只做 enrichment，详见 [arXiv](#arxiv)
  - HTML 成功轨迹是 `fulltext:arxiv_html_ok`
  - HTML 不可用、非 HTML、正文不足或质量门控失败时先保留 `fulltext:arxiv_html_fail`，再尝试 `fulltext:arxiv_pdf_fallback_ok`
  - PDF fallback 公开为 `arxiv_pdf`，HTML 公开为 `arxiv_html`
- `copernicus`
  - provider 自管 `landing HTML -> NLM/JATS XML -> direct HTTP PDF -> metadata fallback`
  - XML 成功轨迹是 `fulltext:copernicus_xml_ok`
  - XML 不可用时先保留 `fulltext:copernicus_xml_fail`，再尝试 `fulltext:copernicus_pdf_fallback_ok`
  - PDF fallback 公开为 `copernicus_pdf`，XML 主路径公开为 `copernicus_xml`
- `royalsocietypublishing`
  - provider 自管 `selected-browser DOI HTML -> browser-seeded PDF -> metadata fallback`
  - HTML 成功轨迹是 `fulltext:royalsocietypublishing_html_ok`，PDF fallback 成功轨迹是 `fulltext:royalsocietypublishing_pdf_fallback_ok`
  - HTML 公开为 `royalsocietypublishing_html`，PDF fallback 公开为 `royalsocietypublishing_pdf`
- `annualreviews`
  - provider 自管 `selected-browser landing/full-text HTML -> browser-seeded PDF -> abstract/metadata fallback`
  - HTML 成功轨迹是 `fulltext:annualreviews_html_ok`，PDF fallback 成功轨迹是 `fulltext:annualreviews_pdf_fallback_ok`
  - HTML 公开为 `annualreviews_html`，PDF fallback 公开为 `annualreviews_pdf`
- `plos`
  - provider 自管 `public JATS XML -> direct HTTP PDF -> metadata fallback`
  - XML 成功轨迹是 `fulltext:plos_xml_ok`
  - XML 不可用时先保留 `fulltext:plos_xml_fail`，再尝试 `fulltext:plos_pdf_fallback_ok`
  - PDF fallback 公开为 `plos_pdf`，XML 主路径公开为 `plos_xml`
- `frontiers`
  - provider 自管 `landing HTML -> public JATS XML -> direct HTTP PDF -> metadata fallback`
  - XML 成功轨迹是 `fulltext:frontiers_xml_ok`
  - XML 不可用时先保留 `fulltext:frontiers_xml_fail`，再尝试 `fulltext:frontiers_pdf_fallback_ok`
  - PDF fallback 公开为 `frontiers_pdf`，XML 主路径公开为 `frontiers_xml`
- `oxfordacademic`
  - provider 自管 `direct HTTP article HTML -> direct HTTP PDF -> metadata fallback`
  - HTML 成功轨迹是 `fulltext:oxfordacademic_html_ok`，PDF fallback 成功轨迹是 `fulltext:oxfordacademic_pdf_fallback_ok`
  - HTML 公开为 `oxfordacademic_html`，PDF fallback 公开为 `oxfordacademic_pdf`

因此：

- 没有 public HTML fallback 开关
- provider-owned waterfall 默认会在主路径出现 `NO_RESULT`、`NO_ACCESS`、`RATE_LIMITED` 或 `ERROR` 时继续尝试后续 PDF/abstract fallback；最终失败会保留前序 route 的 warning、`source_trail` 和 retry-after，便于 host 判断限流或访问失败。
- 对 `elsevier` 来说，系统始终按内部 `官方 DOI XML/API -> PII XML/API fallback -> 官方 API PDF fallback` waterfall 执行
- 对 `springer` 来说，系统始终按内部 `direct HTML -> direct HTTP PDF` waterfall 执行
- 对 `wiley` / `science` / `pnas` / `ams` / `annualreviews` / `royalsocietypublishing` / `acs` / `iop` / `aip` / `mdpi` 来说，系统始终按上文声明的 provider-owned browser workflow 执行。
- 对 `pnas` 来说，系统始终按内部 `selected-browser HTML -> browser-seeded publisher PDF/ePDF fallback -> provider abstract-only/metadata fallback` waterfall 执行；不再有 fast browser preflight 特例。
- 对 `ams` 来说，系统始终按内部 `Crossref/DOI landing -> selected-browser HTML -> browser-seeded AMS PDF fallback -> provider failure -> metadata fallback` waterfall 执行，且不会走 `citation_xml_url` / `/doc/...xml`。
- 对 `ieee` 来说，系统始终按内部 direct-first landing/REST HTML/PDF/资产和 selected-browser recovery waterfall 执行
- 对 `arxiv` 来说，系统始终按内部 `arXiv ID 解析 -> arXiv official HTML -> direct HTTP PDF fallback -> metadata fallback` waterfall 执行；metadata enrichment 只在主链外补充字段
- 对 `copernicus` 来说，系统始终按内部 `landing HTML -> NLM/JATS XML -> direct HTTP PDF fallback -> metadata fallback` waterfall 执行
- 对 `royalsocietypublishing` 来说，系统始终按内部 `selected-browser DOI HTML -> browser-seeded PDF fallback -> metadata fallback` waterfall 执行
- 对 `plos` 来说，系统始终按内部 `public JATS XML -> direct HTTP PDF fallback -> metadata fallback` waterfall 执行
- 对 `frontiers` 来说，系统始终按内部 `landing HTML -> public JATS XML -> direct HTTP PDF fallback -> metadata fallback` waterfall 执行
- 对 `oxfordacademic` 来说，系统始终按内部 `direct HTTP article HTML -> direct HTTP PDF fallback -> metadata fallback` waterfall 执行

## 默认输出策略

CLI、Python API、MCP 当前默认值如下：

- CLI `--asset-profile=body`
- Python API / MCP `strategy.asset_profile=null (provider default)`
- `max_tokens="full_text"`
- `include_refs=null`
- MCP `modes=["article", "markdown"]`
- MCP `prefer_cache=false`
- MCP `no_download=false`
- MCP `save_markdown=false`

### `asset_profile`

- `null` / omitted
  - 使用 provider default
  - `springer` / `wiley` / `science` / `pnas` / `ieee` / `arxiv` / `copernicus` / `ams` / `mdpi` / `royalsocietypublishing` / `annualreviews` / `plos` / `frontiers` / `oxfordacademic` / `acs` / `iop` / `aip` 默认等价于 `body`
  - 其他默认等价于 `none`
- `none`
  - 不下载本地资产
  - 不主动清除 Markdown 中已有或 provider 可解析出的远程图片链接
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

#### PDF fallback 的 PDF 图片边界

- PDF fallback 的正文 Markdown 仍由 shared `pymupdf4llm` PDF 转换产生，不引入 provider-owned HTML/XML 清洗。
- 适用 provider：`elsevier`、`springer`、`ieee`、`arxiv`、`copernicus`、`royalsocietypublishing`、`annualreviews`、`plos`、`frontiers`、`oxfordacademic`、`wiley`、`science`、`pnas`、`ams`、`acs`、`iop`、`aip`、`mdpi`。
- `asset_profile=body|all` 且 artifact mode 允许资产落盘时，PDF / ePDF fallback 会把 `pymupdf4llm` 导出的图片保存到 `<doi>_assets/` 并作为正文 inline asset 进入最终 article；`asset_profile=none` 或 `artifact_mode=none` 不保存本地图片。
- PDF fallback 无法稳定区分 supplementary，导出的图片统一按正文资产处理。
- 共享 PDF Markdown 转换会拒绝明显过短或主要由 IEEE 授权页脚组成的结果。
- 共享转换会在渲染后统一修复 `pymupdf4llm` 1.28.0 的确定性标题漂移，包括同级字母小节漏标、空的封面导航标题、重复 title/running header；规则只调整 Markdown 结构，不按 provider/DOI 分支，也不删除正文文本。
- PDF 内有大量透明文本层时，会用 PyMuPDF transparent-text 路径二次转换。
- Windows 上 PyMuPDF 探测 Tesseract 时可能产生本地编码的 stdout/stderr；PDF Markdown 转换会对这类第三方文本子进程输出使用 replacement 解码，避免非 UTF-8 字节让 reader thread 抛出 `UnicodeDecodeError`。
- 二次转换仍不足时，继续走候选重试或 provider 降级。

#### Provider HTML/XML 资产语义

- `wiley` / `science` / `pnas` / `annualreviews` / `royalsocietypublishing` / `acs` / `iop` / `aip` / `mdpi` 的 selected-browser HTML 成功路径支持正文图、表和公式图片资产；Royal Society Publishing HTML 路线保留 Silverchair `div.fig-section` figure caption；AIP replay 覆盖本地 body figure asset rewrite；IOP 当前 committed replay 覆盖远程正文 figure links/captions、body table 和 formula image Markdown，并从 `_online`/`_lr` 标准图链接派生 `_hr` 高分辨率候选，资产下载合约按 best-effort 记录。
- 这些 browser-backed provider 以 selected-browser context 为 HTML 主链路；普通 HTTP 直连不是 HTML 主路径。
- 图片候选优先 full-size/original；全部失败后才尝试 preview，preview 也通过同一个 seeded browser context 下载。
- AMS 走 selected-browser HTML；正文资产复用已加载正文页的浏览器上下文，失败时再按共享 browser asset recovery 顺序回退。
- `ams` 的正文 figure 和 image-only table 会在原 DOM 位置渲染图片块；正文已消费的 figure / table 资产不会再追加到尾部附录。
- `ams` 的正文 figure 下载候选优先来自 `Download Figure` EPS/TIFF；转换后的 PNG 是 Markdown 使用的本地图片，原始源文件保存在同一资产目录并通过 `original_source_path` / `conversion_source_format` / `conversion_output_format` 记录。
- `ams` 表格没有真实 HTML table 时，以 `Table N.`、保留 inline 语义的 caption 和 full-size 表格图片作为可读降级。
- `ams` MathJax 渲染层只作为公式转换输入或 fallback 来源，不应和 LaTeX / MathML 结果重复出现在正文里；display equation label 只来自源站明确编号，不为无编号公式合成。
- `arxiv` HTML 成功路径会从 official HTML 正文抽取 figure 资产候选；当 official HTML 只有缺失图片占位符时，会额外尝试从 arXiv e-print source 包恢复正文图资产。
- `arxiv` 正文图片先插在原 figure caption 附近，下载后改写到 `body_assets/...`。
- 已原位消费的 `arxiv` body figure 不会进入尾部 `Figures`；source 包恢复出的图片会按 caption label 插回正文，而不是作为尾部 `Figures` fallback。
- `arxiv` 图片下载用 direct `HttpTransport` 和图片友好的 `Accept` header。
- `arxiv` 不使用 official HTML URL 触发 cookie-seeded opener。
- `arxiv` 正文图片并发上限是 `min(PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY, 2)`。
- `arxiv` 对网络异常类失败顺序重试一次，不重试 404 或非图片 payload。
- `download_tier=preview` 只有满足最小宽高才视为可接受 preview。
- 宽扁但面积足够的真实论文图可标记为 `preview_accepted`。
- `preview_accepted` 只保留 source trail / asset diagnostics，不写普通 warning。
- 小图标和占位图仍会作为 preview fallback 失败或降级信号。
- IEEE dynamic HTML 成功路径从 cleaned `#article` fragment 抽取正文图、表和公式资产。
- IEEE `asset_profile=all` 会额外下载明确附件区域或 landing multimedia payload。
- Copernicus XML 成功路径会从 JATS/XML 抽取正文图、表、公式和明确 supplementary links。
- Springer HTML 成功路径只从 cleaned body/content scope 抽取正文图片。
- Elsevier XML 的 `body` 只下载 `image` / `table_asset`。
- Elsevier XML 的 `all` 额外下载 `supplementary` references。
- Elsevier supplementary 统一映射到 `kind="supplementary"`、`section="supplementary"` 和 `download_tier="supplementary_file"`。
- Elsevier 正文资产遇到 timeout、TLS、DNS、connection reset/closed 等网络失败时，只对失败项串行重试一轮。
- 明确 HTTP status、权限/认证类或非 HTTP scheme 失败不自动重试。

#### Supplementary 范围与命名

- `wiley` / `science` / `pnas` / `ams` / `annualreviews` / `acs` / `iop` / `aip` / `mdpi` 的 `asset_profile=all` 会把可识别 supplementary 作为独立文件附件下载。Annual Reviews 当前不扩大 supplementary scope；IOP 只把文章页的同 DOI `/data[N]` 当索引，并从索引明确的 `SM数字` 链接下载真实附件。
- 这条链路不因 supplementary 失败重新下载已成功的正文 figure。
- `wiley` supplementary 只从 `Supporting Information` 区块抽取。
- `wiley` 只接受 `/action/downloadSupplement`、结构化 supplementary link 属性或 `sup-*` supporting file 链接。
- 正文 `<figure>` 里的 `/cms/asset/...fig-*.jpg|png|webp` 只保留为 figure 资产。
- `downloadSupplement` query 中的 `file`、`filename`、`attachment`、`download` 优先作为真实文件名。
- 布尔型 `download=true` 不作为文件名。
- `science` / `pnas` supplementary 只从真实 supplementary / supporting section 子树抽取。
- `science` / `pnas` 只保留 publisher `/doi/suppl/.../suppl_file/...` 附件。
- Data Availability 普通数据链接、页内导航和 section 内引用文献 PDF 不归 supplementary。
- Springer supplementary 只允许来自明确 supplementary、supporting 或 extended data section 子树。
- Springer `Source Data` 独立落到 `source_data/` 子目录。
- Springer `Peer Review File` / `Peer reviewer reports` 不归 supplementary。

#### 资产去重与诊断前置约束

- 通用 HTML figure 与 supplementary 下载使用 `paper_fetch.extraction.html.assets.state` 状态机。
- cookie-aware opener/request 统一在 `paper_fetch.extraction.html.assets.requester` 中处理。
- 网络、opener 或浏览器 document fallback resolve 阶段可并发执行。
- Browser workflow 的 browser-backed HTML、PDF fallback 与资产下载通过 `paper_fetch.providers.browser_runtime` facade 访问 Camoufox；provider 代码不应直接调用 backend 私有 helper。
- Camoufox 在同一 `RuntimeContext` 的 owning thread 内复用原生 Firefox/Juggler 进程，每次操作新建隔离 context，并串行执行 browser-backed 资产抓取；Playwright sync 对象不跨线程共享。
- storage-state/profile 路径由 browser runtime 统一解析；auth、preflight、HTML fetch 和 seeded PDF fallback 使用同一 provider-scoped `storage-state.json`，保存时会过滤到当前 publisher URL、加写锁并原子替换。
- Browser-backed asset download 在安全的 caller-thread 路径内会在一次 attempt 中复用同一线程的 page/context；遇到 Playwright 线程所有权异常会降级到 per-call close。
- 文件写入、文件名去重、`source_data/` 分流和失败诊断收集仍串行执行。
- 输出顺序、fallback 候选顺序、`article.assets[*]` 与 `quality.asset_failures` shape 保持稳定。
- Elsevier XML object references 也使用“网络并发、写入串行”约束。
- 并发 worker 上限由 `PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY` 控制，默认 `4`，最小 `1`。
- 普通 HTTP 单资产下载仍可在调用线程解析。
- Provider fulltext 公开契约是 `fetch_result()` / `fetch_raw_fulltext()`。
- Provider fulltext 不提供 `fetch_fulltext()` dict 入口。
- 同一次 provider fetch 内会复用 `RuntimeContext.parse_cache`。
- `parse_cache` 避免 Elsevier XML、Springer HTML、browser-workflow Markdown 和 HTML asset 重复解析。
- IEEE dynamic HTML block-page token 判定也按 payload 缓存。
- 同一个 `RuntimeContext` 生命周期内还会复用 `session_cache`。
- workflow session cache key 由 `paper_fetch.workflow.session_cache.SessionCacheKey` 常量统一生成；`has_fulltext` 与 `fetch_paper` 可共享 query resolution、Crossref DOI metadata、Elsevier metadata probe 和 landing page probe。
- fetch 阶段命中 landing probe 时，会把 citation PDF URL 合并到 metadata `fulltext_links`。
- `BrowserContextManager` 会在进程内按 browser 配置 lazy 复用 managed Chrome 生命周期；`RuntimeContext` 关闭时释放引用，最后一个引用释放后关闭自动启动的 Chrome，进程退出时还有 `atexit` 兜底清理。外部 endpoint 的每个 context 会断开本次 CDP 连接，不关闭操作者的浏览器。
- PNAS 正文 HTML、正文图片/文件 fetcher 与 PDF/ePDF fallback 仍按阶段创建独立 browser context/page。
- `RawFulltextPayload.metadata` 只是 read-only compatibility view。
- provider 新逻辑应读写 `ProviderContent.route_kind`、`markdown_text`、`diagnostics`、`fetcher`、`browser_context_seed`、`warnings`、`trace` 和 `merged_metadata`。

### 资产去重与诊断

- `render_state="inline"` 的资产表示正文已经渲染过，不会进入文末 `Figures` / `Tables`。
- `render_state="appendix"` 的资产仍可进入尾部兜底块；当同类资产全是 appendix 状态时，标题会显示为 `Additional Figures` / `Additional Tables`。
- 正文 Markdown 图片链接和资产路径会按 URL、路径、相对 `body_assets/...` 后缀和 basename 做等价比较。
- 保存 Markdown 时也会按 `full_size_url`、`preview_url`、`download_url`、`original_url`、`source_url` 和最终 `path` 改写远端图片链接。
- 保存 Markdown 时，本地资产路径会先解析 symlink / 平台真实路径，再相对目标 Markdown 文件改写，避免 macOS `/var` 与 `/private/var` 这类等价路径导出成过深的 `../../...` 链接。
- 系统生成或重写的 Markdown 图片行会统一使用短 alt 标签：`Figure N` / `Figure`、`Table N` / `Table`、`Listing N` / `Listing`、`Formula` 或 `Image`；caption 保留为正文段落或资产 caption，不放进 `![alt]`。
- 公式图片资产不参与 figure asset 抽取、跨引用内联或 figure slot 消耗；同一图片 URL 同时命中 figure 和 formula 时保留 formula 语义。
- 这可以避免正文图在尾部重复，或导出残留可本地化远端图。
- 文章组装阶段也会用 `article.assets[*]` 把正文里的远程 figure / table / formula image 链接改写为已下载本地路径，再做 Markdown 图片块边界和短 alt 归一化，避免图片和标题、正文句子或公式块粘连。
- 下载资产会保留 `download_tier`、`download_url`、`original_url`、`preview_url`、`full_size_url`、`content_type`、`downloaded_bytes`、`width`、`height`。
- 下载失败的资产会保留到 `article.quality.asset_failures` 与顶层 `quality.asset_failures`。
- 失败诊断包含 `status`、`content_type`、`title_snippet`、`body_snippet` 和 `reason`。Cloudflare challenge 只记录失败并进入普通候选/seed refresh retry。
- 图片 payload MIME 识别由 `filetype` 负责，JPEG/PNG/GIF/WebP 尺寸读取由 `imagesize` 负责；无法识别时仍按 unknown/空宽高处理，不引入 Pillow。
- `wiley` / `science` / `pnas` / `ams` / `annualreviews` / `acs` / `iop` / `aip` / `mdpi` 正文图片主链路通常输出 `download_tier="full_size"` 或 `download_tier="preview"`；AMS EPS/TIFF `Download Figure` 源图转换成功时输出 `download_tier="source_converted"`。
- supplementary 文件链路输出 `download_tier="supplementary_file"`。
- `playwright_canvas_fallback` tier 只可能来自 HTTP-first 语义的通用图片下载路径。
- browser image document fetcher 会先复用预热正文页中目标 URL 对应的已加载 `<img>` 并用 canvas 导出图片；目标图存在但尚未加载时，会先在同一正文页执行带凭据的 `fetch()` 拉取原图字节；目标图不存在或仍无法取得真实图片时，才退回图片 URL 的直连请求 / 页面 fetch / navigation 候选。
- `wiley` / `science` / `pnas` / `ams` / `annualreviews` / `acs` / `iop` / `aip` / `mdpi` 正文图片下载会缓存重复的 figure page / 图片候选 URL。
- 这条链路按 `PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY` 控制 worker 上限，默认 `4`。
- 使用 browser image document fetcher 时，单个正文图片也会在 worker 线程执行 resolver。
- 这样可以避免主线程已有 browser sync context 时再次启动独立 sync browser。
- 最终输出顺序仍与输入资产顺序一致。
- supplementary 文件下载失败时，`article.quality.asset_failures` 会保留失败诊断。
- 诊断字段包括 `status`、`content_type`、`title_snippet`、`body_snippet` 和 `reason`。
- 浏览器工作流的重试按 `heading`、`caption` 和 URL 字段匹配失败诊断。
- 重试只重跑失败的 body 或 supplementary 资产。
- `download_tier="preview"` 只有在宽高满足当前阈值 `300x200`，或 provider 明确标记该 preview 为可接受时，才会记录 accepted 诊断；否则仍会进入 preview fallback / asset issue 诊断。
- Live review 规则：公式图片是公式语义的 fallback，因此 formula-only preview fallback 不自动归类为 `asset_download_failure`；figure/table preview fallback 仍按资产问题处理，除非已有 accepted 诊断。
- Live review 规则：相关资产下载 warning 会归类为 `asset_download_failure`。
- 这些 warning 包括 `related assets could not be downloaded`、`assets were only partially downloaded` 和 `partially downloaded`。
- `asset_failures` trail 或 `quality.asset_failures` 也会归类为 `asset_download_failure`。
- Live review 规则：golden criteria live review 产物 `extracted.md` 属于内部检查输出。
- 生成脚本见 [`../scripts/run_golden_criteria_live_review.py`](../scripts/run_golden_criteria_live_review.py)。
- 若该文件仍残留 IEEE mediastore 图片链接，且对应资产已经本地下载，会归类为 `asset_download_failure`。
- 即使 preview 被 accepted，上述残留远端链接仍按资产下载失败处理。

### `include_refs`

- `max_tokens="full_text"` 时，默认等价于 `all`
- `max_tokens=<整数>` 时，默认等价于 `top10`

<a id="mcp-download-and-markdown-save"></a>
### 下载行为

CLI 主输出、artifact 与命令组合的用户语义见 [`cli.md`](cli.md)；本节只记录 provider/runtime 侧的下载和 artifact 保留规则。

- CLI `--artifact-mode` 和 MCP `artifact_mode` 控制 provider artifact 保留范围，`--asset-profile` / `strategy.asset_profile` 只控制本地内容资产下载范围；`asset_profile=none` 不会主动移除 Markdown 中可解析的远程图片链接。
- `markdown-assets` 是 CLI 和 MCP `fetch_paper` 默认值：保存 Markdown 和资产策略允许的本地资产，不保存 provider 原始 HTML/XML、额外格式副本或 `<download_dir>/.paper-fetch-http-cache/` textual cache；未显式传 `--output` 且指定 `--output-dir` 时写入的 CLI 主输出文件不属于额外副本。
- 当正文来自 `pdf_fallback` 时，`markdown-assets` 仍会保存 PDF 源文件；文件名优先使用 provider 抓取后合并的标题、作者和年份元数据，缺失时再回退到进入 provider 前的 metadata/DOI。PDF fallback 的 Markdown 转换质量通常低于 XML/provider HTML，需要保留来源便于溯源和排查。
- Browser-backed 正文图片下载对单图有总预算；seed warm、browser page fetch、request-context fetch、直接导航和 image wait 不再简单累加长 timeout。Seeded browser PDF fallback 在进入 PDF 下载前只做 lightweight warm 采集 cookies/user-agent/final URL；当 warm 已经拿到 cookie seed 时，后续 PDF 抓取只传 cookies/referer，不再重复导航同一个 seed URL。
- `all` 保留完整调试 artifact：provider HTML/PDF、辅助 artifact、HTTP textual cache 和 provider structured sidecar 都可落盘；MCP fetch-envelope sidecar/cache-index 仍按 MCP adapter cache 语义单独管理。
- `none` 不保存 provider artifact 或资产；显式 `--output <path>`、`--save-markdown`，以及未显式 `--output` 时由 `--output-dir` 承接的 CLI 主输出仍可写文件。MCP 中 `artifact_mode="none"` 仍可写 fetch-envelope sidecar/cache-index 以支持 `prefer_cache`、`list_cached` 和 resources。
- MCP cache index 读取会校验 index version；旧版或坏 schema 不会被默认当作可信 manifest。`list_cached(cache_mode="index")` 只读 manifest，`cache_mode="refresh"` 校验/修剪/迁移现有 manifest；`get_cached(doi)` 另在当前显式 `download_dir` 内刷新目标 DOI；`rescan` 从 DOI 一致的 fetch-envelope sidecar、结构化 Markdown YAML front matter，以及仍可校验内容指纹的显式注册条目重建整个 index。v1 index 在 refresh 时安全迁移到 v2，无法重新证明归属的旧 Markdown 会被丢弃；其他未知版本需要显式 `cache_mode="rescan"`。
- 本地 Markdown 的 DOI 归属只能由两种证据建立：`save_markdown=true` 成功后以 fetch envelope 的已知 DOI 和实际 `saved_markdown_path` 显式注册，或文件开头的 YAML front matter 经 PyYAML 解析后同时提供可规范化的 `doi`、非空 `source`、布尔 `has_fulltext` 和合法 `content_kind`。文件名、正文中的 DOI 字符串和同目录关系都不是归属证据；坏 YAML、错误 DOI、缺字段或目录外路径不会进入该 DOI 的结果。
- DOI 证明和查询比较统一使用 `normalize_doi()`，因此 DOI URL、大小写和 DOI 合法特殊字符使用同一身份。所有 refresh/rescan 都局限在调用方传入的 `download_dir`，不会跨 scope 搜索或触发网络。scope 检查接受同一根目录的系统等价路径别名（例如 macOS 的 `/var/...` 与 `/private/var/...`），index 中仍记录 canonical 路径；scope 根以下的 symlink 与目录外路径继续拒绝。
- `get_cached(doi)` 的 `preferred.markdown` 只从上述可证明条目选择：当前仍有效且 `has_fulltext=true`、`content_kind="fulltext"` 的版本优先，其次按 front matter 的 `completed_at`（缺失时使用文件 mtime）选择最新版本。Cache entry 会附带 `identity_proof`；Markdown entry 还会附带 `source`、`has_fulltext`、`content_kind`、`completed_at` 和 `content_sha256`。
- `get_cached` 默认 `detail="full"`、`preferred_only=false`，原有 `entries` / `preferred` / index 字段不变。`preferred_only=true` 只返回优选 Markdown/primary entry 数组；`detail="compact"` 完全省略 `entries`、正文、sidecar payload 和资产数组，改为返回优选 entry、`entry_summary`、内容/置信度、acceptance/asset/warning 摘要以及 request fingerprint。
- fetch-envelope 以 DOI + request fingerprint 保存多版本 sidecar；`modes/strategy/include_refs/max_tokens` 与单向 credential capability scope 共同参与 fingerprint，不同请求以及 public/token/storage-state scope 可以并存且不互相覆盖。cache entry 与请求命中仍是两个状态：`status=hit` 只证明当前 `download_dir` 中存在 DOI 归属可证明的条目；`request_satisfied=true` 还要求 sidecar version、extraction revision、credential scope 和 payload DOI 有效，且 `cached_request_matches()` 与 payload modes 满足本次请求。compact 调用必须传与后续 fetch 相同的四组请求参数；它只总结当前快照，不证明任意未来请求。
- sidecar 的 `missing/corrupt/unreadable/version_mismatch/extraction_revision_mismatch/doi_mismatch/invalid_scope` 都结构化报告并禁止请求复用。错误 scope 或无身份可证明条目返回正常 miss，不跨目录搜索、不触发网络，也不伪装成工具失败。
- `--no-download` 等价于 `--artifact-mode none`。
- 对 provider artifact 来说，`download_dir=None` 优先级最高
- CLI/MCP 通过 `workflow.request_builder.build_fetch_pipeline_request()` 统一装配 `FetchPipelineRequest`。
- `FetchPipeline` 负责创建 `RuntimeContext`。
- Provider payload、Springer HTML local copy、Markdown 保存和 asset 诊断仍由 `ArtifactStore` 应用。
- CLI 的 `--output-dir` 是默认主输出、Markdown、PDF fallback 来源文件和本地资产目录；在 `--artifact-mode all` 下也会接收 provider HTML/PDF/图片等调试 artifact。未显式传 `--output` 且指定 `--output-dir` 时，CLI 会把主输出写入该目录，文件名使用安全化论文 stem 加 `.md`、`.json` 或 `.both.json` 后缀，不向 stdout 打印正文；显式 `--output -` 会强制保留 stdout，显式 `--output <path>` 则使用该路径作为主输出。
- 既有 warning 与 `download:*` source trail marker 保持不变。
- MCP `download_dir` 是 cache/artifact scope，不是 CLI `--output-dir` 那样的主输出目录；MCP 只有 `save_markdown=true` 才会单独写 Markdown 主体文件并返回 `saved_markdown_path`。
- MCP fetch-envelope sidecar/cache-index 是 adapter cache，不按 provider artifact 处理；JSON 写入复用 `ArtifactStore` 的原子 writer，但不受 `artifact_mode=markdown-assets|none` 禁止。
- 当 artifact mode 或 MCP `no_download=true` 禁止资产落盘时，即使 `asset_profile` 是 `body` / `all`，资产也不会落盘。
- 没有本地文件时，Markdown 可保留 provider 已解析出的远程图片链接；只有无法解析远程图片时才退回 captions-only 或不展示资源链接。
- MCP `no_download=true` 会让 service/provider 阶段使用 `RuntimeContext(download_dir=None)`，因此不会写 provider payload、PDF、HTML、资产或 fetch-envelope sidecar；`prefer_cache=true` 仍可显式读取已存在的 fetch-envelope sidecar。
- MCP `save_markdown=true` 是独立的 Markdown 保存步骤：成功时写 `.md`、用 envelope DOI 与实际路径显式注册 cache entry、返回 `saved_markdown_path`，并追加 `download:markdown_saved`；没有 fulltext Markdown 时不写文件，追加 `download:markdown_skipped_no_fulltext`。显式注册记录内容 SHA-256；文件之后发生变化时必须由匹配的结构化 front matter 重新证明身份，否则条目失效。
- MCP `save_markdown=true` 的工具响应默认是紧凑结果：`markdown=null`、`article=null`，不把全文正文或 article sections 放入当前上下文；响应仍保留 `saved_markdown_path`、`metadata`、`quality`、`warnings`、`source_trail`、`trace` 和 `token_estimate_breakdown` 等诊断字段。
- MCP `save_markdown=true` 时，即使 `strategy.asset_profile=body|all`，工具结果也不会额外附带 inline `ImageContent`；图片资源仍可按资产策略下载到本地，并由保存的 Markdown 引用。
- `no_download=true` 与 `save_markdown=true` 同时使用时，只允许 Markdown 保存步骤落盘；provider payload、资产和 fetch-envelope sidecar 仍保持关闭。

<a id="provider-原始-html-artifact"></a>
### Provider 原始 HTML artifact

- 当声明了 `ProviderSpec.persist_provider_html=True` 的 provider 抓取链拿到 publisher article HTML 时，`ArtifactStore` 会把可信的原始正文 HTML 单独落盘；当前由 Springer 和 arXiv 声明。
- 如果 `download_dir` 本身就是 DOI slug 文章目录，文件名是 `original.html`；否则文件名是 `<doi_slug>_original.html`。
- `*_assets/` 目录仍可以包含 figure page、table page、redirect page 或辅助 HTML；这些文件不能被当成可信的正文原文源文件。
- 该行为由 [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_springer_html_route_saves_original_html_in_article_dir` 锁定。

<a id="public-output-fields"></a>
## 公开输出里最重要的字段

这些字段最适合拿来判断结果质量和来源：

- `source`
  - 粗粒度公开来源，完整当前枚举与 provider 映射从 `resource://paper-fetch/provider-catalog` 的 `source_provider_map` 读取；`metadata_only` 只在 `FetchEnvelope.source` 的 metadata fallback 中出现。
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
  - 表格区分 `table_layout_degraded_count` 和 `table_semantic_loss_count`；前者表示 Markdown 版式降级，后者才表示语义内容丢失
- `article.quality.asset_failures`
  - 对失败资产保留 `status`、`content_type`、`title_snippet`、`body_snippet` 与 `reason`

### Markdown 与语义 normalize

- 公式输出会在公共公式 normalize 层处理 publisher-specific LaTeX 宏。
- `\updelta` 等 upright Greek 宏会改写成普通 KaTeX 可渲染宏；`\mspace{Nmu}` 会改写成 `\mkernNmu`，其它单位不改；MathJax `\unicode{...}` 码点会改写成 KaTeX 可解析符号，例如 `\unicode{x2A7D}` 输出为 `\leqslant`。
- 外部 MathML 后端返回的常见伪影也会在同一层处理，例如 texmath / mathml-to-latex 产生的空 delimiter `\left(\right.` / `\left.\right)`、被拆成空格的下标标识符 `F_{c r i t}` 和 `S O S_{y 0}`。
- HTML 中源站直接提供的 MathJax / `tex-math` 片段会复用同一套 LaTeX normalize，同时保留原始 `$...$` / `$$...$$` / `\(...\)` / `\[...\]` 包裹，避免 display 公式在清洗后退化成行内公式。
- HTML 公式如果能从 MathML 转成 LaTeX，会按行内或 display 语境渲染；如果只有站点提供的公式图片 fallback，会保留为 `![Formula](...)` 并进入资产下载/改写流程。
- HTML references 会去除 publisher 链接 chrome，如 `Google Scholar`、`Crossref`、`Green Version`、相关链接和隐藏文本，并优先保留用户可见 citation body。
- 默认 reference 组装规则是：fulltext provider 已经从 HTML / XML / 出版社 REST 显式提供非空 references 时，最终 `ArticleModel.references` 和 Markdown references 以这些全文/出版社 references 为准；metadata / Crossref references 只在 provider references 为空、失败或不可用时兜底，不允许追加未匹配的 metadata-only 条目。
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

- 自定义非浏览器 HTTP metadata/API 请求用 `User-Agent`。
- 建议配置为稳定项目标识。
- 不用于 publisher-facing HTML/PDF 直连，也不会传给 browser context；浏览器请求只使用显式 `PAPER_FETCH_BROWSER_USER_AGENT` 或底层浏览器默认 UA。

#### `PAPER_FETCH_BROWSER_USER_AGENT`

- 可选。
- 覆盖 managed Chromium/Playwright browser context 以及 publisher-facing HTML/PDF 直连的 `User-Agent`；Camoufox 后端忽略该变量，以保持生成的 Firefox UA、窗口、字体和 WebGL 指纹一致。
- 未配置时默认使用底层浏览器自身 UA。
- AGU/Wiley 页面遇到 Cloudflare challenge 时，可配置为普通 Chrome UA；例如：

```bash
export PAPER_FETCH_BROWSER_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
```

#### `CROSSREF_MAILTO`

- Crossref polite pool 建议携带的联系邮箱。
- 会被拼入 Crossref 请求参数。

#### `PAPER_FETCH_DOWNLOAD_DIR`

- 覆盖默认下载目录。
- CLI 与 MCP 都会优先使用它。
- CLI 会在开始抓取前创建该目录；MCP `download_dir` 仍按 cache/artifact scope 使用。

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
- `legacy` 不是可用后端；配置该值会返回 backend 不可用错误，不应在新配置中使用。
- 默认是 `texmath`；未显式指定时，如果 `texmath` 失败，会尝试 `mathml-to-latex` fallback。
- 显式指定某个 backend 时，失败会按该 backend 返回，不会自动隐藏错误。
- 内部后端清单由 registry 声明，`auto` 与 benchmark 顺序仍保持 `texmath` → `mathml-to-latex` → `mml2tex` 的既有约定。

#### `TEXMATH_BIN`

- 可选。
- 指定 `texmath` 可执行文件；未配置时先查找公式工具目录，再查找 `PATH`。
- 官方公式工具安装器和全平台离线包固定使用原生 texmath 0.13.2；复用 PATH 中的同版本程序时会复制到公式工具目录，不保留指向构建机或系统路径的符号链接。

#### `MATHML_TO_LATEX_NODE_BIN`

- 可选。
- 指定 Node 可执行文件；默认是 `node`。
- Windows 离线安装器会将它写为包内 `runtime/Lib/site-packages/playwright/driver/node.exe`，避免 Codex Desktop 的 WindowsApps/MSIX 内部 `node.exe` 被外部子进程调用时触发 `[WinError 5]`。

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
- `mathml-to-latex` 默认使用常驻 Node worker；相同 MathML/backend/config 会优先命中结果缓存，不会重复启动 texmath/Node 子进程。

#### `MML2TEX_*`

- 高级可选。
- 代码支持 `MML2TEX_JAVA_BIN`、`MML2TEX_CLASSPATH`、`MML2TEX_SAXON_JAR`、`MML2TEX_XMLRESOLVER_JAR`、`MML2TEX_XMLRESOLVER_DATA_JAR`、`MML2TEX_STYLESHEET`、`MML2TEX_CATALOG`。
- 默认安装脚本不准备这套 Java/XSLT 工具链；只有显式提供这些资产并选择 `MATHML_CONVERTER_BACKEND=mml2tex` 时才使用。

### 图片转换后端

#### `PAPER_FETCH_IMAGE_TOOLS_DIR`

- 可选。
- 覆盖运行时查找 Ghostscript/libvips 的目录。
- 未配置时，运行时会依次考虑 repo-local `.image-tools`、用户数据目录下的 `image-tools`，再查找系统 `PATH`。
- 离线安装器会把它写入 `offline.env` 和 MCP 环境，默认指向安装目录下的 `image-tools`；离线构建不会把构建机 PATH 上的 Ghostscript/libvips 符号链接固化进包内。
- 运行时会按相关 env、搜索目录和候选文件指纹缓存候选列表与可用性探测；同一进程内多张 EPS/TIFF 图不会重复执行 Ghostscript/libvips `--version` 探测。

#### `PAPER_FETCH_GHOSTSCRIPT_BIN`

- 可选。
- 显式指定 Ghostscript 可执行文件，用于 EPS `Download Figure` 转 PNG。
- 未配置时，运行时会在图片工具目录和系统 `PATH` 中查找 `gs` / `gswin64c.exe` / `gswin32c.exe` / `gs.exe`。

#### `PAPER_FETCH_VIPS_BIN`

- 可选。
- 显式指定 libvips `vips` 可执行文件，用于 TIFF `Download Figure` 转 PNG。
- 未配置时，运行时会在图片工具目录和系统 `PATH` 中查找 `vips` / `vips.exe`。

#### `PAPER_FETCH_EPS_DPI`

- 可选。
- Ghostscript EPS 转 PNG 的输出 DPI；默认 `600`。
- 仅影响 EPS 源图转换，不影响 publisher 已提供的 JPG/PNG 图片。

#### `PAPER_FETCH_IMAGE_TOOL_TIMEOUT_SECONDS`

- 可选。
- Ghostscript/libvips 探测与转换子进程超时秒数；默认 `120`。
- 非正数或非整数会回退默认值。超时按转换失败处理，AMS 源图下载继续尝试网页 JPG/PNG 候选。

### PDF fallback guard 与渲染缓存

#### `PAPER_FETCH_PDF_MAX_BYTES`

- 可选。
- PDF fallback 接受的单个 PDF 最大字节数；默认 `157286400`（150 MiB）。
- 超过上限会在写入和 Markdown 渲染前返回 `pdf_too_large` 失败。

#### `PAPER_FETCH_PDF_MAX_PAGES`

- 可选。
- PDF fallback 接受的最大页数；默认 `1000`。
- 能读取页数且超过上限时会在 Markdown 渲染前返回 `pdf_too_many_pages` 失败。

#### `PAPER_FETCH_PDF_MARKDOWN_CACHE_SIZE`

- 可选。
- 进程内 PDF Markdown 渲染 LRU 大小；默认 `16`，设为 `0` 可禁用。
- 只复用无图片导出路径的渲染结果，避免把本地 PDF 图片路径跨输出目录复用；成功结果的 diagnostics 会记录 PDF hash、字节数、页数、cache status 和 Markdown 渲染耗时。

### Elsevier

#### `ELSEVIER_API_KEY`

- 必填。
- Elsevier metadata 和全文 API 的核心凭证。

### Springer

Springer direct HTML / direct HTTP PDF 路线没有额外必填 publisher env：

- `provider_status()` 中会稳定表现为本地 `html_route` 已就绪
- 不需要任何 Springer publisher 凭证
- `nature.com`、`link.springer.com` 与 BMC landing 在内部使用独立 route profile；该分类只影响 selector/diagnostics/fixture coverage，不改变对外 provider 或 source。

<a id="arxiv"></a>
### arXiv

arXiv 路线当前不需要 publisher 凭证；official HTML 主路径不依赖本机转换器：

- `provider_status()` 中 `metadata_api`、`html_route` 与 `pdf_fallback` 不依赖额外 env。
- `html_route` 固定标为 `ok`，表示可直接请求 arXiv official HTML 主路径。
- HTML 不可用、非 HTML、正文不足或质量门控失败时，直接进入 PDF fallback。
- metadata enrichment 默认启用，使用项目内部 Atom API client 调用 `https://export.arxiv.org/api/query` 的 `id_list` 精确查询，不依赖 PyPI `arxiv` / `feedparser` 包，也不实现关键词搜索、作者搜索或分页搜索；API 失败只产生 warning，不会阻断已经成功的 HTML/PDF 正文 payload。
- arXiv 全文路线消费 official HTML；source 包只用于 official HTML 成功但正文图片是缺失占位符时恢复 figure 资产。若 official HTML 缺失或质量不过关，会直接进入 PDF fallback。
- arXiv official HTML 仍兼容 ar5iv/LaTeXML 的 `ltx_*` DOM contract；这些 selector 集中在 provider 数据表中，并为普通 `article > section > h*/p` 标题、摘要和参考文献结构保留 fallback。
- arXiv HTML 系列解析器集中由 `paper_fetch.providers._arxiv_parsing.ARXIV_HTML_PARSER` 指定；正常安装使用 `choose_parser()` 选择可用解析器，arXiv fixture 单测覆盖该路径。
- ar5iv/plain-text 作者前言缺少清晰 person/affiliation DOM 边界时，会使用 `paper_fetch.resources.arxiv.author_boundaries.json` 中的机构/国家边界 fallback，并叠加邮编、国家代码等结构启发式；该数据文件不是通用国家或机构知识库，安装包必须通过 package data 携带。
- ar5iv 服务端转换失败页优先通过 `ltx_ERROR` / `undefined` 等结构 selector 判定；固定 fatal 文案作为失败页信号，命中后该 HTML 被视为不可用并继续 fallback。
- 带 `SITE_UI_COPY_REGRESSION_MARKER` 的 fatal/error 或 publisher UI copy 常量表示站点改版敏感文案，调整时需要回归 extraction rules 单测。
- HTML 资产下载失败会优先读取 transport 层 `RequestErrorCategory` 判定是否可重试；诊断 payload 的 substring fallback 只用于缺少结构化分类的失败记录。

### IEEE

IEEE direct landing/REST HTML/PDF/资产与 selected-browser recovery 路线当前没有额外必填 publisher env：

- `provider_status()` 中会稳定表现为本地 `html_route` 与 `pdf_fallback` 已就绪
- 不需要 IEEE API key
- 是否能拿到全文仍取决于 IEEE Xplore 当前对操作者运行环境的合法访问上下文，以及 endpoint/browser route 是否返回真实 full-text HTML 或 PDF

<a id="wiley-science-pnas-browser-workflow"></a>
### Wiley / Science / PNAS / AMS / Annual Reviews / Royal Society Publishing / ACS / IOP / AIP / MDPI

#### `PAPER_FETCH_BROWSER_BACKEND`

- 可选；省略或设置唯一合法值 `camoufox`。
- 后端选择严格，其它值被拒绝，不自动切换。
- Camoufox 覆盖十家 browser-backed provider 的 HTML、PDF fallback、图片/补充文件、preflight 和 auth，其中包括 AMS。

#### 通用 `PAPER_FETCH_BROWSER_*` 配置

- `PAPER_FETCH_BROWSER_HEADLESS`：默认 `true`，控制所选 managed 后端是否 headless。
- `PAPER_FETCH_BROWSER_TIMEOUT_MS`：默认 `120000`，控制浏览器页面导航超时。
- `PAPER_FETCH_BROWSER_BINARY_PATH`：所选后端的可执行文件覆盖项。
- `PAPER_FETCH_BROWSER_PROFILE_DIR` / `PAPER_FETCH_BROWSER_USER_DATA_DIR`：所选后端的 profile/storage-state 目录覆盖项。
- Camoufox 默认目录为 `publisher-browser-profiles/<provider>-camoufox/`。
- 后端安装、抓取、离线准备和迁移说明见 [`browser-backends.md`](browser-backends.md)。

#### `WILEY_TDM_CLIENT_TOKEN`

- 可选。
- 仅用于 `wiley` 的官方 TDM API PDF lane。
- 未配置时，`wiley` 仍可在 selected-browser runtime 就绪时尝试 HTML 与 seeded-browser PDF/ePDF；已配置时，即使 browser runtime 不就绪，也可单独尝试 TDM PDF fallback。

#### `PAPER_FETCH_WILEY_PROFILE_DIR`

- 可选。
- Wiley 显式 profile 入口。未设置时，managed browser 按 provider 使用 `publisher-browser-profiles/<provider>/storage-state.json`。Wiley 如需人工验证，运行 `paper-fetch auth wiley [--url ...]` 后再次抓取会复用同一 provider storage-state。

#### `PAPER_FETCH_CDP_EXTERNAL_NEW_CONTEXT`

- 默认不设置。只影响显式传入 CDP endpoint 的低层开发/测试调用，不选择生产 backend。

#### `PAPER_FETCH_WILEY_STORAGE_STATE_JSON`

- 可选。
- Wiley 显式 storage-state 入口。未设置时可使用默认 provider-scoped storage-state；自动过盾失败后可运行 `paper-fetch auth wiley [--url ...]` 保存同一 provider 的本地 storage-state。缺失该 JSON 不阻止 Wiley 抓取。

#### `PAPER_FETCH_AMS_STORAGE_STATE_JSON`

- 可选。
- AMS 显式 storage-state 入口。未设置时仍会使用默认 `publisher-browser-profiles/ams-camoufox/` profile 启动 Camoufox 并尝试静默站点验证；自动验证失败后可运行 `paper-fetch auth ams [--url ...]` 保存同一 provider 的本地 storage-state。缺失该 JSON 不阻止 AMS 启动抓取。

#### AGU/Wiley browser UA

- 可选。
- 用于 Wiley / Science / PNAS / AMS / Annual Reviews / Royal Society Publishing / ACS / IOP / AIP / MDPI 的 selected-browser HTML、图片资产恢复和 seeded-browser PDF/ePDF fallback。
- 站点触发 challenge 时，使用 `paper-fetch auth <provider>` 保存 Camoufox 的 provider storage-state。

#### Browser HTML readiness

- `wiley` / `science` / `pnas` / `ams` / `annualreviews` / `royalsocietypublishing` / `acs` / `iop` / `aip` / `mdpi` 的 browser HTML fetch 会先等待 provider 正文 DOM 命中并连续两次轮询稳定，再执行 pre-extraction challenge / paywall 判定。
- ACS 当前 readiness selector 是 `.article-body` 与 `.widget-ArticleFulltext`；旧 Atypon wrapper 不再承担 ACS canonical replay 的就绪判定。
- 如果稳定正文 DOM 已出现，即使页面 shell 仍残留 Cloudflare / challenge 文案，也会继续进入 Markdown 抽取和 availability 判定；只有等待超时仍无可抽取正文 DOM 时，才把 challenge / paywall 作为 HTML route fallback 条件。

<a id="iop"></a>
### IOP Publishing

- `asset_profile=body` 只处理正文 figure；`_online` / `_lr` IOP CDN 图片会派生 `_hr` 候选，已渲染成 LaTeX 的公式不会再把 GIF fallback 当正文图。
- `asset_profile=all` 使用有界两阶段流程：文章页只识别 `#supplDataLink` 或同 DOI `/article/{doi}/data[N]` 索引，不把索引 HTML 当附件；随后把同一个 selected-backend `BrowserRuntimeConfig`、storage-state、文章浏览器 cookie 和 Referer 传给索引/附件 fetcher，只从 `#supplementarydata` 中接受 `id=SM数字` 的文件链接。生产路径配置缺失时返回逐资产结构化失败，不会静默落入 legacy Chrome/CDP。Office 文档、压缩包、数据表、图片或视频都不受通用后缀白名单限制。
- figure 的 Standard/High-resolution 操作链接、页脚 WeChat QR、索引页未编号链接不会进入 supplementary。索引被 challenge 阻断、父 DOI 不匹配、缺少明确 scope 或没有真实附件时，会写入 `article.quality.asset_failures`，因此资产验收不会误报 `complete`。
- publisher 返回的 AWS 签名附件 URL 仅用于即时下载；最终资产和失败诊断会脱敏 `X-Amz-*`、`Signature`、`AWSAccessKeyId` 参数。独立 Radware/hCaptcha 页面仍 fail closed，HTML/PDF 成功 source 分别是 `iop_html` / `iop_pdf`。
- 当前没有声明可用的 IOP TDM XML/API route；runtime catalog 以 `implementation_status=unsupported` 保留 review 结论，避免 status/docs 把不存在的稳定 endpoint 误报为能力。

<a id="royalsocietypublishing"></a>
### Royal Society Publishing

- routing: 通过 `10.1098/` DOI prefix、`royalsocietypublishing.org` domain 和 Royal Society publisher alias 命中。
- waterfall: selected browser 打开 `/doi/{doi}` 或 DOI resolver 后的 Silverchair article HTML；HTML 不可用时用 browser context seed 尝试 `citation_pdf_url` 或 `/doi/pdf/{doi}`；两条全文路线都失败时交给 metadata-only fallback。
- asset_profile: HTML 路线使用 browser-backed article-scoped body assets，并从 Silverchair `div.fig-section` 保留 figure caption；文章 HTML 中的 `DownloadImage.aspx` 签名 CDN 原图优先下载，`/view-large/figure/` 仅作为动态原图发现页，`m_*` preview 最后降级。`all` 额外保留 `/article-supplement/` supplementary 链接；PDF fallback 在 `body/all` 且允许 artifact 落盘时会保存 PDF 导出的正文图片。PDF 正文 Markdown 仍走共享转换，不做 provider-owned HTML/XML 级清洗。
- status: 需要 Playwright/browser runtime，不需要 provider credential；`citation_xml_url` 会回到 HTML/站点路由，不作为 XML route 使用。

<a id="annualreviews"></a>
### Annual Reviews

- routing: 通过 `10.1146/` DOI prefix、`annualreviews.org` / `www.annualreviews.org` domain 和 Annual Reviews publisher alias 命中；Knowable Magazine、issue page 和非 article landing page 不作为该 provider 的成功全文路线。
- waterfall: selected browser 渲染 `/content/journals/{doi}` 或 `/doi/{doi}` landing/full-text HTML，并要求 `#html_fulltext` 或 `#itemFullTextId` 填充；HTML 不足时使用 Crossref / landing PDF URL 或 `/doi/pdf/{doi}` 执行 browser-seeded PDF fallback；仍失败时进入 provider-managed `abstract_only`，最后交给 metadata-only fallback。
- asset_profile: HTML 路线默认使用 `body`，支持正文 figure/table 资产抽取并在下载后改写正文内联 figure 链接；`all` 当前不扩大 supplementary scope，PowerPoint 链接不作为 supplementary material；PDF fallback 在 `body/all` 且允许 artifact 落盘时会保存 PDF 导出的正文图片。
- table rendering: `.html-fulltext-inline-table` 复用 provider-neutral table grid，按列扁平化多层表头并语义展开 rowspan/colspan；Annual Reviews 层只补 table footnotes，不再维护独立的 colspan 填充器。
- status: 需要 Playwright/browser runtime，不需要 provider API credential；probe 级别是 routing signal，成功 source 分别为 `annualreviews_html` 和 `annualreviews_pdf`。

<!-- SCAFFOLD: provider-docs -->

## 运行时护栏

### HTTP 连接池与缓存

`HttpTransport` 带短 TTL 的进程内 GET 缓存和可选磁盘 textual GET 缓存：

- 同一 DOI 的重复 Crossref / metadata 请求可直接命中缓存
- 只有小体积文本响应会入缓存
- PDF 和其他大体积二进制正文不会缓存
- 缓存 identity 与日志脱敏分离：敏感 query/header value 使用单向 SHA-256 scope 区分，不同 Cookie、Authorization、API key 或 token 不能互相命中，原文不进入 cache key、磁盘路径或 structured log；含凭据的响应默认只允许同 scope 的进程内复用，不写磁盘
- `Cache-Control: no-store/private`、`Vary: *`、`Set-Cookie` 和含签名 redirect Location 的响应不缓存；落盘前移除 `Set-Cookie` / auth challenge 等敏感响应头
- `RuntimeContext(download_dir=..., artifact_mode="all")` 会默认启用磁盘 textual GET 缓存，位置是 `<download_dir>/.paper-fetch-http-cache/`；`markdown-assets` / `none` 不会因 `download_dir` 自动创建该缓存
- 磁盘缓存支持 `ETag` / `Last-Modified` 条件请求；stale 条目收到 `304` 时复用本地 body
- `PAPER_FETCH_HTTP_DISK_CACHE_DIR` 可显式指定磁盘 HTTP 缓存目录
- `PAPER_FETCH_HTTP_DISK_CACHE=1` 且未设置下载目录时，会使用用户数据目录下的 `http-cache`
- `PAPER_FETCH_HTTP_METADATA_CACHE_TTL` 控制磁盘缓存 freshness 秒数，默认 `86400`（1 day）；普通进程内 GET TTL 仍默认 `30` 秒
- `PAPER_FETCH_HTTP_DISK_CACHE_MAX_ENTRIES` 控制磁盘 textual GET cache 最大条目数，默认 `4096`；设为 `0` 表示不限制条目数
- `PAPER_FETCH_HTTP_DISK_CACHE_MAX_BYTES` 控制磁盘 textual GET cache 最大总字节数，默认 `536870912`（512 MiB）；设为 `0` 表示不限制总大小
- `PAPER_FETCH_HTTP_DISK_CACHE_MAX_AGE_DAYS` 控制磁盘 textual GET cache 最大保留天数，默认 `30`；设为 `0` 表示不按年龄清理
- 磁盘缓存写入维护增量 path/size/mtime index；只在首次使用、固定写入间隔或周期到期时全量 reconcile，并在超过条数/字节/年龄阈值时批量 prune，避免每次写入扫描整个目录
- `HttpTransport.cache_stats_snapshot()` 返回线程安全的累计计数：`memory_hit`、`disk_fresh_hit`、`disk_stale_revalidate`、`disk_304_refresh`、`miss`、`store`、`bypass`；golden criteria live review 的 sample 结果写入相对执行前的 delta，最终汇总日志保留累计快照

连接池与同 host 并发默认较保守：

- `PAPER_FETCH_HTTP_POOL_NUM_POOLS`：默认 `16`
- `PAPER_FETCH_HTTP_POOL_MAXSIZE`：默认 `4`
- `PAPER_FETCH_HTTP_PER_HOST_CONCURRENCY`：默认 `4`
- `PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY`：默认 `4`，最小 `1`，控制 HTML / browser workflow / Elsevier body asset 下载 worker 上限

### HTTP 重试与大小限制

默认护栏包括：

- `max_response_bytes=32 MiB`
- 只对幂等 GET/HEAD 的 `5xx`、timeout、connection reset/closed 和 temporary DNS 做有限短重试；TLS/security 与确定性 DNS 错误不重试
- backoff 和 cooldown 等待会先释放同 host 并发槽；`429` 优先遵守 `Retry-After` 并进入 host/provider cooldown，不混进普通瞬时错误重试
- 底层使用 `urllib3.PoolManager` 复用连接
- Retry policy 使用 `urllib3.util.Retry` 表达；本地 wrapper 继续保留 public request options、structured logs、cancel checks、最大等待时间和 `RequestFailure` 形状

<a id="provider-status-local-boundary"></a>
### `provider_status()`

`provider_status()` 只检查本地条件，不主动探测远端 publisher API 连通性。需要真实打开 browser-backed provider 样例、刷新 `publisher-browser-profiles/<provider>/storage-state.json` 并识别 Cloudflare/Radware/hCaptcha 等 challenge 时，使用 CLI `paper-fetch browser-preflight` 或 MCP `browser_preflight`；两个入口直接共用同一个 preflight 核心，用内置样例 DOI/URL 构造正常 HTML candidates，复用 provider HTML bootstrap、同一 browser context 重试和 availability 判定，但不触发 PDF fallback。它们是 live 预检，不改变 `provider_status()` 的本地诊断语义。

MCP 入口为 `provider_status(provider=None, group=None, detail="full")`。无参数调用仍按 runtime catalog 顺序返回全部 provider，保持原契约；已知单篇目标应传 `provider`，避免把全部 provider checks 放入上下文。`group` 从 catalog 动态派生：`all` 为全部，`official` 为 official provider，`browser` 为 `requires_browser_runtime=True`，`direct` 为不需要 browser runtime，`metadata` 为非 official provider。provider 与 group 同时给出时必须相容。`detail="compact"` 的每项严格只包含 `provider`、`status`、`reason_code`、`reason` 和 `suggested_action`；`detail="full"` 保留既有 `checks`、`missing_env` 和 notes，并附加配置来源与本地能力。

所有结果都显式带有 `diagnostic_scope="static_configuration_and_local_dependencies"`、`live_network_checked=false` 和 `remote_publisher_health="not_checked"`。其中：

- 配置来源优先级为 process env > 显式 `env_file` > `PAPER_FETCH_ENV_FILE` 指向的文件 > platformdirs 用户配置 > default。报告只含变量名、`source`、`present`、`uses_default` 和 `sensitive`，不包含变量值或配置文件路径。
- browser 本地能力分别报告 Playwright、Camoufox 包和已配置 runtime 是否就绪。静态状态绝不宣称浏览器或出版社页面健康。
- 图片本地能力分别探测 Ghostscript（EPS）与 libvips（TIFF）的候选可执行文件和 `--version` 超时。`image_conversion_backend_missing`、`image_conversion_backend_timeout`、`image_conversion_backend_error` 表示本地转换后端问题；远端资产请求失败沿用网络/资产 reason，不会伪装成后端缺失；一般转换执行失败使用 `image_conversion_failed`。
- 该调用不会执行 HTTP 请求、打开浏览器或自动安装依赖。CLI 的同一汇总入口是 `paper-fetch doctor [--provider ...|--group ...] [--detail full|compact] [--json]`。

MCP `browser_preflight(provider=None, detail="full")` 无 provider 时按 browser runtime catalog 顺序逐项执行，与 CLI 默认一致；指定 `test_url` 或 `storage_state_path` 时必须同时指定单一 provider。它会发送 progress，逐项返回 `ready/challenge/auth_required/runtime_error/cancelled`，并在取消时保留已完成项。默认 `save_storage_state=true` 可能写 provider storage-state；设为 `save_storage_state=false` 可禁止本轮保存。compact 每项只含 `provider/status/reason_code/reason/next_action`。该工具的 annotations 明确是 open-world、非只读和非 idempotent；它不自动 auth、不绕过 challenge，也不进入 PDF fallback。

操作顺序应是 `provider_status` / `doctor`（静态配置与本地依赖）→ `browser-preflight`（CLI）/ `browser_preflight`（MCP）（真实样例网页链路，可能更新 storage-state）→ `auth`（仅在明确需要时由用户人工完成合法登录/验证）。任何静态 `ready` 都不是真实页面可访问、已授权或一定能取得全文的承诺。

当前 provider 状态语义按 runtime catalog 派生，主要分为：

- `elsevier`
  - 只检查官方全文 API key；`ELSEVIER_API_KEY` 配好即 `ready`，否则 `not_configured`。
- `springer` / `oxfordacademic`
  - 返回本地 direct HTML / PDF route 就绪状态；不依赖本地浏览器运行时或 provider credential。
- `arxiv`
  - `metadata_api`、`html_route` 与 `pdf_fallback` 不依赖额外 env；official HTML 主路径不可用时继续 PDF fallback。
- `copernicus` / `plos` / `frontiers`
  - 返回本地 XML / PDF route 就绪状态；不依赖本地浏览器运行时或 provider credential。
- `ieee`
  - direct HTML/PDF route 保持 ready，并额外返回 `browser_fallback` 子检查，报告当前 selected backend 的静态可用性；不依赖 IEEE API key，也不因浏览器缺失把 direct 路线整体标为 not configured。
- `wiley`
  - 统一检查 selected backend 的 `runtime_env`、Playwright 与对应 Python 包，以及可选的 `tdm_api_token`。
  - browser runtime ready 时，即使 `WILEY_TDM_CLIENT_TOKEN` 缺失，也应表现为 `ready`。
  - browser runtime 未配置但 `WILEY_TDM_CLIENT_TOKEN` 已配置时，通常表现为 `partial`，仍可尝试官方 TDM API PDF lane；如果 browser 检查本身报 `error`，provider 状态仍会反映该错误。
- `science` / `pnas` / `ams` / `mdpi` / `annualreviews` / `royalsocietypublishing` / `acs` / `iop` / `aip`
  - 这些 provider 以 `ProviderSpec.requires_browser_runtime=True` 为准，统一检查 selected backend 的 `runtime_env`、Playwright 与对应 Python 包。
  - 本地 runtime 未就绪时，HTML 主路径、图片资产恢复和 seeded-browser PDF/ePDF fallback 会表现为 `not_configured` 或 `error`；远端 access gate、paywall 或 challenge 仍由实际抓取路线判定，不属于 `provider_status()` 的本地探测范围。
