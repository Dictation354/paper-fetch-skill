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
- `WILEY_TDM_CLIENT_TOKEN`：Wiley 官方 TDM PDF lane 的可选 token 名称；本地 browser 路线是否可用仍由动态 catalog 与诊断决定。
- `XDG_DATA_HOME`：改变 platformdirs 用户数据基目录，因而影响默认下载和本地工具目录。
- `PAPER_FETCH_RUN_LIVE`：仅用于显式 opt-in 的 live publisher 测试；正常诊断和单元测试不得设置它。

## Browser backend 与 storage-state

- `PAPER_FETCH_BROWSER_BACKEND`：可省略或设置为唯一合法值 `camoufox`；其它值被拒绝，不会自动切换 backend。
- `PAPER_FETCH_BROWSER_AUTO_PREPARE`：managed Camoufox 的按需安装、修复和更新策略，严格接受 `true/false`、`1/0`、`yes/no`、`on/off`。未设置时 CLI browser fetch/auth/preflight 默认开启，MCP/库默认关闭；CLI flag 或 MCP 单次请求字段优先于环境。
- `PAPER_FETCH_BROWSER_HEADLESS`、`PAPER_FETCH_BROWSER_TIMEOUT_MS`：Camoufox managed runtime 的 headless 开关与请求超时；默认分别为 `true`、`120000`。
- `PAPER_FETCH_BROWSER_BINARY_PATH`：已准备好的 Camoufox runtime executable 覆盖项。
- `PAPER_FETCH_BROWSER_PROFILE_DIR`、`PAPER_FETCH_BROWSER_USER_DATA_DIR`：provider-scoped profile/storage-state 目录覆盖项。默认使用 `publisher-browser-profiles/<provider>-camoufox/`。
- `PAPER_FETCH_BROWSER_USER_AGENT`：publisher direct 路线的可选浏览器 UA；它与 `PAPER_FETCH_SKILL_USER_AGENT` 分离。Camoufox 忽略该值，以保持生成的 Firefox 指纹一致。
- `PAPER_FETCH_CDP_EXTERNAL_NEW_CONTEXT=1`：只影响显式传入 CDP endpoint 的低层开发/测试调用，不选择生产 backend。
- `PAPER_FETCH_WILEY_STORAGE_STATE_JSON`、`PAPER_FETCH_WILEY_PROFILE_DIR`：Wiley 的兼容 storage/profile 覆盖。常规流程优先使用 provider-scoped storage-state；人工验证只在 preflight/fetch 明确要求时运行 `paper-fetch auth <provider>`。

静态 `paper-fetch doctor --provider <name> --detail full --json` / MCP `provider_status` 不启动或准备 Camoufox，也不访问出版社页面。需要 live 证明时再运行 CLI `paper-fetch browser-preflight --provider <name>` 或 MCP `browser_preflight(provider=...)`；CLI 默认允许缺失 runtime 的按需准备，MCP 默认禁止，需联网准备时传 `browser_auto_prepare=true`，并通过 logging notification 报告进度。它们可能更新过滤后的 storage-state，但不会运行 PDF fallback 或自动认证。MCP preflight is open-world：它会访问远端页面、非只读且可能写 storage-state。

PNAS、AMS、MDPI、Royal Society、Annual Reviews、ACS、IOP、T&F 的成功 preflight HTML 只在当前进程内短期、一次性复用（默认 16 项、60 秒），并同时约束 provider、规范 DOI、目标 URL 与 browser runtime 指纹。MCP server 内紧随其后的 fetch 可命中；CLI 跨进程仅复用 storage-state。Wiley、IEEE、Science 不接入该 HTML cache；AIP 不发布跨 `RuntimeContext` 的 preflight HTML/cookie/storage-state，challenge、空壳、PDF fallback 和失败结果也不进入该缓存。

## 图片与资产工具

- `PAPER_FETCH_IMAGE_TOOLS_DIR`：Ghostscript/libvips 工具目录覆盖；默认还会检查 repo-local 和 platformdirs 用户工具目录。
- `PAPER_FETCH_GHOSTSCRIPT_BIN`：Ghostscript executable 覆盖，用于 EPS → PNG。
- `PAPER_FETCH_VIPS_BIN`：libvips `vips` executable 覆盖，用于 TIFF → PNG。
- `PAPER_FETCH_EPS_DPI`：Ghostscript EPS 输出 DPI，默认 `600`。
- `PAPER_FETCH_IMAGE_TOOL_TIMEOUT_SECONDS`：后端探测/转换子进程超时，默认 `120` 秒。
- `PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY`：HTTP/HTML 资产 worker 上限；实际 provider/runtime 限制仍以动态 catalog 和运行时为准。

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
2. 只有动态 catalog 表明目标依赖 browser runtime 且需要真实链路证明时，运行 `browser-preflight` / `browser_preflight`；MCP 若需准备缺失 runtime，显式传 `browser_auto_prepare=true`。
3. 只有结构化结果为 `challenge` / `auth_required` 时进入人工 auth；`runtime_error` 先修 Camoufox runtime/工具链。
4. 配置或合法访问状态没有变化时，不重复抓取；重试边界统一遵循 [`failure-handling.md`](failure-handling.md)。
