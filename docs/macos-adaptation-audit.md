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
  `.github/workflows/ci.yml` 把精确 `github.sha` 交给 reusable
  `.github/workflows/verify.yml`，后者在 CPython 3.14 执行原生 build + verifier；
  release / offline workflow 实际执行四个 `macos-15` ABI job；普通 CI 还在
  Ubuntu 与 Windows 分别执行 portable contract entrypoint。release workflow
  对 lightweight/annotated tag peel 到完整 commit SHA；同一 SHA 的 reusable
  `package.yml` 与九目标 frozen snapshot resolver 并行运行，随后 offline matrix
  构建，Release 不运行或等待 unit/普通 CI；source/tooling checkout、Python
  distributions、离线构建、发布 target 与 provenance 都绑定该 SHA。provenance 步骤还会校验
  `actions/attest-build-provenance` v4.2.2 的完整 SHA、精确一次调用和
  `release-assets/**/*` subject path；每目标实际 staging 的 dependency manifest
  与 CycloneDX SBOM 随对应 artifact 上传。POSIX/Windows builder 分别固定使用
  `.venv/bin/python` 与 `.venv/Scripts/python.exe`，保证 SBOM 生成器来自锁定 dev
  环境，而不是 runner 全局 Python。所有 artifact/release upload、attestation
  和 publication 还必须在对应目录通过 raw/URL-encoded sentinel 扫描；扫描只报告
  变量名与路径，命中或扫描错误都阻断后续步骤。发布资产与 checksum 文件执行强制
  `fsync`，目录项只在平台支持 directory descriptor 时 best-effort 同步，避免 Windows
  portable gate 把不支持目录 `fsync` 误判为资产失败。
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
  checksum 工具之前验证精确 payload inventory，再校验每个 digest。机器合约、
  validator 和 unit test 还要求根目录与随包公式资源的两套 Node manifest 声明
  相同兼容范围，并要求两套 lockfile 对 KaTeX 和 `mathml-to-latex` 解析一致。
- 平台：S / L 只能检查脚本存在和调用；D 才能解释实际 Mach-O。
- 关闭条件：原生 verifier 对发布 tarball 通过，且 manifest target 与产物一致。

### MAC-AUD-005

**可迁移并签名的 texmath**

- 要求：texmath 是实体文件；非系统 dylib 收进 `formula-tools/lib`；install
  name 使用 `@rpath` / `@loader_path`；texmath 和随包 dylib 均有可验证的
  ad-hoc 签名。构建 setup 固定为 `haskell-actions/setup` v2.12.0 的完整 SHA，
  GHC 9.10.3 与 Cabal 3.12.1.0；reusable `verify.yml` 精确使用一次，
  `offline.yml` 精确使用两次同一 pin。
- 自动证据：机器合约 validator 拒绝 action、版本注释、SHA、GHC/Cabal 或使用
  次数漂移；原生构建继续执行 smoke、`otool -L`、
  `codesign --verify --strict` 和公式转换 smoke。
- 平台：只有 D 可作为关闭证据。
- 关闭条件：从解压 bundle 复制到随机绝对 install root 后，仍通过版本和复杂
  MathML 转换。
- 限制：ad-hoc 签名不是 Developer ID 签名，也不等于 notarization 或
  Gatekeeper 发行者信任。v2.12.0 随附的 GHCup 0.2.6.2 只更新构建工具链，
  不改变 texmath 0.13.2、公式入口或发布产物接口。

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
  以及 `.github/workflows/ci.yml` 调用的 `verify.yml` 中固定 `macos-15` 的精确
  原生 pytest node。
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
  合约、Camoufox 兼容范围或已解析 wheelhouse 版本一致性校验的旧上游 `v4.1.0`
  拒绝重打包。POSIX/Windows tooling
  ref 都必须是完整 40 字符 commit SHA；POSIX 只允许 builder、installer、verifier
  与 staged-evidence generator 四个同名 source/destination pair；Windows 把
  packaging script、同一 evidence generator、原生 EXE lifecycle verifier、installer
  helper、installer manifest 和 Inno `.iss` 作为来自同一 tooling SHA 的原子集合，均不
  复制 Python wheel source。tooling 脚本是显式信任边界；产物 manifest 分别记录
  source `git_revision` 与可选 `tooling_revision`。Windows embedded CPython 的
  version、python.org URL 和官方 SHA-256 同时固定在 installer manifest 与平台合约，
  下载后必须先校验再解压，expected/actual digest 写入 staged provenance/SBOM。
