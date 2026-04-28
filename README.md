# Paper Fetch Skill

`paper-fetch-skill` 是一个面向“已知论文”的抓取工具：输入 DOI、论文落地页 URL 或标题，把论文解析成更适合 AI 消费的结构化元数据、正文 Markdown，以及可选的本地缓存资源。

它不是文献发现、选题推荐或综述生成系统。它解决的是“我已经知道要看哪篇论文，怎样稳定地拿到可读正文和出处信息”。

## 这份首页解决什么，不解决什么

这份首页解决：

- 项目定位和边界
- 核心能力总览
- 当前业务主流程
- 5 分钟上手
- 关键默认值与限制
- 文档导航

这份首页不展开：

- 各 provider 的全部配置细节
- Wiley / Science / PNAS 的运维步骤
- 架构演进背景和探针语义细节

这些内容分别在 [`docs/providers.md`](docs/providers.md)、[`docs/flaresolverr.md`](docs/flaresolverr.md)、[`docs/architecture/target-architecture.md`](docs/architecture/target-architecture.md) 和 [`docs/architecture/probe-semantics.md`](docs/architecture/probe-semantics.md) 中定义。

## 项目提供什么

- `paper-fetch`
  - 命令行抓取入口，适合人工试跑、CI smoke 和本地调试。
- `paper-fetch-mcp`
  - 给 Codex、Claude Code 等 runtime 使用的 stdio MCP server。
- `skills/paper-fetch-skill/`
  - 静态 thin skill，负责教 agent 何时调用 MCP，而不是承载抓取逻辑。
- `provider_status()`
  - 在真正抓取前做本地可用性预检。
- `has_fulltext()`
  - 便宜的全文可用性 probe，不触发完整抓取瀑布。
- `batch_resolve()` / `batch_check()`
  - 适合 citation list 批量甄别与预处理。
- MCP cache resources
  - 暴露共享缓存索引和缓存条目，方便 host 读取已落地结果。

## 业务主流程

当前核心业务逻辑统一走下面这条主线：

```text
输入解析
-> resolve 查询类型（DOI / URL / 标题）
-> 生成 provider_hint 与候选 DOI
-> 用 Crossref / provider metadata 建立路由信号
-> 合并元数据
-> 尝试 provider 全文主链
-> 失败时降级为 abstract-only 或 metadata-only
-> 输出 FetchEnvelope / Markdown / 本地缓存 / MCP 结果
```

更具体一点：

