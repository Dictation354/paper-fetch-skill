# Tool Contract

本文件承接 `SKILL.md` 中移出的工具说明。处理论文抓取时，入口流程优先；需要精确参数、默认值或返回契约时再读取本文件。

任务意图到显式参数以及实际写盘影响以 [`presets.md`](presets.md) 的 CLI/MCP 独立矩阵为准；本文件列出的默认值只描述兼容运行时，不能代替 agent-facing 预设传参。

## MCP Tools

- 所有 tool 成功/失败 JSON payload 顶层使用 `schema_version=2`。新 fetch/cache payload 的完整 trace 只在顶层出现；`quality.trace` 已删除。FetchEnvelope sidecar 当前为 version 5 并要求 acquisition；v4 及更旧 sidecar 明确失效后重新抓取，既有 Markdown 不删除。
- `resolve_paper(query | title, authors, year)`: 在抓取前规范化 DOI、URL 或标题查询，并尽早暴露歧义。标题输入必须先解析出 DOI 或落地页，再交给 `fetch_paper(...)`。
- `fetch_paper(..., browser_auto_prepare=None)`: 返回稳定 JSON 载荷；成功响应包含兼容态 `status="ok"`、原值不变的 `source`、可空的 `acquisition={provider,route,representation,transport,fallback_used}`、七分面紧凑 `acceptance`、溯源信息、`token_estimate_breakdown={abstract,body,refs}`，并按需附带 `article`、`markdown`、`metadata`。`acceptance.overall` 才是任务级结论；当 `save_markdown=true` 时，响应会改为紧凑结果，只保留路径、元数据、acceptance 和诊断字段。MCP managed runtime 准备默认关闭；需按需安装/修复/更新时显式传 `true`。
- `acceptance.identity=resolved` 必须有 DOI，或同时具备 verified、unique 的 canonical landing identity；title、单一 publisher domain 或候选域本身不构成唯一身份。冲突 routing signal 下，weak provider 的 `no_access` 会保留诊断并继续 strong DOI/provider candidate，只有 strong identity 的 access boundary 才停止 waterfall。
- `list_cached(cache_mode="index|refresh|rescan")` / `get_cached(doi, download_dir=..., detail="full|compact", preferred_only=false, modes=..., strategy=..., include_refs=..., max_tokens=...)`: 多轮会话重新抓取前，在同一个显式 cache scope 内检查缓存；已知 DOI 优先使用请求敏感的 `get_cached` compact 结果。
- `has_fulltext(query)`: 使用解析结果、Crossref 元数据、轻量 Elsevier 元数据探测和落地页 HTML meta 做低成本全文可用性探测，不触发完整抓取流程。
- `provider_status(provider=None, group=None, detail="full|compact")`: 返回 catalog-backed 本地静态诊断，不调用远程出版商 API；已知 provider 时应筛选，避免把全 catalog checks 放入上下文。
- `browser_preflight(provider=None, test_url=None, timeout_ms=None, browser_user_agent=None, storage_state_path=None, save_storage_state=true, detail="full|compact", browser_auto_prepare=None)`: 对一个或全部 browser provider 运行 live HTML 预检；会访问出版社页面，默认可能更新过滤后的 storage-state，但不运行 PDF fallback 或自动认证。MCP 默认不准备 managed runtime，传 `browser_auto_prepare=true` 才允许。
- `batch_resolve(queries, concurrency)` / `batch_check(queries, mode, concurrency, browser_auto_prepare=None)`: 默认 `concurrency=1`，允许范围 `1..8`，每次最多 `50` 个查询；只有 article check 可能进入浏览器准备。
- `batch_fetch(queries, concurrency, ..., browser_auto_prepare=None)`: 对 `1..50` 篇执行真实全文抓取，复用 `fetch_paper` 的 modes/strategy/cache/artifact/Markdown 参数；默认只返回按输入 index 排列的紧凑 manifest/acceptance 记录，不返回多篇完整正文。

## MCP Prompts（不是 Tools）

