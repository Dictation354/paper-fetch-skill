# 添加一个 Provider：快速上手

> Human reference only. AI/coordinator provider onboarding must use [`onboarding/coordinator-spec.md`](../onboarding/coordinator-spec.md) and related authority docs.

这是为第一次给 paper_fetch 接入新出版社的人类开发者写的快速教程。下面用假想 provider `newpub` 作占位；MDPI、PLOS、Frontiers 等已实现 provider 只能作为历史先例参考，不应按本文命令从零 scaffold。它不作为 AI/coordinator worker 输入；AI/coordinator 的入口索引是 [`onboarding/README.md`](../onboarding/README.md)，行为事实源分别见 [`coordinator-spec.md`](../onboarding/coordinator-spec.md)、[`provider-manifest.md`](../onboarding/provider-manifest.md)、[`provider-manifest.schema.json`](../onboarding/provider-manifest.schema.json)、[`agent-task-brief.md`](../onboarding/agent-task-brief.md)、[`hard-constraints.md`](../onboarding/hard-constraints.md) 和 [`acceptance.md`](../onboarding/acceptance.md)。完整人工规约见 [`provider-development.md`](provider-development.md)，本文只讲流程。

## 你要做什么

让 `fetch_paper(doi="10.X/Y")` 在 DOI 属于新出版社时返回结构化 `ArticleModel`，主路径走该出版社的官方 HTML/XML/PDF，失败时降级为 abstract-only 或 metadata-only。

## 时间预估

| 阶段 | 时间 |
|---|---|
| 设计 + 收 fixtures + 起步 | 1-3 天 |
| 写 extraction + 客户端 | 2-5 天 |
| 跑通 + 重构 + 文档 | 1-2 天 |
| **合计** | **1-2 周** |

如果出版社用 Atypon 等已有 browser-workflow 框架，可能 3-5 天就够。

---

## Step 0：花 30 分钟先写设计

不要直接 coding。先在一个 issue 或 doc 段里写清楚下面 5 个问题：

1. **怎么 routing 到这个 provider？** 按域名（如 `newpub.example`）还是按 Crossref publisher 字段还是 DOI 前缀（如 `10.xxxx/`）？
2. **主路径顺序是什么？** 比如 `landing HTML → XML API → PDF fallback → abstract-only`。
3. **怎么判断 fulltext 成功？** 只看 HTTP 200 是不够的（项目反模式之一）——要看 article container、章节、正文长度、access gate 文案等。
4. **`asset_profile` 三模式分别下载什么？** `none` / `body` / `all` 各对应什么 scope？
5. **需要哪些环境变量 / API key / browser runtime？** `probe_status()` 怎么检查本地配置？

跳过这步会让 Step 1（收 fixture）选偏「快乐路径」，Step 3（实现）反复返工。

---

## Step 1：按正交清单收 fixtures（1-3 天）

**不要积累 8-9 篇相似的「跑得通」文献**——按能力维度铺开：

```
golden_criteria/<doi_slug>/
  ├─ structure 篇        # 标题/作者/摘要/章节/参考文献
  ├─ tables 篇           # 含 inline + 复杂 caption
  ├─ formulas 篇         # MathML / image fallback
  ├─ figures 篇          # multi-panel
  ├─ supplementary 篇    # asset_profile=all 触发
  ├─ references 篇       # 复杂样式
  └─ pdf-fallback 篇 ×1-2

block/
  ├─ abstract-only 篇    # provider 主动返回摘要
  ├─ access-gate 篇      # paywall
  └─ empty-shell 篇      # 空壳 HTML
```

操作流程：

1. 找真实 DOI（不要造假数据）。
2. 用 `capture_fixture.py` 录制 replay，并让脚本登记 `manifest.json`，`expected_outcome` 初始为 `"pending"`。
3. golden 类样本写到 `tests/fixtures/golden_criteria/<doi_slug>/original.{html,xml,pdf}`。
4. block 类样本用 `--purpose abstract-only|access-gate|empty-shell`，写到 `tests/fixtures/block/<doi_slug>/original.html`。

示例：

```bash
PYTHONPATH=src python3 scripts/capture_fixture.py \
  --doi <real-structure-doi> \
  --provider newpub \
  --purpose structure

PYTHONPATH=src python3 scripts/capture_fixture.py \
  --doi <real-access-gate-doi> \
  --provider newpub \
  --purpose access-gate
```

