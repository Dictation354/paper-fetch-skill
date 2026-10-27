# Tool Contract

按当前问题只读对应章节：[标题解析](#标题解析)、[单篇抓取](#单篇抓取)、[cache](#cache-query-contract)、[batch probe](#batch-probe-contract)、[batch fetch](#batch-fetch-contract)、[错误字段](#error-contract)或 [catalog](#static-provider-catalog)。浏览器预检参数见 Browser Preflight Contract，资产参数见 Fetch Notes；[内部一致性诊断](#内部一致性诊断)仅在异常或用户要求时展开。

任务意图到显式参数以及实际写盘影响以 [`presets.md`](presets.md) 的 CLI/MCP 独立矩阵为准；本文件列出的默认值只描述兼容运行时，不能代替 agent-facing 预设传参。

## MCP Tools

### 标题解析

`resolve_paper(query | title, authors, year)` 在抓取前规范化 DOI、URL 或标题查询，并暴露歧义。标题输入先解析出 DOI 或落地页，再交给 `fetch_paper`。`acceptance.identity=resolved` 要求 DOI，或同时 verified、unique 的 canonical landing identity；title、单一 publisher domain 或候选域本身不能证明唯一身份。

### 单篇抓取

所有工具成功/失败 JSON payload 顶层使用 `schema_version=2`。`fetch_paper(...)` 成功响应含兼容 `status="ok"`、原值不变的 `source`、可空 `acquisition={provider,route,representation,transport,fallback_used}`、七分面紧凑 `acceptance`、溯源信息及 `token_estimate_breakdown={abstract,body,refs}`，并按需附带 `article`、`markdown`、`metadata`。`save_markdown=true` 时 `article/markdown=null`，返回路径、元数据、acceptance 和诊断字段；落盘组合归[预设](presets.md#五个预设)，任务结论归[验收](acceptance.md#七个分面)。

抓取自动准备 managed runtime；机制与异常处理只查[环境参考](environment.md#运行时准备与授权)。

### 独立补充材料任务

参数组合见[任务目标](presets.md#任务目标)，结果核对见[补充材料验收](acceptance.md#补充材料验收)。

`fetch_paper(query=..., target="supplementary")` 和 `batch_fetch(queries=[...], target="supplementary")` 使用独立材料任务。`target` 默认 `paper`；`supplementary` 不调用正文充分性检查、正文组装或正文 PDF fallback，正文付费不影响公开材料发现。材料范围由现有 provider 定义，包含明确补充区、Source Data、Extended Data 和多媒体，普通数据仓库链接不自动纳入；不支持的来源返回 `not_supported`。正文的 `asset_profile`、引用和 token 渲染选项不影响此范围。

返回 `target="supplementary"`、`has_fulltext=false`、`article=null`，以及 `supplementary={assets,asset_failures,discovery_complete,identity_verified,source_urls}`。Markdown 只含材料名称、来源链接和本地路径；`save_markdown=true` 只保存 `<paper-stem>_supplementary.md` 材料索引。`no_download=true` 或 artifact 禁止资产落盘时，保留发现清单，标记 `archive_state="not_archived"`，不声称下载完成。

acceptance v2 增量字段 `target="supplementary"`、`content_requested=false`，`content="unavailable"`（正文未请求）；按身份、发现、文件和来源验收。全部材料下载成功为 `complete`，部分成功或发现但未归档为 `degraded`，全部下载失败保留具体原因。只有完整检查且未发现材料时，返回 `status="no_result"`、空清单和来源记录。正文与补充请求指纹隔离；`prefer_cache=true` 的补充命中要求发现完整、身份匹配且所需文件仍存在。随正文获取材料用 `target="paper", strategy={"asset_profile":"all"}`。

### 其它工具入口

- `list_cached(download_dir=...)` / `get_cached(doi, download_dir=..., detail="full|compact", preferred_only=false, modes=..., strategy=..., include_refs=..., max_tokens=...)`: 多轮会话重新抓取前，在同一个显式 cache scope 内读取当前索引；已知 DOI 优先使用请求敏感的 `get_cached` compact 结果。
- `provider_status(provider=None, group=None, detail="full|compact")`: 返回 catalog-backed 本地静态诊断，不调用远程出版商 API；已知 provider 时应筛选，避免把全 catalog checks 放入上下文。
- `browser_preflight(provider=None, test_url=None, timeout_ms=None, browser_user_agent=None, storage_state_path=None, save_storage_state=true, detail="full|compact")`: 对一个或全部 browser provider 运行 live HTML 预检；会访问出版社页面，默认可能更新过滤后的 storage-state，但不运行 PDF fallback、自动认证或 runtime 安装。
- `batch_resolve(queries, concurrency)` / `batch_check(queries, mode, concurrency)`: 默认 `concurrency=1`，允许范围 `1..8`，每次最多 `50` 个查询；`batch_check` 的 `mode` 默认且仅允许 `"metadata"`，单篇也使用此入口。
- `batch_fetch(queries, concurrency, ...)`: 对 `1..50` 篇执行真实全文抓取，复用 `fetch_paper` 的 modes/strategy/cache/artifact/Markdown 参数；默认只返回按输入 index 排列的紧凑 manifest/acceptance 记录，不返回多篇完整正文。

## Browser Preflight Contract

- 先做 `provider_status` / CLI `doctor` 静态检查；只有需要真实链路证明时再运行 MCP `browser_preflight` / CLI `paper-fetch browser-preflight`。静态 `ready` 不是远端页面健康或访问授权证明。仅在实际 fetch 或按需预检明确要求时，由用户执行 `paper-fetch auth <provider>`。
- 未传 `provider` 时，MCP 与 CLI 都检查 runtime catalog 中全部 browser provider 的内置样例。诊断已知目标时显式限定 provider；不默认执行 live 工具。
- `test_url` 和 `storage_state_path` 只允许与一个显式 `provider` 一起使用。`test_url` 必须是无内嵌凭据的 HTTP(S) URL；`timeout_ms` 范围为 `1..600000`。`save_storage_state=false` 只关闭本轮保存，仍可读取已有 storage-state；默认 `true` 可能创建或原子更新 provider storage-state 文件。
- 工具 annotations 为 open-world、非只读、非 destructive、非 idempotent：它会使用 Camoufox runtime 打开出版社页面，也可能写 storage-state。它不调用 PDF fallback，且 `auth_attempted=false`；challenge、验证码、付费或登录边界不会被自动绕过。
- preflight 启动前自动准备 managed runtime；静态诊断仍只读，缺少 Python 依赖返回 `not_configured`。具体机制归[环境参考](environment.md#运行时准备与授权)。
- 每个 provider 独立返回 `ready`、`challenge`、`auth_required`、`network_timeout`、`extraction_error`、`runtime_error` 或 `cancelled`，并给出唯一 `status/reason_code/stage/message/next_action` 契约。前一个 provider 的 challenge/runtime failure 不会删除其它已完成结果；取消会保留取消前的结果，并停止调度后续 provider。
- `detail="compact"` 的每项严格只有 `provider/status/reason_code/stage/message/next_action`；`full` 另含 provider label、脱敏目标/最终 URL、title、storage-state 保存诊断和 browser/page diagnostics。顶层始终显式报告 `pdf_fallback_attempted=false`、`auth_attempted=false` 和逐状态汇总。
- browser runtime 失败沿用 fetch trace 的结构化 code，例如仍存在的 `browser_context_create_failed` 和 `browser_page_create_failed`；调用方应读取返回 code，而不是维护穷举静态列表。custom binary 不会被自动删除或更新。
- 支持 progress 的宿主会收到开始、逐 provider 完成和最终完成通知。已执行预检时，`ready` 表示可继续目标 fetch；`challenge` / `auth_required` 需人工 auth，`runtime_error` 按 [`environment.md`](environment.md#运行时准备与授权) 处理。

## Cache Query Contract

- `get_cached` 默认 `detail="full"`、`preferred_only=false`，保留既有 `entries`、`preferred` 和 index 字段。`preferred_only=true` 的 full 响应只在 `entries` 中保留优选 Markdown/primary payload，并把 `preferred.assets` 置空；`entry_summary` 仍统计 scope 中全部已证明条目。
- 缓存查询使用 `detail="compact"`；需要后续 prefer-cache fetch 复用时，显式传相同的 `modes`、`strategy`、`include_refs`、`max_tokens` 和 `download_dir`。临时阅读适用范围按 [`presets.md`](presets.md#本地优先决策树) 处理。compact 不返回 `entries`、完整正文、sidecar payload 或资产数组，只返回优选 Markdown/primary entry、内容/置信度、acceptance/asset/warning 摘要、sidecar/request 状态与稳定 SHA-256 fingerprint。
- 顶层 `status="hit"` 只表示该 DOI 在当前 scope 有身份可证明的 entry。fetch-envelope 是否满足请求直接读取 `request_satisfied`；工具已检查 sidecar、身份、scope 和请求匹配，agent 不手工重算。需要解释 mismatch 时再读[内部一致性诊断](#内部一致性诊断)。
- `cached_request` / `cached_request_fingerprint` 描述被选中的 sidecar；`requested_request` / `requested_request_fingerprint` 描述本次查询。FetchEnvelope cache 以 DOI + request fingerprint 保存多版本 sidecar，同一 DOI 的 modes、strategy、`include_refs`、`max_tokens` 变体可以并存，不再由最后一次窄请求覆盖富请求。读取优先精确 fingerprint，再按质量/时间检查兼容候选；不兼容 entry 仍只能得到 `request_status="mismatch"`。
- fingerprint 包含摘要化 `credential_scope`，不保存秘密或本地 state 内容。Browser scope 绑定实际 provider/backend、解析路径和内容摘要，只有成功注入的 state 才算使用。带 API token/storage-state capability 的调用在精确 sidecar 缺失或不满足请求时可单向复用 public sidecar；public 调用不能读取 private sidecar，不同 private scope 之间也不能复用。cache index、`list_cached`、`get_cached` 与 fetch 共用该可见性边界；非 sidecar artifact 保留自身可信 scope，legacy/多 scope 歧义 entry 不可见。
- `sidecar.status` 明确区分 `ready`、`missing`、`corrupt`、`unreadable`、`version_mismatch`、`extraction_revision_mismatch`、`doi_mismatch`、`invalid_scope` 等状态。损坏/旧版/错误 DOI sidecar 以及 `identity_status="no_proven_entries"` 都令 `request_satisfied=false`，但 cache miss 仍是正常路由结果，不是工具失败。
- 查询始终限制在显式 `download_dir`，不跨 scope 搜索、不联网。compact acceptance 是当前索引/sidecar 快照的摘要；它不承诺满足未传入的未来请求，命中后仍进入统一 acceptance/report。

## Error Contract

- `ambiguous`：`candidates` 给出身份候选。
- `no_access`：凭证、entitlement 或访问上下文不足。
- `rate_limited`：读取 `retry_after_seconds` / cooldown 和 provider lane。
- `error`：其它失败，读取 `reason` 及存在的 `code/error_category/http_status`。

CLI runtime fetch 的退出码为 `ambiguous=2`、`no_access=3`、`rate_limited=4`；argparse/参数校验也可能 exit 2，应结合结构化字段区分。暂停条件归[工作流](workflow.md#blocking-白名单)，重试动作与上限归[失败处理](failure-handling.md#分层与总尝试次数)。

## 输入与返回契约

- 当前九个工具在 `tools/list` 中的 `output_schema` 都为空，不发布协议级 `outputSchema`。`CallToolResult.structured_content` 继续返回带 `schema_version=2` 的版本化 payload；调用方按工具文档和实际字段消费，不把它误称为 output schema。
- 以当前工具公开 schema 为参数事实源：`modes=article|markdown|metadata`、`include_refs=none|top10|all`、`strategy.asset_profile=none|body|all`、`strategy.require_local_body_assets`、`strategy.require_full_size_body_assets`、`artifact_mode=markdown-assets|all|none`、`batch_check` 的 `mode=metadata`，以及 cache `detail=full|compact`。Full-size 自动隐含 local；两项默认关闭且只对 `body|all` 生效。
- batch `queries` 的公开 schema 和运行时验证都要求 `1..50` 项，`concurrency` 要求 `1..8`；所有公开工具输入对象及嵌套 strategy/budget 对象均拒绝未知字段（`additionalProperties=false`）。
- 兼容请求仍可使用既有 nested `strategy={...}`，包括 `inline_image_budget`；字符串枚举在 Pydantic validator 中继续做去空白和大小写规范化。规范化不是放宽值域，未知枚举、越界数字、过长数组和额外字段会在已注册工具函数执行前失败。

## Batch Probe Contract

- `batch_check(mode="metadata")` 调用低成本全文可用性 probe，只把 `probe_state=likely_yes|unknown` 作为信号；`likely_yes` 不是已抓取正文或已验证 `has_fulltext`。
- 独立 `has_fulltext` 工具与 `batch_check(mode="article")` 已移除，不保留别名。省略 `mode` 或显式传 `"metadata"` 均可；旧工具调用、article 模式沿用现有工具/参数错误机制。
- 单篇调用 `batch_check(queries=[query])`，从 `results[0]` 读取 `probe_state`、`evidence`、`warnings` 和 `error`。歧义等探测失败包装在逐项 `error`（包含 `candidates`），整批仍是正常工具返回，不能继续依赖旧单篇顶层错误语义。
- 顶层保留 `schema_version=2`、`mode="metadata"`、`results`、`aborted`、`abort_reason` 和 `progress`。成功项保留现有空字段：`has_fulltext/content_kind/has_abstract/source/acquisition/token_estimate/token_estimate_breakdown=null`，`source_trail/trace=[]`；`likely_has_fulltext` 在 `likely_yes` 时为 true，否则为 null。
- `batch_resolve` / `batch_check` 的 `results` 始终与输入等长、保持原顺序；每项都有稳定 1-based `index`、原 `query`、终态 `status`、结构化 `error` 和 `provider_lane`。`not_scheduled` 是必须保留的终态，顶层 progress 分别报告 `terminal/completed/not_scheduled`，不能把未执行项伪报为完成。
- Title/generic 输入按解析后的 provider lane 调度；已知 DOI/DOI URL 使用规范身份。`batch_resolve` 成功结果的 `provider_lane` 来自实际解析身份；一个 provider 的 cooldown 只停止该 lane 后续提交。
- 同批规范 DOI 相同的检查只执行一次，结果映射回全部原始输入。
- 单次调用最多 50 条。更大输入在调用前保留原始 1-based index，按原顺序切成最多 50 条的连续块，把块内结果映射回原 index 后排序合并。
- resolve、probe/fetch 和 acceptance 等阶段保持依赖有序；同一阶段的独立条目可显式设置 `concurrency=1..8` 受控并发，不假定默认值为 3。
- 代理级重试、provider lane 限流和失败报告只遵循 [`failure-handling.md`](failure-handling.md)。它与底层 HTTP Retry-After/5xx retry 分层；相同 `prefer_cache=false` 请求重跑不得称为绕过缓存。

仅探测时按[探测核对与报告](acceptance.md#探测核对与报告)完成任务，不要求全文 acceptance，也不自动升级为抓取。用户要求真实正文检查时使用 `batch_fetch`，以每项 `acceptance` 判断获取结果；下面的 compact 示例不交付阅读正文。需要完整阅读或多篇比较时直接使用[单篇阅读预设](presets.md#1-临时阅读)或读取合格本地文件。无需落盘的批量正文检查显式调用以下现有参数组合（不传 `batch_results`，不改变 `batch_fetch` 默认值）：

```python
batch_fetch(
    queries=[...],
    concurrency=4,
    modes=["article"],
    include_refs="all",
    max_tokens="full_text",
    detail="compact",
    save_markdown=False,
    no_download=True,
    prefer_cache=False,
    artifact_mode="none",
    strategy={"asset_profile": "none"},
)
```

## Batch Fetch Contract

- `batch_fetch` 是结构化 MCP 全文批量入口；`batch_resolve` 只解析身份，`batch_check(mode="metadata")` 只做低成本 probe。需要 shell 原生批量文件、既有 CLI 自动命名或人工直接检查 JSONL 时仍优先 CLI；需要宿主 progress/cancel、结构化结果或无需解析 CLI stdout 时使用 `batch_fetch`。CLI 批量能力没有被移除。
- 输入沿用 `fetch_paper` 的 `target`、`modes`、`strategy`、`include_refs`、`max_tokens`、`prefer_cache`、`no_download`、`artifact_mode`、`save_markdown`、`markdown_output_dir`、`markdown_filename` 和 `download_dir` 语义；`queries` 限 `1..50`，`concurrency` 限 `1..8`。多条输入不能共用一个 `markdown_filename`。
- 默认 `detail="compact"`，每项只返回稳定 1-based `index`、attempt/完成序号、run/record ID、request fingerprint、DOI/source、统一 acceptance 摘要、结构化 error、warning/code 摘要和带 size/SHA-256 的输出文件快照；结果数组始终按输入 index 排列，`completion_order` 单独保留实际完成顺序。
- `get_cached.asset_summary` 使用完整 v2 asset facet，含 audited/expected/discovered/attempted、accepted/fallback preview、failure/issue codes 与 remote-link facts；`batch_fetch.output_artifacts[]` 除 path/kind/hash 外还稳定声明 `route` 和 `failure_code`（不可用时为 `null`）。
- 只需少量正文片段时使用 `detail="bounded", content_max_chars=N`；`N` 是整批共享的 `1..100000` 字符上限，不是每篇上限。compact 不含 `article` 或 `markdown`，bounded 也只含受总上限约束的 Markdown 片段；核对逐项 `content_truncated`、`content_available_chars`、`content_returned_chars`，不能据截断片段宣称已读全文。多篇完整阅读直接逐篇使用阅读预设，已归档正文则读文件，不先批量抓取再重复获取。
- `batch_results=<path>` 可选；指定时只在整批结束后按输入顺序原子写一次最终 schema-v2 JSONL，每个输入一条终态记录。目标存在且内容不同时默认拒绝覆盖，`overwrite=true` 才允许替换。该文件不是 journal，不提供 audit、reconcile 或恢复语义。
- 一个 provider/resource lane 限流后只停止该 lane 的新项，其他 lane 继续；普通单项失败默认 `continue_on_error=true`，设为 false 才停止新的全批提交。支持 progress 的宿主会收到开始、逐终态和最终通知。
- Resolve 后以规范 DOI 建 canonical target table；DOI、DOI URL、大小写变体及多个 title alias 只在当前批次执行一个 representative，再按原 index/query 顺序 fan-out。不同请求之间不共享执行。
- 取消后保留已完成产物及 cancelled/not-scheduled 结果；取消提交边界之后的 worker 不得再提交文件或报告完成。
- 批量归档成功项通过 `output_artifacts` 返回路径和输出 hash；需要查询 cache 时使用相同 scope 的 `get_cached` 或 `list_cached`。`save_markdown`/`no_download`/`prefer_cache`/artifact/asset 的实际写盘组合与下方 Fetch Notes及 [`presets.md`](presets.md) 的 MCP 矩阵相同；显式 `batch_results` 是额外预期写盘产物。

## 运行时默认值（不是任务预设）

- `target="paper"`

- `modes=["article", "markdown"]`
- `strategy.asset_profile=null (provider default)`
- `strategy.require_local_body_assets=false`
- `strategy.require_full_size_body_assets=false`
- `strategy.allow_metadata_only_fallback=true`
- `include_refs=null`
- `max_tokens="full_text"`
- `prefer_cache=false`
- `no_download=false`
- `artifact_mode="markdown-assets"`
- `save_markdown=false`
- `markdown_output_dir=null`
- `markdown_filename=null`

`asset_profile=null` 使用最终 provider route 的默认资产范围；显式 `none|body|all` 覆盖它，其中 `none` 禁用资产解析和下载。

- `include_refs=null` behaves like `all` when `max_tokens="full_text"`.
- When `max_tokens` is a positive integer, `include_refs=null` behaves like `top10`.

## Fetch Notes

- Artifact、fetch sidecar、Markdown 和 cache index 原子提交；`overwrite=false` 时相同字节幂等、不同字节冲突，只有用户已有适用覆盖授权时才用 `overwrite=true` 替换。
- `prefer_cache=true` 对已经包含 DOI 的查询先做无网络规范化，再按 DOI + request fingerprint + credential scope 精确检查本地 FetchEnvelope variant；只有 cache miss 才进入 resolver/provider enrichment。标题等未知身份查询仍需先解析出 DOI。
- `artifact_mode`、`no_download`、`save_markdown` 的实际写盘影响只按[预设与落盘矩阵](presets.md#五个预设)选择；`save_markdown=true` 的响应形态见[单篇抓取](#单篇抓取)。
- `download_dir` 只定义本次请求与 `list_cached` / `get_cached` 共用的 cache scope；MCP 不把缓存索引或条目暴露为 resource。
- `strategy.asset_profile="body"` 或 `all` 时，可能额外返回少量关键本地图像，作为 `ImageContent` 输出；但 `save_markdown=true` 时不会附带 inline `ImageContent`。
- `body`/`all` 的正文图与 supplementary 在同一篇请求中共享固定运行时安全预算：普通 provider 默认不限制文件数，仍限制单文件 32 MiB、累计 256 MiB、64,000,000 像素、并发最多 4 且受 route cap 限制；arXiv source archive 独立限制最多 128 个 regular member。Direct 401/403 最多进入一次 browser-byte recovery，恢复仍受 MIME、实际字节、像素、累计预算、安全发布和取消检查约束，不得规避。预算失败读取 `asset_failures[*].reason` 的稳定 `asset_file_limit_exceeded` / `asset_bytes_per_asset_exceeded` / `asset_bytes_total_exceeded` / `asset_pixel_limit_exceeded` / `asset_content_encoding_unsupported`，不要从 warning 文案推断；内部预算终止时每个已发现但未保存的资产也必须有明确失败终态。
- Catalog host/sensitive-header 声明只服务 routing 和非授权执行策略，不自动成为 HTTP/PDF/body/supplementary allowlist。基础策略仍逐跳检查 HTTP(S)、标准端口、公网 DNS、userinfo、HTTPS downgrade 和跨域标准敏感头剥离；只有调用方显式传入 `allowed_hosts` 时才额外 fail closed。
- `strategy.require_local_body_assets=true` 要求全部正文逻辑资产本地化；`strategy.require_full_size_body_assets=true` 进一步拒绝 accepted/fallback preview，并隐含 local。失败只把 asset/overall acceptance 降为 `degraded`，不把已取得全文改成 fetch failure。两项进入 request/cache fingerprint、manifest、单篇与 batch acceptance。
- 每个成功/失败资产可带不含 URL 的 `asset_timing`，分解 queue、DNS policy validation、connect-to-headers/TTFB、body stream、browser recovery、retry wait、conversion、save 和 total；聚合时间不能当作签名 URL 诊断载体。
- 可选 `strategy.inline_image_budget={max_images,max_bytes_per_image,max_total_bytes}` 用于调节默认内联图像上限：`3` 张图、每张 `2 MiB`、总计 `8 MiB`；任一最终值为 `0` 都会禁用内联图像。
- 如果返回了资源，判断图片缺失前先检查 `article.assets[*].render_state`、`download_tier`、`preview_accepted`、`content_type`、`downloaded_bytes`、`width` 和 `height`。发生 direct/browser 恢复时还可读取向后兼容的 `browser_backend`、`final_fetcher` 和 `recovery_attempts`；CLI JSON、MCP 与 cache sidecar 原样往返这些字段。跨 adapter 机器分类只读取 `issue_codes`，不从 warning 文案重分类。
- `article.quality.semantic_losses.table_layout_degraded_count` 表示源表 span/列定义异常导致布局无法可靠验证；合法合并单元格成功展开只属于规范化，不计为降级；`table_semantic_loss_count` 才是表格内容可能真的丢失的更强信号。
- HTML/XML 公式先校验源 TeX，通过时保留内部命令、空白和环境；失败时只从同节点唯一配对的 MathML 转换并再校验。全部失败保留源 TeX，无源 TeX 时沿用图片、文字或缺失回退。`article.quality.semantic_losses.formula_diagnostics` 保留源 TeX、最终 LaTeX、校验错误、后端和样式降级，降级沿用统一 acceptance。PDF 正文不进入此流程。

## Local Markdown and Cache Identity

- `download_dir` 是 cache scope。`get_cached` 和 `list_cached` 只读该目录中的当前索引，不跨目录搜索，也不因 miss 联网。
- 本地 Markdown 只有两种可信身份来源：`save_markdown=true` 后由已知 envelope DOI + 实际写入路径显式注册；或 YAML front matter 经结构化解析后同时含 `doi`、`source`、布尔 `has_fulltext`、`content_kind` 和当前 acquisition。缺字段、旧版本或损坏 front matter 不能作为命中。文件名或正文里的 DOI 文本不能证明归属。
- Sidecar、Markdown 或资产成功写入后，会在当前 scope 中显式增量注册并记录内容 SHA-256；读取 cache 不扫描 loose files，也不修复或迁移旧索引。
- DOI URL、大小写和合法特殊字符都通过 `normalize_doi()` 后比较。错误 DOI、坏 YAML、metadata 缺字段和目录外路径不会作为命中返回。
- `preferred.markdown` 优先有效 fulltext，再按 `completed_at`（缺失时按 mtime）选最新版本；entry 的 `identity_proof` 说明归属证据，Markdown entry 还返回 `source`、`has_fulltext`、`content_kind`、`completed_at` 与内容 SHA-256。
- `list_cached()` 与 `get_cached()` 只信任当前版本索引和仍通过 DOI、scope、stat/hash 校验的显式注册条目；旧版、未知版或损坏索引不会被静默迁移或信任。
- fetch-envelope 复用直接读取 `request_satisfied`，本地 Markdown 归属不替代请求匹配。
- 当前预设允许且具备 scope 时，已知 DOI 的本地优先流程使用 `get_cached(doi, download_dir=<scope>, detail="compact", preferred_only=true, modes=..., strategy=..., include_refs=..., max_tokens=...)`；只有 DOI 未知且确需浏览 scope 时使用 `list_cached()`。只有 `request_satisfied=true` 才能把同一请求交给后续 prefer-cache fetch 复用，且继续传同一 `download_dir`。

## Static Provider Catalog

- `resource://paper-fetch/provider-catalog` 是 MCP provider/source/capability 的机器可读权威入口；需要选择 `provider_hint`、`preferred_providers`、status/preflight 路径或解释公开 source 时先读该 resource，不从工具 description 或本文推测静态名单。
- resource 返回 `schema_version`、`tool_version`、逐 provider 的 `sources`、带 `transport=api|browser|http` 的 routes、`asset_default`、browser/runtime/status/preflight capabilities 和 `source_provider_map`。不要另维护静态名单。
- resource 只描述当前 runtime 能力，不代表本地依赖已就绪或远端页面可访问。本地静态状态继续调用 `provider_status`；browser 真实页面健康度继续调用 open-world `browser_preflight`，并保留人工认证与访问控制边界。

仓库维护中的 exact replay 只提供离线、canonical raw + expected contract 的 extractor
回归，不证明当前用户的凭据、browser runtime 或受保护全文可用；skill 不得据此跳过
`provider_status`、必要的 `browser_preflight` 或人工授权边界。

## 内部一致性诊断

本节仅用于异常或用户要求的诊断；普通任务直接消费工具结论，不重复执行以下内部校验。

### acceptance 与 trace

- acceptance wire schema 为 v2（`schema_version=2`、`minimum_reader_schema_version=2`）。单篇响应、批量逐项摘要、manifest 和 cache 的七分面由同一统一验收报告投影；异常时检查载体是否对应同一请求与产物，不从 warning 或 `has_fulltext` 重建结论。
- 完整 trace 只在 fetch/cache payload 顶层出现，`quality.trace` 已删除。Envelope、acceptance 与 manifest 的完整 trace event count 应一致；两个 retry 的同 code 是两条事实，不按 marker 去重。`quality` 中的 source trail 是摘要，不能回拼成第二份 trace。
- acquisition 应与 catalog route、source owner 和 trace fallback 事实一致；缺失时保留 partial，不从兼容 `source` 猜测。冲突 routing signal 下，weak provider 的 `no_access` 保留诊断并继续 strong DOI/provider candidate，只有 strong identity 的 access boundary 才停止 waterfall。

### 资产计数与别名

- asset facet 分别记录 `accepted_preview`、`fallback_preview` 和有序去重 `issue_codes`；`preview = accepted_preview + fallback_preview`。accepted preview 且无其它 issue 可以 complete；publisher 接受的公式位图不因尺寸小或内容重复另造 placeholder。fallback preview 对应 `asset_fidelity_degraded`，不等同于 `asset_download_failure`。
- 严格 local/full-size 的 requirement 与 `*_satisfied`、`has_local_body_assets`、`all_body_assets_local`、`all_body_assets_full_size` 和 body discovered/attempted/local/full-size/preview/failed/not-archived/remote-only 计数由工具生成。分母只含需要独立 binary 的正文逻辑资产；无 remote/failure 且已有内联语义的 table/formula/figure 不算缺少文件。local 要求全部落盘且无 failure、not-archived 或 remote-only；full-size 还拒绝 accepted/fallback preview。
- 资产按 provider 合并后的逻辑对象计数。Springer/Nature `media.springernature.com/lwNN/...` 预览别名与对应 `/full/...` 下载记录由既有 full-size promotion 规则合并；全尺寸已有本地路径时，预览别名不再作为第二个 `missing_path` / remote-only 资产进入 Manifest。无对应本地记录的真实远端资产仍按原规则验收。agent 不重新合并别名或推导 preview 计数。

### cache 匹配

- `request_satisfied` 已涵盖 sidecar version、extraction revision、payload DOI、acquisition、scope、`cached_request_matches()` 严格请求匹配及全部请求 modes；诊断时读取返回的 sidecar/request 状态与 fingerprint，不用手算替代该布尔值。
- FetchEnvelope sidecar 当前 version 5 并要求 acquisition；v4 及更旧 sidecar 失效后重新抓取，既有 Markdown 不删除。缺失、损坏或请求 mismatch 均按正常 cache miss 路由。
