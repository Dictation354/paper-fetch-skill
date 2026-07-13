# paper-fetch 一次性优化执行计划（2026-07-13 审计更新）

> 推荐执行入口：`/goal follow paper-fetch-optimization.md`
>
> 本文是执行规范，不是问题清单。`[x]` 表示审计或本次执行确认已完成，`[ ]` 表示仍待完成。`/goal` 的初始范围是 `PF-012`、`PF-013`、`PF-014`、`PF-016` 至 `PF-022`；截至当前 `PF-001` 至 `PF-022` 已全部完成，**不再有待完成项**，不得重新执行任何 `[x]` 项。全部工作均由根代理直接完成，未使用子代理。

## 0. 当前审计结论

### 0.1 审计口径与快照

- 审计时间：2026-07-13（Asia/Shanghai）；源码 revision：`10e30297df2cc7c354c1cb407a8514b22d2800d8`，审计对象包含当时未提交的工作树变更。
- 只有实现、针对性测试、相关旧回归和指定文档均已落地的优化点才记为“已完成”；只有类型、注册点、共享基础设施或 CI 片段等前置基础时，仍记为“待完成”。
- 针对性审计集结果：`202 passed, 68 subtests passed`；完整 unit 结果：`2016 passed, 1 skipped, 1 warning, 425 subtests passed`，均复用 `pyproject.toml` 的并行配置。
- 初始审计确认源码 `pyproject.toml` / `DEFAULT_USER_AGENT` 为 `3.0.1`，当前环境 distribution metadata 为 `3.0.0`，PATH CLI 为 `2.8.0`；`PF-020` 已把目标版本准备为 `3.1.0` 并实现可验证 provenance，活动安装仍保持 `2.8.0`，只由 `PF-022` rollout。
- 本次审计没有运行完整 integration、devtools、ruff、mypy、build、offline/temp-install、活动安装升级或 live publisher 测试；这些不能写成已通过，仍由后续优化点负责。
- `PF-012` 完成后已追加验证：聚焦 persistence/resume/overwrite/只读审计集 `34 passed`；CLI、manifest、共享 runner 与架构相关回归 `142 passed, 19 subtests passed`；完整 unit `2050 passed, 1 skipped, 1 warning, 430 subtests passed`；相关 Ruff 与 diff whitespace 检查通过。完整 integration/devtools/build/install 仍按 `PF-021` / `PF-022` 执行。
- `PF-013` 完成后已追加验证：静态 diagnostics/CLI/MCP/schema/image/browser/config/docs 聚焦集 `279 passed, 66 subtests passed`；manifest/catalog 同步回归 `72 passed, 33 subtests passed`；独立 stdio MCP/schema 集成 `2 passed`；完整 unit `2071 passed, 1 skipped, 1 warning, 438 subtests passed`；相关 Ruff、定向 mypy、真实 compact doctor smoke 与 diff whitespace 检查通过。全量 mypy 仍有审计前邻近 `auth.py:229` 的 6 个 `dataclasses.replace(**dict[str, object])` 类型错误，保留给 `PF-021` 统一门禁修复；未运行 live 页面测试。
- `PF-014` 完成后已追加验证：browser core/runtime、MCP adapter/schema/stdio、CLI 回归与契约文档聚焦集 `205 passed, 28 subtests passed`；其中独立 stdio MCP/schema 集成 `2 passed`；完整 unit `2088 passed, 1 skipped, 1 warning, 438 subtests passed`；相关 Ruff、定向 mypy 与 diff whitespace 检查通过。全部 browser/preflight 用例使用 mock，未运行 live publisher/browser 页面测试；CI 文件按所有权留给 `PF-021` 统一同步。
- `PF-016` 完成后已追加验证：cache full/compact/preferred-only、严格请求匹配、sidecar 异常、DOI 归属、schema/stdio、skill/docs 聚焦集 `176 passed, 51 subtests passed`；独立 stdio MCP/schema 集成 `2 passed`；完整 unit `2110 passed, 1 skipped, 1 warning, 438 subtests passed`；相关 Ruff format/check、去除已知 models stub `attr-defined` 噪声后的定向 mypy、diff whitespace 检查通过。完整 mypy 的旧 stub 导出缺口与 `auth.py` 旧错误仍由 `PF-021` 统一收口；未运行 live publisher/browser 测试，且本项未修改 CI。
- `PF-017` 完成后已追加验证：runtime catalog/source 精确投影、动态新增映射、native resource、文案/宿主/schema/tools-list 预算、provider/docs/skill 与 MCP resource 回归聚焦集 `154 passed, 47 subtests passed`；独立 stdio `resources/list` + `resources/read` 集成 `1 passed`；完整 unit `2116 passed, 1 skipped, 1 warning, 438 subtests passed`；相关 Ruff format/check、定向 mypy 与 diff whitespace 检查通过。实测 instructions/fetch description/全部 descriptions/host narrative 分别为 `1057/985/2266/11779` 字符，native tools/list 和独立 schema 快照为 `61972/58931` bytes；未运行 live publisher/browser 测试，且本项未修改 CI。
- `PF-018` 完成后已追加验证：结构化 batch fetch 的乱序保序、完成序号、progress/cancel、provider lane 限流、continue-on-error、cache hit、保存/完全不落盘、持久化/resume/overwrite、interrupted/cancelled 完整 index、typed schema、resource 同步与独立 stdio 回归聚焦集 `178 passed, 45 subtests passed`；stdio schema/架构/注解兼容回归 `50 passed, 8 subtests passed`；完整 unit `2142 passed, 1 skipped, 1 warning, 438 subtests passed`；相关 Ruff format/check、lazy MCP export smoke、diff whitespace 检查通过。定向 mypy 只报告已记录并留给 `PF-021` 的 `auth.py:229` 六项旧错误。加入第十个工具后 instructions/fetch description/全部 descriptions/host narrative 为 `1093/985/2601/13531` 字符，native tools/list 和独立 schema 快照为 `74411/70913` bytes；未运行 live publisher/browser 测试，且本项未修改 CI。
- `PF-019` 完成后已追加验证：正常 CLI workflow/窄 fallback、thin SKILL 直达七个关键 reference、独立 acceptance/path/hash、prompt/tool 边界、环境优先级/offline wrapper、Chrome/CDP 与 formula/image diagnostics、动态 catalog 和主 docs 交叉链接均已收口；使用 dev-only `markdown-it-py` AST 对 source、真实 offline staging 以及 Codex/Claude installer 临时安装副本检查相对链接不越界、目标存在、SKILL 直达和无孤儿。聚焦文档/链接/installer/既有契约集 `81 passed, 64 subtests passed`；完整 unit `2150 passed, 1 skipped, 1 warning, 444 subtests passed`；相关 Ruff format/check 与 diff whitespace 检查通过。未修改 runtime 代码或 CI，未运行 live publisher/browser 测试。
- `PF-020` 完成后已追加验证：目标 SemVer 已选为 `3.1.0` 并同步 package metadata、稳定 User-Agent、Inno 默认版本、中英文 changelog 和部署/CLI/skill 文档；offline manifest schema 3 在 POSIX/Windows 构建器中记录完整 skill 文件集合及逐文件 SHA256，POSIX 安装器与 Windows helper 共用 `skill_integrity.py` 在 bundle、安装根和 Codex/Claude/Antigravity 三副本执行严格前后校验。`doctor --json --install-root` 汇总 source、当前 distribution、PATH CLI、manifest revision/target/build/entrypoint、安装 runtime 和 skill 状态；实测可直接指出源码 `3.1.0`、活动 manifest/runtime/PATH CLI `2.8.0` 及对应绝对路径，纯 source 无 manifest 为 `not_applicable`。PF020 聚焦集 `109 passed, 1 skipped, 23 subtests passed`，skill source/staging/installer 回归 `35 passed, 15 subtests passed`，完整 unit `2162 passed, 1 skipped, 1 warning, 444 subtests passed`；相关 Ruff、bash syntax、定向 mypy 和 diff whitespace 检查通过，全量 mypy 仅保留既有 `auth.py:229` 六项错误给 `PF-021`。`python3 -m build`、clean venv console scripts 和临时 CPython 3.14 Linux offline build/install/provenance/uninstall/purge 均通过，产物均在临时目录并已清理；正式 offline verifier 显式跳过 live DOI。一次调试重跑漏传 skip 变量而进入 DOI smoke 后已立即终止，未采纳其结果。未修改 CI，也未覆盖活动安装。
- `PF-021` 完成后已追加验证：复用既有 CLI help/input/output、MCP input/output schema、description/resource/catalog/skill links、CLI/MCP 落盘矩阵、batch 乱序/完整 index/限流/取消、manifest stale/reconcile/resume/output hash 测试，并新增 CLI/MCP/cache/manifest 四 adapter acceptance 一致性和真实 source→staging→temp-install skill hash/version/references/link 契约。CI 保留 Ruff/mypy 与独立 MCP input schema step，新增跨执行面轻量门；package-smoke 在 checkout 外构建并验证 wheel/sdist、版本、四个 console scripts、MCP EOF 和静态 provenance，offline/full-golden/live 触发边界保持不变。CI workflow 契约集 `20 passed, 3 subtests passed`，接入 CI 的跨面集合 `85 passed, 55 subtests passed`；完整 unit `2166 passed, 1 skipped, 1 warning, 444 subtests passed`，integration `195 passed, 132 skipped, 9 subtests passed`，devtools `39 passed, 4 subtests passed`。全仓 Ruff format/check、174 个源码文件 mypy、extraction-rule 校验和 diff whitespace 均通过；旧 `auth.py:229` 六项 mypy 错误已用类型明确的 `dataclasses.replace()` 参数修复。临时 clean-venv package smoke 通过并已清理；未运行 live publisher、未 push 或触发 GitHub CI。
- `PF-022` 完成后已追加验证：根代理重新读取全部停止条件并独立执行 `scripts/dev-preflight.sh`，确认 pytest 继续使用仓库 `-n auto`；完整 unit `2166 passed, 1 skipped, 1 warning, 444 subtests passed`，integration `195 passed, 132 skipped, 9 subtests passed`，devtools `39 passed, 4 subtests passed`，全仓 Ruff、174 个源码文件 mypy、文档规则和 diff whitespace 均通过。最终 CPython 3.14 Linux 离线包 SHA256 为 `424cca3540caa1fe32a9d81da6e76e6645c3fb9d37ccd5fb6e9302b4608c556c`，正式 offline verifier、全新临时 HOME/install、四份 skill 各 8 文件 hash、CLI/local smoke 和独立 MCP stdio 均通过；MCP 实测为 10 tools、2 prompts、2 至 3 个静态 resources、1 resource template、19 providers、33 sources，compact `provider_status` 正常。首个候选包因构建环境 PATH 复用了旧安装的绝对 `texmath` 链接而被活动安装 smoke 拒绝；该候选未被采纳，根代理从备份恢复工具后以隔离 PATH 和既有 Cabal 缓存重建，最终包中的 `texmath` 为普通 ELF 文件，无需修改源码。升级前创建了 mode `0700`、约 711 MiB 的完整回滚备份 `/home/dictation/.local/state/paper-fetch-skill/rollout-backups/20260713T101744Z-2.8.0-to-3.1.0`；活动安装、三宿主 skill/MCP 配置和 PATH 入口现均指向 `3.1.0`，doctor/provenance 为 `ready`，旧 Miniforge `2.8.0` editable distribution/四个入口点已在补充备份后卸载且 `pip check` 通过。`offline.env` 三个自定义值的 secret-safe 指纹、downloads、全局 cache/data/config、44 个浏览器状态文件与备份一致；所有 PF022 临时构建/安装目录已清理。未运行 live publisher/auth，未 commit、push、tag、发布或触发 GitHub CI；当前已启动宿主需新会话才能重载 MCP/skill。

