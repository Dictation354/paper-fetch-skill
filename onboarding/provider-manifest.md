# ProviderManifest v1 字段说明

本文面向实现和维护 provider 的工程读者。`ProviderManifest` 是 capture、scaffold、review 与 sync-back 的输入合约，字段必须能追溯到 runtime catalog、现有 fixture、公开 evidence 或后续 sync-back。

## 顶层字段

| 字段 | Type | Required | 约束 | 决策依据 |
|---|---|---:|---|---|
| `schema_version` | integer | 是 | `1` | 让后续 schema 版本可以并存。 |
| `name` | string | 是 | regex `^[a-z][a-z0-9_]*$`；等于文件名 stem | provider 模块名、bundle name、manifest 文件名使用同一稳定 key。 |
| `display_source` | string | 是 | regex `^[a-z][a-z0-9_]*$` | 映射到运行时公开 source，例如 `wiley_browser`、`copernicus_xml`。 |
| `route_sources` | object | 否 | key 必须来自 `main_path`，value 必须是当前 provider 注册 source；若存在，`display_source` 必须出现在 values 中 | 多 route provider 用它表达 `article_html` / `pdf_fallback` 等路线实际公开 source。 |
| `generation` | object | 是 | 见下表 | 记录 manifest 由 discovery 生成还是由现有 provider 回放生成。 |
| `routing` | object | 是 | 见下表 | scaffold 和路由同步检查的输入。 |
| `main_path` | array[string] | 是 | item enum `landing_html` / `article_html` / `xml` / `pdf_fallback` / `abstract_only` / `metadata_only`；`minItems: 1` | scaffold 用它按顺序生成 provider 主链骨架。 |
| `route_contract` | object | 是 | 每个 `main_path` step 都必须有同名 key | 实现前固定抓取成功 / 拒绝判定，避免只按 HTTP 200 判成功。 |
| `markdown_contract` | object | 是 | 每个 non-null fixture purpose 都必须有同名 key | 实现前固定 Markdown 质量断言，供 scaffold 和 review loop 转成 provider-local tests。 |
| `success_criteria` | object | 是 | step key 到 object / array / `null`；每个 step value 标注 `x-sync-back: true` | 实现完成后由代码侧实际阈值回写。 |
| `asset_profile` | object | 是 | `none` / `body` / `all` 三组数组，item enum `figures` / `body_tables` / `formula_images` / `supplementary` / `multimedia` | 对齐运行时 asset profile 语义。 |
| `asset_contract` | object | 是 | 当前必须含 `figures`；见下方 `asset_contract.figures` | 对 figure fixture 固定正文内联和本地下载契约，避免只用 caption 证明资产支持。 |
| `supplementary_scope` | object | 是 | `selector` / `url_pattern` 可为 string 或 `null` | 描述补充材料的 DOM 或 URL 边界。 |
| `abstract_only_strategy` | string | 是 | enum `provider_managed` / `metadata_only` / `not_supported` | 对齐 provider-managed fallback 行为。 |
| `probe` | object | 是 | 见下表 | provider status 和 live 运行依赖的输入。 |
| `fixtures` | object | 是 | 见下表 | 固定 DOI purpose 到 evidence object 的映射。 |
| `extra_fixtures` | array | 否 | item 见下表；用于固定 purpose 以外的补充 replay 样本 | 让结构广度样本进入 capture/review 流程，但不强迫新增固定 purpose。 |
| `extraction_hints` | object | 是 | 各子字段允许 `null` / `[]` 起步；标注 `x-sync-back: true` | 实现完成后由 bundle/rules 反向序列化。 |
| `owner_reuse_exceptions` | array | 是 | item 需要 `owner` 和 `reason` | 只有通用 owner 无法复用时才记录例外。 |
| `docs` | object | 是 | 需要 `providers_md_capability_row` 和 `changelog_summary`，`extraction_rules_summary` 可为 string/null | scaffold 和 reviewer 使用的用户可见 docs 事实底稿。 |

## `generation`

