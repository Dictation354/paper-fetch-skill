# Tool Contract

本文件承接 `SKILL.md` 中移出的工具说明。处理论文抓取时，入口流程优先；需要精确参数、默认值或返回契约时再读取本文件。

任务意图到显式参数以及实际写盘影响以 [`presets.md`](presets.md) 的 CLI/MCP 独立矩阵为准；本文件列出的默认值只描述兼容运行时，不能代替 agent-facing 预设传参。

## MCP Tools

- `resolve_paper(query | title, authors, year)`: 在抓取前规范化 DOI、URL 或标题查询，并尽早暴露歧义。标题输入必须先解析出 DOI 或落地页，再交给 `fetch_paper(...)`。
- `fetch_paper(...)`: 返回稳定 JSON 载荷，顶层包含溯源信息、`token_estimate_breakdown={abstract,body,refs}`，并按需附带 `article`、`markdown`、`metadata`；当 `save_markdown=true` 时，响应会改为紧凑结果，只保留路径、元数据和诊断字段。
- `list_cached(cache_mode="index|refresh|rescan")` / `get_cached(doi, download_dir=..., detail="full|compact", preferred_only=false, modes=..., strategy=..., include_refs=..., max_tokens=...)`: 多轮会话重新抓取前，在同一个显式 cache scope 内检查缓存；已知 DOI 优先使用请求敏感的 `get_cached` compact 结果。
- `has_fulltext(query)`: 使用解析结果、Crossref 元数据、轻量 Elsevier 元数据探测和落地页 HTML meta 做低成本全文可用性探测，不触发完整抓取流程。
- `provider_status(provider=None, group=None, detail="full|compact")`: 返回 catalog-backed 本地静态诊断，不调用远程出版商 API；已知 provider 时应筛选，避免把全 catalog checks 放入上下文。
- `browser_preflight(provider=None, test_url=None, timeout_ms=None, browser_user_agent=None, storage_state_path=None, save_storage_state=true, detail="full|compact")`: 对一个或全部 browser provider 运行 live HTML 预检；会访问出版社页面，默认可能更新过滤后的 storage-state，但不运行 PDF fallback 或自动认证。
- `batch_resolve(queries, concurrency)` / `batch_check(queries, mode, concurrency)`: 默认 `concurrency=1`，允许范围 `1..8`，每次最多 `50` 个查询。
- `batch_fetch(queries, concurrency, ...)`: 对 `1..50` 篇执行真实全文抓取，复用 `fetch_paper` 的 modes/strategy/cache/artifact/Markdown 参数；默认只返回按输入 index 排列的紧凑 manifest/acceptance 记录，不返回多篇完整正文。

## MCP Prompts（不是 Tools）

- `summarize_paper` 和 `verify_citation_list` 是 MCP prompt 模板，不是普通 tool；不得把它们放进 `tools/call`，也不得把 prompt 渲染本身报告成已经解析、抓取或验收论文。
- 支持 MCP prompts 的宿主先通过 `prompts/list` 与 `prompts/get` 选择并渲染模板，再按模板调用上面的普通 tools。`summarize_paper` 仍需执行身份解析、本地/cache、必要 fetch 和 [`acceptance.md`](acceptance.md)；`verify_citation_list` 仍需保留原 index，执行 `batch_resolve`、按需 `batch_check`/真实 fetch，并恢复输入顺序。
- 不支持 MCP prompts 的宿主使用等价工具流程：单篇总结走 `resolve_paper` → 请求敏感的 `get_cached` → 必要的 `fetch_paper` → acceptance → 基于已验收正文总结；citation list / 引用列表走 `batch_resolve` → DOI 去重 → `batch_check(mode="metadata")` 分诊 → 对确需正文的项调用 `fetch_paper`/`batch_fetch` → acceptance/report。重试和限流仍只遵循 [`failure-handling.md`](failure-handling.md)。

## Browser Preflight Contract

