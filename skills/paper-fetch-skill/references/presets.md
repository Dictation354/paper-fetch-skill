# 任务预设与落盘矩阵

输入超过 50 条时，在批量解析前先读[分块规则](#批量分块与证据等级)。按 [`workflow.md`](workflow.md) 完成身份解析后，读取共同规则和当前任务对应的预设，先确定请求参数及必要的 scope，再检查本地/cache。预设只补全用户未指定项；按预设执行不必另读落盘矩阵，自定义输出组合时才查对应矩阵。不要用预设跳过当前任务适用的验收或探测核对与报告。

## 目录

- [共同规则](#共同规则)
- [任务目标](#任务目标)
- [临时阅读](#1-临时阅读)
- [可缓存阅读](#2-可缓存阅读)
- [单篇本地归档](#3-单篇本地归档)
- [仅探测](#4-批量可读性分诊)
- [批量本地归档](#5-批量本地归档)
- [CLI 输出/落盘矩阵](#cli-输出落盘矩阵)
- [MCP 输出/落盘矩阵](#mcp-输出落盘矩阵)
- [本地优先决策树](#本地优先决策树)
- [批量分块与证据等级](#批量分块与证据等级)

## 共同规则

- 支持 `include_refs` 的 fetch/cache 调用（`fetch_paper`、`batch_fetch`、`get_cached` 及 CLI fetch）都显式选择引用范围：`none`、`top10` 或 `all`。以下完整阅读示例选择 `all`；任务不需要参考文献时改为 `none`。解析、探测、`list_cached` 等不支持该参数的接口不传此字段。
- 每条 CLI fetch 命令都显式传 `--artifact-mode` 和 `--asset-profile`。`--output` / `--output-dir` 是主输出；`--save-markdown` 只是额外 Markdown 副本。
- 正文任务的文本归档使用 `artifact_mode=none`、`asset_profile=none`。用户明确要求正文图时使用 `artifact_mode=markdown-assets`、`asset_profile=body`；随正文获取补充材料时使用 `artifact_mode=markdown-assets`、`asset_profile=all`。只要补充材料时按[任务目标](#任务目标)使用独立材料请求。
- 只在用户还要求原始 provider 载荷或调试 sidecar 时使用 `artifact_mode=all`。正文任务随附的补充材料范围由 `asset_profile=all` 决定；独立材料任务的范围固定，二者均不由 `artifact_mode=all` 决定。
- `body|all` 资产共用每篇运行时预算，不拆调用规避；超限按结构化原因说明未归档项。具体预算仅在需要时查[资产参数](tool-contract.md#fetch-notes)。
- 默认使用兼容的 provider-policy 资产验收。用户明确要求离线完整正文资产时，CLI 加 `--require-local-body-assets`、MCP strategy 加 `require_local_body_assets=true`；明确要求原尺寸时改用 `--require-full-size-body-assets` / `require_full_size_body_assets=true`，它会自动隐含 local。两项只适用于 `body|all`，不应加到纯文本预设。
- MCP 的 `no_download` 控制 provider 载荷、资产和 fetch-envelope sidecar；CLI 使用 `--artifact-mode none`。`save_markdown=true` 仍会写用户要求的 Markdown；PF-005 的 DOI 证明索引也会随显式保存更新。
- “不保存最终 Markdown”“不建立用户归档”“不写 provider artifact”“允许 cache”和“完全不落盘”是五个独立判断，不要互换。

## 任务目标

`target` 与下列五个预设的路径、批量和落盘选择分开处理；默认 `paper`。正文阅读、归档和仅探测沿用原预设。用户只要补充附件、Source Data、Extended Data 或多媒体时，CLI 加 `--target supplementary`，MCP `fetch_paper` / `batch_fetch` 传 `target="supplementary"`，不先抓正文或探测全文可用性。

- 材料范围由 provider 定义，`asset_profile`、引用、token 及严格正文资产参数不影响范围。CLI 可显式传 `--asset-profile none`，仍按独立材料范围处理。
- 下载材料时沿用已有归档路径和批量设置，使用 `artifact_mode=markdown-assets`；MCP 同时设 `no_download=false`。需要保存 Markdown 材料索引时沿用 `save_markdown` 和输出路径设置，不照搬文本归档的禁止下载参数。
- 只需发现清单时，MCP 用 `no_download=true`，CLI 用 `--artifact-mode none`；显式保存索引仍按原落盘语义处理，清单不等于材料已下载。
- 本地复用检查同一论文的材料清单和所需文件；已有全文不能替代材料请求。已有 cache scope 且允许复用时，MCP 材料请求可用 `prefer_cache=true`，由工具检查独立请求匹配及文件状态。

返回字段见[独立补充材料任务](tool-contract.md#独立补充材料任务)，结果按[补充材料验收](acceptance.md#补充材料验收)处理。

## 五个预设

### 1. 临时阅读

适用：取得阅读、总结、比较或翻译所需正文，且不要求归档或缓存。多篇比较也沿用此预设。优先使用 MCP `fetch_paper`，并完整显式传参：

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

这个组合把正文放在 MCP 响应中，不写论文产物或 cache。保持 `prefer_cache=false`，不为临时阅读要求 scope；managed runtime 的自动准备独立于论文落盘参数。

多篇完整阅读先复用并读取合格本地正文；其余每个规范目标直接调用上述单篇预设，在 provider 速率和 runtime 限制内受控并发。不要先批量抓取再重复获取；单篇 `fetch_paper` 不接受 `concurrency`、`detail` 或 `content_max_chars`。核对实际收到的正文与截断提示后继续用户的阅读任务。

CLI 会准备工作目录；若接受此行为且只需 stdout，见 [CLI 单篇用法](cli-workflow.md#单篇)。要求完全不写论文产物或 cache 时使用上面的 MCP 组合。

### 2. 可缓存阅读

适用：单篇或多篇阅读，用户允许缓存且已有明确 cache scope。使用 MCP `fetch_paper`，把响应保留在上下文，同时只允许写严格请求匹配所需的 fetch-envelope sidecar 和 DOI cache index：

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

按[本地优先决策树](#本地优先决策树)查询同 scope；直接消费 `request_satisfied`，未满足则正常抓取并写 cache。CLI 没有等价的 cache-only / prefer-cache 预设。

### 3. 单篇本地归档

适用：用户要求保存一篇论文到本地。默认只归档主 Markdown，不隐式下载图片：

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

用户要求正文图时，把 CLI 改为 `--artifact-mode markdown-assets --asset-profile body`；把 MCP 改为 `no_download=false`、`artifact_mode="markdown-assets"`、`strategy.asset_profile="body"`。随正文获取补充材料时把两个执行面的 asset profile 改为 `all`；只要补充材料时按[任务目标](#任务目标)改用独立请求。不要同时保留 `no_download=true`，否则资产不会落盘。

### 4. 批量可读性分诊

适用：只需探测指定论文的全文可用性；单篇也沿用此预设。身份解析使用 `batch_resolve`（单篇用 `resolve_paper`）；探测使用 MCP `batch_check`，不要用 CLI 全文 fetch 冒充低成本 probe。以下 `batch_check` 示例显式设置 `mode="metadata"` 和并发数；不向 `batch_resolve` 传 `mode`：

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

`batch_check(mode="metadata")` 不写下载目录，只返回可用性证据。调用后直接按[探测核对与报告](acceptance.md#探测核对与报告)完成任务，不要求全文 acceptance，不自动升级为抓取。只有需要解释返回字段时才查 [Batch Probe Contract](tool-contract.md#batch-probe-contract)。

超过 50 条时从解析阶段起按[批量分块与证据等级](#批量分块与证据等级)处理。CLI 当前没有等价的 metadata probe 预设。

### 5. 批量本地归档

适用：用户要求将多篇论文归档到本地。默认使用 CLI 文本归档，并显式指定主输出、汇总、artifact 和资产策略：

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

每篇主 Markdown 和 `batch-results.jsonl` 都是用户归档。需要正文图时显式改为 `--artifact-mode markdown-assets --asset-profile body`；随正文获取补充材料时显式改为 `--artifact-mode markdown-assets --asset-profile all`；只要补充材料时按[任务目标](#任务目标)改用独立请求。

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

这个 MCP 组合写每篇 Markdown 和最终 input-ordered JSONL，返回 compact acceptance 与文件快照；JSONL 不提供恢复语义。正文图或补充材料按[单篇归档](#3-单篇本地归档)调整。返回字段需要查阅时见 [Batch Fetch Contract](tool-contract.md#batch-fetch-contract)，实际文件按[文件验收](acceptance.md#文件路径与-hash-验收)核对。

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

`batch_fetch` 不传 `batch_results` 时不写批量结果文件；无需落盘的批量正文验收可沿用第一行完全不落盘组合。默认 `detail="compact"` 不返回正文；只需片段时显式用 `detail="bounded", content_max_chars=<全批上限>`，并检查逐项 `content_truncated`、`content_available_chars` 和 `content_returned_chars`。需要完整阅读时直接使用单篇阅读预设或读取合格文件，不能用 compact 验收摘要或 bounded 截断片段宣称已读全文。显式传入 `batch_results` 时，即使论文下载参数本身不落盘，最终 JSONL 仍是预期写盘产物。

## 本地优先决策树

先按任务意图确定参数，再按适用分支执行：已核验本地 fulltext → 同 scope 精确 DOI cache → 严格请求匹配的 prefer-cache → 正常 fetch。

临时阅读未指定 cache scope 或用户禁止使用缓存时，跳过第 2、3 步，不为查缓存而要求目录；若本地全文未满足任务，直接使用临时阅读预设。临时阅读已指定 scope 且允许读取缓存时，可只读检查并复用合格本地 Markdown；需要由 `fetch_paper` 返回结构化正文时仍保持 `prefer_cache=false, download_dir=null`，不把缓存查询 scope 带入完全不落盘请求。可缓存阅读和归档则使用各自预设的 scope 与缓存参数。

对每个已经规范化的目标按以下顺序执行适用步骤：

1. **已核验本地 fulltext**：先检查用户提供或工作区已有的文件。只复用身份可证明、`has_fulltext=true` / `content_kind=fulltext`、内容和当前资产意图相符的文件；命中后不调用网络工具，直接进入 acceptance。
2. **同 scope 精确 DOI cache**：已知 DOI 时调用 `get_cached(doi=<normalized-doi>, download_dir=<scope>)`，实际常规参数补全为 `detail="compact", preferred_only=true, modes=..., strategy=..., include_refs=..., max_tokens=...`；不要为已知 DOI 全量调用 `list_cached()`。`get_cached` 只扫描该 scope，不联网。若 `preferred.markdown` 是已证明的合格 fulltext，读取它并进入 acceptance；不能仅凭顶层 `status=hit` 宣称请求匹配。
3. **严格请求匹配的 prefer-cache**：仍需结构化响应或只有 fetch-envelope 时，先要求 compact cache 结果的 `request_satisfied=true`，再用同一个 `download_dir` 调用 `fetch_paper(..., prefer_cache=true)`，并显式传与当前意图相同的 `modes`、`strategy`、`include_refs` 和 `max_tokens`。直接消费该布尔值，不手工重算 fingerprint、sidecar 版本或 payload modes 匹配；未满足时进入正常 fetch。
4. **正常 fetch**：本地/cache 未满足任务时，按选定预设调用 `fetch_paper`；可缓存请求保持 `prefer_cache=true`，工具在 cache miss 时进入正常抓取。不要因 cache miss 停止，也不要放宽请求匹配。

使用第 3 步的 prefer-cache 复用时，从 `get_cached` 到 `fetch_paper` 始终传相同的 `download_dir` 和请求参数。只有 DOI 未知且任务确实需要浏览 scope 时才使用 `list_cached()`；它不能替代身份解析。

## 批量分块与证据等级

- 在输入规范化时为每条原始输入固定 1-based `index`，去重和分块后仍保留原 index 到规范目标的映射。
- `batch_resolve`、`batch_check`、`batch_fetch` 每次均最多 50 条。首次批量解析前按原顺序切块；例如 113 条先拆成 `[1..50]`、`[51..100]`、`[101..113]`。每块显式传 `concurrency`。汇总解析结果后跨块 DOI 去重，再把需 probe/fetch 的规范目标按每块最多 50 条提交。原始 index 是宿主保留的映射，不作为工具额外参数；将各阶段块内结果映射到全部原始别名，最终按原 index 排序，不按完成顺序或块内 `1..N` 重新编号。
- `batch_check(mode="metadata")` 是 likely probe：`likely_yes` 表示有可读信号，`unknown` 表示证据不足。二者都不是已抓取全文。
- 真实抓取使用 `batch_fetch` 或 `fetch_paper`，并通过 acceptance 才能报告全文完成；已移除 article check。无需落盘的正文检查参数见 [Batch Probe Contract](tool-contract.md#batch-probe-contract)。
