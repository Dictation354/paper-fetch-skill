# Extraction Rule Test Simplification Plan

## Summary

本计划把当前 extraction 规则测试集合的“可精简 / 可合并”分析落成一个可执行方案，目标是在不削弱规则覆盖的前提下，降低重复 setup、减少近似重复断言、收敛模块边界。

当前已注册规则测试集合来自 `tests/fixtures/golden_criteria/manifest.json`，共 67 个测试，主要分布如下：

- `tests/unit/test_science_pnas_postprocess.py`: 13
- `tests/unit/test_science_pnas_markdown.py`: 11
- `tests/unit/test_science_pnas_provider.py`: 10
- `tests/unit/test_elsevier_markdown.py`: 9
- `tests/unit/test_springer_html_regressions.py`: 7
- `tests/unit/test_html_availability.py`: 7
- `tests/unit/test_regression_samples.py`: 5
- `tests/unit/test_springer_html_tables.py`: 3
- `tests/unit/test_html_shared_helpers.py`: 2

这批测试没有明显的大面积“冗余到可以直接删掉”的问题；更准确地说，当前重复主要来自两类：

1. 同一 fixture、同一入口函数、同一规则，在不同模块里重复写了相近断言。
2. 同一测试模式在不同 provider / fixture 上重复展开，但尚未参数化。

因此本计划优先做“参数化 + helper 抽取 + 模块职责收敛”，而不是直接删测试。

---

## Current Status

状态更新时间：2026-04-23

- 总体状态：全部完成。
- 已完成：A、B、C、D、E、F，以及 `docs/extraction-rules.md` 的阶段归属和测试映射同步。
- 已验证回归：
  `pytest -q tests/unit/test_elsevier_markdown.py`
  `pytest -q tests/integration/test_fixture_provenance.py`
- 当前结果：
  `tests/unit/test_elsevier_markdown.py`: `12 passed, 9 subtests passed`
  `tests/integration/test_fixture_provenance.py`: `5 passed`

---

## Goals

- 降低规则测试集合的维护成本。
- 保持 `docs/extraction-rules.md` 与 manifest 的规则闭环不变。
- 保留真正跨层级的 contract 覆盖，不把 extractor / provider / final render 的不同职责误并掉。

---

## Non-Goals

- 不重写 `golden_criteria` 资产目录结构。
- 不修改规则文档结论，只在测试层做结构性精简。
- 不把当前有价值的“跨层级重复锁定”误判为冗余。

---

## Principles

### 1. 优先合并“样板重复”，谨慎处理“行为重复”

只有当测试满足下面两个条件时，才优先合并：

- 同一 fixture 或同一类型 fixture；
- 同一层级入口，且断言目标高度重合。

### 2. 保留跨层级覆盖

下列组合默认不合并：

- extractor 输出 vs provider `to_article_model()` 结果
- provider article model vs final `to_ai_markdown()` 渲染
- helper 级行为 vs 端到端集成行为

### 3. 优先参数化，而不是删 case

若多个测试只是 provider / DOI / expected signal 不同，应优先改为 case table + `subTest`，而不是减少样本数。

---

## High-Priority Work

### A. 合并 `test_html_availability.py` 中的成对 accept/reject case

**当前状态**：已完成。Science / Wiley / PNAS 的 accept/reject case 已经改成共享 case table + helper，且保留了原有规则测试函数名。

**目标文件**

- `tests/unit/test_html_availability.py`

**现状**

Science / Wiley / PNAS 的 paywall reject 与 entitled accept 结构高度一致：

- Science: `test_assess_html_rejects_science_paywall_sample_with_abstract` / `test_assess_html_accepts_science_entitled_fulltext_fixture`
- Wiley: `test_assess_html_rejects_wiley_paywall_metadata_with_abstract` / `test_assess_html_accepts_wiley_fulltext_fixture_despite_login_chrome`
- PNAS: `test_assess_html_rejects_pnas_paywall_metadata_with_abstract` / `test_assess_html_accepts_pnas_fulltext_fixture_despite_institutional_login_chrome`

Springer paywall 已经在同文件中采用多 DOI 子测试循环，说明这个模块已经具备表驱动风格。

**改动方式**

1. 新增 provider case table，统一描述：
   - `provider`
   - `doi`
   - `kind` (`accept` / `reject`)
   - `html asset`
   - `markdown asset` 或 extractor 构造方式
   - `expected content_kind`
   - `expected reason`
   - `expected blocking_fallback_signals`
2. 抽出一个小 helper，统一构造 `diagnostics`。
3. 用一个或两个表驱动测试覆盖 Science / Wiley / PNAS 成对场景。

**预期收益**

- 测试数减少有限，但重复 setup 会明显下降。
- 后续新增 provider availability contract 时，扩展成本更低。

