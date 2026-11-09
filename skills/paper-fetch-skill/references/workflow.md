# 身份优先工作流

沿用现有状态机；已有明确身份或合格本地文件时复用相应结果：

> 输入规范化 → resolve/batch_resolve → DOI 去重 → 仅歧义项阻塞 → 意图 → 本地/cache → 后端 → 必要状态检查 → fetch → acceptance → report

阶段依赖有序，同阶段独立目标可受控并发。除用户要求整批原子完成外，单项目标暂停或失败不阻止其余目标。

## BLOCKING 白名单

只有仍需用户决定的以下事项才暂停相应目标；沿用已有选择和授权，不重复询问：

| 情形 | 需要决定的内容 |
| --- | --- |
| `multiple_candidates` | 多个合理候选无法唯一化。 |
| `insufficient_identity` | 标识和书目信息不足以定位论文。 |
| `manual_auth` | 用户需完成人工登录或授权。 |
| `lawful_access_boundary` | 付费、许可或访问控制需要权限。 |
| `overwrite_existing` | 将覆盖可用成果，尚无覆盖授权。 |
| `material_output_choice` | 无法推断且实质影响内容、位置或资产的选择。 |

缓存命中、执行面选择、目标数量、普通降级或单项失败不构成额外确认点。缺少工具或 runtime 时报告该执行面的能力限制，并继续可执行目标；环境修复沿用任务已有授权。

## 状态机

1. **输入与身份**：保留原条目、来源和稳定 1-based `index`；单篇用 `resolve_paper`，批量用 `batch_resolve`。标题先按[标题解析契约](tool-contract.md#标题解析)取得规范身份。超过 50 条先按[分块规则](presets.md#批量分块与证据等级)切块；汇总后按规范 DOI 跨块去重，无 DOI 的唯一目标保留规范落地页身份。始终保留原输入到规范目标的映射，只阻塞歧义项。
2. **意图**：按[任务目标](presets.md#任务目标)区分正文与独立材料，再选[五个预设](presets.md#五个预设)之一。预设只补全未指定项，多篇比较沿用阅读预设。归档路径依次复用用户路径、项目配置或唯一已有约定、唯一合理的 `papers/`；仍有实质歧义才询问。写盘前检查可用成果及覆盖授权。
3. **本地/cache**：优先复用身份和内容满足任务的本地文件；正文按[本地优先决策树](presets.md#本地优先决策树)检查同 scope 缓存，直接消费 `request_satisfied`。临时阅读不为查缓存新增 scope。独立材料检查材料清单和所需文件，不能以正文命中替代；允许缓存时由 `target="supplementary", prefer_cache=true` 检查材料请求。仅探测没有合格本地证据时继续 probe，不为查询缓存抓正文。
4. **执行面与状态**：阅读和结构化提取默认 MCP，批量归档默认 CLI；需要宿主 progress/cancel 或结构化批量结果时用 `batch_fetch`，沿用用户限制。CLI 用法见 [CLI 工作流](cli-workflow.md)。配置或依赖异常时用筛选后的 `provider_status(provider=...)`；只有需要真实链路证据时才做 [browser preflight](tool-contract.md#browser-preflight-contract)，普通抓取自动准备 runtime。实际返回 `challenge` / `auth_required` 时进入人工认证，不绕过访问控制。
5. **fetch**：仅处理未被本地/cache 满足的目标。正文用当前预设；独立材料用 `target="supplementary"`，不要求正文或追加正文 PDF fallback；仅探测用 `batch_check`（单篇传一个 query），不自动升级为全文抓取。同阶段受 provider/runtime 限制并发，批量沿用分块规则；失败和重试见[失败处理](failure-handling.md)。
6. **acceptance 与 report**：探测按[探测核对](acceptance.md#探测核对与报告)，材料按[补充材料验收](acceptance.md#补充材料验收)，正文按[七个分面](acceptance.md#七个分面)和[响应验收](acceptance.md#响应验收)。只在请求相应资产、文件或批量输出时读对应章节。按[最终报告](acceptance.md#最终报告)交付，批量保留原始映射和逐项状态。

获取后继续用户原本要求的阅读、总结、比较、翻译或提取。完整阅读须取得并读取实际正文；compact 仅含验收摘要，bounded 可能截断，已归档正文可直接读文件。paper-fetch 本身负责身份解析、获取、验收和报告。
