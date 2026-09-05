# 更新日志

本文件是 [`CHANGELOG.md`](CHANGELOG.md) 的中文对照版，记录 `paper-fetch-skill` 所有值得关注的公共变更。

## 未发布

<!-- SCAFFOLD: changelog-unreleased -->

### 修复——出版社浏览器与资产获取

- AIP 直接使用正常 HTML attempt，取消媒体拦截及 Adzerk/Crossmark 空脚本响应，保留现有非持久会话和正文 readiness 检查。
- IEEE 原图恢复现在复用浏览器会话中匹配的文章链接：图片通过站内查看器获取，表格图片链接通过临时浏览器标签获取。恢复过程验证原始响应字节，保留逐资产失败报告和预览降级。
- Springer/Nature 优先下载已知原图候选，仅在需要时请求图页；延后发现仍在同一次资产解析和预算内完成，保留表格页面补齐和预览降级来源。
- Science 最终页面现在采用当前候选中 URL、DOI 匹配的最新已完成主框架导航响应，避免初始拒绝响应覆盖随后成功加载的文章；iframe 和无关响应不能替换文章状态。
- PNAS 仅拦截精确匹配的侧栏统计接口，并记录 `blocked_sidebar_metrics_count`。三组冷会话对照未证明稳定提速，浏览器页面处理仍是性能限制；文档记录的 PMC 无浏览器实验尚未接入获取流程。

## 6.1.3 - 2026-09-04

### 变更——provider 与 browser 所有权

- 文章来源 provenance 现在读取 catalog 中各 route 显式声明的 source：优先按精确 route name 选择，并兼容只携带 route kind 的 PDF recovery payload。ACS、Science、PNAS 的通用 source 与 Wiley 共用的 browser source 保持不变。
- Browser landing page、provider 与资产 URL 检查统一复用 catalog hostname matcher，同时保留 provider domain、route host、候选构造集合及 MDPI/Frontiers 精确网络边界的不同语义。
- 删除 AMS/MDPI HTML compatibility facade、Springer 专用引用再导出、15 个无人消费的 browser-workflow 根私有导出、旧 Playwright 命名 PDF alias，以及两个未使用的 fast-browser wrapper。保留的 Springer facade 现在是静态兼容导出，调用时不再改写 canonical extraction 模块。
- 删除未使用的即时 `browser_runtime.save_storage_state` facade 及其 backend/path 转发链。Browser fetch 与 preflight 仍会先暂存 provider 范围内的状态，并且只在验收通过后原子提交。

### 变更——schema 与仓库维护

- MCP request schema 现在让 fetch、batch、cache 与 browser-preflight 路径字段复用同一个精确 optional-string 规范化 helper；路径值仍只去除首尾空白。同时删除 article-source rendering 中返回值相同的无效分支。
- 删除 240 个已跟踪的一次性 live 调查产物。维护者 live 验证改写到被忽略的 `failures/` scope；长期仓外保留只需 JUnit 与 `live-acceptance.json`，IEEE 受保护资产专项再保留 `asset-hashes.json`。

## 6.1.2 - 2026-09-03

### 修复——资产完整性与 provider 分页

- 普通 provider 抓取不再默认限制最多 128 个资产；单文件、累计字节、像素和 worker 上限继续生效，arXiv source archive 仍保留独立的 128 个 regular member 遍历门禁。显式有限文件预算继续执行；致命预算终止现在会为每个已准入但未完成的资产返回带 timing 的失败；普通流式图片只有在载荷实际为 EPS 或 TIFF 时才预留转换输出名额。
- IEEE references 现在可以继续抓取超过 20 页，并在达到已声明数量、遇到空页、短页、重复页或总 wall-clock deadline 时停止；landing page 声明存在 references 但未给出数量时也会抓取。
- Taylor & Francis 动态 CSV 表格和同页内嵌表格现在按每批 24 张持续 hydration，直到处理完全部已发现表格或页面 deadline 到期。deadline 截断会报告未完成表格数，离线 replay 也会恢复全部符合边界的同页表格 payload。
- 异步 MCP 抓取在成功、provider 失败和协作取消路径中，都会由 owner worker 线程关闭各自的 Camoufox manager。
- 文章渲染现在会把带 HTML 强调标记的 metadata 标题与 Markdown 强调形式的开头标题识别为等价，避免重复文章标题。
- 离线包验证的 DOI smoke test 现在使用受支持的 `paper-fetch fetch` 子命令。

## 6.1.1 - 2026-09-02

### 修复——ACS 资产与 AIP 浏览器稳定性

- ACS HTML 提取现在会在资产发现前从原始 Silverchair 正文恢复出版社的图片下载链接，并按资产身份去重；清理后的正文省略这些链接时仍可保留官方图片 rendition。
- AIP 浏览器尝试现在只对精确匹配的 Adzerk 与 Crossmark widget 脚本 URL 返回空 JavaScript；其它 URL 和资源类型继续正常加载，fulfill 失败时安全放行，避免第三方 TLS 间歇停滞阻塞正文就绪或产生 `insufficient_body`。

## 6.1.0 - 2026-09-02

### 修复——审计一致性

- 批量 MCP 抓取现在与单篇抓取一致地规范化可选字符串；仅含空白的共享 Markdown 文件名视为未指定，manifest 记录的也是规范化后的请求。
- 异步内联图片抓取只在复现所请求图片确有需要时把已有 article 字段保留到内部缓存；旧的不完整 sidecar 会安全 miss，公开 structured content 仍隐藏未请求的 article。
- Provider 资源 hook 对正文的更新现在会一致传播到 article 构建、workflow 落盘、acquisition 和 provider 返回正文。
- 删除未使用的 KaTeX 运行时依赖及安装检查；打包的 Node workspace 只保留 MathML→LaTeX 转换器及其传递依赖，同时维持 KaTeX 兼容的规范化目标。
- 使 CLI、MCP、浏览器、cache、provider、部署、macOS 与提取文档重新符合仍然存在的能力和契约。

### 破坏性变更——命令、MCP、批处理与 manifest 接口

- CLI 现在只支持子命令形式：请使用 `paper-fetch fetch ...`。删除根级 fetch 参数兼容层、CLI `--no-download`、持久化 `--run-manifest` / `--resume` 以及 `manifest audit|reconcile` 命令；不保留 provider artifact 与资产时改用 `--artifact-mode none`。
- CLI 与 MCP 批处理可以写入一份最终 `batch-results.jsonl`；只有全部输入取得终态后，才按输入顺序组装并原子提交。删除 append-only attempt、run summary、audit/reconcile 与 resume 语义，同时保留单批次内按 canonical DOI fan-out。目标结果文件已存在且内容不同时，仍需显式传入 `--overwrite` / `overwrite=true`。
- Schema-v2 manifest record 现在只公开当前 `record_status`、`acceptance` 与 `output_artifacts` 契约。删除旧顶层 `status`、`output_path`、`saved_markdown_path` projection 以及旧 acceptance/cache 迁移 shim；旧版、未知或不完整记录不再猜测或升级，而是 fail closed。
- 删除 `summarize_paper` 与 `verify_citation_list` MCP prompt 模板。Fetch、resolve、check、cache tools，静态 provider-catalog resource 以及 schema-v2 payload 契约均保持不变。

### 变更——浏览器与 transport 运行时

