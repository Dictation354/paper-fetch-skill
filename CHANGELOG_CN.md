# 更新日志

本文件是 [`CHANGELOG.md`](CHANGELOG.md) 的中文对照版，记录 `paper-fetch-skill` 所有值得关注的公共变更。

## 未发布

<!-- SCAFFOLD: changelog-unreleased -->

## 4.1.0 - 2026-07-29

### 新增

- 新增逐 route 的 provider 契约与治理：runtime catalog 统一记录 route 顺序、可用状态、browser 要求、超时、并发、限流策略、验收规则和资产范围；通过自动生成的 route/catalog 快照、按 route family 统计的 golden replay、带到期日的证据 waiver，以及定时 corpus/provider drift 检查，持续校验代码、manifest、fixture 与文档一致性。
- 新增共享的类型化失败诊断、route attempt 耗时摘要、远端 JSON 根/schema 校验、fail-closed 公网 URL 校验和可配置 PDF 传输上限，使 provider、HTTP、workflow、CLI、manifest 与 MCP 各层保留同一组机器可读失败事实。

### 变更

- MCP Python SDK 硬依赖由 1.x 升级到 `mcp>=2,<3`，server 与协议模型访问迁移到 v2 `MCPServer` API，自定义 stdio pump 替换为官方 transport；继续兼容 2025 握手协议客户端，并新增 2026-07-28 现代协议与 resource subscription 支持。
- FetchEnvelope cache 改为按 DOI + request fingerprint 保存多版本，并加入单向 credential capability scope；public、token 与 browser-state 请求可以并存且不会互相覆盖或泄漏，compact cache 投影仍保留确定性的请求与验收证据。
- 将 publisher identity、route discovery、batch lane 并发、browser capability 与 source ownership 集中到 runtime provider catalog；PLOS 使用版本化 journal route，Springer 显式区分 site family，Frontiers canonical route 改为 direct-first，并用结构化 diagnostics 取代分散的隐式启发式判断。
- 加固共享 HTTP/cache runtime：cache identity 纳入 credential scope，敏感/private 响应禁止落盘，redirect diagnostics 全程脱敏，磁盘 cache 使用增量索引做 reconcile/prune；瞬态重试类别受控，host/provider cooldown 等待会先释放并发槽。
- 扩展 Frontiers、Oxford Academic、IEEE、IOP、PLOS、Springer 与 Wiley 的正文提取和资产处理，包括更严格的 JATS identity/body 校验、direct-first 资产下载、显式未归档 supplementary 记录、selected-browser 状态透传和逐 route PDF recovery。

### 修复

- 防止 browser/PDF fallback 接受 challenge 或非 PDF 响应、突破共享 deadline/传输上限、跨 origin 或 credential 边界复用状态，以及在取消或下载失败后遗留半成品。
- 修正 JATS 公式、表格、图片、参考文献与 supplementary 渲染；provider identity 不一致时 fail closed，语义损失保持可见，正文或资产证据不足时不再误升为 complete acceptance。

## 4.0.2 - 2026-07-28

### 修复

- 统一 HTML、JATS 与 Elsevier/CALS 表格的 provider-neutral cell/grid 规范化：扁平化多层表头，支持 CALS named spans，保留整表宽度分组，语义展开可安全处理的 rowspan/colspan，并将不规则网格保留为可读列表和准确的 fallback/布局诊断，避免误报语义丢失。
- 修正 Royal Society Publishing 的 Silverchair 图片提取：保留 `DownloadImage.aspx` 中的签名 CDN 原图，将 `/view-large/figure/` 如实建模为 HTML 原图发现页，拒绝分组 slide 跨图串接，并在降级 preview 前使用选择器驱动的 viewer 兜底。
- 受控跟随 PLOS manuscript endpoint 到临时签名 Google Cloud Storage XML 的重定向，同时脱敏全部 `X-Goog-*` 查询值，并禁止含凭证 Location 的重定向响应进入 HTTP cache。
- 恢复 AMS 共享 Camoufox HTML 与 browser-seeded PDF 工作流，将 AWS WAF HTTP 202 验证页识别为 challenge；无保存状态仍可直接尝试抓取，同时恢复可选的 `paper-fetch auth ams` 与 `PAPER_FETCH_AMS_STORAGE_STATE_JSON` 状态复用。
- 将 ACS 提取迁移到当前 Silverchair 页面结构：保留完整 `.article-body`、表格、图片、MathML 公式、结构化 references 和稳定 article-supplement 链接，同时隔离嵌入 Figshare viewer 与 figure UI chrome；全面刷新 3 份 ACS golden fixture，让 fixture PDF 抓取复用所选浏览器 runtime，并停止在 full-size 图页上等待文章正文 readiness。
- IEEE 受保护的 full-size 图片、表格、multimedia 与 supplementary 资产改为复用同一篇已就绪论文页的 browser context/page，持续携带最新 cookie 与论文页 Referer，且不再把共享 page 导航到资产 URL；同时让 HTTP 403/HTML challenge 的重试选择与既有 browser recovery policy 保持一致。

## 4.0.1 - 2026-07-27

### 修复

- Linux、macOS、Windows 离线包恢复原生 texmath 0.13.2 作为首选公式后端；复用 POSIX 可执行文件时改为复制而非保留构建机符号链接，并继续将锁定的 `mathml-to-latex` 作为二级回退。
- 调用 Inno Setup 前规范化 Windows 相对输出目录，并允许稳定发布重跑在不移动不可变源码 tag 的前提下覆盖受信任打包工具。
- 修复 4.0 CI 拆分时中断的每日 `dependency-latest` 滚动 prerelease：为九个冻结平台/ABI 快照解析 `full` extra，复用共享离线 workflow 构建并校验 wheelhouse，恢复精确资产覆盖和发布后完整性验证。
- 稳定版从 `CHANGELOG_CN.md` 提取对应版本章节，滚动 prerelease 使用中文状态模板；两条发布路径今后都只附带中文 Release Notes，不再生成英文说明。

## 4.0.0 - 2026-07-26

### 破坏性变更

- 移除已弃用的 CloakBrowser 后端和全部 `CLOAKBROWSER_*` 兼容配置；Camoufox 成为唯一受支持的浏览器后端。
- 默认安装改为轻量 core；浏览器正文提取和 PDF 转换分别需要 `browser`、`pdf` 或 `full` extra。

### 变更

- 新增全局与高风险模块的分支覆盖率报告、完整生产包类型检查、unit 运行状态隔离、有界 cookie-aware 下载和安全 XML 解析。
- 以 `pyproject.toml` 为项目版本事实源，采用 SPDX 许可证元数据，并补全发布与供应链元数据。

### 修复

- 在保留 `pymupdf4llm` 1.28.0 的前提下稳定共享 PDF Markdown 结构，用无 provider/DOI 特例的规则修复确定性标题漂移。
- 对 Royal Society Silverchair 的 `view-large` 与 CDN URL 变体做逻辑图片去重，同时保留首选大图 URL、预览 URL、图号和 caption。
- 在去除 HTML 重复标题 section 并应用 PDF、Royal Society 修复后，刷新并完成全部 26 份受影响 golden 的 agent 审核。

## 3.2.1 - 2026-07-25

### 变更

- 将 GitHub Actions 中全部 Python 环境初始化步骤从 `actions/setup-python@v6` 升级到 `actions/setup-python@v7`。
- 将已弃用 CloakBrowser 的兼容范围从 `>=0.4,<0.5` 扩展到 `>=0.4,<0.6`，覆盖 0.5.x Python wrapper，同时保持 Camoufox 为唯一默认浏览器后端。
- 将 KaTeX 从 `0.17.0` 升级到 `0.18.1`，并同步根目录与内置公式工具的 manifest 和 lockfile。

## 3.2.0 - 2026-07-22

### 新增

- 新增浏览器中立的 runtime context/session 契约，统一承载原生 Firefox/Juggler Camoufox 与已弃用 CloakBrowser，并提供 provider 独立状态和正式后端文档。
- IEEE landing、REST HTML、PDF、figure/table/formula、multimedia discovery 与 supplementary file 新增 direct-first selected-browser recovery；仅认证失败、HTML challenge 和网络失败进入浏览器恢复。
- 新增每日 `dependency-latest` 滚动 prerelease：从最新稳定 `v*` Release 解析完整的 Python 直接/传递运行时依赖矩阵，仅在源码或 wheel 集合变化时重建全部 9 个离线安装包，并提供显式 `force_refresh` 恢复入口。
- 新增依赖快照工具与契约测试，覆盖逐目标 wheel 清单、确定性的跨平台 manifest、依赖集合比较，以及构建前的 wheel 文件名/SHA256 校验。

### 变更

- Camoufox 改为唯一默认浏览器后端；CloakBrowser 在整个 3.x 中仅可显式选择，首次选择发出一次 `FutureWarning`，最早于 4.0.0 移除；旧 `CLOAKBROWSER_*` 变量不再隐式选择后端。
- 后端选择保持严格，不做自动跨后端 fallback；所有 runtime config 必须携带 backend，Camoufox/CloakBrowser 状态目录继续隔离。
- 为 `camoufox>=0.5.4,<0.6` 的已支持组合把 Playwright 约束为 `<1.61`；同一运行时/owning thread 复用 Camoufox 进程，完整 HTML 使用 `commit` 加 provider DOM readiness，且不全局屏蔽图片、字体或样式。
- 滚动更新复用现有 Linux、macOS 和 Windows 离线构建 job 并消费冻结 wheelhouse；发布阶段移动固定 prerelease tag、精确覆盖并核验安装包/manifest/checksum assets，上一次资产缺失或校验失败时触发重建，同时不改变稳定版 latest Release。

### 修复

- 修复 IEEE large/preview 内联资源重复渲染，并区分“部分资源失败”和“全部资源未能下载”的警告语义。
- 修复干净 `setup-python` 环境缺少仅解析阶段使用的 `packaging` 时，滚动离线构建在实际打包前失败的问题；`merge`、`compare` 与构建前 `verify` 现在保持标准库自包含。
- 修复滚动 prerelease 指向较旧稳定版源码 commit 时的发布权限问题：tag 与 Release 变更改用仓库级 `ROLLING_RELEASE_TOKEN`，同时保持 job 内置 token 只读。
- 修复 Windows 离线安装脚本环境变量数组末尾逗号导致打包前 PowerShell 解析失败的问题，并为三个发布脚本增加静态回归契约。
- 修复稳定版发布 job 因依赖链中按设计跳过的依赖刷新任务而被 GitHub 隐式 `success()` 条件跳过的问题；发布条件现在始终求值，并显式要求全部直接质量门和离线构建成功。

## 3.1.3 - 2026-07-15

### 新增

- managed Chrome profile、启动、CDP、context 和 page 阶段新增稳定的浏览器生命周期失败 code；有界且脱敏的 stderr 诊断会贯通 browser preflight、provider trace、fallback payload、CLI manifest 与 agent 指引。

### 变更

- CLI 与 MCP 批量执行现在会跨条目空档保留同一个共享 browser manager，并采用带宽限期的协作式取消、仅一次的浏览器关闭升级，以及 CLI 第一次/第二次 Ctrl-C 分级处理。
- 扩展 macOS 离线浏览器 smoke 与单元契约，覆盖保守的陈旧 profile 恢复、4 worker/50 context 复用、取消收敛、诊断脱敏和 fallback provenance。

