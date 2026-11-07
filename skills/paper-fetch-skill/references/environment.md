# Environment

仅在配置、凭证、runtime 或工具链实际影响任务时读取对应章节。普通抓取由工具自动准备 runtime，无需 agent 预读更新机制。配置来源见[配置来源与离线 wrapper](#配置来源与离线-wrapper)，runtime 缺失/异常见[运行时准备与授权](#运行时准备与授权)，定位问题见[诊断顺序](#诊断顺序)；图片与公式工具只在相应转换受影响时读。Provider/source/capability 以[运行时 catalog](tool-contract.md#static-provider-catalog)为准。

## 配置来源与离线 wrapper

运行时配置优先级固定为：**进程环境 > 调用方显式 `env_file` > `PAPER_FETCH_ENV_FILE` 指向的文件 > platformdirs 用户配置 > 内置默认值**。CLI diagnostics 的显式层是 `paper-fetch doctor --env-file <path>`；显式参数和环境变量指向同一文件时只读取一次，并归因到显式层。仓库本地 `.env` 不会被隐式加载。

离线安装的 `paper-fetch` / `paper-fetch-mcp` wrapper 只在调用方尚未设置 `PAPER_FETCH_ENV_FILE` 时把它指向 `<install-root>/offline.env`。`activate-offline.sh` 默认安全解析同一文件；使用 installer 的 `--reuse-env-file <path>` 时改为指向该外部文件。dotenv 内容不作为 shell 执行，安装/激活后仍以最终进程环境为运行时最高优先级。不要在诊断输出、日志或报告中复制 secret 值。

## 基础配置与凭证名称

- `PAPER_FETCH_ENV_FILE`：显式 dotenv 文件路径。
- `PAPER_FETCH_DOWNLOAD_DIR`：CLI/MCP 默认下载和 cache scope；未设置时使用 platformdirs 用户数据目录。
- `PAPER_FETCH_SKILL_USER_AGENT`：非 browser metadata/API 请求的可选 User-Agent；未设置时使用 `paper_fetch.config.DEFAULT_USER_AGENT`。
- `CROSSREF_MAILTO`：Crossref polite pool 联系邮箱。
- `ELSEVIER_API_KEY`：Elsevier 官方 API 路线所需的 key；ScienceDirect 浏览器路线不要求该 key。
- `WILEY_TDM_CLIENT_TOKEN`：Wiley 官方 TDM PDF lane 的可选 token 名称；本地 browser 路线是否可用仍由 runtime catalog 与诊断决定。
- `XDG_DATA_HOME`：改变 platformdirs 用户数据基目录，因而影响默认下载和本地工具目录。
- `PAPER_FETCH_RUN_LIVE`：仅用于显式 opt-in 的 live publisher 测试；正常诊断和单元测试不得设置它。

## Browser backend 与 storage-state

- `PAPER_FETCH_BROWSER_HEADLESS`、`PAPER_FETCH_BROWSER_TIMEOUT_MS`：Camoufox managed runtime 的 headless 开关与请求超时；默认分别为 `true`、`120000`。
- `PAPER_FETCH_BROWSER_BINARY_PATH`：已准备好的 Camoufox runtime executable 覆盖项。
- `PAPER_FETCH_BROWSER_PROFILE_DIR`、`PAPER_FETCH_BROWSER_USER_DATA_DIR`：原生状态模式使用的 provider-scoped profile/storage-state 目录覆盖项。组合运行时复用 `PAPER_FETCH_BROWSER_BINARY_PATH`。默认使用 `publisher-browser-profiles/<provider>-camoufox/`。
- `PAPER_FETCH_BROWSER_USER_AGENT`：publisher direct 路线的可选浏览器 UA；它与 `PAPER_FETCH_SKILL_USER_AGENT` 分离。Camoufox 忽略该值，以保持生成的 Firefox 指纹一致。
- `PAPER_FETCH_WILEY_STORAGE_STATE_JSON`、`PAPER_FETCH_WILEY_PROFILE_DIR`：Wiley 的 storage/profile 覆盖。Camoufox 使用出版社原生持久目录；用户要求认证或 preflight/fetch 返回认证需求时运行 `paper-fetch auth <provider>`，交互验证由用户完成。

Byparr 自动处理支持的 Cloudflare interstitial；登录、付费和其他验证仍遵守既有访问边界。自动处理后仍返回 `challenge` / `auth_required` 时，由用户完成必要的人工认证。

静态 `paper-fetch doctor --provider <name> --detail full --json` / MCP `provider_status` 不启动 Camoufox，也不访问出版社页面。需要 live 证明时再运行 CLI `paper-fetch browser-preflight --provider <name>` 或 MCP `browser_preflight(provider=...)`；两者在实际启动浏览器前自动准备 managed runtime。原生模式可更新持久目录，默认另导出 JSON 快照；原 JSON 模式继续恢复过滤后的状态并按配置保存。预检会访问远端页面且可能写状态，不运行 PDF fallback 或自动认证。

同出版社的各浏览器阶段在一次抓取内复用同一 context；native／JSON 状态模式与后端名称独立，HTTP 仍可并行。
其原生目录是认证状态来源，JSON 用于状态快照；默认 JSON 仅初始化尚无原生状态的目录，显式 JSON
内容变化按摘要导入一次。`auth` 人工验证后按正式抓取窗口配置重开同一目录验证，
JSON 导出失败单独报告。`save_storage_state=false` 仅禁止导出 JSON，不禁止更新原生目录。
同目录进程间排队遵守取消和请求期限；目录归属冲突、外部占用和超时必须如实报告，
不删除 Firefox 原生锁或静默回退临时会话。

全部浏览器 provider 在现有 Camoufox／Playwright 平台使用 Byparr＋Camoufox，含 macOS 的 Elsevier 浏览器阶段。`PAPER_FETCH_<PROVIDER>_BROWSER_BACKEND=auto|camoufox|byparr` 均进入组合链路，旧 `camoufox` 是兼容别名。原 Camoufox 配置保留 `<provider>-camoufox/` 原生目录与显式覆盖；Windows/Linux x64 上 PNAS／Elsevier 原有 `auto|byparr` 保留 `<provider>-byparr/` 过滤后 JSON；新开放平台使用原生目录。不自动合并或迁移状态。旧 FlareSolverr 后端值和命令已移除；现有后端配置改用 `auto`、`camoufox` 或 `byparr`，删除旧 `PAPER_FETCH_CHROME_BINARY_PATH`；如需指定可执行文件，使用 `PAPER_FETCH_BROWSER_BINARY_PATH`。不迁移或合并认证目录。

支持平台的安装器统一准备版本锁定的 Byparr、playwright-captcha、Camoufox 与指纹缓存。现有 macOS 离线目标也包含锁定源码、私有依赖、许可证与适配记录；组件损坏需重新安装。源码/pip 安装自动下载固定组件。fetch/preflight 默认 headless，auth 使用窗口。

安装准备失败保留核心安装。用安装环境 Python 执行 `-m paper_fetch.offline_setup --install-root <install-dir> --env-file <config.env> --prepare-browsers all` 可重新准备；也可选 `camoufox` 或 `byparr`；`--prepare-byparr` 等价于 `--prepare-browsers byparr`。缺系统依赖时提供安装指引；下载与本地空白页检查分别限 10 分钟、2 分钟，后者使用临时状态。

## 运行时准备与授权

MCP/CLI/library 在实际进入所选浏览器后端时按需准备 runtime。纯 HTTP 和缓存命中不触发浏览器准备；单次及批量请求共享准备状态。

抓取、auth、preflight 和安装准备共享持久检查记录。最近一次检查成功且组件有效时，24 小时内复用；无需更新也算成功。失败或取消记录最近结果但不延长成功窗口，也不会借更早成功阻止下次重试。缺失、损坏或不兼容时立即准备；渠道、pin/SHA 或 Camoufox Python 包版本变化后重新判断，有效本地 pin 直接复用。记录在文件锁内检查并原子更新，版本不匹配或损坏的记录重新确认。

browser/full 使用锁定的 Camoufox Python 包，默认以 `official/prerelease` 沿用上游排序，从正式版和预发布版中选择当前平台最新兼容浏览器；`prerelease` 表示允许预发布，`official/stable` 仅接受正式版，不自动升级 Python 包，也不使用包配套 browser 隐式 pin。已有显式渠道、版本 pin、SHA、自定义 executable 优先；pin 只准备对应版本。准备时在缓存锁内补写默认渠道，静态探测不写配置。

更新失败但本地有效时继续使用；无可用浏览器则报告准备失败。单次及批量请求复用成功准备，失败后允许下一次调用重试。进度和错误写 stderr，取消继续传播。core 缺少 browser extra 或显式 executable 时跳过托管更新，不自动安装 Python 依赖。`doctor`、状态查询、解析和帮助保持只读。

联网预置最新兼容浏览器和 fpgen 的项目准备命令使用 `python -c "from paper_fetch.providers.browser_runtime.preparation import prepare_camoufox_managed_runtime; from camoufox.fpgen_model import ensure_fpgen_model; prepare_camoufox_managed_runtime(); ensure_fpgen_model()"`。额外环境修复沿用当前任务已有适用授权。

运行时准备不授予出版社访问权限。用户要求认证或 fetch/preflight 返回 `challenge` / `auth_required` 时进入人工 auth；沿用已有授权，交互验证由用户完成。

## 图片与资产工具

- `PAPER_FETCH_IMAGE_TOOLS_DIR`：Ghostscript/libvips 工具目录覆盖；默认还会检查 repo-local 和 platformdirs 用户工具目录。
- `PAPER_FETCH_GHOSTSCRIPT_BIN`：Ghostscript executable 覆盖，用于 EPS → PNG。
- `PAPER_FETCH_VIPS_BIN`：libvips `vips` executable 覆盖，用于 TIFF → PNG。
- `PAPER_FETCH_EPS_DPI`：Ghostscript EPS 输出 DPI，默认 `600`。
- `PAPER_FETCH_IMAGE_TOOL_TIMEOUT_SECONDS`：后端探测/转换子进程超时，默认 `120` 秒。
- `PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY`：HTTP/HTML 资产 worker 上限；实际 provider/runtime 限制仍以 runtime catalog 和运行时为准。

安装入口是 `paper-fetch-install-image-tools`（已安装环境）或仓库脚本 `./install-image-tools.sh`。`paper-fetch doctor --json` / `provider_status(detail="full")` 会报告 Ghostscript/libvips 的 `ready`、`missing`、`timeout` 或 `error`，不自动安装。对应结构化原因包括 `image_conversion_backend_missing`、`image_conversion_backend_timeout` 和 `image_conversion_backend_error`；它们不能被解释为远端 publisher 资产失败。

## 公式工具

- `PAPER_FETCH_FORMULA_TOOLS_DIR`：公式工具目录覆盖。
- `MATHML_CONVERTER_BACKEND`：选择 `texmath`、`mathml-to-latex` 或高级 `mml2tex` backend；未显式选择时优先 `texmath`，失败可回退 `mathml-to-latex`。
- `TEXMATH_BIN`：`texmath` executable 覆盖。
- `MATHML_TO_LATEX_NODE_BIN`、`MATHML_TO_LATEX_SCRIPT`：Node fallback executable/script；离线安装默认指向包内 Playwright driver Node。
- `MATHML_TO_LATEX_WORKER`、`MATHML_TO_LATEX_WORKER_SCRIPT`：可复用 worker 及其脚本开关/覆盖。
- `MATHML_CONVERSION_CACHE_SIZE`：进程内 MathML 转换结果 cache 上限。
- `MML2TEX_JAVA_BIN`、`MML2TEX_CLASSPATH`、`MML2TEX_SAXON_JAR`、`MML2TEX_XMLRESOLVER_JAR`、`MML2TEX_XMLRESOLVER_DATA_JAR`、`MML2TEX_STYLESHEET`、`MML2TEX_CATALOG`：仅在显式 `mml2tex` 高级后端时使用；默认 installer 不准备该 Java/XSLT 工具链。

安装入口是 `paper-fetch-install-formula-tools`（已安装环境）或仓库脚本 `./install-formula-tools.sh`。公式工具缺失只影响相应转换/fallback，不改变 provider 身份。HTML/XML 公式使用随公式工具提供的校验引擎选择源 TeX 或同节点 MathML；工具缺失或校验失败保留原表达和诊断，PDF 转换正文不进入该流程。

## 诊断顺序

按实际问题选择检查：

- 配置或依赖异常：用 `paper-fetch doctor --json` 或 `provider_status(detail="full")` 静态检查。配置来源部分只报告变量名、是否存在和来源层；runtime 和工具诊断可包含路径等运行信息，秘密值保持脱敏。
- 需要真实页面证据：对目标 provider 运行 `browser-preflight` / `browser_preflight`；普通 fetch 不要求先预检。
- 用户要求认证，或结果为 `challenge` / `auth_required`：进入人工 auth。`runtime_error` 按[运行时准备与授权](#运行时准备与授权)处理。
- 修复后按[失败处理](failure-handling.md)判断是否重试，沿用当前任务已有授权。

## 离线安装后的可选配置

Linux/macOS 离线安装器及 Windows EXE 在核心 smoke 成功后提供可选向导，源码在线安装使用各工具的安装入口。凭据隐藏输入，留空保留已有值；下载/安装默认关闭。Unix `--non-interactive`、无终端及 Windows `/SILENT`、`/VERYSILENT` 全部跳过；`--reuse-env-file` 保持外部配置只读。Linux 仅为 Debian/Ubuntu 提供经确认的 APT 辅助安装，macOS 仅复用已有 Homebrew，Windows 使用摘要固定的官方 Ghostscript EXE（需要 UAC、系统注册表）和完整 libvips ZIP。图片工具通过实际 EPS/TIFF 转换后保存绝对路径，桌面 MCP 无需依赖 shell PATH。

Camoufox 可选择准备并验证本地空白页，不访问 provider、不保存登录状态；下载、启动与站点访问状态分开报告。跳过本次安装不会关闭后续运行时自动准备。可选失败/取消不影响核心安装，升级保留凭据与可选工具；卸载默认保留可选工具和共享浏览器缓存。安装器负责升级和卸载；配置或升级后重启已运行的宿主/MCP。