| 字段 | Type | Required | 约束 | 决策依据 |
|---|---|---:|---|---|
| `generated_by` | string | 是 | enum `ai_discovery` / `manual_replay` | 新 provider 使用 discovery；现有 provider golden manifest 使用 replay。 |
| `generated_at` | string | 是 | JSON Schema `date-time` | 记录生成时间，便于审计 stale manifest。 |
| `source_queries` | array[string] | 是 | `minItems: 1` | 记录 discovery query 或 replay 输入来源；必须覆盖 `fixtures.discovery_proof.*.queries`。 |
| `confidence` | string | 是 | enum `high` / `medium` / `low` | 标识 manifest 初稿证据强度。 |

## `routing`

| 字段 | Type | Required | 约束 | 决策依据 |
|---|---|---:|---|---|
| `primary` | string | 是 | enum `doi_prefix` / `domain` / `publisher_alias` | 声明首选路由信号。 |
| `doi_prefixes` | array[string] | 是 | 可为空数组 | 对齐 `ProviderSpec.doi_prefixes`。 |
| `domains` | array[string] | 是 | 可为空数组 | 对齐 `ProviderSpec.domains`。 |
| `domain_suffixes` | array[string] | 是 | 可为空数组 | 对齐 `ProviderSpec.domain_suffixes`。 |
| `publisher_aliases` | array[string] | 是 | 可为空数组 | 对齐 publisher alias 路由。 |
| `crossref_publisher` | string/null | 是 | string 或 `null` | 只有 discovery 有可靠 Crossref publisher 证据时填写。 |

## `success_criteria`

`success_criteria` 是以 `main_path` step 或 provider 自定义 step 为 key 的 object。每个 step value 由实现者或 sync-back 工具回写，schema 上均带 `x-sync-back: true`。

| 字段 | Type | Required | 约束 | 决策依据 |
|---|---|---:|---|---|
| `<step>` | object/array/null | 否 | step key 可为空；value 是 sync-back 占位或实现后阈值对象 | 主路径正文质量阈值、success marker、figure/table/reference 数量等实现事实。 |

## `route_contract`

`route_contract` 是实现前的抓取判定合同，不是 sync-back 字段。每个 `main_path` step 必须有同名 key。实现者必须先按它写 provider-local waterfall / rejection 测试，再实现 provider route。

| 字段 | Type | Required | 决策依据 |
|---|---|---:|---|
| `<step>.success_requires` | array[string] | 是 | 该 route 被视为成功时必须同时满足的结构或 payload 条件。 |
| `<step>.reject_if_any` | array[string] | 否 | 命中任一条件时不得把该 route 当 fulltext success。 |
| `<step>.min_body_chars` | integer | 否 | HTML/XML/PDF text 路线的最小正文长度门槛。 |
| `<step>.min_body_sections` | integer | 否 | HTML/XML 路线的最小正文 section 门槛。 |
| `<step>.require_pdf_magic` | boolean | 否 | PDF fallback 必须校验 `%PDF` magic bytes 或等价 PDF payload 信号。 |
| `<step>.reject_html_wrapper` | boolean | 否 | PDF fallback 必须拒绝 HTML wrapper、challenge page 或错误页。 |
| `<step>.notes` | string | 否 | 只写对实现有约束力的补充说明。 |

## `route_sources`

`route_sources` 是可选的 route step 到 runtime source 映射。key 必须是 `main_path` 中已有 step，value 必须能通过 `ProviderBundle.sources` 或 runtime source map 解析到当前 provider。`display_source` 仍是主要公开 source；只要 `route_sources` 存在，`display_source` 必须出现在 `route_sources` values 中。

示例：

```yaml
main_path:
  - article_html
  - pdf_fallback
  - metadata_only
display_source: mdpi_html
route_sources:
  article_html: mdpi_html
  pdf_fallback: mdpi_pdf
```

## `asset_contract.figures`

`asset_contract.figures` 是 figure fixture 的强制资产验收合同。只要 provider 有 non-null `fixtures.doi_samples.figure.doi` 且 approved 主路线可以获得 figure asset，就必须声明正文内联和下载要求；只有 text-only PDF fallback、abstract-only/access-gate/empty-shell，或确实没有可下载图片时，才允许 `not_applicable`，并必须写明具体 `exception_reason`。

