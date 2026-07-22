# 浏览器后端

paper-fetch 通过统一的 `paper_fetch.providers.browser_runtime` facade 提供浏览器能力。Camoufox 是唯一默认后端；CloakBrowser 在 3.x 中作为已弃用的手动兼容后端保留，并可能在 4.0.0 移除。

后端选择是严格的：Camoufox 失败不会自动改用 CloakBrowser，CloakBrowser 失败也不会自动改用 Camoufox。需要临时回滚时必须显式设置：

```dotenv
PAPER_FETCH_BROWSER_BACKEND="cloakbrowser"
```

显式选择 CloakBrowser 会产生一次 `FutureWarning`，并在 doctor、preflight 和 provider status 中显示弃用说明。仅设置 `CLOAKBROWSER_*` 旧变量不会选择 CloakBrowser；这些变量只在同时显式选择 `cloakbrowser` 时生效。

## 选择矩阵

| 配置 | 后端 | 行为 |
| --- | --- | --- |
| 未设置 `PAPER_FETCH_BROWSER_BACKEND` | Camoufox | 默认行为，不探测或启动 CloakBrowser/CDP |
| `camoufox`（大小写不敏感） | Camoufox | 严格使用本地 Firefox/Juggler runtime |
| `cloakbrowser`（大小写不敏感） | CloakBrowser | 兼容模式，显示弃用提示 |
| 非法值 | 无 | 立即报告配置错误及合法值 |
| 仅设置 `CLOAKBROWSER_*` | Camoufox | 旧变量不生效，诊断提示显式迁移方法 |

## 安装与 runtime

项目使用已验证的依赖范围：

```text
camoufox>=0.5.4,<0.6
playwright>=1.47,<1.61
```

从源码安装或升级：

```bash
python3 -m pip install -e '.[dev]'
```

静态检查不会启动浏览器，也不会下载 runtime：

```bash
paper-fetch doctor --group browser
```

第一次确实需要 Camoufox 的抓取允许官方 Python wrapper 按需下载 runtime。也可以提前准备：

```bash
python3 -m camoufox fetch
python3 -m camoufox path
```

需要配置精确可执行文件时，使用官方 package manager 获取路径：

```bash
python3 -c 'from camoufox.pkgman import launch_path; print(launch_path())'
```

离线安装包包含 Camoufox、CloakBrowser 和 Playwright 的 Python 包，但不重新分发浏览器二进制。完全离线环境必须预置 `camoufox fetch` 产生的完整 active runtime（包括相邻配置、addons 和字体），并在需要时设置 `PAPER_FETCH_BROWSER_BINARY_PATH`。只复制可执行文件不足以组成可用 runtime。

## 配置

以下通用变量作用于所选后端：

| 变量 | 含义 |
| --- | --- |
| `PAPER_FETCH_BROWSER_BACKEND` | `camoufox`（默认）或 `cloakbrowser`（已弃用） |
| `PAPER_FETCH_BROWSER_HEADLESS` | 自动抓取是否 headless，默认 `true` |
| `PAPER_FETCH_BROWSER_TIMEOUT_MS` | 页面操作上限，默认 `120000` |
| `PAPER_FETCH_BROWSER_BINARY_PATH` | runtime 可执行文件覆盖值 |
| `PAPER_FETCH_BROWSER_PROFILE_DIR` | profile/storage-state 目录覆盖值 |
| `PAPER_FETCH_BROWSER_USER_DATA_DIR` | user-data 目录覆盖值 |

默认状态目录按 provider 和后端隔离：

```text
<paper-fetch-data>/publisher-browser-profiles/<provider>-camoufox/storage-state.json
<paper-fetch-data>/publisher-browser-profiles/<provider>/storage-state.json
```

第二行只属于显式选择的 CloakBrowser。系统不会复制、合并或自动迁移两种后端的登录态；从旧默认升级后可能需要按 provider 重新认证。

`PAPER_FETCH_BROWSER_USER_AGENT` 不适用于 Camoufox。不要向 Camoufox 注入 Chrome UA、固定 viewport、字体或 WebGL 参数，否则会破坏 Firefox 指纹的一致性。`auth` 和 `browser-preflight` 的 `--browser-user-agent` 在 Camoufox 模式下会直接报错。

