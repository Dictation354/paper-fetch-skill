# Failure Handling

本文件是代理级重试、限流和失败报告的唯一长规则事实源。`SKILL.md`、MCP prompt 与其它 reference 只保留链接、运行时事实或简短护栏，不另建重试规则。

## 目录

- [分层与总尝试次数](#分层与总尝试次数)
- [批量分诊和并发](#批量分诊和并发)
- [失败决策表](#失败决策表)
- [降级结果和质量警告](#降级结果和质量警告)
- [最终报告](#最终报告)

## 分层与总尝试次数

- 对同一规范目标和同一任务意图，代理层最多执行 **初次尝试 + 2 次有意义的重试**，即最多 3 次工具调用尝试。消歧、修正参数或改变认证/运行时状态后的再次调用都计入该上限。
- `paper-fetch` 的底层 HTTP transport 会独立处理允许的 Retry-After、5xx 和网络瞬态重试。一次工具调用内部发生的 transport retry 不增加代理层 `attempt`；工具返回失败后，代理也不得把底层已经耗尽的重试当成理由额外突破 3 次上限。
- “有意义”要求在下一次调用前记录可观察变化：规范 query、工具参数、认证/授权、provider/browser 状态、网络状态或 Retry-After/cooldown 至少一项发生变化。只改措辞、立即原样重跑或重复相同失败路线不算。
- `prefer_cache=false` 本来就是 `fetch_paper` 的兼容默认值。初次调用已经是 `false` 时，再传相同值不是“绕过缓存”；只有从实际使用的 `prefer_cache=true` 改为 `false`，且 trace/cache 证据表明缓存结果与当前请求不符时，才能准确报告为改变缓存策略。
- 每次尝试保留 `attempt=1..3`、触发失败、调用参数、相对上次的变化、结果和终止/继续决定。不要修改底层 HTTP retry 算法，也不要自动执行认证。

## 批量分诊和并发

- `batch_check(mode="metadata")` 是较低成本的 likely probe，只产生 `probe_state=likely_yes|unknown` 的证据。`likely_yes` 表示存在可读信号，不能报告成已经抓取正文、已经验收全文或已验证 `has_fulltext=true`。
- `batch_check(mode="article")` 会为每项执行真实 article fetch，成本和副作用都更高；其 `has_fulltext` / `content_kind` 仍须经过 acceptance 才能成为完成结论。
- 在切块前给输入保留原始 1-based `index`。每次 `batch_resolve` / `batch_check` 最多 50 条；超过 50 条时按原顺序切为连续块，例如 113 条为 `1..50`、`51..100`、`101..113`。把块内结果映射回原 index，最终按原 index 排序，不按完成顺序或块内序号重新编号。
- `batch_fetch` 同样每次最多 50 条，并直接返回 input-ordered terminal records 与独立 `completion_order`；不要按完成顺序重排。单项普通失败默认继续，其结构化 acceptance/error 进入最终报告；显式 `continue_on_error=false` 才停止全批后续新提交。
- 阶段之间保持依赖有序：先 resolve/去重，再 probe 或 fetch，最后 acceptance/report。同一阶段内身份独立的条目可使用显式 `concurrency=1..8` 受控并发；根据 provider、宿主容量和任务规模选择，不假定默认并发为 3。
- 收到 `rate_limited` 后立即停止向相同 provider lane 提交新项，保留尚未调度项和 `retry_after_seconds`/cooldown；不相关 provider lane 可以继续。等待期满后若仍需重试，也受单项最多 3 次代理尝试约束。

## Error Contract

兼容的短状态摘要如下；具体动作和上限始终以下表为准：

- `ambiguous`: Contains `candidates`; prompt the user to choose and retry.
- `no_access`: Credentials or entitlements are missing; retry only after auth or entitlement state changes.
- `rate_limited`: Back off and retry later.
- `error`: Any other failure; inspect `reason`.

### 失败决策表

优先读取结构化 `status`、`code`、`error_category`、`http_status` 和 `retry_after_seconds`，再用 `reason`、`source_trail` 与 `warnings` 补充判断；字段存在时不得另写字符串分类器。CLI runtime fetch 的 `ambiguous=2`、`no_access=3`、`rate_limited=4` 保持不变；argparse/参数校验也可能 exit 2，但必须按参数错误而不是歧义处理。

| 类别与触发条件 | 重试前必须发生的参数/状态变化 | 终止条件 | 用户报告字段 |
|---|---|---|---|
| `ambiguous`：结构化结果含多个 `candidates`，或身份不能唯一确定 | 用户或可靠上下文选择候选；把 query 改为选定的规范 DOI/落地页 | 未选择、仍多候选，或达到 attempt 3；不得自动猜测 | 原 index/query、`status`、候选 DOI/标题、选择结果、attempt |
| `validation_error` / 参数错误：Pydantic、tool schema、argparse 或范围/组合校验失败 | 修正被点名的字段、类型、范围或互斥组合；参数不变时不调用 | 无法从契约确定正确值、修正后同错，或达到 attempt 3 | `code`、字段路径、`reason`、旧值→新值、attempt |
| 确定性 `no_result` / `not_supported` / `invalid_json` / `response_schema_mismatch` / `response_too_large` / `unsupported_url_scheme` / `unsafe_redirect` / `empty_article_shell` / 解析错误：合法响应在同一输入和路线下稳定缺少标识、正文、API schema 或受支持格式，或请求违反下载安全边界 | 只有规范 identity、所需 mode、合法 provider route、响应版本、明确缩小的响应范围、浏览器临时会话状态或输入内容确实变化时才重试；browser fast path 可把同一调用内尚未持久化的 provider-scoped seed 传给正常重试，不得把 HTML challenge 当 JSON 修补，也不得放宽响应上限、scheme 或重定向安全校验来重试 | 没有新的输入/路线/临时会话状态、相同解析/schema/安全边界证据重复，或达到 attempt 3 | `code/error_category`、规范 identity、provider/route、`http_status`、脱敏响应摘要、`source_trail`、确定性证据、attempt |
| `no_access` / `not_configured` / HTTP 401/403：缺少凭证、授权、entitlement 或合法访问上下文 | `missing_env` 已补齐，或用户完成手动认证/授权且状态可观察地改变；不得自动 auth | 认证状态未变、合法访问边界不允许继续、用户不授权，或达到 attempt 3 | `status/code`、provider、`http_status`、`missing_env`、所需用户动作、attempt |
| `rate_limited` / HTTP 429 / 出现 `retry_after_seconds`：provider 或资源 lane 限流 | 停止同 provider 新提交并尊重 Retry-After；无该字段时使用工具记录的 cooldown/policy，明确报告服务端未给时长 | 冷却尚未结束、任务不适合等待、冷却后仍限流，或达到 attempt 3 | provider/lane、`http_status`、`retry_after_seconds` 或 cooldown、未调度 index、attempt |
| `network_error` / `timeout` / `tls_error` / `dns_error` / `connection_reset` / `connection_closed`，或已返回的 HTTP 5xx | 确认底层 transport 已结束；等待/backoff 后观察网络状态变化，或在契约允许时改变 provider route/环境；不得立即原样重跑 | 网络/路由状态无变化、相同瞬态重复，或达到 attempt 3 | `error_category`、`http_status`、provider/route、等待或环境变化、attempt |
| browser transient：trace/preflight 出现 `browser_runtime_exited`、`browser_connect_timeout`、`cdp_connect_failed`、`browser_context_create_failed`、`browser_page_create_failed` 或 `camoufox_request_failed`，且不含确定性 challenge/auth 证据 | 先读取 `backend/code/stage/exit_code/stderr_summary/diagnostic_path` 并检查静态配置；在执行面可用时做 live browser preflight，`provider_status()` 不是 live 健康证明。只有 browser profile/CDP endpoint、backend、认证状态、运行时健康、请求参数或环境发生变化才重试 | 无状态变化、preflight 为 challenge/auth_required/runtime_error 且未解决、相同失败重复，或达到 attempt 3 | provider、backend、精确 browser code/stage、脱敏摘要、diagnostic artifact、preflight/trace、变化项、`source_trail`、attempt |
| `cancelled` / `request_cancelled`：用户、宿主或 cooperative cancellation 终止 | 只有用户明确恢复任务并重新确认仍需执行时才开始新的尝试；批量先保留 cancelled/not-scheduled index | 未恢复、任务已过期，或达到 attempt 3 | 已完成/取消/未调度 index、产物、恢复条件、attempt |
| 未分类 `error`：结构化字段不足，且不匹配上述类别 | 先收集 `reason`、trace、provider status 与实际产物；只有诊断导出具体参数/状态变化时重试 | 无可执行变化、同错重复，或达到 attempt 3 | `status/code/error_category`、`reason`、provider、trace/产物、诊断和 attempt |

`aws_waf_challenge` / `cloudflare_challenge` 是等待 provider readiness 后仍存在的确定性验证页。只有合法 browser profile/storage state、网络授权或人工验证状态发生变化时才可重试；不得把初始 HTTP 202、隐藏 `noscript` 文案或单独 REST 请求当成最终结论，也不得自动绕过 challenge。报告应保留 `status=challenge`、精确 reason code、`challenge_provider`、`legacy_reason_code`、HTTP 状态、readiness trace、页面关闭前采集的脱敏诊断和 attempt。

## 降级结果和质量警告

- `abstract_only` / `metadata_only` 是降级成功，不是已验证全文。告诉用户证据边界；若摘要或元数据足以完成意图则停止，只有用户确需全文且能改变 provider/访问/策略时才按上表计入重试。
- Browser HTML 失败后 PDF/ePDF fallback 成功仍是降级成功：顶层可为 `status=ok`，但必须保留 HTML failure trace/code，且 `acceptance.overall=degraded`；不得只报告 PDF 成功或把 browser 原因抹掉。
- `artifact_mode=all` 且 HTML 页面已到达但 extraction/availability 失败时，优先读取返回的 `diagnostic_path` 和 manifest 中 `kind=diagnostic` 的 `diagnostic.json` / `page-sanitized.html`。自动诊断是脱敏页面结构，不含原始失败 HTML、截图、Cookie/Authorization 或 URL query token。
- `asset_profile=body|all` 返回资源但图片似乎缺失时，先检查 `article.assets[*].render_state`、`download_tier`、`width`、`height`、`content_type`、`downloaded_bytes` 和 `source_trail`。`download_tier=preview` 在尺寸达标且 source trail 记录接受时可以合格，不自动触发全文重试。
- Browser/runtime 能力和 provider/source 归属只从 `resource://paper-fetch/provider-catalog` 读取，不在本文件维护静态 provider 列表。Browser HTML 资产通常只报告 `full_size` 或 `preview`；challenge recovery 失败时检查 `quality.asset_failures[*].reason` 与 `recovery_attempts`，direct HTTP 转换可能报告 `source_converted`。
- `table_layout_degraded_count` 是源 span/列定义异常导致布局无法可靠验证的警告；合法合并单元格成功展开不计为降级。`table_semantic_loss_count` 才是内容可能不完整的更强信号；真实降级都应进入 acceptance，而不是无条件重抓全文。
- 本地没有 PDF/Markdown 只表示 cache/local miss，不证明论文不可读；按工作流继续 probe/fetch，不得仅据此报告 `unreadable`，也不得把未请求资产报告成下载失败。

## 最终报告

每项至少报告原始 1-based index/query、规范 identity、最终 `status/code/error_category`、provider/source、尝试总数、每次有意义变化、Retry-After/cooldown、降级或 acceptance、实际产物路径，以及仍需用户完成的动作。批量还要报告已完成、失败、限流、取消和未调度的 index；不得用完成顺序替代输入顺序。