### 0.2 数量汇总

| 状态 | 数量 | 优化点 |
|---|---:|---|
| 已完成 | 22 | `PF-001` 至 `PF-022` |
| 待完成 | 0 | — |

### 0.3 逐项证据与剩余范围

| 优化点 | 状态 | 审计依据或 `/goal` 剩余范围 |
|---|---|---|
| PF-001 | 已完成 | `test_pf001_compatibility_contracts.py` 覆盖 preview、AMS Blank、metadata probe、稳定 index、严格 cache 匹配、限流停止、native strategy schema 和离线 skill 递归复制。 |
| PF-002 | 已完成 | 已有统一 `workflow/acceptance.py`、版本化 schema、状态矩阵测试和架构文档。 |
| PF-003 | 已完成 | 已有结构化资产模型、`quality/assets.py`、真实 MIME/尺寸/hash/保守 placeholder 诊断、fallback provenance、兼容测试和 extraction rules。 |
| PF-004 | 已完成 | 已有 Pydantic manifest v2 record builder、打包 JSON Schema、稳定依赖注入、旧九字段投影和模型测试。 |
| PF-005 | 已完成 | 已有 PyYAML front matter parser、DOI-scope 注册/refresh/rescan/preferred 规则、v1 迁移、无网络回归和文档。 |
| PF-006 | 已完成 | skill 已改为身份优先状态机，入口保持精简，阶段、BLOCKING、目录推断和 reference 链接测试已覆盖。 |
| PF-007 | 已完成 | 五个预设、CLI/MCP 独立落盘矩阵、本地优先树、显式参数与运行时产物测试已落地。 |
| PF-008 | 已完成 | failure-handling 已成为唯一重试事实源，prompt/skill 对 probe、分块、并发、限流和最多三次代理尝试的契约测试已通过。 |
| PF-009 | 已完成 | argparse 子命令、legacy fetch 兼容、help/错误/退出码测试和 CLI 文档已落地。 |
| PF-010 | 已完成 | CLI 已复用 manifest builder 与共享 runner，支持单篇显式 manifest、批量完成顺序流式 v2 JSONL、终态完整性、hash 和兼容字段测试。 |
| PF-011 | 已完成 | 共享增量 batch runner 已被 MCP 和 CLI 复用，provider lane、限流、取消、异常、callback 与未调度终态测试已通过。后续文档总收口由 `PF-019` 处理。 |
| PF-012 | 已完成 | 已有原子 run manifest、append-only attempt、确定性 record id、只读 audit/reconcile、安全 resume/overwrite、单篇共用审计、锁与原子写入；聚焦及相关回归和 CLI/架构文档均已同步。 |
| PF-013 | 已完成 | 共享静态 diagnostics 已支持 provider/group/detail、secret-safe 配置来源、浏览器/图片本地能力与区分 reason code；MCP schema/stdio 和内置 `doctor --json` 已接通，无参全量兼容且不做网络探测。 |
| PF-014 | 已完成 | MCP `browser_preflight` 已直接复用 CLI 共享核心，支持 provider/URL/storage/detail、逐 provider progress/cancel 与五类状态；open-world 写盘注解、无 PDF/auth 边界、native/host-safe/stdio schema、structured output、mock 回归和 CLI/MCP/skill/架构契约均已落地。 |
| PF-015 | 已完成 | typed Pydantic 输入、native/host-safe 双层 schema、无 `$ref` host 结果、范围/枚举/extra-forbid 和 stdio/native 测试已落地。 |
| PF-016 | 已完成 | `get_cached` 已支持 full/compact/preferred-only 与当前请求参数；compact 返回 DOI/scope/index/preferred/quality/acceptance/asset/warning/sidecar/fingerprint 摘要，严格复用 `cached_request_matches()`，不回传正文或全量资产，并显式报告旧版、损坏、错 DOI/scope 与无归属证据。 |
| PF-017 | 已完成 | `resource://paper-fetch/provider-catalog` 已直接投影 runtime provider/source catalog，包含版本、sources、browser/runtime、status/preflight 和资产默认；超长静态路由已从 instructions/fetch description/tool contract 移除，四类文案预算、host narrative、native tools/list 与 schema 快照及 stdio resources/read 已锁定。 |
| PF-018 | 已完成 | 已注册第十个结构化 `batch_fetch` 工具，复用共享 runner、manifest builder、PF-012 persistence 和单篇 fetch 语义；支持输入保序/完成序号、compact/bounded、progress/cancel、lane 限流、完整终态、保存/不落盘、可审计 persistence/resume/overwrite，并同步 typed schema、resource、预算快照、stdio/单元测试和契约文档。 |
| PF-019 | 已完成 | 正常 CLI 主路径已迁到自包含 `cli-workflow.md`，旧 fallback 命名和仓库外链接已删除；SKILL 直达 workflow/presets/acceptance/tool/failure/environment/CLI，prompt/tool、环境/offline/toolchain、动态 catalog、gitignored path/hash 与主 docs 已同步，并用成熟 Markdown parser 验证 source、staging 和 installer 副本。 |
| PF-020 | 已完成 | 已准备 `3.1.0`，offline manifest schema 3 记录完整 skill 清单/hash，POSIX/Windows 构建与安装前后校验对齐；doctor provenance 可定位 source/distribution/manifest/runtime/UA/PATH/三宿主副本漂移，wheel/sdist、clean venv 和临时 offline 安装均已验证，未 rollout 活动安装。 |
| PF-021 | 已完成 | 已复用并显式接入 CLI/MCP schema、落盘、batch、manifest 与 skill/provenance 契约，新增四 adapter acceptance 和真实 source/staging/temp-install hash/link 测试；完整 unit/integration/devtools/Ruff/mypy/docs/package smoke 均通过，CI/live/offline 边界由 workflow contract 锁定。 |
| PF-022 | 已完成 | 完整 preflight、最终离线包 verifier、全新临时 HOME/install、活动安装备份升级、三宿主 skill/hash、PATH/runtime/provenance、数据保留和独立 MCP stdio 均已复核；旧 `2.8.0` 入口已清除，临时目录已清理。 |

## 1. Goal 定义

### 1.1 唯一目标

在不破坏 `PF-001` 至 `PF-011`、`PF-015` 已完成行为的前提下，一次性完成 `PF-012`、`PF-013`、`PF-014`、`PF-016` 至 `PF-022`，补齐批量恢复、浏览器诊断、MCP cache/catalog/batch、技能文档、版本 provenance、离线安装和 CI/终验，使以下链路可被机器验证：

~~~text
输入解析与去重
  -> 本地文件与精确缓存复用
  -> 任务意图和执行面选择
  -> 必要的 provider 状态或浏览器预检
  -> 抓取
  -> 身份、文本、资产、输出、溯源验收
  -> 单篇或批量 manifest
  -> reconcile / resume
  -> 用户可读且机器可读的结果报告
~~~

### 1.2 可验证停止条件

只有同时满足以下条件，根代理才可把本次 `/goal` 标记为完成：

- 本次初始待完成的 10 项全部由根代理直接完成并逐项复核，且审计前已完成的 12 项回归保持通过。
- 不创建或使用任何子代理；独立性通过重新读取规范、fresh process、临时目录/临时 HOME、独立 MCP client 和可重复命令获得。
- 每个代码优化点均有针对性自动化测试，并同步对应用户文档或架构文档。
- CLI、MCP、cache、manifest 和技能工作流使用同一套验收语义，不存在第二套平行质量模型。
- 完整 unit、integration、devtools、ruff、mypy、文档规则、wheel/package 和临时安装验证全部通过。
- `.github/workflows/ci.yml` 已与新增本地检查同步，但没有 push、tag、release 或主动触发 GitHub CI。
- 离线 staging、临时安装和当前活动安装的版本、skill 文件清单及 hash 一致；当前活动的 `2.8.0` runtime 漂移已消除。
- 使用独立 MCP client 进程验证已安装 entrypoint 的 `tools/list`、resources 和关键 schema；不要求当前已启动的 Codex 会话热重载 MCP。
- 未修改、删除或覆盖用户已有缓存、下载、凭证、`offline.env` 自定义值和无关工作树变更。
- 没有仍在运行的测试、构建、安装或 MCP 会话。
- 最终报告列出变更文件、验证命令、结果、未运行的 live 测试和剩余外部风险。

### 1.3 本次明确不做

- 不绕过登录、验证码、付费墙或出版社访问控制。
- 不把 live publisher 测试纳入默认完成门；只有明确需要验证外部状态时才运行，并说明串行原因。
- 不基于已经不存在的 `/home/dictation/drought_prediction` 或 `/home/dictation/pshed` 写死项目规则。
- 不把 `git status` 当作 papers 是否存在或是否有效的验收依据。
- 不为追求测试通过而降低断言、删除回归测试、隐藏 warning 或扩大 metadata-only 的成功含义。
- 不提交、push、打 tag、发布 release 或触发 GitHub Actions，除非用户另行明确要求。

## 2. 审计基线与纠偏

### 2.1 必须采用的事实基线

- 仓库 HEAD 源码版本为 `3.0.1`，当前 Codex/PATH 实际活动离线 runtime 为 `2.8.0`；两者必须分层测试，不能混写为“本机当前就是 3.0.1”。
- 源码 runtime provider 数为 19；provider catalog 应以运行时 catalog 为唯一事实源。
- native FastMCP `tools/list` 已把 `strategy` 暴露为带 `$defs` 的对象；Codex host 显示 `unknown` 是宿主展示兼容问题，不能通过把模型退化为 `dict` 来“修复”。
- native 工具描述和 Codex host 展开的上下文不是同一指标；后续必须分别建立 schema 快照、描述预算和宿主展开预算。
- CLI 批量结果已经有稳定的 1-based `index`，JSONL 当前按完成顺序写入；优化必须保留这两个公开事实。
- `TraceEvent`、结构化 MCP error、表格布局/语义损失字段和严格的 cache request 匹配已经存在；应复用并向外汇总，禁止重新发明字符串分类器或宽松 cache 匹配。
- CLI/MCP batch 已复用共享 runner，并在 rate limit 后停止相同 lane 的新提交；后续不得复制第二套调度器或破坏该行为。
- `batch_check(mode="metadata")` 只产生 `likely_yes` 或 `unknown` 的可读性探测结论，不得报告成已抓取的 `metadata-only` 或已验证全文。
- 源码离线构建已经递归复制完整 skill 目录；真实问题是安装版本漂移、只强制检查 `SKILL.md`、缺少安装后完整清单/hash 证明。

### 2.2 问题清单到优化点的映射

