# Browser runtime ownership

生产 browser runtime 只有 Camoufox；browser/full extra 接受
`camoufox>=0.5.5,<0.6`。开发和常规 CI 使用 `uv.lock` 中的具体版本，离线构建使用
依赖 wheelhouse 实际解析出的兼容版本，并由 `paper_fetch.providers.browser_runtime`
统一管理。

## 依赖方向

```text
provider/browser workflow
        ↓
browser_runtime facade + BrowserRuntimeConfig
        ↓
RuntimeContext.new_browser_context_for_runtime_config
        ↓
CamoufoxBrowserManager
```

provider 只读取显式 `BrowserRuntimeConfig`，不探测 backend、不持有全局 browser，
也不直接导入 Camoufox 私有实现。缺少 `browser` extra 时，静态状态返回结构化
缺失依赖；core import 和非 browser provider 仍可正常工作。

## 生命周期与线程边界

- 一个 `RuntimeContext` 在当前 owning thread 内复用 Camoufox process。
- 正文 HTML/PDF 操作继续使用独立 context/page；同一 `RuntimeContext` 内尚未解析的
  figure page discovery 使用一个专用 context/page 串行复用，并随 runtime 统一关闭。
- Playwright sync 对象不跨线程共享。
- batch 结束、取消升级或 runtime context 关闭时统一释放 manager。
- provider storage-state 目录隔离，默认以 `<provider>-camoufox` 命名。
- 显式 executable 启动会读取相邻 Camoufox `version.json`，让隔离子进程复用已准备的官方 runtime，而不是从隔离 cache 误判为未安装。
- Camoufox 启动进度写入 stderr；MCP stdio 的 stdout 始终只承载 JSON-RPC。
- managed runtime 准备进度同样写入 CLI stderr；MCP 启用准备时通过 logging
  notification 转发，不污染 JSON-RPC stdout。

## HTML 策略、短期复用与资源阻断

browser profile 的正文策略是内部配置，不改变 CLI/MCP schema。默认 profile 仍保留
既有 fast attempt、readiness 和资源加载行为；只有明确 opt-in 的 provider 才覆盖：

- PNAS 只执行一次完整 HTML attempt，候选依次为 canonical `/doi/{doi}`、
  `/doi/full/{doi}` 和 DOI resolver。它不再等待失效的 bodymatter selector，而是在
  固定 8 秒总预算内检查正文长度、段落数和连续两次稳定指纹；预算耗尽后仍对最后
  一份 HTML 做 block detection 与正文抽取。
- PNAS、AMS、MDPI、Royal Society、Annual Reviews、ACS、IOP 与 Taylor & Francis
  的正文导航只阻断 `image`、`font`、`media`；document、stylesheet、JavaScript、
  XHR/fetch 保持放行。Wiley、IEEE、AIP 与 Science 的既有策略不变。
- 上述八个 opt-in provider 的 `BrowserPreflightReuseCache` 使用已有
  `cachetools.TTLCache`，默认最多 16 项、TTL 60 秒、线程安全且一次性消费。key
  包含 provider、规范 DOI、候选 URL 和非敏感的
  browser runtime 指纹；只有正文已抽取且 storage-state 已成功提交的 HTML 才能写入。
  challenge、空壳、PDF fallback、失败 HTML、未提交状态和落盘产物都不缓存。
- 这些 provider 在 MCP server 内连续执行的 preflight 与正式 fetch、以及同进程
  catalog live 测试可
  共享这份 HTML；命中后仍使用正式 metadata 重新执行 Markdown/资产抽取。独立 CLI
  进程之间仅继续复用 storage-state，不承诺 HTML 复用。
- Wiley、IEEE 与 Science 不接入这份 HTML cache；AIP 的 cookie/HTML 与 Camoufox
  进程指纹绑定，禁止跨 `RuntimeContext` preflight
  HTML 或 cookie 复用，也不把 preflight storage-state 发布给后续独立 context。
- PNAS 与 AMS 另有 60 秒的精确 DOI 路由提示，只把同 DOI、合法 provider host 上
  已验收的最终 URL 置顶；challenge、abstract redirect 和失败候选不会写入。

