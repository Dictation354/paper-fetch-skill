# macOS 适配审计矩阵

本文定义 macOS 适配需要哪些证据，以及 Windows、WSL 和原生 Mac 各自能证明
什么。它是持续审计清单，不是某一次 CI run 的结果抄本。实现和静态引用的事实源
是 [`macos-adaptation-contract.toml`](macos-adaptation-contract.toml)，变更
背景和同步流程见
[`macos-adaptation-changes.md`](macos-adaptation-changes.md)。

## 证据等级

| 等级 | 环境 | 可以证明 | 不能替代 |
| --- | --- | --- | --- |
| S | Windows 原生 | TOML / YAML / Python 静态契约、文件存在、文本和 LF 策略 | POSIX mode、symlink、`/bin/zsh`、Mach-O、`xattr`、Gatekeeper |
| L | WSL / Linux 原生文件系统 | S 级证据，以及 Linux shell、pytest、部分 mode / symlink 行为 | Darwin syscall、macOS `platformdirs`、Mach-O、`codesign`、`otool`、`xattr`、Gatekeeper |
| D | 原生 macOS 15 arm64 | Darwin 安装、Zsh、Mac 用户目录、Mach-O、codesign、xattr 和 tarball verifier | Developer ID/notarization；未执行的真实断网 browser launch |

`/mnt/*` 下的 WSL checkout 只计 S 级 validator 证据。即使测试显示绿色，也不能
升级为 L 级 symlink、mode、case sensitivity 或 LF checkout 证据。

## 审计 case

### MAC-AUD-001

**上游基线可追溯**

- 要求：合约记录上游仓库、`v4.1.0` 和完整 commit
  `fc3bd96e8d781667a2e86e90dc6e8e35a8a26fa7`。
- 自动证据：`uv run python scripts/validate_macos_adaptation.py`。
- 平台：S / L / D。
- 关闭条件：更新上游时，基线、contract version、change/audit ID 常量、测试与
  所有实现引用同步更新；旧 v1 合约不被复制回来。上游 `v4.1.0` 标签保持
  不可移动，发布 fork 适配必须提升版本并创建新标签。

### MAC-AUD-002

**固定原生 macOS 15 gate**

- 要求：CPython 3.11、3.12、3.13、3.14 的 macOS arm64 离线 job 都固定
  `macos-15`，生成 `.tar.gz`，运行原生 verifier，artifact 缺失即失败。
- 自动证据：静态 contract gate 检查 workflow；普通 push/PR 的
  `.github/workflows/ci.yml` 在 CPython 3.14 执行原生 build + verifier，
  release / offline workflow 实际执行四个 `macos-15` ABI job；普通 CI 还在
  Ubuntu 与 Windows 分别执行 portable contract entrypoint。
- 平台：S / L 只能验证 YAML；D 才能提供平台证据。
- 关闭条件：四个 ABI job 都在固定 runner 通过，不能用 `macos-latest` 或
  Windows / WSL 结果代替。

### MAC-AUD-003

**目标、ABI 和最低系统安装前检查**

- 要求：manifest 声明 macOS、arm64、Python tag 和
  `target.minimum_os_version = "15.0"`；安装器在任何用户写入前检查
  platform、arch、标准 GIL CPython ABI、解释器架构和 `sw_vers`。构建器在
  staging 清理前拒绝非标准 ABI、解释器/目标架构不匹配、非安全单组件包名、
  危险 canonical build root、位于 staging 内的 output dir 和无 ownership
  marker 的非空 staging；正式产物必须由同目录临时文件原子发布。
- 自动证据：installer unit tests、合约 validator、原生 tar verifier。
- 平台：S / L 可检查分支和字面契约；D 验证真实 `uname` / `sw_vers`。
- 关闭条件：路径穿越包名在清理前失败；错误平台、架构、Rosetta Python、
  free-threaded/debug ABI 或低版本系统都 fail closed，且临时 HOME 没有发生
  shell、skill、MCP 或用户配置写入；打包失败不覆盖已有正式 artifact，也不留下
  看似完整的截断文件。

### MAC-AUD-004

**manifest、checksum 与 Mach-O 兼容性**

- 要求：归档先经 `tarfile.data_filter` 安全预检；安装前校验 bundle manifest，
  并要求 checksum 清单与除清单自身外的所有 regular file 精确一一对应；构建器
  在 npm smoke 后移除不使用的 `.bin` launcher symlink，再拒绝任何其它 payload
  symlink、危险路径、重复、缺失和未列出的 payload；公式二进制和
  Playwright Node 为精确 arm64，非系统
  Mach-O 依赖 canonical 后仍在 bundle 内，不使用 symlink 或绝对 build-host
  `LC_RPATH`，随包 Node 只在递归闭包通过后真实启动。