- `summarize_paper` 和 `verify_citation_list` 是 MCP prompt 模板，不是普通 tool；不得把它们放进 `tools/call`，也不得把 prompt 渲染本身报告成已经解析、抓取或验收论文。
- 支持 MCP prompts 的宿主先通过 `prompts/list` 与 `prompts/get` 选择并渲染模板，再按模板调用上面的普通 tools。`summarize_paper` 仍需执行身份解析、本地/cache、必要 fetch 和 [`acceptance.md`](acceptance.md)；`verify_citation_list` 仍需保留原 index，执行 `batch_resolve`、按需 `batch_check`/真实 fetch，并恢复输入顺序。
- 不支持 MCP prompts 的宿主使用等价工具流程：单篇总结走 `resolve_paper` → 请求敏感的 `get_cached` → 必要的 `fetch_paper` → acceptance → 基于已验收正文总结；citation list / 引用列表走 `batch_resolve` → DOI 去重 → `batch_check(mode="metadata")` 分诊 → 对确需正文的项调用 `fetch_paper`/`batch_fetch` → acceptance/report。重试和限流仍只遵循 [`failure-handling.md`](failure-handling.md)。

## Browser Preflight Contract

- 固定顺序是 `provider_status` / CLI `doctor` 静态检查 → MCP `browser_preflight` / CLI `paper-fetch browser-preflight` live HTML 预检 → 仅在结果或实际 fetch 明确要求时由用户执行 `paper-fetch auth <provider>`。静态 `ready` 不是远端页面健康或访问授权证明。
- MCP 与 CLI 直接共用 `run_browser_provider_preflight()` 和 provider HTML bootstrap。未传 `provider` 时，两者都按 browser runtime catalog 顺序检查全部 provider，并使用各自内置样例；不会默认执行该 live 工具。
- MCP 同一服务进程中，PNAS、AMS、MDPI、Royal Society、Annual Reviews、ACS、IOP、T&F 的成功 preflight 可把已验收 HTML 一次性交给紧随其后的正式 fetch；命中只减少重复导航，正式 metadata、Markdown/资产抽取和 acceptance 都会重新执行。该内部状态通过既有 `source_trail`/diagnostics 标记观察，不新增或改变公开工具 schema；CLI 跨进程以及 Wiley、IEEE、Science、AIP 不承诺这种复用。
- `test_url` 和 `storage_state_path` 只允许与一个显式 `provider` 一起使用。`test_url` 必须是无内嵌凭据的 HTTP(S) URL；`timeout_ms` 范围为 `1..600000`。`save_storage_state=false` 只关闭本轮保存，仍可读取已有 storage-state；默认 `true` 可能创建或原子更新 provider storage-state 文件。
- 工具 annotations 为 open-world、非只读、非 destructive、非 idempotent：它会使用 Camoufox runtime 打开出版社页面，也可能写 storage-state。它不调用 PDF fallback，且 `auth_attempted=false`；challenge、验证码、付费或登录边界不会被自动绕过。
- `browser_auto_prepare` 未传时 MCP/库默认 `false`；显式 `true` 才允许官方 Camoufox CLI 在跨进程锁内安装、修复或做 24 小时更新检查。支持 logging 的宿主会收到阶段与命令输出；显式 custom binary 永不进入该维护路径。
- 每个 provider 独立返回 `ready`、`challenge`、`auth_required`、`network_timeout`、`extraction_error`、`runtime_error` 或 `cancelled`，并给出唯一 `status/reason_code/stage/message/next_action` 契约。前一个 provider 的 challenge/runtime failure 不会删除其它已完成结果；取消会保留取消前的结果，并停止调度后续 provider。
- `detail="compact"` 的每项严格只有 `provider/status/reason_code/stage/message/next_action`；`full` 另含 provider label、脱敏目标/最终 URL、title、storage-state 保存诊断和 browser/page diagnostics。顶层始终显式报告 `pdf_fallback_attempted=false`、`auth_attempted=false` 和逐状态汇总。
- browser runtime 失败沿用 fetch trace 的稳定 code，包括 `browser_runtime_prepare_cancelled`、`browser_runtime_prepare_failed`、`browser_runtime_prepare_timeout`、`browser_runtime_repair_failed`、`cdp_connect_failed`、`browser_context_create_failed`、`browser_page_create_failed`。full diagnostics 在可用时保留 stage、版本状态和有界命令输出；custom binary 不会被自动删除或更新。
- 支持 progress 的宿主会收到开始、逐 provider 完成和最终完成通知。`challenge` / `auth_required` 的下一步是显式人工 auth；`runtime_error` 先修复静态配置或本地 runtime；`ready` 才继续目标 fetch。

