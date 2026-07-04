# 自助添加出版社 Provider

本页是普通用户在 agent 对话里自助添加出版社 provider 的入口。你不需要手动学习 coordinator DAG、state JSON 或 worker prompt；通常只要发一句 `/goal`，agent 会按项目内 onboarding 流程推进，并在必须人工判断时停下。

内部权威细节仍由本目录下的专门文档承载：执行入口见 [`instruction.md`](./instruction.md)，用户/agent runbook 见 [`runbook.md`](./runbook.md)，合入验收见 [`acceptance.md`](./acceptance.md)，manifest 字段见 [`provider-manifest.md`](./provider-manifest.md)，强约束见 [`hard-constraints.md`](./hard-constraints.md)。本 README 只做用户入口说明，不作为 AI worker 推断 provider 行为的输入。

边界保持不变：流程不会绕过付费墙，不会替你批准 access review，不会解决 CAPTCHA/challenge，不会默认触发 GitHub CI，也不会自动提交 commit。

## 最快开始

在 agent 对话中发送：

```text
/goal follow onboarding/instruction.md 添加 <provider> Provider，domain 是 <domain>，目标 merge-ready
```

如果不知道 DOI prefix，可以省略；discovery 会尝试自动找到合适的 DOI 样本。如果你知道 DOI prefix，可以补充：

```text
DOI prefix 是 10.xxxx/
```

`merge-ready` 是完整合入标准。若你只想先做到本地可用，可以把目标写成 `local-ready`，或省略目标让 agent 使用默认档位。

## 一键 prompt 示例

通用模板：

```text
/goal follow onboarding/instruction.md 添加 <provider> Provider，domain 是 <domain>，目标 merge-ready
```

示例：

```text
/goal follow onboarding/instruction.md 添加 NewPub Provider，domain 是 https://newpub.example/，目标 merge-ready
```

如果该 provider 已经存在，agent 应从现有 state、manifest、access review、review artifact 和 run logs 继续，而不是从零覆盖已有成果。

## 自动流程会做什么

agent/coordinator 会尽量自动完成中间链路：

- 生成或读取 `onboarding/manifests/<provider>.yml`。
- 发现 DOI 样本，补齐 structure、figure、references、table、formula、supplementary 等 purpose 覆盖证据。
- 捕获 fixture，并为不可用样本按 structured error 做诊断、替换或恢复。
- 生成 cleaning proposal，约束后续清洗和 Markdown contract delta。
- scaffold provider，并在已有文件存在时生成安全合并计划。
- 实现 provider-owned waterfall、route 成功/拒绝逻辑、HTML/XML/PDF 转换、资产处理和 provider-local 测试。
- 生成 expected snapshots、`extracted.md` 和 Markdown quality artifact。
- 运行 Markdown quality repair loop，修复 fresh review 发现的 blocking issue。
- 同步 manifest docs facts、shared docs、known provider index 和必要的共享集成。
- 执行本地验收命令，默认不触发 GitHub CI。

状态上，`local-ready` 表示主路径本地可用，最小 provider-owned 验证通过，但还不是完整合入标准。`merge-ready` 表示 manifest、fixture、route、asset、Markdown contract、review artifact、snapshots、sync-back、provider-local acceptance、shared integration、global lint、docs drift 和 extraction rules validation 都已通过，并且人工 signoff 已写入。

## 人工必须审核的部分

流程只有两个强制人工 gate；agent 不能代替你做这些判断。

第一个 gate 是 `access/waterfall/purpose preflight`。你需要查看 `prepare-human-preflight` 输出和 `onboarding/access-reviews/<provider>.yml`，确认：

- 合法访问来源是否允许继续。
- allowed runtime 是否覆盖当前路线，例如 HTTP、browser 或 publisher API。
- challenge、CAPTCHA、paywall、rate limit 和临时站点策略是否可接受。
- waterfall 顺序、route 成功/拒绝条件和 purpose coverage 计划是否合理。
- `status: approved` 与 `may_continue: true` 是否应由你写入。

agent 可以生成 blocked 草稿和预检摘要，但不能替你把 access review 改成批准。

第二个 gate 是 `final Markdown semantic review`。你需要批量查看当前 `extracted.md`、`markdown-quality.json`、fresh review 摘要和 `onboarding/reviews/<provider>.yml`，确认：

