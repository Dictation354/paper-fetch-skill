# Browser backend

paper-fetch 4.0 仅支持 Camoufox。所有 browser-backed provider 都通过
`paper_fetch.providers.browser_runtime` facade 获取 Firefox/Juggler context；
provider 不得直接创建 Playwright 或 Camoufox 生命周期。

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
准备 Camoufox active runtime，包括相邻配置、addons 和字体；只复制可执行文件
不足以组成可用 runtime。联网时须显式运行 `python -m camoufox fetch`；普通 fetch、
auth 和 preflight 只读探测并使用已准备的 runtime。

## 选择与配置

browser backend 固定为 Camoufox，不再提供单值选择配置。

通用变量如下：

| 变量 | 含义 |
|---|---|
| `PAPER_FETCH_BROWSER_HEADLESS` | managed runtime 是否 headless |
| `PAPER_FETCH_BROWSER_BINARY_PATH` | 仅用于自行维护、且支持 Camoufox custom-executable metadata 语义的 executable 覆盖 |
| `PAPER_FETCH_BROWSER_PROFILE_DIR` | provider storage-state/profile 目录覆盖 |
| `PAPER_FETCH_BROWSER_USER_DATA_DIR` | profile 目录的后备覆盖 |
| `PAPER_FETCH_BROWSER_TIMEOUT_MS` | browser navigation timeout |
| `PAPER_FETCH_BROWSER_USER_AGENT` | publisher direct HTTP 的可选 UA；Camoufox 本身忽略它以保持生成指纹一致 |

默认状态位于 platformdirs 用户数据目录下的
`publisher-browser-profiles/<provider>-camoufox/storage-state.json`。不同 provider
不共享登录态。

macOS 官方 managed app bundle 把 executable 放在 `Contents/MacOS`，把运行属性表
放在 `Contents/Resources`。不要把官方 cache 内的
`Contents/MacOS/camoufox` 配置为 `PAPER_FETCH_BROWSER_BINARY_PATH`；这样会把
managed bundle 错当成 custom executable。官方 runtime 应保持该变量未设置，
由 `python -m camoufox fetch` 和 Camoufox active-version 配置共同管理。只有自定义
runtime 明确实现 Camoufox 的 custom-path metadata 布局时才使用该覆盖。

## 生命周期

一个 `RuntimeContext` 在 owning thread 内复用一个 Camoufox process，每次操作
创建独立 `BrowserContext`。HTML、PDF fallback 和资产下载共享相同 runtime
配置及 provider storage-state，但 Playwright sync 对象不会跨线程共享。

`doctor` 和 `provider_status` 只做静态依赖/配置检查，不启动浏览器、不下载
runtime、不访问出版社页面。CLI 与 MCP `browser_preflight` 都只使用已准备的
runtime，并打开页面、按请求保存过滤后的 storage-state。两者都不会
自动认证、绕过 challenge/paywall，也不会调用 PDF fallback。

Preflight 只报告本次 live 检查；正式 fetch 独立导航并重新执行身份、阻断与正文验收。
图片、附件或 PDF 的 direct 401/403 只允许一次 browser-byte 恢复；
`response.body()`、page `arrayBuffer()`、canvas 或 download/file bytes 都会先进入统一
MIME、大小、像素、预算、staging 与原子发布检查。

## 4.0 迁移

4.0 已删除 CloakBrowser 包、backend、环境变量、离线构建要求与自动迁移路径。
升级前使用旧 backend 的部署应：

1. 安装 `paper-fetch-skill[browser]` 或 `[full]`。
2. 删除旧 backend 选择与旧前缀环境变量。
3. 按 provider 重新执行 headed `paper-fetch auth <provider>`。
4. 用 `paper-fetch doctor` 和显式 `browser-preflight` 分别验证静态配置与 live
   页面能力。
