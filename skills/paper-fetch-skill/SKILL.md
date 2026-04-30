---
name: paper-fetch-skill
description: "适用场景：通过 DOI、URL 或标题抓取一篇已知论文，或校验由可识别论文组成的引用列表。不适用于：主题综述、文献发现、或仅需要推荐的请求。"
---

# 论文抓取 Skill

当 agent 需要获取某一篇具体论文的内容或全文可用性时使用这个 skill，而不是用来处理宽泛的主题概览。

## 适用场景

- 用户提供了 `doi`、论文 `url` 或论文 `title`。
- 用户要求阅读、总结、比较、批判、翻译，或从某一篇具体论文中提取方法/结果。
- 用户提供了引用列表或参考文献列表，并询问其中哪些具体论文可读或可抓取。
- 你需要紧凑的 Markdown 或结构化元数据，以便直接放入模型上下文。

## 不适用场景

- 用户想要的是宽泛的文献综述或论文发现。
- 已验证的论文全文已经存在于当前对话或工作区中，不需要重新抓取。

## 工作流

1. 能用 MCP 工具时，优先使用 MCP 工具。
2. 在多轮会话里，重新抓取前先调用 `list_cached()` 或 `get_cached(doi)`。
3. 如果查询可能存在歧义，先调用 `resolve_paper(query | title, authors, year)`。
4. 对于参考文献列表或引用列表任务，在逐篇抓取全文前先调用 `batch_check(queries, mode, concurrency)`。
5. 当你只需要一次低成本的可读性探测时，调用 `has_fulltext(query)`。
6. 如果 provider 凭证或 Wiley / Science / PNAS 的本地运行时就绪状态会影响结果，在第一次抓取前先调用 `provider_status()`。
7. 当你需要适合 AI 使用的 Markdown、结构化文章数据或元数据时，调用 `fetch_paper(query, modes, strategy, include_refs, max_tokens, prefer_cache, download_dir)`。
8. 不要因为没有本地 PDF 或缓存文本文件，就直接下结论说“不可读”。
9. 如果无法获取全文，继续使用返回的“仅摘要”或“仅元数据”结果，并明确告诉用户当前依据的只是元数据或摘要。

## 工具说明