- 正文结构、章节层级和关键段落语义完整。
- References 可识别，且没有被站点 chrome、access noise、错误页或重复 boilerplate 污染。
- Figures、tables、formulas 和 supplementary 信息符合 manifest contract。
- persistent quality 与 fresh quality 均为 pass，且没有 blocking issue。

确认后告诉 agent：

```text
已确认最终 Markdown 质量，继续 <provider> provider 到 merge-ready
```

随后由 `finalize-review-artifact --confirmed-final-quality` 在当前 artifact 上写入最终 signoff；agent 不能提前伪造 `markdown_semantic_reviewed: true`。

## 常用继续与诊断 prompt

继续推进：

```text
继续 <provider> provider 到 merge-ready
```

查看状态：

```text
查看 <provider> provider 状态
```

诊断阻塞：

```text
诊断 <provider> provider 为什么卡住
```

最终 Markdown 审核通过后继续：

```text
已确认最终 Markdown 质量，继续 <provider> provider 到 merge-ready
```

## 进一步阅读

常用用户入口和 operator 话术：

- [`instruction.md`](./instruction.md)：可复用 `/goal follow onboarding/instruction.md 添加 <provider> provider` 执行入口。
- [`runbook.md`](./runbook.md)：agent 对话入口、自然语言 prompt、简化状态、人工 gate 输出和 blocked 恢复话术。
- [`operator-prompts.md`](./operator-prompts.md)：coordinator session 和 worker dispatch prompt 模板。
- [`scripts/provider_agent.py`](../scripts/provider_agent.py)：agent-facing `add`、`continue`、`status`、`doctor` 包装层。
- [`scripts/onboard_from_manifests.py`](../scripts/onboard_from_manifests.py)：coordinator DAG、state、task brief、verification plan 和本地 runner 入口。

机器权威和验收：

- [`agent-task-brief.md`](./agent-task-brief.md)：discovery 与 implementation worker brief 必填字段。
- [`coordinator-spec.md`](./coordinator-spec.md)：coordinator invocation、固定 DAG、state machine、retry 和 worker isolation。
- [`hard-constraints.md`](./hard-constraints.md)：worker scope、provider-owned 边界、pytest 和 grep acceptance。
- [`acceptance.md`](./acceptance.md)：machine-verifiable merge-ready 定义。
- [`failure-recovery.md`](./failure-recovery.md)：structured JSON error `code` 到恢复动作的映射。
- [`automation-roadmap.md`](./automation-roadmap.md)：自动化范围、runner、worker dispatch、live gate 和不可自动化边界。
- [`manifest-discovery.md`](./manifest-discovery.md)：discovery worker 输入、证据要求、schema 输出和 retry 规则。

Schema、manifest 和审核 artifact：

- [`provider-manifest.md`](./provider-manifest.md)：provider manifest 字段参考。
- [`provider-manifest.schema.json`](./provider-manifest.schema.json)：provider manifest JSON Schema。
- [`access-review.schema.json`](./access-review.schema.json)：operator access preflight JSON Schema。
- [`provider-review.schema.json`](./provider-review.schema.json)：fixture 代表性和 Markdown semantic review JSON Schema。
- [`onboarding-state.schema.json`](./onboarding-state.schema.json)：coordinator state JSON Schema。
- [`known-providers.yml`](./known-providers.yml)：provider manifest index 和 status registry。
- [`manifests/`](./manifests/)：已登记 provider manifest；当前 provider 集合以本目录和 [`known-providers.yml`](./known-providers.yml) 为准。
- [`cleaning-chain-proposals/`](./cleaning-chain-proposals/)：fixture-derived cleaning proposal artifacts；proposal 不替代 provider implementation 或人工 semantic review signoff。
- [`access-reviews/`](./access-reviews/)：operator 对合法访问、runtime、challenge/CAPTCHA、paywall 和临时站点策略的审核记录。
- [`reviews/`](./reviews/)：fixture 代表性和最终 Markdown semantic review artifact。

Human references：

- [`docs/provider-development.md`](../docs/provider-development.md) 和 [`docs/adding-a-provider.md`](../docs/adding-a-provider.md) 仍可作为背景资料，但 AI/coordinator provider onboarding 必须以 `onboarding/` 下的 schema、manifest、brief、hard constraints、failure recovery 和 acceptance 文档为准。两者与 onboarding authority 的漂移由 `tests/unit/test_human_docs_drift.py` 检查。