| 原问题 | 审计后的处理 | 对应优化点 |
|---|---|---|
| 3.1、3.7、6.2、6.5、6.6、9.3 | 成立或部分成立，建立统一验收、资产摘要和 manifest | PF-002、PF-003、PF-004、PF-010 |
| 3.2 至 3.6、4.1 至 4.3、4.5 至 4.10 | 主要是技能工作流、意图预设、重试和执行面语义问题 | PF-006、PF-007、PF-008、PF-009 |
| 4.4 | CLI 缺少增量提交和 provider-aware 限流；MCP 已有部分防护 | PF-011、PF-010 |
| 5.1 至 5.3、6.7 | 状态探测与 live preflight 混淆，诊断范围和图片后端信息不足 | PF-013、PF-014 |
| 6.1、6.4 | 需要保守的资产真实性诊断和分类汇总 | PF-001、PF-003 |
| 7.1 至 7.6 | 断链、孤儿契约、CLI 定位、环境优先级和 prompt 表述问题 | PF-019、PF-020 |
| 8.1 至 8.5 | MCP schema、上下文、动态 catalog、compact cache 和 batch fetch | PF-015 至 PF-018 |
| 9.1、9.2、9.4 | 保留稳定 index/完成顺序，增加 run manifest、reconcile 和 resume | PF-004、PF-010、PF-012 |
| 10.1、10.2 | 历史工作区不可复核，只提炼为通用目录推断和文件验收规则 | PF-006、PF-007 |
| 10.3、10.4 | 脚本兼容和本地全文复用成立 | PF-005、PF-007、PF-019 |
| 11 至 13 | 作为预设、验收和测试的目标契约实现，不照抄其中错误示例 | PF-007、PF-008、PF-021 |

### 2.3 只能加回归护栏、不得重复修复的行为

- AMS `Blank.svg/png` URL 拒绝和 lazy 真实 URL 提取已经存在。
- Wiley preview 是可用但可能降级的资产，不得把整篇正文抓取标记为失败，也不得一概拒绝 preview。
- `asset_profile=none` 时保留远程图片链接是既有契约，不代表本地资产下载失败。
- cache 对 `modes/strategy/include_refs/max_tokens` 的请求匹配已经严格。
- MCP batch 的限流后停止增量提交已经存在。
- CLI JSONL 的稳定 `index` 已经存在，完成顺序写入也已文档化。
- `table_layout_degraded_count` 与 `table_semantic_loss_count` 已分离，不得重新合并成单一“表格失败”。
- offline package 当前不是“只包含 SKILL.md”；需要修的是完整性证明和活动安装漂移。

## 3. `/goal` 执行协议

### 3.1 根代理直接执行职责

- 只创建一个长期 `/goal`，目标严格限定为 `PF-012`、`PF-013`、`PF-014`、`PF-016` 至 `PF-022`；不得为每个优化点创建新的 goal。
- 根代理负责依赖调度、文件所有权、代码复核、冲突处理、总体验收和最终报告。
- 根代理直接实现全部待完成项，不创建、调用或依赖子代理。
- 根代理可以处理纯机械冲突，但不能借“集成”为名新增未测试行为。
- 开始前记录 `git rev-parse HEAD`、`git status --short`、源码版本、PATH CLI 版本、活动 offline manifest、Codex MCP 配置目标和 skill 文件 hash；这些记录只用于对比，不覆盖用户文件。
- 每完成一个优化点立即复核 diff、针对性测试和文档同步，再更新 goal 进度，不得到最后一次性把全部任务标完成。
- 已完成项默认只运行回归，不重新实现；只有待完成项所需的兼容修复或回归失败才能修改其邻近代码，并在报告中说明原因。

### 3.2 禁止子代理与范围控制

- 不调用 subagent、spawn/follow-up、并行代理或“独立终验代理”；所有实现、复核和终验均由当前根代理完成。
- 每个待完成项开始前重新读取最新工作树、本文对应条目、相关实现、测试和文档，不能只依据原问题清单直接编码。
- 只修改条目列出的主要文件和必要的紧邻文件；扩大范围时先在 goal 进度和最终报告中记录原因。
- 不 commit、push、tag、发布或触发 CI。
- 每项结束时记录：修改文件、关键设计、执行命令、测试结果、文档更新、兼容性影响和残余风险。

### 3.3 顺序和文件所有权

- 不并行实现优化点；只允许 pytest/构建工具按仓库配置并行执行内部测试任务。
- `src/paper_fetch/cli.py` 的剩余任务只由 `PF-020` 继续处理。
- `src/paper_fetch/mcp/server.py` 的 `PF-016 -> PF-017 -> PF-018` 串行任务已完成；后续项不得重新打开或复制这些 MCP 行为。
- skill 文档剩余任务在所有用户可见 MCP 行为稳定后由 `PF-019` 收口。
- manifest/恢复链严格按 `PF-012 -> PF-018` 串行；不得在 `PF-018` 复制 persistence。
- `.github/workflows/ci.yml` 只在 `PF-021` 修改；其它待完成项先在逐项审计记录中列出所需 CI 调整。
- `CHANGELOG.md`、`CHANGELOG_CN.md` 和版本号只由 `PF-020` 统一修改，避免并发冲突。

### 3.4 通用实现约束

- 优先复用现有 `Quality`、`SemanticLosses`、`TraceEvent`、`reason_codes`、`FetchEnvelope`、`ArtifactStore`、`FileLock`、`cached_request_matches()`、`normalize_doi()`、Pydantic/FastMCP 和项目已有 provider catalog。
- 结构化数据必须使用 Pydantic、JSON Schema、PyYAML 或现有结构化 parser；不得用正则或字符串搜索模拟 YAML、JSON、Markdown front matter 或 MCP schema 解析。
- 图片类型和尺寸复用 `filetype`、`imagesize`，内容 hash 使用标准库 `hashlib`；不得自写图像解码或感知相似算法。
- 公共字段采用向后兼容的 additive 变更；必须改变默认值或删除字段时，需单独迁移期、弃用提示和兼容测试。本计划默认不改变 CLI/MCP 已公开的默认值。
- 每个代码优化点必须同步对应 docs/skill reference；`PF-019` 负责信息架构收口，不替代前面任务的文档责任。
- 测试默认复用 `pyproject.toml` 的 `-n auto`，不得在常规 unit/integration 命令添加 `-n 0`。
- 只有 live、共享外部状态或竞态排查可串行，并必须在报告中解释原因。
- 不依赖 `jq` 或裸 `python` 命令；仓库脚本和文档示例使用 `python3` 或当前解释器变量。

### 3.5 单点完成模板

每个优化点只有满足以下条件才可由 `in_progress` 变为 `completed`：

1. 实现与本条“实施要求”逐项对应。
2. 针对性测试在默认并行配置下通过。
3. 相关旧测试通过，且没有通过删除断言来规避回归。
4. 用户可见行为已同步到指定文档。
5. 根代理的逐项审计记录完整。
6. 根代理复核 diff，确认未修改无关文件和未覆盖用户变更。

## 4. 依赖波次

已完成项视为依赖已满足，不再进入调度。波次 0 至波次 9 的 `PF-012`、`PF-013`、`PF-014`、`PF-016` 至 `PF-022` 已全部完成；`/goal` 已无剩余执行项。以下顺序保留为已执行的依赖记录：

| 波次 | 可调度优化点 | 进入条件 |
|---|---|---|
| 0 | PF-012 | 记录审计基线；PF-010 已完成 |
| 1 | PF-013 | PF-012、PF-015 已完成 |
| 2 | PF-014 | PF-013 完成 |
| 3 | PF-016 | PF-014 完成；PF-005、PF-015 已完成 |
| 4 | PF-017 | PF-016 完成 |
| 5 | PF-018 | PF-012、PF-017 完成；PF-004、PF-010、PF-011 已完成 |
| 6 | PF-019 | 所有用户可见功能稳定 |
| 7 | PF-020 | 文档结构稳定 |
| 8 | PF-021 | 全部实现、文档和打包任务完成 |
| 9 | PF-022 | CI 同步和本地完整验证通过 |

依赖表是硬约束。若发现未列出的依赖或文件重叠，继续串行并在 goal 进度中记录。

## 5. 原子优化点

### [x] PF-001：锁定审计事实和兼容性护栏

- **优先级**：P0
- **类型**：characterization tests，不修改生产行为
- **依赖**：无
- **主要文件**：新增聚焦的 unit/integration 测试文件；只在缺少覆盖时补充现有测试
- **问题映射**：4.4、4.5、4.6、6.3、6.4、7.4、8.1、9.2

**目标**

把审计中已经正确或被部分误判的行为固化为回归测试，确保后续代理不会重复实现、倒退或“修复”不存在的问题。

**实施要求**

- 断言 Wiley preview 不改变正文 `fetch/content` 成功，只在真实需要时表现为资产 preview/degraded 诊断。
- 断言 AMS Blank URL 被拒绝，lazy 真实 URL 和 `figure/formula/table` 分类保持有效。
- 断言 `batch_check(mode="metadata")` 只返回 `likely_yes/unknown`，不声称已验证全文。
- 断言 CLI 批量保持 1-based `index`，JSONL 完成顺序不等同输入顺序。
- 断言 cache 请求匹配继续校验 modes、strategy、include_refs 和 max_tokens。
- 断言 MCP batch 在 rate limit 后不再提交新任务。
- 断言 native `tools/list` 中 `strategy` 是对象；测试名称和失败信息明确区分 native schema 与 host 展示。
- 断言 source skill 的全部 references 会进入离线 staging；不得写成当前离线包只复制 `SKILL.md`。

**测试**

- 复用现有 fixture 和 mock，不新增 live 网络 fixture。
- 新增测试必须在 `PYTHONPATH=src python3 -m pytest tests/unit -q` 的并行配置下稳定。

**验收标准**

- 测试在任何后续生产改动前即通过。
- 测试失败信息能直接指出被破坏的既有契约。
- 生产代码 diff 为空。

**非目标**

- 不改变 preview、Blank URL、cache matcher、batch scheduler 或工具 schema。

### [x] PF-002：建立统一抓取验收模型

- **优先级**：P0
- **类型**：共享领域模型
- **依赖**：PF-001
- **主要文件**：`src/paper_fetch/workflow/acceptance.py`、`src/paper_fetch/workflow/__init__.py`、现有 model/output adapter、`tests/unit/test_workflow_acceptance.py`、架构文档
- **问题映射**：3.1、3.7、6.2、6.5、6.6、9.3、12.1 至 12.5

**目标**

从现有 `ArticleModel/Quality/TraceEvent/reason_codes` 派生唯一的 `FetchAcceptanceReport`，让 CLI、MCP、cache 和 manifest 对同一结果给出一致判定。

**实施要求**

- 至少提供 `overall`、`identity`、`fetch`、`content`、`asset`、`output`、`provenance` 七个分面。
- `overall` 使用稳定枚举：`complete`、`degraded`、`limited`、`failed`、`action_required`。
- `content` 明确区分 `fulltext`、`abstract_only`、`metadata_only`、`unavailable`。
- `fetch=ok` 只代表调用完成；metadata-only 可以是 `fetch=ok` 且 `overall=limited`。
- `asset_profile=none` 产生 `asset.requested=false` 和 `status=not_requested`，不能算失败；保留远程链接需单独字段说明。
- 分开报告 table layout degradation、table semantic loss、formula fallback/missing，不从 warning 文本猜分类。
- fallback/warning 分类从现有 trace outcome/code、quality flags、semantic losses 和 asset failures 派生。
- evaluator 必须是纯函数，不联网、不写盘、不重新抓取、不重复 provider 质量判断。
- 输出 schema 必须有版本字段和明确的向后兼容规则。

**测试**

- fulltext 完整成功、metadata-only、abstract-only、歧义、no_access、表格布局降级、表格语义损失、公式缺失、资产未请求、资产失败、输出缺失和 provenance 不完整矩阵。
- 同一 envelope 经不同 adapter 得到相同报告。
- 序列化和 JSON Schema 校验。

**文档**