- `resolve_paper(query | title, authors, year)`：在抓取前先规范化 DOI、URL 或标题查询，并尽早暴露歧义。
- `summarize_paper(query, focus)` 和 `verify_citation_list(citations, mode)`：这是 MCP prompt 模板，宿主可以直接暴露出来，用于单篇论文总结和引用列表分诊。
- `fetch_paper(...)`：返回一个稳定的 JSON 载荷，顶层包含 provenance，并可选包含 `article`、`markdown` 和 `metadata` 字段。
- `fetch_paper(...)`：顶层的 `token_estimate_breakdown={abstract,body,refs}` 有助于判断是否需要收紧 `include_refs`，或用更小的数值型 `max_tokens` 重试。
- `fetch_paper(...)`：支持的 MCP 客户端还会看到 `outputSchema`；在 `fetch_paper`、`batch_check` 或 `batch_resolve` 运行期间，可能还会收到 `progress` 和结构化日志通知。
- `fetch_paper(...)`：推荐默认值是 `modes=["article", "markdown"]`、`strategy.asset_profile=null`（provider 默认值）、`strategy.allow_metadata_only_fallback=true`、`include_refs=null`、`max_tokens="full_text"` 和 `prefer_cache=false`。
- `fetch_paper(...)`：当 `max_tokens="full_text"` 时，`include_refs=null` 的行为等同于 `all`。
- `fetch_paper(...)`：当 `max_tokens` 为正整数时，`include_refs=null` 的行为等同于 `top10`。
- `fetch_paper(...)`：`prefer_cache=true` 会先把查询解析到 DOI，然后在执行完整抓取瀑布流程前，先尝试匹配本地 `FetchEnvelope` sidecar。
- `fetch_paper(...)`：当你传入 `download_dir` 时，MCP 服务器还可以在当前会话中为该隔离目录暴露有作用域的缓存资源。
- `fetch_paper(...)`、`list_cached()` 和 `get_cached()`：支持 MCP resource-list 通知的宿主，在缓存资源 URI 被新增或移除时，可能会收到 `resources/list_changed`。
- `fetch_paper(...)`：`strategy.asset_profile="body"` 或 `all` 还可能把少量关键本地图表以 `ImageContent` 形式一起返回。
- `fetch_paper(...)`：可选参数 `strategy.inline_image_budget={max_images,max_bytes_per_image,max_total_bytes}` 用于调整默认的内联图片上限：`3` 张图、每张 `2 MiB`、总计 `8 MiB`；任一结果为零都会禁用内联图片。
- `fetch_paper(...)`：当返回了 assets 时，在判断某张图缺失之前，先检查 `article.assets[*].render_state`、`download_tier`、`content_type`、`downloaded_bytes`、`width` 和 `height`。如果尺寸满足阈值，且 warnings/source trail 表明接受了 preview，那么 `preview` 级别也可能足够使用。
- `fetch_paper(...)`：`article.quality.semantic_losses.table_layout_degraded_count` 表示表格布局为 Markdown 被压平；`table_semantic_loss_count` 才是内容真正丢失的更强信号。
- `fetch_paper(...)`：在返回 Markdown 前，公式 LaTeX 会对常见出版商宏（如 `\updelta` 和 `\mspace{Nmu}`）做规范化处理。
- `fetch_paper(...)`：`science` 和 `pnas` 需要仓库本地的 FlareSolverr/浏览器运行时，但不再需要旧版本地限流环境变量。`wiley` 对 HTML 和 seeded-browser PDF/ePDF 使用同一套运行时；而 `WILEY_TDM_CLIENT_TOKEN` 则可在无需浏览器就绪的情况下启用其官方 TDM API PDF 通道。`wiley` 对外发布的公共 source 名为 `wiley_browser`；`science` 和 `pnas` 保持现有公共 source 名称不变。它们在 HTML 成功路径下支持 `asset_profile="body"` / `all` 的资源下载；PDF/ePDF 回退路径仍然只返回文本。
- `fetch_paper(...)` 和批量工具：支持的 MCP 宿主可能会取消进行中的请求；worker 在观察到取消后，会协作式停止发起后续网络请求。
- `has_fulltext(query)`：会基于解析结果、Crossref 元数据、剩余的轻量 Elsevier 元数据探测，以及落地页 HTML meta 执行一次低成本探测，而不会触发完整抓取瀑布流程。
- `has_fulltext(query)`：成功载荷格式为 `{query, doi, state, evidence, warnings}`；v1 当前只会主动返回 `likely_yes` 或 `unknown`，而 `confirmed_yes` 和 `no` 仍保留为预留状态。
- `provider_status()`：在不调用远端出版商 API 的前提下，为 `crossref`、`elsevier`、`springer`、`wiley`、`science` 和 `pnas` 返回稳定的本地诊断信息。
- `provider_status()`：provider 级别的 `status` 可能是 `ready`、`partial`、`not_configured`、`rate_limited` 或 `error`；在选择抓取路径前，请查看 `checks=[...]` 中的能力级或运行时级细节。
- `batch_resolve(queries, concurrency)` 和 `batch_check(queries, mode, concurrency)`：默认 `concurrency=1`；允许范围是 `1..8`；更高的值允许不同宿主并行，但共享传输层仍会保持同一宿主串行；每次调用最多接受 `50` 个查询。
- `batch_check(queries, mode, concurrency)`：`mode="metadata"` 会复用低成本探测并返回轻量 provenance 字段；`mode="article"` 仍会运行完整抓取路径，并报告最终的全文可用性判断。
- 只读 MCP 工具现在会暴露 `ToolAnnotations` 提示（`readOnlyHint=true`），因此支持的宿主可能会更顺滑地自动批准这些调用；`fetch_paper(...)` 仍保留可写属性，因为它可能刷新本地缓存文件。

## 参考资料

- 当你需要 provider 凭证、`download_dir` 行为说明，或 Wiley / Science / PNAS 运行时要求时，请阅读 [`references/environment.md`](references/environment.md)。
- 当 MCP 不可用，或用户明确要求 shell 命令时，请阅读 [`references/cli-fallback.md`](references/cli-fallback.md)。
- 当结果为 `ambiguous`、`no_access`、`rate_limited` 或仅返回元数据时，请阅读 [`references/failure-handling.md`](references/failure-handling.md)。
