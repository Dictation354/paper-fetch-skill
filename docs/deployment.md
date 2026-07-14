# 部署指南

这份文档解决：

- 如何安装 `paper-fetch-skill`
- 如何准备配置文件
- 如何注册 MCP server
- 如何做最小化验证和更新

这份文档不解决：

- provider 差异、路由规则和限速语义
- Wiley / Science / PNAS / Annual Reviews / Royal Society Publishing / ACS / IOP / AIP / MDPI 的浏览器运行时细节，以及 AMS direct HTTP HTML/PDF 路径
- 架构实现细节

provider 运行时细节见 [`providers.md`](providers.md)，架构说明见 [`architecture/overview.md`](architecture/overview.md)。安装 skill 内部的自包含环境/离线 wrapper 说明见 [`environment.md`](../skills/paper-fetch-skill/references/environment.md)，正常 CLI 主路径见 [`cli-workflow.md`](../skills/paper-fetch-skill/references/cli-workflow.md)；这些 reference 不依赖安装包外的仓库 `docs/`。

## 1. 安装 Python 包

如果目标是把本仓库的完整本地运行环境一次性准备好，推荐先使用顶层一键安装脚本：

```bash
./install.sh
```

默认行为：

- 创建仓库内 `.venv`
- 安装当前 Python 包
- 如果存在 `.env.example` 且用户配置文件还不存在，创建 `~/.config/paper-fetch/.env`
- 安装 Python 依赖、外部公式后端和图片转换后端；默认 provider-owned HTML bootstrap 使用 CDP browser workflow，浏览器 binary 由 cloakbrowser 在运行时按需下载/定位或通过外部 CDP endpoint 提供
- 安装结束时提示 Elsevier 官方 API key 的申请入口和配置位置；抓取 Elsevier 全文前需要从 <https://dev.elsevier.com/> 申请并设置 `ELSEVIER_API_KEY`

补充说明：

- 这是在线一键安装入口：用户不需要手动准备公式后端；浏览器路径统一由 CDP browser workflow 负责，未配置外部 endpoint 时由 cloakbrowser 启动受控 Chrome
- 如果只想安装 Python 包和配置骨架，不准备外部公式或图片转换后端，使用 `./install.sh --lite`
- 如果要装进当前 `python3` 环境而不是 `.venv`，使用 `./install.sh --system`
- arXiv 不需要本地转换器；official HTML 不可用或质量检测失败时直接进入 PDF fallback
- 如果只想跳过公式 Node fallback，可使用 `--no-node`

### 离线包

离线发布支持 Linux x86_64、macOS 和 Windows x86_64。Linux 按 CPython ABI 提供 3.11、3.12、3.13、3.14 自解压 `.sh` 安装器，内部 payload 是预安装 runtime 包；macOS 也按 CPython ABI 提供 3.11、3.12、3.13、3.14 tarball，由 `macos-latest` runner 按本机架构生成；Windows 提供一个内置 CPython 3.13 x64 的 Inno Setup 安装器：

```text
paper-fetch-skill-offline-linux-x86_64-cp311.sh
paper-fetch-skill-offline-linux-x86_64-cp312.sh
paper-fetch-skill-offline-linux-x86_64-cp313.sh
paper-fetch-skill-offline-linux-x86_64-cp314.sh
paper-fetch-skill-offline-macos-<arch>-cp311.tar.gz
paper-fetch-skill-offline-macos-<arch>-cp312.tar.gz
paper-fetch-skill-offline-macos-<arch>-cp313.tar.gz
paper-fetch-skill-offline-macos-<arch>-cp314.tar.gz
paper-fetch-skill-windows-x86_64-setup.exe
```

CI 自动发布规则：

- 普通 `push` / `pull_request` 只运行 `lint`、`integration` 和 `package-smoke` 常规质量门，不启动完整 unit / devtools / coverage，也不启动 Linux / macOS / Windows 离线包矩阵或 release job。
- 推送 `v*` tag 时，CI 会先等待 `lint`、`integration`、`package-smoke`、`offline-linux-x86-64`、`offline-macos-install` 和 `offline-windows-x86-64` 全部成功，再创建对应 GitHub Release。
- 手动运行 `workflow_dispatch` 可以运行离线包矩阵；设置 `run_offline_windows_only=true` 时只运行 `offline-windows-x86-64`，其它常规 job 和非 Windows 离线 job 会跳过。
- release job 会下载本次运行产出的 `paper-fetch-skill-*` artifacts，确认上面 9 个文件都存在且没有额外文件，然后把它们作为 release assets 上传。
- `offline-macos-install` 会在 `macos-latest` 上使用 CPython 3.11、3.12、3.13、3.14 矩阵构建本机架构 macOS tarball，执行安装器验证、headful preset 安装布局检查，并用安装后的 `paper-fetch` / `python` 通过 CloakBrowser 启动本机浏览器打开本地 `data:` 页面，确认 macOS 包安装后可实际使用浏览器路径；验证通过后上传 `paper-fetch-skill-offline-macos-*-cp*.tar.gz` artifact。
- 手动运行 workflow 时，只有在 `v*` tag 上显式设置 `publish_release=true` 才会发布，确保 release tag 和本次构建产物来自同一个 commit。
- 发布使用 workflow 内置的 `GITHUB_TOKEN`，release job 单独声明 `contents: write` 和 `actions: read` 权限，不需要额外 PAT。

