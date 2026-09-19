> **2026-09-19 最新链路复核：** 基于上述重采结果确认 5 项当前问题，涉及 8 篇；包括 arXiv 错图绑定、远程正文图漏计、重复插图、算法位置丢失，以及 Springer 回退原因传递丢失。277/277 仅表示已登记资产本地化，不能证明整篇正文图片正确归档。当前问题以 [problems.md](../problems.md) 为准，方法和边界见[复核记录](fixture-records/chain-review-2026-09-19.md)；以下采集统计保留为历史事实。

> 历史覆盖审计；当前选择和预期由 fixture manifest、provenance 与 expected 管理。

> **2026-09-19 正式 CLI 重采：** 27/27 篇取得全文，16 complete、11 degraded；当前发现正文资产 277/277 本地化。372 个实际文件已追加入库，来源与关联 golden 验证通过。用户已确认 T&F 当前结构化公式没有问题，本轮采集待补项为 0；旧 232 个 GIF 不再列为本轮待办，未下载事实保留；其余原始载荷与降级边界见[最新采集记录](fixture-records/official-reacquisition-2026-09-19.md)。以下按日期保留历史事实，不以旧计数代表当前状态。

> **2026-09-17 修复状态：** P15、P01、P13、P14、P03、P04、P06 已按顺序完成，详见[修复验证记录](fixture-records/problem-fixes-2026-09-17.md)。PNAS commentary 原有 22 个书目节点，其中 21 条非空，第 22 条源正文为空；未编造该条内容。下文来源审计与问题描述保留修复前历史语义，原始采集状态和 hash 不改写。

> **2026-09-17 来源更正与续采（优先于下文历史统计）：** P12 的 9 个误标文件已撤销真实来源声明，8 项已有真实 HTML/XML 替代；另 1 项存疑输入已重采。PNAS commentary 与独立摘要页现已取得真实 DOM，实际 HTTP403 和运行时拒绝记录保留；SAGE 已按 P15 移出活跃 fixture 和测试登记，仅保留[历史记录](fixture-records/retired/10.1345_aph.1M379/README.md)，不属于补采待办。共享多语言摘要由 Springer、Wiley、Elsevier 的真实原文继续覆盖。当前 manifest 255 项（202 个 golden-family、53 个其他条目），2168 个登记资产：1149 个真实捕获实体、287 个来源未验证、690 个派生/辅助、23 个 synthetic、19 个机制场景。202 个 golden-family 中，46 份 HTML/XML 导出、10 份 PDF 身份核验、15 个受限/门禁输入、3 个索引输入、128 个缺少可核验文章原文的条目。修复前 commentary 确认书目遗漏（22 个节点中 21 条非空，第 22 项源正文为空）。canonical 的 151 项只表示可执行提取契约，不能作为已认证的真实论文总数。最新来源分类、46 份正文导出及模板边界见 [来源审计](fixture-records/source-origin-audit-2026-09-17.json)、[来源更正](fixture-records/source-origin-corrections-2026-09-17.json)、[续采记录](fixture-records/fixture-page-continuation-2026-09-17.json)、[真实来源复审](fixture-records/real-source-review-2026-09-17.json)。两篇 PNAS 书目与 Elsevier 英语摘要回归现已修复通过，未使用 skip/xfail。

# 真实案例与验收记录

更新日期：2026-09-16。范围为当前 19 个正式 provider（含 arXiv）。本文是案例证据与当前验收状态的统一入口；完整样本、文件路径及来源以 [manifest](../tests/fixtures/golden_criteria/manifest.json) 和各样本的 `acquisition/provenance.json` 为准。

最新 canonical 内容审阅见文末“151 项 canonical 原文内容审阅”及其逐项机器登记；下面的采集阶段记录保留历史范围。

## 当前收口结果

**此前约定的采集目标已按用户“以最新的为准，全部实现收口”的确认完成。此结论仅覆盖下表，不表示全仓测试证据缺口为零。** 当前验收以各目标最新且适用的实际证据为准；[机器记录](fixture-records/fixture-known-gaps-2026-09-16.json) 通过 `status=closed`、`remaining=[]` 和 `current_evidence` 列出具体依据。全仓测试证据的最新审阅与剩余范围见本文末尾“102 条模板缺口登记审阅”。

| 目标 | 当前采用的证据与收口结果 |
| --- | --- |
| Wiley Appendix A | 原文及最新 DOM 回放均保留完整段落、五个引文目标，顺序为 Conclusions → Appendix A → References，75 条引用不变。 |
| Wiley 公式 | 用户确认原始 384×17 GIF 可接受；保留 `preview` 标签，已关闭，无后续采集要求。 |
| T&F 8 张图 | 最新采集已取得原始 HTTP200 JPEG，解码像素与保留 PNG 一致，下载及最终文章链接回放通过。 |
| Science／PNAS PDF | 分别采用项目 fallback 的 HTTP200／12 页 PDF、官方 HTTP200／10 页 PDF，文件完整性和同篇身份通过。 |
| AIP／OUP 页面 | 采用最新真实 HTTP200 导航响应及独立同篇 DOM；旧 Cloudflare DOM 仅作历史回放。 |
| IEEE 两篇门禁 | 采用无订阅环境下的同篇 Sign In or Purchase 门禁；确认正文受限后停止后续请求，满足识别与停止契约。 |

正文图片的 **332 个逻辑目标均已完成本轮验收**：331 个原尺寸文件，另 1 个 Wiley 公式按用户确认接受原始 GIF；没有把该公式改标为 `full_size`。未采集到的门禁后 REST／PDF 拒绝响应不再列为必需样本，也不声称已经取得。

历史 PDF 的未知响应状态／最终 URL、旧挑战 DOM 的未知 HTTP 状态继续保持未知，移入历史说明，不追溯补造、不要求人工补日志。附件仍只验索引与链接；PDF 转换质量和 151 项 exact 的全面内容审阅均不在本轮范围内。

下文按日期保留采集过程记录，阶段性的“待补”“未知”及计数只描述当时情况，不自动构成当前采集待办；采集结论以本节和机器记录的 `current_evidence` 为准，测试证据缺口以文末审阅为准。既有文件、失败响应和未提交修改均保留；未提交、发布或触发 GitHub CI。

**收口验证：** 按默认并行配置完成全量 unit（2262 passed，366 subtests）、integration（102 passed，4 skipped，1358 subtests）和 golden（935 passed，1 skipped，177 subtests），无失败。来源／manifest 审计确认 9 项验收目标、21 个证据路径有效，4 类历史未知状态保持原值；77 个相关文件的敏感信息扫描、本轮修改 Python 文件的 Ruff 检查及 `git diff --check` 均通过。

## 当前验收：识别、停止、降级

确认同篇正文付费墙后，验收要求是停止浏览器候选及重试、REST／TDM／PDF、资产与跨 provider 请求，仅以已收到的摘要／元数据降级并落盘。正常全文中的外围提示、隐藏模板、单个资产限制和无明确权限语义的 HTTP403 均有反例测试。详见 [终止回归](../tests/unit/test_confirmed_paywall_stop.py) 和 [CLI／MCP 落盘回放](../tests/integration/test_paywall_stop_replay.py)。不再要求付费墙之后取得全文或穷尽路线得到最终权限拒绝。

下文采集日期、原始请求序列、曾经成功的 PDF 和 CLI 终态均保留为历史事实，不代表当前应继续执行的流程。旧 PDF 引用／排版断言已改为转换器正文原样保存断言；当前待补项不包括 PDF 转换质量。2026-09-15 的停止语义修订只做离线回放；2026-09-16 的真实补采另列如下，旧响应未被替换。

## 真实下载范围

按用户最新澄清，**真实下载验收仅限正文和正文图片（含公式、表格图片）**。补充材料只要求原文／官方索引、同篇身份和链接覆盖，不要求全量真实下载，也不以文件下载失败或缺少可读性验证判定本轮未完成。已按用户要求删除已有附件文件及其重复响应、截断文件和附件内容派生件；仅保留索引、链接、失败页面和采集元数据。附件 PDF 不计正文。

删除范围与逐文件哈希见[清理记录](fixture-records/supplementary-removal-2026-09-15.json)。manifest 和活动 provenance 仅登记当前存在的文件；已删除文件的来源信息移入 `removed_records`。源码包中的 22 个非附件成员已独立保留，正文 PDF、图片和 Elsevier 作者稿继续保留。

**删除后验证：** 默认并行全量 unit 为 3038 passed、2 skipped；全量 integration 为 24 passed、4 skipped。最终来源审计为 4 passed（1182 subtests），资产专项为 83 passed、1 skipped；跳过项对应无合格正文图片的 Wiley 目标。Ruff 和 `git diff --check` 通过。

## 2026-09-16 初轮补齐结果（Wiley 浏览器追加结果见下节）

本轮机器记录见 [fixture-regression-2026-09-16.json](fixture-records/fixture-regression-2026-09-16.json)。新增采集保存到各 DOI 的 `acquisition/regression-2026-09-16/`，原采集、失败响应与历史 CLI 判定均保留。

- **固定订阅预期。** [场景表](../tests/support/subscription_scenarios.py) 独立规定 DOI＋响应的门禁预期；已去掉根据当前检测函数选择测试分支的做法。IOP 三篇订阅响应、ACS、AIP、Royal Society、AMS JAS 购买页、OUP HTTP200／DOM 和 Science／PNAS 新模板均验证身份、已收到摘要／元数据、无全文、`limited` 及后续请求停止。IOP 历史挑战与同 DOI 后续订阅响应分开保留；AMS JPO 及同一 JAS DOI 后续响应的可见主文、Wiley 普通摘要页、隐藏模板、外围购买提示、其他论文门禁、单图 403 和普通 403 不等同于正文门禁。
- **局部修复。** IOP 的出版社介绍、版权和作者单位不再抵消正文门禁；Science／PNAS 的 `bodymatter` 门禁面板和 DOI 元数据优先级得到覆盖，`div[role=paragraph]` 正文仍能否决外围购买提示；AMS 的购买按钮与实际正文分别判断。没有更改全局阈值、重试策略、CLI／MCP 接口、依赖、版本或 CI。
- **42 个原图片缺口实际补齐 22 个。** IEEE `ACCESS.2024.3352924` 先收到 HTTP202，正常 headless readiness 随后得到 HTTP200 同篇 DOM；现有 provider 通过文章中的原图入口取得 22 个 `large.gif`（全部 `full_size`），与既有 1 张组成 **23/23**。实际 MIME、解码、尺寸、SHA-256、同篇链接和最终文章本地链接均已核验。
- **仍缺 20 个 Wiley 文件。** `gcb.16414`（6 个）与 `2004gb002273`（14 个）的新官方入口均返回 HTTP403／`cf-mitigated: challenge`。每篇本轮请求一次即停止，没有切换浏览器或下载缩略图冲销原图缺口。T&F 的 8 个旧缺口继续留待后续。
- **Frontiers 第二种真实模板完成。** `10.3389/fpls.2020.01216` 已取得真实 NLM 2.3 XML、官方路由发现页面及全部 **5 张正文 WebP**。官方页面的内部 article ID 是 **569407**，不是 DOI 尾号 **01216**；现有下载路径从同篇页面选择正确 URL。新增回放核对 56 条引用、3 个表格的完整数据行、8 个展示公式的结构和指定完整公式，以及正文顺序。构造 XML／1×1 图仍只用于机制测试。
- **新增 10 项 exact。** 新 Frontiers 加上原有五篇 arXiv `2605.06556v1`、`2605.06598v1`、`2605.06659v1`、`2605.06665v1`、`2605.06666v1`，以及 Nature `nature13376`、Wiley `2004gb002273`、OUP `beheco/arag047` 和 `molehr/gaaf013`。复用原文增加结构基线、人工内容锚点和适用的引用／数据表／公式断言；exact 不以派生 `extracted.md` 为必备来源证据。OUP 两页唯一的表格是隐藏的月访问量统计，不算论文表格。Wiley 附录 A 位于致谢之后，当前抽取范围未保留，仍是内容覆盖缺口，不能用新增 exact 基线声称已恢复该附录。

初轮合计新增 **27 个合格正文图片文件**（IEEE 22＋Frontiers 5）。原正文资产集合加上新 Frontiers 后为 **304/332**，剩余 **28** 个（Wiley 20＋本轮不处理的 T&F 8）。新文件均经现有下载路径与最终文章链接回放；测试绿灯不冲销外部访问缺口。Science／PNAS 历史 PDF 的 HTTP 状态和最终 URL、AIP／OUP 历史挑战 DOM 状态仍为未知；本地复用只补当前字节审计，不补造原始 HTTP 证据。

