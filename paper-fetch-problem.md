# paper-fetch 使用与契约问题清单

## 1. 文档目的

本文汇总当前 paper-fetch-skill 在真实使用、CLI/MCP 参数语义、缓存、批量执行、浏览器 provider、结果验收、资产质量、文档和自动化测试方面发现的全部问题，并给出建议修复方向。

审计基线：

- 审计日期：2026-07-10
- 当前本机 CLI 版本：paper-fetch 3.0.1
- 当前 Codex 可见 MCP 工具数：8
- 当前 runtime provider 数：19
- 审计方式：只读检查当前 SKILL.md、references、CLI 帮助、MCP schema、已安装 Python 实现，以及历史 paper-fetch 使用记忆

历史记忆中的文件数和成功数是当时快照，用于识别稳定的失败模式；它们不应被解释为当前 papers 目录的实时状态。

## 2. 总体结论

当前 paper-fetch 的主要瓶颈已经不是“能否抓到论文”，而是以下四个方面：

1. 交互门过重：本来可以自动完成的任务被保存确认和 CLI 选择反复阻塞。
2. 参数语义混乱：不保存、不落盘、只缓存、本地归档在 CLI 和 MCP 中不是同一组参数。
3. 缺少正式验收：status=ok、退出码 0、文件存在、图片非空都不足以证明全文和资产真正成功。
4. 契约和文档漂移：关键文档断链、MCP schema 过弱、provider 说明重复且占用大量上下文。

建议把工作流重构为：

~~~text
解析与去重
  -> 精确检查本地文件和缓存
  -> 按任务意图选择读取、核验或归档路径
  -> 仅在需要时检查 provider
  -> 抓取
  -> 文本、资产、输出和溯源四层验收
  -> 输出可复用报告
~~~

## 3. P0：必须优先解决的问题

### 3.1 缺少强制的抓取后验收步骤

当前问题：

- SKILL.md 的正式流程在“抓取”后直接结束。
- 只有当用户后来发现问题并追问时，代理才会检查 Markdown、图片和 warnings。
- 批量命令成功不等于最终产物满足任务要求。

历史证据：

- 一次 36 篇批量抓取中，36 条记录均为 status=ok、36 个 Markdown 均非空，但仍有 14 条记录带有降级 warning。
- 某条 JSONL 一度显示 metadata-only，而后来最终 Markdown 已是 fulltext。
- AMS/BAMS/JHM 的 Markdown 文本完整，但多个 Blank 图片具有相同大小和哈希，实际是占位图。
- Wiley 的 preview 图片属于资产质量降级，而不是全文抓取失败。

影响：

- 用户必须继续追问“成功了吗”“图片成功了吗”。
- 代理容易把 fetch 成功、全文成功、图片成功混成一个布尔值。
- 下游文献阅读可能基于仅摘要、缺图或语义受损的内容而不自知。

建议：

增加强制的第 4 步“验收与报告”，至少输出以下四级状态：

1. 完整成功
2. 文本成功，但资产、表格或公式降级
3. 仅摘要或元数据
4. 失败、歧义或需要用户处理

每篇论文至少分别记录：

- identity_status：论文身份是否唯一、DOI 是否匹配
- fetch_status：工具调用是否正常完成
- content_status：fulltext、abstract-only 或 metadata-only
- asset_status：完整、preview 降级、部分失败、占位图或未请求
- output_status：Markdown、JSONL 和资产路径是否存在且非空
- provenance_status：source、source_trail、fallback 和 warnings

### 3.2 保存决策的 BLOCKING 门过重

当前问题：

- 只要任务涉及保存，而保存位置或图片策略有一个未明确，SKILL.md 就强制暂停。
- 即使仓库已经有稳定的 papers 约定，也不能依据项目上下文继续。
- “是否下载图片”被强制作为每次保存都必须询问的问题。

影响：

- 单篇归档也会产生不必要的额外往返。
- 用户已经说“抓取到 papers”时，代理仍可能继续询问可合理推断的信息。
- 项目级长期约定没有被利用。

建议：

- 只有当保存位置确实存在多种合理选择时才阻塞。
- 在 /home/dictation/drought_prediction 和 /home/dictation/pshed 中，优先使用项目根目录 papers 作为项目配置默认值。
- 当前目录只是 /home/dictation、无法确定目标项目时，再询问目标仓库。
- 用户未要求图片时，显式使用 asset_profile=none，并在结果中说明没有归档正文图片。
- 用户明确说“下载正文图片资源”时，直接使用 body，不再重复确认。
- 用户明确要求补充材料时，才使用 all。

### 3.3 CLI 分流不应成为用户必须选择的 BLOCKING 门

当前问题：

- SKILL.md 规定通常在 3 篇及以上时，必须先建议 CLI，并等待用户选择“CLI”或“代理直接抓取”。
- CLI 是执行后端，不是通常需要用户承担的产品决策。
- 用户已经授权批量归档后，代理本可直接运行 CLI。

影响：

- 批量工作流至少多一轮对话。
- “提高效率、节省 token”被错误地设计成用户选择题。
- 与代理应自主完成正常实现步骤的工作方式冲突。

建议：

- 批量归档默认由代理直接使用 CLI。
- 只在用户明确禁止 CLI 时切换到 MCP 或逐篇处理。
- commentary 中说明将使用 CLI 即可，不需要暂停。
- 真正保留 BLOCKING 的情况只包括：
  - 论文目标有多个候选；
  - 需要人工登录、授权或浏览器验证；
  - 可能覆盖或替换已有成果；
  - 用户选择会实质改变产物；
  - 外部付费、账号状态或合法访问边界需要用户决定。

