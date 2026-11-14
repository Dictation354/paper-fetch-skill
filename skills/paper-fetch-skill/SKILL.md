---
name: paper-fetch-skill
description: "获取、下载或核验指定论文全文或补充材料，或探测全文可用性。支持 DOI、URL、arXiv ID、标题和引用条目；阅读、总结、比较或翻译已知论文而需要全文时使用。不用于尚无明确候选的开放式领域检索。"
---

# 论文抓取

确认论文身份，按用户意图获取全文、补充材料或探测全文可用性，验收后继续完成阅读、总结、比较或翻译。搜索只用于发现候选，搜索摘要和网页片段不能冒充论文全文。

## 最短阅读路径

已有用户指定正文或有效会话句柄时直接复用。明确 DOI/URL 的普通阅读可直接调用，fetch 内部完成身份解析：

```javascript
const result = (await callTool("fetch_paper", {
  query: "10.1186/1471-2105-11-421", preset: "temporary_read"
})).structuredContent;
text({doi: result.doi, source: result.source, acceptance: result.acceptance,
      fallback_codes: result.fallback_codes, failure_codes: result.failure_codes});
// 保存 result.content_ref 和 offset；每轮输出一个片段。
const page = (await callTool("read_content", {
  content_id: result.content_ref.content_id, offset: 0, max_chars: 6000
})).structuredContent;
text(page);
// 后续使用 page.next_offset 继续，直到读完任务所需范围。
```

`callTool` 代表宿主实际工具调用。只消费 structuredContent。以 acceptance 区分全文、摘要和元数据；工具取得全文不代表调用方已读完。多篇用 `batch_fetch(queries=[...], preset="temporary_read", concurrency=4)`，逐项保存身份、句柄和阅读进度。追问先用 `navigate_content(content_id, mode="search", query="关键词")` 或 `mode="headings"` 定位，再用 `read_content` 读取原文范围。完整错误、材料清单和来源按需读取 `view="diagnostics"`。

CLI 临时阅读：`paper-fetch fetch --preset temporary_read --query "10.1186/1471-2105-11-421" --progress jsonl`。入口不可用时按[入口发现](references/cli-workflow.md#窄-fallback)查受管 wrapper。

## 关键约束

- 沿用用户明确的路径、资产范围、执行面和覆盖授权；预设只补全未指定项。需用户决定的情形见[工作流](references/workflow.md#blocking-白名单)。
- 用户显式指定的文件或来源优先；否则先复用有效会话句柄，再查合格本地正文，最后获取。允许缓存且 scope 明确时直接 `fetch_paper(prefer_cache=true)`；临时阅读不为查询缓存而要求目录。
- 阅读用 默认 `preset="temporary_read"`，多篇用批量句柄，再以 `read_content` 分段消费；需要 article 时显式请求。只消费 structuredContent 中的业务载荷，保存身份、句柄和进度供追问复用，示例见[正文读取](references/tool-contract.md#正文句柄与读取)。区分工具取得全文、返回片段和调用方已读完；仅探测不自动升级为抓取。
- 工具按需准备浏览器 runtime；配置、状态和安装问题见[环境说明](references/environment.md)。实际返回 `challenge` / `auth_required` 时进入人工认证，遵守登录、验证码、付费墙和访问控制边界。
- 消费统一 acceptance，并核对任务要求的响应、资产和实际文件。保留来源及影响任务的降级。
- PDF 正文以现有转换器输出为边界，不清洗或修复内容。

## 按需参考

普通阅读无需预读 reference；消歧、复杂批量或特殊任务再查[工作流](references/workflow.md)，其余按需读取：

- 选择参数：只要材料用 `target="supplementary"`；随正文取材料用 `target="paper", strategy.asset_profile="all"`。先读[任务目标](references/presets.md#任务目标)和[共同规则](references/presets.md#共同规则)，再选适用预设：[临时阅读](references/presets.md#1-临时阅读)、[可缓存阅读](references/presets.md#2-可缓存阅读)、[单篇归档](references/presets.md#3-单篇本地归档)、[仅探测](references/presets.md#4-批量可读性分诊)或[批量归档](references/presets.md#5-批量本地归档)。自定义输出组合时再查该文件的 CLI/MCP 落盘矩阵。
- 验收：仅探测直接读[探测核对与报告](references/acceptance.md#探测核对与报告)；独立材料任务直接读[补充材料验收](references/acceptance.md#补充材料验收)；正文抓取或复用读[七个分面](references/acceptance.md#七个分面)和[响应验收](references/acceptance.md#响应验收)。均按[最终报告](references/acceptance.md#最终报告)交付；资产、文件、批量章节只在适用时读。
- 附件或指定图件阅读：按[材料与图件交接](references/reading-handoff.md)复用已有文件/URL，交给宿主 reader。
- 精确参数或返回字段：按需查[工具契约](references/tool-contract.md)的对应章节；内部一致性诊断仅在异常或用户要求时读。
- 凭证、runtime 或工具链实际影响任务时，读[环境参考](references/environment.md)的对应章节；普通抓取无需预读更新机制。
- 选用 CLI 时，读 [CLI 工作流](references/cli-workflow.md)的单篇或批量章节；入口不可用时再读窄 fallback。
- 失败、限流、需解释的降级或准备重试时，读[失败处理](references/failure-handling.md)的对应章节。
