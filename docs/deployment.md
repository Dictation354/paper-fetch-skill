# 部署指南

安装、配置、MCP 注册和升级见下文；7.0 行为变化见 [迁移说明](migration-v7.md)。
provider 差异见 [providers.md](providers.md)，浏览器准备见 [browser-backends.md](browser-backends.md)，
原生 macOS 证据边界见 [适配说明](macos-adaptation-audit.md)。已安装 skill 的独立说明位于
[environment.md](../skills/paper-fetch-skill/references/environment.md) 和
[cli-workflow.md](../skills/paper-fetch-skill/references/cli-workflow.md)。

## 1. 安装 Python 包

默认 `pip install .` 只安装轻量 core。按需要选择 `.[browser]`（Camoufox/HTML）、
`.[pdf]`（PDF 转换）或 `.[full]`（两者）。开发与普通 CI 使用已提交的锁文件：

```bash
uv sync --frozen --extra dev --extra full
```

core 运行时要求 MCP Python SDK 2.x（`mcp>=2,<3`）。server 使用 v2
`MCPServer`，同时兼容 2025 握手协议客户端和 2026-07-28 现代协议客户端；
项目不再支持与 MCP Python SDK 1.x 共装。

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
- 安装 Python 依赖、外部公式后端和图片转换后端；源码在线安装入口不下载 Camoufox 浏览器 binary；browser route 启动前保留运行时自动准备机制
- 安装结束时提示 Elsevier 官方 API key 的申请入口和配置位置；抓取 Elsevier 全文前需要从 <https://dev.elsevier.com/> 申请并设置 `ELSEVIER_API_KEY`

补充说明：

- 这是在线一键安装入口：用户不需要手动准备公式后端；浏览器路径统一由 Camoufox facade 负责。CLI/MCP/library 在实际启动浏览器前自动准备 managed Camoufox；进入受限网络前可显式运行 `python -m camoufox fetch` 预置，再用 `paper-fetch browser-preflight` 验证
- 如果只想安装 Python 包和配置骨架，不准备外部公式或图片转换后端，使用 `./install.sh --lite`
- 如果要装进当前 `python3` 环境而不是 `.venv`，使用 `./install.sh --system`
- arXiv 不需要本地转换器；official HTML 不可用或质量检测失败时直接进入 PDF fallback
- 如果只想跳过公式 Node fallback，可使用 `--no-node`

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

`pyproject.toml` 的大多数依赖保留兼容范围；browser/full extra 使用 `camoufox>=0.5.5,<0.6`，允许后续兼容版本提供新的浏览器能力。`uv.lock` 固定普通开发和 CI 实际使用的版本；POSIX 离线构建不再对 Camoufox 增加单独的 lockfile 精确约束，而是读取依赖 wheelhouse 中唯一 Camoufox wheel 的 METADATA，验证安装后的 distribution 与该版本一致，并在 `offline-manifest.json` 的 `components.camoufox.python_package_version` 记录实际值。quality job 在其它静态门禁之前通过独立的 `Check lockfile freshness` 步骤执行 `uv lock --check`，项目版本、依赖声明或 lock metadata 的陈旧状态会直接令 CI 失败；后续 `uv sync --frozen` 只消费已验证的锁文件，不会在常规运行中重新选择版本。Dependabot 每周为 pip、npm 和 GitHub Actions 更新创建可跟进的 PR；普通 PR 继续由 `verify.yml` 对锁定依赖执行全 extras 漏洞审计。离线 wheelhouse/hash manifest 继续负责跨平台离线资产，不替代开发锁文件。

主包版本号同步清单：

- `pyproject.toml` 的 `[project].version` 是 Python 包和离线构建脚本读取的主版本来源。
- `src/paper_fetch/version.py` 从项目元数据读取版本；`DEFAULT_USER_AGENT` 和 CLI `--version` 由它派生。
- `skills/paper-fetch-skill/references/environment.md` 不写死版本号，只指向运行时 `paper_fetch.config.DEFAULT_USER_AGENT`。
- `scripts/sync_version.py --write` 生成 Inno `AppVersion` 默认值；`--check` 验证安装器和中英文 changelog。
- `tests/integration/test_offline_install.py` 中用于离线安装测试的 runtime fixture 需要与 Linux / macOS 安装脚本的布局保持同步。
- `CHANGELOG.md` / `CHANGELOG_CN.md` 仍人工维护版本章节；发布前的同步检查会拒绝缺失章节。

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

如果要在之后进入受限网络或离线环境，请在仍联网时预置并验证浏览器。普通运行时
会在实际启动浏览器前自动准备 binary，也可以提前显式预置：

```bash
source ~/.local/share/paper-fetch-skill/activate-offline.sh
python -m camoufox fetch
paper-fetch browser-preflight
```

自定义安装目录或未激活 shell 时，下载命令可以改为
`<install>/runtime/paper-fetch-python -m camoufox fetch`。

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
- `activate-offline.sh` 会用包内 Python 和 `python-dotenv` 按 dotenv 语法解析本安装目录的 `offline.env`，或安装时通过 `--reuse-env-file` 绑定的外部文件，再逐个导出合法 env key；不会 `source` 该文件或执行其中的命令替换、函数定义、普通 shell 命令。默认 activate 不再被外层已有 `PAPER_FETCH_ENV_FILE` 改道。

Linux / macOS MCP 注册行为与 Windows 对齐：检测到 `codex` CLI 时执行 `codex mcp remove/add paper-fetch`，没有 CLI 或注册失败时更新 `~/.codex/config.toml` 中的 `mcp_servers.paper-fetch`；检测到 `claude` CLI 时执行 `claude mcp remove/add -s user paper-fetch`，没有 Claude CLI 时只安装 skill 并跳过 Claude MCP 注册；Antigravity 没有 `mcp add` CLI，安装器会把 `paper-fetch` server 合并到 `~/.gemini/antigravity-cli/mcp_config.json` 并保留其它 server。Codex / Claude Code / Antigravity 需要重启后才会重新扫描 skill 和 MCP 配置。

