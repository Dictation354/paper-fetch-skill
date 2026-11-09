# Browser runtime ownership

浏览器请求统一使用受管 Byparr 3.1.1（Windows/Linux x64 使用 Invisible，其余既有平台使用 Camoufox），由 `paper_fetch.providers.browser_runtime`
管理线程、context、状态目录与资源释放。组件和状态模式见[浏览器后端](browser-backends.md)，
安装与预置见[部署指南](deployment.md#浏览器安装与准备)。

## 依赖方向

```text
provider/browser workflow
        ↓
browser_runtime facade + BrowserRuntimeConfig
        ↓
RuntimeContext.new_browser_context_for_runtime_config
        ↓
PublisherProfileManager / ByparrManager
```

provider 只读取显式 `BrowserRuntimeConfig`，不探测 backend、不持有全局 browser，
也不直接导入 Camoufox 私有实现。缺少 `browser` extra 时，静态状态返回结构化
缺失依赖；core import 和非 browser provider 仍可正常工作。

## 生命周期与线程边界

一个 `RuntimeContext` 在 owning thread 内复用同一出版社 context；正文 HTML、PDF、
figure page discovery、图片、附件、auth 与 preflight 均通过同一 runtime 入口获取会话。
各阶段只关闭自己创建的页面，batch 结束、取消升级或 runtime 关闭时统一释放 manager、
所属浏览器会话及其控制资源。Playwright sync 对象不跨线程共享；资产调度通过
caller-thread 机制调用浏览器，direct HTTP 仍可并行。

原生模式由 profile owner 管理 `persistent_context=True`、出版社归属与目录锁；JSON
模式由原有状态 owner 管理过滤后快照，选择规则见[状态模式](browser-backends.md#状态模式)。
规范化目录使用进程间排他锁，同目录请求排队，不同出版社可并行；等待遵守取消和
请求期限。切换出版社前关闭上一会话并释放锁，不交叉持锁等待。外部占用、归属冲突、
元数据损坏和等待超时明确报错，不删除 Firefox 原生锁或回退临时会话。

显式 executable 必须匹配当前平台引擎：Invisible 校验 release seal，Camoufox 读取
相邻 `version.json`；配置边界见[浏览器后端](browser-backends.md#选择与配置)。
启动进度与错误写 stderr；MCP stdio 的 stdout 仅承载 JSON-RPC。

## HTML 策略与资源阻断

browser profile 的正文策略是内部配置，不改变 CLI/MCP schema。provider 决定候选 URL、
readiness 和允许的资源阻断；具体获取顺序与例外见[provider 指南](providers.md)。
媒体阻断只作用于相应页面，不扩展到其他 provider 或任意 XHR/fetch。

PNAS、Science、Wiley 在正文连续两次指纹一致（观察间隔 750ms）后，通过 owner 线程
内的一次同步 `page.evaluate` 捕获含 doctype 的 HTML、标题和最终 URL。权限检查使用
provider preparation 前的快照，之后重新捕获以保留展开的引用。捕获异常、导航切换或
结果无效时沿用原生捕获路径；请求 deadline 与协作取消保持生效，取消直接传播。

### 补充材料索引

独立 `target=supplementary` 任务的浏览器索引模式复用同一受管浏览器 runtime 和页面附件下载路径，不要求正文就绪，允许摘要页及正文付费页上的公开材料索引；附件自身仍遵守访问限制。材料范围与逐项诊断见 [CLI 说明](cli.md#独立补充材料任务)。macOS 合同中的 `browser.supplementary_index_without_body` 同步记录此边界。

### PNAS 获取边界

PNAS 正文使用浏览器 DOM；就绪采样覆盖 `p` 和 `[role="paragraph"]`，从选中正文
容器的 `textContent` 生成指纹，避免布局变化重置稳定性判断。仍要求两次相同指纹、
750ms 观察间隔和每候选 8 秒预算；首次同步浏览器调用可能受页面执行阻塞影响。
正文图片在 JSON 与原生状态模式下均先直连，失败后复用同主机恢复决策；浏览器恢复
优先通过同会话 `context_get` 携带 cookie 和文章 Referer 收取原始字节，成功即返回，
失败才进入原有页面请求与图片恢复路径，同一轮不重复 context request。原图候选、
并发上限和验收保持不变。侧栏统计请求拦截不构成性能保证。项目尚未接入 PMC
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

- 浏览器的主文导航、重定向、子资源和 service worker 使用引擎原生
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
  JSON 导出独立记录于 `storage_state_save`。两种状态模式的目录、JSON 导入和 auth
  回放见[浏览器生命周期](browser-backends.md#生命周期)。
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

后端选择、环境变量及状态目录见[浏览器配置](browser-backends.md#选择与配置)，
渠道、pin、检查间隔和失败重试见[浏览器安装与准备](deployment.md#浏览器安装与准备)。
CLI、MCP 和 Python API 入口只建立准备作用域，首次使用后端才准备；批次共享准备
结果，浏览器会话、clients 和认证状态仍按请求隔离。原生 Camoufox 本地验证入口见
[测试说明](../tests/README.md)。

## 诊断边界

`doctor`/`provider_status`、解析和帮助命令保持静态、只读；`fetch`、`auth` 和
`browser-preflight` 在首次实际启动前准备 runtime。预检随后执行 live 页面访问与可选
storage-state 保存。受支持的 Cloudflare interstitial 可在原预算内自动处理；登录、
付费、entitlement 与不支持的 challenge 仍遵守访问边界，详见
[受管 Byparr](browser-backends.md#统一受管-byparr)。

IEEE preflight 不以初始 HTTP 202 或 `/rest/document/` 请求作为终态：它最多等待
15 秒，直到 `#article` 包含目标文章号。持续的 AWS WAF 页使用
`reason_code=aws_waf_challenge`、`status=challenge`，diagnostics 保留
`challenge_provider=aws_waf` 与兼容字段 `legacy_reason_code`。