- 自动证据：source 与 tooling validator 的精确 overlay pair allow-list、SHA gate 与
  `tests/unit/test_ci_release_workflow.py`；原生 Windows offline job 还对最终 Inno EXE
  串行执行 silent install、installed CLI/doctor/provider/formula/browser smoke、覆盖
  升级、用户数据保留和 silent uninstall；卸载后递归枚举安装根并与唯一允许的
  `offline.env`、`downloads/`、`downloads/user-owned.txt` 精确比较，未知残留也失败。
- 关闭条件：只有已经带当前合约的不可变适配标签可做工具链重跑；发布 fork 适配
  必须提升版本并创建新标签，不能靠 overlay 把上游 `v4.1.0` 冒充为适配发布。
  Windows lifecycle 关闭证据必须来自原生 runner；S/L 级只证明脚本和 workflow
  静态契约，不能替代真实 Inno、HKCU 与安装状态。

### MAC-AUD-012

**真正断网的 Camoufox 启动**

- 当前状态：**开放**。
- 已有证据：离线 runtime 包含 Camoufox / Playwright Python 包，安装 verifier
  检查 import；联网时可先用该 runtime 执行 `python -m camoufox fetch` 下载
  browser binary，再运行 `paper-fetch browser-preflight` 验证启动和 provider
  state；CLI live browser 路径也可在策略允许时按需准备，MCP/库默认禁止。
- 补充 portable 证据：selected-browser 正文 DOM 稳定等待、MDPI delayed-body
  readiness、Wiley 稳定正文就绪后将页头登录导航交给正文感知验收且保留强阻断，
  以及“已确认的候选/快速 attempt 访问门槛不被后续候选的传输/导航
  失败或下一候选、保守重试的 deadline timeout 覆盖”均由纯 Python 单测锁定；
  PNAS 单次导航/8 秒稳定正文预算、provider 精确 image/font/media 阻断、一次性
  preflight HTML cache 的 DOI/URL/runtime 指纹隔离、AIP 禁用跨 context 复用，以及
  Royal/Annual/ACS figure discovery 的 runtime context/page 复用也由 portable mock
  回归锁定；
  CLI/MCP 批量预解析和 provider lane 排队也不得提前消耗 item fetch deadline，
  且重置时保留 item-local 解析缓存；live MCP 还只接受精确
  access-boundary marker，而不接受一般 limited 结果；HTTP-200 empty shell 的重试
  会切换到下一个既有 provider URL。这些证据能区分远端 access state 与 runtime
  failure，但不构成原生 macOS 断网启动证明。
- Browser 网络行为证据：portable 回归验证主导航、redirect、跨源子资源与 service
  worker 使用浏览器原生行为，不安装 context-wide URL/DNS route，带 cookie/storage/
  profile 的 context 不再由项目绑定单一 origin，external CDP 恢复借用既有 context。
  Provider image/font/media 优化仍是 page-scope 资源类型策略；catalog compiler 继续固定
  browser deadline、timeout、retry、QPS、acceptance、asset scope 和 cap，但 catalog
  host/sensitive-header 不自动成为授权 allowlist。机器合约不声明 browser SSRF、
  credential origin 或 service-worker 阻断保证；direct HTTP/API 和资产 transport 的
  基础 URL/redirect/凭据策略由独立回归继续锁定。
  这些行为在 Darwin 与其他平台共用 Python 实现，但不替代原生浏览器启动证据。
- Browser state/cache scope 证据：portable 回归覆盖默认 provider data 目录、profile、
  user-data 和显式 storage-state 的 canonical path/content digest；只有 context 创建成功
  且实际注入 state 才记录 use，并在 fetch 完成时按最终 digest 写 private sidecar。
  `path/exists/used` diagnostics、public→private 禁止和不同 private scope 隔离均为跨平台
  Python 契约；它不扩大原生 macOS browser launch 的证据范围。
- 主文档响应诊断证据：portable mock 同时锁定 Playwright `requestfinished` lifecycle、
  Content-Length、捕获 DOM 字节和 Navigation Timing；HTTP 200 小空壳可据此区分“响应已
  完整结束”与“采样时仍在传输”。诊断只保存脱敏 URL、选定数值和 transfer 布尔事实，
  不保存 header/cookie/query/原始 HTML。该证据验证跨平台 Python 采样契约，不代表
  原生 macOS 或真实 publisher 必然重现相同网络时序。
