# Tool Contract

仅查当前需要的参数或返回字段。任务参数组合与落盘影响见[预设](presets.md)，验收与报告见[统一验收](acceptance.md)；下列运行时默认值不能替代任务预设。

## MCP Tools

### 标题解析

`resolve_paper(query | title, authors, year)` 规范化 DOI、URL 或标题并暴露歧义。fetch 内部解析标题；仅消歧或需要候选信息时独立调用 resolve。`acceptance.identity="resolved"` 要求 DOI，或同时 verified、unique 的 canonical landing identity；标题和 publisher domain 本身不能证明唯一身份。

### 单篇抓取

`fetch_paper(...)` 正文成功响应含 preset、effective_options、content_ref、output_artifacts，以及 `schema_version=4`、`status="ok"`、`source`、可空 `acquisition={provider,route,representation,transport,fallback_used}`、紧凑 `acceptance`、溯源信息；完整 quality、trace 和逐公式诊断通过 diagnostics 视图读取。



### 正文句柄与读取


`content_ref={content_id, views:{markdown|article|diagnostics:{total_chars}}, idle_ttl_seconds, render_truncated}`。只保留请求的正文表示；Markdown 是最终渲染快照，article 和 diagnostics 是 JSON 文本。diagnostics 含完整质量、来源、材料清单、逐项失败、trace、warnings、acceptance 和 `formula_locations`。失败结果也提供仅含 diagnostics 的句柄，别名共享快照；首包保留身份、code/reason、provider/route/stage、实际 HTTP 状态、重试及必要消歧/配置摘要。定位以完整数学片段匹配 final_latex：唯一为 located，多候选为 ambiguous，无匹配为 unlocated；范围 start/end 为 Markdown 的 Unicode 码点、左闭右开，section 为所在标题，不猜公式编号、不改正文或重新判断数学正确性。

`read_content(content_id, view="markdown", offset=0, max_chars=6000)` 中 max_chars 为 1..20000，offset 为非负 Unicode 码点。返回 `text/offset/returned_chars/total_chars/next_offset/eof` 和原渲染 `render_truncated`。使用 next_offset 推进，不能用 JavaScript 字符串长度计算偏移；JSON 表示拼完后再解析。eof 只表示此表示读取结束，不能消除渲染本身的截断。

句柄仅属于当前 MCP 服务实例，闲置 24 小时过期，读取刷新期限；总容量 256 MiB，按保留表示的 UTF-8 字节计量并 LRU 淘汰。批量结束后统一注册，优先淘汰旧请求，本批放不下的项 `content_ref=null`、warning `content_store_capacity_exceeded`，真实获取验收不变，不自动内联、落盘或重抓。句柄不写入持久 manifest、JSONL 或缓存。

