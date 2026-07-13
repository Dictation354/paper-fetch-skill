# 身份优先工作流

把每个目标作为独立状态项推进，整批任务共享意图、输出和并发策略。唯一阶段顺序如下，不得插入后端确认或保存确认作为额外阶段：

> 输入规范化 → resolve/batch_resolve → DOI 去重 → 仅歧义项阻塞 → 本地/cache → 意图 → 后端 → 必要状态检查 → fetch → acceptance → report

阶段依赖必须有序；一个阶段内身份独立的论文可以受控并发。某个目标暂停时，除非用户要求整批原子完成，否则继续推进其余身份明确的目标。

## BLOCKING 白名单

仅以下六类情况可以暂停并请求用户决定：

- `multiple_candidates`：解析得到多个合理候选，无法自动唯一化。
- `insufficient_identity`：现有标识和书目信息不足以唯一定位目标。
- `manual_auth`：必须由用户完成人工登录或明确授权。
- `lawful_access_boundary`：付费、许可范围或其他合法访问边界需要用户决定或补充权限。
- `overwrite_existing`：继续会覆盖已有且可用的成果。
- `material_output_choice`：多个无法自动推断的选择会实质改变产物内容、位置或资产集合。

其它事项一律不标为 BLOCKING。尤其不得因为尚未讨论保存、选择 CLI/MCP、目标较多、命中缓存、普通降级或某个目标失败而暂停整批任务。保存目录只有在完成下述推断后仍不唯一时，才归入 `material_output_choice`。

## 状态机

### 1. 输入规范化

- 接收 DOI、URL、arXiv ID、书目、标题候选以及搜索工具发现的候选，保留原始顺序、原始条目和来源。
- 规范化空白、标识表示和结构化书目信息，不在此阶段抓取全文或选择执行后端。
- web search 只发现候选；后续阅读、总结、比较、翻译、批判或全文核验必须进入本状态机。
- 不得用去重前的原始条目数决定 CLI 或 MCP。

### 2. resolve/batch_resolve

- 单篇调用 `resolve_paper(...)`，成批候选调用 `batch_resolve(...)`，记录每个输入对应的解析状态、规范身份和候选。
- 标题候选严格遵循 [`tool-contract.md`](tool-contract.md) 中唯一的标题解析规则，不在其它文档重新定义该规则。
- 先完成本阶段再抓取，不把搜索结果页面或未经解析的书目当成全文身份。

### 3. DOI 去重

- 以规范化 DOI 合并同一论文的重复输入，保留原始条目到规范目标的映射；没有 DOI 但身份唯一时保留可追溯的规范落地页身份。
- 后续规模、缓存、意图和后端判断只针对去重后的规范目标，不丢失用户输入的别名和顺序。

### 4. 仅歧义项阻塞

- 只暂停 `multiple_candidates` 或 `insufficient_identity` 的目标，展示候选或缺失身份字段并请求最小必要信息。
- 继续推进其它身份唯一的目标；用户要求整批原子完成时，才等待所有身份项就绪。
- 用户消歧后从规范身份恢复状态项，并保留原始条目映射。

### 5. 本地/cache

- 严格执行 [`presets.md`](presets.md) 的本地优先决策树：已核验本地 fulltext → 同 scope 精确 DOI cache → 严格请求匹配的 prefer-cache → 正常 fetch。
- 先检查用户已提供且身份可证明的全文文件。已知 DOI 时调用 `get_cached(doi, download_dir=<scope>, detail="compact", preferred_only=true, modes=..., strategy=..., include_refs=..., max_tokens=...)`，不要全量调用 `list_cached()`；请求参数必须与后续 `fetch_paper(..., prefer_cache=true)` 相同，且始终传相同 `download_dir`。
- 只有文件身份、内容级别和当前任务意图相符时才复用。`get_cached` 不联网；顶层 `status=hit` 只证明存在条目，FetchEnvelope 只有在 `request_satisfied=true` 时才满足本次请求。该判断仍由 `cached_request_matches()` 严格完成，不匹配时正常进入 fetch。
- 缓存命中不是自动验收通过，metadata-only 也不是全文。合格本地全文或精确缓存命中可跳过联网抓取，但仍必须进入 acceptance 和 report。

### 6. 意图

