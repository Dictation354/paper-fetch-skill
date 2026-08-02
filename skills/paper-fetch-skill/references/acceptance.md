# 统一验收与报告

抓取、cache 命中或本地文件复用都不是最终成功。每个规范目标必须读取工具、manifest 或 cache 返回的统一 acceptance，复核实际响应/文件，再进入 report；不要按 warning 文案另造成功标准。

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

当前 acceptance wire schema 是 v2（`schema_version=2`、`minimum_reader_schema_version=2`）。asset 分面分别记录 `accepted_preview`、`fallback_preview` 与有序去重 `issue_codes`，同时保留 `preview` 且要求它等于前两者之和。只有 accepted preview 且无其它 issue 时可以 complete；fallback preview 是 `asset_fidelity_degraded`，不等同于 `asset_download_failure`。

## 响应验收

- 核对响应的规范 identity 与原始输入映射；歧义、DOI mismatch 或身份不足按 [`workflow.md`](workflow.md) 的 BLOCKING 白名单处理。
- 核对 `content` 是否满足当前 [`presets.md`](presets.md) 的文本意图；任务只需摘要时可接受 limited，用户明确需要全文时不能升级结论。
- 只有请求了资产才检查 asset 完整度。允许保留的远程链接、被接受的 preview 和 `asset_profile=none` 不是自动失败；结构化 asset failure 和 placeholder 仍需报告。
- 核对请求输出集合，保留 table/formula/asset 降级、fallback code 和 source trail。普通 warning 不按字符串猜测类别。
- envelope、acceptance 和 manifest 的完整 trace event count 必须一致；两个 retry 的同 code 是两条事实，不能按 marker 去重。`quality` 中的 source trail 只是摘要，不得回拼成第二份 trace。

## 文件、路径与 hash 验收

任务要求写盘时，对每个返回的 `output_path`、`saved_markdown_path` 或 `output_artifacts[*].path` 执行以下检查：

1. 路径位于用户选择/推断的目标目录，文件存在、可读且非空。
2. Markdown front matter 或 manifest identity 与规范目标一致；文件名和正文里偶然出现的 DOI 不能证明归属。
3. 内容级别满足意图；`abstract_only` / `metadata_only` 文件仍不能当作 fulltext archive。
4. 当前文件 size/SHA-256 与 manifest snapshot 一致；`paper-fetch manifest audit <path>` / `reconcile <path>` 的 stale 结果必须保留为未通过。
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

## 批量与恢复验收

- 结果必须覆盖原始规范目标的完整 1-based index 集合；`results` 按 input index，`completion_order`/JSONL 行序只表示完成顺序。
- 每个 index 的最新 attempt 都有 terminal record、run/record ID、request fingerprint、acceptance 和结构化 error/输出 hash；取消、限流和未调度项不能静默消失。
- Resume 前先只读 audit。只有 reusable 的最新 attempt 可跳过；missing、stale、失败或低于请求质量的项追加下一 attempt。输入顺序、工具版本或关键请求 fingerprint 不一致时新建 run，不改写旧状态。
- 持久化 summary/JSONL、主输出和额外 Markdown 分别验收；某一类文件存在不证明其它类已经完成。

## 最终报告

每项至少报告原始 index/query、规范 identity、local/cache 是否复用、所选执行面、provider/source、attempt、`overall` 与 content/asset/output 降级、结构化 code、实际产物路径和 hash，以及仍需用户完成的动作。批量另给 complete/degraded/limited/failed/action-required、限流、取消和未调度汇总。需要重试时只按 [`failure-handling.md`](failure-handling.md) 的上限和状态变化条件执行。
