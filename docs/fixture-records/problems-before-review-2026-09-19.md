# 问题清单与修复状态

> **2026-09-19 正式重新采集：** Wiley P02 本轮31/31正文资产本地化、complete；P18七篇arXiv全文资产78/78本地化；P19两篇PLOS全文资产27/27本地化，保留preview降级。P17 T&F本轮结构化公式、5/5正文图、complete；用户已确认没有问题，旧232个GIF不再列为本轮待补，未下载事实保留。本轮27篇采集目标已收口。27篇逐项验收、入库与仍保留的证据边界见[正式重采记录](docs/fixture-records/official-reacquisition-2026-09-19.md)。下文9月18日的单轮限制保留为历史事实。

更新：2026-09-18。原清单 **18 项**已按顺序委派处理，17 项已完成局部修复、原归因纠正及相应证据核验；P02 的 26 个公式实体已跨两轮核验，最新抓取仍有 1 张公式受限；P17 的图片实体证据仍受访问限制。各条目保留真实资产质量与全文分母，不把局部目标完成等同于整篇 acceptance complete。此前完整验证通过：unit 2486 项、integration 136 项（4 skipped）、golden 2839 项（1 skipped）；后续 P02 资产预处理修复另通过 34 项定向测试与 1808 个子测试。详见汇总记录。

依据：[逐篇回放](docs/fixture-records/markdown-quality-review-2026-09-18.md)、[归并对账记录](docs/fixture-records/problem-triage-2026-09-18.md)、[本次定向核验数据](docs/fixture-records/problem-triage-2026-09-18.json)。P26、P27 已由用户选择 A，无待裁定的策略选项；P17 仍有图片实体证据缺口；P02 最新单轮归档仍有 1 张公式未本地化。

各项修复与验证状态见下；本次过程汇总见 [修复记录](docs/fixture-records/problem-fixes-2026-09-18.md)。P05 的 53 个历史图片对象已完成本地组装；P02 的单轮归档限制与 P17 的图片实体证据缺口独立保留。

本文涉及 HTML/XML 内容、回放验收及 IEEE 文件获取。PDF 转换质量不纳入修复或 fixture 补齐目标；禁止清洗或修复 pymupdf4llm 输出。生产改动应优先局限于实际 provider/执行路径，保留现有资产、验收和合法访问边界。

## P02：Wiley gcb.16758 公式与资产预处理已修复

状态：**局部修复及 26 个公式位置的实体核验完成；最新单轮严格归档仍 degraded**；优先级：高；归并：保留旧 P02 的 Wiley 剩余样本，并承接旧 P03 在同篇上的地址证据缺口。

此前已修复渲染后空 MathML 的 19 处占位和七处根相对图片地址。正式抓取进一步发现，原生 MathML 的 `location="graphic/..."` 在独立资产提取时先于相邻官方 fallback 被选中，再按 basename 去重丢弃正确地址，导致 19 张行内公式下载失败。

现已在 Wiley 专用公式资产提取入口复用图片预处理，覆盖原生 MathML 与 MathJax 两种 DOM；紧邻绑定且存在 `location` 时核对文件名，正文继续优先使用结构化数学。真实两种 DOM 的 26 条官方资产地址逐项验证通过。定向验证：34 passed、1808 subtests passed；未改共享浏览器、重试、去重或 PDF 行为。

修复后正式 CLI 约 34 秒取得全文、5/5 正文图和 25/26 公式图；原先失败的 19 张全部成功。本轮仅公式 2 遇到 `cloudflare_challenge`，该公式在前轮正式抓取中已有同官方 URL 的可读 PNG，因此跨轮 26 个位置的实体证据已齐全。当前 manifest 如实保持 30/31 本地资产、严格 local 不满足和 overall=degraded；没有合并旧文件冒充本轮完整成功。

证据：[最新修复与正式重抓记录](docs/fixture-records/wiley-native-formula-assets-2026-09-18.md)；[逐位置、文件哈希与验收](.paper-fetch-runs/wiley-official-fixed-20260918T094520Z/verification.json)；[早期捕获与修复历史](docs/fixture-records/problem-fixes-2026-09-18-p02.md)。

## P05：历史签名图片的 owner 缺陷及 53 对象实体组装已修复

状态：**已修复，53 对象本地组装已验证；保留实际 fidelity 降级**；优先级：中。

首次离线核验：十篇53对象已逐项核对旧/新原文的发布者对象ID、路径、rendition与来源；不能把新签名尚未过期等同于可访问。离线复用真实捕获文件，已验证 ACS `3c06992` 的8张、OUP `btaa823` 的9张、Royal `rsif.2019.0334` 的5张共22张，经现有下载与旧正文组装后成为实际可读的本地文件链接，三篇严格local资产分面为complete。另Royal `rsos.150470` Figure 1、2 已复用捕获的article/viewer/image完成同样组装，本地映射合计24张；该篇严格local如实保留2/5、degraded。完整overall仍保留回放provenance不足的degraded。

已局部修复：ACS `4c03987` 表内 `gr8/gr9` 图片漏入资产候选（8→10）；OUP签名更新后九张已本地化图片仍被旧远程记录重复计数。签名只在OUP对象身份比较时区分认证参数，所有实际请求/来源URL原样保留；不同路径、rendition及内容参数不合并。未调整全局cache/retry，也不承诺旧缓存自动刷新。

首次离线阶段剩余：29对象缺图片实体证据，已有可解码捕获文件均已完成必要组装核验。远程profile继续保留既有链接和验收语义，不升级为必须下载；包括ACS两张表内Graphic在内的旧正文远程更新不得报告成已验证成功。该离线阶段无网络图片请求，不声称其远端403、损坏或不可访问。

