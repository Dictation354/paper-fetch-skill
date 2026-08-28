# Paper Fetch v6 问题关闭记录

本文记录 2026-08-28 复杂度收敛与破坏性重构的确定决策。v6 不为已删除的私有入口、兼容字段、治理层或 devtool 提供 facade、弃用代理或过渡期。

## 关闭摘要

| 编号 | 决策 | 状态 |
| --- | --- | --- |
| PF-AUDIT-001 | Provider route 成为 capability 唯一事实源 | 已关闭（v6） |
| PF-AUDIT-002 | 删除自建 AI onboarding coordinator | 已关闭（v6） |
| PF-AUDIT-003 | Batch 生命周期集中到现有 shared owner | 已关闭（v6） |
| PF-RELEASE-001 | Stable/rolling 公开资产收敛为精确集合 | 已关闭（v6） |
| PF-AUDIT-004 | MCP 不再发布 output schema | 已关闭（v6） |
| PF-AUDIT-005 | Provider 仅由显式模块清单加载 | 已关闭（v6） |
| PF-AUDIT-006 | 删除无消费者兼容入口与 wrapper | 已关闭（v6） |
| PF-AUDIT-007 | 降低已触及热点复杂度基线 | 已关闭（v6） |
| PF-AUDIT-008 | macOS contract 只保留 macOS 事实与安全不变量 | 已关闭（v6） |
| PF-AUDIT-009 | `BrowserWorkflowDeps` 收敛为标准 dataclass | 已关闭（v6） |
| PF-AUDIT-010 | 重复 helper 并入现有 owner | 已关闭（v6） |
| PF-AUDIT-011 | Architecture closeout 只验证当前边界 | 已关闭（v6） |
| PF-AUDIT-012 | 删除无消费者 routing 草稿 | 已关闭（v6） |
| PF-AUDIT-013 | Golden manifest 成为测试—规则—样本机器映射 | 已关闭（v6） |
| PF-AUDIT-014 | 通用 reason code 只在根模块定义 | 已关闭（v6） |
| PF-AUDIT-015 | Browser preflight 状态顺序由 core 提供 | 已关闭（v6） |
| PF-AUDIT-016 | Markdown 资产引用字段使用唯一 tuple | 已关闭（v6） |
| PF-AUDIT-017 | 删除两条未接线执行路径 | 已关闭（v6） |
| PF-AUDIT-018 | 删除失真的 fixture size baseline | 已关闭（v6） |
| PF-AUDIT-019 | 恢复 production/devtool package 边界 | 已关闭（v6） |
| PF-AUDIT-020 | 停止生成和跟踪 cleaning evidence sidecar | 已关闭（v6） |
| PF-AUDIT-021 | 删除当前版本、日期与 inventory 数量快照 | 已关闭（v6） |
| PF-AUDIT-022 | 删除 geography 专用 live/report/artifact 生命周期 | 已关闭（v6） |

## 关闭决策与验收

### PF-AUDIT-001：Provider capability

- `ProviderSpec` 不再保存 `requires_playwright` 或 `requires_browser_runtime`；也不自动补 route。
- MCP catalog 的 `browser_available`、`browser_required`、`browser_optional` 与 `requires_playwright` 全部从 `ProviderSpec.routes` 派生。
- Required、optional 与 hybrid 行为由 route 不变量和 MCP catalog 测试覆盖。

### PF-AUDIT-002：Onboarding coordinator

- 删除 coordinator、共享 `exec` fragments、私有 state/DAG/retry/prompt/worker dispatch、递归 `codex exec` 入口及专属文档/测试。
- 保留 manifest/schema、access review、provider review、capture、scaffold、proposal、snapshot、sync-back、fixture/golden 与确定性 acceptance。
- Review hash、quality、contract 与 signoff 的机械校验由 `scripts/bootstrap_review_artifact.py` 直接承担。

### PF-AUDIT-003：Batch 生命周期

- `BatchRunLifecycle` 在现有 `workflow/batch_lifecycle.py` 中统一 lock、prepare、journal/event persistence、terminalization、abort 与逆序 cleanup。
- CLI/MCP 只保留输入映射、item fetch、progress 和输出投影。
- Durable/in-memory、resume、overwrite、duplicate fan-out、fail-fast、cancel 与 interrupt 行为由共享生命周期测试覆盖。

### PF-RELEASE-001：公开发布资产

- Stable Release 公开文件精确为九个安装包和 `SHA256SUMS`；checksum 含九条记录。
- Rolling prerelease 公开文件精确为九个安装包、`dependency-manifest.json` 和 `SHA256SUMS`；checksum 含十条记录。
- Wheel、sdist、inventory、merged manifest、SBOM 与 target evidence 仍在构建期验证，但不复制到公开目录。
- Missing、extra、basename collision、secret scan 与 attestation 输入继续 fail closed。

### PF-AUDIT-004：MCP output schema

