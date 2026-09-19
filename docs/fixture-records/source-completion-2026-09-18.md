# 128 个条目的来源补齐记录

2026-09-18：针对上一份报告中“没有可核验文章原文”的 128 个条目逐项处理，已取得 **118 个条目的可核验文章原文**。其中 112 个为可离线回放全文的 HTML/XML，6 个为已核对文件及身份的 PDF。另有 6 个摘要／附件目录场景、3 个仍未取得全文的条目和 1 个有意保留的无效 DOI 合成场景。剩余 3 个缺口均已由用户确认无访问权限：两篇 Elsevier、一篇 Taylor & Francis。IEEE 已通过文章页 PDF 点击流程取得官方原文件。因此，不能声称 128 个条目均已补齐全文，也不能据此声称 `problems.md` 中所有内容问题已经解决。

逐项结果见 [来源补齐 JSON](source-completion-2026-09-18.json)，全部资产的最新分类见 [来源审计 JSON](source-origin-audit-2026-09-18.json)。2026-09-17 的报告与原始字节保留历史语义。

## 结果与口径

| 结果 | 条目数 | 核验范围 |
| --- | ---: | --- |
| HTML/XML 文章原文 | 112 | 原始实体、同篇身份、现有 provider 离线回放的全文可用性 |
| PDF 文章原文件 | 6 | 实际文件、可读取页与身份；不验收转换质量 |
| arXiv 摘要原页面 | 3 | 同版本完整摘要页；不算全文 |
| arXiv 附件目录原页面 | 3 | 同版本完整附件目录页；不算全文 |
| 出版社元数据／摘要／访问限制页 | 1 | 页面来源及同篇身份成立；全文仍缺失 |
| 尚无可核验文章源 | 2 | 仅保留解析、API 失败等记录 |
| 无效 DOI 合成机制场景 | 1 | 明确保留为 synthetic，不伪造真实替代 |
| 合计 | 128 | 对应 125 个不同 DOI |

本次重新采集 120 个条目，登记 **332 个新响应实体**，包括正文、元数据与失败响应。其余 8 个条目分别利用既有 IEEE 采集记录、6 个 arXiv 父条目的完整原页面，以及保留 1 个无效 DOI 机制场景。

新采集还为 **30 个条目的 34 个既有文章文件**补上了相同字节、相同 DOI 的证据。其他旧文件没有因新采集而自动升级：新的 golden 测试明确使用逐项报告中的 `source` 路径，旧的原文文件、历史预期和合成场景保留。6 个 arXiv excerpt 的片段本身也没有冒充网络原始响应。

当前 manifest 仍为 255 项，登记资产增至 **2599 个**：真实捕获 1520、来源未验证 248、派生／辅助 789、synthetic 23、机制场景 19。真实捕获数包含门禁响应、图片等，**不是论文数**。与上一份资产审计逐文件对比，既有 HTML、XML、PDF 的原始字节均保持一致。本次追加新源及 provenance，不改写历史预期。

## PNAS 空响应后的 Camoufox 补采

按用户指示，对 9 个 PNAS 条目进行 Camoufox 专项补采。使用现有浏览器运行时，将 `/doi/full/` 改为规范 `/doi/` 页面，使用必需正文 selector `#bodymatter, .article-section__body`，给予 30 秒 readiness 等待；不同时启用互斥的通用正文等待分支。

9 个条目均得到可核对同篇 DOI 和正文节点的原始 DOM，离线回放均为全文。实际响应为 **2 次 HTTP 200、7 次 HTTP 403**；后 7 次的运行时 `publisher_access_denied` 仍然保留，没有改为在线访问成功。诊断边界保存的是收到的原始 DOM，不是脱敏后的诊断页面。

DOI 后缀：`2309123120`、`1915921117`、`2208095119`、`2305050120`、`2310157121`、`2314265121`、`2322622121`、`2402656121`、`2410294121`，共同前缀为 `10.1073/pnas.`。各次 URL、时间、HTTP 状态、等待参数、正文长度和 hash 均在逐项 JSON 与对应 `acquisition/provenance.json` 中。