详见[修复与未完成清单](docs/fixture-records/problem-fixes-2026-09-18-p05.md)和[53对象机器映射、最终Markdown及profile验收](docs/fixture-records/problem-fixes-2026-09-18-p05.json)。后续实体补证（2026-09-18）：新增29个真实可解码响应，连同已有24个文件，53/53均经既有下载链路与旧正文完成本地组装；十篇按完整原分母验收，local均满足，旧签名URL残留为0。ACS `4c03987` 的一个 fallback preview 仍使资产 fidelity 为 degraded，不宣称全部full-size或overall complete。见[有界资产补证](docs/fixture-records/problem-fixes-2026-09-18-asset-evidence.md)及其[逐响应与组装证据](docs/fixture-records/problem-fixes-2026-09-18-asset-evidence.json)。未手改Expires、剥除请求签名或把新URL期限当作图片可用性证据。

| DOI | 链接数 | 最新链接最早到期日（UTC） | 证据 |
| --- | ---: | --- | --- |
| `10.1021/acsomega.3c06992` | 8 | 2026-10-07 | [原文](<tests/fixtures/golden_criteria/10.1021_acsomega.3c06992/acquisition/article-response-2026-09-15.bin>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/acs/10.1021_acsomega.3c06992.md>) |
| `10.1021/acsomega.4c03987` | 10 | 2026-10-07 | [原文](<tests/fixtures/golden_criteria/10.1021_acsomega.4c03987/acquisition/template-browser-2026-09-16/000-browser_rendered_dom.html>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/acs/10.1021_acsomega.4c03987.md>) |
| `10.1063/5.0188905` | 6 | 2026-10-21 | [原文](<tests/fixtures/golden_criteria/10.1063_5.0188905/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/aip/10.1063_5.0188905.md>) |
| `10.1093/bioinformatics/btaa823` | 9 | 2026-10-20 | [原文](<tests/fixtures/golden_criteria/10.1093_bioinformatics_btaa823/acquisition/known-gaps-2026-09-16/000-browser_rendered_dom.html>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/oxfordacademic/10.1093_bioinformatics_btaa823.md>) |
| `10.1098/rsif.2019.0334` | 5 | 2026-10-08 | [原文](<tests/fixtures/golden_criteria/10.1098_rsif.2019.0334/acquisition/article-response-2026-09-15.bin>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/royalsocietypublishing/10.1098_rsif.2019.0334.md>) |
| `10.1098/rsos.150470` | 5 | 2026-10-09 | [原文](<tests/fixtures/golden_criteria/10.1098_rsos.150470/acquisition/requested-viewer-2026-09-16/000-browser_rendered_dom.html>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/royalsocietypublishing/10.1098_rsos.150470.md>) |
| `10.1098/rsos.201188` | 3 | 2026-10-06 | [原文](<tests/fixtures/golden_criteria/10.1098_rsos.201188/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/royalsocietypublishing/10.1098_rsos.201188.md>) |
| `10.1098/rsos.201200` | 3 | 2026-10-06 | [原文](<tests/fixtures/golden_criteria/10.1098_rsos.201200/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/royalsocietypublishing/10.1098_rsos.201200.md>) |
| `10.1098/rspb.2020.0097` | 2 | 2026-10-08 | [原文](<tests/fixtures/golden_criteria/10.1098_rspb.2020.0097/acquisition/subscription-2026-09-15/response-005.bin>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/royalsocietypublishing/10.1098_rspb.2020.0097.md>) |
| `10.1098/rsta.2019.0558` | 2 | 2026-10-09 | [原文](<tests/fixtures/golden_criteria/10.1098_rsta.2019.0558/acquisition/subscription-2026-09-15/response-005.bin>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/royalsocietypublishing/10.1098_rsta.2019.0558.md>) |

## P06：MDPI、Science 五处文内链接没有输出目标

状态：**已修复，原文对象身份与筛选回归通过**；优先级：中。

修复前的 Markdown 保留以下本地 fragment，但既没有显式目标，也没有对应名称的标题可生成这些 fragment；正文中的引用或表格跳转不可用。只保留剩余三篇五处，不将已处理的 Royal Society 链接列入本项。

| DOI | Markdown 行 | 缺失目标 | 证据 |
| --- | --- | --- | --- |
| `10.3390/math11030657` | 170, 170, 209 | `#B68-mathematics-11-00657`、`#B69-mathematics-11-00657`、`#table_body_display_mathematics-11-00657-t0A4` | [原文](<tests/fixtures/golden_criteria/10.3390_math11030657/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/mdpi/10.3390_math11030657.md>) |
| `10.1126/science.abp8622` | 171 | `#R43` | [原文](<tests/fixtures/golden_criteria/10.1126_science.abp8622/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/science/10.1126_science.abp8622.md>) |
| `10.1126/science.adp0212` | 112 | `#R49` | [原文](<tests/fixtures/golden_criteria/10.1126_science.adp0212/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/science/10.1126_science.adp0212.md>) |

处理与验收：MDPI / Science owner 按原 DOM 书目／表对象 ID 将五处链接补全为同篇官方对象地址；Table A4 从隐藏弹窗 ID 按显式关联映射至可见表 wrapper。没有有效来源地址时降为无跳转文字。原 HTML ID 不在输出中时不新增空 anchor。三篇 golden 逐项核验 B68/B69/R43/R49 的书目身份及 Table A4 表身份，覆盖 `include_refs=all/top10/none`、表注及公开 token 预算过滤附录；unit 约束无来源、无关同名 ID 和外部链接边界。证据：[P06 修复记录](docs/fixture-records/problem-fixes-2026-09-18-p06.md)。

## P07：旧回放适配器将真实标题覆盖为 DOI

状态：**已修复，旧适配器真实来源回归通过**；优先级：中。

