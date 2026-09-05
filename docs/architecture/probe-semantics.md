# `batch_check` Probe 语义说明

这份文档解决：

- `batch_check()` MCP tool 到底在回答什么问题
- 它和 `fetch_paper().has_fulltext` 有什么差别
- 使用哪些证据、会返回哪些状态

这份文档不解决：

- 完整抓取瀑布的架构背景
- provider 详细配置
- provider 深度探测策略的实现细节

完整业务流程见 [`overview.md`](overview.md)。

## 背景

`fetch_paper().has_fulltext` 是完整抓取瀑布跑完之后的最终 verdict：

1. resolve 查询
2. 获取 metadata
3. 尝试官方 provider 全文路径
4. 必要时走 provider 自管 HTML/PDF fallback
5. 必要时降级为 provider `abstract_only` 或 metadata-only

这很适合作为最终答案，但它不便宜。

因此单篇和批量低成本探测统一使用 MCP 工具：

```text
batch_check(queries=[query])
```

该入口的 `mode` 默认且仅允许 `"metadata"`。独立 `has_fulltext` 工具已移除，MCP 共九个工具；底层 Python `probe_has_fulltext` 服务保持不变。

它的目标不是“模拟完整抓取”，而是“用更便宜的信号给出一个有用但保守的预判”。

## 结论

`batch_check()` 与 `fetch_paper().has_fulltext` 不是同一个语义层级：

- `batch_check()`
  - 便宜
  - 快
  - 允许保守和不确定
  - 适合批量甄别和预检
- `fetch_paper().has_fulltext`
  - 昂贵
  - 是最终抓取瀑布后的 verdict
  - 更适合做最终展示或下游处理

因此，probe 结果不要求与最终抓取结果逐案完全一致。

## 证据来源

`batch_check()` 只使用廉价信号，不会触发完整正文抓取瀑布。

具体包括：

- `resolve_paper()` 的解析结果
- Crossref metadata
- 轻量 Elsevier metadata probe
- 落地页 HTML meta，例如 `citation_pdf_url`

它不会做：

- 完整 `_fetch_article` 瀑布
- 正文下载
- provider 级完整正文 fallback

## 状态

公开契约层声明 4 种状态：

- `confirmed_yes`
- `likely_yes`
- `unknown`
- `no`

当前实现只主动返回：

- `likely_yes`
- `unknown`

也就是说，probe 更偏“保守给正信号”，而不是积极输出否定；`confirmed_yes` 和 `no` 是契约层合法值，但当前实现不会主动生成。

## 何时返回 `likely_yes`

出现以下廉价正信号时，会倾向返回 `likely_yes`：

- Crossref metadata 中有 `license`
- Crossref metadata 中有 `fulltext_links`
- Elsevier metadata probe 命中
- 落地页 HTML meta 中发现 `citation_pdf_url`

这些信号说明“很可能存在可访问或可机器读取的全文”，但不保证当前实现一定能成功抓取。

## 何时返回 `unknown`

以下情况通常会返回 `unknown`：

- 没有足够正信号
- Elsevier probe 不可用
- 需要凭证但本地未配置
- provider 不支持对应 probe
- 落地页 HTML meta 探测失败

`unknown` 的设计目的，是避免把“不知道”误判成“没有全文”。

## warnings 的作用

`batch_check()` 的每项结果还会带 `warnings`，单篇从 `results[0].warnings` 读取。

这些 `warnings` 主要用来表达：

- Crossref metadata probe 暂时不可用
- 某个 provider 不参加 metadata probe
- 落地页 HTML meta 探测失败
- 环境缺少配置或权限，导致 probe 无法确认

调用方应把这些 warning 理解为“证据不足”或“当前探测能力受限”，而不是把它们直接解释成负结论。

## 调用和返回

`batch_check(queries, mode="metadata", concurrency=1)` 复用 Python `probe_has_fulltext` 的廉价 probe 逻辑，不触发完整正文抓取，不写下载目录。

- 顶层保持 `schema_version=2`、`mode="metadata"`、按输入顺序的 `results`、`aborted`、`abort_reason` 和 `progress`。
- 单篇也传 `queries=[query]`，从 `results[0]` 读取 `probe_state`、`evidence`、`warnings` 及逐项 `error`。歧义候选位于 `error.candidates`，不再依赖旧单篇工具顶层错误。
- 成功项的 `has_fulltext/content_kind/has_abstract/source/acquisition/token_estimate/token_estimate_breakdown` 保持 null，`source_trail/trace` 保持空数组；`likely_has_fulltext` 仅在 `likely_yes` 时为 true，否则为 null。
- 逐项保留稳定 1-based `index`、`query`、`status`、`error` 和 `provider_lane`，progress 区分 `terminal/completed/not_scheduled`。

`batch_check(mode="article")` 已移除；真实抓取使用 `batch_fetch`，并通过每项 `acceptance` 判断结果。无需落盘的正文检查使用：

```python
batch_fetch(
    queries=[...],
    modes=["article"],
    detail="compact",
    save_markdown=False,
    no_download=True,
    prefer_cache=False,
    artifact_mode="none",
    strategy={"asset_profile": "none"},
)
```

不传 `batch_results`；这是显式调用组合，不改变 `batch_fetch` 默认行为。

## 为什么 probe 不能等价于最终 fetch verdict

原因主要有四个：

1. 廉价信号不等于可成功抓取
   - 有 license、link 或 `citation_pdf_url`，不代表正文此刻一定可访问。
2. Elsevier 探针和真实全文路径未必完全同构
   - metadata probe 成功，不等于 fulltext endpoint 一定成功。
3. provider 自管 HTML/PDF fallback 可能在 probe 阶段根本没被执行
   - 最终抓取能成功，probe 仍可能只给 `unknown`。
4. 强行追求完全一致会让 probe 退化成完整抓取
   - 那就失去了 probe 的意义。

## 非目标

`batch_check()` 不负责：

- CLI 级 `has_fulltext` 命令
- 让 probe 结果强制等于 `fetch_paper().has_fulltext`
- provider 级 HEAD / OPTIONS 深度探测
- 积极产出 `confirmed_yes` 或 `no`

## 扩展边界

增强 probe 时优先保持这些边界：

- 对少数 provider 增加更强但仍廉价的 metadata-level 证据
- 在不触发完整抓取的前提下细化 `confirmed_yes`
- 只有 provider 能稳定证明无全文时才输出 `no`
- probe 语义和最终 fetch 语义保持分离

## 相关文档

- [`overview.md`](overview.md)
- [`../providers.md`](../providers.md)
- [`../../README.md`](../../README.md)
