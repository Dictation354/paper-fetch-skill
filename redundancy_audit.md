# 文献抓取与转换链路 — 冗余与重复实现审计

本文记录代码库中曾识别出的冗余/重复实现，按"严格意义上的代码重复"程度排序。已处理项保留原审计描述用于追溯。

> 处理状态：#1-#12 已处理完成；`browser_workflow.py` 已拆成 facade 与内部 fetcher / HTML extraction 模块。

---

## 高严重度（真正的代码分叉，有维护风险）

### 1. [已处理] `score_container` / `select_best_container` / `should_drop_node` / `clean_container` 在两处 fork
- **位置**：`src/paper_fetch/quality/html_availability.py:222-285` 与 `src/paper_fetch/providers/_science_pnas_html.py:211-345`
- **重复内容**：四个同名函数都存在，但**评分公式已经分叉**：
  - `html_availability.py:score_container` 用 `text_length + heading*200 + paragraph*40 + figure*20 + identity_bonus`
  - `_science_pnas_html.py:score_container` 用 `text_length/120 + paragraph*6 + heading*12 - excess_links*1.5 + 关键词加分`
- **影响**：Wiley 走 `html_availability` 的版本（`_wiley_html.py:130` 引入），Science/PNAS 走自己的版本。同一个名字、同一个语义、不同的计算 → 任何一边修 bug，另一边都得手动同步。
- **建议**：统一到 `quality/html_availability.py`，通过 publisher rule 注入差异化的权重；删除 `_science_pnas_html.py` 中的本地拷贝。

### 2. [已处理] `_normalize_section_hint_heading` 三处一模一样
- **位置**：`src/paper_fetch/models.py:2036`、`src/paper_fetch/extraction/html/_runtime.py:526`、`src/paper_fetch/quality/html_availability.py:332`
- **重复内容**：三份函数体均为 `return normalize_text(text).lower().strip(" :")`，逐字符相同。
- **影响**：纯字面重复，三份同步成本。
- **建议**：移到 `utils.py`，统一导入。

### 3. [已处理] `_coerce_section_hints` 三份近似实现
- **原位置**：`src/paper_fetch/models.py`、`src/paper_fetch/extraction/html/_runtime.py`、`src/paper_fetch/quality/html_availability.py`
- **重复内容**：HTML runtime 与 HTML availability 曾保留相同的 dict wrapper；`models.py` 版本返回 `SectionHint` dataclass，接口不同。
- **处理结果**：dict 版本收口到 `src/paper_fetch/extraction/html/semantics.py:coerce_html_section_hints`；`_runtime.py` 与 `html_availability.py` 直接复用。`models.py` 保留 dataclass 适配层。

### 4. [已处理] `_match_next_section_hint` 重复
- **原位置**：`src/paper_fetch/extraction/html/_runtime.py` 与 `src/paper_fetch/quality/html_availability.py`，逐行相同。
- **处理结果**：HTML dict 版本收口到 `src/paper_fetch/extraction/html/semantics.py:match_next_html_section_hint`；`models.py` 保留 `SectionHint` 返回值的适配逻辑。

---

## 中等严重度（薄包装可被参数化）

### 5. [已处理] `extract_markdown` 在 Science/PNAS 提供方是纯委托
- **位置**：`src/paper_fetch/providers/_science_html.py:255` 和 `src/paper_fetch/providers/_pnas_html.py:130`
- **重复内容**：主体都是 `browser_workflow.extract_science_pnas_markdown(html, source_url, "science"|"pnas", metadata=metadata)`。
- **注意**：`finalize_extraction` 不是重复 — Science 版多做了 frontmatter 拍平等逻辑，应保留差异。
- **建议**：把 publisher tag 写进 `ProviderBrowserProfile` 或注册表，删掉两个壳函数。

### 6. [已处理] `build_html_candidates` / `build_pdf_candidates` 在四个 provider 里全是 1:1 包装
- **位置**：`_science_html.py`、`_pnas_html.py`、`_wiley_html.py`、`_springer_html.py` 各自定义这两个函数。
- **重复内容**：函数体都只是把模块级 `HOSTS / BASE_HOSTS / PATH_TEMPLATES` 灌进 `_browser_workflow_shared.build_browser_workflow_*_candidates`。
- **建议**：让 `ProviderBrowserProfile` 直接持有 hosts/templates 数据，由共享构造器一次性生成；provider 文件从函数变成数据声明。

### 7. [已处理] `_extract_meta_authors` 在 PNAS / Wiley 是单行包装
- **位置**：`src/paper_fetch/providers/_pnas_html.py:55-56`、`src/paper_fetch/providers/_wiley_html.py:55-56`
- **重复内容**：均为 `return extract_meta_authors(html, keys={...})`。
- **注意**：Springer 版本 (`_springer_html.py:142`) 在外面套了 `_normalize_display_authors`，**不应** 删除。
- **建议**：删除 PNAS / Wiley 的包装函数，调用点直接传 `keys=...`。

