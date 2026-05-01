# Paper Fetch Skill

`paper-fetch-skill` 面向已经确定的论文：给定 DOI、论文落地页 URL 或标题，尽量抓取可读正文、结构化元数据和 Markdown，并把结果暴露给命令行、MCP host 和 agent skill 使用。

## 为什么需要这个项目

AI agent 读论文时经常会卡在同一类问题上：

- 你有权限获取全文，但AI 没有权限，AI 只能读到摘要。
- PDF无法正确解析文字、图片，agent理解效果不如markdown。
- 文章html有很多无关的网页信息，给agent造成语义负担。
- 文章html中的图片 agent 读不到。

这个项目把这些问题收敛到一个工具层：
- 当你有全文获取权限时，让AI也能获取全文，而不仅是摘要。
- 输入n篇已知论文，抓取 AI 更容易理解的 markdown 版本，为后续知识库构建做好干净的数据基础。

## 这个项目做什么

项目提供三个主要入口：

- `paper-fetch`：命令行工具，适合手动大规模快速抓取文献。
- `paper-fetch-mcp`：stdio MCP server，适合接入 Codex、Claude Code 等支持 MCP 的 host。
- `skills/paper-fetch-skill/`：静态 agent skill，告诉 agent 什么时候应该调用论文抓取工具。

核心能力：

- 支持 DOI、URL 和标题查询。
- 输出结构化论文元数据、正文 Markdown、引用信息和本地缓存资源。
- 支持常见 provider 路由，包括 Crossref、Elsevier、Springer、Wiley、Science 和 PNAS。
- 在无法取得全文时返回带 warning 的 abstract-only 或 metadata-only 结果。

项目边界：

- 不做主题检索、文献推荐或综述生成。
- 不绕过付费墙或访问授权；可用性取决于 provider、凭据和本机运行环境。
- Wiley、Science、PNAS 的浏览器路径需要额外运行时组件，详见 [`docs/flaresolverr.md`](docs/flaresolverr.md)。

## 如何部署

### 离线安装（推荐）

离线 release asset 包含 4 个 Linux ABI tarball 和 1 个 Windows x86_64 安装器：

```text
paper-fetch-skill-offline-linux-x86_64-cp311.tar.gz
paper-fetch-skill-offline-linux-x86_64-cp312.tar.gz
paper-fetch-skill-offline-linux-x86_64-cp313.tar.gz
paper-fetch-skill-offline-linux-x86_64-cp314.tar.gz
paper-fetch-skill-windows-x86_64-setup.exe
```

推送 `v*` tag 时，GitHub Actions 会等常规验证、全部 Linux 离线包和 Windows 安装器成功后，自动创建对应 GitHub Release，并把上述 5 个文件作为 release assets 上传。也可以从 `v*` tag 手动运行 CI workflow，并设置 `publish_release=true` 重新发布。


#### **I. Windows x86_64：**

**1.下载安装包**

在 Releases 中下载 
```text
paper-fetch-skill-windows-x86_64-setup.exe
```

**2.本地终端运行安装程序：**
```powershell
.\paper-fetch-skill-windows-x86_64-setup.exe
```

安装器默认安装到 `%LOCALAPPDATA%\PaperFetchSkill`，不要求管理员权限。安装内容包含 CPython 3.13 x64 embeddable runtime、Python 依赖、Playwright Chromium、formula tools、FlareSolverr runtime、CLI/MCP cmd wrapper、Codex skill 和 Claude Code skill。安装器会把 `bin` 加入用户 PATH，复制 skill，并在检测到 Codex / Claude CLI 时注册 MCP；没有 Claude CLI 时只跳过 Claude MCP 注册，Codex 没有 CLI 时会备份并更新 `%USERPROFILE%\.codex\config.toml`。

**3.验证安装成功：**

安装后新开一个 PowerShell 

```powershell
paper-fetch --help
```
如果有输出`usage: cli.py [-h] -（后略）`则安装成功

**4.开启 Wiley / Science / PNAS 获取权限**
如果要启用 Wiley / Science / PNAS 的浏览器路径，启动安装器内置 FlareSolverr：

```powershell
flaresolverr-up
flaresolverr-status
```

停止时运行：

```powershell
flaresolverr-down
```

**5.开启Elsvier获取权限**

Elsevier 官方 XML/API 和 PDF fallback 需要从 <https://dev.elsevier.com/> 申请 key，并写入安装目录下的 `offline.env`：

```powershell
notepad "$env:LOCALAPPDATA\PaperFetchSkill\offline.env"
```

**6.刷新 agent 的 skill**

修改 Codex / Claude Code skill 或 MCP 配置后需要重启对应 host。

**7.常见问题**

Windows 安装器和 legacy 手动排障路径见 [`paper-fetch-windows-cli-mcp-skill-install.md`](paper-fetch-windows-cli-mcp-skill-install.md)，离线安装细节见 [`docs/deployment.md`](docs/deployment.md)。


#### **II.Linux** 

**1.下载安装包**

检查python版本
```bash
python --version
```


在 Releases 中选择与目标机 Python 版本的包下载。
```text
paper-fetch-skill-offline-linux-x86_64-cp311.tar.gz
paper-fetch-skill-offline-linux-x86_64-cp312.tar.gz
paper-fetch-skill-offline-linux-x86_64-cp313.tar.gz
paper-fetch-skill-offline-linux-x86_64-cp314.tar.gz
```

解压后执行：

```bash
./install-offline.sh --preset=headless --no-user-config
source ./activate-offline.sh
```

WSLg 或桌面显示环境可改用：

```bash
./install-offline.sh --preset=wslg --no-user-config
```

### 在线安装（可以但不推荐）

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

安装脚本结束时会提示 Elsevier 官方 API 配置入口。抓取 Elsevier 全文前，需要从 <https://dev.elsevier.com/> 申请 key，并在配置文件中填写 `ELSEVIER_API_KEY`。

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

其中 Elsevier 官方 XML/API 和 PDF fallback 至少需要从 <https://dev.elsevier.com/> 申请并配置：

```bash
ELSEVIER_API_KEY="..."
```

也可以通过环境变量显式指定：

```bash
export PAPER_FETCH_ENV_FILE=/path/to/.env
```

完整环境变量说明见 [`docs/providers.md`](docs/providers.md)。


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
