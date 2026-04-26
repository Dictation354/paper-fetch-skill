# Paper Fetch 重构问题清单与修订计划

日期：2026-04-25

本文档记录对本项目进行只读分析后的结论。分析范围包括模块优化、模块间解耦、Markdown 提取规则合并、出版社/provider 复用，以及可用成熟 package 替代自实现逻辑的机会。

本文档本身不代表立即修改代码。后续修订应按阶段、小步提交，并由测试保护。

## 总览结论

项目当前的主流程总体清晰：

```text
CLI / MCP
-> service.py facade
-> workflow.resolution / metadata / routing / fulltext / rendering
-> providers/*
-> models / FetchEnvelope
```

主要问题不是公共流程形态，而是若干通用概念仍放在 provider 私有模块下，导致核心模型层、HTML 抽取层反向依赖 `providers._html_*`。这会让抽取规则调整、新 provider 接入、质量判断修改都更容易产生连锁影响。

最高价值的改进方向：

1. 将 provider 无关的 HTML 语义、引用处理、语言过滤、可用性评估从 `providers/` 迁到 `extraction/html`、`quality` 或 `markdown` 等中立模块。
2. 引入集中式 `ProviderSpec` / `ProviderCatalog`，统一 provider 名称、DOI/domain/publisher 路由、默认 asset 策略、abstract-only 策略和 probe 能力。
3. 瘦身 `_science_pnas_html.py`；旧 site rule、availability 常量和本地诊断数据类已删除，抽取入口保留兼容 wrapper。
4. 抽取 provider waterfall runner，复用 XML/HTML/PDF/TDM/browser fallback 编排。
5. 将 Science/PNAS/Wiley 等 browser workflow 差异收敛到 profile：hosts、URL templates、selectors、access signals、作者抽取策略和后处理。

## 当前模块形态

关键模块：

- `src/paper_fetch/service.py`：较薄的公共 facade。
- `src/paper_fetch/workflow/*`：解析、路由、元数据合并、全文编排、渲染。
- `src/paper_fetch/providers/base.py`：provider payload/result/error/status 契约。
- `src/paper_fetch/providers/elsevier.py`：Elsevier API XML/PDF 路线和资产下载。
- `src/paper_fetch/providers/springer.py`：Springer direct HTML/PDF 路线和 inline table 处理。
- `src/paper_fetch/providers/_science_pnas.py`：实际是通用 browser workflow，目前命名仍带 Science/PNAS，但被 Science、PNAS、Wiley 共用。
- `src/paper_fetch/providers/_science_pnas_html.py`：体量很大的 browser workflow HTML 抽取模块，含多处遗留重复规则。
- `src/paper_fetch/extraction/html/*`：provider-neutral HTML runtime/metadata/assets，但仍 import provider 私有 helper。
- `src/paper_fetch/models.py`：核心文章模型、渲染、质量判断和部分 HTML/availability 逻辑。

高变更风险大文件：

- `src/paper_fetch/models.py`：约 2700 行。
- `src/paper_fetch/providers/_science_pnas_html.py`：约 3000 行。
- `src/paper_fetch/extraction/html/_assets.py`：约 1200 行。
- `src/paper_fetch/providers/_flaresolverr.py`：约 1100 行。
- `src/paper_fetch/providers/springer.py`：约 1100 行。

## 问题清单

### P0（已修复）：核心/抽取层反向依赖 provider 内部模块

涉及文件：

- `src/paper_fetch/models.py`
- `src/paper_fetch/extraction/html/_runtime.py`
- `src/paper_fetch/providers/_html_citations.py`
- `src/paper_fetch/providers/_html_semantics.py`
- `src/paper_fetch/providers/_html_availability.py`
- `src/paper_fetch/providers/_language_filter.py`

现状：

- `models.py` 直接或懒加载引用 provider 私有 helper，用于 citation normalization、section semantics、availability assessment。
- `extraction/html/_runtime.py` 标称 provider-neutral，但 import 了 `providers._html_access_signals`、`providers._html_semantics`、`providers._language_filter`。

影响：

- 依赖方向不清晰：模型层和抽取层应位于 provider 下层，而不是依赖 provider 内部实现。
- 放在 `providers/` 下的共享逻辑会被误认为 provider-specific。
- 后续新增 provider 时，容易继续把共享规则塞进 `providers`，加重耦合。

建议：

- 将 provider-neutral helper 下沉到中立模块：
  - `extraction/html/signals.py`
  - `extraction/html/semantics.py`
  - `extraction/html/language.py`
  - `markdown/citations.py`
  - `quality/html_availability.py`
- providers 反向依赖这些中立模块。
- provider-specific access heuristics 留在 provider profile 或 provider-owned 模块。

修复状态：

- 已新增 `paper_fetch.extraction.html.signals`、`paper_fetch.extraction.html.semantics`、`paper_fetch.extraction.html.language`、`paper_fetch.markdown.citations`、`paper_fetch.quality.html_availability`。
- 已新增 `paper_fetch.quality.html_profiles`，承载 HTML availability site rules、Science/PNAS/Wiley positive/blocking signals、abstract redirect 判断和相关 datalayer 解析。
- `models.py`、`extraction/html/*.py` 与 `quality/*.py` 已改为依赖这些中立模块，不再 import `paper_fetch.providers._*`。
- `quality/html_availability.py` 不再懒加载 `providers/_science_pnas_profiles.py`；旧 provider-private profile 和 provider HTML 模块保留兼容 symbol，并委托到中立 profile 模块。
- 旧 `providers/_html_*` 与 `providers/_language_filter.py` 保留为兼容 re-export，避免破坏现有私有导入。
- 已增加 import-boundary 测试覆盖 `models.py`、`extraction/html/*.py` 和 `quality/*.py` 的依赖方向。

风险：

- 中等。多数是 import move，但 quality classification 若迁移失误会改变行为。

验证：

- 运行 models、HTML availability、HTML semantics、provider markdown extraction 测试。
- 增加 import-boundary 测试，防止 `models`、`extraction/html` 或 `quality` 再 import `paper_fetch.providers._*`。

### P0（已修复）：Provider 身份与能力配置分散

涉及文件：

- `src/paper_fetch/publisher_identity.py`
- `src/paper_fetch/providers/registry.py`
- `src/paper_fetch/workflow/routing.py`
- `src/paper_fetch/workflow/types.py`
- `src/paper_fetch/workflow/fulltext.py`
- `src/paper_fetch/mcp/tools.py`

现状：

- Provider 名称和 official provider 集合散落在多处。
- DOI prefixes、publisher aliases、domain rules、默认 asset policy、状态排序、abstract-only policy 分别配置。
- 新增 provider 需要改 routing、workflow、identity、MCP、registry 等多个位置。

建议：

