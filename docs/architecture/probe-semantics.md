# `has_fulltext` Probe 语义说明

这份文档解决：

- `has_fulltext()` MCP tool 到底在回答什么问题
- 它和 `fetch_paper().has_fulltext` 有什么差别
- 当前 v1 使用哪些证据、会返回哪些状态

这份文档不解决：

- 完整抓取瀑布的架构背景
- provider 详细配置
- 所有未来 probe 策略的实现细节

完整业务流程见 [`target-architecture.md`](target-architecture.md)。

## 背景

`fetch_paper().has_fulltext` 是完整抓取瀑布跑完之后的最终 verdict：

1. resolve 查询
2. 获取 metadata
3. 尝试官方 provider 全文路径
4. 必要时走 provider 自管 HTML/PDF fallback
5. 必要时降级为 provider `abstract_only` 或 metadata-only

这很适合作为最终答案，但它不便宜。

因此系统额外公开了一个 MCP 工具：

```text
has_fulltext(query)
```

它的目标不是“模拟完整抓取”，而是“用更便宜的信号给出一个有用但保守的预判”。

## 结论

`has_fulltext()` 与 `fetch_paper().has_fulltext` 不是同一个语义层级：

- `has_fulltext()`
  - 便宜
  - 快
  - 允许保守和不确定
  - 适合批量甄别和预检
- `fetch_paper().has_fulltext`
  - 昂贵
  - 是最终抓取瀑布后的 verdict
  - 更适合做最终展示或下游处理

因此，probe 结果不要求与最终抓取结果逐案完全一致。

## 当前 v1 的证据来源

当前 `has_fulltext()` 只使用廉价信号，不会触发完整正文抓取瀑布。

具体包括：

- `resolve_paper()` 的解析结果
- Crossref metadata
- 轻量 Elsevier metadata probe
- 落地页 HTML meta，例如 `citation_pdf_url`

当前不会做：

- 完整 `_fetch_article` 瀑布
- 正文下载
- provider 级完整正文 fallback

## 当前 v1 的状态

公开契约预留了四种状态：

- `confirmed_yes`
- `likely_yes`
- `unknown`
- `no`

但当前 v1 主动返回的主要是：

- `likely_yes`
- `unknown`

也就是说，当前 probe 更偏“保守给正信号”，而不是积极输出否定。

## 当前 v1 何时返回 `likely_yes`

出现以下廉价正信号时，会倾向返回 `likely_yes`：

- Crossref metadata 中有 `license`
- Crossref metadata 中有 `fulltext_links`
- Elsevier metadata probe 命中
- 落地页 HTML meta 中发现 `citation_pdf_url`

这些信号说明“很可能存在可访问或可机器读取的全文”，但不保证当前实现一定能成功抓取。

## 当前 v1 何时返回 `unknown`

以下情况通常会返回 `unknown`：

- 没有足够正信号
- Elsevier probe 当前不可用
- 需要凭证但本地未配置
- provider 不支持对应 probe
- 落地页 HTML meta 探测失败

`unknown` 的设计目的，是避免把“不知道”误判成“没有全文”。

## warnings 的作用

`has_fulltext()` 返回里还会带 `warnings`。

这些 `warnings` 主要用来表达：

- Crossref metadata probe 暂时不可用
- 某个 provider 当前不参加 metadata probe
- 落地页 HTML meta 探测失败
- 当前环境缺少配置或权限，导致 probe 无法确认

调用方应把这些 warning 理解为“证据不足”或“当前探测能力受限”，而不是把它们直接解释成负结论。

## 与 `batch_check(mode="metadata")` 的关系

当前 `batch_check(mode="metadata")` 复用的就是同一条廉价 probe 逻辑。

这意味着：

- 它不会触发完整正文抓取
- 它不会把正文或 provider payload 落盘
- 它更适合 citation list 批量预判，而不是最终抓取

相对地：

- `batch_check(mode="article")` 仍保留完整抓取语义

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

## 当前非目标

当前这一轮明确不做：

- CLI 级 `has_fulltext` 命令
- 让 probe 结果强制等于 `fetch_paper().has_fulltext`
- provider 级 HEAD / OPTIONS 深度探测
- 大规模积极产出 `confirmed_yes` 或 `no`

## 后续可扩展方向

未来如果要增强 probe，优先方向可以是：

- 对少数 provider 增加更强但仍廉价的 metadata-level 证据
- 在不触发完整抓取的前提下，细化 `confirmed_yes`
- 明确哪些 provider 允许输出真正的 `no`
- 继续把 probe 语义和最终 fetch 语义分离，而不是混成一个接口

## 相关文档

- [`target-architecture.md`](target-architecture.md)
- [`../providers.md`](../providers.md)
- [`../../README.md`](../../README.md)
