# Paper Fetch Skill

`paper-fetch-skill` 用来把一篇已知论文（DOI、URL 或标题）抓取成 AI 更容易消费的正文和元数据。它既可以单独作为命令行工具使用，也可以通过 MCP + skill 接入 Codex、Claude Code 等 agent。

## 这个项目提供什么

- `paper-fetch`: 在终端里按 DOI、URL 或标题抓取论文
- `paper-fetch-mcp`: 给 agent runtime 使用的 stdio MCP server
- `scripts/install-codex-skill.sh`: 把 skill 安装到 Codex，并可顺手注册 MCP
- `scripts/install-claude-skill.sh`: 把 skill 安装到 Claude Code，并可顺手注册 MCP

## 快速开始

如果你只想先在当前环境里试用：

```bash
python3 -m pip install .
paper-fetch --query "10.1186/1471-2105-11-421"
```

如果需要出版社 API key 或自定义配置，默认配置文件放在 `~/.config/paper-fetch/.env`：

```bash
mkdir -p ~/.config/paper-fetch
cp .env.example ~/.config/paper-fetch/.env
```

变量说明见 [docs/providers.md](docs/providers.md)。
如果你要启用 `science` / `pnas`，还需要看 [docs/flaresolverr.md](docs/flaresolverr.md) 里的 repo-local FlareSolverr 工作流说明。

补充说明：

- 运行时依赖现在都显式声明在 `pyproject.toml` 里，安装不再依赖上游包“顺带带进来”的传递依赖
- HTTP 传输层默认带 `32 MiB` 响应上限，以及针对 `5xx` / timeout 的短重试；更详细的行为见 [docs/providers.md](docs/providers.md)
- provider 路由现在采用 `domain / Crossref publisher` 优先、`DOI prefix` 兜底的策略；像 `10.1006/jaer.1996.0085` 这类 Elsevier DOI 现在也能更稳定地命中官方链路
- `science` / `pnas` 已作为公开 provider 名字接入；但这两个通道只保证在当前仓库 checkout + `vendor/flaresolverr/` 工作流下可用，离开仓库单独 `pip install .` 的环境会明确报缺少 repo-local 依赖

## 默认输出策略

当前默认值统一如下：

- `asset_profile="none"`
  - 不下载 figure / table-image / supplementary 到本地
  - Markdown 仍保留 figure captions
  - 不保留远程图片 URL，也不输出 supplementary 链接
- `max_tokens="full_text"`
  - 默认尽量输出完整 abstract + 正文文字
  - references 默认全量输出
  - 如果 `asset_profile` 允许展示本地资产，也会一并完整展示
- 只有显式传数值 `max_tokens` 时，才进入硬上限裁剪模式
  - 裁剪优先级为：正文文字 > 当前 profile 对应非文字内容 > references

可选资产层级：

- `none`: 适合泛读 / 搜索 / 大规模文献调研
- `body`: 下载并渲染正文 figure + 正文表格原图
- `all`: 下载并渲染 provider 已识别的全部相关资产，包括 supplementary

## Provider 路由说明

- `resolve_paper().provider_hint` 现在表示“基于落地 URL domain、Crossref publisher、Crossref landing page 综合得出的最佳 hint”，不再等同于 DOI 前缀猜测
- provider 候选优先级固定为：`domain > publisher > DOI fallback`
- `preferred_providers` 仍严格限制最终允许使用的 official/fulltext/html 路径
- 即使 `preferred_providers` 没有包含 `crossref`，运行时仍可能内部调用 Crossref 只做 routing signal；这不会让最终结果自动变成 Crossref 来源
- `provider_hint` / `preferred_providers` / 最终 `source` 现在都可能直接出现 `science` 或 `pnas`
- `science` / `pnas` 的公开 `source` 固定是 provider 级别的 `science` / `pnas`；HTML 成功还是 PDF fallback 成功，会写在 `source_trail` 里，比如 `fulltext:science_html_ok`、`fulltext:pnas_pdf_fallback_ok`

## MCP Surface

当前 MCP server 提供这些工具：

- `resolve_paper(query | title, authors, year)`
- `has_fulltext(query)`
- `fetch_paper(query, modes, strategy, include_refs, max_tokens, prefer_cache, download_dir)`
- `list_cached(download_dir)`
- `get_cached(doi, download_dir)`
- `batch_resolve(queries)`
- `batch_check(queries, mode)`

`fetch_paper` 的 MCP 默认值是：

- `modes=["article", "markdown"]`
- `strategy.asset_profile="none"`
- `strategy.allow_html_fallback=true`
- `strategy.allow_metadata_only_fallback=true`
- `include_refs=null`
- `max_tokens="full_text"`
- `prefer_cache=false`