### 修复

- 修复异常退出后 managed Chrome profile 无法复用的问题：同时核验 singleton 的 owner、host、PID/profile 与 socket，仅归档已确认陈旧的链接并保留恢复记录；首次启动留下新的陈旧 singleton 时最多恢复并重试一次。
- 修复 browser/PDF 与 metadata fallback 丢失精确 HTML/browser 失败 trace 的问题；fallback 成功后 acceptance 仍保留 degraded，浏览器 runtime 失败也不再错误建议执行出版社认证，而是引导先修复本地 runtime 状态。

## 3.1.2 - 2026-07-14

### 变更

- HTML 全文验收改为同时要求可信的 article/body container scope 与实质正文证据；合成 `<article>` 规范化会保留原始 scope，并把 `EXTRACTION_REVISION` 提升到 3，使旧的误判 sidecar 重新抓取。
- 新增聚焦的离线 CI 门和真实 Annual Reviews 空壳 replay，覆盖共享 availability、provider PDF fallback 与 block corpus 回归。

### 修复

- 修复空 full-text marker 与大量 Most Read、Most Cited、Recommended、Related 模块仅凭页面文字量被升级为全文的问题。
- 修复 Annual Reviews 空落地页未触发 HTML 质量失败和既有 PDF fallback 的问题；同时锁住 Wiley `10.1002/joc.3370130706` 的摘要 datalayer 阻断行为。

## 3.1.1 - 2026-07-14

### 新增

- `asset_profile=all` 新增有界的 IOP 补充材料展开流程：先识别同 DOI 的 `/data` 索引，再复用 browser cookie/Referer 提取并下载 `SM` 编号附件。
- CI 新增聚焦契约门，覆盖 IOP 补充材料抽取、显式资产 Referer 透传、签名 URL 脱敏和 browser challenge 回归。

### 修复

- 修复 IOP 补充材料发现误把 `/data` 索引 HTML、figure 下载控件、二维码、父 DOI 不匹配、被阻断索引或空 scope 当作附件的问题；无法解析的已声明索引现在会产生结构化资产失败。
- 修复 browser-backed 补充附件请求未透传显式 Referer，以及 cache key 和保留的资产诊断未脱敏 AWS `X-Amz-*`、`Signature`、`AWSAccessKeyId` 查询值的问题。

## 3.1.0 - 2026-07-13

### 新增

- CLI、MCP、cache 和持久批量任务新增统一资产验收与 manifest v2 记录，覆盖确定性输出 hash、audit/reconcile/resume、有界并发、取消和限流停止语义。
- 新增无网络 provider/runtime 诊断、browser preflight 与 provider catalog MCP resource/tool、紧凑 cache 检查，以及带明确落盘和 resume 模式的结构化 `batch_fetch` MCP tool。
- `paper-fetch doctor --json` 新增机器可读安装 provenance，汇总源码与 distribution 版本、默认 User-Agent、PATH entrypoint、离线 target/revision/build 信息、安装 runtime metadata 和三个宿主的 skill 副本。

### 变更

- 静态 skill 改为薄而自包含的 workflow 入口，拆分 workflow、presets、acceptance、CLI、environment、tool-contract 和 failure-handling reference；source、staging 与安装副本均使用成熟 Markdown parser 验证链接。
- 离线 manifest schema 升级到 3；Linux、macOS、Windows bundle 都记录完整 skill 文件清单及逐文件 SHA256，安装器会在宿主安装前后拒绝缺失、多余、符号链接或 hash 漂移的 skill 内容。
- 按向后兼容新增功能准备 SemVer minor `3.1.0`，同步 Python 包 metadata、稳定工具 User-Agent、Windows 安装器默认版本、部署说明和中英文 changelog。
- CI 新增跨 CLI/MCP/cache/manifest 的轻量契约门；package smoke 改在 checkout 外构建并验证版本、全部 console scripts、MCP EOF 与静态安装 provenance，同时保持 live/offline 重任务仅显式触发。

### 修复

- 修复源码、当前 distribution metadata 和 PATH CLI 处于不同版本时缺少具体路径证据的问题；源码开发态没有 offline manifest 时现在报告不适用，不再误判为安装失败。

## 3.0.1 - 2026-07-04

### 变更

- `paper-fetch browser-preflight` / `paper-fetch auth` 的 Wiley 和 Science 内置样例改为结构更轻、已有 fixture 覆盖的 full-text 页面，减少默认 browser preflight 的慢解析耗时。
- `paper-fetch browser-preflight` / `paper-fetch auth royalsocietypublishing` 新增 Royal Society Publishing 内置样例，默认预检现在会覆盖该 browser-backed provider。
- 默认 GitHub Actions CI 移除完整 unit/devtools/coverage job；本地 `scripts/dev-preflight.sh` 仍保留完整 unit、devtools 和可选 coverage 检查。
- 刷新用户与 agent 文档：恢复 README 展示内容和抓取效果截图，同时保留精简快速上手路径；修正 AMS direct HTTP / browser runtime 表述，统一 CLI `--output-dir` 默认文件名说明为论文 stem 命名，并把 onboarding 中已完成 provider 示例替换为占位 provider 示例。

## 3.0.0 - 2026-07-03

### 变更

- browser-backed provider 现在通过公共 `browser_runtime` backend facade 访问 CloakBrowser；auth、preflight、HTML fetch 和 seeded PDF fallback 共享 storage/profile 路径解析、storage-state 写锁和原子写入。
- external CDP 现在会报告是否借用已有 context、忽略了哪些 context option，以及 storage-state cookie 注入数量；新增 `PAPER_FETCH_CDP_EXTERNAL_NEW_CONTEXT=1` 可在外部浏览器中创建新 context。
- browser-backed 资产下载在安全的 caller-thread attempt 内会复用线程本地 page/context；遇到 Playwright 线程所有权异常会自动降级回 per-call close。
- browser 图片抓取现在对单图 seed warm、page fetch、request-context fetch、直接导航和图片等待共用一个 wall-clock 总预算；PDF fallback 的 browser seed 改为轻量 warm，已拿到 cookie seed 时不再重复导航 seed URL。
- 本地转换链路现在会缓存 Ghostscript/libvips 候选路径与 `--version` 探测；公式转换继续复用既有结果缓存/worker，并新增 subprocess 调用次数测试；无图片导出的 PDF Markdown 渲染会按 PDF hash 复用，并带字节/页数 guard 与渲染诊断。
- browser HTML、seeded PDF fallback、browser asset retry 和 browser preflight 循环新增协作式取消检查。
- `paper-fetch browser-preflight` 现在会对内置样例复用各 browser-backed provider 的正常 HTML candidates 和 HTML bootstrap 重试语义，但仍不触发 PDF fallback。
- 移除 PNAS fast browser HTML preflight 特例；PNAS 现在先走标准 browser workflow HTML bootstrap，再按需进入 seeded PDF fallback。
- AMS 改为无需浏览器的 direct HTTP HTML provider，并新增 direct HTTP PDF fallback；成功时发布 `ams_html` 或 `ams_pdf`，仍不参与 browser auth / preflight / status，也不尝试 seeded-browser PDF fallback。
- CI 离线包 job 现在只在 `v*` tag push 或手动 dispatch 时运行，普通 push/PR 只保留常规质量门。
- 质量门禁现在把 mypy 覆盖扩展到 runtime/config/quality/PDF fallback/browser-runtime/formula core 路径，并在 mypy 配置层启用 `no_site_packages`；CI 与本地 coverage preflight 都强制 unit coverage baseline 40，同时移除 `tests/**` 全局 `B023` ruff ignore。
- 离线安装器现在从 `installer/manifest.json` 派生 MCP、`offline.env`、shell 和 activate runtime env key，一致传播包内 Node / Python encoding 配置；验证脚本覆盖 Antigravity MCP，并且 `activate-offline.sh` 只按 dotenv 解析 env 文件，不再执行其中的 shell 代码。
- `RuntimeContext.parse_cache` 访问器现在使用锁和同 key in-flight 协调，并发 parser memoization 对每个 key 只执行一次 supplier。
- MCP tool 输出现在统一带顶层 `schema_version=1`，provider/HTTP 错误细节会进入机器可读字段；批量任务遇到 rate-limit category、HTTP 429 或 retry-after hint 会停止继续提交，并保留 `abort_reason.retry_after_seconds`。
- MCP cache-index 读取现在校验 `INDEX_VERSION`，旧版/坏 manifest 只有显式 rescan 才会重建；`list_cached` 新增 `cache_mode="index"|"refresh"|"rescan"`，structured resolve 会把 `title`/`authors`/`year` 作为独立 resolver 信号，并把 provider/Crossref primary-secondary metadata merge 语义收敛到一个 rule-backed helper。
- provider waterfall 现在会对访问失败、限流、无结果和通用 provider 失败一致继续后续 fallback route；最终失败会去重聚合 warnings/source trail，并保留 retry-after 细节。
- provider registry 冷启动路径现在不会在根 `paper_fetch` import 时加载 provider entry module、`trafilatura` 或 `idutils`；provider discovery 改为显式内置入口清单加缓存 AST 检测动态入口，browser workflow 的字符串路线标签改放在 `route_order`，不再塞进 `waterfall_steps`。
- 共享 Markdown 表格渲染现在统一复用 canonical pipe-table formatter；IR 与 HTML 路径都会消费显式 headers、转义 pipe/单元格换行、补齐 ragged rows，并渲染 fallback message。
- HTML 派生的公式与 citation 渲染现在会为 inline TeX 保留数学分隔符，formula image URL 启发式会先让位于显式 figure 上下文，并让 section renderer 与 Atypon renderer 共用同一个数字 citation payload helper。
- 同步 README、CLI/MCP instructions、provider/runtime/deployment/extraction 文档、AMS onboarding manifest / access review / cleaning-chain 证据，以及 provider runtime 优化计划，使其匹配新的 browser-runtime 与 AMS direct-HTTP 归属边界。
- 扩展 unit 与 integration 覆盖：包含 AMS direct HTTP HTML/PDF fallback、browser-preflight provider candidates 与不触发 PDF 的行为、external-CDP new-context 诊断、browser runtime facade 接线，以及 browser workflow 依赖分组。

## 2.8.0 - 2026-07-02

### 新增

- 新增基于 provider path template 的 URL DOI 提取：支持 query parameter 中的 DOI、已知 route/扩展名后缀剥离，以及 AMS 旧式 SICI `view` / `downloadpdf` slug；许多带 DOI 的出版社 URL 现在可直接解析，不必先抓 landing page。
- 新增 `scripts/dev-preflight.sh --coverage`，并让 CI unit job 生成 coverage baseline 报告（`term-missing` 和 `coverage.xml`），第一阶段只产出信号，不设置覆盖率阈值。

### 变更