- Camoufox 现在是唯一 browser backend。删除 backend selector、通用 Chrome/CDP runtime 路径、浏览器自动安装/修复/更新，以及 CLI/MCP/环境中的 `browser_auto_prepare` 控制。Fetch、auth 与 preflight 只使用已经准备好的 runtime；需要安装时显式运行 `python -m camoufox fetch`。
- Browser preflight 不再向后续 fetch 发布短期 HTML 或 route hint。每次 fetch 都独立导航，并重新执行 identity、access boundary、正文与资产验收；storage state 仍是有意保留的可复用浏览器能力。
- 删除基于 `download_dir` 的 HTTP 文本磁盘缓存、条件式磁盘 revalidation、cache stat/timing collector 及其环境变量。HTTP GET 现在只在当前进程内有界复用，request safety、redirect 检查、retry policy 与资产限制继续执行。

### 变更——MCP cache 访问

- 删除动态 cache index/entry resource、cache resource-list notification 与 `batch_fetch` cache `resource_uri` 字段。Cache 访问现在通过显式 `download_dir` scope 内的 `list_cached` / `get_cached` 完成；静态 provider catalog resource 继续保留。
- 删除 cache `refresh` / `rescan` 模式与 loose-file discovery。Sidecar、Markdown 和资产在写入时增量注册；读取只信任当前 scoped index 以及当前 DOI、capability scope、stat 与 hash 证据，不再静默迁移旧版或损坏的 index。

### 变更——provider 与库契约

- 内置 provider 现在从一份固定且经过验证的 bundle 列表加载。删除动态注册、依赖 import order 的优先级、identity overlap priority、route-union 编译以及生成式 provider catalog/route governance 层；运行时网络策略只从精确声明的 route 编译。
- 删除仅用于兼容的 positional constructor、宽泛 keyword adapter、旧 urllib asset request 注入、通用 browser/PDF launch 参数、跨请求 singleflight 与其它私有 wrapper import。当前 typed request/options object 与单批次 DOI 去重仍是支持路径。

### 变更——维护工具与验证

- 用更小的 `docs/adding-a-provider.md` 流程取代 manifest/review/scaffold onboarding tree：定义 runtime bundle，添加 provider-local test，并加入代表性 golden replay 证据。删除 provider governance/drift/canary generator、递归 onboarding 自动化、Markdown review sidecar、live benchmark tooling 与生成式 route 文档。
- 删除仓库 coverage-focus、complexity-budget gate 与打包的 `paper_fetch_devtools` 质量层。确定性的 unit、integration、provider replay、package、platform 与 live-test 入口继续保留在各自范围内。
- 将静态 Skill 完整性验证从 runtime package 移至 `scripts/skill_integrity.py`。离线 builder/installer 直接验证 bundle 与已安装的宿主副本；`doctor` 现在只报告 runtime/provider 健康状态，不再接受 `--install-root` 或输出 installation-provenance 状态。

### 变更——发布与依赖 CI

- 删除可变的 `dependency-latest` 滚动发布、专用 token 路径和跨 revision release tooling overlay。稳定 `v*` 发布继续公开九个离线安装器与 `SHA256SUMS`，并保留冻结依赖证据、SBOM、secret scan 和 provenance attestation。
- 删除不 gate 的 provider canary 状态机；经合法授权的显式检查继续保留在 `tests/live`。
- 锁定依赖审计现在导出全部 extras，并让每个 `pip-audit` finding 直接失败，不再保留空的例外框架。
- Python 3.11 与 3.14 boundary job 现在每个 Python 版本只构建一次 wheel，并分别 smoke 隔离的 core/full 安装。
- Python distribution verification 现在检查 archive safety、必需 package/Skill payload、metadata、entry point 与完整 wheel `RECORD` 覆盖，不再维护签入仓库的精确源码 inventory。删除仓库根目录的旧 Windows PowerShell bundle installer；受支持的 Windows release artifact 仍是原生 setup executable。

## 6.0.4 - 2026-08-29

### 修复——发布质量门禁

- 将 XML tail 空白处理从共用行内渲染器中提取，保持 6.0.3 行为不变，同时使渲染器回到仓库复杂度预算内；并对 JATS 回归测试应用规范格式。
- 为 6.0.4 重新生成机器可读 provider catalog，使其 tool-version 快照与项目元数据一致，并恢复 provider governance 同步。

## 6.0.3 - 2026-08-29

### 修复——XML 行内空白渲染

- Elsevier/JATS 共用的行内转换器现在会在组装 Markdown 前折叠出版社 XML 中仅用于源码排版的空白。运算符和强调标记附近的源码折行不再造成错误强调或意外块级解析，同时显式换行元素与既有的分离斜体下标修复保持原有行为。
- 含嵌入块的 JATS 段落同步应用相同空白规则。回归测试覆盖本次报告的 Elsevier `=`、`<` 案例以及真实 Frontiers、Copernicus XML；PLOS 共用修复后的 JATS 转换路径。

## 6.0.2 - 2026-08-29

### 修复——Frontiers 原图与滚动发布

- Frontiers 正文图和公式图片现在会从 canonical landing page 发现并优先使用出版社提供的精确 `xml-images` 原图 URL。按 graphic stem 匹配可保持已下载全尺寸资产与渲染后的 Markdown 一致，并避免根据 DOI 后缀推导出错误的文章目录 URL。
- 滚动依赖发布的 `publish` job 现在会先 checkout 触发 workflow 的 commit，再调用仓库内的发布脚本。该 checkout 使用固定 action、浅克隆且不持久化凭证，避免 `prepare_release_assets.py` 因 `Errno 2` 失败；结构化 workflow 契约会持续保护执行顺序和信任边界。

## 6.0.1 - 2026-08-28

### 修复——发布流程

- 稳定版发布现在直接使用已验证的远端 tag，不再把对应 commit 重复作为 `target_commitish` 传入；即使不可变 tag 构建期间默认分支继续前进，也不会触发 GitHub 的 workflow 权限拒绝。
- 应用规范 formatter，同步移除无差异 `--ci` 模式后的抽取规则验证命令，并从受跟踪的发布源码中删除本地问题审计文件。

## 6.0.0 - 2026-08-28

### 变更——显式 capability 与更小的公开面

- Provider route 现在是 capability 唯一事实源。删除 provider 顶层 browser flag、自动 route 合成、源码树发现和动态 registry monkeypatch；内置 provider 由一份显式且保持 lazy import 的模块清单加载。
- MCP 工具继续返回既有 `CallToolResult.structured_content` 成功/错误 payload，但 `tools/list` 不再发布 `outputSchema`。Browser capability 与 preflight 状态直接从运行时 owner 派生，未知 preflight 状态 fail closed。
- 删除 `RawFulltextPayload.metadata`、`build_provider_registry`、无消费者 provider wrapper，以及未接线的 direct-HTTP/browser link helper；这些破坏性删除不提供弃用 facade。

### 变更——仓库工具与发布

- 删除递归 onboarding agent 编排、私有 DAG/state/retry 机制、evidence sidecar、geography 专用 live/report 工具，以及生产 wheel 中的 Markdown review/quality 诊断。仓库继续保留确定性的 review bootstrap/finalize 和 golden fixture manifest 流程。
- Stable Release 精确公开九个安装包与 `SHA256SUMS`；Rolling prerelease 额外公开 `dependency-manifest.json`。Wheel、sdist、inventory、SBOM 与逐目标 evidence 仍作为构建期验证输入。
- 用从项目元数据、workflow、installer manifest 和 release asset owner 派生事实的精简合同，替换历史 macOS ledger。

