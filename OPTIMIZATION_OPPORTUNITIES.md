# 项目优化机会汇总

生成日期：2026-07-03

本文汇总对当前项目各模块的只读分析结果，覆盖 providers、HTML/Markdown 提取、MCP/service/cache、安装与发布、测试与 CI。本文不代表已经实施变更，仅作为后续优化 backlog。

## 执行 Runbook

本节把后续优化拆成可用 `/goal` 逐步执行的任务队列。每个 goal 都应独立可交付、可验证，并在完成后更新本文对应状态或在 changelog / docs 中同步说明。默认不要触发 GitHub CI；本地验证默认复用 `pyproject.toml` 的 pytest 配置并保持并行执行。

### 使用规则

1. 每次只启动一个 goal，不要把多个不同风险面的任务揉在一起。
2. goal 开始前先读本节的“全局检查清单”和对应 goal 的“范围 / 步骤 / 验证 / 完成标准”。
3. 若执行中发现比当前目标更严重的阻断问题，只记录到本文“新发现”或对应 backlog，不在同一 goal 中顺手重构。
4. 修改代码后同步文档；修改测试或 CI 后同步本地命令与 GitHub Actions 配置。
5. 常规 unit 验证使用 `PYTHONPATH=src python3 -m pytest tests/unit -q`。仅 live 测试、共享外部状态测试或排查顺序/竞态时才使用 `-n 0`，并在结果中说明原因。
6. 完成 goal 前至少运行对应小范围测试；若跳过完整 unit，需要在结果中说明原因和残余风险。

### 全局检查清单

1. 读取 `AGENTS.md`、`pyproject.toml`、目标模块和已有相关测试。
2. 运行 `git status --short`，确认工作区已有用户改动；不要还原无关改动。
3. 用 `rg` 定位调用点、测试、文档，不凭文件名猜测影响面。
4. 优先复用已有 helper、类型、fixture、测试模式；禁止为已有成熟功能重新手写平行实现。
5. 更新文档时至少检查 `README.md`、`docs/`、`CHANGELOG.md`、`CHANGELOG_CN.md` 是否需要同步。
6. 最终结果记录：改动摘要、验证命令、未验证项、后续建议。

### 全量串行总控模式

复制下面的 `/goal` 作为全量优化入口：

```text
/goal 按 OPTIMIZATION_OPPORTUNITIES.md 的“全量串行总控模式”执行全量优化：从第一个未完成的 Gxx 开始，每轮只完成一个 Gxx；每个 Gxx 先按“子代理拆分矩阵”派发小模块子代理，再由主代理整合方案、实施代码和文档改动、运行验证、回填状态；不要触发 GitHub CI；遇到跨 goal 的新问题只记录，不顺手扩 scope。
```

总控状态机：
1. 定位第一个没有“状态：YYYY-MM-DD 已完成”的 Gxx；若上一个 Gxx 是“部分完成”，先继续该 Gxx。
2. 读取该 Gxx 的范围、步骤、验证、完成标准，以及下方“子代理拆分矩阵”的对应行。
3. 派发子代理。子代理默认先只读审计，输出证据、建议补丁边界、测试建议；如果 host 支持子代理改代码，只允许修改该子代理声明的文件集，且不得与其他子代理并行修改同一文件。
4. 主代理汇总所有子代理输出，去重后形成本轮实施计划。若子代理结论冲突，优先选择更小变更面、更符合现有架构和测试模式的方案。
5. 主代理实施改动并同步文档。跨模块公共 helper 只能由主代理创建或修改，避免多个子代理并行产生重复抽象。
6. 运行该 Gxx 的小范围验证；必要时再运行完整 unit：`PYTHONPATH=src python3 -m pytest tests/unit -q`。
7. 将状态写回该 Gxx 下方，并在最终回复中报告验证结果、未验证项和下一个建议执行的 Gxx。
8. 只有当前 Gxx 满足完成标准后，下一轮 `/goal` 才进入下一个 Gxx。

子代理输出模板：

```markdown
### 子代理结果：<Gxx>/<模块名>

结论：<可执行结论，最多 5 条>
证据：<文件/函数/测试引用>
建议改动：<按文件列出>
测试建议：<最小测试集合>
风险：<兼容性、性能、行为变更>
是否阻塞主 goal：是/否；原因：<如适用>
```

主代理整合模板：

```markdown
Gxx 执行汇总

采用的子代理建议：<列表>
未采用的建议：<列表和原因>
实际改动：<文件/行为>
验证：<命令和结果>
状态回填：<已完成/部分完成/阻塞>
下一步：<下一个 Gxx 或阻塞解除条件>
```

### 子代理拆分矩阵

| Goal | 子代理小模块 | 子代理任务 | 主代理整合重点 |
|---|---|---|---|
| G01 | workflow 触发条件 | 只读解析 `.github/workflows/ci.yml` 的 `on`、job `if`、tag/dispatch 路径。 | 统一 offline job 条件，避免普通 push/PR 触发重型 job。 |
| G01 | workflow 测试 | 审计 `test_ci_release_workflow.py` 的 YAML 解析方式和断言缺口。 | 用结构化测试守住 Linux/macOS/Windows offline job。 |
| G01 | CI 文档 | 检查 README/docs 是否描述 CI/offline 触发策略。 | 同步“默认不触发重型 CI”的用户可见说明。 |
| G02 | runtime cache | 审计 `RuntimeContext` cache 字段、锁、访问器和现有测试。 | 设计与 `session_cache` 对齐的锁和原子 `get_or_set`。 |
| G02 | provider cache users | 审计 Elsevier/Springer/browser workflow 的 `get_or_set_parse_cache` 使用和 `copy_value` 语义。 | 决定可变对象是否复制、只读或加测试约束。 |
| G02 | 并发测试 | 查找现有 batch/runtime 并发测试模式。 | 用 barrier/event 写确定性并发测试。 |
| G03 | MCP schema | 审计 `output_schemas.py`、result envelope、文档示例。 | 定义版本字段和兼容默认值。 |
| G03 | error mapping | 审计 `results.py` 中异常到 payload 的映射。 | 保留 `code/http_status/retry_after/provider/source_trail/warnings`。 |
| G03 | batch abort | 审计 `batch.py` 的限流中止语义。 | 改为机器可读 `error_category` / retry-after 判定。 |
| G04 | waterfall runner | 审计 `_waterfall.py`、`combine_provider_failures()` 和末位 step 行为。 | 统一失败聚合、retry-after、warnings、source trail。 |
| G04 | provider routes | 分 provider 审计 Elsevier/Springer/Copernicus/IEEE/Oxford/PLOS/Frontiers 的 route 和 `continue_codes`。 | 建立参数化 route 契约测试。 |
| G04 | PDF fallback artifacts | 审计 PDF fallback text-only/artifact 逻辑是否与 route 聚合耦合。 | 只处理必要的错误语义，较大 artifact helper 可留给后续。 |
| G05 | IR table renderer | 审计 `extraction/markdown_render` 的 `MarkdownTable`、`render_table`、formatter。 | 选择 canonical formatter 并消除 raw pipe 拼接。 |
| G05 | provider table paths | 审计 JATS/Elsevier/Atypon/arxiv/generic table 输出路径。 | 保证同一 mini table 输出一致。 |
| G05 | table tests | 搜索现有 table 单测和 golden fixture。 | 补 pipe/newline/ragged/header/fallback 覆盖。 |
| G06 | formula | 审计 inline TeX、MathML、IR 渲染分支。 | 修正 inline `$...$`，保持 display 行为。 |
| G06 | figure/formula assets | 审计 formula image 判定、figure context、共享 URL 去重。 | 调整判定顺序，防止 figure 被公式规则删除。 |
| G06 | citation | 审计 `markdown/citations.py`、section renderer、Atypon normalization。 | 抽 canonical node payload helper。 |
| G07 | cache index | 审计 index version、list/get/rescan 语义。 | 版本校验和 list/get 行为对齐。 |
| G07 | resolve | 审计 `ResolvePaperRequest` 到 resolve engine 的数据流。 | 让 title/authors/year 保持结构化。 |
| G07 | metadata merge | 审计 workflow merge 与 `metadata/types.py` rule 差异。 | 建立单一 merge 事实源。 |
| G08 | image fetch budget | 审计 browser image fetch 策略链和 timeout。 | 引入单图总预算和 fake page 测试。 |
| G08 | PDF warm | 审计 PDF warm context 是否执行完整 HTML 抓取。 | 增加轻量 warm/seed 路径，减少重复导航。 |
| G08 | browser tests | 查找 browser workflow fake/mocking 模式。 | 用 fake context 验证预算和导航次数。 |
| G09 | image tools | 审计 Ghostscript/libvips 探测、glob、tool env。 | 缓存 binary 探测和 env 计算。 |
| G09 | formula tools | 审计 texmath/mathml worker、subprocess 调用和缓存。 | 先补调用次数测试，再决定 worker/批处理。 |
| G09 | PDF common | 审计 PDF hash、页数 guard、subprocess monkeypatch。 | 缓存同一 PDF 转换并缩小污染窗口。 |
| G10 | cold import | 用 import-time 或静态路径审计 `trafilatura`/`idutils` import。 | 惰性化重依赖并加 smoke。 |
| G10 | provider discovery | 审计字符串发现、memoization、provider catalog 调用。 | 改 AST/manifest/cache，避免重复读盘。 |
| G10 | client contract | 审计 browser providers 的字符串 `waterfall_steps` 和基类契约。 | 删除/改名/改成真实 `WaterfallStep` 并加契约测试。 |
| G11 | mypy coverage | 统计 `[tool.mypy].files` 覆盖和高风险漏项。 | 扩覆盖并新增覆盖清单守卫。 |
| G11 | coverage/ruff | 审计 coverage fail-under、B023 ignore、相关测试。 | 设置可执行门槛并收窄 ignore。 |
| G11 | preflight/CI | 对比 CI 与 `scripts/dev-preflight.sh` 命令。 | 统一命令事实源。 |
| G12 | env key matrix | 列出 POSIX/Windows/root PS1/MCP 的 env key 差异。 | 用 manifest/template 统一 key 集。 |
| G12 | activate safety | 审计 `activate-offline.sh` source 外部 env 的路径。 | 改安全解析或限定 trusted source。 |
| G12 | installer docs/tests | 审计 README/docs/installer tests/verify 脚本。 | 同步用户文档和 fake HOME 测试。 |

### 串行执行门禁

每个 Gxx 完成前必须通过这些门禁：
1. 子代理输出齐全：该 Gxx 在“子代理拆分矩阵”中的所有小模块都有结果；不适用的小模块需说明原因。
2. 主代理有整合记录：采用/未采用建议有理由，公共 helper 没有重复实现。
3. 验证命令已运行：至少运行 Gxx 指定小范围测试；若测试不可运行，必须说明环境原因。
4. 文档已同步：本文 Gxx 状态已回填，必要时 README/docs/changelog 已更新。
5. 工作区可解释：`git status --short` 中所有与 Gxx 相关的改动都能说明用途，无关用户改动未被触碰。

