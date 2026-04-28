# Paper Fetch 链路性能优化清单

按"潜在收益 × 改造成本"由高到低排列，所有结论基于当前源码（非历史断言）。

## 已落地状态（2026-04-28）

第一阶段已落地：

- 公式转换线程安全 LRU，key 覆盖 backend、原始 MathML、display mode、关键 converter env 与脚本候选路径。
- `mathml-to-latex` 新增 JSONL 常驻 Node worker；worker 失败回退到原单次 CLI。
- `texmath` 只做路径解析缓存与结果缓存。
- `HttpTransport` 改为可配置 `PoolManager(num_pools, maxsize, block=True)`，并用 per-host bounded semaphore 替代单锁。
- textual GET 可选磁盘缓存已加入，支持 ETag / Last-Modified 条件请求；`RuntimeContext(download_dir=...)` 默认把缓存放在 `.paper-fetch-http-cache/`。
- metadata disk cache 默认 freshness 已提升到 1 day；普通进程内 GET TTL 仍是 30s，`PAPER_FETCH_HTTP_METADATA_CACHE_TTL` 可覆盖。
- metadata/probe 阶段已并发 Crossref + 不依赖 routing metadata 的 official probe，并保持 `source_trail` 顺序。
- MCP fetch 与 batch 路径复用 `RuntimeContext`、transport、clients、env。
- Elsevier body asset 下载改为网络并发、文件写入按引用顺序串行。
- Provider fulltext / asset / article conversion 链路显式传递同一 `RuntimeContext`，并通过 `RuntimeContext.parse_cache` 复用单次 fetch 内的 XML/HTML 派生结果。
- 同一 `RuntimeContext` 内新增 `session_cache`，复用 `has_fulltext` → `fetch_paper` 之间的 query resolution、Crossref metadata、Elsevier probe metadata 和 landing `citation_pdf_url` probe。
- Elsevier XML root 已在 asset 抽取与 article 渲染之间复用。
- 通用 `download_figure_assets` 与 supplementary 下载拆成"并行解析网络响应 + 串行落盘"两阶段，默认 worker 上限 4。
- Springer HTML extraction、Wiley/Science/PNAS browser-workflow Markdown extraction、HTML asset extraction 已接入 `RuntimeContext.parse_cache`。
- 生产代码 BeautifulSoup parser 选择已统一到 `choose_parser()`。
- `_provider_fetch_result` 的 `inspect.signature` 判断已按 provider 类型缓存。
- `scripts/benchmark_formula_converters.py` 输出 `cold_start`、`cache_hit` 与 `worker` 路径对比。
- PNAS HTML 主链路新增 direct Playwright preflight；成功标记 `html_fetcher=playwright_direct`，失败保持 FlareSolverr/PDF 回退。
- Wiley/Science/PNAS FlareSolverr HTML 首轮 fast path（`waitInSeconds=0` + `disableMedia=true`）；challenge 或抽取不足时回退保守等待。
- FlareSolverr HTML 请求默认不再要求 `returnScreenshot`；图片恢复链路只依赖 `solution.imagePayload`。

第二阶段本轮已落地：