- publisher-facing landing/PDF 请求和 browser workflow 改为通过 `build_publisher_user_agent` 使用浏览器形态 UA；`PAPER_FETCH_USER_AGENT` 继续只作为工具/API UA，不再默认传给 browser context。
- Royal Society Publishing 从 direct HTTP DOI/PDF 抓取改为共享 CDP browser HTML 加 seeded-browser PDF workflow，同时保持 `royalsocietypublishing_html` / `royalsocietypublishing_pdf` source 和不走 XML route 的契约。
- 标题查询解析现在会在 Crossref metadata 明确存在正式期刊版本时，优先选择与 preprint 分数接近的正式出版候选。
- mypy 覆盖面扩展到 136 个项目源码文件，新增覆盖 HTML extraction、browser workflow、Atypon browser workflow、shared JATS/common Markdown helper、CloakBrowser helper、service、artifacts、image conversion 和 resolver 模块。
- 本地和 CI 质量门禁现在会执行 `ruff format --check`、保留 ruff lint、优先使用 repo-local `.venv/bin/python` 或显式 `PYTHON_BIN`、提前提示缺失的开发依赖，并在本地 preflight 中用 `mypy --no-site-packages` 检查项目文件。
- 对全 Python 代码库应用 `ruff format`，并同步调整 module layout 与 asset contract 守护测试，使其匹配格式化后的源码形态。

### 修复

- 修复扩展后的 mypy 契约检查：BeautifulSoup 属性值在传入 helper 前会先规整为文本，可选 HTML 依赖 fallback 在类型检查下保持可用，并让 MCP request/resource/result 类型与当前 SDK 签名对齐。
- 修复 browser-backed 批量并发：managed CDP browser manager 现在会按 provider/browser 配置在同一进程内共享，避免同一 provider profile 的 CLI/MCP 并发抓取互相争抢 `.paper-fetch-profile.lock`；隔离 context 会使用调用线程自己的 CDP 连接，避免跨线程复用 Playwright sync 对象。
- 修复 SICI DOI normalize 与 URL DOI 后缀处理：`<...>` / `;` 等 DOI 后缀会被保留；Frontiers `/full`、IOP `/pdf`、Wiley `/fullpdf`、Springer `.pdf` 等 provider route token 只有在 provider catalog template 能证明其为路由/扩展名时才会被剥离。
- 修复 official PDF fallback 的降级行为：真实 PDF 已下载但 Markdown extraction 不可用时，会保留 provider source trail 和本地 PDF artifact，并通过 warning 说明 PDF-only 状态，不再替换为 Crossref/general metadata-only 结果。
- 修复 publisher landing/probe 请求误把稳定的 `paper-fetch-skill/<version>` 工具 UA 发给浏览器形态出版社路线的问题。
- 修复 `PdfFallbackStrategy`、browser runtime ownership、provider URL/route 行为和 asset-download contract marker 扫描相关的文档/契约漂移，并同步仓库级 ruff format 后的测试窗口。

## 2.7.1 - 2026-07-01

### 新增

- 新增 `paper-fetch browser-preflight`：串行打开 browser-backed provider 的内置样例页，成功时保存 provider 归属的 storage-state JSON，失败时报告需要运行 `paper-fetch auth` 的出版社。

### 变更

- PDF/ePDF fallback 图片导出现在会在有 DOI 时使用与 HTML/XML 资产下载一致的 DOI 归属 `<doi>_assets/` 目录；无 DOI 的内部调用仍保留旧的 `body_assets/` 回退。

### 修复

- AMS 公式图片提取现在会优先读取 lazy `data-image-src` 中的真实 GIF URL，再避开 `Blank.svg` 占位图；纯图片公式会使用出版社真实公式资产渲染和下载。
- AMS direct HTTP HTML preflight 现在会在解析前跟随 DOI 3xx 跳转到出版社全文页，同时仍拒绝 challenge 页面；公开 AMS 文章可保留在无需浏览器的 `ams_html` 路径，不再误落到 browser/PDF fallback。
- PDF fallback 源文件落盘命名现在优先使用 provider payload 中合并后的 metadata；arXiv 这类抓取后才补齐标题、作者和年份的路径不再退回 `unknown_unknown_<doi>.pdf`。

## 2.7.0 - 2026-07-01

### 新增

- 新增 AMS direct HTTP HTML preflight：在 CDP browser fallback 之前先用等价浏览器请求头请求公开 AMS 正文页，公开页面可减少浏览器启动，同时保留原有 browser/PDF 恢复路线。
- 新增 AMS `Download Figure` EPS/TIFF 源图处理：正文 figure 资产会优先使用 publisher 源文件；Ghostscript/libvips 可用时转为 PNG，同时保留原始源文件和转换元数据；转换工具不可用或转换失败时继续回退网页 JPG/PNG 候选。
- 新增可选图片转换工具链：`paper-fetch-install-image-tools`、`install-image-tools.sh`、`PAPER_FETCH_IMAGE_TOOLS_DIR`、`PAPER_FETCH_GHOSTSCRIPT_BIN`、`PAPER_FETCH_VIPS_BIN`、`PAPER_FETCH_EPS_DPI` 和 `PAPER_FETCH_IMAGE_TOOL_TIMEOUT_SECONDS`，并同步离线安装器环境变量。

### 变更

- Linux、macOS、Windows 离线包构建现在只配置 image-tools 路径，不再把构建机 `PATH` 上的 `gs`/`vips` 符号链接打进包内；Ghostscript/libvips 仍是可选运行时工具。
- arXiv Atom API metadata enrichment 改为使用 60 秒专用超时，并对 timeout/5xx 做 2 次 transient retry；provider status 也会暴露这些诊断设置。

### 修复

- 修复 direct HTTP browser-workflow 资产下载：AMS 未启动 browser runtime 时，资产失败不会再尝试刷新 browser seed；supplementary 下载也会继承和正文 figure 一致的 seeded Referer 行为。
- 忽略 repo-local `.image-tools/` 产物，避免本机 Ghostscript/libvips 暂存链接被误提交。
- 同步 README、provider、deployment、architecture、extraction-rule、离线安装器、CI 和单测，覆盖 AMS 源图、图片转换回退和离线 image-tools 行为。

## 2.6.2 - 2026-06-27

### 变更

- 刷新人读与 agent 文档，使 provider routing、browser runtime、artifact、cache、probe、onboarding 和 extraction-rule 契约都描述当前行为，不再保留过时迁移表述，并将 browser runtime 参考文档重命名为 `docs/browser-runtime.md`。
- 更新 CLI 与 MCP 中 provider authentication、browser storage/profile override 的帮助文案，改为说明当前按 provider 归属的 storage-state 行为。

### 修复

- 更新 extraction-rule 校验逻辑，使刷新后的 extraction rules 从旧“兼容说明”表述切换到当前“兼容锚点”表述后，兼容锚点重定向仍会被接受。

### 移除

- 移除过时的 `problems.md` 实现任务草稿和已废弃的 `docs/legacy-browser-runtime.md` 参考文档。

## 2.6.1 - 2026-06-27

### 修复

- 修复 MathJax `\unicode{...}` 命令的 LaTeX normalize，例如把 `\unicode{x2A7D}` 改写为 `\leqslant`，避免 `10.1088/1748-9326/ad560b` 等 IOP Markdown 输出在 KaTeX 中报 undefined control sequence。
- 修复 `MarkdownFormula` 渲染路径：现在会复用公共 LaTeX normalize，而不是只做通用文本 normalize。
- 修复 browser workflow 图片下载：优先使用显式 `download_url` 候选，并拒绝 `Blank.svg`、`Blank.png`、`Blank.gif` 等 lazy placeholder，避免 Atypon/AMS 页面把占位图保存成正文 figure 资产。
- 修复 seeded browser PDF fallback 在 async 线程切换后的浏览器上下文处理：现在使用线程本地 browser context manager，同时保留已配置的 profile 和 user-data 目录，避免跨线程复用 runtime browser manager。

## 2.6.0 - 2026-06-26

### 新增

- 新增 Frontiers (`frontiers`) XML-first provider：支持 `10.3389/` 与 `frontiersin.org` 路由、canonical article 发现、共享 JATS 渲染、figure URL 重写、direct HTTP PDF fallback、`frontiers_xml` / `frontiers_pdf` source、manifest、文档和单测覆盖。
- 新增 `paper-fetch --version`，并补充 CLI help 中 reference、asset 和 token 渲染选项说明。

### 变更

- PDF fallback 现在会在启用 artifact 保存且 `asset_profile=body|all` 时导出 PDF 正文图片到 `body_assets/`，并在 direct HTTP 与 seeded-browser PDF 路由中把这些图片同步暴露到 article assets/artifacts。
- PDF fallback 来源文件现在使用根据 source 派生的稳定文件名，不再统一写成 `downloaded.pdf`，减少同一 artifact 目录内多个 PDF fallback 文件互相覆盖的风险。

### 修复

- 修复 IOP figure 资产抽取：标准 `_lr` / `_online` CDN 图片链接现在会先升级为 `_hr` 高分辨率候选，再进入预览图回退；因此 `10.1088/1748-9326/ad560b` 等 IOP HTML 抓取在高分辨率图可用时会保存 full-size 正文图片。

## 2.5.2 - 2026-06-24

### 修复

- 修复共享 HTML cleanup 误用 `data-title`、`alt`、`title`、`aria-*` 等语义属性触发页面 chrome 噪声过滤的问题。正文图表标题中包含 “related” 等词时不再被误删，例如 Springer/Nature HTML 抽取中 Nature 文章 Fig. 2 缺失的问题。
- 新增回归测试，确保带语义 `data-title` 文本的 Springer/Nature 正文 figure 资产会被保留，同时 class/id 等结构属性标记的 related/recommended article chrome 仍会被移除。

## 2.5.1 - 2026-06-23

### 修复

- 修复 browser PDF fallback 在 async 线程切换后没有保留调用方 runtime browser 配置的问题；现在会继续复用 provider profile 和 user-data 目录等配置，而不是强制创建新的非 runtime browser context。
- 新增 runtime-browser PDF fallback 路径的回归测试，确保线程切换后仍复用已配置的 runtime context。

## 2.5.0 - 2026-06-23

本版本重构 CloakBrowser 浏览器链路，统一切换到 CDP-managed Chrome 复用模型，并通过 provider-scoped 浏览器状态、共享 runtime context 管理和更安全的外部浏览器接入增强反爬/站点验证场景下的稳定性。

### 新增

- 新增可选 `CLOAKBROWSER_CDP_ENDPOINT`，browser workflow 可通过 CDP 连接已经运行的 Chrome/CloakBrowser。
- 未配置 endpoint 时，新增通过 CloakBrowser 启动 managed Chrome，并默认在 `publisher-browser-profiles/<provider>` 下按出版社复用 profile/storage-state。
- 新增按 provider 归属的 browser authentication：`paper-fetch auth <provider>` 支持 browser-backed provider、内置样例 URL、`--url` 覆盖、headed 手动验证，以及无需写 `.env` 的本地 storage-state 保存。
- 新增 `CLOAKBROWSER_PROFILE_DIR`，并识别旧 Wiley storage/profile 环境变量；已有配置可被说明和兼容，managed CDP 路径默认使用 provider-scoped state。

### 变更

