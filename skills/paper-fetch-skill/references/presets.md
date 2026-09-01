# 任务预设与落盘矩阵

把已确认的任务意图映射成下面五个预设。先按 [`workflow.md`](workflow.md) 完成身份解析和本地/cache 检查，再使用本文件；不要用预设跳过 acceptance 和 report。

## 目录

- [共同规则](#共同规则)
- [五个预设](#五个预设)
- [CLI 输出/落盘矩阵](#cli-输出落盘矩阵)
- [MCP 输出/落盘矩阵](#mcp-输出落盘矩阵)
- [本地优先决策树](#本地优先决策树)
- [批量分块与证据等级](#批量分块与证据等级)

## 共同规则

- 每次调用都显式选择引用范围：`none`、`top10` 或 `all`。以下完整阅读示例选择 `all`；任务不需要参考文献时改为 `none`，不要省略参数。
- 每条 CLI fetch 命令都显式传 `--artifact-mode` 和 `--asset-profile`。`--output` / `--output-dir` 是主输出；`--save-markdown` 只是额外 Markdown 副本。
- 文本归档使用 `artifact_mode=none`、`asset_profile=none`。用户明确要求正文图时使用 `artifact_mode=markdown-assets`、`asset_profile=body`；明确要求补充材料时使用 `artifact_mode=markdown-assets`、`asset_profile=all`。
- 只在用户还要求原始 provider 载荷或调试 sidecar 时使用 `artifact_mode=all`。补充材料范围由 `asset_profile=all` 决定，不由 `artifact_mode=all` 决定。
- `asset_profile=body|all` 始终受每篇共享预算约束（默认 128 文件、32 MiB/文件、256 MiB 累计、64 MP、最多 4 个资产 worker并受 route cap 限制）；不要通过把正文图和 supplementary 拆成两次调用来规避。超限时以 `asset_failures[*].reason` 的稳定 `asset_*` code 向用户说明未归档项。
- 默认使用兼容的 provider-policy 资产验收。用户明确要求离线完整正文资产时，CLI 加 `--require-local-body-assets`、MCP strategy 加 `require_local_body_assets=true`；明确要求原尺寸时改用 `--require-full-size-body-assets` / `require_full_size_body_assets=true`，它会自动隐含 local。两项只适用于 `body|all`，不应加到纯文本预设。
- MCP 的 `no_download` 控制 provider 载荷、资产和 fetch-envelope sidecar；CLI 使用 `--artifact-mode none`。`save_markdown=true` 仍会写用户要求的 Markdown；PF-005 的 DOI 证明索引也会随显式保存更新。
- “不保存最终 Markdown”“不建立用户归档”“不写 provider artifact”“允许 cache”和“完全不落盘”是五个独立判断，不要互换。

## 五个预设

### 1. 临时阅读

优先使用 MCP，并完整显式传参：

```json
{
  "query": "10.1186/1471-2105-11-421",
  "modes": ["article", "markdown"],
  "strategy": {
    "allow_metadata_only_fallback": true,
    "preferred_providers": null,
    "asset_profile": "none",
    "inline_image_budget": null
  },
  "include_refs": "all",
  "max_tokens": "full_text",
  "prefer_cache": false,
  "no_download": true,
  "artifact_mode": "none",
  "save_markdown": false,
  "markdown_output_dir": null,
  "markdown_filename": null,
  "download_dir": null
}
```

这个组合把正文放在 MCP 响应中，不写最终 Markdown、provider artifact、资产、fetch-envelope sidecar 或 cache index。保持 `prefer_cache=false`，否则读取 cache 就需要一个 `download_dir` scope。

CLI 没有同等的硬零写盘保证；它在 fetch 前会准备工作目录。只需要 stdout 且接受创建一个空工作目录时使用：

```bash
paper-fetch fetch --query "10.1186/1471-2105-11-421" \
  --format markdown \
  --output - \
  --output-dir ./.paper-fetch-tmp \
  --artifact-mode none \
  --asset-profile none \
  --include-refs all \
  --max-tokens full_text
```

此 CLI 组合不写论文文件，但会创建或检查 `./.paper-fetch-tmp`。要求完全不落盘时改用上面的 MCP 预设。

### 2. 可缓存阅读

使用 MCP，把响应保留在上下文，同时只允许写严格请求匹配所需的 fetch-envelope sidecar 和 DOI cache index：

```json
{
  "query": "10.1186/1471-2105-11-421",
  "modes": ["article", "markdown"],
  "strategy": {
    "allow_metadata_only_fallback": true,
    "preferred_providers": null,
    "asset_profile": "none",
    "inline_image_budget": null
  },
  "include_refs": "all",
  "max_tokens": "full_text",
  "prefer_cache": true,
  "no_download": false,
  "artifact_mode": "none",
  "save_markdown": false,
  "markdown_output_dir": null,
  "markdown_filename": null,
  "download_dir": "./.paper-fetch-cache"
}
```

先按本地优先决策树调用同 scope 的 `get_cached(detail="compact", preferred_only=true)`，并传与上述 fetch 完全相同的 `modes`、`strategy`、`include_refs` 和 `max_tokens`。`status=hit` 只表示存在已证明条目；只有 `request_satisfied=true` 才表示严格匹配的 sidecar 可短路联网。没有 sidecar 或请求不匹配时正常抓取，并为后续相同请求写 cache。CLI 没有等价的 cache-only / prefer-cache 预设；不要把 `--artifact-mode all` 冒充成可缓存阅读。

### 3. 单篇本地归档

默认只归档主 Markdown，不隐式下载图片：

```bash
paper-fetch fetch --query "10.1186/1471-2105-11-421" \
  --format markdown \
  --output ./papers/example.md \
  --output-dir ./papers \
  --artifact-mode none \
  --asset-profile none \
  --include-refs all \
  --max-tokens full_text
```

MCP 文本归档显式把主 Markdown 与 cache scope 放在同一目录：

```json
{
  "query": "10.1186/1471-2105-11-421",
  "modes": ["article", "markdown"],
  "strategy": {
    "allow_metadata_only_fallback": true,
    "preferred_providers": null,
    "asset_profile": "none",
    "inline_image_budget": null
  },
  "include_refs": "all",
  "max_tokens": "full_text",
  "prefer_cache": true,
  "no_download": true,
  "artifact_mode": "none",
  "save_markdown": true,
  "markdown_output_dir": "./papers",
  "markdown_filename": "example.md",
  "download_dir": "./papers"
}
```

这个 MCP 组合写 `./papers/example.md` 和证明其 DOI 归属所需的 cache index，不写 fetch-envelope sidecar、provider artifact 或资产。响应会把 `article`、`markdown` 设为 `null`，保留诊断字段；文件位置由请求中的输出目录/文件名确定，并通过返回路径或批量 `output_artifacts` 验收。

用户要求正文图时，把 CLI 改为 `--artifact-mode markdown-assets --asset-profile body`；把 MCP 改为 `no_download=false`、`artifact_mode="markdown-assets"`、`strategy.asset_profile="body"`。用户要求补充材料时把两个执行面的 asset profile 改为 `all`。不要同时保留 `no_download=true`，否则资产不会落盘。

### 4. 批量可读性分诊

使用 MCP `batch_resolve` / `batch_check`，不要用 CLI 全文 fetch 冒充低成本 probe。每次显式设置 `mode="metadata"` 和并发数：

```json
{
  "queries": [
    "10.1000/first",
    "10.1000/second"
  ],
  "mode": "metadata",
  "concurrency": 4
}
```

`batch_check(mode="metadata")` 固定不写下载目录，结果只有 `likely_yes` 或 `unknown` 的探测证据。结果数组与输入等长、原顺序，每项保留 1-based `index/query/status/error/provider_lane`；`not_scheduled` 不是完成，顶层 progress 会单列。Title 会先在 item-local context 解析 provider lane，已知 DOI 只做本地 canonical 规范化；一个 provider 的 cooldown 不会扩大到其它 lane。它没有抓取全文，不能报告成“已归档”“已验证全文”或“metadata-only 全文”。需要真实正文结论时，对选中的规范 DOI 再进入本地优先决策树并调用 `fetch_paper`。

超过 50 条时按[批量分块与证据等级](#批量分块与证据等级)处理。CLI 当前没有等价的 metadata probe 预设。

### 5. 批量本地归档

默认使用 CLI 文本归档，并显式指定主输出、汇总、artifact 和资产策略：

```bash
paper-fetch fetch --query-file ./queries.txt \
  --format markdown \
  --output-dir ./papers \
  --batch-concurrency 4 \
  --batch-results ./papers/batch-results.jsonl \
  --artifact-mode none \
  --asset-profile none \
  --include-refs all \
  --max-tokens full_text
```

每篇主 Markdown 和 `batch-results.jsonl` 都是用户归档。需要正文图时显式改为 `--artifact-mode markdown-assets --asset-profile body`；需要补充材料时显式改为 `--artifact-mode markdown-assets --asset-profile all`。

需要 MCP 宿主内 progress/cancel、结构化 acceptance 或不便解析 CLI stdout 时，使用 `batch_fetch`；其归档预设显式保留同一文本意图和持久化路径：

```json
{
  "queries": ["10.1000/first", "10.1000/second"],
  "concurrency": 4,
  "modes": ["article", "markdown"],
  "strategy": {"asset_profile": "none"},
  "include_refs": "all",
  "max_tokens": "full_text",
  "prefer_cache": true,
  "no_download": true,
  "artifact_mode": "none",
  "save_markdown": true,
  "markdown_output_dir": "./papers",
  "download_dir": "./papers",
  "detail": "compact",
  "batch_results": "./papers/batch-results.jsonl",
  "overwrite": false
}
```

这个 MCP 组合为每篇返回 input-ordered compact record、实际完成序号、acceptance、输出 SHA-256 和 Markdown path，并在整批结束时按输入顺序原子写一次 `batch_results`。同批规范 DOI 重复项只抓取 representative 一次，再 fan-out 到原 index；不同请求之间不共享执行。已有不同内容路径默认拒绝覆盖；`batch_results` 不是 journal，也不提供恢复语义。正文图和补充材料仍按上文分别改成 `no_download=false`、`artifact_mode="markdown-assets"`、`asset_profile="body|all"`。`batch_check` 仍不是归档工具，不能用 probe 结果替代 `batch_fetch`/CLI 的真实 fetch 和 acceptance。

## CLI 输出/落盘矩阵

CLI 始终在 fetch 前准备显式 `--output-dir` 或解析后的默认下载目录。表中的“无论文文件”不等于硬零写盘。

| 显式组合 | stdout | 主输出 | 额外 Markdown | provider/cache artifact | 本地资产 | 实际落盘结论 |
| --- | --- | --- | --- | --- | --- | --- |
| `--output - --artifact-mode none --asset-profile none` | Markdown | 无 | 无 | 无 | 无 | 仅准备工作目录；无论文文件 |
| `--output <paper.md> --artifact-mode none --asset-profile none` | 无 | `<paper.md>` | 无 | 无 | 无 | 只写主输出 |
| `--output-dir <dir> --artifact-mode none --asset-profile none` | 无 | `<dir>/<paper-stem>.md` | 无 | 无 | 无 | 只写主输出；批量另写 JSONL 汇总 |
| `--format json --output <paper.json> --output-dir <dir> --save-markdown --artifact-mode none --asset-profile none` | 无 | `<paper.json>` | `<dir>/<paper-stem>.md` | 无 | 无 | 显式写主 JSON 与额外 Markdown |
| `--output <paper.md> --output-dir <dir> --artifact-mode markdown-assets --asset-profile body` | 无 | `<paper.md>` | 无重复副本 | PDF fallback 等保留型 artifact | 正文资产 | 主输出加正文归档 |
| `--output <paper.md> --output-dir <dir> --artifact-mode markdown-assets --asset-profile all` | 无 | `<paper.md>` | 无重复副本 | PDF fallback 等保留型 artifact | 正文与补充资产 | 主输出加完整资产范围 |
| `--output <paper.md> --output-dir <dir> --artifact-mode all --asset-profile body|all` | 无 | `<paper.md>` | 无重复副本 | 再加原始 provider 载荷、调试 sidecar | 显式 profile 对应资产 | 仅用于用户要求调试/原始材料 |

CLI 不提供 cache-only `prefer_cache`。`--artifact-mode none` 不会禁止显式 `--output`、由 `--output-dir` 承接的主输出或 `--save-markdown`。

## MCP 输出/落盘矩阵

| 显式组合 | MCP 正文响应 | 用户 Markdown | fetch-envelope/cache index | provider artifact | 本地资产 | 实际落盘结论 |
| --- | --- | --- | --- | --- | --- | --- |
| `save_markdown=false, no_download=true, prefer_cache=false, artifact_mode=none, asset_profile=none, download_dir=null` | 有 | 无 | 无 | 无 | 无 | 完全不落盘 |
| `save_markdown=false, no_download=false, prefer_cache=true, artifact_mode=none, asset_profile=none, download_dir=<scope>` | 有 | 无 | sidecar + index + 锁元数据 | 无 | 无 | 只写可复用 cache |
| `save_markdown=true, no_download=true, prefer_cache=true, artifact_mode=none, asset_profile=none, markdown_output_dir=<dir>, download_dir=<dir>` | 紧凑响应，无正文 | 有 | 仅保存注册所需 index 与锁元数据；无 sidecar | 无 | 无 | 文本归档 |
| `save_markdown=true, no_download=false, prefer_cache=true, artifact_mode=markdown-assets, asset_profile=body, markdown_output_dir=<dir>, download_dir=<dir>` | 紧凑响应，无正文 | 有 | sidecar + index + 锁元数据 | PDF fallback 等保留型 artifact | 正文资产 | 正文图归档 |
| `save_markdown=true, no_download=false, prefer_cache=true, artifact_mode=markdown-assets, asset_profile=all, markdown_output_dir=<dir>, download_dir=<dir>` | 紧凑响应，无正文 | 有 | sidecar + index + 锁元数据 | PDF fallback 等保留型 artifact | 正文与补充资产 | 补充材料归档 |
| `save_markdown=true, no_download=false, prefer_cache=true, artifact_mode=all, asset_profile=body|all, markdown_output_dir=<dir>, download_dir=<dir>` | 紧凑响应，无正文 | 有 | sidecar + index + 锁元数据 | 再加原始 provider 载荷、调试 sidecar | 显式 profile 对应资产 | 调试/原始材料归档 |
| `batch_fetch(..., batch_results=<path>)` | input-ordered compact；可选全批受限片段 | 由同一 `save_markdown` 参数决定 | 由同一 `no_download/prefer_cache` 参数决定 | 由同一 artifact mode 决定 | 由同一 asset profile 决定 | 原子写最终 input-ordered JSONL，不可恢复 |

`artifact_mode=none` 不等于 MCP 完全不落盘：只要 `no_download=false`，成功 fetch 仍会写 fetch-envelope sidecar 和 cache index。`no_download=true` 也不覆盖 `save_markdown=true` 的显式用户输出。

`batch_fetch` 不传 `batch_results` 时不写批量结果文件；因此临时批量阅读仍可沿用第一行完全不落盘组合。默认 `detail="compact"` 不返回多篇正文；确需临时片段时显式用 `detail="bounded", content_max_chars=<全批上限>`。显式传入 `batch_results` 时，即使论文下载参数本身不落盘，最终 JSONL 仍是预期写盘产物。

## 本地优先决策树

固定顺序是：已核验本地 fulltext → 同 scope 精确 DOI cache → 严格请求匹配的 prefer-cache → 正常 fetch。

对每个已经规范化的目标严格按以下顺序执行：

1. **已核验本地 fulltext**：先检查用户提供或工作区已有的文件。只复用身份可证明、`has_fulltext=true` / `content_kind=fulltext`、内容和当前资产意图相符的文件；命中后不调用网络工具，直接进入 acceptance。
2. **同 scope 精确 DOI cache**：已知 DOI 时调用 `get_cached(doi=<normalized-doi>, download_dir=<scope>)`，实际常规参数补全为 `detail="compact", preferred_only=true, modes=..., strategy=..., include_refs=..., max_tokens=...`；不要为已知 DOI 全量调用 `list_cached()`。`get_cached` 只扫描该 scope，不联网。若 `preferred.markdown` 是已证明的合格 fulltext，读取它并进入 acceptance；不能仅凭顶层 `status=hit` 宣称请求匹配。
3. **严格请求匹配的 prefer-cache**：仍需结构化响应或只有 fetch-envelope 时，先要求 compact cache 结果的 `request_satisfied=true`，再用同一个 `download_dir` 调用 `fetch_paper(..., prefer_cache=true)`，并显式传与当前意图相同的 `modes`、`strategy`、`include_refs` 和 `max_tokens`。该布尔值直接复用 `cached_request_matches()` 严格匹配并检查 payload modes；不匹配不得复用。
4. **正常 fetch**：sidecar 缺失或请求不匹配时，上一步的 `fetch_paper` 自动进入正常抓取。不要因 cache miss 停止，也不要放宽请求匹配。

从 `get_cached` 到 `fetch_paper` 始终传相同的 `download_dir`。只有 DOI 未知且任务确实需要浏览 scope 时才使用 `list_cached()`；它不能替代身份解析。

## 批量分块与证据等级

- 在输入规范化时为每条原始输入固定 1-based `index`，去重和分块后仍保留原 index 到规范目标的映射。
- 对超过 50 条的分诊按原顺序切块；例如 113 条必须拆成 `[1..50]`、`[51..100]`、`[101..113]`。每块最多 50 条，并显式传 `concurrency`。给每条块内结果重新附上分块前的原 index，收集后按该 index 排序合并；不得用完成顺序或块内 `1..N` 重新编号。
- `batch_check(mode="metadata")` 是 likely probe：`likely_yes` 表示有可读信号，`unknown` 表示证据不足。二者都不是已抓取全文。
- 只有 `batch_check(mode="article")` 或后续 `fetch_paper` 才执行真实抓取；仍需通过 acceptance 才能报告全文完成。