### 3.4 “不保存”不等于“不落盘”

当前问题：

- SKILL.md 把 save_markdown=false 描述为普通阅读默认不保存。
- MCP 当前默认仍是 no_download=false 和 artifact_mode=markdown-assets。
- 因此即使没有保存最终 Markdown，也可能写 provider artifact、资产或 fetch-envelope sidecar/cache。

影响：

- 用户以为是临时阅读，实际可能在默认数据目录产生文件。
- 代理无法清楚解释哪些产物是用户归档、哪些只是工具缓存。
- cache、artifact、Markdown 和图片的生命周期混在一起。

建议建立三个明确预设：

| 预设 | 目标 | MCP 建议参数 |
|---|---|---|
| 临时阅读 | 尽量不落盘 | save_markdown=false, no_download=true, strategy.asset_profile=none |
| 可缓存阅读 | 不建立用户归档，但保留可复用 cache | save_markdown=false, no_download=false, artifact_mode=none, strategy.asset_profile=none |
| 本地归档 | 保存 Markdown 和指定范围的资产 | save_markdown=true, no_download=false, artifact_mode=markdown-assets，显式指定目录和 asset_profile |

任何预设都不应依赖隐式默认值。

### 3.5 CLI 与 MCP 的保存参数不能共用一套解释

当前问题：

- CLI 的 --no-download 实际是 --artifact-mode none 的别名。
- CLI 即使使用 --no-download，显式 --output、--output-dir 主输出或 --save-markdown 仍然可以写文件。
- MCP 的 no_download=true 重点禁止 provider payload、资产和 fetch-envelope sidecar。
- MCP 的 artifact_mode=none 仍可保留 envelope cache。
- CLI 的 --output-dir 本身会写主 Markdown；--save-markdown 是额外保存步骤。
- SKILL.md 当前把“保存 Markdown”机械映射为 save_markdown=true，没有充分区分执行面。

影响：

- 相同自然语言意图在 CLI 和 MCP 中可能生成不同产物。
- 代理可能重复保存 Markdown，或错误地声称完全没有落盘。
- 用户选择“不下载资产”时仍可能因为 CLI 默认值而下载正文图片。

建议：

- 单独维护“CLI 保存矩阵”和“MCP 保存矩阵”。
- CLI 批量归档使用 --output-dir 作为主 Markdown 输出，不把 --save-markdown 当作必选。
- 每次 CLI 调用都显式传入 --artifact-mode 和 --asset-profile。
- MCP 每次都显式设置 save_markdown、no_download、artifact_mode 和 strategy.asset_profile。
- 对“无任何写盘”的承诺增加临时目录测试，不能只根据参数名推断。

### 3.6 CLI 的 asset_profile 隐式默认会造成意外图片下载

当前问题：

- 当前 CLI 的 --asset-profile 默认值实际是 body。
- cli-fallback.md 没有写明这个默认值。
- SKILL.md 的简单批量示例没有显式指定 --asset-profile。

影响：

- 用户没有要求图片时也可能下载正文图片、表格或公式资产。
- 批量任务的时间、带宽和磁盘开销超出预期。
- 与“缺失图片策略必须先询问”的严格门形成矛盾：流程要求确认，但示例却依赖会下载图片的隐式默认。

建议：

- 所有 CLI 示例强制显式写 --asset-profile none、body 或 all。
- 普通文本归档默认 none。
- 只有明确要求正文图时使用 body。
- 只有明确要求补充材料时使用 all。

### 3.7 status=ok 和退出码 0 不能代表全文成功

当前问题：

CLI 批量 JSONL 成功项当前主要包含：

- index
- query
- status
- doi
- source
- output_path
- saved_markdown_path
- warnings
- error

但缺少：

- has_fulltext
- content_kind
- has_abstract
- token_estimate
- table semantic loss
- asset quality
- fallback classification
- 输出哈希和完成时间

影响：

- status=ok 只说明没有抛出运行时异常。
- metadata-only 也可能被写出非空 Markdown。
- 无法只靠 JSONL 回答“是否全文成功”“图片是否可用”。

建议：

扩展批量 JSONL，至少加入：

- schema_version
- tool_version
- run_id
- started_at 和 completed_at
- has_fulltext
- content_kind
- has_abstract
- warnings_class
- fallback_class
- table_layout_degraded_count
- table_semantic_loss_count
- asset_requested
- asset_total
- asset_full_size
- asset_preview
- asset_failed
- placeholder_suspected
- output_size
- output_sha256

## 4. P1：高价值流程优化

### 4.1 固定“3 篇使用 CLI”的阈值过于机械

当前问题：

- 三篇精读比较和三十篇批量归档被同一阈值处理。
- 是否使用 CLI 更取决于产物类型、是否保存、是否需要恢复和是否要在上下文中直接阅读，而不是纯数量。

建议按任务路由：

| 任务 | 推荐路径 |
|---|---|
| 单篇或少量精读、问答 | MCP fetch_paper |
| 结构化字段提取 | MCP，仅请求 article |
| 书目身份解析 | batch_resolve |
| 批量低成本可读性分诊 | batch_check(mode=metadata) |
| 批量归档到本地 | 代理直接运行 CLI |
| 大于 50 条的 MCP 分诊 | 分块处理并保留统一索引 |

### 4.2 工作流顺序倒置

当前问题：

