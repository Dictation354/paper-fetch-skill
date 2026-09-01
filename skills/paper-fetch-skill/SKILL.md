---
name: paper-fetch-skill
description: "适用场景：已知论文阅读、总结、全文获取与核验；用户提供 DOI、URL、arXiv ID、标题、引用条目，或 web search / 主题检索已产生候选论文且需要阅读、总结、比较、翻译、批判、核验可读性或获取全文时，使用 paper-fetch；不替代开放式领域检索。"
---

# 论文抓取技能

先确认论文身份，再根据任务意图选择执行面；抓取后必须验收并报告。搜索工具只负责发现候选，不得用搜索摘要或网页片段冒充论文全文。

## 核心契约

- 开始任务前读取 [`references/workflow.md`](references/workflow.md)，按其中唯一的状态机推进。阶段之间保持依赖有序；同一阶段内身份独立的论文允许受控并发。
- 身份和意图明确后读取 [`references/presets.md`](references/presets.md)，把任务映射为五个显式预设之一；分别按 CLI/MCP 矩阵设置主输出、cache、artifact、资产与完全不落盘语义，不依赖运行时默认值。
- 只允许状态机的 BLOCKING 白名单暂停工作。普通上下文阅读/总结不因保存策略缺失而阻塞，后端选择本身也不要求用户确认。
- 对单篇使用 `resolve_paper(...)`，对成批候选使用 `batch_resolve(...)`；身份去重后优先检查同 scope 的 `get_cached(doi, detail="compact", preferred_only=true, ...)`，只有 DOI 未知且确需浏览 scope 时才用 `list_cached()`，再按需使用 `has_fulltext(...)`、`batch_check(...)`、`fetch_paper(...)` 或结构化全文批量入口 `batch_fetch(...)`。
- 只在 provider、凭证或浏览器运行时可能影响结果时调用 `provider_status()`；对 runtime `capabilities.browser_available=true`（由 provider routes 派生） 的 provider，首次联网抓取前先做静态检查，需要 live 证明时再调用 `browser_preflight(provider=...)`。缺失 runtime 时提示用户显式运行 `python -m camoufox fetch`；普通工具不安装或修复 runtime。仅在结果明确要求时进入人工 auth。
- 抓取不是终点。始终按 [`references/acceptance.md`](references/acceptance.md) 检查实际响应、文件和统一 acceptance 结果，再报告身份、来源、降级、产物路径和下一步；不得用 `.gitignore` 或 `git status` 是否变化代替文件验收。
- 不要仅因为本地没有 PDF 或缓存文本文件就断定论文不可读；也不要把 abstract-only 或 metadata-only 报告成全文成功。
- Browser HTML 失败但 PDF/ePDF fallback 成功时，仍按 trace 中的精确 browser code 报告降级，并要求 `acceptance.overall=degraded`；不得用顶层 `status=ok` 抹掉 HTML failure provenance。
- 参考文献列表或 web search 已产生候选论文后，先进入身份状态机；没有可核验候选的开放式发现任务不由本技能替代。

## 按需参考

- 工作流阶段、BLOCKING 白名单、目录推断、执行面选择和验收报告：[`references/workflow.md`](references/workflow.md)
- 五个任务预设、CLI/MCP 独立落盘矩阵、本地优先决策树和 50 条分块规则：[`references/presets.md`](references/presets.md)
- 统一 acceptance 分面、文件/path/hash 复核和最终报告字段：[`references/acceptance.md`](references/acceptance.md)
- 工具参数、默认值、返回字段及唯一的标题解析规则：[`references/tool-contract.md`](references/tool-contract.md)
- provider 凭证、下载目录、browser runtime 与合法访问上下文：[`references/environment.md`](references/environment.md)
- 正常 CLI 单篇/批量归档、最终结果文件和 CLI 不可用时的窄 fallback：[`references/cli-workflow.md`](references/cli-workflow.md)
- 批量 probe、代理级重试、限流、全部 error category、降级与失败报告的唯一决策表：[`references/failure-handling.md`](references/failure-handling.md)