- 固定顺序是 `provider_status` / CLI `doctor` 静态检查 → MCP `browser_preflight` / CLI `paper-fetch browser-preflight` live HTML 预检 → 仅在结果或实际 fetch 明确要求时由用户执行 `paper-fetch auth <provider>`。静态 `ready` 不是远端页面健康或访问授权证明。
- MCP 与 CLI 直接共用 `run_browser_provider_preflight()` 和 provider HTML bootstrap。未传 `provider` 时，两者都按 browser runtime catalog 顺序检查全部 provider，并使用各自内置样例；不会默认执行该 live 工具。
- `test_url` 和 `storage_state_path` 只允许与一个显式 `provider` 一起使用。`test_url` 必须是无内嵌凭据的 HTTP(S) URL；`timeout_ms` 范围为 `1..600000`。`save_storage_state=false` 只关闭本轮保存，仍可读取已有 storage-state；默认 `true` 可能创建或原子更新 provider storage-state 文件。
- 工具 annotations 为 open-world、非只读、非 destructive、非 idempotent：它会打开 Chrome/CDP 与出版社页面，也可能写 storage-state。它不调用 PDF fallback，且 `auth_attempted=false`；challenge、验证码、付费或登录边界不会被自动绕过。
- 每个 provider 独立返回 `ready`、`challenge`、`auth_required`、`runtime_error` 或 `cancelled`，并给出 `reason_code`、`reason` 和 `next_action`。前一个 provider 的 challenge/runtime failure 不会删除其它已完成结果；取消会保留取消前的结果，并停止调度后续 provider。
- `detail="compact"` 的每项严格只有 `provider/status/reason_code/reason/next_action`；`full` 另含 provider label、目标/最终 URL、title、storage-state 保存诊断和 browser runtime diagnostics。顶层始终显式报告 `pdf_fallback_attempted=false`、`auth_attempted=false` 和逐状态汇总。
- 支持 progress 的宿主会收到开始、逐 provider 完成和最终完成通知。`challenge` / `auth_required` 的下一步是显式人工 auth；`runtime_error` 先修复静态配置或本地 runtime；`ready` 才继续目标 fetch。

## Cache Query Contract

- `get_cached` 默认 `detail="full"`、`preferred_only=false`，保留既有 `entries`、`preferred` 和 index 字段。`preferred_only=true` 的 full 响应只在 `entries` 中保留优选 Markdown/primary payload，并把 `preferred.assets` 置空；`entry_summary` 仍统计 scope 中全部已证明条目。
- 常规 cache-first 决策使用 `detail="compact"`，并显式传与随后 `fetch_paper` 相同的 `modes`、`strategy`、`include_refs`、`max_tokens` 和 `download_dir`。compact 不返回 `entries`、完整正文、sidecar payload 或资产数组，只返回优选 Markdown/primary entry、内容/置信度、acceptance/asset/warning 摘要、sidecar/request 状态与稳定 SHA-256 fingerprint。
- 顶层 `status="hit"` 只表示该 DOI 在当前 scope 有身份可证明的 index entry，不表示 fetch-envelope 可复用。只有 `request_satisfied=true` 才表示 sidecar version、extraction revision、payload DOI 均有效，既有 `cached_request_matches()` 严格匹配本次请求，且 payload 包含全部请求 modes。
- `cached_request` / `cached_request_fingerprint` 描述已存 sidecar；`requested_request` / `requested_request_fingerprint` 描述本次查询。改变 modes、strategy、`include_refs` 或 `max_tokens` 会得到 `request_status="mismatch"`，不能把 entry hit 升级为请求命中。
- `sidecar.status` 明确区分 `ready`、`missing`、`corrupt`、`unreadable`、`version_mismatch`、`extraction_revision_mismatch`、`doi_mismatch`、`invalid_scope` 等状态。损坏/旧版/错误 DOI sidecar 以及 `identity_status="no_proven_entries"` 都令 `request_satisfied=false`，但 cache miss 仍是正常路由结果，不是工具失败。
- 查询始终限制在显式 `download_dir`，不跨 scope 搜索、不联网。compact acceptance 是当前索引/sidecar 快照的摘要；它不承诺满足未传入的未来请求，命中后仍进入统一 acceptance/report。

## Input Schema Layers

- native FastMCP schema 与 Codex/stdio host-safe schema 分开验证。native schema 保留 `FetchStrategyInput` 的结构化 Pydantic 模型和运行时对象，不把 `strategy` 退化为无约束字典；host-safe schema 由同一组 Pydantic request model 生成并内联嵌套结构，不包含宿主无法解析的 `$ref`。
- `src/paper_fetch/mcp/schemas.py` 是枚举、范围和规范化的事实源：`modes=article|markdown|metadata`、`include_refs=none|top10|all`、`strategy.asset_profile=none|body|all`、`artifact_mode=markdown-assets|all|none`、batch `mode=article|metadata`、cache `mode=index|refresh|rescan`，以及 cache `detail=full|compact`。工具只暴露当前已实现的字段。
- batch `queries` 的公开 schema 和运行时验证都要求 `1..50` 项，`concurrency` 要求 `1..8`；所有公开工具输入对象及嵌套 strategy/budget 对象均拒绝未知字段（`additionalProperties=false`）。
- 兼容请求仍可使用既有 nested `strategy={...}`，包括 `inline_image_budget`；字符串枚举在 Pydantic validator 中继续做去空白和大小写规范化。规范化不是放宽值域，未知枚举、越界数字、过长数组和额外字段会在已注册工具函数执行前失败。

