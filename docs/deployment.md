# 部署指南

这份文档解决：

- 如何安装 `paper-fetch-skill`
- 如何准备配置文件
- 如何注册 MCP server
- 如何做最小化验证和更新

这份文档不解决：

- provider 差异、路由规则和限速语义
- Wiley / Science / PNAS / AMS / Annual Reviews / Royal Society Publishing / ACS / IOP / AIP / MDPI / Taylor & Francis Online 的浏览器运行时细节
- 架构实现细节

provider 运行时细节见 [`providers.md`](providers.md)，架构说明见 [`architecture/overview.md`](architecture/overview.md)。安装 skill 内部的自包含环境/离线 wrapper 说明见 [`environment.md`](../skills/paper-fetch-skill/references/environment.md)，正常 CLI 主路径见 [`cli-workflow.md`](../skills/paper-fetch-skill/references/cli-workflow.md)；这些 reference 不依赖安装包外的仓库 `docs/`。macOS 支持与跨平台证据边界另见 [`macos-adaptation-audit.md`](macos-adaptation-audit.md)。

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
- 安装 Python 依赖、外部公式后端和图片转换后端；不在安装阶段下载 Camoufox 浏览器 binary，真实 CLI browser 路径默认首次按需准备
- 安装结束时提示 Elsevier 官方 API key 的申请入口和配置位置；抓取 Elsevier 全文前需要从 <https://dev.elsevier.com/> 申请并设置 `ELSEVIER_API_KEY`

补充说明：

- 这是在线一键安装入口：用户不需要手动准备公式后端；浏览器路径统一由 selected-browser facade 负责。CLI 首次 browser fetch/auth/preflight 可显示进度并按需准备 managed Camoufox；MCP/库默认关闭该联网行为。进入受限网络前仍建议显式运行 `python -m camoufox fetch`，再用 `paper-fetch browser-preflight` 验证
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

CI 自动发布规则：

- 普通 `push` / `pull_request` 运行完整 unit、branch coverage、focus coverage
  失败门禁、integration、devtools、全部可执行 exact replay 的四个 provider shard、完整包
  mypy、Ruff、复杂度预算、锁定依赖漏洞审计，以及 Python 3.11/3.14 的
  core/full wheel smoke。
- `provider-canary.yml` 每周两次只运行 `quality/public-direct-canary.json`
  声明的公开、无凭据、direct HTTP route。报告与按 route 连续失败状态作为 artifact/cache
  保留；前两次失败不告警，第三次及以后输出 workflow warning，成功清零。这个 job
  `continue-on-error`，不替代普通 CI 的确定性 replay，也不运行 browser/auth route。
- `offline.yml` 是可复用且可手动运行的 full 离线构建 workflow；Linux 使用 CPython 3.11–3.14，macOS 在固定 `macos-15` arm64 runner 使用 CPython 3.11–3.14，Windows 使用 CPython 3.13。
- 推送与 `pyproject.toml` 版本一致的 `v*` tag 时，`release.yml` 把 tag peel 到完整 commit SHA，并以该 SHA 并行构建 wheel/sdist 和九目标冻结依赖；随后在构建期验证 inventory、merged dependency manifest、每目标 staged dependency manifest/CycloneDX SBOM、target evidence 与 attestation 输入。Release 不运行或等待普通 CI，发布操作者须在创建正式标签前本地运行完整并行 unit。发布前从构建清单与 release asset owner 读取 exact set，拒绝 missing/extra/basename collision；稳定版只把九个安装包和含九条记录的 `SHA256SUMS` 复制到公开目录。wheel、sdist、inventory、merged manifest、SBOM 与 target evidence 不进入公开下载接口。稳定版只截取 `CHANGELOG_CN.md` 中与项目版本匹配的章节作为中文 Release Notes，不使用 GitHub 自动生成说明。
- `rolling-release.yml` 每日解析最新稳定版的九目标 full 依赖矩阵；源码或运行时 wheel 集合变化时，复用 `offline.yml` 的冻结 wheelhouse 构建并覆盖 `dependency-latest` prerelease。
- `offline.yml` 会在固定 `macos-15` 上使用 CPython 3.11、3.12、3.13、3.14 矩阵构建 arm64 macOS tarball；四个包都先运行原生 verifier，再上传逐 Python 版本 artifact，缺少产物会直接令 job 失败。
- 所有第三方 GitHub Actions 固定到完整 commit SHA；发布 job 才单独提升 `contents`、`id-token` 与 `attestations` 权限。

#### 锁定依赖与定期刷新

`pyproject.toml` 的大多数依赖保留兼容范围；browser/full extra 使用 `camoufox>=0.5.5,<0.6`，允许后续兼容版本提供新的浏览器能力。`uv.lock` 固定普通开发和 CI 实际使用的版本；POSIX 离线构建不再对 Camoufox 增加单独的 lockfile 精确约束，而是读取依赖 wheelhouse 中唯一 Camoufox wheel 的 METADATA，验证安装后的 distribution 与该版本一致，并在 `offline-manifest.json` 的 `components.camoufox.python_package_version` 记录实际值。quality job 在其它静态门禁之前通过独立的 `Check lockfile freshness` 步骤执行 `uv lock --check`，项目版本、依赖声明或 lock metadata 的陈旧状态会直接令 CI 失败；后续 `uv sync --frozen` 只消费已验证的锁文件，不会在常规运行中重新选择版本。每周 `dependency-refresh.yml` 执行 `uv lock --upgrade`、full unit 和漏洞审计；发现兼容更新时产生 notice，但不自动提交或推送。离线 wheelhouse/hash manifest 继续负责跨平台离线资产，不替代开发锁文件。

#### 滚动依赖预发布