---

### B. 合并 `test_regression_samples.py` 的 bilingual regression case

**当前状态**：已完成。bilingual regression 已收敛到共享 case spec/helper，保留了原测试身份。

**目标文件**

- `tests/unit/test_regression_samples.py`

**现状**

以下 5 个测试已共用 `_assert_bilingual_abstract_sections`，只是 builder 与期望 headings 不同：

- `test_wiley_bilingual_fixture_preserves_parallel_abstract_sections`
- `test_springer_bilingual_fixture_preserves_parallel_abstract_sections`
- `test_elsevier_bilingual_fixture_preserves_parallel_abstract_sections`
- `test_sage_bilingual_fixture_preserves_parallel_abstract_sections`
- `test_tandf_bilingual_fixture_preserves_parallel_abstract_sections`

**改动方式**

1. 保留 `_assert_bilingual_abstract_sections`。
2. 新增 bilingual case table：
   - `label`
   - `builder`
   - `abstract_headings`
   - `first_body_heading`
3. 改为一个 `subTest` 循环。

**预期收益**

- 去掉 5 个几乎相同的壳测试。
- 后续新增 bilingual provider 时，只需加 case，不必再复制测试函数。

---

### C. 为 Science / PNAS / Wiley 规则测试抽共享 helper

**当前状态**：已完成。三个模块内都已抽出最小 helper，用于减少 fixture 读取、markdown 提取和 article 构造重复。

**目标文件**

- `tests/unit/test_science_pnas_markdown.py`
- `tests/unit/test_science_pnas_postprocess.py`
- `tests/unit/test_science_pnas_provider.py`

**现状**

这三个模块里存在大量重复 setup：

- 反复读取同一 fixture
- 反复调用 `extract_science_pnas_markdown(...)`
- 反复构造 `RawFulltextPayload`
- 反复 `client.to_article_model(...)`

尤其是以下 fixture 被高频重复使用：

- `10.1073/pnas.2406303121`
- `10.1111/gcb.16414`
- `10.1126/science.adp0212`
- `10.1126/science.abp8622`
- `10.1073/pnas.2317456120`

**改动方式**

1. 在各自模块内部先抽最小 helper，而不是立刻跨模块共用：
   - `_extract_markdown_from_fixture(...)`
   - `_build_provider_article_from_fixture(...)`
2. 若 helper 形态稳定，再考虑提取到 `tests/unit/_paper_fetch_support.py` 或新 helper 模块。
3. 保持测试名和 manifest 注册不变，先只减少样板代码。

**预期收益**

- 降低 fixture setup 重复。
- 让真正的断言更突出，便于后续继续判断哪些 case 还能收敛。

---

## Medium-Priority Work

### D. 收敛 `test_science_pnas_markdown.py` 与 `test_science_pnas_postprocess.py` 的近似重复断言

**当前状态**：已完成。`markdown` 模块现在保留 extractor 层 smoke / structure 断言，`postprocess` 模块保留格式细节与 normalization 断言；Wiley 噪声、PNAS 表格行内语义、Science 公式/图注间距三组近似重复断言已完成职责重分。

**重点簇**

1. Wiley 噪声过滤  
   - `test_wiley_full_fixture_omits_real_page_collateral_noise`
   - `test_wiley_real_fixture_filters_frontmatter_and_viewer_noise`

2. PNAS 表格 / 行内语义  
   - `test_pnas_full_fixture_keeps_data_availability_and_renders_table_markdown`
   - `test_pnas_real_fixture_renders_table_and_inline_cell_formatting`

3. Science 公式 / 图注间距  
   - `test_science_adp0212_fixture_splits_display_equations_and_caption_sentences`
   - `test_science_real_fixture_keeps_formula_and_figure_caption_spacing`

**策略**

- `markdown` 模块保留 extractor 层的代表性断言和 smoke coverage。
- `postprocess` 模块保留格式细节和 normalization 断言。
- 避免同一条断言文案同时出现在两个模块。

**注意**

这一步不是先删测试，而是先重分断言职责。若收敛后自然可以合并，再做第二步。

---

### E. 参数化 provider-owned authors 的正向 case

**当前状态**：已完成。Science / Wiley / PNAS 三个正向 case 已收敛成单一 table-driven / `subTest` 测试，manifest 与规则文档映射已同步更新。

**目标文件**

- `tests/unit/test_science_pnas_provider.py`

**现状**

原本 3 个仅 provider / fixture / expected authors 不同的独立测试，现已收敛为：

- `test_provider_owned_html_signals_populate_final_article_authors`

**改动方式**

1. 将三者整理为一个表驱动测试。
2. 保留 `test_science_provider_falls_back_to_dom_authors_when_datalayer_is_missing` 为独立 fallback case。

**预期收益**

