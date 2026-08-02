# macOS 适配变更与维护流程

本文记录当前 fork 相对上游在 macOS 平台上的适配边界，并给出以后主要在
Windows / WSL 开发时同步上游 `main` 的重放流程。它不是一次性的迁移笔记：
机器可读约束见 [`macos-adaptation-contract.toml`](macos-adaptation-contract.toml)，
证据边界和未关闭项见
[`macos-adaptation-audit.md`](macos-adaptation-audit.md)。

## 基线与决策

- 上游仓库：`Dictation354/paper-fetch-skill`
- 本轮代码基线：`v4.1.0`
- 上游 commit：`fc3bd96e8d781667a2e86e90dc6e8e35a8a26fa7`
- macOS 离线目标：Apple Silicon `arm64`、CPython 3.11–3.14、最低
  macOS 15.0
- 原生构建 runner：固定 `macos-15`，不使用会随 GitHub 镜像迁移的
  `macos-latest`
- browser/full extra 接受 `camoufox>=0.5.4,<0.6`，由 `uv.lock` 固定原生 browser
  launch gate 与离线产物实际使用的 Python package 版本
- `v4.1.0` 是不可移动的上游审计基线，不是本 fork 适配后的发布版本；发布这些
  适配必须先提升 fork 版本并创建新标签，不能移动或复用上游 `v4.1.0` 标签

这个适配方案值得保留，但关键不是维护一份长期偏离上游的“Mac 分支”，而是把
Mac 差异拆成可重放实现、机器可验证合约、原生 Mac 证据三层。Windows / WSL
可以尽早发现文本和静态契约漂移，最终平台事实仍由原生 macOS gate 证明。

旧版 v1 适配合约不能直接复制到 v4。v4 已经原生具备 arm64 的
CPython 3.11–3.14 macOS tarball、Zsh 启动文件处理、`platformdirs` 用户目录和
Camoufox browser workflow；同时浏览器后端、离线 runtime 布局、manifest、
texmath 和发布 workflow 都已经变化。本轮因此以 v4.1.0 的现状重新建模，合约
schema 从 v4 的实际文件和风险出发，不继承过时路径或旧浏览器假设。

## 上游 v4 已有能力

在本轮适配之前，上游 v4.1.0 已经提供：

- `paper-fetch-skill-offline-macos-arm64-cp311` 到 `cp314` 的 tarball
  构建矩阵；
- POSIX 离线安装器的 Bash / Zsh / Fish 启动文件选择；
- Python 运行时通过 `platformdirs` 解析用户配置和数据目录；
- `runtime/site-packages` 中预安装的 full Python extra；
- Camoufox 作为唯一受支持 browser backend；
- Linux、macOS、Windows 的原生 texmath 0.13.2 和 Node 公式回退；
- runtime-only 安装、升级、`--uninstall` / `--purge` 以及 host skill /
  MCP 注册。

这些已有代码应继续复用。本轮只收紧原生 Mac 的发布、安装和验证边界。

## 本轮新增或收紧的适配

| 变更 ID | 适配主题 | 对应审计 case |
| --- | --- | --- |
| `MAC-V4-001` | v4.1.0 原生离线矩阵、标准 ABI/架构与安全包名 | `MAC-AUD-001`、`MAC-AUD-002`、`MAC-AUD-003` |
| `MAC-V4-002` | 可迁移、可签名、可启动的 Mach-O / Node 工具 | `MAC-AUD-004`、`MAC-AUD-005`、`MAC-AUD-006` |
| `MAC-V4-003` | Camoufox 离线边界 | `MAC-AUD-012` |
| `MAC-V4-004` | Zsh、macOS `platformdirs` 布局与等价路径别名 | `MAC-AUD-008`、`MAC-AUD-010` |
| `MAC-V4-005` | 递归 quarantine、安装目录 ownership、配置保留与 safe purge | `MAC-AUD-007`、`MAC-AUD-009`、`MAC-AUD-010` |
| `MAC-V4-006` | 原生 macOS CI / release 证据 | `MAC-AUD-002`、`MAC-AUD-006` |
| `MAC-V4-007` | Windows / WSL 可执行维护合约 | `MAC-AUD-001`、`MAC-AUD-011` |
| `MAC-V4-008` | Camoufox 官方 Mac app bundle 解析 | `MAC-AUD-013` |

表中的 ID 与
[`macos-adaptation-contract.toml`](macos-adaptation-contract.toml) 一一对应；
审计 case 的关闭条件以
[`macos-adaptation-audit.md`](macos-adaptation-audit.md) 为准。

### MAC-V4-001：固定构建平台和最低系统版本