1. `resolve_paper()` 先把原始输入解析成 `ResolvedQuery`。
2. 路由优先级固定是 `domain > publisher > DOI fallback`。
3. `crossref` 既可能是公开来源 `source="crossref_meta"`，也可能只是内部 routing signal。
4. `elsevier` 固定走 `官方 XML/API -> 官方 API PDF fallback -> metadata-only`。
5. `springer` 固定走 `direct HTML -> direct HTTP PDF -> abstract-only / metadata-only`。
6. `pnas` 先尝试 `direct Playwright HTML preflight`，失败后继续 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> abstract-only / metadata-only`；`wiley` 从 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> Wiley TDM API PDF -> abstract-only / metadata-only` 开始，`science` 从 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> abstract-only / metadata-only` 开始。
7. 未命中这五家 provider 的 URL / landing page 不再尝试通用 HTML 正文提取，只会继续做 DOI / Crossref metadata 解析，并在允许时返回 metadata-only。
8. 最终统一输出 `FetchEnvelope`，其中会显式给出：
   - `source`
   - `has_fulltext`
   - `warnings`
   - `source_trail`
   - `token_estimate_breakdown`

## 5 分钟上手

安装当前仓库：

```bash
python3 -m pip install .
```

最小试跑：

```bash
paper-fetch --query "10.1186/1471-2105-11-421"
```

如果需要 API key、下载目录或自定义环境变量，默认配置文件位置是：

```text
~/.config/paper-fetch/.env
```

可以先准备目录：

```bash
mkdir -p ~/.config/paper-fetch
cp .env.example ~/.config/paper-fetch/.env
```

变量说明见 [`docs/providers.md`](docs/providers.md)。

如果你要接入 MCP server：

```bash
paper-fetch-mcp
```

或：

```bash
python3 -m paper_fetch.mcp.server
```

如果你在 WSL 里把它挂到 Codex，优先用仓库自带的启动包装脚本：

```bash
./scripts/run-codex-paper-fetch-mcp.sh
```

这个脚本会优先选择 `vendor/flaresolverr/.env.flaresolverr-source-wslg`，并在拿不到 WSLg 图形环境时回退到 headless preset。

如果要把 skill 和 MCP 注册到常见 agent runtime，直接看 [`docs/deployment.md`](docs/deployment.md)。

## 默认值与关键限制

这些是最值得先记住的默认行为：

- `asset_profile=null (provider default)`
  - 默认不显式指定资产策略，由 provider/source 决定。
  - 目前 `springer` / `wiley` / `science` / `pnas` 的 HTML 成功路径默认等价于 `body`；其余默认等价于 `none`。
  - `article.assets[*]` 会保留下载诊断字段，例如 `render_state`、`download_tier`、`download_url`、`content_type`、`downloaded_bytes`、`width`、`height`。
  - 正文已经内联消费过的 figure / table / formula image 会标记为 `render_state="inline"`，不会再在文末重复追加。
  - `body` 现在明确表示：只下载 provider-cleaned 正文 fragment 中的 figure / table image / formula image 资产，不扫整页 raw HTML。
  - `all` 会在 `body` 基础上额外下载 supplementary 文件附件；supplementary 走独立文件下载链路，不参与 MCP inline `ImageContent`，代码层不额外设置单文件或总大小上限。
- `max_tokens="full_text"`
  - 默认尽量返回完整 abstract、正文和 references。
- `include_refs=null`
  - 在 `full_text` 模式下等价于全量 references。
  - 在数值 token budget 模式下默认等价于 `top10`。
- `fetch_paper()` 的 MCP 默认 `modes=["article", "markdown"]`
  - 同时返回结构化结果和 AI 直接可读的 Markdown。
  - `strategy` 可包含 `allow_metadata_only_fallback`、`preferred_providers`、`asset_profile`，以及 MCP-only 的 `inline_image_budget`。
  - 当 `asset_profile` 实际为 `body` 或 `all` 时，MCP 可能额外返回少量 `ImageContent`；默认上限为 `3` 张、单张 `2 MiB`、总计 `8 MiB`，任一上限为 `0` 时禁用。
- `has_fulltext()`
  - 是廉价 probe，不等同于最终 `fetch_paper().has_fulltext`。
- `wiley` / `science` / `pnas`
  - `science` / `pnas` 依赖仓库 checkout + `vendor/flaresolverr/` 工作流。
  - `wiley` 的 HTML 与 seeded-browser PDF/ePDF 路径也依赖这套工作流；配置 `WILEY_TDM_CLIENT_TOKEN` 后，官方 TDM API PDF lane 会在 browser PDF/ePDF fallback 失败或本地浏览器运行时不可用时继续尝试。
  - 仅 `pnas` 正文 HTML 会先尝试 direct Playwright preflight；成功时标记 `html_fetcher="playwright_direct"` 并跳过 FlareSolverr，失败时保持原 FlareSolverr / PDF 回退语义。`wiley` / `science` 从 FlareSolverr HTML 开始。
  - `FlareSolverr HTML` 成功路径支持 `asset_profile=body|all`；正文 figure / table / formula 图片会复用同一个 seeded Playwright browser context 下载，supplementary 文件只在 `all` 下单独下载。
  - 正文 HTML 首轮 FlareSolverr 请求会用 `waitInSeconds=0` + `disableMedia=true` 快速路径；challenge、访问拦截、摘要页或正文抽取不足时自动用原保守等待策略重试，图片恢复和 figure-page 发现不禁用媒体资源。
  - 候选顺序仍优先 full-size/original，full-size 全部失败后才回退 preview；preview 也通过同一个 browser context 获取，目标 provider 不再输出 `download_tier="playwright_canvas_fallback"`。
  - 正文图片下载会在单次 download attempt 内做有限并行和 URL 级缓存：重复的 figure page / 图片候选只抓一次，最终仍按输入资产顺序稳定落盘。
  - 如果浏览器页面已经显示目标图片，但页面内 `fetch()` 被 Cloudflare challenge 返回 HTML 拦截，下载器只接受 FlareSolverr/Selenium 返回的 `solution.imagePayload` 作为浏览器像素恢复结果；不再回退 FlareSolverr 图片文档截图裁剪，并继续按原候选记录为 `full_size` 或 `preview`。
  - supplementary 文件如果先拿到 challenge/login HTML，会先记录诊断，再用 FlareSolverr 刷新 article/附件 seed，随后通过 Playwright context request 重试；成功时记录 `download_tier="supplementary_file"`。
  - `PDF/ePDF fallback` 仍是 text-only，不阻塞正文成功。
- 公式 Markdown
  - MathML 转 LaTeX 和 Springer/Nature raw MathJax TeX 都会经过轻量 normalize。
  - HTML 中无法转换成 LaTeX 的公式图片 fallback 会保留为 `![Formula](...)`，下载成功后会像 figure/table 一样改写成本地路径。
  - 目前会把 `\updelta` 这类 upright Greek 宏改成 KaTeX 常用宏，并把 `\mspace{Nmu}` 改成 KaTeX 可解析的 `\mkernNmu`。
- Markdown 清洗
  - 已下载资产会在文章组装阶段改写远程图片链接，之后再做节解析和图片块边界归一化，避免标题、正文、公式和 `![...]` 粘连。
  - 结构化 metadata 会在 front matter 中解开 HTML entity，例如 `&amp;` 会渲染成 `&`。
- abstract-only / metadata-only 降级
  - 默认允许。正文不可用时，系统会返回 provider 摘要级结果或 metadata + abstract，并显式带 warning。

## 支持的 provider 概览

当前公开 provider 包括：

- `crossref`
- `elsevier`
- `springer`
- `wiley`
- `science`
- `pnas`

其中：

- `elsevier` 保留官方 API/XML 主链，并在 XML 不可用时直接走官方 API PDF fallback；XML 成功时公开为 `elsevier_xml`，PDF fallback 成功时公开为 `elsevier_pdf`。
- `springer` 使用 provider 自管 `direct HTML -> direct HTTP PDF` 主链，公开来源统一为 `springer_html`。
- `pnas` 先尝试 direct Playwright HTML preflight；`wiley` / `science` 从 repo-local FlareSolverr HTML 开始。三者后续都可继续使用 Playwright seeded-browser publisher PDF/ePDF 工作流，`wiley` 还可在后续 fallback 中使用 Wiley TDM API PDF。
- `wiley` 公开来源为 `wiley_browser`；`science`、`pnas` 继续保持原有 public source。
- `crossref` 负责 metadata、题名检索、路由信号和 metadata-only 结果，不承担 publisher fulltext。

完整能力矩阵、环境变量、缓存和限速说明见 [`docs/providers.md`](docs/providers.md)。

## MCP Surface

当前 MCP server 公开这些工具：

- `resolve_paper(query | title, authors, year)`
- `has_fulltext(query)`
- `fetch_paper(query, modes, strategy, include_refs, max_tokens, prefer_cache, download_dir)`；`strategy` 支持 `allow_metadata_only_fallback`、`preferred_providers`、`asset_profile` 和 `inline_image_budget`
- `provider_status()`
- `list_cached(download_dir)`
- `get_cached(doi, download_dir)`
- `batch_resolve(queries, concurrency)`
- `batch_check(queries, mode, concurrency)`，其中 `mode` 为 `metadata` 或 `article`

`download_dir` 相关 provider artifact 落盘由 `RuntimeContext` / `ArtifactStore` 管理；`prefer_cache=true` 的 fetch-envelope sidecar 复用与 scoped cache resources 由 `FetchCache` 管理，外部参数和 resource URI 保持稳定。

同一个 `RuntimeContext` 生命周期内会复用 session 级浅缓存：`has_fulltext` 与后续 `fetch_paper` 可共享 query resolution、Crossref DOI metadata、Elsevier metadata probe，以及 landing page `citation_pdf_url` probe；命中的 citation PDF URL 会并入 fetch 阶段 metadata `fulltext_links`。

HTTP textual disk cache 的 metadata freshness 默认 `86400` 秒；`PAPER_FETCH_HTTP_METADATA_CACHE_TTL` 可覆盖，普通进程内 GET TTL 仍默认 `30` 秒。

golden criteria live review 的 `stage_timings` 会保留 `fetch_seconds`、`materialize_seconds`、`total_seconds`、`resolve_seconds`、`metadata_seconds`、`fulltext_seconds`、`asset_seconds`、`formula_seconds`、`render_seconds`；每个 sample 的 `http_cache_stats` 是该 sample 的 cache delta。

批量工具每次最多接收 `50` 条 query，`concurrency` 默认 `1`，允许范围是 `1..8`。

还提供两个 prompt 模板：

- `summarize_paper(query, focus="general")`
- `verify_citation_list(citations, mode="metadata")`

MCP 细节和部署入口见 [`docs/deployment.md`](docs/deployment.md)。

## 常用 CLI 示例

默认抓取：

```bash
paper-fetch --query "10.1186/1471-2105-11-421"
```

抓正文图、正文表格原图和可识别的公式图片：

```bash
paper-fetch --query "10.1016/j.rse.2025.114648" --asset-profile body
```

抓全部已识别资产：

```bash
paper-fetch --query "10.1016/j.rse.2025.114648" --asset-profile all
```

改成数值 token 上限：

```bash
paper-fetch --query "10.1016/j.rse.2025.114648" --max-tokens 12000
```

只拿结果、不落本地文件：

```bash
paper-fetch --query "10.1016/j.rse.2025.114648" --no-download
```

CLI 抓取期错误的退出码为：

- `0`：成功
- `1`：其他失败
- `2`：`ambiguous`
- `3`：`no_access`
- `4`：`rate_limited`

命令行参数解析错误仍沿用 `argparse` 的标准行为，也会以 `2` 退出，但不表示论文解析歧义。

## Wiley / Science / PNAS 边界

`wiley`、`science`、`pnas` 的运行边界和 `springer` 不一样：

- metadata 仍来自 `crossref`
- 全文链路由 provider 自己管理
- `pnas` 的主路径会先做 `direct Playwright HTML preflight`；失败后继续 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> abstract-only / metadata-only`。`wiley` 从 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> Wiley TDM API PDF -> abstract-only / metadata-only` 开始，`science` 从 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> abstract-only / metadata-only` 开始
- `wiley` / `science` / `pnas` 的 HTML 成功路径支持 `none/body/all` 资产下载；PDF/ePDF fallback 仍是 text-only
- `wiley` / `science` / `pnas` 的正文 figure / table / formula 图片资产下载以 shared Playwright browser context 为主链路；同一个 `RuntimeContext` 会 lazy 复用 Chromium browser，每次下载 attempt 仍只创建隔离 context/page，并在多图之间复用
- 资产下载 worker 上限由 `PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY` 控制，默认 `4`、最小 `1`；调高时需要自行评估 publisher 限速
- `science` / `pnas` 必须依赖 repo-local `vendor/flaresolverr/`
- `wiley` 的 HTML 与 seeded-browser PDF/ePDF 路径依赖 repo-local `vendor/flaresolverr/`；`WILEY_TDM_CLIENT_TOKEN` 只启用官方 TDM API PDF lane
- browser 路径需要显式配置 `FLARESOLVERR_ENV_FILE`；本地 FlareSolverr 限速变量与账本已移除