不兼容 import 与协议变化见 [docs/migration-v6.md](docs/migration-v6.md)。

## 5.6.1 - 2026-08-27

### 修复——Windows 发布 lifecycle

- 修复 Inno Setup 两阶段卸载导致的原生 Windows release 失败：首阶段进程返回时，TEMP 中的第二阶段仍可能占用 `unins000.exe`，覆盖升级于是生成 `unins001.exe`，最终残留检查又与延迟清理发生竞态。
- 用官方 UninsIS 1.7.0 替换安装器侧自行维护的注册表与命令行解析，并固定 release archive、DLL 和许可证摘要。Windows builder 会在 Inno 编译前校验这些文件，并把 setup-time 组件写入 offline manifest、依赖证据与 CycloneDX SBOM。升级现在会 fail closed，直到旧卸载器完成并删除原 EXE，同时继续保留 `offline.env` 与其它用户内容；LGPL 许可证和 provenance notice 随安装器分发。
- 加强原生 lifecycle gate：覆盖升级后必须精确只有一个 `unins000.exe`；最终卸载后最多等待 60 秒，只有同时观察到 Inno 成功日志标记且全部 `unins*.exe/.dat/.msg` 消失，才执行精确卸载残留 allowlist 检查。

## 5.6.0 - 2026-08-27

### 修复——技能完整性、可复现测试与复杂度债务

- 基于精确排序的普通文件清单，为静态 skill bundle 生成稳定的聚合 SHA-256/版本，实现内容寻址。源码、staging、离线 manifest 与宿主机已安装副本现在使用同一 verifier 拒绝缺失、多余、已更改、符号链接及特殊条目；规范的 `agents/openai.yaml` 改为随源码分发，不再因重新生成而形成永久漂移。
- 为 Codex/Claude/Antigravity 共用安装器新增严格只读的 `--check` 模式，并正确查找 Codex 用户/项目作用域。源码与离线 `doctor` 诊断现在会对比仓库/随包 skill 和当前启用的 Codex 副本，公开预期/实际内容版本，并在启用的 skill 缺失或漂移时令整体 readiness 失败。
- 在仓库指引、生成的 onboarding 与 CI 中，将常规测试命令统一为 `PYTHONPATH=src uv run python -m pytest ...`。当环境中的 MCP 主版本或必需的 trafilatura API 行为不兼容时，Pytest 现在会在 collection 前失败，并给出可直接执行的冻结 `uv` 修复命令；Python boundary controller 安装这套完整测试契约，而全新隔离 venv 仍分别证明 core 与 full wheel。
- 通过归组既有 request/runtime state 并抽取保持行为不变的 browser、PDF、asset、HTTP stream、cache 与 MCP batch helper，在不放宽 threshold、ignore 或 suppression 的情况下消除全部 24 个复杂度回归。历史超预算清单从 55 个 symbol 单调降至 47 个，其中 Playwright C901 从 44 降至 40。

### 修复——经验证的构建与发布供应链

- 将 Python wheel/sdist 构建拆到只接受不可变完整 SHA 的 reusable `package.yml`，保留精确 inventory、wheel/sdist 独立安装 smoke、密钥扫描和 artifact 上传。普通 CI 继续运行完整 unit/coverage/quality/integration/golden/平台门禁，Dependency refresh 继续运行完整 unit；Stable release 则只构建发布产物：Python package 与九目标冻结依赖解析并行，随后 offline installer 验证、Windows lifecycle、SBOM、checksum、attestation 和发布全部消费同一 tagged SHA。Release 不运行、也不等待远程 unit/普通 CI；下一版本和不可变新标签创建前，仍以本地完整 unit 命令作为发布操作者门禁。
- 所有 workflow artifact 扫描现在都会显式选择该扫描步骤注入的凭据。真实 workflow token 的 raw 与 URL 编码检查保持不变，同时排除 `PGPASSWORD` 等无关 hosted-runner 默认值，避免其与 Windows 第三方 wheel 中的普通字节偶然匹配并误阻断发布。
- 将完整质量矩阵抽取为一套可复用的 verify workflow，供常规 CI 与稳定版发布共同调用。稳定版 tag（包括 annotated tag）会 peel 到不可变 commit；验证、依赖解析、离线构建、发布 checkout、attestation 与 GitHub Release target 全部使用该精确 SHA，并在发布前执行最终 tag 漂移检查。
- 稳定版发布现在会在同一次 run 中解析并合并全部九个目标的冻结依赖快照：Linux CPython 3.11–3.14、macOS arm64 CPython 3.11–3.14，以及 Windows CPython 3.13；随后以启用冻结依赖的方式调用 offline workflow。
- 新增从实际 staging tree 派生的逐目标证据：已安装 Python distribution 及内容 digest、Node/Playwright package、Camoufox 交付状态、公式/图片/native 文件与嵌入式 runtime provenance。每个离线产物现在都会携带并上传实际 dependency manifest 和经验证的 CycloneDX 1.6 SBOM；release 不再用 lock export 冒充 staged evidence。
- 将原生与发布离线 builder 绑定到仓库锁定虚拟环境（POSIX 使用 `.venv/bin/python`，Windows 使用 `.venv/Scripts/python.exe`），确保 CycloneDX 证据生成器始终复用已验证的开发工具链，不再依赖 runner 全局包。
- 在 installer manifest 与平台合约中，将 Windows CPython 3.13.13 x64 embeddable archive 固定到 python.org 官方 URL 和 SHA-256；解压前会验证，并在 offline manifest 与 SBOM 中记录预期/实际 digest。
- 为完整 archive 新增精确 wheel/sdist inventory。它会从结构上规范化唯一合法的 distribution root/`dist-info`/`egg-info`，要求 metadata 与 wheel `RECORD` 精确覆盖，并拒绝所有未知的 top-level、`.data`、package、source 或 metadata member。两个产物分别安装到独立 venv，并运行 CLI、import、MCP、resource 与已安装 skill smoke。
- 稳定版发布现在会验证 checksum 前精确的 31 个 asset（两个 Python distribution、对应 inventory、九个离线 installer、十八个目标 evidence 文件及 merged dependency manifest），拒绝缺失、多余和 basename collision，将它们复制到平坦且排他的 namespace，并生成只含 basename 的 `SHA256SUMS`。资产与 checksum 文件执行 fsync，而 Windows 等不提供 POSIX directory descriptor 的平台只对目录 fsync 做 best-effort；滚动发布复用同一 offline asset-set checker。
- 正式采用刷新后的兼容依赖图，包括 MCP 2.1.1、imagesize 2.0.1 与 PyMuPDF4LLM 1.28.2。tool payload 测试改为验证实际对外发布的 Draft 2020-12 JSON Schema，不再绑定 SDK 内部生成的 model；cache 授权测试兼容 SDK 包装或直接传播异常，同时继续 fail-closed；合成 PNG fixture 补齐解析器要求的 IHDR 字段，PDF exact golden 快照同步当前结构化提取结果。全部 Python、公式 Node 与 release resolver 依赖声明均使用可滚动的兼容范围，不再精确锁死 package 版本；lockfile 继续保存可复现的实际解析图。
- 新增原生、串行的最终 Windows EXE lifecycle gate：静默安装、已安装 doctor/provider/formula/browser smoke、原地覆盖升级、用户数据保留、静默卸载，以及精确递归 residue allowlist。只允许残留 `offline.env`、`downloads/` 和 `downloads/user-owned.txt`；任何现有或未来的 managed file 都会令 gate 失败。不可变 Windows tooling overlay 现在会把 builder、evidence/lifecycle script、helper、installer manifest 与 Inno definition 作为同一组按 revision 固定的文件移动。

