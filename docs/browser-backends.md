# Browser backend

全部 13 个浏览器出版社统一使用 Byparr＋Camoufox，覆盖正文、图片、附件、浏览器 PDF、预检和认证。支持现有 Camoufox／Playwright 平台，Elsevier 也开放 macOS 浏览器阶段。API、HTTP 直连和 provider 获取顺序不变。

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

`PAPER_FETCH_<PROVIDER>_BROWSER_BACKEND=auto|camoufox|byparr` 均选择 Byparr＋Camoufox；`camoufox` 是兼容别名。组件不可用时报告准备错误。

通用变量如下：

| 变量 | 含义 |
|---|---|
| `PAPER_FETCH_PNAS_BROWSER_BACKEND` | PNAS 后端，默认 `auto` |
| `PAPER_FETCH_BROWSER_HEADLESS` | managed runtime 是否 headless |
| `PAPER_FETCH_BROWSER_BINARY_PATH` | 仅用于自行维护、且支持 Camoufox custom-executable metadata 语义的 executable 覆盖 |
| `PAPER_FETCH_BROWSER_PROFILE_DIR` | provider storage-state/profile 目录覆盖 |
| `PAPER_FETCH_BROWSER_USER_DATA_DIR` | profile 目录的后备覆盖 |
| `PAPER_FETCH_BROWSER_TIMEOUT_MS` | browser navigation timeout |
| `PAPER_FETCH_BROWSER_USER_AGENT` | publisher direct HTTP 的可选 UA；Camoufox 本身忽略它以保持生成指纹一致 |

Camoufox 原生持久目录位于 platformdirs 用户数据目录下的
`publisher-browser-profiles/<provider>-camoufox/`，首次未认证访问也会创建。
覆盖优先级保持为通用 profile、provider 专用 profile、通用 user-data、默认目录；
显式目录记录所属出版社，不同出版社不能共用。`storage-state.json` 仅为兼容快照。Byparr 使用 provider 隔离的 JSON 状态目录，见下文。

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

## 统一受管 Byparr

全部浏览器 provider 使用 Byparr v2.1.0（提交 `1e726296a3143cbce0982cf4fd47a9a3224094e9`）、Camoufox 0.5.9 和 playwright-captcha 0.1.1。`PAPER_FETCH_<PROVIDER>_BROWSER_BACKEND=auto|camoufox|byparr` 均进入组合链路，诊断的后端为 `byparr`、引擎为 `camoufox`。

源码/pip 安装在首次使用时自动下载锁定源码与私有纯 Python 依赖；离线包内置
`runtime/browser-components/byparr/`，包含完整上游源码、GPL-3.0 许可证、适配记录、
组件清单和文件摘要。源码与依赖同时进入 frozen snapshot、inventory、checksum 和 SBOM。
离线组件缺失或损坏报告安装错误，需重新安装，不联网回补。包内
`byparr-manifest.json` 和 `byparr-requirements.lock` 记录版本、来源与 SHA-256。
运行时缓存位于用户数据目录 `byparr/`，通过目录锁、校验、暂存与原子发布复用。

项目复用已有 Camoufox 浏览器与指纹模型准备缓存；`PAPER_FETCH_BROWSER_BINARY_PATH`
对 Camoufox 和 Byparr 都有效，`PAPER_FETCH_BROWSER_COMPONENT_CACHE` 可覆盖组件缓存。
主进程与子进程使用同一 Playwright 安装（`>=1.58,<1.64`）及其 Node driver，启动
仅监听 loopback 的共享 Firefox 服务。Byparr 异步控制端与同步提取端连接同一上下文、
同一页面，直接访问文章候选 URL。等待期间同步端继续处理事件与资源路由；随后复用
正文就绪判断、MathJax 原始 MathML 采集、身份检查及图片、PDF、附件流程。

每次 URL 导航均由统一入口托管，保留原 `wait_until` 和剩余期限；图片／下载不等待 HTML 正文或统一 networkidle。点击前安装监控，在原页面、弹窗、iframe 关系中解题，不重放点击或另建 context。浏览器 GET 成功路径保留；明确 Cloudflare challenge 才在同一 context 内处理，并在原预算内重试一次 GET。

私有适配层复用锁定 Byparr 的 Cloudflare interstitial ClickSolver，分开导航、检测和解题；普通 403、登录、付费和不支持的 challenge 沿用原分类。同一 context 串行解题，重复观察复用任务。同步端真实 Response／Download 与统一 acceptance 决定成功。结构化事件分别记录 `navigation_managed`、`challenge_detected`、`solver_called`、`solver_click`、`challenge_result`，关联 operation、页面和真实响应序列。初始化不算 solver 调用，自动验证不算点击。
验证码插件的可写脚本与 registry 使用请求私有副本，共享组件保持只读。
准备、导航与等待受请求期限和取消约束，退出时清理所属控制进程、Node 与 Camoufox。

状态通过内部 `state_mode` 保持既有绑定：原 Camoufox 配置保留原生持久目录 `publisher-browser-profiles/<provider>-camoufox/`，继续接受 profile/user-data 覆盖，由既有 profile owner 管理排他锁、导入摘要和认证重放。Windows/Linux x64 上 PNAS／Elsevier 原有 `auto|byparr` 配置保留 `<provider>-byparr/` 的过滤后 JSON 状态；显式 `camoufox` 保留原生目录。新开放的 Elsevier 平台使用原生 profile。两种状态不自动合并或迁移。
抓取与 preflight 默认 headless；显式 auth 使用窗口。

安装后默认准备当前平台支持的后端；在线 `--lite`、POSIX `--skip-browser-prepare`
和 Windows `/SKIPBROWSERPREPARE` 可跳过。非交互准备允许用户级下载；缺 Linux 共享库时
提供系统安装指引，交互模式须确认后才调用 APT。无需 Chrome、ChromeDriver、Selenium、
Xvfb 或 bubblewrap。浏览器和指纹模型准备可能联网。

独立重试：安装环境 Python 执行
`-m paper_fetch.offline_setup --install-root <install-dir> --env-file <config.env> --prepare-browsers all`。
`--prepare-browsers all|camoufox|byparr` 与 `--prepare-byparr` 均准备整套组合运行时，浏览器／指纹与 Byparr 组件分别复用一次准备。
下载预算 10 分钟，本地启动检查另限 2 分钟，仅使用临时状态与 `about:blank` 脚本。
失败或取消保留核心安装，结果与重试命令保存在 `browser-setup-results.txt`。

## Migration

FlareSolverr 已移除。将 `PAPER_FETCH_<PROVIDER>_BROWSER_BACKEND=flaresolverr`
改为 `auto` 或 `byparr`；旧值明确报告配置错误。
删除 `PAPER_FETCH_CHROME_BINARY_PATH`，自定义浏览器改用
`PAPER_FETCH_BROWSER_BINARY_PATH` 指向 Camoufox。
`--prepare-flaresolverr` 和 `--prepare-browsers flaresolverr` 明确报错并提示
`--prepare-byparr` / `--prepare-browsers byparr`。
已有 FlareSolverr 缓存和状态保留在磁盘，新后端不自动导入；历史采集证据保留原来源名称。
