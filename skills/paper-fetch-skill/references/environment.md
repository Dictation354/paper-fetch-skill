# Environment

仅在配置、凭证、runtime 或工具链影响任务时读取。普通抓取自动准备 runtime，无需 agent 先做更新检查。provider/source/capability 以[运行时 catalog](tool-contract.md#static-provider-catalog)为准。

## 配置来源与离线 wrapper

优先级：**进程环境 > 调用方显式 env_file > PAPER_FETCH_ENV_FILE > platformdirs 用户配置 > 内置默认值**。CLI diagnostics 的显式层为 `doctor --env-file <path>`；同一路径只读取一次并归因显式层。仓库 `.env` 不隐式加载。

离线 wrapper 仅在调用方未设置 PAPER_FETCH_ENV_FILE 时指向 `<install-root>/offline.env`；activate-offline.sh 默认安全解析该文件，installer `--reuse-env-file <path>` 则复用外部文件。dotenv 不作为 shell 执行。最终进程环境始终优先，诊断和报告不复制 secret。

## 基础配置与凭证名称

| 环境变量 | 作用 |
| --- | --- |
| PAPER_FETCH_ENV_FILE | 显式 dotenv 路径。 |
| PAPER_FETCH_DOWNLOAD_DIR | 默认下载/cache scope；未设时为 platformdirs 用户数据目录。 |
| PAPER_FETCH_SKILL_USER_AGENT | 非 browser metadata/API 请求 UA。 |
| CROSSREF_MAILTO | Crossref polite pool 联系邮箱。 |
| ELSEVIER_API_KEY | Elsevier 官方 API key，ScienceDirect browser 路线不要求它。 |
| WILEY_TDM_CLIENT_TOKEN | Wiley 官方 TDM PDF lane 的可选 token。 |
| XDG_DATA_HOME | platformdirs 用户数据基目录。 |
| PAPER_FETCH_RUN_LIVE | 仅显式 opt-in live 测试使用，普通任务不设置。 |

## Browser backend 与 storage-state

全部 browser provider 使用锁定 Byparr 3.1.1；Windows/Linux x64 的底层引擎为 Invisible，其余平台保留 Camoufox。`PAPER_FETCH_<PROVIDER>_BROWSER_BACKEND=auto|camoufox|byparr` 都进入组合链路，旧 camoufox 值为兼容别名，仍影响既有状态模式绑定。

| 环境变量 | 作用 |
| --- | --- |
| PAPER_FETCH_BROWSER_HEADLESS / PAPER_FETCH_BROWSER_TIMEOUT_MS | 默认 true / 120000；fetch/preflight 默认 headless，auth 使用窗口。 |
| PAPER_FETCH_BROWSER_BINARY_PATH | 当前平台引擎 executable 覆盖，须匹配 Invisible seal 或 Camoufox metadata。 |
| PAPER_FETCH_BROWSER_PROFILE_DIR / PAPER_FETCH_BROWSER_USER_DATA_DIR | provider-scoped 原生状态目录覆盖。 |
| PAPER_FETCH_BROWSER_USER_AGENT | publisher direct UA，独立于 API UA；Camoufox 忽略以保持指纹一致。 |
| PAPER_FETCH_WILEY_STORAGE_STATE_JSON / PAPER_FETCH_WILEY_PROFILE_DIR | Wiley 状态/profile 覆盖。 |

原 Camoufox 配置保留 `<provider>-camoufox/` 原生目录及显式覆盖；Windows/Linux x64 上 PNAS/Elsevier 原有 auto|byparr 保留 `<provider>-byparr/` 过滤后 JSON，新开放平台使用原生目录。不自动迁移或合并状态。旧 flaresolverr 值及 PAPER_FETCH_CHROME_BINARY_PATH 已移除，改用支持的后端值和 PAPER_FETCH_BROWSER_BINARY_PATH。

同出版社一次抓取的各 browser 阶段复用 context，HTTP 仍可并行。原生目录是认证来源，JSON 是快照：默认 JSON 只初始化尚无原生状态的目录，显式 JSON 内容变化按摘要导入一次。`save_storage_state=false` 仅禁止 JSON 导出，不禁止原生目录更新。同目录进程间排队遵守取消和期限；归属冲突、外部占用和超时如实报告，不删除 Firefox 锁或静默回退临时会话。

Byparr 自动处理支持的 Cloudflare interstitial。实际 fetch/preflight 仍返回 challenge/auth_required，或用户要求认证时，用 `paper-fetch auth <provider>` 进入用户交互验证。auth 后按正式抓取窗口配置重开同目录核验，JSON 导出失败单独报告；登录、付费和其他访问控制不因 runtime 准备而获得授权。预检参数见[工具契约](tool-contract.md#browser-preflight-contract)。

## 运行时准备与授权

MCP/CLI/library 进入所选 browser 时按需准备 runtime；纯 HTTP 和 cache 命中不触发。单次及批量请求共享准备状态，doctor、状态查询、解析及帮助保持只读。

- 安装器准备锁定 Byparr 和平台引擎依赖；源码/pip 安装自动下载固定组件。Byparr 损坏需重新准备，缺 Python browser extra 不自动安装依赖；自定义 executable 不自动删除或更新。
- 抓取/auth/preflight/安装准备共享持久检查记录。成功且组件有效时 24 小时内复用，失败或取消不延长成功窗口；组件缺失、损坏、不兼容或 pin/渠道变化时重新判断。
- Camoufox 使用锁定 Python 包，默认 official/prerelease 选择当前平台最新兼容 browser；official/stable 仅正式版。显式渠道、版本 pin、SHA 和 executable 优先，不自动升级 Python 包。
- 更新失败但本地仍有效时继续使用；无可用引擎则报告准备失败。进度和错误写 stderr，取消继续传播。读取 backend/code/stage/runtime_state/version/diagnostic_path 定位，不把组件故障报成 publisher 拒绝。

离线环境重新准备命令：用安装环境 Python 执行 `-m paper_fetch.offline_setup --install-root <install-dir> --env-file <config.env> --prepare-browsers all`，也可选 camoufox 或 byparr；`--prepare-byparr` 等价于后者。缺系统依赖时按诊断指引处理，额外环境修改沿用任务已有授权。安装准备失败保留核心安装。

## 图片与资产工具

- PAPER_FETCH_IMAGE_TOOLS_DIR：工具目录覆盖；也检查 repo-local 和用户工具目录。
- PAPER_FETCH_GHOSTSCRIPT_BIN / PAPER_FETCH_VIPS_BIN：EPS→PNG / TIFF→PNG executable 覆盖。
- PAPER_FETCH_EPS_DPI / PAPER_FETCH_IMAGE_TOOL_TIMEOUT_SECONDS：默认 600 DPI / 120 秒。
- PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY：HTTP/HTML 资产 worker 上限，仍受 provider/runtime 限制。

安装入口 `paper-fetch-install-image-tools` 或仓库 `./install-image-tools.sh`。doctor / provider_status(detail="full") 只诊断 ready/missing/timeout/error，不自动安装。image_conversion_backend_missing/timeout/error 是本地转换工具问题，不能归为远端资产失败。

## 公式工具

- PAPER_FETCH_FORMULA_TOOLS_DIR：工具目录覆盖。
- MATHML_CONVERTER_BACKEND：texmath（默认优先）、mathml-to-latex 或显式高级 mml2tex。
- TEXMATH_BIN：texmath executable；MATHML_TO_LATEX_NODE_BIN / MATHML_TO_LATEX_SCRIPT：Node fallback executable/script，离线默认使用 Playwright driver Node。
- MATHML_TO_LATEX_WORKER / MATHML_TO_LATEX_WORKER_SCRIPT：复用 worker 开关/路径；MATHML_CONVERSION_CACHE_SIZE：进程内 cache 上限。
- MML2TEX_JAVA_BIN / MML2TEX_CLASSPATH / MML2TEX_SAXON_JAR / MML2TEX_XMLRESOLVER_JAR / MML2TEX_XMLRESOLVER_DATA_JAR / MML2TEX_STYLESHEET / MML2TEX_CATALOG：仅显式 mml2tex 使用，默认 installer 不准备 Java/XSLT 链。

安装入口 `paper-fetch-install-formula-tools` 或仓库 `./install-formula-tools.sh`。缺工具只影响相应 HTML/XML 转换/fallback，保留原表达及诊断；PDF 正文不进入该流程。

## 诊断顺序

按实际问题选择：配置/依赖用筛选后的 doctor/provider_status；需要真实页面证据用目标 provider 的 browser-preflight；认证需求进入人工 auth。普通 fetch 不要求先预检，静态 ready 不证明远端页面健康或授权。修复后按[失败处理](failure-handling.md)决定是否重试。

## 离线安装后的可选配置

离线安装器在核心 smoke 后提供可选配置；非交互/静默安装跳过，reuse-env-file 保持外部配置只读。凭据隐藏输入、留空保留原值，下载/安装默认关闭。可选失败或取消不影响核心安装，跳过 browser 准备不关闭后续自动准备。升级保留凭据和可选工具，卸载默认保留可选工具及共享 browser cache；配置或升级后重启已运行宿主/MCP。