补充说明：

- `resolve_paper` 既支持原始 `query`，也支持 `title` + 可选 `authors` / `year` 的结构化输入
- `has_fulltext()` 是廉价 probe：只看 resolution、Crossref/官方 metadata probe 与 landing-page HTML meta，不会走完整正文抓取瀑布
- `has_fulltext()` 当前只主动产出 `state="likely_yes"` 或 `state="unknown"`；`confirmed_yes` / `no` 仍保留给后续迭代
- `include_refs=null` 在 `max_tokens="full_text"` 下等价于 `all`
- 显式 `prefer_cache=true` 时，`fetch_paper` 会先尝试命中本地 MCP cache 里的 envelope sidecar；命中才短路，未命中再照常上网
- 显式传 `download_dir` 会覆盖 `PAPER_FETCH_DOWNLOAD_DIR` 和 XDG 默认目录，适合隔离多任务下载目录
- `list_cached()` / `get_cached()` 只读本地 cache index，不触发网络
- `batch_check(mode="metadata")` 现在复用同一个廉价 probe，返回 `probe_state` / `evidence` / `warnings` 这类轻量字段，不会走完整抓取，也不会把正文或原始 payload 写入磁盘
- `batch_check(mode="article")` 仍保留“完整 fetch 后给最终 verdict”的语义
- 当 `strategy.asset_profile` 为 `body` / `all` 时，`fetch_paper` 可能在 JSON 结果后附带少量关键正文图的 `ImageContent`
- 这 7 个 MCP tools 现在都会向支持的 client 暴露 `outputSchema`，可直接用于 JSON Schema 参数补全和结果校验
- 支持这些能力的 MCP client 还会在 `fetch_paper` / `batch_check` / `batch_resolve` 期间收到 progress 和 structured log notifications

默认共享缓存资源会暴露在 MCP resources 下：

- `resource://paper-fetch/cache-index`
- `resource://paper-fetch/cached/{entry_id}`

这些 resources 只覆盖默认共享下载目录。若你在工具调用里显式传了 `download_dir`，请改用 `list_cached(download_dir)` 和 `get_cached(doi, download_dir)` 访问隔离目录。

## CLI 常用法

默认抓取：

```bash
paper-fetch --query "10.1186/1471-2105-11-421"
```

抓正文图和正文表格原图：

```bash
paper-fetch --query "10.1016/j.rse.2025.114648" --asset-profile body
```

抓全部资产：

```bash
paper-fetch --query "10.1016/j.rse.2025.114648" --asset-profile all
```

在 token 紧张时改成数值上限：

```bash
paper-fetch --query "10.1016/j.rse.2025.114648" --asset-profile body --max-tokens 12000
```

如果只想拿全文文字，不想落任何文件：

```bash
paper-fetch --query "10.1016/j.rse.2025.114648" --no-download
```

注意：

- `--no-download` 优先级高于 `--asset-profile`
- `--include-refs` 现在默认不需要传
  - `max_tokens=full_text` 时默认等价于全量 refs
  - 显式传数值 `--max-tokens` 时默认等价于 `top10`
- CLI 退出码现在固定为：
  - `0`: 成功
  - `1`: 其他失败
  - `2`: `ambiguous`
  - `3`: `no_access`
  - `4`: `rate_limited`

## 如何部署

### 部署到 Codex

```bash
python3 -m pip install .
./scripts/install-codex-skill.sh --register-mcp
```

### 部署到 Claude Code

```bash
python3 -m pip install .
./scripts/install-claude-skill.sh --register-mcp
```

## 如何更新

进入你原来安装用的那个 Python 环境后，重新安装当前仓库即可：

```bash
python3 -m pip install .
```

如果你还在用 Codex 或 Claude Code，推荐顺手再跑一次对应安装脚本，让 skill 和 MCP 一起更新：

```bash
./scripts/install-codex-skill.sh --register-mcp
./scripts/install-claude-skill.sh --register-mcp
```

### 可选：安装公式后端

如果你希望公式转换效果更好，可以额外安装公式后端：

```bash
paper-fetch-install-formula-tools
```

如果你是在当前仓库里做 repo-local 开发，而不是给已安装环境补依赖，才使用：

```bash
./install-formula-tools.sh
```

这个脚本现在也会顺手引导 Science/PNAS 的 repo-local 依赖：

- 调 `vendor/flaresolverr/setup_flaresolverr_source.sh`
- 调 `python3 -m playwright install chromium`
- 对 headless preset 检查 `Xvfb`

如果只想装公式后端，可以传：

```bash
./install-formula-tools.sh --skip-flaresolverr-setup --skip-playwright-install
```