**初轮最终验证：** 按 `pyproject.toml` 默认并行配置执行完整 unit（2252 passed，366 subtests）、integration（102 passed，4 skipped，1271 subtests）和 golden（916 passed，1 skipped，177 subtests）。来源／manifest 审计、修改文件的 Ruff 检查、macOS 静态契约校验及 `git diff --check` 均通过；静态校验不替代原生 macOS gate。未提交或发布。


## 2026-09-16 Wiley 浏览器追加结果

用户明确要求浏览器重试后，复用现有 headless Camoufox 会话、同篇官方页面与 provider 下载路径，实际取得原先缺失的 **20 个文件**：`gcb.16414` 为 **6 张 full_size 原图**；`2004gb002273` 为 **13 张 full_size 原图＋1 张 preview 公式 GIF**。所有新增图片响应均为真实 HTTP200，已核验解码、尺寸、SHA-256、同篇 URL 及最终文章本地链接。两篇新集合、DOM、失败和成功响应分别保存在 `acquisition/browser-retry-2026-09-16/`，旧采集不变。

公式 `gbc1137-math-0001.gif` 为 384×17，是官方 DOM 唯一提供的公式图片；沿用现有 provider 的 `preview` 标记，**单独记录，不冲销原尺寸缺口**。因此原 42 个缺口累计补齐 **41 个原尺寸文件，另取得 1 个 preview 文件**；Wiley 追加完成时正文资产严格计数为 **323/332**，另有 **1 个已取得并回放的 preview**、**8 个 T&F 文件仍待后续**。Wiley 两篇已没有未取得字节的目标，但该公式没有可验证的原尺寸替代链接。

AGU 页面导航记录为 HTTP403，而浏览器最终 DOM 已含同篇正文；保留该状态及 DOM，不改写为 HTTP200。其 14 个新图片响应均另有实际 HTTP200 证据。这次没有修改生产代码、依赖或浏览器策略。

详见[追加机器记录](fixture-records/fixture-wiley-browser-2026-09-16.json)和[图片回放](../tests/golden/test_browser_retry_asset_collections.py)。默认并行专项回放 **2 passed**，来源／manifest／敏感信息审计 **5 passed、1251 subtests passed**；Ruff 与 `git diff --check` 通过。


## 2026-09-16 T&F Camoufox 追加结果

按用户要求重试一次，`10.1080/15481603.2026.2667034` 的官方页面返回 HTTP200；缺失的 **8 张图均恢复为 1500 像素宽的原尺寸 PNG**，复用已有 1 张后，正文图片集合为 **9/9**。这 8 张由现有 provider 从浏览器已加载的同篇原图 URL 导出，已验证 URL 一致、解码、尺寸、SHA-256 及最终文章链接。

**这次取得的是浏览器像素导出的 PNG，不是原始 JPEG 响应字节。** 新图片的 HTTP 状态保持未知；离线回放注入的 HTTP200 只用于测试，不写成真实响应。官方 DOM、导出文件和下载记录另存于 `acquisition/browser-retry-2026-09-16/`，旧 403 证据及旧集合保留。没有修改生产代码或浏览器策略。

至此原定 T&F 8 个延期图片目标已经处理。当前正文资产 **332 个目标均有可用文件**：**331 个满足原尺寸要求，另 1 个 Wiley 公式仅为 preview**，不冲销原尺寸要求。详见[追加机器记录](fixture-records/fixture-tandf-browser-2026-09-16.json)及[图集回放](../tests/golden/test_browser_retry_asset_collections.py)。

本次默认并行图集回放 **3 passed**，来源／manifest／敏感信息审计 **5 passed、1261 subtests passed**；修改测试的 Ruff 与 `git diff --check` 通过。

## 2026-09-16 已知缺口专项补齐

本轮仅处理已确认缺口，未扩展为 151 项 exact 的全面内容审阅。[机器记录](fixture-records/fixture-known-gaps-2026-09-16.json)列出每篇采集目录、尝试次数和人工核验问题；新增内容写入各 DOI 的 `acquisition/known-gaps*-2026-09-16/`，旧文件、旧响应及未知状态保留。

- **Wiley Appendix A 已恢复。** Wiley 自有 DOM 预处理仅将正式附录块移至后置内容边界之前，并让标题随正文内容进入扫描。完整长段落、五个引文目标及 75 条参考文献得到独立回归验证，最终顺序为 Conclusions → Appendix A → References，没有致谢混入或内容重复。原文、上一轮 DOM 和本轮 DOM 均通过回放；审阅后 exact 从 9 个 section 更新为 10 个。最小 unit 覆盖多个附录、无附录、隐藏块及侧栏同名标题。
- **T&F 原始 JPEG 字节缺口已关闭。** 导航前挂接响应采集，从现有 provider 识别的同篇弹窗原图链接取得 8 份实际 HTTP200 JPEG，记录最终 URL、MIME、尺寸与 SHA-256。全部宽 1500 像素；浏览器解码后的 RGBA 与保留的 8 份 PNG 完全一致（差异通道数均为 0），并通过下载及最终文章链接回放。原 PNG、其未知 HTTP 状态、旧 403 和测试注入标识继续保留。三次尝试分别为原文采集、采集脚本导入错误、修正导入路径后取得 JPEG；没有因脚本错误伪造请求证据。
- **PNAS 新 PDF 响应证据已补齐。** 官方入口先有挑战响应，正常浏览器导航随后取得 HTTP200 PDF，10 页完整、同 DOI、可读取且未修复。新文件及响应单独保留；历史 `original.pdf` 的 HTTP 状态和最终 URL仍未知，新响应不能倒填。Science 本轮最后仍为 HTTP403／Cloudflare 人工验证页，已停止，未取得新 PDF 字节。
- **AIP／OUP 当前响应与 DOM 已补齐。** 两篇均取得真实 HTTP200 导航响应和独立最终 DOM，核对为同篇正常文章。DOM 自身不附会 HTTP 状态；当前正常页面不算历史挑战证据，历史状态继续未知。
- **IEEE 权限拒绝覆盖仍缺。** 两个已知候选的当前页面显示机构访问状态，TBME 有正文；REST 本轮均是 HTTP200、0 字节，官方 PDF 则分别取得同篇 4 页／9 页 HTTP200 文件。空 REST 和可访问 PDF 都不能登记为权限拒绝。每篇三次有依据的观察后停止，未移除凭证或制造拒绝。
- **Wiley 公式已获用户确认，无需继续核验。** 保留原始事实与程序标签： 当前同篇官方 DOM 的公式节点只列出 `gbc1137-math-0001.gif`；与已取得的 384×17 GIF 对应，未发现可核验的高分辨率替代链接，没有猜路径、放大或从 PDF 导出。用户随后确认该公式没有问题，因此不再把它列为待补或人工核验项；此确认不改写尺寸或 `preview` 标签。正文图片目标仍为 **331 个原尺寸＋1 个 preview**；T&F 新 JPEG 补强原始响应证据，不重复增加逻辑资产数。

新 PDF 仅核验文件完整性和论文身份，没有检查或修改转换质量。没有更改公开 CLI／MCP、依赖、版本或 CI，也未提交、发布。

**本轮验证：** 默认并行完整 unit **2262 passed、366 subtests**，integration **102 passed、4 skipped、1335 subtests**，golden **931 passed、1 skipped、177 subtests**。全量 golden 启动后新增的公式证据在 **9 passed** 的证据专项中另行验证；图片／附录回放 **7 passed**，最终来源／manifest＋新证据审计 **13 passed、1301 subtests**。55 个新采集文件的敏感信息扫描、本轮 Python 文件 Ruff 与 `git diff --check` 均通过。

### 历史记录的替代依据（已收口）

| 目标 | 当前验收依据 | 历史边界 |
| --- | --- | --- |
| Science `sciadv.abf8021` | [项目 PDF fallback 集合](../tests/fixtures/golden_criteria/10.1126_sciadv.abf8021/acquisition/project-pdf-fallback-2026-09-16/collection.json)：HTTP200、完整 12 页同篇 PDF。 | 旧 PDF 成功响应未知，保留原值；无需追溯。 |
| PNAS `pnas.2406303121` | [新 PDF 集合](../tests/fixtures/golden_criteria/10.1073_pnas.2406303121/acquisition/known-gaps-2026-09-16/collection.json)：HTTP200、完整 10 页同篇 PDF。 | 旧 PDF 成功响应未知，保留原值；无需追溯。 |
| AIP `5.0129134` | [新页面集合](../tests/fixtures/golden_criteria/10.1063_5.0129134/acquisition/known-gaps-2026-09-16/collection.json)：正常文章 HTTP200 与同篇 DOM。 | 旧 DOM 已知为 Cloudflare 挑战，其 HTTP 状态未知；不再补日志。 |
| OUP `btaa823` | [新页面集合](../tests/fixtures/golden_criteria/10.1093_bioinformatics_btaa823/acquisition/known-gaps-2026-09-16/collection.json)：正常文章 HTTP200 与同篇 DOM。 | 旧 DOM 已知为 Cloudflare 挑战，其 HTTP 状态未知；不再补日志。 |
| IEEE 两篇 | [无订阅环境记录](fixture-records/fixture-no-subscription-2026-09-16.json)：真实同篇正文门禁与停止。 | 不要求门禁后的 REST／PDF 拒绝；先前成功 PDF 和空 REST 继续保留为历史。 |

## 2026-09-16 Science 项目 PDF fallback 追加结果

用户确认 Wiley 公式没有问题，已从待核验清单移除；保留 384×17 原文件及 `preview` 技术标签。按用户要求，Science `10.1126/sciadv.abf8021` 改用项目现有 `fetch_pdf_with_browser`，对已知官方 `/doi/pdf/` 入口调用一次；没有修改生产代码、浏览器策略或转换器。

该方法先遇到 HTTP403，随后经其现有 PDF 获取流程收到 **HTTP200、17,082,873 字节的完整 PDF**。项目成功返回的文件与捕获响应 SHA-256 完全一致，共 **12 页**、未加密、无需修复，标题一致，第 11／12 页明确印有目标 DOI。项目原有身份验收以标题匹配通过；额外页内 DOI 核验只记录身份，不扩展为转换质量审阅。

新 PDF、原始失败／成功响应及 [collection](../tests/fixtures/golden_criteria/10.1126_sciadv.abf8021/acquisition/project-pdf-fallback-2026-09-16/collection.json) 独立保留，已补 provenance 和 manifest；旧文件和历史未知状态不变。当前 Science PDF 获取与新响应证据缺口已关闭，上一节 Cloudflare 结论仅描述此前导航采集。回归见 [test_science_project_pdf_fallback.py](../tests/golden/test_science_project_pdf_fallback.py)。

**追加验证：** 默认并行 PDF 获取回归＋来源／manifest 审计 **5 passed、1305 subtests**；7 个采集文件敏感信息扫描、新测试 Ruff 与 `git diff --check` 通过。

## 2026-09-16 无订阅环境核验

用户切换网络后，保留现有浏览器状态和凭证，对 IEEE 两个既有候选各进行一次官方文章页观察。两篇均取得实际 HTTP200 导航响应及最终 DOM：**没有机构访问横幅，出现同篇 “Sign In or Purchase”，没有 `#article` 全文容器**。现有检测器均识别为正文门禁，已停止后续主动请求。新采集与先前机构可访问页面、成功 PDF 分别保留，不能相互覆盖。[机器记录](fixture-records/fixture-no-subscription-2026-09-16.json)和[新回归](../tests/golden/test_ieee_no_subscription_evidence.py)登记具体边界。

此次补入了 **2 份当前真实正文门禁证据**，但 **REST 全文／PDF 权限拒绝仍未取得**：文章页自动请求的 `/toc`、`/similar` 以及 TBME `/snippet` 均是 HTTP200；这些不是全文 REST 或 PDF 拒绝。确认正文门禁后，不再主动调度 REST 全文、PDF、引用或资产请求，因此不为填充负样本继续穿过已知门禁。

切换网络也无法恢复 Science／PNAS 旧 PDF 的响应状态和最终 URL，或 AIP／OUP 旧挑战 DOM 的响应状态；此类历史缺口仍只能依赖当时日志。新响应可以补充当前证据，不能倒填历史。当前正文／图片文件的已完成结论不变。