### 全量完成标准

当 G01-G12 全部完成后，启动最后一个收尾 `/goal`：

```text
/goal 按 OPTIMIZATION_OPPORTUNITIES.md 的“全量完成标准”执行收尾审计：确认 G01-G12 均已完成，运行完整 unit 验证，检查 README/docs/CHANGELOG/CHANGELOG_CN 是否同步，生成最终风险报告；不要触发 GitHub CI。
```

收尾验证：
1. `PYTHONPATH=src python3 -m pytest tests/unit -q`
2. 若 G11 已统一 preflight，则运行新的本地 preflight fast 命令。
3. 对涉及 extraction/provider 的 goal，按变更范围补跑相关 integration/golden 子集；完整 golden 仅在有明确需要时运行并记录耗时。
4. `git status --short` 中只保留本轮预期改动。

全量完成输出：
1. G01-G12 状态清单。
2. 所有验证命令及结果。
3. 未完成或延期项。
4. 仍需人工决策的架构问题。
5. 建议是否提交，以及提交前是否需要用户明确同意运行更重验证。

### 队列概览

1. G01：限制普通 push/PR 触发 offline/release 矩阵。
2. G02：加固 `RuntimeContext.parse_cache` 并发语义。
3. G03：为 MCP 输出增加 schema/error 契约。
4. G04：统一 provider fallback `continue_codes` 与失败聚合。
5. G05：修正 Markdown table IR 渲染边界。
6. G06：修复 inline TeX、figure/formula、citation 的确定性输出 bug。
7. G07：修正 cache index / resolve / metadata merge 语义漂移。
8. G08：收敛 browser image/PDF warm 的超时预算。
9. G09：缓存 image/formula/PDF 工具链重复开销。
10. G10：清理 provider registry、`waterfall_steps` 契约和冷启动。
11. G11：扩大 mypy/coverage/preflight 质量门禁。
12. G12：统一安装器 env/MCP 事实源和安全边界。

### G01：限制普通 push/PR 触发 offline/release 矩阵

`/goal` 目标：让普通 `push` / `pull_request` 只运行常规质量门，offline/release 构建只在 tag 或手动 dispatch 下运行，并用单元测试守住 workflow 条件。

范围：
- `.github/workflows/ci.yml`
- `tests/unit/test_ci_release_workflow.py`
- 必要时同步 `README.md` / `docs/deployment.md` 的 CI 说明

步骤：
1. 解析当前 workflow 的 `on`、offline Linux/macOS/Windows、package-smoke、release jobs 条件。
2. 明确常规 job 与 offline/release job 的触发策略：普通 push/PR 不跑 offline；`refs/tags/v*` 和 `workflow_dispatch` 可以跑。
3. 给所有 offline jobs 添加一致 `if` 条件，尤其补齐 Windows offline job。
4. 更新或新增 YAML 结构测试，避免只做脆弱字符串包含。
5. 同步文档中“提交默认不触发重型 CI”的说明。

验证：
- `PYTHONPATH=src python3 -m pytest tests/unit/test_ci_release_workflow.py -q`
- 如 workflow 测试依赖 YAML 解析，也运行相关 CI/workflow 测试文件。

完成标准：
- 普通 push/PR 不满足 offline jobs 条件。
- tag / workflow_dispatch 路径仍能运行 offline/release。
- 测试覆盖 Linux、macOS、Windows offline jobs。

状态：2026-07-03 已完成，提交/变更：offline Linux/macOS/Windows job 统一限制为 `refs/tags/v*` 或手动 `workflow_dispatch`，Windows 补齐 job-level `if`；新增 YAML 结构测试覆盖 push/PR/tag/dispatch、Windows-only dispatch、package-smoke 和 release job 条件；同步 README、deployment、architecture 与双语 changelog 的 CI 触发策略；验证：`PYTHONPATH=src python3 -m pytest tests/unit/test_ci_release_workflow.py -q`、`PYTHONPATH=src python3 -m pytest tests/unit/test_human_docs_drift.py tests/unit/test_scaffold_docs_sync.py -q`、`python3 -m ruff check tests/unit/test_ci_release_workflow.py`；残余风险：未实际触发 GitHub Actions 验证 tag/dispatch 运行时行为（按要求不要触发 GitHub CI）。

### G02：加固 `RuntimeContext.parse_cache` 并发语义

`/goal` 目标：让 `parse_cache` 与 `session_cache` 一样具备线程安全访问和原子 `get_or_set`，并明确可变对象缓存边界。

范围：
- `src/paper_fetch/runtime.py`
- Elsevier / Springer / browser workflow 中使用 `get_or_set_parse_cache` 的路径
- `tests/unit/` 中 runtime、workflow、batch 或 provider cache 相关测试

步骤：
1. 对比 `session_cache` 锁实现，给 `parse_cache` 增加同级别锁。
2. 将 `get_parse_cache`、`set_parse_cache`、`get_or_set_parse_cache` 调整为锁保护；`get_or_set` 必须避免 check-then-act 重复写。
3. 审计 `copy_value=False` 使用点，确认缓存对象是否只读；必要时改为复制或增加注释/测试。
4. 新增并发测试：同 key 多线程调用 supplier，断言 supplier 调用次数和返回对象语义符合预期。
5. 覆盖 `copy_value=True` 与 `copy_value=False` 两种路径。

验证：
- `PYTHONPATH=src python3 -m pytest tests/unit -q -k "parse_cache or runtime or batch"`
- 若新增压力测试不稳定，先用确定性 barrier/event 控制并发，不使用 sleep 猜时间。

完成标准：
- `parse_cache` 所有访问器持锁。
- `get_or_set_parse_cache` 对同 key 原子。
- 测试能复现并守住并发语义。

状态：2026-07-03 已完成，提交/变更：`RuntimeContext.parse_cache` 增加 `RLock` 与同 key in-flight 协调，`get_parse_cache` / `set_parse_cache` / `get_or_set_parse_cache` 均通过访问器持锁，`get_or_set` 并发同 key 只执行一次 supplier；保留 Elsevier XML root `copy_value=False` 只读复用语义并补近端注释和测试；新增 runtime parse cache 并发测试覆盖 `copy_value=True` 与 `copy_value=False`；同步 architecture 与双语 changelog；验证：`PYTHONPATH=src python3 -m pytest tests/unit/test_runtime_parse_cache.py tests/unit/test_elsevier_markdown.py -q`、`PYTHONPATH=src python3 -m pytest tests/unit -q -k "parse_cache or runtime or batch"`、`PYTHONPATH=src python3 -m pytest tests/unit/test_human_docs_drift.py tests/unit/test_scaffold_docs_sync.py -q`、`python3 -m ruff check src/paper_fetch/runtime.py src/paper_fetch/providers/elsevier.py tests/unit/test_runtime_parse_cache.py tests/unit/test_elsevier_markdown.py`；残余风险：`parse_cache` 仍是 dataclass 字段，直接外部读写该 dict 不经过锁，现有代码路径已改为通过访问器约束。

### G03：为 MCP 输出增加 schema/error 契约

`/goal` 目标：给 MCP top-level 输出增加版本字段，并保留机器可读错误细节，避免限流和 provider 失败信息丢失。

范围：
- `src/paper_fetch/mcp/output_schemas.py`
- `src/paper_fetch/mcp/results.py`
- `src/paper_fetch/mcp/batch.py`
- MCP 相关 tests / snapshots / docs

步骤：
1. 设计 `schema_version` 或 `contract_version` 的位置和初始值。
2. 扩展错误输出字段：`code`、`http_status`、`error_category`、`retry_after_seconds`、`provider`、`warnings`、`source_trail`。
3. 修改异常到 MCP payload 的转换，避免把细粒度 code 全折叠为 `ERROR`。
4. 修改 batch abort 判定：按 error category / retry-after / rate-limit 字段，而不是只认字符串 `RATE_LIMITED`。
5. 更新 schema tests、MCP output tests、文档示例。

验证：
- `PYTHONPATH=src python3 -m pytest tests/unit -q -k "mcp or batch or output_schema or results"`

完成标准：
- 成功和失败 payload 都包含版本字段。
- 429 / `RATE_LIMITED` / provider failure 的机器可读细节进入输出。
- batch 遇到限流能按契约中止并保留 retry-after。

状态：2026-07-03 已完成，提交/变更：MCP tool payload 统一注入顶层 `schema_version=1`，`error_payload_from_exception` 保留旧 `status` / `reason` 同时输出 `code`、`http_status`、`error_category`、`retry_after_seconds`、`provider`、`warnings`、`source_trail`；direct MCP payload helper 与 FastMCP `structuredContent` / text content 共用版本化 payload；batch sync/async runner 改为按 rate-limit status/code/category、HTTP 429 或 retry-after 中止并保留 `abort_reason` 细节；output schema、MCP instructions、architecture 与双语 changelog 已同步；新增/更新 MCP schema、错误映射、sync/async batch retry-after 回归测试；验证：`PYTHONPATH=src python3 -m pytest tests/unit -q -k "mcp or batch or output_schema or results"`、`PYTHONPATH=src python3 -m pytest tests/unit/test_provider_docs_facts.py tests/unit/test_human_docs_drift.py -q`、`python3 -m ruff format --check src/paper_fetch/mcp/results.py src/paper_fetch/mcp/batch.py src/paper_fetch/mcp/fetch_tool.py src/paper_fetch/mcp/cache_payloads.py src/paper_fetch/mcp/output_schemas.py src/paper_fetch/mcp/_instructions.py tests/unit/_mcp_support.py tests/unit/test_mcp_batch_resolve_payloads.py tests/unit/test_mcp_async_tools.py tests/unit/test_mcp_payload_cache.py`、`python3 -m ruff check src/paper_fetch/mcp/results.py src/paper_fetch/mcp/batch.py src/paper_fetch/mcp/fetch_tool.py src/paper_fetch/mcp/cache_payloads.py src/paper_fetch/mcp/output_schemas.py src/paper_fetch/mcp/_instructions.py tests/unit/_mcp_support.py tests/unit/test_mcp_batch_resolve_payloads.py tests/unit/test_mcp_async_tools.py tests/unit/test_mcp_payload_cache.py`、`git diff --check`；未触发 GitHub CI；残余风险：ProviderFailure 结构本身仍不稳定承载 `provider/http_status`，当前 MCP 层只透传已有/可选属性，provider fallback 聚合的更深层语义留给 G04。

### G04：统一 provider fallback `continue_codes` 与失败聚合

`/goal` 目标：让 HTML/XML -> PDF fallback 的继续策略、最终错误码、warnings、`source_trail` 在 provider 间一致。

范围：
- `src/paper_fetch/providers/_waterfall.py`
- `src/paper_fetch/providers/base.py`
- Elsevier、Springer、Copernicus、IEEE、Oxford、PLOS、Frontiers provider
- provider waterfall / PDF fallback tests

