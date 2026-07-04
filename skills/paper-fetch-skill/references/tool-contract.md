# Tool Contract

本文件承接 `SKILL.md` 中移出的工具说明。处理论文抓取时，入口流程优先；需要精确参数、默认值或返回契约时再读取本文件。

## MCP Tools

- `resolve_paper(query | title, authors, year)`: 在抓取前规范化 DOI、URL 或标题查询，并尽早暴露歧义。标题输入必须先解析出 DOI 或落地页，再交给 `fetch_paper(...)`。
- `fetch_paper(...)`: 返回稳定 JSON 载荷，顶层包含溯源信息、`token_estimate_breakdown={abstract,body,refs}`，并按需附带 `article`、`markdown`、`metadata`；当 `save_markdown=true` 时，响应会改为紧凑结果，只保留路径、元数据和诊断字段。
- `list_cached()` / `get_cached(doi)`: 多轮会话重新抓取前先检查缓存。
- `has_fulltext(query)`: 使用解析结果、Crossref 元数据、轻量 Elsevier 元数据探测和落地页 HTML meta 做低成本全文可用性探测，不触发完整抓取流程。
- `provider_status()`: 按 runtime `provider_status_order()` 返回 provider catalog 中每个 provider 的本地诊断信息，不调用远程出版商 API。
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
- `artifact_mode="markdown-assets"`
- `save_markdown=false`
- `markdown_output_dir=null`
- `markdown_filename=null`

- `include_refs=null` behaves like `all` when `max_tokens="full_text"`.
- When `max_tokens` is a positive integer, `include_refs=null` behaves like `top10`.

## Fetch Notes

- `prefer_cache=true` 会先把查询解析为 DOI，再尝试命中本地匹配的 FetchEnvelope sidecar，之后才走完整抓取流程。
- `artifact_mode="none"` 会关闭 provider artifact 和资产落盘，但仍保留 MCP fetch-envelope sidecar/cache-index 用于 `prefer_cache`、`list_cached` 和资源暴露。
- `no_download=true` 会避免写入 provider 载荷、资源文件和 fetch-envelope sidecar。
- `save_markdown=true` 会把渲染后的全文 Markdown 写盘，并在成功时返回 `saved_markdown_path`。本轮 MCP 响应会设置 `markdown=null`、`article=null`，避免把全文正文放入上下文；仍保留 `metadata`、`quality`、`warnings`、`source_trail`、`trace` 和 `token_estimate_breakdown` 等诊断字段。
- 传入 `download_dir` 时，MCP 服务器还能在当前会话里暴露这个隔离目录对应的缓存资源。
- 支持 MCP 资源列表通知的宿主，可能在 `fetch_paper(...)`、`list_cached()` 或 `get_cached()` 改变缓存资源 URI 时收到 `resources/list_changed`。
- `strategy.asset_profile="body"` 或 `all` 时，可能额外返回少量关键本地图像，作为 `ImageContent` 输出；但 `save_markdown=true` 时不会附带 inline `ImageContent`。
- 可选 `strategy.inline_image_budget={max_images,max_bytes_per_image,max_total_bytes}` 用于调节默认内联图像上限：`3` 张图、每张 `2 MiB`、总计 `8 MiB`；任一最终值为 `0` 都会禁用内联图像。
- 如果返回了资源，判断图片缺失前先检查 `article.assets[*].render_state`、`download_tier`、`content_type`、`downloaded_bytes`、`width` 和 `height`。
- `article.quality.semantic_losses.table_layout_degraded_count` 表示 Markdown 中表格布局被压平；`table_semantic_loss_count` 才是表格内容可能真的丢失的更强信号。
- 返回 Markdown 前，公式中的 LaTeX 会先对常见出版商宏做规范化处理，例如 `\updelta`、`\mspace{Nmu}`。

## Provider Notes