## Batch Probe Contract

- `batch_check(mode="metadata")` 调用低成本全文可用性 probe，只把 `probe_state=likely_yes|unknown` 作为信号；`likely_yes` 不是已抓取正文或已验证 `has_fulltext`。
- `batch_check(mode="article")` 对每项执行真实 article fetch，成本和副作用高于 metadata probe；返回结果仍需 acceptance 后才能报告全文完成。
- 单次调用最多 50 条。更大输入在调用前保留原始 1-based index，按原顺序切成最多 50 条的连续块，把块内结果映射回原 index 后排序合并。
- resolve、probe/fetch 和 acceptance 等阶段保持依赖有序；同一阶段的独立条目可显式设置 `concurrency=1..8` 受控并发，不假定默认值为 3。
- 代理级重试、provider lane 限流和失败报告只遵循 [`failure-handling.md`](failure-handling.md)。它与底层 HTTP Retry-After/5xx retry 分层；相同 `prefer_cache=false` 请求重跑不得称为绕过缓存。

## Batch Fetch Contract

- `batch_fetch` 是结构化 MCP 全文批量入口；`batch_resolve` 只解析身份，`batch_check(mode="metadata")` 只做低成本 probe。需要 shell 原生批量文件、既有 CLI 自动命名或人工直接检查 JSONL 时仍优先 CLI；需要宿主 progress/cancel、结构化结果或无需解析 CLI stdout 时使用 `batch_fetch`。CLI 批量能力没有被移除。
- 输入沿用 `fetch_paper` 的 `modes`、`strategy`、`include_refs`、`max_tokens`、`prefer_cache`、`no_download`、`artifact_mode`、`save_markdown`、`markdown_output_dir`、`markdown_filename` 和 `download_dir` 语义；`queries` 限 `1..50`，`concurrency` 限 `1..8`。多条输入不能共用一个 `markdown_filename`。
- 默认 `detail="compact"`，每项只返回稳定 1-based `index`、attempt/完成序号、run/record ID、request fingerprint、DOI/source、统一 acceptance 摘要、结构化 error、warning/code 摘要和带 size/SHA-256 的输出文件快照；结果数组始终按输入 index 排列，`completion_order` 单独保留实际完成顺序。
- 临时阅读需要少量正文时使用 `detail="bounded", content_max_chars=N`；`N` 是整批共享的 `1..100000` 字符上限，不是每篇上限。compact 不含 `article` 或 `markdown`，bounded 也只含受总上限约束的 Markdown 片段，不能用来无界回传多篇全文。
- 默认不创建 run manifest。只有显式给出 `run_manifest`、`batch_results` 或 `resume` 才启用 PF-012 persistence；新 run 默认拒绝覆盖同名摘要/事件文件，`overwrite=true` 才允许覆盖。`resume=<run-manifest>` 不能同时传新的 manifest/event 路径，并要求有序输入、工具版本和关键 fetch/output fingerprint 与原 run 一致。
- 持久化 run 复用同一 `RunManifestStore`、append-only v2 attempts、只读 audit 和 shared runner。只有 audit 判定 reusable 的最新 attempt 会跳过；失败、stale、缺失或低于请求的 index 追加下一 attempt。任务取消写 `cancelled`，适配层意外中断写 `interrupted`；两者都尽力为完整 `1..N` index 集合写终态 record。
- runner 对 provider/resource lane 增量提交。一个 lane 限流后只停止该 lane 的新项，其他 lane 继续；普通单项失败默认 `continue_on_error=true`，设为 false 才停止新的全批提交。支持 progress 的宿主会收到开始、逐终态和最终通知；已在途 worker 通过同一 `cancel_check` 协作退出。
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
- `markdown_output_dir=null`
- `markdown_filename=null`

- `include_refs=null` behaves like `all` when `max_tokens="full_text"`.
- When `max_tokens` is a positive integer, `include_refs=null` behaves like `top10`.

## Fetch Notes

