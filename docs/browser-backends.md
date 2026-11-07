# Browser backend

全部浏览器出版社统一使用 Byparr＋Camoufox，覆盖正文、图片、附件、浏览器 PDF、预检和认证。支持现有 Camoufox／Playwright 平台，Elsevier 也开放 macOS 浏览器阶段。API、HTTP 直连和 provider 获取顺序不变。

## 安装

browser/full extras、离线预置、Camoufox 渠道与版本 pin、准备重试命令统一见
[部署指南：浏览器安装与准备](deployment.md#浏览器安装与准备)。
运行时首次实际使用后端才准备；纯 HTTP、缓存命中与静态诊断不触发准备。

## 选择与配置

`PAPER_FETCH_<PROVIDER>_BROWSER_BACKEND=auto|camoufox|byparr` 均选择 Byparr＋Camoufox；`camoufox` 是兼容别名。组件不可用时报告准备错误。

通用变量如下：

| 变量 | 含义 |
|---|---|
| `PAPER_FETCH_PNAS_BROWSER_BACKEND` | PNAS 后端，默认 `auto` |
| `PAPER_FETCH_BROWSER_COMPONENT_CACHE` | Byparr 组件缓存目录覆盖 |
| `PAPER_FETCH_BROWSER_HEADLESS` | managed runtime 是否 headless |
| `PAPER_FETCH_BROWSER_BINARY_PATH` | 仅用于自行维护、且支持 Camoufox custom-executable metadata 语义的 executable 覆盖 |
| `PAPER_FETCH_BROWSER_PROFILE_DIR` | provider storage-state/profile 目录覆盖 |
| `PAPER_FETCH_BROWSER_USER_DATA_DIR` | profile 目录的后备覆盖 |
| `PAPER_FETCH_BROWSER_TIMEOUT_MS` | browser navigation timeout |
| `PAPER_FETCH_BROWSER_USER_AGENT` | publisher direct HTTP 的可选 UA；Camoufox 本身忽略它以保持生成指纹一致 |

Camoufox 原生持久目录位于 platformdirs 用户数据目录下的
`publisher-browser-profiles/<provider>-camoufox/`，首次未认证访问也会创建。
覆盖优先级为通用 profile、provider 专用 profile、通用 user-data、默认目录；
显式目录记录所属出版社，不同出版社不能共用。原生与 JSON 状态模式独立于后端名称，
目录选择见[状态模式](#状态模式)。

macOS 官方 managed app bundle 把 executable 放在 `Contents/MacOS`，把运行属性表
放在 `Contents/Resources`。不要把官方 cache 内的
`Contents/MacOS/camoufox` 配置为 `PAPER_FETCH_BROWSER_BINARY_PATH`；这样会把
managed bundle 错当成 custom executable。官方 runtime 应保持该变量未设置，
由请求准备和 Camoufox active-version 配置共同管理。只有自定义
runtime 明确实现 Camoufox 的 custom-path metadata 布局时才使用该覆盖。

## 生命周期

同一次请求内，正文、PDF、图片、图页与附件借用同一出版社 context，各阶段只关闭自己
创建的页面；所属 `RuntimeContext` 在 owner 线程释放会话。目录锁、资源调度及进程
归属见 [runtime 生命周期](browser-runtime.md#生命周期与线程边界)。

`doctor` 和 `provider_status` 只做静态依赖与配置检查，不启动浏览器、下载 runtime
或访问出版社。CLI 与 MCP `browser_preflight` 自动准备后执行 live 页面检查，
可保存过滤后的 storage-state；不执行自动认证或 PDF fallback。Preflight 只报告本次
检查，正式 fetch 独立导航并重新执行身份、阻断和正文验收。

### 状态模式

所有浏览器后端的诊断名称均为 `byparr`，引擎为 `camoufox`；内部 `state_mode` 决定
状态归属，不能仅凭后端名称判断目录类型：

| 配置与平台 | 状态模式与目录 |
|---|---|
| Windows/Linux x64 的 PNAS、Elsevier，`auto` 或 `byparr` | 过滤后 JSON，`<provider>-byparr/` |
| 上述 provider 显式 `camoufox`，以及其他支持的 provider/平台 | 原生持久目录，`publisher-browser-profiles/<provider>-camoufox/` |

两种状态不自动合并或迁移。原生模式接受 profile/user-data 覆盖，首次未认证访问也
创建目录。默认 JSON 快照仅初始化尚无原生 profile 的目录；显式 JSON 内容变化按
摘要导入一次，默认快照不覆盖已有状态。已有原生 profile 时，缺少可选 JSON 不阻止使用。
PDF 不用清理后的 JSON 替换原生状态，`save_storage_state=false` 仅禁止 JSON 导出。

`auth` 使用有窗口模式，人工验证后关闭并重开同一状态目录，按正式抓取的窗口配置
（默认无窗口）验证。原生目录是该模式的认证来源；JSON 导出失败独立报告，不使已验证
目录变为认证失败。auth 保留显式 JSON 路径并更新导入摘要。
`paper-fetch-profile.json` 原子记录出版社、导入摘要和实际 context 的状态摘要，
不保存明文凭证。私有缓存绑定真实目录和最新可信摘要，缺少可信摘要时不复用或写入。

## 统一受管 Byparr

全部浏览器 provider 使用 Byparr v2.1.0（提交 `1e726296a3143cbce0982cf4fd47a9a3224094e9`）、Camoufox 0.5.9 和 playwright-captcha 0.1.5。`PAPER_FETCH_<PROVIDER>_BROWSER_BACKEND=auto|camoufox|byparr` 均进入组合链路，诊断的后端为 `byparr`、引擎为 `camoufox`。

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

抓取与 preflight 默认 headless；显式 auth 使用窗口。准备、重试与安装器跳过选项见
[部署指南](deployment.md#浏览器安装与准备)。

## Migration

FlareSolverr 已移除。将 `PAPER_FETCH_<PROVIDER>_BROWSER_BACKEND=flaresolverr`
改为 `auto` 或 `byparr`；旧值明确报告配置错误。
删除 `PAPER_FETCH_CHROME_BINARY_PATH`，自定义浏览器改用
`PAPER_FETCH_BROWSER_BINARY_PATH` 指向 Camoufox。
`--prepare-flaresolverr` 和 `--prepare-browsers flaresolverr` 明确报错并提示
`--prepare-byparr` / `--prepare-browsers byparr`。
已有 FlareSolverr 缓存和状态保留在磁盘，新后端不自动导入；历史采集证据保留原来源名称。