- Public source/provider 映射以 runtime `SOURCE_PROVIDER_MAP` 为准；当前包含 `acs`->`acs`、`aip_html`->`aip`、`aip_pdf`->`aip`、`ams_html`->`ams`、`ams_pdf`->`ams`、`annualreviews_html`->`annualreviews`、`annualreviews_pdf`->`annualreviews`、`arxiv_html`->`arxiv`、`arxiv_pdf`->`arxiv`、`copernicus_pdf`->`copernicus`、`copernicus_xml`->`copernicus`、`crossref_meta`->`crossref`、`elsevier_pdf`->`elsevier`、`elsevier_xml`->`elsevier`、`frontiers_pdf`->`frontiers`、`frontiers_xml`->`frontiers`、`ieee_html`->`ieee`、`ieee_pdf`->`ieee`、`iop_html`->`iop`、`iop_pdf`->`iop`、`mdpi_html`->`mdpi`、`mdpi_pdf`->`mdpi`、`oxfordacademic_html`->`oxfordacademic`、`oxfordacademic_pdf`->`oxfordacademic`、`plos_pdf`->`plos`、`plos_xml`->`plos`、`pnas`->`pnas`、`royalsocietypublishing_html`->`royalsocietypublishing`、`royalsocietypublishing_pdf`->`royalsocietypublishing`、`science`->`science`、`springer_html`->`springer`、`springer_pdf`->`springer`、`wiley_browser`->`wiley`。
- `elsevier` 保留官方 XML 路径，并可能回退到官方 Elsevier API PDF 路径；XML 成功发布 `elsevier_xml`，PDF 回退成功发布 `elsevier_pdf`。
- `springer` 使用 provider-managed direct HTML 和 direct HTTP PDF fallback，公开 source 为 `springer_html` 或 `springer_pdf`。
- `wiley` 使用 CDP browser HTML 路径，并可在配置 `WILEY_TDM_CLIENT_TOKEN` 时启用官方 TDM API PDF 通道；公开 source 为 `wiley_browser`。
- `science` 与 `pnas` 使用 provider-managed CDP browser HTML 加 CDP browser-seeded publisher PDF/ePDF workflow，并保持现有公开 source 名称。
- `ams` 使用 provider-managed direct HTTP HTML 加 direct HTTP PDF fallback；HTML 成功公开 `ams_html`，PDF fallback 成功公开 `ams_pdf`，不使用 CDP browser auth/preflight 或 seeded-browser PDF fallback。
- `annualreviews` 使用 provider-managed CDP browser HTML 加 CDP browser-seeded PDF fallback；HTML 成功公开 `annualreviews_html`，PDF fallback 成功公开 `annualreviews_pdf`。
- `royalsocietypublishing` 使用 provider-managed CDP browser DOI HTML 加 CDP browser-seeded PDF fallback；HTML 成功公开 `royalsocietypublishing_html`，PDF fallback 成功公开 `royalsocietypublishing_pdf`，`citation_xml_url` 不作为 XML/JATS 路线。
- `plos` 使用 public JATS XML 加 direct HTTP PDF fallback；XML 成功公开 `plos_xml`，PDF fallback 成功公开 `plos_pdf`。
- `frontiers` 从 landing HTML 发现 canonical Frontiers article route，再使用 public JATS XML 加 direct HTTP PDF fallback；XML 成功公开 `frontiers_xml`，PDF fallback 成功公开 `frontiers_pdf`。
- `oxfordacademic` 使用 direct HTTP article HTML 加 direct HTTP PDF fallback；HTML 成功公开 `oxfordacademic_html`，PDF fallback 成功公开 `oxfordacademic_pdf`。
- `acs` 使用 provider-managed CDP browser HTML 加 CDP browser-seeded publisher PDF/ePDF fallback；成功公开 `acs`。
- `iop` 使用 provider-managed CDP browser article HTML 加 CDP browser-seeded IOP PDF fallback；HTML 成功公开 `iop_html`，PDF fallback 成功公开 `iop_pdf`，Radware/hCaptcha challenge 页面必须 fail closed。
- `aip` 使用 provider-managed CDP browser AIP article HTML 加 CDP browser-seeded AIP PDF fallback；HTML 成功公开 `aip_html`，PDF fallback 成功公开 `aip_pdf`。
- `mdpi` 使用 provider-managed CDP browser HTML 加 CDP browser-seeded article PDF fallback；HTML 成功公开 `mdpi_html`，PDF fallback 成功公开 `mdpi_pdf`。
- `ieee` 使用 landing metadata / article number、Xplore dynamic HTML endpoint、direct HTTP PDF fallback 和 seeded-browser PDF fallback；HTML 成功公开 `ieee_html`，PDF fallback 成功公开 `ieee_pdf`，非 PDF wrapper/access/challenge 页面必须 fail closed 到 abstract-only / metadata-only。
- Wiley / Science / PNAS / Annual Reviews / Royal Society Publishing / ACS / IOP / AIP / MDPI 在 browser HTML 成功路径下支持 `asset_profile="body"` / `"all"` 资源下载；AMS direct HTTP HTML 成功路径也支持正文资产下载，但不进入 browser workflow。
- PDF/ePDF fallback 的正文 Markdown 来自共享 PDF 转换；`asset_profile="body"` / `"all"` 且 artifact saving 启用时，会保存 PDF 导出的正文图片。