除固定版本 Release 外，`rolling-release.yml` 维护 tag 固定为 `dependency-latest` 的滚动 prerelease，Release 标题同时标注当前稳定源码 tag。它始终以 GitHub 最新稳定 `v*` Release 的源码为基线，分别解析 Linux x86_64 CPython 3.11–3.14、macOS arm64 CPython 3.11–3.14 和 Windows x86_64 CPython 3.13 的 `full` extra 直接及传递运行时依赖。

- 每日任务先生成九份带 wheel 文件名和 SHA256 的依赖快照，合并后与现有 `dependency-manifest.json` 比较。稳定源码 commit 或任一运行时 wheel 变化时才调用可复用 `offline.yml`，所有构建先校验冻结快照，再通过 `PIP_NO_INDEX` / `PIP_FIND_LINKS` 消费同一组 wheel。
- 发布精确包含九个离线安装包、`dependency-manifest.json` 和 `SHA256SUMS`。固定 tag 会移动到最新稳定源码 commit，Release 保持 `prerelease=true`、`make_latest=false`，不会替代稳定版 latest。
- 滚动 prerelease 的 Release Notes 也只保留中文，记录稳定源码、项目版本、依赖集合摘要、刷新原因和更新时间。
- 现有 Release 缺少资产、资产集合异常、manifest/checksum/digest 校验失败时，基线会被视为无效并自动全量重建；`workflow_dispatch` 的 `force_refresh=true` 可显式强制重建。
- tag 移动和 Release 覆盖使用仓库 secret `ROLLING_RELEASE_TOKEN`；该 fine-grained PAT 只应授权本仓库所需的 Contents/Workflows 写权限。其余解析、比较和离线构建任务继续使用只读的内置 token。
- `dependency-latest` 是可变版本，只适合获取最新兼容依赖。需要长期可复现安装时应使用不可变的稳定 `v*` Release。

主包版本号同步清单：

- `pyproject.toml` 的 `[project].version` 是 Python 包和离线构建脚本读取的主版本来源。
- `src/paper_fetch/version.py` 从项目元数据读取版本；`DEFAULT_USER_AGENT` 和 CLI `--version` 由它派生。
- `skills/paper-fetch-skill/references/environment.md` 不写死版本号，只指向运行时 `paper_fetch.config.DEFAULT_USER_AGENT`。
- `scripts/sync_version.py --write` 生成 Inno `AppVersion` 默认值；`--check` 验证安装器和中英文 changelog。
- `tests/unit/test_offline_install.py` 中用于离线安装测试的 runtime fixture 需要与 Linux / macOS 安装脚本的布局保持同步。
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

如果要在之后进入受限网络或离线环境，请在仍联网时显式准备并验证浏览器。虽然
CLI live 入口默认也能按需准备，但预置可把联网副作用留在可控阶段：

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

Windows 安装器默认安装到 `%LOCALAPPDATA%\PaperFetchSkill`，不要求管理员权限。安装器会复制运行组件，写入用户 PATH，复制 Codex / Claude Code / Antigravity skill，并执行 best-effort 基础 smoke check。检测到 `codex` CLI 时会用 `codex mcp remove/add` 注册 MCP；没有 Codex CLI 时会备份并更新 `%USERPROFILE%\.codex\config.toml` 中的 `mcp_servers.paper-fetch`。检测到 `claude` CLI 时会用 `claude mcp remove/add -s user` 注册；没有 Claude CLI 时只安装 skill 并跳过 Claude MCP 注册。Antigravity MCP 写入 `%USERPROFILE%\.gemini\antigravity-cli\mcp_config.json`，并保留其它 server。用户级 skill / PATH / MCP 集成或 smoke check 失败时不会回滚已复制的 runtime，详细警告写入 `%LOCALAPPDATA%\PaperFetchSkill\install-helper.log`；可修正本机环境后手动重跑 `%LOCALAPPDATA%\PaperFetchSkill\scripts\windows-installer-helper.ps1 -Action Install`。仓库根目录 `install-offline.ps1` 是 repo-local/旧 Windows 离线 bundle 入口，不作为 release 用户安装入口。

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
- Playwright 和 Camoufox Python 依赖随 Linux / macOS `runtime/site-packages` 和 Windows embedded runtime 分发；Camoufox 浏览器 binary 不随包分发，安装器与静态诊断不下载。CLI `fetch` / `auth` / `browser-preflight` 默认可按需安装、修复和每 24 小时检查更新；`--no-browser-auto-prepare` 或 `PAPER_FETCH_BROWSER_AUTO_PREPARE=false` 可禁止。MCP/库默认禁止，需环境或单次请求 `browser_auto_prepare=true` 开启。进入受限网络或离线环境前仍必须联网预置 binary，并运行 preflight 做启动/provider 验证。当前验证尚未覆盖预置后真正断网的 Camoufox launch，因此不能宣称完整离线浏览器支持
- Linux `.sh` payload 不包含仓库源码快照和 `tests/` 目录；离线安装目标是运行已打包工具，不在目标机执行项目测试
- Linux、macOS、Windows 离线包都携带原生 texmath 0.13.2，分别位于 `formula-tools/bin/texmath` 和 `formula-tools/bin/texmath.exe`，并将它作为首选公式后端；`mathml-to-latex>=1.8.0,<2.0.0`、`katex>=0.18.4,<0.19.0` 和随 Playwright 分发的 Node 作为二级回退及 LaTeX 验证工具。两套 Node manifest 声明相同的可滚动兼容范围，两套 lockfile 则记录当前解析出的 `mathml-to-latex` 1.8.0 与 KaTeX 0.18.4；机器合约和 unit test 会同时拒绝范围、解析结果或双份资源漂移。目标机不编译 texmath，也不运行 `npm install`。CI / release 公式构建固定使用 `haskell-actions/setup` v2.12.0 的完整 SHA、GHC 9.10.3 和 Cabal 3.12.1.0；v2.12.0 随附的 GHCup 0.2.6.2 只更新构建工具链，不改变 texmath 0.13.2、公式入口、安装布局或产物接口。macOS 构建会把非系统 Mach-O dylib 复制到 `formula-tools/lib`，用 `@rpath` / `@loader_path` 重写引用，并对 texmath 与随包 dylib 做 ad-hoc codesign
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