步骤：
1. 列出现有 provider 的 route 顺序、`continue_codes`、末位 step 行为和 final failure 构造方式。
2. 定义统一继续策略，至少覆盖 `NO_RESULT`、`NO_ACCESS`、`RATE_LIMITED`、`ERROR` 的预期。
3. 修正 `combine_provider_failures()`：限流 retry-after 合并、空 failures 兜底、warnings/source_trail 去重、优先级注释清晰。
4. 让末位 step 失败也进入聚合路径，避免丢失前序上下文。
5. 将 PLOS/Frontiers 是否迁移到 `WaterfallStep` 作为本 goal 的可选子项；若影响过大，先补契约测试和 TODO。

验证：
- `PYTHONPATH=src python3 -m pytest tests/unit -q -k "waterfall or provider_failure or fallback or pdf"`

完成标准：
- 参数化测试覆盖各 provider 在四类错误码下是否进入 PDF step。
- 最终错误包含前序 route 上下文、warnings、source trail、retry-after。
- Springer 两个入口策略不再自相矛盾。

状态：2026-07-03 已完成，提交/变更：`WaterfallStep` 默认继续策略统一为 `DEFAULT_WATERFALL_CONTINUE_CODES`，覆盖 `NO_RESULT`、`NO_ACCESS`、`RATE_LIMITED`、`ERROR` 等 provider 失败码；`combine_provider_failures()` 增加空 failures 兜底、稳定去重 warnings/source_trail/missing_env，并跨失败聚合 retry-after；`run_provider_waterfall()` 对短路失败和自定义 final failure 回填 state 中的前序 warnings/source_trail/missing_env/retry-after，成功路径 warnings 也稳定去重；Elsevier XML/PII XML 失败现在允许 `NO_ACCESS` 继续官方 PDF fallback，Springer raw/fetch_result 两入口通过统一默认策略保持一致；`ArtifactStore.apply_provider_artifacts()` 解耦 skip warning 与 skip trace，Oxford Academic PDF text-only artifact 也补齐 skip marker；PLOS/Frontiers 暂不迁移到 `WaterfallStep`，改用参数化契约测试守住现有手写 fallback 行为；同步 architecture、providers 文档与双语 changelog；新增 provider PDF fallback route contract 测试覆盖 Elsevier、Springer、Copernicus、Oxford、PLOS、Frontiers 在 `NO_RESULT`/`NO_ACCESS`/`RATE_LIMITED`/`ERROR` 下进入 PDF step，并补 runner 聚合与 artifact skip trace 测试；验证：`PYTHONPATH=src python3 -m pytest tests/unit/test_provider_fetch_result_template.py tests/unit/test_provider_payloads.py tests/unit/test_provider_pdf_fallback_route_contract.py -q`、`PYTHONPATH=src python3 -m pytest tests/unit -q -k "waterfall or provider_failure or fallback or pdf"`、`PYTHONPATH=src python3 -m pytest tests/unit/test_provider_docs_facts.py tests/unit/test_human_docs_drift.py -q`、`python3 -m ruff format --check src/paper_fetch/providers/base.py src/paper_fetch/providers/_waterfall.py src/paper_fetch/providers/elsevier.py src/paper_fetch/providers/oxfordacademic.py src/paper_fetch/artifacts.py tests/unit/test_provider_fetch_result_template.py tests/unit/test_provider_payloads.py tests/unit/test_provider_pdf_fallback_route_contract.py`、`python3 -m ruff check src/paper_fetch/providers/base.py src/paper_fetch/providers/_waterfall.py src/paper_fetch/providers/elsevier.py src/paper_fetch/providers/oxfordacademic.py src/paper_fetch/artifacts.py tests/unit/test_provider_fetch_result_template.py tests/unit/test_provider_payloads.py tests/unit/test_provider_pdf_fallback_route_contract.py`、`git diff --check`；未触发 GitHub CI；残余风险：IEEE landing failure 仍在 waterfall 外，不作为“HTML/browser HTML 四类码进入 PDF”的契约；失败 artifact payload/diagnostics 不进入 `ProviderFailure`，该结构性重构留给后续 artifact helper 工作。

### G05：修正 Markdown table IR 渲染边界

`/goal` 目标：让 Markdown table IR 使用统一 formatter，正确处理 headers、pipe、换行、ragged rows 和 fallback message。

范围：
- `src/paper_fetch/extraction/markdown_render/`
- HTML/JATS/Elsevier/Atypon table 相关调用点
- table renderer tests / golden mini fixtures

步骤：
1. 读取现有 table IR、formatter、Atypon/arxiv/generic table 输出路径。
2. 选定 canonical table formatter，避免再手写 `|` 拼接。
3. 让 `MarkdownTable.headers` 被实际消费；无 headers 时从 rows 推导或降级为 fallback。
4. 统一 escape pipe、cell newline、ragged row 补齐、fallback message 渲染。
5. 补单元测试覆盖 pipe/newline/ragged/header/fallback；必要时增加小型 HTML fixture。

验证：
- `PYTHONPATH=src python3 -m pytest tests/unit -q -k "table or markdown_render"`

完成标准：
- 同一 mini table 经主要路径输出一致。
- 表格内 `|` 和换行不会破坏 Markdown。
- `fallback_message` 不再构造后丢失。

状态：2026-07-03 已完成，提交/变更：新增 `paper_fetch.extraction.markdown_render.table_format` 作为 canonical pipe-table formatter，统一处理单元格换行、pipe escape、ragged row padding 和列宽对齐；`extraction.html.tables` 保留原有 formatter/helper API，但实现委托给 canonical formatter，Atypon/arXiv/HTML provider 路径可继续通过现有 import 间接复用；`MarkdownTable` 增加 `fallback_message`，IR renderer 现在实际消费显式 `headers`，无 headers 时保留 `rows[0]` 作为表头的兼容约定，显式 headers 与首行重复时自动去重，fallback table 会把 provider/JATS/Elsevier 构造的 message 渲染到正文而不是只进入 conversion notes；Elsevier table 断言改为内容/列顺序契约，不再依赖旧紧凑 pipe spacing；同步 architecture 文档与双语 changelog。验证：`PYTHONPATH=src python3 -m pytest tests/unit/test_markdown_render_ir.py tests/unit/test_html_shared_helpers.py -q`、`PYTHONPATH=src python3 -m pytest tests/unit/test_elsevier_markdown.py -q -k "table"`、`PYTHONPATH=src python3 -m pytest tests/unit -q -k "table or markdown_render"`、`python3 -m ruff check src/paper_fetch/extraction/markdown_render/_ir.py src/paper_fetch/extraction/markdown_render/tables.py src/paper_fetch/extraction/markdown_render/table_format.py src/paper_fetch/extraction/html/tables.py tests/unit/test_markdown_render_ir.py tests/unit/test_html_shared_helpers.py tests/unit/test_elsevier_markdown.py`、`PYTHONPATH=src python3 -m pytest tests/unit/test_provider_docs_facts.py tests/unit/test_human_docs_drift.py -q`、`git diff --check`；未触发 GitHub CI；残余边界：Annual Reviews HTML 仍存在 provider-local raw pipe 拼接，输入已预规范化，本轮按子代理建议不扩大范围，留给后续统一 provider table formatter 清理。

### G06：修复 inline TeX、figure/formula、citation 的确定性输出 bug

`/goal` 目标：修复三个用户可见 Markdown 输出 bug：inline TeX 缺 `$...$`、figure 被误判公式删除、citation payload 多实现漂移。

范围：
- `src/paper_fetch/extraction/markdown_render/formulas.py`
- `src/paper_fetch/extraction/html/formula_rules.py`
- `src/paper_fetch/extraction/html/assets/`
- `src/paper_fetch/providers/_html_section_markdown.py`
- `src/paper_fetch/providers/atypon_browser_workflow/normalization.py`
- `src/paper_fetch/markdown/citations.py`

步骤：
1. 先修 inline TeX：无分隔符 inline latex 输出统一包 `$...$`，display 逻辑保持不变。
2. 调整 formula image 判定顺序：figure 上下文排除必须早于 URL 关键词命中；同步所有复制路径。
3. 设计并落地 canonical `numeric_citation_payload_from_html_node()`，provider 层只传 wrapper/strip 配置。
4. 对 `srcset` helper 是否顺手合并做风险判断；若变更面大，记录到后续 goal。
5. 补覆盖 `<script type="math/tex">`、figure URL 含 `equation`、共享 URL、`<i><a>1</a>-<a>3</a></i>`、`[1,2]`。

验证：
- `PYTHONPATH=src python3 -m pytest tests/unit -q -k "formula or figure or citation or atypon"`

完成标准：
- inline formula 在 Markdown 中保留数学语义。
- 单图 figure 不会因 URL 关键词被整体删除。
- citation HTML 在 section renderer 和 Atypon normalization 中输出一致。

状态：2026-07-03 已完成，提交/变更：新增共享 `render_inline_latex_markdown()`，HTML section renderer、HTML formula container 与 Atypon inline formula image fallback 统一为无分隔符 inline TeX 包 `$...$`，display MathML/TeX 逻辑保持既有 block 输出；`looks_like_formula_image()` 与 HTML formula asset wrapper 均改为先排除显式 figure context，再应用 URL/alt/ancestor 公式启发式，避免单图 figure 因 URL/alt 含 `equation` 被公式规则吞掉，同时保留真实 formula container 与共享 URL “公式胜出”的既有 scoped asset 语义；新增 canonical `numeric_citation_payload_from_html_node()`，section renderer 与 Atypon normalization 只传 `wrapper_tags` 配置，统一处理 `<i><a>1</a>-<a>3</a></i>`、`[1,2]`、reference href/marker，并保持年份、裸上标、figure href 不误判；更新 Frontiers 表格断言以接受 G05 canonical aligned table 输出；同步 architecture 与双语 changelog。验证：`PYTHONPATH=src python3 -m pytest tests/unit/test_html_citations.py tests/unit/test_html_shared_helpers.py tests/unit/test_springer_html_regressions.py tests/unit/test_atypon_browser_workflow_markdown.py tests/unit/test_markdown_render_ir.py -q -k "formula or mathjax or inline_math or citation or numeric or figure"`、`PYTHONPATH=src python3 -m pytest tests/unit/test_frontiers_provider.py -q -k "figure or table"`、`PYTHONPATH=src python3 -m pytest tests/unit -q -k "formula or figure or citation or atypon"`、`PYTHONPATH=src python3 -m pytest tests/unit/test_provider_docs_facts.py tests/unit/test_human_docs_drift.py -q`、`python3 -m ruff check src/paper_fetch/extraction/markdown_render/formulas.py src/paper_fetch/extraction/html/formula_rules.py src/paper_fetch/extraction/html/assets/formulas.py src/paper_fetch/markdown/citations.py src/paper_fetch/providers/_html_section_markdown.py src/paper_fetch/providers/atypon_browser_workflow/formulas.py src/paper_fetch/providers/atypon_browser_workflow/normalization.py tests/unit/test_html_citations.py tests/unit/test_html_shared_helpers.py tests/unit/test_springer_html_regressions.py tests/unit/test_atypon_browser_workflow_markdown.py tests/unit/test_frontiers_provider.py`、`git diff --check`；未触发 GitHub CI；未采用/延期：`srcset` helper 合并与 scoped asset 全局 URL 去重重构变更面较大，本轮按 G06 要求只做风险判断并留给后续清理。

