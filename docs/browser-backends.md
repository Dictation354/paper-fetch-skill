# Browser backend

全部浏览器出版社统一使用 Byparr 3.1.1，覆盖正文、图片、附件、浏览器 PDF、预检和认证。支持现有 Camoufox／Playwright 平台，Elsevier 也开放 macOS 浏览器阶段。API、HTTP 直连和 provider 获取顺序不变。

## 安装

browser/full extras、离线预置、Camoufox 渠道与版本 pin、准备重试命令统一见
[部署指南：浏览器安装与准备](deployment.md#浏览器安装与准备)。
运行时首次实际使用后端才准备；纯 HTTP、缓存命中与静态诊断不触发准备。

## 选择与配置

`PAPER_FETCH_<PROVIDER>_BROWSER_BACKEND=auto|camoufox|byparr` 均选择受管 Byparr；`camoufox` 是兼容别名。组件不可用时报告准备错误。

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

所有浏览器后端的诊断名称均为 `byparr`，引擎由平台选择 `invisible` 或 `camoufox`；内部 `state_mode` 决定
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

全部浏览器 provider 使用 Byparr v3.1.1（提交 `b041dd2998110fc61789ae65e2506bd5b79edba5`）。Windows/Linux x64 使用 InvisiblePlaywright 0.47.1、与其匹配的 invisible-core 58.56.0 和 seal 校验的 Firefox 引擎；macOS 与 ARM 保留 Camoufox 0.5.9，避免移除现有平台支持。各平台均接入新版 Byparr 的 locator/polling 挑战处理逻辑，替代旧 ClickSolver 和 shadow-root addon。

`auto|camoufox|byparr` 仍是同一后端的兼容选项，状态目录和 native/JSON 绑定沿用上表。`PAPER_FETCH_BROWSER_BINARY_PATH` 覆盖当前平台引擎的 executable：Invisible 要求与其 release seal 匹配，Camoufox 要求其自有 metadata 布局，两个引擎的 executable 不能互换。

组件清单、源码 SHA-256 和纯 Python 私有依赖仍由 `byparr-manifest.json`、`byparr-requirements.lock` 管理。离线包保留完整上游源码、许可证和适配说明；浏览器 binary 继续按需准备。组件缓存由 `PAPER_FETCH_BROWSER_COMPONENT_CACHE` 覆盖。

Invisible 沿用上游的自动 GeoIP 时区和语言选择，可通过 `BROWSER_TIMEZONE`、`BROWSER_LOCALE` 显式设置；安装器的本地空白页检查使用固定设置，不要求外部定位。

Invisible 使用自己的 Python protocol transport，同步提取与挑战处理在所属线程复用一个 context，不再经过共享 Node 浏览器服务。macOS/ARM 的 Camoufox 仍使用共享 Playwright（`>=1.58,<1.63`）连接。新版上游异步解题函数在 Invisible 所属线程编译为同步调用，仅转换 async/await、导入和等待绑定；选择器、点击间隔及算法保持一致。独立发行版的 Python 3.14 FastAPI/GeoIP 初始化不进入项目的 CPython 3.11–3.14 适配路径。

Invisible 不实现 HTTP APIRequestContext，项目沿用原有 host HTTP GET 通道并同步 Cookie，受挑战的请求仍在原浏览器 context 中恢复一次。原生 profile 租约、过滤后 JSON 的验收提交、请求期限和取消归属保持原有语义。

结构化事件保留 `navigation_managed`、`challenge_detected`、`solver_called`、`solver_click`、`challenge_result`。只有真实成功响应或下载才记为 `cleared`；页面挑战标记消失但尚无成功响应时记为 `awaiting_response`。实际 Response/Download 和统一 acceptance 决定抓取结果。

## Migration

FlareSolverr 已移除。将 `PAPER_FETCH_<PROVIDER>_BROWSER_BACKEND=flaresolverr`
改为 `auto` 或 `byparr`；旧值明确报告配置错误。
删除 `PAPER_FETCH_CHROME_BINARY_PATH`，自定义浏览器改用
`PAPER_FETCH_BROWSER_BINARY_PATH` 指向 Camoufox。
`--prepare-flaresolverr` 和 `--prepare-browsers flaresolverr` 明确报错并提示
`--prepare-byparr` / `--prepare-browsers byparr`。
已有 FlareSolverr 缓存和状态保留在磁盘，新后端不自动导入；历史采集证据保留原来源名称。