修复前，verified-source 回放的三篇标题正确，但沿用 `tests/golden_corpus.py` 的 `_base_metadata()` 和 canonical builder、仅切换到相同已核验原文字节时，Article metadata.title 仍为 DOI。缺失 title 被 fixture.title 退化成 DOI，再压过真实标题。本项在旧适配器直接构建路径修复，不以新的正确回放遮蔽问题，也不据此推断联网生产一定同样失败。

| DOI | 应保留的原文标题 | 证据 |
| --- | --- | --- |
| `10.1016/j.rse.2026.115369` | Sentinel-1 for offshore wind energy application | [原文](<tests/fixtures/golden_criteria/10.1016_j.rse.2026.115369/acquisition/source-completion-2026-09-18/002-http_response_entity.xml>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/elsevier/10.1016_j.rse.2026.115369.md>) |
| `10.1007/s10584-011-0143-4` | Hydrological response to climate change in a glacierized catchment in the Himalayas | [原文](<tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/acquisition/source-completion-2026-09-18/001-http_response_entity.html>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/springer/10.1007_s10584-011-0143-4.md>) |
| `10.1038/nature12915` | A two-fold increase of carbon cycle sensitivity to tropical temperature variations | [原文](<tests/fixtures/golden_criteria/10.1038_nature12915/acquisition/source-completion-2026-09-18/001-http_response_entity.html>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/springer/10.1038_nature12915.md>) |

处理与验收：HTML/XML 的 `_base_metadata` 排除缺失／空白／同 DOI 占位，PDF fallback 回放元数据保留原行为；Elsevier 复用 XML coredata 身份提取，Springer 复用 HTML 源元数据解析，两者沿用 base-first 合并并在合并前拒绝不同 DOI。三篇以缺失 title 和 DOI 占位两种输入走旧 canonical builder，Article JSON、YAML、唯一 H1 均采用源标题，DOI 不变。最小 unit 覆盖真实标题优先、无源标题和身份冲突；没有修改生产 owner 或 fixture 标题。`nature12915` 按独立原文八个正文标题断言修正旧重复 H1 导致的节数预期。证据：[P07 修复记录](docs/fixture-records/problem-fixes-2026-09-18-p07.md)。

## P08：Annual Reviews Figure 3 与图注公式重复

状态：**已修复，原文对象次数与位置回归通过**；优先级：中。

`10.1146/annurev-control-090419-075625` 修复前输出中，`as030269.f3.gif` 与 `eq-075625-125/126/127.gif` 各出现两次；原文 `#itemFullTextId #f3` 为一个图块。第 805、813 行重复主图，第 807–811 行单独输出公式，随后第 815 行图注再次包含这三幅公式。此问题与 P24 的 arXiv 尾图分开处理。

证据：[原文](<tests/fixtures/golden_criteria/10.1146_annurev-control-090419-075625/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/annualreviews/10.1146_annurev-control-090419-075625.md>)

处理与验收：仅在 Annual Reviews 渲染副本中让图注子树先形成原位 Markdown，主图枚举不再包含图注公式，资产发现仍读取原 DOM。原文实际为全部 128 个独立公式图片（含 Figure 3 图注 124–127 四幅），不是另外 128 个。golden 核验全部 128 个源顺序与每幅位置、全部主图次数、四幅图注公式原位及 138 条引用身份／顺序；unit 验证不同 figure 和正文合法复用 URL 不被删除。证据：[Annual Reviews 修复记录](docs/fixture-records/problem-fixes-2026-09-18-annualreviews.md)。

## P09：最终输出验收仍存在独立覆盖缺口

状态：**已补独立源对象断言与损坏输出反例**；优先级：高。

完整 golden 的既有通过记录与本次 P06 的五处悬空 fragment、P08 的四组重复图片及 P18 的 object/内联 SVG 遗漏并存。现有检查未充分约束输出目标可达性、单个源图块的输出次数及图形表示类型；“有图注”“引用数量正确”不足以验证这些对象完整。

证据：[完整回放及验证记录](docs/fixture-records/markdown-quality-review-2026-09-18.md)、[本次定向检查](docs/fixture-records/problem-triage-2026-09-18.json)。具体文章和原始对象见 P06、P08、P18；单项内容修复与本项测试能力不重复计为新增文章。

处理与验收：复用 tests/support 中的 helper，从独立原文对象登记预期，再检查最终渲染位置、同篇对象身份、fragment 目标和出现次数。删除目标、删除 SVG 图形、重复同一图块的损坏输出必须被拦截；原文合法重复必须通过。其余公式、引文与表格断言随对应问题补齐；不以输出反推预期或更新快照自证。最小片段放 unit，完整原文与资产放 golden，真实浏览器契约放 integration，按项目默认并行配置验证。

补齐结果（2026-09-18）：复用既有 support 和真实回放，P06 五目标校验删除／改错／本地悬空链接；P08 以源出现序列拒绝图及图注公式重复，复制整个 Figure 3 块也失败；P18 七篇 34 个图形核对类型、位置和唯一源出现，删除／复制均失败，五个内联 SVG 及落盘资产完整核对路径、transform、foreignObject 与 MathML 内容。P24 DDPM Figure 1／6／13／14 的源合法复用通过。无生产代码或输出快照改动，29 个远程 SVG 实体未取得的边界不变。详见 [P09 记录](docs/fixture-records/problem-fixes-2026-09-18-p09.md)。

## P16：IEEE PDF fallback 未捕获 iframe PDF 响应

状态：**已修复并验证**；优先级：中。

历史复现：`10.1109/MPER.1985.5526567`的 `stamp.jsp` 返回 HTTP 200 HTML 包装页，实际 PDF 由其中的 `/stampPDF/getPDF.jsp` iframe 加载。现有 PDF 候选提取器对该包装页返回空列表；浏览器 fallback 等待下载事件、检查主导航响应，却未收取内嵌 PDF 响应，最终误以 `pdf_download_not_triggered` 结束。