Windows 目标机运行安装器即可：

```powershell
.\paper-fetch-skill-windows-x86_64-setup.exe
```

Windows 安装器默认安装到 `%LOCALAPPDATA%\PaperFetchSkill`，不要求管理员权限。安装器会复制运行组件，写入用户 PATH，复制 Codex / Claude Code / Antigravity skill，并执行 best-effort 基础 smoke check。检测到 `codex` CLI 时会用 `codex mcp remove/add` 注册 MCP；没有 Codex CLI 时会备份并更新 `%USERPROFILE%\.codex\config.toml` 中的 `mcp_servers.paper-fetch`。检测到 `claude` CLI 时会用 `claude mcp remove/add -s user` 注册；没有 Claude CLI 时只安装 skill 并跳过 Claude MCP 注册。Antigravity MCP 写入 `%USERPROFILE%\.gemini\antigravity-cli\mcp_config.json`，并保留其它 server。用户级 skill / PATH / MCP 集成或 smoke check 失败时不会回滚已复制的 runtime，详细警告写入 `%LOCALAPPDATA%\PaperFetchSkill\install-helper.log`；可修正本机环境后手动重跑 `%LOCALAPPDATA%\PaperFetchSkill\scripts\windows-installer-helper.ps1 -Action Install`。

核心安装及 smoke 检查成功后，三平台提供可选配置向导。Linux/macOS 使用终端，`--non-interactive`、无可交互终端或 `--skip-smoke` 时跳过；Windows 使用 Inno 密码输入框和默认未选中的组件选项，`/SILENT`、`/VERYSILENT` 不进入可选阶段。下载、安装均默认关闭，各组件独立选择；可选阶段断网、拒绝、取消、sudo/UAC 或功能验证失败不会回滚核心安装。

