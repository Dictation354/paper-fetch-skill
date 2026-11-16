# 验收

## 七个分面

回执 acceptance 包含 overall、identity、fetch、content、asset、output、provenance，以及 has_fulltext/has_abstract。按任务需要读取 manifest 中对应细节；不要仅凭退出码或文件名认定已取得全文。

## 响应验收

区分 fulltext、abstract_only、metadata_only、unavailable。降级全文仍可能满足任务，保留影响当前回答的来源、语义损失或失败原因。请求的格式、资产范围不代表已经交付；正文截断标记与 reader 输出截断是不同的事实。

## 探测核对与报告

check 结果只说明探测时的可用性信号，不表示已获取或阅读正文。按输入 index/query 关联论文身份。

## 补充材料验收

只要材料时使用 target supplementary，核对实际材料清单、身份、状态与文件路径。随正文获取材料使用 asset-profile all。

## 最终报告

交付用户要求的答案或文件，引用实际阅读的正文、图件或附件。不能把“工具取得全文”“请求读取完整范围”表述为“已通读全文”。局部任务说明相关证据即可；只说明真正影响当前结果的缺失、错误或降级。
