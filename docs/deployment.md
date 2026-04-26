# 部署指南

这份文档解决：

- 如何安装 `paper-fetch-skill`
- 如何准备配置文件
- 如何注册 MCP server
- 如何做最小化验证和更新

这份文档不解决：

- provider 差异、路由规则和限速语义
- Wiley / Science / PNAS 的详细运维步骤
- 架构实现细节

provider 与环境变量说明见 [`providers.md`](providers.md)，Wiley / Science / PNAS 运维说明见 [`flaresolverr.md`](flaresolverr.md)。

## 1. 安装 Python 包

先把包安装到目标环境：

```bash
python3 -m pip install .
```

安装完成后，当前环境会提供这些命令：

- `paper-fetch`
- `paper-fetch-mcp`
- `paper-fetch-install-formula-tools`

## 2. 准备配置文件

默认主配置文件是：

```text
~/.config/paper-fetch/.env
```

如果你需要 provider API key、自定义下载目录或自定义 `User-Agent`，可以先这样准备：

```bash
mkdir -p ~/.config/paper-fetch
cp .env.example ~/.config/paper-fetch/.env
```

补充说明：

- 运行时默认读取 `platformdirs` 解析出的用户配置目录下的 `.env`；常见 Linux/XDG 布局为 `~/.config/paper-fetch/.env`
- 仓库内的 `.env` 不会自动加载
- 如果要显式指定配置文件，请设置：

```bash
PAPER_FETCH_ENV_FILE=/path/to/.env
```

完整变量说明见 [`providers.md`](providers.md)。

## 3. 可选：安装公式后端

主抓取链路不依赖外部公式后端；只有当你希望公式转换效果更好时，才需要这一步。

即使没有安装外部公式后端，运行时仍会对已经拿到的 LaTeX 做轻量 normalize，例如把 `\updelta` 这类 upright Greek 宏改成 KaTeX 常用宏，并把 `\mspace{Nmu}` 改成 `\mkernNmu`。外部后端只影响 MathML 到 LaTeX 的转换能力，不是这些 normalize 规则的开关。

### 已安装环境

如果你已经 `pip install .`，推荐直接执行：

```bash
paper-fetch-install-formula-tools
```

### 当前仓库里的 repo-local 开发

如果你只是在当前仓库里开发：

```bash
./install-formula-tools.sh
```

补充说明：

- `paper-fetch-install-formula-tools` 会把工具装到用户数据目录，更适合部署环境
- `./install-formula-tools.sh` 会把工具装到当前仓库的 `./.formula-tools/`，并默认顺手准备 repo-local FlareSolverr 与 Playwright Chromium
- 如果只想安装公式工具，可给仓库脚本加 `--skip-flaresolverr-setup --skip-playwright-install`
- 运行时可用 `PAPER_FETCH_FORMULA_TOOLS_DIR` 覆盖公式工具查找目录；默认会考虑 repo-local `.formula-tools` 和用户数据目录下的 `formula-tools`

### CI / GitHub Actions

普通 CI 的 unit suite 会验证 Elsevier display formula 的 `texmath` 输出格式。GitHub Actions 因此需要先准备 Haskell/cabal，再执行：

```bash
python -m paper_fetch.formula.install --target-dir "$PWD/.formula-tools" --no-node
./.formula-tools/bin/texmath --help >/dev/null
```

测试步骤应设置 `PAPER_FETCH_FORMULA_TOOLS_DIR=$GITHUB_WORKSPACE/.formula-tools`。这里用 `--no-node` 是为了避免安装失败后静默落到 `mathml-to-latex` fallback；如果 `texmath` 没有装好，CI 会在验证步骤直接失败。

## 4. Elsevier / Wiley / Science / PNAS 接入入口

`elsevier` 现在不再依赖 FlareSolverr 浏览器链路；它只需要官方 API 凭据，并走 `官方 XML/API -> 官方 API PDF fallback -> metadata-only`。

`wiley`、`science`、`pnas` 仍然不是“装完 wheel 就自动可用”的浏览器路径。

如果你要启用后面三家的浏览器链路，至少还需要：

- 准备 repo-local `vendor/flaresolverr/`
- 设置 `FLARESOLVERR_ENV_FILE`

补充：