- 引入 `ProviderSpec` 和 `ProviderCatalog`。
- 建议字段：
  - `name`
  - `official`
  - `domains`
  - `doi_prefixes`
  - `publisher_aliases`
  - `asset_default`
  - `probe_capability`
  - `abstract_only_policy`
  - `client_factory`
  - `status_order`
- 让 `publisher_identity`、routing、默认 asset profile、MCP provider listing、registry 都读取 catalog。

修复状态：

- 已新增 `paper_fetch.provider_catalog.ProviderSpec` 与静态 `PROVIDER_CATALOG`。
- `publisher_identity`、`workflow.routing`、`workflow.types`、`workflow.fulltext`、`workflow.rendering`、`mcp.tools`、`providers.registry` 已从 catalog 派生 provider 身份、路由规则、默认资产策略、abstract-only 策略、status 顺序、official 判断、已知 source 判断和 client factory。
- `client_factory_path` 使用字符串路径，registry 运行时再加载 provider client，避免 catalog import provider 实现。
- 已增加 catalog 一致性测试覆盖 registry、official provider、source 到 provider 映射、known article source、asset 默认值、status order 和现有 DOI/publisher/domain 推断行为。
- Phase 2 provider catalog 收尾已完成；不进入 Phase 3 browser workflow profile 重命名。

风险：

- 中等。路由顺序和 provider 优先级一旦变化会影响结果。

验证：

- 已运行 `pytest tests/unit/test_provider_catalog.py`、`pytest tests/unit/test_publisher_identity.py`、`pytest tests/unit/test_provider_status.py`、`pytest tests/unit/test_provider_request_options.py`、`pytest tests/unit/test_service_provider_managed_fallbacks.py`、`pytest tests/integration/test_architecture_closeout.py` 和 `pytest`。
- 全量结果：`581 passed, 1 skipped`。
- 已运行 `ruff check src/paper_fetch/provider_catalog.py src/paper_fetch/workflow/fulltext.py src/paper_fetch/workflow/rendering.py src/paper_fetch/mcp/tools.py tests/unit/test_provider_catalog.py`。

### P0（已修复）：`_science_pnas_html.py` 存在大量遗留重复规则

涉及文件：

- `src/paper_fetch/providers/_science_pnas_html.py`
- `src/paper_fetch/providers/_science_pnas_profiles.py`
- `src/paper_fetch/providers/_browser_workflow_shared.py`
- `src/paper_fetch/providers/_html_availability.py`
- `src/paper_fetch/providers/_html_tables.py`
- `src/paper_fetch/providers/_science_pnas_postprocess.py`

现状：

- 已删除 `_science_pnas_html.py` 中重复的 `SITE_RULE_OVERRIDES`、`PUBLISHER_HOSTS`、`PDF_URL_TOKENS`、`DEFAULT_SITE_RULE`、`HTML_FULLTEXT_MARKERS`。
- 已删除本地重复 availability 分析结构和死代码，如 `StructuredBodyAnalysis`、`FulltextAvailabilityDiagnostics`、`_analyze_html_structure`、`_analyze_markdown_structure`、`_structure_accepts_fulltext`、`_dom_access_hints`。
- `_science_pnas_html.py` 仍保留 browser HTML 抽取编排、table / figure / formula 处理和兼容 wrapper；site rules / URL tokens / positive signals / availability 由 profile/shared/quality 模块提供。

建议：

- 让 `_science_pnas_profiles.py` 和 `_browser_workflow_shared.py` 成为 site rules、hosts、URL tokens、positive signals 的唯一事实来源。
- `_science_pnas_html.py` 只保留抽取编排和仍被测试直接 import 的兼容 wrapper。
- 确认无 public import 依赖后，迁移或删除重复 availability/table 代码。

风险：

- 中到高。抽取行为对空格、caption、表格、figure link 很敏感。

验证：

- 运行 Science/PNAS/Wiley Markdown 测试和 golden criteria 测试。
- 删除重复实现前，为仍需 re-export 的兼容 symbol 增加明确测试。

### P0（已修复）：Provider fallback/waterfall 逻辑重复

涉及文件：

- `src/paper_fetch/providers/elsevier.py`
- `src/paper_fetch/providers/springer.py`
- `src/paper_fetch/providers/_science_pnas.py`
- `src/paper_fetch/providers/wiley.py`

现状：

- 已新增 `src/paper_fetch/providers/_waterfall.py`，提供 `ProviderWaterfallStep` 和 `run_provider_waterfall`。
- Elsevier、Springer、Science/PNAS browser workflow、Wiley 已使用 runner 编排主要 fallback 顺序。
- Provider-specific step 仍负责自己的 payload、warning 文案、错误映射和 source marker，runner 只负责顺序、warning 累积、失败组合和成功停止。

建议：

- 增加轻量 `run_provider_waterfall(steps, failure_policy)`。
- 每个 step 可定义：
  - `name`
  - `attempt()`
  - `is_usable(result)`
  - `success_markers`
  - `failure_markers`
  - `fallback_warning`
  - `failure_mapper`
- provider-specific 细节仍留在 step 定义中，不要强行把 Elsevier XML 和 browser HTML 统一成同一内部结构。

风险：

- 中等。错误消息和 source trail 是用户可见诊断信息。

验证：

- 重构前锁定当前 warning/source-trail 期望。
- 运行 provider waterfall tests 和 service fallback tests。

### P0（已修复）：`fetch_result` 的资产/警告/trace 组装重复

涉及文件：

- `src/paper_fetch/providers/base.py`
- `src/paper_fetch/providers/_science_pnas.py`
- `src/paper_fetch/providers/springer.py`

现状：

- Base `ProviderClient.fetch_result` 已改为 template-method，统一以下流程：
  - 获取 raw payload
  - 传播 local-copy flag
  - 计算 artifact policy
  - 下载 related assets
  - 合并 warning/trace
  - `to_article_model`
  - `describe_artifacts`
- Browser workflow 和 Springer 不再复制完整尾部组装；只覆盖 `prepare_fetch_result_payload`、`maybe_recover_fetch_result_payload`、`should_download_related_assets_for_result`、`finalize_fetch_result_article` 或 `asset_download_failure_warning` 等 hook。

建议：

- 将 base `fetch_result` 改成 template-method 风格。
- 候选 hook：
  - `prepare_payload()`
  - `maybe_recover_payload()`
  - `should_download_assets()`
  - `finalize_abstract_only()`
  - `asset_download_failure_warning()`
- Browser 和 Springer 只覆盖 hook。

风险：

- 中等。Asset download policy 必须保持 provider-specific。

验证：

- 运行 `test_service_provider_managed_fallbacks`、`test_provider_waterfalls`、provider asset tests、PDF fallback tests。

### P1：Browser workflow 命名和 provider profile 边界混乱

涉及文件：

