# 环境说明

优先使用已有 CLI 和用户指定配置。入口发现见 [CLI 工作流](cli-workflow.md#入口发现)。配置位置通常为 `~/.config/paper-fetch/.env`；`PAPER_FETCH_ENV_FILE` 可指定现有环境文件。

`main` 源码使用 Scrapling Chromium。认证、预检和抓取共用用户数据目录下的 `publisher-browser-profiles/<provider>/chromium/`。从 Firefox 迁移后，运行 `paper-fetch auth <provider>`，在打开的 Chromium 窗口中重新登录。

普通抓取按需准备浏览器 runtime，同批共享准备结果。浏览器任务按展开用户目录、解析符号链接及平台大小写规范化后的实际 profile 路径协调；纯 HTTP/API 请求不申请该资源。队列可取消且无超时，页面预算在取得使用权后建立，重试和 fallback 共用剩余预算。

遇到 challenge 或 auth_required，按 provider 使用 `paper-fetch auth PROVIDER` 打开人工认证；不代填密码、验证码或绕过访问控制。认证、browser-preflight、抓取和补图共享同一资源机制。外部浏览器占用与 provider 归属冲突分别报错。

用 `paper-fetch doctor --catalog --json` 查看当前 CLI 的 `browser_runtime.backend` 和 `browser_runtime.platform_engine`，`main` 对应 `scrapling` 和 `chromium`。`paper-fetch doctor` 是静态诊断，`paper-fetch browser-preflight` 会实际启动浏览器。只有环境问题影响当前任务时使用。更新和安装按用户请求执行，不为普通阅读自动改配置。

AMS 联网获取前必须通过 `paper-fetch auth ams` 完成人工认证及同一原生 profile 的重开验证；仅有目录、Cookie 或普通抓取状态不够。交互 fetch/fetch-assets 自动先认证再继续；批量由调度线程按实际 profile 集中认证，并与其他 CLI 协调，等待可取消。不预持后续抓取租约。非交互或 `--control-stdin` 返回 auth_required；认证提示写 stderr，不占用回执／正文 stdout。兼容缓存和现有本地文件无需认证，resolve/check 不弹认证窗口。