## Cache Query Contract

- `get_cached` 默认 `detail="full"`、`preferred_only=false`，保留既有 `entries`、`preferred` 和 index 字段。`preferred_only=true` 的 full 响应只在 `entries` 中保留优选 Markdown/primary payload，并把 `preferred.assets` 置空；`entry_summary` 仍统计 scope 中全部已证明条目。
- 常规 cache-first 决策使用 `detail="compact"`，并显式传与随后 `fetch_paper` 相同的 `modes`、`strategy`、`include_refs`、`max_tokens` 和 `download_dir`。compact 不返回 `entries`、完整正文、sidecar payload 或资产数组，只返回优选 Markdown/primary entry、内容/置信度、acceptance/asset/warning 摘要、sidecar/request 状态与稳定 SHA-256 fingerprint。
- 顶层 `status="hit"` 只表示该 DOI 在当前 scope 有身份可证明的 index entry，不表示 fetch-envelope 可复用。只有 `request_satisfied=true` 才表示 sidecar version、extraction revision、payload DOI 与 acquisition 均有效，既有 `cached_request_matches()` 严格匹配本次请求，且 payload 包含全部请求 modes。
- `cached_request` / `cached_request_fingerprint` 描述被选中的 sidecar；`requested_request` / `requested_request_fingerprint` 描述本次查询。FetchEnvelope cache 以 DOI + request fingerprint 保存多版本 sidecar，同一 DOI 的 modes、strategy、`include_refs`、`max_tokens` 变体可以并存，不再由最后一次窄请求覆盖富请求。读取优先精确 fingerprint，再按质量/时间检查兼容候选；不兼容 entry 仍只能得到 `request_status="mismatch"`。
- fingerprint 同时包含摘要化 `credential_scope`，不保存秘密或本地 state 内容。Browser scope 绑定实际 provider/backend、最终解析路径和内容摘要，并且只有成功注入的 state 才算 use；只配置空 profile/path 仍是 public。查询先尝试当前 runtime 的精确 scope；带 API token/storage-state capability 的调用在精确 sidecar 缺失或不满足请求时可以单向复用 public sidecar，public 调用绝不读取 private sidecar，不同 private scope 之间也不复用。loader、inspector 和 compact projection 使用同一个 variant selector，每个候选只解析一次；cache index/list/get、entry template 和 MCP resource 也应用同一可见性边界。非 sidecar artifact 保留自身可信 scope，不能由较新的 canonical sidecar 降级；legacy/多 scope 歧义 entry 不可见。已发布的 resource URI 每次读取都会重新验证当前 capability、index scope 与 scoped file integrity，撤销凭据或删除 storage state 后旧 URI 立即失效。
- `sidecar.status` 明确区分 `ready`、`missing`、`corrupt`、`unreadable`、`version_mismatch`、`extraction_revision_mismatch`、`doi_mismatch`、`invalid_scope` 等状态。损坏/旧版/错误 DOI sidecar 以及 `identity_status="no_proven_entries"` 都令 `request_satisfied=false`，但 cache miss 仍是正常路由结果，不是工具失败。
- 查询始终限制在显式 `download_dir`，不跨 scope 搜索、不联网。compact acceptance 是当前索引/sidecar 快照的摘要；它不承诺满足未传入的未来请求，命中后仍进入统一 acceptance/report。

## Input / Output Schema Layers