- 在架构文档新增验收模型及状态组合说明。
- 明确 `status=ok`、`has_fulltext` 和 `overall` 是三个不同维度。

**验收标准**

- 任何调用方不再需要解析 warning 字符串来判断总体质量。
- 现有 Quality、TraceEvent 和 reason code 仍是底层事实源。

**非目标**

- 不在本任务修改 CLI JSONL、MCP 工具签名或资产下载实现。

### [x] PF-003：增加资产真实性验证和结构化资产摘要

- **优先级**：P0
- **类型**：共享资产质量能力
- **依赖**：PF-002
- **主要文件**：`src/paper_fetch/models/schema.py`、`src/paper_fetch/quality/`、`src/paper_fetch/artifacts.py`、现有 image payload/asset helper、相关 unit tests、`docs/extraction-rules.md`
- **问题映射**：6.1 至 6.4、6.6、6.7、12.3、13.6

**目标**

在不做视觉语义识别的前提下，对已下载资产建立保守、可解释、可序列化的真实性诊断，并把文本成功与资产成功彻底分开。

**实施要求**

- 复用 `filetype` 校验真实 MIME，复用 `imagesize` 获取尺寸，使用 `hashlib.sha256` 记录内容 hash。
- 记录请求 profile、逻辑 kind、下载 tier、路径、真实 MIME、字节数、宽高、hash、失败 code 和 provenance。
- 汇总 `requested`、`total`、`full_size`、`preview`、`failed`、`placeholder_suspected`，并按 `figure/formula/table/supplement/decoration` 分类。
- 对 Blank URL、极小尺寸、无效 MIME、零字节和多个不同逻辑正文图共享完全相同 SHA256 只生成保守的 `placeholder_suspected`，不得自动删除文件。
- `asset_profile=none` 的远程链接报告 `not_requested`；请求了资产但因 no-download/artifact policy 未归档时报告 `not_archived`。
- preview 可以是可用资产；只降低资产分面，不能直接把正文抓取改成失败。
- EPS/TIFF 转换失败后 JPG/PNG fallback 成功时保留 `conversion_degraded` provenance，不制造虚假的最终 asset failure。
- 如需要超出精确 hash 的图像能力，必须引入成熟库并说明依赖，禁止手写感知 hash 或图像解码器。

**测试**

- 有效 PNG/JPEG/SVG、伪扩展、零字节、Blank SVG、极小图、重复 hash、远程链接、缺失路径、preview、转换 fallback。
- AMS 正文图与公式分类、Wiley preview 回归。
- 旧 cache/旧模型字段缺失时的兼容反序列化。

**文档**

- 更新 extraction rules，说明哪些信号只是 suspected，哪些是确定失败。
- 明确图片可用性不等于正文完整性。

**验收标准**

- 统一验收报告可以直接消费资产摘要。
- 资产失败、未请求、未归档、preview 和完整资产可被机器区分。

**非目标**

- 不做 OCR、人工视觉判断、图像内容分类或自动删除。

### [x] PF-004：建立 CLI/MCP 共用 manifest 记录模型

- **优先级**：P0
- **类型**：纯模型和序列化层
- **依赖**：PF-002、PF-003
- **主要文件**：新增 `src/paper_fetch/manifest.py` 或同等清晰模块、JSON Schema 资源、model tests、架构文档
- **问题映射**：3.7、9.1 至 9.4、12.4、13.5

**目标**

建立单篇和批量共用的版本化 manifest record builder，后续 CLI 和 MCP 只调用这一实现。

**实施要求**

- 使用 Pydantic 或仓库现有结构模型，提供稳定 JSON Schema；不得用散落 dict 拼接字段。
- 至少包含 `schema_version`、`tool_version`、`run_id`、`record_id`、1-based `index`、`attempt`、原 query、规范化 identity、request fingerprint、开始/结束时间、source、acceptance、trace/fallback、warnings、asset summary、error 和 output artifacts。
- 每个 output artifact 至少记录 path、kind、size、SHA256、mtime/完成时间和验证状态。
- 保留现有 CLI JSONL 的九个旧字段作为兼容投影。
- 结构化 fallback/warning 复用 PF-002 和 trace，不新增基于消息子串的分类表。
- record builder 是纯逻辑；写盘、resume 和 reconcile 留给 PF-012。
- 时间、UUID 和文件 stat/hash 通过可注入依赖构建，保证测试确定性。

**测试**

- 完整成功、degraded、limited、失败、aborted、无输出、多资产、Unicode、稳定 round-trip、JSON Schema。
- 相同输入和固定 clock/UUID 生成稳定结果。

**文档**

- 记录 schema 版本策略、兼容字段和“记录状态不等于当前文件状态”。

**验收标准**

- CLI 和未来 MCP batch 无需各自维护字段清单。
- 所有旧 CLI JSONL 字段均可从新 record 获取。

**非目标**

- 不在本任务写 JSONL、run manifest 或实现 resume。

### [x] PF-005：修复 DOI 感知的本地 Markdown 与 cache 归属

- **优先级**：P0
- **类型**：cache 正确性和本地复用
- **依赖**：PF-001
- **主要文件**：`src/paper_fetch/mcp/cache_index.py`、`src/paper_fetch/mcp/fetch_cache.py`、front matter parser/helper、cache output schema、cache tests、相关文档
- **问题映射**：4.6、4.7、10.4、11.2

**目标**

使项目 `papers` 中可证明 DOI 归属的已核验 Markdown 成为一等本地来源，同时消除 refresh 时把目录内任意 loose Markdown 归给当前 DOI 的交叉污染风险。

**实施要求**

- 停止默认把同目录所有 `*.md` 归给正在 refresh 的 DOI。
- 保存 Markdown 时使用已知 DOI 和实际 saved path 显式注册 cache entry。
- 对既有本地 Markdown 使用结构化 YAML front matter parser，解析 DOI、source、has_fulltext/content_kind；不得用正则或全文字符串搜索猜 DOI。
- 优先复用已有 PyYAML；若生产代码需要，正式提升为 runtime dependency，不能依赖仅 dev 环境存在的包。
- DOI 比较复用 `normalize_doi()`，覆盖 DOI URL、大小写和合法特殊字符。
- preferred Markdown 只从可证明匹配 DOI 的条目选择，并优先当前有效 fulltext，再按完成时间选择。
- index schema 升级需提供旧版本迁移或明确 rescan 行为；不能静默保留错误归属。
- 现有 `cached_request_matches()` 继续负责请求兼容，不能在本任务另写宽松规则。
- 所有扫描限定在显式 `download_dir` 内，不跨目录、不联网。

**测试**

- 同目录两个 DOI、作者标题文件名、无关 Markdown、错误 DOI、坏 YAML、metadata-only、多个版本、旧 index、rescan、显式保存注册。
- 请求 DOI A 绝不能返回 DOI B 的 Markdown。
- cache miss 不触发网络。

**文档**

- 说明 index/refresh/rescan、本地 Markdown 证明条件、scope 和 preferred 选择规则。

**验收标准**

- `get_cached(doi, download_dir=papers)` 只返回身份可追溯的文件。
- 已有合格 fulltext 可供技能流程在联网前复用。

**非目标**

- 不建立全盘论文搜索器，不放宽 cache request 匹配。

### [x] PF-006：把 skill 重构为身份优先的工作流状态机

- **优先级**：P0
- **类型**：技能工作流
- **依赖**：PF-001
- **主要文件**：`skills/paper-fetch-skill/SKILL.md`、可新增 `references/workflow.md`、`tests/integration/test_skill_template.py`
- **问题映射**：3.2、3.3、4.1 至 4.3、4.7、4.9、10.1、10.2

**目标**

取消保存位置和 CLI/MCP 选择的无条件阻塞，把技能流程改为身份解析优先、任务意图驱动、后端自主选择、抓取后强制验收。

**实施要求**

- 唯一顺序为：输入规范化 -> resolve/batch_resolve -> DOI 去重 -> 仅歧义项阻塞 -> 本地/cache -> 意图 -> 后端 -> 必要状态检查 -> fetch -> acceptance -> report。
- 标题解析规则只定义一次；web search 只发现候选，标题不能直接传给 fetch。
- 去重前的原始条目数不能决定执行后端。
- 删除“>=3 篇必须等待用户选择 CLI/MCP”；批量本地归档默认 CLI，少量阅读/结构化抽取默认 MCP，用户明确禁止某后端时再切换。
- 只有多候选、身份不足、人工登录/授权、付费或合法访问边界、覆盖已有成果、会实质改变产物的选择才是 BLOCKING。
- “严格串行”改写为阶段依赖有序；同一阶段的多篇论文允许受控并发。
- 保存目录按“用户显式路径 -> 项目配置/唯一已有约定 -> 唯一合理 `papers/` -> 无法唯一确定才询问”推断，不写死不存在的历史仓库。
- 检查实际文件和验收结果，不能因目录被 gitignore 或 `git status` 无变化而判定失败。
- 保持 SKILL 入口精简，细节下沉到 reference。

**测试**

- 阶段顺序、BLOCKING 白名单、无硬编码三篇阈值、规则只定义一次、reference 链接存在。

**文档**

- 本任务本身即 skill 文档变更；更新相关技能模板测试。

**验收标准**

- 已授权且身份明确的批量归档无需额外后端选择往返。
- 抓取永远不是流程最后一步，后面必须出现验收与报告。

**非目标**

- 不在本任务改 CLI/MCP 代码或 provider 路由。

### [x] PF-007：定义任务预设、双执行面保存矩阵和本地优先策略

- **优先级**：P0
- **类型**：技能契约
- **依赖**：PF-005、PF-006
- **主要文件**：新增 `skills/paper-fetch-skill/references/presets.md`、`SKILL.md`、`tool-contract.md`、CLI reference、`docs/cli.md`、技能测试
- **问题映射**：3.4 至 3.6、4.6 至 4.8、10.3、10.4、11.1 至 11.5

**目标**

把自然语言意图唯一映射为显式 CLI/MCP 参数，彻底区分“不保存最终 Markdown”“不建立用户归档”“不写 provider artifact”“允许 cache”和“不做任何写盘”。

**实施要求**

- 至少定义五个预设：临时阅读、可缓存阅读、单篇本地归档、批量可读性分诊、批量本地归档。
- 临时阅读 MCP 显式设置 `save_markdown=false`、`no_download=true`、`artifact_mode=none`、`strategy.asset_profile=none`；引用范围按任务显式设置。
- 可缓存阅读 MCP 显式设置 `save_markdown=false`、`no_download=false`、`artifact_mode=none`、`strategy.asset_profile=none`。
- 文本归档默认不隐式下载图片；CLI 必须显式 `--artifact-mode none --asset-profile none`，使用 `--output/--output-dir` 作为主 Markdown 输出。
- 用户明确请求正文图时显式 `asset_profile=body`，请求补充材料时显式 `all`；相应 artifact mode 也必须显式。
- MCP 归档明确 `save_markdown/no_download/artifact_mode/markdown_output_dir/strategy.asset_profile`，不得把 CLI `--no-download` 语义套到 MCP。
- 所有 CLI 示例显式写 `--artifact-mode` 和 `--asset-profile`；本任务默认不改变公开运行时默认值。
- 本地/cache 决策树为：已核验本地 fulltext -> 同 scope 精确 DOI cache -> 匹配请求的 prefer-cache fetch -> 正常抓取。
- 已知 DOI 使用 `get_cached` 而不是全量 `list_cached`，并始终传相同 `download_dir`。
- 超过 50 条的分诊按原 index 分块合并；metadata probe 不写成已经抓取全文。
- 文档示例使用 `python3` 或 CLI 自身，不依赖 `jq`。