- `src/paper_fetch/providers/_science_pnas.py`
- `src/paper_fetch/providers/science.py`
- `src/paper_fetch/providers/pnas.py`
- `src/paper_fetch/providers/wiley.py`
- `src/paper_fetch/providers/_science_pnas_profiles.py`

现状：

- `_science_pnas.py` 实际是通用 browser workflow，但名称仍绑定 Science/PNAS。
- 内部仍有 `self.name in {"science", "pnas", "wiley"}`、PNAS 文案等 name-specific 分支。

建议：

- 概念上拆为 `providers/browser_workflow.py`。
- 定义 `ProviderBrowserProfile`：
  - URL builders
  - PDF fallback policy
  - HTML extractor
  - asset strategy
  - user-facing provider label
  - access signal provider
  - author extraction strategy
- `science.py`、`pnas.py`、`wiley.py` 保持轻量。

风险：

- 中等。主要是架构和命名，但 import 和兼容性需要谨慎。

验证：

- 临时保留 compatibility alias，确保现有测试/import 不断。

### P1：Browser provider URL candidate builders 重复

涉及文件：

- `src/paper_fetch/providers/_science_html.py`
- `src/paper_fetch/providers/_pnas_html.py`
- `src/paper_fetch/providers/_wiley_html.py`
- `src/paper_fetch/providers/_browser_workflow_shared.py`

现状：

- Science、PNAS、Wiley 都执行：
  - preferred landing URL
  - base host generation
  - path templates
  - ordered dedupe
- PDF candidate builders 也高度相似，只是模板顺序和 Crossref PDF 位置不同。

建议：

- 增加配置驱动 builder：
  - `build_provider_html_candidates(profile, doi, landing_page_url)`
  - `build_provider_pdf_candidates(profile, doi, crossref_pdf_url)`
- 将差异放进 profile 字段：
  - `html_path_templates`
  - `pdf_path_templates`
  - `crossref_pdf_position`
  - `hosts`
  - `base_hosts`

风险：

- 低到中。Candidate 顺序会影响访问成功率。

验证：

- 为每个 provider 增加 candidate ordering snapshot 测试。

### P1：Crossref PDF link 提取重复

涉及文件：

- `src/paper_fetch/providers/_browser_workflow_shared.py`
- `src/paper_fetch/providers/_pdf_candidates.py`

现状：

- 两个模块都从 Crossref `fulltext_links` 里判断 PDF URL，使用 URL token 和 content type。

建议：

- 让 `_pdf_candidates.extract_pdf_url_from_metadata_links()` 成为唯一实现。
- Browser workflow 直接复用该函数。

风险：

- 低。行为容易用测试锁定。

验证：

- 覆盖 `application/pdf`、`/doi/pdf/`、`/doi/pdfdirect/`、`/doi/epdf/`、`/fullpdf`、`.pdf`、`download=true`。

### P1：Landing HTML fetch 和 metadata probe 重复

涉及文件：

- `src/paper_fetch/resolve/query.py`
- `src/paper_fetch/providers/springer.py`
- `src/paper_fetch/workflow/routing.py`

现状：

- 多处执行相似 HTML GET，配置类似 Accept/User-Agent，再解析 HTML metadata。
- Springer 有定制 redirect 处理，应保留 provider-specific redirect 限制。

建议：

- 增加 `fetch_landing_html(transport, url, env_or_user_agent, max_redirects)`，返回：
  - response
  - final URL
  - decoded HTML
  - parsed HTML metadata
- Springer 传入自己的 redirect policy 和 headers。

风险：

- 中等。Redirect 语义和 URL redaction 需要保持稳定。

验证：

- 增加 redirect 和 HTML metadata fixture 测试。

### P1：HTML 作者抽取规则重复

涉及文件：

- `src/paper_fetch/providers/_science_html.py`
- `src/paper_fetch/providers/_pnas_html.py`
- `src/paper_fetch/providers/_wiley_html.py`
- `src/paper_fetch/providers/_springer_html.py`

现状：

- 以下逻辑重复：
  - 判断是否像作者名
  - 忽略 ORCID/URL/email
  - 读取 meta `citation_author`
  - 读取 schema.org `givenName` + `familyName`
  - provider selector

建议：

- 增加 `html_author_extraction.py`：
  - `looks_like_author_name`
  - `is_common_non_author_text`
  - `extract_meta_authors`
  - `extract_schema_person_authors`
  - selector-driven DOM extractor
- provider-specific ignore phrase、datalayer/json-ld 优先级留在 provider 模块。

风险：

- 中等。作者顺序和去重是用户可见元数据。

验证：

- 各 provider 作者抽取测试和 golden metadata 检查。

### P1：Script JSON / Datalayer 解析重复

涉及文件：

- `src/paper_fetch/providers/_science_html.py`
- `src/paper_fetch/providers/_pnas_html.py`
- `src/paper_fetch/providers/_wiley_html.py`

现状：

- 各 provider 都用 regex 抓 JavaScript JSON assignment 或 push payload，再调用 `json.loads`。

建议：

- 增加 helper：
  - `extract_script_json(patterns, html_text)`
  - `extract_assignment_json(var_name, html_text)`
  - `extract_function_call_json(function_name, html_text)`
- provider-specific 对象路径解析保留本地。

风险：

- 低到中。Regex 形态相近但仍有差异。

验证：

- 用 AAAS、PNAS、Wiley script 样本做单元测试。

### P2：Markdown inline normalization 重复

涉及文件：

- `src/paper_fetch/providers/_article_markdown_common.py`
- `src/paper_fetch/providers/_html_section_markdown.py`
- `src/paper_fetch/providers/_html_tables.py`
- `src/paper_fetch/providers/_science_pnas_html.py`

现状：

- 多个模块分别处理 sub/sup、换行、标点、Markdown emphasis 附近的 inline text normalization。
- 规则轻微漂移会造成难以排查的 Markdown 差异。

建议：

- 增加共享 inline normalization helper，并用 policy 区分：
  - XML inline text
  - HTML body text
  - HTML heading text
  - table cell text
  - citation-aware text
- renderer-specific 行为通过 policy 参数表达，而不是复制 regex。

风险：

- 中等。即使只是空格变化，也可能影响 snapshot/golden。

验证：

- 覆盖 sub/sup punctuation、inline formula、italic/bold、citation sentinel、table cell。

### P2：Section taxonomy 分散

涉及文件：

- `src/paper_fetch/models.py`
- `src/paper_fetch/extraction/html/_runtime.py`
- `src/paper_fetch/providers/_html_semantics.py`
- `src/paper_fetch/providers/_science_pnas_html.py`

现状：

- abstract/front matter/back matter/data availability/ancillary heading 集合分散定义。
- DOM 分类和 Markdown block 过滤维护了相近但不完全相同的 taxonomy。

建议：