macOS 离线矩阵固定到 `macos-15`，构建脚本仅接受原生 Darwin arm64。构建环境
使用并强制最低部署目标 15.0，`offline-manifest.json` 同步记录
`target.minimum_os_version = "15.0"`。

构建器只接受标准 GIL CPython：拒绝 free-threaded/debug ABI，要求 `SOABI`
属于当前 `cp311`–`cp314`，并要求解释器架构与构建宿主目标一致。显式
`--package-name` 只能是由字母或数字开头、仅包含字母数字、点、下划线和短横线的
单一路径组件；manifest 派生的默认名称也会复验。构建根会 canonicalize 并拒绝
`/`、HOME、仓库及其祖先；非空 staging 只有在
`.paper-fetch-offline-staging-owner` 同时匹配仓库、canonical staging 和包名时
才可清理。临时 wheelhouse/project wheel 也位于该 owned staging，ownership
marker 不进入 checksum 或发行包。输出目录不能位于 staging 内；正式 `.sh` /
`.tar.gz` 先在输出目录写入不可碰撞临时文件，成功后同文件系统原子 rename，
失败会清理 scratch 并保留既有正式产物。

安装器在写入用户的 shell、skill、MCP 或配置文件之前，先验证：

- 当前平台确实是 macOS；
- 当前架构为 arm64；
- CPython ABI 与 tarball 的 `cp311`–`cp314` tag 完全一致，且解释器架构与
  arm64 宿主一致；Rosetta x86_64 Python、free-threaded/debug ABI 均 fail closed；
- 当前 macOS 版本不低于 manifest 声明；
- checksum 清单与 bundle 中除清单自身外的所有 regular file 精确一致，且每个
  清单条目路径安全、唯一、可校验；payload symlink 和未列出的附加 payload 都会
  fail closed；
- 所需入口完整。

这使“包名看起来正确”和“目标机确实兼容”成为两个独立检查。

### MAC-V4-002：可迁移且可验证的 texmath

构建阶段不再假定 runner 上编译出的 texmath 可以原样移动。构建脚本会：

- 把 `formula-tools/bin/texmath` 实体化，避免保留构建机符号链接；
- 递归收集其非系统 Mach-O 动态库到 `formula-tools/lib`；
- 用 `@rpath` / `@loader_path` 重写 install name，移除构建机绝对路径；
- 对 texmath 和随包动态库执行 ad-hoc codesign；
- verifier 先用 Python `tarfile.data_filter` 拒绝绝对路径、`..`、多顶层目录、
  特殊文件及逃逸 link，再解包；
- 在原生 Mac verifier 中使用 `file -b`、`lipo -archs`、`otool` 和
  `codesign --verify --strict` 复核 Mach-O 格式、精确 arm64 架构与签名；
- canonicalize 每条非系统依赖，拒绝 symlink、bundle 外目标和绝对
  build-host `LC_RPATH`，递归证明依赖闭包；Playwright Node 也走同一闭包，
  完成检查后才实际运行 `node --version`。

这里的 ad-hoc 签名用于保证本地 bundle 内 Mach-O 的结构一致性，不等同于
Developer ID 签名或 Apple notarization，也不承诺 Gatekeeper 的发行者信任。

### MAC-V4-006：原生 tarball 安装与发布验证

Linux `.sh` 和 macOS `.tar.gz` 都进入
`scripts/verify-offline-package.sh`。macOS 验证明确使用 `/bin/zsh` 和
`.zshrc`，覆盖：

- tarball 只有一个顶层 bundle，且安装入口可执行；
- 安装过程不调用受 guard 拦截的联网或现场构建命令；
- runtime-only 目录、CLI、MCP、skill、manifest 和 dotenv 安全解析；
- Camoufox / Playwright **Python 包导入**；
- texmath Mach-O 架构、动态库可迁移性和 codesign；
- Playwright Node 的 `otool -L` 可迁移性和真实 `--version` 启动；
- 对嵌套 native runtime 文件写入 quarantine，证明递归 xattr 检查在安装目录、
  shell、skill 和用户配置写入前 fail closed；
- `.zshrc` 相对 symlink 的安装、升级和卸载保持，以及 macOS user-config 的
  非 managed 内容保留和 managed block 卸载清理；
- `--uninstall` 保留 runtime，显式安全 `--purge` 才删除安装目录。