准备和排障细节见 [`docs/flaresolverr.md`](docs/flaresolverr.md)。

## 文档导航

- [`docs/README.md`](docs/README.md)
  - 文档总览、阅读顺序和术语表。
- [`docs/providers.md`](docs/providers.md)
  - provider 能力矩阵、路由规则、输出默认值、环境变量、缓存/重试/限速。
- [`docs/deployment.md`](docs/deployment.md)
  - 安装、配置、MCP 注册、更新和最小验证步骤。
- [`docs/flaresolverr.md`](docs/flaresolverr.md)
  - Wiley / Science / PNAS 的 repo-local 浏览器工作流。
- [`docs/architecture/target-architecture.md`](docs/architecture/target-architecture.md)
  - 当前架构分层、端到端业务流程、数据契约与扩展点。
- [`docs/architecture/probe-semantics.md`](docs/architecture/probe-semantics.md)
  - `has_fulltext()` 探针语义与 `fetch_paper()` 最终 verdict 的边界。

## Repo-local 验收

如果你在仓库源码目录里做本地验证，先安装测试依赖，并推荐显式带上 `PYTHONPATH=src`。默认 `pytest` 现在只覆盖 `tests/unit` + `tests/integration`，并通过 `xdist` 走多进程并行；`tests/live` 需要显式指定路径并串行运行：