- Elsevier API Key 与 Wiley TDM Token 隐藏输入，留空保留旧值，只更新明确填写的 `ELSEVIER_API_KEY` / `WILEY_TDM_CLIENT_TOKEN`。凭据按 dotenv 转义、去重并原子保存，POSIX 文件权限为 `0600`，Windows 使用用户专属 DACL；不会进入命令行、日志或宿主注册参数。`--reuse-env-file` 的外部文件保持只读，向导提供手动配置说明。
- Linux 实际加载 GTK、X11/XCB、音频等共享库；不能确认时报告“未验证”。Debian/Ubuntu 根据当前 APT sources 的候选解析 `t64` 包名，先显示确切清单和命令，再分别询问浏览器系统库、Ghostscript 和 libvips 安装。仅 APT 子进程使用 sudo（由 sudo 收取密码），不刷新软件源、不全系统升级。缺包时给出建议，包锁/权限失败保留现有结果并重新检测；其它发行版仅检测和提示。
- macOS 保持 15+ arm64、CPython ABI、quarantine 和原生验证边界。已有 Homebrew 时可分别安装 `ghostscript`、`vips`，使用实际 prefix 下的绝对路径，无 `sudo brew`；无 Homebrew 时仅提供 [官方说明](https://brew.sh/)，不安装 Homebrew/Xcode/CLT，不清除 quarantine。
- Windows 图片工具固定于 `installer/manifest.json`：已从官方 release 下载并核验 [Ghostscript 10.08.0 x64 EXE](https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/tag/gs10080)、[libvips 8.18.6 x64 all ZIP](https://github.com/libvips/build-win64-mxe/releases/tag/v8.18.6) 的 SHA-256；用户安装时不查询 latest。下载先进入临时目录，摘要通过后才执行或解压；ZIP 拒绝路径逃逸、链接、重复路径及特殊文件，保留完整 DLL 和资源。
- Ghostscript 使用 [官方安装器](https://github.com/ArtifexSoftware/ghostpdl/blob/master/psi/nsisinst.nsi)，可见运行，使用末尾 `/D=<install-dir>\image-tools\ghostscript\<version>`；官方安装器要求管理员权限并写系统注册表。检测 PATH、配置和官方注册位置，优先复用有效工具；目标版本已注册但失效时仅给出修复提示。用户在官方向导更改目录时，以注册及转换验证确认的位置为准，外部目录不归 paper-fetch 清理。libvips 完整解压到 `image-tools\libvips\<version>`。
- 图片工具必须完成真实 EPS/TIFF → PNG 转换、PNG 解码与像素检查，才将绝对路径保存到既有 `PAPER_FETCH_GHOSTSCRIPT_BIN` / `PAPER_FETCH_VIPS_BIN`。版本探测成功不等于转换就绪。Windows 用独立 `optional-tools.json` 记录版本、来源、目录、归属、文件摘要及验证状态，与 release payload 清单分开。
- Camoufox 以普通用户使用既有 channel/pin/cache 准备规则；已有有效版本直接复用，不默认更新。随后只启动本地 `about:blank` 验证，分别报告准备、启动与“站点访问未测试”，不访问出版社、不登录、不保存 provider state。**跳过仅影响本次安装，后续运行时自动准备仍启用**；不代表预置后已验证完全断网的浏览器支持。

Windows 耗时步骤有进度窗口和控制台结果，可用 Ctrl+C 取消当前可选步骤；官方 Ghostscript 向导及 UAC 可直接取消。完成后显示汇总，并写入不含凭据的 `optional-setup-results.txt`。Unix 汇总输出到终端。重启已运行的宿主/MCP 后配置生效。需要重试时可使用安装目录绝对运行时执行 `-m paper_fetch.offline_setup --install-root <install-dir>`（Unix）；Windows 重新运行 EXE 向导。

离线更新：

- Windows：下载新版 `paper-fetch-skill-windows-x86_64-setup.exe` 并直接运行。安装路径和 `AppId` 固定；安装器先备份 `offline.env`，再通过固定版本与摘要的 UninsIS 1.7.0 静默运行同 `AppId` 的既有卸载器，并等待 Inno 的 TEMP 第二阶段删除原卸载器 EXE 后才覆盖新版 runtime-only payload。旧卸载器只移除自身管理的文件，不递归清空目录，因此 `offline.env`、`downloads/` 和其它用户自建文件会保留；UninsIS 的 LGPL 与 provenance notice 随安装器分发，新版 helper 只替换 managed runtime block，并重新写入 PATH、skill 和 MCP 注册。
- Linux：下载与目标机 CPython ABI 匹配的新 `.sh` 后直接运行。默认安装目录固定为 `~/.local/share/paper-fetch-skill`，升级时会备份安装目录内的 `offline.env`，清理既有 runtime payload 和源码/构建残留，把新版 runtime-only payload 复制进去，再写回 `offline.env` 并刷新 shell / skill / MCP managed block。若希望更新时不改动外部 `offline.env`，用 `--reuse-env-file` 指向现有文件；安装脚本不会写入该文件，只会把 shell 启动文件和 Codex fallback config 中的 managed block 替换为新安装目录的 PATH / MCP runtime 路径。
- macOS：在 macOS 15+ arm64 目标机下载或构建与 CPython ABI 匹配的新 tarball，核验 checksum / quarantine 后运行 `install-offline.sh`；更新语义与 Linux 相同，默认固定安装目录同样是 `~/.local/share/paper-fetch-skill`。

```bash
./paper-fetch-skill-offline-linux-x86_64-cp312.sh --preset=headless --no-user-config
./paper-fetch-skill-offline-linux-x86_64-cp312.sh --preset=headless --no-user-config --reuse-env-file /path/to/shared/offline.env
source ~/.local/share/paper-fetch-skill/activate-offline.sh
```

被复用的 `offline.env` 可以保留原 managed block；运行时路径会通过 shell / activate / MCP 进程环境覆盖为新安装目录路径，文件内容只按 dotenv 解析，不当 shell 执行。更新后重启 Codex / Claude Code / Antigravity。

离线卸载：

Windows 正式卸载默认保留可选工具，交互窗口提供默认关闭的清理复选框，静默卸载（包括升级先卸载）始终保留。清理仅接受 `optional-tools.json` 中本向导拥有的版本目录：Ghostscript 校对注册路径和官方卸载器摘要后调用对应可见卸载器；UAC 取消、路径不符或失败时保留并报告位置。libvips 仅删除清单内摘要未变的文件，新增/修改文件保留。清理报告保存为 `optional-cleanup-results.txt`。Linux/macOS 不卸载 APT/Homebrew 工具；任何平台均不清理共享 Camoufox 缓存。

- Windows：在“设置 > 应用 > 已安装的应用”中卸载 `Paper Fetch Skill`，或运行 `%LOCALAPPDATA%\PaperFetchSkill\unins000.exe`。卸载器会删除其管理的 runtime、wrapper、bundled skill 和元数据，删除安装器复制的 Codex / Claude Code / Antigravity skill、用户 PATH 中的安装目录 `bin`，并移除安装器管理的 MCP 注册；`offline.env`、`downloads/` 内用户文件、其它安装根用户内容及用户手写的其它 Codex / Claude / Antigravity 配置会保留。
- Linux：运行 `~/.local/share/paper-fetch-skill/install-offline.sh --uninstall`，自定义目录则运行该目录下的 `install-offline.sh --install-dir <path> --uninstall`。该路径不做 checksum、Python ABI 或 bundle asset 检查，只删除 `~/.codex/skills/paper-fetch-skill`、`~/.claude/skills/paper-fetch-skill`、`~/.gemini/antigravity-cli/skills/paper-fetch-skill`，清理 shell 启动文件、用户配置和 Codex fallback config 中的 installer managed block，并通过可用的 `codex` / `claude` CLI 和 Antigravity `mcp_config.json` 移除 MCP；不会删除固定安装目录、`bin/`、`runtime/`、`offline.env`、`downloads/`，也不会删除用户配置中的非 managed 内容。需要删除固定安装目录时显式运行 `install-offline.sh --purge`。
- macOS：卸载命令与 Linux 相同；如果使用自定义安装目录，运行该目录下的 `install-offline.sh --install-dir <path> --uninstall`。卸载只清理 `~/Library/Application Support/paper-fetch/.env` 的 managed block，保留用户自写内容。`--purge` 会在删除任何用户集成之前拒绝 `/`、HOME 及其祖先、尚未安装的当前 bundle root 等危险目标，并要求目标目录中的 schema 3 `offline-manifest.json` 证明 project / entrypoint 所有权且存在 `runtime/python-bin` 安装标记；校验失败时不会做部分卸载。

离线安装约束：

- Linux / macOS 必须使用标准 GIL CPython，版本、`SOABI` 和架构均须与包名及 `offline-manifest.json` 目标完全匹配；例如 macOS `cp313` arm64 包只能用原生 arm64 CPython `3.13.x` 运行，Rosetta x86_64 Python、free-threaded/debug ABI 会在写入前拒绝
- Linux / macOS 安装器会校验 `offline-manifest.json` 的 `target.platform` 和 `target.arch`；本轮发布的 Mac 包只支持 arm64
- macOS manifest 额外声明 `target.minimum_os_version = "15.0"`；安装器通过系统版本检查确认目标机满足最低版本，并在 shell、skill、MCP 和用户配置写入前完成所有平台、ABI、checksum 与整个 bundle 的递归 quarantine 预检
- Linux / macOS 安装时会把通过 `PAPER_FETCH_OFFLINE_PYTHON_BIN` / `python3` 选中的解释器路径写入 `runtime/python-bin`，后续 `runtime/paper-fetch-python` 私有 launcher、CLI wrapper 和 MCP 都复用该解释器；`bin/` 不暴露通用 `python` wrapper，避免全局 PATH 前置后遮蔽用户自己的 Python
- Windows 安装器固定使用包内 CPython 3.13.13 x64 embeddable runtime；版本、python.org URL 与官方 SHA-256 `8766a8775746235e23cf5aee5027ab1060bb981d93110577adcf3508aa0cbd55` 均来自 `installer/manifest.json`，构建器在解压前校验，目标机不需要预装 Python
- Linux 构建阶段用临时 wheelhouse 把项目和依赖安装进 `runtime/site-packages`，然后只把安装后的 runtime、`bin/` 启动器、公式工具和 skill 放进自解压 `.sh` payload；目标机安装阶段不运行 pip，不包含源码树、`dist/` 或 `wheelhouse/`
- Playwright 和 Camoufox Python 依赖随 Linux / macOS `runtime/site-packages` 和 Windows embedded runtime 分发；Camoufox 浏览器 binary 不随包分发，核心安装和静态诊断不下载，可选向导仅在用户明确选择时下载；fetch、auth 和 preflight 在实际启动浏览器前自动补全或更新 managed runtime。未固定版本时检查所选渠道最新兼容版本，固定时只补全对应版本；更新失败且本地版本有效时提示并继续使用，否则报告准备失败。显式 binary 由用户维护。进入受限网络或离线环境前应在联网阶段运行 `python -m camoufox fetch` 预置 binary，并运行 preflight 做启动/provider 验证。当前验证尚未覆盖预置后真正断网的 Camoufox launch，因此不能宣称完整离线浏览器支持
- Linux `.sh` payload 不包含仓库源码快照和 `tests/` 目录；离线安装目标是运行已打包工具，不在目标机执行项目测试
- Linux、macOS、Windows 离线包都携带原生 texmath 0.13.2，分别位于 `formula-tools/bin/texmath` 和 `formula-tools/bin/texmath.exe`，并将它作为首选公式后端；`mathml-to-latex>=1.8.0,<2.0.0` 和随 Playwright 分发的 Node 作为二级转换回退。项目不随包安装或调用 KaTeX renderer/validator；KaTeX 只描述 LaTeX 规范化的兼容目标。`src/paper_fetch/resources/formula` 是 Node manifest、lockfile 和转换脚本的唯一源码位置；checkout runtime 直接引用它，Python 安装器和离线构建将它暂存到 `formula-tools`。lockfile 当前解析为 `mathml-to-latex` 1.8.0 及其实际传递依赖，unit test 会拒绝声明或解析结果漂移。目标机不编译 texmath，也不运行 `npm install`。CI / release 公式构建固定使用 `haskell-actions/setup` v2.12.0 的完整 SHA、GHC 9.10.3 和 Cabal 3.12.1.0；v2.12.0 随附的 GHCup 0.2.6.2 只更新构建工具链，不改变 texmath 0.13.2、公式入口、安装布局或产物接口。macOS 构建会把非系统 Mach-O dylib 复制到 `formula-tools/lib`，用 `@rpath` / `@loader_path` 重写引用，并对 texmath 与随包 dylib 做 ad-hoc codesign
- Linux / macOS 会配置安装目录内 `image-tools` 作为图片转换工具查找目录；离线构建不会把构建机 PATH 上的 Ghostscript/libvips 符号链接固化进包内。运行时找到 Ghostscript 时可转 EPS，找到 libvips 时可转 TIFF；缺少对应工具时只影响 AMS `Download Figure` 源图转换，网页 JPG/PNG 候选仍可回退
- Linux / macOS 默认写固定安装目录内的 `offline.env`、生成可在 bash/zsh 中 `source` 的 `activate-offline.sh`、复制三份 host skill，并把离线 CLI PATH、工具路径、`PAPER_FETCH_ENV_FILE`、`PYTHONUTF8`、`PYTHONIOENCODING` 等写入当前 shell 启动文件；`offline.env` 的 managed block 写入 `PAPER_FETCH_BROWSER_HEADLESS=true`，不覆盖 Camoufox 生成的 Firefox UA/指纹。只有显式传 `--user-config` 才会把受标记管理的运行时块合并到用户配置；Linux 目标是 `~/.config/paper-fetch/.env`，macOS 目标是 `~/Library/Application Support/paper-fetch/.env`
- Linux / macOS `--install-dir <path>` 只接受不存在、空目录，或同时带 schema 3 ownership manifest 与 `runtime/python-bin` marker 的既有安装目录；拒绝 HOME/祖先、非空未拥有目录及指向它的 symlink。合法升级会清理 `src/`、`tests/`、`wheelhouse/`、`dist/`、`.github/` 等残留，保留安装目录内 `offline.env`，并保留用户配置中非 managed 内容
- Linux / macOS `--reuse-env-file <path>` 会把 `PAPER_FETCH_ENV_FILE` 指向现有文件且不修改该文件；其它 runtime 路径仍由新安装目录写入 shell / activate / MCP 环境，activate 时只做安全 dotenv 解析
- Linux / macOS 写入 shell 启动文件和 Codex fallback config 时会先替换既有受管理 block，重复安装不会重复追加；不修改 `/etc/profile`。macOS 的 `.zshrc` 即使是 symlink 也保持 symlink
- Windows 首次安装会写安装目录内 `offline.env`；升级安装会保留用户已有内容，只替换 managed runtime block。MCP 注册环境固定指向安装目录内 runtime 路径，并设置 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`、`PAPER_FETCH_BROWSER_HEADLESS=true`，不注入 Chrome UA。Linux / macOS 同样把 `MATHML_TO_LATEX_NODE_BIN` 指向包内 Playwright Node
- Windows 安装、升级或手工修改 `offline.env` 后，需要重启 Codex Desktop / Claude Code / Antigravity；已启动的 MCP 服务不会自动继承新写入的 env。
- Windows GUI 安装完成页会提示 Elsevier API key 申请入口和包内 `offline.env` 位置，并提供可选的 Notepad 打开项；silent 安装不会弹出该提示。离线环境抓取 Elsevier 全文前，从 <https://dev.elsevier.com/> 申请 key，并在该文件中填写 `ELSEVIER_API_KEY`
- `--preset=headless` / `--preset=headful` 设置 Camoufox 的 headed/headless 行为

构建离线包：

```bash
scripts/build-offline-package.sh --output-dir dist
```

Windows 构建在 PowerShell 中执行：

```powershell
.\scripts\build-offline-package-windows.ps1 -OutputDir dist
```

**包命名与路径安全。** Linux / macOS 构建脚本会从当前平台、架构和 Python 推导包名；例如 Linux x86_64 上 `PYTHON_BIN=python3.13 scripts/build-offline-package.sh` 会默认生成 `paper-fetch-skill-offline-linux-x86_64-cp313.sh`，原生 Darwin arm64 上会生成 `paper-fetch-skill-offline-macos-arm64-cp313.tar.gz`。显式和 manifest 派生的包名都只能是安全单路径组件。构建根会 canonicalize 并拒绝 `/`、HOME、仓库及其祖先；非空 staging 只有携带匹配仓库、canonical 路径和包名的 `.paper-fetch-offline-staging-owner` 才可清理。临时 wheelhouse/project wheel 位于 owned staging，marker 与临时目录均不进入产物；output dir 不得位于 staging，正式 artifact 先写同目录临时文件再原子 rename，失败不会覆盖已有正式文件。

**平台构建范围。** 构建解释器必须是标准 GIL CPython，架构须与宿主目标一致。macOS 构建只接受 Darwin arm64，并把最低 deployment target 固定为 15.0；Linux / WSL 交叉构建不能充当发布证据。Windows 构建必须在 CPython 3.13 x64 上运行，并按 manifest 下载和校验官方 CPython 3.13.13 embeddable x64 runtime。

**Payload 所有权。** Linux 产物是 shell stub 与压缩 payload 组成的单文件 `.sh` 安装器，macOS 产物是 `.tar.gz` bundle；两者都把项目和依赖安装进 `runtime/site-packages`，预编译 bytecode，并写入私有 launcher 与 paper-fetch 命令启动器。`bin/` 不包含通用 `python` wrapper，payload 不携带源码树或 wheelhouse。离线构建只从 repo-local 可重定位 runtime 暂存 Ghostscript/libvips；macOS 还会实体化 texmath、收集非系统动态库、重写 Mach-O install name 并执行 ad-hoc codesign。Windows 把 Python 包安装进 `runtime/Lib/site-packages`，Inno Setup 安装器只包含 embedded runtime、命令启动器、静态 skill、formula tools、image-tools、installer manifest、Windows helper 和离线元数据；安装后不携带顶层 `src/`、`tests/`、`.github/`、`wheelhouse/`、`dist/` 或 `pyproject.toml`。

**Evidence 所有权。** GitHub Actions 中 POSIX builder 使用 `.venv/bin/python`，Windows builder 使用 `.venv/Scripts/python.exe`，使 evidence generator 复用已锁定并安装 CycloneDX CLI 的开发环境；该控制解释器不进入目标 runtime。三个平台都从最终 staging 生成 `dependency-manifest.json`、经 CycloneDX 工具校验的 `paper-fetch-sbom.cdx.json` 和目标唯一的 `dist/paper-fetch-evidence-<target>.*` sidecar，盘点实际安装的 Python distribution、Node/Playwright、Camoufox、公式/图像/native 文件及 Windows embedded runtime digest。

**可选配置向导的原生验证。** 使用正式发行包，在目标平台分别验证全部跳过、各组件独立选择、
断网或取消、升级和卸载。macOS 覆盖 Homebrew 选择、quarantine 拒绝与 Camoufox 本地启动；
Windows 覆盖凭据输入及实际 DACL、Ghostscript 安装/卸载与 UAC 取消、安装目录变更和注册冲突。
临时 payload、mock 或 Linux portable 检查不能替代对应平台的正式包验证。

图片工具已准备好时，显式指定绝对路径运行真实转换测试；Windows 使用 PowerShell 设置
相同环境变量，分别指向 `gswin64c.exe` 和 `vips.exe`：

```bash
PAPER_FETCH_TEST_GHOSTSCRIPT_BIN=/absolute/path/to/gs \
PAPER_FETCH_TEST_VIPS_BIN=/absolute/path/to/vips \
PYTHONPATH=src uv run python -m pytest tests/integration/test_offline_optional_tools.py -q
```

该测试不下载或安装工具。原生 macOS 浏览器验证沿用
`PAPER_FETCH_RUN_NATIVE_CAMOUFOX_TEST=1`，须事先准备缓存。

**Release 终验。** 操作顺序见 [发布前检查](#release-checklist)。构建、安装、证据与发布
必须对应同一不可变 source SHA，平台和验证器限制如下。

安装器共享配置集中在 `installer/manifest.json`：`skill.name`、`mcp.name`、`mcp.env_keys`、managed block marker 和离线包命名都从这里读取。shell 与 activate 环境变量沿用 `mcp.env_keys`，offline.env 使用其中除 `PAPER_FETCH_ENV_FILE` 外的键；技能展示 metadata 以实际复制的 `skills/paper-fetch-skill/agents/openai.yaml` 为准。Linux / macOS / Windows 离线安装脚本、Windows Inno helper 和离线包构建脚本都使用该 manifest，新增运行时环境变量或调整 managed block 文案时应优先改这里。

验证离线包：

```bash
scripts/verify-offline-package.sh dist/paper-fetch-skill-offline-linux-x86_64-cp311.sh
scripts/verify-offline-package.sh dist/paper-fetch-skill-offline-macos-arm64-cp311.tar.gz
```

上面的验证路径按实际构建出的 `cp311`、`cp312`、`cp313` 或 `cp314` 包名替换。

验证脚本先用 Python `tarfile.data_filter` 安全预检并解包 `.tar.gz`，拒绝 absolute/`..` 路径、多顶层目录、特殊文件与逃逸 link，再执行包内安装器；构建器在 npm smoke 后移除运行时不使用的 `node_modules/.bin` launcher symlink，随后与安装器共同要求 checksum 清单精确覆盖 bundle 中除清单自身外的所有 regular file，并拒绝任何其它 payload symlink。未列出的附加 payload 会在任何用户写入前失败。随后确认 runtime-only 布局，并用 guard 拦截安装阶段的在线/构建命令，使用临时 HOME 和 fake host CLI 验证 skill/MCP、dotenv、命令、公式/图片工具、Camoufox/Playwright Python import、卸载与 purge。原生 macOS 路径固定 `/bin/zsh` 和相对 `.zshrc` symlink，真实覆盖嵌套 quarantine、xattr fail-closed、owned upgrade、用户内容保留与卸载 managed block；purge 无条件拒绝 symlink 入口。执行 native code 前先扫描 quarantine，再用 `file -b`、`lipo -archs`、`otool`、`codesign --verify --strict` 验证精确 arm64、canonical bundle containment、非 symlink regular dependencies、LC_RPATH 与递归闭包，最后启动 Playwright Node `--version`。`/var` 或 `/tmp` 的系统 cache alias 由固定 `macos-15` CI node 验证，不属于 tarball verifier。该 guard 不等于真正断网的 browser launch 测试。

Windows offline job 构建 runtime-only 安装器后，直接对最终 EXE 串行执行 silent install、installed CLI/version/doctor、`provider_status_payload()`、公式工具和 Camoufox/Playwright runtime smoke、同 EXE 覆盖升级、用户数据保留、silent uninstall 及托管内容清理。覆盖升级必须只生成 `unins000.exe`；最终卸载不能只采信首阶段 exit code，而是在 60 秒内同时等到成功日志标记和全部 `unins*.exe/.dat/.msg` 消失，再检查精确残留树。该步骤依赖真实 Inno/HKCU/安装状态，只在原生 `windows-latest` 运行；本地 Linux/WSL 静态契约不能替代它。

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

Elsevier 官方 XML/API 和 PDF fallback 至少需要从 <https://dev.elsevier.com/> 申请并配置：

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

主抓取链路不依赖外部公式后端；只有当你希望公式转换效果更好时，才需要这一步。

即使没有安装外部公式后端，运行时仍会对已经拿到的 LaTeX 做轻量 normalize，例如把 `\updelta` 这类 upright Greek 宏改成 KaTeX 常用宏、把 `\mspace{Nmu}` 改成 `\mkernNmu`、把 MathJax `\unicode{x2A7D}` 这类码点命令改成 KaTeX 可解析符号，并清理外部后端可能产生的空 delimiter / 拆分标识符伪影。外部后端只影响 MathML 到 LaTeX 的转换能力，不是这些 normalize 规则的开关。

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
- `src/paper_fetch/resources/formula/package.json` / `package-lock.json` 是公式 Node 依赖的唯一 manifest 与 lockfile；唯一直接依赖是 `mathml-to-latex`，unit contract 检查 lockfile 根依赖与 manifest 一致且该转换包有解析结果。

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

`doctor` 与 MCP `provider_status` 共用同一静态诊断：检查 provider 配置、配置来源、Playwright/Camoufox 和 Ghostscript/libvips，但不启动浏览器、不请求出版社页面，也不自动安装依赖。配置部分只输出变量名、来源层和是否存在，不输出 token、cookie、endpoint、文件路径或其它值；因此可以保存 JSON 供部署排查，但仍应按敏感运维日志管理。

`full` 保留 provider checks 和本地能力；`compact` 只保留路由所需的状态、关键 reason 与建议动作。

offline manifest schema 3 保留 `version`、`git_revision`、`built_at_utc`、`target.platform` / `arch` / `python_tag` 和 `entrypoint`，并包含 skill bundle schema 2：除 `SKILL.md`、全部 `references/`、canonical `agents/openai.yaml` 等完整 regular-file 列表和逐文件 SHA256 外，还记录路径排序、与 mtime/遍历顺序无关的 `content_sha256` / `content_version=sha256:<digest>`。macOS tarball 还写入 `target.minimum_os_version`。POSIX 与 Windows 安装器会在复制前校验 bundle，在复制后再次校验安装根目录及 Codex、Claude Code、Antigravity 三份 skill；缺文件、多文件、符号链接、special file 或 hash 不一致都会阻止完整性验收。

源码安装或升级后可运行 `./scripts/install-codex-skill.sh --check` 检查 Codex user scope，或加 `--project --check` 检查仓库 `.codex/skills/paper-fetch-skill`。该模式严格只读，不安装包、不复制/建目录、不注册或注销 MCP、不写配置/日志；`0` 表示精确同步，`1` 表示缺失或漂移，`2` 表示参数用法冲突。离线安装器会在复制前后及三个宿主目标上 fail closed 验证 Skill，完成后重启 Codex、Claude Code 和 Antigravity 使宿主重新扫描已验证的 skill/MCP。

部署排查顺序为：`doctor` / `provider_status` 静态检查 → 对 browser provider 运行 CLI 或 MCP `browser_preflight` 做真实页面预检 → 只有返回 challenge/auth required 或实际抓取明确需要时，才由用户运行 `paper-fetch auth <provider>`。live 步骤会访问网络，preflight 默认可能更新 provider storage-state；MCP 可显式设 `save_storage_state=false` 禁止本轮保存。两种 preflight 入口共用 HTML 核心，均在实际启动前自动准备 managed runtime，不运行 PDF fallback 或自动 auth。静态 `ready` 不代表网页当前健康或账号已有访问权，预置后真正断网的 Camoufox launch 仍是公开审计项。

### CI / GitHub Actions

| 入口 | 验证与产物 |
| --- | --- |
| `ci.yml` → `verify.yml` | 锁文件新鲜度、全 extras 漏洞审计、Ruff/mypy/版本、完整 unit/integration、Python 3.11/3.14 的 core/full 安装、原生 macOS 15 / CPython 3.14 gate |
| `package.yml` | 同一不可变 SHA 的 wheel/sdist exact archive 检查，以及各自在独立环境中的 CLI/MCP/import/resource/skill smoke |
| `offline.yml` | Linux x86_64 和 macOS arm64 的 CPython 3.11–3.14、Windows x86_64 CPython 3.13；原生 build/install/upgrade/uninstall 验证 |
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

Windows 构建任务在 checkout 前启用 Git `core.longpaths`，以完整检出保留原始采集文件名的 fixture；该设置仅作用于临时 CI runner。
Integration CI 使用同一固定 Haskell 工具链和现有安装器准备 texmath、Node 公式后端，再运行真实进程契约测试。

<a id="release-checklist"></a>
### 发布前检查

1. 在 `pyproject.toml` 定稿版本，补齐中英文 changelog 与适用迁移说明。运行
   `uv lock`、`uv run python scripts/sync_version.py --write` 和 `--check`；提取语义变化时
   更新现有 extraction revision，并验证旧缓存升级，不改写历史 fixture。
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

安装器和离线包不会内置 Camoufox 浏览器 binary；首次 browser launch 保留 managed
runtime 自动准备机制。进入受限网络前需显式预置并验证。Ghostscript/libvips 的原生
依赖和 macOS 验证范围见 [macOS 适配说明](macos-adaptation-audit.md)。

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
- 注册 Codex MCP 时直接使用当前 `python3` 解释器启动 `paper_fetch.mcp.server`
- 如需 headed browser，可设置 `PAPER_FETCH_BROWSER_HEADLESS=false` 让 Camoufox 可见

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

离线 release 包的更新方式见“离线包”小节。本节只针对源码或在线安装环境。

更新当前仓库版本时，进入原来的 Python 环境后重新安装即可：

```bash
python3 -m pip install --upgrade .
```

使用 MCP SDK 2.x 的源码环境，源码开发环境应重新执行 `uv sync --frozen`；在线
安装应使用上面的 `--upgrade` 命令。安装完成后可用
`python3 -c "from importlib.metadata import version; print(version('mcp'))"`
确认主版本为 2，并重启所有已经运行的 MCP host。

如果你还在使用 Codex 或 Claude Code，推荐顺手重跑对应安装脚本，让 skill 和 MCP 一起更新：

```bash
./scripts/install-codex-skill.sh --register-mcp
./scripts/install-claude-skill.sh --register-mcp
```

## 9. 最小验证步骤

先做一个最小 smoke test：

```bash
paper-fetch fetch --query "10.1186/1471-2105-11-421"
```

CLI 默认打印 Markdown 到终端；如果指定 `--output-dir` 且未显式传 `--output`，主输出会用安全化论文 stem 加 `.md`、`.json` 或 `.both.json` 后缀写入该目录，正文不会打印到终端。完整输出、artifact、资产下载和错误码语义见 [`cli.md`](cli.md)。

如果你在仓库源码目录里做 repo-local 验证，先从 lockfile 同步并激活仓库 `.venv`。不要使用系统 site-packages 代替项目环境；当前项目要求 MCP 2.x，而系统解释器中残留的 MCP 1.x 会在测试收集前产生不兼容。完整 unit 命令复用 `pyproject.toml` 的 xdist 配置：

```bash
uv sync --frozen
source .venv/bin/activate
PYTHONPATH=src uv run python -m pytest tests/unit -q
```

完整本地门和其它分层验证继续使用：

```bash
bash scripts/dev-preflight.sh
PYTHONPATH=src uv run python -m pytest tests/unit/test_cli.py tests/unit/test_service_*.py tests/unit/test_mcp_*.py
PYTHONPATH=src uv run python -m pytest
```

`scripts/dev-preflight.sh` 是显式本地完整门禁入口：优先使用 repo-local `.venv/bin/python`，不存在时退回 `python3`，也可显式设置 `PYTHON_BIN=/path/to/python`。脚本依次运行 `ruff format --check`、`ruff check`、完整生产包 `mypy`、版本一致性、`tests/unit --durations=30` 和 `tests/integration --durations=30`；`--with-golden` 追加完整 `tests/golden`，与 `--fast`、`--skip-integration` 冲突时立即报错；如果缺少 ruff / mypy / pytest，会提示先运行 `scripts/dev-bootstrap.sh` 或指定已安装依赖的解释器。快速迭代可用 `--fast`，需要单独排除 integration 或 type check 时使用 `--skip-integration` / `--skip-typecheck`。

验证分层如下：

- 本地完整门：`scripts/dev-preflight.sh`，包含完整并行 unit、integration、Ruff 和 mypy；发布前必须使用 `--with-golden` 完成三层、版本一致性及既有 build/install 终验。
- 普通默认分支 `push` / `pull_request` CI 门：完整并行 unit、integration、Ruff、完整生产包 mypy、版本/漏洞门禁，以及 Python 3.11/3.14 的 core/full wheel smoke。
- 本地 opt-in 门：live publisher/MCP 和完整 golden corpus 只由开发者通过下文命令显式运行，不配置 GitHub Actions schedule 或 dispatch；offline/release 仍只走相应 dispatch 或 `v*` tag。普通 push/PR 不运行真实 publisher 或认证 browser。

所有常规 pytest 步骤继续复用 `pyproject.toml` 的 xdist 并行配置，不传 `-n 0`。CI 能力与触发边界以当前 workflow 为准。

三层测试各有独立入口，均复用默认并行配置：

```bash
PYTHONPATH=src uv run python -m pytest tests/unit -q
PYTHONPATH=src uv run python -m pytest tests/integration -q
PYTHONPATH=src uv run python -m pytest tests/golden -q
```

默认 pytest 的 `testpaths` 只包含 unit＋integration；显式指定 `tests/golden` 就会执行全部可执行样本，无需环境开关。旧 full/shard 开关及分片逻辑已移除；定向调试使用路径、nodeid 或 `-k`。普通 PR/push 不运行 golden，也不新增 golden workflow。分层边界和证据要求见 [测试说明](../tests/README.md)。

未设置 `PAPER_FETCH_RUN_LIVE=1` 时，`tests/live/test_live_publishers.py` 和 `tests/live/test_live_mcp.py` 应稳定 skip。额外验证 live 时，`arxiv` 不需要 browser runtime；包括 `ams` 在内的 browser-backed provider 先按静态报告中的 `browser_runtime.available` 检查本地能力，再启动 Camoufox 做真实页面预检。pytest 隔离 XDG data/runtime、通用 profile 和所有 provider storage-state；Camoufox 的 browser bundle、版本元数据、字体和默认 addon 则复用隔离前由官方包管理器确认的 dependency cache，避免 live/MCP 子进程重复下载 runtime。每家 provider 的状态仍写入临时 `<provider>-camoufox/storage-state.json`，不会进入该共享 dependency cache。

publisher catalog 不是宽松的全文 smoke：每个已执行样本都请求 `asset_profile=body` 并按默认 provider policy 要求 `acceptance.overall=complete`，同时写出 `live-acceptance.json`。无论 preflight/fetch 成功或失败，每个 provider 都先追加 terminal record；JSON 从 runtime catalog 计算总数、已记录/未记录 provider、已记录结果是否全 complete，以及全 catalog 是否全部执行并 complete。每个 provider 还记录外层 wall time、browser readiness、导航数和逐资产 timing。需要离线或 full-size 验收时，另以公开的两个严格布尔约束运行并读取同一 v2 acceptance。challenge/no-access skip 不会被伪装为全量完成；只有机器可读的 preflight `challenge` / `auth_required`、fetch/MCP `status=no_access`，或成功 metadata fallback 中仅由 `ProviderFailure(NO_ACCESS)` 产生的精确 access-boundary marker，才按合法访问边界 skip。解析失败、空壳、正文不足和其它未知错误仍是 hard failure。非 challenge/auth/cancelled 的 preflight 失败必须保留可读取的隐私安全诊断 artifact。Live fixture 的环境 mapping repr 不显示值；JUnit、acceptance、diagnostics 和待上传目录必须先通过 sentinel 扫描。live 测试依赖共享外部状态和 Camoufox 线程边界，必须串行运行；JUnit 使用与 `record_property` 兼容的 legacy family：

```bash
PAPER_FETCH_RUN_LIVE=1 PAPER_FETCH_LIVE_ARTIFACT_DIR=failures/live-publishers \
  PYTHONPATH=src uv run python -m pytest \
  tests/live/test_live_publishers.py tests/live/test_live_mcp.py \
  -q -n 0 -o junit_family=legacy \
  --junitxml=failures/live-publishers.xml
```

普通 publisher/MCP live tests 只保留上述本地入口，不由 GitHub Actions 定时或手动触发。只有在具备相应出版社访问授权和凭据的本机网络环境中才应运行；JUnit 和诊断目录也由本地操作者自行保存。

`failures/` 已被 Git 忽略；live 输出属于一次性、本机和外部状态相关的运维证据，不作为仓库 fixture，也不得用 `git add -f` 提交。确需在仓库外长期归档一次运行时，最小记录为 JUnit 与 `live-acceptance.json`；IEEE 专项再保留 `asset-hashes.json`。原始全文、图片和页面诊断只在排查对应失败所需的期间保留。

需要验证 AIP 冷启动 HTML 稳定性时，额外显式启用五个隔离 profile 的串行测试；每次都必须得到 `aip_html` 与完整 acceptance，不能以 `aip_pdf` 降级通过：

```bash
PAPER_FETCH_RUN_LIVE=1 PAPER_FETCH_RUN_AIP_COLD_STABILITY=1 \
  PAPER_FETCH_LIVE_ARTIFACT_DIR=failures/aip-cold-start \
  PYTHONPATH=src uv run python -m pytest \
  tests/live/test_live_publishers.py::test_aip_cold_start_stability_uses_html_for_five_fresh_profiles \
  -q -n 0
```

该测试依赖同一远端 publisher lane 和本机 Camoufox runtime，必须使用 `-n 0`；失败诊断写入显式本地 artifact 目录。它不由 GitHub Actions 启用，不影响普通 push/PR CI。

IEEE 大型 GIF 资产专项与普通 publisher suite 分离；未确认 runner 具备合法 Xplore 访问上下文时不得启用。在获授权的隔离 runner 上显式运行：

```bash
PAPER_FETCH_RUN_LIVE=1 PAPER_FETCH_RUN_IEEE_BROWSER_LIVE=1 \
  PAPER_FETCH_LIVE_ARTIFACT_DIR=failures/live-ieee-protected \
  PYTHONPATH=src uv run python -m pytest \
  tests/live/test_live_ieee_protected.py -q -n 0 \
  -o junit_family=legacy --junitxml=failures/live-ieee-protected.xml
```

该专项要求统一 `acceptance.overall=complete`、13 个正文资产全部为 `full_size`，目标大型 GIF 有有效 header、可解析且非零的尺寸，并由生成的 Markdown 使用本地路径引用。测试保持 direct-first：本轮 direct 成功时接受 `final_fetcher=direct_http`；只有 direct 失败并进入恢复时，才硬性核对 Camoufox backend 以及 `direct(403) -> browser` trace。每次 `run-*` 目录会保存 `asset-hashes.json`，其中包含目标 SHA-256、全部正文资产 size/hash、fetcher/recovery trace 和 acceptance。该模块同样只保留本地入口；授权操作者按上述最小证据边界在仓库外保存 JUnit、`live-acceptance.json` 和 `asset-hashes.json`。

专项 preflight 若在 15 秒 readiness 窗口后仍停留于 AWS WAF HTTP 202 页面，会保留页面关闭前采集的脱敏诊断并以 `aws_waf_challenge` skip；这代表当前网络/会话仍未取得文章 DOM，不可解释为已成功访问。只有后续抓取和上述资产硬门全部通过，才可关闭 PF-LIVE-007。

## 相关文档

- [`../README.md`](../README.md)
- [`docs/README.md`](README.md)
- [`providers.md`](providers.md)
- [`architecture/overview.md`](architecture/overview.md)