- 自动证据：`scripts/verify-offline-package.sh` 使用 `file`、`lipo -archs` 和
  `otool -L` 检查 texmath、dylib 与 Node，并执行 Node `--version`；安装器在
  checksum 工具之前验证精确 payload inventory，再校验每个 digest。
- 平台：S / L 只能检查脚本存在和调用；D 才能解释实际 Mach-O。
- 关闭条件：原生 verifier 对发布 tarball 通过，且 manifest target 与产物一致。

### MAC-AUD-005

**可迁移并签名的 texmath**

- 要求：texmath 是实体文件；非系统 dylib 收进 `formula-tools/lib`；install
  name 使用 `@rpath` / `@loader_path`；texmath 和随包 dylib 均有可验证的
  ad-hoc 签名。
- 自动证据：构建 smoke、`otool -L`、`codesign --verify --strict` 和公式转换
  smoke。
- 平台：只有 D 可作为关闭证据。
- 关闭条件：从解压 bundle 复制到随机绝对 install root 后，仍通过版本和复杂
  MathML 转换。
- 限制：ad-hoc 签名不是 Developer ID 签名，也不等于 notarization 或
  Gatekeeper 发行者信任。

### MAC-AUD-006

**原生 tar 安装 verifier**

- 要求：Mac tarball 经过 `/bin/zsh`、`.zshrc` 和临时 HOME 的完整安装、
  runtime 布局、CLI/MCP、skill、dotenv、公式工具、卸载和 purge 检查；安装阶段
  的联网 / 构建命令被 guard 拦截。原生流程还必须真实覆盖嵌套 native 文件的
  quarantine fail-closed、相对 `.zshrc` symlink、owned upgrade、`offline.env`
  与 user-config 非 managed 内容保留，以及卸载 managed user-config block。
- 安全前置：解包前拒绝 absolute/`..`/特殊文件/逃逸 link；执行 texmath 或 Node
  前递归检查 quarantine。
- 自动证据：`scripts/verify-offline-package.sh <macos-tarball>` 和
  `offline.yml`。
- 平台：D。
- 关闭条件：四个 CPython ABI 的原生 job 都执行 verifier；不能只构建并上传。
- 限制：这里的“断网 guard”证明安装器不现场下载或构建，不证明 Camoufox
  浏览器能在断网时启动。

### MAC-AUD-007

**quarantine、xattr 与 Gatekeeper 边界**

- 要求：安装器在用户级写入前递归检查整个 bundle 的
  `com.apple.quarantine`，包括嵌套 native extension、公式 dylib 与
  Playwright driver Node；发现时 fail closed，并给出用户显式
  `xattr -dr com.apple.quarantine <bundle>` 的恢复提示；权限/I/O 等
  `xattr` 检查错误同样 fail closed。
- 自动证据：installer 的 quarantine/error tests 和原生 verifier 对嵌套 `.so`
  写入 xattr 的 case；portable test 还生成大于管道缓冲区的 provenance 输出，
  防止 `set -o pipefail` 下的早退 `grep` / `SIGPIPE` 漏判。
- 平台：D；Windows / WSL 不提供 `xattr` 或 Gatekeeper 证据。
- 关闭条件：带 quarantine 的测试 bundle 在写入前失败，用户显式清除后可重试。
- 限制：项目不会静默移除 quarantine；也不把 ad-hoc codesign 宣称为
  notarization。

### MAC-AUD-008

**Mac `platformdirs` 用户配置与系统路径别名**

- 要求：macOS `--user-config` 写
  `~/Library/Application Support/paper-fetch/.env`，Linux 仍写
  `~/.config/paper-fetch/.env`；默认 `--no-user-config` 不写两者。MCP cache
  scope 应把 macOS `/var/...` 与 `/private/var/...`，或 `/tmp/...` 与
  `/private/tmp/...` 识别为同一根目录，同时
  继续拒绝 scope 根以下的 symlink 与目录外文件。
- 自动证据：platform-specific installer unit test、等价目录 alias cache test，
  以及 `.github/workflows/ci.yml` 中固定 `macos-15` 的精确原生 pytest node。
  tarball verifier 不承担 cache alias 证据。
- 平台：L 可证明 Linux 路径和通用目录 alias；D 才能证明 Mac 路径与系统
  `/var` 或 `/tmp` alias。
- 关闭条件：用户既有内容被保留，只替换受管理 block；路径中空格处理正确；
  原生 tempfile cache/resource 测试不因 canonical path 拼写差异失效。

### MAC-AUD-009

**safe purge**