- native MCPServer schema 与 Codex/stdio host-safe schema 分开验证。native schema 保留 `FetchStrategyInput` 的结构化 Pydantic 模型和运行时对象，不把 `strategy` 退化为无约束字典；host-safe schema 由同一组 Pydantic request model 生成并内联嵌套结构，不包含宿主无法解析的 `$ref`。
- output schema 仍由 typed Pydantic/TypedDict contract 生成；发布到 `tools/list` 时只移除展示性 `title` 注解与可选字段的 `default: null`。真实 `properties.title` / `properties.default` 字段、`required`、枚举、范围及运行时结构化输出验证均保留。
- `src/paper_fetch/mcp/schemas.py` 是枚举、范围和规范化的事实源：`modes=article|markdown|metadata`、`include_refs=none|top10|all`、`strategy.asset_profile=none|body|all`、`artifact_mode=markdown-assets|all|none`、batch `mode=article|metadata`、cache `mode=index|refresh|rescan`，以及 cache `detail=full|compact`。工具只暴露当前已实现的字段。
- batch `queries` 的公开 schema 和运行时验证都要求 `1..50` 项，`concurrency` 要求 `1..8`；所有公开工具输入对象及嵌套 strategy/budget 对象均拒绝未知字段（`additionalProperties=false`）。
- 兼容请求仍可使用既有 nested `strategy={...}`，包括 `inline_image_budget`；字符串枚举在 Pydantic validator 中继续做去空白和大小写规范化。规范化不是放宽值域，未知枚举、越界数字、过长数组和额外字段会在已注册工具函数执行前失败。

## Batch Probe Contract

- `batch_check(mode="metadata")` 调用低成本全文可用性 probe，只把 `probe_state=likely_yes|unknown` 作为信号；`likely_yes` 不是已抓取正文或已验证 `has_fulltext`。
- `batch_check(mode="article")` 对每项执行真实 article fetch，成本和副作用高于 metadata probe；返回结果仍需 acceptance 后才能报告全文完成。
- `batch_resolve` / `batch_check` 的 `results` 始终与输入等长、保持原顺序；每项都有稳定 1-based `index`、原 `query`、终态 `status`、结构化 `error` 和 `provider_lane`。`not_scheduled` 是必须保留的终态，顶层 progress 分别报告 `terminal/completed/not_scheduled`，不能把未执行项伪报为完成。
- `batch_check` 为每个 logical item 建独立 child `RuntimeContext`。Title/generic 输入先在该 child 中解析并缓存 identity，再按 resolved provider lane 调度；已知 DOI/DOI URL 只做本地 canonical 解析并用 initial lane。`batch_resolve` 自身在执行解析前无法知道 title provider，所以该阶段可能用 generic lane，但成功结果的 `provider_lane` 来自实际 resolved identity。一个 provider 的 cooldown 只停止该 lane 后续提交。
- 同批规范 DOI 相同的检查只执行一次并安全 fan-out；child 之间只共享线程安全 HTTP transport/不可变环境，不共享 provider client、session、CookieJar、trace/timing 或 browser context。Duplicate、取消和未调度 child 最终均幂等关闭。
- 单次调用最多 50 条。更大输入在调用前保留原始 1-based index，按原顺序切成最多 50 条的连续块，把块内结果映射回原 index 后排序合并。
- resolve、probe/fetch 和 acceptance 等阶段保持依赖有序；同一阶段的独立条目可显式设置 `concurrency=1..8` 受控并发，不假定默认值为 3。
- 代理级重试、provider lane 限流和失败报告只遵循 [`failure-handling.md`](failure-handling.md)。它与底层 HTTP Retry-After/5xx retry 分层；相同 `prefer_cache=false` 请求重跑不得称为绕过缓存。

## Batch Fetch Contract