**验证：** 默认并行新门禁回放＋来源／manifest 审计 **6 passed、1314 subtests**；11 个新采集文件敏感信息扫描、新测试 Ruff 和 `git diff --check` 均通过。没有修改生产代码、依赖、版本或 CI，未提交或发布。

## PDF 范围约束

**所有 PDF 解析与转换质量问题均不纳入待补、修复或验收目标。禁止在现有 `pymupdf4llm` 输出之上做任何格式清洗或内容修复**，适用于 shared、provider、文章组装和最终渲染各层。包括标题层级、页眉页脚、断行、跨栏顺序、引用分条／编号／去重／重排、公式、OCR、表格及导出占位图等；不得通过换层、DOI 特判或新增后处理器绕过。完整规则见 [PDF 转换边界](extraction-rules.md#rule-pdf-conversion-boundary)。

PDF 获取与合法访问、真实文件及完整论文身份校验、回退／降级、原始文件和转换器导出资产落盘、来源记录仍在范围内。表内已有 PDF 引用数量和解析测试只记录历史事实，不作为继续清洗、补齐质量或保真验收的依据。

## 当前总量

| 项目 | 已有 |
| --- | --- |
| manifest 登记 | 246 项：193 golden、33 block、20 scenario |
| 可执行真实 exact 回放 | 151 项；辅助输入、规则场景和合成样本不计入 |
| 完整论文 `original.pdf` | 26 份，覆盖全部 19 家；附件 PDF、受限首页不计入 |
| 补充材料保留范围 | 原文／官方索引、同篇身份、远程链接及历史采集元数据；附件真实字节已删除 |
| 图片、公式、表格专项 | 19 家 × 3 类均有真实原文的具体断言；不代表全部像素、公式或单元格保真 |
| 正文拒绝样本（block） | 33 份，覆盖 12 家；含付费墙、摘要页、挑战／拒绝页和空正文 XML |
| 其中 `abstract_only` | 24 份，分布于 Springer、Wiley、Science、PNAS、Annual Reviews、IOP、Oxford Academic、Taylor & Francis、Copernicus；这是正文抽取结果分类，不等于 24 份均已单独证明订阅限制 |

“已有”只适用于列出的论文和路线。文件已取得、当前代码离线回放通过、标准 CLI 实际成功分别记录；模拟 PDF 失败不能当作实际无访问权限。历史未覆盖的路线不表示对应出版社所有论文都有问题，也不自动构成本轮待办。

## 历史：2026-09-15 非 OA／订阅候选采集

2026-09-15 在用户报告的无订阅网络下，保留现有 API key／TDM token 和浏览器状态，完成 **14 家、36 篇标准 CLI 实际采集**：CLI 报告 8 `complete`、16 `degraded`、12 `limited`。**这些是程序输出，不能直接等同于全文证据：后续文件身份核验发现 AIP 1 篇误收其他文档、AMS 1 篇误收预览、Nature 1 篇误收补充材料，撤回这 3 项全文恢复成功结论。**其余 5 家当前 OA 目标不设付费墙配额，19 家均在采集记录中列明处理范围。原始响应、DOM、下载文件、CLI manifest 和逐项证据分类见 [本轮机器记录](fixture-records/fixture-acquisition-2026-09-15-subscriptions.json)。新增 23 项辅助 golden 和 2 项 IOP block；辅助 golden 不计 exact 全文回放数。

| 出版社 | 尝试数 | 本轮事实及仍缺证据 |
| --- | --- | --- |
| ACS | 2 | JACS 1990 `ja00160a040`、2026 `jacs.6c10062` 均有明确无访问权限页面，实际 PDF 回退成功；已加入按采集响应固定的停止／降级回放。 |
| AIP | 2 | 两篇均有付费访问提示；`1.39658` PDF 恢复，`5.0260731` 初轮误收讲义；修复后最终超时降级，但中间请求已收到同篇正式 PDF，已加入按采集响应固定的停止／降级回放。 |
| AMS | 3 | 2026 `jas-d-26-0015.1` 有 Purchase article 页，初轮两页 `/previewpdf/` 被误报全文，修复后重测取得 HTML 全文；另 2 篇取得 HTML／PDF。JPO 页面可见主文，不能凭当前拒绝原因码认定付费墙。已加入按采集响应固定的停止／降级回放。 |
| Annual Reviews | 1 | 既有神经科学订阅页实际降级 `limited/abstract_only`，PDF 终止原因为 `pdf_fallback_timeout`；已加入按采集响应固定的停止／降级回放。 |
| Elsevier | 4 | 1988–1994 年 RSE／AFM 全部由官方 `ENTITLED` 返回 HTTP401 `NOT_ENTITLED`；标准 CLI 的 DOI XML → PII XML → PDF 均实际失败，最终 `limited/abstract_only`。**4 篇真实订阅受限负样本已补齐**，详见下文。 |
| IEEE | 2 | TCOMM REST 全文成功；1967 PGEC 为 REST HTTP200 空 `#article` → 浏览器无正文 → PDF HTTP502 → `limited/abstract_only`。仍缺真实 REST／PDF 权限拒绝，HTTP502 不算订阅限制。 |
| IOP | 3 | `1681-7575/ae1dfc`、`0034-4885/53/3/002`、`2058-9565/ac3460` 的文章入口和 `/pdf` 均返回明确订阅 HTML，实际均为 `limited`，PDF 原因为 `pdf_download_not_triggered`。**3 篇真实订阅受限负样本已补齐**。前两篇新增正式 block；ac3460 新响应另存，保留历史挑战样本。 |
| Oxford Academic | 5 | 4 篇取得 HTML 全文，1980 Mind `lxxxix.354.263` 经 PDF 恢复。PDF-only 页面不能单凭没有 HTML 主文判付费墙；仍缺当前网络中的明确订阅页及最终权限拒绝。 |
| PNAS | 2 | 两篇均恢复 PDF；`pnas.2607267123` PDF 标注开放许可，不算非 OA；已加入按采集响应固定的停止／降级回放。 |
| Royal Society | 3 | 1984 `rspa.1984.0023` 有明确付费页并恢复 PDF，其余 2 篇 HTML 成功；已固定该历史档案响应的识别、停止与降级。2026 年文章已通过 S2O 开放，不用作非 OA 候选，依据 [官方访问范围说明](https://royalsociety.org/journals/open-access/free-content/)。 |
| Science | 2 | `science.aeg3511` 订阅页后恢复 PDF；1983 `science.7809609` 实际仅摘要，PDF 超时；已加入按采集响应固定的停止／降级回放。 |
| Springer / Nature | 2 | `nature12915` 订阅页后恢复 PDF；2026 `s41586-026-11124-z` 初轮误收补充材料，修复后仅摘要，最终 PDF 候选 HTTP404；已加入按采集响应固定的停止／降级回放。 |
| Taylor & Francis | 3 | 2025 候选及 1993／1995 旧文献入口均出现 HTTP403 Error；2025 候选恢复 PDF 且明确标注 OA，旧文献均 `limited`。仍缺明确订阅页；普通错误页不能作为付费墙。 |
| Wiley | 2 | `gcb.16758`、`gcb.16998` 实际摘要重定向后均由既有 TDM token 取得 PDF；当前仅证明普通摘要页，不单凭摘要重定向认定正文门禁；对应固定反例已覆盖。 |

本轮 12 个 `limited` 中，Elsevier 4 篇和 IOP 3 篇明确归为真实订阅受限负样本；Annual Reviews／Science 的 2 篇保留 PDF 超时事实，IEEE 1 篇保留空 REST／HTTP502，T&F 2 篇保留 HTTP403 Error。不得把全部 `limited` 统一登记为“所有路线无权限”。PDF 文件只用于身份、获取和落盘核验，不增加解析质量目标。上述 3 个误报属于获取身份／完整性缺陷，仍在范围内；原始 CLI manifest 的 fulltext 判定保留作为缺陷证据，不作成功背书。

### 修复后复核（2026-09-15）

已修复正文 PDF 候选混入参考文献／站点页脚链接，以及预览、补充材料被当作正文的问题。浏览器 PDF 路线传入目标标题；已提供标题但文件无法以 DOI／标题证明身份时，拒绝并继续既有回退。校验在转换前执行，`allow_pdf_only` 不豁免文件身份和类型检查；不做 PDF 格式清洗。

真实回归文件的处理及重新联网结果分别记录，详见 [修复后机器记录](fixture-records/pdf-identity-recheck-2026-09-15.json)：

| 目标 | 旧文件判定 | 修复后证据与实际结果 |
| --- | --- | --- |
| AIP `5.0260731` | `ci.pdf` 是另一篇讲义，拒绝；站点用户手册也不是论文。 | 最终重测 `limited/abstract_only`，原因为 PDF deadline 耗尽。中间一次重测真实收到同篇正式 16 页 PDF，身份核验通过；这是文件获取证据，不能改写最终 CLI 判定，也不能列为所有路线权限拒绝。 |
| AMS `jas-d-26-0015.1` | 两页 `/previewpdf/` 被拒绝，不凭页数短判断其他论文。 | 本次实际返回 HTML 全文，`complete/fulltext`，包含正文各节及 67 条引用；没有走 PDF 回退。不能把本次响应变化归因于 PDF 修复，也不能列为最终无权限。 |
| Nature `s41586-026-11124-z` | `MOESM1_ESM.pdf` 为 Supplementary Information，被排除。 | 继续正文 PDF 候选后 `limited/abstract_only`；最终候选为 HTTP404，不能据此称 PDF 明确权限拒绝。 |

其余 13 份历史成功 PDF 已通过新身份检查；两页 PNAS commentary 保留为正常短文。以这 3 次 final 重测替换对应历史结果后，36 篇的当前 CLI 记录为 **9 complete、13 degraded、14 limited，即 22 篇全文、14 篇摘要／元数据**；其他 33 篇未重新联网。另有上述 AIP 正式 PDF 文件获取证据，不混入 CLI 成功数。初次 AIP／AMS 错误文件和原始 manifest 保留为回归证据；Nature 补充 PDF 及其派生内容已按用户要求删除，保留拒绝元数据和合成回归。

付费墙分析仍需区分访问提示、文件可获取性和 CLI 终态：已确认的真实订阅受限负样本包括 Elsevier 4 篇、IOP 3 篇，两家的该类负样本覆盖已具备；新出现的 AIP／Nature limited 是超时／请求失败，不能增加最终权限拒绝数量。PNAS `pnas.2607267123` 与 T&F `19455224.2025.2547671` 的 PDF 明确带有 CC BY-NC-ND 4.0 开放许可，不作为非 OA 样本。其余出版社仍按下表保留缺口，不能宣称全部最终拒绝链已经补齐。保留已有 key、TDM token 和浏览器状态的测试不等于匿名访问测试。


### OUP／T&F 订阅页补采（2026-09-15）

本次只采集文章页面，沿用既有浏览器状态并使用 headed 模式，未运行标准 CLI 全文／PDF 回退，不计入上述 36 篇 CLI 统计。HTTP 响应实体、最终 DOM 和截图分别留存，记录见[本轮机器记录](fixture-records/fixture-acquisition-2026-09-15-subscriptions.json)的 `additional_subscription_pages`。

- **Oxford Academic 订阅页已补齐**：[reseval/rvag052](../tests/fixtures/block/10.1093_reseval_rvag052/) 先返回 HTTP403，随后正常浏览器导航取得 HTTP200 文章页。响应与最终 DOM 均包含同篇 DOI／标题、完整摘要、明确无访问权限提示和订阅入口，没有正文各节；当前 extractor／availability 回放拒绝为 `abstract_only`。新增 1 项正式 block。该页面证据不证明 PDF 或其他全文路线最终无权限，当前改为验证停止与本地降级。
- **Taylor & Francis 订阅页已补齐**：用户确认切换网络后，`01431161.2025.2516689` 第 3 次尝试经正常 headed 导航取得 HTTP200 [订阅页](../tests/fixtures/block/10.1080_01431161.2025.2516689/)。响应与最终 DOM 均有同篇 DOI／标题、摘要、`Access Denial` 标记、机构登录及同篇购买选项，没有全文容器。采集时 provider 在抽取可见摘要前以 `publisher_paywall` 拒绝，历史回放分类为 `metadata_only`。当前回放保留响应中的摘要，确认门禁后停止请求并返回 `abstract_only`；原始采集记录不改写。切换前旧候选 `01431169308904370` 及该新候选的 3 次 HTTP403 IP 错误观察继续保留为辅助失败证据，其中新 DOI 的辅助 golden 不改成成功样本。

## 各出版社已有案例和待补项

表中链接指向论文 fixture 目录，完整 PDF 清单见下一节。附件覆盖以原文／官方索引、同篇身份及链接为准。已下载的附件文件已删除；下表仅列保留的索引／链接与正文证据。正文及正文图片的缺口继续保留。

| 出版社／平台 | 已有代表案例 | 待补项 |
| --- | --- | --- |
| ACS | [acsomega.3c06992](../tests/fixtures/golden_criteria/10.1021_acsomega.3c06992/) 正文、整式、完整表行及真实 Figure 1；另有完整论文 PDF。 | 已补 JACS 订阅页和 PDF 恢复，已加入按采集响应固定的停止／降级回放；`acsomega.4c03987` 保留 `ao4c03987_si_001` 附件索引和链接；代表论文 8 张正文图齐全。 |
| AIP | [5.0129134](../tests/fixtures/golden_criteria/10.1063_5.0129134/) HTML、代表图、完整 9 页 PDF及 31 条 PDF 引用核对；另有历史挑战 DOM 回放。 | 已补非 OA 付费页；5.0260731 旧误判已修复，收到同篇正式 PDF 但最终 CLI 超时降级；已加入按采集响应固定的停止／降级回放；同篇 `125205_1_epaps` ZIP 附件索引和链接保留；4 张正文图齐全。完整论文 PDF 已补齐。 |
| AMS（美国气象学会） | [jamc-d-24-0048.1](../tests/fixtures/golden_criteria/10.1175_jamc-d-24-0048.1/) 正文图表、真实 Figure 1；BAMS/JCLI 完整 PDF；真实 CloudFront 403 回放。 | JAS 旧两页预览误判已修复，本次重测取得 HTML 全文；已加入按采集响应固定的停止／降级回放；JCLI `.s1.pdf` 附件索引和链接保留；JAMC 10 张图和 5 张表格图齐全。图片下载回放不证明当次正文联网成功。 |
| Annual Reviews | [annurev-control-030123-013355](../tests/fixtures/golden_criteria/10.1146_annurev-control-030123-013355/) 正文、表格、真实图；[annurev-control-090419-075625](../tests/fixtures/golden_criteria/10.1146_annurev-control-090419-075625/) 真实公式 GIF 及人工转录；完整论文 PDF；新增明确订阅页。 | 神经科学目标保留 Supplemental Figures 1–6 和 Videos 1–4 的索引和链接；历史视频 403 元数据保留；实际 PDF 超时已记录，已加入按采集响应固定的停止／降级回放。 |
| arXiv | [0811.2625v2](../tests/fixtures/golden_criteria/10.48550_arxiv.0811.2625v2/) 完整 43 页正文 PDF、保留的正文源码／图片及 2 个附件的索引；[2606.00587v2](../tests/fixtures/golden_criteria/10.48550_arxiv.2606.00587v2/) 和 [0905.2326v2](../tests/fixtures/golden_criteria/10.48550_arxiv.0905.2326v2/) 完整页面及 1／103 个附件的索引；正文源码与图片按原字节单独保留。 | 三组附件仅保留索引／身份／链接，附件文件和含附件的源码包已删除；更多 HTML 模板的内容完整性仍可扩展。当前 OA 目标不设付费墙配额。 |
| Copernicus | [acp-24-1-2024](../tests/fixtures/golden_criteria/10.5194_acp-24-1-2024/) XML 正文、整式和真实图；4 份空 body XML → 同篇真实 PDF 恢复及注入失败降级。 | ACP supplement 索引／链接保留，8 张正文图已补齐。当前 OA 目标不设付费墙配额。 |
| Elsevier | [j.envres.2018.12.059](../tests/fixtures/golden_criteria/10.1016_j.envres.2018.12.059/) 官方 API XML、完整 11 页 PDF及 gr1 JPEG；[j.agrformet.2024.109975](../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/) 当前 API key 取得 XML 全文，另存历史 PDF 首页权限限制响应。 | **仅 API key 路线**的历史 RSE／AFM 权限拒绝及实际降级链已补齐；三篇既有 XML 保留 16 张正文图及 3 份同篇作者稿 PDF；3 份 mmc1 DOCX 已删除，保留其索引和链接；作者稿不计补充材料。浏览器页面不作为该 provider 的证据。 |
| Frontiers | [fmars.2023.1101972](../tests/fixtures/golden_criteria/10.3389_fmars.2023.1101972/) XML 正文、公式、表格、完整 12 页 PDF；真实 supplemental-data API 与 `Table_1.DOCX` 的同篇链接。 | 附件保留 API／同篇身份／远程链接；同篇全部 4 张正文 WebP 的下载、解码和文章链接已补齐；第二篇 [fpls.2020.01216](../tests/fixtures/golden_criteria/10.3389_fpls.2020.01216/) 的真实 NLM 2.3 XML 与 5/5 正文图也已补齐。当前 OA 目标不设付费墙配额。 |
| IEEE（电气与电子工程师协会） | [ACCESS.2024.3352924](../tests/fixtures/golden_criteria/10.1109_ACCESS.2024.3352924/) 完整 17 页 PDF、真实 Figure 1、3 页引用响应去重为 60 条；[TBME.2024.3434477](../tests/fixtures/golden_criteria/10.1109_TBME.2024.3434477/) 购买页之后 REST 实际取得全文，回退机制已验证。 | 真实 REST／PDF 权限拒绝及最终降级链；RITA 的 `supp1-3668995.pdf` 附件索引和链接保留；ACCESS 全篇 23/23 个图片资产已完成，旧 22 个文件 403 的响应仍保留。购买 UI 本身不能算最终无权限，详见下文。 |
| IOP | [1748-9326/ab7d02](../tests/fixtures/golden_criteria/10.1088_1748-9326_ab7d02/) 标准 CLI 全文、27 条引用、5 张高清图；保留真实 `/data` 索引与同篇附件签名链接。另有 ac3460 代表图、Radware 挑战页及完整论文 PDF。 | 3 篇真实订阅页及实际降级已补齐。ab7d02 附件索引和远程链接保留，补充 PDF 已删除。 |
| MDPI | [math11030657](../tests/fixtures/golden_criteria/10.3390_math11030657/) 真实 Figure 1、整式、附录表格；完整论文 PDF；真实 403 Access Denied 回放。 | S1 ZIP 附件索引和远程链接保留，文件已删除；代表论文 5 张图齐全。当前 OA 目标不设付费墙配额。 |
| Oxford Academic | [bioinformatics/btaa823](../tests/fixtures/golden_criteria/10.1093_bioinformatics_btaa823/) 新正文提供的签名 preview JPEG 下载和组装；btaa161 正文、公式、表格、引用；完整论文 PDF；历史挑战 DOM 回放；新增 [reseval/rvag052](../tests/fixtures/block/10.1093_reseval_rvag052/) 明确订阅页及当前拒绝回放。 | 订阅目标的识别、停止与本地降级回放；btaa161 附件索引／链接保留；btaa823 全部 9 张 **full-size** 图已补齐。preview 成功及旧签名 403 分别保留。 |
| PLOS | [journal.pone.0015338](../tests/fixtures/golden_criteria/10.1371_journal.pone.0015338/) XML 与真实图；其他样本完整表格、正文及引用审阅；完整论文 PDF。 | `journal.pone.0218513` 18 个附件保留索引链接，已取得的完整／截断文件全部删除。代表论文 9 张图、4 张公式图、5 张表格图齐全。当前 OA 目标不设付费墙配额。 |
| PNAS | [pnas.2406303121](../tests/fixtures/golden_criteria/10.1073_pnas.2406303121/) 标准 CLI 在 HTML 空壳后恢复完整 10 页 PDF，另有真实 Figure 1；3 份摘要类及 1 份仅元数据 block。 | 受限目标历史回退已采集，当前已固定限制的识别、停止与降级；`pnas.2509692123` 的 `.sapp.pdf`／`.sd01.xlsx` 历史文件请求为 403，不要求补下载；代表论文 4 张正文图齐全。 |
| Royal Society Publishing | [rsif.2019.0334](../tests/fixtures/golden_criteria/10.1098_rsif.2019.0334/) 正文及真实图；其他样本公式、表格和引用审阅；完整论文 PDF。 | 已补历史档案付费页及 PDF 恢复，已加入按采集响应固定的停止／降级回放；该目标 electronic supplementary material 索引／链接保留，5 张正文图已补齐。 |
| Science / AAAS | [sciadv.abf8021](../tests/fixtures/golden_criteria/10.1126_sciadv.abf8021/) 人工验证后 HTML 全文、完整 12 页 PDF及当前转换，43 条 PDF 引用；[sciadv.adl6155](../tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/) 真实图；3 份摘要类及 1 份仅元数据 block。 | 受限目标历史回退已采集，当前已固定限制的识别、停止与降级；adl6155 的 SM PDF 历史下载为挑战／403，不要求补下载；adl6155／abf8021 的 8／7 张正文图齐全。abf8021 转换已经完成。 |
| Springer / Nature | [s43247-024-01295-w](../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/) 完整 10 页 PDF及真实图；新旧模板正文、表格、引用审阅；5 份摘要类 block，含新增明确 Nature 订阅预览。 | nature12915 PDF 恢复已补；2026 Nature 补充材料误判已修复，正文候选请求失败后仅摘要；已加入按采集响应固定的停止／降级回放；`s41561-022-00912-7` 的补充 PDF、2 个 source data ZIP 和 1 个 CSV 仅保留索引／链接；代表论文 5 张正文图齐全。 |
| Taylor & Francis | [LST：17538947.2022.2137254](../tests/fixtures/golden_criteria/10.1080_17538947.2022.2137254/) 标准 CLI HTML 全文、64 条引用、全部 12 张 full-size 原始 JPEG及浏览器恢复 PNG；另有真实 23 页 PDF 回退和 Python／CLI／MCP 回放；新增 [01431161.2025.2516689](../tests/fixtures/block/10.1080_01431161.2025.2516689/) 明确订阅页及当前拒绝回放。 | 订阅目标的识别、停止与本地降级回放；[15481603.2026.2667034](../tests/fixtures/golden_criteria/10.1080_15481603.2026.2667034/) 的 `tgrs_a_2667034_sm1980.docx` 历史下载为 403，不要求补下载；该篇 9 张图复用 1 张，另 8 张已由 Camoufox 恢复为原尺寸 PNG，旧文件 403 证据保留。LST 12 张原图已补齐。 |
| Wiley | [gcb.16414](../tests/fixtures/golden_criteria/10.1111_gcb.16414/) 正文、表格、完整 12 页官方 TDM PDF；[2004gb002273](../tests/fixtures/golden_criteria/10.1029_2004gb002273/) 真实图；4 份摘要类 block。 | 普通摘要页与明确门禁的语义已分别固定；gcb.16414 Supporting Information DOCX 历史下载为 403，不要求补下载；gcb.16414 的 6 张原图已补齐；2004gb002273 复用 1 张图，新增 13 张原图及 1 张 preview 公式 GIF，旧 403 证据保留。 |

## 指定附件与整篇图片补采（2026-09-15）

沿用用户确认的原网络、既有订阅凭证和浏览器状态；**headless 优先，失败后才允许 headed；每目标最多三次尝试，明确访问拒绝／挑战／限流遵守停止要求**。Elsevier 全程仅使用既有 API key。复用 Frontiers、IOP、三组 arXiv 的附件索引和 T&F LST 12 张原图；不新增论文或模板配额。

2026-09-15 使用固定的 34 篇论文。**当时正文图片验收为 274/324 个，尚缺 50 个，分布于 IEEE ACCESS、T&F `15481603.2026.2667034` 和 Wiley 两篇；这些真实文件请求均为 403。**另有 3 份 Elsevier 同篇作者稿 object 已完成文件及链接回放。43 个补充材料文件仅要求索引／同篇身份／链接覆盖，不计入真实下载待补数。

2026-09-15 登记 370 个来源文件目标：**277 个保留真实文件及回放证据（274 张正文图片、3 份作者稿）、50 个正文图片待补、43 个补充材料仅保留索引／链接**。历史 307 个文件验收结果已归入机器记录的历史字段，不代表这些附件文件仍存在。当时图片为 **25 篇、324 个唯一图片资产，274 个完成，21 篇整篇集合齐全**。2026-09-16 补采后的当前数量见上文“补齐结果”。相同文件重复引用按稳定 URL 去重，PLOS 的 `id` 查询参数参与身份，签名参数不参与；内容相同但官方文件名不同不擅自合并。当前 provider 选择的最高尺寸 object 与其缩略图不重复计算；MathML／结构化文本的替代表示、IOP 单字符 entity GIF、站点装饰和 PDF 转换导出图不作为独立正文图片目标。

下文“文件验收完成”是原文／索引 → 同篇实际文件 → 当前发现和下载 → 最终文章链接的离线回放通过，**不等于标准 CLI 本轮联网全文成功**。逐请求状态、实体／DOM／下载、大小、SHA-256、浏览器模式和文件类型见[机器记录](fixture-records/fixture-assets-2026-09-15.json)及各 DOI 的 `acquisition/assets-2026-09-15/`。历史本地图片的未知 HTTP 状态保持未知，回放注入的 HTTP 包装不冒充真实响应。

### 16 家指定附件（仅保留索引与链接）

已取得的补充材料文件已删除；下表数量表示指定索引条目，不表示本地附件文件数。此前文件下载、失败、校验的元数据明确标为历史记录。

| Provider | DOI | 指定索引条目 | 当前保留 |
| --- | --- | --- | --- |
| acs | [10.1021/acsomega.4c03987](../tests/fixtures/golden_criteria/10.1021_acsomega.4c03987/acquisition/assets-2026-09-15/collection.json) | 1 | 原文／官方索引、同篇身份及远程链接 |
| aip | [10.1063/5.0129134](../tests/fixtures/golden_criteria/10.1063_5.0129134/acquisition/assets-2026-09-15/collection.json) | 1 | 原文／官方索引、同篇身份及远程链接 |
| ams | [10.1175/jcli-d-23-0738.1](../tests/fixtures/golden_criteria/10.1175_jcli-d-23-0738.1/acquisition/assets-2026-09-15/collection.json) | 1 | 原文／官方索引、同篇身份及远程链接 |
| annualreviews | [10.1146/annurev-neuro-062111-150343](../tests/fixtures/golden_criteria/10.1146_annurev-neuro-062111-150343/acquisition/assets-2026-09-15/collection.json) | 5 | 原文／官方索引、同篇身份及远程链接 |
| copernicus | [10.5194/acp-24-1-2024](../tests/fixtures/golden_criteria/10.5194_acp-24-1-2024/acquisition/assets-2026-09-15/collection.json) | 1 | 原文／官方索引、同篇身份及远程链接 |
| elsevier | [10.1016/j.ecolind.2024.112140](../tests/fixtures/golden_criteria/10.1016_j.ecolind.2024.112140/acquisition/assets-2026-09-15/collection.json) | 1 | 原文／官方索引、同篇身份及远程链接 |
| ieee | [10.1109/RITA.2026.3668995](../tests/fixtures/golden_criteria/10.1109_RITA.2026.3668995/acquisition/assets-2026-09-15/collection.json) | 1 | 原文／官方索引、同篇身份及远程链接 |
| mdpi | [10.3390/s23010001](../tests/fixtures/golden_criteria/10.3390_s23010001/acquisition/assets-2026-09-15/collection.json) | 1 | 原文／官方索引、同篇身份及远程链接 |
| oxfordacademic | [10.1093/bioinformatics/btaa161](../tests/fixtures/golden_criteria/10.1093_bioinformatics_btaa161/acquisition/assets-2026-09-15/collection.json) | 1 | 原文／官方索引、同篇身份及远程链接 |
| plos | [10.1371/journal.pone.0218513](../tests/fixtures/golden_criteria/10.1371_journal.pone.0218513/acquisition/assets-2026-09-15/collection.json) | 18 | 原文／官方索引、同篇身份及远程链接 |
| pnas | [10.1073/pnas.2509692123](../tests/fixtures/golden_criteria/10.1073_pnas.2509692123/acquisition/assets-2026-09-15/collection.json) | 2 | 原文／官方索引、同篇身份及远程链接 |
| royalsocietypublishing | [10.1098/rsif.2019.0334](../tests/fixtures/golden_criteria/10.1098_rsif.2019.0334/acquisition/assets-2026-09-15/collection.json) | 1 | 原文／官方索引、同篇身份及远程链接 |
| science | [10.1126/sciadv.adl6155](../tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/acquisition/assets-2026-09-15/collection.json) | 1 | 原文／官方索引、同篇身份及远程链接 |
| springer | [10.1038/s41561-022-00912-7](../tests/fixtures/golden_criteria/10.1038_s41561-022-00912-7/acquisition/assets-2026-09-15/collection.json) | 4 | 原文／官方索引、同篇身份及远程链接 |
| tandf | [10.1080/15481603.2026.2667034](../tests/fixtures/golden_criteria/10.1080_15481603.2026.2667034/acquisition/assets-2026-09-15/collection.json) | 1 | 原文／官方索引、同篇身份及远程链接 |
| wiley | [10.1111/gcb.16414](../tests/fixtures/golden_criteria/10.1111_gcb.16414/acquisition/assets-2026-09-15/collection.json) | 1 | 原文／官方索引、同篇身份及远程链接 |

### 整篇图片集合

| Provider | DOI | 已完成／唯一图片 | 结论 |
| --- | --- | --- | --- |
| acs | [10.1021/acsomega.3c06992](../tests/fixtures/golden_criteria/10.1021_acsomega.3c06992/acquisition/assets-2026-09-15/collection.json) | 8/8 | 整篇集合完成 |
| aip | [10.1063/5.0129134](../tests/fixtures/golden_criteria/10.1063_5.0129134/acquisition/assets-2026-09-15/collection.json) | 4/4 | 整篇集合完成 |
| ams | [10.1175/jamc-d-24-0048.1](../tests/fixtures/golden_criteria/10.1175_jamc-d-24-0048.1/acquisition/assets-2026-09-15/collection.json) | 15/15 | 10 张图 + 5 张表格图；保留原始 TIFF/EPS 响应及 headed JPEG 回退 |
| annualreviews | [10.1146/annurev-control-030123-013355](../tests/fixtures/golden_criteria/10.1146_annurev-control-030123-013355/acquisition/assets-2026-09-15/collection.json) | 5/5 | 整篇集合完成 |
| annualreviews | [10.1146/annurev-control-090419-075625](../tests/fixtures/golden_criteria/10.1146_annurev-control-090419-075625/acquisition/assets-2026-09-15/collection.json) | 131/131 | 3 张图 + 128 个公式 GIF；行内公式及图注公式均有文件链接 |
| copernicus | [10.5194/acp-24-1-2024](../tests/fixtures/golden_criteria/10.5194_acp-24-1-2024/acquisition/assets-2026-09-15/collection.json) | 8/8 | 整篇集合完成 |
| elsevier | [10.1016/j.ecolind.2024.112140](../tests/fixtures/golden_criteria/10.1016_j.ecolind.2024.112140/acquisition/assets-2026-09-15/collection.json) | 8/8 | 整篇集合完成 |
| elsevier | [10.1016/j.envres.2018.12.059](../tests/fixtures/golden_criteria/10.1016_j.envres.2018.12.059/acquisition/assets-2026-09-15/collection.json) | 3/3 | 整篇集合完成 |
| elsevier | [10.1016/j.agrformet.2024.109975](../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/acquisition/assets-2026-09-15/collection.json) | 5/5 | 整篇集合完成 |
| ieee | [10.1109/ACCESS.2024.3352924](../tests/fixtures/golden_criteria/10.1109_ACCESS.2024.3352924/acquisition/assets-2026-09-15/collection.json) | 23/23 | 2026-09-16 新增 22 个原图，旧 403 记录保留；新集合见本轮机器记录 |
| mdpi | [10.3390/math11030657](../tests/fixtures/golden_criteria/10.3390_math11030657/acquisition/assets-2026-09-15/collection.json) | 5/5 | 整篇集合完成 |
| oxfordacademic | [10.1093/bioinformatics/btaa823](../tests/fixtures/golden_criteria/10.1093_bioinformatics_btaa823/acquisition/assets-2026-09-15/collection.json) | 9/9 | 9 张 full-size JPEG；保留 preview 和旧签名失败 |
| plos | [10.1371/journal.pone.0015338](../tests/fixtures/golden_criteria/10.1371_journal.pone.0015338/acquisition/assets-2026-09-15/collection.json) | 18/18 | 9 张图 + 4 张公式图 + 5 张表格图；真实 provider 下载与组装通过 |
| pnas | [10.1073/pnas.2406303121](../tests/fixtures/golden_criteria/10.1073_pnas.2406303121/acquisition/assets-2026-09-15/collection.json) | 4/4 | 整篇集合完成 |
| royalsocietypublishing | [10.1098/rsif.2019.0334](../tests/fixtures/golden_criteria/10.1098_rsif.2019.0334/acquisition/assets-2026-09-15/collection.json) | 5/5 | 整篇集合完成 |
| science | [10.1126/sciadv.adl6155](../tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/acquisition/assets-2026-09-15/collection.json) | 8/8 | 整篇集合完成 |
| science | [10.1126/sciadv.abf8021](../tests/fixtures/golden_criteria/10.1126_sciadv.abf8021/acquisition/assets-2026-09-15/collection.json) | 7/7 | 整篇集合完成 |
| springer | [10.1038/s43247-024-01295-w](../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/acquisition/assets-2026-09-15/collection.json) | 5/5 | 整篇集合完成 |
| tandf | [10.1080/15481603.2026.2667034](../tests/fixtures/golden_criteria/10.1080_15481603.2026.2667034/acquisition/browser-retry-2026-09-16/collection.json) | 9/9 | 复用 1 张，新增 8 张原尺寸浏览器 PNG；未捕获原始 JPEG 字节／HTTP 状态 |
| tandf | [10.1080/17538947.2022.2137254](../tests/fixtures/golden_criteria/10.1080_17538947.2022.2137254/acquisition/assets-2026-09-15/collection.json) | 12/12 | 整篇集合完成 |
| wiley | [10.1111/gcb.16414](../tests/fixtures/golden_criteria/10.1111_gcb.16414/acquisition/browser-retry-2026-09-16/collection.json) | 6/6 | 现有浏览器取得全部原图；旧 403 证据保留 |
| wiley | [10.1029/2004gb002273](../tests/fixtures/golden_criteria/10.1029_2004gb002273/acquisition/browser-retry-2026-09-16/collection.json) | 14/15 原尺寸＋1 preview | 新增 13 个原图及 1 个公式 GIF；复用旧图 1 个，preview 不冲销原尺寸要求 |
| frontiers | [10.3389/fmars.2023.1101972](../tests/fixtures/golden_criteria/10.3389_fmars.2023.1101972/acquisition/assets-2026-09-15/collection.json) | 4/4 | 4 张 WebP；headless 本地 Image.decode 与像素读回核验 |
| iop | [10.1088/2058-9565/ac3460](../tests/fixtures/golden_criteria/10.1088_2058-9565_ac3460/acquisition/assets-2026-09-15/collection.json) | 2/2 | 整篇集合完成 |
| iop | [10.1088/1748-9326/ab7d02](../tests/fixtures/golden_criteria/10.1088_1748-9326_ab7d02/acquisition/assets-2026-09-15/collection.json) | 5/5 | 整篇集合完成 |

**历史文件失败证据边界（附件不影响当前验收）：** PLOS 两个 ZIP 的截断字节及两个 OPJ 已删除，只保留历史状态和哈希；未扩大生产下载上限。PNAS 初次采集脚本错误拼接到 `doi.org/doi/suppl/` 的 404 单独标为采集错误，最终状态以正确官方域名的真实 403 为准。浏览器通用 `publisher_paywall` 提示也不直接判定正文受限：Springer、PNAS、Wiley 的正文证据与文件拒绝分别记录；Annual Reviews 神经科学页面经当前 provider 复核为 abstract-only。真实响应失败与离线注入失败始终分开。

**本轮局部修复：** Annual Reviews 旧模板保留全部行内公式 GIF，并避免将图注公式误选为主图；PLOS 下载 JATS 明确链接的表格图片，保留公式 `info:doi/` 身份，结构化表格正文与对应图片文件链接同时保留。没有更改全局 retry/cache/browser、安全上限、公开参数、依赖、版本号或 CI。

**删除附件前的历史验证：** 使用项目默认并行配置，全量 unit 为 3031 passed、3 skipped（576 subtests），全量 integration 为 24 passed、4 skipped（1217 subtests）。最终资产与来源专项审计为 78 passed、2 skipped（1206 subtests）；两项跳过对应无合格文件的 PNAS 附件和 Wiley `gcb.16414`；前者不阻塞当前范围，后者的正文图片缺口仍保留。改动文件的 Ruff 检查及 `git diff --check` 通过。

### 完整论文 PDF 清单

下列目录均保存 `original.pdf`。它们证明真实完整文件已归档；是否实际触发过标准流程回退，应查看同篇采集记录，不能从文件存在推断。

| 出版社／平台 | 样本（DOI；arXiv 使用版本 ID） |
| --- | --- |
| ACS | `10.1021/acsomega.2c02828` |
| AIP | `10.1063/5.0129134` |
| AMS | `10.1175/bams-d-24-0270.1`、`10.1175/jcli-d-25-0547.1` |
| Annual Reviews | `10.1146/annurev-med-120811-171056` |
| arXiv | `1406.2661v1`、`2006.11239v2`、`0811.2625v2` |
| Copernicus | `10.5194/acp-1-1-2001`、`10.5194/bg-1-1-2004`、`10.5194/cp-1-1-2005`、`10.5194/dwes-1-1-2008` |
| Elsevier | `10.1016/j.envres.2018.12.059` |
| Frontiers | `10.3389/fmars.2023.1101972` |
| IEEE | `10.1109/ACCESS.2024.3352924` |
| IOP | `10.1088/1748-9326/aa9f73` |
| MDPI | `10.3390/en16186655` |
| Oxford Academic | `10.1093/bioinformatics/btaa153` |
| PLOS | `10.1371/journal.pbio.0040298` |
| PNAS | `10.1073/pnas.2406303121` |
| Royal Society Publishing | `10.1098/rsta.2020.0108` |
| Science / AAAS | `10.1126/sciadv.abf8021` |
| Springer / Nature | `10.1038/s43247-024-01295-w` |
| Taylor & Francis | `10.1080/15481603.2026.2667034`、`10.1080/17538947.2022.2137254` |
| Wiley | `10.1111/gcb.16414` |

## 付费墙与正文负例

**Elsevier 4 篇、IOP 3 篇就是典型的真实订阅受限负样本，两家的该类负样本覆盖已具备。** Elsevier 保存官方无权限声明和实际仅摘要终态；IOP 保存文章及 PDF 入口的订阅页和实际降级终态。每条请求的状态码、权限提示来源和回退结果属于样本属性，不要求所有请求都返回同一种权限拒绝码才承认负样本。

该归类以采集记录为单位：`golden_criteria` 下的辅助 acquisition 也可以保存负样本，不因所在目录叫 golden 就视为正样本；同 DOI 的历史正文、挑战页和本次订阅负样本分别保留。机器记录中这 7 篇统一标注 `sample_role=negative`、`negative_kind=subscription_restricted`，不重复增加 manifest 样本数。

后续优先补真实订阅限制。挑战页数量已足够，不继续按出版社凑挑战页；开放获取目标不要求产生付费墙。换成无订阅 IP 后，已有 API key 或其他合法路线仍可能取得全文。后续浏览器采集先用 headless；在非明确访问拒绝的失败后才用 headed，模式切换计入同目标最多 3 次尝试。明确权限拒绝、挑战和限流不通过切换模式绕过；Elsevier 仅使用 API key 路线。

| 类型 | 已有案例 | 仍需补充 |
| --- | --- | --- |
| 明确 HTTP200 订阅页 | [Annual Reviews](../tests/fixtures/block/10.1146_annurev-neuro-062111-150343/)：完整摘要、购买／订阅入口，主文缺失；[Nature](../tests/fixtures/block/10.1038_nature12915/)：`access=No`、订阅预览及购买入口，摘要、引用和部分图注／扩展材料可见，主文缺失。两份均由当前 extractor 拒绝为 `abstract_only`；另新增 IOP 两篇明确订阅 HTML block。 | 本轮 Annual Reviews 实际 PDF 超时，Nature 实际恢复 PDF；IOP 文章入口和 `/pdf` 均返回订阅 HTML并最终 limited。旧注入失败测试只保留机制含义。 |
| 其他摘要类 block | Springer 另外 4 份、Wiley 4 份、Science 4 份、PNAS 4 份；完整 DOI 列表见 manifest。 | 本轮已补 Wiley／Science／PNAS 指定目标的实际回退，逐项结果见上表；其余旧样本仍需核对订阅语义，不能只凭 `abstract_only` 原因码认定付费墙。 |
| 挑战／拒绝／空壳 | AIP 1、AMS 1、Annual Reviews 1、IOP 1、MDPI 1、Oxford Academic 1、T&F 1；均已登记当前拒绝及失败降级回放。 | 不再设数量目标。IOP 实际为 Radware，`cloudflare_challenge` 是既有兼容原因码；AMS 为 CloudFront 403。 |
| 空正文 XML | Copernicus 4 份，当前 adapter/provider/service 覆盖同篇真实 PDF 恢复和注入失败。 | PDF 内容边界见下文；这些不是付费墙。 |

<a id="ieee-flow"></a>

### IEEE：历史恢复记录与当前门禁停止

`10.1109/TBME.2024.3434477` 的 headed landing 显示 Sign In or Purchase，metadata 标识非 OA，且没有 `#article`。此前把 landing 就绪条件误设为必须有正文容器，导致提前退出；现已改为等待文章 metadata，正文恢复仍使用正文就绪条件。

历史修复后的[真实标准 CLI 记录](../tests/fixtures/golden_criteria/10.1109_TBME.2024.3434477/acquisition/ieee-flow-2026-09-15/)证明：直接 landing HTTP202 → headed 浏览器取得 metadata → 两页引用 → REST HTTP200 全文 → `complete/fulltext`。REST 成功后停止，未调用 PDF 是正常结果。该采集记录证明当时 REST 路线成功；当前正文付费墙的停止验收由下述离线回放承担。

[当前代码离线回放](../tests/golden/test_acquired_ieee_paywall_flow.py)使用同一真实 landing，确认同篇正文购买门禁后立即停止；即使预置可成功的 REST 全文，也不请求 REST、引用分页或 PDF，保留已收到摘要并返回 `limited/abstract_only`。历史成功链保留为历史事实，不再作为已确认门禁后的恢复预期。 本轮另测 `10.1109/TCOMM.2024.3395332`，REST 仍成功；`10.1109/PGEC.1967.264619` 实际为 REST HTTP200 空正文、PDF HTTP502 后降级，仅补齐真实失败链，不能将它称为权限拒绝。

### Elsevier：仅使用 API key 路线

`10.1016/j.agrformet.2024.109975` 当前通过既有 API key 取得 XML 全文，标准 CLI 为 `complete/fulltext`。历史官方 PDF 响应虽然 HTTP200，但 `x-els-status` 明确表示无权限、只返回首页；该文件单独保存为 `pdf-first-page.pdf`，不计完整 PDF，也不代表当前 XML 路线受限。

已有浏览器观察及其人工验证记录不用于 Elsevier provider 证据。本轮新增以下 4 篇历史非 OA 候选，均由当前 API key 取得官方 HTTP401 `NOT_ENTITLED`：

- RSE：`10.1016/0034-4257(88)90106-X`、`10.1016/0034-4257(94)90046-9`。
- AFM：`10.1016/0168-1923(91)90003-9`、`10.1016/0168-1923(91)90002-8`。

标准 CLI 实际尝试 DOI XML → PII XML → PDF，3 条 FULL 请求均返回 HTTP400 `INVALID_INPUT`，最终 `limited/abstract_only`。另行使用官方支持的 `ENTITLED` view 验证权限；其中 RSE 1994、AFM 1991（90002-8）省略 view 的 PDF 请求返回 HTTP200，`x-els-status` 明确限制为首页。这些补充请求与标准流程分别记录，未把 HTTP400 原因码改造成 HTTP403/no_access，也未将受限首页计为完整 PDF。官方 view 契约见 [Article Retrieval API](https://dev.elsevier.com/documentation/ArticleRetrievalAPI.wadl)。

## 已完成范围和证据边界

1. **门禁识别与停止。** 真实订阅页、访问提示、摘要降级及终止回归均保留。IEEE 最新无订阅记录满足同篇门禁识别和停止；不再设置门禁后 REST／PDF 拒绝样本配额。其他出版社历史未覆盖路线仅描述覆盖范围，不扩展本轮任务。
2. **附件索引与链接。** 指定目标已按原文／官方索引、同篇身份和远程链接范围验收，不设附件字节补下载目标；arXiv 正文源码／图片仍按原字节保留。
3. **正文与图片。** Wiley 附录已修复并更新 exact；332 个逻辑图片目标均有文件且已按本轮要求验收，Wiley 公式已获用户确认。T&F 本轮 8 张原图及另一篇 LST 的 12 张原始 JPEG 均已核对，旧 PNG 和失败响应继续保留。
4. **PDF。** Science／PNAS 采用最新有完整响应证据的同篇 PDF。PDF 解析、引用重建、OCR、公式、表格、跨栏顺序及排版不纳入改进或验收，维持转换器输出原样保存边界。
5. **HTML／XML 审阅。** 已完成指定正文、引文、公式、表格及模板回归；未开展 151 项 exact 的全面内容审阅，不将其列为本轮未完成事项。
6. **来源记录。** 最新响应与旧记录分开保留。旧成功 PDF 响应和旧挑战 DOM 状态中未知的字段不倒填；用户已明确以最新证据验收，这些历史未知值不再触发后续采集或人工核验。

## 已有内容回放入口

以下列出已有断言的主要入口，具体 DOI 与期望值保留在测试和 manifest 中，避免另建一套编号清单。

| 已有案例范围 | 回放入口 |
| --- | --- |
| 固定订阅响应、OUP HTTP／DOM、历史证据未知值 | [test_subscription_response_contracts.py](../tests/golden/test_subscription_response_contracts.py)、[test_reviewed_block_provider_paths.py](../tests/golden/test_reviewed_block_provider_paths.py) |
| IEEE 新原图／Frontiers 第二模板完整图集与真实内容 | [test_regression_asset_collections.py](../tests/golden/test_regression_asset_collections.py)、[test_frontiers_second_template.py](../tests/golden/test_frontiers_second_template.py) |
| 已有 arXiv／Nature／Wiley／OUP 变体 | [test_reviewed_html_variants.py](../tests/golden/test_reviewed_html_variants.py) |
| PLOS／OUP／Copernicus／Frontiers／AIP：正文长段落、顺序、引用和附件身份 | [test_reviewed_publisher_content.py](../tests/golden/test_reviewed_publisher_content.py) |
| ACS／IOP／MDPI／Royal／Annual Reviews：正文、引用、完整公式与表行 | [test_reviewed_html_publisher_content.py](../tests/golden/test_reviewed_html_publisher_content.py) |
| Springer 新旧模板／Wiley／Science／PNAS／AMS：正文、引用及指定公式表格 | [test_reviewed_atypon_springer_content.py](../tests/golden/test_reviewed_atypon_springer_content.py) |
| Elsevier／IEEE／arXiv／T&F：正文、引用、完整公式和指定表格 | [test_reviewed_remaining_provider_content.py](../tests/golden/test_reviewed_remaining_provider_content.py) |
| PDF 获取／组装原样文本回放；不解析、重建正文内引用 | [test_reviewed_pdf_assembly.py](../tests/golden/test_reviewed_pdf_assembly.py)、[test_reviewed_pdf_completion.py](../tests/golden/test_reviewed_pdf_completion.py)、[test_acquired_completion.py](../tests/golden/test_acquired_completion.py) |
| 代表图片真实字节、下载及当前文章链接 | [test_representative_asset_bytes.py](../tests/golden/test_representative_asset_bytes.py)、[test_acquired_article_assets.py](../tests/golden/test_acquired_article_assets.py)、[test_acquired_completion_assets.py](../tests/golden/test_acquired_completion_assets.py) |
| Frontiers API／附件、Wiley TDM PDF、IEEE 引用分页／PDF／图 | [test_acquired_publisher_inputs.py](../tests/golden/test_acquired_publisher_inputs.py)、[test_acquired_wiley_pdf.py](../tests/golden/test_acquired_wiley_pdf.py)、[test_acquired_ieee_inputs.py](../tests/golden/test_acquired_ieee_inputs.py) |
| IOP／arXiv 附件索引与远程链接、T&F 12 张原图及 Python／CLI／MCP 落盘 | [test_acquired_network_repair.py](../tests/golden/test_acquired_network_repair.py)、[test_tandf_lst_replay.py](../tests/integration/test_tandf_lst_replay.py)、[test_tandf_lst_render.py](../tests/golden/test_tandf_lst_render.py) |
| 付费墙识别与停止、正文 block 及非付费墙 XML 回退 | [test_acquired_paywall_inputs.py](../tests/golden/test_acquired_paywall_inputs.py)、[test_acquired_ieee_paywall_flow.py](../tests/golden/test_acquired_ieee_paywall_flow.py)、[test_reviewed_block_provider_paths.py](../tests/golden/test_reviewed_block_provider_paths.py)、[test_reviewed_copernicus_xml_blocks.py](../tests/golden/test_reviewed_copernicus_xml_blocks.py) |
| 本轮 API 权限、真实订阅 HTML、PDF 入口返回付费页及恢复成功证据 | [test_acquired_subscription_access.py](../tests/golden/test_acquired_subscription_access.py)、[test_pdf_document_acceptance.py](../tests/golden/test_pdf_document_acceptance.py)（正文文件身份、预览和补充材料拒绝，不做 PDF 解析质量断言） |
| 本轮完整资产集合、文件字节、真实 provider 下载与文章落盘链接 | [test_collected_asset_files.py](../tests/golden/test_collected_asset_files.py)、[test_annualreviews_complete_formula_assets.py](../tests/golden/test_annualreviews_complete_formula_assets.py) |
| 来源、文件大小和 SHA-256 登记审计 | [test_fixture_provenance.py](../tests/integration/test_fixture_provenance.py) |

## 文件与记录位置

- 当前案例和验收状态只更新本文，不再新增按日期、重试原因拆分的状态 Markdown。
- 样本原文、附件、成功及失败响应继续保存在 [golden_criteria](../tests/fixtures/golden_criteria/) 或 [block](../tests/fixtures/block/) 的对应 DOI 目录；规范见 [fixture README](../tests/fixtures/README.md)。
- 原始采集摘要集中保存在 [fixture-records/](fixture-records/)：保留既有日期文件名，其历史计数和单次请求结果不作为当前状态。文件内部的 `tests/fixtures/...` 路径相对仓库根目录。
- 提取规则与正式支持边界分别维护在 [extraction-rules.md](extraction-rules.md) 和 [providers.md](providers.md)。SAGE 不属于本清单的 19 个正式 provider。

## 内容缺陷修复与测试证据登记

本轮复用已有采集，不新增联网补采。PDF 身份不足且无有效标题的漏检已收紧；AIP 错误讲义在有／无／空白标题下拒绝，真实同篇 PDF 的 DOI 成功仍可通过。验收范围是文件身份和回退，不包括 PDF 转换质量。

OUP `btaa161`、`btaa823` 的完整表下注释已有独立原文、顺序与最终渲染断言；Science `sciadv.adl6155`、`sciadv.adm9732`、`science.ade0347` 的独立可用性声明已有原文、链接、分类及单次渲染断言，见 [正式回归](../tests/golden/test_retained_publisher_notes.py)。仅更新被局部修复影响的 exact 基线。

全仓测试分类见 [测试证据清单](../tests/test-evidence.json)，来源事实仍由唯一 fixture manifest/provenance 维护。清单区分真实内容断言、机制契约和基础设施检查；`template_gap` 保留最初问题描述，最新判断及具体未覆盖范围以 `template_review` 为准。占位图片、手写片段、错误注入和派生快照不会因同测试读了真实 HTML 就取得真实下载或原文覆盖资格。IEEE PGEC acquisition 的来源只覆盖对应资产，旧 synthetic 文件未提升。

自动检查覆盖测试收集与实际读取，缓存命中继续传播原始证据；断言语义仍需要人工审阅。完整测试通过不代表所有论文逐字审阅，也不代表 PDF 转换质量验收。

来源检查发现并纠正了 Annual Reviews 两篇旧 `body_assets` 中 9 个 67 字节占位图的默认真实分类：逐资产标为 `synthetic`，保留定位机制用途；代表图片与 provider 下载回归复用已有同篇 acquisition 原图。不能再把这些占位图算作真实下载证据。另三篇同结构 Science 样本（`sciadv.abj3309`、`science.abp8622`、`science.adp0212`）也补齐了独立声明原文断言；共 6 份 exact 仅增加可用性声明标记及节数，正文节数不变。

最终验证使用项目默认并行配置：完整 unit 2286 项通过，integration 117 项通过、4 项既有条件跳过，golden 948 项通过、1 项既有条件跳过。integration 跳过原因分别是缺少 Ghostscript、libvips、zsh，以及未启用原生 Camoufox gate；golden 跳过案例没有已验证的二进制文件，失败事实仍保留在 provenance。live 仅完成 32 项收集和分类，未执行外网请求。补强 OUP 表内脚注标记断言后，8 项 OUP／Science 原文回归再次通过；相关 Ruff 检查和 `git diff --check` 通过。本轮没有新增跳过。

### 102 条模板缺口登记审阅

原有 56 个模块默认标记和 46 个用例覆盖标记已经逐条审阅。离线阶段剩余 17 条具体缺口，首次联网补强后剩余 9 条；后续按用户要求补采、删除无依据分支，并以真实 Springer 布局和摘要页 PDF 回退为准。用户确认保留 Science 恢复机制及作者 pipeline 的限定真实依据后，当前待补采登记为 **0 条**。原始标记保留供追溯，`template_review` 记录人工判断、断言范围、真实回归及机制边界。

| 原始登记范围 | 明确为机制契约 | 已绑定限定范围的真实回归 | 仍有具体缺口 |
| --- | ---: | ---: | ---: |
| 56 个模块默认标记 | 22 | 34 | 0 |
| 46 个用例覆盖标记 | 31 | 15 | 0 |
| 合计 | 53 | 49 | 0 |

“已绑定”只证明各条 `scope` 指明的内容；同模块的故障注入、阈值、并发、优先级仍是机制测试，不会随之获得真实来源分类。53 条机制项说明其可控输入为何必要，不冒充 53 份新原文；其中 Science 同图挑战恢复按用户决定保留设计并接受真实链路 fixture 缺失，不计为真实覆盖。作者备用分支按下述限定范围绑定真实回归，其余已接受的机制分支仍无逐分支真实证据。49 条已绑定只覆盖保留下来的断言范围；删除分支属于产品范围收敛，不能记为补采了对应原文。

实际补强包括：OUP 九张完整 JPEG、AMS 图二与表一、Annual Reviews 五张 PNG、新 Nature 五张原图，通过同篇来源匹配、真实字节下载与最终链接替换原先占位路径/文件。新 Nature 回归采用真实 `s43247-024-01295-w`，旧 synthetic 样本未改标。Science `adz3492` 原有 SVG 已补 DOM 图入口、完整 SVG 字节和最终链接回归；unit 改为最小 SVG 协议输入。旧采集 SVG 的 HTTP200 仍明确为注入 envelope，不补造历史响应。

原文回归另外发现并修复两处局部缺陷：AIP `5.0188905` 的 `.fig-modal` 副本导致图一、图五完整图注重复，现于 AIP DOM 清理阶段删除弹窗副本；arXiv `2606.00587v2` 原始 TeX 的两个 `extdatafigure` 被遗漏，现同 `figure` 一起发现，保留 `extdatacaption`、标签与七张图的原始路径/字节。两项均有先失败后通过的原文断言，不涉及 PDF 输出清洗。

联网补采的完整响应、失败条件及判断见[机器记录](fixture-records/fixture-template-gaps-2026-09-16.json)，来源事实仍归唯一 manifest/provenance。新增回归见 [test_online_template_evidence.py](../tests/golden/test_online_template_evidence.py)：

- arXiv `2605.06556v1` 改用真实同版本源码归档和 40,866 字节原图；缺失 `src` 仍明确为错误注入，不能宣称远端原文曾自然缺图。源码 preview 升级与原始字节对照为内容回归。
- 旧 Nature `nature13376` 的四张正文原图、四份表格页、四张 extended-data table JPEG 已采集并用于 provider 提取、下载和最终位置回归。另两篇 Nature 验证真实可展开 Box 原文、图片型 Box 标题与原 PNG；实际发现的公式误绑定、重复正文图及图片型 Box 丢失已局部修复。原始资产图注仍保留完整描述。
- Science `science.abo2812` 的原生 DOM 含致谢区粗体纯代码声明，已验证原文、CodeOcean 链接、`code_availability` 分类和只渲染一次，不增加正文充分性。
- IEEE `TBME.2024.3434477` 复用历史真实 REST 原文：表三 alt 含 `Equation`，确实进入公式和表格两种候选，二者使用相同 preview。新增回归验证表格优先级、原图注与最终单一资产；这不是新的在线全文授权证据。

后续精确决定与 19 个候选的实际观察见[路由收敛记录](fixture-records/fixture-route-removals-2026-09-16.json)。本阶段：

- ACS：删除缺原图时访问 `view-large` 的额外回退；保留有原文依据的 `DownloadImage` 解包装。纠正此前把独立 viewer 直链当成文章直链的错误判断。
- Royal：复查全部已登记原文，`rsos.150470`、`rsos.201188`、`rspb.2020.0097` 的部分 figure 缺少匹配原图，不符合“有直链才删除”的条件。因此保留其缺原图时的查看器发现和分组 slide 同图校验；新增实际查看器与原图响应回归，不以邻图原图代替当前图。
- arXiv：审阅 14 份真实 HTML 资产，其中 8 份有 `ltx_*`，未见包含 article 却无 ltx 的全文样本；删除未经验证的通用标题、摘要、参考文献猜测分支及对应测试，不宣称证明所有历史网页均无例外。
- PNAS：按用户明确要求，删除原图失败后下载 preview、以及仅有 preview 时下载的功能和两项成功测试；保留原图与浏览器原图恢复。新增负向回归检查串行和普通路径不请求 preview。Annual Reviews 的图页回退继续保留。
- Springer：检查 19 个新旧候选，保存 4 份已核对 DOI 的代表原文。最新提前发布页只有摘要；2018 原文证明无 section 正文块顺序，2018–2019 原文证明正文、Reporting summary 与 Data availability 顺序。原手写 scenario 的直接子节点实际为 section，已纠正此前“裸 p”的错误登记。
- Science：第三次及用户追加的第四次观察均导出同图 4325×2111 PNG。第四次先请求相同原图再打开浏览器，原图仍为 HTTP200；文章导航先 403 再 200。两种图片字节和响应事实分别登记，不能以文章 challenge 代替图片 challenge；追加记录见路由收敛记录的 `science_additional_retry`。

Springer 两条按用户确认的真实范围收口：待刊页只有摘要时验证 HTML 拒绝验收，并经直接与 prepared 两条入口进入 PDF 候选流程，保留目标 DOI、标题及原文 PDF 地址；回归在 PDF 获取边界注入中止，不声明 PDF 下载成功或转换质量。正文排列使用真实 2019 原文替换手写同级排列测试，断言 Reporting summary 位于 Methods 内、Data availability 位于 main-content 外，提取及最终渲染均保持该顺序和原文。原手写资产保留历史来源分类，不再作为待补采模板；通知与充分正文的人为组合仅保留为优先级机制测试。

作者 pipeline 按用户确认保留结构，新增 [7 项真实作者回归](../tests/golden/test_original_author_branches.py)：

| 真实样本 | 可以证明的范围 |
| --- | --- |
| arXiv `2605.06556v1`、`2605.06653v1` | 原文自然进入 person-names 回退，姓名与顺序准确。 |
| Wiley `2004GB002273`、Springer `s41467-019-11472-7`、Science `sciadv.abf8021`、PNAS `2309123120` | 首选与备用作者结构共存，分别提取相同的原文姓名；不证明首选自然缺失。 |
| Nature `nature13376` 表一页面 | 表格子页缺少 author meta，实际进入 JSON-LD；不算正文页自然回退。 |

真实回归发现 Springer DOM 选择器同时提取姓名节点和带单位序号的外层 li，30 位作者变成 47 条。现仅在 Springer 中让 li 复用内层姓名节点，通过既有去重去掉重复项，pipeline 和 selector 顺序不变。

Wiley JSON-LD、AMS 备用选择器、IEEE 姓名／容器形状及其余未绑定原文的分支仍仅为机制契约。Science 同图挑战恢复仍无真实链路 fixture。**待补采登记为零是按用户接受的验收范围收口，不代表全部分支已获真实证据。**

收集检查拒绝缺少审阅、失效回归引用、用机制测试冒充内容证据、无证据却标记 covered，以及状态与 remaining 冲突。子 pytest 验证这些失败条件；即使 covered 引用自身测试，synthetic 主证据仍会被实际读取检查拒绝。链接有效不等于断言语义等价，后续增加用例仍须审阅范围。

离线审阅阶段验证（项目默认并行）：完整 unit **2291 passed**，完整 integration **124 passed、4 skipped**，完整 golden **951 passed、1 skipped**；live 仅收集 **32** 项。integration 的 Ghostscript、libvips、zsh 和原生 Camoufox gate 条件跳过，以及 golden 旧 Wiley 采集记录无合格二进制的跳过均维持原状，未新增跳过。ACS 查看器断言补强后，相关两项原文回归另行通过。相关 Ruff、格式检查及 `git diff --check` 通过；无需更新 exact 基线。该离线阶段没有联网补采；两阶段均未改动版本或依赖、提交或触发 CI。

首次联网补采阶段历史验证（项目默认并行）：unit **2293 passed**，integration **124 passed、4 skipped**，golden **956 passed、1 skipped**；live 仅收集 **32** 项。相关 8 个 Python 文件的 Ruff 与格式检查、`git diff --check` 通过；无需更新 exact 基线。精确结果和跳过原因见上述机器记录。网络采集在显式的补采操作中完成，未执行 live 测试请求。保持既有条件跳过，未用新增 skip 隐藏剩余 9 条证据缺口。

用户追加删除／补采阶段最终验证（默认并行，包含 Royal 回退保留及真实查看器回归）：unit **2295 passed**；integration **124 passed、4 skipped**；golden **964 passed、1 skipped**。新增 8 项原文回归全部通过；live 仅收集 **32** 项、未执行联网请求。上述 5 项既有条件跳过不变。相关 17 个 Python 文件的 Ruff 与格式检查、`git diff --check` 通过；macOS 契约静态验证和 Linux portable 6 项测试通过，不替代原生 macOS gate。无需更新 exact 基线。详细结果见[路由收敛记录](fixture-records/fixture-route-removals-2026-09-16.json)。未修改版本、依赖、公开 CLI/MCP 接口或 PDF 输出；未提交或触发 CI。测试通过仅验证声明范围，不表示所有论文逐字审阅，也不表示 PDF 转换质量验收。

Springer 真实范围收口的本次验证（默认并行）：相关 golden **25 passed**，HTML 验收与来源策略检查 **59 passed、1370 subtests passed**；全仓含 live 仅收集 **3421** 项，未执行 live 联网请求。两份改动 Python 文件的 Ruff、格式检查与 `git diff --check` 通过，无新增跳过。结果见[路由收敛记录](fixture-records/fixture-route-removals-2026-09-16.json)中的 `springer_scope_followup`。本次只调整测试、登记和说明，生产代码未改，未重跑完整三套测试；上段全量结果保留为此前验证记录。

Science 第四次同图观察的新增采集与回放验证：默认并行 **14 passed、1368 subtests passed**；Ruff、格式及差异检查通过，无新增跳过、未改生产代码。先直连再浏览器的实际时序由原始采集时间断言，HTTP200 与 canvas 成功分开登记；随后用户明确保留设计，该项归入机制契约并退出待补采清单，仍注明没有真实同图挑战恢复 fixture。

作者结构保留与真实依据绑定的最终验证（默认并行）：unit **2295 passed**；integration **124 passed、4 skipped、1412 subtests passed**；golden **973 passed、1 skipped**；live 仅收集 **32** 项。新增作者原文回归先出现 1 项 Springer 重复作者失败，局部修正后 7 项全通过；完整测试没有新增跳过，沿用上文的五项既有环境／历史资产条件。相关 Ruff、格式检查和 `git diff --check` 通过，未刷新 exact 基线、未改版本或依赖、未提交或触发 CI。最新结果见路由收敛记录的 `author_structure_decision`。

## 2026-09-16：151 项 canonical 原文内容审阅

本节是新增的离线逐篇审阅，取代前文历史阶段“151 项 exact 全面内容审阅不在范围内”的范围说明。没有新增网络采集。逐项路径、原文 SHA-256、来源选择、各维度计数、断言位置及证据限制见 [151 项审阅登记](fixture-records/canonical-content-review-2026-09-16.json)。集合严格为 **151 项：106 HTML、31 XML、14 PDF**；登记完整性与原文选择计数均由测试固定，不能通过缩小选择范围掩盖遗漏。

137 项 HTML/XML 在现有 [canonical golden 模块](../tests/golden/test_golden_corpus.py) 中逐篇检查作者名单及顺序、完整已捕获参考文献正文与 DOI、正文和附录段落顺序、全部已捕获图注、数据表单元格及脚注、数据／代码声明。预期仅从原始 DOM/XML、原始元数据及明确人工核对的作者块取得；共享辅助代码放在 [tests/support/canonical_content.py](../tests/support/canonical_content.py)，不从提取结果生成内容预期。

数字和表格符号不依赖去标点的文本比较。TeX 另查保留上下标、分式、分组与换行结构的原文表达式；MathML 另查数字内容、标识符、关键运算符及上下标、分式、根式的结构事实。引文目标按原文 ID 对应到同一顺序的输出参考文献与 DOI。图片将最终链接追溯到原文 URL／同一图片的 rendition 文件名，并逐图对应到自身 DOM 或同页查看器条目；已有真实文件的哈希、字节及本地最终链接继续由原有采集集合和 provider 回放检查。IEEE canonical 不再生成 GIF 占位文件，Annual Reviews 不再按序号把旧占位 PNG 当作下载成功；有捕获响应时绑定真实文件，其余保留原文远程链接。

14 项 PDF 分别检查目标身份、正文角色、可读取页数／完整结构及 provider 组装；将现有转换器实际返回的文本视为不透明内容，确认正文与最终输出原样保留。此测试不评价 `pymupdf4llm` 的排版、公式、引用或 OCR，也不修改其输出。历史未知 HTTP 状态和最终 URL 仍保持未知。

本次修复与合并：

- PDF 标题回退拒绝短于完整规范化目标标题的开头文本，保留 DOI 优先级、20 字符下限和 92 分阈值；覆盖失败清理及下一候选继续。
- 共享引用候选验证统一 URL 解码及旧式 SICI DOI；T&F、AMS、MDPI、共享 HTML 路径复用，Springer 删除重复的整页解码。保留出版社候选优先级、编号规则及 OUP 的 ISSN 排除。原文还证明 MDPI、Royal、Wiley 链接 DOI 和 Elsevier 文字引用、书籍版次／出版社、电子页码、作者后缀、备注与网页链接字段需要保留。
- 门禁身份复用 HTML 元数据解析，保留 IEEE 内嵌元数据与文章编号，明确请求身份优先。原有三个检查时点不变，同一请求只缓存相同 HTML 输入的检测结果，每次仍检查最新 diagnostics。
- 链接／强调保留通过显式启用的 inline token helper 实现；用于 OUP 表注、Science 声明以及同类已定位保留内容，普通正文默认行为不变。
- 原文驱动的局部修复包括 arXiv 作者拼写变体重复与遗漏 TeX；MDPI 数据声明、缩略语、附录表格位置和嵌套表注；ACS 拆分表格的后半段及表注；Annual Reviews 科学章节层级与图注 “Top”；Elsevier 科学 “Metrics” 章节；T&F 独立 highlights 和真实重复句；Royal 空单元格；PNAS 方程引用；IEEE 科学图注；Science 正文开头照片；JATS 图注标题和列表内显示公式；MathML 带编号矩阵与表格字面星号。

仅更新 **9 项**已有独立原文断言证明正确的结构基线：MDPI 六篇的数据声明／附录／缩略语，Annual Reviews 神经科学文章的父章节，Elsevier 的科学 Metrics 章节，以及 T&F 的独立 highlights。其他 `expected.json` 保持原有结构契约；不把结构快照或“已登记”当作内容验收。

证据限制继续逐篇公开：IOP 引用只有捕获的元数据字段；IEEE RITA 未捕获参考文献集合，零捕获不等于原文没有参考文献。MathML 数字和结构事实不是全部表达式的 AST 等价证明，位图公式不做 OCR；普通段落／图注文本归一化不证明全部排版标点等价。引文测试证明原文目标与输出书目的对应，所有最终 inline anchor 的完整结构仍只有出版社专项案例覆盖。没有真实图片文件的维度只认原文索引与链接，附件只验同篇索引／链接；没有新增 skip，也没有把这些限制改记为完整内容验收通过。

本轮最终验证（项目默认并行）：完整 unit **2333 passed、366 subtests passed**；integration **124 passed、4 skipped、1412 subtests passed**；golden **2511 passed、1 skipped、33791 subtests passed**。来源审计及测试证据登记检查 **26 passed、1368 subtests passed**。相关 43 个 Python 文件的 Ruff、格式检查及 `git diff --check` 通过；macOS 静态契约和原生 Linux portable **6 passed**，不替代原生 macOS gate。五项既有环境／历史资产跳过维持原状，没有新增 skip。逐篇通过范围以登记中的维度、原文计数和限制为准。本轮未联网补采、未新增依赖、未改版本、未提交、未发布或触发 GitHub CI。


## 2026-09-17：离线修复科学语义与对象对应断言

本次不联网补采，继续复用 151 项 canonical 样本（137 HTML/XML、14 PDF）。修复前确认 PNAS 7 篇的 325 个、Science 5 篇的 43 个 MathML 节点因占位 `alttext` 同时绕过 TeX 与 MathML 检查；现共 368 个节点进入 MathML 检查。逐篇登记新增 `formula_audit`，分别核对选中公式、TeX 检查、MathML 检查与无文本节点的明确排除数量。没有公式的样本不冒充执行过公式断言。

`_words` 仅保留粗略文字定位用途。canonical 正文、图注和表注另用保留小数点、符号、大小写及科学上下标的比较；表格保留上下标归属、分式／根式参数边界，并归一化明确的 Unicode、HTML 和 TeX 等价表示。负向控制验证空输出、删除公式、数字和上下标变化、分式分组变化、图片错配、表格缺失与整表移位；错误注入在证据清单中仍登记为机制测试。

数据表在独立输出表块中检查行列、表头与对应表注，不允许跨表重复消费相同行。Elsevier 集中存放的 XML 表按正文调用点和列表边界核对，MDPI 主文图库与附录使用既有渲染顺序。图注绑定自身来源图片或原文多面板父图组；可辨识图号保留，显式 inline 资产还检查已有正文邻接锚点。单列表格、语义列表、无可用邻接段落、独立图库及既有尾部资产布局不宣称取得全部原位证据；共享面板组也不等于逐面板几何排版验证。MathML 仍是结构事实检查，不是完整语法树等价；位图公式和表格仍不做 OCR。

严格断言同时发现并修复 provider 局部问题：Royal Society 的科学上下标及图注、MDPI 摘要、Science/Wiley 标题、OUP 表内 MathML、Annual Reviews 链接内脚注、Taylor & Francis 布局列表的行内语义，以及 Elsevier 将附录 Table 1 误当主文 Table 1 提前插入的问题。没有修改 PDF 转换输出、浏览器策略、公开 CLI/MCP 接口或依赖，未新增 skip，也未用派生快照生成原文内容预期。

完整回归另发现 4 项历史专项断言固化了原有格式丢失：OUP 表头的带帽 χ、PO 下标与平方，Annual Reviews 表注上标，Royal Society 的 F 上标 III，以及 T&F 列表中 X 的斜体。核对原始 HTML/MathML 后更新这些专项预期，原始 fixture 和 `expected.json` 均未因本轮修改。

本轮最终验证（项目默认并行）：完整 unit **2353 passed、366 subtests passed**；完整 integration **124 passed、4 skipped、1412 subtests passed**；完整 golden **2516 passed、1 skipped、34159 subtests passed**。新增比较及真实损坏输出控制 **25 passed**；最后的表格无邻接锚点分支与 Elsevier 专项复验 **48 passed、358 subtests passed**。相关 19 个 Python 文件的 Ruff、格式检查与 `git diff --check` 通过。既有五项条件跳过不变；未联网补采、未改版本、未提交或触发 CI。以上结果只证明本节明确的检查范围，不扩大为全部模板或完整公式语义的覆盖声明。
