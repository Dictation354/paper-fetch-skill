# Tool Contract

本文件承接 `SKILL.md` 中移出的工具说明。处理论文抓取时，入口流程优先；需要精确参数、默认值或返回契约时再读取本文件。

## MCP Tools

- `resolve_paper(query | title, authors, year)`: 在抓取前规范化 DOI、URL 或标题查询，并尽早暴露歧义。标题输入必须先解析出 DOI 或落地页，再交给 `fetch_paper(...)`。
- `fetch_paper(...)`: 返回稳定 JSON 载荷，顶层包含溯源信息、`token_estimate_breakdown={abstract,body,refs}`，并按需附带 `article`、`markdown`、`metadata`。
- `list_cached()` / `get_cached(doi)`: 多轮会话重新抓取前先检查缓存。
- `has_fulltext(query)`: 使用解析结果、Crossref 元数据、轻量 Elsevier 元数据探测和落地页 HTML meta 做低成本全文可用性探测，不触发完整抓取流程。
- `provider_status()`: 返回 `crossref`、`elsevier`、`springer`、`wiley`、`science`、`pnas` 的本地诊断信息，不调用远程出版商 API。
- `batch_resolve(queries, concurrency)` / `batch_check(queries, mode, concurrency)`: 默认 `concurrency=1`，允许范围 `1..8`，每次最多 `50` 个查询。
- `summarize_paper(query, focus)` / `verify_citation_list(citations, mode)`: MCP prompt 模板；支持的宿主可直接用于单篇总结和 citation list 分诊。

## Recommended Defaults

- `modes=["article", "markdown"]`
- `strategy.asset_profile=null (provider default)`
- `strategy.allow_metadata_only_fallback=true`
- `include_refs=null`
- `max_tokens="full_text"`
- `prefer_cache=false`
- `no_download=false`
- `save_markdown=false`
- `markdown_output_dir=null`
- `markdown_filename=null`

- `include_refs=null` behaves like `all` when `max_tokens="full_text"`.
- When `max_tokens` is a positive integer, `include_refs=null` behaves like `top10`.

## Fetch Notes

- `prefer_cache=true` 会先把查询解析为 DOI，再尝试命中本地匹配的 FetchEnvelope sidecar，之后才走完整抓取流程。
- `no_download=true` 会避免写入 provider 载荷、资源文件和 fetch-envelope sidecar。
- `save_markdown=true` 会把渲染后的全文 Markdown 写盘，并在成功时返回 `saved_markdown_path`。
- 传入 `download_dir` 时，MCP 服务器还能在当前会话里暴露这个隔离目录对应的缓存资源。
- 支持 MCP 资源列表通知的宿主，可能在 `fetch_paper(...)`、`list_cached()` 或 `get_cached()` 改变缓存资源 URI 时收到 `resources/list_changed`。
- `strategy.asset_profile="body"` 或 `all` 时，可能额外返回少量关键本地图像，作为 `ImageContent` 输出。
- 可选 `strategy.inline_image_budget={max_images,max_bytes_per_image,max_total_bytes}` 用于调节默认内联图像上限：`3` 张图、每张 `2 MiB`、总计 `8 MiB`；任一最终值为 `0` 都会禁用内联图像。
- 如果返回了资源，判断图片缺失前先检查 `article.assets[*].render_state`、`download_tier`、`content_type`、`downloaded_bytes`、`width` 和 `height`。
- `article.quality.semantic_losses.table_layout_degraded_count` 表示 Markdown 中表格布局被压平；`table_semantic_loss_count` 才是表格内容可能真的丢失的更强信号。
- 返回 Markdown 前，公式中的 LaTeX 会先对常见出版商宏做规范化处理，例如 `\updelta`、`\mspace{Nmu}`。

## Provider Notes

- `elsevier` 保留官方 XML 路径，并可能回退到官方 Elsevier API PDF 路径；XML 成功发布 `elsevier_xml`，PDF 回退成功发布 `elsevier_pdf`。
- `springer` 使用 provider-managed direct HTML 和 direct HTTP PDF fallback，公开 source 保持 `springer_html`。
- `wiley` 使用 repo-local FlareSolverr HTML 路径，并可在配置 `WILEY_TDM_CLIENT_TOKEN` 时启用官方 TDM API PDF 通道；公开 source 为 `wiley_browser`。
- `science` 与 `pnas` 使用 provider-managed FlareSolverr HTML 加 seeded-browser publisher PDF/ePDF repo-local workflow，并保持现有公开 source 名称。
- Wiley / Science / PNAS 在 HTML 成功路径下支持 `asset_profile="body"` / `"all"` 资源下载；PDF/ePDF 回退路径仍然只返回文本。
- Elsevier PDF fallback 和 Springer PDF fallback 在当前版本也保持 text-only。