### G07：修正 cache index / resolve / metadata merge 语义漂移

`/goal` 目标：消除 MCP/service 层三个结构化语义漂移：cache index version、structured resolve、metadata merge。

范围：
- `src/paper_fetch/mcp/cache_index.py`
- `src/paper_fetch/mcp/cache_payloads.py`
- `src/paper_fetch/mcp/schemas.py`
- `src/paper_fetch/resolve/`
- `src/paper_fetch/workflow/metadata.py`
- `src/paper_fetch/metadata/types.py`

步骤：
1. cache index：读取时校验 `INDEX_VERSION`；定义不匹配时迁移、rescan 或拒绝策略；给 `list_cached` 增加明确 refresh/rescan 语义。
2. structured resolve：引入结构化 request 到 resolve 层，title/authors/year 不再拼成一个标题字符串；year 做过滤或加权，authors 做独立相似度。
3. metadata merge：把 workflow merge 迁移到声明式 rule，明确 blank primary、authors、大小写、dict list 的去重策略。
4. 分三组测试提交，避免一个失败掩盖另一个语义。

验证：
- `PYTHONPATH=src python3 -m pytest tests/unit -q -k "cache_index or resolve or metadata"`

完成标准：
- 旧/坏 index 不会被静默误读并覆盖。
- authors/year 作为结构化信号参与消歧。
- provider metadata 与 Crossref metadata 合并规则只有一个事实源。

状态：2026-07-03 已完成，提交/变更：cache index 读取新增 `INDEX_VERSION` 严格校验与 `CacheIndexResult` 状态，旧版/坏 schema 默认返回 `version_mismatch`/`invalid` 且不会被 `get_cached` 的单 DOI refresh 静默覆盖；`list_cached` 新增 `cache_mode="index"|"refresh"|"rescan"`，输出 `cache_mode`、`index_status`、`index_version`、`expected_index_version` 与 `index_reason`，其中 `rescan` 只从可证明 DOI 归属的 fetch-envelope sidecar / 有效 seed entries 重建；structured resolve 新增 `StructuredResolveRequest`，MCP raw `query` 仍按字符串传递，`title/authors/year` 路径以结构化对象进入 resolver，Crossref search 只用 title，authors 通过 canonical author key、year 通过 `published` 年份参与候选加权消歧；workflow primary-secondary metadata merge 迁移到 `metadata/types.py` 的 `PRIMARY_SECONDARY_METADATA_MERGE_RULE` / `merge_primary_secondary_metadata()`，明确 blank primary、authors、大小写文本、fulltext link URL、reference DOI/raw 的去重语义，并保留 public wrapper。同步 architecture/providers 文档与双语 changelog。验证：`PYTHONPATH=src python3 -m pytest tests/unit -q -k "cache_index or resolve or metadata"`、`PYTHONPATH=src python3 -m pytest tests/unit/test_provider_docs_facts.py tests/unit/test_human_docs_drift.py -q`、`python3 -m ruff check src/paper_fetch/mcp/cache_index.py src/paper_fetch/mcp/cache_payloads.py src/paper_fetch/mcp/fetch_cache.py src/paper_fetch/mcp/fetch_tool.py src/paper_fetch/mcp/output_schemas.py src/paper_fetch/mcp/schemas.py src/paper_fetch/resolve/query.py src/paper_fetch/resolve/__init__.py src/paper_fetch/workflow/resolution.py src/paper_fetch/workflow/metadata.py src/paper_fetch/metadata/types.py src/paper_fetch/metadata/__init__.py tests/unit/test_cache_index_semantics.py tests/unit/test_mcp_batch_resolve_payloads.py tests/unit/test_metadata_layer_merge.py tests/unit/test_resolve_query.py`、`python3 -m ruff format --check src/paper_fetch/mcp/cache_index.py src/paper_fetch/mcp/cache_payloads.py src/paper_fetch/mcp/fetch_cache.py src/paper_fetch/mcp/fetch_tool.py src/paper_fetch/mcp/output_schemas.py src/paper_fetch/mcp/schemas.py src/paper_fetch/resolve/query.py src/paper_fetch/resolve/__init__.py src/paper_fetch/workflow/resolution.py src/paper_fetch/workflow/metadata.py src/paper_fetch/metadata/types.py src/paper_fetch/metadata/__init__.py tests/unit/test_cache_index_semantics.py tests/unit/test_mcp_batch_resolve_payloads.py tests/unit/test_metadata_layer_merge.py tests/unit/test_resolve_query.py`、`git diff --check`；未触发 GitHub CI。

### G08：收敛 browser image/PDF warm 的超时预算

`/goal` 目标：为 browser image fetch 和 PDF warm context 加总预算，避免单图或 PDF fallback 因串联超时耗费数十秒到数分钟。

范围：
- `src/paper_fetch/providers/browser_workflow/fetchers/image.py`
- `src/paper_fetch/providers/browser_workflow/pdf_fallback.py`
- `src/paper_fetch/providers/_cloakbrowser.py`
- browser workflow tests

步骤：
1. 梳理 image fetch 五条策略和三次 attempt 的现有超时。
2. 引入单图 wall-clock budget，并把各策略 timeout 绑定到剩余预算。
3. 避免 attempt 间对所有 seed 强制长时间重导航。
4. 为 PDF warm 提供轻量 seed 采集路径：跳过 DOM-ready、`page.content()` 和不必要的 HTML 摘要。
5. 用 fake page/context 测试预算上限和导航次数，不依赖真实网络。

验证：
- `PYTHONPATH=src python3 -m pytest tests/unit -q -k "browser_workflow or image_fetch or pdf_fallback or cloakbrowser"`

完成标准：
- 单图失败耗时有确定上界。
- PDF fallback 前不会对 PDF URL 做完整 HTML 抓取。
- 同 DOI 的 PDF 候选导航次数下降且有测试守住。

状态：2026-07-03 已完成，提交/变更：browser image fetch 新增单图 wall-clock budget，attempt 数固定为 2，各策略 timeout 按剩余预算收敛，forced seed warm 只预热首个 seed；`_warm_seed_urls()` 支持轻量 timeout 和 `max_urls`，避免 attempt 间重跑所有 seed；CloakBrowser 增加 `lightweight_seed_only`/runtime `lightweight` warm 路径，跳过 DOM-ready、`page.content()`、title 和 HTML 摘要；PDF fallback 使用轻量 warm 收集 cookies，已有 browser cookies 时不再把同一 article URL 作为 seed 重导航，同时保留 referer；新增 fake page/context 测试覆盖预算 timeout、导航次数、轻量 warm 不触发 full HTML 处理，以及 PDF fallback 跳过 seed 的契约；同步 architecture、providers 文档与双语 changelog。验证：`PYTHONPATH=src python3 -m pytest tests/unit -q -k "browser_workflow or image_fetch or pdf_fallback or cloakbrowser"`、`PYTHONPATH=src python3 -m pytest tests/unit/test_provider_docs_facts.py tests/unit/test_human_docs_drift.py -q`、`python3 -m ruff check src/paper_fetch/providers/browser_workflow/fetchers/context.py src/paper_fetch/providers/browser_workflow/fetchers/image.py src/paper_fetch/providers/_cloakbrowser.py src/paper_fetch/providers/browser_runtime/api.py src/paper_fetch/providers/browser_runtime/backends/cloakbrowser.py src/paper_fetch/providers/browser_runtime/types.py src/paper_fetch/providers/browser_workflow/pdf_fallback.py tests/unit/test_browser_workflow_fetchers.py tests/unit/test_cloakbrowser_backend.py tests/unit/test_pdf_fallback_helpers.py tests/unit/test_atypon_browser_workflow_provider_fallbacks.py`、`python3 -m ruff format --check src/paper_fetch/providers/browser_workflow/fetchers/context.py src/paper_fetch/providers/browser_workflow/fetchers/image.py src/paper_fetch/providers/_cloakbrowser.py src/paper_fetch/providers/browser_runtime/api.py src/paper_fetch/providers/browser_runtime/backends/cloakbrowser.py src/paper_fetch/providers/browser_runtime/types.py src/paper_fetch/providers/browser_workflow/pdf_fallback.py tests/unit/test_browser_workflow_fetchers.py tests/unit/test_cloakbrowser_backend.py tests/unit/test_pdf_fallback_helpers.py tests/unit/test_atypon_browser_workflow_provider_fallbacks.py`；未触发 GitHub CI；残余风险：PDF fallback 仍依赖 provider 传入的 seed URL 质量，跨 provider 的 seed 优先级排序不在本轮范围。

### G09：缓存 image/formula/PDF 工具链重复开销

`/goal` 目标：减少本地工具链重复探测和重复转换，尤其是 Ghostscript/libvips、texmath 和 PDF markdown 渲染。

范围：
- `src/paper_fetch/image_tools/convert.py`
- `src/paper_fetch/image_tools/paths.py`
- `src/paper_fetch/formula/convert.py`
- `src/paper_fetch/providers/_pdf_common.py`
- 对应 unit tests

步骤：
1. image tools：缓存可执行文件解析、`--version` 探测、tool env 计算，缓存 key 必须包含相关 env/目录。
2. formula：评估 texmath worker 或批处理；若实现成本高，先增加 worker 设计和 subprocess 调用次数测试。
3. PDF：给 `pdf_bytes` 加 hash cache；增加页数/字节 guard 和耗时 diagnostics；缩小或隔离全局 monkeypatch。
4. 用 mock `subprocess.run` 和 fake binary fixture 验证调用次数，不要求真实工具链。

验证：
- `PYTHONPATH=src python3 -m pytest tests/unit -q -k "image_tools or formula or pdf_common"`

完成标准：
- 多张图不会重复二进制探测。
- 公式密集路径减少不必要 subprocess。
- 同一 PDF 不重复完整转换；并发中无关 subprocess 不被 monkeypatch 污染。

