# 验收

## 七个分面

回执 acceptance 包含 overall、identity、fetch、content、asset、output、provenance，以及 has_fulltext/has_abstract、token_estimate 和 asset_summary。`target_satisfied` 与退出码共用目标满足判断；`status` 是生命周期。结合实际文件判断交付。按任务需要读取逐篇 schema-v3 manifest 的 `acceptance`（如 `content.semantic_losses`、`provenance`）获取完整细节；不要仅凭退出码或文件名认定已取得全文。

## 响应验收

区分 fulltext、abstract_only、metadata_only、unavailable。降级全文仍可能满足任务，保留影响当前回答的来源、语义损失或失败原因。请求的格式、资产范围不代表已经交付；正文截断标记与 reader 输出截断是不同的事实。

## 探测核对与报告

check 结果只说明探测时的可用性信号，不表示已获取或阅读正文。按输入 index/query 关联论文身份。

## 补充材料验收

只要材料时使用 target supplementary，核对实际材料清单、身份、状态与文件路径：asset_summary.local 是已落盘项，not_archived 是只发现链接的项，failed 是下载失败项。完整与部分下载按实际验收报告区分；`asset_not_archived` 等问题会出现在顶层原因码。随正文获取材料使用 asset-profile all。

## 最终报告

交付用户要求的答案或文件，引用实际阅读的正文、图件或附件。不能把“工具取得全文”“请求读取完整范围”表述为“已通读全文”。局部任务说明相关证据即可；只说明真正影响当前结果的缺失、错误或降级。