- 浏览器后端从直接持有 `cloakbrowser.launch()` 改为 CDP-backed `BrowserContextManager`；HTML 抓取、browser-backed 资产下载、fast HTML preflight 和 seeded PDF/ePDF fallback 会尽量复用 runtime keyed browser manager。
- managed browser 启动改为通过 `cloakbrowser.ensure_binary()` 和本地 Chrome CDP endpoint；`CLOAKBROWSER_HEADLESS`、`CLOAKBROWSER_BINARY_PATH`、`CLOAKBROWSER_PROFILE_DIR`、`CLOAKBROWSER_USER_DATA_DIR` 作用于该 managed 路径。
- 外部 CDP 模式改为借用浏览器中已有 context，并尽量注入 storage-state cookies；文档明确说明 user agent、viewport 等 new-context 参数可能不会作用到 borrowed context。
- runtime-shared browser-backed 资产下载在 managed 和外部 CDP 模式下都改为串行执行，打开隔离 context/page，但不再把 Playwright sync 对象跨 worker thread 传递；普通 HTTP 资产下载仍按配置并发。
- AMS authentication 和抓取改为与其它 browser-backed provider 使用同一套 provider-scoped storage-state 模型；`PAPER_FETCH_AMS_STORAGE_STATE_JSON` 现在是 legacy override，不再是必需配置。
- `paper-fetch auth` 的旧 AMS 专用参数（`--state-json`、`--env-file`、`--no-env-write`、`--wait-seconds`）改为不再支持的兼容占位；profile/storage-state 位置现在由 browser runtime 目录配置控制。
- Browser provider status 检查和 MCP/skill 文档从 CloakBrowser launch 术语调整为 CDP browser runtime / Playwright dependency 术语，并明确外部 endpoint 与 managed browser 行为边界。
- 离线安装器、离线包构建脚本和 CI smoke 检查改为验证 Playwright、CloakBrowser `ensure_binary` 和 `BrowserContextManager`，不再探测已移除的直接 `cloakbrowser.launch()` 路径。
- 生成的离线环境文件和安装器提示改为说明 `CLOAKBROWSER_CDP_ENDPOINT`、managed Chrome 启动、默认 `CLOAKBROWSER_HEADLESS`，以及 browser-backed publisher 的 browser user-agent 默认值。
- CloakBrowser 依赖约束调整为 `cloakbrowser>=0.4,<0.5`。

### 修复

- 修复 managed headless Chrome 启动：当 CloakBrowser 没有产出 headless 参数时，paper-fetch 会补上 Chrome 原生 `--headless=new`，避免 Wiley 等普通 browser-backed CLI 抓取弹出可见浏览器窗口。
- 修复 browser-backed image/file fetcher 在 managed CDP 模式下各自启动独立 Chrome 的问题；现在复用 runtime keyed browser manager，避免同 profile 文件锁死锁，同时保持隔离 context/page。
- 修复批量和单篇 CLI 中 browser-backed figure 资产下载跨线程复用 runtime-shared Playwright/CDP 对象的问题，消除 `greenlet` / `TargetClosed` 异常，并确保 CloakBrowser-backed provider 的本地图表资产能正常落盘。
- managed browser profile 文件锁新增超时，避免另一个 managed browser 已持有同一 profile 目录时永久阻塞。
- 修复 CDP startup polling：当 `/json/version` 已响应但 `webSocketDebuggerUrl` 暂时为空时，不再无 sleep 忙等。
- 修复 fast HTML preflight、browser-backed asset fetcher 和 browser PDF fallback 的配置传递，确保 binary path、CDP endpoint、profile 目录、user-data 目录和 storage-state 能一致传给 browser context manager。
- 修复 seeded PDF fallback 的 HTTP retry cookie 处理：重放 PDF 请求前会按目标 URL 请求并过滤 cookies。
- 修复 provider status 行为：managed browser 模式下不再要求预配置外部 endpoint 或 AMS storage-state JSON 即可把 browser-backed provider 判为 ready，同时仍会拒绝无效 managed binary path 和格式错误的 CDP endpoint。
- 修复离线安装器 activation 与 MCP 环境注册，使 managed CDP browser 变量稳定导出，并避免把过时的 profile/binary 变量继续作为 MCP env key 传播。

## 2.4.1 - 2026-06-20

### 变更

- 更新 CloakBrowser 依赖下限到 `0.3.32`，增强浏览器路线对站点反爬和自动化检测变化的适配能力；推荐所有用户更新。

## 2.4.0 - 2026-06-18

### 变更

- 调整随包 skill 指令：paper-fetch 现在明确适用于 DOI、URL、arXiv ID、标题、引用条目，以及搜索工具已产生候选且需要阅读、总结、比较、翻译、批判、获取全文或核验可读性的流程；普通阅读/总结任务默认不本地保存，只有用户要求归档输出时才确认保存策略；browser runtime 指引也改为跟随 `ProviderSpec.requires_browser_runtime`，不再维护硬编码 provider 名单。
- 加固 provider 与资产抓取路径中的 HTML bytes 解码：`decode_html()` 现在会依次处理 UTF-8 BOM/UTF-8、HTTP `Content-Type` charset、HTML meta charset、`charset-normalizer` 和 UTF-8 replacement 兜底；Springer、IEEE、browser workflow、通用 provider 与 figure-page 路径也会在可用时传入响应 content type。
- 减少 Annual Reviews、Royal Society Publishing、IOP、共享作者/参考文献 helper 与 arXiv helper 中的重复 HTML 解析和 DOM clone 开销。纯 BeautifulSoup 字符串重解析 clone 已改为使用 bs4 node copy，AMS 的 raw MathML fragment 解析仍保持显式处理。
- 将 arXiv official HTML parser 选择集中到 `ARXIV_HTML_PARSER = choose_parser()`，并通过 fixture 测试确认 `lxml` parser 路径仍兼容。

### 修复

- 优化无 `article`、`main` 或 `role=main` 页面上的通用 HTML cleanup：no-root cleanup 现在跳过逐节点噪声分类，同时保留 tag、selector 与 ORCID 移除；content-root 选择也避免重复的整棵子树文本提取。
- 为 raw trafilatura fallback 增加 `1_000_000` 字符上限；cleaned HTML 失败后，超大的原始 HTML 不再传给 trafilatura，但 cleaned fallback parser 仍会继续运行。

## 2.3.0 - 2026-06-14

### 新增

- 新增 Antigravity CLI（`agy`）作为继 Codex、Claude Code 之后的第三个安装目标。新增的 `scripts/install-antigravity-skill.sh` 会拷贝静态 skill（用户级 `~/.gemini/antigravity-cli/skills/`，项目级 `./.agents/skills/`，可用 `ANTIGRAVITY_HOME` 覆盖），并在 `--register-mcp` 时把本地 stdio server（`command`/`args`/`env`）合并进对应的 `mcp_config.json`，同时保留已有的其它 server 条目。离线安装器（`install-offline.sh`、`scripts/windows-installer-helper.ps1`）也会一并安装 Antigravity 的 skill 与 `mcp_config.json`，并提供对称的卸载处理与 CI 校验。

### 变更

- 将 ruff 检查规则集从 `E4,E7,E9,F,TID251` 扩展为额外启用 `UP`、`B`、`SIM105`、`RUF022`，并在全代码库应用相应修复：`typing` 抽象基类导入迁移至 `collections.abc`，`datetime.timezone.utc` 改写为 `datetime.UTC`，`try`/`except`/`pass` 替换为 `contextlib.suppress`，为 `run_provider_waterfall` 补充显式异常链（`raise ... from exc`），并在新规则暴露的位置使用显式 `zip(..., strict=...)`。`B008` 在全项目忽略（MCP 的 `default_mcp_deps()` 参数默认值是刻意的依赖注入接缝），`B023` 在 `tests/` 下忽略。
- 将 mypy `files` 覆盖范围从 model/workflow/mcp/http 契约面扩展至更多基础模块（`metadata`、`markdown`、`extraction/markdown_render`、`tracing`、`reason_codes`、`arxiv_id`、`normalize_journal_name`、`section_vocab`、`logging_utils`、`publisher_identity`、`provider_catalog`、`extraction/citation_anchors`），分析文件数从 45 增至 68，并附带使检查通过所需的类型修复。
- 不再跟踪 `failures/` 下的临时批处理调试产物与 `figures/` 下三个无引用的原始抓取产物，并将二者加入 `.gitignore` 以防再次提交。
- 将打包的 `mathml-to-latex` 公式后端从 1.5.0 升级到 1.8.0，并在根目录与 `src/paper_fetch/resources/formula/` 的 package 清单与 lockfile 之间同步该版本。

## 2.2.1 - 2026-06-12

### 变更

- 磁盘缓存条目遍历不再读取每个 JSON 文件以提取 `stored_at`，改为直接使用 `st_mtime`，消除每次 `_prune_disk_cache` 调用中的 O(n) 文件读取。
- `_load_disk_cached_entry` 中的磁盘缓存读取不再持有独占 `_disk_cache_lock` 进行文件 I/O，并发缓存读取不再相互阻塞。
- `_sensitive_cache_header_names` 与 `_cache_key_header_names` 改为通过 `@functools.cache` 在进程级别计算一次，不再在每次 HTTP 请求时重复调用 `provider_sensitive_header_names()`。
- `prepare_html_extraction_tree` 消除了多余的第二次 BeautifulSoup 解析：现在直接在原树上执行剪枝并序列化一次，不再先将子树序列化为字符串再重新解析。
- `html_cleanup_rules` 改为通过 `@functools.lru_cache(maxsize=32)` 进行缓存，单次抽取流程中相同 noise profile 的多次调用共享同一个 `HtmlCleanupRules` 实例。
- `choose_parser` 在模块导入时计算一次 `importlib.util.find_spec("lxml")` 并将结果存为模块级常量，每次调用不再重复执行。
- `classify_dom_cleanup_node` 改为引用模块级 `_HEADING_TAG_RE` 常量，不再在每次访问 DOM 元素时编译两次 `re.compile(r"^h[1-6]$")`。
- `_inline_image_contents` 每个资产只调用一次 `path.stat()`，不再先调用 `path.is_file()` 再调用 `path.stat()`。
- `run_blocking_call` 改为使用 asyncio 默认线程池（`None`），不再为每次调用创建独立的 `ThreadPoolExecutor`；`batch_resolve_tool_async` 与 `batch_check_tool_async` 中的日志桥生命周期改用 `ExitStack` 管理。
- `mark_envelope_cached_with_current_revision` 改为原地修改并返回 `None`，调用方相应更新。
- 将 mypy 覆盖范围扩展至 `paper_fetch.mcp` 和 `paper_fetch.http` 包；补充缺失的类型标注和 `cast` 调用以通过严格检查。
- 将 `mcp` 版本约束从 `>=1.27,<1.28` 放宽至 `>=1.27,<2`。

### 修复

- `parse_retry_after_seconds` 现在通过 `float()` 解析后截断为 `int`，能正确处理 `"0.5"` 或 `"1.5"` 等分数秒 `Retry-After` 值；此前这类值会落入 HTTP-date 解析器并被静默丢弃。
- `_mcp_log_level` 对级别高于 `CRITICAL` 的日志记录不再返回 `"debug"` 作为兜底值，改为返回 `"critical"`。

## 2.2.0 - 2026-06-10

### 新增

- browser-workflow 图片恢复链路现在会先复用预热正文页中目标 `<img>` 的 canvas 导出；目标图存在但尚未加载时，会先在同一正文页执行带凭据的 `fetch()` 拉取原图字节，再退回图片 URL 直连请求、页面 fetch 与 navigation 候选（影响 `wiley`、`science`、`pnas`、`ams`、`annualreviews`、`acs`、`iop`、`aip`、`mdpi`）。

### 变更

