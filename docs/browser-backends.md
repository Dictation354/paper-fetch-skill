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
不足以组成可用 runtime。

## 选择与配置

`PAPER_FETCH_BROWSER_BACKEND` 可以省略或设置为 `camoufox`。其它值会以结构化
`not_configured`/runtime failure 拒绝，不会自动回退到其它浏览器。

通用变量如下：

| 变量 | 含义 |
|---|---|
| `PAPER_FETCH_BROWSER_BACKEND` | 唯一合法值为 `camoufox` |
| `PAPER_FETCH_BROWSER_HEADLESS` | managed runtime 是否 headless |
| `PAPER_FETCH_BROWSER_BINARY_PATH` | 已准备好的 Camoufox runtime executable 覆盖 |
| `PAPER_FETCH_BROWSER_PROFILE_DIR` | provider storage-state/profile 目录覆盖 |
| `PAPER_FETCH_BROWSER_USER_DATA_DIR` | profile 目录的后备覆盖 |
| `PAPER_FETCH_BROWSER_TIMEOUT_MS` | browser navigation timeout |
| `PAPER_FETCH_BROWSER_USER_AGENT` | publisher direct HTTP 的可选 UA；Camoufox 本身忽略它以保持生成指纹一致 |

默认状态位于 platformdirs 用户数据目录下的
`publisher-browser-profiles/<provider>-camoufox/storage-state.json`。不同 provider
不共享登录态。

低层 `PAPER_FETCH_CDP_EXTERNAL_NEW_CONTEXT` 只影响显式传入 CDP endpoint 的
开发/测试调用，不选择生产 backend，也不提供旧后端兼容。

## 生命周期

一个 `RuntimeContext` 在 owning thread 内复用一个 Camoufox process，每次操作
创建独立 `BrowserContext`。HTML、PDF fallback 和资产下载共享相同 runtime
配置及 provider storage-state，但 Playwright sync 对象不会跨线程共享。

`doctor` 和 `provider_status` 只做静态依赖/配置检查，不启动浏览器、不下载
runtime、不访问出版社页面。`browser-preflight` 是显式 live 操作，可以打开
页面并保存过滤后的 storage-state；它不会自动认证、绕过 challenge/paywall，
也不会调用 PDF fallback。

## 4.0 迁移

4.0 已删除 CloakBrowser 包、backend、环境变量、离线构建要求与自动迁移路径。
升级前使用旧 backend 的部署应：

1. 安装 `paper-fetch-skill[browser]` 或 `[full]`。
2. 删除旧 backend 选择与旧前缀环境变量。
3. 按 provider 重新执行 headed `paper-fetch auth <provider>`。
4. 用 `paper-fetch doctor` 和显式 `browser-preflight` 分别验证静态配置与 live
   页面能力。