- `RuntimeContext` 新增 lazy Playwright manager / Chromium browser 复用；PNAS direct HTML preflight、browser workflow 图片/文件 fetcher、PDF fallback 都可通过同一 runtime 复用 browser，并继续按阶段创建独立 context/page。
- `_SharedPlaywrightImageDocumentFetcher` 与 `_SharedPlaywrightFileDocumentFetcher` 的 Playwright lazy context 创建已合并到共享 helper；无 `RuntimeContext` 的旧调用仍保留本地 manager/browser close 兼容路径。
- direct Playwright HTML preflight 仅保留给 PNAS；Wiley/Science 不启用该快速路径，继续从 FlareSolverr HTML 开始，避免低成功率 preflight 增加固定开销。
- `HttpTransport.cache_stats_snapshot()` 已提供线程安全计数快照，覆盖 `memory_hit`、`disk_fresh_hit`、`disk_stale_revalidate`、`disk_304_refresh`、`miss`、`store`、`bypass`。
- golden criteria live review 结果新增 `stage_timings`，包含 `fetch_seconds`、`materialize_seconds`、`total_seconds` 以及 `resolve_seconds`、`metadata_seconds`、`fulltext_seconds`、`asset_seconds`、`formula_seconds`、`render_seconds`；`elapsed_seconds` 保留兼容，报告 JSON、Markdown 表格和结构化日志均输出关键耗时。每条 sample 记录 HTTP cache delta，最终汇总日志保留累计 cache 统计。
- `_science_pnas_postprocess.py` 的重复 regex 编译已提升为模块级常量，Wiley abbreviations 移动逻辑复用同一次 heading 扫描结果。
- `models.py`、`_science_pnas_html.py`、`_html_section_markdown.py` 中本轮命中的重复 Markdown/heading cleanup regex 已提升为模块级常量。
- `formula/convert.py::subprocess_env` 在无 overrides 时不再拷贝整份 `os.environ`。
- HTML figure、supplementary、shared image-document fetcher 和 Elsevier body asset 下载的 worker 上限由 `PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY` 控制，默认仍是 4。

仍未完成（来自旧清单）：

- `probe/fulltext` 层的 PDF 候选预取尚未做；XML/HTML route 与 PDF fallback 仍保持 waterfall 串行语义。
- `texmath` 常驻 worker 尚未启用，仍需可靠协议探测和 benchmark 证明。

---

## 第二阶段待办（按优先级）

### 1. 共享 Playwright manager / browser（最大隐性损耗）

状态：已落地。当前实现把 Playwright manager / browser 挂到 `RuntimeContext`，按需 lazy launch；PNAS direct HTML preflight、图片/文件 fetcher 与 PDF fallback 复用 runtime browser，但每个阶段仍新建隔离 context/page。

兼容性：旧调用不传 `RuntimeContext` 时仍自行启动并关闭 Playwright；传入 runtime 时由 `RuntimeContext.close_playwright()` / `close()` 统一关闭 browser。

### 2. direct Playwright preflight 仅保留 PNAS

状态：已落地并按运行策略收窄。只有 PNAS 会先尝试 direct Playwright HTML preflight；该路径只作为快速成功路径，失败时不改变原 FlareSolverr / seeded-browser PDF/ePDF fallback 语义。Wiley 与 Science 继续从 FlareSolverr HTML 开始。

### 3. probe → fetch 元数据复用

MCP 调用通常先 `has_fulltext` 再 `fetch_paper`，两者会重复打 Crossref + Elsevier metadata + landing page citation_pdf probe（`workflow/routing.py:200-227`）。当前 `RuntimeContext.parse_cache` 是 per-fetch 字典，跨调用不复用。

状态：已落地。`RuntimeContext.session_cache` 现在复用 query resolution、Crossref DOI metadata、Elsevier provider metadata probe 和 landing page `citation_pdf_url` probe；landing probe 命中时，fetch 阶段会把 citation PDF URL 合并到 metadata `fulltext_links`，不额外请求 landing page。

### 4. Crossref 元数据 TTL 提升 + disk cache 覆盖面扩展

`http.py:33` 的 `DEFAULT_CACHE_TTL_SECONDS = 30` 对 Crossref 这种近乎不可变的元数据太保守。批量场景或反复调试同一 DOI 时，每 30 秒就会重新打 Crossref。

状态：已落地。`RuntimeContext` 构建的 transport 默认 `metadata_cache_ttl=86400`，`PAPER_FETCH_HTTP_METADATA_CACHE_TTL=0/30/...` 可覆盖；cache key 继续 redact `mailto`，并支持 `application/*+json` 与 Crossref content-negotiation 常见 XML/JSON 类型入 textual disk cache。

### 5. 可观测性：cache 命中率 + 分阶段耗时

状态：已落地。`HttpTransport` 已有 cache 计数快照，golden criteria live review 已输出样本级阶段耗时与 cache delta；`fetch_seconds` 已细分为 resolve / metadata / fulltext / asset / formula / render。