- Atypon/Wiley figure caption label 现在只从显式 label、figure DOM id、图片 URL basename，或以 `Figure N` 起始的 caption 推断，并新增读取 `.figure__title` 选择器；caption 正文中间的 `Figure N` 交叉引用不再能覆盖当前图号。
- 收敛 browser-workflow 资产下载内部实现（行为不变）：image 与 supplementary fetcher 共用同一个泛型的按线程文档 fetcher，image/file fetcher 复用共享的 browser 响应头/状态 helper，两个 attempt-fetcher 构建函数合并为一个（删除未使用参数），并以共享的 `dedupe_normalized` 工具替换四处重复的有序 URL 去重。

### 修复

- 公式图片不再被当作 figure：节点中唯一图片是公式图时不产出 figure 资产，公式图片锚点只按 formula 资产改写，同一图片 URL 同时命中 figure 与 formula 时保留 formula 语义，公式图片也不再占用 inline figure 槽位。
- inline figure 注入现在同时按图片 alt 与图片 URL basename 提取去重键；当某 figure 已以 Markdown 图片形式出现时，正文里的 `Figure N` 交叉引用会被跳过，重复或缺少 label 的 figure 不再触发第二次插图。

## 2.1.0 - 2026-06-08

### 新增

- 新增 `paper-fetch auth ams`：打开 headed CloakBrowser 完成 AMS 合法站点验证，保存 storage-state JSON，并可把 `PAPER_FETCH_AMS_STORAGE_STATE_JSON` 写入 paper-fetch 用户环境文件。
- 新增 Elsevier PII URL 解析：直接输入 ScienceDirect 或 LinkingHub `/pii/...` URL 时会提取 PII，先用 Elsevier 官方 Abstract PII API 补 metadata，再进入常规 DOI 全文路径。

### 变更

- AMS browser workflow 和 provider status 现在要求显式配置 `PAPER_FETCH_AMS_STORAGE_STATE_JSON`；AMS 不再依赖无状态 browser 启动，也不把 `CLOAKBROWSER_USER_DATA_DIR` 当作认证来源。

### 修复

- Springer HTML 虽被 availability 判为可用但最终只渲染出 abstract-only Markdown 时，现在会继续尝试 PDF fallback，而不是提前返回摘要级结果。
- Crossref 标题查询同时命中近重复预印本与正式发表版本时，现在优先选择正式发表候选。
- Springer article-in-press 提示页在缺少摘要后正文时会被识别为 availability blocker，避免误判为全文可用。
- IOP Appendix figure caption 已在正文 Markdown 出现时不再重复追加；已渲染但非内联图片对应的 figure asset caption 也会去重保留。

## 2.0.0 - 2026-05-28

### 变更

- MCP provider 指引改为从运行时 provider catalog 派生，使可用 provider hint、browser-runtime provider 和公开 source 名称与已注册 provider 保持一致。
- 刷新公开 provider 与抽取规则文档，覆盖当前 provider catalog 中 Annual Reviews、Royal Society Publishing、PLOS、Oxford Academic、ACS、IOP、AIP、MDPI、AMS、Science 和 PNAS 等 route 细节。
- browser-workflow provider 改为通过 provider spec 标记，不再维护单独硬编码的 browser-runtime provider 列表。
- 更新 Codex skill 安装、离线安装器、部署和 onboarding 文档，使其匹配当前支持的安装入口。

### 移除

- 从随包脚本中移除 Gemini skill 安装器和旧版 Codex MCP runner 脚本。

### 修复

- 让 CloakBrowser workflow 标签、provider docs drift 检查、离线安装检查和 skill template 测试与 catalog 派生的 provider 事实保持同步。

## 1.9.0 - 2026-05-27

### 新增

- 新增 AIP Publishing (`aip`) provider：支持 `10.1063/` 与 `pubs.aip.org` 路由、CloakBrowser article HTML、seeded-browser PDF fallback、`aip_html` / `aip_pdf` source、正文图/表/公式/补充材料抽取与 provider-managed abstract-only 降级。
- 新增两段式 provider onboarding 人工 gate：通过 `prepare-human-preflight` 和 `finalize-review-artifact` 先审核 waterfall/access，再批量确认最终 Markdown 质量，避免逐 fixture 手工编辑 review YAML。
- 新增 IOP Publishing (`iop`) provider：支持 `10.1088/` 与 `iopscience.iop.org` 路由、CloakBrowser article HTML、seeded-browser PDF fallback、`iop_html` / `iop_pdf` source，以及 Radware/hCaptcha challenge 拒绝。
- 新增真实 IOP fixture 覆盖 table、formula 与 PDF fallback purpose，样本为 `10.1088/2058-9565/ac3460` 和 `10.1088/1748-9326/aa9f73`。
- 新增 ACS (`acs`) provider：支持 `10.1021/`、`www.acs.org` / `pubs.acs.org` 路由、共享 CloakBrowser HTML、seeded publisher PDF/ePDF workflow、table/formula/Supporting Information replay 覆盖，以及 seeded browser-navigation headers 下的公开 `/doi/pdf` fallback 捕获。
- 新增 Annual Reviews (`annualreviews`) provider：支持 `10.1146/` DOI 路由、CloakBrowser 渲染 HTML 全文、seeded-browser PDF fallback、provider-managed abstract-only 降级、fixture replay、golden corpus 覆盖和 HTML 正文图片资产抽取。

### 变更

- 收紧 provider fixture discovery：Crossref 候选搜索现在可按 DOI prefix 过滤，probe 前会剔除 off-provider DOI，challenge/access/empty-shell probe 结果不会再被评为 high-confidence 全文 fixture。

### 修复

- 重新审批 IOP replay fixture 覆盖范围：真实 `10.1088/1748-9326/ab7d02` 捕获现在通过正文内的 `stacks.iop.org` media 链接覆盖 supplementary purpose。
- ACS onboarding 合约现在要求正文 figure 资产内联和下载；browser workflow 清理会保留 figure 内图片链接，下载后可把正文 Markdown 远程 figure URL 改写为本地 asset path。
- Annual Reviews fast browser fixture 捕获会等待动态全文 DOM 容器填充；机构访问提示 `access provided by` 不再作为 paywall 阻断词，但仍保留为 Markdown 降噪词。
- browser PDF fixture 下载返回非 PDF payload 时改为 `NON_PDF_FALLBACK_CONTENT`，不再误报为网络暂态，并要求替换失败 PDF 样本后才能续跑 onboarding。
- Chromium 暴露 PDF viewer shell 而不是底层 PDF 字节时，browser PDF fallback 会通过同一 browser request context 重新获取真实 PDF payload。
- manifest 驱动的 fixture 捕获在多个 purpose 复用同一 DOI 文章时，会复用已登记 fixture，避免重复 purpose 阻断批量捕获。
- fixture 捕获页已经包含填充的全文容器时，不再把同页访问 UI 文案误判为 access gate。
- 对已知 MDPI 数字段 article URL 在通用 landing page 抓取前先推导 DOI；对已知 MDPI DOI suffix 在回退 `doi.org` 前先反推 MDPI article landing URL。
- 外部公式转换子进程输出包含非法 UTF-8 字节时改为 replacement 解码，避免 Windows reader thread 抛出 `UnicodeDecodeError`。
- PDF fallback 转 Markdown 时，PyMuPDF 在 Windows 上探测 Tesseract 的子进程输出如果包含非法 UTF-8 字节，也改为 replacement 解码。

## 1.6 - 2026-05-22

### 新增

- 新增实验性 macOS 离线 release tarball，覆盖 CPython 3.11、3.12、3.13、3.14，并在 CI 中验证安装、headful 布局和 CloakBrowser smoke。
- 新增 MDPI CloakBrowser HTML provider，支持 browser PDF fallback、录制 replay fixtures、Markdown 清洗覆盖，以及 `mdpi_html` / `mdpi_pdf` source。
- 新增 AI provider onboarding 的 operator access review 和 Markdown review artifact，并用 schema gate 在 discovery 前和 acceptance 阶段校验。
- 新增本地 `scripts/dev-preflight.sh` 门禁、低强度 contract 层 `mypy` 检查、公式 Node 包版本同步测试，以及 golden corpus provider adapter，方便后续 provider 接入。

### 变更

- manifest 驱动的 fixture 捕获新增 `--all` 批量模式；provider scaffold replay 在目标文件已存在时返回 merge plan JSON。
- live review 现在会对照 manifest `route_sources` 校验 provider source，并复用 manifest Markdown contract 做自动 issue 分类。
- 离线安装器生成和刷新 `offline.env` managed block 时默认启用普通 Chrome browser User-Agent，降低 CloakBrowser 抓取 AGU/Wiley 时停在 Cloudflare challenge 页的概率。
- MCP status、live review 支持和 golden corpus 代表样本覆盖尽量从 provider 事实源派生，减少新增 provider 时的硬编码同步点。

## 1.5.6 - 2026-05-18

### 修复

- 修复 Windows 离线安装器 smoke check：改为把 bundled Python 探针写入临时 `.py` 文件后执行，不再通过 `python.exe -c` 传递多行脚本，避免 PowerShell/native command 边界剥离 CloakBrowser 检查中的引号。

## 1.5.5 - 2026-05-17

### 修复

- 恢复 Wiley 在 Cloudflare/challenge HTML 失败后的全文 waterfall：仍会继续尝试 browser PDF/ePDF fallback，再尝试可选 Wiley TDM API PDF lane，全部失败后交给 provider-managed metadata-only 降级。
- 保留 AGU/Wiley Cloudflare workaround 的推荐路径：优先设置 `PAPER_FETCH_BROWSER_USER_AGENT`，通常继续使用 headless CloakBrowser。

## 1.5.4 - 2026-05-17

### 变更

- Linux 离线 release asset 从 `.tar.gz` 包改为单文件自解压 `.sh` 安装器，支持 `--install-dir <path>`，默认安装到 `~/.local/share/paper-fetch-skill`。
- Linux 和 Windows 离线升级会在安装新版 runtime-only payload 前清理旧 runtime payload，同时保留用户写入的 `offline.env` 内容，并刷新受管理的环境变量、PATH、skill 和 MCP 注册块。
- Linux 离线卸载语义调整为 `--uninstall` 只移除用户级 shell / skill / MCP 集成，`--purge` 才显式删除固定安装目录。

### 修复

- 修复 Windows 离线安装器在 runtime 文件已安装后，仍会因用户级集成或 smoke check 在本机失败而中断的问题；相关警告现在写入 `install-helper.log`。
- 修复 Linux 离线安装器的 CloakBrowser 检查以及 Claude MCP 注册参数，使其匹配当前 host CLI。
- 修复 browser PDF fallback 在调用方已处于 asyncio loop 中时直接启动 Playwright Sync API 的问题，相关 CloakBrowser 同步工作现在转交到 worker 线程执行。

## 1.5.3 - 2026-05-17

### 变更

- Windows 离线安装器改为只打包 embedded runtime、已安装 Python 包、命令启动器、静态 skill、formula tools 和安装器元数据，不再把仓库源码快照或构建 wheelhouse 放进安装后的 payload。

## 1.5.2 - 2026-05-17

### 变更

- Linux 离线 tarball 改为预安装 runtime 包，包含 `bin/` 启动器和 `runtime/site-packages/`，不再分发仓库源码快照或目标机安装用 wheelhouse；安装阶段不再运行 pip。

### 修复

- 修复 Wiley、Science、PNAS、AMS 的 Atypon browser HTML 路线：当稳定全文 DOM 已出现时，不再因为页面残留 Cloudflare/challenge 文案而过早判定 HTML route 失败。

