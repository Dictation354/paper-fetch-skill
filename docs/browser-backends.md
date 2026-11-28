# 浏览器后端

以下配置适用于 `main` 的 Scrapling Chromium 源码。要查看旧实现，可切换到 `feat/byparr`（Byparr 与 Camoufox）或 `feat/FlareSolverr`（FlareSolverr）。稳定版安装包使用对应 Release 标签的实现，例如使用 Byparr 的 [`v8.2.2`](https://github.com/Dictation354/paper-fetch-skill/releases/tag/v8.2.2)。

## Scrapling Chromium

Linux、Windows 和 macOS 的浏览器路线统一使用 Scrapling Chromium。正文 HTML、浏览器 PDF、图片、附件、认证和预检都通过 `paper_fetch.providers.browser_runtime`。受管子进程启动 Scrapling 的持久 session，Playwright 在调用线程经本机 CDP 接入同一 Chromium 上下文。Cloudflare 页面由 Scrapling 的处理逻辑在请求预算内处理。

`browser` 和 `full` 固定使用 `scrapling[fetchers]==0.5.1`、`patchright==1.64.4` 和 `playwright==1.64.1`。

## 选择与配置

<a id="生命周期"></a>

认证、预检与抓取共用原生持久 profile。默认路径为 `publisher-browser-profiles/<provider>/chromium/`。指定 `PAPER_FETCH_BROWSER_PROFILE_DIR`、`PAPER_FETCH_BROWSER_USER_DATA_DIR` 或预检的 `--profile-dir` 时，实际 profile 位于指定目录下的 `chromium/`。目录由 provider 独占，锁与上下文随所属线程释放。私有缓存 scope 绑定实际目录与可信状态摘要。

升级后，历史 Firefox profile 留在原处。需要原有登录权限时，在 Chromium 中重新运行 `paper-fetch auth <provider>`。抓取默认无头，认证使用有头窗口。

## 准备与预检

安装器与首次使用共用准备入口。受管准备执行 `patchright install --no-shell chromium`，复用 `PLAYWRIGHT_BROWSERS_PATH` 或平台默认缓存中符合当前 Patchright 版本的安装。可用 `PAPER_FETCH_BROWSER_BINARY_PATH` 指定 Chromium executable。

`paper-fetch doctor --catalog --json` 的 `browser_runtime.backend` 和 `browser_runtime.platform_engine` 分别显示当前 CLI 的后端和引擎。`paper-fetch doctor` 读取 Python 包版本和本地安装状态。`paper-fetch browser-preflight` 使用同一 profile 访问出版社样例页面。`--artifact-mode all` 可保留 `diagnostics/<provider>/<DOI>/scrapling.json`，记录后端、Chromium 版本、窗口模式、实际响应和失败阶段。