已验证的方法：先进入文章页完成预热，沿用该浏览器会话与 Referer，直接打开页面提供的 `stamp.jsp` 地址，监听并捕获 iframe 的 `application/pdf` 响应。**无需点击 PDF 按钮，也无需触发下载事件**；本篇已取得 HTTP 200 的真实 PDF，文件可读，PDF 元数据 DOI、标题和页数核对通过。此结论仅覆盖本篇及本次浏览器会话，未证明裸 HTTP 请求或所有 IEEE 论文均可用。

已完成修复与验收：

- 已在 IEEE 专属 stamp 路由内识别同篇 `getPDF.jsp` iframe，并在导航前注册 PDF 响应监听，保留文章页预热、浏览器会话和来源信息；复用现有 provider、超时、大小限制、访问判定及 PDF 验收，不调整全局 fallback 策略。
- 已将实际 PDF 响应字节接入既有 artifact／来源追踪和统一 acceptance；核验同篇身份，保留此前 HTML 失败及降级原因。包装页 HTTP 200 本身不能作为 PDF 成功依据，不增加 PDF 转换清洗或排版修复。
- 真实离线 Camoufox integration 已覆盖“主响应为 HTML、子 iframe 返回 PDF、没有下载事件、没有按钮点击”的浏览器契约，以及子响应不是 PDF／身份不符的失败边界；另覆盖原有主响应直接 PDF 和 download 事件两条路径；golden 复用真实包装页和 PDF，验证来源、DOI、标题与一页文件身份。

证据：[无点击采集的 PDF](tests/fixtures/golden_criteria/10.1109_MPER.1985.5526567/acquisition/source-completion-2026-09-18/009-user-followup-browser_iframe_no_click_pdf_response.pdf)、[包装页](tests/fixtures/golden_criteria/10.1109_MPER.1985.5526567/acquisition/source-completion-2026-09-18/010-user-followup-browser_iframe_no_click_result_dom.html)、[采集记录](tests/fixtures/golden_criteria/10.1109_MPER.1985.5526567/acquisition/provenance.json)。逐项报告中的 `browser_pdf_gap` 和 `user_iframe_no_click_followup` 保留复现与对比结果，见 [来源补齐 JSON](docs/fixture-records/source-completion-2026-09-18.json)。

验证：定向 unit/integration/golden 组合 **58 passed、8 subtests passed**；Linux macOS 契约校验及 portable 测试 **6 passed**。仍需原生 `macos-15` gate，Linux 结果不能替代。修复细节与证据边界见 [P16 记录](docs/fixture-records/problem-fixes-2026-09-18-p16.md)。

## P17：T&F 公式 fallback 输出无效图片地址 //:0

状态：**输出路径已修复；图片可读性待核验**；优先级：高；维度：`formula/image`。

同一篇 Markdown 有 92 个 `![Formula](//:0)`。源 DOM 的 data-formula-source 含实际 GIF 地址，另一类节点含 MathJax 内容。不能把 `//:0` 当成可用公式图片。当前 formula_fallback_count=92、formula_missing_count=0，属于有降级提示但 fallback 本身不可读。

影响文章与复现证据：