**测试**

- CLI/MCP 写盘矩阵：临时阅读、cache-only、主输出、额外保存、none/body/all。
- 临时目录断言实际产物，而不是根据参数名推断。
- 本地 fulltext 命中时不联网；不匹配 cache 正常进入 fetch。

**文档**

- 在 reference 中给出两张独立矩阵：CLI 输出/落盘矩阵和 MCP 输出/落盘矩阵。

**验收标准**

- 任一预设都没有依赖隐藏默认值。
- “不保存”和“完全不落盘”不再混用。

**非目标**

- 不在本任务改变 CLI/MCP 全局默认值。

### [x] PF-008：统一批量分诊、并发和代理级重试规则

- **优先级**：P1
- **类型**：工作流与故障契约
- **依赖**：PF-006、PF-007、PF-011
- **主要文件**：`SKILL.md`、`references/failure-handling.md`、`tool-contract.md`、`src/paper_fetch/mcp/prompts.py`、相关测试
- **问题映射**：4.3 至 4.5、4.10、5.1、11.4

**目标**

让技能和 MCP prompts 对 probe、真实 fetch、阶段并发、限流和重试使用同一套可执行决策表。

**实施要求**

- 说明 `batch_check(metadata)` 是 likely probe，`batch_check(article)` 会实际抓取，二者成本和证据等级不同。
- 说明单次最多 50 条、超过限制如何按原 1-based index 分块并恢复顺序。
- 区分“阶段有序”和“阶段内并发”，不写死未经证实的默认并发 3。
- 定义代理级“初次尝试 + 最多 2 次有意义的重试”，并与底层 HTTP Retry-After/5xx retry 分层。
- ambiguous/参数错误/确定性解析错误不盲目重试；no_access 在认证状态不变时不重试；rate_limited 尊重 Retry-After 并停止相同 provider 新提交；browser transient 只有参数、状态或环境发生变化才重试。
- 默认本来就是 `prefer_cache=false` 时，不能把同参数再跑描述为“绕过缓存”。
- 每类失败都必须有触发条件、参数变化、终止条件和用户报告字段。
- prompt 不得把 metadata `likely_yes` 写成已验证 `has_fulltext`。

**测试**

- skill/prompt 静态契约覆盖所有 error category、50 条分块、likely probe、限流和总尝试次数。

**文档**

- failure handling 成为唯一重试事实源，SKILL 只链接，不重复长规则。

**验收标准**

- 同一失败不会因 SKILL、prompt 和 reference 表述不同而采取冲突动作。

**非目标**

- 不修改底层 HTTP retry 算法，不自动 auth。

### [x] PF-009：重构可发现且兼容的 CLI 命令面

- **优先级**：P1
- **类型**：CLI UX 和兼容层
- **依赖**：PF-007
- **主要文件**：`src/paper_fetch/cli.py`、CLI tests、`docs/cli.md`
- **问题映射**：3.5、5.2、13.2、13.4

**目标**

让 `paper-fetch --help` 直接展示 fetch、auth、browser-preflight 和后续 manifest/doctor 扩展入口，同时保留现有根级 fetch 参数的兼容性。

**实施要求**

- 使用 argparse 的标准 subparser/父 parser 机制，不继续扩展手写 argv 特判。
- 提供明确的 `fetch`、`auth`、`browser-preflight` 命令结构，并预留 `manifest`、`doctor` 注册点。
- 现有 `paper-fetch --query ...` 和 query-file 调用至少保留一个兼容周期，行为、退出码和 stdout/stderr 契约不变。
- 顶层 help 列出子命令用途，子命令 help 显示有效默认、枚举和落盘影响。
- `--no-download` 明确是 CLI artifact-mode alias，不承诺阻止显式主输出或 save-markdown。
- `--asset-profile` 当前公开默认保持兼容；agent-facing 示例全部显式传参。
- 错误参数必须由 argparse/结构校验统一返回，不再因 argv 分支产生不同格式。

**测试**

- 顶层和各子命令 help 快照、legacy 调用、退出码、未知命令、冲突参数、stdout/stderr。
- 现有 CLI unit 全量回归。

**文档**

- 更新 CLI 入口、兼容期、保存矩阵和示例。

**验收标准**

- 不读源码即可发现 auth 和 browser-preflight。
- 旧 fetch 命令仍可运行。

**非目标**

- 不在本任务实现 manifest resume、doctor 内容或改变默认资产策略。

### [x] PF-010：升级 CLI 单篇/批量结果为 manifest schema v2

- **优先级**：P0
- **类型**：CLI 结果契约
- **依赖**：PF-003、PF-004、PF-009、PF-011
- **主要文件**：`src/paper_fetch/cli.py`、manifest adapter/writer、CLI tests、`docs/cli.md`
- **问题映射**：3.7、9.1 至 9.3、12.4、13.2、13.5

**目标**

让 CLI JSONL 可以回答工具是否运行、是否全文、资产是否可用、输出是否与记录一致，同时保留旧消费者和完成顺序流式输出。

**实施要求**

- 使用 PF-004 builder；禁止在 CLI 再维护一份字段拼装逻辑。
- 保留 `index/query/status/doi/source/output_path/saved_markdown_path/warnings/error`。
- 新增 schema/tool version、run/record id、attempt、时间、request fingerprint、acceptance、trace/fallback、semantic losses、asset summary 和 output artifact size/SHA256。
- `status=ok` 保持“调用未抛异常”的旧语义；metadata-only 仍可是 ok，但 acceptance 必须是 limited。
- JSONL 继续按完成顺序流式写入，稳定 1-based index 不变；文档明确消费者按 index 关联输入。
- 采用 PF-011 增量 runner；每个输入最终必须有唯一终态记录，未调度项写 `aborted`，保证 `query_count == record_count == unique_index_count`。
- 单篇新增显式 `--manifest <path>`；默认不写 manifest，避免普通 stdout 阅读新增隐式落盘。
- hash/size 必须在最终原子写入完成后计算；失败记录字段结构保持一致并允许 null。
- 退出码继续由工具失败/aborted 决定，不能把所有 degraded 自动升级为非零。

**测试**

- fulltext、preview、metadata-only、资产失败、none、异常、aborted、输出 hash、固定 clock/UUID。
- 刻意乱序完成，验证行顺序可乱但 index 完整唯一。
- legacy 字段、退出码和单篇默认不落 manifest 回归。

**文档**

- 发布 JSONL v2 字段表、兼容策略、完成顺序和示例。

**验收标准**

- 只读 JSONL 即可区分 complete/degraded/limited/failed。
- 输出路径、size 和 SHA256 描述同一时刻的最终文件。

**非目标**

- 不在本任务实现跨进程 resume/reconcile。

### [x] PF-011：抽取共享增量 batch runner 和 provider-aware 限流

- **优先级**：P0
- **类型**：共享并发基础设施
- **依赖**：PF-001
- **主要文件**：新增 `src/paper_fetch/workflow/batch_runner.py`、`src/paper_fetch/mcp/batch.py`、runner tests、架构文档
- **问题映射**：4.3、4.4、8.4、9.2

**目标**

把 MCP 已有的增量提交、取消、限流停止和结果恢复逻辑抽为 CLI/MCP 共用 runner，并支持按 provider lane 控制新任务。

**实施要求**

- runner 支持全局最大 worker、provider/resource key、每 lane 上限、完成 callback、progress callback、停止谓词、取消事件和可注入 clock。
- 只维持有限 in-flight 项，禁止一次性提交整个批次。
- 相同 provider rate limit 后停止该 lane 新提交并记录 Retry-After/cooldown；不相关 provider 可继续。
- 并发上限保持公开的 `1..8`，不把默认值武断改为 3。
- 输入顺序结果和完成顺序 event/callback 分开表达。
- worker 异常、取消和未调度项必须产生结构化终态。
- 先迁移现有 MCP batch 使用共享 runner，保持当前结果、progress 和 rate-limit 行为；CLI 由 PF-010 接入。
- 复用现有 retry/reason code，不复制第二套线程池状态机。

**测试**

- 刻意乱序、输入保序结果、完成 callback、provider lane、rate limit、Retry-After、取消、worker 异常和未调度项。
- 现有 MCP batch 测试全部通过。

**文档**

- 架构文档说明阶段有序、批内受控并发和 provider lane。

**验收标准**

- MCP 和 CLI 只有一个 batch 调度实现。
- rate limit 不会继续淹没相同 provider。

**非目标**

- 不承诺通过运行历史自动学习最佳并发，不做跨运行全局限流服务。

### [x] PF-012：实现 run manifest、只读 reconcile 和安全 resume

> **执行状态：已完成（2026-07-13）。** 已复用 v2 record builder、统一 acceptance、PF-005 YAML front matter parser、共享 batch runner、`ArtifactStore` 和 `FileLock`，新增 run persistence、audit/reconcile、resume/overwrite 及 CLI 命令；聚焦测试 `34 passed`，CLI/manifest/runner/架构相关回归 `142 passed, 19 subtests passed`，完整 unit `2050 passed, 1 skipped, 1 warning, 430 subtests passed`，CLI 与架构文档已同步。完整 unit 首轮发现输出目录内多出 artifact lock 的产品契约回归；实现改为使用 `platformdirs` 用户 runtime 锁目录并新增无输出锁文件断言，未放宽既有测试。架构回归另校正了两个由既有 `presets.md` 和当前 CLI 顶层描述引起的陈旧快照，没有改变对应生产行为。

- **优先级**：P0
- **类型**：可恢复性和可重复性
- **依赖**：PF-010
- **主要文件**：manifest persistence 模块、`src/paper_fetch/cli.py`、`ArtifactStore`/file lock adapter、CLI tests、`docs/cli.md`
- **问题映射**：9.1、9.4、11.5、12.4、13.5

**目标**

使批量归档真正可恢复、可审计，并能发现 JSONL 与后来被覆盖的 Markdown 不一致，而不是只提供一个看似可重跑的命令。

**实施要求**

- 每次 run 建立原子 `run-manifest.json`，包含 run id、tool version、完整有序输入、配置/request fingerprint、开始/完成时间、状态统计和结果 event 路径。
- 结果采用 append-only attempt records；`record_id` 至少由 run/index/attempt 唯一确定，最新终态可重建。
- `paper-fetch manifest audit/reconcile` 默认只读，校验输入数、index 完整唯一、文件存在、size/hash、front matter DOI/source/content、request fingerprint 和 acceptance。
- 结构化 parser 复用 PF-005 front matter helper，不得用 regex。
- reconcile 输出稳定 JSON 报告和退出码，明确 `manifest_stale` 原因；默认不改 manifest、不联网、不自动修复。
- `--resume` 只跳过 request fingerprint 相同且 output hash/acceptance 仍满足的项；missing/stale/degraded-below-request 项产生新 attempt。
- 输入或关键配置 fingerprint 不同必须拒绝静默 resume，并提示创建新 run。
- 覆盖已有合格输出必须显式 `--overwrite`；写入使用 `ArtifactStore`、临时文件、原子替换和现有 `FileLock`。
- interrupted/cancelled run 必须持久化可恢复状态。
- 单篇 `--manifest` 与批量记录使用同一 audit 逻辑。

**测试**

- 中断后恢复、缺文件、覆盖、hash 改变、错误 DOI、重复 index、合法乱序、参数变化、并发写、manifest 写失败。
- resume 不重复抓取已验证项，stale 项产生新 attempt。