| 字段 | Type | Required | 约束 | 决策依据 |
|---|---|---:|---|---|
| `inline` | string | 是 | enum `body` / `not_applicable` | `body` 表示 `extracted.md` 正文中必须出现 `![Figure ...](...)`，位置早于 `## References` / `## Figures` / Supplementary 等尾部 section。 |
| `download` | string | 是 | enum `required` / `not_applicable` | `required` 表示 provider-local tests 必须实际下载 figure asset 到本地，并断言 path / bytes / asset result state。 |
| `purposes` | array[string] | 是 | 至少包含有 DOI 的 fixture purpose，通常是 `figure` | 指定哪些 fixture purpose 触发 inline/download 检查。 |
| `exception_reason` | string/null | 是 | 任一字段为 `not_applicable` 时必须是非空字符串；全部适用时必须为 `null` | 记录无法执行内联或下载契约的可审计原因。 |

正文内联不接受只在文末 `## Figures` 输出 caption bullet；下载契约不接受只保存远程 URL 或只 mock asset metadata，必须验证本地文件落盘、字节数和最终 Markdown 链接 rewrite 到本地 asset path。

## `markdown_contract`

`markdown_contract` 是每个真实 fixture purpose 的 Markdown oracle。每个 non-null `fixtures.doi_samples.<purpose>.doi` 必须在 `markdown_contract.<purpose>` 中重复同一 DOI，并至少提供一条正向和一条负向断言输入。

| 字段 | Type | Required | 决策依据 |
|---|---|---:|---|
| `<purpose>.doi` | string | 是 | 必须等于对应 `fixtures.doi_samples.<purpose>.doi`。 |
| `<purpose>.must_include` | array[string] | 是 | scaffold 生成 `assert ... in markdown`，实现者可改成更强 provider-local 断言。 |
| `<purpose>.must_not_include` | array[string] | 是 | scaffold 生成站点 chrome / access noise / boilerplate 负断言。 |
| `<purpose>.must_match` | array[string] | 否 | 需要正则表达的表格、公式、图片或引用格式断言。 |
| `<purpose>.count_equals` | object | 否 | 文本去重、caption 去重、重复 chrome 清理的计数断言。 |
| `<purpose>.notes` | string | 否 | 只写会改变断言选择的 fixture 观察。 |

## `probe`

| 字段 | Type | Required | 约束 | 决策依据 |
|---|---|---:|---|---|
| `env_requirements` | array[string] | 是 | item string | provider status 和 live sample 所需环境变量。 |
| `requires_playwright` | boolean | 是 | boolean | 声明是否依赖 browser runtime。 |
| `requires_browser_runtime` | boolean | 是 | boolean | 声明是否依赖 Camoufox browser runtime。 |
| `ping_url` | string/null | 否 | URI 或 `null` | status probe 或人工排查入口。 |

## `fixtures.doi_samples`

固定 purpose：`structure`、`table`、`formula`、`figure`、`supplementary`、`references`、`pdf_fallback`、`abstract_only`、`access_gate`、`empty_shell`。

每个 purpose 的 value 都是 evidence object：

| 字段 | Type | Required | 约束 | 决策依据 |
|---|---|---:|---|---|
| `doi` | string/null | 是 | DOI string 或 `null`；`structure` / `figure` / `references` 必须非空 | capture fixture 的主输入。 |
| `evidence_url` | string | 是 | URI | 指向 DOI landing page 或可审计页面。 |
| `evidence_reason` | string | 是 | 非空 | 解释此 DOI 覆盖该 purpose 的原因。 |
| `observed_signals` | array[string] | 是 | 可为空数组 | 页面或 fixture 中可观察的信号。 |
| `confidence` | string | 是 | enum `high` / `medium` / `low` | 标识该样本证据强度。 |

## `fixtures.discovery_proof`

