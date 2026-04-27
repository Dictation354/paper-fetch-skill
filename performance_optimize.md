# Paper Fetch 链路性能优化清单

按"潜在收益 × 改造成本"由高到低排列，所有结论基于当前源码（非历史断言）。

## 已落地状态（2026-04-27）

本轮已完成第一阶段性能改造，并修正原清单里的几个过度假设：

- 公式转换现在有线程安全 LRU，key 覆盖 backend、原始 MathML、display mode、关键 converter env 与脚本候选路径。
- `mathml-to-latex` 新增 JSONL 常驻 Node worker（`scripts/mathml_to_latex_worker.mjs` 与打包资源各一份），worker 失败会回退到原单次 CLI。
- `texmath` 只做路径解析缓存与结果缓存；没有假设它支持可靠流式常驻协议。
- `HttpTransport` 已改为可配置 `PoolManager(num_pools, maxsize, block=True)`，并用 per-host bounded semaphore 替代单锁。默认同 host 并发是 4，可由 env 下调。
- textual GET 可选磁盘缓存已加入，支持 ETag / Last-Modified 条件请求；`RuntimeContext(download_dir=...)` 会默认把缓存放在下载目录的 `.paper-fetch-http-cache/`。
- metadata/probe 阶段只并发不依赖 Crossref routing metadata 的 official probe；Crossref 返回后再补依赖 publisher/landing metadata 的候选，并保持 `source_trail` 的确定性顺序。
- MCP fetch 与 batch 路径会复用 `RuntimeContext`、transport、clients 和 env；service 调用仍保留 legacy keyword 兼容。
- Elsevier body asset 下载已改为网络并发、文件写入按原引用顺序串行。
- Provider fulltext / asset / article conversion 链路会显式传递同一个 `RuntimeContext`，并通过 `RuntimeContext.parse_cache` 复用单次 fetch 内的 XML/HTML 派生结果。
- Elsevier XML root 已在 asset 抽取与 article 渲染之间复用；`build_article_structure` 可直接消费已解析 root。
- 通用 `download_figure_assets` 与 supplementary 下载已拆成“并行解析网络响应”和“按原 asset 顺序串行写文件”两阶段，默认 worker 上限为 4。
- Springer HTML extraction、Wiley/Science/PNAS browser-workflow Markdown extraction 与 HTML asset extraction 已接入 RuntimeContext 级 memo。
- 生产代码中的 BeautifulSoup parser 选择已统一到 `paper_fetch.extraction.html.parsing.choose_parser()`。
- `_provider_fetch_result` 的 `inspect.signature` 判断已按 provider 类型缓存。
- `scripts/benchmark_formula_converters.py` 现在输出 `cold_start`、`cache_hit`，以及 `mathml-to-latex` 的 `worker` 路径对比。
- PNAS HTML 主链路新增 direct Playwright preflight：`domcontentloaded` 后直接抽取，阻断 image/font/stylesheet/media；成功时标记 `html_fetcher=playwright_direct` 并跳过 FlareSolverr，失败时保持原 FlareSolverr/PDF 回退语义。
- FlareSolverr HTML 请求默认不再要求 `returnScreenshot`；challenge/failure 时仍保留 HTML 与 response JSON 诊断，图片恢复链路继续只依赖 `solution.imagePayload`。

仍未完成：

- `probe/fulltext` 层的 PDF 候选预取尚未做；XML/HTML route 与 PDF fallback 仍保持 waterfall 串行语义。
- `texmath` 常驻 worker 尚未启用，仍需可靠协议探测和 benchmark 证明。
- Science 仍稳定依赖 FlareSolverr HTML；是否能低于 30s 需要以 live 连跑结果为准，不应通过强制 30s timeout 牺牲成功率。

## 1. 公式转换：最大的可见瓶颈

`src/paper_fetch/formula/convert.py:234` 的 `_run_command` 对每一个 MathML 元素调用 `subprocess.run`，texmath/node 都被反复拉起。`_article_markdown_math.render_external_mathml_expression` 在 Elsevier、Springer、Wiley、Science/PNAS 四条 Markdown 链路上都被逐元素调用（如 `_article_markdown_common.py:104`、`_html_section_markdown.py:292`、`_science_pnas_html.py:755`）。一篇含 40 条公式的文章会触发 40 次 fork+exec+Haskell/Node 冷启动。

优化方向与当前实现：

