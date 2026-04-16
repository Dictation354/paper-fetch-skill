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
-> 失败时尝试 generic HTML fallback 或 provider 内部 fallback
-> 再失败时降级为 metadata-only
-> 输出 FetchEnvelope / Markdown / 本地缓存 / MCP 结果
```

更具体一点：

1. `resolve_paper()` 先把原始输入解析成 `ResolvedQuery`。
2. 路由优先级固定是 `domain > publisher > DOI fallback`。
3. `crossref` 既可能是公开来源 `source="crossref_meta"`，也可能只是内部 routing signal。
4. `elsevier` 仍优先走官方 API/XML 主链。
5. `springer` 走 provider 自管 direct HTML 主链，不再回到通用 `html_generic` fallback。
6. `wiley`、`science`、`pnas` 走 provider 自管 `HTML -> PDF fallback -> metadata-only` 浏览器工作流。
7. 普通 provider 或未命中 provider 自管 HTML 路径的场景，才会根据 `strategy.allow_html_fallback` 进入通用 `html_generic` fallback。
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

如果要把 skill 和 MCP 注册到常见 agent runtime，直接看 [`docs/deployment.md`](docs/deployment.md)。

## 默认值与关键限制

这些是最值得先记住的默认行为：

- `asset_profile="none"`
  - 默认不下载 figure、表格原图和 supplementary 到本地。
- `max_tokens="full_text"`
  - 默认尽量返回完整 abstract、正文和 references。
- `include_refs=null`
  - 在 `full_text` 模式下等价于全量 references。
  - 在数值 token budget 模式下默认等价于 `top10`。
- `fetch_paper()` 的 MCP 默认 `modes=["article", "markdown"]`
  - 同时返回结构化结果和 AI 直接可读的 Markdown。
- `has_fulltext()`
  - 是廉价 probe，不等同于最终 `fetch_paper().has_fulltext`。
- `wiley` / `science` / `pnas`
  - 当前只保证在仓库 checkout + `vendor/flaresolverr/` 工作流里可用。
  - `asset_profile=body|all` 目前会降级为 text-only，不阻塞正文成功。
- metadata-only fallback
  - 默认允许。正文不可用时，系统会返回 metadata + abstract，并显式带 warning。

## 支持的 provider 概览

当前公开 provider 包括：

- `crossref`
- `elsevier`
- `springer`
- `wiley`
- `science`
- `pnas`

其中：

- `elsevier` 是唯一保留的 publisher API fulltext provider，继续走 API/XML 主链。
- `springer` 使用 provider 自管 direct HTML 主链，公开来源为 `springer_html`。
- `wiley`、`science`、`pnas` 使用 repo-local FlareSolverr + Playwright 浏览器工作流。
- `wiley` 公开来源为 `wiley_browser`；`science`、`pnas` 继续保持原有 public source。
- `crossref` 负责 metadata、题名检索、路由信号和 metadata-only 结果，不承担 publisher fulltext。

完整能力矩阵、环境变量、缓存和限速说明见 [`docs/providers.md`](docs/providers.md)。

## MCP Surface

当前 MCP server 公开这些工具：

- `resolve_paper(query | title, authors, year)`
- `has_fulltext(query)`
- `fetch_paper(query, modes, strategy, include_refs, max_tokens, prefer_cache, download_dir)`
- `provider_status()`
- `list_cached(download_dir)`
- `get_cached(doi, download_dir)`
- `batch_resolve(queries, concurrency)`
- `batch_check(queries, mode, concurrency)`

还提供两个 prompt 模板：

- `summarize_paper(query, focus="general")`
- `verify_citation_list(citations, mode="metadata")`

MCP 细节和部署入口见 [`docs/deployment.md`](docs/deployment.md)。

## 常用 CLI 示例

默认抓取：

```bash
paper-fetch --query "10.1186/1471-2105-11-421"
```

抓正文图和正文表格原图：

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

CLI 退出码固定为：

- `0`：成功
- `1`：其他失败
- `2`：`ambiguous`
- `3`：`no_access`
- `4`：`rate_limited`

## Wiley / Science / PNAS 边界

`wiley`、`science`、`pnas` 已经是公开 provider 名字，但它们的运行边界和 `elsevier` / `springer` 不一样：

- metadata 仍来自 `crossref`
- 全文链路由 provider 自己管理
- 主路径是 `HTML first -> PDF fallback -> metadata-only`
- 依赖 repo-local `vendor/flaresolverr/`
- 需要显式配置 `FLARESOLVERR_ENV_FILE` 和本地限速变量

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

如果你在仓库源码目录里做本地验证，推荐显式带上 `PYTHONPATH=src`：

```bash
PYTHONPATH=src python3 -m unittest -q tests.unit.test_cli tests.unit.test_service tests.unit.test_mcp
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

如果要验收 `wiley` / `science` / `pnas` live 路径，再补充：

```bash
PAPER_FETCH_RUN_LIVE=1 \
FLARESOLVERR_ENV_FILE="$PWD/vendor/flaresolverr/.env.flaresolverr-source-headless" \
FLARESOLVERR_MIN_INTERVAL_SECONDS=20 \
FLARESOLVERR_MAX_REQUESTS_PER_HOUR=30 \
FLARESOLVERR_MAX_REQUESTS_PER_DAY=200 \
PYTHONPATH=src python3 -m unittest tests.live.test_live_science_pnas -q
```