- 现在先完成保存映射和 CLI 选择，之后才处理标题歧义、batch_check 和解析。
- 一组引用可能包含重复 DOI、无效条目和歧义标题，但流程在去重前就决定执行后端。

影响：

- 原始数量会误导 CLI 分流。
- 一个歧义标题可能拖住整批任务。
- 无效或重复条目会被不必要地抓取。

建议顺序：

1. 解析输入格式。
2. 对 DOI/URL 规范化。
3. 对标题使用 resolve_paper 或 batch_resolve。
4. 按规范化 DOI 去重。
5. 只对歧义条目请求用户选择。
6. 对唯一目标执行缓存检查或 batch_check。
7. 最后选择 MCP 或 CLI。

### 4.3 严格全局串行与批量并发相互矛盾

当前问题：

- SKILL.md 宣称整个工作流必须严格串行，否则算执行失败。
- CLI 和 MCP 批量工具又明确支持并发 1 到 8。

影响：

- 代理可能因为“严格串行”而放弃安全的跨论文并发。
- 或者使用批量并发时形式上违反技能最高优先级规则。

建议：

- 依赖阶段之间串行，例如解析必须先于抓取、抓取必须先于验收。
- 同一阶段内彼此独立的论文允许并行。
- 浏览器资产下载仍遵守 runtime 自身的串行约束。
- 将“全局严格串行”改成“阶段有序、项目内受控并发”。

### 4.4 批量并发应按 provider 自适应

当前问题：

- 示例常写 batch-concurrency 4。
- 历史中稳定验证值是 3。
- 浏览器 provider、限流 provider 和公共 XML/API 路线的最佳并发不同。

建议：

- 默认从 3 开始，而不是盲目最大化。
- 浏览器 provider 或高限流 provider 使用 1 到 2。
- 公共 API、XML 或 PDF 路线可使用 3 到 4。
- 预检后按 provider 分组执行。
- 遇到 rate_limited 时停止继续提交新任务，并遵守 retry_after_seconds。
- 在 run manifest 中记录实际并发。

### 4.5 batch_check 的语义没有被充分说明

当前问题：

- batch_check.mode 的真实允许值只有 metadata 和 article。
- metadata 模式的 has_fulltext=true 代表 likely_yes 探测，不代表已经抓取并验证全文。
- article 模式成本更高，不能被理解为普通轻量预检。
- 单次批量最多 50 条，但主技能没有强调分块策略。

影响：

- 代理可能把 likely readable 当作全文已获取。
- 可能为了简单书目核验触发昂贵的 article 模式。
- 超过 50 条时才在运行阶段遇到验证错误。

建议：

- 默认 batch_check(mode=metadata)。
- 报告字段使用 likely_readable，而不是 fulltext_verified。
- 只有需要真实内容判定时才使用 article。
- 大于 50 条时先分块，并在最终报告中重新合并原始顺序。

### 4.6 缓存策略不完整

当前问题：

- SKILL.md 只说多轮中调用 list_cached 或 get_cached。
- 已知 DOI 时调用 list_cached 会返回整个缓存索引，噪声大。
- get_cached 会返回同一 DOI 的 Markdown、primary payload 和多项资产。
- 抓取默认仍是 prefer_cache=false，检查缓存后未必真正复用。
- repo-local papers 与默认共享缓存属于不同 download_dir；不传相同目录可能互相看不到。
- fetch-envelope cache 是请求敏感的，已有缓存未必满足新的 modes、asset_profile、引用范围或 token 预算。

历史证据：

- 单篇 Wiley 论文的缓存查询出现了同一 DOI 的多项记录，最终需要回到精确 Markdown front matter 验证。

建议缓存决策树：

1. 先规范化 DOI。
2. 先检查项目 papers 中是否已有 DOI 匹配、has_fulltext=true 的 Markdown。
3. 已知 DOI 时调用 get_cached，不使用全量 list_cached。
4. 传入与原抓取相同的 download_dir。
5. 优先查看 preferred.markdown 和最新 fulltext 记录。
6. 校验缓存是否满足当前 modes、asset_profile、include_refs 和 max_tokens。
7. 满足则 prefer_cache=true 复用。
8. 不满足质量要求时才 prefer_cache=false 刷新。
9. 缓存命中后仍执行最终验收。

### 4.7 本地已核验 Markdown 应优先于重新抓取

当前问题：

- SKILL.md 虽然说工作区已有完整文本时不需要重抓，但没有给出可执行的检查顺序。
- 用户后续询问同一论文时，代理仍可能重新联网。

建议：

- 先在目标 papers 目录按 DOI、标题和 front matter 查找。
- 核对 DOI、source、content_kind、has_fulltext 和文件非空。
- 满足任务时直接读取本地 Markdown。
- 只有本地文本不完整、资产档位不足或用户明确要求刷新时才重新抓取。

### 4.8 普通阅读的默认返回内容过重

当前问题：

MCP 默认可能同时请求：

- article
- markdown
- full_text
- 全部参考文献
- provider 默认资产
- prefer_cache=false

影响：

- article 和 markdown 重复占用上下文。
- 参考文献可能占用大量 token。
- 普通摘要任务可能触发不必要的图片内联和落盘。

建议任务预设：

- 普通总结：modes=[markdown]，include_refs=none，asset_profile=none。
- 需要引用上下文：include_refs=top10。
- 完整引用核验：include_refs=all。
- 结构化抽取：modes=[article]。
- 完整本地归档：save_markdown=true，工具响应保持紧凑，然后只读取相关章节。
- 在决定 token 预算前检查 token_estimate_breakdown。
- 只有深度阅读全文时才使用 full_text；针对性问题使用合理的 numeric max_tokens。

