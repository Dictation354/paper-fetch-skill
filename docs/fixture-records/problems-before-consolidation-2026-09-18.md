<!-- 历史快照：2026-09-18 归并前；不作为当前待办清单。 -->

# 真实来源复审：问题修复结果

## 2026-09-18：新增真实原文的逐篇 Markdown 质量回放

202 项登记全部纳入审阅清单。158 项 HTML/XML 已重新提取并导出：**154 项全文、3 项摘要、1 项元数据**；另 16 项 PDF 按项目约束排除转换质量，28 项没有本轮可审阅的全文输入。不能把旧记录中的 `exported` 自动视为全文。

本轮确认 **9 类问题，涉及 14 篇全文**，另有 5 篇的标题层级排版候选和 1 篇的正文保留范围候选。逐篇结论、原文及当前 Markdown 链接、行号、源/输出 hash、误报复核见 [完整报告](../../docs/fixture-records/markdown-quality-review-2026-09-18.md) 和 [逐项 JSON](../../docs/fixture-records/markdown-quality-review-2026-09-18.json)。以下为识别结果，尚未修改生产提取器或修复输出。

- [ ] **P17：T&F 公式图片 fallback 无效**。`08839514.2024.2375110` 输出 92 个 `![Formula](//:0)`；实际图片地址/MathJax 内容在源 DOM 中。
- [ ] **P18：arXiv SVG 图形遗漏**。7 篇共 34 个图形节点（29 个 `object[data]`、5 个内联 SVG），包括子图；图注保留但图形未输出。
- [ ] **P19：PLOS 行内公式图片遗漏**。`pbio.0040298`、`pcbi.1003118` 共 8 个缺失占位，原 XML 有 `inline-graphic` 身份引用。
- [ ] **P20：OUP 公式截断**。`bioinformatics/btaa153` 的指数丢失 `(k−1)/K` 与右括号；原始 `merror` 的存在及转换后的进一步丢失分别记录。
- [ ] **P21：PNAS 公式间距异常**。`2310157121` 公式 3 的 `40pt` 被转为 `\mkern7200mu`，造成异常宽度。
- [ ] **P22：Copernicus 正文引文关联丢失**。`hess-28-1-2024` 有 83 个带 `rid` 的空文本引文节点；输出出现 “derived using the method of.” 等缺少引用的句子。
- [ ] **P23：arXiv GAN 标题污染及空表**。`1406.2661v1` 标题混入两段 Thanks，摘要后残留无内容表格。
- [ ] **P24：arXiv DDPM 重复尾图与相对链接**。`2006.11239v2` 两张已原位输出的图片在尾部再次追加，地址仍为无法在导出目录解析的相对路径。
- [ ] **P25：Science 表格展示及诊断退化**。`sciadv.abj3309` 第三张表输出为字段列表，已核对的内容仍在，但两个表格退化计数均为 0；未将其误报为数值丢失。
- [ ] **P26：Annual Reviews 标题层级候选**。5 篇共 9 处 H3→H5 等跳跃；属于低优先级排版候选，未确认内容丢失。
- [ ] **P27：Springer Methods 伦理小节的保留范围候选**。`s41467-022-32108-3` 的 `Ethics compliance` 段落被排除；现有策略会过滤 ethics 类内容，因此先记录正文位置与遗漏事实，待裁定保留范围，不擅自调整全局策略。

完整 golden 使用默认并行配置：**2771 passed、1 skipped、34168 subtests passed**。绿灯不表示上述新模板问题已有断言覆盖。本轮只作回放、识别和报告，未改生产代码、fixture、既有预期、版本或 CI；PDF 转换质量不纳入修复或验收。

## 2026-09-18：补齐此前 128 个条目的来源

已为 **118 个条目**取得可核验文章原文：112 个 HTML/XML 全文回放、6 个 PDF 文件及身份核验；另外 6 个是已核验的摘要／附件目录原页面，**3 个仍未取得全文**，1 个保留为无效 DOI 合成机制场景。PNAS 空响应后的 9 个条目均经 Camoufox 补得同篇正文，实际 2 次 HTTP 200、7 次 HTTP 403 与运行时拒绝如实保留。

本次新增 332 个原始响应实体；其中相同字节的采集还为 30 个条目的 34 个既有文章文件补上证据。新的来源回归明确读取已核验的 `source` 路径，未匹配的历史文件继续保留原有未验证状态。当前资产为 2599 个：真实捕获 1520、未验证 248、派生／辅助 789、synthetic 23、机制场景 19；这些是文件数，不是论文数。

用户澄清后的续采：AMS `aies-d-23-0093.1` 已取得 HTTP 200 同篇全文 DOM 并通过回放。IEEE `MPER.1985.5526567` 随后通过文章页实际点击 PDF、捕获 iframe PDF 响应成功，已登记 203,259 bytes 的单页官方文件，PDF 元数据 DOI／标题核验通过。剩余 3 个全文缺口均已由用户确认无访问权限：两篇 Elsevier 旧 DOI 和 T&F `01972243.1995.9960198`，停止续采。后续不点击对比同样成功：保留文章页预热与会话，直接打开包装页并捕获 `getPDF.jsp` iframe 响应即可取得本篇 PDF。自动 PDF fallback 的 iframe 候选识别／响应捕获缺口已定位，本次尚未修改生产路径。详情及逐项证据见 [来源补齐报告](../../docs/fixture-records/source-completion-2026-09-18.md) 和 [JSON](../../docs/fixture-records/source-completion-2026-09-18.json)。本次只补采、登记及核验来源，**不代表下列历史内容问题已全部修复**。