artifact 上传设置 `if-no-files-found: error`，避免构建成功但没有产物时继续发布。
普通 push / PR 的 `.github/workflows/ci.yml` 固定用 `macos-15`、CPython 3.14
执行原生 build + verifier，并单独运行真实 `/var` ↔ `/private/var` 或
`/tmp` ↔ `/private/tmp` cache scope alias pytest node；该 alias 证据来自原生
CI，而不是 tarball verifier。
`offline.yml` 和 release gate 则覆盖 CPython 3.11–3.14 四个 ABI。

### MAC-V4-005：quarantine、safe purge 和 symlink 安全

macOS 安装器在任何用户级写入之前，对整个 bundle 递归检查 quarantine 扩展
属性；这包括任意嵌套的 native extension、texmath、随包 dylib 和 Playwright
driver Node，而不是维护一个容易漏项的文件清单。发现
`com.apple.quarantine` 时拒绝继续，并提示用户在核验 Release 来源和
`SHA256SUMS` 后显式运行：

```bash
xattr -dr com.apple.quarantine /path/to/paper-fetch-skill-offline-macos-arm64-cp312
```

移除 quarantine 是用户的信任决定，安装器不会静默绕过 Gatekeeper；若递归
`xattr` 检查本身因权限或 I/O 错误失败，也会在写入前拒绝，不能把检查错误当成
“没有 quarantine”。扫描结果使用不经过管道的匹配方式，避免真实 bundle 中
大量 `com.apple.provenance` 输出触发 `pipefail` / `SIGPIPE`，从而把已经命中的
quarantine 误判为未命中；portable regression 会在 quarantine 行后追加超过管道
缓冲区的模拟 provenance 输出。

构建器在 npm smoke 后移除运行时不使用的 `node_modules/.bin` launcher symlink，并
拒绝把任何其它 payload symlink 写入 checksum 清单。普通安装同样先校验目标：
checksum 清单必须精确覆盖 bundle 中的所有 regular file，拒绝任何 symlink、绝对
路径、`..`、重复条目、缺失条目和未列出的附加 payload。安装器只使用 Python
isolated mode 读取 manifest、规范化路径及执行其它 host-side
preflight，避免调用者的 `PYTHONPATH`、`sitecustomize.py` 或用户 site 在 inventory
拒绝附加 payload 之前执行。随后只
允许不存在、空目录，或同时具有 schema 3
`offline-manifest.json` ownership 和非空 `runtime/python-bin` 安装标记的已有
目录。HOME、HOME 的祖先、非空未拥有目录以及指向这类目录的 symlink 均在清理
旧 payload 之前拒绝。合法升级会清理旧 runtime payload，同时保留安装目录内
`offline.env`，并保留 macOS user-config 中不属于 managed block 的用户内容。

`--purge` 在删除任何用户集成或安装目录之前使用同一 ownership 事实校验目标，
拒绝 `/`、用户 HOME 及其祖先、尚未安装的 bundle root 等危险路径；purge 入口
本身只要是 symlink 就拒绝，即使它指向合法 owned 安装目录，从而避免验证 canonical
target 后只删除链接或发生路径替换竞态。实际删除只使用已验证并规范化的 lexical
target，因此合法的 `<install>/.` 拼写不会在移除用户集成后留下部分卸载；即使
manifest 合法，也必须存在 `runtime/python-bin` 标记。卸载会删除 Linux 与
macOS user-config 的 installer managed block，但保留用户自行写入的其它内容。
该安全项与 Zsh startup symlink 的保留行为共同由
`MAC-AUD-007`、`MAC-AUD-009` 和 `MAC-AUD-010` 跟踪。

### MAC-V4-004：Mac 用户配置和 Zsh

- `--user-config` 在 macOS 写
  `~/Library/Application Support/paper-fetch/.env`；Linux 仍写
  `~/.config/paper-fetch/.env`。路径继续由 `platformdirs` 语义约束。
- `.zshrc` 是符号链接时，安装和卸载都修改其链接目标，不用 `mv` 把链接替换成
  普通文件。
- 重复安装或升级只替换受管理的 user-config block；用户自写键和值保持不变。
  `--uninstall` 删除该 managed block，不把整份用户配置删除。
- MCP cache scope 同时接受调用方给出的路径别名根与其 canonical 根，例如
  macOS 的 `/var/...` 与 `/private/var/...`，或 `/tmp/...` 与
  `/private/tmp/...`。文件仍会
  canonicalize 后写入 index；scope 根以下的 symlink 与目录外路径继续拒绝。

## MAC-V4-003：“离线包”的浏览器边界

