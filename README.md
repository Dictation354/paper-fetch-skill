# Paper Fetch Skill

> Fetch papers as agent-ready markdown — DOI/URL/title in, structured full text out. CLI · MCP · Skill.

**Paper Fetch Skill** —— 已知论文的 AI 阅读层。
你有 DOI、URL 或标题；它返回结构化元数据 + 干净 Markdown 全文 + 图表资源，直接喂给 Codex / Claude Code / 任意 MCP host。
不绕付费墙，只在你本就有访问权限的地方，把 AI 从「只能读摘要」升级到「读全文」。

## 🙁 AI agent 读论文的痛点

1. 你有权限获取全文，但 AI 没有权限，AI 只能读到摘要。
2. PDF 无法正确解析文字、图片，agent 理解效果不如 markdown。
3. 文章 html 有很多无关的网页信息，给 agent 造成语义负担。
4. 文章 html 中的图片 agent 读不到。


## 😍 这个项目做什么

✅这个项目把这些问题收敛到一个工具层：
1. 当你有全文获取权限时，让 AI 也能获取全文，而不仅是摘要。
2. 输入 n 篇已知论文，抓取 AI 更容易理解的 markdown 版本，为后续知识库构建做好干净的数据基础。

✅项目提供三个主要入口：

1. `paper-fetch`：命令行工具，适合手动大规模快速抓取文献。
2. `paper-fetch-mcp`：stdio MCP server，适合接入 Codex、Claude Code 等支持 MCP 的 host。
3. `skills/paper-fetch-skill/`：静态 agent skill，告诉 agent 什么时候应该调用论文抓取工具。

核心能力：

- 支持 DOI、URL 和标题查询。
- 输出结构化论文元数据、正文 Markdown、引用信息和本地缓存资源。
- 支持常见 provider 路由，包括 Crossref、Elsevier、Springer、Wiley、Science 和 PNAS。
- 在无法取得全文时返回带 warning 的 abstract-only 或 metadata-only 结果。

项目边界：

- 不做主题检索、文献推荐或综述生成。
- 不绕过付费墙或访问授权；可用性取决于 provider、凭据和本机运行环境。
- Wiley、Science、PNAS 的浏览器路径需要额外运行时组件，详见 [`docs/flaresolverr.md`](docs/flaresolverr.md)。

## 效果展示

agent 安装 skill 后，可以识别 `paper-fetch-skill` 的适用边界，并在抓取前确认是否保存全文和图表资源。

![agent 识别 paper-fetch-skill 能力范围](figures/agent-skill-overview.png)

以下示例来自 `figures/` 中的真实开放抓取产物。

### Nature 示例