状态：2026-07-03 已完成，提交/变更：image tools 在 `paths.py` 缓存 Ghostscript/libvips 候选列表，cache key 覆盖显式 binary env、`PAPER_FETCH_IMAGE_TOOLS_DIR`、`XDG_DATA_HOME`、`PATH` 和搜索目录指纹；`convert.py` 增加 working-binary probe cache、tool env overlay cache 和测试清缓存入口，按候选文件指纹、probe args、timeout 与 `LD_LIBRARY_PATH`/`GS_LIB` 失效，首次 miss 用锁避免并发多图重复 `--version`；formula 审计后保留现有 texmath 默认和 `mathml-to-latex` worker，不在本轮新增 texmath worker/跨 provider 批处理，新增 subprocess 调用次数测试守住相同 MathML/backend/config 只启动一次 texmath；PDF common 新增 `pdf_bytes` SHA-256 渲染缓存，限定无图片导出路径以避免本地图片路径跨输出目录复用，新增 `PAPER_FETCH_PDF_MAX_BYTES`、`PAPER_FETCH_PDF_MAX_PAGES`、`PAPER_FETCH_PDF_MARKDOWN_CACHE_SIZE`，成功结果 diagnostics 记录 hash、字节数、页数、cache status 与 Markdown 渲染耗时；`_SubprocessTextDecodeReplace` 只在 owner thread 注入 `errors="replace"`，窗口内其他线程调用 `subprocess.run` 不再被改写；新增 fake binary/mock subprocess 和 fake pymupdf 测试覆盖多图 probe 复用、env 变更失效、公式 cache 调用次数、同 PDF 渲染缓存、字节/页数 guard、PDF diagnostics 与 monkeypatch 隔离；同步 providers/deployment/architecture 文档与双语 changelog。验证：`PYTHONPATH=src python3 -m pytest tests/unit -q -k "image_tools or formula or pdf_common"`、`PYTHONPATH=src python3 -m pytest tests/unit/test_provider_docs_facts.py tests/unit/test_human_docs_drift.py -q`、`python3 -m ruff check src/paper_fetch/image_tools/paths.py src/paper_fetch/image_tools/convert.py src/paper_fetch/providers/_pdf_common.py tests/unit/test_image_tools.py tests/unit/test_formula_conversion.py tests/unit/test_pdf_fallback_helpers.py`、`python3 -m ruff format --check src/paper_fetch/image_tools/paths.py src/paper_fetch/image_tools/convert.py src/paper_fetch/providers/_pdf_common.py tests/unit/test_image_tools.py tests/unit/test_formula_conversion.py tests/unit/test_pdf_fallback_helpers.py`；未触发 GitHub CI；残余风险：texmath 仍是单次 CLI 协议，没有新增常驻 worker；跨 provider 的公式批处理入口变更面较大，保留给后续专门设计。

### G10：清理 provider registry、`waterfall_steps` 契约和冷启动

`/goal` 目标：降低 `import paper_fetch` 冷启动成本，修正 provider 发现和 `waterfall_steps` 类型契约。

范围：
- `src/paper_fetch/providers/__init__.py`
- `src/paper_fetch/provider_catalog.py`
- `src/paper_fetch/providers/base.py`
- browser provider client 类
- `src/paper_fetch/extraction/html/_runtime.py`
- `src/paper_fetch/publisher_identity.py`

步骤：
1. 将 `trafilatura`、`idutils` 改为函数内惰性 import，保持缺依赖降级语义。
2. provider 自动发现优先改显式 manifest；若范围过大，先用 AST 识别真实调用并加缓存。
3. 修正 browser providers 的字符串 `waterfall_steps`：删除、改名为 `route_order`，或改成真实 `WaterfallStep`。
4. 增加 import-time smoke，至少断言 `trafilatura` / `idutils` 不在根 import 路径。
5. 增加契约测试：所有 `ProviderClient.waterfall_steps` 元素必须是 `WaterfallStep`。

验证：
- `PYTHONPATH=src python3 -m pytest tests/unit -q -k "provider_catalog or providers or import or waterfall_steps"`

完成标准：
- 冷启动重依赖惰性化。
- provider 发现不会被注释/docstring 误触发，且不重复读盘。
- `waterfall_steps` 不再有字符串死代码。

状态：2026-07-03 已完成，提交/变更：`trafilatura` 与 `idutils` 改为函数内惰性 import，并保留缺依赖 fallback；`provider_catalog`、workflow preferred/official/provider-managed 集合和 provider registry 改为按需触发 provider entry 导入，根 `paper_fetch` import 不再加载 provider entries；provider discovery 改为显式内置 entry 清单加 AST 真实调用识别与文件指纹缓存，避免注释/docstring 误触发和重复扫描；browser workflow provider 的字符串路线声明从 `waterfall_steps` 改名为 `route_order`，新增 `WaterfallStep` 契约测试；`browser_runtime.__init__` API 导出改为惰性加载并修复 `_cloakbrowser` 收集期循环导入；同步 architecture、provider-development 与双语 changelog。验证：`PYTHONPATH=src python3 -m pytest tests/unit -q -k "provider_catalog or providers or import or waterfall_steps"`、`PYTHONPATH=src python3 -m pytest tests/unit/test_provider_docs_facts.py tests/unit/test_human_docs_drift.py -q`、`python3 -m ruff format --check <G10 touched Python files>`、`python3 -m ruff check <G10 touched Python files>`、根 import 子进程 probe、`git diff --check`；未触发 GitHub CI；残余风险：内置 provider entry 清单成为新增内置 provider 时需要同步维护的显式事实源。

### G11：扩大 mypy/coverage/preflight 质量门禁

`/goal` 目标：让类型检查和测试门禁覆盖高风险路径，并避免本地 preflight 与 CI 漂移。

范围：
- `pyproject.toml`
- `.github/workflows/ci.yml`
- `scripts/dev-preflight.sh`
- `tests/unit/` 中 CI/preflight/ruff 配置测试

步骤：
1. 统计当前 mypy 覆盖和未覆盖模块，优先把 `_waterfall.py`、`_pdf_common.py`、provider route、quality、runtime、config 纳入。
2. 用局部 overrides 处理第三方缺类型，不扩大全局 `ignore_missing_imports`。
3. 新增覆盖清单守卫，防止 `[tool.mypy].files` 继续缩小。
4. 对齐 CI 与本地 preflight 的 mypy 命令。
5. 设置低但真实的 coverage baseline；收窄 `tests/**` 全局 `B023` ignore。

验证：
- `python3 -m mypy`
- `ruff check tests --select B023`
- `PYTHONPATH=src python3 -m pytest tests/unit -q -k "ci or preflight or coverage or mypy"`
- 如改动广泛，再跑 `PYTHONPATH=src python3 -m pytest tests/unit -q`

完成标准：
- 高风险路径进入类型门禁。
- 本地 preflight 与 CI 命令一致。
- 覆盖率下降和 B023 新增问题能被阻断。

状态：2026-07-03 已完成，提交/变更：mypy 白名单扩展到 165 个源文件，新增覆盖 `config.py`、`runtime.py`、`runtime_browser.py`、`_cloakbrowser_runtime.py`、`quality/`、`providers/_waterfall.py`、`providers/_asset_retry.py`、`providers/_pdf_candidates.py`、`providers/_pdf_common.py`、`providers/_pdf_fallback.py`、`providers/browser_runtime/` 与 formula core；`pyproject.toml` 配置 `no_site_packages = true`，CI 和 preflight 均统一调用 `python -m mypy`；新增 mypy 覆盖清单/entry 存在性守卫；CI 与 `scripts/dev-preflight.sh --coverage` 均强制 `--cov-fail-under=40`，preflight 的 pytest `--durations=30` 与 extraction rules `--ci` 和 CI 对齐；移除 `tests/**` 全局 `B023` ignore，并用默认参数绑定修复 6 个测试闭包捕获；修复 mypy 扩展暴露的 MCP TypedDict 重复字段、browser runtime 动态导出静态类型、browser image budget 可空类型问题；完整 coverage 暴露的 browser image 内部默认 budget 与旧 Springer inline equation image 回归已修复；同步 deployment/provider-development 与双语 changelog。验证：`PYTHONPATH=src python3 -m mypy`、`python3 -m ruff check tests --select B023`、`PYTHONPATH=src python3 -m pytest tests/unit -q -k "ci or preflight or coverage or mypy"`、`PYTHONPATH=src python3 -m pytest tests/unit -q --cov=paper_fetch --cov-report=term-missing --cov-report=xml --cov-fail-under=40`（1880 passed，coverage 86.31%）、`PYTHONPATH=src python3 -m pytest tests/unit/test_provider_docs_facts.py tests/unit/test_human_docs_drift.py -q`、`git diff --check`；未触发 GitHub CI；残余风险：顶层 provider route 模块整体纳入 mypy 仍有较多一手类型错误，按子代理审计保留为后续专项，不在 G11 本轮扩大。

### G12：统一安装器 env/MCP 事实源和安全边界

`/goal` 目标：让 POSIX、Windows helper、根 PS1、MCP 注册使用同一份 env/MCP key 事实源，并收紧 `activate-offline.sh` source 外部 env 的风险。

范围：
- `install-offline.sh`
- `install-offline.ps1`
- `scripts/windows-installer-helper.ps1`
- `installer/manifest.json`
- installer tests、deployment docs、README

步骤：
1. 列出 POSIX offline.env、POSIX activate、POSIX MCP、Windows helper、根 PS1 的 env key 集合。
2. 以 manifest 或共享 Python/template 作为事实源，至少统一 `MATHML_TO_LATEX_NODE_BIN`、`PYTHONUTF8`、`PYTHONIOENCODING`、tool dirs。
3. 修改 `activate-offline.sh`：避免无条件 `source` 外部 env；改为安全 key/value parser，或只 source installer 自己生成的 trusted file 并文档化。
4. 明确根 `install-offline.ps1` 定位：deprecated wrapper、调用官方 helper，或补齐能力。
5. 更新 README、docs/deployment、安装器测试和 verify 脚本。

验证：
- `PYTHONPATH=src python3 -m pytest tests/unit -q -k "offline_install or installer or windows"`
- 如涉及 shell helper，运行对应脚本的 dry-run / fake HOME 测试。

完成标准：
- 各安装器输出 key 集合一致或有文档化差异。
- POSIX CLI 直跑与 MCP 都能获得离线 Node / Python encoding 配置。
- 外部 env 文件不会被 activate 脚本当 shell 代码执行。

状态：2026-07-03 已完成，提交/变更：新增 `installer/manifest.json` 的 `env_sets.offline_env_keys` / `shell_env_keys` / `activate_env_keys` 事实源，POSIX installer、Windows helper、根 Windows PS1 和 Windows build staging `offline.env` 均按 manifest key 生成 env；POSIX shell startup/offline.env/activate 统一传播 `MATHML_TO_LATEX_NODE_BIN`、`PYTHONUTF8`、`PYTHONIOENCODING` 和工具目录；`activate-offline.sh` 改用包内 Python + `python-dotenv` 安全解析 env 文件，不再 `source` 外部文件，默认只读本安装目录 env，`--reuse-env-file` 走安装时显式绑定；离线 verifier 和 unit 覆盖 Antigravity skill/MCP 注册、manifest env key、activate 不执行命令替换；README、deployment、包内 offline README 和双语 changelog 已同步。验证：`PYTHONPATH=src python3 -m pytest tests/unit -q -k "offline_install or installer or windows"`、`PYTHONPATH=src python3 -m pytest tests/unit/test_offline_install.py tests/unit/test_offline_package_build.py -q`、`PYTHONPATH=src python3 -m pytest tests/unit/test_provider_docs_facts.py tests/unit/test_human_docs_drift.py -q`、`python3 -m ruff check tests/unit/test_offline_install.py tests/unit/test_offline_package_build.py`、`python3 -m ruff format --check tests/unit/test_offline_install.py tests/unit/test_offline_package_build.py`、`bash -n install-offline.sh scripts/verify-offline-package.sh scripts/build-offline-package.sh`、`python3 -m json.tool installer/manifest.json >/dev/null`、`git diff --check`；残余风险：本机未安装 `pwsh`，PowerShell 脚本只做了单测静态/字符串守卫，未运行 PowerShell parser。