本次验证：新 unit **2 passed**；完整 integration **127 passed、4 skipped**；来源专项 golden **237 passed**（236 项来源／回放＋1 项清单覆盖，分两次运行）。用户定向续采后的受影响来源／全文回放和清单覆盖另跑 **6 passed**；IEEE 点击补采后，来源完整 golden＋身份 unit **241 passed**（238＋3），来源证据 policy **29 passed、1737 subtests passed**。详见上述报告。

## 待优化项

- [ ] **P16：IEEE PDF fallback 捕获 `getPDF.jsp` iframe 的实际 PDF 响应**（方法已实测，生产路径待实现）。

现象：`10.1109/MPER.1985.5526567` 的 `stamp.jsp` 返回 HTTP 200 HTML 包装页，实际 PDF 由其中的 `/stampPDF/getPDF.jsp` iframe 加载。现有 PDF 候选提取器对该包装页返回空列表；浏览器 fallback 等待下载事件、检查主导航响应，却未收取内嵌 PDF 响应，最终误以 `pdf_download_not_triggered` 结束。

已验证的方法：先进入文章页完成预热，沿用该浏览器会话与 Referer，直接打开页面提供的 `stamp.jsp` 地址，监听并捕获 iframe 的 `application/pdf` 响应。**无需点击 PDF 按钮，也无需触发下载事件**；本篇已取得 HTTP 200 的真实 PDF，文件可读，PDF 元数据 DOI、标题和页数核对通过。此结论仅覆盖本篇及本次浏览器会话，未证明裸 HTTP 请求或所有 IEEE 论文均可用。

优化与验收要求：

- 在 IEEE PDF 路由内识别同篇 `getPDF.jsp` iframe，并在导航前注册 PDF 响应监听，保留文章页预热、浏览器会话和来源信息；复用现有 provider、超时、大小限制、访问判定及 PDF 验收，不调整全局 fallback 策略。
- 将实际 PDF 响应字节接入既有 artifact／来源追踪和统一 acceptance；核验同篇身份，保留此前 HTML 失败及降级原因。包装页 HTTP 200 本身不能作为 PDF 成功依据，不增加 PDF 转换清洗或排版修复。
- integration 覆盖“主响应为 HTML、子 iframe 返回 PDF、没有下载事件、没有按钮点击”的浏览器契约，以及子响应不是 PDF／身份不符的失败边界；golden 复用真实包装页和 PDF，验证来源与身份。

证据：[无点击采集的 PDF](../../tests/fixtures/golden_criteria/10.1109_MPER.1985.5526567/acquisition/source-completion-2026-09-18/009-user-followup-browser_iframe_no_click_pdf_response.pdf)、[包装页](../../tests/fixtures/golden_criteria/10.1109_MPER.1985.5526567/acquisition/source-completion-2026-09-18/010-user-followup-browser_iframe_no_click_result_dom.html)、[采集记录](../../tests/fixtures/golden_criteria/10.1109_MPER.1985.5526567/acquisition/provenance.json)。逐项报告中的 `browser_pdf_gap` 和 `user_iframe_no_click_followup` 保留复现与对比结果，见 [来源补齐 JSON](../../docs/fixture-records/source-completion-2026-09-18.json)。

## 2026-09-17：内容修复结果（历史）

更新：2026-09-17。按待办顺序串行调用子代理完成 P15、P01、P13、P14、P03、P04、P06；基于已有真实 HTML/XML 局部修复，未修改 PDF 转换、版本或 CI。

## 修复清单

- [x] **P15：移除 SAGE 活跃样本与登记**。旧合成字节、失败采集及拒绝 hash 保留于历史归档；Springer、Wiley、Elsevier 的真实输入保留多语言摘要覆盖。
- [x] **P01：Science/PNAS 书目**。恢复 Science 100 条、PNAS 正文 78 条及 commentary 21 条非空书目，逐条验证正文、编号、DOI 和顺序。更正：commentary 源有 22 个节点，但第 22 项仅为空的 `.citations#r22`，没有可恢复的正文。
- [x] **P13：Elsevier 平行摘要**。英语四段与西班牙语四段按原文标题、内容和顺序保留。
- [x] **P14：MDPI 公式与诊断**。两处 CO₂ 保留，错误占位为 0；真实缺失公式的占位和诊断计数同步。
- [x] **P03：根相对图片地址**。Wiley 1 处、AMS 7 处按同篇来源解析；保留既有远程、preview/full 与下载状态。
- [x] **P04：协议相对图片地址**。Springer/Nature 三处补齐协议；Box 沿用既有 full-size 选择，新闻保留原图片版本。
- [x] **P06：正文锚点**。六个链接按原文旧标识映射到实际标题 ID：`s2 → 19033670`（4 个）、`s3 → 19033689`（2 个），生成同篇来源页绝对链接。

截至 2026-09-17，活跃 manifest **255 项**（202 个 golden-family、53 个其他条目），登记资产 **2168 个**：真实捕获 1149、来源未验证 287、派生/辅助 690、synthetic 23、机制场景 19。当时无可核验文章原文的条目为 128 个（126 未验证、2 synthetic）。历史采集 HTTP403 和访问拒绝记录保留；离线内容修复不代表在线访问已通过验收。

完整验证：unit **2365 passed**；integration **127 passed、4 skipped**；golden **2533 passed、1 skipped**。子测试分别为 373、1450、34168 个通过，跳过均为既有条件。详情、首轮失败修正及既有静态检查限制见 [修复验证记录](../../docs/fixture-records/problem-fixes-2026-09-17.md)。