### 安全——网络、凭据与日志边界

- 恢复按 hostname 复用 urllib3 连接池，同时保留既有 `SafeRemoteUrlPolicy` 基线：每个 redirect hop 都检查 HTTP(S)、80/443、公网 DNS、无 userinfo、无 HTTPS downgrade，并在跨源重定向时剥离标准敏感 header。
- Provider catalog 的 host 与 sensitive-header 声明不再自动成为网络授权。调用方显式给出的 `allowed_hosts` 仍按 fail-closed 执行；未请求 allowlist 时，Royal Society、IOP 与 AIP 的公网资产 CDN 使用基础 URL 策略。
- 以标准 cookie jar policy 替换手工 browser-cookie matching，从而保留 host-only/domain、RFC path、secure、expiry、HttpOnly 与 SameSite 作用域。
- 集中处理 human/structured log 中 URL/query/header/text secret 的脱敏，增加防御性 MCP filtering，并用一个引用计数 router 加 context-local request ownership 取代逐请求 global handler。Live 环境映射现在使用不显示值的 repr；所有 CI artifact/release 上传前都必须通过扫描器，扫描原始及 URL 编码 credential sentinel，且只报告变量名和文件路径。Bridge teardown 前会在锁内使 request target 失效，因此持有 context 副本的 worker 无法向已结束的 MCP session 或重叠请求发出消息；closed loop 会在构造 notification coroutine 前被拒绝。

### 修复——能力作用域缓存的正确性与规模

- 新增统一的 `CapabilityScopeBuilder`，仅纳入实际注入成功 context 的 API credential 与 browser state。Browser-backed scope 绑定 provider、backend、规范 storage-state path 与最终文件 digest；配置的空路径保持 public，而实际使用过的 state 绝不会写成 public。旧版仅基于 environment 的 digest 与既有 private sidecar 保持逐字节兼容。
- `prefer_cache` 现在会在本地规范化已知 DOI，并在 resolver/provider enrichment 前检查精确 sidecar。Loader、`get_cached`、compact projection、cache-index listing、entry resource 与生成的 MCP resource 只允许 exact-private-to-public fallback。未变化的 DOI-local artifact 保留其独立证明的 scope，不再继承最新 canonical sidecar；缺失/旧版 provenance 与冲突的 sidecar scope 会 fail closed。每次 resource read 都会重新评估当前 API/storage-state capability 与 file/index integrity，因此撤销 capability 也会撤销已公开的 URI，无需重新同步 resource。
- 将 cache discovery 与 hashing 移出 global index lock，限制 YAML front matter 读取量，持久化 stat/content fingerprint 以复用未变化文件，合并并发 refresh/rescan 更新，并以 incremental upsert 取代写入后的 rescan。对 50 个 DOI 执行批量或顺序刷新时，每个未变化 Markdown 文件最多打开一次。

### 修复——原子提交、取消与批处理身份

- 将 artifact、sidecar、Markdown、cache-index 与 run-summary 的发布统一置于 path-scoped lock、同目录唯一 staging file、flush/fsync、atomic replace 与一个可线性化 runtime commit fence 之后。非 overwrite 写入现在将相同内容视为幂等，并拒绝不同内容；显式 overwrite 允许串行化的原子替换。
- 在每个同步/异步单篇 fetch 与 output stage 中贯穿同一个 runtime context。异步取消现在会封锁 commit、等待有界且独立的 grace period，并阻止迟到 worker 发布 artifact 或 progress；batch item 使用隔离的 child context，并关闭重复或未调度的 child。
- Resolve/check output 现在保持与输入同序同长，包含稳定 index、terminal status/error/provider lane，以及真实的 terminal/not-scheduled progress。Title check 使用解析出的 provider lane，已知 DOI check 使用 local lane identity，避免一个 provider cooldown 阻断无关 lane。
- 为 MCP 与 CLI batch fetch 新增 canonical DOI representative/fan-out execution，并提供跨请求共享的 DOI/request/scope/path singleflight key；waiter 的取消彼此隔离，result/error 也会安全复制。
- 在 resume manifest 中将不可变 run semantics 与可覆盖 execution policy 分离。Concurrency 及 continue/retry/rate policy 可以安全变更，而有序输入、fetch/render/output semantics 与 tool version 保持固定；旧版内嵌 execution field 会在验证后迁移。

### 修复——有界二进制资产与浏览器会话复用

- 新增线程安全的逐文章 `AssetBudget`，由正文图、补充文件、direct/browser discovery、arXiv source decoding 与 image conversion 共享。默认最多保留 128 个文件、单文件 32 MiB、总计 256 MiB、6400 万像素和 4 个 worker，worker 数还会进一步受 route 限制。
- 恢复 browser-owned image/file/PDF bytes，包括 `response.body()`、`arrayBuffer()`、`bodyB64`、canvas 与浏览器 download payload，同时继续执行 Content-Length/实际字节、MIME、像素、累计预算、取消、唯一 staging、fsync 与原子发布检查。Direct 401/403 最多进入一次真正的 browser-byte recovery；同 URL、同会话状态不会再次通过 direct HTTP 重放。
- 按 completion order 持久化或回滚已完成 future，同时让轻量 result 保持输入顺序。触发致命 byte/file/pixel limit 时会移除全部 staging file、协作式停止 queued work 并保留第一条 diagnostic；外部 RuntimeContext cancellation 则继续传播。EPS/TIFF 与 arXiv PDF rendering 使用带输出 byte/pixel 检查的 path-to-path conversion；source archive 会在 name validation/deduplication 前统计遇到的每个 regular member，并以相同 member/aggregate limit 避免无界读取。Archive decoding 现在位于有界 `_arxiv_source_archive` module，且不放宽既有 `_arxiv_assets` complexity gate。
- 连续 figure 与 supplementary 阶段按 hostname 复用共享连接池和 cookie jar。AMS、Annual Reviews 与 Springer 新增独立 `assets` route，并发上限为 2，且仍受全局上限 4 约束。
- 为所有下载正文资源的 provider 补齐显式 `assets` route，默认单次 direct 超时 20 秒、route cap 2；可靠 browser recovery 的路线不追加瞬时 direct retry。每篇论文、每个 host 只允许一个首资源 direct probe；browser recovery 成功后，同源剩余资源复用已验证路径，状态不跨论文持久化。ACS/AIP 不再让单个 CDN 连接占用约 120 秒，MDPI 也不再为每张同源图片重复 403 direct 尝试。
- 新增逐资产阶段计时：queue、candidate resolution、URL/DNS policy validation、connect-to-headers/TTFB、body stream、browser recovery、retry wait、conversion、save 与 total；browser context prepare/release 另列 stage timing。IEEE 自定义恢复在合并逻辑资产时保留相同 timing/route。报告只聚合阶段、终态、download tier 和质量原因，不持久化签名 URL。
- Wiley 优先 `/doi/{doi}`；主文档 401/403 改为有界复核，只有正文连续稳定、页面 DOI 精确匹配、无 challenge/明确 no-access 且后续 Markdown/全文验收通过时才接受，返回与 trace 保留真实状态，失败会继续下一候选。Science 可复用已验收 preflight HTML 并阻断重资源；PNAS readiness 与 `#bodymatter` 解析器 selector 对齐。IEEE preflight 复用因三轮 live 未达到端到端收益门槛而撤回，逐资源计时保留。图片候选方面，arXiv source archive、Copernicus JATS `graphic` 和 AIP 最大 `srcset` rendition 优先官方原图；T&F 仅有官方 CMS preview 时保持现有质量，并与其它合法预览一样输出 `official_full_size_not_exposed` 或 `official_full_size_access_restricted`，不冒充 full-size。
- Python、MCP、CLI、batch、cache fingerprint 与 manifest 新增可选严格正文资产验收 `require_local_body_assets` 和 `require_full_size_body_assets`。两项默认关闭，full-size 隐含 local；未满足时只把 asset/overall 降为 degraded，不会把已取得的全文改成 fetch failure。
- HTTP 200 空文章壳现在提供可行动诊断：ACS 的主文档、失败请求/脚本、console/challenge signal 与页面/storage 指纹均有界且脱敏；route/profile/storage/page 状态完全相同时立即停止，只有 candidate、profile 或 storage state 改变时允许一次重试。Live preflight key 绑定 provider、规范 DOI、target 与 runtime fingerprint，成功和失败都会追加 terminal record。
- Doctor provenance 拆为 `source_development` 与 `installation` scope。源码运行只审计 checkout bundle 与 active skill，不混入无关 PATH 或旧 offline root；显式 `--install-root` 与安装包运行仍执行严格 installation audit。