- `batch_fetch` 是结构化 MCP 全文批量入口；`batch_resolve` 只解析身份，`batch_check(mode="metadata")` 只做低成本 probe。需要 shell 原生批量文件、既有 CLI 自动命名或人工直接检查 JSONL 时仍优先 CLI；需要宿主 progress/cancel、结构化结果或无需解析 CLI stdout 时使用 `batch_fetch`。CLI 批量能力没有被移除。
- 输入沿用 `fetch_paper` 的 `modes`、`strategy`、`include_refs`、`max_tokens`、`prefer_cache`、`no_download`、`artifact_mode`、`save_markdown`、`markdown_output_dir`、`markdown_filename` 和 `download_dir` 语义；`queries` 限 `1..50`，`concurrency` 限 `1..8`。多条输入不能共用一个 `markdown_filename`。
- 默认 `detail="compact"`，每项只返回稳定 1-based `index`、attempt/完成序号、run/record ID、request fingerprint、DOI/source、统一 acceptance 摘要、结构化 error、warning/code 摘要和带 size/SHA-256 的输出文件快照；结果数组始终按输入 index 排列，`completion_order` 单独保留实际完成顺序。
- `get_cached.asset_summary` 使用完整 v2 asset facet，含 audited/expected/discovered/attempted、accepted/fallback preview、failure/issue codes 与 remote-link facts；`batch_fetch.output_artifacts[]` 除 path/kind/hash 外还稳定声明 `route` 和 `failure_code`（不可用时为 `null`）。
- 临时阅读需要少量正文时使用 `detail="bounded", content_max_chars=N`；`N` 是整批共享的 `1..100000` 字符上限，不是每篇上限。compact 不含 `article` 或 `markdown`，bounded 也只含受总上限约束的 Markdown 片段，不能用来无界回传多篇全文。
- 默认不创建 run manifest。只有显式给出 `run_manifest`、`batch_results` 或 `resume` 才启用 PF-012 persistence；新 run 默认拒绝覆盖不同内容的同名摘要/事件文件，`overwrite=true` 才允许原子替换，相同内容是幂等成功。`resume=<run-manifest>` 不能同时传新的 manifest/event 路径，并要求有序输入、工具版本和 fetch/render/output semantic fingerprint 与原 run 一致。`execution_policy` 单列 concurrency、retry/rate wait 与 continue-on-error，可在 resume 时覆盖；已知旧格式会在验证后迁移。
- 持久化 run 复用同一 `RunManifestStore`、append-only v2 attempts、只读 audit 和 shared runner。只有 audit 判定 reusable 的最新 attempt 会跳过；失败、stale、缺失或低于请求的 index 追加下一 attempt。任务取消写 `cancelled`，适配层意外中断写 `interrupted`；两者都尽力为完整 `1..N` index 集合写终态 record。
- runner 对 provider/resource lane 增量提交。一个 lane 限流后只停止该 lane 的新项，其他 lane 继续；普通单项失败默认 `continue_on_error=true`，设为 false 才停止新的全批提交。支持 progress 的宿主会收到开始、逐终态和最终通知；已在途 worker 通过同一 `cancel_check` 协作退出。
- Resolve 后以规范 DOI 建 canonical target table；DOI、DOI URL、大小写变体及多个 title alias 只执行一个 representative，再按原 index/query/attempt 顺序 fan-out。重叠 MCP 单篇/批量请求使用同一个进程内 key：canonical DOI + 完整 `FetchPaperRequest` 语义 + capability scope + canonical cache/Markdown 目录。等待者取消不取消 owner；结果/异常以安全快照隔离；任何 request、scope 或目录差异都不合并。
- 单篇 async 与每个 batch worker 都用一个贯穿 fetch、sidecar、Markdown、index 和最终输出的 runtime context。取消先设置 cooperative event 与线性化 commit fence，再等待有界 grace；fence 返回后晚 worker 只能清理 staging，不能提交文件或发送错误的完成进度。
- 归档成功项返回 `saved_markdown_path`、输出 hash 和可读的 cache `resource_uri`；服务器同步 default/scoped cache resources 后宿主可用 `resources/read` 读取。`save_markdown`/`no_download`/`prefer_cache`/artifact/asset 的实际写盘组合与下方 Fetch Notes 及 [`presets.md`](presets.md) 的 MCP 矩阵相同；显式持久化还会额外写 run summary 和 JSONL events，因此不能再宣称完全不落盘。

## Recommended Defaults

- `modes=["article", "markdown"]`
- `strategy.asset_profile=null (provider default)`
- `strategy.allow_metadata_only_fallback=true`
- `include_refs=null`
- `max_tokens="full_text"`
- `prefer_cache=false`
- `no_download=false`
- `artifact_mode="markdown-assets"`
- `save_markdown=false`

`asset_profile=null` 由最终 provider route 的编译 `asset_scope` 选择；显式
`none|body|all` 保持调用者覆盖，其中 `none` 必须在资产 resolver/网络调用前生效。
- `markdown_output_dir=null`
- `markdown_filename=null`

