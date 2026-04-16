# Deployment Guide

这份文档面向“把 `paper-fetch-skill` 部署到一个可用环境里”的场景，重点说明安装顺序、MCP 接入方式和可选依赖。

## 1. 安装 Python 包

先把包安装到目标环境：

```bash
python3 -m pip install .
```

安装完成后，当前环境会提供这些命令：

- `paper-fetch`
- `paper-fetch-mcp`
- `paper-fetch-install-formula-tools`

补充说明：

- runtime 依赖都在 `pyproject.toml` 里显式声明；安装后不需要再额外手动补 `pydantic`

## 2. 准备配置

默认主配置文件是 `~/.config/paper-fetch/.env`。如果你需要出版社 API key、`mailto` 或自定义下载目录，可以这样准备：

```bash
mkdir -p ~/.config/paper-fetch
cp .env.example ~/.config/paper-fetch/.env
```

详细变量说明见 [providers.md](providers.md)。

补充说明：

- 运行时默认读取 `~/.config/paper-fetch/.env`
- 仓库内的 `.env` 不会自动生效；如果你要在开发场景下使用它，请显式设置 `PAPER_FETCH_ENV_FILE=/path/to/.env`
- 安装脚本也不会自动绑定仓库 `.env`；如果你希望 MCP 使用某个特定配置文件，请显式传 `--env-file /path/to/.env`
- `science` / `pnas` 额外要求 `FLARESOLVERR_ENV_FILE` 与三条本地限速变量；这些变量说明见 [providers.md](providers.md)，完整工作流见 [flaresolverr.md](flaresolverr.md)

## 3. 可选：安装公式后端

主抓取链路不依赖外部公式后端；不安装也能工作。只有当你希望 `texmath` / `mathml-to-latex` 真正在部署后的环境里可用时，才需要这一步。

推荐分两种场景理解：

- 已经 `pip install .`，或者要在另一台机器上部署：

  ```bash
  paper-fetch-install-formula-tools
  ```

- 只是在当前仓库里做 repo-local 开发：

  ```bash
  ./install-formula-tools.sh
  ```

区别是：

- `paper-fetch-install-formula-tools` 会把工具装到用户数据目录，适合安装后环境复用
- `install-formula-tools.sh` 会把工具装到当前仓库的 `./.formula-tools/`，更适合本仓库开发

补充说明：

- `./install-formula-tools.sh` 现在还会顺手引导 repo-local Science / PNAS 依赖：
  - 调 `vendor/flaresolverr/setup_flaresolverr_source.sh`
  - 调 `python3 -m playwright install chromium`
  - 对 headless preset 检查 `Xvfb`
- 如果你只想装公式后端，不想碰 Science / PNAS 依赖，可以传：

  ```bash
  ./install-formula-tools.sh --skip-flaresolverr-setup --skip-playwright-install
  ```

## 3.1 Repo-local Science / PNAS 依赖

`science` / `pnas` 不是“装完 wheel 就自动可用”的那类 provider。当前只保证在仓库 checkout 里运行，并依赖 repo-local `vendor/flaresolverr/` 工作流。

推荐准备顺序：

```bash
./install-formula-tools.sh
export FLARESOLVERR_ENV_FILE="$PWD/vendor/flaresolverr/.env.flaresolverr-source-headless"
export FLARESOLVERR_MIN_INTERVAL_SECONDS=20
export FLARESOLVERR_MAX_REQUESTS_PER_HOUR=30
export FLARESOLVERR_MAX_REQUESTS_PER_DAY=200
./scripts/flaresolverr-up "$FLARESOLVERR_ENV_FILE"
./scripts/flaresolverr-status "$FLARESOLVERR_ENV_FILE"
```

如果你在 WSLg 下想看见浏览器，也可以改成：

```bash
export FLARESOLVERR_ENV_FILE="$PWD/vendor/flaresolverr/.env.flaresolverr-source-wslg"
./scripts/flaresolverr-up "$FLARESOLVERR_ENV_FILE"
```

补充说明：

- `FLARESOLVERR_URL` 默认是 `http://127.0.0.1:8191/v1`
- `FLARESOLVERR_SOURCE_DIR` 默认是当前仓库的 `vendor/flaresolverr/`
- `FLARESOLVERR_ENV_FILE` 对 Science / PNAS 是必填；wrapper 脚本不会自动猜 preset
- headless preset 依赖 `Xvfb`
- 如果你把项目单独安装到一个没有当前仓库 checkout 的环境里，命中 `science` / `pnas` 时会得到明确的 “需要 repo-local vendor/flaresolverr” 错误

## 4. 部署到 Codex

最常用的部署方式是：

```bash
python3 -m pip install .
./scripts/install-codex-skill.sh --register-mcp
```

这个脚本会做三件事：

- 在当前 `python3` 环境里执行 `pip install .`
- 把静态 skill bundle 安装到用户级或项目级 Codex skill 目录，包括 `SKILL.md` 和 `references/`
- 如果带了 `--register-mcp`，调用 Codex CLI 注册 `paper-fetch` 这个 stdio MCP server