主包版本号同步清单：

当前 IOP 补充材料修复集按 SemVer patch 准备为 `3.1.1`；构建脚本不得把高于该版本的 HEAD 降级。

- `pyproject.toml` 的 `[project].version` 是 Python 包和离线构建脚本读取的主版本来源。
- `src/paper_fetch/config.py` 的 `DEFAULT_USER_AGENT` 需要同步默认 `paper-fetch-skill/<version>`。
- `skills/paper-fetch-skill/references/environment.md` 不写死版本号，只指向运行时 `paper_fetch.config.DEFAULT_USER_AGENT`。
- `installer/paper-fetch-skill.iss` 的 `AppVersion` 默认值需要同步；正常 Windows 构建会从 `pyproject.toml` 传入覆盖值，但直接运行 Inno Setup 模板时会使用这里的默认值。
- `tests/unit/test_offline_install.py` 中用于离线安装测试的 runtime fixture 需要与 Linux / macOS 安装脚本的布局保持同步。
- `CHANGELOG.md` / `CHANGELOG_CN.md` 需要新增对应版本章节。`paper-fetch-skill-formula-tools` 的 `package.json` / `package-lock.json` 是公式辅助 Node 包版本，除非单独发布该辅助包，否则不跟随 Python 主包版本。
- `tests/unit/test_install_provenance.py` 会把上述版本来源作为同一契约检查；任何一处漂移都必须在发布前修正。

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

macOS 目标机使用与本机 CPython ABI 和架构匹配的 tarball，解压后运行包内安装脚本：

```bash
tar -xzf paper-fetch-skill-offline-macos-arm64-cp312.tar.gz
cd paper-fetch-skill-offline-macos-arm64-cp312
./install-offline.sh --preset=headful --no-user-config
source ~/.local/share/paper-fetch-skill/activate-offline.sh
```

Preset 选项：

- `headless` 面向服务器或无桌面环境。
- `headful` 面向 macOS 或常规桌面显示环境。

Shell rc 写入策略：

- Linux / macOS 安装脚本会把 payload 复制到固定安装目录，使用该目录下的 `bin/` 启动器和 `runtime/site-packages/` 已安装 Python 包，复制 Codex / Claude Code skill，并注册 MCP。
- Bash 写 `~/.bashrc`，Zsh 写 `~/.zshrc`，Fish 写 `~/.config/fish/conf.d/paper-fetch-offline.fish`。
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

- Windows：下载新版 `paper-fetch-skill-windows-x86_64-setup.exe` 并直接运行。安装路径和 `AppId` 固定，安装器会先备份安装目录内的 `offline.env`，静默运行同 `AppId` 的既有卸载器或清理既有安装目录，再安装新版 runtime-only payload，写回 `offline.env`，只替换 `# BEGIN/END paper-fetch offline managed` 运行时块，并重新写入 PATH、skill 和 MCP 注册。
- Linux：下载与目标机 CPython ABI 匹配的新 `.sh` 后直接运行。默认安装目录固定为 `~/.local/share/paper-fetch-skill`，升级时会备份安装目录内的 `offline.env`，清理既有 runtime payload 和源码/构建残留，把新版 runtime-only payload 复制进去，再写回 `offline.env` 并刷新 shell / skill / MCP managed block。若希望更新时不改动外部 `offline.env`，用 `--reuse-env-file` 指向现有文件；安装脚本不会写入该文件，只会把 shell 启动文件和 Codex fallback config 中的 managed block 替换为新安装目录的 PATH / MCP runtime 路径。
- macOS：下载或构建与目标机架构和 CPython ABI 匹配的新 tarball 后解压运行 `install-offline.sh`；更新语义与 Linux 相同，默认固定安装目录同样是 `~/.local/share/paper-fetch-skill`。

```bash
./paper-fetch-skill-offline-linux-x86_64-cp312.sh --preset=headless --no-user-config
./paper-fetch-skill-offline-linux-x86_64-cp312.sh --preset=headless --no-user-config --reuse-env-file /path/to/shared/offline.env
source ~/.local/share/paper-fetch-skill/activate-offline.sh
```

被复用的 `offline.env` 可以保留原 managed block；运行时路径会通过 shell / activate / MCP 进程环境覆盖为新安装目录路径，文件内容只按 dotenv 解析，不当 shell 执行。更新后重启 Codex / Claude Code / Antigravity。

离线卸载：