- 要求：普通安装仅允许不存在、空目录，或同时带 schema 3 project/entrypoint
  ownership manifest 与 `runtime/python-bin` marker 的已有目标；HOME、祖先、
  非空未拥有目录和指向它的 symlink 必须在旧 payload 清理前拒绝。合法升级保留
  `offline.env` 和 user-config 非 managed 内容。所有 host Python preflight 使用
  isolated mode，调用者的 `PYTHONPATH` / `sitecustomize.py` 不能在 exact inventory
  之前执行。`--purge` 在删除任何用户集成
  之前使用相同 ownership 事实校验目标，并无条件拒绝 symlink 形式的 purge 入口，
  即使 canonical target 本身合法 owned；删除使用已验证的 normalized lexical target。
- 自动证据：installer unit tests、原生 verifier 的 owned upgrade 与合法 purge。
- 平台：L / D；D 保留最终原生证据。
- 关闭条件：所有拒绝 case 都没有发生 payload 清理、部分卸载或目录删除；只有
  合法安装目录可升级/删除，升级后的用户 secret/note 保持不变。

### MAC-AUD-010

**Zsh 与 symlink checkout**

- 要求：Mac verifier 固定 `/bin/zsh`；`.zshrc` 为 symlink 时，安装和卸载均
  修改链接目标，不用 `mv` 覆盖 symlink 本身。
- 自动证据：installer unit test 和原生 tar verifier 的安装、owned upgrade、
  卸载全流程。
- 平台：D。WSL 中安装的 zsh 或 NTFS symlink 不能替代 `/bin/zsh` 和 macOS
  filesystem 行为。
- 关闭条件：安装、重复安装、卸载后 symlink 仍为 symlink，目标文件的 managed
  block 正确增加、替换和删除。

### MAC-AUD-011

**Windows / WSL contract gate 与 LF**

- 要求：Windows 运行 `scripts/test-macos-contract.ps1`，WSL / Linux 运行
  `scripts/test-macos-contract.sh`；两者先执行 validator，再执行各自允许的
  Python/static test nodes。`.gitattributes` 固定 POSIX 入口 LF，validator
  检查实际字节。普通 CI 必须在 `windows-latest` 和 `ubuntu-latest` 各执行一次
  portable gate。
- 自动证据：

  ```bash
  uv run python scripts/validate_macos_adaptation.py
  scripts/test-macos-contract.sh
  ```

  ```powershell
  scripts/test-macos-contract.ps1
  ```

- 平台：S / L。
- 关闭条件：Windows 与 WSL 能提前发现 drift，且 `/mnt/*` 明确降级为
  validator-only；它们不宣称覆盖 Mach-O、原生 Zsh、xattr 或 Gatekeeper。

**带当前合约的不可变源码与受信任 tooling overlay**

- 要求：源码标签不移动，且必须在 overlay 前通过自身的当前 Mac contract；没有
  合约或精确 Camoufox pin 的旧上游 `v4.1.0` 拒绝重打包。POSIX/Windows tooling
  ref 都必须是完整 40 字符 commit SHA；POSIX 只允许 builder、installer、verifier
  三个同名 source/destination pair，Windows 只允许自己的 packaging script，均不
  复制 Python wheel source。tooling 脚本是显式信任边界；产物 manifest 分别记录
  source `git_revision` 与可选 `tooling_revision`。
- 自动证据：source 与 tooling validator 的精确 overlay pair allow-list、SHA gate 与
  `tests/unit/test_ci_release_workflow.py`。
- 关闭条件：只有已经带当前合约的不可变适配标签可做工具链重跑；发布 fork 适配
  必须提升版本并创建新标签，不能靠 overlay 把上游 `v4.1.0` 冒充为适配发布。

### MAC-AUD-012

**真正断网的 Camoufox 启动**

- 当前状态：**开放**。
- 已有证据：离线 runtime 包含 Camoufox / Playwright Python 包，安装 verifier
  检查 import；联网时可先用该 runtime 执行 `python -m camoufox fetch` 下载
  browser binary，再运行 `paper-fetch browser-preflight` 验证启动和 provider
  state。
- 补充 portable 证据：selected-browser 正文 DOM 稳定等待、MDPI delayed-body
  readiness，以及“已确认的候选/快速 attempt 访问门槛不被下一候选或保守重试的
  deadline timeout 覆盖”均由纯 Python 单测锁定；live MCP 还只接受精确
  access-boundary marker，而不接受一般 limited 结果；HTTP-200 empty shell 的重试
  会切换到下一个既有 provider URL。这些证据能区分远端 access state 与 runtime
  failure，但不构成原生 macOS 断网启动证明。
- Hosted 准备边界：常规原生 CI 与 live workflow 通过 Camoufox 已支持的
  `GITHUB_TOKEN` 环境变量传入只读 workflow token，避免匿名 Releases API
  rate limit；凭据不写入命令、cache、diagnostics 或 artifact。
