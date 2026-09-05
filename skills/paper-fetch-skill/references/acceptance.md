# 统一验收与报告

抓取、cache 命中或本地文件复用都不是最终成功。每个规范目标必须读取工具、manifest 或 cache 返回的统一 acceptance，复核实际响应/文件，再进入 report；不要按 warning 文案另造成功标准。

共用章节是七个分面、响应验收和最终报告。请求资产时读资产验收；复用本地文件或归档时读文件、路径与 hash 验收；批量任务再读批量验收。检查所需证据与向用户展示多少技术细节是两件事。

## 七个分面

| 分面 | 必查事实 |
| --- | --- |
| `overall` | 任务级结论：`complete`、`degraded`、`limited`、`failed` 或 `action_required`。 |
| `identity` | 规范 DOI/落地页、期望 DOI、标题，以及 `resolved/ambiguous/mismatch/unavailable`。 |
| `fetch` | 调用是否完成、是否因歧义/访问/配置需要动作；它不等同于全文存在。 |
| `content` | `fulltext`、`abstract_only`、`metadata_only` 或 `unavailable`，以及 `has_fulltext`、`has_abstract`、confidence/flags。 |
| `asset` | 请求的 profile、正文/补充资产、本地/远程、full-size/preview、failure、placeholder 和 not-archived 事实。 |
| `output` | 只检查本次明确请求的 article/Markdown/metadata 或文件；未请求不算缺失。 |
| `provenance` | 结构化 fallback/warning/failure code、trace、semantic loss 和 asset failure。 |

顶层兼容 `status=ok` 只表示调用没有抛出运行时失败；`has_fulltext` 是内容事实；`overall` 才是任务验收结论。三者不能互换。摘要或 metadata 可以是成功返回，但最多是 `limited`，不能报告成全文完成。

MCP 单篇 `fetch_paper` 成功响应直接返回紧凑 `acceptance`；`batch_fetch` 在每个 result 中返回同形摘要。两者的七分面状态必须由同一个统一验收报告投影，不能从 warning 文本或 `has_fulltext` 另行推断。

当前 acceptance wire schema 是 v2（`schema_version=2`、`minimum_reader_schema_version=2`）。provenance 包含可空的 `acquisition={provider,route,representation,transport,fallback_used}`；它须与 catalog route、source owner 和 trace fallback 事实一致，缺失时保留 partial，不能从兼容 `source` 猜测。

## 资产验收

asset 分面分别记录 `accepted_preview`、`fallback_preview` 与有序去重 `issue_codes`；`preview` 等于前两者之和。只有 accepted preview 且无其它 issue 时可以 complete；publisher 明确接受的规范公式位图即使尺寸小或内容重复，也按结构化 `preview_accepted` 事实验收，不据此另造 placeholder issue。fallback preview 是 `asset_fidelity_degraded`，不等同于 `asset_download_failure`。

正文资产严格验收是 v2 的兼容增量：`require_local_body_assets` 和 `require_full_size_body_assets` 默认都为 `false`，后者自动隐含前者，且只在 `asset_profile=body|all` 时适用。报告同时给出 `has_local_body_assets`、`all_body_assets_local`、`all_body_assets_full_size`、两项 `*_satisfied`，以及 body discovered/attempted/local/full-size/preview/failed/not-archived/remote-only 计数。严格分母只包含需要独立 binary 文件的正文逻辑资产；没有 remote/failure 且已以内联语义完成的 table/formula/figure 不算缺少文件。严格 local 要求其余全部已发现正文逻辑资产落盘且没有 failure、not-archived 或 remote-only；严格 full-size 还要求没有 accepted/fallback preview。未满足时 `asset`/`overall` 为 `degraded`，已经取得的全文仍保持 `fetch=ok`。

资产验收统计 provider 合并后的逻辑资产，而不是同一远端对象的每个尺寸 URL。Springer/Nature 的 `media.springernature.com/lwNN/...` 预览别名与对应 `/full/...` 下载记录必须先按既有 full-size promotion 规则合并；全尺寸记录已有本地路径时，预览别名不能再作为第二个 `missing_path` / remote-only 资产进入 Manifest。没有对应本地记录的真实远端资产仍按原规则验收失败。

