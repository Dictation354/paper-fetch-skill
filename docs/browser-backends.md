# Browser backend

当前仅支持 Camoufox。所有 browser-backed provider 都通过
`paper_fetch.providers.browser_runtime` facade 获取 Firefox/Juggler context；
provider 不得直接创建 Playwright 或 Camoufox 生命周期。

PNAS、Science、Wiley HTML 在正文连续两次指纹一致（观察间隔 750ms）后，
通过浏览器 owner 线程内的一次同步 `page.evaluate` 捕获含 doctype 的完整 HTML、
标题和最终 URL。权限检查使用 provider preparation 前的快照，preparation 后重新
捕获以保留展开的引用。捕获异常、导航切换或结果无效时沿用原生捕获路径；
请求 deadline 与协作取消检查保持生效，取消直接传播。

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
准备 Camoufox runtime，包括相邻配置、addons、字体和 fpgen 指纹模型；只复制可执行文件
不足以组成可用 runtime。CLI、MCP 和 Python API 在每次抓取请求开始时检查并
准备 managed runtime，包括纯 HTTP 和缓存命中；批量任务在调度前统一检查一次，
子任务和后续浏览器启动复用本次结果。`auth` 和 preflight 在启动浏览器前准备，
与抓取及项目准备函数共享滚动 24 小时（86400 秒）的更新检查记录。
运行时不自动安装缺失的 Python 依赖；core 安装缺少 browser extra，或指定
`PAPER_FETCH_BROWSER_BINARY_PATH` 时，跳过托管更新。
核心安装不下载浏览器，可选安装向导仅在用户明确选择后预置并验证本地启动，
详见 [离线包](deployment.md#离线包)。

browser/full extras 固定 `camoufox==0.5.8`，不自动升级 Python 包。未显式指定
渠道或 browser pin 时，默认跟踪 `official/prerelease`，由 Camoufox 官方版本
发现和兼容判断选择当前平台最新兼容 prerelease，不再使用 Python 包的隐式配对。
准备时在缓存锁内补写默认渠道，旧 active 配置自动迁移；静态探测不写配置。
用户已有渠道、版本 pin、SHA 和自定义 executable 保持优先。可用
`python -m camoufox set official/stable` 跟踪 stable，或用
`python -m camoufox set official/prerelease/<version>` 固定版本。
显式 pin 只准备对应版本，有效本地 pin 直接复用；未 pin 时，本地 runtime 有效且
距上次实际检查结束不足 24 小时则直接复用，满 24 小时后的首次调用再次联网检查。
检查或更新失败也计时；跳过检查不延长间隔，取消不记为完成。浏览器缺失、损坏
或不兼容时立即准备。渠道、pin/SHA 或 Camoufox Python 包版本变化后重新判断
准备需求。记录位于共享 cache 的 `.paper-fetch-update-check.json`，在同一进程锁内
读取和原子写入；缺失、损坏或时间戳在未来时重新检查，写入失败只向 stderr 报告。
更新失败且本地版本校验有效时提示并继续使用；没有可用版本
则记录准备失败并继续 HTTP／缓存流程，实际需要浏览器时报告该失败，同次请求不
重复更新。进度和错误写 stderr，取消继续传播。

联网阶段可先用项目准备逻辑预置 prerelease 和 fpgen 模型：

```bash
python - <<'PYCODE'
from paper_fetch.providers.browser_runtime.preparation import prepare_camoufox_managed_runtime
from camoufox.fpgen_model import ensure_fpgen_model
assert prepare_camoufox_managed_runtime().valid
ensure_fpgen_model()
PYCODE
```

fpgen 模型不包含在 Python wheel 中；首次生成指纹也可能下载模型到 fpgen 包目录，
完全离线前需确认该目录可写并完成准备。

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
由请求准备和 Camoufox active-version 配置共同管理。只有自定义
runtime 明确实现 Camoufox 的 custom-path metadata 布局时才使用该覆盖。

## 生命周期

一个 `RuntimeContext` 在 owning thread 内复用一个 Camoufox process，每次操作
创建独立 `BrowserContext`。HTML、PDF fallback 和资产下载共享相同 runtime
配置及 provider storage-state，同一浏览器生命周期复用准备结果；纯 HTTP 和缓存
命中的抓取也在请求开始时进入准备逻辑，并共享上述 24 小时检查间隔。
Playwright sync 对象不会跨线程共享。

`doctor` 和 `provider_status` 只做静态依赖/配置检查，不启动浏览器、不下载
runtime、不访问出版社页面。CLI 与 MCP `browser_preflight` 在实际启动前自动
准备 managed runtime，并打开页面、按请求保存过滤后的 storage-state。两者都不会
自动认证、绕过 challenge/paywall，也不会调用 PDF fallback。

Preflight 只报告本次 live 检查；正式 fetch 独立导航并重新执行身份、阻断与正文验收。
共享 direct-first 路径中，图片、附件或 PDF 的 direct 401/403 只允许一次 browser-byte 恢复；
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