## 原始问题与复审记录（修复前历史）

以下保留修复前的证据、输出链接、统计和失败记录。“待修复”“当前”等表述属于当时状态，以以上修复清单和本轮验证为准。commentary 原记录的“22 条”是节点数，已更正为 21 条非空书目与 1 个空节点；历史原文及采集 hash 不改写。

### P15：移除不受支持的 SAGE 样本与测试登记

项目没有 SAGE provider。现有 [manifest 条目](../../tests/fixtures/golden_criteria/manifest.json) 将 `10.1345/aph.1M379` 标为 `skipped_unsupported_provider`；[多语言摘要测试](../../tests/golden/test_regression_samples.py) 通过共享 HTML helper 消费合成的 `bilingual.html`，并不证明 SAGE 抓取支持。此前使用通用 HTTP/Camoufox 采集该页面，也不构成 provider 支持。

移除范围与验收要求：

- 移除 `tests/fixtures/golden_criteria/10.1345_aph.1M379/` 的活跃样本及 manifest 登记，清理针对该样本的测试、case spec 和 `tests/test-evidence.json` 条目；不新增 SAGE adapter 或抓取路由。
- 检查来源更正、hash 校验和 fixture catalog 对该路径的引用，清理活跃依赖；历史误标及失败采集记录保留历史语义，不能再计入当前支持范围或补采待办。
- 复用已有 Springer、Wiley、Elsevier 等真实 fixture 保留共享多语言摘要覆盖，按原文验收，不保留人工构造的 SAGE 内容作为真实证据。移除后来源校验、测试证据登记及相关 golden 测试不应有悬空引用，并重算当前样本统计；已有真实内容缺陷仍需保留失败断言。

### P12：来源更正与真实替换

此前确认的 9 个误标文件全部撤销真实原文声明；其中 8 项已有真实 HTML/XML 替代，SAGE 仍是合成输入，按 P15 待移除。额外 1 个来源存疑的 Nature 新闻输入也已换成真实响应，旧文件继续标为 `unverified`。旧合成/存疑字节及 hash 均保留；目录名、DOI、测试通过与文件 hash 单独均不是网络来源证明。

| 原输入 | 本轮结果 | 实际覆盖与剩余限制 |
| --- | --- | --- |
| Springer `s13158-025-00473-x/bilingual.html` | 换入完整真实 HTML | 原来的标题、期刊和正文是人工构造；真实论文为 Japanese–Chinese bilingual children，含 Abstract、Résumé、Resumen。相关断言已按原文更新。 |
| Elsevier `S1575-1813(18)30261-4/bilingual.xml` | 用真实 PII 解析出的 `10.1016/j.edumed.2018.09.002` XML 替代内容测试 | 原无效 DOI 保留为 synthetic，真实论文另建条目；不能把 API 返回的另一 DOI 冒充原 DOI。真实双语输入暴露 P13。 |
| Nature `d41586-022-01795-9/original.html` | 换入真实响应 | 原注入哨兵的文件保存为 `legacy-original.html`，标 synthetic。 |
| Nature `d41586-023-01829-w/original.html` | 换入真实响应 | 旧简化输入保存为 `legacy-original.html`，仍为来源未验证，不武断判为 synthetic。 |
| Nature `s41561-022-00983-6/original.html` | 换入真实完整 Research Briefing | 本地项目链路取得完整正文；保留 6 个正文节、3 条原始书目，无摘要。仅此篇结构基线和 canonical 审阅记录随源文件变更。公开网页预览与本地实际访问结果分开记录。 |
| Wiley `cas.16117/extracted.md` | 新增真实 `original.html` | 旧人工释义 Markdown 仍为 synthetic；新 DOM 的实际 HTTP 状态是 403，完整正文及身份独立核验，未伪造为 200。 |
| Wiley `gcb.16386/bilingual.html` | 换入真实完整 DOM | 保留 Abstract、Resumo 与实际正文标题，旧文件标 synthetic。 |
| PNAS `2317456120/commentary.html` | **已换入真实 commentary DOM**，99,248 bytes | 同篇 DOI、约 1.2 万字符无小节标题正文及 22 条书目独立核验。实际 HTTP403 和运行时拒绝保留；旧 synthetic 另存 `legacy-commentary.html`，真实 PDF 也保留。新输入暴露 22 条书目全部丢失。 |
| PNAS `2406303121/abstract.html` | **已换入真实独立摘要页 DOM**，127,111 bytes | `/doi/abs/` 的同篇 DOI、1,637 字符摘要与空正文独立核验，离线仍正确判定 `abstract_only`。实际 HTTP403 保留；旧 synthetic 另存 `legacy-abstract.html`，已取得的完整正文独立保留。 |
| SAGE `aph.1M379/bilingual.html` | **待移除，见 P15** | 项目不支持 SAGE provider，此输入只用于共享提取器的合成机制测试。此前 DNS 校验失败、Camoufox `NS_ERROR_NET_RESET` 仅为历史采集结果，不再以此要求补齐 SAGE 真页面。 |

证据：[逐文件更正与未完成项](../../docs/fixture-records/source-origin-corrections-2026-09-17.json)、[完整来源分类](../../docs/fixture-records/source-origin-audit-2026-09-17.json)。每个新响应在对应 DOI 的 `acquisition/provenance.json` 中保存 URL、时间、采集方式、实际状态、字节数与 SHA-256；PDF 未观察到的最终 HTTP 状态/URL 保持未知。