- `include_refs=null` behaves like `all` when `max_tokens="full_text"`.
- When `max_tokens` is a positive integer, `include_refs=null` behaves like `top10`.

## Fetch Notes

- Artifact、fetch sidecar、Markdown 和 cache index 使用 path-scoped lock、唯一同目录 staging、flush/fsync 与原子 replace。`overwrite=false` 时相同字节幂等、不同字节冲突；`overwrite=true` 才允许串行替换。所有同请求提交使用同一个 runtime commit guard。
- `prefer_cache=true` 对已经包含 DOI 的查询先做无网络规范化，再按 DOI + request fingerprint + credential scope 精确检查本地 FetchEnvelope variant；只有 cache miss 才进入 resolver/provider enrichment。标题等未知身份查询仍需先解析出 DOI。
- `artifact_mode="none"` 会关闭 provider artifact 和资产落盘，但仍保留 MCP fetch-envelope sidecar/cache-index 用于 `prefer_cache`、`list_cached` 和资源暴露。
- `no_download=true` 会避免写入 provider 载荷、资源文件和 fetch-envelope sidecar。
- MCP 只有 `save_markdown=false`、`no_download=true`、`prefer_cache=false`、`artifact_mode="none"`、`strategy.asset_profile="none"` 的临时阅读组合才承诺完全不落盘。`no_download=true` 不覆盖 `save_markdown=true` 的显式 Markdown 输出。
- `save_markdown=true` 会把渲染后的全文 Markdown 写盘，并在成功时返回 `saved_markdown_path`。本轮 MCP 响应会设置 `markdown=null`、`article=null`，避免把全文正文放入上下文；仍保留 `metadata`、`quality`、`warnings`、`source_trail`、`trace` 和 `token_estimate_breakdown` 等诊断字段。
- 传入 `download_dir` 时，MCP 服务器还能在当前会话里暴露这个隔离目录对应的缓存资源。
- 支持 MCP 资源列表通知的宿主，可能在 `fetch_paper(...)`、`list_cached()` 或 `get_cached()` 改变缓存资源 URI 时收到 `resources/list_changed`。
- `strategy.asset_profile="body"` 或 `all` 时，可能额外返回少量关键本地图像，作为 `ImageContent` 输出；但 `save_markdown=true` 时不会附带 inline `ImageContent`。
- `body`/`all` 的正文图与 supplementary 在同一篇请求中共享固定运行时安全预算：默认 128 文件、单文件 32 MiB、累计 256 MiB、64,000,000 像素、并发最多 4 且受 route cap 限制。Browser 只发现 URL，远端二进制由 pinned direct transport 流式落盘；无法安全 stream 时返回 `browser_stream_unavailable`。预算失败读取 `asset_failures[*].reason` 的稳定 `asset_file_limit_exceeded` / `asset_bytes_per_asset_exceeded` / `asset_bytes_total_exceeded` / `asset_pixel_limit_exceeded` / `asset_content_encoding_unsupported`，不要从 warning 文案推断。
- 可选 `strategy.inline_image_budget={max_images,max_bytes_per_image,max_total_bytes}` 用于调节默认内联图像上限：`3` 张图、每张 `2 MiB`、总计 `8 MiB`；任一最终值为 `0` 都会禁用内联图像。
- 如果返回了资源，判断图片缺失前先检查 `article.assets[*].render_state`、`download_tier`、`preview_accepted`、`content_type`、`downloaded_bytes`、`width` 和 `height`。发生 direct/browser 恢复时还可读取向后兼容的 `browser_backend`、`final_fetcher` 和 `recovery_attempts`；CLI JSON、MCP 与 cache sidecar 原样往返这些字段。资产摘要满足 `preview = accepted_preview + fallback_preview`；跨 adapter 机器分类只读取 `issue_codes`，不从 warning 文案重分类。
- `article.quality.semantic_losses.table_layout_degraded_count` 表示源表 span/列定义异常导致布局无法可靠验证；合法合并单元格成功展开只属于规范化，不计为降级；`table_semantic_loss_count` 才是表格内容可能真的丢失的更强信号。
- 返回 Markdown 前，公式中的 LaTeX 会先对常见出版商宏做规范化处理，例如 `\updelta`、`\mspace{Nmu}`。