- `wiley` / `science` / `pnas` 还需要 Playwright Chromium，因为 HTML 正文图片资产下载和 seeded-browser PDF/ePDF fallback 都会使用 browser context
- `elsevier` 只需要 `ELSEVIER_API_KEY`
- 如果只想启用 `wiley` 的官方 TDM API PDF lane，可以只配置 `WILEY_TDM_CLIENT_TOKEN`；这不会启用 HTML 资产下载或 seeded-browser PDF/ePDF fallback
- `wiley` 现在走 `FlareSolverr HTML -> Wiley TDM API PDF -> seeded-browser publisher PDF/ePDF -> abstract-only / metadata-only`
- 本地 FlareSolverr 限速变量与账本已移除；browser workflow 不再读取 `FLARESOLVERR_MIN_INTERVAL_SECONDS`、`FLARESOLVERR_MAX_REQUESTS_PER_HOUR` 或 `FLARESOLVERR_MAX_REQUESTS_PER_DAY`

最常见入口是：

```bash
./install-formula-tools.sh
```

然后配置：

```bash
export FLARESOLVERR_ENV_FILE="$PWD/vendor/flaresolverr/.env.flaresolverr-source-headless"
```

完整启动、检查和排障步骤见 [`flaresolverr.md`](flaresolverr.md)。

## 5. 部署到 Codex

最常用流程：

```bash
python3 -m pip install .
./scripts/install-codex-skill.sh --register-mcp
```

这个脚本会：

- 安装当前包
- 复制静态 skill bundle
- 在显式传入 `--register-mcp` 时注册 `paper-fetch` MCP server
- 在 WSL 下默认通过 `scripts/run-codex-paper-fetch-mcp.sh` 启动 MCP，优先使用 `vendor/flaresolverr/.env.flaresolverr-source-wslg`，拿不到 WSLg 图形环境时回退到 headless preset

常用选项：

- `--project`
- `--env-file <path>`
- `--mcp-name <name>`

## 6. 部署到 Claude Code

最常用流程：

```bash
python3 -m pip install .
./scripts/install-claude-skill.sh --register-mcp
```

常用选项：

- `--project`
- `--env-file <path>`
- `--mcp-scope local|user|project`
- `--mcp-name <name>`

## 7. 手动注册 MCP

如果你不想使用安装脚本，也可以直接挂一个 stdio MCP server：

```bash
paper-fetch-mcp
```

或：

```bash
python3 -m paper_fetch.mcp.server
```

如果你是在 WSL 下给 Codex 挂宿主 MCP，推荐直接用：

```bash
./scripts/run-codex-paper-fetch-mcp.sh
```

这个包装脚本会：

- 在 WSL 下补齐缺失的 `XDG_RUNTIME_DIR`
- 优先选 `vendor/flaresolverr/.env.flaresolverr-source-wslg`
- 如果 WSLg 不可用，则回退到 `vendor/flaresolverr/.env.flaresolverr-source-headless`

如果配置文件不在进程环境里，额外设置：

```bash
PAPER_FETCH_ENV_FILE=/path/to/.env
```

当前 MCP server 适合挂到支持 stdio MCP 的 host。

## 8. 更新方式

更新当前仓库版本时，进入原来的 Python 环境后重新安装即可：

```bash
python3 -m pip install .
```

如果你还在使用 Codex 或 Claude Code，推荐顺手重跑对应安装脚本，让 skill 和 MCP 一起更新：

```bash
./scripts/install-codex-skill.sh --register-mcp
./scripts/install-claude-skill.sh --register-mcp
```

## 9. 最小验证步骤

先做一个最小 smoke test：

```bash
paper-fetch --query "10.1186/1471-2105-11-421"
```

如果你在仓库源码目录里做 repo-local 验证，先安装测试依赖，并推荐显式带上 `PYTHONPATH=src`。默认 `pytest` 只覆盖 `tests/unit` + `tests/integration` 并启用多进程并行；`tests/live` 需要显式指定路径并串行运行：

```bash
python3 -m pip install '.[dev]'
PYTHONPATH=src pytest tests/unit/test_cli.py tests/unit/test_service.py tests/unit/test_mcp.py
PYTHONPATH=src pytest
```

如果你要额外验证 `wiley` / `science` / `pnas` live 路径，请先按 [`flaresolverr.md`](flaresolverr.md) 准备环境，再运行对应 live 测试。

## 相关文档

- [`../README.md`](../README.md)
- [`docs/README.md`](README.md)
- [`providers.md`](providers.md)
- [`flaresolverr.md`](flaresolverr.md)
- [`architecture/target-architecture.md`](architecture/target-architecture.md)