### 修复——可执行 route、身份与 MCP 合约

- 新增编译后的统一 `RouteExecutionPolicy`，作为 provider catalog 到 runtime 的边界。它组合 exact/suffix/base、API/CDN/template 与 route host，并驱动 HTTP/browser/PDF timeout、retry、QPS/rate wait、acceptance、asset scope 和 route concurrency。Oxford PDF、PLOS XML/DOI/asset 与 arXiv source archive 现在使用精确的 compiled route；provider-owned request 不再用并行常量覆盖。Catalog default 现在使用 runtime `dns_error` category，其中包括 Copernicus suffix host。
- 对共享 transport scope 的 worker 强制执行 arXiv Atom 与 source asset 每 3 秒最多启动一次的节流。逐 scope 串行化 start gate 在排队时释放 host concurrency；确定性 fake-clock 覆盖证明，较晚到达的 `Retry-After` 会将 queued start 推迟到 10/13 秒，而不会同时放行，并继续保持 cancellation 可观察。
- 只有 `asset_profile` 未设置时，才将 compiled route asset scope 作为默认 selector；显式 `none|body|all` 仍然优先。Route acceptance 现在评估相匹配的 identity、HTML、XML、PDF 或 audited/local-asset facet，未知 policy 会 fail closed。
- 将 provider identity evidence 分为 strong 与 weak。过期或冲突 domain candidate 的 `no_access` 会保留用于诊断，但不再阻断 strong DOI provider；只有强确认的 access boundary 才会终止 waterfall。无 DOI acceptance 现在要求唯一且经过验证的 canonical landing identity，不再以 title 作为依据。
- 补全已公开的 MCP v2 cache asset facet 与 batch artifact `route`/`failure_code` 字段，并增加 payload-key/schema subset contract。Provider registration 现在会检测 normalized alias、DOI prefix、exact/suffix domain 及 cross-overlap conflict；有意 overlap 必须具有不同 priority 和 reason，且绝不依赖 import order。

### 修复——可执行 provider 证据与回归 gate

- Provider governance 现在使用真实 corpus loader。只有同时具备 canonical raw asset、精确 expected contract 与当前可执行 adapter 的 140 个 fixture 才计为 replay；2 个 synthetic 与 15 个 manifest-only claim 仍保持可见，但不能覆盖 route。两个 synthetic IEEE PDF claim 现在各自需要有 owner 且会过期的 waiver。
- 扩展 block manifest，新增 negative kind、精确 route/source identity、reason、failure code 与 content kind。签入的全部 17 个 negative raw HTML response 现在都通过当前 provider extractor 与 availability boundary 运行；历史 extracted Markdown 不再作为证据。
- 在常规 CI 中新增四个确定性 provider-level shard，使全部 140 个精确 fixture 在每次 push/PR 中恰好运行一次。新增机器可读的 focus coverage baseline，聚合 coverage.py 官方 pure branch exit，对 unmatched/unmeasured/branchless area fail closed，报告 covered/total、精确百分比与向下取整百分比，并强制 security boundary 覆盖率至少为 90%。
- 补齐 PDF fallback 的兼容参数作用域、浏览器导航同源与响应保护，以及 request-context PDF 二次取回边界覆盖，使 64% PDF 风险分支门禁在刷新后的 PyMuPDF4LLM 1.28.2 依赖图上继续可执行，而不是放宽基线。
- 将集中的 evidence debt 替换为 10 个 route-specific 与 13 个 negative route-specific waiver；每个 waiver 都带 owner、restriction、具体 plan、review date 与独立错开的 expiry。Governance 会拒绝缺失、已过期、期限过长或共用 expiry 的条目。
- 为四条公开、无凭据的 direct route 新增非阻塞 scheduled canary。Report 会作为 artifact 保存，连续失败次数通过 Actions cache 持久化；同一路线第三次失败时才开始 warning，成功一次即重置计数。

## 5.5.0 - 2026-08-25

### 新增——精确抓取来源

- 保持兼容字段 `source` 的原值不变，并在 fetch envelope、article、Markdown front matter、acceptance、manifest v2、MCP fetch/cache/batch payload 与 cache-index entry 中新增 `acquisition={provider,route,representation,transport,fallback_used}`。精确 route 与 transport 由 provider route catalog 提供；事实缺失时保留 `null` 并把 provenance 判为 partial，不再从 `source` 猜测。
- FetchEnvelope sidecar 版本提升到 5，缺少 acquisition 的 v4 sidecar 会明确判为旧版并重新抓取；既有 Markdown 仍可读取且 `acquisition=null`。Provider waterfall 会标记最终胜出的 catalog route，同时不改变既有公开 `source` 或兼容 source-trail marker。
- Complete provenance 现在必须同时匹配 catalog route、source owner 与结构化 fallback trace，manifest 审计也会检测 Markdown acquisition 漂移。生成的 route 文档公开 `api|browser|http`，成功 trace 保留精确胜出路线，并由 core CI 覆盖这一增量协议；manifest 与 MCP wire schema 继续保持 v2。

### 修复——公式资产、公式回退与 Markdown 链接

- 修复 Wiley/Atypon display equation 的空 MathML 只暴露公式编号时的错误渲染：仍优先使用结构化 TeX，否则先使用出版社公式图片，再考虑可见文本；只有编号的公式明确保留 unavailable 状态，不再生成伪公式，完整 display-math 块也不会被 Markdown 后处理误删。
- 允许 figure caption 内显式命中 `math-N`、`_IEqN` 或 `_EquN` 的公式 URL 进入公式资产发现，同时保留正文主图，并继续把普通 equation 相关图片归为 figure。出版社只提供的公式位图继续如实记录为 `download_tier="preview"`，但作为 accepted preview 验收；公式固有的小尺寸或重复内容不再触发 placeholder 或 fidelity-degradation 误报，真实 payload 与路径故障仍保留诊断。
- 在资产验收前合并 Springer/Nature `media.springernature.com/lwNN/...` 尺寸别名与对应的 `/full/...` 下载记录。已成功归档的公式或正文图现在只计为一个本地逻辑资产，不再残留重复的 remote-only 记录并以 `missing_path`、`asset_below_request` 错误降级 Manifest 审计。
- 阻止根相对 publisher 资产被改写成不存在的 `../../cms/...` 路径。只有真实存在的本地文件才生成相对链接，已下载资产仍然优先；未匹配的 `/cms/...` 使用有效 publisher landing page 补成完整远程 URL，没有有效基址时保持原样。preview fallback 警告也改为 asset-neutral 文案。

