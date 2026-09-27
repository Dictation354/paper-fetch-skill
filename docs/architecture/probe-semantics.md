# `batch_check` Probe 语义说明

`batch_check(queries=[query])` 是单篇和批量的低成本全文可用性预判。
它复用 Python `probe_has_fulltext()`，`mode` 默认且仅允许 `"metadata"`，
不触发正文 waterfall，也不写下载目录。它仍会进行 metadata/landing 网络请求，
不是本地静态诊断；本地诊断使用 `provider_status` / CLI `doctor`。

## 与真实抓取的区别

| 入口 | 证据 | 结论 |
| --- | --- | --- |
| `batch_check` | metadata、路由及 landing meta | 可能可用或证据不足 |
| `fetch_paper` / `batch_fetch` | 完整 provider 抓取和统一验收 | 最终 `has_fulltext` 与 acceptance |

有 license、全文链接或 `citation_pdf_url` 不证明当前可成功获取；probe 没有正信号时，
后续 provider HTML/PDF 路径仍可能成功。两者不要求逐案一致。独立 `has_fulltext`
MCP 工具和 `batch_check(mode="article")` 已移除，Python probe 服务保留。

## 证据与状态

公开 probe 状态为 `confirmed_yes`、`likely_yes`、`unknown`、`no`；当前实现只主动
生成 `likely_yes` 与 `unknown`。判断位于 `paper_fetch.workflow.routing.probe_has_fulltext`：

| 正信号 | `evidence` |
| --- | --- |
| Crossref license | `crossref_license` |
| Crossref fulltext link | `crossref_fulltext_link` |
| catalog 允许的 provider metadata probe 成功（如 Elsevier、arXiv） | `provider_probe:<provider>` |
| landing meta 包含 PDF 地址 | `landing_page_citation_pdf_url` |

至少一个正信号得到 `likely_yes`；没有正信号得到 `unknown`，不能把它解释成无全文。
metadata/probe 请求失败的 warnings 表达证据不足或环境受限，不是负结论。
具体 provider probe 能力由 runtime catalog 决定，不另维护工具侧名单。

## 调用和返回

```python
batch_check(queries=["10.1186/1471-2105-11-421"], mode="metadata", concurrency=1)
```

- 顶层包含 `schema_version=2`、`mode="metadata"`、按输入顺序的 `results`、
  `aborted`、`abort_reason` 和 `progress`。
- 每项保留稳定 1-based `index`、`query`、`status`、`error`、`provider_lane`，
  从 `probe_state`、`evidence`、`warnings` 读取预判；歧义候选在 `error.candidates`。
- 成功项的 `has_fulltext/content_kind/has_abstract/source/acquisition/token_estimate/`
  `token_estimate_breakdown` 保持 null，`source_trail/trace` 为空数组。
  `likely_has_fulltext` 仅在 `likely_yes` 时为 true，否则为 null。
- progress 区分 `terminal/completed/not_scheduled`；不能把没有调度或失败项算成
  已确认可读，也不能把 `likely_has_fulltext` 当作最终 `has_fulltext`。

真实批量获取使用 `batch_fetch` 并读取每项 `acceptance`。无需落盘的正文检查可用：

```python
batch_fetch(
    queries=["10.1186/1471-2105-11-421"],
    modes=["article"],
    detail="compact",
    save_markdown=False,
    no_download=True,
    prefer_cache=False,
    artifact_mode="none",
    strategy={"asset_profile": "none"},
)
```

不传 `batch_results`；这是显式参数组合，不改变默认行为。compact 仅返回验收摘要，
后续阅读任务仍须取得实际正文，见 [预设](../../skills/paper-fetch-skill/references/presets.md)。

## 扩展边界

probe 不承担正文下载、CLI 独立 `has_fulltext` 命令或 provider HEAD/OPTIONS 深度探测。
新增证据应保持 metadata 级成本；只有稳定证据才能支持未来的 `confirmed_yes` 或 `no`，
不能为追求与 fetch 一致而在 probe 中复制完整 waterfall。

完整流程见 [架构](overview.md)，配置与回退见 [provider 说明](../providers.md)，
Agent 的探测核对与报告见 [acceptance](../../skills/paper-fetch-skill/references/acceptance.md#探测核对与报告)。
