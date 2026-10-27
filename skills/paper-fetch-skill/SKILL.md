---
name: paper-fetch-skill
description: "获取、下载或核验指定论文全文或补充材料，或探测全文可用性。支持 DOI、URL、arXiv ID、标题和引用条目；阅读、总结、比较或翻译已知论文而需要全文时使用。不用于尚无明确候选的开放式领域检索。"
---

# 论文抓取

确认论文身份，按用户意图获取全文或探测可用性，验收后继续完成阅读、总结、比较或翻译。搜索只用于发现候选，搜索摘要和网页片段不能冒充论文全文。

## 关键约束

- 沿用用户明确的路径、资产范围、执行面和覆盖授权；预设只补全未指定项。状态与暂停条件统一见工作流。
- 优先复用身份可证明且满足当前意图的本地全文或同 scope 缓存；临时阅读不为查询缓存而要求目录。
- 阅读必须取得并读取实际正文，区分全文、摘要、元数据与截断片段；仅探测不自动升级为抓取。
- 工具自动准备 managed runtime。仅实际返回 `challenge` / `auth_required` 时进入人工认证，不绕过登录、验证码、付费墙或访问控制。
- 消费统一 acceptance，并核对任务要求的响应、资产和实际文件。保留来源及影响任务的降级；HTML 失败后 PDF/ePDF 成功仍保留 browser failure provenance。
- PDF 正文以现有转换器输出为边界，不清洗或修复内容。

## 独立补充材料

用户只要补充材料时，使用 CLI `fetch --target supplementary` 或 MCP `fetch_paper` / `batch_fetch` 的 `target="supplementary"`，沿用已有路径和批量设置。此任务不要求正文、不获取正文 PDF；材料范围固定，不用 `asset_profile` 改变范围。读取返回的 `supplementary.assets`、逐项失败及发现完整性，按材料验收报告；`has_fulltext=false` 和正文未请求不是失败。随正文归档补充材料仍使用 `target="paper", asset_profile="all"`。精确返回与落盘语义见[工具契约](references/tool-contract.md#独立补充材料任务)。

## 按需参考

先读[工作流](references/workflow.md)，再按任务读取章节，不默认加载整份 reference：

- 选择参数：读[共同规则](references/presets.md#共同规则)和当前预设：[临时阅读](references/presets.md#1-临时阅读)、[可缓存阅读](references/presets.md#2-可缓存阅读)、[单篇归档](references/presets.md#3-单篇本地归档)、[仅探测](references/presets.md#4-批量可读性分诊)或[批量归档](references/presets.md#5-批量本地归档)。自定义输出组合时再查该文件的 CLI/MCP 落盘矩阵。
- 验收：仅探测直接读[探测核对与报告](references/acceptance.md#探测核对与报告)；抓取或复用读[七个分面](references/acceptance.md#七个分面)、[响应验收](references/acceptance.md#响应验收)及[最终报告](references/acceptance.md#最终报告)。资产、文件、批量章节只在适用时读。
- 精确参数或返回字段：按需查[工具契约](references/tool-contract.md)的对应章节；内部一致性诊断仅在异常或用户要求时读。
- 凭证、runtime 或工具链实际影响任务时，读[环境参考](references/environment.md)的对应章节；普通抓取无需预读更新机制。
- 选用 CLI 时，读 [CLI 工作流](references/cli-workflow.md)的单篇或批量章节；入口不可用时再读窄 fallback。
- 失败、限流、需解释的降级或准备重试时，读[失败处理](references/failure-handling.md)的对应章节。