### 4.9 title、保存和 provider 规则存在重复

当前问题：

- 标题必须 resolve 的规则在抓取步骤中重复出现。
- 单篇保存和多篇保存分别重复“先询问保存位置和图片”。
- provider_status 条件在多个条目中重复。

影响：

- SKILL.md 变长但状态机仍不清晰。
- 修改一处规则时容易漏改另一处。
- 代理可能重复询问或重复检查。

建议：

- 把流程改成一个决策表或状态机。
- 标题解析只定义一次。
- 保存策略只在“意图预设”中定义一次。
- provider 静态检查、live preflight 和 auth 分别定义一次。

### 4.10 重试规则不够明确

当前问题：

- “最多重试 2 次”可能理解为总共 2 次，也可能理解为初次加 2 次。
- prefer_cache=false 本身就是默认值，“优先绕过缓存重试”可能没有产生行为变化。
- ambiguous、no_access、rate_limited 和 browser transient 不应使用同一重试策略。

建议：

- 明确写成“初次尝试 + 最多 2 次重试”，或明确“最多 2 次总尝试”。
- ambiguous：不自动重试，先消歧。
- no_access：只有凭证或授权状态改变后才重试。
- rate_limited：遵守 retry_after_seconds，并停止继续提交新批次。
- browser transient：静态检查后做一次 live preflight，再绕缓存重试。
- 确定性解析错误和参数错误：不重试。
- 每次重试在 trace 中记录原因、参数变化和结果。

## 5. P1：浏览器 provider 问题

### 5.1 provider_status 不能证明浏览器链路健康

当前问题：

- SKILL.md 把 provider_status 描述为确认本地 browser runtime 健康。
- 当前实现只检查配置、依赖和 runtime 环境。
- 诊断文字明确说明 CDP connection is not probed。
- Playwright 可导入也不代表浏览器已经安装、Chrome 能启动、CDP 可连接或出版商页面可访问。

影响：

- provider_status=ready 容易被误报成真实浏览器链路可用。
- 首次抓取失败后，代理可能错误地认为问题不在浏览器。

建议：

把浏览器检查拆成三层：

1. 静态状态：provider_status，检查配置和依赖。
2. 实时预检：browser-preflight，真实启动或连接浏览器并访问 provider。
3. 人工认证：paper-fetch auth，仅在确实需要登录或挑战恢复时使用。

### 5.2 CLI 顶层帮助没有清楚暴露 auth 和 browser-preflight

当前问题：

- CLI 内部存在 paper-fetch auth 和 paper-fetch browser-preflight。
- 顶层 paper-fetch --help 只展示抓取参数，没有展示这些子命令。
- failure-handling.md 没有完整路由到这两个入口。

影响：

- 代理和用户不容易发现正确的恢复手段。
- 浏览器问题容易退化为重复 fetch。

建议：

- 顶层帮助展示可用子命令。
- failure-handling.md 增加静态检查、实时预检、人工认证的分层流程。
- MCP 增加 browser_preflight 工具，避免必须退回 shell。
- auth 是交互式外部状态操作，应明确标为 BLOCKING。

### 5.3 provider_status 返回范围过大

当前问题：

- provider_status 每次返回全部 provider。
- 单篇论文通常只关心 resolve 后的一个 provider。

影响：

- 输出噪声大。
- 重复消耗上下文。
- 代理更难聚焦真正失败的 provider。

建议：

- 支持 provider_status(provider=...)。
- 支持 detail=compact 或 detail=full。
- 同一会话对相同 provider 的静态状态可复用，不必每篇重复调用。

## 6. P0/P1：资产和内容质量问题

### 6.1 文件存在和非空不足以证明图片成功

当前问题：

- AMS/JHM 可能生成非空 Blank 图片。
- 同一论文中的多个占位图可能大小和哈希完全相同。
- 普通“路径存在且 size > 0”检查无法识别。

建议：

- 检测 Blank.svg、Blank.png 和同类命名。
- 检测同论文多图相同 SHA256。
- 检测异常小尺寸和异常小文件。
- 核对 MIME、扩展名、width、height 和 downloaded_bytes。
- 当图片对结论重要时，执行视觉抽查。
- 将 placeholder_suspected 单独报告，不能归入成功。

### 6.2 文本成功和资产成功必须分开

当前问题：

- BAMS/JHM 的 fulltext 可以成功，但图片资产仍降级。
- 用户历史上明确要求把“文本成功”“图片质量”“provider 原因”分开回答。

建议：

最终报告至少分为：

- 论文身份
- 文本内容
- 正文图片/表格/公式
- 补充材料
- provider/fallback

不要只给一个“成功/失败”。

### 6.3 Wiley preview 不应误报为整篇失败

当前问题：

- Wiley 原图不可用时可能回退到 preview。
- Markdown、全文和图片引用仍可能可读。

建议：

- preview 记录为 asset degraded。
- 核对 download_tier、width、height 和 source_trail。
- 只有文本不完整、图片引用损坏或分辨率不满足任务时，才升级为失败。
- 用户要分析图中细节时，preview 应被明确标记为不一定满足需求。

### 6.4 AMS 公式占位与主图缺失容易混淆

历史证据：

- Roy et al. 2019 的 coarse warning 显示有资产失败，进一步检查后发现主要真实图件已存在，失败的是重复 Blank.svg 公式占位引用。