## 用户澄清后的定向续采

用户确认两篇 Elsevier 和 Taylor & Francis 无访问权限，已在逐项 JSON 标记 `access_disposition.status=user_confirmed_no_access`，停止这三篇的进一步采集。该用户确认与原始 HTTP/API 错误分开记录，不能把 Elsevier 的 HTTP 400 擅自改写成权限错误。

AMS `10.1175/AIES-D-23-0093.1` **已补齐全文**。此前两份 DOM 只有 head，没有 body；本次改为必需正文 selector、45 秒 readiness 预算，取得 HTTP 200 的原始 DOM（1,369,793 bytes），同篇 DOI、标题与全文回放均通过。离线 `content=fulltext`，`overall=degraded` 的原因是回放模型的 acquisition 来源链不完整；独立的原始采集记录与 hash 已登记，未将其伪报为完整在线 service 验收。

IEEE `10.1109/MPER.1985.5526567` **已取得官方 PDF 原文件**。此前第 2 次直接 PDF 尝试遇到 HTTP 502，第 3 次 Camoufox 直接导航只得到包装页，报 `pdf_download_not_triggered`。用户随后明确要求先进入文章页点击 PDF：第 4 次等待实际可见的 `PDF` 按钮并点击，监听到包装页 iframe 的 **HTTP 200、`application/pdf` 响应，203,259 bytes、1 页**。原文件见 [IEEE PDF](../../tests/fixtures/golden_criteria/10.1109_MPER.1985.5526567/acquisition/source-completion-2026-09-18/006-user-followup-browser_click_pdf_response.pdf)。PDF Info 的 subject 含请求 DOI，title 与同篇文章页一致；正文没有印刷 DOI 的事实保留。原先只扫页面文字的审计 helper 补入了 PDF 元数据身份检查，未改动文件或转换输出。

该 DOI 属于《IEEE Power Engineering Review》的单页条目，页面上还包含相邻条目，不能当作另一份七页 Transactions 论文。本次验收仅覆盖这一 DOI 的官方文件与身份。

已定位旧流程的漏取点：`stamp.jsp` HTML 包装页含 `/stampPDF/getPDF.jsp` iframe，但现有 `extract_pdf_candidate_urls_from_html` 对真实包装页返回空列表；通用浏览器 PDF 流程等待 download、检查主导航响应，未收取这次内嵌 PDF 响应。随后按用户提议进行第 5 次受控对比：保留文章页预热，并沿用文章页所在的浏览器会话，在可见 PDF 控件就绪后**不点击**，直接导航到该控件的真实包装页 href 并传递文章页 Referer，同时监听 iframe PDF 响应。该路径同样取得 HTTP 200 的 `application/pdf`，PDF Info DOI、标题与 1 页文件均通过核验。因此，对本篇及本次会话，点击并非必要；关键是捕获 iframe 实际返回的 PDF。这没有验证脱离浏览器会话的裸 HTTP 请求或所有 IEEE 论文均可用。逐项 JSON 的 `browser_pdf_gap` 保存原始包装页及 hash、iframe 和候选提取结果。生产自动 fallback 尚未加入该 iframe 响应捕获路径，前几次失败记录继续保留。

本次增加 AMS HTML、IEEE PDF 和来源记录，未修改生产 provider、PDF 转换、全局 fallback 或访问判定。

## 仍未取得全文的 3 个条目（用户确认无访问权限）

| DOI | 本次结果 |
| --- | --- |
| `10.1016/0034-4257(88)90106-X` | 用户确认无访问权限，停止续采；保留此前 API 400 `INVALID_INPUT`。 |
| `10.1016/0168-1923(91)90003-9` | 用户确认无访问权限，停止续采；保留此前 API 400 `INVALID_INPUT`。 |
| `10.1080/01972243.1995.9960198` | 用户确认无访问权限，停止续采；保留同篇访问限制页及 paywall/access gate 判定。 |

