# Browser backend

Windows/Linux x64 的 PNAS 默认使用 FlareSolverr 与系统 Google Chrome；Elsevier 浏览器阶段固定使用同一后端，不支持的平台跳过。macOS、其他架构的 PNAS 及其余出版社继续使用 Camoufox。所有 provider 都通过
`paper_fetch.providers.browser_runtime` facade 获取受管 context；生命周期由请求 runtime 管理。

PNAS、Science、Wiley HTML 在正文连续两次指纹一致（观察间隔 750ms）后，
通过浏览器 owner 线程内的一次同步 `page.evaluate` 捕获含 doctype 的完整 HTML、
标题和最终 URL。权限检查使用 provider preparation 前的快照，preparation 后重新
捕获以保留展开的引用。捕获异常、导航切换或结果无效时沿用原生捕获路径；
请求 deadline 与协作取消检查保持生效，取消直接传播。

## 安装

默认 core 安装不包含浏览器依赖：

```bash
python -m pip install "paper-fetch-skill[browser]"
```

需要浏览器与 PDF 能力时安装：

```bash
python -m pip install "paper-fetch-skill[full]"
```

离线安装包始终按 `full` 构建，但不重新分发浏览器 binary。完全离线环境需提前
准备 Camoufox runtime，包括相邻配置、addons、字体和 fpgen 指纹模型；只复制可执行文件
不足以组成可用 runtime。CLI、MCP 和 Python API 只建立准备作用域，首次使用后端才准备；HTTP、缓存命中与静态诊断不触发准备。批次复用成功结果，失败后允许下一次调用重试。auth、preflight 和安装器共用持久记录。
运行时不自动安装缺失的 Python 依赖；core 安装缺少 browser extra，或指定
`PAPER_FETCH_BROWSER_BINARY_PATH` 时，跳过托管更新。
安装器默认准备平台支持的后端，并提供跳过开关；准备后验证真实后端本地启动，
详见 [离线包](deployment.md#离线包)。

browser/full extras 固定 `camoufox==0.5.9`，不自动升级 Python 包。未显式指定
渠道或 browser pin 时，默认跟踪 `official/prerelease`，由 Camoufox 官方版本
发现的排序和兼容判断，从正式版和预发布版中选择当前平台最新兼容浏览器。
`prerelease` 表示允许预发布，也接受正式版；`stable` 仅接受正式版。
准备时在缓存锁内补写默认渠道，active 配置缺少渠道时自动补齐；静态探测不写配置。
用户已有渠道、版本 pin、SHA 和自定义 executable 保持优先。可用
`python -m camoufox set official/stable` 跟踪 stable，或用
`python -m camoufox set official/prerelease/<version>` 固定版本。
显式 pin 只准备对应版本，有效本地 pin 直接复用。最近一次检查成功且本地组件有效时，24 小时内不查询远端；“无需更新”也算成功。失败或取消只记录最近结果，不延长成功窗口，也不使用更早的成功时间阻止重试。记录在文件锁内复核并原子写入；不包含成功状态的时间记录会重新确认。缺失、损坏或不兼容允许立即准备，更新失败时可复用兼容本地组件。安装器、CLI、MCP、API、auth 和 preflight 共用记录。

联网阶段可先用项目准备逻辑预置最新兼容浏览器和 fpgen 模型：

```bash
python - <<'PYCODE'
from paper_fetch.providers.browser_runtime.preparation import prepare_camoufox_managed_runtime
assert prepare_camoufox_managed_runtime().valid
PYCODE
```

fpgen 模型不包含在 Python wheel 中；首次生成指纹也可能下载模型到 fpgen 包目录，
完全离线前需确认该目录可写并完成准备。
项目模型准备入口在原下载请求失败时，通过 GitHub 官方 Release API 获取同一固定 tag
和文件名的资产；压缩包及每个模型文件仍使用 Camoufox 包内固定的 SHA-256 校验，
校验失败不触发回退。托管与自定义 executable 的模型准备均在启动 Playwright 之前完成，
下载失败时直接返回错误。

## 选择与配置

`PAPER_FETCH_<PROVIDER>_BROWSER_BACKEND=auto|camoufox|flaresolverr` 统一选择已声明支持的后端，默认 `auto` 按 provider 和平台选择。现有 PNAS 变量保持兼容。显式选择不受支持的后端会报告配置错误，不自动切换。

通用变量如下：

| 变量 | 含义 |
|---|---|
| `PAPER_FETCH_PNAS_BROWSER_BACKEND` | PNAS 后端，默认 `auto` |
| `PAPER_FETCH_CHROME_BINARY_PATH` | 系统 Google Chrome 路径覆盖；不改变 Camoufox 配置 |
| `PAPER_FETCH_BROWSER_HEADLESS` | managed runtime 是否 headless |
| `PAPER_FETCH_BROWSER_BINARY_PATH` | 仅用于自行维护、且支持 Camoufox custom-executable metadata 语义的 executable 覆盖 |
| `PAPER_FETCH_BROWSER_PROFILE_DIR` | provider storage-state/profile 目录覆盖 |
| `PAPER_FETCH_BROWSER_USER_DATA_DIR` | profile 目录的后备覆盖 |
| `PAPER_FETCH_BROWSER_TIMEOUT_MS` | browser navigation timeout |
| `PAPER_FETCH_BROWSER_USER_AGENT` | publisher direct HTTP 的可选 UA；Camoufox 本身忽略它以保持生成指纹一致 |

Camoufox 原生持久目录位于 platformdirs 用户数据目录下的
`publisher-browser-profiles/<provider>-camoufox/`，首次未认证访问也会创建。
覆盖优先级保持为通用 profile、provider 专用 profile、通用 user-data、默认目录；
显式目录记录所属出版社，不同出版社不能共用。`storage-state.json` 仅为兼容快照。FlareSolverr 使用 provider 隔离的 JSON 状态目录，见下文。

macOS 官方 managed app bundle 把 executable 放在 `Contents/MacOS`，把运行属性表
放在 `Contents/Resources`。不要把官方 cache 内的
`Contents/MacOS/camoufox` 配置为 `PAPER_FETCH_BROWSER_BINARY_PATH`；这样会把
managed bundle 错当成 custom executable。官方 runtime 应保持该变量未设置，
由请求准备和 Camoufox active-version 配置共同管理。只有自定义
runtime 明确实现 Camoufox 的 custom-path metadata 布局时才使用该覆盖。

## 生命周期

Camoufox 出版社（含 AIP、IEEE）的 auth、预检、HTML、PDF 浏览器回退、图页、图片恢复
和补充材料统一以 `persistent_context=True` 打开原生持久目录。同一次抓取内借用同一
出版社 context，各阶段只关闭自己创建的页面，所属 `RuntimeContext` 最终关闭会话。
浏览器工作在所属线程执行，资产调度复用 caller-thread 机制，HTTP 仍可并行。
目录规范化后使用进程间排他锁，同目录请求排队，不同出版社可并行；等待遵守取消和请求期限。
切换出版社前关闭上一会话并释放目录锁，不交叉持锁等待。外部占用、目录归属冲突、
元数据损坏和等待超时明确报错，不删除 Firefox 原生锁，不回退临时会话。
纯 HTTP 和缓存命中不触发浏览器准备。

`auth` 使用有窗口模式；人工验证后关闭并重开同一目录，按正式抓取的窗口配置
（默认无窗口）验证。原生目录是认证状态的主要来源；JSON 导出失败单独报告，不使
已验证目录变为认证失败。默认 JSON 快照 仅初始化尚无原生 profile 的目录；显式 JSON
内容变化按摘要导入一次，默认快照不覆盖已有原生状态。auth 保留显式 JSON 路径并更新其导入摘要；已有原生 profile 时，缺少可选 JSON 不阻止使用原生状态。PDF 不用清理后的 JSON
替换原生状态。`save_storage_state=false` 仅禁止 JSON 导出，浏览器仍更新原生目录。
目录元数据 `paper-fetch-profile.json` 原子记录出版社、导入摘要和实际 context 的
状态摘要，不保存明文凭证。私有缓存绑定真实目录和最新可信摘要；缺少可信摘要时
禁止该私有缓存复用与写入。

`doctor` 和 `provider_status` 只做静态依赖/配置检查，不启动浏览器、不下载
runtime、不访问出版社页面。CLI 与 MCP `browser_preflight` 在实际启动前自动
准备 managed runtime，并打开页面、按请求保存过滤后的 storage-state。两者都不会
自动认证、绕过 challenge/paywall，也不会调用 PDF fallback。

Preflight 只报告本次 live 检查；正式 fetch 独立导航并重新执行身份、阻断与正文验收。
共享 direct-first 路径中，图片、附件或 PDF 的 direct 401/403 只允许一次 browser-byte 恢复；
`response.body()`、page `arrayBuffer()`、canvas 或 download/file bytes 都会先进入统一
MIME、大小、像素、预算、staging 与原子发布检查。

## PNAS / Elsevier 系统 Chrome 与按需 FlareSolverr

Windows 安装器和 Linux x64 在线／离线安装器在核心安装后自动准备，支持首次安装、升级和同版本重装；在线 `--lite`、macOS 和其他架构跳过。准备失败、缺依赖、拒绝安装或取消均保留核心安装。离线安装器此阶段可能联网；静默／非交互模式允许用户级组件准备（离线包不下载 FlareSolverr 源码和依赖），缺系统依赖时只输出指引，不等待输入或提权。

检查当前 Python、Playwright、系统 Google Chrome（115+）路径和版本，Linux 另查共享库、headless 的 Xvfb、只读 X11 socket 所需 bubblewrap 及 namespace。Chrome 显式路径优先且无效时要求修正；Windows 依次检查注册表、标准目录、PATH，Linux 检查命令和标准位置。Debian/Ubuntu 显示缺项与 APT 命令，默认不安装，确认后由 sudo 接收密码并重新检测；Chrome 优先使用源中候选，无候选时经确认下载 [Google 官方 deb](https://support.google.com/chrome/answer/95346) 并由 APT 安装。Windows 缺 Chrome 只提供官网指引，其他发行版提供手动安装指引。

抓取和 preflight 默认 headless，失败不会弹窗。显式 `auth` 保持 headed；Linux headless 使用 Xvfb，Windows 使用上游的隐藏窗口模式，沿用 1920×1080 窗口配置。Linux 还需满足 Chrome 实际共享库依赖。WSL `/tmp/.X11-unix` 只读时，受管进程通过 rootless bubblewrap 的 user/mount/pid namespaces 使用私有可写 socket 目录；不改 WSLg 挂载，不提权或安装系统软件。缺少 Xvfb、bubblewrap 或 namespace 能力时返回准备错误。

安装后准备或首次进入 PNAS / Elsevier 浏览器路线时下载 FlareSolverr v3.5.2（提交 `93125d6ea6956906c8dfa29e169b2dc67d993dc3`）和隔离依赖。源码及完整依赖清单、SHA-256 见包内 `flaresolverr-manifest.json` 与 `flaresolverr-requirements.lock`。使用当前 CPython 3.11–3.14 的隔离子进程直接解包加载私有 wheel／纯 Python 源码；Windows embedded Python 不需要 pip、venv 或编译器。主环境不安装 Selenium。静态诊断、身份解析、缓存满足的请求及其余出版社不会下载 FlareSolverr。

运行时保存在用户数据目录 `flaresolverr/`；文件锁、校验、暂存解包与原子发布保证失败时保留有效版本。根据实际 Chrome build 从 Google Chrome for Testing 官方渠道准备 ChromeDriver，并按平台与 Chrome 完整版本缓存；Chrome 更新后重新匹配。每个服务复制自己的驱动供上游 patch，避免修改共享缓存或启动时再次下载。

薄启动器加载官方源码，绑定 Chrome 与驱动，移除上游忽略证书错误的参数，保留 TLS 校验。服务只监听随机 loopback 端口，私有控制接口带随机凭据，只暴露自己创建的会话 CDP 地址。新会话先访问对应 provider 主页（PNAS 或 ScienceDirect），再访问文章候选。FlareSolverr 导航期间 Playwright 只处理事件与既有资源路由；导航结束后由 Playwright 检查正文并收取资产。正文、图片、PDF、附件共用该上下文；按各 provider 的获取顺序验收，独立补充材料允许只读材料索引。上游的 `Challenge solved!` 和填充状态码不作为全文成功依据。

状态目录按 provider 隔离为 `publisher-browser-profiles/pnas-flaresolverr/` 与 `publisher-browser-profiles/elsevier-flaresolverr/`，只在现有验收提交规则允许时保存过滤后的 cookies/localStorage，不导入 Firefox profile。Camoufox binary/profile 变量保留其原含义。能力缓存与来源诊断记录实际后端、状态摘要以及 Chrome／驱动版本。准备、导航和启动共用请求期限与取消机制；退出时清理所属服务、ChromeDriver、Chrome、CDP 和 Xvfb。Linux/Windows x64 离线包内置固定源码、私有 Python 依赖、许可证和组件清单，位于 `runtime/browser-components/flaresolverr/`；macOS 不组装该组件。源码、摘要和依赖在构建阶段进入 frozen snapshot、inventory、checksum 和 SBOM。离线组件损坏或缺失报告安装错误，不联网回补源码。源码/pip 安装继续按锁定版本准备源码与依赖，运行时不升级它们。Chrome、ChromeDriver、Camoufox binary 和指纹模型由准备流程管理。

Elsevier 复用 `flaresolverr/` 中已校验的程序和驱动缓存。ScienceDirect 主文档响应结合最终 URL、PII 与页面 DOI 关联；保留实际 `403 → 200` 响应轨迹，不采用 solver 填充的状态。四阶段顺序及公开 source 见 [provider 说明](providers.md#3-provider-全文主路径)。

安装后准备复用上述校验与缓存锁，下载预算 10 分钟；单独的 2 分钟本地启动检查按配置的 headless/headful 创建临时状态目录，验证 CDP 和 `about:blank` 脚本，不读取出版社登录态、不调用主页导航，完成或取消后关闭所属进程。重试：安装环境 Python 执行 `-m paper_fetch.offline_setup --install-root <install-dir> --env-file <config.env> --prepare-browsers all`，也可重跑安装器。运行时继续修复缓存缺失、损坏及 Chrome 更新后的驱动匹配。

`--prepare-browsers` 可选 `all`、`camoufox` 或 `flaresolverr`；兼容选项 `--prepare-flaresolverr`
等价于单独准备 FlareSolverr。离线安装将汇总保存到 `browser-setup-results.txt`。