- Windows：在“设置 > 应用 > 已安装的应用”中卸载 `Paper Fetch Skill`，或运行 `%LOCALAPPDATA%\PaperFetchSkill\unins000.exe`。如需保留安装目录内 `offline.env` 的 API key，卸载前先备份该文件。卸载器会删除安装目录、安装器复制的 Codex / Claude Code / Antigravity skill、用户 PATH 中的安装目录 `bin`，并移除安装器管理的 MCP 注册；不会删除用户手写的其它 Codex / Claude / Antigravity 配置。
- Linux：运行 `~/.local/share/paper-fetch-skill/install-offline.sh --uninstall`，自定义目录则运行该目录下的 `install-offline.sh --install-dir <path> --uninstall`。该路径不做 checksum、Python ABI 或 bundle asset 检查，只删除 `~/.codex/skills/paper-fetch-skill`、`~/.claude/skills/paper-fetch-skill`、`~/.gemini/antigravity-cli/skills/paper-fetch-skill`，清理 shell 启动文件、Codex fallback config 中的 installer managed block，并通过可用的 `codex` / `claude` CLI 和 Antigravity `mcp_config.json` 移除 MCP；不会删除固定安装目录、`bin/`、`runtime/`、`offline.env`、`downloads/` 或用户配置目录。需要删除固定安装目录时显式运行 `install-offline.sh --purge`。
- macOS：卸载命令与 Linux 相同；如果使用自定义安装目录，运行该目录下的 `install-offline.sh --install-dir <path> --uninstall`。

离线安装约束：

