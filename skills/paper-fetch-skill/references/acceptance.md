# 统一验收与报告

仅探测直接读[探测核对与报告](#探测核对与报告)；独立 `target=supplementary` 任务直接读[补充材料验收](#补充材料验收)，不加载全文验收章节。正文抓取或本地/cache 复用读取[七个分面](#七个分面)和[响应验收](#响应验收)。均按[最终报告](#最终报告)交付；请求资产、文件或真实批量结果时，再读对应章节。

直接消费工具、manifest 或 cache 的统一 acceptance，核对当前任务所需的实际响应和文件，不从 warning 文案另造成功标准。内部一致性由工具负责；只有结果异常或用户要求诊断时，才查[内部一致性诊断](tool-contract.md#内部一致性诊断)。

## 探测核对与报告

- `batch_check(mode="metadata")` 按逐项 `probe_state`、`evidence`、`warnings` 和 `error` 核对；`likely_yes` 只表示有可读信号，`unknown` 表示证据不足，都不证明已取得或已读全文。
- 检查每项 `index/query/status`、顶层 `aborted/abort_reason/progress` 及原始输入映射。歧义候选从逐项 `error` 读取；错误、取消、限流和 `not_scheduled` 分别保留，不把未完成项计作成功探测或推断成不可读。
- 报告规范身份、逐项探测结论及支持证据、错误和必要动作；批量按 probe_state 和调度/错误状态汇总。明确材料只经过可用性探测，没有全文 acceptance，也不宣称已归档或已验证全文。
- 完成仅探测任务后停止，不自动升级为全文抓取。若复用的是已取得的合格本地全文，仍按本文件的文件与内容验收，并标明本地证据来源，不伪造 `probe_state` 或远端当前可用性。

## 补充材料验收

- 独立 `target=supplementary` 任务只验收材料。正文 `content.requested=false`（紧凑摘要为 `content_requested=false`）和 `has_fulltext=false` 符合请求，不据此判为全文缺失或触发正文重抓。
- 核对规范身份、`supplementary.identity_verified`、`source_urls` 和来源记录；核对 `assets`、逐项 `asset_failures` 及 `discovery_complete`。只有完整发现且没有材料时才报告 `no_result`；发现未完成或失败不能报告为没有补充材料。
- 需要归档时核对用户要求的实际附件和材料索引，文件检查见[文件、路径与 hash 验收](#文件路径与-hash-验收)。材料 Markdown 只有名称、来源链接和本地路径，不要求包含论文正文或 front matter。
- 直接消费统一 acceptance：全部材料下载成功为 `complete`，部分成功或发现但未归档为 `degraded`，全部下载失败保留具体原因。`archive_state="not_archived"` 的发现清单不能报告为下载完成。
- 真实批量任务再按[批量验收](#批量验收)核对原始映射和逐项状态；按[最终报告](#最终报告)交付材料发现、归档结论及影响任务的失败。

## 七个分面

| 分面 | 任务相关事实 |
| --- | --- |
| `overall` | 任务级结论：`complete`、`degraded`、`limited`、`failed` 或 `action_required`。 |
| `identity` | 规范 DOI/落地页、期望 DOI、标题，以及 `resolved/ambiguous/mismatch/unavailable`。 |
| `fetch` | 调用是否完成、是否因歧义/访问/配置需要动作；它不等同于全文存在。 |
| `content` | `fulltext`、`abstract_only`、`metadata_only` 或 `unavailable`，以及 `has_fulltext`、`has_abstract`、confidence/flags。 |
| `asset` | 请求的 profile、正文/补充资产、本地/远程、full-size/preview、failure、placeholder 和 not-archived 事实。 |
| `output` | 只检查本次明确请求的 article/Markdown/metadata 或文件；未请求不算缺失。 |
| `provenance` | 结构化 fallback/warning/failure code、trace、semantic loss 和 asset failure。 |

顶层兼容 `status=ok` 只表示调用没有抛出运行时失败；`has_fulltext` 是内容事实；`overall` 才是任务验收结论。三者不能互换。摘要或 metadata 可以是成功返回，但最多是 `limited`，不能报告成全文完成。

单篇响应和批量逐项结果都提供统一 acceptance 摘要；直接读取各分面结论。保留返回的 `source`、`acquisition` 和 provenance 降级，不从 provider 名或 URL 补全缺失来源。

## 资产验收

- 按请求的 `asset_profile` 核对 asset 分面和实际资产；未请求的资产不算缺失。
- 默认 provider-policy 下，被接受的 preview、允许保留的远程链接可以合格；读取工具给出的 `issue_codes`、failure 和 placeholder，保留影响任务的降级，不按尺寸或重复内容另造问题。
- 请求严格 local/full-size 时，直接检查 `local_body_assets_satisfied` / `full_size_body_assets_satisfied` 及对应 requirement；不要从计数重算。未满足只降低 asset/overall，已取得全文仍可为 `fetch=ok`。
- 要求本地资产时核对实际文件，沿用[文件、路径与 hash 验收](#文件路径与-hash-验收)。字段含义或结果异常时查[资产参数](tool-contract.md#fetch-notes)及[内部一致性诊断](tool-contract.md#内部一致性诊断)。

## 响应验收

- 核对响应的规范 identity 与原始输入映射；歧义、DOI mismatch 或身份不足按 [`workflow.md`](workflow.md) 的 BLOCKING 白名单处理。
- 核对 `content` 是否满足当前 [`presets.md`](presets.md) 的文本意图；任务只需摘要时可接受 limited，用户明确需要全文时不能升级结论。
- 阅读任务还要取得并读取实际正文：compact 只含验收摘要，不能充当阅读材料；bounded 检查逐项 `content_truncated`、`content_available_chars` 和 `content_returned_chars`，并保留正文自身或宿主的截断提示。即使 acceptance 表明抓取到全文，也不能据截断响应宣称已读全文；完整阅读的获取路径见[临时阅读预设](presets.md#1-临时阅读)。
- 请求资产时按[资产验收](#资产验收)核对；结构化 asset failure 和 placeholder 保留为对应降级。
- 核对请求输出集合，保留 table/formula/asset 降级、fallback code 和 source trail。普通 warning 不按字符串猜测类别。
- 保留工具给出的来源及 provenance partial/degraded；遇到缺失或矛盾的结果才查[内部一致性诊断](tool-contract.md#内部一致性诊断)，普通验收不逐项比对 catalog/trace。

## 文件、路径与 hash 验收

任务要求写盘或复用本地文件时，对 CLI `output_path`、批量 `output_artifacts[*].path`、单篇 MCP 请求参数确定的 Markdown 目标或待复用文件执行以下检查：

1. 路径位于用户选择/推断的目标目录，文件存在、可读且非空；独立材料任务完整空发现的索引允许为空，以结构化 `no_result` 和发现完整性为准。
2. 正文 Markdown front matter 或 manifest identity 与规范目标一致；材料索引及附件通过结构化响应或 manifest 的身份、来源和资产路径关联核对。文件名和正文里偶然出现的 DOI 不能证明归属。
3. 内容满足当前任务意图；正文任务的 `abstract_only` / `metadata_only` 文件仍不能当作 fulltext archive，独立材料任务按[补充材料验收](#补充材料验收)核对。
4. 当前文件 size/SHA-256 与返回的输出快照一致；没有输出快照时直接计算实际值供验收，按最终报告的场景决定是否展示。
5. 正文任务按资产 profile、独立材料任务按返回的材料集合，核对实际本地文件、MIME/尺寸/hash、remote-only 或 missing 事实。

文件被 `.gitignore` 忽略、`git status` 没有变化或位于仓库外，都不影响上述验收。需要独立复核单个产物时可用标准库计算实际 size/hash，不依赖 `jq`：

```bash
python3 - ./papers/example.md <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
payload = path.read_bytes()
print(json.dumps({"path": str(path.resolve()), "size": len(payload), "sha256": sha256(payload).hexdigest()}, sort_keys=True))
PY
```

## 批量验收

- 本节适用于真实批量抓取；`batch_check` 使用[探测核对与报告](#探测核对与报告)，不要求其提供下述 manifest 字段。
- 结果必须覆盖原始规范目标的完整 1-based index 集合；响应 `results` 和最终 JSONL 都按 input index，`completion_order` 只在响应中表示实际完成顺序。
- 每个 index 都有 terminal record、request fingerprint、acceptance 和结构化 error/输出 hash；取消、限流和未调度项不能静默消失。
- 最终 JSONL、主输出和额外 Markdown 分别验收；某一类文件存在不证明其它类已经完成。JSONL 是一次性最终结果，不作为恢复状态。

## 最终报告

- 仅探测：按[探测核对与报告](#探测核对与报告)展示可用性证据、错误和调度状态，不套用全文 acceptance 汇总。
- 独立材料任务：按[补充材料验收](#补充材料验收)报告身份、来源、发现完整性、材料清单及归档路径，保留逐项失败，区分完整空发现和未归档清单。
- 普通阅读：保留论文身份、可追溯来源、实际取得的内容范围及影响任务的降级。全文、摘要和元数据必须区分；browser HTML 失败后 PDF 成功仍需保留精确 failure code 和 degraded 结论。
- 归档：补充实际产物路径、验收结论和缺失资产；只展示本次请求的产物，不把未请求项列为失败。
- 失败或需用户动作：说明具体原因、受影响目标及必要动作；按需展开结构化 code、执行面、attempt、acquisition、hash 或诊断路径。用户要求审计时提供完整技术证据。
- 批量抓取：保留原始 index/query 到规范身份的映射及逐项状态，汇总 complete/degraded/limited/failed/action-required、限流、取消和未调度项；其余技术字段保留在已有机器结果中，按核对或诊断需要展示。

展示精简不改变工具、manifest 或 cache 的完整结果，也不省略必要的身份、文件和降级验收。需重试时只按 [`failure-handling.md`](failure-handling.md) 的上限和状态变化条件执行。

获取验收后，宿主继续完成用户原本要求的总结、比较、翻译或提取；不要以获取报告结束阅读任务。证据不足时说明限制并完成有依据的部分，不把摘要或片段冒充全文。paper-fetch 本身仍只负责身份解析、全文获取、验收与报告。