后续可继续细化：

- 按 provider 聚合 cache delta 与阶段耗时，用于 live A/B 对比。

### 6. 清洗链路里的 regex 与节点扫描重复

状态：已部分落地。`_science_pnas_postprocess.py` 的 citation italic、equation block、heading tag 等 regex 已模块级化；`move_wiley_abbreviations_to_end` 在单次调用内复用 heading 列表，避免重复扫描同一 container。`models.py`、`_science_pnas_html.py`、`_html_section_markdown.py` 中本轮命中的重复 `re.sub` / heading regex 也已收敛为模块级常量。

### 7. PDF fallback 候选预取（旧清单遗留）

`_try_official_provider` 内的 PDF/XML waterfall 仍是串行：XML/HTML route 失败才开始 PDF fallback。

优化方向：

- XML/HTML 解析在飞时，并发触发 PDF 候选的 HEAD / first-byte probe，让 fallback 决策路径已经"热"。
- 先在 Elsevier 一家上做（PDF 候选语义最稳定），有 live 数据后再推广。

### 8. Asset worker 上限可调

`extraction/html/_assets.py:1337,1624,1741` 与 `providers/elsevier.py:352` 都硬写 `min(4, len(...))`。`HTTP_PER_HOST_CONCURRENCY_ENV_VAR` 已是可调的；同样思路加 `ASSET_DOWNLOAD_CONCURRENCY_ENV_VAR`，对图表多的 Wiley/Science 文章把上限提到 6–8 是免费的速度（前提是 publisher 不限速）。

状态：已落地。新增 `PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY`，默认 `4`、最小 `1`；HTML figure、supplementary、shared image-document fetcher、Elsevier body object reference 下载都会读取该上限，直接调用 helper 时也可用可选参数覆盖。

### 9. Wiley waterfall 并行化

`wiley.py` 顺序是 FlareSolverr HTML → seeded-browser PDF/ePDF → TDM API PDF。FlareSolverr 冷启时这一段稳定 30s+。

优化方向：

- 当配置了 `WILEY_TDM_CLIENT_TOKEN` 时，TDM API PDF 可与 FlareSolverr 并行启动（赢者取，输者 cancel）。
- 代价是失败路径上多一次 TDM 调用，需要 A/B 测端到端时延的改善是否值得 TDM 配额。

### 10. 写入路径上 ArtifactStore 的二次重建

状态：已落地。`_try_official_provider` 成功路径使用传入的 `artifact_store` 保存 provider payload、HTML payload 与 provider artifacts；`RuntimeContext` 初始化时负责创建/携带 `artifact_store`。

### 11. `subprocess_env` 与 texmath 常驻 worker（旧清单遗留）

`formula/convert.py:301-304` 的 `subprocess_env` 每次调用都 `dict(os.environ)`（80–200 项）。当前已有 LRU 兜底，但 worker 不可用、texmath 走 CLI、或 LRU miss 时仍会触发。

状态：短期优化已落地，`subprocess_env` 在无 overrides 时直接返回 `os.environ`，避免无意义拷贝。

剩余：texmath 常驻 worker 仍需可靠协议探测 + benchmark；只在能证明显著收益后启用。

### 12. `_ensure_page` 重复实现合并

状态：已落地。图片 fetcher 与文件 fetcher 现在通过同一个 `RuntimeContext`-aware helper 创建 Playwright context。

---

## 优先级建议

1. **PDF fallback 候选预取评估**（#7）— 只作为后续待验证项，本轮不改 waterfall 运行语义。
2. **Wiley waterfall 并行化**（#9）— 从当前清单执行范围排除；需要单独 live A/B 和配额评估后再决定。
3. **剩余 regex 模块级化与 texmath 常驻 worker**（#6 后续, #11 后续）— 低风险打扫与中风险 worker 化分开推进。

## 下一步建议

下一步先用现有 live review 阶段耗时与 sample cache delta 做基线；PDF fallback 预取和 Wiley waterfall 并行化只保留为后续独立验证项，不在当前优化批次改变运行语义。
