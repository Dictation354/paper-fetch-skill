# Browser runtime ownership

PNAS 在 Windows/Linux x64 默认使用 FlareSolverr＋系统 Google Chrome，macOS 和其他架构继续使用 Camoufox；Elsevier 浏览器阶段固定使用 FlareSolverr，不支持的平台跳过；其余出版社保持 Camoufox。browser/full extra 固定
`camoufox==0.5.9`。开发和常规 CI 使用 `uv.lock` 中的具体版本，离线构建使用
依赖 wheelhouse 中的同一固定版本，并由 `paper_fetch.providers.browser_runtime`
统一管理。

## 依赖方向

```text
provider/browser workflow
        ↓
browser_runtime facade + BrowserRuntimeConfig
        ↓
RuntimeContext.new_browser_context_for_runtime_config
        ↓
PublisherProfileManager / FlareSolverrManager
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

## HTML 策略与资源阻断

browser profile 的正文策略是内部配置，不改变 CLI/MCP schema。默认 profile 仍保留
既有 fast attempt、readiness 和资源加载行为；只有明确 opt-in 的 provider 才覆盖：

- PNAS 只执行一次完整 HTML attempt，候选依次为 `/doi/full/{doi}`、
  `/doi/{doi}` 和 DOI resolver。它使用与解析器一致的 bodymatter selector，并在
  配置为 8 秒的 readiness 预算内检查正文长度、段落数和连续两次稳定指纹；预算
  检查在同步浏览器调用返回后执行，不能打断正在等待的 `evaluate`，因此实际耗时
  可能超过预算。预算耗尽后仍对最后一份 HTML 做 block detection 与正文抽取。
- AIP 直接使用正常 HTML attempt，不启用媒体阻断或空脚本替换，因此正常加载期间
  不注册请求拦截；使用出版社独立的原生持久会话及现有正文 readiness。
- Elsevier 正文导航不拦截图片、字体或媒体，沿用浏览器正常资源加载；headed 与
  headless 使用同一策略。
- Science 直接使用正常 HTML attempt；正文稳定后，使用请求剩余预算等待
  bibliography 中实际目标 ID 对应的可抽取引用文本。每轮一次读取引用与可见展开控件，
  按页面控件点击；空引用、ID 先到或仅链接工具不算完成。预算耗尽如实保留缺项和
  degraded 验收，取消继续传播。在自动主框架导航后，使用当前候选中已完成、URL 与当前页面一致且 DOI
  匹配的最新主文档响应采集状态和响应头。初始拒绝响应仍保留在 trace 中；iframe、
  未完成响应和其他论文的响应不能替代文章状态，访问与正文检查继续执行。
- Wiley 主文档返回 401/403 时在 route
  deadline/readiness 预算内继续检查正文。只有正文 selector 达到阈值并连续两次保持
  同一指纹、citation meta/canonical/`.epub-doi` 中的 DOI 与请求精确匹配，且现有
  challenge、验证码、显式 no-access 和 Wiley datalayer 检测均无阻断时，block
  detection 才暂时不把状态本身作为拒绝理由。随后仍须通过 Markdown 和全文
  availability；结果与 trace 始终保留真实 401/403，失败候选继续尝试下一 Wiley URL。
- PNAS、AMS、MDPI、Royal Society、Annual Reviews、ACS、IOP 与 Taylor & Francis
  的正文导航只阻断 `image`、`font`、`media`；document、stylesheet、JavaScript、
  XHR/fetch 保持放行。PNAS 另外精确跳过 `www.pnas.org` 的
  `/pb/widgets/fullSideBarMetric/getResponse` 侧栏统计接口，按 hostname 和 pathname
  匹配，并记录 `blocked_sidebar_metrics_count`；不扩展到其他 XHR/fetch 或 provider。
- ACS 的 `200 + 正确文章标题 + 无 body` 继续归类为 `empty_article_shell`。诊断只保留
  主文档状态、request lifecycle、失败 request/script、console/page error、challenge
  signal、无 query 的 URL 摘要、页面 SHA-256 与 storage-state 指纹；相同
  route/profile/storage/page SHA 立即停止，只有候选 URL、profile 或 storage-state
  确实变化时才允许一次重试。

### 补充材料索引

独立 `target=supplementary` 任务的浏览器索引模式复用同一 Camoufox runtime 和页面附件点击下载，不要求正文就绪，允许摘要页及正文付费页上的公开材料索引；附件自身仍遵守访问限制。材料范围与逐项诊断见 [CLI 说明](cli.md#独立补充材料任务)。macOS 合同中的 `browser.supplementary_index_without_body` 同步记录此边界。

### PNAS 获取边界

PNAS 正文使用浏览器 DOM；侧栏统计请求拦截不构成性能保证。项目尚未接入 PMC
获取路径，不将第三方归档图视为 PNAS 原图验收的等价替代。

### 主文档诊断

主文档诊断会同时记录响应头声明的 `content_length_bytes`、`page.content()` 实际序列化的
`captured_html_bytes`、是否声明 transfer encoding、Playwright 是否观察到
`requestfinished`，以及页面采样时的 Navigation Timing（`document_ready_state`、
`response_end_ms`、transfer/encoded/decoded body size 等）。这可以区分“服务端已完整结束但
只给了小空壳”与“采样时主响应仍未结束”；实现不会等待可能无限阻塞的
`response.finished()`。Content-Length、网络传输字节和 DOM 序列化字节含义不同，只能结合
lifecycle/readiness 判断。诊断不保存响应头集合、cookie、query 或原始 HTML；transfer
encoding 也只输出布尔事实。

正文 diagnostics 会记录实际阻断类型/数量、导航次数、readiness 预算与结果，以及
Wiley 的脱敏 `http_access_status_review`（状态、正文是否稳定、DOI 是否匹配、阻断
signal、最终全文验收与原因）；该复核不保存
Cookie、Authorization、storage-state 或原始失败 HTML。

## 网络与登录态边界

- Camoufox/Playwright 的主文导航、重定向、子资源和 service worker 使用浏览器原生
  网络行为；项目不安装 context-wide URL/DNS 安全 interceptor，也不把带 cookie、
  storage state 的 context 额外限制为单一 origin。
- Provider 的 image/font/media 屏蔽是 page scope 的性能优化，只按 catalog/runtime
  配置处理资源类型，不承担 URL allowlist 或 SSRF 安全保证；其它跨源页面资源继续
  交给浏览器原生加载。
- Direct HTTP/API、二进制流式下载与 cookie-seeded direct fallback 继续使用
  `SafeRemoteUrlPolicy`：每个 redirect hop 重新验证 HTTP(S)、公网 DNS、标准端口、
  userinfo 与 HTTPS downgrade，并在跨 origin 时剥离标准敏感 header。Catalog host 与
  sensitive-header 数据不作为授权 allowlist；调用方显式给出的
  `allowed_hosts` / 额外敏感 header 仍逐跳生效。
- Browser cookie 转 direct opener 时使用标准 `CookieJar`，保留 host-only/domain、
  RFC path boundary、secure 与 expiry，避免把 publisher cookie 扩到子域或相邻路径。
- `persistent_profile` diagnostics 区分原生目录加载、同 context 复用和 JSON 导入；
  `storage_state_load.used` 只在本次实际导入 JSON 时为 true，不把存在的快照标为已注入。
  JSON 导出独立记录于 `storage_state_save`。Camoufox 出版社使用原生持久目录；PNAS / Elsevier FlareSolverr 使用按 provider 隔离的验收后 JSON 状态目录。Camoufox 覆盖
  含 AIP、IEEE、PDF 浏览器回退与资产恢复；目录锁、JSON 导入和 auth 回放见
  [浏览器生命周期](browser-backends.md#生命周期)。
- MCP 私有缓存使用实际目录与从打开的 context 获取的最新摘要；无法取得可信摘要时
  禁用私有缓存读写。元数据只保存摘要，不保存 Cookie 或 localStorage 明文。

## 二进制资产与资源预算

- Springer/Nature 先下载并验收已知原图，失败或无原图候选时才解析图页，最后考虑
  预览降级。两个阶段在同一次资产解析中复用预算、失败来源和落盘；表格页面补齐保留。
- IEEE 浏览器恢复复用已就绪的文章页，按原图 URL 匹配文章入口并提前监听响应。
  图片点击站内查看器；普通表格链接用浏览器原生新标签动作打开，取得原始图像字节后
  关闭临时标签。逐资产串行操作，保留文章页和原有预览降级、失败报告及质量验收。
- 共享图片、附件和 PDF 下载默认先按 URL 走 hostname pool 的 direct stream；Wiley 正文资产
  使用 provider 专用的同会话串行导航，详见 [provider 说明](providers.md#wiley-正文资产)。direct
  401/403 最多进入一次真正的 browser-byte recovery；同一 URL/同一会话状态只执行一次 direct 尝试。恢复可使用 browser `response.body()`、page-context
  `arrayBuffer()`、已加载图像 canvas、`bodyB64`、download/file bytes 或 PDF viewer
  response body。
- 同一论文的正文图和 supplementary 共用 `RuntimeContext` 的一个 `AssetBudget`：普通
  provider 默认不限制资产文件数，仍限制单文件 32 MiB、累计 256 MiB、每图
  64,000,000 像素、并发最多 4，且可被 route cap 进一步收紧。显式有限
  `max_files` 仍会收紧文件数；不可信 arXiv source archive 另有最多 128 个 regular
  member 的遍历门禁。Content-Length、未知长度 chunk、gzip 压缩/解压、EPS/TIFF/PNG
  转换输出和 arXiv source archive 解压都计入对应边界。
- 每个候选写入目标同目录的唯一排他 staging；成功后 flush/fsync 并原子发布，失败或
  取消则回滚 reservation 并删除 staging。达到文件、字节或像素上限会停止后续 worker，
  对外保留 `asset_file_limit_exceeded`、`asset_bytes_per_asset_exceeded`、
  `asset_bytes_total_exceeded`、`asset_pixel_limit_exceeded` 或
  `asset_content_encoding_unsupported` 等稳定 reason。
- 不论字节来自 direct 还是 browser，Content-Length 和实际字节、MIME、像素、取消、
  单文件/总预算、目标同目录排他 staging、flush/fsync 与原子发布完全相同。Browser
  触发的 `blob:`/`data:` PDF download 直接使用 browser-owned bytes，不重放 URL。
- HTTP 资产复用标准 hostname 连接池。AMS、Annual Reviews 与 Springer 的独立 assets
  route 采用 cap 2；全局仍最多 4 worker，正文 HTML/PDF 的串行约束不降低资产 worker。
- 每个资产或失败项公开 queue、DNS policy validation、connect-to-headers/TTFB、body
  stream、browser recovery、retry wait、conversion、save 和 total 毫秒及终态。报告只
  聚合这些时间，不保存带签名 query 的 URL。
- 显式请求的页面 screenshot 是诊断输出而非远端 asset：普通 browser screenshot 只截
  viewport，PNG 超过 16 MiB 即丢弃；PDF failure screenshot 直接写文件，超过 16 MiB
  即删除。两者不作为论文资产，也不会绕过统一资产预算与发布边界。

## 配置

后端选择、系统依赖与按需源码准备见 [浏览器后端](browser-backends.md#pnas--elsevier-系统-chrome-与按需-flaresolverr)。可使用：

- `PAPER_FETCH_PNAS_BROWSER_BACKEND`（`auto|flaresolverr|camoufox`）
- `PAPER_FETCH_CHROME_BINARY_PATH`

- `PAPER_FETCH_BROWSER_HEADLESS`
- `PAPER_FETCH_BROWSER_BINARY_PATH`
- `PAPER_FETCH_BROWSER_PROFILE_DIR`
- `PAPER_FETCH_BROWSER_USER_DATA_DIR`
- `PAPER_FETCH_BROWSER_TIMEOUT_MS`

`PAPER_FETCH_BROWSER_USER_AGENT` 只用于允许覆盖 UA 的 direct publisher request；
Camoufox 启动不接受固定 UA，以避免生成的 Firefox 指纹内部不一致。

CLI、MCP 和 Python API 入口只建立准备作用域，首次使用后端才准备；纯 HTTP、缓存命中与静态诊断不会触发准备。批次共享组件准备结果，浏览器会话、clients 和认证状态仍按请求隔离。抓取、`auth`、preflight 和安装器共用持久记录及文件锁。

Camoufox 的渠道、pin、检查间隔、失败重试和自定义 executable 行为统一见
[浏览器安装与准备](browser-backends.md#安装)与[选择配置](browser-backends.md#选择与配置)。
准备记录和 active 配置在同一缓存锁内更新；损坏目标只修复已校验的版本目录。
配置损坏、路径越界或 symlink/reparse 路径会报错，不通过删除配置修复。
进度和错误写 stderr，取消继续传播。

按 [浏览器预置说明](browser-backends.md#安装) 准备官方最新兼容浏览器和 fpgen 模型后，可执行不访问远端 publisher 的原生双 context
回归：

```bash
PAPER_FETCH_RUN_NATIVE_CAMOUFOX_TEST=1 \
  PYTHONPATH=src uv run python -m pytest \
  tests/integration/test_camoufox_native_macos.py -q -n 0
