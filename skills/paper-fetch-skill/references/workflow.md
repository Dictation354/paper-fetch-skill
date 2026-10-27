# 身份优先工作流

把每个目标作为独立状态项推进，整批任务共享意图、输出和并发策略。唯一阶段顺序如下，不得插入后端确认或保存确认作为额外阶段：

> 输入规范化 → resolve/batch_resolve → DOI 去重 → 仅歧义项阻塞 → 意图 → 本地/cache → 后端 → 必要状态检查 → fetch → acceptance → report

阶段依赖必须有序；一个阶段内身份独立的论文可以受控并发。某个目标暂停时，除非用户要求整批原子完成，否则继续推进其余身份明确的目标。

阶段名保持一致：仅探测任务在 fetch 阶段调用 `batch_check`，在 acceptance 阶段核对探测证据，不要求全文 acceptance，也不自动升级为全文抓取。

## BLOCKING 白名单

仅以下六类情况可以暂停并请求用户决定：

- `multiple_candidates`：解析得到多个合理候选，无法自动唯一化。
- `insufficient_identity`：现有标识和书目信息不足以唯一定位目标。
- `manual_auth`：必须由用户完成人工登录或明确授权。
- `lawful_access_boundary`：付费、许可范围或其他合法访问边界需要用户决定或补充权限。
- `overwrite_existing`：继续会覆盖已有且可用的成果，且用户尚未授权该覆盖。
- `material_output_choice`：多个无法自动推断的选择会实质改变产物内容、位置或资产集合。

其它事项一律不标为 BLOCKING。尤其不得因为尚未讨论保存、选择 CLI/MCP、目标较多、命中缓存、普通降级或某个目标失败而暂停整批任务。保存目录只有在完成下述推断后仍不唯一时，才归入 `material_output_choice`。

沿用用户在当前任务中的明确选择和已有授权，不因进入新阶段而重复询问。BLOCKING 用于仍需用户决定的事项；缺少工具或 runtime 时报告该执行面的能力限制，并继续其它可执行目标，不强行安装环境。

## 状态机

### 1. 输入规范化