常用选项：

- `--project`: 安装到当前仓库的 `.codex/skills/`
- `--env-file <path>`: 显式指定 MCP 启动时读取的环境文件
- `--mcp-name <name>`: 修改默认 MCP server 名称 `paper-fetch`

完成后重启 Codex，让它重新扫描 skill 和 MCP。

## 5. 部署到 Claude Code

最常用的部署方式是：

```bash
python3 -m pip install .
./scripts/install-claude-skill.sh --register-mcp
```

这个脚本同样会安装包、复制静态 skill，并在显式传入 `--register-mcp` 时注册 MCP。

补充说明：

- 复制的是整个静态 skill bundle，而不只是入口 `SKILL.md`
- 详细环境变量、CLI fallback 和错误语义文档会随 `references/` 一起进入安装后的 skill 目录

常用选项：

- `--project`: 安装到当前仓库的 `.claude/skills/`
- `--env-file <path>`: 显式指定 MCP 启动时读取的环境文件
- `--mcp-scope local|user|project`: 指定 Claude MCP 配置作用域
- `--mcp-name <name>`: 修改默认 MCP server 名称 `paper-fetch`

完成后重启 Claude Code，让它重新扫描 skill 和 MCP。

## 6. 手动接入 MCP

如果你不想使用安装脚本，也可以手动注册一个 stdio MCP server，启动命令指向下面任一入口：

```bash
paper-fetch-mcp
```

或：

```bash
python3 -m paper_fetch.mcp.server
```

如果配置文件不在进程环境里，可以额外设置：

```bash
PAPER_FETCH_ENV_FILE=/path/to/.env
```

当前 MCP 入口是 stdio server，适合挂到 Codex、Claude Code 或其他支持 stdio MCP 的 agent runtime。

如果 MCP 请求命中 `science` / `pnas` 路由，server 会在 provider 运行前后做这些检查：

- repo-local `vendor/flaresolverr/` 工作流资源是否存在
- `FLARESOLVERR_ENV_FILE` 与三条本地限速变量是否齐全
- 本地 FlareSolverr 的 `sessions.list` 健康检查是否通过

检查不通过时会返回明确的 `not_configured` 或 `rate_limited` 错误，并在 reason 里带上 `./scripts/flaresolverr-up <preset>` 这一类启动提示。

## 7. 验证是否部署成功

可以先做一个最小 smoke test：

```bash
paper-fetch --query "10.1186/1471-2105-11-421"
```