- 删除 `paper_fetch.mcp.output_schemas`、`Annotated[CallToolResult, ...]`、schema compactor 与字节预算。
- 十个工具在 `tools/list` 中均不发布 `outputSchema`，调用结果继续返回原有 `CallToolResult.structured_content`。

### PF-AUDIT-005：Provider 加载

- 内置 provider 只由 `paper_fetch.providers._BUILTIN_PROVIDER_ENTRY_MODULES` 加载；新增 provider 登记一次。
- 删除源码 AST discovery、fingerprint cache 与 discovery lock；根 package import 仍保持 lazy。

### PF-AUDIT-006：兼容入口

- 删除 `build_provider_registry` 动态 monkeypatch、`RawFulltextPayload.metadata` 兼容视图，以及已确认无消费者的私有 wrapper/re-export。
- v6 不保留弃用代理；route、正文、diagnostics、assets、warnings、trace 与 merged metadata 使用 typed 字段。

### PF-AUDIT-007：复杂度

- 保留现有 complexity gate，删除已消失或低于阈值的 budget 项。
- 本次触及热点不增加复杂度；`BatchRunner.run_async` 的 budget 基线下降。

### PF-AUDIT-008：macOS contract

- Machine contract 只保留 macOS 支持矩阵、portable/native evidence 区分和安全不变量。
- 删除历史 `[[changes]]`、Windows/global release 镜像与精确 path/test inventory。
- Validator 直接读取 `pyproject.toml`、workflow、installer manifest 与 release asset owner；`AGENTS.md` 同步为精简合同。

### PF-AUDIT-009：BrowserWorkflowDeps

- 改为 frozen、keyword-only dataclass。
- 删除手写字段清单、构造器以及无生产消费者的 view/type。

### PF-AUDIT-010：重复 helper

- 资产 merge/filter、metadata raw values、PDF candidates 与 `srcset` 解析复用现有 owner。
- 保持原有顺序与覆盖语义，不新增 clone detector 或抽象层。

### PF-AUDIT-011：Architecture closeout

- 删除历史 absent-path 墓碑和重复 skill inventory。
- 只保留当前依赖方向、cycle、typed payload 与公开边界断言。

### PF-AUDIT-012：Journal routing 草稿

- 直接删除 `references/journal_lists.yaml` 及文档索引，不归档、不新增刷新 gate。

### PF-AUDIT-013：抽取规则映射

- `quality/fixture-manifest.schema.json` 定义 `tests[]` 的必填 `test`、`anchors`、`samples`，golden manifest 是唯一机器映射。
- 删除测试 docstring marker、文档反向清单、重复 subprocess wrapper 与无差异模式。

### PF-AUDIT-014：Reason code

- 通用 reason code 只在 `paper_fetch.reason_codes` 定义。
- `paper_fetch.quality.reason_codes` 仅显式导入并 re-export。

### PF-AUDIT-015：Browser preflight 状态

- Core 暴露唯一状态顺序，MCP 直接消费。
- 未知状态显式报错，不得被汇总为 `ready`。

### PF-AUDIT-016：Markdown 资产字段

- `extraction/html/asset_fields.py` 定义唯一 Markdown 资产引用字段 tuple。
- Rendering、model rewrite 与 IOP 共用该 tuple。

### PF-AUDIT-017：未接线执行路径

- 删除 `providers/browser_workflow/direct_http.py`、`scripts/fulltext_links.py` 及相关导出/说明。

### PF-AUDIT-018：Fixture size baseline

- 删除 fixture size baseline 与文档索引；保留真实 fixture provenance、schema 与行为测试。

### PF-AUDIT-019：Package/devtool 边界

- Markdown review、quality issue 与 benchmark-only 公式代码位于 `paper_fetch_devtools` 或 benchmark script。
- Production wheel 不包含兼容模块或 `paper_fetch_devtools`；运行时公式 backend 不维护 benchmark 维度。

### PF-AUDIT-020：Cleaning evidence

- 删除已跟踪的 `.evidence.yml`；proposal 只保留 compact contract 与 fixture digest。
- 删除 evidence path 传播与存在性断言；现场 contract check 继续从 fixture 重建事实。

### PF-AUDIT-021：易失快照

- 删除固定项目版本、发布日期、provider 当前数量和 fixture 当前数量断言/说明。
- 保留动态版本同步、schema version、安全上限、零缺口与 catalog/corpus 一致性断言。

### PF-AUDIT-022：Geography 专项管线

- 删除 geography live/report/artifact 模型、脚本、sample catalog、live 入口与专属测试；不迁移无消费者 DOI。
- 通用 golden live 是唯一 repo-local live 生命周期。

## v6 边界

- 版本源同步为 `6.0.0`，迁移说明见 `docs/migration-v6.md`。
- 保留五个预设、resolver/provider adapter、统一 acceptance、cache/artifact、来源追踪和合法访问约束。
- 不运行 live，不主动触发 GitHub CI；原生 `macos-15`/CPython 3.14 gate 仍是发布前平台证据。