Linux / macOS 构建脚本会从当前平台、架构和 Python 推导包名；例如 Linux x86_64 上 `PYTHON_BIN=python3.13 scripts/build-offline-package.sh` 会默认生成 `paper-fetch-skill-offline-linux-x86_64-cp313.sh`，原生 Darwin arm64 上会生成 `paper-fetch-skill-offline-macos-arm64-cp313.tar.gz`。显式和 manifest 派生的包名都只能是安全单路径组件。构建根会 canonicalize 并拒绝 `/`、HOME、仓库及其祖先；非空 staging 只有携带匹配仓库、canonical 路径和包名的 `.paper-fetch-offline-staging-owner` 才可清理。临时 wheelhouse/project wheel 位于 owned staging，marker 与临时目录均不进入产物；output dir 不得位于 staging，正式 artifact 先写同目录临时文件再原子 rename，失败不会覆盖已有正式文件。构建解释器必须是标准 GIL CPython，架构须与宿主目标一致。本轮 macOS 构建只接受 Darwin arm64，并把最低 deployment target 固定为 15.0；不能在 Linux / WSL 交叉构建充当发布证据。Linux 构建继续输出由 shell stub 和压缩 payload 组成的单文件 `.sh` 安装器，并在安装子进程结束后正常触发 trap 清理临时 payload；macOS 构建输出 `.tar.gz` bundle。两者都会把项目和依赖安装进 `runtime/site-packages`，预编译 bytecode，写入私有 launcher 与 paper-fetch 命令启动器；`bin/` 不包含通用 `python` wrapper，payload 不携带源码树或 wheelhouse。离线构建只会从 repo-local 可重定位 runtime 暂存 Ghostscript/libvips，不会把构建机系统 PATH 的二进制或符号链接打包。macOS 还会实体化 texmath、收集非系统动态库、重写 Mach-O install name 并执行 ad-hoc codesign。Windows 构建必须在 CPython 3.13 x64 上运行，按 manifest 下载并在解压前校验官方 CPython 3.13.13 embeddable x64 runtime，把 Python 包安装进 `runtime/Lib/site-packages`，并只把 embedded runtime、`bin/` 启动器、静态 skill、formula tools、image-tools 目录/启动器、`installer/manifest.json`、`scripts/windows-installer-helper.ps1` 和离线元数据放进 Inno Setup 安装器；安装后的 Windows payload 不携带顶层 `src/`、`tests/`、`.github/`、`wheelhouse/`、`dist/` 或 `pyproject.toml`。GitHub Actions 中 POSIX builder 固定使用 `.venv/bin/python`，Windows builder 固定使用 `.venv/Scripts/python.exe`，使 evidence generator 复用已锁定并安装 CycloneDX CLI 的开发环境；该控制解释器不会被打入目标 runtime。三个平台的 builder 都从最终 staging 生成 `dependency-manifest.json` 和经 CycloneDX 工具校验的 `paper-fetch-sbom.cdx.json`，同时把目标唯一 sidecar 放到 `dist/paper-fetch-evidence-<target>.*`，其中盘点实际安装的 Python distribution、Node/Playwright、Camoufox 状态、公式/图像/native 文件以及 Windows embedded runtime 的 expected/actual digest。

稳定发布对已存在的不可变标签执行手动重跑时，会把 lightweight 或 annotated tag peel 到完整 commit SHA；`package.yml` 从该 SHA 构建并独立安装验证 wheel/sdist，九目标 frozen dependency resolver 与它并行运行。依赖合并后，`offline.yml` 为 Linux cp311–314、macOS arm64 cp311–314、Windows cp313 构建并验证安装包；publish 只等待 tag、Python distributions、merged manifest 与 offline build。Release 自身不运行或等待完整 unit/普通 CI；创建下一正式版本和新标签前，发布操作者必须先在本地运行 `PYTHONPATH=src uv run python -m pytest tests/unit -q`。构建、sidecar、attestation、最终 checkout 和 `gh release --target` 全部使用同一 source SHA，发布前再次确认远端 tag 仍 peel 到该 SHA。受信任的 POSIX tooling ref 只会成套复制 builder、installer、verifier 和 staging evidence generator；Windows tooling ref 则把 Windows builder、evidence generator、原生 EXE lifecycle verifier、installer helper、manifest 和 Inno `.iss` 当成同一不可分割工具集，从同一个完整 SHA 覆盖。这保证用最新工具重建较早稳定源码时，embedded runtime pin、安装内容和卸载 cleanup 规则不会跨版本错配。公式 installer 与其它 Python wheel source 都不属于 copy allow-list。项目业务源码、Python wheel 内容、静态 skill 和版本元数据仍来自同一 commit，manifest 的 `git_revision` 与可选 `tooling_revision` 分别记录两条 provenance。

