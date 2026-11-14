# 部署指南

安装、配置、MCP 注册和升级见下文。
provider 差异见 [providers.md](providers.md)，浏览器组件与状态见 [browser-backends.md](browser-backends.md)，
原生 macOS 证据边界见 [适配说明](#macos-适配与证据边界)。已安装 skill 的独立说明位于
[environment.md](../skills/paper-fetch-skill/references/environment.md) 和
[cli-workflow.md](../skills/paper-fetch-skill/references/cli-workflow.md)。

## 1. 安装 Python 包

安装器在核心安装完成后默认准备受管 Byparr 及当前平台引擎，首次安装、升级与重装均复用有效
缓存和成功检查记录，准备失败保留核心安装。跳过选项、离线预置和重试入口见
[浏览器安装与准备](#浏览器安装与准备)。后续可选配置只处理凭据、Ghostscript 和
libvips，图片工具默认不选，不会再次启动浏览器。

默认 `pip install .` 只安装轻量 core。按需要选择 `.[browser]`（浏览器/HTML）、
`.[pdf]`（PDF 转换）或 `.[full]`（两者）。开发与普通 CI 使用已提交的锁文件：

```bash
uv sync --frozen --extra dev --extra full
```

core 运行时要求 MCP Python SDK 2.x（`mcp>=2,<3`）。server 使用 v2
`MCPServer`，同时兼容 2025 握手协议客户端和 2026-07-28 现代协议客户端。

如果目标是把本仓库的完整本地运行环境一次性准备好，推荐先使用顶层一键安装脚本：

```bash
./install.sh
```

默认行为：

- 创建仓库内 `.venv`
- 安装当前 Python 包
- 如果存在 `.env.example` 且用户配置文件还不存在，按 `platformdirs` 创建配置：
  Linux 常见路径是 `~/.config/paper-fetch/.env`，macOS 是
  `~/Library/Application Support/paper-fetch/.env`
- 安装 Python 依赖、外部公式后端和图片转换后端；源码在线安装默认准备支持的浏览器，可用 `--skip-browser-prepare` 跳过；运行时首次使用后端时自动准备
- 安装结束时提示 Elsevier 官方 API key 的申请入口和配置位置；使用 Elsevier API 路线时从 <https://dev.elsevier.com/> 申请并设置 `ELSEVIER_API_KEY`

补充说明：

- 这是在线一键安装入口：用户不需要手动准备公式后端；浏览器路径通过统一后端接口执行。CLI/MCP/library 在首次实际使用后端时自动准备组件；进入受限网络前可按 [预置说明](#浏览器安装与准备) 准备当前平台浏览器及所需模型，再用 `paper-fetch browser-preflight` 验证
- 如果只想安装 Python 包和配置骨架，不准备外部公式或图片转换后端，使用 `./install.sh --lite`
- 如果要装进当前 `python3` 环境而不是 `.venv`，使用 `./install.sh --system`
- arXiv 不需要本地转换器；official HTML 不可用或质量检测失败时直接进入 PDF fallback
- 如果只想跳过公式 Node fallback，可使用 `--no-node`

### 浏览器安装与准备

core 不包含浏览器依赖；pip 安装可选择：

```bash
python -m pip install "paper-fetch-skill[browser]"
python -m pip install "paper-fetch-skill[full]"
```

`full` 同时包含 PDF 能力。运行时不自动安装缺失的 Python 依赖。离线包按 `full`
构建并内置锁定的 Byparr 源码和私有依赖，但不分发浏览器 binary 或 fpgen 模型。
组件版本、缓存和后端配置见[浏览器后端](browser-backends.md#统一受管-byparr)。

Byparr 在 Windows/Linux x64 使用 InvisiblePlaywright 及其 seal 校验的 Firefox；
macOS 与 ARM 使用 Camoufox。平台选择与组件版本见
[统一受管 Byparr](browser-backends.md#统一受管-byparr)，两个引擎的 executable 不能互换。

以下渠道、版本 pin、24 小时更新检查与 fpgen 说明仅适用于 Camoufox。
Camoufox Python 包固定为 0.5.9，浏览器独立跟踪渠道。未显式配置渠道或 pin 时默认
`official/prerelease`，由官方版本发现机制选择当前平台最新兼容正式版或预发布版；
`stable` 仅接受正式版。可显式设置：

```bash
python -m camoufox set official/stable
python -m camoufox set official/prerelease/<version>
```

已有渠道、版本 pin、SHA 和自定义 executable 优先；显式 pin 只准备对应版本，
有效本地 pin 直接复用。准备时在缓存锁内补齐默认渠道，静态探测不写配置。
最近检查成功且本地组件有效时，24 小时内不查询远端，“无需更新”也算成功。
失败或取消不延长成功窗口，下一次调用允许重试；缺失、损坏或不兼容允许立即准备，
更新失败时可复用兼容本地组件。配置损坏、路径越界或 symlink/reparse 路径报错，
不通过删除配置修复。显式 `PAPER_FETCH_BROWSER_BINARY_PATH` 跳过托管浏览器更新。
安装器、CLI、MCP、Python API、auth 与 preflight 共用持久准备记录及文件锁。

安装阶段默认准备整套 Byparr 和当前平台引擎。在线 `--lite`、POSIX
`--skip-browser-prepare` 或 Windows `/SKIPBROWSERPREPARE` 可跳过，运行时仍按需准备。
完全离线前，在联网环境用安装环境的 Python 预置；此命令也用于失败后重试：

```bash
python -m paper_fetch.offline_setup --install-root <install-dir> --env-file <config.env> --prepare-browsers
```

安装汇总以 `Browser preparation: ready|not ready|skipped` 报告本次结果，失败或取消
保留核心安装并显示重试命令。Camoufox 的完整 runtime 包括相邻配置、addons、字体和
fpgen 模型，只复制 executable 不足以使用；fpgen 模型不在 Python wheel 内，模型目录
需可写。项目在原模型下载失败时从官方 Release API 获取同一固定 tag 和文件名，继续
核验压缩包及各模型 SHA-256；校验失败不回退。Camoufox 的模型准备先于 Playwright 启动，
自定义 executable 也遵守此顺序。

`--prepare-browsers` 为布尔开关，准备所选平台引擎及 Byparr，
当前平台引擎与 Byparr 组件分别复用准备结果。`--non-interactive` 允许用户级下载，
不安装系统软件；Debian/Ubuntu 缺共享库时显示 APT 指引，交互模式经确认后安装。
无需 Chrome、ChromeDriver、Selenium、Xvfb 或 bubblewrap。

下载准备预算 10 分钟，本地启动检查另限 2 分钟，可用 Ctrl+C 取消。检查仅使用临时
状态和 `about:blank`，不访问出版社或认证，结束时清理所属进程。失败保留核心安装，
结果和重试命令写入 `browser-setup-results.txt`。

### 离线包

离线发布支持 Linux x86_64、macOS 15+ arm64 和 Windows x86_64。Linux 按 CPython ABI 提供 3.11、3.12、3.13、3.14 自解压 `.sh` 安装器，内部 payload 是预安装 runtime 包；macOS 也按 CPython ABI 提供 3.11、3.12、3.13、3.14 tarball，由固定 `macos-15` runner 原生构建 arm64 产物，并在 manifest 声明最低 macOS 15.0；Windows 提供一个内置 CPython 3.13 x64 的 Inno Setup 安装器：

```text
paper-fetch-skill-offline-linux-x86_64-cp311.sh
paper-fetch-skill-offline-linux-x86_64-cp312.sh
paper-fetch-skill-offline-linux-x86_64-cp313.sh
paper-fetch-skill-offline-linux-x86_64-cp314.sh
paper-fetch-skill-offline-macos-arm64-cp311.tar.gz
paper-fetch-skill-offline-macos-arm64-cp312.tar.gz
paper-fetch-skill-offline-macos-arm64-cp313.tar.gz
paper-fetch-skill-offline-macos-arm64-cp314.tar.gz
paper-fetch-skill-windows-x86_64-setup.exe
```

构建和发布流程统一见 [CI / GitHub Actions](#ci--github-actions) 与
[发布前检查](#release-checklist)。离线包按对应原生平台构建和验证，Linux/WSL 不能
替代 macOS 或 Windows 安装证据。

#### 锁定依赖与更新

`pyproject.toml` 的大多数依赖保留兼容范围；browser/full extra 使用 `camoufox==0.5.9`，浏览器默认独立跟踪正式版和预发布版中的最新兼容版本，Python 包不自动升级。`uv.lock` 固定普通开发和 CI 实际使用的版本；POSIX 离线构建读取依赖 wheelhouse 中唯一 Camoufox wheel 的 METADATA，验证安装后的 distribution 与该版本一致，并在 `offline-manifest.json` 的 `components.camoufox.python_package_version` 记录实际值。quality job 在其它静态门禁之前通过独立的 `Check lockfile freshness` 步骤执行 `uv lock --check`，项目版本、依赖声明或 lock metadata 的陈旧状态会直接令 CI 失败；后续 `uv sync --frozen` 只消费已验证的锁文件，不会在常规运行中重新选择版本。Dependabot 每周为 pip、npm 和 GitHub Actions 更新创建可跟进的 PR；普通 PR 继续由 `verify.yml` 对锁定依赖执行全 extras 漏洞审计。离线 wheelhouse/hash manifest 继续负责跨平台离线资产，不替代开发锁文件。

PDF 的 `pdf/full` extras 协调使用 `PyMuPDF>=2,<3` 与 `pymupdf4llm>=2,<3`，
开发锁定这两个包及其传递依赖 `pymupdf-layout` 均为 2.1；仅维护 2.x。
转换调用、上游输出透传及资产落盘语义保持不变。

HTML 提取依赖 trafilatura 暂限 `>=2.0,<2.3`，开发锁定 2.2.0。
2.3.0 和 2.3.1 的 Markdown 转义会改写既有 `$...$` 公式中的下划线及表格引用；
在线安装与离线构建沿用这一兼容上限，保留现有公式和表格输出契约。

Camoufox 路线当前锁定为 Camoufox 0.5.9 / Playwright 1.62.0。项目允许
`playwright>=1.58,<1.63`，但解析时仍受 Camoufox 自身的 `<1.63` 约束，不能强制
安装 1.63。当前 Playwright 要求 Camoufox browser beta.30 或更新版本；固定浏览器版本时须满足该兼容范围。
浏览器渠道、pin、24 小时检查记录及 fpgen 预置统一见
[浏览器安装与准备](#浏览器安装与准备)。原生 macOS gate 预置浏览器、fpgen 和锁定的 Byparr 组件，
再验证同一版本的临时与持久 context；安装向导验收复用这些组件，并检查统一的 Byparr 就绪结果。

版本以 `pyproject.toml` 的 `[project].version` 为准，CLI 和 User-Agent 从元数据派生。
`scripts/sync_version.py --write` 同步 Inno `AppVersion`；`--check` 验证安装器及人工维护的
中英文 changelog 版本章节。发布命令见[发布前检查](#release-checklist)。

Linux 目标机直接运行与 Python ABI 匹配的 `.sh`。默认安装到 `~/.local/share/paper-fetch-skill`：

```bash
chmod +x paper-fetch-skill-offline-linux-x86_64-cp312.sh
./paper-fetch-skill-offline-linux-x86_64-cp312.sh --preset=headless --no-user-config
source ~/.local/share/paper-fetch-skill/activate-offline.sh
```

桌面显示环境可用：

```bash
./paper-fetch-skill-offline-linux-x86_64-cp312.sh --preset=headful --no-user-config
```

如需固定到自定义目录：

```bash
./paper-fetch-skill-offline-linux-x86_64-cp312.sh --install-dir "$HOME/tools/paper-fetch-skill" --preset=headless --no-user-config
source "$HOME/tools/paper-fetch-skill/activate-offline.sh"
```

macOS 目标机必须是 macOS 15+ Apple Silicon，并使用与本机 CPython ABI 匹配的
arm64 tarball。解压后运行包内安装脚本：

```bash
tar -xzf paper-fetch-skill-offline-macos-arm64-cp312.tar.gz
cd paper-fetch-skill-offline-macos-arm64-cp312
./install-offline.sh --preset=headful --no-user-config
source ~/.local/share/paper-fetch-skill/activate-offline.sh
```

安装器在任何用户级写入前验证 manifest、checksum、Darwin/arm64、CPython ABI、
最低 macOS 15.0 和 quarantine。若 bundle 带
`com.apple.quarantine`，安装器会 fail closed；先核验 Release 来源和
`SHA256SUMS`，再由用户显式清除解压目录的 quarantine 后重试：

```bash
xattr -dr com.apple.quarantine \
  ./paper-fetch-skill-offline-macos-arm64-cp312
```

安装器不会自行移除 quarantine。包内 texmath 使用 ad-hoc codesign；这验证
Mach-O 结构，不等同于 Developer ID 签名或 Apple notarization。

进入离线环境前，在联网阶段按[浏览器预置说明](#浏览器安装与准备)准备
当前平台浏览器及所需模型，并运行 `paper-fetch browser-preflight` 检查实际启动和站点访问。
离线安装使用激活后的 `python`，或 `<install>/runtime/paper-fetch-python`。

Preset 选项：

- `headless` 面向服务器或无桌面环境。
- `headful` 面向 macOS 或常规桌面显示环境。

Shell rc 写入策略：

- Linux / macOS 安装脚本会把 payload 复制到固定安装目录，使用该目录下的 `bin/` 启动器和 `runtime/site-packages/` 已安装 Python 包，复制 Codex / Claude Code skill，并注册 MCP。
- Bash 写 `~/.bashrc`，Zsh 写 `~/.zshrc`，Fish 写 `~/.config/fish/conf.d/paper-fetch-offline.fish`。
- `~/.zshrc` 是符号链接时，安装和卸载修改链接目标并保留符号链接本身；不会用临时文件 `mv` 覆盖成普通文件。
- 无法识别 `$SHELL` 时写 `~/.profile` 并打印提示。

`activate-offline.sh` 入口：

- 安装后新开 shell，或临时执行 `source ~/.local/share/paper-fetch-skill/activate-offline.sh`；自定义安装目录时使用该目录下的 `activate-offline.sh`。
- `activate-offline.sh` 会用包内 Python 和 `python-dotenv` 按 dotenv 语法解析本安装目录的 `offline.env`，或安装时通过 `--reuse-env-file` 绑定的外部文件，再逐个导出合法 env key；不会 `source` 该文件或执行其中的命令替换、函数定义、普通 shell 命令。默认 activate 使用安装时绑定的配置，不受外层 `PAPER_FETCH_ENV_FILE` 覆盖。

Linux / macOS MCP 注册行为与 Windows 对齐：检测到 `codex` CLI 时执行 `codex mcp remove/add paper-fetch`，没有 CLI 或注册失败时更新 `~/.codex/config.toml` 中的 `mcp_servers.paper-fetch`；检测到 `claude` CLI 时执行 `claude mcp remove/add -s user paper-fetch`，没有 Claude CLI 时只安装 skill 并跳过 Claude MCP 注册；Antigravity 没有 `mcp add` CLI，安装器会把 `paper-fetch` server 合并到 `~/.gemini/antigravity-cli/mcp_config.json` 并保留其它 server。Codex / Claude Code / Antigravity 需要重启后才会重新扫描 skill 和 MCP 配置。

Windows 目标机运行安装器即可：

```powershell
.\paper-fetch-skill-windows-x86_64-setup.exe
```

Windows 安装器默认安装到 `%LOCALAPPDATA%\PaperFetchSkill`，不要求管理员权限。安装器会复制运行组件，写入用户 PATH，复制 Codex / Claude Code / Antigravity skill，并执行 best-effort 基础 smoke check。检测到 `codex` CLI 时会用 `codex mcp remove/add` 注册 MCP；没有 Codex CLI 时会备份并更新 `%USERPROFILE%\.codex\config.toml` 中的 `mcp_servers.paper-fetch`。检测到 `claude` CLI 时会用 `claude mcp remove/add -s user` 注册；没有 Claude CLI 时只安装 skill 并跳过 Claude MCP 注册。Antigravity MCP 写入 `%USERPROFILE%\.gemini\antigravity-cli\mcp_config.json`，并保留其它 server。用户级 skill / PATH / MCP 集成或 smoke check 失败时不会回滚已复制的 runtime，详细警告写入 `%LOCALAPPDATA%\PaperFetchSkill\install-helper.log`；可修正本机环境后手动重跑 `%LOCALAPPDATA%\PaperFetchSkill\scripts\windows-installer-helper.ps1 -Action Install`。

核心安装及 smoke 检查成功后，三平台提供可选配置向导。Linux/macOS 使用终端，`--non-interactive`、无可交互终端或 `--skip-smoke` 时跳过；Windows 使用 Inno 密码输入框和默认未选中的组件选项，`/SILENT`、`/VERYSILENT` 不进入可选阶段。可选配置只处理凭据和图片工具，图片工具下载、安装默认关闭，各组件独立选择；可选阶段断网、拒绝、取消、sudo/UAC 或功能验证失败不会回滚核心安装。

- Elsevier API Key 与 Wiley TDM Token 隐藏输入，留空保留旧值，只更新明确填写的 `ELSEVIER_API_KEY` / `WILEY_TDM_CLIENT_TOKEN`。凭据按 dotenv 转义、去重并原子保存，POSIX 文件权限为 `0600`，Windows 使用用户专属 DACL；不会进入命令行、日志或宿主注册参数。`--reuse-env-file` 的外部文件保持只读，向导提供手动配置说明。
- Linux 实际加载 GTK、X11/XCB、音频等共享库；不能确认时报告“未验证”。Debian/Ubuntu 根据当前 APT sources 的候选解析 `t64` 包名，先显示确切清单和命令，在自动准备阶段询问浏览器系统依赖安装，在可选阶段分别询问 Ghostscript 和 libvips 安装。仅 APT 子进程使用 sudo（由 sudo 收取密码），不刷新软件源、不全系统升级。缺包时给出建议，包锁/权限失败保留现有结果并重新检测；其它发行版仅检测和提示。
- macOS 保持 15+ arm64、CPython ABI、quarantine 和原生验证边界。已有 Homebrew 时可分别安装 `ghostscript`、`vips`，使用实际 prefix 下的绝对路径，无 `sudo brew`；无 Homebrew 时仅提供 [官方说明](https://brew.sh/)，不安装 Homebrew/Xcode/CLT，不清除 quarantine。
- Windows 图片工具固定于 `installer/manifest.json`：已从官方 release 下载并核验 [Ghostscript 10.08.0 x64 EXE](https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/tag/gs10080)、[libvips 8.18.7 x64 all ZIP](https://github.com/libvips/build-win64-mxe/releases/tag/v8.18.7) 的 SHA-256；用户安装时不查询 latest。下载先进入临时目录，摘要通过后才执行或解压；ZIP 拒绝路径逃逸、链接、重复路径及特殊文件，保留完整 DLL 和资源。
- Ghostscript 使用 [官方安装器](https://github.com/ArtifexSoftware/ghostpdl/blob/master/psi/nsisinst.nsi)，可见运行，使用末尾 `/D=<install-dir>\image-tools\ghostscript\<version>`；官方安装器要求管理员权限并写系统注册表。检测 PATH、配置和官方注册位置，优先复用有效工具；目标版本已注册但失效时仅给出修复提示。用户在官方向导更改目录时，以注册及转换验证确认的位置为准，外部目录不归 paper-fetch 清理。libvips 完整解压到 `image-tools\libvips\<version>`。
- 图片工具必须完成真实 EPS/TIFF → PNG 转换、PNG 解码与像素检查，才将绝对路径保存到既有 `PAPER_FETCH_GHOSTSCRIPT_BIN` / `PAPER_FETCH_VIPS_BIN`。版本探测成功不等于转换就绪。Windows 用独立 `optional-tools.json` 记录版本、来源、目录、归属、文件摘要及验证状态，与 release payload 清单分开。
自动浏览器准备以普通用户使用既有 channel/pin/cache 和成功检查记录；随后只启动本地 `about:blank` 验证，不访问出版社、不登录、不保存 provider state。浏览器结果单独保存到 `browser-setup-results.txt`，可选配置不会再次启动浏览器。

Windows 耗时步骤有进度窗口和控制台结果，可用 Ctrl+C 取消当前可选步骤；官方 Ghostscript 向导及 UAC 可直接取消。完成后显示汇总，并写入不含凭据的 `optional-setup-results.txt`。Unix 汇总输出到终端。重启已运行的宿主/MCP 后配置生效。需要重试时可使用安装目录绝对运行时执行 `-m paper_fetch.offline_setup --install-root <install-dir>`（Unix）；Windows 重新运行 EXE 向导。

离线更新：已安装官方包且命令支持 `update` 时，运行 `paper-fetch update`。命令通过 [GitHub latest release API](https://docs.github.com/en/rest/releases/releases#get-the-latest-release) 查询固定仓库 `Dictation354/paper-fetch-skill` 的最新正式 Release，仅升级到更高版本。按当前平台、架构和标准 CPython ABI 选择安装包，安装包与 `SHA256SUMS` 均取自本次 Release；流式下载至临时目录并核验 SHA256 后才执行。

Linux/macOS 自动把当前安装目录、当前 Python、现有配置解析得到的 headless/headful 和外部 env 路径传给安装器，以 `--non-interactive` 跳过可选配置。macOS 在解包前拒绝越界路径、符号/硬链接、特殊文件及路径冲突，随后执行包内 `install-offline.sh`，保留原 ABI、payload inventory 和 quarantine 检查。Unix 下载临时文件在命令结束后清理。

Windows 下载校验后以 `/DIR=<当前安装目录>` 启动图形安装向导，CLI 随即返回 `0` 释放 runtime，并输出“已启动安装向导”和保留的安装包路径；升级结果由向导报告。Linux/macOS 完成升级或当前版本相同/更新时返回 `0`；不支持的安装方式或查询、下载、校验、安装失败返回 `1`，错误写 stderr。升级的配置、论文、认证状态和宿主集成保留行为仍由原安装器负责。

手动下载安装包更新：

- Windows：下载新版 `paper-fetch-skill-windows-x86_64-setup.exe` 并直接运行。安装路径和 `AppId` 固定；安装器先备份 `offline.env`，再通过固定版本与摘要的 UninsIS 1.7.0 静默运行同 `AppId` 的既有卸载器，并等待 Inno 的 TEMP 第二阶段删除原卸载器 EXE 后才覆盖新版 runtime-only payload。既有卸载器只移除自身管理的文件，不递归清空目录，因此 `offline.env`、`downloads/` 和其它用户自建文件会保留；UninsIS 的 LGPL 与 provenance notice 随安装器分发，新版 helper 只替换 managed runtime block，并重新写入 PATH、skill 和 MCP 注册。
- Linux：下载与目标机 CPython ABI 匹配的新 `.sh` 后直接运行。默认安装目录固定为 `~/.local/share/paper-fetch-skill`，升级时先在目标文件系统的独立临时目录复制新版 payload，重新验证 checksum、精确 inventory、入口和 skill。随后备份并逐项替换受管组件；写入 runtime marker、验证已安装 skill，并执行原有开关控制的 smoke（含浏览器 Python 包检查）后才提交。提交前失败会恢复旧组件并保留原退出码；回滚失败会报告并保留备份目录。成功后清理备份、临时目录和源码/构建残留，再刷新配置及 shell / skill / MCP managed block。论文目录、用户自建文件和环境文件不参与运行时替换。若希望更新时不改动外部 `offline.env`，用 `--reuse-env-file` 指向现有文件；安装脚本不会写入该文件，只会把 shell 启动文件和 Codex fallback config 中的 managed block 替换为新安装目录的 PATH / MCP runtime 路径。
- macOS：在 macOS 15+ arm64 目标机下载或构建与 CPython ABI 匹配的新 tarball，核验 checksum / quarantine 后运行 `install-offline.sh`；更新语义与 Linux 相同，默认固定安装目录同样是 `~/.local/share/paper-fetch-skill`。

```bash
./paper-fetch-skill-offline-linux-x86_64-cp312.sh --preset=headless --no-user-config
./paper-fetch-skill-offline-linux-x86_64-cp312.sh --preset=headless --no-user-config --reuse-env-file /path/to/shared/offline.env
source ~/.local/share/paper-fetch-skill/activate-offline.sh
```

被复用的 `offline.env` 可以保留原 managed block；运行时路径会通过 shell / activate / MCP 进程环境覆盖为新安装目录路径，文件内容只按 dotenv 解析，不当 shell 执行。更新后重启 Codex / Claude Code / Antigravity。

离线卸载：

Windows 正式卸载默认保留可选工具，交互窗口提供默认关闭的清理复选框，静默卸载（包括升级先卸载）始终保留。清理仅接受 `optional-tools.json` 中本向导拥有的版本目录：Ghostscript 校对注册路径和官方卸载器摘要后调用对应可见卸载器；UAC 取消、路径不符或失败时保留并报告位置。libvips 仅删除清单内摘要未变的文件，新增/修改文件保留。清理报告保存为 `optional-cleanup-results.txt`。Linux/macOS 不卸载 APT/Homebrew 工具；Windows 卸载另清理安装目录内由 runtime 生成的四个 fpgen 指纹模型文件，相关目录仅在为空时删除；用户新增文件保留。任何平台均不清理共享 Camoufox 缓存。

- Windows：在“设置 > 应用 > 已安装的应用”中卸载 `Paper Fetch Skill`，或运行 `%LOCALAPPDATA%\PaperFetchSkill\unins000.exe`。卸载器会删除其管理的 runtime、wrapper、bundled skill 和元数据，删除安装器复制的 Codex / Claude Code / Antigravity skill、用户 PATH 中的安装目录 `bin`，并移除安装器管理的 MCP 注册；`offline.env`、`downloads/` 内用户文件、其它安装根用户内容及用户手写的其它 Codex / Claude / Antigravity 配置会保留。
- Linux：运行 `~/.local/share/paper-fetch-skill/install-offline.sh --uninstall`，自定义目录则运行该目录下的 `install-offline.sh --install-dir <path> --uninstall`。该路径不做 checksum、Python ABI 或 bundle asset 检查，只删除 Codex skill 的当前路径 `~/.agents/skills/paper-fetch-skill`、`~/.claude/skills/paper-fetch-skill`、`~/.gemini/antigravity-cli/skills/paper-fetch-skill`，清理 shell 启动文件、用户配置和 Codex fallback config 中的 installer managed block，并通过可用的 `codex` / `claude` CLI 和 Antigravity `mcp_config.json` 移除 MCP；不会删除固定安装目录、`bin/`、`runtime/`、`offline.env`、`downloads/`，也不会删除用户配置中的非 managed 内容。需要删除固定安装目录时显式运行 `install-offline.sh --purge`。
- macOS：卸载命令与 Linux 相同；如果使用自定义安装目录，运行该目录下的 `install-offline.sh --install-dir <path> --uninstall`。卸载只清理 `~/Library/Application Support/paper-fetch/.env` 的 managed block，保留用户自写内容。`--purge` 会在删除任何用户集成之前拒绝 `/`、HOME 及其祖先、尚未安装的当前 bundle root 等危险目标，并要求目标目录中的 schema 3 `offline-manifest.json` 证明 project / entrypoint 所有权且存在 `runtime/python-bin` 安装标记；校验失败时不会做部分卸载。

离线安装约束：

- Linux / macOS 必须使用标准 GIL CPython，版本、`SOABI` 和架构均须与包名及 `offline-manifest.json` 目标完全匹配；例如 macOS `cp313` arm64 包只能用原生 arm64 CPython `3.13.x` 运行，Rosetta x86_64 Python、free-threaded/debug ABI 会在写入前拒绝
- Linux / macOS 安装器会校验 `offline-manifest.json` 的 `target.platform` 和 `target.arch`；macOS 离线包只支持 arm64
- macOS manifest 额外声明 `target.minimum_os_version = "15.0"`；安装器通过系统版本检查确认目标机满足最低版本，并在 shell、skill、MCP 和用户配置写入前完成所有平台、ABI、checksum 与整个 bundle 的递归 quarantine 预检
- Linux 离线安装默认使用 `/usr/bin/python3`，不受 PATH 中 Miniforge、Conda 或 virtualenv 的优先级影响；macOS 默认仍使用 PATH 中的 `python3`。可通过 `--python /path/to/python3.14` 或 `--python=/path/to/python3.14` 自选解释器，也接受命令名和相对路径。安装时选择顺序为 `--python` → `PAPER_FETCH_OFFLINE_PYTHON_BIN` → 平台默认值；例如 `bash paper-fetch-skill-offline-linux-x86_64-cp314.sh --python /usr/bin/python3.14`。所选解释器必须匹配包的 ABI，缺失或不匹配时安装停止，可用 `--python` 指定兼容解释器
- Linux / macOS 安装时把选中解释器的绝对路径写入 `runtime/python-bin`，并在安装结果中显示；后续 `runtime/paper-fetch-python` 私有 launcher、CLI wrapper 和 MCP 都复用该解释器。运行时仍允许 `PAPER_FETCH_OFFLINE_PYTHON_BIN` 显式覆盖绑定；`paper-fetch update` 沿用当前解释器。离线包包含 Python 依赖，不包含独立解释器；`bin/` 不暴露通用 `python` wrapper
- Windows 安装器固定使用包内 CPython 3.14.10 x64 embeddable runtime；版本、python.org URL 与官方 SHA-256 `90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159` 均来自 `installer/manifest.json`，构建器在解压前校验，目标机不需要预装 Python
- Linux 构建阶段用临时 wheelhouse 把项目和依赖安装进 `runtime/site-packages`，然后只把安装后的 runtime、`bin/` 启动器、公式工具和 skill 放进自解压 `.sh` payload；目标机安装阶段不运行 pip，不包含源码树、`dist/` 或 `wheelhouse/`
- browser/full 的 Python 依赖随离线 runtime 分发；当前平台浏览器 binary 和所需模型由[准备流程](#浏览器安装与准备)管理。离线使用需提前预置；现有安装验证不覆盖完全断网的浏览器启动。
- Linux `.sh` payload 不包含仓库源码快照和 `tests/` 目录；离线安装目标是运行已打包工具，不在目标机执行项目测试
- Linux、macOS、Windows 离线包都携带原生 texmath 0.13.3，分别位于 `formula-tools/bin/texmath` 和 `formula-tools/bin/texmath.exe`，并将它作为首选公式后端；`mathml-to-latex>=1.8.0,<2.0.0` 和随 Playwright 分发的 Node 作为二级转换回退。公式工具和离线包同时携带固定为 4.1.3 的 MathJax、TeX 字库、mhchem 与 bbm 字形扩展，预载 `bbm`、`textcomp` 及既有扩展，供源 TeX 与 MathML 转换结果的编译／排版校验使用。LitRoot 提交由 `scripts/sync_mathjax_engine.py /path/to/LitRoot` 生成的引擎副本；`--check`、副本摘要测试和独立检查器阻止内容漂移。`src/paper_fetch/resources/formula` 是 Node manifest、lockfile 和转换脚本的唯一源码位置；checkout runtime 直接引用它，Python 安装器和离线构建将它暂存到 `formula-tools`。目标机不编译 texmath，也不运行 `npm install`。CI / release 公式构建固定使用 `haskell-actions/setup` v2.12.1 的完整 SHA、GHC 9.14.1 和 Cabal 3.18.1.0。macOS 构建会把非系统 Mach-O dylib 复制到 `formula-tools/lib`，用 `@rpath` / `@loader_path` 重写引用，并对 texmath 与随包 dylib 做 ad-hoc codesign
- Linux / macOS 会配置安装目录内 `image-tools` 作为图片转换工具查找目录；离线构建不会把构建机 PATH 上的 Ghostscript/libvips 符号链接固化进包内。运行时找到 Ghostscript 时可转 EPS，找到 libvips 时可转 TIFF；缺少对应工具时只影响 AMS `Download Figure` 源图转换，网页 JPG/PNG 候选仍可回退
- Linux / macOS 默认写固定安装目录内的 `offline.env`、生成可在 bash/zsh 中 `source` 的 `activate-offline.sh`、复制三份 host skill，并把离线 CLI PATH、工具路径、`PAPER_FETCH_ENV_FILE`、`PYTHONUTF8`、`PYTHONIOENCODING` 等写入当前 shell 启动文件；`offline.env` 的 managed block 写入 `PAPER_FETCH_BROWSER_HEADLESS=true`，不覆盖 Camoufox 生成的 Firefox UA/指纹。只有显式传 `--user-config` 才会把受标记管理的运行时块合并到用户配置；Linux 目标是 `~/.config/paper-fetch/.env`，macOS 目标是 `~/Library/Application Support/paper-fetch/.env`
- Linux / macOS `--install-dir <path>` 只接受不存在、空目录，或同时带 schema 3 ownership manifest 与 `runtime/python-bin` marker 的既有安装目录；拒绝 HOME/祖先、非空未拥有目录及指向它的 symlink。合法升级会清理 `src/`、`tests/`、`wheelhouse/`、`dist/`、`.github/` 等残留，保留安装目录内 `offline.env`，并保留用户配置中非 managed 内容
- Linux / macOS `--reuse-env-file <path>` 会把 `PAPER_FETCH_ENV_FILE` 指向现有文件且不修改该文件；其它 runtime 路径仍由新安装目录写入 shell / activate / MCP 环境，activate 时只做安全 dotenv 解析
- Linux / macOS 写入 shell 启动文件和 Codex fallback config 时会先替换既有受管理 block，重复安装不会重复追加；不修改 `/etc/profile`。macOS 的 `.zshrc` 即使是 symlink 也保持 symlink
- Windows 首次安装会写安装目录内 `offline.env`；升级安装会保留用户已有内容，只替换 managed runtime block。MCP 注册环境固定指向安装目录内 runtime 路径，并设置 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`、`PAPER_FETCH_BROWSER_HEADLESS=true`，不注入 Chrome UA。全部平台将 `MATHML_TO_LATEX_NODE_BIN` 和 `PLAYWRIGHT_NODEJS_PATH` 默认指向独立打包的官方 Node 26.13.0（POSIX：`runtime/node/bin/node`；Windows：`runtime/node/node.exe`），公式工具、Playwright 与 Byparr 共用该运行时，并保留显式环境覆盖。Node 版本、下载 URL 和官方 SHA-256 由 `installer/manifest.json` 管理，许可证随包分发，离线 manifest、dependency evidence 和 SBOM 记录来源、归档摘要与实际可执行文件摘要
- Windows 安装、升级或手工修改 `offline.env` 后，需要重启 Codex Desktop / Claude Code / Antigravity；已启动的 MCP 服务不会自动继承新写入的 env。
- Windows GUI 安装完成页会提示 Elsevier API key 申请入口和包内 `offline.env` 位置，并提供可选的 Notepad 打开项；silent 安装不会弹出该提示。使用 Elsevier API 路线时从 <https://dev.elsevier.com/> 申请 key，并在该文件中填写 `ELSEVIER_API_KEY`
- `--preset=headless` / `--preset=headful` 设置当前平台引擎的 headed/headless 行为

构建离线包：

```bash
scripts/build-offline-package.sh --output-dir dist
```

Windows 构建在 PowerShell 中执行：

```powershell
.\scripts\build-offline-package-windows.ps1 -OutputDir dist
```

**包命名与路径安全。** Linux / macOS 构建脚本会从当前平台、架构和 Python 推导包名；例如 Linux x86_64 上 `PYTHON_BIN=python3.13 scripts/build-offline-package.sh` 会默认生成 `paper-fetch-skill-offline-linux-x86_64-cp313.sh`，原生 Darwin arm64 上会生成 `paper-fetch-skill-offline-macos-arm64-cp313.tar.gz`。显式和 manifest 派生的包名都只能是安全单路径组件。构建根会 canonicalize 并拒绝 `/`、HOME、仓库及其祖先；非空 staging 只有携带匹配仓库、canonical 路径和包名的 `.paper-fetch-offline-staging-owner` 才可清理。临时 wheelhouse/project wheel 位于 owned staging，marker 与临时目录均不进入产物；output dir 不得位于 staging，正式 artifact 先写同目录临时文件再原子 rename，失败不会覆盖已有正式文件。

公式 workspace 要求 Node ≥22.12.0；在线安装遇到旧版本会提示升级，并保留核心安装。已有 workspace 按 `package-lock.json` 核对全部依赖版本，传递依赖变更时重新执行 `npm ci`。

**平台构建范围。** 构建解释器必须是标准 GIL CPython，架构须与宿主目标一致。macOS 构建只接受 Darwin arm64，并把最低 deployment target 固定为 15.0；Linux / WSL 交叉构建不能充当发布证据。Windows 构建必须在 CPython 3.14 x64 上运行，并按 manifest 下载和校验官方 CPython 3.14.10 embeddable x64 runtime。

**Payload 所有权。** Linux 产物是 shell stub 与压缩 payload 组成的单文件 `.sh` 安装器，macOS 产物是 `.tar.gz` bundle；两者都把项目和依赖安装进 `runtime/site-packages`，预编译 bytecode，并写入私有 launcher 与 paper-fetch 命令启动器。`bin/` 不包含通用 `python` wrapper，payload 不携带源码树或 wheelhouse。离线构建只从 repo-local 可重定位 runtime 暂存 Ghostscript/libvips；macOS 还会实体化 texmath、收集非系统动态库、重写 Mach-O install name 并执行 ad-hoc codesign。Windows 把 Python 包安装进 `runtime/Lib/site-packages`，Inno Setup 安装器只包含 embedded runtime、命令启动器、静态 skill、formula tools、image-tools、installer manifest、Windows helper 和离线元数据；安装后不携带顶层 `src/`、`tests/`、`.github/`、`wheelhouse/`、`dist/` 或 `pyproject.toml`。

**Evidence 所有权。** GitHub Actions 中 POSIX builder 使用 `.venv/bin/python`，Windows builder 使用 `.venv/Scripts/python.exe`，使 evidence generator 复用已锁定并安装 CycloneDX CLI 的开发环境；该控制解释器不进入目标 runtime。三个平台都从最终 staging 生成 `dependency-manifest.json`、经 CycloneDX 工具校验的 `paper-fetch-sbom.cdx.json` 和目标唯一的 `dist/paper-fetch-evidence-<target>.*` sidecar，盘点实际安装的 Python distribution、Node/Playwright、Camoufox、公式/图像/native 文件及 Windows embedded runtime digest。

**可选配置向导的原生验证。** 使用正式发行包，在目标平台分别验证全部跳过、各组件独立选择、
断网或取消、升级和卸载。macOS 覆盖 Homebrew 选择、quarantine 拒绝与 Camoufox 本地启动；
Windows 覆盖凭据输入及实际 DACL、Ghostscript 安装/卸载与 UAC 取消、安装目录变更和注册冲突。
临时 payload、mock 或 Linux portable 检查不能替代对应平台的正式包验证。

图片工具真实转换与原生 Camoufox 的验证入口见[测试说明](../tests/README.md)。

**Release 终验。** 操作顺序见 [发布前检查](#release-checklist)。构建、安装、证据与发布
必须对应同一不可变 source SHA，平台和验证器限制如下。

安装器共享配置集中在 `installer/manifest.json`：`skill.name`、`mcp.name`、`mcp.env_keys`、managed block marker 和离线包命名都从这里读取。shell 与 activate 环境变量沿用 `mcp.env_keys`，offline.env 使用其中除 `PAPER_FETCH_ENV_FILE` 外的键；技能展示 metadata 以实际复制的 `skills/paper-fetch-skill/agents/openai.yaml` 为准。Linux / macOS / Windows 离线安装脚本、Windows Inno helper 和离线包构建脚本都使用该 manifest，新增运行时环境变量或调整 managed block 文案时应优先改这里。

验证离线包：

```bash
scripts/verify-offline-package.sh dist/paper-fetch-skill-offline-linux-x86_64-cp311.sh
scripts/verify-offline-package.sh dist/paper-fetch-skill-offline-macos-arm64-cp311.tar.gz
```

上面的验证路径按实际构建出的 `cp311`、`cp312`、`cp313` 或 `cp314` 包名替换。

POSIX verifier 在临时 HOME 中检查解包、精确 checksum/inventory、runtime-only 布局、
CLI/MCP/skill、配置、公式与图片工具、升级和卸载。macOS 额外验证 quarantine、原生
arm64 Mach-O 依赖闭包与签名、独立 Node 和原包 Playwright Node 启动及 Zsh 集成；Linux/WSL 不替代这些证据。
这不等同于完全断网的浏览器启动验证。

Windows offline job 对最终 EXE 执行原生安装、CLI/doctor/provider status 与运行时 smoke，
再验证覆盖升级、用户内容保留、卸载完成与残留树。Inno/HKCU 和实际安装状态必须由
原生 Windows 提供证据。

Windows 原生 lifecycle gate 验证 cp314 全新安装后，校验并安装 v7.4.2 的 cp313 基线安装器，再升级至 cp314，核对用户配置、downloads、可选工具、Codex/Antigravity MCP 的独立 Node 路径和非受管内容保留，并继续验证 cp314 覆盖升级与卸载。基线 URL 和 SHA-256 固定在 `.github/workflows/offline.yml`；本地可通过 `scripts/verify-windows-installer-lifecycle.ps1 -PreviousSetupPath <已校验的旧安装器>` 复用同一验证。

只需要复核 Windows 安装器时，可手动触发 `Offline packages` workflow，并在运行记录中只重跑 Windows job。

### 手动安装

先把包安装到目标环境：

```bash
python3 -m pip install .
```

安装完成后，当前环境会提供这些命令：

- `paper-fetch`
- `paper-fetch-mcp`
- `paper-fetch-install-formula-tools`
- `paper-fetch-install-image-tools`

## 2. 准备配置文件

默认主配置文件由 `platformdirs` 决定：

```text
Linux: ~/.config/paper-fetch/.env
macOS: ~/Library/Application Support/paper-fetch/.env
```

如果你需要 provider API key、自定义下载目录或自定义 `User-Agent`，Linux 可以先
这样准备：

```bash
mkdir -p ~/.config/paper-fetch
cp .env.example ~/.config/paper-fetch/.env
```

macOS 可以向
`~/Library/Application Support/paper-fetch/.env` 写入相同 dotenv 内容；
离线安装时只有显式传 `--user-config` 才会创建或合并该文件，
`--no-user-config` 是默认值。

Elsevier 官方 XML/API 与 API PDF 路线需要从 <https://dev.elsevier.com/> 申请并配置：

```bash
ELSEVIER_API_KEY="..."
```

补充说明：

- 运行时默认读取 `platformdirs` 解析出的用户配置目录下的 `.env`；常见 Linux/XDG 布局为 `~/.config/paper-fetch/.env`，macOS 布局为 `~/Library/Application Support/paper-fetch/.env`
- 仓库内的 `.env` 不会自动加载
- 配置覆盖优先级从高到低为：进程环境、调用方显式 `env_file`（CLI doctor 对应 `--env-file`）、`PAPER_FETCH_ENV_FILE` 指向的文件、platformdirs 用户配置、代码默认值。同一个文件同时由显式参数和环境变量指定时只读取一次，并按显式层报告。
- 如果要显式指定配置文件，请设置：

```bash
PAPER_FETCH_ENV_FILE=/path/to/.env
```

完整变量说明见 [`providers.md`](providers.md)。

## 3. 可选：安装公式后端

公式后端用于源 TeX 校验和 MathML 转换；缺失时主抓取链路仍可运行。

公式工具提供 MathJax 校验与本地字形；源 TeX 保真、转换及失败回退语义见
[提取规则](extraction-rules.md#rule-formula-latex-normalization)。

### 独立 Markdown 公式审阅

公式审阅使用显式指定的 LitRoot checkout 及其已安装依赖，从 `src/shared/markdown-math.mjs` 加载与阅读器相同的同步 MathJax 4.1.3 引擎、本地 SVG 字形和扩展，不访问 CDN：

```bash
node scripts/review_markdown_math.mjs --modules-root /path/to/LitRoot --output report.json paper.md
```

可传多个 Markdown 文件；省略 `--output` 时向 stdout 输出 JSON。报告顶层 `mathjax` 是引擎版本，`extensions` 列出预载扩展；每篇文档独立维护宏和诊断，保留公式计数、位置、源表达式、相对资产和定界符候选。`warnings` 保留为空数组；解析、编译或排版失败时每条公式只记录一次错误，退出码为 1，无错误时为 0。阅读器只在失败公式处显示源 TeX 和错误提示，其余正文继续渲染。

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
- `./install-formula-tools.sh` 会把工具装到当前仓库的 `./.formula-tools/`
- 如果只想安装公式工具但跳过 Node fallback，可给仓库脚本加 `--no-node`
- 运行时可用 `PAPER_FETCH_FORMULA_TOOLS_DIR` 覆盖公式工具查找目录；默认会考虑 repo-local `.formula-tools` 和用户数据目录下的 `formula-tools`
- `src/paper_fetch/resources/formula/package.json` / `package-lock.json` 是公式 Node 依赖的唯一 manifest 与 lockfile；直接依赖包括 `mathml-to-latex` 和固定 4.1.3 的 MathJax／字体包。安装器检查完整 Node 依赖，离线构建执行转换及 bbm/textcomp 排版 smoke test。

### 可选图片转换后端

AMS 页面 `Download Figure` 常提供 EPS 或 TIFF 源图；运行时会优先保存这些源图，并用 Ghostscript/libvips 转成 PNG 供 Markdown 本地图片使用。缺少后端时，资产下载会继续尝试网页 full-size JPG/PNG 候选。

已安装环境推荐执行：

```bash
paper-fetch-install-image-tools
```

当前仓库 repo-local 开发可执行：

```bash
./install-image-tools.sh
```

补充说明：

- `paper-fetch-install-image-tools` 会把可用工具装到用户数据目录，更适合部署环境
- `./install-image-tools.sh` 会把工具装到当前仓库的 `./.image-tools/`
- 运行时可用 `PAPER_FETCH_IMAGE_TOOLS_DIR` 覆盖图片工具查找目录；默认会考虑 repo-local `.image-tools` 和用户数据目录下的 `image-tools`
- `PAPER_FETCH_GHOSTSCRIPT_BIN` 可显式指定 Ghostscript 可执行文件；`PAPER_FETCH_VIPS_BIN` 可显式指定 libvips `vips` 可执行文件
- `PAPER_FETCH_EPS_DPI` 控制 EPS 转 PNG 的 Ghostscript 输出 DPI，默认 `600`
- `PAPER_FETCH_IMAGE_TOOL_TIMEOUT_SECONDS` 控制 Ghostscript/libvips 探测与转换子进程超时，默认 `120`
- 运行时会按相关 env、目录和候选文件指纹缓存 Ghostscript/libvips 候选与 `--version` 探测结果；批量下载多张 EPS/TIFF 源图时不会为每张图重复探测同一工具

### 静态诊断与 live 边界

安装或修改配置后，可以先运行无网络诊断：

```bash
paper-fetch doctor --json
paper-fetch doctor --provider elsevier --detail full --json
paper-fetch doctor --group browser --detail compact
```

`doctor` 与 MCP `provider_status` 共用同一静态诊断：检查 provider 配置、配置来源、Playwright/Camoufox 和 Ghostscript/libvips，但不启动浏览器、不请求出版社页面，也不自动安装依赖。配置部分只输出变量名、来源层和是否存在，不输出 token、cookie、endpoint、文件路径或其它值；可保存 JSON 供部署排查。

`full` 保留 provider checks 和本地能力；`compact` 只保留路由所需的状态、关键 reason 与建议动作。

离线 manifest 记录项目版本、source SHA、目标平台与 ABI，并以 skill bundle schema 2
记录完整文件列表、逐文件 SHA-256 与内容摘要。安装器在复制前后校验安装根与三个
宿主 skill，缺失、多余、链接或摘要不符均无法通过完整性验收。

Codex 用户级 skill 安装到 `~/.agents/skills/paper-fetch-skill`，项目级安装到项目 `.agents/skills/paper-fetch-skill`；Windows 用户级对应 `%USERPROFILE%\.agents\skills\paper-fetch-skill`。安装目录遵循 [OpenAI skill 指导](https://learn.chatgpt.com/docs/build-skills)，不由 `CODEX_HOME` 决定；MCP 配置位置沿用现有契约。安装和卸载仅处理当前 skill 路径，user/project scope 不互相清理。离线安装器仅处理其既有用户 scope。

源码安装或升级后可运行 `./scripts/install-codex-skill.sh --check` 检查 Codex user scope，或加 `--project --check` 检查仓库 `.agents/skills/paper-fetch-skill`。该模式严格只读，不安装包、不复制/建目录、不注册或注销 MCP、不写配置/日志；`0` 表示精确同步，`1` 表示缺失或漂移，`2` 表示参数用法冲突。离线安装器会在复制前后及三个宿主目标上 fail closed 验证 Skill，完成后重启 Codex、Claude Code 和 Antigravity 使宿主重新扫描已验证的 skill/MCP。

排查本地配置使用 `doctor` / `provider_status`；检查站点访问使用 CLI 或 MCP `browser_preflight`；需要登录或人工验证时运行 `paper-fetch auth <provider>`。live 步骤会访问网络，并复用[原生 profile](browser-backends.md)，与 auth、fetch 共用持久目录。两种 preflight 入口共用 HTML 核心，均在实际启动前自动准备 managed runtime，不运行 PDF fallback 或自动 auth。静态 `ready` 只表示本地能力可用；站点访问由实际请求验收。

### CI / GitHub Actions

| 入口 | 验证与产物 |
| --- | --- |
| `ci.yml` → `verify.yml` | 锁文件新鲜度、全 extras 漏洞审计、Ruff/mypy/版本、完整 unit/integration、Python 3.11/3.14 的 core/full 安装、原生 macOS 15 / CPython 3.14 gate |
| `package.yml` | 同一不可变 SHA 的 wheel/sdist exact archive 检查，以及各自在独立环境中的 CLI/MCP/import/resource/skill smoke |
| `offline.yml` | Linux x86_64 和 macOS arm64 的 CPython 3.11–3.14、Windows x86_64 CPython 3.14；原生 build/install/upgrade/uninstall 验证 |
| `release.yml` | 与项目版本一致的 `v*` tag 或明确手动发布；冻结九目标依赖、构建并核验 staging manifest/SBOM/evidence，再发布九个安装包和九条记录的 `SHA256SUMS` |

Release 不运行或等待普通 CI。wheel、sdist、merged dependency manifest、SBOM 和
sidecar evidence 只用于构建期验证，不进入稳定版公开下载集合；资产集合由 workflow、
installer manifest 和 `prepare_release_assets.py` 维护，拒绝缺失、多余和 basename collision。
中文 Release Notes 只取 `CHANGELOG_CN.md` 对应版本章节。

普通 CI 使用 `uv.lock` 和共享 setup action；Dependabot 是兼容依赖更新入口。
发布解析工具范围为 `pip>=26.1.2,<27`、`packaging>=26.2,<27`。第三方 actions 固定
完整 SHA；artifact 上传和 attestation/publication 前必须通过各步骤指定凭据的
`scan_artifacts_for_secrets.py` 扫描，覆盖 raw/URL-encoded 值，只报告变量名和路径。
原生 Camoufox 准备可向上游 CLI 传只读 `GITHUB_TOKEN`，不写入 cache/artifact。

Live publisher/MCP 和完整 golden 仅在本地显式执行。普通 unit/integration/golden
沿用 pytest 并行配置；只有 live 或依赖共享外部状态的检查按其契约串行。
Linux/WSL 先用项目 Python 执行 `scripts/validate_macos_adaptation.py`，再执行
`scripts/test-macos-contract.sh`；Windows 对应 `.ps1`。`/mnt/*` 仅可作静态验证，
Mach-O、Zsh、xattr、Gatekeeper 与原生安装须由相应平台提供证据。

Integration CI 使用现有公式安装器准备 texmath 与 Node 后端，再运行真实进程契约测试。
CI setup、工具链版本和重试细节分别以 `.github/actions/`、workflow 与安装脚本为准。

<a id="release-checklist"></a>
### 发布前检查

1. 在 `pyproject.toml` 定稿版本，更新中英文 changelog。运行
   `uv lock`、`uv run python scripts/sync_version.py --write` 和 `--check`；提取语义变化时
   更新现有 extraction revision，并验证缓存修订号检查，保留 fixture 的采集记录。
2. 对候选运行 `scripts/dev-preflight.sh --with-golden`，覆盖完整并行 unit、integration、
   golden、格式、lint、mypy 和版本同步；另执行 `uv lock --check` 与锁定依赖审计。
3. `uv build` 后用 `scripts/verify_python_distribution.py --wheel ... --sdist ...`
   检查归档；分别安装 wheel/sdist，验证 core/full、CLI 版本、MCP server、资源和 skill。
4. 把已验证内容固定到一个提交。候选分支可手动运行现有 `ci.yml`、`offline.yml`，
   完成上表原生门禁；这两个 workflow 不发布稳定 Release。候选准备提交使用 `[skip ci]`，
   需要这些远端验证时显式执行 workflow。修复后必须以新的同一 SHA 重新验证受影响产物。
5. 仅在发布操作已获授权、前置验证通过后创建 `v<version>`。`release.yml` 将 lightweight
   或 annotated tag peel 到完整 SHA，构建/attestation/最终 checkout/发布全部使用该 SHA，
   发布前再次确认远端 tag 未移动。候选验证成功本身不等于已公开发布。

平台安装验证的具体安全边界见 [离线包](#离线包)；Windows 必须验证最终 EXE 的
覆盖升级、用户内容保留及卸载残留树，macOS 必须验证四个 ABI 的原生 tarball。

本地清理构建、测试缓存和 rollout 日志时可以用：

```bash
scripts/clean-local-artifacts.sh --dry-run
scripts/clean-local-artifacts.sh --days 7
```

该脚本只删除 `git check-ignore` 确认为 ignored 的目标；未被 `.gitignore` 覆盖的路径会跳过。

## 4. Provider 接入入口与本地运行时

provider 路由、付费墙终态、browser readiness、PDF 恢复与环境变量统一见
[providers.md](providers.md)。静态 `ready` 仅证明本地能力，不能代替真实获取验收。
浏览器 runtime、显式准备和人工认证命令见 [browser-backends.md](browser-backends.md)。

安装器和离线包不会内置浏览器 binary；首次 browser launch 保留 managed
runtime 自动准备机制。进入受限网络前需显式预置并验证。Ghostscript/libvips 的原生
依赖和 macOS 验证范围见 [macOS 适配说明](#macos-适配与证据边界)。

## 5. 部署到 Codex

最常用流程：

```bash
./scripts/install-codex-skill.sh --register-mcp
```

这个脚本会：

- 安装当前包
- 复制静态 skill bundle
- 在显式传入 `--register-mcp` 时注册 `paper-fetch` MCP server
- 注册 Codex MCP 时直接使用当前 `python3` 解释器启动 `paper_fetch.mcp.server`
- 如需有窗口浏览器，可设置 `PAPER_FETCH_BROWSER_HEADLESS=false`

常用选项：

- `--project`
- `--env-file <path>`
- `--mcp-name <name>`

## 6. 部署到 Claude Code

最常用流程：

```bash
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

Codex CLI 可手动注册同一个 stdio server：

```bash
codex mcp add paper-fetch -- python3 -X utf8 -m paper_fetch.mcp.server
```

如果配置文件不在进程环境里，额外设置：

```bash
PAPER_FETCH_ENV_FILE=/path/to/.env
```

当前 MCP server 适合挂到支持 stdio MCP 的 host。

常用抓取参数的默认模式、`artifact_mode`、`prefer_cache`、`no_download` 和 `save_markdown` 语义见 [`providers.md`](providers.md#mcp-download-and-markdown-save)。

## 8. 更新方式

官方 release 包运行 `paper-fetch update`，具体行为见“离线包”小节。源码或 pip 安装环境运行该命令时只提示原有更新命令，返回 `1`。源码或在线安装的更新方式如下。

更新当前仓库版本时，进入原来的 Python 环境后重新安装即可：

```bash
python3 -m pip install --upgrade .
```

源码开发环境执行 `uv sync --frozen --extra dev --extra full`；在线
安装应使用上面的 `--upgrade` 命令。安装完成后可用
`python3 -c "from importlib.metadata import version; print(version('mcp'))"`
确认主版本为 2，并重启所有已经运行的 MCP host。

如果你还在使用 Codex 或 Claude Code，推荐顺手重跑对应安装脚本，让 skill 和 MCP 一起更新：

```bash
./scripts/install-codex-skill.sh --register-mcp
./scripts/install-claude-skill.sh --register-mcp
```

## 9. 最小验证步骤

需要验证实际获取时可运行（会访问网络）：

```bash
paper-fetch fetch --query "10.1186/1471-2105-11-421"
```

CLI 默认打印 Markdown 到终端；如果指定 `--output-dir` 且未显式传 `--output`，主输出会用安全化论文 stem 加 `.md`、`.json` 或 `.both.json` 后缀写入该目录，正文不会打印到终端。完整输出、artifact、资产下载和错误码语义见 [`cli.md`](cli.md)。

源码 checkout 使用锁定的开发与完整依赖，再运行本地门禁：

```bash
uv sync --frozen --extra dev --extra full
bash scripts/dev-preflight.sh
```

源码检查使用上述项目环境。
preflight 优先使用 `.venv/bin/python`，没有时退回 `python3`，可通过
`PYTHON_BIN=/path/to/python` 显式选择已准备好的解释器。它检查格式、lint、完整生产包
mypy、版本一致性及完整 unit＋integration。`--fast` / `--skip-integration` 跳过
integration，`--skip-typecheck` 跳过 mypy。发布前使用 `--with-golden`，它与
`--fast` / `--skip-integration` 互斥。

独立测试命令、默认并行配置和证据分层统一见 [测试说明](../tests/README.md)，
CI 平台门禁见 [CI / GitHub Actions](#ci--github-actions)，发布终验见
[发布前检查](#release-checklist)。live 检查只在本地显式执行。

出版社/MCP live 入口及其网络、凭据和结果保存约定见[测试说明](../tests/README.md)。

## 相关文档

- [`../README.md`](../README.md)
- [`docs/README.md`](README.md)
- [`providers.md`](providers.md)
- [`architecture/overview.md`](architecture/overview.md)

## macOS 适配与证据边界

macOS 的机器合同见 [`macos-adaptation-contract.toml`](macos-adaptation-contract.toml)。它只记录长期支持矩阵、安全不变量和原生证据要求；全平台 release 事实继续由 workflow、installer manifest 与 release asset owner 维护。

### 支持范围

- 在线安装遵循 `pyproject.toml` 的 Python 版本范围。
- 离线安装包只面向 Apple Silicon；具体 CPython 矩阵和 runner 由 `.github/workflows/offline.yml` 定义。
- 安装包命名来自 `installer/manifest.json`，公开资产集合由 `scripts/prepare_release_assets.py` 定义。macOS 合同不复制全平台资产数量或依赖清单。
- 稳定发布的源码、离线构建与依赖快照验证工具来自同一个已验证 commit SHA，不支持跨 revision tooling overlay。

### 安全不变量

macOS 使用统一的受管 Camoufox＋Byparr；浏览器和模型可能联网准备，失败保留核心安装，见[浏览器安装与准备](#浏览器安装与准备)。

### 证据等级

- `scripts/validate_macos_adaptation.py` 从项目元数据、workflow、installer manifest 和 release asset owner 读取当前事实并校验合同。
- Windows 与 Linux/WSL contract 入口只提供本地静态和纯 Python 预检查，不属于 CI 平台证据，也不证明 Mach-O、codesign、quarantine、文件模式、大小写或原生浏览器 bundle。
- `.github/workflows/verify.yml` 的原生 macOS gate 提供 CPython 3.14 与浏览器 bundle 证据；`.github/workflows/offline.yml` 覆盖发布矩阵。

本地修改涉及上述边界时，先运行 `python scripts/validate_macos_adaptation.py`，再在当前平台运行对应 contract 入口。原生发布证据只能由 macOS runner 提供。

Codex skill 的 `.agents/skills` 当前路径安装与卸载同样适用于 macOS；Linux portable 验证不替代原生 macOS 安装证据。

`browser.supplementary_index_without_body` 对应的跨平台行为见[补充材料索引](browser-runtime.md#补充材料索引)。

macOS 出版社状态使用原生持久目录；升级保留状态与现有路径覆盖。备份应在浏览器
关闭后执行，外部 Firefox 占用时先正常关闭，不删除原生锁。状态导入、认证重放和
缓存摘要见[浏览器生命周期](browser-backends.md#生命周期)，机器合同仍由
`macos-adaptation-contract.toml` 维护。

### 统一浏览器准备

macOS 的浏览器预置与重试使用[浏览器安装与准备](#浏览器安装与准备)的统一入口；
组件随包 inventory、checksum 与 SBOM 的边界见[受管 Byparr](browser-backends.md#统一受管-byparr)。

## 活动 Codex 配置与接口刷新

Unix 和 Windows 直接注册、卸载共用路径规则：非空 CODEX_HOME 优先，其下 config.toml 为实际目的地；否则使用宿主默认 ~/.codex/config.toml（Windows：USERPROFILE/.codex/config.toml）。安装器打印实际目的地，Codex CLI 可用时仍优先注册；skill 位置保持 ~/.agents/skills/paper-fetch-skill。macOS 的相同规则见 macos-adaptation-contract.toml 的 host_config.codex。

升级后可用受管绝对 wrapper 执行 doctor --catalog --json，查看运行版本、解释器、模块及安装来源。未注册、进程启动失败和宿主目录未刷新分别检查活动配置、启动错误及宿主/MCP 重载。不要从工具命名空间推测 resource server 名：先发现资源，再使用发现结果中的 server 与 URI。

MCP 业务输出为 v4，fetch-envelope sidecar 为 v7；旧缓存按版本不匹配处理，不迁移。CLI manifest 和完整 acceptance 仍为 v2，cache index 仍为 v3。成功与失败完整 diagnostics 使用会话句柄分页读取；CLI 完整证据保留原语义。