影响：

- 单看 warning 容易误报“主图全部失败”。

建议：

- 按上下文区分 figure、table、formula 和 decorative asset。
- 检查 Markdown 引用附近的标题和 caption。
- 最终报告分别统计主图缺失、公式占位和装饰资源失败。

### 6.5 表格布局降级和语义丢失不能混为一谈

当前问题：

- table_layout_degraded_count 表示布局保真度下降。
- table_semantic_loss_count 才是内容可能缺失的强信号。

建议：

- 两项分别报告。
- semantic loss 大于 0 时，将 content_status 至少降为“文本成功但表格语义可能不完整”。
- 需要精确数值的任务应回看原 PDF、XML 或表格资产。

### 6.6 asset_profile=none 时远程图片链接的解释不清

当前问题：

- 不下载本地资产不代表 Markdown 中不会保留远程图片链接。
- 对远程链接做本地存在性检查会产生假失败。

建议：

- 验收逻辑先读取 asset_requested。
- asset_profile=none 时，将远程链接标记为 not archived，而不是 broken local asset。
- 只有请求了本地资产时，才要求所有本地目标存在。

### 6.7 图片转换工具环境没有完整记录

当前问题：

- environment.md 未完整记录 PAPER_FETCH_IMAGE_TOOLS_DIR。
- 离线包可能不包含所有 Ghostscript/libvips 工具。
- AMS EPS/TIFF 转换质量会受环境影响。

建议：

- 环境文档补充图像工具变量、探测方式和降级行为。
- provider_status 或 preflight 报告图片转换后端是否可用。
- 资产 warning 中区分“远端资源不可得”和“本地转换后端缺失”。

## 7. P1/P2：文档和打包问题

### 7.1 cli-fallback.md 存在真实断链

当前问题：

- references/cli-fallback.md 中的 ../../../docs/cli.md 解析为 /home/dictation/.codex/docs/cli.md。
- 该文件不存在。
- 离线安装位置对应的 docs/cli.md 也不存在。

影响：

- “完整 CLI 语义”无法从文档链接访问。
- 关键保存和输出行为只能通过源码或 --help 猜测。

建议：

- 把 docs/cli.md 正确打包并修复相对链接。
- 或删除断链，把 cli-fallback.md 写成自包含文档。
- CI 增加 Markdown 相对链接扫描。

### 7.2 tool-contract.md 是孤儿文档

当前问题：

- references/tool-contract.md 存在并包含关键默认值、返回字段、缓存和资产说明。
- SKILL.md 的“参考资料”没有链接它。

影响：

- 代理会读 SKILL.md，但不一定知道应该读取 tool-contract.md。
- 精确参数和返回契约容易被忽略。

建议：

- 在 SKILL.md 的参考资料中加入 tool-contract.md。
- 明确何时必须读取：需要精确参数、缓存、token、资产或返回字段时。

### 7.3 cli-fallback 的命名与实际定位矛盾

当前问题：

- 主流程把 CLI 作为批量首选。
- 参考文件却叫 cli-fallback，并说 MCP 不可用时使用。

影响：

- CLI 究竟是批量主后端还是故障 fallback 不清晰。

建议：

- 拆成 cli-batch.md 和 cli-fallback.md。
- cli-batch.md 描述正常批量归档。
- cli-fallback.md 只描述 MCP 不可用或用户明确要求 shell 的场景。

### 7.4 离线安装包内的技能参考资料不完整

当前问题：

- 当前活动 Codex skill 目录包含 references。
- /home/dictation/.local/share/paper-fetch-skill/skills/paper-fetch-skill 中只发现 SKILL.md。

影响：

- 重装、复制或直接使用离线包中的 skill 时，引用的 references 可能缺失。
- 活动副本和打包副本可能漂移。

建议：

- 离线包必须包含完整 references。
- 安装测试检查 SKILL.md 中所有相对资源在安装后存在。
- 比较活动副本与打包副本的哈希。

### 7.5 environment.md 未说明离线 wrapper 的配置优先级

当前问题：

- 离线 wrapper 会加载安装包内 offline.env。
- environment.md 主要描述 platformdirs 默认配置和显式 PAPER_FETCH_ENV_FILE。

影响：

- 用户难以判断最终使用了哪组 browser UA、headless、路径和 provider 凭证配置。

建议：

- 明确配置优先级。
- provider_status 输出有效配置来源，但不得输出秘密值。
- 文档解释 offline.env、用户配置、进程环境变量和显式参数的覆盖顺序。

### 7.6 prompt 能力与当前宿主可调用能力表述不清

当前问题：

- tool-contract.md 提到 summarize_paper 和 verify_citation_list MCP prompt。
- 当前 Codex 可调用工具列表只有 8 个工具，没有把这两个 prompt 暴露为普通工具。

影响：

- 代理可能尝试调用不存在的工具。

建议：

- 明确写“仅支持 MCP prompts 的宿主可用”。
- 同时给出普通工具的等价流程：
  - summarize：resolve -> cache -> fetch_paper -> 检查质量 -> 总结
  - verify citations：batch_resolve/batch_check -> 只抓取需要跟进的条目

## 8. P1/P2：MCP 契约问题

### 8.1 MCP 输入 schema 丢失重要类型信息

当前 Codex 可见 schema 中存在：

- fetch_paper.strategy 显示为 unknown
- modes 显示为普通 string 数组
- include_refs 显示为普通 string
- batch_check.mode 显示为普通 string
- list_cached.cache_mode 显示为普通 string
- provider_status 输入显示为任意对象