```bash
python3 -m pip install '.[dev]'
PYTHONPATH=src pytest tests/unit/test_cli.py tests/unit/test_service.py tests/unit/test_mcp.py
PYTHONPATH=src pytest
```

默认 `pytest` 会跑默认离线快集；`tests/integration/test_golden_corpus.py` 现在会对 51 篇 canonical golden corpus 先跑一轮轻量 provider 契约检查，再对 5 篇代表性真实文献跑主路径回归，并继续跳过 51 篇的全文精确重放。

如果需要显式跑完整 51 篇 golden corpus 扩展回归，单独执行：

```bash
PAPER_FETCH_RUN_FULL_GOLDEN=1 PYTHONPATH=src pytest tests/integration/test_golden_corpus.py
```

如果要验收 `wiley` / `science` / `pnas` live 路径，再补充：

```bash
PAPER_FETCH_RUN_LIVE=1 \
FLARESOLVERR_ENV_FILE="$PWD/vendor/flaresolverr/.env.flaresolverr-source-headless" \
PYTHONPATH=src pytest -n 0 \
  tests/live/test_live_publishers.py::LivePublisherTests::test_wiley_doi_live_fulltext \
  tests/live/test_live_science_pnas.py
```

如果要跑自然地理五出版商的 live-only 全链路报告，直接走当前项目提取链路，不经过 MCP：