- 保留规则覆盖不变。
- 降低 provider author smoke case 的重复 setup。

---

### F. 用真实 XML 驱动 Elsevier 正向 contract，并参数化保留 synthetic 边界分支

**当前状态**：已完成。appendix / table / formula 相关场景已收敛为 3 个表驱动 contract 测试：正向主干改为真实 Elsevier XML，缺失稳定 DOI 的负向/稀有分支保留 synthetic。

**目标文件**

- `tests/unit/test_elsevier_markdown.py`

**落地结果**

- 新增共享 helper：
  - `_load_elsevier_golden_xml(...)`
  - `_render_elsevier_golden_markdown(...)`
- F 组公共测试已收敛为：
  - `test_elsevier_formula_rendering_contracts`
  - `test_elsevier_appendix_context_contracts`
  - `test_elsevier_table_placement_contracts`
- 正向主干已切换为真实 XML：
  - formula: `10.1016/j.agrformet.2024.109975`
  - appendix: `10.1016/j.rse.2026.115369`
  - table placement: `10.1016/j.jhydrol.2021.126210`
- 仍保留 synthetic 的边界分支：
  - inline math 不得重复变成 display block
  - formula failure placeholder + conversion notes
  - unreferenced body table -> `## Additional Tables`
- `tests/fixtures/golden_criteria/manifest.json` 与 `docs/extraction-rules.md` 已同步到 3 个新公共测试和对应 real fixture sample。

**收益**

- Elsevier F 组的正向 provenance 现在直接锚定 canonical real XML。
- synthetic 场景只保留在当前无稳定 DOI 的失败分支和稀有边界上。
- F 阶段不再需要继续评估是否值得 case-table 化，方案已实际落地。

---

## Do Not Merge

以下测试簇虽然看起来“同一规则、同一 fixture”，但属于不同层级 contract，当前不建议合并：

### 1. extractor vs provider final article

- `test_science_real_frontmatter_fixture_preserves_structured_summaries_and_main_text`
- `test_science_provider_keeps_frontmatter_sections_but_only_one_abstract_in_final_article`

前者锁 extractor 输出顺序与语义，后者锁 article model / final render 去重。

### 2. headingless body extractor vs final render

- `test_pnas_real_commentary_keeps_headingless_body_flat`
- `test_pnas_provider_renders_headingless_commentary_without_synthetic_title_section`

前者锁抽取结果，后者锁最终渲染不引入伪标题。

### 3. helper-level Springer table rendering vs integrated table injection

- `test_render_table_markdown_handles_real_springer_classic_table_page`
- `test_springer_html_injects_real_nature_inline_table_page_with_flattened_headers`
- `test_springer_html_keeps_article_success_when_inline_table_page_has_no_table`

这三者分别覆盖 helper 成功路径、集成成功路径、集成失败路径，边界清楚，应保留。

---

## Execution Order

### Phase 1

- 参数化 `test_html_availability.py`
- 参数化 `test_regression_samples.py`

### Phase 2

- 给 `science_pnas_markdown/postprocess/provider` 抽共享 helper
- 先减少重复 setup，不先动测试名和 manifest

### Phase 3

- 收敛 `markdown` / `postprocess` 的近似重复断言
- 参数化 provider-owned authors 正向 case

### Phase 4

- 评估 Elsevier case table 化是否值得
- 若可读性下降，则放弃这一阶段

---

## Acceptance Criteria

- 已注册规则测试总覆盖不下降。
- `tests/fixtures/golden_criteria/manifest.json` 不需要缩减样本，只允许测试实现方式收敛。
- `docs/extraction-rules.md` 与 manifest 的映射关系保持有效。
- 不删除跨层级 contract 测试。
- 重构后新增或保留的 helper 不引入非 canonical fixture 依赖。

---

## Verification

每一阶段至少执行：

- `pytest tests/integration/test_fixture_provenance.py`
- `pytest tests/unit/test_html_availability.py`
- `pytest tests/unit/test_regression_samples.py`
- `pytest tests/unit/test_science_pnas_markdown.py`
- `pytest tests/unit/test_science_pnas_postprocess.py`
- `pytest tests/unit/test_science_pnas_provider.py`
- `pytest tests/unit/test_elsevier_markdown.py`
- `pytest tests/unit/test_springer_html_regressions.py`
- `pytest tests/unit/test_springer_html_tables.py`

若只改局部模块，可先跑对应模块，再跑一次上述最小回归集合。

---

## Expected Outcome

完成本计划后，规则测试集合应当具备以下特征：

- case 数量变化不一定很大，但测试样板明显更少；
- “同一层级同一规则”的重复断言减少；
- “跨层级不同 contract”的覆盖继续保留；
- 后续新增规则测试时，优先沿用 case table 和 helper，而不是继续复制测试壳。