- 增加共享 section taxonomy：
  - heading sets
  - identity token sets
  - section kind enum/literals
  - DOM heading classifier
  - Markdown heading classifier
- 允许 provider profile 扩展 Science structured abstract、PNAS significance、Wiley abbreviations、Springer/Nature section conventions。

风险：

- 中等。过度泛化可能破坏必要的 provider-specific 处理。

验证：

- 覆盖 abstract-only detection、data availability retention、references removal、narrative article types。

### P2：Table rendering 应单一来源

涉及文件：

- `src/paper_fetch/providers/_html_tables.py`
- `src/paper_fetch/providers/_html_section_markdown.py`
- `src/paper_fetch/providers/_science_pnas_html.py`
- `src/paper_fetch/providers/springer.py`

现状：

- 已有共享 `_html_tables.py`，但 `_science_pnas_html.py` 仍保留旧 table analysis/rendering。
- Springer 的 inline table supplement fetch 是 provider-specific，应保留。

建议：

- 让 `_html_tables.py` 成为唯一 table matrix/rendering 实现。
- 增加注入点：
  - inline citation renderer
  - table caption extraction policy
  - degraded/fallback placeholder text
- Springer 保留 table supplement retrieval，但最终渲染使用共享代码。

风险：

- 中到高。Rowspan/colspan、多级表头、caption、footnote 都很脆弱。

验证：

- 运行 Springer table tests、Science/PNAS table tests、含复杂表格的 golden criteria。

### P2：Figure link injection 存在两套策略

涉及文件：

- `src/paper_fetch/providers/_science_pnas_html.py`
- `src/paper_fetch/providers/_science_pnas_postprocess.py`
- `src/paper_fetch/providers/html_assets.py`
- `src/paper_fetch/extraction/html/_assets.py`

现状：

- 抽取阶段 figure link 插入和下载后 `rewrite_inline_figure_links()` 使用不同匹配逻辑。

建议：

- 引入共享 `FigureLinker` 或 helper：
  - label normalization
  - caption matching
  - URL alias matching
  - downloaded asset path preference
  - publisher profile options
- 抽取阶段和 asset 下载后都复用它。

风险：

- 中到高。Science `f1`、PNAS `fig01`、Wiley asset name、Springer full-size page 差异大。

验证：

- 每个 provider 的 asset rewrite 测试。
- Golden fixture 检查相对 asset link。

### P2：Formula detection 规则重复

涉及文件：

- `src/paper_fetch/providers/_html_section_markdown.py`
- `src/paper_fetch/providers/_science_pnas_html.py`
- `src/paper_fetch/extraction/html/_assets.py`
- `src/paper_fetch/providers/_article_markdown_math.py`

现状：

- Formula image URL regex 和 formula container tokens 重复。
- MathML 渲染已有部分共享，但 HTML formula discovery 分散。

建议：

- 增加共享 `html_formula_rules.py`：
  - formula image URL pattern
  - formula ancestor/container tokens
  - candidate image attributes
  - MathML extraction helper
  - display vs inline classifier
- XML formula rendering 继续留在 `_article_markdown_math.py`。

风险：

- 中等。Provider-specific image attrs 和 fallback formula 容易回归。

验证：

- 运行 Science、Wiley、Springer、Elsevier XML 的 formula conversion 和 HTML Markdown 测试。

### P2：Springer/Nature noise profile 有误导性

涉及文件：

- `src/paper_fetch/extraction/html/_runtime.py`
- `src/paper_fetch/providers/html_springer_nature.py`

现状：

- Springer/Nature 代码传递或暗示 `springer_nature` noise profile，但 runtime 只识别 generic 和 pnas-specific promo tokens，未知值会回退 generic。

建议：

- 要么注册真实 `springer_nature` profile，要么停止传递该名称。
- 只有在有具体额外 tokens/selectors 且有测试保护时，才注册新 profile。

风险：

- 低。

验证：

- Springer/Nature extraction tests 覆盖 rights/permissions、related content、back matter。

### P3：Provider payload legacy 协议仍隐式存在

涉及文件：

- `src/paper_fetch/providers/base.py`

现状：

- `RawFulltextPayload` 仍接受 legacy `metadata` magic keys，并转成 `ProviderContent`。
- 兼容性保留了，但 provider/workflow 契约不够显式。

建议：

- 近期重构中保留兼容。
- 增加 deprecation comment 和测试，明确记录当前接受哪些 legacy keys。
- 后续要求 provider 直接返回 `ProviderFetchResult`、`ProviderContent`、`ProviderArtifacts`。

风险：

- 中等。现有测试或外部用户可能还在实例化 legacy payload。

验证：

- 移除前先保留兼容性测试。

### P3：Provider interface 依赖具体基类和运行时判断

涉及文件：

- `src/paper_fetch/providers/base.py`
- `src/paper_fetch/workflow/fulltext.py`

现状：

- `ProviderClient` 是带默认方法的基类，默认方法抛 `ProviderFailure`。
- Workflow 仍使用 `Any` 和 `hasattr(fetch_result)` 之类运行时判断。

建议：

- 增加 `typing.Protocol`：
  - `MetadataProvider`
  - `FulltextProvider`
  - `StatusProvider`
  - `AssetProvider`
- Registry 可返回 `ProviderSpec + client`。
- 如有必要，保留 base class 作为 convenience implementation。

风险：

- 低到中。主要是类型边界清晰化，但测试可能依赖 subclass 行为。

验证：

- 不需要专门类型测试，但运行时 provider 测试应保持通过。

### P3：Crossref lookup 同时服务 provider 和 resolution，却位于 providers 下

涉及文件：

- `src/paper_fetch/providers/crossref.py`
- `src/paper_fetch/resolve/crossref.py`
- `src/paper_fetch/resolve/query.py`

现状：

- Resolve 层间接复用 provider Crossref client。
- provider 与 metadata client 边界不清晰。

建议：

- 将 Crossref HTTP lookup 移到 `clients/crossref.py` 或 `metadata/crossref.py`。
- Provider 层和 resolve 层共同依赖该底层 client。

风险：

- 中等。Query resolution 行为和 Crossref metadata 行为必须保持一致。

验证：

- 运行 resolve query tests 和 Crossref provider metadata tests。

### P3：Artifact 与 cache policy 分散在 workflow、CLI、MCP

涉及文件：

- `src/paper_fetch/workflow/fulltext.py`
- `src/paper_fetch/cli.py`
- `src/paper_fetch/mcp/tools.py`
- `src/paper_fetch/mcp/cache_index.py`

现状：

- Provider payload saving、Markdown saving、fetch envelope cache、MCP resource handling 分散在不同层。

建议：

- 增加 `ArtifactStore`、`DownloadPolicy`、`FetchCache`。
- Workflow 只产出 artifact intents 和 article result；adapter 决定如何写文件。