## Local Markdown and Cache Identity

- `download_dir` 是 cache scope。`get_cached`、refresh 和 rescan 只读该目录，不跨目录搜索，也不因 miss 联网。
- 本地 Markdown 只有两种可信身份来源：`save_markdown=true` 后由已知 envelope DOI + 实际 `saved_markdown_path` 显式注册；或 YAML front matter 经结构化解析后同时含 `doi`、`source`、布尔 `has_fulltext` 和 `content_kind`。新文件另含 acquisition；旧文件缺少时仍可读但值为 `null`，不能据此宣称 provenance complete。文件名或正文里的 DOI 文本不能证明归属。
- Cache refresh 只读取 Markdown 的 256 KiB 有界 front-matter 前缀；变化文件在锁外一次流式计算全文 SHA-256，未变化文件用 device/inode/size/mtime_ns 复用 index。50 DOI 批量或顺序 refresh 中，每个未变化 Markdown 最多打开一次；sidecar/Markdown 成功写入后走增量 upsert，不触发全目录重扫。
- DOI URL、大小写和合法特殊字符都通过 `normalize_doi()` 后比较。错误 DOI、坏 YAML、metadata 缺字段和目录外路径不会作为命中返回。
- `preferred.markdown` 优先有效 fulltext，再按 `completed_at`（缺失时按 mtime）选最新版本；entry 的 `identity_proof` 说明归属证据，Markdown entry 还返回 `source`、`has_fulltext`、`content_kind`、`completed_at` 与内容 SHA-256。
- `cache_mode="index"` 只读当前 manifest，`list_cached(..., cache_mode="refresh")` 校验/修复现有 manifest，`get_cached(doi)` 才刷新单个 DOI；`rescan` 从可证明的 sidecar/front matter 重建整个 index。v1 会在 refresh 时迁移到 v2 并删除无法重新证明的旧 Markdown；未知版本使用 rescan。
- fetch-envelope 是否满足当前请求仍唯一由 `cached_request_matches()` 按 modes、strategy、`include_refs` 和 `max_tokens` 严格判断；本地 Markdown 归属规则不会放宽该匹配。
- 已知 DOI 的本地优先流程使用 `get_cached(doi, download_dir=<scope>, detail="compact", preferred_only=true, modes=..., strategy=..., include_refs=..., max_tokens=...)`；只有 DOI 未知且确需浏览 scope 时使用 `list_cached()`。只有 `request_satisfied=true` 才能把同一请求交给后续 prefer-cache fetch 复用，且继续传同一 `download_dir`。

## Dynamic Provider Catalog

- `resource://paper-fetch/provider-catalog` 是 MCP provider/source/capability 的机器可读权威入口；需要选择 `provider_hint`、`preferred_providers`、status/preflight 路径或解释公开 source 时先读该 resource，不从工具 description 或本文推测静态名单。
- resource 直接从 runtime `ProviderSpec` 和 `SOURCE_PROVIDER_MAP` 生成，返回 `schema_version`、`tool_version`、provider/source 数量、逐 provider 的 `sources`、带 `transport=api|browser|http` 的 routes、`asset_default` 与 browser/runtime/status/preflight capabilities，以及完整 `source_provider_map`。新 provider 或 source 注册后无需同步第二张表。
- resource 只描述当前 runtime 能力，不代表本地依赖已就绪或远端页面可访问。本地静态状态继续调用 `provider_status`；browser 真实页面健康度继续调用 open-world `browser_preflight`，并保留人工认证与访问控制边界。

仓库维护中的 exact replay 与 scheduled canary 也不能改变上述语义：exact replay 是
离线、canonical raw + expected contract 的 extractor 回归；scheduled canary 只观察公开
direct route，连续三次同 route 失败才产生非阻塞 warning。两者都不证明当前用户的凭据、
browser runtime 或受保护全文可用，skill 不得据此跳过 `provider_status`、必要的
`browser_preflight` 或人工授权边界。