- 二进制资产 portable 证据：共享 hostname transport 与 browser-owned image/file/PDF
  bytes 都经过 MIME、Content-Length/实际字节、像素、累计预算、取消、唯一 staging 和
  原子发布。正文资产使用显式 20 秒/route cap 2 的 assets route；每篇论文、每个 host
  只有首资源 direct probe，browser recovery 成功后才让同源剩余资源复用 browser，
  不跨论文持久化。同一 runtime 的 figure/supplementary 共用文件、字节、像素与最多
  4 worker 的预算；逐资源另记 candidate resolution，browser prepare/release 单列
  stage timing。gzip/未知长度/转换放大、pending future 取消、host 并发、论文生命周期、
  arXiv archive 解压和 staging 清理由小阈值 unit test 固定；
  这同样不宣称真实 publisher 或离线 Camoufox bundle 已在 macOS 上完成资产下载。
- 图片质量 portable 证据：arXiv source archive、Copernicus JATS alternatives、AIP
  Silverchair `srcset` 与 T&F authentic fixture 锁定官方原图优先级；官方未暴露或访问
  受限分别进入稳定 provenance，preview 不冒充 full-size。该证据不证明远端站点三轮
  都继续暴露相同 rendition，真实质量仍需本地显式 live 审计。
- T&F page-preparation 证据：portable 回归验证 provider hook 在最终 HTML capture
  前执行，并且只把文章 DOM 暴露的同源官方 CSV table action（单次脚本、并发 4、
  每表 2 秒、最多 24 表、输入顺序保持）或已加载的同页 table payload 有界水合为
  语义 table；`macos-15` 常规 CI 在原生 Camoufox bundle context gate 后重跑该 hook、
  T&F batch/fallback、preflight cache、资源阻断与共享 figure page 节点。它证明平台
  调用契约一致，不等于真实站点 live access，也不关闭断网 browser-backed fetch 缺口。
- Hosted 准备边界：常规原生 CI 通过 Camoufox 已支持的 `GITHUB_TOKEN` 环境变量
  传入只读 workflow token，避免匿名 Releases API rate limit；凭据不写入命令、
  cache、diagnostics 或 artifact。Live 验证只保留本地入口，由操作者预置 runtime
  并管理所需访问凭据。
- 缺失证据：在网络完全断开的原生 macOS 15 arm64 环境中，从已预置 cache
  启动 Camoufox，并对 browser-backed provider 完成受控 launch/fetch 的可重复
  测试。
- 明确边界：Camoufox browser binary 不随 tarball 分发，安装器和静态诊断不下载。
  真实 CLI 浏览器路径默认可按需准备，MCP/库默认关闭且必须显式 opt-in；两类入口在
  禁用策略或断网时仍要求提前执行 `python -m camoufox fetch`。preflight 本身也需要
  publisher 网络访问。关闭此项前不得宣称“完整离线浏览器支持”。
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
- 按需准备边界：CLI 浏览器路径默认允许、MCP/库默认禁止；环境与单次请求均可覆盖。
  安装、精确修复和 24 小时更新检查必须走 Camoufox 官方 CLI，并保留跨进程锁、进度、
  取消和 900 秒预算。显式 custom binary 不得进入任何 managed-cache 维护路径。
- 依赖一致性：browser/full extra 接受 `camoufox>=0.5.5,<0.6`；开发与原生 CI
  继续使用 `uv.lock` 的具体版本，离线 artifact 使用依赖 wheelhouse 解析出的兼容版本。
  POSIX 构建器从唯一 wheel 的 METADATA 解析版本，验证 installed distribution
  与该 wheel 完全一致，并把实际值写入
  `components.camoufox.python_package_version` manifest 字段。
- portable 自动证据：`tests/unit/test_camoufox_backend.py` 分别锁定 managed
  ephemeral、managed persistent、两种 manager 的 explicit override 与策略关闭时的
  no-download 行为；`tests/unit/test_camoufox_preparation.py` 锁定首次安装、节流、失败
  回退、安全修复、并发与取消。Windows / WSL 可以执行这些纯 mock/临时目录节点，但
  不能证明 app bundle 实际可启动。
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
5. 发布 fork 适配前本地运行完整并行 unit，再提升版本并创建新不可变标签；Release
   只构建发布产物，不运行或等待远程 unit/普通 CI；不移动/复用上游 `v4.1.0`；
6. `MAC-AUD-012` 保持开放不会阻止非浏览器离线安装发布，但 Release Notes 和
   文档必须继续披露该限制。
7. `MAC-AUD-013` 的 portable mock 不能替代原生 prepared-bundle 双 context
   启动证据；更新 Camoufox package 或 app layout 后必须重新执行该节点。

任一 Windows / WSL 绿灯都不能作为跳过原生 Mac gate 的理由。