**文档**

- 完整说明 run 目录布局、状态机、audit/reconcile 只读语义、resume 和 overwrite。

**验收标准**

- 当前文件状态与历史记录不一致时可稳定检测。
- 同一 run 可在异常退出后继续，且不会误跳过 stale 文件。

**非目标**

- 不自动编辑用户 Markdown，不跨机器同步 run。

### [x] PF-013：分层 provider 状态、配置来源和本地能力诊断

> **执行状态：已完成。** 保留无参 `provider_status()` 的全 catalog 顺序与原 full checks；新增筛选、来源/本地能力边界、内置 doctor、schema/stdio 契约、测试和文档，未使用子代理、网络页面或自动安装。

**完成记录（2026-07-13）**

- `paper_fetch.diagnostics` 成为 CLI/MCP 的共享静态诊断 owner；provider 与 group 均从 runtime catalog 派生，compact 每项只返回五个路由字段，full 保留原 checks 并附配置来源、browser 与 image capabilities。异常文本被脱敏为异常类型，配置报告只输出 key/source/presence/default/sensitive。
- `config.resolve_runtime_env()` 保留 process > explicit file > env-var file > user config > default 的来源元数据；Elsevier catalog/onboarding manifest 同步声明 `ELSEVIER_API_KEY`。`static_browser_capabilities()` 只做 import/config 探测，明确 `live_checked=false`；Ghostscript/libvips 复用原候选、缓存与 subprocess helper，区分 ready/missing/timeout/error。
- MCP `provider_status(provider, group, detail)` 的 native/host-safe/stdio schema 均公开动态 provider enum、group/detail enum，非法值在调用前失败；内置 `paper-fetch doctor` 支持 provider/group/detail/env-file/JSON 并保留 registrar 替换能力；当时为 PF-020 预留的 provenance 段现已由 PF-020 实现。
- 更新 `docs/cli.md`、`docs/providers.md`、`docs/deployment.md`、`docs/architecture/overview.md` 和 skill `environment.md`，统一写明 status/doctor（静态）→ preflight（live）→ auth（人工副作用），并记录图片后端与远端资产 reason 的边界。
- 验证：聚焦 unit `279 passed, 66 subtests passed`；manifest/catalog 同步 `72 passed, 33 subtests passed`；stdio MCP/schema integration `2 passed`；完整 unit `2071 passed, 1 skipped, 1 warning, 438 subtests passed`；相关 Ruff、定向 mypy、compact doctor smoke、`git diff --check` 通过。全量 integration/devtools/build/install 留给 `PF-021` / `PF-022`，live publisher/browser 页面测试按非目标未运行。
- 全量 mypy 当前只报告既有 `auth.py:229` 六个邻近类型错误；PF-013 没有为隐藏该问题修改断言、串行测试或放宽类型配置，按严格波次留给 `PF-021` 收口。PF-013 未修改 CI，CI 同步仍只在 `PF-021` 执行。

- **优先级**：P1
- **类型**：CLI/MCP diagnostics
- **依赖**：PF-003、PF-009、PF-012、PF-015
- **主要文件**：provider status/fetch tool、`browser_preflight.py` 邻近 helper、image tools paths/convert、`mcp/server.py`、output schemas、CLI doctor 注册、tests、environment/providers docs
- **问题映射**：5.1 至 5.3、6.7、7.5

**目标**

明确区分静态配置就绪、本地依赖就绪和真实网页链路健康；让调用方只查询目标 provider，并能诊断配置来源和图片转换后端。

**实施要求**

- `provider_status(provider=None, group=None, detail="full|compact")` 支持筛选；默认无参数仍返回全部 provider，保持兼容。
- status 明确标注为静态配置/依赖检查，不宣称 Chrome、CDP 或出版社网页实际健康。
- compact 只返回任务路由需要的 provider、状态、关键 reason 和建议动作；full 保留现有 checks。
- 报告配置值来源层级：process env、显式/env-var 文件、user config、default；只报告 source 和是否存在，绝不回显 token/cookie/secret 值。
- 复用现有 image tool/runtime helper，探测 Ghostscript、libvips、Playwright/Cloakbrowser、Chrome/CDP 配置的本地可用性。
- EPS/TIFF 后端缺失与远端资产失败必须使用不同 reason code。
- CLI `doctor --json` 汇总静态诊断，为 PF-020 预留 install/version provenance 段。
- 非法 provider/group/detail 在结构校验阶段失败。

**测试**

- 默认全量、单 provider、group、compact/full、非法值、配置优先级、秘密不泄漏、各图片后端存在/缺失/超时。
- 全部使用 mock，不做 live 页面访问。

**文档**

- 更新 environment/providers/deployment，给出 status -> preflight -> auth 的分层入口。

**验收标准**

- 单篇任务无需接收 19 个 provider 的完整诊断。
- 用户能区分“已配置”和“真实页面可访问”。

**非目标**

- 不在 provider_status 发网络请求，不自动安装系统工具。

### [x] PF-014：把现有 browser preflight 暴露为 MCP 工具

> **执行状态：已完成（2026-07-13）。** MCP tool/adapter 直接调用既有 `run_browser_provider_preflight()`；共享核心只增加可选目标、storage-state 写入开关、逐项 callback 和取消结果，不复制 browser workflow。五类逐 provider 状态、open-world 非只读 annotations、progress/cancel、native/host-safe/stdio schema、structured output、无 PDF fallback/自动 auth 边界及 CLI/MCP/skill/架构文档均已验证；默认测试未访问外部网络或浏览器。

- **优先级**：P1
- **类型**：MCP 新工具
- **依赖**：PF-013
- **主要文件**：复用 `src/paper_fetch/browser_preflight.py`，新增轻量 MCP adapter，`mcp/server.py`、schemas/output schemas、unit/integration tests、tool contract
- **问题映射**：5.1、5.2、13.7

**目标**

让 MCP 用户在真实 browser provider fetch 前执行与 CLI 相同的 live preflight，而不是误用 provider_status 作为健康证明。

**实施要求**

- 新增 `browser_preflight` tool，直接调用现有 `run_browser_provider_preflight()` 或公开等价 API；不得复制浏览器流程。
- 支持目标 provider/测试 URL、必要的 storage-state 选项和结构化 detail；默认行为与 CLI 保持一致。
- annotations 正确声明 open-world 和可能写 storage-state，不能伪装成纯只读。
- 支持 progress、取消、逐 provider 结果；一个 provider challenge 不得抹掉其他已完成结果。
- 结果区分 ready、challenge、auth_required、runtime_error、cancelled，并给出下一步，不进入 PDF fallback。
- auth 保持显式人工入口，不尝试绕过 challenge。

**测试**

- mock ready、challenge、auth required、逐 provider 继续、取消、storage-state 写盘和无 PDF fallback。
- stdio MCP integration 验证工具注册、schema、annotations 和 structured output。

**文档**

- CLI/MCP 契约写清 status、preflight、auth 的顺序和副作用。

**验收标准**

- CLI 和 MCP 使用同一个 preflight 核心实现。
- 默认测试无需外部网络或浏览器。

**非目标**

- 不默认运行 live preflight，不自动 auth。

### [x] PF-015：补全 native schema 并提供 Codex host-safe 输入契约

- **优先级**：P1
- **类型**：MCP schema
- **依赖**：PF-002
- **主要文件**：`src/paper_fetch/mcp/schemas.py`、`mcp/server.py`、schema tests/snapshots、tool contract
- **问题映射**：8.1、13.3

**目标**

让 native MCP 和 Codex host 都能看到关键 enum、数组长度、数值范围和 strategy 结构，同时保留 Pydantic 运行时规范化。

**实施要求**

- 为 modes、include_refs、asset_profile、artifact mode、batch mode、cache detail/mode 使用 `Literal`/Enum 和 `Field` 约束。
- 公开 schema 必须显示 queries `minItems=1/maxItems=50`、concurrency `minimum=1/maximum=8` 和 `additionalProperties=false`。
- 保留 `FetchStrategyInput` 的结构模型；不得因 host 显示问题退化为无类型 dict。
- 先分别快照 native FastMCP 内部 schema、stdio `tools/list` 和 host-safe 规范化结果，再修 Codex 展示兼容。
- host-safe 方案必须使用 FastMCP/Pydantic 的受支持 API；若 nested `$ref` 确实无法被 host 展开，可提供向后兼容的 inline/flat adapter，但既有 nested 请求仍须接受。
- host-safe schema 不得包含无法解析的引用；native schema 仍须是合法 Draft 2020-12 JSON Schema。
- 大小写/别名规范化继续在 Pydantic validator 中完成，schema 约束不能替代运行时校验。

**测试**

- input schema 快照、stdio tools/list、所有 enum/range/maxItems、extra forbid、legacy nested request、非法值调用前失败。
- 测试名称明确说明 native 与 host-safe 层，不能用一个快照代表两层。

**文档**

- tool contract 说明两层 schema、兼容字段和约束事实源。

**验收标准**

- native `strategy` 仍是 object。
- Codex-facing schema 不再把 strategy 显示为无约束 unknown，关键选项可自动补全。

**非目标**

- 不修改仓库外 Codex host，不通过超长 description 补偿弱 schema。

### [x] PF-016：增加紧凑且请求敏感的 cache 查询

> **执行状态：已完成（2026-07-13）。** `get_cached` 的默认 full 响应保持兼容，新增 compact/preferred-only 视图、与 fetch 对齐的请求参数、manifest canonical fingerprint、统一 acceptance/asset/warning 摘要与显式 sidecar 状态。实现严格调用既有 `cached_request_matches()`，并用 `request_satisfied` 区分“存在归属可证的 index entry”与“当前请求可复用”；旧版/损坏/错 DOI/错 scope/无归属证据都不会被升级为请求命中。工具契约、workflow/presets、provider 与架构文档均已同步。

- **优先级**：P1
- **类型**：MCP cache contract
- **依赖**：PF-005、PF-014、PF-015
- **主要文件**：`mcp/cache_payloads.py`、`mcp/fetch_cache.py`、`mcp/output_schemas.py`、`mcp/server.py`、cache tests、tool contract
- **问题映射**：4.6、8.5、11.2

**目标**

让常规 cache-first 决策只返回优选条目和质量摘要，同时保留完整模式和严格请求兼容判断。

**实施要求**

- `get_cached` 新增 `detail="full|compact"` 和 `preferred_only`；默认 `full` 保持现有响应。
- compact 至少返回 DOI、scope/download_dir、index status、preferred Markdown/primary payload、content kind、has_fulltext、confidence、acceptance 摘要、asset 摘要、warnings 分类、cached request 和稳定 fingerprint。
- compact 不返回完整正文或全量资产数组，除非调用方显式 full。
- 明确区分“cache 中有条目”和“该条目满足当前请求”；兼容判断必须调用现有 `cached_request_matches()`。
- 损坏 sidecar、旧 cache version、错误 scope 和无法证明 DOI 归属必须显式报告，不能伪装 hit。
- 保留源码已有的 `list_cached.cache_mode`，不要因活动 2.8.0 安装缺少该参数而重复添加另一实现。

**测试**

- full/compact/preferred_only、modes/strategy/include_refs/max_tokens 不匹配、旧版本、损坏 sidecar、wrong scope、无网络。
- 默认 full 字段兼容。

**文档**

- 说明 compact 是索引/sidecar 摘要，不自动证明满足任意未来请求。

**验收标准**

