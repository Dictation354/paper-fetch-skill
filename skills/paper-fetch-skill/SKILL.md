---
name: paper-fetch-skill
description: "获取并核验已知论文全文，为阅读、总结或比较提供可追溯文本。适用于 DOI、URL、arXiv ID、标题、引用条目及检索产生的明确候选；不承担开放式领域检索。"
---

# 论文抓取技能

先确认论文身份，再根据任务意图选择执行面；抓取后必须验收并报告。搜索工具只负责发现候选，不得用搜索摘要或网页片段冒充论文全文。

## 核心契约

- 开始任务前读取 [`references/workflow.md`](references/workflow.md)，按其中唯一的状态机推进。阶段之间保持依赖有序；同一阶段内身份独立的论文允许受控并发。
- 身份明确后读取 [`references/presets.md`](references/presets.md) 的共同规则和当前预设；先确定意图、请求参数及必要的 scope，再检查本地/cache。执行面确定后按对应 CLI/MCP 矩阵核对落盘语义，不依赖运行时默认值。
- 预设只补全未指定项；沿用用户明确的路径、资产范围、执行面和已有覆盖授权，不重复确认。身份、访问权限和数据完整性约束仍须满足。
- 只允许状态机的 BLOCKING 白名单暂停工作。普通上下文阅读/总结不因保存策略缺失而阻塞，后端选择本身也不要求用户确认。
- 对单篇使用 `resolve_paper(...)`，对成批候选使用 `batch_resolve(...)`；去重后按当前预设检查合格本地全文及适用的同 scope 精确缓存。临时阅读不为查询缓存而要求目录。后续按意图使用 `batch_check(queries=[query])`（单篇探测）或 `batch_check(...)`（批量探测）、`fetch_paper(...)` 或 `batch_fetch(...)`。
- 只在 provider、凭证或浏览器运行时可能影响结果时调用 `provider_status()`；对 runtime `capabilities.browser_available=true`（由 provider routes 派生） 的 provider，首次联网抓取前先做静态检查，需要 live 证明时再调用 `browser_preflight(provider=...)`。普通工具不安装或修复 runtime；缺失时按 [`references/environment.md`](references/environment.md#运行时准备与授权) 的已有授权规则处理。仅在结果明确要求时进入人工 auth。
- 抓取后按 [`references/acceptance.md`](references/acceptance.md) 的对应章节核验实际响应或文件，并保留来源与降级证据；不得用 `.gitignore` 或 `git status` 是否变化代替文件验收。验收后宿主继续完成用户要求的总结、比较或翻译等任务；获取报告不替代原任务。
- 不要仅因为本地没有 PDF 或缓存文本文件就断定论文不可读；也不要把 abstract-only 或 metadata-only 报告成全文成功。
- Browser HTML 失败但 PDF/ePDF fallback 成功时，仍按 trace 中的精确 browser code 报告降级，并要求 `acceptance.overall=degraded`；不得用顶层 `status=ok` 抹掉 HTML failure provenance。
- 参考文献列表或 web search 已产生候选论文后，先进入身份状态机；没有可核验候选的开放式发现任务不由本技能替代。

## 按需参考

- 每次使用先读工作流和 BLOCKING 白名单：[`references/workflow.md`](references/workflow.md)。
- 确定参数时读共同规则、当前预设及适用的本地/cache 分支；选定执行面后核对对应落盘矩阵，超过 50 条时再读分块规则：[`references/presets.md`](references/presets.md)。
- 每次验收读七个分面、响应验收和最终报告；请求资产、复用本地文件、归档或批量任务再读对应章节：[`references/acceptance.md`](references/acceptance.md)。
- 标题解析读 MCP Tools；需精确参数、返回值、cache 或 provider catalog 时读对应章节：[`references/tool-contract.md`](references/tool-contract.md)。
- 凭证或工具链影响任务时读相关配置及诊断章节；runtime 缺失时读准备与授权：[`references/environment.md`](references/environment.md)。
- 使用 CLI 时读单篇或批量流程；入口不可用时再读窄 fallback：[`references/cli-workflow.md`](references/cli-workflow.md)。
- 出现失败、限流、需解释的降级或准备重试时，读总尝试次数及对应决策表行：[`references/failure-handling.md`](references/failure-handling.md)。