续采纠正了上次采集脚本同时启用通用正文等待和必需 selector 的参数组合：两种 readiness 分支互斥，不能据此把已有 DOM 判为未到达。改用已有 selector 等待后，两页节点都就绪，但 HTTP403 仍使运行时拒绝；本轮仅在项目诊断边界记录已收到的原始 DOM，没有放宽访问判定或把脱敏诊断页冒充原文。见 [续采记录](../../docs/fixture-records/fixture-page-continuation-2026-09-17.json)。

来源回归现在拒绝将已知 synthetic／unverified 的同一字节重新标为 real，包括改名后的文件；拒绝用另一 DOI 的采集 hash 补证。`unverified` 已加入 manifest schema。成功测试不再被解释为来源认证。

### 本轮审计范围

- manifest 256 项（新增 1 个真实 Elsevier DOI）：203 个 golden-family 条目、53 个其他条目；全部登记资产共 2171 个，逐资产分类为 1149 个可绑定真实捕获的实体、288 个来源未验证文件、691 个派生/辅助文件、24 个 synthetic、19 个机制场景。**1149 不是论文数，包含图片、门禁响应等。**
- 203 个 golden-family 条目逐项登记：46 份 HTML/XML Markdown 导出（42 fulltext、3 abstract-only、1 metadata-only）；10 份 PDF 文件/身份核验；15 个真实捕获的受限/门禁输入；3 个 arXiv 索引输入；129 个没有可核验文章原文的条目（126 来源未验证、3 synthetic）。无 provenance 不自动判为 synthetic，也不默认认证真实。
- 46 份 Markdown 均重新检查输出、源 hash、完整预算、公式占位、图片 URL 和文内锚点；对报告中的缺陷逐项回查原始 DOM/XML。没有声称对全部论文逐字或完整公式 AST 审阅。PDF 只核验实际文件、可读取页和身份信号；没有评分、清洗或修复转换排版。PDF 内嵌 DOI、开头 DOI、标题比较分别记录，缺失信号保持缺失。
- 17 个已有图片文件复制到导出相对路径，Markdown 字节不变；此导出包装处理不算 provider 修复。远程图片是否当前可访问未由离线检查证明。

证据：[逐项复审记录](../../docs/fixture-records/real-source-review-2026-09-17.json)、[正文与扫描索引](../../.paper-fetch-runs/provenance-repair-2026-09-17/audit/index.json)、[新采集输入专项复审](../../.paper-fetch-runs/provenance-repair-2026-09-17/audit/replacements.json)、[扫描候选](../../.paper-fetch-runs/provenance-repair-2026-09-17/audit/scan.json)。旧版“173 个真实候选 / 34 篇问题”不沿用；[上一轮报告快照](../../.paper-fetch-runs/provenance-repair-2026-09-17/problems-before-reacquisition.md)仅保留历史线索。

### 基于真实来源确认的内容问题

以下 **6 类问题共涉及 12 篇**，均待修复；SAGE 的范围清理单独计为 P15，不计入真实内容缺陷。仅更新 fixture、断言和审计记录，没有为使测试变绿而修改生产提取器或放宽缺失内容断言。各项验收应同时核对原文与输出，书目需核对逐条内容和顺序，摘要需核对段落，不能仅以数量或测试变绿证明修复。

| 问题 | 原文证据与实际输出 | 后续局部修复方向 |
| --- | --- | --- |
| **P01：Science/PNAS 新模板书目全失** | Science `10.1126/science.abo2812` 的 `#bibliography .biblioentry` 有 **100** 条；PNAS `10.1073/pnas.2406303121` 有 **78** 条，续采 commentary `10.1073/pnas.2317456120` 有 **22** 条。三者输出均为 0；两篇 PNAS 的真实回归明确失败。 | 在相关 provider 的正式 bibliography 路径识别 `.biblioentry`，逐条保留正文、编号、DOI 和次序。原独立核查的 `role=listitem` 选择器也漏掉新模板，不能再用 0 对 0 通过。 |
| **P13（新增）：Elsevier 英语平行摘要遗漏** | 真实 `10.1016/j.edumed.2018.09.002` XML 含 2 个 abstract；`xml:lang=en` 中的 **4 个正文段落**均未进入摘要输出，西班牙语摘要保留。真实回归失败；段落比较忽略 Markdown 强调标记，避免把斜体差异误报为丢失。 | 局部检查 Elsevier XML 的多 abstract 遍历及语言/结构化小节组装，按原文逐段验收；不根据输出生成预期。 |
| **P14（新增）：MDPI 多出公式缺失占位且诊断漏报** | `10.3390/s23010001` 的真实 browser DOM 输出在两个已保留的 `$CO_{2}$` 后又追加 `[Formula unavailable]`，共 **2** 处；`formula_missing_count=0`。源 DOM 的 MathJax Preview 与 MathML 非空。 | 检查 MDPI 对同一公式的 Preview/MathJax/script 节点识别，避免把界面重复表示当成第二个空公式；同时核对诊断计数。不得猜写公式或以 PDF 修复替代。 |
| **P03：根相对图片地址** | Wiley `10.1029/2004GB002273` 1 处；AMS `10.1175/jtech-d-24-0028.1` 2 处、`10.1175/jamc-d-24-0048.1` 5 处，共 **8** 处保留 `/cms/asset/` 或 `/view/`。 | 在各 provider 形成资产地址时使用同篇 source URL 解析；保留远程/本地和 preview 的真实状态。 |
| **P04：协议相对图片地址** | Springer/Nature `s42003-021-02908-2` 的 Box 图片，及本轮两篇真实 Nature 新闻 `d41586-022-01795-9`、`d41586-023-01829-w`，各 **1** 处 `//media...`。 | 在 Springer/Nature 的原始资产 URL 归一化处补足 HTTPS 上下文，不在最终 Markdown 全局替换。 |
| **P06：正文锚点失去目标** | Royal Society `10.1098/rsif.2019.0334` 保留 **6** 个 `#s2` / `#s3` 链接，导出没有对应 ID。 | provider 局部输出稳定锚点或同篇绝对链接，保留来源目标，不猜测阅读器自动标题 slug。 |