- Linux / macOS Python 版本必须与包名和 `offline-manifest.json` 的 `target.python_tag` 完全匹配；例如 `cp313` 包只能用 CPython `3.13.x` 运行，避免包内已安装 runtime 的 ABI 不匹配
- Linux / macOS 安装器会校验 `offline-manifest.json` 的 `target.platform` 和 `target.arch`；macOS arm64 与 x86_64 包不能混用
- Linux / macOS 安装时会把通过 `PAPER_FETCH_OFFLINE_PYTHON_BIN` / `python3` 选中的解释器路径写入 `runtime/python-bin`，后续 `runtime/paper-fetch-python` 私有 launcher、CLI wrapper 和 MCP 都复用该解释器；`bin/` 不暴露通用 `python` wrapper，避免全局 PATH 前置后遮蔽用户自己的 Python
- Windows 安装器固定使用包内 CPython 3.13 x64 embeddable runtime；目标机不需要预装 Python
- Linux 构建阶段用临时 wheelhouse 把项目和依赖安装进 `runtime/site-packages`，然后只把安装后的 runtime、`bin/` 启动器、公式工具和 skill 放进自解压 `.sh` payload；目标机安装阶段不运行 pip，不包含源码树、`dist/` 或 `wheelhouse/`
- Playwright/CloakBrowser 相关 Python 依赖随 Linux / macOS `runtime/site-packages` 和 Windows embedded runtime 分发；浏览器 binary 不随包分发，browser workflow 会在首次需要时通过 `cloakbrowser.ensure_binary()` 下载/定位 Chrome 并自动启动本机 CDP 浏览器；也可用 `CLOAKBROWSER_CDP_ENDPOINT` 复用已运行浏览器
- Linux `.sh` payload 不包含仓库源码快照和 `tests/` 目录；离线安装目标是运行已打包工具，不在目标机执行项目测试
- Linux / macOS 公式工具使用包内 `formula-tools/bin/texmath`，Windows 使用 `formula-tools/bin/texmath.exe`；目标机不编译 texmath，也不运行 `npm install`
- Linux / macOS 会配置安装目录内 `image-tools` 作为图片转换工具查找目录；离线构建不会把构建机 PATH 上的 Ghostscript/libvips 符号链接固化进包内。运行时找到 Ghostscript 时可转 EPS，找到 libvips 时可转 TIFF；缺少对应工具时只影响 AMS `Download Figure` 源图转换，网页 JPG/PNG 候选仍可回退
- Linux / macOS 默认写固定安装目录内的 `offline.env`、生成可在 bash/zsh 中 `source` 的 `activate-offline.sh`、复制 `~/.codex/skills/paper-fetch-skill`、`~/.claude/skills/paper-fetch-skill` 和 `~/.gemini/antigravity-cli/skills/paper-fetch-skill`，并把离线 CLI PATH、formula tools PATH、image tools PATH、`PAPER_FETCH_ENV_FILE`、`PAPER_FETCH_FORMULA_TOOLS_DIR`、`PAPER_FETCH_IMAGE_TOOLS_DIR`、`MATHML_TO_LATEX_NODE_BIN`、`PYTHONUTF8`、`PYTHONIOENCODING` 等写入当前 shell 对应启动文件；`offline.env` 的 managed block 默认启用普通 Chrome `PAPER_FETCH_BROWSER_USER_AGENT`、包内 Playwright Node、Python UTF-8 encoding 和 `CLOAKBROWSER_HEADLESS=true`，只有显式传 `--user-config` 才会把受标记管理的运行时块合并到 `~/.config/paper-fetch/.env`
- Linux / macOS `--install-dir <path>` 会把 runtime-only payload 固定安装到指定目录；升级同一目录时会清理 `src/`、`tests/`、`wheelhouse/`、`dist/`、`.github/` 等残留并保留安装目录内 `offline.env`
- Linux / macOS `--reuse-env-file <path>` 会把 `PAPER_FETCH_ENV_FILE` 指向现有文件且不修改该文件；其它 runtime 路径仍由新安装目录写入 shell / activate / MCP 环境，activate 时只做安全 dotenv 解析
- Linux / macOS 写入 shell 启动文件和 Codex fallback config 时会先替换既有受管理 block，重复安装不会重复追加；不修改 `/etc/profile`
- Windows 首次安装会写安装目录内 `offline.env`；升级安装会保留用户已有内容，只替换 `# BEGIN/END paper-fetch offline managed` 包围的运行时 block。MCP 注册环境固定指向安装目录内 `offline.env`、`downloads/`、`formula-tools/`、`image-tools/` 和包内 `runtime/Lib/site-packages/playwright/driver/node.exe`，并设置 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`、`PAPER_FETCH_BROWSER_USER_AGENT=<普通 Chrome UA>`、`CLOAKBROWSER_HEADLESS=true`、`PAPER_FETCH_IMAGE_TOOLS_DIR=<install-root>/image-tools`、`MATHML_TO_LATEX_NODE_BIN=<install-root>/runtime/Lib/site-packages/playwright/driver/node.exe`。Linux / macOS 也会在包内 Playwright Node 存在时把 `MATHML_TO_LATEX_NODE_BIN` 指向 `runtime/site-packages/playwright/driver/node`
- Windows 安装、升级或手工修改 `offline.env` 后，需要重启 Codex Desktop / Claude Code / Antigravity；已启动的 MCP 服务不会自动继承新写入的 env。
- Windows GUI 安装完成页会提示 Elsevier API key 申请入口和包内 `offline.env` 位置，并提供可选的 Notepad 打开项；silent 安装不会弹出该提示。离线环境抓取 Elsevier 全文前，从 <https://dev.elsevier.com/> 申请 key，并在该文件中填写 `ELSEVIER_API_KEY`
- `--preset=headless` / `--preset=headful` 设置自动启动浏览器的默认 headed/headless 行为；显式 `CLOAKBROWSER_CDP_ENDPOINT` 指向外部浏览器时，以外部浏览器自身状态为准

构建离线包：

```bash
scripts/build-offline-package.sh --output-dir dist
```

Windows 构建在 PowerShell 中执行：

```powershell
.\scripts\build-offline-package-windows.ps1 -OutputDir dist
```

Linux / macOS 构建脚本会从当前平台、架构和 Python 推导包名；例如 Linux x86_64 上 `PYTHON_BIN=python3.13 scripts/build-offline-package.sh` 会默认生成 `paper-fetch-skill-offline-linux-x86_64-cp313.sh`，macOS arm64 上会生成 `paper-fetch-skill-offline-macos-arm64-cp313.tar.gz`。Linux 构建继续输出由 shell stub 和压缩 payload 组成的单文件 `.sh` 安装器；macOS 构建输出 `.tar.gz` bundle。两者都会先解析 binary wheelhouse，再把项目和依赖安装进 `runtime/site-packages`，预编译 bytecode，写入 `runtime/paper-fetch-python` 私有 launcher，以及 `bin/paper-fetch`、`bin/paper-fetch-mcp`、`bin/paper-fetch-install-formula-tools`、`bin/paper-fetch-install-image-tools` 命令启动器；`bin/` 不包含通用 `python` wrapper，payload 不携带源码树或 wheelhouse。离线构建只会从 repo-local 可重定位 runtime 暂存 Ghostscript/libvips，不会把构建机系统 PATH 的二进制或符号链接打包。Windows 构建必须在 CPython 3.13 x64 上运行，会下载官方 CPython 3.13 embeddable x64 runtime，把 Python 包安装进 `runtime/Lib/site-packages`，并只把 embedded runtime、`bin/` 启动器、静态 skill、formula tools、image-tools 目录/启动器、`installer/manifest.json`、`scripts/windows-installer-helper.ps1` 和离线元数据放进 Inno Setup 安装器；安装后的 Windows payload 不携带顶层 `src/`、`tests/`、`.github/`、`wheelhouse/`、`dist/` 或 `pyproject.toml`。

安装器共享配置集中在 `installer/manifest.json`：`skill.name`、`mcp.name`、`mcp.env_keys`、`env_sets.offline_env_keys`、`env_sets.shell_env_keys`、`env_sets.activate_env_keys`、managed block marker 和离线包命名都从这里读取。Linux / macOS / Windows 离线安装脚本、Windows Inno helper 和离线包构建脚本都使用该 manifest，新增 MCP / offline.env / shell / activate 环境变量或调整 managed block 文案时应优先改这里。

验证离线包：

```bash
scripts/verify-offline-package.sh dist/paper-fetch-skill-offline-linux-x86_64-cp311.sh
```

上面的验证路径按实际构建出的 `cp311`、`cp312`、`cp313` 或 `cp314` 包名替换。

验证脚本会执行 `.sh --install-dir <临时目录>` 或先解压 macOS `.tar.gz` 再执行包内 `install-offline.sh --install-dir <临时目录>`，确认安装后的固定目录包含 `runtime/site-packages` 和 `bin/` 启动器，且不包含源码树、`tests/`、`dist/` 或 build wheelhouse；再用 guard 拦截 `curl`、`git`、`npm`、`playwright` 等命令来确认安装器没有在线下载或目标机 patch 动作，并使用临时 HOME、fake `codex` / `claude` CLI 和 Antigravity `mcp_config.json` 验证 Linux / macOS shell 写入、skill 复制、MCP remove/add/config 注册、manifest env key、`activate-offline.sh` 不执行 env 文件命令替换；随后检查 `paper-fetch --help`、`texmath --help`、`paper-fetch-install-image-tools`、`cloakbrowser.ensure_binary` 可导入、`paper_fetch.mcp.fetch_tool.provider_status_payload`，最后执行 `install-offline.sh --uninstall` 验证用户级集成可清理且不删除安装目录内 `offline.env` 或 runtime，并执行 `--purge` 验证固定安装目录可显式删除。

Windows CI 在 `offline-windows-x86-64` job 中执行安装器验证：通过 `Start-Process -Wait -PassThru` silent install 并检查安装器进程退出码，失败时输出安装日志；随后验证安装目录是 runtime-only 布局，不存在顶层源码或构建目录，再验证 bundled `runtime\python.exe` import 和 `provider_status_payload()`、`bin\paper-fetch.cmd --help`、`texmath.exe --help`、CloakBrowser/Playwright runtime smoke，并用 fake `codex` / `claude` CLI 验证 MCP remove/add 命令。

只需要复核 Windows 安装器时，可以手动触发 `CI` workflow 并设置 `run_offline_windows_only=true`；该模式只运行 `offline-windows-x86-64`，其它常规 job 会跳过。

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

默认主配置文件是：

```text
~/.config/paper-fetch/.env
```

如果你需要 provider API key、自定义下载目录或自定义 `User-Agent`，可以先这样准备：

```bash
mkdir -p ~/.config/paper-fetch
cp .env.example ~/.config/paper-fetch/.env
```

Elsevier 官方 XML/API 和 PDF fallback 至少需要从 <https://dev.elsevier.com/> 申请并配置：

```bash
ELSEVIER_API_KEY="..."
```

补充说明：

- 运行时默认读取 `platformdirs` 解析出的用户配置目录下的 `.env`；常见 Linux/XDG 布局为 `~/.config/paper-fetch/.env`
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
- 根目录 `package.json` / `package-lock.json` 与 `src/paper_fetch/resources/formula/package.json` / `package-lock.json` 必须保持公式 Node 依赖版本一致；`tests/unit/test_formula_package_sync.py` 会阻止 KaTeX / MathML 工具版本漂移。

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

`doctor` 与 MCP `provider_status` 共用同一静态诊断：检查 provider 配置、配置来源、Playwright/CloakBrowser、Chrome/CDP 配置和 Ghostscript/libvips，但不连接 CDP、不启动 Chrome、不请求出版社页面，也不自动安装依赖。配置部分只输出变量名、来源层和是否存在，不输出 token、cookie、endpoint、文件路径或其它值；因此可以保存 JSON 供部署排查，但仍应按敏感运维日志管理。

`full` 保留 provider checks 和本地能力；`compact` 只保留路由所需的状态、关键 reason 与建议动作。`install_provenance` 会分别给出 source `pyproject.toml`、当前 Python distribution metadata、`DEFAULT_USER_AGENT`、PATH 上 `paper-fetch --version`、指定或自动发现的 `offline-manifest.json`、安装 runtime metadata 与 entrypoint 的版本和绝对路径；`consistency.version_drift` 直接列出 expected/actual/path。源码开发态没有 offline manifest 时，离线安装部分返回 `not_applicable`，不会误报安装失败，但 distribution 或 PATH CLI 与源码版本不一致仍会报告 `drift`。

offline manifest schema 3 保留 `version`、`git_revision`、`built_at_utc`、`target.platform` / `arch` / `python_tag` 和 `entrypoint`，并新增 `skill_bundle`：其中列出 `SKILL.md`、全部 `references/` 及其它 bundle 文件的相对路径和逐文件 SHA256。POSIX 与 Windows 安装器会在复制前校验 bundle，在复制后再次校验安装根目录及 Codex、Claude Code、Antigravity 三份 skill；缺文件、多文件、符号链接或 hash 不一致都会阻止完整性验收。

升级后应从目标安装 runtime 执行带 `--install-root` 的诊断，确认 `install_provenance.status=ready`，再重启 Codex、Claude Code 和 Antigravity，使宿主重新扫描已验证的 skill/MCP。PF-020 只准备并验证 `3.1.0` 包，不覆盖当前活动安装；实际替换活动安装和重启后的独立 MCP 验收留在发布收口步骤执行。

部署排查顺序为：`doctor` / `provider_status` 静态检查 → 对 browser provider 运行 CLI `paper-fetch browser-preflight` 或 MCP `browser_preflight` 做真实页面预检 → 只有返回 challenge/auth required 或实际抓取明确需要时，才由用户运行 `paper-fetch auth <provider>`。后两步可能访问网络，preflight 默认可能更新 provider storage-state；MCP 可显式设 `save_storage_state=false` 禁止本轮保存。两种 preflight 入口共用 HTML 核心，均不运行 PDF fallback 或自动 auth；静态 `ready` 不代表网页当前健康或账号已有访问权。

### CI / GitHub Actions

本地完整 unit suite 和手动 `full-golden` workflow 会验证或使用公式 / 图片后端。GitHub Actions 的 `full-golden` job 因此需要先准备 Haskell/cabal，再执行：

```bash
python -m paper_fetch.formula.install --target-dir "$PWD/.formula-tools" --no-node
./.formula-tools/bin/texmath --help >/dev/null
python -m paper_fetch.image_tools.install --target-dir "$PWD/.image-tools"
```

相关测试步骤应设置 `PAPER_FETCH_FORMULA_TOOLS_DIR=$GITHUB_WORKSPACE/.formula-tools` 和 `PAPER_FETCH_IMAGE_TOOLS_DIR=$GITHUB_WORKSPACE/.image-tools`。这里用 `--no-node` 是为了避免安装失败后静默落到 `mathml-to-latex` fallback；如果 `texmath` 没有装好，对应验证步骤会直接失败。图片后端安装是 best-effort：Ghostscript/libvips 不可用时，相关测试只覆盖识别和回退契约。

CI 还包含 package smoke job：用 `python -m build --outdir "$RUNNER_TEMP/paper-fetch-dist"` 在 checkout 外生成且只接受一个 sdist / wheel，然后在干净 venv 里安装 wheel。该门会核对安装 metadata 与 `paper-fetch --version`，运行 CLI help、formula/image installer help、`paper-fetch-mcp` EOF smoke，并加载四个 console-script entry point；最后运行静态 `doctor --json`，确认 wheel 开发态没有版本 drift。构建和诊断产物都只写 runner 临时目录。

重型 offline/release job 不属于普通 `push` / `pull_request` 默认门禁；触发边界见上方“CI 自动发布规则”。

本地清理构建、测试缓存和 rollout 日志时可以用：

```bash
scripts/clean-local-artifacts.sh --dry-run
scripts/clean-local-artifacts.sh --days 7
```

该脚本只删除 `git check-ignore` 确认为 ignored 的目标；未被 `.gitignore` 覆盖的路径会跳过。

## 4. Provider 接入入口与本地运行时

`elsevier` 不依赖本地浏览器链路；它只需要官方 API 凭据，并走 `官方 DOI XML/API -> PII XML/API fallback -> 官方 API PDF fallback -> metadata-only`。

`ieee` 不需要 IEEE API key；它走 `landing metadata / article number -> direct REST HTML -> clean-browser HTML -> direct HTTP PDF fallback -> seeded-browser PDF fallback`，但全文是否可用仍取决于当前环境对 IEEE Xplore 的合法访问上下文。clean-browser HTML 使用新的 CDP browser context，不读取本机浏览器 profile、不复用用户登录态、不自动登录、不处理验证码，也不绕过访问权限。direct HTTP PDF 返回 `stamp.jsp` HTML wrapper 或 access/challenge 页面时，seeded-browser PDF fallback 只复用当前页面运行期间获得的合法 IEEE cookies/session。

`wiley`、`science`、`pnas`、`annualreviews`、`royalsocietypublishing`、`acs`、`iop`、`aip`、`mdpi` 默认通过 CDP browser workflow 进入 provider-owned browser workflow；`ams` 只使用带浏览器 UA/Referer 的 direct HTTP HTML 主路径和 direct HTTP `downloadpdf` PDF fallback，不进入 CDP browser HTML 或 seeded-browser PDF fallback。显式配置 `CLOAKBROWSER_CDP_ENDPOINT` 时复用已运行浏览器并借用现有 browser context；未配置时自动通过 cloakbrowser 下载/定位 Chrome 并启动受控本机 CDP 浏览器，同一进程内按 runtime/browser 配置复用一个 keyed browser manager，批量并发任务不会为同一个 provider profile 启动多个 Chrome 去抢 profile lock。HTML 与 PDF fallback 会打开隔离 context/page，并在调用线程建立自己的 CDP 连接；browser-backed 资产下载会串行化以避免跨线程复用 Playwright sync 对象，普通 HTTP 资产下载仍按配置并发。是否能拿到全文仍取决于 publisher 访问权限、paywall/challenge 与远端站点行为。

需要复用手动验证过的浏览器时，可启动带 DevTools 端口的浏览器并设置 endpoint：

```bash
/path/to/chrome \
  --user-data-dir="$HOME/.cache/paper-fetch/browser-profile" \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9222 \
  --no-first-run