但 runtime 实际有明确约束：

- modes：article、markdown、metadata
- include_refs：none、top10、all
- batch_check.mode：metadata、article
- cache_mode：index、refresh、rescan
- concurrency：1 到 8
- 批量查询：最多 50
- strategy：allow_metadata_only_fallback、preferred_providers、asset_profile、inline_image_budget

影响：

- 客户端无法自动补全和校验。
- 代理必须依赖长篇描述猜参数。
- 容易在运行时才发现参数错误。

建议：

- 用 Literal、枚举和嵌套 Pydantic 模型把约束暴露进 MCP input schema。
- 为 strategy 提供完整对象 schema。
- 为数值范围和最大条数提供 min/max。
- 对 provider_status 使用空对象 schema或明确可选字段，不使用任意对象。

### 8.2 MCP 工具描述严重重复并占用上下文

当前问题：

- 8 个 paper-fetch MCP 工具描述合计约 61,885 字符。
- 粗略相当于约 15.5k token。
- provider catalog、source/provider 映射和 fallback 说明在多个工具中重复。
- fetch_paper 单项描述约 13.9k 字符。

影响：

- 在真正读取论文前，工具描述已经占用大量上下文。
- 每次 provider 更新需要同步多处文本。
- 长描述掩盖了每个工具真正重要的输入和输出。

建议：

- 每个工具只保留用途、关键边界和精确 schema。
- 公共 provider catalog 移到 MCP resource、server instructions 或 tool-contract.md。
- source/provider 映射由 runtime 动态资源提供。
- 客户端需要时再读取 provider 细节。

### 8.3 provider catalog 被硬编码进文档，容易漂移

当前问题：

- tool-contract 和工具描述列出大量 provider/source 映射。
- runtime provider catalog 才是实际真源。

影响：

- 新增或修改 provider 后，文档可能与实现不同步。

建议：

- 文档只说明“以 runtime catalog 为准”。
- 提供机器可读 provider catalog resource。
- CI 比较文档快照和 runtime catalog，或完全由 runtime 生成文档。

### 8.4 缺少结构化的 batch fetch MCP 工具

当前问题：

- MCP 有 batch_resolve 和 batch_check，但没有真正的 batch_fetch。
- 代理要批量归档时只能退到 CLI，随后自己解析 JSONL 和文件。

影响：

- 这也是当前技能要求“批量转 CLI”的根本原因之一。
- MCP progress、structured error 和工具结果验证无法覆盖完整批量归档。

建议：

- 增加 batch_fetch，支持受控并发、每项结果、统一 run manifest、取消和限流中止。
- 若暂不增加 batch_fetch，CLI JSONL 必须补足内容和资产质量字段。

### 8.5 get_cached 缺少紧凑模式

当前问题：

- get_cached 会返回匹配 DOI 的所有相关条目和资产。
- 代理通常只需要最新优选 Markdown 和摘要状态。

建议：

- 增加 preferred_only=true。
- 或支持 detail=compact、full。
- compact 返回最新 Markdown、fulltext 状态、资产摘要和 cache request fingerprint。

## 9. P0/P1：批量结果与可重复性问题

### 9.1 JSONL 和最终 Markdown 可能不是同一时刻的状态

当前问题：

- 某次历史批量结果中，JSONL 初始记录与后来最终 Markdown 的 fulltext 状态不一致。
- 后续重试或覆盖文件时，旧 JSONL 不会自动更新。

影响：

- 审计者无法判断 JSONL 对应哪一版输出。

建议：

- 每个 run 使用唯一 run_id。
- JSONL 记录 completed_at、output_size、output_sha256。
- 结束时执行 reconcile，重新读取最终 front matter。
- 若文件在 run 后发生变化，标记 manifest_stale。

### 9.2 并发结果不能依赖 JSONL 行顺序

当前问题：

- 批量并发可能使完成顺序与输入顺序不同。

建议：

- 使用 index 作为稳定身份。
- 验收 query_count = record_count = unique_index_count。
- 索引集合必须完整覆盖 1 到 N 或约定的 0 到 N-1。
- 汇总时按 index 恢复原始顺序。

### 9.3 fallback、warning 和 failure 缺少统一分类

当前问题：

- arXiv HTML 到 PDF、Wiley HTML 到 PDF、preview 图片、AMS 部分资产、Elsevier 表格压平等都属于不同类型。
- 简单搜索 warning 文本会把普通论文正文中的 source 等词也匹配出来。

建议：

- 使用结构化 fallback_class 和 warning_class。
- 至少区分：
  - paper_failure
  - metadata_fallback
  - pdf_fallback
  - asset_preview
  - asset_partial_failure
  - placeholder_asset
  - table_layout_degraded
  - table_semantic_loss
  - formula_degraded
- 审计先读 JSONL 和 front matter，再做针对性正文搜索。

### 9.4 缺少统一的单篇和批量 manifest

当前问题：

- 批量有 JSONL，单篇主要依赖返回结果和 Markdown front matter。
- 后续难以统一查找、去重和验证。

建议：

- 单篇和批量都写同一 schema 的 manifest。
- 推荐位置：目标 papers 目录下的 fetch-manifest.jsonl，或每次运行独立 manifest。
- 记录 query、normalized DOI、source、内容状态、资产状态、输出路径、哈希、版本和时间。

## 10. 针对当前用户工作区的使用问题