上述源路径、输出文件及 hash 见逐项复审记录。Annual Reviews `annurev-neuro-062111-150343` 的 Footnotes 标题层级仅记录为现象，不算内容缺失。此前 P02 的 PLOS/Wiley 公式、P05 本地资产、P07 元数据、P08 重复图、P10 Ethics 等历史问题未在本轮有依据的原文集合中全部重证，**不宣称已修复或已排除**。

#### 真实 fixture 与问题输出索引

以下链接对应本轮实际回放文件；源字节、同 DOI 采集记录和导出 hash 已逐项核对。

| 问题 | DOI | 原始 fixture | 本轮输出 |
| --- | --- | --- | --- |
| P01 | `10.1126/science.abo2812` | [原文](../../tests/fixtures/golden_criteria/10.1126_science.abo2812/acquisition/template-browser-repeat4-2026-09-16/003-1-http_response_entity.html) | [Markdown](../../.paper-fetch-runs/provenance-repair-2026-09-17/audit/papers/science/10.1126_science.abo2812.md) |
| P01 | `10.1073/pnas.2406303121` | [原文](../../tests/fixtures/golden_criteria/10.1073_pnas.2406303121/acquisition/provenance-camoufox-retry-2026-09-17/000-browser_rendered_dom.html) | [Markdown](../../.paper-fetch-runs/provenance-repair-2026-09-17/audit/replacements/10.1073_pnas.2406303121.md) |
| P01 | `10.1073/pnas.2317456120` | [原文](../../tests/fixtures/golden_criteria/10.1073_pnas.2317456120/commentary.html) | [Markdown](../../.paper-fetch-runs/provenance-repair-2026-09-17/audit/continued/10.1073_pnas.2317456120.md) |
| P13 | `10.1016/j.edumed.2018.09.002` | [原文](../../tests/fixtures/golden_criteria/10.1016_j.edumed.2018.09.002/original.xml) | [Markdown](../../.paper-fetch-runs/provenance-repair-2026-09-17/audit/replacements/10.1016_j.edumed.2018.09.002.md) |
| P14 | `10.3390/s23010001` | [原文](../../tests/fixtures/golden_criteria/10.3390_s23010001/acquisition/assets-2026-09-15/mdpi-headless-002-browser_dom.html) | [Markdown](../../.paper-fetch-runs/provenance-repair-2026-09-17/audit/papers/mdpi/10.3390_s23010001.md) |
| P03 | `10.1029/2004GB002273` | [原文](../../tests/fixtures/golden_criteria/10.1029_2004gb002273/acquisition/known-gaps-2026-09-16/000-browser_rendered_dom.html) | [Markdown](../../.paper-fetch-runs/provenance-repair-2026-09-17/audit/papers/wiley/10.1029_2004gb002273.md) |
| P03 | `10.1175/jtech-d-24-0028.1` | [原文](../../tests/fixtures/golden_criteria/10.1175_jtech-d-24-0028.1/acquisition/subscription-2026-09-15/response-002.bin) | [Markdown](../../.paper-fetch-runs/provenance-repair-2026-09-17/audit/papers/ams/10.1175_jtech-d-24-0028.1.md) |
| P03 | `10.1175/jamc-d-24-0048.1` | [原文](../../tests/fixtures/golden_criteria/10.1175_jamc-d-24-0048.1/acquisition/assets-2026-09-15/ams-headless-body-001-browser_dom.html) | [Markdown](../../.paper-fetch-runs/provenance-repair-2026-09-17/audit/papers/ams/10.1175_jamc-d-24-0048.1.md) |
| P04 | `10.1038/s42003-021-02908-2` | [原文](../../tests/fixtures/golden_criteria/10.1038_s42003-021-02908-2/acquisition/template-gaps-2026-09-16/article-response.html) | [Markdown](../../.paper-fetch-runs/provenance-repair-2026-09-17/audit/papers/springer/10.1038_s42003-021-02908-2.md) |
| P04 | `10.1038/d41586-022-01795-9` | [原文](../../tests/fixtures/golden_criteria/10.1038_d41586-022-01795-9/original.html) | [Markdown](../../.paper-fetch-runs/provenance-repair-2026-09-17/audit/replacements/10.1038_d41586-022-01795-9.md) |
| P04 | `10.1038/d41586-023-01829-w` | [原文](../../tests/fixtures/golden_criteria/10.1038_d41586-023-01829-w/original.html) | [Markdown](../../.paper-fetch-runs/provenance-repair-2026-09-17/audit/replacements/10.1038_d41586-023-01829-w.md) |
| P06 | `10.1098/rsif.2019.0334` | [原文](../../tests/fixtures/golden_criteria/10.1098_rsif.2019.0334/acquisition/article-response-2026-09-15.bin) | [Markdown](../../.paper-fetch-runs/provenance-repair-2026-09-17/audit/papers/royalsocietypublishing/10.1098_rsif.2019.0334.md) |