- `10.1080/08839514.2024.2375110`：[真实原文](<tests/fixtures/golden_criteria/10.1080_08839514.2024.2375110/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/tandf/10.1080_08839514.2024.2375110.md#L64>)（第 64 行）。

`10.1080/08839514.2024.2375110` 的定位信息：

- `selector`：`img[src="//:0"][data-formula-source]`。
- `output_count`：`92`。
- `example_real_image`：`/cms/asset/e11d8608-4809-4334-ac83-f5049d8a3981/uaai_a_2375110_ilm0001.gif`。

处理与验收：在 T&F 公式路径优先读取实际 MathJax/公式数据；图片回退解析同篇真实地址。逐一核对 92 个位置的可读输出与原公式身份；无可用内容时如实报告缺失，不能仅将 fallback 计数归零。

修复与核验（2026-09-18）：T&F 局部预处理优先真实 MathML／TeX；CHTML 展示树无源公式时按紧邻图片表示的 `data-formula-source` 恢复官方绝对 GIF 地址，同一公式只输出一次。原文实际有 232 对表示（186 inline、46 display），旧 92 个坏输出来自 46 个 display 的双重表示。真实全文逐一核对 232 个地址、顺序、正文位置及资产身份，编号保留，`formula_fallback_count=232 / formula_missing_count=0`；无可用源或图片的最小场景如实计为 missing。尚未下载 GIF 像素，不能将地址恢复视作图片可读性已闭合；有界实体补证已确认232个唯一地址，首个请求HTTP 403后停止该provider，剩余231个未调度，详见[资产补证](docs/fixture-records/problem-fixes-2026-09-18-asset-evidence.md)。原修复详见 [P17 证据](docs/fixture-records/problem-fixes-2026-09-18-p17.md)。

## P18：arXiv object SVG 和内联 SVG 图形遗漏

状态：**已修复，34 个目标图形实体已落盘组装；其他全文资产保留实际状态**；优先级：高；维度：`image`。

7 篇共遗漏 34 个源图形节点：6 篇的 29 个 object[data] SVG，以及 DDPM 的 5 个内联 svg.ltx_picture。图注/正文仍在，但图形没有出现在 Markdown，也没有等价图片引用。此前 img/graphic 检查未覆盖这两种表示。

证据边界：34 是图形节点数，包含子图，不能称为 34 个不同 Figure。首次离线核验未下载29个远程SVG；后续实体补证已完成34个目标本地组装，全文其余资产仍如实计数。

影响文章与复现证据：

- `10.48550/arxiv.1406.2661v1`：[真实原文](<tests/fixtures/golden_criteria/10.48550_arxiv.1406.2661v1/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.1406.2661v1.md>)。
- `10.48550/arxiv.2006.11239v2`：[真实原文](<tests/fixtures/golden_criteria/10.48550_arxiv.2006.11239v2/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.2006.11239v2.md>)。
- `10.48550/arxiv.2605.06659v1`：[真实原文](<tests/fixtures/golden_criteria/10.48550_arxiv.2605.06659v1/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.2605.06659v1.md>)。
- `10.48550/arxiv.2605.06663v1`：[真实原文](<tests/fixtures/golden_criteria/10.48550_arxiv.2605.06663v1/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.2605.06663v1.md>)。
- `10.48550/arxiv.2605.06665v1`：[真实原文](<tests/fixtures/golden_criteria/10.48550_arxiv.2605.06665v1/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.2605.06665v1.md>)。
- `10.48550/arxiv.2605.06666v1`：[真实原文](<tests/fixtures/golden_criteria/10.48550_arxiv.2605.06666v1/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.2605.06666v1.md>)。
- `10.48550/arxiv.2605.06667v1`：[真实原文](<tests/fixtures/golden_criteria/10.48550_arxiv.2605.06667v1/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.2605.06667v1.md>)。

`10.48550/arxiv.1406.2661v1` 的定位信息：

- `embedded_object_image_missing`：4 个节点。

  节点：`S3.F1.g1`、`S3.F1.g2`、`S3.F1.g3`、`S3.F1.g4`。

`10.48550/arxiv.2006.11239v2` 的定位信息：

- `inline_svg_diagram_missing`：5 个节点。

  节点：`S4.F5.pic1`、`S4.F5.pic2`、`S4.F5.pic3`、`A4.F10.pic1`、`A4.F10.pic2`。

`10.48550/arxiv.2605.06659v1` 的定位信息：

- `embedded_object_image_missing`：1 个节点。

  节点：`S3.F1.g1`。

`10.48550/arxiv.2605.06663v1` 的定位信息：

- `embedded_object_image_missing`：12 个节点。

  节点：`S1.F1.g1`、`S3.F2.g1`、`S5.F3.g1`、`S5.F4.g1`、`S5.F5.g1`、`A1.F7.g1`、`A1.F8.g1`、`A1.F9.g1`、`A1.F10.g1`、`A2.F11.g1`、`A2.F12.g1`、`A2.F13.g1`。

`10.48550/arxiv.2605.06665v1` 的定位信息：

- `embedded_object_image_missing`：7 个节点。

  节点：`S1.F1.g1`、`S5.SS1.g1`、`S5.SS1.g2`、`A3.F4.sf1.g1`、`A3.F4.sf2.g1`、`A3.F4.sf3.g1`、`A3.F4.sf4.g1`。

`10.48550/arxiv.2605.06666v1` 的定位信息：

- `embedded_object_image_missing`：3 个节点。

  节点：`S0.F3.g1`、`S1.F1.g1`、`S1.F2.g1`。

`10.48550/arxiv.2605.06667v1` 的定位信息：

- `embedded_object_image_missing`：2 个节点。

  节点：`S4.F3.g1`、`S4.F4.g1`。

处理与验收：覆盖已列出的 object SVG 与内联 SVG，复用现有资产及落盘机制保留图形和子图身份。34 个节点逐一对应输出图形与原位图注；有链接不等于文件已取得，按实际下载状态验收，不新增 PDF 转换修复。

首次离线修复验收（2026-09-18）：7 篇 34 个节点均逐一原位输出，保留子图身份与图注；DDPM 5 个捕获内联 SVG 已经 ArtifactStore/预算管线落盘并组装，本地对象审计 `body_local=5`、`complete`，范围仅这 5 个向量。其余 29 个 object 保留正确绝对源链接，未把链接当下载；既有无下载资产模型验收为 `unknown`。详见[合并证据与测试](docs/fixture-records/problem-fixes-2026-09-18-arxiv.md)及[34 节点映射](docs/fixture-records/problem-fixes-2026-09-18-arxiv.json)。

后续实体补证（2026-09-18）：29个远程SVG取得真实HTTP 200可解析实体，连同5个已捕获内联SVG，34/34逐节点本地化并原位输出一次。七篇完整body分母仍为78，本地34，其余44本轮未获取；除`2605.06659v1`外，全文资产验收仍degraded，未以目标集合代替全文分母。见[有界资产补证](docs/fixture-records/problem-fixes-2026-09-18-asset-evidence.md)。

## P19：PLOS inline-graphic 公式被替换为缺失占位

归并：包含旧 P02 的 PLOS 七处，另增 pbio.0040298 一处，不重复计数。

状态：**已修复并经真实原文回归验证**；优先级：高；维度：`formula`。

两篇分别出现 1 和 7 个 [Formula unavailable]，共 8 处。源 XML 的 inline-formula/inline-graphic 已给出 info:doi 图片身份。现有质量诊断诚实报告缺失，但实际输出未保留图片 fallback。

证据边界：首次离线核验仅确认源XML的图片身份；后续8个inline公式PNG已实际下载、解码并原位组装，不宣称OCR或TeX恢复。

影响文章与复现证据：

- `10.1371/journal.pbio.0040298`：[真实原文](<tests/fixtures/golden_criteria/10.1371_journal.pbio.0040298/acquisition/source-completion-2026-09-18/001-http_response_entity.xml>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/plos/10.1371_journal.pbio.0040298.md#L99>)（第 99 行）。
- `10.1371/journal.pcbi.1003118`：[真实原文](<tests/fixtures/golden_criteria/10.1371_journal.pcbi.1003118/original.xml>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/plos/10.1371_journal.pcbi.1003118.md#L44>)（第 44 行）。

`10.1371/journal.pbio.0040298` 的定位信息：

- `source_selector`：`inline-formula > inline-graphic`。
- `placeholder_count`：`1`。

`10.1371/journal.pcbi.1003118` 的定位信息：

- `source_selector`：`inline-formula > inline-graphic`。
- `placeholder_count`：`7`。

处理与验收：在既有 PLOS/JATS 路径支持 inline-graphic，复用 DOI 资产身份映射。八个位置分别对应原文公式图片、可追溯官方链接或明确的获取失败；不做 OCR，不将图片回退称为 TeX 恢复。

首次离线修复与核验（2026-09-18）：JATS 公式容器识别 `inline-graphic`；PLOS 入口复用既有 DOI 资产映射，将同篇 `.eNNN`／`.exNNN` 转为官方图片地址，实际 MathML／TeX 仍优先。两篇八个位置逐项验证源图片身份、输出顺序、正文位置和资产候选；缺失计数均归零，图片回退如实计数（pbio 全文另有三个原有 display 图片，共四次；pcbi 七次）。合法公式 URL 继续进入现有下载候选，图片像素未下载，不声称 TeX／OCR 恢复。见 [JATS 修复证据](docs/fixture-records/problem-fixes-2026-09-18-jats.md)。

后续实体补证（2026-09-18）：8个真实PNG逐个解码并目视核验为公式，现按源info:doi精确匹配下载文件与正文位置；局部修复同端点不同query误配，以及未获取资产缺少官方HTTP来源而漏出严格验收分母的问题。真实回归逐项核对源身份→请求URL→文件SHA→原位local链接与顺序；零／部分下载时其余对象保持各自远程URL。两篇公式图片完整分母为11，8个inline本地、另3个display未获取；全部body分母为27，8本地、19未获取，保留preview及degraded。见[有界资产补证](docs/fixture-records/problem-fixes-2026-09-18-asset-evidence.md)。

## P20：OUP 行内公式丢失指数中的分数与右括号

状态：**已修复并通过真实后端回放**；优先级：高；维度：`formula`。

源公式 (C,w^(t),Θ^(t+(k−1)/K)) 中，(k−1)/K 和右括号在 merror 内；输出退成 \left(C,w^{(t)},\Theta^{(t +} \right)，分数项消失，语义及括号不完整。源 merror 本身已标错误；本项记录转换后进一步丢失内容，不能把上游错误说成原文完整正确。

影响文章与复现证据：

- `10.1093/bioinformatics/btaa153`：[真实原文](<tests/fixtures/golden_criteria/10.1093_bioinformatics_btaa153/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/oxfordacademic/10.1093_bioinformatics_btaa153.md#L157>)（第 157 行）。

`10.1093/bioinformatics/btaa153` 的定位信息：

- `source_selector`：`math merror`。
- `lost_source`：`<merror><mfrac><mrow><mi>k</mi><mo>-</mo><mn>1</mn></mrow><mi>K</mi></mfrac><mo>)</mo></merror>`。

处理与验收：在实际 MathML 转换路径保留 merror 中仍可读取的分数及括号，同时保留上游错误事实。逐项核对 (k−1)/K、指数与括号；无法可靠转换时使用现有诚实降级，不猜写公式。

修复验证：实际 backend 入口保留 `merror` 子结构，原始 MathML 不改写；OUP 提取诊断及文章 warning 明示上游错误。真实全文分别经 `texmath`、`mathml-to-latex` 验证分数、指数与右括号保留。上游错误本身仍存在，未猜写或宣称修正源公式。详见 [回归记录](docs/fixture-records/problem-fixes-2026-09-18-mathml.md)。

## P21：PNAS 公式 3 的缩进被转换为异常大间距

状态：**已修复并通过真实后端回放**；优先级：中；维度：`formula/layout`。

源 MathML 的 mspace width="40pt" 被输出为 \mkern7200mu，等于 400 个数学 em，会造成极宽公式和横向溢出。各项变量仍保留；这是间距问题，不是八个下标内容丢失。

证据边界：本轮为源码/输出对照，未对每个阅读器做截图或字体尺寸验收。

影响文章与复现证据：

- `10.1073/pnas.2310157121`：[真实原文](<tests/fixtures/golden_criteria/10.1073_pnas.2310157121/acquisition/source-completion-2026-09-18/002-camoufox-selector-dom.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/pnas/10.1073_pnas.2310157121.md#L117>)（第 117 行）。

`10.1073/pnas.2310157121` 的定位信息：

- `source_selector`：`math#me3 mspace`。
- `source_width`：`40pt`。
- `output_spacing`：`\mkern7200mu`。

处理与验收：修正该 mspace 单位转换，保留 40pt 的合理间距及原公式变量。对已知单位换算补最小边界回归，并验证该真实公式不再产生 \mkern7200mu；不能仅删除全部间距或修改 PDF。

修复验证：实际 backend 转换后精确保留 `\hspace{40pt}`；两种 backend 的真实全文回放均在同一公式块核验八项下标，且不再产生 `\mkern7200mu`。已知尺寸、零间距、安全解析及恢复失败有最小边界回归。未扩展为阅读器截图或字体验收。详见 [回归记录](docs/fixture-records/problem-fixes-2026-09-18-mathml.md)。

## P22：Copernicus 空文本引文节点的关联丢失

状态：**已修复并经真实原文回归验证**；优先级：高；维度：`citation/prose`。

正文 90 个 bibr xref 中有 83 个无显示文本，但包含可解析的 rid。输出丢掉这些引用位置；例如 “The potential evapotranspiration was derived using the method of.” 后面没有作者、编号或链接。参考文献列表存在不能替代正文引用关联。

证据边界：83 是源空文本引文节点数；没有把每一个节点误计成独立参考文献。

影响文章与复现证据：

- `10.5194/hess-28-1-2024`：[真实原文](<tests/fixtures/golden_criteria/10.5194_hess-28-1-2024/original.xml>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/copernicus/10.5194_hess-28-1-2024.md#L78>)（第 78 行）。

`10.5194/hess-28-1-2024` 的定位信息：

- `source_id`：`paren.45`。
- `reference_target`：`bib1.bibx20`。
- `empty_xrefs`：`83`。

处理与验收：按 rid 对应真实书目生成可读引文，保留正文位置与关联。逐一核对 83 个空文本节点及其目标，覆盖一处多目标和不可解析目标；不从无依据的文本推测作者或编号。

修复与核验（2026-09-18）：Copernicus 适配层仅为空 `bibr` 引文按 `rid` 读取真实书目 label，保留作者年份短标签并链接同篇官方 XML 的对应书目对象；多目标按源顺序展开，不覆盖已有文字，无法解析时明确提示。83 个正文空节点的 101 个目标逐项核对身份、次序、正文位置；原文 Data availability 另有 `paren.91` 一个空节点／一个目标，全文恢复 102 个关联。`include_refs=all/partial/none` 均不产生悬空本地链接。见 [JATS 修复证据](docs/fixture-records/problem-fixes-2026-09-18-jats.md)。

后续实体补证（2026-09-18）：8个真实PNG逐个解码并目视核验为公式，现按源info:doi精确匹配下载文件与正文位置；局部修复同端点不同query误配，以及未获取资产缺少官方HTTP来源而漏出严格验收分母的问题。真实回归逐项核对源身份→请求URL→文件SHA→原位local链接与顺序；零／部分下载时其余对象保持各自远程URL。两篇公式图片完整分母为11，8个inline本地、另3个display未获取；全部body分母为27，8本地、19未获取，保留preview及degraded。见[有界资产补证](docs/fixture-records/problem-fixes-2026-09-18-asset-evidence.md)。

## P23：GAN 论文标题混入致谢，摘要后残留空表

状态：**已修复并通过真实原文回归**；优先级：中；维度：`layout`。

输出 YAML 标题和 H1 均混入两个 Thanks 致谢段；摘要后还有没有内容的单列表格。原文致谢属于 h1 下的 .ltx_pubnotes，不能当作标题。直接调用现有生产 frontmatter helper 也能复现污染，不仅是身份审计元数据的问题。

影响文章与复现证据：

- `10.48550/arxiv.1406.2661v1`：[真实原文](<tests/fixtures/golden_criteria/10.48550_arxiv.1406.2661v1/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.1406.2661v1.md#L14>)（第 14 行）。

`10.48550/arxiv.1406.2661v1` 的定位信息：

- `source_selector`：`h1.ltx_title_document .ltx_pubnotes`。
- `empty_table_line`：`20`。

处理与验收：在 arXiv 标题提取处排除 .ltx_pubnotes，避免空 frontmatter 表落入正文。元数据、YAML 与 H1 一致使用真实标题，摘要和有效正文不丢失；只移除无内容表格。

修复验收（2026-09-18）：生产 metadata、YAML、H1 均为 `Generative Adversarial Nets`；仅删除无内容 frontmatter 排版表，摘要、有效正文/表格和恢复的 4 个图形节点保留。详见[合并证据](docs/fixture-records/problem-fixes-2026-09-18-arxiv.md)。

## P24：DDPM 相对图片路径；原重复归因已纠正

状态：**已修复相对路径；原文合法重复已核验保留**；优先级：中；维度：`image/layout`。

历史输出中的 Figure 13/14 留下 `2006.11239v2/images/...` 相对地址，导出目录不存在这些文件。最初将其归因为 Figure 1/6 的人工重复追加，经原文核验纠正：原文确有独立 `A4.F13/A4.F14`、各自图注和正文引用，属于合法不同源位置的重复使用，不能删除。

影响文章与复现证据：

- `10.48550/arxiv.2006.11239v2`：[真实原文](<tests/fixtures/golden_criteria/10.48550_arxiv.2006.11239v2/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.2006.11239v2.md#L398>)（第 398 行）。

`10.48550/arxiv.2006.11239v2` 的定位信息：

- `also_line`：`402`。
- `original_lines`：`[20, 227]`。

处理与验收：按来源上下文解析相对 URL，在语义表提取前规范化和标注图片。Figure 1/6/13/14 各按独立源对象原位输出一次，两个共享 URL 各保留两处合法引用，图注及正文 Figure 13 / Figs. 14 and 10 引用不丢失；没有人工尾部 Figures 或悬空相对图片 URL。没有全局去重，也未声称这些远程像素已下载。详见[原文纠正及真实回归](docs/fixture-records/problem-fixes-2026-09-18-arxiv.md)。

## P25：Science 表格退为字段列表且表格退化计数为零

状态：**已修复，真实源表逐格回归通过**；优先级：中；维度：`table`。

原文第三张表的 Variable / Representation in the cellular space / Source 三列，在 Markdown 变成逐项字段列表，含 `<br>`。所核对的字段内容仍在，未确认数值丢失；列对齐已丢失，而 table_fallback_count、table_layout_degraded_count 均为 0。

证据边界：记录展示退化及诊断缺口，不将内容保留的列表降级误报为语义损失。

影响文章与复现证据：

- `10.1126/sciadv.abj3309`：[真实原文](<tests/fixtures/golden_criteria/10.1126_sciadv.abj3309/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/science/10.1126_sciadv.abj3309.md#L160>)（第 160 行）。

`10.1126/sciadv.abj3309` 的定位信息：

- `source_table_index`：`3`。
- `source_first_row`：`["Degradation", "Percentage of the cell degraded at year t", "DEGRAD and DETER (16, 17)"]`。
- `quality_counters`：`{"table_fallback_count": 0, "table_layout_degraded_count": 0, "table_semantic_loss_count": 0, "formula_fallback_count": 0, "formula_missing_count": 0}`。

处理与验收：优先保留源表三列的表格展示，核对全部行、字段及顺序。确需字段列表降级时，table_fallback_count / table_layout_degraded_count 必须反映真实退化；内容仍在时不误报语义丢失。

修复验证：Science 局部保留三列表及全部源字段、行序；末行源只有两格，第二格本身止于 “at year”，第三格留空并附源缺口说明，不补造 t 或 Source。列结构与已有内容均保留，退化及语义损失计数为零符合实际。相关 canonical summary 无需修改。详见 [Science / Springer 记录](docs/fixture-records/problem-fixes-2026-09-18-science-springer.md)。

## P26：Annual Reviews 表题和词汇节出现标题层级跳跃

状态：**已按用户选择 A 修复，五篇九处原文回归通过**；优先级：低；维度：`layout`。

5 篇共 9 处排版问题：表题常从 H3 直接到 H5，Terms And Definitions / Footnotes 常直接用 H4。未确认内容丢失；按用户决定规范阅读层级。归并旧 L01，不重复登记。

影响文章与复现证据：

- `10.1146/annurev-control-030123-013355`：[真实原文](<tests/fixtures/golden_criteria/10.1146_annurev-control-030123-013355/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/annualreviews/10.1146_annurev-control-030123-013355.md>)。
- `10.1146/annurev-control-090419-075625`：[真实原文](<tests/fixtures/golden_criteria/10.1146_annurev-control-090419-075625/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/annualreviews/10.1146_annurev-control-090419-075625.md>)。
- `10.1146/annurev-environ-102511-084654`：[真实原文](<tests/fixtures/golden_criteria/10.1146_annurev-environ-102511-084654/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/annualreviews/10.1146_annurev-environ-102511-084654.md>)。
- `10.1146/annurev-med-120811-171056`：[真实原文](<tests/fixtures/golden_criteria/10.1146_annurev-med-120811-171056/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/annualreviews/10.1146_annurev-med-120811-171056.md>)。
- `10.1146/annurev-neuro-062111-150343`：[真实原文](<tests/fixtures/golden_criteria/10.1146_annurev-neuro-062111-150343/acquisition/assets-2026-09-15/annualreviews-headed-all-001-browser_dom.html>)；[当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/annualreviews/10.1146_annurev-neuro-062111-150343.md>)。

`10.1146/annurev-control-030123-013355` 的定位信息：

- 第 60 行：H5 `Table 1`。
- 第 117 行：H5 `Table 2`。
- 第 177 行：H5 `Table 3`。
- 第 267 行：H4 `Terms And Definitions`。

`10.1146/annurev-control-090419-075625` 的定位信息：

- 第 266 行：H5 `Table 1`。

`10.1146/annurev-environ-102511-084654` 的定位信息：

- 第 257 行：H4 `Terms And Definitions`。

`10.1146/annurev-med-120811-171056` 的定位信息：

- 第 87 行：H5 `Table 1`。
- 第 199 行：H4 `Terms And Definitions`。

`10.1146/annurev-neuro-062111-150343` 的定位信息：

- 第 197 行：H4 `Footnotes`。

处理与验收：Table 1–3 等五处表题使用普通加粗说明，不再形成目录章节；原文 article-level 后置结构中的三个 Terms And Definitions 与一个 Footnotes 作为 H2。golden 逐项核验五篇九处源对象、标题级别、表格全部单元格／表注、术语／脚注内容与相邻正文位置；仅更新真实三个表题伪章节造成的 summary 计数。证据：[Annual Reviews 修复记录](docs/fixture-records/problem-fixes-2026-09-18-annualreviews.md)。

## P27：Springer Methods 伦理小节被过滤

状态：**已按用户选择 A 修复，两篇完整原文回归通过**；优先级：中；归并：旧 P10。

两篇原文的 Methods 内伦理小节被既有 ethics/back-matter 策略整段排除。用户已确认保留这些正文方法说明，页尾继续沿用现有过滤规则。

| DOI | 原文位置 | 当前遗漏内容 | 证据 |
| --- | --- | --- | --- |
| `10.1038/s41467-022-32108-3` | Methods / Ethics compliance（Sec6-content） | 46 年数据采集的动物伦理审批、相关机构许可证及批准、Australian Bird and Bat Banding Scheme 注册说明 | [原文](<tests/fixtures/golden_criteria/10.1038_s41467-022-32108-3/acquisition/template-gaps-2026-09-16/article-response.html>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/springer/10.1038_s41467-022-32108-3.md>) |
| `10.1038/s41522-026-01027-2` | Methods / Ethics statement | 实验遵循动物福利委员会指南，安徽农业大学动物实验与使用委员会批准及编号 AHAUXMSQ2024053 | [原文](<tests/fixtures/golden_criteria/10.1038_s41522-026-01027-2/acquisition/template-gaps-2026-09-16/article-response.html>) · [当前 Markdown](<.paper-fetch-runs/markdown-review-2026-09-18/papers/springer/10.1038_s41522-026-01027-2.md>) |

处理与验收：在 Springer 路径按 DOM 位置和 Methods 父子关系保留两处标题、完整段落及前后节顺序，逐字核对机构、审批编号和数字。页尾 Ethics declarations / Competing interests 等继续沿用现有规则；不直接从全局语义过滤词表删除 ethics。修复公开提取行为时同步对应规则说明与源文回归。

修复验证：依据 Methods 的 DOM section 祖先，仅将对应伦理标题 hint 归为 body；两篇完整段落逐字核对并验证相邻节序，46 年、各机构及 AHAUXMSQ2024053 保留。同名页尾和 Competing interests 分类不变，未调整全局 ethics 词表。详见 [Science / Springer 记录](docs/fixture-records/problem-fixes-2026-09-18-science-springer.md)。