### 10.1 没有充分利用稳定的 papers 目录约定

历史偏好：

- /home/dictation/drought_prediction 的单篇和批量论文归档通常使用项目根目录 papers。
- /home/dictation/pshed 也使用项目根目录 papers。

建议：

- 将其做成项目 profile，而不是写死在全局技能中。
- 进入项目后自动识别 git root 和已有 papers。
- 当前目录存在多个项目时再询问。

### 10.2 papers 可能被 gitignore，不能用 git status 验收

历史证据：

- drought_prediction 的顶层 papers 曾被 .gitignore 忽略。

影响：

- git status 为空容易被误解为抓取没有生成文件。

建议：

- 验收使用直接文件检查、front matter、资产路径和 git check-ignore。
- 不把 git status 作为论文归档成功与否的主要证据。

### 10.3 环境中不一定有 jq 或 python 命令

历史证据：

- 某次批量审计没有 jq，也没有名为 python 的命令，但 python3 可用。

建议：

- 审计脚本优先使用 python3。
- 不把 jq 设为必需依赖。
- 最好由 paper-fetch 自己提供 audit 子命令，减少外部脚本依赖。

### 10.4 后续论文解释应复用本地全文

当前问题：

- 抓取成功后，后续总结或方法分析仍可能重新搜索网页。

建议：

- 保存成功后，把 saved_markdown_path 作为会话状态。
- 后续解释先读取本地 Markdown 的摘要、方法、结果和结论章节。
- 明确回答基于全文、摘要还是元数据。

## 11. 建议的标准任务预设

### 11.1 临时阅读或普通总结

目标：

- 不建立本地归档。
- 尽量减少落盘和上下文占用。

建议：

~~~text
resolve_paper
-> 检查已有本地全文
-> fetch_paper(
     modes=["markdown"],
     include_refs="none",
     strategy.asset_profile="none",
     no_download=true
   )
-> 检查 has_fulltext/content_kind
-> 总结
~~~

### 11.2 可缓存阅读

目标：

- 不建立用户可见归档。
- 保留后续可复用的 envelope cache。

建议：

~~~text
resolve_paper
-> get_cached(normalized DOI, same download_dir)
-> 命中且质量满足：prefer_cache=true
-> 未命中：artifact_mode="none", no_download=false
-> asset_profile="none"
~~~

### 11.3 单篇本地归档

目标：

- 保存完整 Markdown。
- 图片范围由用户意图决定。

建议：

~~~text
resolve_paper
-> 精确缓存/本地文件检查
-> 必要时 provider 静态检查
-> fetch_paper(
     save_markdown=true,
     markdown_output_dir=<repo>/papers,
     download_dir=<repo>/papers,
     artifact_mode="markdown-assets",
     strategy.asset_profile="none" | "body" | "all"
   )
-> 验证 saved_markdown_path、front matter、资产和 warnings
~~~

### 11.4 批量可读性核验

目标：

- 只判断候选是否唯一、是否可能有全文。
- 不抓取全部正文。

建议：

~~~text
解析输入
-> batch_resolve
-> DOI 去重
-> batch_check(mode="metadata", concurrency=3)
-> ambiguous 单独请求用户选择
-> 报告 likely readable / unknown / metadata-only
~~~

### 11.5 批量本地归档

目标：

- 可恢复、可审计地保存整批 Markdown。

建议命令形态：

~~~bash
paper-fetch \
  --query-file ./queries.txt \
  --output-dir ./papers \
  --batch-concurrency 3 \
  --batch-results ./papers/batch-results.jsonl \
  --format markdown \
  --artifact-mode markdown-assets \
  --asset-profile none \
  --include-refs none \
  --max-tokens full_text
~~~

如果用户明确要求正文图片，把 --asset-profile none 改为 body；如果明确要求补充材料，再改为 all。

命令结束后必须运行验收，不能只检查退出码。

## 12. 建议的标准验收契约

### 12.1 身份验收

- 每个输入都有稳定 index。
- 标题输入已解析为唯一 DOI 或唯一 landing URL。
- 输出 front matter DOI 与规范化 DOI 一致。
- 重复 DOI 已去重或明确保留重复原因。

### 12.2 文本验收

- output_path 存在且非空。
- Markdown front matter 可解析。
- content_kind 和 has_fulltext 一致。
- 仅摘要或元数据时明确降级。
- body token 或字符量满足最低阈值。
- 需要精确表格时，table_semantic_loss_count=0。

### 12.3 资产验收

- 先确认是否请求了资产。
- 所有本地 Markdown 图片引用可解析。
- 文件存在、非空、MIME 和扩展名合理。
- 尺寸和 downloaded_bytes 合理。
- 区分 full_size、preview、source_converted 和 failed。
- 检测 Blank 文件、相同哈希和异常小图。
- 主图、公式、表格和补充材料分别统计。

### 12.4 批量输出验收

- 输入数 = JSONL 记录数。
- unique index 数 = 输入数。
- 索引集合完整。
- 每个输出文件存在且非空。
- JSONL 与最终 front matter 完成 reconcile。
- 统计 fulltext、abstract、metadata、fallback 和 failure。
- JSONL 记录工具版本、run_id、时间和 SHA256。

### 12.5 用户报告模板

建议最终固定报告：

~~~text
总输入：
唯一论文：
歧义：

文本：
- fulltext：
- abstract-only：
- metadata-only：
- failed：

资产：
- 完整：
- preview 降级：
- 部分失败：
- 占位图嫌疑：
- 未请求：