详细 fixture 规则见 [`provider-development.md` §8](provider-development.md#testing-standard)，正交清单见同文档 [附录 A](provider-development.md#appendix-a-fixtures)。

---

## Step 2：跑 scaffold 起步（10 分钟）

```bash
python3 scripts/scaffold_provider.py --name newpub --doi <real-structure-doi> --fulltext-client
```

会生成：
- `src/paper_fetch/providers/_newpub_html.py`（provider HTML starter；provider 变大后应降为 compatibility facade，并按 authors / references / assets / markdown / dom 拆到 `_newpub_*` helper）
- `src/paper_fetch/providers/newpub.py`（ProviderClient 子类骨架）
- `tests/unit/test_newpub_provider.py`（测试骨架）
- `tests/fixtures/golden_criteria/<doi_slug>/.gitkeep`
- `manifest.json` 占位条目
- stdout 打印 PR-checklist

---

## Step 3：实现 extraction 与客户端，并跑 Markdown Review Loop（2-5 天）

### 3.1 填 `ProviderBundle`

打开 provider entry module（例如 `newpub.py`）把 `register_provider_bundle(ProviderBundle(...))` 填完整；scaffold 生成的 HTML starter 只作为 provider-owned helper / compatibility facade：

- `catalog=ProviderSpec(...)`：hosts / 路径模板 / asset_default / probe_capability（见 [§2](provider-development.md#provider-bundle)）
- `html_rules=ProviderHtmlRules(cleanup=..., front_matter=..., availability=..., dom_hooks=..., markdown_hooks=...)`（见 [§5](provider-development.md#extraction-owner-reuse)）
- 可选：`asset_retry=AssetRetryPolicy(...)`、`metadata_merge=(...)`

### 3.2 写 hook 函数

`newpub_before_block_normalization(container)` / `newpub_normalize_markdown(text)` 等先按职责放到 provider-owned helper。小型 provider 可暂存在 `_newpub_html.py` starter；一旦出现 authors / references / assets / markdown / dom 多类职责，应让 `_newpub_html.py` 保持 compatibility facade，并拆到 `_newpub_authors.py`、`_newpub_references.py`、`_newpub_assets.py`、`_newpub_markdown.py`、`_newpub_dom.py`。**不要**在 `extraction/html/provider_rules.py` 写 wrapper——直接函数引用即可。

### 3.3 写客户端 `NewpubClient`

继承 `paper_fetch.providers.base.ProviderClient`，**只覆盖必要 hook**：

- `fetch_raw_fulltext()`：发请求 + 校验 payload（见 [§3-§4](provider-development.md#client-contract)）
- `to_article_model()`：raw → ArticleModel
- `html_to_markdown()`：HTML 路线必填
- `download_related_assets()`：仅有资产能力时实现
- `probe_status()`：本地环境检查

**不要**绕过 `fetch_result()` template method 自己拼 `FetchEnvelope`——会被 review 打回。

### 3.4 复用 canonical owner

写代码前先看 [`provider-development.md` §5 owner 复用规则](provider-development.md#extraction-owner-reuse)。HTTP header、access gate 文案、table 渲染、markdown IR 全部有 canonical 实现。**不要重写**——重写会被打回。

### 3.5 Markdown Review Loop

对 manifest 中每个 non-null `fixtures.doi_samples.<purpose>` 固定执行；AI/coordinator manifest 字段定义以 [`onboarding/provider-manifest.md`](../onboarding/provider-manifest.md) 和 [`provider-manifest.schema.json`](../onboarding/provider-manifest.schema.json) 为准：

1. 生成 baseline Markdown。
2. 逐篇阅读，记录 `fixture/purpose -> issue -> assertion -> fix`。
3. 先把 issue 写成 `tests/unit/test_newpub_provider.py` 里的断言，再修 provider-owned helper / facade / `newpub.py`。
4. 主成功路径至少保留一个 Markdown 正断言和一个站点 chrome / access noise / boilerplate 负断言。
5. 重复到所有 fixture Markdown 干净。

不要保留 scaffold skipped placeholder 或 review-loop placeholder。

---

## Step 4：Prototype 通过（Commit A，约 1 天）

跑：

```bash
PYTHONPATH=src python3 -m pytest tests/unit -q
```

直到 `test_newpub_provider.py` 全绿，并且每个 non-null fixture purpose 都已经在 provider-local 测试中点名覆盖。然后**第一次为每篇 fixture 写四类 snapshot/review 产物**：

```bash
PYTHONPATH=src python3 scripts/snapshot_expected.py --doi <real-structure-doi> --review
PYTHONPATH=src python3 scripts/snapshot_expected.py --doi <real-structure-doi>
```

写入命令会同时更新 `expected.json`、`extracted.md`、`markdown-quality-prompt.md`、pending 状态的 `markdown-quality.json` 和 manifest assets。`expected.json` 只锁 `has` / `counts` / `expected_content_kind` 摘要；Markdown quality 需要 agent 按 `markdown-quality-prompt.md` 阅读 `extracted.md` 后，把 `markdown-quality.json` 写成 `status: pass` 且没有 blocking issue。

如果 quality report 已经是 agent-authored fail，可运行 `python3 scripts/onboard_from_manifests.py repair-markdown-quality --provider <provider> --doi <doi>`。该命令只通过 `PROVIDER_ONBOARDING_AGENT_CLI` 派发实现和复审 agent，最多 3 轮；pending report 会被拒绝，需要先完成初次 quality review。

之后每次改 extraction 都用 provider-local 断言和 `pytest` diff 来审；新增 correction 时继续先写断言再修 provider。

跑完整性 lint：

```bash
PYTHONPATH=src python3 -m pytest tests/unit/test_provider_bundle_completeness.py -q
PYTHONPATH=src python3 -m pytest tests/unit/test_provider_markdown_review_contract.py -q
```

全过即 Commit A。这一步固化「跑通」的状态。

---

## Step 5：重构对齐 canonical owner（Commit B，约半天）

逐条跑 [`provider-development.md` 附录 B](provider-development.md#appendix-b-owner-reuse) 的 grep checklist。**每条命中**要么删除并 import canonical owner，要么加注释解释 publisher 差异。

典型清理：

- 自己写的 `_header_value(response, "Content-Type")` → `from paper_fetch.http.headers import header_value`
- 自己 hardcode 的 `_doi_pdf_candidate(doi)` → 改成 `ProviderSpec` 模板字段
- 自己写的 `_render_table_markdown(table)` → 改用 `paper_fetch.extraction.markdown_render`

清理后再跑一遍全量 pytest，确认 `expected.json`、`extracted.md`、`markdown-quality-prompt.md` 和 `markdown-quality.json` 没有非预期变化。Commit B。

---

## Step 6：端到端收尾（约半天）

按 [`provider-development.md` §9](provider-development.md#docs-sync-standard) 更新：

| 文件 | 必填项 |
|---|---|
| `docs/providers.md` | 能力矩阵、routing 信号、waterfall、asset_profile、status |
| `docs/extraction-rules.md` | 用户可见新规则（若有） |
| `docs/architecture/overview.md` | 仅新增 canonical owner 时 |
| `docs/deployment.md` / `.env.example` | 新环境变量（若有） |
| `CHANGELOG.md` | 一行用户可见摘要 |

然后对照 [`provider-development.md` 附录 C PR Checklist](provider-development.md#appendix-c-pr-checklist) 逐项勾选。所有项通过 → PR。

---

## 一个完整例子：接 `newpub` 的路线

```bash
# Step 0 (设计 doc)
# - routing: domain newpub.example + DOI 前缀 10.xxxx
# - 主路径: landing HTML → article HTML → PDF fallback
# - asset_profile: body 下图 + 表 + 公式；all 下加 supplementary zip
# - probe: 检查 newpub.example 可达即 ready

# Step 1 (fixtures, 1-2 天)
PYTHONPATH=src python3 scripts/capture_fixture.py \
  --doi <real-structure-doi> \
  --provider newpub \
  --purpose structure
# 重复 8-10 篇覆盖 structure/table/formula/figure/supp/refs/pdf/block

# Step 2 (scaffold)
python3 scripts/scaffold_provider.py --name newpub --doi <real-structure-doi> \
  --fulltext-client

# Step 3 (实现, 2-3 天)
# - 编辑 provider entry module 和 provider-owned HTML helper/facade
# - 编辑 src/paper_fetch/providers/newpub.py: 填 NewpubClient
# - 跑 pytest 直到 test_newpub_provider.py 局部通过

# Step 4 (Commit A)
PYTHONPATH=src python3 scripts/snapshot_expected.py --doi <real-structure-doi> --review
PYTHONPATH=src python3 scripts/snapshot_expected.py --doi <real-structure-doi>
PYTHONPATH=src python3 -m pytest tests/unit -q
git commit -m "feat(newpub): prototype provider with golden replay"

# Step 5 (重构, 半天)
# - 按附录 B grep 自查
# - 删除 local helper
git commit -m "refactor(newpub): align with canonical owners"

# Step 6 (文档, 半天)
# - 改 docs/providers.md / CHANGELOG.md / extraction-rules.md
# - 跑 python3 scripts/validate_extraction_rules.py
git commit -m "docs(newpub): add provider documentation"

# PR
```

---

## 5 个最容易踩的坑

1. **跳过 Step 0 直接收 fixture**：fixtures 全是 open-access HTML，后期发现没覆盖 paywall 或 abstract-only，要回炉。
2. **只写 snapshot，不写 Markdown review 断言**：每个 correction 先落 provider-local 断言，再写 / 更新 `expected.json`、`extracted.md`、`markdown-quality-prompt.md` 和 `markdown-quality.json`。
3. **在 `_X_html.py` 内重写 canonical owner 已有的能力**（table 渲染、header 查找、access gate 文案）：项目反模式，PR 会被打回。
4. **prototype 和重构混在一个 commit**：重构发现要改 fixtures 时丢失 prototype 进度。
5. **改了 `provider_catalog.py` / `provider_rules.py` / `quality/html_signals.py`**：这些属于禁区，CI lint 会失败。所有 provider 数据走 `ProviderBundle` 自注册。

---

## 接下来读哪里

- 详细规约：[`provider-development.md`](provider-development.md)
- 已支持 provider 的能力矩阵：[`providers.md`](providers.md)
- 系统分层与 typed contract：[`architecture/overview.md`](architecture/overview.md)
- 用户可见提取规则：[`extraction-rules.md`](extraction-rules.md)

有不清楚的，先看现有 provider 的 `_pnas_html.py` 或 `mdpi.py` / `MdpiClient` 等已实现先例，按当前 provider 的路线和权限边界改写，不要直接覆盖已有 provider 文件。