不安装公式后端也能使用主抓取链路，只是公式渲染会退回到较弱的内置路径。若要启用 `science` / `pnas`，仍然需要下面的 repo-local FlareSolverr 步骤。

## Science / PNAS

`science` 和 `pnas` 现在已经是公开通道：

- `resolve_paper().provider_hint` 可直接返回它们
- `preferred_providers` 可显式指定它们
- `fetch_paper()` / MCP 返回的 `source` 也直接是 `science` 或 `pnas`

这两个通道的正文链路是：

- Crossref 提供 metadata 和路由信号
- provider 自己走 `HTML first -> PDF fallback`
- HTML 由 repo-local FlareSolverr 抓取
- HTML 被判定为摘要页、挑战页、登录页或正文不足时，转到带 cookies + user-agent 的 Playwright PDF fallback
- PDF 最终通过 `pymupdf4llm` 转成 AI-friendly markdown

启用前需要：

```bash
export FLARESOLVERR_ENV_FILE="$PWD/vendor/flaresolverr/.env.flaresolverr-source-headless"
export FLARESOLVERR_MIN_INTERVAL_SECONDS=20
export FLARESOLVERR_MAX_REQUESTS_PER_HOUR=30
export FLARESOLVERR_MAX_REQUESTS_PER_DAY=200
./scripts/flaresolverr-up "$FLARESOLVERR_ENV_FILE"
./scripts/flaresolverr-status "$FLARESOLVERR_ENV_FILE"
```

停止服务时：

```bash
./scripts/flaresolverr-down "$FLARESOLVERR_ENV_FILE"
```

补充说明：

- `FLARESOLVERR_URL` 默认是 `http://127.0.0.1:8191/v1`
- `FLARESOLVERR_SOURCE_DIR` 默认是当前仓库里的 `vendor/flaresolverr/`
- `FLARESOLVERR_ENV_FILE` 对 `science` / `pnas` 是必填，不会自动猜 preset
- `asset_profile=body|all` 在 `science` / `pnas` 当前会自动降级成 text-only，并在 `warnings` / `source_trail` 里说明
- 通用 `allow_html_fallback` 只控制 provider 失败后的普通 landing-page fallback，不会关闭 `science` / `pnas` 自己的 HTML 主路径
- 使用这些通道时，目标站点 ToS / robots / 授权风险由操作者自己承担

更完整的启动、限速和排障说明见 [docs/flaresolverr.md](docs/flaresolverr.md)。

## Repo-local 验收

如果你是在仓库源码目录里直接跑测试，推荐显式带上 `PYTHONPATH=src`，这样会优先导入当前工作树，而不是环境里可能已经安装过的旧版 `paper_fetch`：

```bash
ruff check .
PYTHONPATH=src python3 -m unittest -q tests.unit.test_cli tests.unit.test_service tests.unit.test_models_render tests.unit.test_html_generic tests.unit.test_http_cache tests.unit.test_fetch_common tests.unit.test_mcp tests.unit.test_provider_request_options tests.unit.test_publisher_identity tests.unit.test_resolve_query
PYTHONPATH=src python3 -m unittest -q tests.unit.test_science_pnas_html tests.unit.test_science_pnas_flaresolverr tests.unit.test_science_pnas_provider
PYTHONPATH=src python3 -m unittest discover -s tests -q
PAPER_FETCH_RUN_LIVE=1 PYTHONPATH=src python3 -m unittest tests.live.test_live_mcp -q
```

如果你要验收 `science` / `pnas` live 路径，再额外加上：

```bash
PAPER_FETCH_RUN_LIVE=1 \
FLARESOLVERR_ENV_FILE="$PWD/vendor/flaresolverr/.env.flaresolverr-source-headless" \
FLARESOLVERR_MIN_INTERVAL_SECONDS=20 \
FLARESOLVERR_MAX_REQUESTS_PER_HOUR=30 \
FLARESOLVERR_MAX_REQUESTS_PER_DAY=200 \
PYTHONPATH=src python3 -m unittest tests.live.test_live_science_pnas -q
```

## 文档

- [docs/deployment.md](docs/deployment.md): 安装、MCP 注册、公式后端和验证步骤
- [docs/flaresolverr.md](docs/flaresolverr.md): Science / PNAS 的 repo-local FlareSolverr、Playwright 和限速工作流
- [docs/providers.md](docs/providers.md): 环境变量、provider 配置和 API key 说明
- [docs/architecture/probe-semantics.md](docs/architecture/probe-semantics.md): `has_fulltext` probe 语义与当前 v1 落地范围
- [docs/architecture/target-architecture.md](docs/architecture/target-architecture.md): 项目结构和架构说明