## 5.4.1 - 2026-08-19

### 修复——Camoufox 兼容离线快照

- 将支持的 Camoufox 范围提升到 `>=0.5.5,<0.6`，并把开发与 CI 锁文件更新到 0.5.5。
- 移除 POSIX 离线构建器针对 Camoufox 的 `uv.lock` 精确版本覆盖。离线构建现在从已解析 wheelhouse 获取实际版本，同时继续要求唯一 Camoufox wheel，并核验 wheel METADATA、installed distribution 与 manifest 记录一致，避免包含较新兼容 Camoufox wheel 的冻结滚动快照被稳定源码中的旧锁错误拒绝。

## 5.4.0 - 2026-08-18

### 新增——Camoufox 运行时首次按需准备

- 为 CLI 浏览器路径新增托管 Camoufox 运行时的首次按需准备。`paper-fetch fetch`、`paper-fetch auth` 和 `paper-fetch browser-preflight` 只有在实际请求浏览器工作时才会准备缺失运行时，并复用 Camoufox 官方 CLI 完成安装、修复与更新检查。有效运行时最多每 24 小时检查一次更新；更新失败时继续使用原有有效运行时。
- 新增结构化准备进度、900 秒子进程超时、协作式取消、失败冷却和跨进程文件锁，使并发命令共享同一次安装尝试。任何修复前都会验证托管路径没有逃逸 Camoufox 根目录，也没有经过符号链接或 junction。

### 变更——显式浏览器联网策略

- 新增 `--browser-auto-prepare` / `--no-browser-auto-prepare`、`PAPER_FETCH_BROWSER_AUTO_PREPARE` 与 MCP 请求级 `browser_auto_prepare` 控制。CLI 浏览器命令默认开启；MCP 工具和直接库调用默认关闭，避免服务或嵌入模式仅因被调用就获取浏览器 binary。
- 显式自定义浏览器 binary 始终不受托管运行时变更影响；静态诊断、`provider_status`、离线安装器及离线包验证继续保持不下载浏览器。Linux、Windows 与原生 macOS CI 合约、回归覆盖、运维文档及随包 skill 指引已同步这一边界。

## 5.3.2 - 2026-08-17

### 变更——公式与发布完整性

- 将开发环境与随包公式资源的 KaTeX manifest 和 lockfile 从 0.18.1 同步更新到 0.18.4，纳入设置对象原型污染防护和解析修复。机器合约与 unit test 现在会拒绝两份依赖声明或锁文件之间的漂移。
- 将固定的 `actions/attest-build-provenance` action 从 v4.1.1 更新到 v4.2.2，并保留既有 subject-path 接口。macOS 合约、validator、测试、审计和部署文档现已同步精确的 action 名称、版本、完整 SHA、使用次数及输入。

## 5.3.1 - 2026-08-10

### 修复——Wiley 浏览器访问判断

- 修复 Wiley 全文页和 Open Access 页面仅因当前页头把 `Institutional login` 提前到前 1,000 个可见字符内，就被误判为 `publisher_paywall` 的问题。现有 provider 正文 readiness 确认实质文章内容后，导航中的普通付费墙和 not-found 文本会交给正文感知的 availability assessor；challenge 页面、HTTP 401/402/403、HTTP 404、显式拒绝访问和摘要重定向仍会 fail closed。
- 对没有实质正文 readiness 的页面继续保留 `Institutional login` 通用 access-gate 信号，并新增端到端 Wiley browser-preflight、共享信号、Linux CI、原生 `macos-15` 与 macOS adaptation contract 回归。

## 5.3.0 - 2026-08-10

### 新增——浏览器复用与可观测性

- 为 PNAS、AMS、MDPI、Royal Society Publishing、Annual Reviews、ACS、IOP 和 Taylor & Francis 新增有界、一次性的进程内已验收 preflight HTML 复用。缓存同时绑定 provider、规范 DOI、候选 URL 与 browser runtime 指纹；正式 fetch 仍会重新执行 metadata、Markdown/资产抽取和 acceptance，challenge、空壳、PDF fallback、失败页面及未提交 storage-state 均不会复用。PNAS 与 AMS 还会短期保留当前 DOI 最近验收通过的 provider route 提示。
- 新增浏览器导航次数、被阻断资源类型与请求数、readiness 预算/结果、preflight 复用和候选重排 diagnostics。Catalog live 测试同步保留阶段耗时证据，并为 PNAS preflight 加正式 fetch 设置观察性的总耗时目标，不把性能波动误当成访问边界失败。

### 变更——浏览器与资产性能

- 将浏览器加载策略改为 provider 级配置：上述八个 opt-in provider 只阻断 image、font 与 media 请求，继续放行 document、stylesheet、JavaScript 和 API 流量。PNAS 改为按 canonical 候选顺序执行一次完整导航，并使用 8 秒正文 readiness 预算；MDPI 会在 PDF fallback 前继续尝试不完整的中间 HTML 候选，Royal Society Publishing 则直接识别当前 Silverchair 正文容器，不再固定等待。
- ACS、Annual Reviews 与 Royal Society Publishing 优先使用 download/media link、`srcset` 和原图属性暴露的高分辨率图片 URL。仍缺少原图时，在 runtime 所有的单个 Camoufox figure page 上串行发现，单页等待 2 秒并按 URL memoize；随后 direct asset download 继续使用常规并发。
- Taylor & Francis 同源 CSV 表格改为 4 个有界 worker 批量 hydration，共享总 deadline、保持输入顺序，并为每张失败表保留 embedded-data fallback，不再逐表串行请求。
- 在常规 Linux 与原生 `macos-15` CI 中增加同一组非 Science 浏览器性能和资产回归 gate，并同步 macOS 适配合约、审计与维护文档。

### 修复——运行时隔离与补充资产

- 将 AIP Camoufox cookie 与 storage-state 限定在所属 `RuntimeContext`：cold HTML retry 仍可在单次 fetch 内复用 transient seed，但不再跨 runtime 指纹边界发布 preflight HTML、cookie 或 storage-state。
- IEEE multimedia discovery 与 IOP supplementary index 解析现在按 request context 使用规范化、脱敏 URL memoize。签名参数轮换不再触发重复发现/下载，也不会进入 cache key；IOP 还会确定性复用成功的索引解析结果和稳定的抽取失败。

## 5.2.1 - 2026-08-08

### 变更——构建与发布完整性

- 将固定的 `haskell-actions/setup` 构建 action 从 v2.11.0 更新到 v2.12.0，并同步 macOS 机器合约、validator、测试和文档。action 随附的 GHCup 0.2.6.2 更新仍保留 GHC 9.10.3、Cabal 3.12.1.0、texmath 0.13.2 和既有产物接口。
- 新增独立的 `uv lock --check` quality gate；项目版本、依赖声明或 lock metadata 陈旧时，会在其余静态检查前直接令 CI 失败。