风险：

- 中等。路径和 MCP resource URI 是用户可见行为。

验证：

- CLI output tests、MCP integration tests、cache index tests。

### P3：HTML asset compatibility facade 使用隐藏全局修改

涉及文件：

- `src/paper_fetch/providers/html_assets.py`
- `src/paper_fetch/extraction/html/_assets.py`

现状：

- Compatibility facade 临时 monkey-patch `_asset_impl` 内部函数。

建议：

- 改成显式依赖注入：
  - `opener_factory`
  - `request_fn`
  - `image_document_fetcher`
  - `figure_page_fetcher`

风险：

- 中等。并发执行和 monkey-patch 当前 internals 的测试可能受影响。

验证：

- Asset downloader tests 和并行测试。

## 可用成熟 Package 替代机会

这些替换是可选项，应在架构边界更清晰后推进，不建议优先于模块解耦。

### HTTP Retry

现状：

- `src/paper_fetch/http.py` 使用 `urllib3.PoolManager`，但关闭 urllib3 自带 retry，手写 429/5xx/timeout retry。

候选：

- `urllib3.util.Retry`

收益：

- 减少自维护 retry/backoff 代码。

风险：

- 当前实现有结构化日志、取消检查、最大等待时间和 `RequestFailure` 形状，这些都必须保留。

### `.env` 与平台目录

现状：

- `src/paper_fetch/config.py` 手写 `.env` 解析和 XDG 路径。

候选：

- `python-dotenv`
- `platformdirs`
- 可选 `pydantic-settings`

收益：

- 减少配置解析边界问题，提高跨平台目录处理可靠性。

风险：

- 必须保持现有环境变量优先级。

### 内存 HTTP Cache

现状：

- `src/paper_fetch/http.py` 自实现 TTL LRU，并统计 total body bytes。

候选：

- `cachetools.TTLCache`

收益：

- 减少 cache eviction 代码。

风险：

- 当前 total-body-byte limit、敏感 header/query 脱敏 cache key 仍需要 wrapper。

### MCP / 文件 Cache

现状：

- `src/paper_fetch/mcp/cache_index.py` 手写 JSON index、扫描和去重。

候选：

- `diskcache`
- 如果保留 JSON 兼容，可加 `filelock`

收益：

- 原子写和并发行为更稳。

风险：

- 需要保持现有 MCP resource URI 兼容。

### FlareSolverr Rate Limiting

现状：

- `src/paper_fetch/providers/_flaresolverr.py` 用 JSON 文件记录窗口计数，只用进程内锁保护。

候选：

- `limits`
- `pyrate-limiter`
- `filelock` 或 `portalocker`

收益：

- 多进程行为更安全。

风险：

- 现有 provider 粒度错误消息和限流策略需要映射。

### Image Type And Dimensions

现状：

- `src/paper_fetch/extraction/html/_assets.py` 手写 JPEG/PNG/GIF/WebP magic 和尺寸解析。

候选：

- `filetype` + `imagesize`
- `Pillow`

收益：

- 减少二进制格式维护。

风险：

- 依赖体积可能不值得；当前只支持少数格式时自实现也可接受。

### DOI 与标题相似度

现状：

- `src/paper_fetch/publisher_identity.py` 使用自定义 DOI regex/normalize。
- `src/paper_fetch/resolve/query.py` 使用 token Jaccard + `SequenceMatcher`。

候选：

- `idutils` 用于 DOI 校验/规范化。
- `rapidfuzz` 用于标题匹配。

收益：

- 边界更稳，fuzzy matching 更快。

风险：

- 当前 DOI routing 依赖较宽松的 normalize；变严格可能降低召回。
- fuzzy score 阈值需要重新标定。

## 不建议整体替换的逻辑

以下部分不建议作为主要策略整体替换成通用 package：

- Publisher routing 和候选 URL 生成。这是项目核心业务启发式。
- 科研文章 HTML extraction 和 postprocessing。通用 `markdownify` / `html2text` 很难可靠保留 formula、citation、figure、table 和 publisher noise 策略。
- PDF fallback 编排。Playwright、cookies、seeded context、publisher PDF candidates、HTML access detection 的组合属于业务逻辑。
- CLI。当前 `argparse` 对命令面足够。
- Formula conversion 编排。当前已经优先使用外部 `texmath` / Node `mathml-to-latex`，并保留 fallback。

## 多阶段修订计划

### Phase 0：建立基线与安全护栏

目标：

- 在重构前保护当前行为。

范围：

- 不改功能。
- 增强当前 provider warnings、source trails、routing、Markdown snapshots 的测试。

任务：

1. 记录当前 import graph 约束，并增加面向目标架构的 import-boundary 测试。
2. Snapshot Science、PNAS、Wiley、Springer、Elsevier 等 provider URL candidate ordering。
3. Snapshot waterfall warning/source-trail 行为：
   - Elsevier XML 成功
   - Elsevier XML 失败 -> PDF 成功
   - Springer HTML 成功
   - Springer HTML abstract/fail -> PDF 成功/失败
   - Science/PNAS/Wiley HTML 成功/fallback
4. 识别 `_science_pnas_html.py` 中被测试或公共模块 import 的 symbol。
5. 用测试标注 legacy compatibility surface，确保后续移除是有意行为。

退出标准：

- 现有 unit/integration suite 通过。
- 有 import-boundary 测试记录当前或目标 layering。
- 高风险 provider fallback 路径有行为 snapshot。

建议验证：

```bash
pytest tests/unit/test_publisher_identity.py tests/unit/test_provider_waterfalls.py tests/unit/test_service_provider_managed_fallbacks.py
pytest tests/unit/test_science_pnas_markdown.py tests/unit/test_springer_html_regressions.py tests/unit/test_elsevier_markdown.py
```

完成状态（2026-04-26）：

- Phase 0 已完成；本阶段不修改业务功能，只补齐重构前的行为基线和兼容护栏。
- 已有 `tests/unit/test_import_boundaries.py` 记录 `models.py`、`extraction/html/*.py`、`quality/*.py` 不得依赖 `paper_fetch.providers._*` 的目标 layering。
- Provider URL/PDF candidate ordering 已有 snapshot 覆盖 Science、PNAS、Wiley；本次补齐 Springer PDF candidate ordering，并在 Elsevier fallback 测试中锁定 XML -> PDF API route 的请求顺序、URL 和 `view=FULL` query。
- Waterfall warning/source-trail 行为已补齐断言：Elsevier XML 不可用后进入 PDF fallback 时保留 XML fail、PDF API ok、PDF fallback ok marker，并记录 fallback warning；Springer HTML 不可用后进入 PDF fallback 时保留 HTML fail、PDF fallback ok marker，并记录 fallback warning。
- `_science_pnas_html.py` 的 compatibility surface 已显式测试，包括 browser workflow 入口、figure link rewrite、profile candidate wrapper、availability wrapper、HTML block detection 和 legacy html-noise re-export，后续删减需要有意更新测试。
- `RawFulltextPayload.metadata` legacy magic-key ingestion 已由测试标注：`route`、`reason`、`markdown_text`、`merged_metadata`、availability diagnostics、HTML fetcher、browser seed、failure reason/message、extracted assets、warnings、source trail 仍会被转换到结构化字段，同时保留未知 passthrough metadata。