正文 diagnostics 会记录实际阻断类型/数量、导航次数、readiness 预算与结果，以及
`preflight_reuse`、`candidate_reorder` 和 DOI hint 写入状态；source trail 以
`browser:preflight_reuse_hit|miss|disabled` 与
`browser:candidate_reorder_hit|miss` 暴露同一事实，不新增公开请求或响应字段。

## 网络与登录态边界

- Camoufox/Playwright 的主文导航、重定向、子资源和 service worker 使用浏览器原生
  网络行为；项目不安装 context-wide URL/DNS 安全 interceptor，也不把带 cookie、
  storage state、profile 或 user-data 的 context 额外限制为单一 origin。外部 CDP
  默认仍可借用既有 context。
- Provider 的 image/font/media 屏蔽是 page scope 的性能优化，只按 catalog/runtime
  配置处理资源类型，不承担 URL allowlist 或 SSRF 安全保证；其它跨源页面资源继续
  交给浏览器原生加载。
- Direct HTTP/API、browser 发现后的二进制流式下载与 cookie-seeded direct fallback
  继续使用 `SafeRemoteUrlPolicy` 和 provider catalog request policy：每个 redirect hop
  重新验证公网地址、批准端口、HTTPS downgrade、route host 和敏感 header。
- Browser cookie 转 direct opener 时使用标准 `CookieJar`，保留 host-only/domain、
  RFC path boundary、secure 与 expiry，避免把 publisher cookie 扩到子域或相邻路径。
- Browser context diagnostics 用 `storage_state_load={path,exists,used}` 明确区分“已配置”
  与“实际注入”。只有 context 创建成功且 `storage_state` option 真正传入时，
  `RuntimeContext` 才记录 capability use；MCP fetch 完成后以 provider、backend、最终
  canonical path 和最终文件 SHA-256 重新构建 sidecar scope。默认 provider 目录、
  `PAPER_FETCH_BROWSER_PROFILE_DIR`、`PAPER_FETCH_BROWSER_USER_DATA_DIR` 与 provider
  显式 storage-state 都遵循同一规则。

## 二进制资产与资源预算

- Camoufox/Playwright 只解析页面、发现最终 `http(s)` 资产 URL，并传递浏览器 cookie；
  图片、附件和 PDF 不调用 browser `response.body()`、
  `arrayBuffer()` 或 base64 整包回传。URL 必须能交给 verified-IP pinned direct
  transport 流式获取，否则以 `browser_stream_unavailable` fail closed。
- 同一论文的正文图和 supplementary 共用 `RuntimeContext` 的一个 `AssetBudget`：默认
  最多 128 个文件、单文件 32 MiB、累计 256 MiB、每图 64,000,000 像素，并发最多
  4 且可被 route cap 进一步收紧。Content-Length、未知长度 chunk、gzip 压缩/解压、
  EPS/TIFF/PNG 转换输出和 arXiv source archive 解压都计入该边界。
- 每个候选写入目标同目录的唯一排他 staging；成功后 flush/fsync 并原子发布，失败或
  取消则回滚 reservation 并删除 staging。达到文件、字节或像素上限会停止后续 worker，
  对外保留 `asset_file_limit_exceeded`、`asset_bytes_per_asset_exceeded`、
  `asset_bytes_total_exceeded`、`asset_pixel_limit_exceeded` 或
  `asset_content_encoding_unsupported` 等稳定 reason。
- Browser-first 的 warm-up 使用 pinned transport 的有界 GET；每个 worker 的标准
  `CookieJar` 只 seed 一次，并在同一 runtime 的 figure/supplementary phase 间复用。
  CookieJar 不跨线程共享；每个已验证 redirect hop 的多条 `Set-Cookie` 都先按
  domain/path/secure 语义导入，再为下一 hop 刷新 Cookie，候选响应 cookie 也只保留在
  当前 worker。它们不会写入 HTTP response cache，catalog 自定义凭据在跨源 hop 删除。