export CLOAKBROWSER_CDP_ENDPOINT="ws://127.0.0.1:9222/devtools/browser/..."
```

自动过盾失败时，可打开对应 provider 的 headed browser 手动登录/验证：

```bash
paper-fetch auth <provider>
paper-fetch auth wiley --url "https://onlinelibrary.wiley.com/doi/full/10.1111/example"
```

`provider` 来自 browser runtime catalog，例如 `wiley` / `science` / `pnas` / `mdpi` / `royalsocietypublishing` / `annualreviews` / `acs` / `iop` / `aip`。未传 `--url` 时打开内置样例文章；传入 `--url` 时打开具体失败文章页。命令强制 headed 模式，打印 managed Chrome 启动目录和 storage-state 路径，终端按 Enter 后保存过滤后的本地 storage-state 并退出，不写 `.env`。AMS 主路径是 direct HTTP HTML，不支持 `paper-fetch auth ams`。

这些浏览器 HTML route 会在 challenge/paywall 判定前先等待正文 DOM 稳定；如果正文已经可抽取，页面残留的 Cloudflare/challenge 文案不会提前中断 HTML route，最终全文/摘要/降级结论仍由 Markdown 抽取后的 availability 判定负责。

默认 browser workflow 的常用配置：

```bash
export CLOAKBROWSER_TIMEOUT_MS="120000"
# 可选：复用外部浏览器
export CLOAKBROWSER_CDP_ENDPOINT="ws://127.0.0.1:9222/devtools/browser/..."
# 可选：自动启动路径使用预装 Chrome 或显式 startup/storage-state 目录
export CLOAKBROWSER_BINARY_PATH="/absolute/path/to/chrome"
export CLOAKBROWSER_PROFILE_DIR="$HOME/.cache/paper-fetch/browser-profile"
```

`CLOAKBROWSER_HEADLESS` 控制自动启动的 headed/headless；`CLOAKBROWSER_BINARY_PATH` 由 cloakbrowser 用作本地 binary override；未显式设置目录时，自动浏览器会按 publisher 使用 `publisher-browser-profiles/<provider>/storage-state.json` 持久化过滤后的 storage-state。`CLOAKBROWSER_PROFILE_DIR` / `CLOAKBROWSER_USER_DATA_DIR` 可覆盖 managed Chrome 启动目录和 storage-state 保存位置，但不承诺完整复用 IndexedDB、service worker 或扩展等浏览器 profile 状态。手动 auth 后再次抓取同一 provider 会复用同一个 provider storage-state 文件；未配置持久凭证不阻止抓取，仍会按 provider 现有 fallback 运行。

补充：

- `wiley` / `science` / `pnas` / `mdpi` / `royalsocietypublishing` / `annualreviews` / `acs` / `iop` / `aip` 需要本地 browser runtime；`ams` direct HTTP HTML/PDF 路径不启动 browser runtime，也不参与 `paper-fetch auth` / `browser-preflight`。`CLOAKBROWSER_CDP_ENDPOINT` 可显式复用外部浏览器，未设置时自动启动 cloakbrowser Chrome，并默认按 publisher 复用本地 storage-state
- `paper-fetch auth <provider>` 是自动过盾失败后的人工 headed fallback；storage-state 只保存本机辅助状态，不绕过权限，也不作为正常抓取的必要条件
- `elsevier` 只需要 `ELSEVIER_API_KEY`
- `ieee` 不需要额外 env；普通 fetch 在无授权或 REST/browser/PDF route 返回非全文时会降级到 provider abstract-only / metadata-only；golden criteria live review 面向具备合法 IEEE Xplore 授权上下文的机器，IEEE 样本预期为 fulltext，降级会作为 blocked live fetch 暴露；配置了 `download_dir` 且 artifact mode 为 `all` 时 PDF fallback 的最后一个非 PDF HTML 会保存在 `ieee_pdf_fallback/pdf.failure.html`
- `arxiv` 不需要额外 env；路径细节见 [`providers.md` 的 arXiv 小节](providers.md#arxiv)。
- 如果只想启用 `wiley` 的官方 TDM API PDF lane，可以只配置 `WILEY_TDM_CLIENT_TOKEN`；这不会启用 HTML 资产下载或 seeded-browser PDF/ePDF fallback
- `wiley` / `science` / `pnas` / `mdpi` / `royalsocietypublishing` / `annualreviews` / `acs` / `iop` / `aip` 的 browser workflow 顺序见 [`providers.md`](providers.md#wiley-science-pnas-browser-workflow)；AMS 的 direct HTTP HTML/PDF 顺序见同页 AMS 小节。

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
- 如需 headed browser，可设置 `CLOAKBROWSER_HEADLESS=false` 让自动浏览器可见，或手动启动可见 Chrome/CloakBrowser 并通过 `CLOAKBROWSER_CDP_ENDPOINT` 暴露给 paper-fetch

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

CLI 默认打印 Markdown 到终端；如果指定 `--output-dir` 且未显式传 `--output`，主输出会用安全化论文 stem 加 `.md`、`.json` 或 `.both.json` 后缀写入该目录，正文不会打印到终端。完整输出、artifact、资产下载和错误码语义见 [`cli.md`](cli.md)。

如果你在仓库源码目录里做 repo-local 验证，先安装测试依赖，并推荐显式带上 `PYTHONPATH=src`。默认 `pytest` 覆盖 `tests/unit` + `tests/integration` + `tests/devtools` 并启用多进程并行；`tests/live` 需要显式指定路径并串行运行：

```bash
python3 -m pip install '.[dev]'
bash scripts/dev-preflight.sh
PYTHONPATH=src pytest tests/unit/test_cli.py tests/unit/test_service_*.py tests/unit/test_mcp_*.py
PYTHONPATH=src pytest
```

`scripts/dev-preflight.sh` 是本地完整门禁入口：优先使用 repo-local `.venv/bin/python`，不存在时退回 `python3`，也可显式设置 `PYTHON_BIN=/path/to/python`。脚本依次运行 `ruff format --check`、`ruff check`、contract 层 `mypy`（`pyproject.toml` 配置 `no_site_packages = true`）、`tests/unit --durations=30`、`tests/devtools --durations=30`、`scripts/validate_extraction_rules.py --ci` 和 `tests/integration --durations=30`；如果缺少 ruff / mypy / pytest，会提示先运行 `scripts/dev-bootstrap.sh` 或指定已安装依赖的解释器。快速迭代可用 `--fast`，需要单独排除 integration 或 type check 时使用 `--skip-integration` / `--skip-typecheck`。

验证分层如下：

- 本地完整门：`scripts/dev-preflight.sh`，包含完整并行 unit、devtools、integration、Ruff、mypy 和 extraction-rule 校验；发布候选还需单独执行 build/install 终验。
- 普通 `push` / `pull_request` CI 门：`lint` 保留 Ruff/mypy，`integration` 先运行 MCP schema 与 CLI/MCP/cache/manifest、落盘、batch、skill/provenance 轻量契约集，再运行完整 integration；`package-smoke` 验证 wheel/sdist 和全部 console scripts。为控制耗时，CI 不重复完整 unit、devtools 或 unit coverage。
- opt-in 门：`full-golden`、offline/release 和 `live-mcp` 只允许相应 `workflow_dispatch` 输入或 `v*` tag 路径；普通 push 不运行真实 publisher、认证 browser 或重型 offline 流程。

所有常规 pytest 步骤继续复用 `pyproject.toml` 的 xdist 并行配置，不传 `-n 0`。关键 workflow 步骤和触发边界由 `tests/unit/test_ci_release_workflow.py` 锁定。

Provider 重构前可以生成本地 coverage baseline，用来观察当前 unit suite 保护范围。本地 `--coverage` preflight 会生成 `term-missing` 和 `coverage.xml`，并强制低噪声 baseline `--cov-fail-under=40`；该阈值是防止覆盖率接线失效和大面积倒退的底线，不替代 provider-specific fixture / live/browser 验证。GitHub CI 不再生成 unit coverage report：

```bash
bash scripts/dev-preflight.sh --fast --coverage
PYTHONPATH=src python3 -m pytest tests/unit -q --cov=paper_fetch --cov-report=term-missing --cov-report=xml --cov-fail-under=40
```

该命令会生成 terminal missing report 和 `coverage.xml`；`.coverage`、`coverage.xml` 与 `htmlcov/` 都是本地产物，不应进入 git。

完整 golden corpus regression 默认跳过，可在本地或 workflow dispatch 中显式打开；该测试已按 fixture 参数化，默认复用 `pyproject.toml` 的 pytest-xdist 并行配置：

```bash
PAPER_FETCH_RUN_FULL_GOLDEN=1 PYTHONPATH=src python3 -m pytest tests/integration/test_golden_corpus.py -q
```

未设置 `PAPER_FETCH_RUN_LIVE=1` 时，`tests/live/test_live_publishers.py` 和 `tests/live/test_live_mcp.py` 应稳定 skip。额外验证 live smoke 时，`arxiv` 和 `ams` 不需要凭据或 browser runtime；`wiley` / `science` / `pnas` / `mdpi` / `royalsocietypublishing` / `annualreviews` / `acs` / `iop` / `aip` 需要可用 browser runtime，默认会自动启动 cloakbrowser Chrome 并按 publisher 复用 storage-state；如需复用已验证浏览器，可设置 `CLOAKBROWSER_CDP_ENDPOINT`。`ieee` 不需要 IEEE API key，但 IEEE fulltext smoke 预期当前机器具备合法 IEEE Xplore 访问上下文。live 测试依赖真实 publisher/API/browser/授权上下文和外部限流状态，建议串行运行：

```bash
PAPER_FETCH_RUN_LIVE=1 PYTHONPATH=src python3 -m pytest tests/live/test_live_publishers.py tests/live/test_live_mcp.py -q -n 0
```

GitHub Actions 的手动 `live-mcp` job 默认排除 IEEE fulltext smoke；只有在具备合法 IEEE Xplore 授权的 runner/network 上，才应同时启用 `run_live_mcp` 和 `run_ieee_live_mcp`。

## 相关文档

- [`../README.md`](../README.md)
- [`docs/README.md`](README.md)
- [`providers.md`](providers.md)
- [`architecture/overview.md`](architecture/overview.md)