本次验证：

```bash
ruff check tests/unit/test_pdf_fallback_helpers.py tests/unit/test_provider_waterfalls.py tests/unit/test_provider_fetch_result_template.py tests/unit/test_science_pnas_html_static.py
pytest tests/unit/test_pdf_fallback_helpers.py tests/unit/test_provider_waterfalls.py tests/unit/test_provider_fetch_result_template.py tests/unit/test_science_pnas_html_static.py
pytest tests/unit/test_publisher_identity.py tests/unit/test_provider_waterfalls.py tests/unit/test_service_provider_managed_fallbacks.py tests/unit/test_science_pnas_markdown.py tests/unit/test_springer_html_regressions.py tests/unit/test_elsevier_markdown.py
ruff check
pytest
```

### Phase 1：清理依赖边界（完成）

目标：

- 将 provider-neutral helper 移出 provider 私有模块，明确层次边界。

范围：

- 只做 import move 和兼容 facade。
- 不改变行为。

任务：

1. 将 HTML access signals、semantics、language filtering 从 `providers/_html_*` 移到 `extraction/html/*` 或等价中立模块。
2. 将 `models.py` 使用的 citation normalization 移到 `markdown/citations.py`。
3. 将 availability assessment 移到 `quality/html_availability.py` 或 `extraction/html/availability.py`。
4. 旧 provider-private 模块暂时保留为薄 compatibility facade。
5. 更新 `models.py` 和 `extraction/html/_runtime.py` import，改为引用中立模块。

完成状态：

- HTML access signals、semantics、language filtering、citation normalization 和 availability assessment 已迁到 provider-neutral 模块。
- 已补齐 availability profile 边界：新增 `paper_fetch.quality.html_profiles`，`quality/html_availability.py` 不再依赖 `providers/_science_pnas_profiles.py`。
- Science/PNAS/Wiley 的 availability site rules、positive signals、blocking fallback signals 和 AAAS/PNAS/Wiley datalayer 解析由 `quality/html_profiles.py` 统一承载；`providers/_science_pnas_profiles.py`、`providers/_science_html.py`、`providers/_pnas_html.py`、`providers/_wiley_html.py` 保留兼容 facade。
- Import-boundary 测试已扩展到 `quality/*.py`，防止中立 quality 层重新 import `paper_fetch.providers._*`。

退出标准：

- `models.py` 不再 import `paper_fetch.providers._*`。
- `extraction/html/_runtime.py` 不再 import provider-private helper。
- `quality/*.py` 不再 import provider-private helper。
- 兼容 facade 仍保证现有测试通过。

验证：

- 本阶段收尾验证命令包括 `pytest tests/unit/test_import_boundaries.py`、HTML availability/access/semantics/citations 测试、Science/PNAS browser workflow 测试、architecture closeout、provider waterfall/service fallback 测试和默认 `pytest`。

风险：

- 低到中。如果纯移动实现，风险可控。

### Phase 2：集中 Provider Catalog 与 Routing

目标：

- 让 provider identity 和 capability metadata 单一来源。

范围：

- 引入 `ProviderSpec` / `ProviderCatalog`。
- 保持现有 provider client 和行为。

任务：

1. 为 Crossref、Elsevier、Springer、Wiley、Science、PNAS 定义 provider spec。
2. 将 DOI prefix、domain、publisher alias、official-provider、默认 asset policy 移入 catalog。
3. 更新 `publisher_identity.py`、routing、workflow asset defaults、MCP provider list、registry，使其读取 catalog。
4. 增加一致性测试。

退出标准：

- 新增 provider 基本只需要新增 spec 和 client factory。
- 测试外不再散落重复 official-provider list。

风险：

- 中等。Routing priority 和 candidate ordering 敏感。

### Phase 3：Browser Workflow Profile 重构

目标：

- 将通用 browser workflow 与 Science/PNAS 命名解耦，并集中 browser provider 配置。

范围：

- 概念上拆出 browser workflow。
- 暂时保留旧 import 兼容。

任务：

1. 新增 `providers/browser_workflow.py`，放通用 browser workflow class/function。
2. 定义 `ProviderBrowserProfile`，包含 hosts、URL templates、PDF templates、selectors、access signals、author strategy、postprocess hooks、provider label。
3. 将 Science、PNAS、Wiley 改为 profile-driven URL candidate builders。
4. 将重复 Crossref PDF link extraction 收敛到 `_pdf_candidates.py`。
5. 抽出共享 script JSON/datalayer parsing helper。
6. 抽出共享 HTML author helper，provider-specific 行为通过 strategy hook 表达。

退出标准：

- `_science_pnas.py` 变为兼容 wrapper，或只保留真正共享的 legacy name。
- Science/PNAS/Wiley provider 模块主要声明 profile 和 provider-specific hook。

风险：

- 中等。Browser access 和 URL ordering 容易回归。

本地执行记录（2026-04-25）：

- Phase 3 已完成：新增 `src/paper_fetch/providers/browser_workflow.py` 作为 canonical runtime，`_science_pnas.py` 改为兼容 alias。
- Science、PNAS、Wiley 已改为 `ProviderBrowserProfile` 驱动，保留现有 public source、fallback marker、MCP payload shape 和 URL candidate 顺序。
- Crossref PDF URL 判断已集中到 `_pdf_candidates.py`，HTML/PDF candidate builder 已收敛到 `_browser_workflow_shared.py`。
- 作者抽取的共享 helper 已抽到 `_browser_workflow_authors.py`，当前覆盖 Science datalayer、PNAS meta fallback、Wiley meta-first 行为。
- 本阶段验证命令：`ruff check`、`pytest tests/unit/test_science_pnas_candidates.py`、`pytest tests/unit/test_science_pnas_provider.py`、`pytest tests/unit/test_provider_waterfalls.py`、`pytest tests/unit/test_provider_request_options.py`、`pytest tests/unit/test_provider_status.py`、`pytest tests/unit/test_science_pnas_markdown.py`、`pytest tests/unit/test_science_pnas_postprocess.py tests/unit/test_science_pnas_postprocess_units.py`、`pytest tests/integration/test_architecture_closeout.py`、`pytest tests/integration/test_golden_corpus.py`、`pytest`。
- Phase 4 的 Markdown/table/formula/FigureLinker 深度整理未进入本阶段。