`discovery_proof` 对 `table`、`formula`、`supplementary` 强制记录候选检索矩阵。它用于证明 non-null 选择来自充分搜索，也用于证明 null purpose 不是“没搜到就写 null”。固定 required key：`table`、`formula`、`supplementary`。

| 字段 | Type | Required | 约束 | 决策依据 |
|---|---|---:|---|---|
| `<purpose>.queries` | array[string] | 是 | 至少 3 条；每条包含 provider 名称、域名或 DOI prefix，并包含 purpose 关键词 | 证明搜索不是只基于 seed DOI。 |
| `<purpose>.candidates` | array[string] | 是 | DOI 列表；已选择 DOI 时必须包含 `selected_doi` | 记录候选池，便于 review 和 retry。 |
| `<purpose>.selected_doi` | string/null | 是 | 必须等于 `fixtures.doi_samples.<purpose>.doi` | 防止 proof 与实际 fixture 脱节。 |
| `<purpose>.rejections` | object | 是 | key 为未选择候选 DOI，value 为拒绝原因 | 让 null 或未选候选可审计。 |
| `<purpose>.exhausted` | boolean | 是 | 已选择 DOI 时为 `false`；null purpose 必须为 `true` | 区分已选样本和候选池耗尽。 |
| `<purpose>.evidence_summary` | string | 是 | 非空；null purpose 不能只写“未找到样本” | 说明当前选择或 null 结论。 |

`table`、`formula`、`supplementary` 为 `doi: null` 时，必须有候选 DOI 和拒绝理由。如果同一 manifest 的 non-null fixture 或 cleaning evidence 已暴露该 purpose 强信号，必须选择该 DOI，或在对应 rejection 中明确说明同 DOI 为什么不适合作为该 purpose fixture。

## `extra_fixtures`

`extra_fixtures` 记录固定 DOI purpose 之外的补充 replay 样本。每个 item 都必须有非空 DOI、evidence 字段、observed signals 和 confidence；`purpose` 可以复用固定 purpose，例如 `structure`，用于追加同类结构广度样本。

| 字段 | Type | Required | 约束 | 决策依据 |
|---|---|---:|---|---|
| `purpose` | string | 是 | 非空 | capture/review 输出中保留的样本用途标签。 |
| `doi` | string | 是 | DOI string | capture fixture 的主输入。 |
| `evidence_url` | string | 是 | URI | 指向 DOI landing page 或可审计页面。 |
| `evidence_reason` | string | 是 | 非空 | 解释此 DOI 为什么作为补充 replay 样本。 |
| `observed_signals` | array[string] | 是 | `minItems: 1` | 页面或 fixture 中可观察的信号。 |
| `confidence` | string | 是 | enum `high` / `medium` / `low` | 标识该样本证据强度。 |
| `markdown_contract` | object | 否 | 同 `markdown_contract.<purpose>`，且 `doi` 必须等于本 item DOI | 需要补充 Markdown oracle 时就地记录，不覆盖固定 purpose contract。 |

## `extraction_hints`

这些字段由 sync-back 回写，schema 上均带 `x-sync-back: true`，初稿可以是 `null` 或空数组。

| 字段 | Type | Required | 决策依据 |
|---|---|---:|---|
| `datalayer_signal_set` | object/array/null | 是 | 对齐 availability datalayer signal set。 |
| `text_marker_signal_set` | object/array/null | 是 | 对齐 availability text marker signal set。 |
| `front_matter` | object/array/null | 是 | 对齐 provider front matter rules。 |
| `asset_retry` | object/array/null | 是 | 对齐 provider asset retry policy。 |
| `metadata_merge` | object/array/null | 是 | 对齐 provider metadata merge rules。 |

## `docs`

| 字段 | Type | Required | 决策依据 |
|---|---|---:|---|
| `providers_md_capability_row` | string | 是 | `docs/providers.md` 能力矩阵行的事实来源。 |
| `changelog_summary` | string | 是 | `CHANGELOG.md` 用户可见摘要。 |
| `extraction_rules_summary` | string/null | 否 | 有新增用户可见 extraction rule 时写入摘要，否则为 `null`。 |