### 验证

以下完整测试为首次复审结果；续采后采用相关 fixture、来源契约和内容回放专项验证，未重复运行无关完整测试。

- 完整 unit：2353 passed、366 subtests passed。
- 完整 integration：127 passed、4 项既有条件跳过、1446 subtests passed。
- 完整 golden：**2521 passed、2 failed、1 项既有条件跳过、34168 subtests passed**。两项失败分别为 PNAS 的 78 条书目遗漏、Elsevier 的英语平行摘要遗漏。
- 最终专项复验（更正英文段落比较、来源与替换输入）：**80 passed、2 failed、1418 subtests passed**；仍只失败于上述两项真实缺陷。没有新增 skip/xfail。
- 续采专项：**85 passed、3 failed、1422 subtests passed**；新增失败是 PNAS commentary 的 22 条书目遗漏，其余两项与首次复审一致。单独的来源/模板回放验证为 67 passed、1416 subtests passed。相关两份 Python 文件 Ruff 与格式检查通过；来源与导出 hash 链接重新核验通过。
- 首次复审相关 9 个 Python 文件 Ruff 与格式检查通过；`git diff --check` 通过。真实上游 HTML/XML 的空白与换行原样保留，Git attributes 禁止对 fixture/capture bytes 自动转换换行，不对原文执行去空白。

日志目录：[本轮验证与采集](../../.paper-fetch-runs/provenance-repair-2026-09-17/)。全部测试使用项目默认 pytest 并行配置；未提交、发布或触发 GitHub CI。


## 2026-09-18：P17–P27 完整问题记录（追加）

本节补全上方摘要中的全部 11 项：9 项已确认问题、1 项排版候选、1 项内容保留范围候选。保留原编号和历史修复状态；候选不标为已确认缺陷，已排除的比较器误报不新增为修复待办。

证据来自 [逐篇审阅报告](../../docs/fixture-records/markdown-quality-review-2026-09-18.md) 和 [机器记录](../../docs/fixture-records/markdown-quality-review-2026-09-18.json)。下列链接使用本次实际原文与导出，完整 SHA-256 和比较细节保存在机器记录中。

### P17：T&F 公式 fallback 输出无效图片地址 //:0

状态：**已确认，待修复**；优先级：高；维度：`formula/image`。

