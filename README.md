# Paper Fetch Skill

`paper-fetch-skill` 面向已经确定的论文：给定 DOI、论文落地页 URL 或标题，尽量抓取可读正文、结构化元数据和 Markdown，并把结果暴露给命令行、MCP host 和 agent skill 使用。

它不是文献发现、选题推荐或自动综述系统。它解决的是一个更窄的问题：当你已经知道要读哪篇论文时，怎样把论文内容稳定地交给 AI agent 使用。

## 为什么做这个项目

AI agent 读论文时经常会卡在同一类问题上：

- 论文入口不统一：有 DOI、publisher 页面、PDF、摘要页，也可能只有题名。
- 输出不适合直接喂给模型：网页正文、公式、表格、图片和引用往往混在一起。
- provider 行为差异大：不同出版社的 HTML、PDF、API、反爬和 fallback 路径都不一样。
- 本地复用困难：同一篇论文被多次请求时，缺少稳定缓存和可追踪结果。

这个项目把这些问题收敛到一个可复用工具层：输入一篇已知论文，输出 AI 更容易消费的结果，并在拿不到全文时明确返回摘要级或 metadata-only 结果，而不是伪装成成功。

## 这个项目做什么

项目提供三个主要入口：

- `paper-fetch`：命令行工具，适合本地试跑、脚本调用和 smoke test。
- `paper-fetch-mcp`：stdio MCP server，适合接入 Codex、Claude Code 等支持 MCP 的 host。
- `skills/paper-fetch-skill/`：静态 agent skill，告诉 agent 什么时候应该调用论文抓取工具。

核心能力：

- 支持 DOI、URL 和标题查询。
- 输出结构化论文元数据、正文 Markdown、引用信息和本地缓存资源。
- 提供全文可用性检查、批量解析和批量预检。
- 支持常见 provider 路由，包括 Crossref、Elsevier、Springer、Wiley、Science 和 PNAS。
- 在无法取得全文时返回带 warning 的 abstract-only 或 metadata-only 结果。

项目边界：

- 不做主题检索、文献推荐或综述生成。
- 不绕过付费墙或访问授权；可用性取决于 provider、凭据和本机运行环境。
- Wiley、Science、PNAS 的浏览器路径需要额外运行时组件，详见 [`docs/flaresolverr.md`](docs/flaresolverr.md)。

## 如何部署

### 在线安装

在仓库根目录执行：

```bash
./install.sh
```

默认会创建仓库内 `.venv`，安装 Python 包，并准备 Playwright Chromium、repo-local FlareSolverr 和公式后端等运行组件。

如果只想安装 Python 包和基础配置：

```bash
./install.sh --lite
```

如果只想装进当前 Python 环境：

```bash
python3 -m pip install .
```

安装后可用命令：

```bash
paper-fetch --query "10.1186/1471-2105-11-421"
paper-fetch-mcp
```

### 配置文件

默认配置文件位置：

```text
~/.config/paper-fetch/.env
```

需要 API key、自定义下载目录或 User-Agent 时，可以先创建配置文件：

```bash
mkdir -p ~/.config/paper-fetch
cp .env.example ~/.config/paper-fetch/.env
```

也可以通过环境变量显式指定：

```bash
export PAPER_FETCH_ENV_FILE=/path/to/.env
```

完整环境变量说明见 [`docs/providers.md`](docs/providers.md)。

### 离线安装

离线包按操作系统和 CPython ABI 区分，例如：

```text
paper-fetch-skill-offline-linux-x86_64-cp311.tar.gz
paper-fetch-skill-offline-linux-x86_64-cp312.tar.gz
paper-fetch-skill-offline-linux-x86_64-cp313.tar.gz
paper-fetch-skill-offline-linux-x86_64-cp314.tar.gz
paper-fetch-skill-offline-windows-x86_64-cp311.zip
paper-fetch-skill-offline-windows-x86_64-cp312.zip
paper-fetch-skill-offline-windows-x86_64-cp313.zip
paper-fetch-skill-offline-windows-x86_64-cp314.zip
```

选择与目标机 OS 和 Python 版本匹配的包。Linux 解压后执行：

```bash
./install-offline.sh --preset=headless --no-user-config
source ./activate-offline.sh
```

WSLg 或桌面显示环境可改用：

```bash
./install-offline.sh --preset=wslg --no-user-config
```

Windows x86_64 目标机需要已有匹配 CPython，解压 zip 后在 PowerShell 中执行：

```powershell
.\install-offline.ps1 -NoUserConfig
. .\Activate-Offline.ps1
```

离线安装细节见 [`docs/deployment.md`](docs/deployment.md)。

### 接入 Codex

安装 skill 并注册 MCP server：

```bash
./scripts/install-codex-skill.sh --register-mcp
```

带配置文件注册：

```bash
./scripts/install-codex-skill.sh --register-mcp --env-file ~/.config/paper-fetch/.env
```

只安装到当前项目：

```bash
./scripts/install-codex-skill.sh --project --register-mcp
```

安装后重启 Codex，让它重新扫描 skills 和 MCP 配置。

### 接入 Claude Code

```bash
./scripts/install-claude-skill.sh --register-mcp
```

常用参数包括：

```bash
./scripts/install-claude-skill.sh --project --register-mcp
./scripts/install-claude-skill.sh --register-mcp --env-file ~/.config/paper-fetch/.env
```

### 手动注册 MCP

任何支持 stdio MCP 的 host 都可以直接运行：

```bash
paper-fetch-mcp
```

或：

```bash
python3 -m paper_fetch.mcp.server
```

WSL 下给 Codex 挂 MCP 时，推荐使用仓库包装脚本：

```bash
./scripts/run-codex-paper-fetch-mcp.sh
```

### 常用抓取参数

- MCP `fetch_paper` 默认返回 `article` 和 `markdown`，`prefer_cache=false`。
- `strategy.asset_profile` 支持 `none`、`body`、`all`；默认由 provider 决定。
- `no_download=true` 会关闭 provider payload、PDF、HTML、资产和 fetch-envelope sidecar 写入。
- `save_markdown=true` 会把全文 Markdown 写到硬盘，成功时返回 `saved_markdown_path`。

### 更新

更新仓库后重新安装包和 agent 集成：

```bash
python3 -m pip install .
./scripts/install-codex-skill.sh --register-mcp
```

Claude Code 用户对应执行：

```bash
./scripts/install-claude-skill.sh --register-mcp
```

## 文档

- [`docs/deployment.md`](docs/deployment.md)：安装、配置、MCP 注册和更新。
- [`docs/providers.md`](docs/providers.md)：provider 能力、环境变量和运行时配置。
- [`docs/flaresolverr.md`](docs/flaresolverr.md)：Wiley、Science、PNAS 浏览器路径部署与排障。
- [`docs/README.md`](docs/README.md)：完整文档导航。
- [`docs/architecture/target-architecture.md`](docs/architecture/target-architecture.md)：架构边界和维护者视角。