- 接收 DOI、URL、arXiv ID、书目、标题和搜索发现的候选，保留原始条目、来源及顺序；为每条输入固定原始 1-based `index`。
- 超过 50 条时，在首次批量解析前按[分块规则](presets.md#批量分块与证据等级)处理；后续块内结果映射回原 index。
- 此阶段只规范输入，不抓全文或选后端。搜索用于发现候选，后续全文任务仍进入本状态机。

### 2. resolve/batch_resolve

- 单篇调用 `resolve_paper`；成批调用 `batch_resolve` 并显式选择并发数，记录规范身份、候选和原始输入映射。
- 标题输入遵循[标题解析契约](tool-contract.md#标题解析)。完成解析后再抓取。

### 3. DOI 去重

- 汇总解析块后按规范 DOI 跨块合并重复输入；无 DOI 但身份唯一时保留规范落地页身份。
- 保留所有原始别名和顺序；后续规模、意图和后端判断只针对规范目标。

### 4. 仅歧义项阻塞

- 仅对身份不唯一的目标按 BLOCKING 白名单请求最小必要信息，继续其余目标。
- 用户消歧后从规范身份恢复，保留原始条目映射；只有用户要求整批原子完成时才等待全部身份就绪。

### 5. 意图

- 先按[任务目标](presets.md#任务目标)区分正文与独立补充材料；只要材料时确定 `target=supplementary`，沿用路径和批量设置，不套用全文阅读或可用性探测。
- 正文或仅探测任务从用户目标选择[共同规则](presets.md#共同规则)和当前预设：[临时阅读](presets.md#1-临时阅读)、[可缓存阅读](presets.md#2-可缓存阅读)、[单篇归档](presets.md#3-单篇本地归档)、[仅探测](presets.md#4-批量可读性分诊)或[批量归档](presets.md#5-批量本地归档)。只读所选章节，确定请求参数；多篇比较沿用阅读预设。
- 普通阅读不要求讨论保存。归档目录按用户显式路径 → 项目配置或唯一已有约定 → 唯一合理的 `papers/` 推断；仍不唯一且实质影响产物时才归入 `material_output_choice`。
- 检查实际已有文件；未获授权而将覆盖可用成果时归入 `overwrite_existing`，已有覆盖授权直接沿用。

### 6. 本地/cache

- 独立材料任务先按[任务目标](presets.md#任务目标)检查材料清单和文件，未满足则继续材料请求；正文或正文缓存命中不能替代材料。MCP 的材料缓存复用由 `target=supplementary, prefer_cache=true` 请求处理。
- 正文任务先检查用户提供或已有的合格全文；需要 cache 且当前预设允许、已有 scope 时，再读[本地优先决策树](presets.md#本地优先决策树)。临时阅读不为查缓存而新增 scope。
- cache 复用直接消费 `request_satisfied`；不手工重算内部匹配。未满足则继续 fetch。合格本地正文直接读取，复用后仍进入 acceptance/report。
- 仅探测且没有合格本地证据时继续 `batch_check`，不为查询缓存获取正文。

### 7. 后端

- 按规范目标、意图、产物形式和可用能力自主选择，数量只辅助并发规划，不是单独的硬阈值，也不额外请求确认。
- 阅读和结构化抽取默认 MCP；批量归档默认 CLI。需要宿主 progress/cancel、结构化批量结果或不便解析 stdout 时用 `batch_fetch`；沿用用户对执行面的限制。
- 使用 CLI 时读 [CLI 工作流](cli-workflow.md#单篇)或[批量章节](cli-workflow.md#批量归档)。只有自定义输出组合时才查[CLI](presets.md#cli-输出落盘矩阵)/[MCP](presets.md#mcp-输出落盘矩阵)落盘矩阵。

### 8. 必要状态检查

- provider 凭证、browser runtime 或访问上下文可能影响目标时，用筛选后的 `provider_status(provider=...)` 确认静态状态；provider/capability 以 [catalog](tool-contract.md#static-provider-catalog) 为准。
- browser provider 首次联网抓取前确认静态 runtime；静态 binary 缺失不阻止工具自动准备。缺失或异常时读[运行时准备与授权](environment.md#运行时准备与授权)。
- 只有需要真实链路证明时才做 [browser preflight](tool-contract.md#browser-preflight-contract)；它会联网且可能写 storage-state。已返回 `ready` 则继续 fetch，不要求每次预检。
- 实际 fetch 或按需预检返回 `challenge` / `auth_required` 时按 `manual_auth` 处理；付费、许可等访问边界按 `lawful_access_boundary` 处理，不绕过访问控制。

### 9. fetch

- 对未被本地/cache 满足的目标按当前预设调用工具；普通抓取自动准备 managed runtime，无需 agent 另做更新检查。准备失败时按[环境参考](environment.md#运行时准备与授权)读取具体诊断。
- 独立材料任务使用 CLI `fetch --target supplementary` 或 MCP `fetch_paper` / `batch_fetch(target="supplementary")`；不要求正文成功，不追加正文 PDF fallback。
- 仅探测用 `batch_check`（单篇传一个 query），不升级为抓取；多篇完整阅读对各规范目标直接使用单篇阅读预设，已取得正文不重复抓取。
- 需要结构化批量抓取时用 `batch_fetch`，详细返回见 [Batch Fetch Contract](tool-contract.md#batch-fetch-contract)；compact 无正文，bounded 可能截断，归档正文直接读文件。
- 同阶段独立目标可在 provider 速率和 runtime 限制内受控并发；批量分块沿用第 1 阶段规则。失败、限流或准备重试时读[失败处理](failure-handling.md)；失败或降级仍进入 acceptance。

### 10. acceptance

- 仅探测直接按[探测核对与报告](acceptance.md#探测核对与报告)核对证据和调度状态，再进入 report。
- 独立材料任务按[补充材料验收](acceptance.md#补充材料验收)核对身份、发现完整性、逐项失败及所需文件，不要求实际正文。
- 正文抓取或复用按[七个分面](acceptance.md#七个分面)及[响应验收](acceptance.md#响应验收)消费统一结果，核对身份、内容范围和实际正文，不另造成功标准。
- 正文任务请求资产时读[资产验收](acceptance.md#资产验收)；各任务归档或复用文件时读[文件、路径与 hash 验收](acceptance.md#文件路径与-hash-验收)；真实批量抓取再读[批量验收](acceptance.md#批量验收)。

### 11. report

- 按[最终报告](acceptance.md#最终报告)交付任务结论、来源及影响任务的降级；批量保留原始映射与逐项状态。
- 获取验收后，宿主用已核验文本继续用户要求的总结、比较、翻译或提取；材料不足则说明具体限制并完成有依据的部分。paper-fetch 仍只负责身份解析、获取、验收和报告。