## 响应验收

- 核对响应的规范 identity 与原始输入映射；歧义、DOI mismatch 或身份不足按 [`workflow.md`](workflow.md) 的 BLOCKING 白名单处理。
- 核对 `content` 是否满足当前 [`presets.md`](presets.md) 的文本意图；任务只需摘要时可接受 limited，用户明确需要全文时不能升级结论。
- 只有请求了资产才检查 asset 完整度。默认 provider-policy 下，允许保留的远程链接、被接受的 preview 和 `asset_profile=none` 不是自动失败；请求严格 local/full-size 时必须按上述结构化 satisfaction 字段验收，不能只看 top-level `overall`。结构化 asset failure 和 placeholder 始终需报告。
- 核对请求输出集合，保留 table/formula/asset 降级、fallback code 和 source trail。普通 warning 不按字符串猜测类别。
- 核对兼容 `source` 与结构化 `acquisition`；若 acquisition 为 `null` 或与 catalog/trace 不一致，明确保留 provenance partial/degraded，不以 provider 名或 URL 补全。向用户展示字段的范围按最终报告处理。
- envelope、acceptance 和 manifest 的完整 trace event count 必须一致；两个 retry 的同 code 是两条事实，不能按 marker 去重。`quality` 中的 source trail 只是摘要，不得回拼成第二份 trace。

## 文件、路径与 hash 验收

任务要求写盘或复用本地文件时，对 CLI `output_path`、批量 `output_artifacts[*].path`、单篇 MCP 请求参数确定的 Markdown 目标或待复用文件执行以下检查：

1. 路径位于用户选择/推断的目标目录，文件存在、可读且非空。
2. Markdown front matter 或 manifest identity 与规范目标一致；文件名和正文里偶然出现的 DOI 不能证明归属。
3. 内容级别满足意图；`abstract_only` / `metadata_only` 文件仍不能当作 fulltext archive。
4. 当前文件 size/SHA-256 与返回的输出快照一致；没有输出快照时直接计算实际值供验收，按最终报告的场景决定是否展示。
5. 资产 profile 与实际本地文件、MIME/尺寸/hash、remote-only 或 missing 事实一致。

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

- 结果必须覆盖原始规范目标的完整 1-based index 集合；响应 `results` 和最终 JSONL 都按 input index，`completion_order` 只在响应中表示实际完成顺序。
- 每个 index 都有 terminal record、request fingerprint、acceptance 和结构化 error/输出 hash；取消、限流和未调度项不能静默消失。
- 最终 JSONL、主输出和额外 Markdown 分别验收；某一类文件存在不证明其它类已经完成。JSONL 是一次性最终结果，不作为恢复状态。

## 最终报告

- 普通阅读：保留论文身份、可追溯来源、实际取得的内容范围及影响任务的降级。全文、摘要和元数据必须区分；browser HTML 失败后 PDF 成功仍需保留精确 failure code 和 degraded 结论。
- 归档：补充实际产物路径、验收结论和缺失资产；只展示本次请求的产物，不把未请求项列为失败。
- 失败或需用户动作：说明具体原因、受影响目标及必要动作；按需展开结构化 code、执行面、attempt、acquisition、hash 或诊断路径。用户要求审计时提供完整技术证据。
- 批量：保留原始 index/query 到规范身份的映射及逐项状态，汇总 complete/degraded/limited/failed/action-required、限流、取消和未调度项；其余技术字段保留在已有机器结果中，按核对或诊断需要展示。

展示精简不改变工具、manifest 或 cache 的完整结果，也不省略必要的身份、文件和降级验收。需重试时只按 [`failure-handling.md`](failure-handling.md) 的上限和状态变化条件执行。

获取验收后，宿主继续完成用户原本要求的总结、比较、翻译或提取；不要以获取报告结束阅读任务。证据不足时说明限制并完成有依据的部分，不把摘要或片段冒充全文。paper-fetch 本身仍只负责身份解析、全文获取、验收与报告。