如果你还想验证仓库自带的离线测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/integration -q
```

如果你是在仓库源码目录里做 repo-local 验证，而不是验证已安装环境，推荐所有 `unittest` 命令都显式带上 `PYTHONPATH=src`，避免误导入环境里旧的已安装包。

部署到 agent 之后，推荐再实际调用一次：

- `resolve_paper(query | title, authors, year)`
- `has_fulltext(query)`
- `fetch_paper(query, modes, strategy, include_refs, max_tokens, prefer_cache, download_dir)`
- `provider_status()`
- `list_cached(download_dir)`
- `get_cached(doi, download_dir)`
- `batch_resolve(queries, concurrency)`
- `batch_check(queries, mode, concurrency)`

如果 host 支持 MCP prompts，还可以直接挂出：

- `summarize_paper(query, focus="general")`
- `verify_citation_list(citations, mode="metadata")`

`fetch_paper` 的当前 MCP 默认值是：

- `modes=["article", "markdown"]`
- `strategy.allow_html_fallback=true`
- `strategy.allow_metadata_only_fallback=true`
- `strategy.asset_profile="none"`
- `max_tokens="full_text"`
- `include_refs=null`
- `prefer_cache=false`

也就是默认更偏向“先把全文文字完整拿回来，但不额外下载图片/补充材料”。补充说明：

- `resolve_paper` 支持原始 `query`，也支持 `title` + 可选 `authors` / `year` 的结构化输入
- `summarize_paper()` / `verify_citation_list()` 是薄 prompt 模板，分别覆盖“单篇论文总结”和“citation list 批量甄别”的 cache-first 工作流
- `has_fulltext()` 是廉价 probe，只用 resolution、Crossref/官方 metadata probe 与 landing-page HTML meta 信号，不会触发完整正文抓取
- `has_fulltext()` 当前只主动返回 `likely_yes` / `unknown`；`confirmed_yes` / `no` 仍保留给后续迭代
- `fetch_paper()` 顶层结果现在会附带 `token_estimate_breakdown={abstract,body,refs}`；兼容保留的 `token_estimate` 仍只表示 `abstract + body`
- `provider_status()` 会按稳定顺序返回 `crossref`、`elsevier`、`springer`、`wiley`、`science`、`pnas` 的本地诊断结果；它只检查本地配置、repo-local 依赖、FlareSolverr 健康和本地限速窗口，不会主动探测远端 publisher API 连通性
- `provider_status()` 的 provider 级 `status` 固定使用 `ready` / `partial` / `not_configured` / `rate_limited` / `error`；每个 provider 还会带 `checks=[...]` 明细，适合 agent 在正式抓取前先做预检
- `include_refs=null` 在 `max_tokens="full_text"` 下默认等价于 `all`
- 显式 `prefer_cache=true` 时，`fetch_paper` 会先尝试读取本地 MCP cache 里的 envelope sidecar；只有命中才短路，否则仍会正常联网
- 显式 `download_dir` 的优先级高于 `PAPER_FETCH_DOWNLOAD_DIR` 和 XDG 默认目录
- `list_cached()` / `get_cached()` 只读本地 cache index，不会触发网络
- `batch_resolve()` / `batch_check()` 默认 `concurrency=1`；显式提高时，不同 host 的查询可以并发执行，但同一 host 仍会保持串行
- `batch_resolve()` / `batch_check()` 每次调用最多接受 `50` 条 query；更长的 citation list 需要由 host 自行拆分
- `batch_check(mode="metadata")` 现在复用廉价 probe，返回 `probe_state` / `evidence` / `warnings` 等轻量字段，不会走完整 fetch，也不会把正文或 provider payload 写入磁盘
- `batch_check(mode="article")` 仍保留完整 fetch 语义
- 当 `strategy.asset_profile` 为 `body` / `all` 时，`fetch_paper` 可能在 JSON 块后附带少量关键正文图的 `ImageContent`
- 可选 `strategy.inline_image_budget={max_images,max_bytes_per_image,max_total_bytes}` 用来调节这些 inline 图片的默认上限：`3` 张、单张 `2 MiB`、总计 `8 MiB`；任一生效上限为 `0` 时会直接禁用 inline 图片附带
- 这 8 个 MCP tools 现在都会暴露 `outputSchema`，支持 schema-aware 的 host 可以直接做参数补全与结果校验
- 所有只读工具现在还会显式暴露 MCP `ToolAnnotations`：`resolve_paper` / `has_fulltext` / `provider_status` / `list_cached` / `get_cached` / `batch_*` 都标记为 `readOnlyHint=true`；`fetch_paper` 保持可写（会落 cache）
- 当错误能明确归因到缺失凭证或环境变量时，MCP `structuredContent` 现在会附带 `missing_env=[...]`
- 支持这些能力的 MCP client 会在 `fetch_paper` / `batch_check` / `batch_resolve` 期间收到 progress 和 structured log notifications
- 支持 MCP cancellation 的 host 现在可以取消 `fetch_paper` / `batch_check` / `batch_resolve`；worker 会协作式停止继续发后续网络请求
- `science` / `pnas` 当前只承诺正文 markdown；即使 `strategy.asset_profile` 是 `body` / `all`，也会降级为 text-only 并在结果里给 warning

如果你希望精读某篇论文，可以在 MCP 请求里显式传：

- `strategy.asset_profile="body"`: 下载并渲染正文 figure + 正文表格原图
- `strategy.asset_profile="all"`: 下载并渲染全部识别资产
- `max_tokens=<整数>`: 改成 token 紧张场景下的硬上限模式

默认共享缓存资源会暴露在 MCP resources 下：

- `resource://paper-fetch/cache-index`
- `resource://paper-fetch/cached/{entry_id}`

如果你在工具调用里显式传了 `download_dir`，当前 server session 还会为该目录注册一组 scoped cache resources：

- `resource://paper-fetch/cache-index/{scope_id}`
- `resource://paper-fetch/cached-dir/{scope_id}/{entry_id}`

其中 `scope_id` 是下载目录路径的稳定 hash，不直接暴露本地绝对路径。`list_cached(download_dir)` 和 `get_cached(doi, download_dir)` 仍然是同一批隔离目录缓存的 tool 入口。

支持资源列表变化通知的 MCP host 现在还能看到 `capabilities.resources.listChanged=true`，并在 `fetch_paper()` / `list_cached()` / `get_cached()` 让 cache resource URI 集合发生增删时收到 `notifications/resources/list_changed`。

如果你要验收 Science / PNAS 的 repo-local live 路径，可以额外跑：

```bash
PAPER_FETCH_RUN_LIVE=1 \
FLARESOLVERR_ENV_FILE="$PWD/vendor/flaresolverr/.env.flaresolverr-source-headless" \
FLARESOLVERR_MIN_INTERVAL_SECONDS=20 \
FLARESOLVERR_MAX_REQUESTS_PER_HOUR=30 \
FLARESOLVERR_MAX_REQUESTS_PER_DAY=200 \
PYTHONPATH=src python3 -m unittest tests.live.test_live_science_pnas -q
```

## 相关文档

- [providers.md](providers.md)
- [flaresolverr.md](flaresolverr.md)
- [architecture/probe-semantics.md](architecture/probe-semantics.md)
- [architecture/target-architecture.md](architecture/target-architecture.md)