- `prefer_cache=true` 会先把查询解析为 DOI，再尝试命中本地匹配的 FetchEnvelope sidecar，之后才走完整抓取流程。
- `artifact_mode="none"` 会关闭 provider artifact 和资产落盘，但仍保留 MCP fetch-envelope sidecar/cache-index 用于 `prefer_cache`、`list_cached` 和资源暴露。
- `no_download=true` 会避免写入 provider 载荷、资源文件和 fetch-envelope sidecar。
- MCP 只有 `save_markdown=false`、`no_download=true`、`prefer_cache=false`、`artifact_mode="none"`、`strategy.asset_profile="none"` 的临时阅读组合才承诺完全不落盘。`no_download=true` 不覆盖 `save_markdown=true` 的显式 Markdown 输出。
- `save_markdown=true` 会把渲染后的全文 Markdown 写盘，并在成功时返回 `saved_markdown_path`。本轮 MCP 响应会设置 `markdown=null`、`article=null`，避免把全文正文放入上下文；仍保留 `metadata`、`quality`、`warnings`、`source_trail`、`trace` 和 `token_estimate_breakdown` 等诊断字段。
- 传入 `download_dir` 时，MCP 服务器还能在当前会话里暴露这个隔离目录对应的缓存资源。
- 支持 MCP 资源列表通知的宿主，可能在 `fetch_paper(...)`、`list_cached()` 或 `get_cached()` 改变缓存资源 URI 时收到 `resources/list_changed`。
- `strategy.asset_profile="body"` 或 `all` 时，可能额外返回少量关键本地图像，作为 `ImageContent` 输出；但 `save_markdown=true` 时不会附带 inline `ImageContent`。
- 可选 `strategy.inline_image_budget={max_images,max_bytes_per_image,max_total_bytes}` 用于调节默认内联图像上限：`3` 张图、每张 `2 MiB`、总计 `8 MiB`；任一最终值为 `0` 都会禁用内联图像。
- 如果返回了资源，判断图片缺失前先检查 `article.assets[*].render_state`、`download_tier`、`content_type`、`downloaded_bytes`、`width` 和 `height`。
- `article.quality.semantic_losses.table_layout_degraded_count` 表示 Markdown 中表格布局被压平；`table_semantic_loss_count` 才是表格内容可能真的丢失的更强信号。
- 返回 Markdown 前，公式中的 LaTeX 会先对常见出版商宏做规范化处理，例如 `\updelta`、`\mspace{Nmu}`。

## Local Markdown and Cache Identity

- `download_dir` 是 cache scope。`get_cached`、refresh 和 rescan 只读该目录，不跨目录搜索，也不因 miss 联网。
- 本地 Markdown 只有两种可信身份来源：`save_markdown=true` 后由已知 envelope DOI + 实际 `saved_markdown_path` 显式注册；或 YAML front matter 经结构化解析后同时含 `doi`、`source`、布尔 `has_fulltext` 和 `content_kind`。文件名或正文里的 DOI 文本不能证明归属。
- DOI URL、大小写和合法特殊字符都通过 `normalize_doi()` 后比较。错误 DOI、坏 YAML、metadata 缺字段和目录外路径不会作为命中返回。
- `preferred.markdown` 优先有效 fulltext，再按 `completed_at`（缺失时按 mtime）选最新版本；entry 的 `identity_proof` 说明归属证据，Markdown entry 还返回 `source`、`has_fulltext`、`content_kind`、`completed_at` 与内容 SHA-256。
- `cache_mode="index"` 只读当前 manifest，`list_cached(..., cache_mode="refresh")` 校验/修复现有 manifest，`get_cached(doi)` 才刷新单个 DOI；`rescan` 从可证明的 sidecar/front matter 重建整个 index。v1 会在 refresh 时迁移到 v2 并删除无法重新证明的旧 Markdown；未知版本使用 rescan。
- fetch-envelope 是否满足当前请求仍唯一由 `cached_request_matches()` 按 modes、strategy、`include_refs` 和 `max_tokens` 严格判断；本地 Markdown 归属规则不会放宽该匹配。
- 已知 DOI 的本地优先流程使用 `get_cached(doi, download_dir=<scope>, detail="compact", preferred_only=true, modes=..., strategy=..., include_refs=..., max_tokens=...)`；只有 DOI 未知且确需浏览 scope 时使用 `list_cached()`。只有 `request_satisfied=true` 才能把同一请求交给后续 prefer-cache fetch 复用，且继续传同一 `download_dir`。

## Dynamic Provider Catalog

- `resource://paper-fetch/provider-catalog` 是 MCP provider/source/capability 的机器可读权威入口；需要选择 `provider_hint`、`preferred_providers`、status/preflight 路径或解释公开 source 时先读该 resource，不从工具 description 或本文推测静态名单。
- resource 直接从 runtime `ProviderSpec` 和 `SOURCE_PROVIDER_MAP` 生成，返回 `schema_version`、`tool_version`、provider/source 数量、逐 provider 的 `sources`、`asset_default` 与 browser/runtime/status/preflight capabilities，以及完整 `source_provider_map`。新 provider 或 source 注册后无需同步第二张表。
- resource 只描述当前 runtime 能力，不代表本地依赖已就绪或远端页面可访问。本地静态状态继续调用 `provider_status`；browser 真实页面健康度继续调用 open-world `browser_preflight`，并保留人工认证与访问控制边界。