### 变更记录模板

每完成一个 goal，在本文对应 goal 下追加一行状态，格式如下：

```markdown
状态：YYYY-MM-DD 已完成，提交/变更：<简述>；验证：<命令>；残余风险：<如无写“无已知残余风险”>。
```

若只完成部分内容，使用：

```markdown
状态：YYYY-MM-DD 部分完成；已完成：<列表>；未完成：<列表>；下一步建议：<一个具体 goal>。
```

## Claude 子代理审计报告（2026-07-03 14:41）

本节接续 Claude Code 会话 `b0a60992-9cab-4b16-af93-b626ffcb0df8` 的未完成汇总。该轮会话基于本文已有 backlog 启动 8 个只读子代理，主会话在所有子代理返回后因 session limit 未能生成最终报告；原始记录保存在 `~/.claude/projects/-home-dictation-paper-fetch-skill/b0a60992-9cab-4b16-af93-b626ffcb0df8/`，子代理输出保存在其 `subagents/agent-*.jsonl`。

### 审计范围

1. Provider 注册/发现、client 契约、冷启动、publisher DOM 解析。
2. Provider routing/fallback、PDF fallback、HTTP、错误语义。
3. Browser runtime、CloakBrowser、browser workflow、Atypon。
4. HTML -> Markdown 主提取管线、表格、root 选择、清洗诊断。
5. 公式、图片资产、citation、Markdown IR。
6. MCP、service、cache、workflow、metadata、resolve、quality。
7. formula/image/http/toolchain、models、CLI。
8. 安装、打包、发布、CI、测试门禁。

### 总体判断

子代理结论整体确认了本文已有方向，但补齐了更多可执行证据：最高风险集中在四类问题。第一，CI/offline 触发、provider fallback 状态机、`RuntimeContext.parse_cache`、MCP 错误契约属于 P0/P1 边界，可能造成成本失控、用户可见行为漂移或并发状态污染。第二，HTML/Markdown、公式、figure、citation、table IR 的多路径分叉已经形成确定性输出差异，不只是清理问题。第三，browser/PDF/image/formula 工具链存在多个无全局预算或按条目重复 spawn 的性能热点。第四，安装器、mypy 覆盖、metadata merge、provider 自动发现等共享事实源不足，继续放大会增加后续重构成本。

### P0：应优先排入近期修复

1. 普通 `push`/`pull_request` 触发完整 offline/release 矩阵
   - 子代理补充证据：`.github/workflows/ci.yml` 的 `on: push` / `pull_request` 无过滤；Linux/macOS offline jobs 在普通 push 上 `if` 恒真；`offline-windows-x86-64` 没有等价守卫。
   - 风险：一次普通提交会触发 4 个 Linux、4 个 macOS、1 个 Windows 离线构建以及 Haskell/GHC、Playwright、Inno Setup 等重型步骤。
   - 建议：offline jobs 只允许 tag `refs/tags/v*` 或 `workflow_dispatch`；常规 lint/unit/integration 与 offline/release 拆分 workflow；测试用 YAML 解析断言 job 条件。

2. Provider fallback 的继续码和最终错误聚合不一致
   - 子代理补充证据：`WaterfallStep.continue_codes` 默认仅 `NO_RESULT`；Copernicus/IEEE/Oxford 使用全码继续，Elsevier 排除 `NO_ACCESS`，Springer 两个入口策略不同，PLOS/Frontiers 手写 fallback 近似全码继续。
   - 风险：同样的 403/429/付费墙错误，有的 provider 会继续 PDF fallback，有的直接失败；`combine_provider_failures()` 还会丢失 `retry_after_seconds`，并可能让 `RATE_LIMITED` 被 `NO_ACCESS` 覆盖。
   - 建议：统一 HTML/XML -> PDF fallback 的 `continue_codes`，让末位 step 也进入聚合路径；`retry_after_seconds` 从所有限流失败中合并；最终 `source_trail` / warnings 由 `RouteWaterfall` 统一产出。

3. `RuntimeContext.parse_cache` 无锁且可跨线程共享可变对象
   - 子代理补充证据：`session_cache` 有锁，`parse_cache` 访问器没有锁；Elsevier 以 `copy_value=False` 缓存并返回同一个 `ET.Element`；batch 并发和单次 fetch 内部 probe executor 都会共享同一个 context。
   - 风险：重复解析、check-then-act race、可变 XML 树跨线程共享，严重时可能变成数据污染而不只是性能退化。
   - 建议：给 `parse_cache` 增加 `RLock` 和原子 `get_or_set`；审计 `copy_value=False` 路径是否只读；补同 DOI/同 provider 并发 stress test。

4. MCP 输出契约缺版本和机器可读错误细节
   - 子代理补充证据：MCP top-level payload 无 `schema_version`；`ProviderFailure.code` 多数折叠成通用 `ERROR`；`http_status`、`retry_after_seconds`、`provider`、`source_trail`、warnings 没有进入错误输出；batch abort 只认 `RATE_LIMITED` 字符串。
   - 风险：客户端无法做兼容性判断、重试和限流处理；非标准限流错误会继续批处理并丢失 retry-after。
   - 建议：引入 `schema_version` / `contract_version`；扩展错误 payload；batch abort 改按 `error_category` 或机器可读限流字段判断。

### P1：高价值深化项

1. HTML/Markdown 输出一致性和正确性
   - `prune_html_tree` 对每个 DOM 元素调用 `get_text()`，整体呈 O(n²)；root 选择仅按 word count，长 sidebar 可能胜出。
   - IR `render_table()` 忽略 `headers`、裸拼 `|`、不补齐 ragged rows、丢弃 `fallback_message`；JATS/Elsevier、Atypon/arxiv、generic trafilatura 三条表格路径行为不同。
   - trafilatura fallback 只要非空即接受；三层 cleanup 删除正文时缺少 `CleanupDecision(stage, reason, snippet)` 诊断。
   - `expanded_table_matrix` 的 `rowspan` / `colspan` 无上限，存在内存放大风险。

2. 公式、figure、citation 的确定性渲染 bug
   - inline TeX DOM-walker 分支返回裸 latex，缺 `$...$`，而 MathML/IR 路径会正确包裹。
   - figure URL 中含 `equation` 等词时，公式 URL 模式先于 figure 上下文排除触发，可能把正文 figure 当公式删除；共享 URL 去重还会进一步移除 figure 资产。
   - citation payload 至少有核心文本层、HTML section renderer、Atypon normalization 三份实现，wrapper tag、`[]` 剥离和 `get_text` 分隔符语义不同。
   - `srcset` 解析在公式规则、资产 DOM、arxiv、Atypon、browser JS 中重复实现，分辨率选择策略漂移。

3. Browser runtime 和 PDF fallback 性能热点
   - 图片资产抓取把 warmed article、in-page fetch、context request、goto、primary-image wait 串成多个 15s/60s 超时，单图缺少全局 wall-clock deadline。
   - `warm_browser_context` 对 PDF 候选执行完整 HTML 抓取，包含最长约 20s DOM-ready 轮询，随后 PDF fallback 又重新导航同一批 URL。
   - `_cloakbrowser.py` 仍是 1140 行单体，混合依赖探测、配置、状态、图片 payload、storage seed、HTML 抓取和 warm context。
   - `BrowserWorkflowDeps` 已有分组视图但生产代码仍使用 19 个扁平 callable，测试锁定 identity，`pdf_fallback` 依赖 `is` 比较派发。

4. PDF、image、formula 工具链重复开销
   - 图片转换每张图都重复探测 Ghostscript/libvips：目录 glob、`shutil.which`、`--version` 子进程都无缓存。
   - 默认 texmath 后端每个公式 spawn 一个子进程，只有 mathml-to-latex 有常驻 worker。
   - `_pdf_common.py` 的全局 `subprocess.run` monkeypatch 在锁内贯穿整个 PDF 转换，批量 PDF fallback 会串行化；同一 PDF 最多经历默认渲染、文本层扫描、透明层 fallback 三次解析。
   - 建议优先加二进制探测缓存、texmath worker/批处理、PDF hash cache、页数/大小 guard 和转换耗时诊断。

5. MCP/service/cache/metadata 的语义漂移
   - `workflow/metadata.py` 和 `metadata/types.py` 的 merge 规则不同：空白 primary、作者去重、大小写去重、dict list 去重行为不一致。
   - `ResolvePaperRequest(title/authors/year)` 最终拼成单一 query string，authors/year 进入标题匹配 token，可能降低真实 title 得分。
   - cache index 写入 `INDEX_VERSION` 但读取忽略 version；`list_cached` 不扫盘，`get_cached` 会按 DOI refresh，语义不对称。
   - batch 共享一个 `stage_timings` dict，单条 query 的计时会互相覆盖或累加污染。

6. Provider registry、冷启动和 legacy 契约
   - `import paper_fetch` 约 600ms，其中 `trafilatura` 约 198ms、`idutils` 约 125ms 可惰性化。
   - provider 自动发现通过读取源码并匹配字符串 `register_provider_bundle(`，无 memoization，渲染期 `provider_render_policy_for_source` 也会重复发现。
   - browser providers 的 `waterfall_steps` 声明为字符串 tuple，既违反基类 `tuple[WaterfallStep, ...]` 契约，也没有运行时消费者。
   - `RawFulltextPayload.metadata` legacy 兼容层在生产读写两端基本已死，应迁移测试到 typed `content.*` 字段后淘汰。

7. 安装、发布、测试门禁
   - mypy `files` 白名单漏掉大量高风险 provider、PDF、quality、runtime、CLI/config 模块；缺少覆盖清单守卫。
   - POSIX offline `offline.env` / `activate-offline.sh` 不写 `MATHML_TO_LATEX_NODE_BIN`，只在 MCP 注册注入，和 README 对离线 Node 的承诺不一致；`PYTHONUTF8` / `PYTHONIOENCODING` 也与 Windows helper 漂移。
   - `activate-offline.sh` 使用 `set -a; source "$PAPER_FETCH_ENV_FILE"`，比运行时 dotenv 解析器执行面更宽，`--reuse-env-file` 会 source 外部文件。
   - CI 生成 coverage 但无 `--cov-fail-under`；本地 preflight 与 CI mypy 参数不一致；`tests/**` 全局 ignore `B023` 掩盖 loop closure 风险。

### P2：可合并到重构中的清理项

1. `_append_unique`、`try/except Exception: continue` 包裹 `soup.select()`、arxiv 引用 DOI/年份解析等跨 provider 重复 helper 应收敛到共享模块。
2. PLOS/Frontiers 仍是手写 fallback，应迁到 `RouteWaterfall`；redirect、candidate URL、导航头也应进入共享 HTTP/candidate helper。
3. 根 `install-offline.ps1` 是孤立半安装路径，应明确 deprecated 或调用官方 helper；release metadata、Inno 默认版本、CHANGELOG 需要自动校验。
4. `package.json` 与公式资源目录重复；在线安装和 dev bootstrap 逻辑重复；真实 formula/image 工具链 smoke 可从 unit gate 拆出。
5. `fetch_html_with_cloakbrowser_fast` 只是直通别名，`warm_wait_seconds` 全链路死参；`finalize_extraction` 在 Markdown 抽取后再次整页解析 HTML 提取 authors/references。