`runtime/site-packages` 内包含 `uv.lock` 选定的兼容 Camoufox 0.5.x 和 Playwright
**Python 包**，但不
包含 Camoufox 浏览器 binary。`paper-fetch` 的 fetch 路径不会自动下载浏览器。
构建器要求 wheelhouse 中恰好有一个 Camoufox wheel，读取其 METADATA 验证版本，
安装后再通过 distribution metadata 复核，并把已验证版本写入
`offline-manifest.json.components.camoufox.python_package_version`；声明、lock、
wheel、installed runtime 与 manifest 任一漂移都会 fail closed。
因此：

1. 在仍可联网的目标 Mac 上安装 tarball；
2. 激活离线环境后运行 `python -m camoufox fetch` 下载浏览器 binary，或直接运行
   `<install>/runtime/paper-fetch-python -m camoufox fetch`；
3. 运行 `paper-fetch browser-preflight`，启动浏览器并验证所需 provider；
4. 需要人工登录时再运行 `paper-fetch auth <provider>`；
5. 之后才进入计划中的受限网络或离线环境。

`browser-preflight` 本身会访问网络，但不会下载缺失的 binary；下载动作属于
显式的 `python -m camoufox fetch`。当前证据只证明 Python 包导入和在线准备
路径；“预置后在真正断网环境中启动 Camoufox 并完成 browser-backed fetch”仍是
未关闭审计项，见
[`macos-adaptation-audit.md`](macos-adaptation-audit.md#mac-aud-012)。
在该项关闭前，不应把 macOS tarball 描述为“完全离线浏览器包”。

不依赖 browser 的 provider、静态 `doctor`、CLI/MCP runtime 和已打包公式工具
仍可按各自数据源与凭据边界独立使用。

### MAC-V4-008：Camoufox 官方 Mac bundle 与 custom path 分界

原生 Mac 实测发现，Camoufox 0.5.4 下载的官方 app bundle 把浏览器 executable
放在 `Camoufox.app/Contents/MacOS/camoufox`，把运行时属性表放在
`Camoufox.app/Contents/Resources/properties.json`。如果 paper-fetch 先把 managed
runtime 解析成 executable，再作为 custom `executable_path` 传回 Camoufox，后者
会按 custom-path 语义错误查找 `Contents/MacOS/properties.json`，导致
`browser-preflight`、普通 browser fetch 和持久 auth context 都在创建浏览器前
失败。

当前规则因此明确分成两条：

- 默认 managed runtime 仍先调用
  `camoufox_path(download_if_missing=False)`，保证普通抓取不会隐式下载；但不再传
  `executable_path`，由 Camoufox package 按 active version 自行解析完整 app
  bundle；
- 只有用户显式配置 `PAPER_FETCH_BROWSER_BINARY_PATH` 时才透传 custom
  `executable_path`。这个 override 不再被误用于官方 managed cache。

临时 browser manager 与持久 auth manager 共用该规则。portable unit test 在
Windows / WSL 可验证“managed 省略、两种 manager 的 custom 透传、missing runtime
不下载”的调用语义；原生 Darwin arm64 test 则在显式准备 runtime 后启动两种
context 并打开 `about:blank`。普通 CI 的 `macos-15` job 固定准备
`official/152.0.4-beta.28` 并以 `-n 0` 串行执行该节点；测试只接受当前用户固定的
`~/Library/Caches/camoufox` managed cache，并在调用 Camoufox 前验证 compatibility
flag、active config 和 browser containment，避免把任意目录交给 package manager
清理。测试使用 Camoufox 公开的 `exclude_addons` 排除默认扩展，并设置扩展下载
失败 tripwire；因此 app bundle 证据不依赖已有扩展 cache 或首次启动联网。它不
改变生产默认扩展行为，也不验证默认扩展本身。测试同时传入固定 synthetic
screen constraint，避免 headless 原生 CI 查询 WindowServer/物理显示器。远端
provider 的 CAPTCHA、登录或超时仍是独立的访问状态，不能与 app bundle 创建
失败混为一谈。

## MAC-V4-007：Windows / WSL 同步上游 main

建议把 Mac 适配保留为一组独立、主题清晰的提交，不把长期业务开发直接堆在
适配提交里。普通 CI 已在 `ubuntu-latest` 和 `windows-latest` 执行 portable
contract gate；这些结果用于早期发现漂移，不会提升为原生 Mac 证据。每次同步
上游使用以下顺序：

1. 获取上游并确认新基线：

   ```bash
   git fetch upstream --tags --prune
   git log -1 --oneline upstream/main
   ```

2. 从最新 `upstream/main` 创建新的工作分支，不把旧适配分支直接当新基线：

   ```bash
   git switch -c codex/macos-adaptation-vNext upstream/main
   ```

3. 按顺序重放独立的合约、实现、测试和文档提交。可使用 `git cherry-pick`
   或重新应用小补丁；发生冲突时以最新 v4+ 实现为准，不恢复旧 v1 路径。
4. 更新 `macos-adaptation-contract.toml` 的上游基线和实现引用；同时更新
   `scripts/validate_macos_adaptation.py` 中的
   `EXPECTED_BASELINE_REVISION`、`EXPECTED_CONTRACT_VERSION`、
   `EXPECTED_CHANGE_IDS`、`EXPECTED_AUDIT_IDS` 及对应 validator unit tests。
   如果新版本确实增加或删除 change/audit case，必须同步机器合约与两份人类
   文档，不能只放宽 validator。审查 upstream
   对 `.github/workflows/ci.yml`、`.github/workflows/offline.yml`、
   `scripts/build-offline-package.sh`、`install-offline.sh`、
   `scripts/verify-offline-package.sh`、`installer/manifest.json` 和相关测试的
   改动。
5. **先**运行静态 validator：

   ```bash
   uv run python scripts/validate_macos_adaptation.py
   ```

6. 再运行当前宿主对应的 contract gate：

   Windows PowerShell：

   ```powershell
   scripts/test-macos-contract.ps1
   ```

   WSL / Linux：

   ```bash
   scripts/test-macos-contract.sh
   ```

   WSL 必须使用 Linux Python / venv。位于 `/mnt/*` 的 checkout 只有
   validator-only 价值：NTFS 挂载不能提供可靠的 Unix executable bit、symlink、
   case sensitivity 或 LF checkout 证据。

7. 推送分支后等待 `.github/workflows/ci.yml` 中固定 `macos-15`、CPython
   3.14 的原生 build + verifier gate。Windows 或 WSL 绿灯不能豁免该 gate。
8. 涉及离线包时，再手动运行 `Offline packages` workflow，并核对四个 arm64
   Python ABI tarball 均经过原生 verifier。
9. 发布适配结果前提升 fork 版本并创建新的不可变标签。不得移动或复用上游
   `v4.1.0`；validator 会要求 `pyproject.toml` 的发布版本严格高于
   `source_baseline.version`，标签、Python metadata、changelog 与 release notes
   必须指向 fork 的新版本。

对不可变适配标签做“工具链修复重跑”是另一个受限场景。目标源码 checkout 必须
先通过自身的当前 macOS contract，包括 browser/full extra 与 lockfile 的精确
Camoufox pin；没有当前合约的旧上游 `v4.1.0` 会 fail closed，不能靠 overlay
改造成适配发行版。之后 `posix_tooling_ref` 必须是完整 40 字符 commit SHA，并且
只允许从该受信任 commit 复制以下 POSIX 工具链到同名目标：

- `scripts/build-offline-package.sh`
- `install-offline.sh`
- `scripts/verify-offline-package.sh`

validator 同时在 immutable source 和受信任工具 checkout 内运行，并验证精确的
source/destination copy pair。公式 installer 与其它 Python wheel source 明确不在
copy allow-list 内；tooling 脚本仍属于显式信任边界，不能被描述为业务源码证明。
构建器会在 tooling overlay 存在时把 40 位 tooling SHA 写入
`offline-manifest.json.tooling_revision`，使源码 commit 与覆盖工具 commit 可分别
追溯；未使用 overlay 时该字段省略而不是写入空字符串。Windows tooling ref 遵循
相同不可变 SHA 与 provenance 规则，但只复制 Windows packaging script。

完整 unit 验证继续复用项目 pytest 并行配置：

```bash
PYTHONPATH=src python3 -m pytest tests/unit -q
```

不要为常规 unit / integration 验证添加 `-n 0`；只有 live 或共享外部状态的测试
才按项目规则串行。

## 维护时必须同步的材料

修改 Unix 安装器、macOS 离线构建或 verifier、平台目录、texmath、Camoufox /
Playwright 边界、release CI 时，同一提交应同步：

- [`macos-adaptation-contract.toml`](macos-adaptation-contract.toml)；
- [`macos-adaptation-audit.md`](macos-adaptation-audit.md)；
- 对应 unit / integration 测试；
- 本文和 [`deployment.md`](deployment.md) 中对用户可见的行为；
- `.github/workflows/ci.yml` 的 CPython 3.14 原生 macOS gate，以及 release /
  offline workflow 的 CPython 3.11–3.14 矩阵。

合约 validator 负责检查静态引用、关键字面事实和受信任 tooling overlay 的精确
路径；Ubuntu / Windows portable job 确保两个维护入口持续可执行；原生 runner
负责检查无法从 Windows / WSL 推导的平台行为。