- Browser 触发 PDF download 后，把 `download.url` 加入 direct replay 候选；随后由
  direct transport 执行 DNS/host/redirect policy。`blob:`/`data:` 等无法经该 transport
  获取的 browser-owned URL 返回 `browser_stream_unavailable`。
- 显式请求的页面 screenshot 是诊断输出而非远端 asset：普通 browser screenshot 只截
  viewport，PNG 超过 16 MiB 即丢弃；PDF failure screenshot 直接写文件，超过 16 MiB
  即删除。两者都不作为二进制恢复 fallback，也不会绕过上述 direct-stream 边界。

## 配置

唯一 backend 值为 `camoufox`。可使用：

- `PAPER_FETCH_BROWSER_HEADLESS`
- `PAPER_FETCH_BROWSER_AUTO_PREPARE`
- `PAPER_FETCH_BROWSER_BINARY_PATH`
- `PAPER_FETCH_BROWSER_PROFILE_DIR`
- `PAPER_FETCH_BROWSER_USER_DATA_DIR`
- `PAPER_FETCH_BROWSER_TIMEOUT_MS`

`PAPER_FETCH_BROWSER_USER_AGENT` 只用于允许覆盖 UA 的 direct publisher request；
Camoufox 启动不接受固定 UA，以避免生成的 Firefox 指纹内部不一致。

默认 managed runtime 启动仍用 `download_if_missing=False` 做最终无下载检查；在此
之前，CLI browser fetch/auth/preflight 默认允许按需调用 Camoufox 官方 CLI 安装、
修复并每 24 小时检查更新。`--no-browser-auto-prepare` 或
`PAPER_FETCH_BROWSER_AUTO_PREPARE=false` 可关闭；MCP/库默认关闭，只有请求参数
`browser_auto_prepare=true` 或环境显式开启才准备。所有调用共享跨进程锁和 900 秒
预算；更新失败但旧 runtime 有效时告警继续。随后由 Camoufox package 自行解析 active
browser version。paper-fetch 不会把官方 macOS app 内的 `Contents/MacOS/camoufox` 再当成
custom executable 传回去，因为 Camoufox 的 bundle metadata 位于
`Contents/Resources`。只有显式 `PAPER_FETCH_BROWSER_BINARY_PATH` 才作为 custom
`executable_path` 透传；在 macOS 上优先使用 managed runtime，除非 custom bundle
明确支持 Camoufox 的 executable-path metadata 语义。

准备好官方 Mac runtime 后，可执行不访问远端 publisher 的原生双 context
回归：

```bash
PAPER_FETCH_RUN_NATIVE_CAMOUFOX_TEST=1 \
  PYTHONPATH=src uv run python -m pytest \
  tests/integration/test_camoufox_native_macos.py -q -n 0
```

该 test 串行运行是因为临时 context 与持久 context 共用同一个本地 browser
runtime；Windows / WSL 只运行对应的 pure-mock unit tests。原生 test 通过
Camoufox 公开的 `exclude_addons` 参数排除默认扩展，并对实际扩展下载设置失败
tripwire，因此只验证已预置 managed app bundle 和两类 context 的本地启动，
不依赖已有扩展缓存，也不验证 Camoufox 默认扩展行为。它还通过 BrowserForge
公开的 screen constraint 使用固定 synthetic screen，避免原生 CI 依赖已登录的
WindowServer 或物理显示器。

## 诊断边界

`doctor`/`provider_status` 不启动或准备 runtime。CLI `browser-preflight` 默认可先按需
准备；MCP `browser_preflight` 默认关闭准备。之后才执行 live 页面访问和可选
storage-state 保存。challenge、登录、验证码、付费和 entitlement
边界始终需要合法用户操作，工具不会自动绕过。

IEEE preflight 不以初始 HTTP 202 或 `/rest/document/` 请求作为终态：它最多等待
15 秒，直到 `#article` 包含目标文章号。持续的 AWS WAF 页使用
`reason_code=aws_waf_challenge`、`status=challenge`，并在 diagnostics 中保留
`challenge_provider=aws_waf` 与旧消费者可用的 `legacy_reason_code`。