## 1.5.1 - 2026-05-17

### 修复

- 调整 browser workflow 的 User-Agent 策略，CloakBrowser/Playwright context 不再默认继承 `paper-fetch-skill/<version>` HTTP UA。
- 新增 `PAPER_FETCH_BROWSER_USER_AGENT` 作为仅用于浏览器上下文的 UA 覆盖；显式设置的 `PAPER_FETCH_SKILL_USER_AGENT` 仍作为兼容 fallback 可用于浏览器上下文。
- 补充 AGU/Wiley 遇到 Cloudflare challenge 时的配置说明：可在保持 headless CloakBrowser 的同时设置普通 Chrome UA。

## 1.5 - 2026-05-16

### 新增

- 新增基于 CloakBrowser 的浏览器运行时抽象和 provider 状态诊断，替代 FlareSolverr 运行时路径。
- 为迁移后的浏览器工作流新增浏览器图片 payload 和运行时 smoke 覆盖。

### 变更

- 将 Science、PNAS、Wiley、AMS、IEEE 浏览器/PDF 流程、MCP 诊断、live runner、安装器、离线包和 CI 从 FlareSolverr 专用路径迁移到共享 CloakBrowser/browser runtime 路径。
- 移除内置 FlareSolverr 源码、安装脚本、vendor patch、文档和 release 包运行时资产；离线包现在分发 `cloakbrowser` Python 包，并说明浏览器 binary 不再重新分发。
- arXiv HTML 资产处理现在会在官方 HTML 只暴露缺失图片占位符时，从 arXiv e-print source package 恢复 figure 资产；source PDF figure 会渲染为 PNG 资产并插回 figure caption 附近，全文抽取仍优先使用官方 HTML。
- Browser workflow 并发资产下载现在使用线程私有的 browser/context/page 实例，而不是在 worker 线程之间共享 `RuntimeContext` browser。
- 围绕新的运行时契约优化了 browser workflow 抓取、CLI 输出目录处理、provider request options、MCP cache payload 处理，以及 fixture/scaffold 文档。

### 修复

- 修复 Windows 离线包构建器，使 MCP command wrapper 的 PowerShell here-string 在写入 `README.offline.md` 前正确闭合。
- 在浏览器抓取期间抑制 CloakBrowser 首次启动时输出到 stderr 的推广 banner。

## 1.4.1 - 2026-05-15

### 新增

- 新增原生 CLI 批量抓取，支持 `--query-file`、逐条输出文件、JSONL 批量摘要、有界 `--batch-concurrency`，以及不终止整批任务的逐条失败报告。
- 新增专用 CLI 文档，说明输出路由、artifact 模式、asset profile、`--save-markdown` 和批量模式行为。

### 变更

- Release 1.4.1：原生 batch CLI 和 provider/MCP 改进。
- 调整 CLI 输出/artifact 语义，使批量和单条 query 运行都能一致地区分主输出文件、保存的 Markdown 和 provider artifact。
- 更新 MCP fetch/cache payload 行为，覆盖 inline image budget、cache resource 可见性和 schema 覆盖。
- 加固 Elsevier Markdown 和 Springer HTML 抽取中关于表格、figure、资产链接重写和 provider 专属清理的处理。
- 修复离线安装器 smoke check，使 Linux 和 PowerShell 安装都使用当前 MCP provider-status 入口点。
- 刷新 README、provider、deployment、内置 skill 和 tool-contract 文档，使其匹配新的 CLI 与 MCP/provider 行为。

## 1.4 - 2026-05-12

### 新增

- 新增面向 `arxiv.org` 和 DOI prefix `10.48550/` 的 `arxiv` provider；官方 HTML 成功时发布 `arxiv_html`，文本 PDF fallback 发布为 `arxiv_pdf`。
- 新增 10 个真实 arXiv replay fixture：8 个官方 HTML 成功样本和 2 个官方 HTML 404 -> 真实 PDF fallback 样本，每个样本都包含 arXiv API metadata replay。

### 变更

- 重构 Phase 1 routing/extraction 内部实现：Copernicus URL identity 现在使用 catalog `domain_suffixes`，早期 metadata probe 由 `ProviderSpec.probe_capability` 驱动，reference-anchor 检测集中到 HTML semantics，Wiley supplementary data attributes 由 Wiley extractor 处理，Science/PNAS figure teaser 过滤现在接收真实 publisher。
- 集中 provider source ownership，包括 Springer HTML/PDF source ownership、API-like hosts、Wiley TDM URL template、Springer/Nature domain matching、workflow HTML-managed fallback marker，以及 `ProviderSpec` / `SOURCE_PROVIDER_MAP` 中的正文文本阈值。
- 收紧 Phase 4 generic extraction 边界：Springer/Nature citation cleanup pattern 现在位于 provider 层，provider formula token 需要显式注入 `ProviderHtmlRules` profile，Research Briefing 无作者签名由 quality signal 管理。
- 完成 Phase 4 duplicate-source cleanup：`FRONT_MATTER_PUBLICATION_KEYWORDS` 现在只有一个 generic source，Science/PNAS publication token 按 provider rule 作用域限定；`SourceKind` 在 import 时校验 catalog sources；Cloudflare cookie filter 共享 FlareSolverr constants；Science 复用共享 AAAS datalayer pattern。
- 通过 provider rules 和共享 signal pattern 集中 Phase 3 HTML availability override 与 access-gate signal，包括 Science perspective、Elsevier canonical abstract 和 Springer preview-wall body-run 处理。
- 加固 Phase 6 provider-specific contract：IEEE article-number URL parsing 现在只接受 `/document/{article_number}/` landing path，Springer/Nature Creative Commons cleanup 不再移除 article root，HTML asset helper 在 package 初始化期间避免 import public models package。
- 完成 Phase 7 cleanup：generic browser HTML failure 现在是 `HtmlExtractionFailure`，FlareSolverr status probe 使用非 DOI sentinel，landing-page redirect resolution 统一为基于 request URL 的语义，并移除旧 FlareSolverr rate-limit env cleanup code。
- 将 Atypon browser HTML/PDF candidate template 移入 `ProviderSpec`，并移除 `paper_fetch.providers.science_html`、`paper_fetch.providers.pnas_html` 和 `paper_fetch.providers.wiley_html` compatibility facade。
- 完成 Phase 5 Atypon/Wiley cleanup：Wiley 拥有 abbreviation 和 supplementary filename contract，datalayer signal parsing 使用 schema field map，并将 Atypon browser workflow scope 记录为仅覆盖 Science/PNAS/Wiley catalog entry。
- Golden criteria live review 现在把 `copernicus` 纳入受支持 provider rotation 和 provider-status diagnostics。
- 记录 Phase 8 CI/test policy 更新：常规 unit/integration job 和完整 golden regression 继续使用 pytest-xdist 默认值，而 live FlareSolverr/MCP 路径记录其必须串行执行。
- 澄清 CLI 输出语义：显式 `--format` 与 `--output-dir` 和 stdout 输出同时使用时，现在也会在 `--output-dir` 下写入同格式文档副本；`--output` 仍然是显式格式化输出文件路径。
- Golden criteria live review 现在把 `arxiv` 视为受支持 provider，记录 arXiv provider status，在 arXiv API metadata 出现短暂失败时保留 derived-URL fallback，并将 arXiv 资产部分下载诊断分类为 `asset_download_failure`。
- arXiv metadata enrichment 现在使用小型内部 Atom API client 做 ID lookup，不再依赖 PyPI `arxiv` / `feedparser` dependency chain。
- arXiv HTML 资产下载现在使用 provider 专属的较低并发上限，并对网络异常失败顺序重试一次，同时将不可重试失败保留在 `quality.asset_failures`。
- arXiv fulltext routing 现在固定为官方 HTML 优先，并直接使用文本 PDF fallback；废弃的本地 source-conversion fallback code 及相关资产处理不再属于受支持 route。
- arXiv 官方 HTML Markdown cleanup 现在会合并普通正文硬换行，清理 LaTeXML TeX annotation 内嵌套的 `$...$` delimiter，并把全宽表格标题行从 GFM pipe table header 中提升出来。
- 完成 Phase 2 callback cleanup：Atypon DOM postprocess 和 scoped asset extraction 现在是 provider-registered callback，provider display name 通过 catalog-backed `provider_display_name()` helper 解析。
- 完成 Phase 3 catalog field cleanup：Springer/Nature PDF candidate、arXiv metadata probe short-circuit、provider HTML artifact persistence、XML source inference、provider-managed abstract-only handling 和 PDF URL token semantics 现在由 catalog/callback 驱动，不再硬编码 provider name。
- 完成 Phase 5 Atypon browser workflow rename：旧 Science/PNAS package/profile/postprocess 名称迁移到 `atypon_browser_workflow`，移除 legacy profiles facade，Atypon profile dispatch 现在从 `ATYPON_BROWSER_WORKFLOW_PROVIDER_NAMES` 动态 import provider HTML module，共享 figure-link 和 abstract-redirect helper 移入中立 module，Science citation-italic repair 现在属于 `_science_html.py`。
- Elsevier XML body asset download 现在只对短暂网络失败项顺序重试一次，并在重试成功时移除原资产失败记录。
- Wiley formula image discovery 现在包含 `data-altimg` fallback span 和 display formula container，因此 image-only formula 可以进入 `kind="formula"` 资产下载路径，而不再要求必须有 `<img>` tag。

## 1.3 - 2026-05-09

### 新增

- 新增面向 Copernicus Publications DOI prefix `10.5194/` 的 `copernicus` XML-first provider；NLM/JATS XML 成功时发布 `copernicus_xml`，文本 PDF fallback 发布为 `copernicus_pdf`。
- 新增 8 个 Copernicus XML golden fixture，覆盖 ACP、HESS、GMD、TC、ESSD、NHESS、AMT 和 BG；另有 4 个旧 Copernicus PDF-fallback golden fixture，其 XML 仅有 abstract-level 内容；live smoke sample 覆盖仍位于 `PAPER_FETCH_RUN_LIVE=1` 开关之后。
- 加固旧文章 Copernicus fallback 处理：当 XML 只暴露 abstract-level 内容时，这些 XML 失败现在会直接继续进入文本 PDF fallback；landing page 省略 PDF metadata 时，PDF discovery 会包含 DOI-derived `.pdf` candidate。

### 重构

- 将 `paper_fetch.http` 从单模块拆分为 package facade 加内部 transport、cache、retry、body 和 error module，同时保留现有 public import path。
- 将仅开发使用的 `geography_live`、`geography_issue_artifacts` 和 `golden_criteria_live*` module 从 `paper_fetch.*` 移到仅 source-tree 可见的 `paper_fetch_devtools.*`；wheel 不再分发这些 module，现有 repo-local script CLI 保持相同行为。

### 变更