### Phase 4：Markdown 规则合并

目标：

- 减少 Markdown/HTML extraction 规则重复，同时保留 publisher-specific 行为。

范围：

- 高风险抽取工作，必须分小步推进。

任务：

1. 删除或 re-export `_science_pnas_html.py` 中重复 site rules。
2. 让 `_html_availability.py` 或迁移后的中立模块成为唯一 availability 实现。
3. 将 table rendering 收敛到 `_html_tables.py`。
4. 增加共享 inline text normalization policies，覆盖 XML、HTML body、heading、table cell。
5. 增加共享 section taxonomy 和 provider profile extensions。
6. 增加共享 `html_formula_rules.py`。
7. 增加共享 `FigureLinker`，同时用于 extraction-time 和 post-download figure link rewriting。
8. 注册或移除误导性的 `springer_nature` noise profile。

退出标准：

- `_science_pnas_html.py` 明显变小，并主要承担 browser HTML pipeline orchestration。
- Table、formula、figure-link、section taxonomy、availability 每类规则都有单一 owner。
- Provider-specific 差异通过 profiles 或 hook functions 表达。

风险：

- 高。Golden Markdown 输出可能发生细微变化。

建议验证：

```bash
pytest tests/unit/test_science_pnas_markdown.py
pytest tests/unit/test_science_pnas_postprocess.py tests/unit/test_science_pnas_postprocess_units.py
pytest tests/unit/test_springer_html_regressions.py tests/unit/test_springer_html_tables.py
pytest tests/unit/test_elsevier_markdown.py
pytest tests/integration/test_golden_corpus.py
```

完成状态（2026-04-26）：

- Phase 4 已完成；本阶段只合并 Markdown/HTML extraction 规则，不主动改变抽取输出语义。
- Table rendering 已收敛到 `providers/_html_tables.py`：`_science_pnas_html.py` 不再保留 table cell、rowspan/colspan matrix、header flatten、Markdown table 渲染的本地实现，相关私有入口改为薄委托。
- Inline text normalization 已新增 `extraction/html/inline.py`，统一 body、heading、table cell 的空白、`sub`/`sup` 和标点贴合规则；HTML section renderer、table renderer、Science/PNAS browser HTML pipeline 均改为复用该 helper。
- Section taxonomy 已集中到 `extraction/html/semantics.py`：DOM heading 分类与 Markdown heading 解析/分类共用 canonical heading sets，`extraction/html/_runtime.py` 和 `_science_pnas_html.py` 不再维护本地 Markdown heading 集合或解析逻辑。
- Formula discovery 已新增 `extraction/html/formula_rules.py`，统一 formula image URL pattern、container tokens、image candidate attrs、MathML extraction、display formula 判断和 formula image detection；`_html_section_markdown.py`、`_science_pnas_html.py`、`extraction/html/_assets.py` 已复用该模块。
- Figure link matching 已新增 `extraction/html/figure_links.py`，统一 figure label normalization、asset URL/path alias matching、downloaded `path` 优先级；extraction-time injection 与 post-download rewrite 现在共用同一实现。
- Availability/site rules 已确认继续由 `quality/html_availability.py` 与 `quality/html_profiles.py` 单一承载；本阶段只补充 Markdown/table/formula/figure/taxonomy/noise 相关测试。
- `springer_nature` noise profile 已在 `extraction/html/_runtime.py` 注册，不再静默回退 generic；只加入了有 Springer/Nature fixture 或单元测试保护的 promo tokens。
- Phase 0 明确测试的 `_science_pnas_html.py` compatibility surface 保持不变；provider-private public wrappers 仍保留。

本阶段验证：

```bash
ruff check
pytest tests/unit/test_html_shared_helpers.py tests/unit/test_html_semantics.py tests/unit/test_science_pnas_postprocess.py tests/unit/test_science_pnas_postprocess_units.py tests/unit/test_science_pnas_markdown.py tests/unit/test_springer_html_regressions.py tests/unit/test_springer_html_tables.py
pytest tests/unit/test_elsevier_markdown.py
pytest tests/integration/test_golden_corpus.py
pytest
```

未进入本阶段的后续事项：

- Phase 3 后续可继续清理 browser workflow 命名和 profile 边界，但不与 Markdown rule consolidation 混在同一阶段。
- Phase 5 的 provider waterfall/fetch result template 清理已在后续阶段完成。
- Phase 6 的 runtime context、artifact/cache policy、asset downloader 依赖注入已在后续阶段完成。

### Phase 5（已完成）：Provider Waterfall 与 Fetch Result Template

目标：

- 减少 provider fallback 编排和 result assembly 重复。
- 保持 provider 行为、warning/source-trail 诊断语义和 public artifact 输出稳定。

范围：

- Provider 行为保持不变。

完成项：

1. 新增 `src/paper_fetch/providers/_waterfall.py`，提供 `ProviderWaterfallStep`、`ProviderWaterfallState` 和 `run_provider_waterfall`，统一按 step 顺序执行、累积 warnings、保留失败 label、组合失败并写入 source markers。
2. Elsevier、Springer、BrowserWorkflow（Science / PNAS 的 HTML/browser PDF 路径）和 Wiley（HTML/TDM/browser PDF）已迁移到 waterfall runner；各 provider step 仍保留自己的 payload、warning 文案、错误映射和 `fulltext:*` source trail marker。
3. `ProviderClient.fetch_result` 已改为 hook-based template method，统一 raw payload、本地副本同步、asset 下载、warning/trace 合并、`to_article_model`、artifact 组装。
4. BrowserWorkflow 与 Springer 不再复制完整 `fetch_result` 尾部流程，只通过 hook 处理 abstract-only 后 PDF recovery、provider-managed abstract-only finalize 和 provider-specific asset warning。
5. Warning/source-trail 行为由 `tests/unit/test_provider_fetch_result_template.py`、`tests/unit/test_provider_waterfalls.py` 和 `tests/unit/test_science_pnas_provider.py` 锁定。

退出标准：

- Provider-specific class 不再复制完整 `fetch_result` routine：已完成。
- Warning/source-trail 行为有测试覆盖并保持稳定：已完成。

收尾验证：

```bash
pytest tests/unit/test_provider_fetch_result_template.py tests/unit/test_provider_waterfalls.py tests/unit/test_science_pnas_provider.py -q
pytest
```

风险：

- 中到高。Diagnostics 对用户排查问题很重要。

### Phase 6（已完成）：Runtime Context、Artifacts、Cache 边界

目标：

- 显式化 runtime dependencies 和文件输出策略。

范围：

- 引入新对象，同时保留旧函数签名兼容。

完成项：