### 建议落地顺序

1. 先做可快速止血的 P0：CI/offline 触发条件、`parse_cache` 锁、MCP schema/error payload、provider fallback `continue_codes` 和错误聚合。
2. 再修确定性输出 bug：table IR renderer、inline TeX 包裹、figure/formula 分类顺序、citation payload canonical helper、trafilatura 接受条件。
3. 接着处理性能预算：browser image 单图 deadline、PDF warm 轻量化、PDF 转换隔离/缓存、image binary 探测缓存、texmath worker。
4. 最后做共享事实源和结构收敛：provider manifest/AST discovery、metadata merge rule、installer env/MCP 模板、mypy 覆盖扩展、browser runtime 拆分。

## 总体优先级

### P0：建议优先处理

1. 限制普通 `push` 触发完整 offline/release 矩阵
   - 证据：`.github/workflows/ci.yml` 对所有 `push` 生效，Linux/macOS offline jobs 也在普通 push 路径运行。
   - 风险：普通提交会触发昂贵 CI，与仓库约定“提交时除非明确说明，不要触发 Github CI”冲突。
   - 建议：拆分常规 CI 与 offline/release workflow，或给 offline jobs 增加 `startsWith(github.ref, 'refs/tags/v') || workflow_dispatch` 条件。
   - 验证：更新 `tests/unit/test_ci_release_workflow.py`，解析 workflow 并断言触发条件。

2. 扩大 mypy 覆盖范围
   - 证据：`pyproject.toml` 中 `[tool.mypy].files` 是白名单，仍有大量 provider、browser runtime、formula、quality 模块未覆盖。
   - 风险：高风险路径可以通过 lint/test，但完全避开类型门禁。
   - 建议：分阶段把覆盖扩到 `src/paper_fetch`，先用局部 overrides 处理遗留模块；把全局 `ignore_missing_imports = true` 改为按第三方包定向忽略。
   - 验证：先新增覆盖统计测试或脚本，防止覆盖范围继续缩小。

3. 统一 provider fallback 状态机和错误语义
   - 证据：已有 `src/paper_fetch/providers/_waterfall.py`，但 PLOS、Frontiers、Springer 等仍存在手写 fallback 流程；`combine_provider_failures()` 的错误优先级较粗。
   - 风险：最终错误码、warning、source trace 在不同 provider 间漂移，新增 route 时容易复制旧 bug。
   - 建议：引入声明式 `RouteAttempt` / `RouteWaterfall`，统一 route 顺序、candidate 循环、最终错误优先级。
   - 验证：参数化覆盖 PLOS、Frontiers、Copernicus、Oxford、Springer、IEEE 的 route 顺序、错误码、warning 和 source trail。

4. 加固 MCP batch 并发中的 `RuntimeContext`
   - 证据：batch 并发复用同一个 `RuntimeContext`，`session_cache` 有锁，但 `parse_cache` 没有锁。
   - 风险：article-mode batch 同 provider 并发时可能重复解析、cache race，或暴露 provider client 线程安全问题。
   - 建议：给 `parse_cache` 增加锁和原子 `get_or_set`；明确 provider client 是否允许跨线程共享。
   - 验证：新增同 DOI/同 provider 并发 parse cache stress test。

5. 修正 Markdown table IR 渲染边界
   - 证据：`MarkdownTable.headers` 定义后未被 `render_table()` 使用，renderer 直接拼接 raw rows；`fallback_message` 被构造但未渲染。
   - 风险：cell 内 `|`、换行、缺列会破坏 Markdown 表格；fallback 诊断丢失。
   - 建议：让 IR renderer 复用共享 table formatter，统一 escape、换行、ragged row、fallback message 语义。
   - 验证：补 `pipe/newline/ragged rows/image fallback message` 的单元测试。

6. 给 MCP API 输出增加版本化契约和完整错误细节
   - 证据：fetch-envelope cache 有版本，但 MCP top-level payload 无 `schema_version`；错误 payload 只保留 `status/reason/candidates/missing_env` 等少量字段。
   - 风险：客户端难以判断兼容性；rate limit、HTTP status、retry-after、source trail 等机器可读信息丢失。
   - 建议：引入 `schema_version` / `contract_version`；扩展错误输出字段，例如 `code`、`http_status`、`error_category`、`retry_after_seconds`、`warnings`、`source_trail`、`provider`。
   - 验证：补 JSON schema snapshot / MCP output model tests。

## Providers 与运行时

1. 合并 PDF fallback artifact / text-only 逻辑
   - 证据：Elsevier、Springer、PLOS、Frontiers、Copernicus、IEEE、browser workflow 都有类似 `describe_artifacts()`；Oxford 行为已经有差异。
   - 风险：PDF fallback 是否下载 related assets、是否记录 skipped marker 依 provider 而异。
   - 建议：在 `base.py` 或 `_pdf_common.py` 提供共享 helper，例如 `pdf_fallback_artifacts(raw_payload, provider_name)`。
   - 验证：参数化覆盖所有 PDF fallback provider，断言 `allow_related_assets=False`、text-only warning/trace、PDF extracted assets 行为一致。

2. 拆分 `_cloakbrowser.py` 单体
   - 证据：已有 `providers/browser_runtime/api.py` 和 backend wrapper，但旧 `_cloakbrowser.py` 仍同时负责依赖探测、配置、图片 payload、HTML 抓取和 warm context。
   - 风险：新增非 CloakBrowser backend 或调整 Playwright 行为成本高，单文件修改影响面大。
   - 建议：迁移到 `browser_runtime/backends/cloakbrowser/{config,html,image_payload,storage}.py`，旧文件保留 compatibility re-export。
   - 验证：测试面向 facade/backend 行为，减少 alias identity 断言。

3. 收窄 `BrowserWorkflowDeps` 注入面
   - 证据：`BrowserWorkflowDeps` 暴露大量 callable 字段，测试锁定字段精确存在。
   - 风险：测试与实现细节强耦合，后续拆分 HTML/PDF/assets 逻辑改动面大。
   - 建议：拆成 `runtime/html/pdf/assets/cache` 分组依赖对象或 Protocol。
   - 验证：测试改为验证分组接口行为，不断言每个私有函数 identity。

4. 替换脆弱的 provider 自动发现
   - 证据：`providers/__init__.py` 通过读取源码并查找字符串 `register_provider_bundle(` 判断是否导入，且 import 时立即执行发现。
   - 风险：注释/字符串可能误触发；包装注册函数会漏发现；import side effect 和 catalog cache 失效难推理。
   - 建议：优先使用显式 provider manifest 或打包 entry point；最低限度改成 AST 识别调用。
   - 验证：补注释 false-positive、不导入无关模块、动态刷新 catalog 的测试。

5. 改善 PDF 转换性能和并发安全
   - 证据：`_pdf_common.py` 会 monkeypatch 全局 `subprocess.run`；PDF 渲染可能先跑默认转换，再扫描文本层，必要时再跑 fallback 转换。
   - 风险：全局 monkeypatch 可能污染并发中的其他 subprocess；长 PDF fallback CPU 成本高。
   - 建议：优先寻找 `pymupdf4llm` 可配置入口，或隔离到 worker；增加 PDF hash cache、页数/大小 guard、转换耗时 diagnostics。
   - 验证：补并发 subprocess 不被污染、同一 PDF 命中缓存、超大 PDF guard 测试。

6. 统一 HTTP/candidate/redirect helper
   - 证据：browser direct HTTP、Oxford PDF、PLOS/Frontiers/XML provider 都有各自的 redirect、status、content-type 处理。
   - 风险：redirect、rate limit、content-type、final URL 语义不一致。
   - 建议：新增共享 `ProviderHttpClient` 或候选 GET helper，内置 redirect policy、expected content type、`RequestFailure` 映射和诊断字段。
   - 验证：参数化覆盖 redirect/status/content-type/final_url。

7. 清理 provider client 类型契约和 legacy payload 边界
   - 证据：`ProviderClient.waterfall_steps` 类型期望 `WaterfallStep`，但有 provider 使用字符串 tuple；`RawFulltextPayload.metadata` 仍承担 legacy compatibility。
   - 风险：后续继承关系调整可能让非法 steps 进入 runner；legacy metadata 继续扩大类型漂移。
   - 建议：移除或改名不符合契约的 `waterfall_steps`；逐步把结构字段从 `metadata` 迁到 typed payload 字段。
   - 验证：扫描所有 provider client 的 `waterfall_steps` 必须是 `WaterfallStep`。

8. 降低 package import 冷启动成本
   - 证据：`paper_fetch/__init__.py` 直接导入 service，进而拉起 provider/workflow 相关依赖；本地粗测 `import paper_fetch` 约 0.7s。
   - 风险：CLI/MCP 冷启动变慢，轻量使用模型类也会付出完整 service/provider import 成本。
   - 建议：将 public facade 改成惰性导入，或拆轻量 public model surface 与 service surface。
   - 验证：新增 import-time smoke 或预算测试，至少跟踪趋势。

## HTML、Markdown、公式、图片与 citation

1. 收敛 HTML 到 Markdown 的多条渲染路径
   - 证据：generic renderer、trafilatura、provider DOM walker、Atypon normalization 并存。
   - 风险：公式、表格、citation、图片修复容易只覆盖一条路径。
   - 建议：把 DOM -> block IR -> Markdown 变成主通路，provider 只提供 hook/selector。
   - 验证：同一 mini HTML 通过 generic、section renderer、Atypon renderer 输出一致。

2. 统一公式识别与渲染信心模型
   - 证据：`srcset` 解析在公式规则和资产 DOM 各写一份；formula image 判定和 figure context 排除逻辑分散；inline TeX 分支可能返回裸 latex。
   - 风险：figure 被误判为公式、inline math 丢 `$...$` 语义、formula/figure asset 去重误删。
   - 建议：抽共享 `srcset` helper；返回 `FormulaRenderResult(latex, display, image_url, confidence)`；inline latex 默认包 `$`。
   - 验证：覆盖 inline `<script type="math/tex">`、figure URL 含 equation 词、formula/figure 共享 URL。

3. 让图片注入使用 section 语义
   - 证据：figure injection 自带 front/back matter heading 表并按正文引用后插图；项目已有 section semantics 和 scan state。
   - 风险：References、Appendix、caption 列表、相关工作里的 Figure 提及可能触发错位插图。
   - 建议：`inject_inline_figure_links()` 接收 section hints，或复用 `markdown_heading_category()`。
   - 验证：覆盖 Figure 提及出现在 Abstract、Data availability、References、Appendix 与 Results 的差异。