```bash
PAPER_FETCH_RUN_LIVE=1 \
FLARESOLVERR_ENV_FILE="$PWD/vendor/flaresolverr/.env.flaresolverr-source-headless" \
PYTHONPATH=src python3 scripts/run_geography_live_report.py
```

这些 geography 脚本现在按仓库内部 live tooling 维护：

- 只通过 `scripts/*.py` 运行
- 不新增安装后的 console script
- 不暴露为 MCP tool
- 继续受 `PAPER_FETCH_RUN_LIVE=1` 这条 opt-in 边界约束

默认会输出到：

```text
live-downloads/reports/geography-live-report.json
live-downloads/reports/geography-live-report.md
```

自然地理 live 样本清单维护在 [`tests/live/geography_samples.py`](tests/live/geography_samples.py)，默认每家 publisher 尝试前 `10` 条。对应的 live 测试入口是 [`tests/live/test_live_geography_publishers.py`](tests/live/test_live_geography_publishers.py)。

如果需要把 issue 样本导出成独立工件目录，或按问题类型生成分组视图，也继续走 repo-local 脚本：

```bash
PYTHONPATH=src python3 scripts/export_geography_issue_artifacts.py --help
PYTHONPATH=src python3 scripts/group_geography_issue_artifacts.py --help
```
