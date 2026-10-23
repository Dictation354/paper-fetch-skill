---
name: paper-fetch-skill
description: "获取、下载或核验指定论文全文，或探测全文可用性。支持 DOI、URL、arXiv ID、标题和引用条目；阅读、总结、比较或翻译已知论文而需要全文时使用。不用于尚无明确候选的开放式领域检索。"
---

# 论文抓取

确认论文身份，按用户意图获取全文或探测可用性，验收后继续完成阅读、总结、比较或翻译。搜索只用于发现候选，搜索摘要和网页片段不能冒充论文全文。

## 关键约束

- 沿用用户明确的路径、资产范围、执行面和覆盖授权；预设只补全未指定项。遵循状态机，仅 BLOCKING 白名单中的情形暂停。
- 按当前预设复用合格本地全文或同 scope 精确缓存；临时阅读不为查询缓存而要求目录。保留身份、合法访问、来源追踪和统一验收边界。
- 批量工具每次最多 50 条，输入时分块并保留原始 index，解析后跨块去重；阶段依赖有序，同阶段独立论文可受控并发。
- 多篇完整阅读沿用单篇阅读预设取得每篇正文；compact 无正文，bounded 可能截断。不要重复抓取已取得的正文。
- provider、凭证或浏览器影响结果时才检查状态。每次抓取开始时自动准备 managed runtime，批量只检查一次；仅明确返回 challenge/auth_required 时进入人工认证，不绕过访问控制。
- 抓取或文件复用核验实际响应和文件及统一 acceptance；仅探测核对逐项证据和调度状态，不自动升级为抓取。abstract-only、metadata-only 或缺失资产不得报告成全文成功。
- HTML 失败但 PDF/ePDF 成功仍保留 browser failure provenance 和 degraded 验收。PDF 正文以现有转换器输出为边界，不清洗或修复内容。

## 按需参考

- 开始任务读唯一状态机及 BLOCKING 白名单：[`references/workflow.md`](references/workflow.md)。
- 选择五个预设、处理本地/cache、批量分块和落盘矩阵：[`references/presets.md`](references/presets.md)。
- 验收正文或资产、复用文件、核对探测结果及报告：[`references/acceptance.md`](references/acceptance.md)。
- 核对 MCP 参数、返回值、cache 和 provider catalog：[`references/tool-contract.md`](references/tool-contract.md)。
- 配置凭证、准备浏览器或公式工具、解释运行环境诊断：[`references/environment.md`](references/environment.md)。
- 使用 CLI 单篇或批量流程及入口不可用时的窄 fallback：[`references/cli-workflow.md`](references/cli-workflow.md)。
- 处理失败、限流、降级和重试：[`references/failure-handling.md`](references/failure-handling.md)。