`10.1016/S1575-1813(18)30261-4` 另计为无效 DOI 机制场景。其 PII 对应已单独登记的真实论文 `10.1016/j.edumed.2018.09.002`，不能把另一 DOI 的真实文件放到无效 DOI 下冒充成功。

## 证据与验收边界

- 原始实体按字节保存，记录 DOI、请求 URL、实际可观察到的最终 URL／HTTP 状态、UTC 时间、采集方式、大小及 SHA-256。网络错误和未知状态不补写成成功。
- 4 篇旧 Copernicus 的 XML 只有摘要，因此通过现有 provider 的 PDF 路径补采官方 PDF；以已捕获页面中的 DOI、明确 PDF 链接和首页标题绑定身份。PDF 未内嵌 DOI 的事实保留。`acp-1-1-2001`、`bg-1-1-2004` 的运行时 PDF 身份验收失败也保留，离线身份核对结果单独记录。
- AMS `bams-d-24-0270.1` 的 PDF 来自本次已完成的 service 浏览器回退和实际落盘文件。观察器漏记流式响应，因此追加记录注明采集时间窗口、运行时来源链和原 artifact；未观察到的 PDF 最终请求 URL／HTTP 状态保持未知。
- 首轮观察器有 17 次在 service 返回后误用 `requested_modes` 验收参数；此前原始实体已保存。修正为 `requested_outputs` 后用已保存原文离线核验，没有因记录器错误重复发起同样的网络请求。原始错误仍在逐项报告中。
- HTML/XML 回放仅证明同篇原文与全文可用性，不等于逐字、完整公式／表格／书目或本地图片质量验收。PDF 不进行任何转换清洗、排版修复或转换质量评分。本次未修改生产提取器、版本或 CI。

## 验证

不点击 iframe 捕获实验的原始实体登记后，来源完整性复验 **7 passed、1740 subtests passed**。

IEEE 点击补采后，完整来源专项 golden 与身份 unit 合跑 **241 passed**（238 golden＋3 unit）；来源／测试证据 policy **29 passed、1737 subtests passed**。PDF 元数据身份 helper 和 unit 通过 Ruff 检查，历史结果保留如下。

用户定向续采后，受影响来源／全文回放及清单覆盖专项 **6 passed**；来源／测试证据 policy **29 passed、1734 subtests passed**。前一阶段的完整测试结果保留如下。

所有测试沿用 `pyproject.toml` 的默认并行配置，没有使用 `-n 0`。

- 新身份边界 unit：**2 passed**。
- 完整 integration：**127 passed、4 skipped，1777 subtests passed**。
- 来源专项 golden：**236 passed**（125 个来源／身份核对、111 个 HTML/XML 全文回放）；随后新增的 128 条目完整覆盖检查另跑 **1 passed**，合计 **237 passed**。
- 清单覆盖测试登记后，来源／测试证据 policy 专项复验：**29 passed，1733 subtests passed**。
- 本次修改的 helper／测试通过 Ruff 检查及格式检查。

完整 integration 首轮有 1 项失败：既有浏览器测试虽然指定了本地 Camoufox，却仍通过隔离缓存查找 fontconfig，触发 GitHub 更新查询并遭遇 HTTP 403 限流。仅调整该测试，改用已选可执行文件同目录的字体配置；完整 integration 复跑通过。未修改生产浏览器策略。

本次没有重跑完整 unit 和完整 golden；没有修改生产提取器或历史原文。对应完整命令和日志在逐项 JSON 的 `validation` 字段。采集、离线审阅及测试日志保存在 [本次运行目录](../../.paper-fetch-runs/source-completion-2026-09-18/)；可持久审查的原始实体和 provenance 位于各 fixture 的 `acquisition/` 下。