同一篇 Markdown 有 92 个 ![Formula](//:0)。源 DOM 的 data-formula-source 含实际 GIF 地址，另一类节点含 MathJax 内容。不能把 //:0 当成可用公式图片。当前 formula_fallback_count=92、formula_missing_count=0，属于有降级提示但 fallback 本身不可读。

影响文章与复现证据：

- `10.1080/08839514.2024.2375110`：[真实原文](<../../tests/fixtures/golden_criteria/10.1080_08839514.2024.2375110/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/tandf/10.1080_08839514.2024.2375110.md#L64>)（第 64 行）。

`10.1080/08839514.2024.2375110` 的定位信息：

- `selector`：`img[src="//:0"][data-formula-source]`。
- `output_count`：`92`。
- `example_real_image`：`/cms/asset/e11d8608-4809-4334-ac83-f5049d8a3981/uaai_a_2375110_ilm0001.gif`。

### P18：arXiv object SVG 和内联 SVG 图形遗漏

状态：**已确认，待修复**；优先级：高；维度：`image`。

7 篇共遗漏 34 个源图形节点：6 篇的 29 个 object[data] SVG，以及 DDPM 的 5 个内联 svg.ltx_picture。图注/正文仍在，但图形没有出现在 Markdown，也没有等价图片引用。此前 img/graphic 检查未覆盖这两种表示。

证据边界：34 是图形节点数，包含子图，不能称为 34 个不同 Figure；未下载或验收 SVG 远程可用性。

影响文章与复现证据：

- `10.48550/arxiv.1406.2661v1`：[真实原文](<../../tests/fixtures/golden_criteria/10.48550_arxiv.1406.2661v1/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.1406.2661v1.md>)。
- `10.48550/arxiv.2006.11239v2`：[真实原文](<../../tests/fixtures/golden_criteria/10.48550_arxiv.2006.11239v2/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.2006.11239v2.md>)。
- `10.48550/arxiv.2605.06659v1`：[真实原文](<../../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06659v1/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.2605.06659v1.md>)。
- `10.48550/arxiv.2605.06663v1`：[真实原文](<../../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06663v1/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.2605.06663v1.md>)。
- `10.48550/arxiv.2605.06665v1`：[真实原文](<../../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06665v1/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.2605.06665v1.md>)。
- `10.48550/arxiv.2605.06666v1`：[真实原文](<../../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06666v1/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.2605.06666v1.md>)。
- `10.48550/arxiv.2605.06667v1`：[真实原文](<../../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06667v1/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.2605.06667v1.md>)。

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

### P19：PLOS inline-graphic 公式被替换为缺失占位

状态：**已确认，待修复**；优先级：高；维度：`formula`。

两篇分别出现 1 和 7 个 [Formula unavailable]，共 8 处。源 XML 的 inline-formula/inline-graphic 已给出 info:doi 图片身份。现有质量诊断诚实报告缺失，但实际输出未保留图片 fallback。

证据边界：只确认已捕获 XML 中有公式图片引用；不宣称公式图片像素已下载或 OCR 可恢复。

影响文章与复现证据：

- `10.1371/journal.pbio.0040298`：[真实原文](<../../tests/fixtures/golden_criteria/10.1371_journal.pbio.0040298/acquisition/source-completion-2026-09-18/001-http_response_entity.xml>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/plos/10.1371_journal.pbio.0040298.md#L99>)（第 99 行）。
- `10.1371/journal.pcbi.1003118`：[真实原文](<../../tests/fixtures/golden_criteria/10.1371_journal.pcbi.1003118/original.xml>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/plos/10.1371_journal.pcbi.1003118.md#L44>)（第 44 行）。

`10.1371/journal.pbio.0040298` 的定位信息：

- `source_selector`：`inline-formula > inline-graphic`。
- `placeholder_count`：`1`。

`10.1371/journal.pcbi.1003118` 的定位信息：

- `source_selector`：`inline-formula > inline-graphic`。
- `placeholder_count`：`7`。

### P20：OUP 行内公式丢失指数中的分数与右括号

状态：**已确认，待修复**；优先级：高；维度：`formula`。

源公式 (C,w^(t),Θ^(t+(k−1)/K)) 中，(k−1)/K 和右括号在 merror 内；输出退成 \left(C,w^{(t)},\Theta^{(t +} \right)，分数项消失，语义及括号不完整。源 merror 本身已标错误；本项记录转换后进一步丢失内容，不能把上游错误说成原文完整正确。

影响文章与复现证据：

- `10.1093/bioinformatics/btaa153`：[真实原文](<../../tests/fixtures/golden_criteria/10.1093_bioinformatics_btaa153/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/oxfordacademic/10.1093_bioinformatics_btaa153.md#L157>)（第 157 行）。

`10.1093/bioinformatics/btaa153` 的定位信息：

- `source_selector`：`math merror`。
- `lost_source`：`<merror><mfrac><mrow><mi>k</mi><mo>-</mo><mn>1</mn></mrow><mi>K</mi></mfrac><mo>)</mo></merror>`。

### P21：PNAS 公式 3 的缩进被转换为异常大间距

状态：**已确认，待修复**；优先级：中；维度：`formula/layout`。

源 MathML 的 mspace width="40pt" 被输出为 \mkern7200mu，等于 400 个数学 em，会造成极宽公式和横向溢出。各项变量仍保留；这是间距问题，不是八个下标内容丢失。

证据边界：本轮为源码/输出对照，未对每个阅读器做截图或字体尺寸验收。

影响文章与复现证据：

- `10.1073/pnas.2310157121`：[真实原文](<../../tests/fixtures/golden_criteria/10.1073_pnas.2310157121/acquisition/source-completion-2026-09-18/002-camoufox-selector-dom.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/pnas/10.1073_pnas.2310157121.md#L117>)（第 117 行）。

`10.1073/pnas.2310157121` 的定位信息：

- `source_selector`：`math#me3 mspace`。
- `source_width`：`40pt`。
- `output_spacing`：`\mkern7200mu`。

### P22：Copernicus 空文本引文节点的关联丢失

状态：**已确认，待修复**；优先级：高；维度：`citation/prose`。

正文 90 个 bibr xref 中有 83 个无显示文本，但包含可解析的 rid。输出丢掉这些引用位置；例如 “The potential evapotranspiration was derived using the method of.” 后面没有作者、编号或链接。参考文献列表存在不能替代正文引用关联。

证据边界：83 是源空文本引文节点数；没有把每一个节点误计成独立参考文献。

影响文章与复现证据：

- `10.5194/hess-28-1-2024`：[真实原文](<../../tests/fixtures/golden_criteria/10.5194_hess-28-1-2024/original.xml>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/copernicus/10.5194_hess-28-1-2024.md#L78>)（第 78 行）。

`10.5194/hess-28-1-2024` 的定位信息：

- `source_id`：`paren.45`。
- `reference_target`：`bib1.bibx20`。
- `empty_xrefs`：`83`。

### P23：GAN 论文标题混入致谢，摘要后残留空表

状态：**已确认，待修复**；优先级：中；维度：`layout`。

输出 YAML 标题和 H1 均混入两个 Thanks 致谢段；摘要后还有没有内容的单列表格。原文致谢属于 h1 下的 .ltx_pubnotes，不能当作标题。直接调用现有生产 frontmatter helper 也能复现污染，不仅是身份审计元数据的问题。

影响文章与复现证据：

- `10.48550/arxiv.1406.2661v1`：[真实原文](<../../tests/fixtures/golden_criteria/10.48550_arxiv.1406.2661v1/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.1406.2661v1.md#L14>)（第 14 行）。

`10.48550/arxiv.1406.2661v1` 的定位信息：

- `source_selector`：`h1.ltx_title_document .ltx_pubnotes`。
- `empty_table_line`：`20`。

### P24：DDPM 尾部重复追加两张相对路径图片

状态：**已确认，待修复**；优先级：中；维度：`image/layout`。

Figure 1 与 Figure 6 已用绝对 URL 原位输出，却在尾部 Figures 又作为 Figure 13/14 追加，并留下 2006.11239v2/images/... 相对地址。导出目录不存在这两个文件；前文同图的正确远程 URL 仍在。

影响文章与复现证据：

- `10.48550/arxiv.2006.11239v2`：[真实原文](<../../tests/fixtures/golden_criteria/10.48550_arxiv.2006.11239v2/acquisition/source-completion-2026-09-18/001-http_response_entity.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/arxiv/10.48550_arxiv.2006.11239v2.md#L398>)（第 398 行）。

`10.48550/arxiv.2006.11239v2` 的定位信息：

- `also_line`：`402`。
- `original_lines`：`[20, 227]`。

### P25：Science 表格退为字段列表且表格退化计数为零

状态：**已确认，待修复**；优先级：中；维度：`table`。

原文第三张表的 Variable / Representation in the cellular space / Source 三列，在 Markdown 变成逐项字段列表，含 <br>。所核对的字段内容仍在，未确认数值丢失；列对齐已丢失，而 table_fallback_count、table_layout_degraded_count 均为 0。

证据边界：记录展示退化及诊断缺口，不将内容保留的列表降级误报为语义损失。

影响文章与复现证据：

- `10.1126/sciadv.abj3309`：[真实原文](<../../tests/fixtures/golden_criteria/10.1126_sciadv.abj3309/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/science/10.1126_sciadv.abj3309.md#L160>)（第 160 行）。

`10.1126/sciadv.abj3309` 的定位信息：

- `source_table_index`：`3`。
- `source_first_row`：`["Degradation", "Percentage of the cell degraded at year t", "DEGRAD and DETER (16, 17)"]`。
- `quality_counters`：`{"table_fallback_count": 0, "table_layout_degraded_count": 0, "table_semantic_loss_count": 0, "formula_fallback_count": 0, "formula_missing_count": 0}`。

### P26：Annual Reviews 表题和词汇节出现标题层级跳跃

状态：**排版候选，待裁定**；优先级：低；维度：`layout`。

5 篇共 9 处候选：表题常从 H3 直接到 H5，Terms And Definitions / Footnotes 常直接用 H4。内容并未因此丢失，属于阅读层级的排版改进候选，需在保留原文层级和统一表题规则之间裁定。

影响文章与复现证据：

- `10.1146/annurev-control-030123-013355`：[真实原文](<../../tests/fixtures/golden_criteria/10.1146_annurev-control-030123-013355/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/annualreviews/10.1146_annurev-control-030123-013355.md>)。
- `10.1146/annurev-control-090419-075625`：[真实原文](<../../tests/fixtures/golden_criteria/10.1146_annurev-control-090419-075625/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/annualreviews/10.1146_annurev-control-090419-075625.md>)。
- `10.1146/annurev-environ-102511-084654`：[真实原文](<../../tests/fixtures/golden_criteria/10.1146_annurev-environ-102511-084654/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/annualreviews/10.1146_annurev-environ-102511-084654.md>)。
- `10.1146/annurev-med-120811-171056`：[真实原文](<../../tests/fixtures/golden_criteria/10.1146_annurev-med-120811-171056/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/annualreviews/10.1146_annurev-med-120811-171056.md>)。
- `10.1146/annurev-neuro-062111-150343`：[真实原文](<../../tests/fixtures/golden_criteria/10.1146_annurev-neuro-062111-150343/acquisition/assets-2026-09-15/annualreviews-headed-all-001-browser_dom.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/annualreviews/10.1146_annurev-neuro-062111-150343.md>)。

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

### P27：Springer Methods 内的 Ethics compliance 段落被排除

状态：**内容保留范围候选，待裁定**；优先级：中；维度：`prose`。

源文 Methods 下包含 Ethics compliance 小节，说明 46 年数据采集的动物伦理审批、许可证及鸟类环志注册；当前 Markdown 整段不在。现有共享策略会排除 ethics 类内容，因此先登记为保留范围候选，不直接判为提取器回归，也不在本轮更改全局策略。

影响文章与复现证据：

- `10.1038/s41467-022-32108-3`：[真实原文](<../../tests/fixtures/golden_criteria/10.1038_s41467-022-32108-3/acquisition/template-gaps-2026-09-16/article-response.html>)；[当前 Markdown](<../../.paper-fetch-runs/markdown-review-2026-09-18/papers/springer/10.1038_s41467-022-32108-3.md>)。

`10.1038/s41467-022-32108-3` 的定位信息：

- `source_section`：`Sec6-content / Ethics compliance`。
- `source_excerpt`：`All research protocols over the 46 years of data collection were approved by animal ethics committees`。
- `policy_owner`：`src/paper_fetch/extraction/html/semantics.py BACK_MATTER_TOKENS`。

### 本轮问题记录的共同边界

- 154 项全文中，14 篇涉及已确认问题，另 6 篇涉及候选；各问题可能落在同一篇，不能将问题组数或图形节点数相加作为论文数。
- 其余输出未确认问题仅限已检查维度；不等于全部公式视觉、逐字内容、全部图像像素或远程图链已验收。4 项摘要/元数据、16 项 PDF 和 28 项无本轮全文输入的记录不计入全文质量通过。
- 17 个已有本地图片的导出路径问题已通过复制相同字节资产解决，没有改写 Markdown，不再列为 provider 丢图问题。IEEE 的独立书目侧文件未注入本次正文 builder，也不据此判定生产书目提取失败。
- 重复首行、数学等价表示和不适用的旧 DOM 选择器造成的比较器误报已单独复核。源文已有的重复定理、重复书目、表注与矩阵不作为擅自去重依据。
- PDF 转换质量继续排除，未进行清洗或修复。历史 HTTP403、访问拒绝和用户确认无权限状态不因离线回放改变。
- 本轮完整 golden 的历史结果为 2771 passed、1 skipped、34168 subtests passed。此次追加仅修改本文件，不重复运行内容回放或测试，不提交、不触发 GitHub CI。
