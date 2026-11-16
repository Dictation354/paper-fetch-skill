# 环境说明

优先使用已有 CLI 和用户指定配置。入口发现见 [CLI 工作流](cli-workflow.md#入口发现)。配置位置通常为 `~/.config/paper-fetch/.env`；`PAPER_FETCH_ENV_FILE` 可指定现有环境文件。

普通抓取按需准备浏览器 runtime，同批共享准备结果。浏览器任务按展开用户目录、解析符号链接及平台大小写规范化后的实际 profile 路径协调；纯 HTTP/API 请求不申请该资源。队列可取消且无超时，页面预算在取得使用权后建立，重试和 fallback 共用剩余预算。

遇到 challenge 或 auth_required，按 provider 使用 `paper-fetch auth PROVIDER` 打开人工认证；不代填密码、验证码或绕过访问控制。认证、browser-preflight、抓取和补图共享同一资源机制。外部浏览器占用与 provider 归属冲突分别报错。

`paper-fetch doctor` 是静态诊断；`paper-fetch browser-preflight` 是实际浏览器检查。只有环境问题影响当前任务时使用。更新和安装按用户请求执行，不为普通阅读自动改配置。