- 技能常规 cache 检查不需要把全部 entry 塞入上下文。
- 严格匹配行为没有放宽。

**非目标**

- 不跨 download_dir 搜索，不让 cache miss 变成失败。

### [x] PF-017：动态 provider catalog resource 和 MCP 上下文预算

> **执行状态：已完成（2026-07-13）。** 新增的 provider catalog resource 每次读取都直接从已发现 `ProviderSpec` 和 `SOURCE_PROVIDER_MAP` 派生，没有维护第二张 provider/source 表；动态注册变化、resource manager 和独立 stdio `resources/read` 均有回归。Server instructions 只保留整体安全/副作用边界，fetch/tool description 只保留用途、关键默认、写盘/网络边界与 resource URI；逐 provider 路线已从 MCP 文案和 tool contract 移除。四类字符预算、host narrative 与单独 native tools-list/schema 字节快照已纳入测试，并在架构/provider/tool-contract 文档记录。

- **优先级**：P1
- **类型**：MCP resource 与上下文优化
- **依赖**：PF-015、PF-016
- **主要文件**：`src/paper_fetch/provider_catalog.py`、轻量 MCP catalog payload、`mcp/server.py`、`mcp/_instructions.py`、resource/description tests、tool contract
- **问题映射**：8.2、8.3

**目标**

把 provider/source/capability 明细移到机器可读动态 resource，缩短 server instructions 和工具描述，并建立可持续预算。

**实施要求**

- 新增 `resource://paper-fetch/provider-catalog`，完全从 runtime provider catalog/source map 派生。
- resource 至少包含 schema/tool version、provider、sources、browser/runtime 能力、资产默认、status/preflight 能力；不得维护第二张静态表。
- 新 provider 或 source map 变化时，resource 测试自动反映；文档只描述如何读取 resource。
- server instructions 只保留总体边界；工具 description 只保留用途、副作用、关键默认和 resource URI。
- 删除 instructions、fetch description 和 tool-contract 中重复的逐 provider 路线。
- 建立独立预算：server instructions `<=1500` 字符，`fetch_paper` description `<=1200` 字符，全部工具 description 合计 `<=5000` 字符。
- 另记录 `tool_count * instructions_length + descriptions_length` 的 host narrative 展开值，并设 `<=24000` 字符预算；schema 字节量单独快照，不与文案混算。
- minified native `tools/list` 总大小建立快照和有解释的增长阈值，避免新增工具后无界膨胀。

**测试**

- resource/stdin resources/read 与 runtime catalog 精确一致。
- provider docs facts、description budget、host narrative budget、tools/list size snapshot。

**文档**

- tool contract 改为动态 catalog 权威说明，不再复制 19 个 provider。

**验收标准**

- provider 信息只维护在 runtime catalog。
- 描述明显缩短且未丢失写盘、安全和默认值边界。

**非目标**

- 不把 provider catalog 重新包装成长工具描述，不改变 provider 路由。

### [x] PF-018：新增结构化 `batch_fetch` MCP 工具

> **执行状态：已完成（2026-07-13）。** 已新增第十个 typed `batch_fetch` MCP 工具；adapter 直接复用共享 runner、manifest record builder、PF-012 persistence/audit/resume 与单篇 fetch/save 语义，没有另建 batch 或 manifest 状态机。结果按输入 index 排列并单列 completion metadata，默认 compact、可选 batch-wide bounded 内容；progress、协作式取消、provider lane 限流、continue-on-error、cache hit、保存/不落盘、overwrite/resume、cancelled/interrupted 完整终态与资源 URI 均有无 live 回归，工具/schema/context 快照和契约文档已同步。

- **优先级**：P1
- **类型**：MCP 新工具
- **依赖**：PF-004、PF-010、PF-011、PF-012、PF-017
- **主要文件**：新增 MCP batch fetch adapter、`mcp/server.py`、schemas/output schemas、MCP unit/integration tests、tool contract
- **问题映射**：8.4、9.4、11.5

**目标**

为 MCP 提供受控并发、可取消、可恢复、结果紧凑的批量全文抓取能力，使代理无需解析非结构化 CLI stdout。

**实施要求**

- 输入复用 `FetchPaperRequest` 语义和 PF-015 typed schema，queries `1..50`、concurrency `1..8`。
- 复用 PF-011 runner、PF-004 record builder 和 PF-012 run persistence；禁止另建 batch 状态机。
- 支持 progress、cooperative cancellation、rate-limit lane abort、continue-on-error 和 interrupted manifest。
- response 按输入 index 排列，同时保留 completion metadata；每项返回 compact manifest/acceptance 摘要。
- 默认不把多篇完整 Markdown 塞入 MCP 上下文；临时阅读可返回有限内容，归档模式返回路径/resource URI。
- 保存和不落盘矩阵必须与 PF-007 一致；输出目录和 overwrite/resume 语义与 CLI 共用。
- 每个输入都必须有终态 record，且 run id、request fingerprint、输出 hash 可追溯。
- 现有 9 个工具行为不变；工具数快照、描述预算和 catalog 资源同步更新。

**测试**

- stdio tools/list/schema、乱序并发、输入保序、progress、取消、rate limit、cache hit、保存/不落盘、resume、部分失败和完整 index 集合。
- 不依赖 live publisher。

**文档**

- tool contract 说明 batch_fetch 与 CLI 的选择边界、50 条限制和 compact response。

**验收标准**

- MCP 批量抓取不需要代理自己拼线程或解析 CLI 文本。
- 批次中断后保留可审计、可恢复状态。

**非目标**

- 不移除 CLI 批量能力，不返回无限正文集合。

### [x] PF-019：重建 skill/reference 信息架构和安装内链接完整性

> **执行状态：已完成（2026-07-13）。** 正常 CLI 单篇/批量/manifest/resume 路径已从误导性的 `cli-fallback.md` 迁到自包含 `cli-workflow.md`，只保留真正的窄 fallback；新增 acceptance reference，SKILL 直接导航全部七个关键 reference。环境优先级、offline wrapper、Chrome/CDP、Ghostscript/libvips、formula/image 工具和诊断入口已补齐且不写 secret 值；MCP prompts 与普通 tools 已分离并给出无 prompt 宿主的等价流程，provider/source 只指向动态 catalog。`markdown-it-py` AST 链接检查已覆盖 source、offline staging 和实际 installer 临时副本，主 docs 交叉链接同步且 bundle 不依赖仓库 `docs/`。

- **优先级**：P1
- **类型**：文档收口
- **依赖**：PF-007、PF-008、PF-013、PF-014、PF-016、PF-017、PF-018
- **主要文件**：`skills/paper-fetch-skill/SKILL.md`、全部 skill references、`docs/cli.md`、`docs/providers.md`、`docs/deployment.md`、文档测试
- **问题映射**：7.1 至 7.6、10.3、13.1

**目标**

让安装后的 skill 自包含、入口精简、职责清楚，正常 CLI 批量流程不再被叫作 fallback，关键 tool contract 可发现且无断链。

**实施要求**

- 将正常 CLI 工作流与故障 fallback 分开；重命名或拆分 `cli-fallback.md`，所有引用原子更新。
- 删除安装后指向不存在仓库 `docs/` 的相对链接；skill reference 只链接 bundle 内存在文件，或复制必要的精简内容而非整套 docs。
- `SKILL.md` 正式链接 workflow、presets、acceptance、tool-contract、failure-handling、environment 和 CLI workflow。
- 明确 `summarize_paper`、`verify_citation_list` 是 MCP prompts，不是普通 tools；不支持 prompts 的宿主给出等价工具流程。
- environment 说明进程环境 > 显式/env-var 文件 > 用户配置 > default，以及 offline wrapper 默认指向 `offline.env` 的行为。
- 补全 Ghostscript/libvips、formula/image tools、CDP/Chrome 相关变量和诊断入口，不包含 secret 值。
- provider 列表只指向动态 catalog resource，不复制静态表。
- 示例不依赖 `jq`，使用 `python3`；说明被 gitignore 的文件仍需按路径/hash/acceptance 验收。
- 使用成熟 Markdown parser 做 repo source、skill staging 和安装副本的相对链接检查，不用 regex 提取链接。

**测试**

- source skill 所有相对链接解析成功、无孤儿关键 reference、SKILL 保持薄入口、prompt/tool 表述、环境事实、CLI 示例显式 asset/artifact 参数。

**文档**

- 同步主 docs 的交叉链接，但避免维护重复 provider facts。

**验收标准**

- source、staging 和安装后的 skill 均可独立导航。
- 不存在名为 fallback 却承担正常批量主路径的文档。

**非目标**

- 不把完整仓库 docs 全部塞进 skill bundle。

### [x] PF-020：版本、离线 bundle 和活动 skill 的可验证 provenance

> **执行状态：已完成（2026-07-13）。** 以初始 source `3.0.1`、distribution metadata `3.0.0`、PATH CLI `2.8.0` 漂移为输入，最终选择并准备 `3.1.0`；manifest schema 3、共享逐文件 skill hash 校验、POSIX/Windows 前后验证和机器可读 doctor provenance 已落地。wheel/sdist、clean venv 与临时 CPython 3.14 offline build/install 已通过，活动安装仍保持旧版并留给 PF-022。

- **优先级**：P0
- **类型**：打包、诊断和版本发布准备
- **依赖**：PF-019
- **主要文件**：POSIX/Windows offline build/installer/verifier、installer tests、CLI doctor/version helper、`pyproject.toml`、`src/paper_fetch/config.py`、`CHANGELOG.md`、`CHANGELOG_CN.md`、deployment docs
- **问题映射**：7.4、7.5、8.5 的版本漂移部分、审计基线错误

**目标**

让 source distribution、offline manifest、runtime、User-Agent 和三个宿主 skill 副本的版本/文件 hash 可被一条机器可读诊断证明一致。

**实施要求**

- offline manifest 增加 skill bundle 文件清单和每文件 SHA256，并保留 git revision、target、Python tag 和 build time。
- 安装前后验证全部 skill/reference 文件及 hash，不只检查 `SKILL.md`；POSIX 和 Windows 行为一致。
- `doctor --json`/版本 provenance 汇总 distribution version、`DEFAULT_USER_AGENT`、offline manifest version/revision、entrypoint、skill manifest 和指定 install root 的一致性。
- source 开发环境无 offline manifest 时报告 `not_applicable`，不能误报失败。
- 明确区分 source `3.0.1` 与活动安装 `2.8.0`，诊断必须直接指出 drift 和对应路径。
- 根据新增向后兼容功能按 SemVer 准备 minor 版本；基于当前基线目标为 `3.1.0`。若执行期间 HEAD 已高于该版本，不得降级，并记录最终选择。
- 同步 `pyproject.toml`、`DEFAULT_USER_AGENT`、中英文 changelog 和 deployment 版本清单；版本事实不得散落手工不同步。
- 使用现有 build/install scripts 和 checksum 机制扩展，不新写平行安装器。
- 在临时输出目录构建 wheel/sdist 和离线包，不把生成物留在工作树。

**测试**

- 一致、runtime 旧版、manifest 旧版、skill hash 漂移、缺 reference、source 开发环境、POSIX/Windows manifest、临时安装。
- `python3 -m build` 和 clean venv console script smoke。

**文档**

- deployment 说明 provenance 字段、升级和 host 重启边界。

**验收标准**

- 临时安装可证明 runtime、UA、manifest 和 skill hash 同版。
- 旧活动安装漂移可被诊断但尚不在本任务直接覆盖；实际 rollout 留给 PF-022。

