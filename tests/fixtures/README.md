# Fixture conventions

当前样本、来源选择、资产与预期由 [manifest](golden_criteria/manifest.json) 和对应
DOI 目录管理；[fixture catalog](../fixture_catalog.py) 提供测试读取入口。
测试命令、分层和台账维护统一见 [测试说明](../README.md)。本文只定义来源证据约束，
不维护第二份覆盖清单、逐函数分类表或历史审计文件索引。

## 目录与来源

| 目录 | 用途 |
| --- | --- |
| `golden_criteria/<doi_slug>/` | 已登记的正例、原始响应、expected 与回放资产 |
| `block/` | manifest 中 `fixture_family=block` 的真实付费墙、摘要页、空壳及拒绝响应 |
| `golden_criteria/_scenarios/` | 最小规则场景、来源片段或明确标为 synthetic 的机制输入 |

目录不自动证明来源类型。`assets` 是唯一文件清单；可选 `asset_origins` 按已有 asset key
覆盖样本默认来源。未知 key、同路径的冲突来源都应拒绝。可执行回放数量来自
`golden_corpus_replay_inventory()`，不把 manifest-only 输入或 synthetic scenario 算成论文。

| Origin kind | 可证明的范围 |
| --- | --- |
| `real_replay` | 真实文章的原始响应或捕获的 browser DOM；仍须检查身份与 acquisition |
| `real_excerpt` | 从真实来源直接裁取、可追溯的片段；改写文字和生成 Markdown 不属于原文 |
| `contract_scenario` | 已登记的最小机制契约，不证明整篇文章的真实性 |
| `synthetic` | transport/cache/config/service/MCP 等基础设施或局部机制 |
| `unverified` | 尚未核验的历史来源，不能计入真实内容覆盖 |

来源标签是声明，不是联网获取证明。当前拒绝与撤回事实位于 manifest 的
`rejected_sources` / `withdrawn_assets`；不能通过改名或修改标签把已拒绝字节提升为真实原文。
捕获的 challenge 或 abstract 页面是真实字节，但不是全文证据。

## 内容与机制边界

- 内容测试的 primary input 必须是 `real_replay` 或直接 `real_excerpt`；手写、改写正文及
  derived snapshot 不能代替原文。snapshot 只作为辅助预期。
- unit 只用最小片段、现有 contract scenario 和边界 mock；完整原文、资产集合及整篇
  构建放在 golden，真实进程与浏览器契约放在 integration。
- publisher DOM、正文顺序、对象归属、数值和上下标断言必须有对应原文支撑；基础阈值、
  参数、状态及错误分类使用最小机制输入即可，不为每个机制制造整篇论文。
- PDF 只验证获取、合法访问、真实文件及身份/完整性、来源、落盘与转换输出透传。
  标题、页眉页脚、引用、公式、表格、OCR 和排版质量不属于 fixture 补齐或验收目标；
  任何层都不得在现有 `pymupdf4llm` 输出上清洗或修复。见
  [PDF 转换边界](../../docs/extraction-rules.md#rule-pdf-conversion-boundary)。

HTML/XML 回放 metadata 只使用已声明的书目标题。`GoldenCorpusFixture.title` 的 DOI
fallback 仅用于展示，不能进入可信 metadata；缺失题名可由既有源解析器补齐，否则
保持缺失。源 DOI 与目标冲突时须在转换前拒绝。对应回归见
[来源标题测试](../golden/test_replay_source_titles.py)，PDF metadata 沿用原契约。

## 采集与逐资产证据

- 原始 HTML/XML 和 acquisition 文件保留上游字节及空白；Git attributes 禁止对这些
  带 hash 输入执行 checkout 换行转换。来源 URL、时间、状态/MIME、SHA-256 与实际
  响应分开记录；新增采集不改写旧失败响应或 synthetic 来源。
- Browser DOM、HTTP entity 和 canvas export 使用不同 capture kind。canvas 导出
  不捏造 HTTP 状态；direct 图片成功也不能证明 challenged-HTTP 的 browser recovery。
- 捕获 HTML 不会自动认证图片字节。资产断言必须声明 `asset` primary role 并实际读取
  资产；只读取正文不能满足资产证据要求。源码包使用真实容器扩展名，归资产证据。
- 同一样本、同来源分类的重复字节可由 manifest 指向保留实体；每次采集的 provenance
  仍独立，`body_file` 指向实体，`original_body_file` 保留合并前名称。
- 图片回放复用 `tests.support.captured_images.download_captured_images`，核对登记的
  SHA-256、尺寸及响应。URL 默认精确匹配；仅既有 Silverchair provider 的签名回放忽略
  已知过期签名参数，保留对象、尺寸及其他 query。它证明存储/本地化，不证明候选顺序。
- 文章图片包装 URL 与独立 viewer 直链分别核验，不能互相代替。临时 token、cookie 和
  原始挑战脚本不得作为论文原文入库；按既有脱敏边界保留诊断、hash 和尺寸。

## 测试台账与实际读取审计

`tests/test-evidence.json` 使用 v2 模块默认分类，仅不同契约的测试写 `overrides`。
新增普通测试继承模块默认，无需逐函数登记；失效模块、override 或跨模块引用由
`test_evidence_ledger_integrity` 检查。声明中的 `scope` 和 primary roles 描述断言范围，
不能靠改标签绕过证据要求。

历史 `template_gap` 仍需 `template_review={status,scope,evidence_tests,remaining}`：
`mechanism` 仅证明局部机制，`covered` 关联该范围的离线内容测试，`partial` 列出具体缺口。
只有 `partial` 可有非空 `remaining`；引用须指向已登记的内容测试，不能用机制或 live
测试代替。review 不改变测试 kind 或资产来源。

`tests.support.test_evidence` 审计收集、fixture、模块加载、参数化、实际文件读取与共享
缓存；`evidence_cache` 和跨 worker 的 golden cache 必须传播 read set。审计证明使用了
哪些来源，不能判断断言含义或证明逐字验证。live 声明 `live_response`，离线文件审计
不会认证线上响应；收集 live 测试也不代表执行过 live。