1. 新增 `RuntimeContext`，集中持有 `env`、`transport`、`clients`、`download_dir`、`cancel_check`、`artifact_store` 和 MCP 可选 `fetch_cache`。
2. `service.fetch_paper()`、`service.probe_has_fulltext()`、`workflow.fulltext.fetch_article()`、`workflow.routing.probe_has_fulltext()` 均支持 `context=`；旧 `env`、`transport`、`clients`、`download_dir` keyword 保留，显式 keyword 覆盖 context。
3. 新增 `ArtifactStore` / `DownloadPolicy`，集中 provider PDF/binary local copy、Springer HTML `original.html` copy 和 asset warning/source-trail 诊断；保留既有 `download:*` marker 与 warning 文案。
4. `ProviderClient.fetch_result()` 增加可选 `artifact_store=`，旧 `output_dir` 位置参数保持兼容；未传 `artifact_store` 时按旧行为从 `output_dir` 构造默认 store。
5. 新增 `mcp.fetch_cache.FetchCache`，封装 fetch-envelope sidecar load/write、cache request match、revision 校验和 cache index refresh；保留 `_FETCH_ENVELOPE_CACHE_VERSION = 2`、`EXTRACTION_REVISION` 校验、sidecar shape、resource URI 与 scoped cache 行为。
6. `providers/html_assets.py` 不再临时改写 `extraction.html._assets` 全局函数；`download_figure_assets()` 显式传入 `cookie_opener_builder` 与 `opener_requester`，测试仍可 patch facade 上的兼容函数。
7. MCP async `fetch_paper` 使用 `RuntimeContext(cancel_check=...)` 创建 cancel-aware `HttpTransport`，progress/log bridge 行为保持不变。

退出标准：

- Workflow 不再直接拼写 provider payload / Springer HTML 输出路径，改由 `ArtifactStore` 管理。
- MCP `tools.py` 只保留 request validation、service 调用、tool result 组装和兼容 wrapper，fetch-envelope sidecar 逻辑下沉到 `FetchCache`。

风险：

- 中等。路径、resource URI、cache 兼容性是用户可见行为。

本阶段验证：

```bash
pytest tests/unit/test_service.py tests/unit/test_provider_fetch_result_template.py tests/unit/test_provider_request_options.py tests/unit/test_mcp.py -q
pytest tests/unit/test_cli.py tests/unit/test_provider_waterfalls.py tests/unit/test_science_pnas_provider.py -q
pytest
```

### Phase 7（已完成）：引入成熟 Package

目标：

- 在行为和模块边界已受保护后，减少自维护基础设施代码。

范围：

- 低风险基础设施替换；不重标定标题匹配、DOI routing 或图片资产语义。

完成项：

1. 新增 `platformdirs>=4,<5`，默认用户 config/data 目录改由 `user_config_path()` / `user_data_path()` 生成；继续保留 `PAPER_FETCH_DOWNLOAD_DIR` 优先、`XDG_DATA_HOME` 覆盖 data base、CLI 创建失败回退 `live-downloads` 的行为。
2. 新增 `python-dotenv>=1.2,<2`，用 `dotenv_values(..., interpolate=False)` 替换手写 `.env` parser；继续不隐式加载 repo-local `.env`，process/base env 最高优先级，bare key 跳过，空值保留。
3. 新增 `cachetools>=6,<7`，用 `TTLCache` 替换 `OrderedDict + expires_at` 的 HTTP GET 内存缓存；继续保留 textual-only、敏感 header/query 脱敏、TTL、entry capacity、单响应 body 上限和 total body bytes 上限。
4. 新增 `filelock>=3.20,<4`，用隐藏 `.paper-fetch-locks/` 下的 lock file 保护 MCP cache index read-modify-write 和 fetch-envelope sidecar 写入；继续保留 index JSON shape、fetch-envelope sidecar version、resource URI 和 scoped cache 行为。

退出标准：

- 每个新增依赖都有明确维护收益。
- 不为替换稳定领域逻辑而盲目新增 package。

风险：

- 单个 package 风险低到中，但依赖膨胀是真实成本。

本阶段验证：

```bash
pip install -e .[dev]
ruff check src tests
pytest tests/unit/test_config.py tests/unit/test_http_cache.py tests/unit/test_mcp.py -q
pytest
```

延后项：

- `rapidfuzz`：会影响标题匹配阈值，需要单独标定。
- `idutils`：会影响当前宽松 DOI/routing 行为，需要单独兼容评估。
- `filetype` + `imagesize` 或 `Pillow`：会改变图片类型/尺寸解析语义，需要结合资产 fixture 单独推进。

### Phase 8：移除 Legacy Surface 并完成架构收尾

目标：

- 在迁移稳定后移除兼容层。

任务：

1. 移除 legacy `RawFulltextPayload.metadata` magic-key ingestion，或限制在测试中。
2. 移除旧 provider-private helper 路径下的 compatibility wrappers。
3. 只有在无 public/test usage 时，移除 `SciencePnasClient` alias。
4. 删除 `_science_pnas_html.py` 未使用的重复常量和 dead wrappers。
5. 更新 architecture 文档和 import-boundary 测试，反映最终 layering。

退出标准：

- Provider-neutral modules 不依赖 provider-private modules。
- Provider catalog 是单一事实来源。
- Browser workflow 由 profile 驱动。
- Markdown 规则族各有单一 owner。
- 完整 unit/integration suite 通过。

## 建议执行顺序

推荐顺序：

1. Phase 0：测试安全护栏。
2. Phase 1：依赖边界迁移。
3. Phase 2：provider catalog。
4. Phase 3：browser workflow profile 清理。
5. Phase 4：Markdown 规则合并。
6. Phase 5：waterfall 和 fetch result template。
7. Phase 6：runtime/artifact/cache 边界。
8. Phase 7：成熟 package。
9. Phase 8：移除兼容层。

这个顺序能让风险最高的 Markdown 行为修改排在测试和模块边界更清晰之后。

## 不应放在同一个 PR 的高风险组合

除非必要，不要在同一个 PR 中混合以下改动：

- Provider routing catalog 修改 + Markdown extraction 修改。
- Availability assessment 修改 + PDF fallback waterfall 修改。
- Table renderer consolidation + figure link rewriting。
- Runtime context 修改 + MCP cache format 修改。
- DOI normalization 修改 + Crossref query scoring 修改。

## 最小首个 PR 建议

第一个小实现 PR 可以是：

1. 增加 import-boundary tests，记录目标依赖方向。
2. 将 `_html_citations`、`_html_semantics`、`_html_access_signals`、`_language_filter` 移到中立模块，并保留 compatibility re-export。
3. 更新 `models.py` 和 `extraction/html/_runtime.py` import。
4. 不改变行为。

选择它作为第一步的原因：

- 能降低架构耦合，同时不触碰 extraction algorithm。
- 后续 provider 和 Markdown refactor 更容易 review。
- 明确规则：共享 extraction/quality 代码不应位于 provider-private 命名空间。
