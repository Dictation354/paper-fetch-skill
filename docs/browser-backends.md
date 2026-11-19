# 浏览器后端

## 统一受管 Byparr

所有 provider 固定经单一 `paper_fetch.providers.browser_runtime.backends.byparr.ByparrBackend` 使用受管 Byparr，不再维护平行的浏览器后端分支或选择注册表。底层按平台策略选用引擎（Windows/Linux x64 使用 InvisiblePlaywright，macOS 与 ARM 使用 Camoufox）；当前事实由 provider catalog 提供。

## 选择与配置

<a id="生命周期"></a>

认证、预检和抓取共用原生持久 profile，默认路径为 `publisher-browser-profiles/<provider>/`。仅支持通用 `PAPER_FETCH_BROWSER_PROFILE_DIR`、`PAPER_FETCH_BROWSER_USER_DATA_DIR` 或运行配置显式指定目录覆盖，不支持单出版社专用环境变量或浏览器后端选择别名。目录由 provider 独占，锁与上下文随所属线程关闭。凭证 scope 绑定实际使用的 profile 路径与可信摘要。

JSON 状态文件不参与导入、导出、认证或 scope；旧文件保持原样。平台引擎的原生持久目录在首次访问时创建；论文资产范围不控制浏览器组件与 profile。

## 准备与预检

使用安装环境 Python 执行 `-m paper_fetch.offline_setup --install-root <dir> --prepare-browsers`，准备所选平台引擎及 Byparr。该选项为布尔开关。认证使用 `paper-fetch auth`，预检使用 `paper-fetch browser-preflight`，均沿用原生 profile。