- 缺失证据：在网络完全断开的原生 macOS 15 arm64 环境中，从已预置 cache
  启动 Camoufox，并对 browser-backed provider 完成受控 launch/fetch 的可重复
  测试。
- 明确边界：Camoufox browser binary 不随 tarball 分发，paper fetch 不会自动
  下载，`browser-preflight` 也不代替 `python -m camoufox fetch`；preflight
  本身需要联网。关闭此项前不得宣称“完整离线浏览器支持”。
- 建议关闭方式：增加独立的原生 Mac 两阶段测试——联网预置后冻结 cache，再在
  禁网 sandbox 中验证 browser launch；测试应区分“浏览器成功启动”和“远端
  publisher 页面当然不可访问”。

### MAC-AUD-013

**Camoufox 官方 macOS app bundle 解析**

- 状态：**已实现，需持续保留原生回归**。
- 要求：默认 managed runtime 先以 `download_if_missing=False` 验证已经预置，随后
  让 Camoufox package 自行选择 active app bundle，不能把
  `Contents/MacOS/camoufox` 强制作为 custom `executable_path`；只有显式
  `PAPER_FETCH_BROWSER_BINARY_PATH` 才透传 custom path。临时 fetch/preflight
  context 和持久 auth context 必须遵循同一规则。
- 依赖一致性：browser/full extra 接受 `camoufox>=0.5.4,<0.6`，具体版本由
  `uv.lock` 固定；原生 CI 与离线 artifact 因此使用同一 locked package。
  POSIX 构建器从 lockfile 解析版本，验证下载 wheel METADATA 与 installed
  distribution 完全一致，并把实际值写入
  `components.camoufox.python_package_version` manifest 字段。
- portable 自动证据：`tests/unit/test_camoufox_backend.py` 分别锁定 managed
  ephemeral、managed persistent、两种 manager 的 explicit override 和 missing-runtime
  no-download 行为。Windows / WSL 可以执行这些纯 mock 节点，但不能证明 app
  bundle 实际可启动。
- 原生自动证据：普通 CI 的 `macos-15` job 显式准备固定的
  `official/152.0.4-beta.28`，设置 `PAPER_FETCH_RUN_NATIVE_CAMOUFOX_TEST=1`，再以
  `-n 0` 串行运行 `tests/integration/test_camoufox_native_macos.py`。测试要求 Darwin
  arm64，只接受当前用户固定的 managed cache，并在调用 Camoufox 前验证 compatibility
  flag、active config 和 browser 目录 containment；随后验证 executable 位于
  `Contents/MacOS`、属性表位于 `Contents/Resources`，分别启动临时和持久 context
  并打开 `about:blank`。测试通过公开的 `exclude_addons` 参数排除默认扩展，并
  对真实扩展下载设置失败 tripwire，使该本地启动证据不依赖已有扩展 cache 或
  首次启动联网；它不验证 Camoufox 的默认扩展行为。固定 synthetic screen
  constraint 还避免 headless CI 依赖已登录的 WindowServer 或物理显示器。
- 本轮发现证据：2026-08-01 的原生 arm64 Mac 测试在修复前稳定报
  `Contents/MacOS/properties.json` 不存在；修复后 Science、PNAS、MDPI 的 live
  preflight 成功进入远端页面。Wiley timeout 和 IEEE challenge 属于远端访问
  状态，而不是 browser context 创建失败。
- 关闭条件：上述两类 unit test 和原生双 context test 通过；显式 custom path
  继续透传；移除 prepared runtime 后普通 fetch 仍 fail closed 且不下载。
- 与 `MAC-AUD-012` 的边界：本项证明已预置官方 Mac bundle 的本地启动与路径
  解析，不证明在真正断网 sandbox 中完成 browser-backed provider fetch，因此
  `MAC-AUD-012` 继续开放。

## 合并和发布判定

普通业务变更只要不触及 Mac 合约范围，可沿用项目常规 gate。修改 Unix 安装器、
离线构建 / verifier、平台目录、公式工具、Playwright、release CI 时：

1. 同步机器合约、测试和人类文档；
2. Windows / WSL 先跑可用 contract gate；
3. 原生 `macos-15` gate 必须通过；
4. 影响 tarball 时四个 ABI 产物必须经过原生 verifier；
5. 发布 fork 适配前提升版本并创建新不可变标签；不移动/复用上游 `v4.1.0`；
6. `MAC-AUD-012` 保持开放不会阻止非浏览器离线安装发布，但 Release Notes 和
   文档必须继续披露该限制。
7. `MAC-AUD-013` 的 portable mock 不能替代原生 prepared-bundle 双 context
   启动证据；更新 Camoufox package 或 app layout 后必须重新执行该节点。

任一 Windows / WSL 绿灯都不能作为跳过原生 Mac gate 的理由。