读取不联网、不准备 runtime、不写论文。`content_handle_expired` 表示失效/淘汰/未知句柄，`content_view_unavailable` 表示没有请求此表示，`content_range_out_of_bounds` 表示 offset 大于 total_chars；offset 等于末尾合法。处理见[失效与截断](failure-handling.md#正文句柄失效与宿主截断)。

下面是宿主代码示例，`callTool(name,args)` 代指当前环境提供的工具调用。只消费 structuredContent 中的业务载荷，不整包 `text(r)`。一次输出一个正文片段，保存身份、句柄和读取进度供后续轮次调用 `readNext`：

```javascript
function payload(r) {
  return r.structuredContent;
}
const request = {preset: "temporary_read"};
// 单篇：const r = payload(await callTool("fetch_paper", {query, ...request}));
// const items = [r];
const r = payload(await callTool("batch_fetch", {queries, concurrency: 4, ...request}));
const items = r.results;
const reading = items.map(item => ({
  doi: item.doi, source: item.source, acceptance: item.acceptance,
  ref: item.content_ref, offset: 0, eof: false
}));
// 将 reading 保留在会话状态；后续追问直接复用对应句柄。
async function readNext(state, maxChars = 6000) {
  if (!state.ref) throw new Error("No retained content handle");
  const p = payload(await callTool("read_content", {
    content_id: state.ref.content_id, view: "markdown",
    offset: state.offset, max_chars: maxChars
  }));
  if (p.status !== "ok") throw new Error(p.code + ": " + p.reason);
  text({text: p.text, eof: p.eof, render_truncated: p.render_truncated});
  state.pending = {next_offset: p.next_offset, eof: p.eof};
  // 此调用只交付片段；宿主确认完整收到后，下一轮调用 acceptChunk。
  // 若宿主截断，不调用 acceptChunk；保持 offset 并缩小 maxChars 重读。
}
function acceptChunk(state) {
  state.offset = state.pending.next_offset;
  state.eof = state.pending.eof;
  delete state.pending;
}
await readNext(reading[0]);
```

### 正文导航

`navigate_content(content_id, mode="headings"|"search", query=None, offset=0, max_results=20, context_chars=200)` 只导航保留的 Markdown。headings 返回 title/level/start/end/section_start/section_end；search 为不区分大小写的字面匹配，返回匹配 start/end 和有界 context/context_start/context_end。位置均为原文 Unicode 码点、左闭右开；offset 是原文字位置，next_offset/eof 分页导航结果，接着用 read_content 读章节或命中范围。max_results 为 1..100，context_chars 为 0..2000，search 要求非空 query。导航沿用句柄错误和有效期，不改写正文或触发获取。

### 独立补充材料任务

`fetch_paper` / `batch_fetch` 的 `target` 默认为 `paper`，`target="supplementary"` 只获取材料，不执行正文充分性检查、正文组装或正文 PDF fallback。范围由 provider 定义，含明确补充区、Source Data、Extended Data 和多媒体；普通数据仓库链接不自动纳入。正文付费不影响公开材料发现，不支持的来源返回 `not_supported`，保留已解析 DOI、trace 和来源；已知 provider、stage="supplementary"、target 和 retryable=false 明确返回，未执行 route 为 null。缺少实际 DOI 是 identity unavailable，只有显式冲突或实际/期望 DOI 均存在且不同时是 mismatch。正文的 `asset_profile`、引用和 token 选项不影响材料范围。

结果含 `target="supplementary"`、材料索引句柄，以及 `supplementary={asset_count,local_count,failure_count,discovery_complete,identity_verified}`；完整 assets、asset_failures、source_urls 保留在 diagnostics。Markdown 是材料索引，默认文件名为 `<paper-stem>_supplementary.md`，显式 `markdown_filename` 可覆盖。`no_download=true` 或 artifact 禁止资产写盘时保留发现清单及 `archive_state="not_archived"`。

紧凑 acceptance 附带 `target="supplementary"`、`content_requested=false`、`content="unavailable"`，按身份、发现、文件及来源验收。只有完整检查且未发现材料时返回 `status="no_result"`。正文和材料请求指纹隔离；材料 `prefer_cache=true` 命中要求发现完整、身份匹配且所需文件仍存在。参数组合见[任务目标](presets.md#任务目标)，结论见[补充材料验收](acceptance.md#补充材料验收)。

### 其它工具入口

| 工具 | 用途 |
| --- | --- |
| `list_cached(download_dir=...)` | 只读浏览当前 scope 的身份已证明条目。 |
| `get_cached(doi, download_dir=..., detail="full|compact", preferred_only=false, modes=..., strategy=..., include_refs=..., max_tokens=...)` | 已知 DOI 的请求敏感缓存查询，常规用 compact。 |
| `provider_status(provider=None, group=None, detail="full|compact")` | 本地静态诊断，不访问出版社；已知目标时筛选 provider。 |
| `browser_preflight(...)` | 真实 HTML 链路预检，参数和状态见下节。 |
| `batch_resolve(queries, concurrency=1)` | 批量解析身份。 |
| `batch_check(queries, mode="metadata", concurrency=1)` | 低成本可用性探测，单篇也使用此入口。 |
| `batch_fetch(queries, concurrency=1, ...)` | 真实批量抓取，默认返回紧凑 manifest/acceptance，不返回完整正文。 |

## Browser Preflight Contract

- 只在需要真实页面证据时调用；静态配置问题用 `provider_status` / CLI `doctor`。未传 `provider` 时检查 catalog 中全部 browser provider 的内置样例，诊断已知目标应限定 provider。
- 参数：`provider=None, test_url=None, timeout_ms=None, browser_user_agent=None, profile_dir=None, detail="full"`。`test_url` / `profile_dir` 要求一个显式 provider；URL 必须为无内嵌凭据的 HTTP(S)，`timeout_ms` 为 `1..600000`；非空 `browser_user_agent` 当前被拒绝。
- 预检自动准备 managed runtime、访问远端页面并复用原生 profile；不执行 PDF fallback 或自动认证。状态与认证语义见[环境](environment.md#browser-backend-与-storage-state)。
- 逐 provider 返回 `ready`、`challenge`、`auth_required`、`network_timeout`、`extraction_error`、`runtime_error` 或 `cancelled`。compact 每项只有 `provider/status/reason_code/stage/message/next_action`；full 另含 label、脱敏 URL/title、原生 profile 目录与 browser/page diagnostics。顶层含 `pdf_fallback_attempted=false`、`auth_attempted=false` 及状态汇总。
- 一个 provider 失败不删除其它结果；取消保留已有结果并停止后续调度。支持 progress 的宿主收到开始、逐项和最终通知。读取实际结构化 code，不维护完整错误枚举；`ready` 后继续 fetch，认证需求进入人工 auth，runtime 错误见[运行时准备](environment.md#运行时准备与授权)。

## Cache Query Contract

MCP 输出为 v4，fetch-envelope sidecar 为 v7，cache index 为 v3。旧缓存返回版本不匹配，不迁移或删除旧文件。

- `download_dir` 是 cache scope。查询只读当前版本注册索引，核对 DOI、scope、stat/hash，不扫描 loose files、不跨目录搜索、不联网；损坏或版本不匹配按 miss 处理。
- `get_cached` 默认 `detail="full", preferred_only=false`，返回 entries、preferred 和索引字段；`preferred_only=true` 只保留优选 Markdown/primary entries，`preferred.assets=[]`，entry_summary 仍统计全部已证明条目。
- compact 不含完整正文、entries、sidecar payload 或资产数组，保留优选条目、内容/验收/资产/warning 摘要、sidecar/request 状态和 SHA-256 fingerprint。`status="hit"` 仅表示有身份已证明的条目；严格请求复用直接消费 `request_satisfied`，后续 fetch 传同一 scope、modes、strategy、include_refs、max_tokens。
- `cached_request` / `cached_request_fingerprint` 描述所选 sidecar，`requested_request` / `requested_request_fingerprint` 描述当前查询。工具以 DOI + fingerprint 保存变体并判断兼容性；不兼容返回 `request_status="mismatch"`，无需 agent 手算。
- fingerprint 含摘要化 credential scope，不含 secret 或 state 内容。私有请求可复用 public sidecar；public 不能读 private，不同 private scope 不互通。Browser scope 绑定 provider/backend、状态路径及可信状态摘要；摘要不可信时禁用私有缓存读写。legacy/多 scope 歧义条目不可见。
- `sidecar.status` 可为 `ready/missing/corrupt/unreadable/version_mismatch/extraction_revision_mismatch/doi_mismatch/invalid_scope` 等；不合格 sidecar 或 `identity_status="no_proven_entries"` 令 `request_satisfied=false`，miss 后正常抓取。compact acceptance 只是当前快照，不承诺满足未传入的未来请求。

## Error Contract

- `ambiguous`：从 `candidates` 读取候选。
- `no_access`：缺少凭证、entitlement 或访问上下文。
- `rate_limited`：读取 `retry_after_seconds` / cooldown 及 provider lane。
- 其它失败：读取 `status/reason` 及存在的 `code/error_category/http_status`。

CLI runtime fetch 退出码为 `ambiguous=2`、`no_access=3`、`rate_limited=4`；argparse/参数校验也可 exit 2，应结合结构化字段区分。暂停见[工作流](workflow.md#blocking-白名单)，重试见[失败处理](failure-handling.md)。

## 输入与返回契约

- 工具返回带 `schema_version=4` 的 structured payload；`tools/list` 不发布协议级 `outputSchema`。
- 输入枚举：`modes=article|markdown|metadata`、`include_refs=none|top10|all`、`strategy.asset_profile=none|body|all`、`artifact_mode=markdown-assets|all|none`、cache `detail=full|compact`。以当前工具公开 schema 为准。
- batch `queries` 为 `1..50` 项，`concurrency` 为 `1..8`、默认 `1`。输入对象及嵌套 strategy/budget 拒绝未知字段；字符串枚举去空白和规范大小写不放宽值域。

## Batch Probe Contract

- `batch_check` 的 mode 仅支持 `"metadata"`（默认）。`probe_state=likely_yes|unknown` 是可用性信号，不是已取得正文；单篇传 `queries=[query]`，读 `results[0]`。
- 顶层含 `mode/results/aborted/abort_reason/progress`。成功项 `likely_has_fulltext` 仅在 likely_yes 时为 true，否则 null；`has_fulltext/content_kind/has_abstract/source/acquisition/token_estimate/token_estimate_breakdown=null`，`trace=[]`。
- `batch_resolve` / `batch_check` 的 results 与输入等长并保持顺序；每项有稳定 1-based `index/query/status/error/provider_lane`，歧义候选在逐项 error。progress 区分 `terminal/completed/not_scheduled`；错误、取消和未调度项不计作完成。
- 调度采用解析后的 provider lane；同批规范 DOI 相同的检查执行一次再映射回全部输入。更大批量遵循[分块规则](presets.md#批量分块与证据等级)，限流和重试遵循[失败处理](failure-handling.md)。

仅探测按[探测核对](acceptance.md#探测核对与报告)完成。用户要求真实批量正文获取检查时可用 `batch_fetch`，以 acceptance 判断获取结果；无需论文落盘的组合为：

```python
batch_fetch(
    queries=[...],
    concurrency=4,
    modes=["article"],
    include_refs="all",
    max_tokens="full_text",
    save_markdown=False,
    no_download=True,
    prefer_cache=False,
    artifact_mode="none",
    strategy={"asset_profile": "none"},
)
```

不传 `batch_results`。上述调用返回正文句柄；完整阅读用[阅读预设](presets.md#1-临时阅读)、批量句柄或读合格文件。

## Batch Fetch Contract

- 输入沿用单篇的 target、modes、strategy、渲染、cache、artifact、Markdown 和 download_dir 语义；多条输入不能共用一个 markdown_filename。
- 正文始终通过句柄读取。逐项含 index/query、attempt、完成序号、run/record ID、request fingerprint、DOI/source/acquisition、acceptance、error、warning/code 摘要及 output_artifacts。快照有 path/kind/size/SHA-256，route/failure_code 不可用时为 null。results 按输入 index，completion_order 保留实际完成顺序。
- 可选 `batch_results=<path>` 在整批结束后按输入顺序原子写最终 schema-v2 JSONL，每项一条 terminal record；文件已存在时默认拒绝，`overwrite=true` 允许替换。它不提供 journal 或恢复语义。
- 同 provider/resource lane 限流只停止该 lane 的新项。`continue_on_error=true` 默认继续其它目标，false 停止新的全批提交。支持 progress/cancel；取消保留已完成产物及 cancelled/not-scheduled 结果，取消提交边界后的 worker 不再提交文件。
- Resolve 后以规范 DOI 去重当前批次的 DOI/URL/title aliases，再按原 index/query fan-out；不同请求不共享执行。归档与 cache 参数组合见[落盘矩阵](presets.md#mcp-输出落盘矩阵)。

## 默认临时阅读参数

| 参数 | 默认值 |
| --- | --- |
| `target` | `"paper"` |
| `modes` | `["markdown"]` |
| `preset` | `"temporary_read"` |
| `strategy.asset_profile` | `"none"` |
| `strategy.require_local_body_assets` | `false` |
| `strategy.require_full_size_body_assets` | `false` |
| `strategy.allow_metadata_only_fallback` | `true` |
| `include_refs` | `"all"` |
| `max_tokens` | `"full_text"` |
| `prefer_cache` | `false` |
| `no_download` | `true` |
| `save_markdown` | `false` |
| `artifact_mode` | `"none"` |
| `markdown_output_dir` | `null` |
| `markdown_filename` | `null` |

`strategy.asset_profile=null` 使用最终 provider route 的默认范围；显式 none 禁用正文任务的资产解析和下载。`include_refs=null` 在 full_text 时等同 all，正整数 max_tokens 时等同 top10。

## Fetch Notes

- 写盘为原子提交，但多种产物不是跨文件事务。CLI 和 batch_fetch 提供覆盖开关；单篇 fetch_paper 不暴露 overwrite，保存 Markdown 使用覆盖写入。因此调用前须检查已有成果和适用覆盖授权，不能假定单篇工具会拒绝覆盖。
- `prefer_cache=true` 对已含 DOI 的输入先无网络规范化和请求/credential scope 匹配，miss 后进入 resolver/provider enrichment；标题仍需先解析。
- download_dir 同时是下载目录及 cache scope；未指定 markdown_output_dir 时也作为 Markdown 输出目录。缓存条目不暴露为 MCP resource。实际写盘组合见[预设](presets.md#mcp-输出落盘矩阵)。
- `body|all` 共用每篇资产预算：单文件 32 MiB、累计 256 MiB、64,000,000 像素、并发最多 4 且受 route cap 限制；普通 provider 默认不限文件数，arXiv source archive 最多 128 个 regular member。不拆调用规避预算，失败读取 asset_failures 中结构化 reason。
- direct 401/403 最多进入一次 browser-byte recovery，仍受 MIME、字节、像素、预算、安全发布和取消检查。下载策略逐跳检查 HTTP(S)、标准端口、公网 DNS、userinfo、HTTPS downgrade 和跨域敏感头；catalog host 声明不是访问授权或下载 allowlist。
- `require_local_body_assets=true` 要求正文逻辑资产全部本地化；`require_full_size_body_assets=true` 隐含 local 并拒绝 preview。仅对 body|all 生效，进入请求指纹；未满足降低 asset/overall，不抹去已取得正文。
- body|all 可附带关键本地图像 ImageContent；save_markdown=true 不返回 inline image。可选 strategy.inline_image_budget={max_images,max_bytes_per_image,max_total_bytes} 默认 3 张、每张 2 MiB、总计 8 MiB；任一最终值为 0 禁用。
- 资产字段含 render_state/download_tier/preview_accepted/content_type/downloaded_bytes/width/height；恢复时还可含 browser_backend/final_fetcher/recovery_attempts，CLI/MCP/cache 原样保留。计时 asset_timing 不含 URL。分类消费 issue_codes，不按 warning 重新推断。
- 表格 table_layout_degraded_count 表示布局无法可靠验证，table_semantic_loss_count 表示更强的内容丢失信号。HTML/XML 公式先校验源 TeX，失败仅使用同节点唯一配对 MathML 转换并再校验；全部失败保留源表达及诊断。PDF 正文不进入这些修复流程。

## Local Markdown and Cache Identity

- 可信 Markdown 身份来自保存时以 envelope DOI 和实际路径显式注册，或结构化 YAML front matter 中的 doi/source/布尔 has_fulltext/content_kind/acquisition；文件名或正文偶现 DOI 不能证明归属。
- sidecar、Markdown 或资产写入后显式增量注册 SHA-256；读取仅使用通过 DOI、scope、stat/hash 校验的当前索引条目。坏 YAML、缺字段、目录外路径和错误 DOI 不作为命中。
- preferred.markdown 优先 fulltext，再按 completed_at（缺失时 mtime）选最新；entry 提供 identity_proof、来源、内容事实和 hash。Markdown 归属不能替代 fetch-envelope 请求匹配；具体复用流程见[本地优先决策树](presets.md#本地优先决策树)。

## Static Provider Catalog

宿主内先不带 server 调用资源发现，使用返回的真实 server 名和 URI 读取；不要从工具前缀 `mcp__paper_fetch__` 猜注册名。发现一次后复用，不作为普通抓取前置步骤。CLI 同源入口为 `paper-fetch doctor --catalog [--json]`，运行来源用 doctor 的 runtime 字段。

`resource://paper-fetch/provider-catalog` 是 provider/source/capability 权威入口，含 schema_version、tool_version、sources、带 transport 的 routes、asset_default、browser/runtime/status/preflight capabilities、支持的 targets（与材料获取共用判断）和 runtime 解释器/模块/受管安装来源 和 source_provider_map。另含只读 `browser_runtime`：当前 backend、manifest 中的 byparr_version、platform_engine、按需 preparation、请求/批量准备复用范围及 update_check_interval_seconds。读取 catalog 不准备或下载组件。选择 provider_hint/preferred_providers 或解释 source 时读取，不另维护静态名单。catalog 不证明依赖就绪或远端可访问：静态状态用 provider_status，真实页面用 browser_preflight。

## 内部一致性诊断

仅在结果矛盾或用户要求诊断时使用，普通任务消费工具结论：

- 完整 acceptance schema 为 v2，单篇/批量紧凑摘要由同一报告投影；不要要求紧凑摘要具有完整报告全部字段。对照同一请求、产物与顶层 trace，保留每个 retry event；不从 warning、source 名或 has_fulltext 重建 acquisition/结论。
- 资产计数和 preview 别名合并由工具负责；accepted preview 可合格，fallback preview 为 fidelity 降级。严格 local/full-size 直接读取 *_satisfied，不能由 agent 重新合并资产或手算分母。
- request_satisfied 包含 sidecar version、extraction revision、DOI、acquisition、scope 和全部请求 modes 匹配。当前 sidecar version=7、cache index version=3；不合格按 miss 重新抓取并保留已有 Markdown。读取返回状态和 fingerprint 解释 mismatch，不手算替代工具判断。

原生 fetch 预设：temporary_read（默认）、cacheable_read、archive。先展开预设，再合并显式参数；正文始终通过 content_ref / read_content 消费。业务载荷仅位于 structuredContent；content 数组仅保留独立媒体。完整 envelope 只序列化一份 quality、acquisition 和 trace；article 部分仅含内容字段。独立 ArticleModel 包含完整质量和来源信息。MCP v4、fetch-envelope v7、cache index v3；旧缓存报告版本不匹配，不迁移或删除。

元数据公开日期为 `publication_dates=[{kind,value,source}]`；保留上游类型，未区分时 unspecified，不补日期。内部引用日期按 print、online、issued、unspecified、created 优先；年份匹配排除 created。article_type、relations 与 update_to 展示实际文献关系，不自动换 DOI 或追抓。PDF diagnostics 的 `bytes_transport=http|browser_response|browser_download` 及 final_url 表示实际字节获取事实，未知为空；acquisition.transport 继续表示路线语义。
