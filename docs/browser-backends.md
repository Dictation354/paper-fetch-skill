# 浏览器后端

所有 provider 固定使用受管 Byparr。底层使用所选平台引擎，由现有平台策略决定；当前事实由 provider catalog 提供。

## 原生 profile

认证、预检和抓取共用原生持久 profile，默认路径为 `publisher-browser-profiles/<provider>/`。支持 `PAPER_FETCH_BROWSER_PROFILE_DIR`、`PAPER_FETCH_BROWSER_USER_DATA_DIR` 及已有 provider profile 目录覆盖。目录由 provider 独占，锁与上下文随所属线程关闭。凭证 scope 绑定实际使用的 profile 路径与可信摘要。

JSON 状态文件不参与导入、导出、认证或 scope；旧文件保持原样。浏览器后端选择环境变量与别名不再提供接口。平台引擎的原生持久目录会被首次访问创建；论文 no_download 不控制浏览器组件与 profile。

## 准备与预检

使用安装环境 Python 执行 `-m paper_fetch.offline_setup --install-root <dir> --prepare-browsers`，准备所选平台引擎及 Byparr。该选项为布尔开关。认证使用 `paper-fetch auth`，预检使用 `paper-fetch browser-preflight` 或 MCP `browser_preflight`，均沿用原生 profile。预检可显式提供 profile_dir。