**非目标**

- 不后台自动升级，不在本任务删除当前活动安装或用户配置。

### [x] PF-021：补齐跨执行面测试并同步 GitHub CI

> **执行状态：已完成（2026-07-13）。** 既有单点矩阵作为显式 CI 门复用，只新增四 adapter acceptance 与真实 source/staging/temp-install skill/provenance 两个缺口；全量轻量门和独立 clean-venv package smoke 已通过，未触发 GitHub CI 或 live 测试。

- **优先级**：P0
- **类型**：测试与 CI 收口
- **依赖**：PF-001 至 PF-020
- **主要文件**：跨层 unit/integration tests、`.github/workflows/ci.yml`、CI workflow contract tests、必要测试 docs
- **问题映射**：13.1 至 13.7、AGENTS.md 的 CI 同步要求

**目标**

补齐单点测试未覆盖的跨执行面契约，并使 GitHub CI 与本地验证命令一致，同时保持 live/offline 重任务的既有触发边界。

**实施要求**

- 增加 CLI help/input/output schema、MCP input/output schema、description budget、resource catalog 和 skill links 的稳定快照或结构断言。
- 增加 CLI/MCP 落盘矩阵：临时阅读、cache-only、主输出、save-markdown、none/body/all、batch_fetch。
- 增加 batch 乱序、完整 index、rate limit、cancel、manifest stale、reconcile、resume 和 output hash 端到端测试。
- 增加 source/staging/temp-install skill hash、版本 provenance、完整 references 和链接测试。
- 增加 acceptance 在 CLI/MCP/cache/manifest 四个 adapter 间一致的契约测试。
- CI lint job 保持 ruff/mypy，integration job 运行 integration，package-smoke 验证 wheel 和 console scripts；将新增轻量检查接入对应 job。
- 重型 offline jobs 和 live tests 保持现有 tag/workflow_dispatch 边界，不让普通 push 意外运行 live publisher。
- 更新 CI workflow contract tests，防止后续删除关键步骤。
- 不通过 `-n 0` 绕过并发失败；若发现竞态，应修实现或测试隔离。

**测试**

- `PYTHONPATH=src python3 -m pytest tests/unit -q`
- `PYTHONPATH=src python3 -m pytest tests/integration -q --durations=30`
- `PYTHONPATH=src python3 -m pytest tests/devtools -q --durations=30`
- `python3 -m ruff format --check .`
- `python3 -m ruff check .`
- `PYTHONPATH=src python3 -m mypy`
- `python3 scripts/validate_extraction_rules.py --ci`

**文档**

- 更新测试/部署说明，列清本地门、CI 门和 opt-in live 门。

**验收标准**

- 本地全部轻量门通过。
- workflow 与本地门一致，但本任务没有 push 或触发 GitHub CI。

**非目标**

- 不运行付费、认证或不稳定出版社 live 测试。

### [x] PF-022：根代理独立终验、当前安装升级和 goal 收尾

> **执行状态：已完成（2026-07-13）。** 未使用终验子代理；根代理通过重新审阅、fresh process、临时 HOME/install root 和独立 MCP client 完成独立终验，并将活动安装从 `2.8.0` 安全升级到 `3.1.0`。

- **优先级**：P0
- **类型**：独立审计与本地 rollout
- **依赖**：PF-021
- **主要文件**：原则上不修改源码；只使用现有 build/install/verify 命令和必要的临时目录
- **问题映射**：全部优化点的最终证明

**目标**

由根代理按独立检查清单重新审阅全部条目，使用 fresh process、临时 HOME/install root 和独立 MCP client 先验证临时安装，再安全消除当前活动 `2.8.0` runtime/skill 漂移，最后提供可复核交付报告。

**实施要求**

- 重新读取本文逐项核对，不以“测试绿”替代需求验收。
- 运行完整 `scripts/dev-preflight.sh`；同时确认完整 unit 命令确实按仓库 `-n auto` 配置执行。
- 运行 `python3 -m build`、clean venv wheel smoke、离线 package verify、临时 HOME/install-root 安装和独立 MCP stdio smoke。
- 临时安装必须先证明目标版本、User-Agent、offline manifest、skill file list/hash、CLI help、10 个预期 MCP tools、prompts/resources 和关键 schema 一致。
- 只有源码、测试、package、临时安装全部通过后，才可处理当前活动安装。
- 读取当前 Codex MCP 配置指向和 install root，使用仓库已有受支持 installer/update 路径；不得手工复制零散 runtime 文件。
- 更新活动安装前创建可回滚备份，保留现有 `offline.env` 自定义值、cache、downloads、storage-state 和凭证；不得清空用户数据。
- 重装 Codex、Claude、Antigravity 三个 skill 副本，并逐文件比对 manifest/hash。
- 更新后验证 PATH CLI、distribution metadata、User-Agent、offline manifest 和活动 skill 都是 PF-020 确定的目标版本，不再残留 `2.8.0` entrypoint。
- 用独立 MCP client 进程连接已安装 `paper-fetch-mcp`，检查 tools/list、resources/list/read、schema 和 compact call；当前 Codex 会话无法热重载不算失败，但最终报告必须提示新会话加载。
- 如终验发现行为缺陷，根代理必须重新打开对应 PF，在该 PF 的文件范围内直接修复并重跑其针对性门；不得把缺陷笼统并入 PF-022 后跨所有权重写。
- 终验结束检查 `git status --short`，确认只有预期源码/文档/CI 修改和用户原有变更，没有 dist、cache、临时包或备份落入仓库。

**完成证据**

- `PYTHON_BIN=python3 bash scripts/dev-preflight.sh` 全部通过；pytest 复用 `pyproject.toml` 的 `-n auto`，结果为 unit `2166 passed, 1 skipped, 1 warning, 444 subtests passed`、integration `195 passed, 132 skipped, 9 subtests passed`、devtools `39 passed, 4 subtests passed`，Ruff、mypy、文档规则和 diff whitespace 同时通过。
- PF-021 的 wheel/sdist clean-venv smoke 在最终源码上通过；PF-022 另在仓库外构建 CPython 3.14 Linux 离线包，并用 `PAPER_FETCH_OFFLINE_SKIP_FETCH_SMOKE=1 scripts/verify-offline-package.sh` 验证校验和、网络/构建命令 guard、安装、skill provenance、入口、本地 smoke、卸载和 purge。最终包 SHA256 为 `424cca3540caa1fe32a9d81da6e76e6645c3fb9d37ccd5fb6e9302b4608c556c`。
- 首个候选包继承旧活动 PATH 后把 `texmath` 打成指向旧安装的绝对符号链接，临时验证因旧目标仍存在而通过，但活动原位 smoke 以 `Too many levels of symbolic links` 正确拒绝。根代理未接受该结果；先从回滚备份恢复活动工具，再使用隔离 PATH 和既有 Cabal 缓存调用原构建脚本重建。最终 staging、临时安装和活动安装的 `texmath` 均为 mode `0755` 的普通 ELF 文件，版本 `0.13.1.2`；该纠偏只改变临时产物和安装状态，未修改源码。
- 最终包在第二个全新临时 HOME/install root 再次通过 installer smoke、manifest schema 3、版本/UA `3.1.0`、四份 skill 各 8 文件完整性校验和独立 MCP stdio；实测 10 tools、2 prompts、2 静态 resources、1 template、19 providers、33 sources，全部输入 schema 禁止 extra、全部输出 schema 含 `schema_version`，batch 上限和 compact `provider_status` 正常。
- rollout 前将完整旧活动安装、paper-fetch 用户 data/cache/config、三宿主 skill/MCP 配置、shell 配置以及旧 Miniforge editable distribution/入口点备份到 `/home/dictation/.local/state/paper-fetch-skill/rollout-backups/20260713T101744Z-2.8.0-to-3.1.0`；备份父目录 mode 为 `0700`，约 711 MiB。受支持离线 installer 随后完整通过活动安装 smoke。
- 活动 `paper-fetch --version`、私有 distribution metadata、默认 UA、offline manifest schema 3、git revision `10e30297df2cc7c354c1cb407a8514b22d2800d8`、四份 skill hash 和三宿主 MCP command 均为/指向 `3.1.0`；`doctor --json --install-root` 返回 `ready`。PATH 只剩活动安装的四个入口，旧 Miniforge `2.8.0` editable distribution/入口已移除且 `pip check` 无破损依赖。
- 自定义 dotenv 值只做 secret-safe 指纹比较：`CROSSREF_MAILTO`、`ELSEVIER_API_KEY`、`WILEY_TDM_CLIENT_TOKEN` 三项升级前后 SHA256 一致；downloads、全局 data/cache/config 的 `rsync --checksum` 差异均为 0，浏览器状态文件计数升级前后均为 44，`offline.env` mode 保持 `0600`。
- 活动安装的独立 MCP client 再次通过 tools/prompts/resources/schema/catalog/compact call；所有 PF022 测试、构建、安装和独立 MCP 子进程均已退出，仓库外临时目录已清理，回滚备份未落入仓库。live publisher/auth 未运行，GitHub CI 未触发；Codex、Claude、Antigravity 的既有进程需新会话重载新 skill/MCP。

**最终命令集**

~~~bash
PYTHONPATH=src python3 -m pytest tests/unit -q
PYTHONPATH=src python3 -m pytest tests/integration -q --durations=30
PYTHONPATH=src python3 -m pytest tests/devtools -q --durations=30
python3 -m ruff format --check .
python3 -m ruff check .
PYTHONPATH=src python3 -m mypy
python3 scripts/validate_extraction_rules.py --ci
python3 -m build
~~~

**验收标准**

- 所有命令成功，且没有仍运行的 process/session。
- 临时安装和当前活动安装均通过 provenance、skill hash 和 MCP stdio 验证。
- 未运行的 live tests 明确列为未运行及原因，不能写成通过。
- 最终报告包含每个 PF 编号、修改文件、测试结果、复核证据和残余风险。
- 根代理复核报告后才可将 `/goal` 设为 complete。

**非目标**

- 不 commit、push、tag、publish release 或触发 GitHub CI。
- 不运行 auth、不抓取真实付费论文、不修改用户凭证。

## 6. 最终交付报告格式

根代理完成 `/goal` 时使用以下结构，缺一项不得结束：

~~~text
目标状态
- 审计前已完成：PF-001 至 PF-011、PF-015（12 项；本 goal 未重复实现）
- 本 goal 完成：PF-012、PF-013、PF-014、PF-016 至 PF-022（10 项）
- 总体：PF-001 至 PF-022 全部 completed（存在 blocked 时只能将 goal 标记为 blocked，不能提交完成报告）
- 最终版本：<version>
- source revision：<sha>

实现摘要
- 工作流与预设：...
- 验收与资产：...
- CLI/MCP：...
- manifest/resume：...
- 文档/打包/CI：...

验证
- unit：<结果>
- integration：<结果>
- devtools：<结果>
- ruff/mypy/docs：<结果>
- wheel/offline/temp install：<结果>
- active install provenance：<结果>
- installed MCP stdio：<结果>

未运行
- live publisher/auth tests：<原因>

工作树
- 预期修改：<文件摘要>
- 用户原有修改：<保留说明>
- 意外生成物：none

剩余风险
- 仅列依赖外部出版社、账号、浏览器会话或新 Codex 会话加载的风险。
~~~

如果任一 required 验收未完成、存在未处理失败、活动安装仍指向旧 runtime，或仍有必要的命令在运行，则不得宣告 goal 完成。
