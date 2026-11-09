# Failure Handling

失败、限流、需解释的降级或准备重试时读本文件。结构化状态与退出码见[错误契约](tool-contract.md#error-contract)，需要用户决定的事项见[工作流](workflow.md#blocking-白名单)。

## 分层与总尝试次数

- 同一规范目标、同一意图最多 **初次尝试 + 2 次有意义重试**；消歧、修正参数或改变认证/runtime 状态后的调用也计入。
- 底层 HTTP transport 独立处理 Retry-After、5xx 和网络瞬态重试，不增加 agent attempt，也不构成突破上限的理由。
- 重试前须有可观察变化：query、参数、认证/授权、provider/browser 状态、网络状态或 cooldown。立即原样重跑、只改措辞不算。记录 attempt、变化和结果即可；不修改底层 retry 算法或自动认证。
- 只有原调用实际用了 prefer_cache=true，且 cache/trace 显示请求不符，再改为 false 才能称为绕过缓存；重复 prefer_cache=false 没有改变缓存策略。

## 批量分诊和并发

保留[分块规则](presets.md#批量分块与证据等级)的原 index 和逐项终态。普通单项失败继续其它目标；batch_fetch 停止调度选项见[工具契约](tool-contract.md#batch-fetch-contract)。收到 rate_limited 时停止同 provider lane 新提交，保留未调度项和 retry_after_seconds/cooldown，不相关 lane 继续；冷却后仍受单项 3 次上限约束。

## 失败决策表

优先读 status/code/error_category/http_status/retry_after_seconds，再用 reason/source_trail/warnings 补充；不以字符串分类覆盖已有结构化字段。以下均在达到 attempt 3、相同失败重复或没有可执行变化时停止。

| 类别 | 可重试的变化或处理 | 额外停止条件 |
| --- | --- | --- |
| ambiguous / 身份不足 | 用户或可靠上下文唯一化候选后改用规范 DOI/落地页。 | 仍有歧义，不猜测。 |
| validation_error / 参数错误 | 按当前 schema 修正被点名的字段、类型、范围或互斥组合。 | 修正后仍同错或无法确定合法参数。 |
| 确定性 no_result / not_supported / 解析或 schema 错误 / response_too_large / 下载安全拒绝 / empty_article_shell | 仅在身份、支持的 route/mode、响应范围、输入或合法 profile/state 发生变化时重试；不修补 challenge HTML 冒充 JSON，不放宽安全边界或响应上限。 | 相同页面/状态指纹或确定性证据重复；empty_article_shell.retry_decision=stop_same_state 立即停止。 |
| no_access / not_configured / 401/403 | 补齐 missing_env，或用户完成人工认证/授权后确认状态变化；runtime 问题按[环境](environment.md#运行时准备与授权)处理。 | 授权未变、访问边界不允许或用户不授权。 |
| rate_limited / 429 | 尊重 Retry-After；缺时长时使用工具记录的 cooldown/policy，并如实说明。 | 冷却未结束、不适合等待或冷却后仍限流。 |
| network_error / timeout / TLS/DNS/连接错误 / 5xx | transport 已结束后等待/backoff，观察网络变化或采用契约允许的 route/环境变化。 | 无状态变化，不立即原样重跑。 |
| browser context/page/runtime 瞬态错误 | 读取 backend/code/stage/runtime_state/version/diagnostic_path，静态检查并修复实际配置或 runtime；provider_status 不是 live 健康证明。 | challenge/auth_required/runtime_error 尚未解决。 |
| cancelled / request_cancelled | 保留已完成、取消和未调度项；用户明确恢复后再开始。 | 用户未恢复或任务已过期。 |
| 未分类 error | 用 reason、trace、目标 provider status 和实际产物诊断，得到具体参数/状态变化后再试。 | 没有可执行变化。 |

aws_waf_challenge / cloudflare_challenge 表示受管后端支持的自动处理和 provider readiness 等待后仍存在验证页。只有合法 profile/state、网络授权或人工验证状态变化才可重试；不以初始 HTTP 202、隐藏 noscript 文案或单独 REST 请求替代最终结论。保留精确 reason code、challenge_provider、legacy_reason_code、HTTP 状态和脱敏 readiness/页面诊断。

## 降级结果和质量警告

- abstract_only / metadata_only 最多是 limited；若足以完成当前任务就交付，不自动增加获取范围。用户仍需全文且有可改变路线/访问条件时才重试。
- Browser HTML 失败后 PDF/ePDF 成功仍保留 HTML failure trace/code 和 acceptance 的降级；不只报告 PDF 成功。
- artifact_mode=all 的 extraction/availability 失败可返回 diagnostic_path 及 diagnostic.json/page-sanitized.html。按需读取脱敏诊断；不收集原始失败 HTML、截图或 secret。
- 资产、表格或公式降级消费[统一验收](acceptance.md#资产验收)，不自动重抓全文；仅具体字段异常时查[工具字段](tool-contract.md#fetch-notes)或[内部诊断](tool-contract.md#内部一致性诊断)。
- 本地/cache miss 不证明远端不可读；继续适用的 probe/fetch，未请求资产不报缺失。

## 最终报告

按[统一报告](acceptance.md#最终报告)说明受影响目标、具体原因和必要动作；技术字段、attempt 与状态变化、cooldown 证据按诊断或审计需要展开。批量保留所有终态的原 index，不以完成顺序替代输入顺序。