## 5.2.0 - 2026-08-07

### 新增——Taylor & Francis Online

- 新增 Taylor & Francis Online（`tandf`）支持：通过 browser-rendered article HTML 获取正文，有界加载同源 CSV 和同页已加载的 table payload，并支持 browser-seeded PDF fallback、provider 管理的 abstract-only 降级、图片、MathML 公式、补充材料与参考文献。

### 修复——Taylor & Francis 浏览器初始化

- 为 `paper-fetch auth tandf` 与 `paper-fetch browser-preflight --provider tandf` 增加已验证的开放文章目标；未传 `--url` 时，默认调用不再于目标解析阶段失败。
- 将文章范围内的 Taylor & Francis CMS 正文图 rendition 标记为可接受 preview；对超出共享宽高阈值、但内容有效的宽图不再误报资产保真度降级。

## 5.1.1 - 2026-08-06

### 修复——Elsevier XML 保真度

- 修复仅通过 `link` locator 暴露的 Elsevier 公式：在公式原位置解析并输出最高保真
  官方 object 图片；已下载的本地资源优先，无资产模式保留官方远程 URL，图片
  fallback 不做 OCR，并继续明确记录降级质量状态。
- Elsevier 与共享 JATS 路径现在按各自列模型独立解析每个 CALS `tgroup`。同一表题
  下的多个源分组按顺序渲染，保留分组前缀与全部行；只有真正退成可读列表的分组
  才记录降级。

## 5.1.0 - 2026-08-06

### 修复——批量请求 deadline

- 修复 CLI 与 MCP 批量任务在预先解析身份和等待 provider lane 时提前消耗单篇论文
  request deadline 的问题。每个 fetch worker 现在会获得完整的新请求预算，同时保留
  item-local 解析缓存和共享 transport，避免 browser route 仅因抓取前的批量等待而
  错误降级为 metadata-only。

## 5.0.1 - 2026-08-04

### 变更——依赖兼容

- 将锁定的 `trafilatura` 升级到 2.2.0，并同步 Royal Society Publishing
  表格 golden contract；统计表头中的字面量管道符现在保留为合法的 GFM
  `\|` 转义，避免被误解析为额外列。
- 刷新当前兼容范围内的锁定依赖：`apify-fingerprint-datapoints` 0.14.0、
  `cachetools` 7.1.7、`cffi` 2.1.1、`coverage` 7.15.3、
  `cryptography` 50.0.0、`filelock` 3.32.2、`isbnlib2` 3.11.21、
  `pip` 26.2、`ruff` 0.16.1 和 `uvicorn` 0.52.1；其中
  `cryptography` 更新修复 `CVE-2026-69247`，锁定全依赖图的漏洞审计恢复通过。

## 5.0.0 - 2026-08-03

### 新增

- 以 `Dictation354/paper-fetch-skill` v4.1.0
  (`fc3bd96e8d781667a2e86e90dc6e8e35a8a26fa7`) 为基线重建 macOS
  适配合约、validator、Windows / WSL contract gate 和分层审计矩阵；旧 v1
  合约不再照搬。新增的维护文档说明如何在最新 `upstream/main` 上重放独立适配
  提交，并明确普通 CI 会在 Ubuntu / Windows 执行 portable gate、`/mnt/*` WSL
  checkout 只能提供 validator-only 证据。
- 新增 macOS 安装前的最低系统版本、manifest/checksum、标准 GIL CPython
  ABI/解释器架构、递归 quarantine 和用户写入顺序检查；构建器还会在 staging
  清理前拒绝路径穿越包名、危险构建根和没有 ownership marker 的非空目录；
  临时 wheelhouse 保持在 owned staging 且不进入产物，正式 artifact 采用同目录
  临时文件原子发布。`--user-config` 使用
  `~/Library/Application Support/paper-fetch/.env`，safe purge 会拒绝 `/`、
  HOME 及其祖先、尚未安装的 bundle root 或没有匹配 ownership manifest 的
  目标；普通安装同样只允许不存在、空目录或同时带 schema 3 manifest 与
  `runtime/python-bin` marker 的目标。合法升级保留 `offline.env` 和用户配置
  非 managed 内容，卸载清理 managed block；Zsh 启动文件为 symlink 时保留链接。
  checksum 清单现在必须精确覆盖 bundle 中全部 regular file，payload symlink 与
  未列出的附加 payload 都会在用户写入前拒绝；`--purge` 也无条件拒绝 symlink
  形式的入口。

### 破坏性变更

- 所有 MCP 成功/失败与 acceptance payload 从 schema v1 升级到 schema v2，并删除
  重复的 `quality.trace`；`FetchEnvelope.trace` 成为唯一完整 trace owner，
  metadata/asset 保留 `article_type` 与 `preview_accepted`，资产摘要用稳定 issue code
  区分 accepted/fallback preview。仍要求 schema v1 的消费者必须先完成升级再采用
  5.0.0；旧 v1 FetchEnvelope cache 仅保留读取迁移。
- 删除曾对外公开但未实现的 IOP XML/TDM 占位 route；catalog/status/docs 现在只公开
  真实可执行的 IOP HTML、PDF、metadata 与 supplementary 能力。

### 变更——macOS 与离线打包

- macOS CPython 3.11–3.14 arm64 离线矩阵固定到 `macos-15`，manifest 声明最低
  macOS 15.0；四个 tarball 均运行原生安装 verifier，缺少 artifact 会令 job
  失败。原生 texmath 会携带可迁移的非系统 dylib，使用
  `@rpath` / `@loader_path` 并进行 ad-hoc codesign，verifier 通过
  安全 `tarfile.data_filter` 解包、`file -b`、`lipo -archs`、canonical
  dependency containment、LC_RPATH 和递归闭包检查；随包 Playwright Node
  仅在闭包通过后实际执行 `--version`。递归 `xattr` 检查发生权限/I/O 错误时
  也会 fail closed；匹配过程不使用早退管道，并加入大体积 provenance 输出
  回归，避免 `set -o pipefail` 下的 `SIGPIPE` 漏判。
- 同步 README、部署和文档索引，区分 Windows、WSL 与原生 Mac 证据；Windows /
  WSL 绿灯不能替代 Mach-O、`/bin/zsh`、`xattr` 或 Gatekeeper 的原生
  `macos-15` gate。原生 verifier 实际覆盖嵌套 quarantine、`.zshrc` symlink、
  owned upgrade 和 user-config；`/var` ↔ `/private/var` cache alias 由原生 CI
  精确测试。旧上游 `v4.1.0` 标签不可移动或复用，发布本 fork 适配必须提升版本
  并创建新标签；不可变标签重跑必须先通过源码 checkout 自身的当前 Mac contract，
  因此不能靠 overlay 把无合约的上游 `v4.1.0` 改造成适配发行版。
- 普通 CI 的 `macos-15` job 现在显式准备固定的官方 Camoufox
  `152.0.4-beta.28` app bundle，并串行启动临时与持久 context。原生测试只接受
  当前用户固定的 managed cache，且在调用 Camoufox 前验证 compatibility flag、
  active config 与 browser 目录 containment，避免把任意目录交给 package manager
  清理。
- browser/full extra 保持 `camoufox>=0.5.4,<0.6` 兼容范围，由 `uv.lock`
  提供可复现的具体版本。POSIX 构建器从 lockfile 解析该版本，核验下载 wheel
  METADATA 与 installed distribution，并把实际版本写入 offline manifest。
  POSIX/Windows tooling ref 都必须是
  完整 commit SHA，只复制精确 packaging-tool 路径且不复制 Python wheel source；
  manifest 会分别记录源码 `git_revision` 和可选 `tooling_revision`。

