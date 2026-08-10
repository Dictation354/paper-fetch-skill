# Browser runtime ownership

生产 browser runtime 只有 Camoufox；browser/full extra 接受
`camoufox>=0.5.4,<0.6`，具体可复现版本由 `uv.lock` 选择，并由
`paper_fetch.providers.browser_runtime` 统一管理。

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

## 配置

唯一 backend 值为 `camoufox`。可使用：

- `PAPER_FETCH_BROWSER_HEADLESS`
- `PAPER_FETCH_BROWSER_BINARY_PATH`
- `PAPER_FETCH_BROWSER_PROFILE_DIR`
- `PAPER_FETCH_BROWSER_USER_DATA_DIR`
- `PAPER_FETCH_BROWSER_TIMEOUT_MS`

`PAPER_FETCH_BROWSER_USER_AGENT` 只用于允许覆盖 UA 的 direct publisher request；
Camoufox 启动不接受固定 UA，以避免生成的 Firefox 指纹内部不一致。

默认 managed runtime 会先用 `download_if_missing=False` 确认用户已经显式执行过
`python -m camoufox fetch`，随后由 Camoufox package 自行解析 active browser
version。paper-fetch 不会把官方 macOS app 内的 `Contents/MacOS/camoufox` 再当成
custom executable 传回去，因为 Camoufox 的 bundle metadata 位于
`Contents/Resources`。只有显式 `PAPER_FETCH_BROWSER_BINARY_PATH` 才作为 custom
`executable_path` 透传；在 macOS 上优先使用 managed runtime，除非 custom bundle
明确支持 Camoufox 的 executable-path metadata 语义。

准备好官方 Mac runtime 后，可执行不访问远端 publisher 的原生双 context
回归：

```bash
PAPER_FETCH_RUN_NATIVE_CAMOUFOX_TEST=1 \
  PYTHONPATH=src python -m pytest \
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

`doctor`/`provider_status` 不启动 runtime。`browser-preflight` 才执行 live 页面
访问和可选 storage-state 保存。challenge、登录、验证码、付费和 entitlement
边界始终需要合法用户操作，工具不会自动绕过。

IEEE preflight 不以初始 HTTP 202 或 `/rest/document/` 请求作为终态：它最多等待
15 秒，直到 `#article` 包含目标文章号。持续的 AWS WAF 页使用
`reason_code=aws_waf_challenge`、`status=challenge`，并在 diagnostics 中保留
`challenge_provider=aws_waf` 与旧消费者可用的 `legacy_reason_code`。