- Copernicus XML extraction 现在在 validation 和 article assembly 中复用已解析 XML root，使用具名阈值验证可用正文段落，并在 landing HTML 无法抓取时继续使用 DOI-derived XML/PDF URL。
- Copernicus XML asset 现在以 `original_url` 作为 canonical remote URL，共享资产下载在下载后镜像兼容 URL 字段；table asset 直接以 `kind="table"` 和 `table_render_kind` 输出。
- 安装器结束摘要现在会明确提示 Elsevier 全文抓取需要从 <https://dev.elsevier.com/> 申请并配置 `ELSEVIER_API_KEY`，并指向对应 `.env` 文件。
- Windows 离线发布产物改为 `paper-fetch-skill-windows-x86_64-setup.exe`，内置 CPython 3.13 x64、Python 依赖、Playwright Chromium、formula tools、FlareSolverr runtime、Codex / Claude Code skill 和 MCP 注册 helper。
- GitHub Actions 在 `v*` tag push 或显式手动发布时，会等常规验证、完整 Linux 离线包矩阵和 Windows x86_64 setup exe 成功后创建 GitHub Release，并上传 4 个 Linux tarball 加 1 个 Windows 安装器 release asset。
- 扩展正文图片 payload 识别与落盘格式：除现有 PNG/JPEG/GIF/WebP/AVIF/TIFF 外，支持 SVG 文本、BMP、ICO、APNG、HEIC/HEIF 的 MIME/扩展名映射；正文图片保存前会确认 payload 具备图片 magic 或顶层 SVG 文档特征，避免把 challenge HTML 当图片保存。
- 将 Science `10.1126/science.adz3492` 加入 golden fixture，保留真实 SVG 正文图资产，防止 Science/PNAS SVG 图片落盘路径回归。
- 为 Wiley / Science / PNAS 正文抓取增加 FlareSolverr HTML 快速首轮：主 HTML 请求使用 `waitInSeconds=0` 和 `disableMedia=true`，遇到 challenge、访问拦截、摘要重定向或正文抽取不足时自动回退到原保守等待策略。
- 图片恢复、正文/附件资产下载、figure-page HTML 发现继续走允许媒体资源的路径，避免 `disableMedia` 阻断 full-size 图片发现与下载。
- 收敛 HTML availability/container、section hint、browser-workflow Markdown profile、作者 fallback、Crossref resolve 转发和 HTML heading/table helper 的重复实现；canonical owner 分别为 `quality.html_availability`、`extraction.section_hints` / `extraction.html.semantics`、`ProviderBrowserProfile` / `_html_authors.py`、`metadata.crossref`。
- 明确 Science / PNAS / Wiley 共享浏览器抽取为 Atypon-only profile，并把 asset scope、Wiley abbreviations、Wiley author noise、supplementary URL/filename 和 AAAS/PNAS/Wiley datalayer 判定收敛到 provider-owned callback/schema。
- 将 HTML asset canonical owner 移到 `paper_fetch.extraction.html.assets` 包，删除 `paper_fetch.extraction.html._assets` 与 `paper_fetch.providers.html_assets` 兼容门面；下载 hook 现在从 extraction asset 包或 `paper_fetch.extraction.html.assets.download` patch。
- 将 `paper_fetch.models` 物化为包，并按 schema、markdown、tokens、quality、render、sections、builders 拆分实现；`from paper_fetch.models import ...` 继续兼容。
- 将 Science/PNAS browser-workflow HTML 实现物化为 `paper_fetch.providers.science_pnas` 包，删除 `paper_fetch.providers._science_pnas_html` 兼容门面，并抽出 provider HTML asset policy engine 与 Playwright document fetcher 基类。

## 1.0.0 - 2026-04-26

### 变更

- 将包发布为 `1.0.0`，并更新默认 `paper-fetch-skill/1.0` User-Agent。
- 加固 Wiley / Science / PNAS seeded Playwright 图片抓取，使 Cloudflare challenge page 和非图片响应快速失败，而不是阻塞 live review。
- 调整 Wiley 全文 waterfall 顺序：当本地浏览器运行时就绪时，browser PDF/ePDF fallback 现在先于可选 TDM API PDF lane 执行，使 `wiley_browser` 保持为默认成功 route。
- 将 `code_availability` 新增为一等 section kind。Elsevier、Springer / Nature、Wiley、Science 和 PNAS 现在共享 data/code/software availability 分类，在最终 Markdown/ArticleModel 输出中保留这些 section，并将其排除在 body sufficiency metric 之外。

### 文档

- 在 FlareSolverr workflow notes 中记录 seeded Playwright image fetch 的短超时行为。
- 记录统一 data/code availability 保留规则和 quality-metric 排除规则。

### 验证

- `PYTHONPATH=src python3 -m pytest tests/unit/test_provider_request_options.py`
- `PYTHONPATH=src python3 -m pytest tests/unit/test_science_pnas_provider.py -k 'download_related_assets or image'`
- Live smoke：Wiley `10.1111/gcb.16414`、Science `10.1126/science.ady3136` 和 PNAS `10.1073/pnas.2406303121` 使用 WSLg FlareSolverr preset 产出带 full-size body image 的全文 Markdown。

## 2026-04-25

### 变更

- 将 Wiley / Science / PNAS browser workflow runtime 提升到 [`src/paper_fetch/providers/browser_workflow.py`](src/paper_fetch/providers/browser_workflow.py)。Science、PNAS 和 Wiley 现在声明 `ProviderBrowserProfile` object，用于 URL candidate、Markdown extraction、author fallback、public source、label 和 browser asset behavior；`_science_pnas.py` 保持 compatibility alias。
- 将 Wiley / Science / PNAS HTML asset downloader 提升为共享 Playwright primary path。Figure、table 和 formula image candidate 现在每次下载尝试复用一个 seeded browser context，而不是先尝试 direct HTTP。
- 保持 full-size/original candidate 优先于 preview candidate，但现在两个层级都通过同一个共享 browser context 抓取。目标 provider 下载报告 `download_tier="full_size"` 或 `download_tier="preview"`，而不是 `playwright_canvas_fallback`。
- 收紧 browser-workflow image recovery path：重复的 figure-page / image-candidate URL 会按 attempt 缓存，body-image payload download 现在使用固定受限并发并保持稳定输出顺序，当 `solution.imagePayload` 缺失或无效时 FlareSolverr recovery 不再回退到 screenshot cropping。
- 保留 FlareSolverr seed refresh retry 来处理部分资产失败，同时保持非目标 provider（如 Springer）的 generic HTTP-first asset downloader 不变。
- 扩展 HTML formula handling，使 Wiley、Science / PNAS shared HTML 和 Springer / Nature 路径在可能时保留 MathML，并在 MathML 缺失或不可用时保留 formula image fallback 为 `![Formula](...)` asset。
- 在 asset-link rewrite 后 normalize 最终 Markdown，使下载的 figure / table / formula link 在 section parsing 前替换 remote URL，block image 与相邻 heading/text/math fence 分隔，空 body parent heading 仍保持可见。
- 加固结构化 metadata 和 references：front matter 会 unescape HTML entity，Elsevier XML reference 不再跳过稀疏 bibliography entry，Wiley / Springer-style HTML reference 会移除 link chrome，并优先使用可见 citation text 而不是 DOI-only snippet。
- 收紧 Springer / Nature HTML cleanup，移除更多 article chrome 和 license section，保留 main body 之外的 scientific back matter，抽取 formula image asset，并在 table-page parsing 失败时输出显式 table-body-unavailable placeholder。
- 调整 golden-criteria live issue 分类，使 formula-only preview fallback 不被视为 asset-download failure；非 formula preview fallback 除非明确接受，否则仍视为 asset issue。

### 文档

- 更新 README、provider、FlareSolverr、extraction-rule、deployment、architecture 和 schema notes，说明共享 Playwright primary asset path、formula image preservation、Markdown asset-link rewrite、reference fallback behavior，以及目标 provider 的 `download_tier` 语义。

### 验证

- `pytest tests/unit/test_science_pnas_provider.py tests/unit/test_provider_waterfalls.py tests/unit/test_provider_request_options.py tests/unit/test_html_shared_helpers.py -q`
- `pytest tests/unit/test_elsevier_markdown.py tests/unit/test_golden_criteria_live.py tests/unit/test_models_render.py tests/unit/test_science_pnas_markdown.py tests/unit/test_springer_html_regressions.py -q`
- Live smoke：Wiley `10.1111/gcb.16455` 下载 5/5 full-size body figure，Science `10.1126/science.ady3136` 下载 6/6 full-size body figure，PNAS `10.1073/pnas.2406303121` 下载 4/4 full-size body figure；所有本地文件都有 image magic bytes、dimensions，且 Markdown link 已重写到本地路径。

## 2026-04-19

### 变更

- 将共享 HTML full-text diagnostics 移入 [`src/paper_fetch/providers/_html_availability.py`](src/paper_fetch/providers/_html_availability.py)，并切换 `html_generic`、`elsevier`、`springer`、FlareSolverr 和 PDF fallback helper，使其直接 import 共享 availability/access-signal layer，而不是经由 `_science_pnas_html.py`。
- 在 [`src/paper_fetch/providers/_science_pnas_profiles.py`](src/paper_fetch/providers/_science_pnas_profiles.py) 中新增内部 `PublisherProfile` plumbing，使 browser-workflow candidate builder、noise-profile selection 和 provider-specific postprocess hook 位于 `_science_pnas_html.py` 之外。
- 移除 `_article_markdown_document.py` compatibility wrapper；direct Elsevier document assembly 现在只位于 [`src/paper_fetch/providers/_article_markdown_elsevier_document.py`](src/paper_fetch/providers/_article_markdown_elsevier_document.py)，而 [`src/paper_fetch/providers/_article_markdown.py`](src/paper_fetch/providers/_article_markdown.py) 仍是有意保留的 aggregate entrypoint。
- 将过大的 `tests/unit/test_science_pnas_html.py` coverage 拆分为聚焦 candidate、availability、markdown 和 postprocess 的测试文件，同时保留 `tests/unit/test_html_access_signals.py` 中的 `detect_html_block()` coverage。
- 将 geography report/export/group 脚本及其 supporting module 和测试提升为 tracked repo-local internal tooling，不新增 CLI install surface 或 MCP tool。

### 文档

- 更新 README、provider docs 和 backlog notes，说明 geography report/export/group 是 `PAPER_FETCH_RUN_LIVE=1` 之后的 live-only internal tooling。

### 验证

- `pytest tests/unit/test_science_pnas_candidates.py tests/unit/test_html_availability.py tests/unit/test_science_pnas_markdown.py tests/unit/test_science_pnas_postprocess.py tests/unit/test_html_access_signals.py tests/unit/test_elsevier_markdown.py -q`
- `pytest tests/unit/test_geography_live.py tests/unit/test_geography_issue_artifacts.py -q`
- `python3 scripts/run_geography_live_report.py --help`
- `python3 scripts/export_geography_issue_artifacts.py --help`
- `python3 scripts/group_geography_issue_artifacts.py --help`

## 2026-04-16

### 新增

- 新增公开 `provider_status()` MCP tool，可在不探测远端 publisher API 的情况下报告 `crossref`、`elsevier`、`springer`、`wiley`、`science` 和 `pnas` 的稳定本地诊断。
- 新增 provider-level status probing，提供稳定的 `ready` / `partial` / `not_configured` / `rate_limited` / `error` 语义，以及每个 provider 的 `checks=[...]` details。
- 新增 MCP `resources/list_changed` 支持：当 `fetch_paper()`、`list_cached()` 或 `get_cached()` 改变当前 session 可见 cache-resource URI set 时，对 cache resource 发出通知。

### 变更

