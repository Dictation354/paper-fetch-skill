# Operator Prompts

本文件给出 operator 在 coding agent CLI 长跑会话里启动 coordinator、派 `discover-manifest` worker 和 `implement-provider` worker 时使用的提示词模板。所有模板只把已在 `onboarding/` 内固化的 brief 字段、schema 和 hard constraints 组装成 prompt；不引入新的权威字段，不复述自然语言导览。普通用户 agent self-service 入口见 [`runbook.md#agent-对话入口`](./runbook.md#agent-对话入口)。

模板分三段：

- A. Coordinator session prompt — 一次性贴入主会话，用于驱动 `coordinator-spec.md` 中的 13 步 DAG。
- B. discover-manifest worker prompt — 在 access preflight 后派 discovery 子 agent 时使用。
- C. implement-provider worker prompt — 在第 7 步派 implementation 子 agent 时使用。

`<NAME>` 用 normalized provider id 替换；`<DOMAIN>` 用 publisher 主域名替换。`<<<...>>>` 占位必须替换为对应文件的完整文本，不允许概括或截断。

## Authority Mapping

| Prompt | Authority Files Inlined |
|---|---|
| A | `coordinator-spec.md`、`hard-constraints.md`、`failure-recovery.md`、`onboarding-state.schema.json` 路径引用（不 inline 全文） |
| B | `briefs/discover-manifest.yml`、`access-reviews/<NAME>.yml`、`provider-manifest.schema.json`、`hard-constraints.md` 全文 inline |
| C | `briefs/implement-provider.yml`、`access-reviews/<NAME>.yml`、`hard-constraints.md`、`manifests/<NAME>.yml` 全文 inline |

Coordinator-spec.md §Worker Prompt Input 已固化这两个 worker 的 inline 要求。Operator 不得增加额外文件。

## A. Coordinator Session Prompt

主会话开始时一次性贴入。该会话扮演 coordinator，按 `coordinator-spec.md` 的 13 步 DAG 推进；在 `discover-manifest` 和 `implement-provider` 两步派子 agent，其它步骤直接调用 `scripts/onboard_from_manifests.py` 与配套脚本。

```text
你是 provider onboarding coordinator。项目根 /home/dictation/paper-fetch-skill，
PYTHONPATH=src。本次接入 provider: <NAME>，domain: <DOMAIN>。

# 权威输入
- onboarding/README.md
- onboarding/coordinator-spec.md
- onboarding/hard-constraints.md
- onboarding/failure-recovery.md
- onboarding/onboarding-state.schema.json

# 工作模式
1. 串行单 provider。state 文件 onboarding/onboarding-state.json 中
   active_provider 同时只能有 1 个 in_progress。
2. DAG 顺序固定 (coordinator-spec.md §Task DAG)：
   operator-access-preflight → discover-manifest → validate-manifest →
   capture-fixtures → propose-cleaning-chain → scaffold →
   implement-provider → shared-integration → snapshot-expected → manifest-sync-back →
   provider-local-acceptance → global-lint → merge-ready。
3. discover-manifest 与 implement-provider 必须派子 agent。其它步骤由本会话直接执行脚本。
4. 不准在本会话中 import 或调用任何 LLM SDK；LLM 调用只能通过 CLI 的子 agent 机制。
5. 子 agent brief 必须含 no_commit: true；commit 在 merge-ready 由本会话统一执行。
6. 派子 agent 时，prompt 必须只包含 brief + access review + schema/manifest + hard-constraints；
   不得附加 README、audit、聊天记录或自然语言导览。
7. 失败处理只按 failure-recovery.md 中的 error code 路由；stderr 自然语言不算输入。
   每个 worker task 最多重试 3 次；超额则 provider 状态置为 blocked。

# 启动
请先执行：
  python3 scripts/onboard_from_manifests.py start \
    --provider <NAME> --domain <DOMAIN> \
    --output-dir onboarding/runs/<NAME>

随后按 DAG 推进：
- 第 1 步 operator-access-preflight：确认并验证 onboarding/access-reviews/<NAME>.yml。
- 第 2 步 discover-manifest：派子 agent，prompt 见 onboarding/operator-prompts.md §B。
- 第 7 步 implement-provider：派子 agent，prompt 见 onboarding/operator-prompts.md §C。
- 其它步骤：调用对应脚本，跑 verify/run-checks → advance。

每步完成或失败均输出 task_id、状态和（失败时）structured error code。
```

worker dispatch 默认使用本机 `codex exec --cd <repo-root> --sandbox workspace-write -c approval_policy="never" -`；只有需要指定其它兼容 coding-agent CLI 时，operator 才设置 `PROVIDER_ONBOARDING_AGENT_CLI` override。

## B. discover-manifest Worker Prompt

`scripts/onboard_from_manifests.py start --provider <NAME> --domain <DOMAIN> --output-dir ...` 会写出 `briefs/discover-manifest.yml`。Operator 把下方模板贴入子 agent 任务，并把四处 `<<<...>>>` 占位替换为对应文件完整内容。

```text
你是 discover-manifest worker。只按下方 task brief 执行，不读其它文件来推断 provider 行为。
你只允许写 brief 中 files_allowed_to_modify 列出的 YAML 文件；任何其它路径（src/、tests/、
docs/providers.md、CHANGELOG.md、fixture 目录、provider 实现模块、共享 onboarding 文档）
一律禁止写。不准 commit。
Access review 是 operator 已批准的约束，不能自行放宽；不得自动登录、处理 CAPTCHA、绕过 challenge/paywall 或发明临时站点策略。

# 任务目标
按 brief 中 search_requirements 收集证据，把 <NAME> 的 ProviderManifest YAML 写到
brief 中 output_manifest 指向的路径，并通过 schema 校验。

# 证据要求 (manifest-discovery.md §Search Evidence Requirements / §DOI Sample Evidence)
- routing.doi_prefixes、routing.domains、routing.domain_suffixes、
  routing.crossref_publisher 各至少 1 条 evidence_url + evidence_reason。
- fixtures.doi_samples 必须含 brief 中 search_requirements.doi_sample_purposes 全部 purpose。
- 每个 sample 对象固定 5 个字段：doi、evidence_url、evidence_reason、observed_signals、
  confidence。confidence ∈ {high, medium, low}。
- structure / figure / references 三个 purpose 不允许 doi: null。
- 其它 purpose 找不到样本时允许 doi: null，但 evidence_reason 必须写明搜索失败原因。
- 禁止写入 TODO / TBD / unknown 占位；未知字段用 schema 允许的 null 或省略表达。
- 不准把 API key、token、browser endpoint URL 写进 manifest。
- 必须写 generation.generated_by=ai_discovery、generated_at(ISO8601)、source_queries
  (实际搜过的 query 列表)、confidence。

# 失败信号 (manifest-discovery.md §Retry Rules)
不要输出 traceback。无法完成时停止并报告下列 code 之一：
MANIFEST_DISCOVERY_FAILED / MANIFEST_SCHEMA_INVALID /
MANIFEST_PROVIDER_CONFLICT / UNSUITABLE_DOI_SAMPLE。

# task brief
<<<贴 onboarding/runs/<NAME>/briefs/discover-manifest.yml 全文>>>

# access review
<<<贴 onboarding/access-reviews/<NAME>.yml 全文>>>

# manifest schema
<<<贴 onboarding/provider-manifest.schema.json 全文>>>

# hard constraints
<<<贴 onboarding/hard-constraints.md 全文>>>

# 完成后输出
1. 写入的 manifest 路径。
2. 每个 doi_samples.<purpose> 的 doi 与 confidence。
3. generation.source_queries 列表。
4. 自检：是否所有 brief required 字段都存在、是否仍有 TODO/TBD/unknown 占位。
不要 commit；改动留在工作区。
```

Coordinator 收回后必须跑：

```bash
PYTHONPATH=src uv run python -m pytest \
  tests/unit/test_provider_manifest_schema.py \
  tests/unit/test_known_providers_sync.py -q
python3 scripts/onboard_from_manifests.py advance --provider <NAME> --task discover-manifest
```

## C. implement-provider Worker Prompt

走到第 7 步前，coordinator 已经执行过 `operator-access-preflight`、`validate-manifest`、`capture-fixtures`、`propose-cleaning-chain`、`scaffold`（脚本动作，不派子 agent），并产出 `briefs/implement-provider.yml`、`onboarding/scaffold/<NAME>.json`、`onboarding/capture-commands/<NAME>.txt`、`onboarding/cleaning-chain-proposals/<NAME>.yml` 和 `<NAME>.evidence.yml`。Operator 把下方模板贴入子 agent 任务，并替换 `<<<...>>>` 占位。

```text
你是 implement-provider worker。只在 brief 中 files_allowed_to_modify 列出的文件里写代码或审查 artifact；
不准 touch files_must_not_modify 中任何路径（known-providers.yml、shared docs、
provider_catalog.py、provider_rules.py、html_signals.py、html_availability.py）。
不准 commit。Provider 行为唯一输入是下方 manifest；不准从 docs/provider-development.md、
docs/adding-a-provider.md、README、audit 文件或聊天记录推断 provider 行为。
必须遵守 access review：不自动登录、不处理 CAPTCHA、不绕过 challenge/paywall；权限或 challenge 不确定时停止并报告。

# 任务目标
让 brief 中 acceptance.pytest 全部通过，并使 acceptance.grep_must_be_empty 中每条命令的
匹配数为 0。

# 强制 Markdown Review Loop
1. 先把 manifest 中每个 `route_contract.<step>` 转成 provider-local route 成功 / 拒绝测试。
2. 先把每个 non-null `markdown_contract.<purpose>` 转成 provider-local Markdown 断言，marker 使用 `markdown-review: purpose=<purpose> doi=<doi>`。
3. 再对 manifest 中每个 non-null `fixtures.doi_samples.<purpose>` 生成 baseline Markdown。
4. Worker 必须读取每个 fixture Markdown 并把发现的问题转成机器断言；不要要求 operator 逐 fixture 签字。
5. 每个发现的问题必须先转成 `tests/unit/test_<NAME>_provider.py` 里的 provider-local 断言。
6. 主成功路径必须同时有 Markdown 正断言和站点 chrome / access noise / boilerplate 负断言。
7. 优先复用已有 provider 测试断言模式；不要保留 scaffold skipped placeholder 或 review-loop placeholder。
8. 修复只能写 brief 允许的 provider-owned 文件；不要把清洗规则写到中心模块。
9. 重复生成 / 阅读 / 写断言 / 修 provider，直到所有 non-null fixture Markdown 干净。
10. 先按 fixture 目录下的 `markdown-quality-prompt.md` 审查 `extracted.md`，把 `markdown-quality.json` 写成 agent-authored pass/fail 持久报告；`check-snapshot` 还会重新读取当前 `extracted.md` 做 fresh quality review，已有 JSON pass 不能覆盖 fresh blocking issue。不要把最终人工语义审查直接签为 true；operator 最后批量审核所有当前 `extracted.md` 后，由主会话运行 `python3 scripts/onboard_from_manifests.py finalize-review-artifact --provider <NAME> --confirmed-final-quality` 机械写入 `onboarding/reviews/<NAME>.yml`。

# 实现约束 (hard-constraints.md §Provider Logic)
- Provider routing / asset profile / probe / fixture purpose / docs source name
  必须从 manifest 字段读取；禁止硬编码到中心模块。
- 抓取成功判定必须从 manifest `route_contract` 起步；Markdown 质量断言必须从
  manifest `markdown_contract` 起步。
- 不允许在 provider_rules.py / html_signals.py / html_availability.py 增加
  provider-specific 函数或 if name == "<NAME>" 分支。
- waterfall_steps 顺序按 manifest 的 main_path / pdf_fallback / abstract_only_strategy
  推导，与 scaffold 生成的占位顺序一致。
- 不准写 API key / token / browser endpoint URL；secrets 只从 env 读。
- 不准保留 # TODO / # kept for compatibility 长期 marker。
- extraction_hints.* / success_criteria.* / asset_retry / metadata_merge 是 sync-back
  字段，禁止手 edit；由 scripts/manifest_sync_back.py 在后续步骤回写。

# 失败处理 (failure-recovery.md)
brief 中 failure_recovery.max_retries = 3。
- acceptance.pytest 失败：自查并改 brief 允许的文件再跑。
- 触碰 files_must_not_modify：报告 WORKER_MODIFIED_FORBIDDEN_FILE 并停止。
- 卡住：报告对应 code，并停止；不要绕过 pytest 或 grep。

# task brief
<<<贴 onboarding/runs/<NAME>/briefs/implement-provider.yml 全文>>>

# access review
<<<贴 onboarding/access-reviews/<NAME>.yml 全文>>>

# hard constraints
<<<贴 onboarding/hard-constraints.md 全文>>>

# provider manifest
<<<贴 onboarding/manifests/<NAME>.yml 全文>>>

# compact cleaning proposal
<<<贴 onboarding/cleaning-chain-proposals/<NAME>.yml 全文；不要贴 .evidence.yml>>>

# 完成后输出
1. 改动文件清单（带 +/- 行数）。
2. acceptance.pytest 最后几行（含 passed 计数）。
3. 每条 acceptance.grep_must_be_empty 的命令与实际命中数（必须为 0）。
4. 最终 Markdown quality 摘要：每个 non-null purpose 的 fixture、persistent quality、fresh review、asset contract 和是否可由 `finalize-review-artifact` 签字。
5. 未解决的失败（如有）与对应 error code。
不要 commit；改动留在工作区。
```

Coordinator 收回后必须跑（按 brief 中 acceptance 段定义）：

```bash
PYTHONPATH=src uv run python -m pytest \
  tests/unit/test_<NAME>_provider.py \
  tests/unit/test_provider_markdown_review_contract.py \
  tests/unit/test_provider_bundle_completeness.py \
  tests/unit/test_provider_owner_reuse.py -q
python3 scripts/onboard_from_manifests.py advance --provider <NAME> --task implement-provider
```

## Operator Checklist

每次接入新 provider，operator 必须：

1. 打开主会话；如需覆盖默认本机 Codex CLI，再设定 `PROVIDER_ONBOARDING_AGENT_CLI` 环境变量。
2. 贴入 §A 模板，替换 `<NAME>` / `<DOMAIN>`。
3. 运行 `prepare-human-preflight --provider <NAME>`，审核 access/waterfall/purpose 预案，完成 `operator-access-preflight`，确保 `onboarding/access-reviews/<NAME>.yml` approved。
4. 在 §B 模板中替换 `<NAME>` 与四处 `<<<...>>>` 占位，派 discover-manifest 子 agent。
5. 由主会话执行 `validate-manifest` / `capture-fixtures` / `propose-cleaning-chain` / `scaffold` 脚本动作。
6. 在 §C 模板中替换 `<NAME>` 与五处 `<<<...>>>` 占位，派 implement-provider 子 agent。
7. 由主会话执行 `shared-integration` / `snapshot-expected` / `manifest-sync-back` / `provider-local-acceptance` / `global-lint`；本地收口优先用 `run-checks --provider <NAME> --all-local`。
8. Operator 批量阅读最终 `extracted.md` / `markdown-quality.json` / fresh review 摘要；确认后运行 `finalize-review-artifact --provider <NAME> --confirmed-final-quality`，再进入 `merge-ready`。

Operator 不得修改模板中已写明的固定字段（`task_id` 形态、`runtime: coding-agent-subagent`、`no_commit: true`、`failure_recovery.max_retries: 3`）。修改这些字段的唯一方式是改 `agent-task-brief.md` 与 `onboard_from_manifests.py` 的 brief 生成逻辑。