- 论文：Towards end-to-end automation of AI research
- DOI：`10.1038/s41586-026-10265-5`
- 来源：Springer/Nature HTML full text
- 许可：[`CC BY 4.0`](https://creativecommons.org/licenses/by/4.0)
- Markdown 全文：[`towards-end-to-end-automation-of-ai-research.md`](figures/towards-end-to-end-automation-of-ai-research.md)

![Nature 论文抓取结果](figures/nature-oa-fetch-result.png)

### Science Advances 示例

- 论文：Deforestation-induced runoff changes dominated by forest-climate feedbacks
- DOI：`10.1126/sciadv.adp3964`
- 来源：Science Advances / Science provider
- Markdown 全文：[`deforestation-induced-runoff-changes-dominated-by-forest-climate-feedbacks.md`](figures/deforestation-induced-runoff-changes-dominated-by-forest-climate-feedbacks.md)

![Science Advances 论文抓取结果](figures/science-fetch-result.png)

## 快速安装

### 离线安装（推荐）

离线 release asset 包含 4 个 Linux ABI tarball 和 1 个 Windows x86_64 安装器：

```text
paper-fetch-skill-offline-linux-x86_64-cp311.tar.gz
paper-fetch-skill-offline-linux-x86_64-cp312.tar.gz
paper-fetch-skill-offline-linux-x86_64-cp313.tar.gz
paper-fetch-skill-offline-linux-x86_64-cp314.tar.gz
paper-fetch-skill-windows-x86_64-setup.exe
```

#### **I. Windows x86_64：**

**1. 下载安装包**

在 Releases 中下载 
```text
paper-fetch-skill-windows-x86_64-setup.exe
```

**2. 双击安装或者在本地终端运行安装程序**
```powershell
.\paper-fetch-skill-windows-x86_64-setup.exe
```

安装器默认安装到 `%LOCALAPPDATA%\PaperFetchSkill`，不要求管理员权限。会自动安装 paper-fetch CLI 工具、注册 MCP 并安装 Skill。

**3. 验证安装**

安装后新开一个 PowerShell 

```powershell
paper-fetch --help
```
如果有输出`usage: cli.py [-h] -`（后略）则安装成功

**4. 开启 Wiley / Science / PNAS 获取权限**
如果要启用 Wiley / Science / PNAS 的浏览器路径，启动安装器内置 FlareSolverr：

```powershell
flaresolverr-up
flaresolverr-status
```

停止时运行：

```powershell
flaresolverr-down
```

**5. 开启 Elsevier 获取权限**

Elsevier 官方 XML/API 和 PDF fallback 需要从 <https://dev.elsevier.com/> 申请 key，并写入安装目录下的 `offline.env`：

```powershell
notepad "$env:LOCALAPPDATA\PaperFetchSkill\offline.env"
```

**6. 刷新 agent skill**

修改 Codex / Claude Code skill 或 MCP 配置后需要重启对应 host。

**7. 常见问题**

Windows 安装器和 legacy 手动排障路径见 [`paper-fetch-windows-cli-mcp-skill-install.md`](paper-fetch-windows-cli-mcp-skill-install.md)，离线安装细节见 [`docs/deployment.md`](docs/deployment.md)。


#### **II. Linux** 

**1. 下载安装包**

检查python版本
```bash
python3 --version
```


在 Releases 中选择与目标机 Python 版本的包下载。
```text
paper-fetch-skill-offline-linux-x86_64-cp311.tar.gz
paper-fetch-skill-offline-linux-x86_64-cp312.tar.gz
paper-fetch-skill-offline-linux-x86_64-cp313.tar.gz
paper-fetch-skill-offline-linux-x86_64-cp314.tar.gz
```

Ubuntu 24.04 系统默认 Python 版本 3.12，Ubuntu 26.04 为 3.14。

解压后执行：

```bash
./install-offline.sh --preset=headless --no-user-config
source ./activate-offline.sh
```

WSLg 或桌面显示环境可改用：

```bash
./install-offline.sh --preset=wslg --no-user-config
```

#### **III. 更新和卸载**

**更新**

Windows 下载新版 `paper-fetch-skill-windows-x86_64-setup.exe` 后直接运行覆盖安装。安装器会保留 `%LOCALAPPDATA%\PaperFetchSkill\offline.env` 中用户写入的 API key，只刷新受管理的运行时配置、PATH、Skill 和 MCP 注册。

Linux 下载与目标机 Python 版本匹配的新版 tarball，解压到新目录。若希望更新时不改动旧 `offline.env`，使用 `--reuse-env-file` 指向现有文件，再使用原来的 preset / flags 重新安装：

```bash
cd /path/to/new-bundle
./install-offline.sh --preset=headless --no-user-config --reuse-env-file /path/to/old/offline.env
source ./activate-offline.sh
```

这会让新安装的 PATH / Skill / MCP 指向新目录，但不会修改被复用的 `offline.env`。如果后续要删除旧解压目录，先把 `offline.env` 放到不会被删除的位置，并把 `--reuse-env-file` 指向该位置。更新后重启 Codex / Claude Code。

**卸载**

Windows 在“设置 > 应用 > 已安装的应用”中卸载 `Paper Fetch Skill`，或运行：

```powershell
& "$env:LOCALAPPDATA\PaperFetchSkill\unins000.exe"
```

如需保留 `offline.env` 中的 API key，卸载前先备份该文件。

Linux 在原离线包解压目录运行：

```bash
./install-offline.sh --uninstall
```

该命令只清理用户级 PATH / Skill / MCP 集成，不删除解压目录、包内 `.venv/`、`offline.env` 或 `downloads/`；确认不再需要后可手动删除解压目录。

### 在线安装（不推荐，开发使用）

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

## 免责声明

本项目通过公开可访问的开放获取接口、publisher 路由和用户配置的凭据获取研究论文内容。

- 获取的文献仅供个人学术研究和学习使用，不得用于商业用途。
- 请遵守所在国家/地区著作权法律法规及所在机构的知识产权政策。
- 本项目不绕过付费墙或访问授权；可用性取决于 provider、凭据和本机运行环境。
- 本项目不存储、分发或传播任何文献内容，仅协助用户定位、抓取或转换用户有权访问的论文内容。
- 使用者应对自身的文献获取和使用行为承担全部责任。

## 社区

<https://linux.do/>