输出：
- JSONL 记录：
- 非空 Markdown：
- 缺失文件：
- JSONL/front matter 不一致：

provider/fallback：
- ...
~~~

## 13. 建议增加的自动化测试

### 13.1 静态文档测试

- 扫描 SKILL.md 和 references 中所有相对链接。
- 断言链接目标存在。
- 检查活动 skill 和离线包 skill 内容一致。
- 检查 references 被正确打包。
- 检查环境变量文档与 runtime 使用变量一致。

### 13.2 CLI 契约快照

- 快照 paper-fetch --version。
- 快照 paper-fetch --help。
- 快照 paper-fetch auth --help。
- 快照 paper-fetch browser-preflight --help。
- 断言顶层帮助暴露子命令。
- 断言 asset-profile 默认值被文档明确说明。

### 13.3 MCP schema 测试

- 快照 tools/list。
- 断言 strategy 不是 unknown。
- 断言 modes、include_refs、batch_check.mode 和 cache_mode 有 enum。
- 断言 concurrency 范围为 1 到 8。
- 断言批量查询最大值 50 可见。
- 断言输出 schema 包含内容和资产质量字段。

### 13.4 落盘语义矩阵测试

在临时目录和 mock provider 下验证：

- 临时阅读不产生文件。
- cache-only 只产生允许的 index/sidecar。
- archive-none 产生 Markdown、不产生正文资产。
- archive-body 产生 Markdown 和可解析正文资产。
- archive-all 额外产生补充材料。
- markdown_output_dir 和 download_dir 隔离正确。
- CLI --no-download 下只有显式允许的输出可以写入。

### 13.5 批量验收测试

- 查询数、JSONL 数和唯一 index 数一致。
- 并发乱序时仍能恢复输入顺序。
- output_path 全部存在且非空。
- front matter DOI、source、content_kind 和 has_fulltext 可读取。
- metadata-only 不被计为 fulltext 成功。
- 后续覆盖文件时能检测 manifest stale。

### 13.6 资产质量测试

- Blank.svg/png 被识别。
- 多图相同哈希被标记。
- 异常小尺寸占位图被标记。
- preview 与 full_size 正确分类。
- 主图缺失和公式占位分别报告。
- table layout degradation 和 semantic loss 分开处理。

### 13.7 浏览器预检测试

- provider_status 只证明静态依赖和配置。
- live preflight 真正探测 CDP。
- auth 流程明确要求交互。
- provider_status=ready 但 CDP 失败时不能误报健康。

## 14. 建议的实现顺序

### 第一阶段：只修改 skill 和 references

1. 合并保存和 CLI 两个 BLOCKING 门。
2. 增加临时阅读、缓存阅读、本地归档三个预设。
3. 把流程改成“先解析去重，再缓存，再选择后端”。
4. 增加强制验收步骤和四级状态。
5. 修复 cli.md 断链。
6. 从 SKILL.md 链接 tool-contract.md。
7. 拆分 cli-batch 和 cli-fallback。
8. 明确 provider_status 只是静态检查。

### 第二阶段：完善 CLI/MCP 契约

1. 丰富批量 JSONL。
2. 修复 MCP input schema。
3. 缩短重复工具描述。
4. 增加 provider_status 的 provider/detail 过滤。
5. 增加 get_cached compact 模式。
6. 顶层 CLI 帮助暴露 auth 和 browser-preflight。

### 第三阶段：增加工具能力

1. 增加 paper-fetch audit。
2. 增加 batch_fetch MCP 工具。
3. 增加 live browser preflight MCP 工具。
4. 生成统一单篇/批量 manifest。
5. 将 provider catalog 暴露为机器可读 resource。

## 15. 最小可行改版

如果只能进行一次较小改版，优先完成以下四项：

1. 删除 CLI 选择的强制暂停。
2. 明确三个保存预设，并分别写 CLI/MCP 参数。
3. 新增抓取后验收，禁止把 status=ok 直接解释为全文和图片成功。
4. 修复 tool-contract 路由、cli.md 断链和 asset-profile 默认值说明。

这四项能够直接解决历史使用中反复出现的四类问题：

- 多问一轮才能开始批量任务；
- 不清楚到底保存了什么；
- status=ok 仍无法回答“成功了吗”；
- 图片存在但实际是降级或占位图。

## 16. 当前证据位置

当前技能和参考资料：

- /home/dictation/.codex/skills/paper-fetch-skill/SKILL.md
- /home/dictation/.codex/skills/paper-fetch-skill/references/tool-contract.md
- /home/dictation/.codex/skills/paper-fetch-skill/references/cli-fallback.md
- /home/dictation/.codex/skills/paper-fetch-skill/references/environment.md
- /home/dictation/.codex/skills/paper-fetch-skill/references/failure-handling.md

当前安装实现：

- /home/dictation/.local/share/paper-fetch-skill/bin/paper-fetch
- /home/dictation/.local/share/paper-fetch-skill/runtime/site-packages/paper_fetch/cli.py
- /home/dictation/.local/share/paper-fetch-skill/runtime/site-packages/paper_fetch/mcp

历史记忆中最相关的审计主题：

- drought_prediction 批量抓取 related_papers.txt
- AMS/BAMS/JHM 文本成功与 Blank 图片占位问题
- JSONL 与最终 Markdown 状态不一致
- Wiley preview 图片降级
- 单篇 AGU/Wiley 抓取、缓存噪声和本地 Markdown 复用
- pshed 批量抓取与 AMS 资产修复