安装器共享配置集中在 `installer/manifest.json`：`skill.name`、`mcp.name`、`mcp.env_keys`、`env_sets.offline_env_keys`、`env_sets.shell_env_keys`、`env_sets.activate_env_keys`、managed block marker 和离线包命名都从这里读取。Linux / macOS / Windows 离线安装脚本、Windows Inno helper 和离线包构建脚本都使用该 manifest，新增 MCP / offline.env / shell / activate 环境变量或调整 managed block 文案时应优先改这里。

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
- 根目录 `package.json` / `package-lock.json` 与 `src/paper_fetch/resources/formula/package.json` / `package-lock.json` 必须保持公式 Node 依赖版本一致；当前机器合约固定 KaTeX 0.18.4 与 `mathml-to-latex` 1.8.0，`scripts/validate_macos_adaptation.py` 和 `tests/unit/test_formula_package_sync.py` 会阻止声明或 lockfile 漂移。

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
paper-fetch doctor --install-root ~/.local/share/paper-fetch-skill --json
```

`doctor` 与 MCP `provider_status` 共用同一静态诊断：检查 provider 配置、配置来源、Playwright/Camoufox 和 Ghostscript/libvips，但不启动浏览器、不请求出版社页面，也不自动安装依赖。配置部分只输出变量名、来源层和是否存在，不输出 token、cookie、endpoint、文件路径或其它值；因此可以保存 JSON 供部署排查，但仍应按敏感运维日志管理。

`full` 保留 provider checks 和本地能力；`compact` 只保留路由所需的状态、关键 reason 与建议动作。`install_provenance.provenance_scope` 明确区分两种审计：源码 checkout 默认为 `source_development`，比较 source `pyproject.toml`、当前解释器与仓库/active Codex skill，不从 PATH 或环境文件推断并混入旧离线安装根；显式 `--install-root` 或安装包运行时为 `installation`，严格比较 `DEFAULT_USER_AGENT`、offline manifest、runtime metadata、entrypoint 及宿主 skill。PATH 上的 CLI 可作为只读事实显示，但不会在 source scope 中制造无关安装漂移；真正的 source bundle/active skill 不一致仍会降级。

offline manifest schema 3 保留 `version`、`git_revision`、`built_at_utc`、`target.platform` / `arch` / `python_tag` 和 `entrypoint`，并包含 skill bundle schema 2：除 `SKILL.md`、全部 `references/`、canonical `agents/openai.yaml` 等完整 regular-file 列表和逐文件 SHA256 外，还记录路径排序、与 mtime/遍历顺序无关的 `content_sha256` / `content_version=sha256:<digest>`。macOS tarball 还写入 `target.minimum_os_version`。POSIX 与 Windows 安装器会在复制前校验 bundle，在复制后再次校验安装根目录及 Codex、Claude Code、Antigravity 三份 skill；缺文件、多文件、符号链接、special file 或 hash 不一致都会阻止完整性验收。

源码安装或升级后可运行 `./scripts/install-codex-skill.sh --check` 检查 Codex user scope，或加 `--project --check` 检查仓库 `.codex/skills/paper-fetch-skill`。该模式严格只读，不安装包、不复制/建目录、不注册或注销 MCP、不写配置/日志；`0` 表示精确同步，`1` 表示缺失或漂移，`2` 表示参数用法冲突。离线升级后还应从目标安装 runtime 执行带 `--install-root` 的诊断，确认 `install_provenance.status=ready`，再重启 Codex、Claude Code 和 Antigravity，使宿主重新扫描已验证的 skill/MCP。

部署排查顺序为：`doctor` / `provider_status` 静态检查 → 对 browser provider 运行 CLI `paper-fetch browser-preflight`，或 MCP `browser_preflight(browser_auto_prepare=true)`，完成必要的 managed runtime 准备和真实页面预检 → 只有返回 challenge/auth required 或实际抓取明确需要时，才由用户运行 `paper-fetch auth <provider>`。也可先显式执行 `python -m camoufox fetch`，尤其是在即将进入受限网络时。live 步骤会访问网络，preflight 默认可能更新 provider storage-state；MCP 可显式设 `save_storage_state=false` 禁止本轮保存。两种 preflight 入口共用 HTML 核心，均不运行 PDF fallback 或自动 auth；CLI 默认允许 runtime 准备，MCP 默认禁止。静态 `ready` 不代表网页当前健康或账号已有访问权，预置后真正断网的 Camoufox launch 仍是公开审计项。

### CI / GitHub Actions

普通 push/PR 的 `ci.yml` 通过仓库 `uv.lock` 和共享 setup action 安装冻结依赖，并运行：

- Ruff format/lint、完整生产包 mypy、复杂度预算、抽取规则、版本同步与锁定依赖漏洞审计。
- 完整并行 unit suite 和 branch coverage（首阶段全局门槛 82%，高于原 40% 门槛并为当前 branch baseline 留出非零余量）。
- 完整 integration、devtools。
- Python 3.11 / 3.14 的 boundary controller 安装完整测试依赖契约，随后在独立 venv 中分别执行 core 与 full wheel 安装 smoke；core 产物本身不会因测试控制环境而获得可选依赖。
- reusable `package.yml` 从同一不可变 SHA 构建 wheel/sdist；完整 archive 必须与结构化预期一一对应：wheel 只允许源码 `paper_fetch`、唯一规范化 `dist-info` 的必需 metadata/`RECORD` 和声明的 static data-files；sdist 只允许唯一规范化 root、明确顶层构建/许可/README/PKG-INFO、源码、`egg-info` 和 skill。任何未知 top-level、`.data`、package/source/metadata member 都失败；两者分别安装到独立 venv，执行 CLI/import/MCP/resource/skill smoke。普通 CI 的 `verify.yml` 调用该 workflow 生成 Python distributions。
- Ubuntu / Windows portable Mac contract gate，以及固定 `macos-15` arm64、CPython 3.14 的原生 cache-alias test + build + verifier gate；Windows / WSL 静态结果不能替代该 gate。

`dependency-refresh.yml` 每周和手动运行 `uv lock --upgrade`、完整 unit 和漏洞审计，用于发现兼容范围内的新依赖问题，但不回写分支。稳定与滚动发布的临时解析工具同样使用 `pip>=26.1.2,<27`、`packaging>=26.2,<27`，允许兼容更新而不把工作流绑死在单个补丁版本。MCP 调用结果继续校验 structured_content，tools/list 不再发布 outputSchema；图片回归使用包含必需 IHDR 字段的 PNG fixture，避免宽松旧解析器掩盖无效测试输入。Live publisher/MCP、provider drift 与完整 golden corpus 不再配置 GitHub Actions workflow、schedule 或 dispatch，只保留下文记录的本地显式入口；依赖共享外部状态的 live 测试按设计使用 `-n 0` 串行运行，完整 golden corpus 继续复用项目并行配置。常规 CI 的原生 macOS Camoufox 准备会把 workflow 自带的只读 `github.token` 作为上游 CLI 已支持的 `GITHUB_TOKEN` 传入，避免 GitHub Releases 匿名 API 限额阻断 pinned runtime discovery；token 不写入 cache、artifact 或命令参数。`ci.yml` 只调用 reusable `verify.yml`，而普通 CI 与稳定发布各自通过它或直接调用 reusable `package.yml`；`offline.yml` 独立构建 Linux、macOS、Windows full 离线包，macOS 四个 ABI 固定在 `macos-15` 构建并运行原生 tar verifier。`release.yml` 只在稳定版本标签或显式手动发布时运行，在同一 run 并行构建 tagged SHA 的 Python distributions 与冻结九目标依赖，随后消费每目标实际 staging SBOM；它不调用或等待普通 CI。`prepare_release_assets.py` 对构建输入执行 exact-set/collision 检查；稳定发布只公开九个安装包与 `SHA256SUMS`，滚动预发布额外公开 `dependency-manifest.json`，wheel、sdist、inventory、SBOM 与 target evidence 仅在构建期验证。Provider canary、普通 artifact、稳定/滚动 release asset 与 attestation/publication 都以 `scan_artifacts_for_secrets.py` 成功为前置条件；扫描覆盖 raw 与 URL-encoded sentinel，只报告变量名和路径。每个 workflow 扫描步骤通过 `--env-var` 精确列出自身注入的凭据，不会把 `PGPASSWORD` 等无关 hosted-runner 默认环境值自动纳入 artifact 匹配。所有第三方 actions 固定到完整 commit SHA，作为供应链身份锚点而不是包版本声明。

在 Windows / WSL 修改 Mac 相关范围时，先运行
`uv run python scripts/validate_macos_adaptation.py`，再运行
`scripts/test-macos-contract.ps1` 或 `scripts/test-macos-contract.sh`。
`/mnt/*` 下的 WSL checkout 只提供 validator-only 证据；Mach-O、原生 Zsh、
`xattr` 和 Gatekeeper 只能由原生 Mac gate 验证。证据边界见
[`macos-adaptation-audit.md`](macos-adaptation-audit.md)。

本地清理构建、测试缓存和 rollout 日志时可以用：

```bash
scripts/clean-local-artifacts.sh --dry-run
scripts/clean-local-artifacts.sh --days 7
```

该脚本只删除 `git check-ignore` 确认为 ignored 的目标；未被 `.gitignore` 覆盖的路径会跳过。

## 4. Provider 接入入口与本地运行时

`elsevier` 不依赖本地浏览器链路；它只需要官方 API 凭据，并走 `官方 DOI XML/API -> PII XML/API fallback -> 官方 API PDF fallback -> metadata-only`。

`ieee` 不需要 IEEE API key；它走 `direct landing -> selected-browser landing recovery -> direct REST HTML -> selected-browser HTML -> direct HTTP PDF -> selected-browser PDF`。preflight、browser landing、正式 HTML 和资产 seed 都允许页面在最长 15 秒内从初始 HTTP 202/shell 转成文章页，且只有包含当前文章号的 `#article` 才算 ready；单独观察到 REST resource 或其它文章 DOM 不会提前放行。正文 figure/table/formula、multimedia discovery 和 supplementary file 同样 direct-first，只在 `401/403`、HTML challenge 或网络失败时使用所选浏览器；`404/410/429` 不启动浏览器。资产 browser recovery 会让图片和附件 fetcher 串行复用同一篇已就绪论文页的 context/page、最新 cookies 和论文页 Referer，并保持共享 page 不跳转到资产 URL。首次 large 图片恢复会先在同页加载一次对应 preview，再立即请求 large；后续资产复用该预热页，large 最终失败时才把缓存 preview 作为 fallback。公开资产可通过 `browser_backend`、`final_fetcher` 和 `recovery_attempts` 审计 direct/browser/preview 恢复过程。持续存在的 AWS WAF 页报告 `reason_code=aws_waf_challenge`、`status=challenge` 和 provider/legacy 兼容诊断；该链路不自动登录、不处理验证码，也不绕过访问权限。

`wiley`、`science`、`pnas`、`ams`、`annualreviews`、`royalsocietypublishing`、`acs`、`iop`、`aip`、`mdpi`、`tandf` 进入 provider-owned Camoufox browser workflow。完整配置与 headed 预检见 [`browser-backends.md`](browser-backends.md)。是否能拿到全文仍取决于 publisher 访问权限、paywall/challenge 与远端站点行为。

自动过盾失败时，可打开对应 provider 的 headed browser 手动登录/验证：

```bash
paper-fetch auth <provider>
paper-fetch auth wiley --url "https://onlinelibrary.wiley.com/doi/full/10.1111/example"
```

`provider` 来自 browser runtime catalog，例如 `wiley` / `science` / `pnas` / `ams` / `mdpi` / `royalsocietypublishing` / `annualreviews` / `acs` / `iop` / `aip` / `tandf`。未传 `--url` 时打开内置样例文章；传入 `--url` 时打开具体失败文章页。命令强制 headed 模式，打印所选后端的 profile 和 storage-state 路径，终端按 Enter 后保存过滤后的本地 storage-state 并退出，不写 `.env`。AMS 无状态抓取仍会启动浏览器；只有静默 AWS WAF 验证失败时，才需要 `paper-fetch auth ams` 保存人工验证状态。

这些浏览器 HTML route 会在 challenge/paywall 判定前先等待正文 DOM 稳定；如果正文已经可抽取，页面残留的 Cloudflare/challenge 文案不会提前中断 HTML route，最终全文/摘要/降级结论仍由 Markdown 抽取后的 availability 判定负责。

Wiley 的主文档 401/403 需要结合 `browser_runtime_trace.candidates[*].http_access_status_review`
排查。`accepted=true` 只会出现在正文连续稳定、页面 DOI 精确匹配、无 challenge/no-access/
datalayer 阻断并且后续 Markdown/availability 已通过之后；`response_status` 和候选
`status` 仍为真实 401/403。`body_not_ready`、`doi_evidence_missing`、`doi_mismatch`、
`blocking_signal` 或全文抽取失败都会保持 fail closed，并继续下一个 Wiley URL。该
diagnostic 只含脱敏枚举、布尔值和状态，不含 Cookie、Authorization、storage-state 或
原始失败 HTML；无状态复现可显式将 profile/user-data/storage-state 设为空并关闭
`persist_storage_state`，此时 `storage_state_load.used=false` 且不得产生 capability use。

browser workflow 的通用配置：

```bash
export PAPER_FETCH_BROWSER_BACKEND="camoufox"
export PAPER_FETCH_BROWSER_AUTO_PREPARE="true"
export PAPER_FETCH_BROWSER_TIMEOUT_MS="120000"
export PAPER_FETCH_BROWSER_HEADLESS="true"
export PAPER_FETCH_BROWSER_PROFILE_DIR="$HOME/.cache/paper-fetch/browser-profile"
# 可提前联网准备官方 managed runtime；CLI 也可首次按需执行
python -m camoufox fetch
```

未显式设置目录时，Camoufox 使用 `publisher-browser-profiles/<provider>-camoufox/storage-state.json`。手动 auth 后再次抓取同一 provider 会复用对应 storage-state；未配置持久凭证不阻止抓取。完整配置与指纹约束见 [`browser-backends.md`](browser-backends.md)。

macOS 官方 cache 应保持 `PAPER_FETCH_BROWSER_BINARY_PATH` 未设置，由 Camoufox
自行解析完整 app bundle。不要把 `Contents/MacOS/camoufox` 当作该变量的值；
它缺少 custom-path 语义所要求的相邻 metadata。该变量只保留给明确支持 Camoufox
custom executable 布局的自行维护 runtime。

补充：

- `wiley` / `science` / `pnas` / `ams` / `mdpi` / `royalsocietypublishing` / `annualreviews` / `acs` / `iop` / `aip` / `tandf` 需要本地 Camoufox runtime，并参与 `paper-fetch auth` / `browser-preflight`
- `paper-fetch auth <provider>` 是自动过盾失败后的人工 headed fallback；storage-state 只保存本机辅助状态，不绕过权限，也不作为正常抓取的必要条件
- `elsevier` 只需要 `ELSEVIER_API_KEY`
- `ieee` 不需要额外 env；普通 fetch 在无授权或 REST/browser/PDF route 返回非全文时会降级到 provider abstract-only / metadata-only；golden criteria live review 面向具备合法 IEEE Xplore 授权上下文的机器，IEEE 样本预期为 fulltext，降级会作为 blocked live fetch 暴露；配置了 `download_dir` 且 artifact mode 为 `all` 时 PDF fallback 的最后一个非 PDF HTML 会保存在 `ieee_pdf_fallback/pdf.failure.html`
- `arxiv` 不需要额外 env；路径细节见 [`providers.md` 的 arXiv 小节](providers.md#arxiv)。
- 如果只想启用 `wiley` 的官方 TDM API PDF lane，可以只配置 `WILEY_TDM_CLIENT_TOKEN`；这不会启用 HTML 资产下载或 seeded-browser PDF/ePDF fallback
- `wiley` / `science` / `pnas` / `ams` / `mdpi` / `royalsocietypublishing` / `annualreviews` / `acs` / `iop` / `aip` / `tandf` 的 browser workflow 顺序见 [`providers.md`](providers.md#wiley-science-pnas-browser-workflow)。

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

本次 MCP SDK 主版本升级后，源码开发环境应重新执行 `uv sync --frozen`；在线
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
paper-fetch --query "10.1186/1471-2105-11-421"
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

`paper-fetch doctor` / install provenance 在 source checkout 下会记录当前 `sys.prefix`。仓库 `.venv` 已存在但未激活时报告 `source_checkout_project_venv_not_active` 并给出 `source .venv/bin/activate`；同时从 `pyproject.toml` 读取 `mcp>=2,<3`，用当前解释器的已安装版本报告 `project_dependency_missing` 或 `project_dependency_incompatible`。离线 bundle 和普通已安装环境不执行仓库 `.venv` 一致性检查。

`scripts/dev-preflight.sh` 是本地完整门禁入口：优先使用 repo-local `.venv/bin/python`，不存在时退回 `python3`，也可显式设置 `PYTHON_BIN=/path/to/python`。脚本依次运行 `ruff format --check`、`ruff check`、完整生产包 `mypy`（`pyproject.toml` 配置 `no_site_packages = true`）、复杂度、provider route/catalog/manifest/fixture/docs 治理与版本一致性门禁、`tests/unit --durations=30`、`tests/devtools --durations=30`、`scripts/validate_extraction_rules.py` 和 `tests/integration --durations=30`；如果缺少 ruff / mypy / pytest，会提示先运行 `scripts/dev-bootstrap.sh` 或指定已安装依赖的解释器。快速迭代可用 `--fast`，需要单独排除 integration 或 type check 时使用 `--skip-integration` / `--skip-typecheck`。

验证分层如下：

- 本地完整门：`scripts/dev-preflight.sh`，包含完整并行 unit、devtools、integration、Ruff、mypy 和 extraction-rule 校验；发布候选还需单独执行 build/install 终验。
- 普通 `push` / `pull_request` CI 门：完整并行 unit + branch coverage、integration、devtools、Ruff、完整生产包 mypy、复杂度/provider governance/版本/抽取规则/漏洞门禁，以及 Python 3.11/3.14 的 core/full wheel smoke。
- 本地 opt-in 门：完整 golden corpus、live publisher/MCP 和 provider drift 只由开发者通过下文命令显式运行，不配置 GitHub Actions schedule 或 dispatch；offline/release 仍只走相应 dispatch 或 `v*` tag。普通 push/PR 不运行真实 publisher、认证 browser 或完整 golden corpus。

所有常规 pytest 步骤继续复用 `pyproject.toml` 的 xdist 并行配置，不传 `-n 0`。关键 workflow 步骤和触发边界由 `tests/unit/test_ci_release_workflow.py` 锁定。

Provider 重构前可以生成本地 coverage baseline，用来观察当前 unit suite 保护范围。本地 `--coverage` preflight 和普通 CI 都启用 branch coverage、生成 `term-missing` 与 `coverage.xml`，并复用 `pyproject.toml` 的首阶段全局 82% 门槛；该值不是锁定当前精确值，后续随分支覆盖提升再推进到 85%：

```bash
bash scripts/dev-preflight.sh --fast --coverage
PYTHONPATH=src uv run python -m pytest tests/unit -q --cov=paper_fetch --cov-branch --cov-report=term-missing --cov-report=xml
```

该命令会生成 terminal missing report 和 `coverage.xml`，随后复用
`scripts/report_coverage_focus.py` 使用 coverage.py 官方 `Coverage.branch_stats()`
逐文件聚合纯分支出口，而不是 statements 与 branches 的综合 report 百分比。它为
security boundaries、workflow、HTTP/cache、PDF fallback、browser runtime 与
installer 同时输出 covered/total、精确百分比和整数 floor；任一 include 未匹配、
源文件未进入 coverage 数据或区域没有可测分支都会失败。安全边界最低为 90%，其余
区域以完整 unit 实测纯分支 floor 为不下降基线。`.coverage`、`coverage.xml` 与
`htmlcov/` 都是本地产物，不应进入 git。

完整 golden corpus regression 默认跳过，只能在本地显式打开；该测试已按 fixture 参数化，默认复用 `pyproject.toml` 的 pytest-xdist 并行配置：

```bash
PAPER_FETCH_RUN_FULL_GOLDEN=1 PYTHONPATH=src uv run python -m pytest tests/integration/test_golden_corpus.py -q
```

未设置 `PAPER_FETCH_RUN_LIVE=1` 时，`tests/live/test_live_publishers.py` 和 `tests/live/test_live_mcp.py` 应稳定 skip。额外验证 live 时，`arxiv` 不需要 browser runtime；包括 `ams` 在内的 browser-backed provider 先按静态报告中的 `browser_runtime.available` 检查本地能力，再启动 Camoufox 做真实页面预检。pytest 隔离 XDG data/runtime、通用 profile 和所有 provider storage-state；Camoufox 的 browser bundle、版本元数据、字体和默认 addon 则复用隔离前由官方包管理器确认的 dependency cache，避免 live/MCP 子进程重复下载 runtime。每家 provider 的状态仍写入临时 `<provider>-camoufox/storage-state.json`，不会进入该共享 dependency cache。

publisher catalog 不是宽松的全文 smoke：每个已执行样本都请求 `asset_profile=body` 并按默认 provider policy 要求 `acceptance.overall=complete`，同时写出 `live-acceptance.json`。无论 preflight/fetch 成功或失败，每个 provider 都先追加 terminal record；JSON 从动态 catalog 计算总数、已记录/未记录 provider、已记录结果是否全 complete，以及全 catalog 是否全部执行并 complete。每个 provider 还记录 preflight/fetch wall time、browser/DOM readiness/HTTP/asset/retry 分段、导航数、preflight reuse，以及不含 URL 的逐资产 phase/status 聚合。需要离线或 full-size 验收时，另以公开的两个严格布尔约束运行并读取同一 v2 acceptance。PNAS 在同一进程内执行当前 benchmark DOI/landing target 的 preflight 后正式 fetch，硬性要求 reuse hit、总 HTML 导航一次、HTML source 成功且 body 资产验收 complete；preflight+fetch 的性能目标只产生告警，不因一次外网抖动失败。MCP live 在同一 server session 内覆盖相同链路。challenge/no-access skip 不会被伪装为全量完成；只有机器可读的 preflight `challenge` / `auth_required`、fetch/MCP `status=no_access`，或成功 metadata fallback 中仅由 `ProviderFailure(NO_ACCESS)` 产生的精确 access-boundary marker，才按合法访问边界 skip。解析失败、空壳、正文不足和其它未知错误仍是 hard failure。非 challenge/auth/cancelled 的 preflight 失败必须保留可读取的隐私安全诊断 artifact。Live fixture 的环境 mapping repr 不显示值；JUnit、acceptance、diagnostics 和待上传目录必须先通过 sentinel 扫描。live 测试依赖共享外部状态和 Camoufox 线程边界，必须串行运行；JUnit 使用与 `record_property` 兼容的 legacy family：

```bash
PAPER_FETCH_RUN_LIVE=1 PAPER_FETCH_LIVE_ARTIFACT_DIR=artifacts/live-publishers \
  PYTHONPATH=src uv run python -m pytest \
  tests/live/test_live_publishers.py tests/live/test_live_mcp.py \
  -q -n 0 -o junit_family=legacy \
  --junitxml=artifacts/live-publishers.xml
```

普通 publisher/MCP live tests 只保留上述本地入口，不由 GitHub Actions 定时或手动触发。只有在具备相应出版社访问授权和凭据的本机网络环境中才应运行；JUnit 和诊断目录也由本地操作者自行保存。

多篇并行对照同样只保留本地 opt-in 入口，不进入 GitHub Actions。默认命令如下：

```bash
PAPER_FETCH_RUN_LIVE=1 PAPER_FETCH_BROWSER_BACKEND=camoufox \
  PYTHONPATH=src python3 scripts/run_parallel_live_benchmark.py \
  --concurrencies 1 2 4 --repetitions 1
```

默认样本混合四条直连和四条 browser 路径；也可用 `--providers` 或 `--sample-ids` 缩小范围。runner 在计时前逐个检查 browser provider，challenge/auth/runtime failure 会阻止对应 provider 的论文调度但不会阻止其它 provider 或后续并发档位。每档创建独立无缓存 HTTP transport，同时复用已确认的 browser storage-state；产物默认位于 `live-downloads/parallel-live-benchmark/<timestamp>/`，显式 `--output-dir` 必须不存在或为空，避免混入旧轮次。单轮结果只用于本次对照，不作为统计显著性结论。任一非预期 acceptance、catalog route 不匹配、preflight 未就绪或跨并发结果漂移都会保留完整报告并返回非零退出码。

排查 HTTP 200 空壳时，`artifact_mode=all` 的页面诊断会把主文档
`requestfinished` 观察结果、Content-Length、实际捕获 HTML 字节与 Navigation Timing
并列保存。`request_finished_observed=false`、`document_ready_state=loading` 且
`response_end_ms=0` 说明采样时响应仍在进行；若 lifecycle 和 response end 均已完成而
DOM 仍很小，则更接近服务端完整返回的小空壳。字段均为页面关闭前的采样事实，不把
transfer size、Content-Length 与 DOM 序列化字节当作可互换的长度。

Wiley 同-provider 探测使用固定矩阵，不能同时传入 `--providers`、`--sample-ids`、`--concurrencies` 或 `--repetitions`：

```bash
PAPER_FETCH_RUN_LIVE=1 PAPER_FETCH_BROWSER_BACKEND=camoufox \
  PYTHONPATH=src python3 scripts/run_parallel_live_benchmark.py \
  --same-provider-probe wiley
```

该命令抓取 3 篇 golden 样本，在并发 `1`、`2` 下各执行 2 轮，共 12 篇次。专项 runner 仅在当前进程内请求 Wiley lane `2`；并发 `1` 的实际 lane 仍为 `1`，CLI/MCP 和 provider catalog 的生产默认值仍为 `1`。`same_provider_probe` 报告包含逐篇 worker 起止时间、请求/实际 lane、逐轮峰值、重叠状态、route/acceptance 稳定性、blocker 和最终判定。没有明显加速不影响能力结论；只有真实峰值重叠及稳定完整结果才通过。preflight、访问授权、challenge、限流、browser runtime 或线程所有权问题判定为 `blocked`，应先修复环境后重跑，不能据此外推 Wiley 不具备并行能力。真实探测只允许本地显式运行，不加入 GitHub Actions。

Provider drift 同样只保留本地脚本入口。完整 browser-risk 样本集会串行访问真实出版社，运行前应准备 Camoufox runtime，并按需配置 publisher 凭据：

```bash
PAPER_FETCH_RUN_LIVE=1 PAPER_FETCH_BROWSER_BACKEND=camoufox \
  PYTHONPATH=src python3 scripts/run_provider_drift_report.py \
  --all-browser-risk --output artifacts/provider-drift-report.json
```

需要验证 AIP 冷启动 HTML 稳定性时，额外显式启用五个隔离 profile 的串行测试；每次都必须得到 `aip_html` 与完整 acceptance，不能以 `aip_pdf` 降级通过：

```bash
PAPER_FETCH_RUN_LIVE=1 PAPER_FETCH_RUN_AIP_COLD_STABILITY=1 \
  PAPER_FETCH_LIVE_ARTIFACT_DIR=artifacts/aip-cold-start \
  PYTHONPATH=src uv run python -m pytest \
  tests/live/test_live_publishers.py::test_aip_cold_start_stability_uses_html_for_five_fresh_profiles \
  -q -n 0
```

该测试依赖同一远端 publisher lane 和本机 Camoufox runtime，必须使用 `-n 0`；失败诊断写入显式本地 artifact 目录。它不由 GitHub Actions 启用，不影响普通 push/PR CI。

IEEE 大型 GIF 资产专项与普通 publisher suite 分离；未确认 runner 具备合法 Xplore 访问上下文时不得启用。在获授权的隔离 runner 上显式运行：

```bash
PAPER_FETCH_RUN_LIVE=1 PAPER_FETCH_RUN_IEEE_BROWSER_LIVE=1 \
  PAPER_FETCH_LIVE_ARTIFACT_DIR=artifacts/live-ieee-protected \
  PYTHONPATH=src uv run python -m pytest \
  tests/live/test_live_ieee_protected.py -q -n 0 \
  -o junit_family=legacy --junitxml=artifacts/live-ieee-protected.xml
```

该专项要求统一 `acceptance.overall=complete`、13 个正文资产全部为 `full_size`，目标大型 GIF 有有效 header、可解析且非零的尺寸，并由生成的 Markdown 使用本地路径引用。测试保持 direct-first：本轮 direct 成功时接受 `final_fetcher=direct_http`；只有 direct 失败并进入恢复时，才硬性核对 Camoufox backend 以及 `direct(403) -> browser` trace。每次 `run-*` 目录会保存 `asset-hashes.json`，其中包含目标 SHA-256、全部正文资产 size/hash、fetcher/recovery trace 和 acceptance。该模块同样只保留本地入口；授权操作者应单独保存 JUnit 和整个 `artifacts/live-ieee-protected/`。

专项 preflight 若在 15 秒 readiness 窗口后仍停留于 AWS WAF HTTP 202 页面，会保留页面关闭前采集的脱敏诊断并以 `aws_waf_challenge` skip；这代表当前网络/会话仍未取得文章 DOM，不可解释为已成功访问。只有后续抓取和上述资产硬门全部通过，才可关闭 PF-LIVE-007。

## 相关文档

- [`../README.md`](../README.md)
- [`docs/README.md`](README.md)
- [`providers.md`](providers.md)
- [`architecture/overview.md`](architecture/overview.md)