### 8. [已处理] Author 抽取流水线的"三段式"在每个 provider 复刻
- **位置**：`_science_html.py`、`_pnas_html.py`、`_wiley_html.py`、`_springer_html.py` 中的 `_extract_dom_authors` → `extract_authors` 模式。
- **重复内容**：每个 provider 都自己实现"DOM 优先 → meta 退路（→ JSON-LD 退路）"的 fallback 链，差别只在选择器集合和忽略词。
- **建议**：在 `_browser_workflow_authors.py` 里加 `AuthorExtractionPipeline(dom_extractor, meta_extractor, jsonld_extractor)` 或工厂函数，provider 仅声明配置。

---

## 低严重度（混乱但不影响正确性）

### 9. [已处理] `resolve/crossref.py` 是 7 行的空壳
- **位置**：`src/paper_fetch/resolve/crossref.py`
- **内容**：仅 `from ..metadata.crossref import CrossrefLookupClient`，被 `resolve/query.py:22` 引用一次。
- **建议**：删除，让 `resolve/query.py` 直接 import `metadata.crossref`。`providers/crossref.py` 保留（它是 `ProviderClient` 适配器，有职责）。

### 10. [已处理] heading-normalize 家族散落
- **位置**：
  - `src/paper_fetch/utils.py:85` — `normalize_text`
  - `src/paper_fetch/providers/_html_section_markdown.py:109` — `normalize_section_title`
  - `src/paper_fetch/providers/_science_pnas_html.py:184` — `_normalize_heading`（已经是 `extraction.html.semantics.normalize_heading` 的薄包装）
  - `_normalize_section_hint_heading` ×3（见 #2）
- **影响**：四种"标题归一化"，规则相互覆盖但语义都偏 "lower + 去标点/冒号"。
- **建议**：在 `extraction/html/semantics.py` 集中两到三个明确语义的函数（章节标题 vs 提示键），删掉 `_normalize_heading` 这种纯转发。

### 11. [已处理] `_science_pnas_html.py` 顶部共享 helper 的 `as _shared_*` 别名层
- **位置**：`src/paper_fetch/providers/_science_pnas_html.py` 顶部 imports
- **内容**：多个共享 helper 曾以 `import ... as _shared_*` 方式导入。
- **影响**：不是逻辑重复，是命名噪音；增加阅读成本。
- **处理结果**：导入别名已改回原名；与本地入口同名的 postprocess helper 改为模块属性调用，避免恢复 `_shared_*` 别名。

### 12. [已处理] `browser_workflow.py` 单文件 3078 行
- **位置**：`src/paper_fetch/providers/browser_workflow.py`
- **说明**：不算"重复"，属于结构问题。原文件混合了 Playwright 编排、图片/文件 fetcher 类、Science/PNAS 的提取入口。
- **处理结果**：
  - `_browser_workflow_fetchers.py` — `_SharedPlaywrightImageDocumentFetcher` 等 fetcher 类、memoized fetcher、Playwright context 与图片 payload/失败诊断 helper
  - `_browser_workflow_html_extraction.py` — direct Playwright HTML preflight、FlareSolverr HTML payload、Markdown/assets parse-cache helper 与 HTML payload helper
  - `browser_workflow.py` — 保留 canonical facade、bootstrap、seeded-browser PDF fallback、article conversion 与 related asset download orchestration，并继续 re-export 既有 patch/import 兼容名

---

## 不建议动的几处（看似可合并但其实合理）

- **`_pdf_candidates` / `_pdf_common` / `_pdf_fallback` 三分**：职责清晰（候选生成 / 数据类与判定 / Playwright 执行），不是重复。
- **`html_profiles.py` 里 `*_blocking_fallback_signals` / `*_positive_signals`**：每个发布商的判据真的不同（不同正则、不同 datalayer 格式），不是 DRY 违规。
- **`metadata/crossref.py` 与 `providers/crossref.py`**：一个是底层 lookup，一个是 ProviderClient 适配器，分层合理；只有 `resolve/crossref.py` 是冗余（见 #9）。

---

## 改造路线建议

按 ROI 推荐顺序：

1. **#2 + #3 + #4** — 一次性解决 section hint 三胞胎，机械性最高、风险最低。
2. **#1** — 拆 `score_container` 分叉，是真正会咬人的隐患（隐式行为差异）。
3. **#5–#8** — provider 壳函数参数化，需要触动 `ProviderBrowserProfile` 设计。
4. **#9–#11** — 清理空壳、统一 heading 归一化、去除 `_shared_` 别名噪音。
5. **#12** — 已完成：`browser_workflow.py` 大文件拆分为 facade + 内部 fetcher / HTML extraction 模块。
