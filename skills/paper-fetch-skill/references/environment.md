# Environment

本文件只说明配置来源、运行时工具链和诊断入口。Provider/source/capability 名单不在静态文档复制；MCP 宿主通过 `resources/read` 读取 `resource://paper-fetch/provider-catalog`，再用 `provider_status(provider=...)` 判断当前机器是否就绪。

## 配置来源与离线 wrapper

运行时配置优先级固定为：**进程环境 > 调用方显式 `env_file` > `PAPER_FETCH_ENV_FILE` 指向的文件 > platformdirs 用户配置 > 内置默认值**。CLI diagnostics 的显式层是 `paper-fetch doctor --env-file <path>`；显式参数和环境变量指向同一文件时只读取一次，并归因到显式层。仓库本地 `.env` 不会被隐式加载。

兼容表述：process environment > an explicit `env_file` argument > the file named by `PAPER_FETCH_ENV_FILE` > the platformdirs user config file > built-in defaults。

离线安装的 `paper-fetch` / `paper-fetch-mcp` wrapper 只在调用方尚未设置 `PAPER_FETCH_ENV_FILE` 时把它指向 `<install-root>/offline.env`。`activate-offline.sh` 默认安全解析同一文件；使用 installer 的 `--reuse-env-file <path>` 时改为指向该外部文件。dotenv 内容不作为 shell 执行，安装/激活后仍以最终进程环境为运行时最高优先级。不要在诊断输出、日志或报告中复制 secret 值。

## 基础配置与凭证名称

- `PAPER_FETCH_ENV_FILE`：显式 dotenv 文件路径。
- `PAPER_FETCH_DOWNLOAD_DIR`：CLI/MCP 默认下载和 cache scope；未设置时使用 platformdirs 用户数据目录。
- `PAPER_FETCH_SKILL_USER_AGENT`：非 browser metadata/API 请求的可选 User-Agent；未设置时使用 `paper_fetch.config.DEFAULT_USER_AGENT`。
- `CROSSREF_MAILTO`：Crossref polite pool 联系邮箱。
- `ELSEVIER_API_KEY`：Elsevier 官方全文路线所需的 key 名称。
- `WILEY_TDM_CLIENT_TOKEN`：Wiley 官方 TDM PDF lane 的可选 token 名称；本地 browser 路线是否可用仍由 runtime catalog 与诊断决定。
- `XDG_DATA_HOME`：改变 platformdirs 用户数据基目录，因而影响默认下载和本地工具目录。
- `PAPER_FETCH_RUN_LIVE`：仅用于显式 opt-in 的 live publisher 测试；正常诊断和单元测试不得设置它。

## Browser backend 与 storage-state

- `PAPER_FETCH_BROWSER_HEADLESS`、`PAPER_FETCH_BROWSER_TIMEOUT_MS`：Camoufox managed runtime 的 headless 开关与请求超时；默认分别为 `true`、`120000`。
- `PAPER_FETCH_BROWSER_BINARY_PATH`：已准备好的 Camoufox runtime executable 覆盖项。
- `PAPER_FETCH_BROWSER_PROFILE_DIR`、`PAPER_FETCH_BROWSER_USER_DATA_DIR`：provider-scoped profile/storage-state 目录覆盖项。默认使用 `publisher-browser-profiles/<provider>-camoufox/`。
- `PAPER_FETCH_BROWSER_USER_AGENT`：publisher direct 路线的可选浏览器 UA；它与 `PAPER_FETCH_SKILL_USER_AGENT` 分离。Camoufox 忽略该值，以保持生成的 Firefox 指纹一致。
- `PAPER_FETCH_WILEY_STORAGE_STATE_JSON`、`PAPER_FETCH_WILEY_PROFILE_DIR`：Wiley 的兼容 storage/profile 覆盖。常规流程优先使用 provider-scoped storage-state；人工验证只在 preflight/fetch 明确要求时运行 `paper-fetch auth <provider>`。

静态 `paper-fetch doctor --provider <name> --detail full --json` / MCP `provider_status` 不启动 Camoufox，也不访问出版社页面。需要 live 证明时再运行 CLI `paper-fetch browser-preflight --provider <name>` 或 MCP `browser_preflight(provider=...)`；两者在实际启动浏览器前自动准备 managed runtime。它们可能更新过滤后的 storage-state，但不会运行 PDF fallback 或自动认证。MCP preflight is open-world：它会访问远端页面、非只读且可能写 storage-state。

## 运行时准备与授权

普通 MCP/CLI/library 工具在每次实际启动浏览器前自动补全或更新 managed Camoufox；无浏览器抓取和静态诊断不检查更新，同一浏览器生命周期不重复检查。未固定版本时查询所选渠道最新兼容版本，固定时只补全对应版本。更新失败但本地版本有效时提示并继续使用，无可用版本则报告准备失败。下载进度写 stderr；显式 binary 路径仍由用户维护。缺失 Python 依赖、损坏配置或不安全路径不会通过自动安装依赖或删除配置修复；代理根据具体诊断报告限制，额外环境修复仍需当前任务已有适用授权。离线使用前可在联网阶段显式运行 `python -m camoufox fetch` 预置 runtime。

运行时准备不授予出版社访问权限。只有实际 fetch 或按需 preflight 明确返回 `challenge` / `auth_required` 时才由用户执行人工 auth；不自动登录或绕过访问控制。

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

安装入口是 `paper-fetch-install-formula-tools`（已安装环境）或仓库脚本 `./install-formula-tools.sh`。公式工具缺失只影响相应转换/fallback，不改变 provider 身份；共享 LaTeX 宏规范化独立运行。

## 诊断顺序

1. 用 `paper-fetch doctor --json` 或 `provider_status(detail="full")` 做无网络静态检查；输出只包含变量名、是否存在和来源层；token, cookie, endpoint, path, and other values are never echoed。
2. 只有 runtime catalog 表明目标依赖 browser runtime 且需要真实链路证明时，运行 `browser-preflight` / `browser_preflight`；缺失 runtime 时按[运行时准备与授权](#运行时准备与授权)处理。
3. 只有结构化结果为 `challenge` / `auth_required` 时进入人工 auth；`runtime_error` 同样按上述授权规则处理，不因诊断建议自动扩大任务为环境修复。
4. 配置或合法访问状态没有变化时，不重复抓取；重试边界统一遵循 [`failure-handling.md`](failure-handling.md)。

## 离线安装后的可选配置

Linux/macOS 离线安装器及 Windows EXE 在核心 smoke 成功后提供可选向导，源码在线安装入口不变。凭据隐藏输入，留空保留旧值；下载/安装默认关闭。Unix `--non-interactive`、无终端及 Windows `/SILENT`、`/VERYSILENT` 全部跳过；`--reuse-env-file` 保持外部配置只读。Linux 仅为 Debian/Ubuntu 提供经确认的 APT 辅助安装，macOS 仅复用已有 Homebrew，Windows 使用摘要固定的官方 Ghostscript EXE（需要 UAC、系统注册表）和完整 libvips ZIP。图片工具通过实际 EPS/TIFF 转换后保存绝对路径，桌面 MCP 无需依赖 shell PATH。

Camoufox 可选择准备并验证本地空白页，不访问 provider、不保存登录状态；下载、启动与站点访问状态分开报告。跳过本次安装不会关闭后续运行时自动准备。可选失败/取消不影响核心安装，升级保留凭据与可选工具；卸载默认保留可选工具和共享浏览器缓存。配置后重启已运行的宿主/MCP；完整说明见项目 `docs/deployment.md`。