### 修复——macOS 与离线打包

- 将 provenance 检查使用的 `packaging` 声明为核心运行时依赖，并让 macOS
  contract validator 通过锁定的项目环境运行，避免干净 core 安装以及原生/离线
  CI runner 因依赖未声明或环境不可见而失败。
- 修复并发或续跑 CLI batch 在结果缺少标题和 DOI 时争用
  `unknown_unknown_article.*` 的问题。主输出文件名现在回退到规范化 query 的
  16 位 SHA-256 摘要，在不向文件名暴露完整 query URL 的同时继续保持
  no-overwrite 安全语义。
- 修复原生 macOS 上已预置的官方 Camoufox app bundle 无法启动的问题：默认
  managed runtime 继续以 `download_if_missing=False` 保持普通 fetch 不联网下载，
  但不再把 `Contents/MacOS/camoufox` 误作 custom executable 传回 Camoufox，
  从而避免错误查找 `Contents/MacOS/properties.json`；临时 fetch/preflight 和
  持久 auth context 均覆盖该规则，显式 binary override 仍保持透传。
- 修复 macOS 把 `tempfile` scope 暴露为 `/var/...` 或 `/tmp/...`、而文件
  canonical path 为 `/private/var/...` 或 `/private/tmp/...` 时 MCP cache index、fetch-envelope 和 resource
  错误 miss 的问题；等价根路径现在共享同一安全 scope，目录内 symlink 和
  scope 外文件仍会拒绝。

### 变更——运行时与 provider 验证

- 删除 GitHub Actions 的 Live publisher/MCP、provider drift 与完整 Golden corpus
  定时/手动工作流；这些 opt-in 检查只保留文档化的本地 pytest 和脚本入口。
- publisher live 样本改为声明 source 与 trail 的联合合法 outcome，browser provider 使用复用 storage state 的 lazy preflight，live socket 由 marker 自动放行，不再依赖全局 force-enable。Springer 成功基准替换为 OA 研究论文，历史 Nature 新闻只保留为独立 access-gate 行为样本。
- publisher catalog live 从全文 smoke 提升为 `asset_profile=body` 硬验收门；JSON/JUnit artifact 会区分“已记录 provider 全部 complete”和“存在 skip/未记录 provider”，IEEE 受保护 GIF 恢复拆为仅授权 runner 显式启用的独立套件。

### 修复——运行时与 provider

- 当浏览器后续候选发生传输/导航失败，或下一候选 URL、保守重试耗尽共享 deadline
  时，保留此前已明确识别的 challenge/paywall/access boundary，并让 provider 自有 PDF waterfall 继续输出
  `no_access`。live 验收只接受显式 `status=no_access` 或 metadata fallback 精确的
  `route:provider_candidate_*_access_boundary_stop` 作为合法访问边界；解析失败、空壳和
  正文不足仍是失败。
- IEEE preflight、浏览器 landing/全文和共享资产 seed 现在最多等待 15 秒，且只接受文章号匹配的 `#article`；持续存在的 AWS WAF HTTP 202 页面精确报告 `aws_waf_challenge` 和兼容诊断，已在窗口内恢复的文章页不再因初始响应被误拒。受保护 large 资产仍保持 direct-first、一次 preview 预热和完整的 full-size 恢复/降级 provenance。
- 稳定 AIP 及共享 browser workflow 的冷启动 HTML 重试：fast 尝试产生的 provider-scoped 临时 cookies 会传给正常尝试，但未验收状态不会提前持久化；HTTP 200 的 head-only 页面现在报告 `empty_article_shell`，重试会优先下一个已有 provider URL 而不再重复同一空壳 landing。诊断保留两轮尝试、响应状态和 DOM readiness，PDF 继续作为终态兜底。
- 修复 publisher live 测试误读浏览器静态能力的问题：改读嵌套的 `browser_runtime.available`，隔离各 provider 的 profile/storage state，并在 pytest 隔离期间复用 Camoufox 已准备的可执行文件与依赖 cache；显式启动复用相邻版本元数据，启动进度不再污染 MCP JSON-RPC stdout。
- 将页面创建前的 browser 失败也保存为隐私安全诊断 JSON，把请求作用域的公式工具配置传入隐式 MathML 转换，修正 body-only 资产及 provenance 验收语义，并在不跨线程使用 Camoufox page 的前提下恢复 Silverchair 签名原图。
- 普通 publisher/MCP live 套件与 IEEE 受保护覆盖保留为彼此独立、仅限本地显式运行的入口；共享外部状态的测试继续串行，并保留 legacy-compatible JUnit 属性和结构化 acceptance artifact。
- 修复 IEEE 浏览器 DOM 提取把非可见脚本/模板中的 `captcha` 或访问 token 误判为 block page 的问题；可见 challenge 仍会被拒绝，验证时保持页面自身 REST 子请求正常放行。
- 为成功的 MCP 单篇抓取响应补齐文档约定的 `status=ok` 与七分面紧凑 acceptance，并与批量抓取复用同一套统一验收及投影逻辑。
- 将成功展开的 HTML/JATS/CALS 行列跨度改判为正常表格规范化：保留结构化 reason，但不再误发版式降级 warning；非法 span/列定义仍保守降级，并提升 extraction revision 以淘汰带旧质量语义的缓存。
- 修复 request deadline 初始化、AIP/Science DOM readiness 与 browser preflight 分类：fast-path 本地 cap 不再耗尽后续 fallback，页面/提取失败会保留隐私安全的诊断产物。
- Springer/Nature HTML 改为复用安全 cookie-aware requester，并对 `cookies_not_supported` 只用全新 session 重试一次；同时保留 Research Briefing article type，合法无署名 briefing 不再误报 `empty_authors`。
- IEEE small/large 资产按 canonical logical identity 对账；direct 资产恢复并发，共享 page 的 browser recovery 仍串行；资产下载失败、保真降级、占位和 remote-only 使用互不替代的稳定分类。
- 移除 trace 三层重复拼接和按 warning 数量降级的质量启发式；真实 retry 的同 code 仍按顺序保留，任意数量的操作通知不再自动降低内容质量。
- 普通 unit 强制零外部 socket attempt，补齐三个 batch resolver fake seam；doctor 诊断 source checkout 未激活 `.venv` 与 MCP 版本不兼容，成功和终态失败 manifest 都保留诊断文件。
- 新增独立 browser/DOM/HTTP/retry/asset/render 计时及 provider-route-stage nearest-rank 性能摘要：单样本只显示 observed，多样本显示 p50/p95。

### 限制

- 离线 runtime 包含 Camoufox / Playwright Python 包，但不包含 Camoufox 浏览器
  binary，普通 fetch 不会自动下载。进入受限网络或离线环境前需联网用离线
  runtime 执行 `python -m camoufox fetch`，再运行
  `paper-fetch browser-preflight` 验证；预置后真正断网的 Camoufox launch
  仍是开放审计项，因此不宣称完整离线浏览器支持。

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
- 修复丢弃 HTTP 重定向或异常响应时仅关闭连接却未归还阻塞式连接池的问题，避免 Springer 并发图片发现耗尽连接槽并令 fetch 与离线发布 smoke 无限等待。

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