`CLOAKBROWSER_CDP_ENDPOINT`、`CLOAKBROWSER_PROFILE_DIR` 等旧变量以及外部 CDP 只属于显式 CloakBrowser。通用 `PAPER_FETCH_BROWSER_*` 变量优先于对应旧变量。

## 抓取、预检与认证

正常抓取无需设置后端变量：

```bash
paper-fetch fetch --query '10.1146/annurev-control-030123-013355' \
  --asset-profile all \
  --artifact-mode markdown-assets \
  --output-dir ./papers
```

对 browser-backed provider 做真实页面预检：

```bash
paper-fetch browser-preflight --timeout-ms 120000
paper-fetch browser-preflight --provider annualreviews
```

需要人工登录、机构认证或完成合法 challenge 时：

```bash
paper-fetch auth annualreviews
```

headed auth 使用 provider 独立的持久 Camoufox profile，并导出过滤后的 storage-state。普通抓取使用全新的隔离 context，不复用完整 profile、IndexedDB 或 service worker。

浏览器后端不会绕过付费墙、访问授权或 CAPTCHA。可用性仍取决于用户已有的合法访问上下文和远端站点行为。

## IEEE direct-first 恢复

IEEE 的 landing、REST HTML、PDF、正文 figure/table/formula、multimedia discovery 和 supplementary file 都遵循 direct-first：direct HTTP 成功时不会创建浏览器 context；只有可恢复失败才使用当前选中的后端。

允许浏览器恢复的情况：

- `401`、`403`；
- `200` 但返回 HTML challenge/access block，而期望图片、PDF 或附件；
- 既有 HTTP retry 耗尽后的网络错误或超时；
- 已有合法浏览器 seed，但 seeded HTTP 仍失败。

不会使用浏览器恢复的情况：

- `404`、`410`；
- `429`（继续尊重 `Retry-After` 和现有限速策略）；
- 非 HTTP(S)、无效 URL、明确不支持的本地格式或转换错误；
- 明确无权限且没有用户提供的合法登录态。

浏览器 HTML 成功取得的 cookie、实际 UA 和最终 URL 会作为去敏 seed 复用于 PDF 和资产请求。Camoufox 的同步对象保持线程绑定，浏览器图片和补充文件操作串行；direct HTTP 下载仍可并发。

## 运行时行为与诊断

一个 `RuntimeContext` 会在 owning thread 内复用 Camoufox 进程，每次操作创建新的隔离 `BrowserContext`。HTML、PDF 和资产路径都从显式 `BrowserRuntimeConfig.backend` 分派，诊断中的 backend/fetcher 不使用静态 CloakBrowser 标签。

诊断只记录后端、阶段、状态码、content type、耗时和失败原因，不记录 cookie、token、完整 storage-state 或受保护正文。provider status 和 doctor 是静态探测；它们不会访问出版社页面或下载 Camoufox runtime。

## 验证

本地契约：

```bash
python3 -m ruff check .
PYTHONPATH=src python3 -m pytest tests/unit -q
python3 -m mypy
```

真实出版社和浏览器 runtime 依赖共享外部状态，只能显式启用并串行运行：

```bash
PAPER_FETCH_RUN_LIVE=1 \
PAPER_FETCH_BROWSER_BACKEND=camoufox \
PYTHONPATH=src python3 -m pytest tests/live/test_live_publishers.py -q -n 0
```

常规 CI 不下载 Camoufox runtime，也不访问真实出版社。升级 Camoufox、Playwright 或 runtime 后应重跑 publisher live matrix；不要用指纹检测网站评分替代真实抓取结果。

## 临时回滚

需要旧 Chromium/CDP 行为时显式选择已弃用后端：

```bash
export PAPER_FETCH_BROWSER_BACKEND=cloakbrowser
paper-fetch fetch --query '10.1146/annurev-control-030123-013355' \
  --output-dir ./papers
```

删除该变量会恢复默认 Camoufox，而不是 CloakBrowser。运行时不提供 Camoufox 到 CloakBrowser 的自动 fallback。

维护者架构和生命周期边界见 [`browser-runtime.md`](browser-runtime.md)，provider 路由见 [`providers.md`](providers.md)，部署与离线准备见 [`deployment.md`](deployment.md)。