- 变更全部 8 个公开 MCP tool，使其暴露 `ToolAnnotations`；read-only tool 现在声明 `readOnlyHint=true`，而 `fetch_paper` 因可能刷新本地 cache 文件仍保持 writable。
- 修改 Science / PNAS local diagnostics，使 MCP 可在不修改 rate-limit tracking file 的情况下检查 FlareSolverr runtime readiness 和本地 rate-limit window。
- 修改 `batch_resolve()` 和 `batch_check()`，当请求超过 `50` 个 query 时直接拒绝，而不是尝试执行超大 batch run。
- 修改 MCP initialization，使 server 在支持的 transport 上声明 `capabilities.resources.listChanged=true`。

### 文档

- 更新 README、deployment docs、provider docs 和内置 skill guide，记录 `provider_status()` 与新的 MCP tool-annotation hint。
- 更新 README、deployment docs 和内置 skill guide，记录 `50` query batch limit 和新的 cache-resource list-change notification。

## 2026-04-15

### 新增

- 新增专用 `has_fulltext(query)` MCP probe tool，使用低成本 Crossref、provider-metadata 和 landing-page HTML-meta signal。
- 为全部 7 个公开 MCP tool 新增 JSON output schema，使 schema-aware client 可以校验 tool result 并提供更强 autocomplete。
- 新增 `fetch_paper(..., prefer_cache=true)` cache-first short-circuit，由 MCP-local cached FetchEnvelope sidecar 支持。
- 当可识别缺失 credential 或必需 environment variable 时，在 MCP error payload 上新增 `missing_env=[...]`。
- 新增两个 MCP prompt template：`summarize_paper(query, focus)` 和 `verify_citation_list(citations, mode)`，分别用于 cache-first paper summary 和 batch-first citation-list triage。
- 在 `fetch_paper` result、`article.quality` 和 `batch_check(mode="article")` item payload 中新增 `token_estimate_breakdown={abstract,body,refs}`。

### 变更

- 修改 `batch_check(mode="metadata")`，复用低成本 probe path，而不是运行完整 fetch waterfall。
- 修改内置 skill layout，变为薄 `SKILL.md` entrypoint 加 `references/` 文档，用于环境变量、CLI fallback 和 failure handling。
- 修改 `batch_resolve` 和 `batch_check`，接受可选 `concurrency`，允许跨 host overlap，同时共享 HTTP transport 仍序列化同 host request。
- 修改长时间运行的 MCP `fetch_paper` 和 `batch_*` tool call，使其协作式观察 cancellation，已取消请求会停止后续网络工作。
- 修改 MCP cache resource，使显式非默认 `download_dir` 也会为当前 server session 注册 scoped cache-index 和 cached-entry resource。
- 修改 MCP `fetch_paper.strategy`，接受可选 `inline_image_budget` 控制 inline `ImageContent` 上限，同时不改变 service-layer fetch 行为或 cache eligibility。
- 修改 `token_estimate` 语义，使其作为 `abstract + body` 保持向后兼容；新的 `refs` budget 只存在于 `token_estimate_breakdown`。
- 修改 MCP cached FetchEnvelope sidecar 加载逻辑，使读取早于新 contract 的旧 cache entry 时回填缺失 token-breakdown 字段。

### 文档

- 更新 README、deployment docs、skill guide 和 probe-semantics note，记录已发布的 `has_fulltext` v1 行为和新的 `batch_check(mode="metadata")` 语义。
- 更新 static skill installer 和 architecture docs，将 `skills/paper-fetch-skill/` 视为 runtime-agnostic bundle，可包含按需 `references/` 文件。
- 更新 MCP-facing docs，说明新的 `concurrency` 参数，以及 `batch_*` 的“cross-host concurrent, same-host serial”行为。
- 更新 MCP-facing docs 和 skill notes，说明 `fetch_paper` 与 `batch_*` 的 cooperative cancellation。
- 更新 README、deployment docs 和 MCP instruction text，记录显式 isolated download directory 的 scoped cache resource。
- 更新 README、deployment docs、skill notes 和 MCP instruction text，记录 `strategy.inline_image_budget` 及其默认 `3 / 2 MiB / 8 MiB` inline-image cap。
- 更新 README、deployment docs 和内置 skill guide，记录两个已发布 MCP prompt 和新的 `token_estimate_breakdown` budgeting hint。

## 2026-04-14

### 新增

- 新增公开 `science` 和 `pnas` provider route，包括 direct `provider_hint`、`preferred_providers` 和最终 `source` 支持。
- 新增 repo-local Science / PNAS provider 实现，位于 [`src/paper_fetch/providers/science.py`](src/paper_fetch/providers/science.py) 和 [`src/paper_fetch/providers/pnas.py`](src/paper_fetch/providers/pnas.py)，由共享 FlareSolverr、HTML cleanup 和 Playwright PDF-fallback helper 支持。
- 新增 repo-local `vendor/flaresolverr/` workflow asset、[`scripts/`](scripts) 下的薄 wrapper script，以及 [`docs/flaresolverr.md`](docs/flaresolverr.md) 中的专用 operator guide。
- 新增离线 Science / PNAS fixture，并增加 routing、FlareSolverr error handling、provider fallback 和 public result provenance 的 unit coverage。
- 在现有 `PAPER_FETCH_RUN_LIVE=1` gate 后新增一个 Science HTML DOI 和一个 PNAS PDF-fallback DOI 的 opt-in live smoke 覆盖。

### 变更

- 扩展 `SourceKind` 和 service provider registry，使 `science` 与 `pnas` 成为一等 public provenance value，而不是仅 envelope-only alias。
- 使 Science / PNAS 使用 provider-managed `HTML first -> PDF fallback -> metadata-only fallback` 链，并在选择这些 provider 后显式跳过 generic `html_generic` fallback。
- 将 Science / PNAS HTML extraction 移到 provider-specific cleanup rule，然后把清理后的 HTML 送回现有 HTML-to-Markdown pipeline 做最终渲染。
- 在 Science / PNAS 全文检索继续前，新增对 `vendor/flaresolverr`、`FLARESOLVERR_ENV_FILE`、本地 FlareSolverr health 和必需 local rate-limit setting 的显式 repo-local runtime check。
- 在 user data directory 中新增本地 Science / PNAS rate-limit accounting，并让这些 route 上的 `asset_profile=body|all` 以带 warning 的 text-only downgrade 处理，而不是 hard failure。
- 扩展 `install-formula-tools.sh`，使 repo-local development 可以通过一个入口 bootstrap FlareSolverr source setup、Playwright Chromium 和 headless `Xvfb` prerequisite。

### 文档

- 更新 README、deployment guidance、provider docs、MCP instruction snippet 和 FlareSolverr workflow docs，说明新的 Science / PNAS route、repo-local-only support boundary、必需 environment variable 和 operator-owned ToS risk。

### 验证

- `python3 -m compileall src/paper_fetch`
- `ruff check src/paper_fetch tests/unit`
- `PYTHONPATH=src python3 -m unittest -q tests.unit.test_publisher_identity tests.unit.test_resolve_query tests.unit.test_science_pnas_html tests.unit.test_science_pnas_flaresolverr tests.unit.test_science_pnas_provider tests.unit.test_service`

## 2026-04-13

### 新增

- 新增 MCP cache indexing，提供 `list_cached()` / `get_cached()`，以及默认共享下载目录的 `resource://paper-fetch/cache-index` 和 `resource://paper-fetch/cached/{entry_id}` resource。
- 新增 `batch_resolve(queries)` 和 `batch_check(queries, mode)` MCP tool，使 citation-list workflow 可以保持串行、复用 transport 且节省 context。
- 在 [`src/paper_fetch/mcp/_instructions.py`](src/paper_fetch/mcp/_instructions.py) 中新增 canonical MCP/skill-facing instruction helper，用于对齐默认值、环境说明和 error-contract wording。
- 当 `strategy.asset_profile` 为 `body` 或 `all` 时，为少量本地 body figure 新增 inline `ImageContent` 支持。
- 为 `fetch_paper`、`batch_check` 和 `batch_resolve` 新增结构化 MCP progress update 和 structured log notification。
- 新增代表性 Elsevier 和 HTML-fallback flow 的 live MCP end-to-end smoke 覆盖。
- 在 [`docs/architecture/probe-semantics.md`](docs/architecture/probe-semantics.md) 中新增 probe-semantics design note，用于定义未来 `has_fulltext(query)` 方向。

### 变更

- 将 public change history 和 shipped-surface notes 从临时 backlog docs 移入此 changelog。
- 在 MCP `fetch_paper` surface 暴露 `download_dir`，使 task-local directory 可覆盖 `PAPER_FETCH_DOWNLOAD_DIR` 和 XDG 默认值。
- 扩展 MCP `resolve_paper`，使其接受 raw `query` 或结构化 `title` 加可选 `authors` / `year`。
- 更新 static skill，记录真实默认值、影响行为的 environment variable、error contract、cache-first call discipline 和 batch-first bibliography workflow。
- 澄清 `include_refs=null` 在 `max_tokens="full_text"` 时表现为 `all`，在 numeric token budget 时表现为 `top10`。
- 将 skill frontmatter 重写为更短的 trigger-style description，并把 call-discipline guidance 前移到 main workflow 之前。
- 将 provider routing 转向 Crossref/domain-first hint，只有必要时才使用 DOI-prefix fallback，并向 `source_trail` 添加 route diagnostic。
- 围绕共享 utility 统一 text-normalization、DOI extraction、metadata merge helper 和 HTML lookup heuristic，减少重复逻辑。
- 将大型 renderer 和 HTML module 拆分为由聚焦 helper 支撑的更薄 facade，同时保留 public compatibility entrypoint。
- 优化 CLI exit code、Markdown asset-link handling、render budgeting 和 token-estimation 内部实现，不改变 public fetch contract。

### 修复

- 使用 `threading.RLock` 保护 in-process HTTP GET cache。
- 将 HTTP transport 切换到 `urllib3.PoolManager`，以复用连接，同时不改变 public request contract。
- 新增 response-size guard、gzip pre-decompression size check、cache-budget eviction，以及 timeout/transient error 的更安全 retry 行为。
- 将 payload 和 asset 写入改为 atomic `.part -> replace` 流程，避免失败写入破坏最终文件。
- 收紧异常处理，使 programming error 不再被静默降级成 partial-download 或 fallback path。
- 通过强制 `download_dir=None` 防止 `batch_check()` 将 payload 写入磁盘。
- 即使未请求 `article`、`markdown` 或 `metadata`，导致其返回为 `null`，仍保留 top-level fetch provenance field。

### 文档

- 将 architecture rationale 保留在 [`docs/architecture/overview.md`](docs/architecture/overview.md)，并把已发布变更移到本文件。
- 更新 deployment、provider、MCP 和 skill-facing documentation，使其匹配已经落地的 MCP surface 和 environment behavior。

### 验证

- `ruff check .`
- `PYTHONPATH=src python3 -m pytest tests/unit tests/integration -q`
- `PYTHONPATH=src python3 -m pytest -n 0 tests/live/test_live_mcp.py -q` 在 live env 未启用时会 clean skip；这里需要 `-n 0`，因为 live MCP 共享外部 publisher/API state 和 secrets。

### 后续

- 专用 MCP probe tool `has_fulltext(query)` 尚未发布；本次只落地了 [`docs/architecture/probe-semantics.md`](docs/architecture/probe-semantics.md) 中的语义说明。
