# AI Onboarding Automation Scope

本文记录 provider onboarding 中当前可以由脚本 / agent 自动完成的部分，以及必须由 operator 保留的人工边界。它补充 [`README.md`](./README.md)、[`coordinator-spec.md`](./coordinator-spec.md) 和 [`acceptance.md`](./acceptance.md)，不替代 manifest、access review 或 provider review schema。

普通用户 agent 对话入口、状态展示和可复制 prompt 见 [`runbook.md#agent-对话入口`](./runbook.md#agent-对话入口)；本文只记录现有自动化能力、不可自动化边界和 runner/worker 维护说明。

## 可自动化项

- `scripts/onboard_from_manifests.py run` 串行执行 provider DAG，并持久化 state、DAG、worker brief、worker stdout/stderr/prompt 日志。
- `scripts/onboard_from_manifests.py prepare-discovery` 可在 discovery worker 前生成 `<output-dir>/discovery/evidence-pack.json`，包含 query plan、Crossref/OpenAlex candidate、HTTP-first publisher 页面信号、score/confidence、probe route 证据和 rejection hint；当 HTTP probe request failed、403/429/challenge、empty shell 或缺少当前 purpose 信号时，默认 `--browser-fallback auto` 会在 access review 允许 `browser`/`playwright` 的前提下复用现有 browser workflow 做一次候选 fallback。`--no-network` 只生成 query plan 并禁用 browser，供默认单测和离线预检使用。
- `scripts/onboard_from_manifests.py run --provider ...` 会在派发 `discover-manifest` 前自动写 evidence pack，把摘要加入 worker prompt，并在 `validate-manifest` 前自动执行一次 `autofix-manifest --write`。
- `validate-manifest` 若以 `MANIFEST_SCHEMA_INVALID` 失败，runner 会再执行一次 targeted manifest autofix 并重跑 validate；仍失败才按既有 retry/blocked 流程处理。
- `scripts/onboard_from_manifests.py inspect-discovery` 可只读列出候选、低置信度 purpose 和 discovery proof 缺口。
- `scripts/onboard_from_manifests.py prepare-human-preflight --provider <name>` 可只读生成第一个人工 gate 摘要：access review、waterfall、route contract、asset contract、purpose coverage、null proof 和 operator checklist。
- `scripts/capture_fixture.py --auto-via` 根据 manifest `probe.requires_browser_runtime` / `probe.requires_playwright` 和 access review `allowed_runtimes` 选择 `http` 或 `browser`。
- fixture capture 对 `HTTP_FORBIDDEN`、`HTTP_RATE_LIMITED`、`CHALLENGE_DETECTED` 可在 access review 允许 browser runtime 时自动 retry 到 browser route；否则返回 structured JSON。
- Discovery browser fallback 不写 fixture，也不绕过 CAPTCHA、paywall、login 或 challenge；browser 失败只写 `probe.browser_failure_code` 和 nested probe 证据，后续仍由 `capture-fixtures --auto-via` 统一捕获。
- `scripts/scaffold_provider.py --from-manifest --merge-existing=safe` 复用相同内容，保留完整已有 provider 文件，并继续生成 fixture/capture/scaffold summary。
- `scripts/bootstrap_review_artifact.py` 从 manifest non-null fixtures 和 `extra_fixtures` 生成 review 草稿，填入 `extracted.md` 路径/sha256、agent-authored `markdown-quality.json` 路径/sha256、manifest assertions 和初始问题分类；pending quality report 会进入草稿 issue。
- `scripts/backfill_access_reviews.py --all --write` 可为已实现 provider 回填 blocked access review 草稿；`--provider <name> --domain <domain> [--doi-prefix <prefix>] --write` 可为尚未登记的新 provider 生成 seed 草稿。已实现 provider 草稿只来自 manifest、known-providers、bundle capabilities 和本地 fixture evidence；seed 草稿只来自显式 provider/domain/DOI prefix 输入，仍不批准 access。
- `scripts/onboard_from_manifests.py run` 会在 `capture-fixtures` 后固定执行 `propose-cleaning-chain`，调用 `scripts/propose_cleaning_chain.py --provider <provider> --write` 生成 compact proposal 和 full evidence。
- `scripts/onboard_from_manifests.py diagnose` 可只读分诊 blocked state；`resume-blocked --dry-run` 只输出续跑计划；非 dry-run 只在 retryable failure 且 access review 已批准、无 operator-only blocker 时复用现有 runner 续跑。
- `scripts/onboard_from_manifests.py summarize --provider <provider>` 可从 state、manifest、access review、review artifact 和真实 run records 合成 JSON/Markdown operator digest。
- `scripts/onboard_from_manifests.py summarize --format agent-json|agent-markdown --target local-ready|merge-ready` 可把 state、failure code、fixture 覆盖和 Markdown review artifact 翻译成 agent 对话中的简化状态、停下原因、下一句话和相关文件。
- `scripts/provider_agent.py add|continue|status|doctor` 是 agent-facing 包装层：默认目标 `local-ready`，只在显式 `--target merge-ready` 时推进完整合入标准；它不维护独立 DAG/state，不替代 `onboarding/`，只调用现有项目脚本。
- `scripts/onboard_from_manifests.py check-snapshot --provider <provider> --doi <doi>` 每次通过默认本机 Codex CLI 或 `PROVIDER_ONBOARDING_AGENT_CLI` override 重新读取当前 `extracted.md`，写入 fresh Markdown quality report；fresh blocking issue 会阻断，即使已有 `markdown-quality.json` 是 pass。
- `scripts/onboard_from_manifests.py repair-markdown-quality --provider <provider> --doi <doi>` 可把 fresh review 或持久 `markdown-quality.json` 暴露的 blocking issue 转成最多 3 轮修复闭环：派发实现 agent、运行 provider-local 验证和 snapshot、再派发 quality review agent 写回 pass/fail。
- `scripts/onboard_from_manifests.py finalize-review-artifact --provider <provider> --confirmed-final-quality` 可在 operator 完成最终批量 Markdown 质量审核后，机械校验并写入 `onboarding/reviews/<provider>.yml` 的每个 fixture signoff。
- `tests/unit/test_provider_asset_contract.py` 可自动验证 manifest `asset_contract.figures`、正文图片位置，以及 `download: required` provider-local marker 是否包含真实下载断言。
- `scripts/run_provider_drift_report.py` 可本地手动生成 route-source drift report；fake runner 可单测 schema，真实 runner 需要 `PAPER_FETCH_RUN_LIVE=1`。
- `scripts/manifest_sync_back.py --sync-docs` 从 manifest docs facts 同步 `known-providers.yml`、provider matrix、extraction rules marker row 和 changelog marker entry。

## 不可自动化边界

- access approval 不能由脚本伪造；`onboarding/access-reviews/<provider>.yml` 必须由 operator 批准，且 `may_continue: true`。
- manifest autofix 不能替代 discovery worker 写 manifest 初稿；它只补机器可判 schema/proof/contract 缺口。低置信 DOI candidate 只能写入 proof/rejection，不会自动替换样本。
- access review backfill 草稿默认 `status: blocked`、`may_continue: false`；脚本不得把草稿升级为批准。
- CAPTCHA、paywall、challenge、登录和权限不确定时，脚本不得绕过；只能按 access review 和 [`failure-recovery.md`](./failure-recovery.md) stop / retry / report。
- `markdown_semantic_reviewed: true` 不能由 bootstrap 自动设置；最终 Markdown 语义审查签字必须来自 operator 对当前 Markdown/quality/fresh review 的批量审核，并通过 `finalize-review-artifact --confirmed-final-quality` 写入。
- cleaning proposal 只能生成建议和风险报告，不直接修改 provider implementation，也不更新 `markdown_semantic_reviewed`。Implementation worker 只接收 compact proposal；full evidence artifact 留给 coordinator/operator 复核。
- markdown quality repair 可以更新 `markdown_quality_sha256` / snapshot hash，但不得把 `markdown_semantic_reviewed` 自动改为 true；最终语义签字仍归 operator，脚本只在显式 `--confirmed-final-quality` 后机械写入。
- figure asset 语义不能由脚本自动豁免；无正文内联图、无本地下载路径、只保留 caption appendix 或没有下载测试 marker 时必须回到实现/manifest 修复，只有 text-only、不可下载或 access/empty-shell 类样本可写明 `not_applicable` 原因。
- worker 不得修改 shared docs、central provider logic 或未授权路径；runner 会用 git changed-path diff 同时检测 forbidden writes 和 `files_allowed_to_modify` 外的越界写入。
- GitHub CI 不由 onboarding runner 触发；本地 gate 只运行 repo-local commands。

## Runner 命令

```bash
python3 scripts/onboard_from_manifests.py run \
  --provider mdpi \
  --domain mdpi.com \
  --output-dir .paper-fetch-runs/mdpi-onboarding

python3 scripts/onboard_from_manifests.py prepare-discovery \
  --provider mdpi \
  --domain mdpi.com \
  --doi-prefix 10.3390 \
  --output-dir .paper-fetch-runs/mdpi-onboarding \
  --browser-fallback auto

python3 scripts/onboard_from_manifests.py inspect-discovery \
  --manifest onboarding/manifests/mdpi.yml \
  --evidence-pack .paper-fetch-runs/mdpi-onboarding/discovery/evidence-pack.json

python3 scripts/onboard_from_manifests.py prepare-human-preflight \
  --provider mdpi \
  --domain mdpi.com \
  --doi-prefix 10.3390

python3 scripts/onboard_from_manifests.py run \
  --manifest onboarding/manifests/mdpi.yml \
  --until merge-ready

python3 scripts/onboard_from_manifests.py finalize-review-artifact \
  --provider mdpi \
  --confirmed-final-quality

python3 scripts/onboard_from_manifests.py diagnose \
  --state onboarding/onboarding-state.json

python3 scripts/onboard_from_manifests.py resume-blocked \
  --provider mdpi \
  --dry-run

python3 scripts/onboard_from_manifests.py summarize \
  --provider mdpi \
  --format markdown \
  --output .paper-fetch-runs/mdpi-onboarding/summary.md

python3 scripts/provider_agent.py add \
  --provider mdpi \
  --domain mdpi.com

python3 scripts/provider_agent.py continue \
  --provider mdpi \
  --target merge-ready

python3 scripts/onboard_from_manifests.py repair-markdown-quality \
  --provider mdpi \
  --doi 10.3390/su12072826 \
  --output-dir .paper-fetch-runs/mdpi-markdown-repair
```

`--until <task>` 是 inclusive cutoff；完成该 task 后停止，并把下一步保留在 state 中。`--state` 默认写 `onboarding/onboarding-state.json`。

真实网络 discovery 是 runner 默认行为；默认 CI/单元测试使用 fake transport 或 `prepare-discovery --no-network`，不把 live discovery/browser probe 纳入常规 gate。

从零实现、已有 manifest 继续、查漏补缺、单 DOI quality repair 和 blocked state 恢复的场景化命令组合，统一见 [`runbook.md`](./runbook.md)。

## Worker Dispatch 契约

- runner 默认通过本机 `codex exec --cd <repo-root> --sandbox workspace-write -c approval_policy="never" -` 调用 coding-agent-subagent；`PROVIDER_ONBOARDING_AGENT_CLI` 仅作为 operator override。脚本不接入 LLM SDK。
- prompt 通过 stdin 输入，内容包含 worker brief、access review、hard constraints，以及 discovery schema 或当前 manifest。
- 日志写入 `<output-dir>/workers/<task>-attempt-N.{prompt.md,stdout.log,stderr.log}`。
- 调用前后读取 git changed paths；新增 forbidden path 或 `files_allowed_to_modify` 外的变更都会以 `WORKER_MODIFIED_FORBIDDEN_FILE` 失败。
- worker retry limit 是 3；CLI 非零退出耗尽后返回 `TASK_RETRY_EXHAUSTED`。
- fresh Markdown quality worker 只能写 `.paper-fetch-runs/.../fresh-markdown-quality.json`；markdown quality repair 的实现 agent 只能写推断 scope：provider-owned implementation/tests、对应 fixture/review artifact，以及 table/formula/reference/asset 等明确 shared domain 的 shared renderer/test 路径；quality review agent 只能写对应 `markdown-quality.json`。

## Live 策略

- 未来新增 provider 默认需要一次 provider subset live assets review；已有低风险 provider 可豁免。例如：

```bash
PAPER_FETCH_RUN_LIVE=1 python3 scripts/run_golden_criteria_live_review.py --providers mdpi
```

- runner 的 `provider-local-acceptance` 会在 `_provider_requires_live_review()` 为 true 时包含 live review command；新增 provider 默认 true，已有低风险 provider 例外。
- live review 必须比较 `FetchEnvelope.source` 与 manifest `route_sources`，并复用 `markdown_contract` 做自动内容 / 噪声分类。
- 维护期 route-source drift 使用手动本地命令，不接 GitHub CI：

```bash
PAPER_FETCH_RUN_LIVE=1 python3 scripts/run_provider_drift_report.py \
  --provider mdpi \
  --output .paper-fetch-runs/drift/mdpi.json

PAPER_FETCH_RUN_LIVE=1 python3 scripts/run_provider_drift_report.py \
  --all-browser-risk \
  --output .paper-fetch-runs/drift/browser-risk.json
```

## Cleaning Proposal

capture 完成后、implementation worker 修改 provider-owned 代码前，可运行：

```bash
python3 scripts/propose_cleaning_chain.py --provider mdpi --write
python3 scripts/propose_cleaning_chain.py --provider mdpi --check-contract
python3 scripts/onboard_from_manifests.py check-cleaning-proposal --provider mdpi
```

compact proposal artifact 位于 `onboarding/cleaning-chain-proposals/<provider>.yml`，full evidence 位于 `<provider>.evidence.yml`。两者都绑定 `fixtures_digest`；provider-local acceptance 会拒绝过期 digest，并要求先重跑 `propose-cleaning-chain`。Worker 只能把 compact proposal 中带 provenance 的 selector/token/anchor 当作输入证据，仍需用 provider-local tests 固化正负 Markdown 断言后再改实现。

## Failure Recovery 映射

- `ACCESS_REVIEW_NOT_FOUND` / `ACCESS_REVIEW_NOT_APPROVED`：停在 operator gate。
- `UNSUITABLE_DOI_SAMPLE`：回到 `discover-manifest`，只替换失败 purpose 的 DOI sample。
- `HTTP_FORBIDDEN` / `HTTP_RATE_LIMITED` / `CHALLENGE_DETECTED`：若 access review 允许 browser，capture 可自动 retry；否则 stop/report。
- `BROWSER_RUNTIME_REQUIRED`：operator 配置合法 browser runtime，或更新 access review / manifest。
- `WORKER_MODIFIED_FORBIDDEN_FILE`：coordinator 处理 forbidden path diff 后才能重派 worker。
- `MARKDOWN_CONTRACT_DRIFT`：warning-only sentinel/cross-route findings 不失败；missing include、truly vacuous guard 或 stale `fixtures_digest` 失败。stale proposal 先重跑 `propose-cleaning-chain`，真实 contract drift 回到 `implement-provider` 调和当前 provider 的相关 `markdown_contract` purpose。
- `MARKDOWN_QUALITY_FAILED`：`check-snapshot` 的 fresh review 或持久 `markdown-quality.json` 发现 blocking/pending/fail；full runner 会在 `snapshot-expected` 阶段自动尝试 `repair-markdown-quality`。
- `MARKDOWN_QUALITY_REPAIR_FAILED`：最多 3 轮后 fresh review、持久 quality report 或 `check-snapshot` 仍未通过，保留最后 fail report 和 repair logs。
- `PROVIDER_LOCAL_ACCEPTANCE_FAILED` / `GLOBAL_LINT_FAILED`：回到实现或 shared integration 修复；不靠 narrative waiver 通过。