- **批处理**：暂未落地。原文“texmath 支持多输入”未在本机和当前代码中验证，不能作为默认路径。
- **常驻 worker**：已对 `mathml-to-latex` 落地 JSONL worker；`texmath` 暂不常驻。
- **结果缓存**：已落地线程安全 LRU，包含 converter 配置 fingerprint。
- **环境复制**：暂保留原实现，后续只在 benchmark 证明有明显收益时再改。

## 2. 工作流层的串行 RPC

`workflow/metadata.py:117–151` 先 Crossref，然后逐个 `probe_official_provider`，最后 `landing_page` 探测，全部串行；`workflow/routing.probe_has_fulltext` 同模式。这些 HTTP 请求互不依赖。

优化方向：

- 并发跑 Crossref + 不依赖 Crossref metadata 即可确定的 official provider probe；Crossref 返回后再补依赖 publisher/landing metadata 的候选。当前实现保持 `source_trail` 顺序，不做“第一个 positive 立即取消其余”的语义变化。
- 对 `_try_official_provider` 内的 PDF/XML waterfall 也可考虑预取 PDF 候选，让其与 XML 解析重叠。

## 3. HTTP 层连接池 & 缓存配置

- `HttpTransport` 已支持 `pool_num_pools`、`pool_maxsize`、`per_host_concurrency`、`disk_cache_dir`、`metadata_cache_ttl`。注意：原先同 host 串行化不只来自 PoolManager `maxsize=1`，还来自 transport 自己的 per-host lock；现在两层都已改为有界并发。
- 缓存仅 in-memory，`DEFAULT_CACHE_TTL_SECONDS=30`。批量回归 / 重复测同一 DOI 的场景下，每次都会重新打 Crossref。可加：
  - 磁盘层缓存（复用已有 `.paper-fetch/` / `.paper-fetch-runs/`），按 `If-None-Match`/`Last-Modified` 走条件请求。
  - 对纯元数据响应放宽 TTL（Crossref 元数据变化极慢）。

## 4. 资源下载并行化的盲区

当前实现已把 Elsevier body object references、通用 `download_figure_assets`、通用 supplementary 下载和 Playwright image-document fetcher 的网络解析阶段放入 bounded worker pool。文件写入、文件名去重和最终结果组装仍按原 asset 顺序串行执行，避免改变可观察输出顺序。单个 asset 内仍按候选 URL 顺序尝试，不并发抢 winner。

## 5. HTML/XML 解析重复与解析器选择

- 多处仍硬编码 `BeautifulSoup(html_text, "html.parser")`：`_html_references.py:88,136`、`_pdf_candidates.py:97`、`_flaresolverr.py:890` 的若干分支。`html.parser` 比 `lxml` 慢 3–10×，且代码已有 `choose_parser()`。统一替换为 `choose_parser()`。
- Elsevier 全文 XML root 已缓存到单次 `RuntimeContext`，asset extraction 和 article structure 渲染共享同一个只读 `Element`。
- Springer HTML extraction payload、Wiley/Science/PNAS browser-workflow Markdown extraction、HTML scoped asset extraction 已接入 `RuntimeContext.parse_cache`。缓存保存派生 dict/list 时返回拷贝，不共享可变 soup。

## 6. 微观热点

- `_provider_fetch_result`（`workflow/fulltext.py:113`）每次 `inspect.signature(fetch_result).parameters` 拉一次 introspection。按 provider 类缓存"是否接受 `artifact_store`"的判断。
- `models.py` 渲染 markdown 时用了约 20 处字面量 `re.sub(...)`；Python 内建 re 缓存 512 项虽够用，但循环内的可预编译为模块级常量，避免反复哈希查表（也提升可读性）。
- `subprocess_env` 中 `dict(os.environ)` 每次拷贝整个环境（50–200 项）；公式频繁调用时是百 KB 级 churn。

## 优先级建议

1. **公式 worker 化（含 LRU）** — 单点改造覆盖所有 provider，预计单篇含公式文章端到端时延降低 50–80%。
2. **元数据 / probe 并发** — 一次 `fetch_paper` 节省 1–2 个 RTT；batch 场景线性放大收益。
3. **PoolManager + 资产并行** — 图多的文章时延减半，与 #2 叠加。
4. **缓存与解析器统一** — 投入低、回归风险小。

## 下一步建议

继续优先做剩余的低风险项：PDF fallback 候选预取、更多 parser 选择统一检查，以及端到端 live 性能记录自动化。`texmath` 常驻只应在有可靠流式协议探测和 benchmark 结果后再启用。