4. 增加 block-level 清洗诊断
   - 证据：DOM 清洗、Markdown 逐行 drop、body metrics 二次清洗分层执行；主 clean 未输出可追踪决策。
   - 风险：正文被静默删掉时难定位是哪层规则触发。
   - 建议：统一输出 `CleanupDecision(stage, action, reason, snippet)`；`clean_markdown()` 改 block-aware。
   - 验证：补多行 chrome block、正文含 promo token、code fence、figure/table/formula block 的保留/删除矩阵。

5. 去重 citation HTML payload 提取逻辑
   - 证据：核心 numeric payload、HTML section renderer、Atypon normalization 各实现一份，wrapper tag 支持不一致。
   - 风险：同一 citation HTML 在不同 provider 输出不同。
   - 建议：把 `numeric_citation_payload_from_html_node()` 放入 canonical owner，wrapper tags 作为参数。
   - 验证：覆盖 `<sup>`、`<i><a>1</a>-<a>3</a></i>`、author-year link、inline code 不改写。

6. 强化 HTML root 选择和 trafilatura 接受条件
   - 证据：root 选择主要按候选 word count；trafilatura 只要返回非空 clean markdown 就接受。
   - 风险：长侧栏/相关内容可能胜出；trafilatura 只抽到摘要/图注也可能被接受。
   - 建议：root scoring 加正文结构、heading、负向 chrome 权重；trafilatura 输出先过 body metrics / section hints 再接受。
   - 验证：覆盖长 sidebar + 短正文、caption-only、abstract-only 的质量判定。

7. 理清 `extraction/markdown_render` 与 HTML helper 边界
   - 证据：共享 Markdown IR 层仍混入 HTML figure/formula helper。
   - 风险：模块职责不清，provider-neutral 层和 HTML DOM 层耦合加深。
   - 建议：IR 层只保留纯 Markdown 数据结构与渲染；HTML DOM 到 IR 的转换放回 `extraction/html`。
   - 验证：补 import boundary 测试。

## MCP、service、cache 与 metadata

1. cache index 读取应校验版本并明确 list/get 语义
   - 证据：cache index 写入 `INDEX_VERSION`，但读取只取 `entries`；`list_cached` 不扫描目录，`get_cached` 会按 DOI refresh。
   - 风险：旧 index schema 可能被误读；用户文件已存在但 list miss。
   - 建议：读取时校验/迁移 `version`；为 `list_cached` 增加 `refresh` / `rescan` 语义。
   - 验证：补旧版本 index、坏 index、无 index 目录扫描测试。

2. structured resolve API 不应降级成字符串拼接
   - 证据：`ResolvePaperRequest` 支持 `title/authors/year`，但最终只是拼接为 query string。
   - 风险：用户以为 authors/year 是结构化 disambiguation，实际可能污染 title query。
   - 建议：新增 `ResolutionRequest` 传到 resolve 层，title/authors/year 作为独立 scoring/filter 信号。
   - 验证：补 author/year 消歧、矛盾年份、纯 title 对比测试。

3. 可观测性应进入 MCP 结果合约
   - 证据：service/runtime 已记录 stage timing，但 MCP output schema 没有 timing/cache 状态字段。
   - 风险：MCP 用户难定位慢在 resolve、metadata、fulltext、assets、render 还是 cache。
   - 建议：在 top-level diagnostics 或 quality 中增加 `stage_timings`、`cache_status`、`cache_hit`。
   - 验证：补 timing/cache-hit MCP payload tests。

4. 统一 metadata merge 规则
   - 证据：`metadata/types.py` 有通用 merge helper，workflow 又有单独 merge 逻辑。
   - 风险：provider metadata 与 Crossref metadata 合并行为难预测，新增字段容易漏规则。
   - 建议：统一使用声明式 `MetadataMergeRule`，把 workflow merge 迁移为字段规则。
   - 验证：覆盖 blank primary、duplicate authors/fulltext_links/references、official-vs-crossref 冲突。

5. config 解析不要静默吞掉无效值
   - 证据：invalid int env 会回落默认值；UA 版本硬编码。
   - 风险：用户配置拼写错误或非法值被吞掉，provider_status 不可见。
   - 建议：增加 config diagnostics，至少在 `provider_status` 暴露 invalid env warning；UA 从 package metadata 派生或加同步测试。
   - 验证：补 invalid concurrency/cache env 的 provider_status/config tests。

## 安装、打包、发布与文档

1. 把安装器逻辑抽成共享事实源
   - 证据：POSIX installer、Windows helper、旧 PS1 各自生成 env/MCP 映射；manifest 只集中一部分名称和 key。
   - 风险：新增 env key、host 或 managed block 时三套实现漂移。
   - 建议：把 env value 生成、managed block、MCP JSON/TOML 生成抽成共享 Python 模块或模板，shell/PS1 只调用。
   - 验证：manifest env key 对所有安装器输出做快照测试。

2. 明确或淘汰根目录 `install-offline.ps1`
   - 证据：官方 Windows 构建复制的是 `scripts/windows-installer-helper.ps1`，根 `install-offline.ps1` 没有 PATH/skill/MCP/卸载等完整行为。
   - 风险：用户或维护者误用后得到半安装状态。
   - 建议：标记 deprecated，或改成提示/调用官方 installer/helper；若保留则补齐能力。
   - 验证：补 Windows PS1 行为测试，不只做字符串检查。

3. 补齐 Antigravity 离线文档和测试
   - 证据：POSIX/Windows 离线安装支持 Antigravity，但文档和测试仍偏 Codex/Claude。
   - 风险：Antigravity 集成破坏时不容易被发现。
   - 建议：deployment 离线安装/卸载补 Antigravity；`verify-offline-package.sh` 和 installer tests 增加覆盖。
   - 验证：fake Antigravity CLI/config 测试。

4. 收紧 `activate-offline.sh` source env 文件的安全边界
   - 证据：生成脚本会 `source "$PAPER_FETCH_ENV_FILE"`，而运行时代码已有 dotenv 解析。
   - 风险：复用外部 env 文件时，shell 语法不兼容或执行非预期命令。
   - 建议：生成安全 key/value export 逻辑；或只 source installer 自己生成的 trusted 文件，并在 `--reuse-env-file` 文档中明确边界。
   - 验证：覆盖空格、注释、`export`、命令替换文本的 env fixture。

5. 自动校验 release metadata
   - 证据：版本在 `pyproject.toml`，Inno 默认版本和 changelog 仍依赖人工同步。
   - 风险：发 tag 或直接运行 Inno 模板时才发现版本/changelog 漂移。
   - 建议：新增 `scripts/check-release-metadata.py`，校验 pyproject、Inno default、`CHANGELOG.md`、`CHANGELOG_CN.md`。
   - 验证：纳入 unit 或 preflight。

6. 澄清根 `package.json` 的定位
   - 证据：根 `package.json` 与 `src/paper_fetch/resources/formula/package.json` 重复维护公式 Node 依赖。
   - 风险：Dependabot/npm 操作容易只改一份或误认为这是主项目 npm 包。
   - 建议：改成 npm workspace，或把资源目录作为唯一源，根文件只用于开发并明确标注。
   - 验证：同步 name/private/license/package-lock 根元数据。

7. 合并在线安装和开发 bootstrap 的重复逻辑
   - 证据：`install.sh` 和 `scripts/dev-bootstrap.sh` 都创建 venv、pip install、安装公式工具。
   - 风险：在线安装行为分叉，Windows 源码用户边界不清。
   - 建议：抽 common bootstrap；或明确 `install.sh` 只支持 POSIX，Windows 源码安装只走文档化 pip 路径。
   - 验证：补 install/dev-bootstrap 参数矩阵和文档快照。

## 测试与质量门禁

1. 增加覆盖率失败门槛
   - 证据：CI 生成 coverage 报告但没有 `--cov-fail-under`；本地 preflight 也明确不强制 coverage threshold。
   - 风险：覆盖率下降不会阻塞合并，尤其 mypy 未覆盖区域更依赖测试兜底。
   - 建议：先设置低但真实的项目级基线，再逐步按包设置门槛。
   - 验证：CI 和本地 preflight 同步更新。

2. 自动化 full golden 回归策略
   - 证据：默认 integration 只比对代表 fixture，完整 golden 需要手动 `PAPER_FETCH_RUN_FULL_GOLDEN=1` 或 workflow input。
   - 风险：非代表 fixture 的提取退化可能长期进入主分支。
   - 建议：保留手动 full-golden，同时增加 nightly 或路径触发；当 `providers/**`、`extraction/**`、golden fixtures 改动时自动跑。
   - 验证：CI workflow 条件测试。

3. 拆分 live CI 覆盖
   - 证据：CI 可选 live job 只跑 MCP live；`tests/live` 中还有 direct publishers 和 geography live。
   - 风险：MCP metadata smoke 通过不代表 direct service fulltext、PDF fallback、geography report 正常。
   - 建议：拆成 `live-mcp`、`live-publishers`、`live-geography` 三个手动/定时 job，继续串行 `-n 0`。
   - 验证：按 provider/授权环境分组记录。

4. 对齐本地 preflight 与 CI 命令
   - 证据：CI mypy 使用 `python -m mypy`，本地 preflight 使用 `mypy --no-site-packages`；CI 只验证 preflight `--help`。
   - 风险：本地和 CI 看到不同 mypy 结果；preflight 脚本坏了也不一定被 CI 发现。
   - 建议：统一 mypy 参数；让 CI 调用 `scripts/dev-preflight.sh --fast`，或把共享命令生成到一个脚本/Make 入口。
   - 验证：测试解析 YAML 后断言规范化命令，而不是简单字符串包含。

5. 拆出真实 formula/image 工具链 smoke
   - 证据：unit job 总是安装 Haskell/GHC/Cabal 和 image backend，但许多公式单测使用 fake/mocking。
   - 风险：普通 unit gate 受外部工具链、缓存、包安装速度影响，失败信号不聚焦。
   - 建议：真实 installer smoke 拆到独立 job 或 integration marker；unit 默认使用 fake executable/fixture。
   - 验证：保留少量安装脚本静态与模拟测试。

6. 收窄测试目录全局 `B023` ignore
   - 证据：`pyproject.toml` 对 `tests/**` 全局忽略 `B023`；隔离抽查仍有当前命中。
   - 风险：loop 内 closure/mock 捕获变量错误会让测试假阳性或在重排后失败。
   - 建议：改成具体文件/行级 `noqa: B023`，或用默认参数显式绑定 loop 变量。
   - 验证：移除全局 ignore 后跑 `ruff check tests --select B023`。

## 建议实施顺序

1. 先做低风险质量门禁：CI/offline 触发条件、`parse_cache` 锁、Markdown table IR、cache index version、`B023` ignore 收窄。
2. 再做契约层：MCP schema version/error payload、provider `waterfall_steps` 契约、metadata merge 规则。
3. 然后做 provider 共享化：RouteWaterfall、PDF fallback artifact helper、HTTP/candidate helper。
4. 最后做大块结构优化：HTML -> block IR -> Markdown 主路径、browser runtime 拆分、安装器共享模板。