```

该 test 串行运行是因为临时 context 与持久 context 共用同一个本地 browser
runtime；Windows / WSL 的可移植契约和本地浏览器验证不能替代原生 macOS 证据。原生 test 通过
Camoufox 公开的 `exclude_addons` 参数排除默认扩展，并将版本查询限定为已预置的
正式版或预发布版、禁止重新安装，同时要求复用已预置的 fpgen 模型，因此只验证
已预置 managed app bundle、两类 context 的本地启动，以及出版社原生持久目录的跨重启 Cookie/localStorage 保留（不使用 JSON 回放），
不依赖已有扩展缓存，也不验证 Camoufox 默认扩展行为。它还通过 Camoufox
公开的 screen constraint 使用固定 synthetic screen，避免原生 CI 依赖已登录的
WindowServer 或物理显示器。

## 诊断边界

`doctor`/`provider_status`、解析和帮助命令保持只读，不联网查询或准备 runtime。
`fetch` 在首次实际使用后端时准备；`auth` 和 `browser-preflight` 在实际启动前准备；显式 executable 不参与
自动管理。预检随后执行 live 页面访问和可选 storage-state 保存。challenge、登录、验证码、付费和 entitlement
边界始终需要合法用户操作，工具不会自动绕过。

IEEE preflight 不以初始 HTTP 202 或 `/rest/document/` 请求作为终态：它最多等待
15 秒，直到 `#article` 包含目标文章号。持续的 AWS WAF 页使用
`reason_code=aws_waf_challenge`、`status=challenge`，并在 diagnostics 中保留
`challenge_provider=aws_waf` 与兼容字段 `legacy_reason_code`。

Elsevier 复用 browser workflow 的期限、取消、上下文和资源释放机制，自行执行 API XML → FlareSolverr HTML → API PDF → FlareSolverr PDF。ScienceDirect 页面准备钩子采集 MathJax 保存的原始 MathML；HTML、图片、补充文件和浏览器 PDF 共用本次上下文。macOS 的 Elsevier 仅执行 API 阶段。

安装器默认准备支持的浏览器（在线 `--lite` 跳过）：Linux/Windows x64 依次准备 Camoufox、FlareSolverr，macOS 只准备 Camoufox。FlareSolverr 复用内置或固定版本缓存中的源码和私有依赖，驱动按 Chrome 版本准备；浏览器、模型和驱动准备可能联网。下载预算 10 分钟，本地启动检查预算 2 分钟，只使用临时状态、CDP 和空白页脚本；失败或取消保留核心安装，运行时按需修复继续生效。系统依赖确认与独立重试命令见 [部署说明](deployment.md)。