- 从用户目标确定本次是临时阅读、可缓存阅读、单篇本地归档、批量可读性分诊或批量本地归档，并按 [`presets.md`](presets.md) 记录需要的正文、引用、cache、artifact、资产和最终文件。
- 普通阅读、总结、比较、翻译、批判或信息提取默认不要求先讨论保存；用户已明确产物目标时直接沿用。
- 需要本地归档时，按以下优先级推断保存目录：用户显式路径 → 项目配置或唯一已有约定 → 唯一合理的 `papers/` → 仍无法唯一确定时请求选择。
- 使用实际目录和文件判断已有成果。继续会覆盖可用成果时以 `overwrite_existing` 暂停；目录选择会实质改变产物且无法唯一推断时以 `material_output_choice` 暂停。

### 7. 后端

- 根据去重后的规范目标、任务意图、产物形式和当前可用能力自主选择执行面。去重后的数量可以辅助并发规划，但不得成为单独的硬阈值。
- 批量本地归档默认使用 CLI；需要 MCP 宿主内 progress/cancel、结构化 acceptance 或不便解析 CLI stdout 时使用 `batch_fetch`。少量阅读或结构化抽取默认使用 MCP。用户明确禁止某个执行面时切换到可用的另一个执行面。
- 不因选择 CLI 或 MCP 请求额外确认，也不在二者之间建立等待往返。正常 CLI 单篇/批量流程、manifest 恢复和窄 fallback 都读取 [`cli-workflow.md`](cli-workflow.md)。

### 8. 必要状态检查

- 仅当 provider 凭证、浏览器运行时、人工登录或合法访问上下文可能影响目标时调用 `provider_status()`，并按 [`environment.md`](environment.md) 处理。
- 对 runtime `ProviderSpec.requires_browser_runtime=True` 的 provider，在首次联网抓取前先用 `provider_status(provider=...)` 确认静态 runtime；需要真实链路证明时再运行 MCP `browser_preflight(provider=...)` 或 CLI `paper-fetch browser-preflight --provider ...`。live preflight 可能联网并写 storage-state，不能当作只读检查。
- 预检的 `challenge` / `auth_required` 才转入显式人工 `auth`；`runtime_error` 先修本地运行时，`ready` 才继续 fetch。预检不执行 PDF fallback 或自动 auth，也不得尝试绕过 challenge。
- 需要人工登录/授权时使用 `manual_auth` 暂停；遇到付费、许可或合法访问边界时使用 `lawful_access_boundary` 暂停。不得绕过登录、验证码、付费墙或访问控制。

### 9. fetch

- 对尚未由合格本地/cache 满足的目标执行抓取或分诊；按意图使用 `has_fulltext(...)`、`batch_check(...)`、`fetch_paper(...)` 或 `batch_fetch(...)`，CLI 只接收规范目标并按选定的批量归档参数运行。
- `batch_check(mode="metadata")` 只给出 `likely_yes` / `unknown` 的低成本探测，不代表已抓取全文；超过 50 条时按原始 1-based index 分块并在合并后恢复原顺序。
- `batch_fetch` 才是 MCP 的真实批量全文入口；单块最多 50 条，默认只返回 input-ordered compact manifest/acceptance，实际完成顺序另列。显式 run manifest 才能 resume；临时阅读不应为获得正文而取消 compact 上限。
- 同一阶段内允许在 runtime 限制和 provider 速率约束下受控并发；不要求所有论文严格逐篇串行，浏览器资产下载仍服从 runtime 自身的串行约束。
- 对浏览器链路失败按 [`failure-handling.md`](failure-handling.md) 与环境策略处理，限制重试并保留诊断。抓取失败或降级仍进入 acceptance。

### 10. acceptance

- 对每个目标按 [`acceptance.md`](acceptance.md) 读取统一 acceptance 结果，检查 overall、identity、fetch、content、asset、output 和 provenance；不得另造一套成功标准。
- 任务要求写盘时，检查返回的实际路径存在且为预期文件；确认文件非空、可读、身份对应规范目标，且内容级别和资产满足意图。任务不要求写盘时，检查实际响应载荷及其验收结果。
- 对本地/cache 复用执行同样的身份、内容和输出验收。目录被 gitignore 或 `git status` 没有变化既不表示失败，也不表示成功。
- 将 abstract-only、metadata-only、缺失资产和质量降级保留为对应验收结论，不升级成全文完成。

### 11. report

- 汇总规范身份、原始条目映射、去重结果、本地/cache 复用、所选后端、实际产物路径和 acceptance 结论。
- 明确区分 complete、degraded、limited、failed、action_required，并列出可操作的警告、阻塞项和下一步。
- 对批量任务逐项报告，同时给出成功、降级、失败和待人工处理的汇总；不得把 fetch 完成当作最终成功。
