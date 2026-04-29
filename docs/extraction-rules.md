# 提取与渲染规则

修订日期：2026-04-28

这份文档解决：

- 当前主干必须维持的提取 / 组装 / 渲染行为约束有哪些
- 每条规则约束了什么用户可见结果
- 哪些真实 HTML / XML 样本和哪些测试在锁定这些规则

这份文档不解决：

- provider 路由、运行时限速、环境变量和部署细节
- 单次事故的时间线、排障过程或 root-cause 复盘全文
- 某篇 DOI 的特殊例外规则

provider 运行时行为见 [`providers.md`](providers.md)，系统分层与业务主线见 [`architecture/target-architecture.md`](architecture/target-architecture.md)。受控阶段到 canonical module 的映射见 [`target-architecture.md` 的 Extraction 阶段映射](architecture/target-architecture.md#extraction-stage-module-map)。

## 规则怎么读

- 这里说的“规则”，指当前主干必须维持的行为约束，不是某篇 DOI 的特判。
- DOI 可以出现在文档里，但只能作为“证据样本”和“测试样本”，不能变成规则本身。
- 每条规则都尽量先用通俗语言描述“约束了什么”，再补充它落在哪个阶段、由哪些样本和测试锁住。
- 本轮新增规则以 HTML 证据为主；个别渲染规则当前只有最小复现测试，没有额外 DOI 样本。

### 受控阶段清单

规则里的“对应阶段”只能使用或映射到这些阶段名，避免同一层行为出现多套说法：

- `metadata`：标题、作者、摘要、provider-owned 信号和 redirect stub lookup metadata。
- `provider-html-or-xml-extraction`：publisher HTML/XML 到中间结构的提取。
- `html-cleanup`：站点 chrome、UI 噪声、caption fallback 和正文清洗。
- `availability-quality`：fulltext / abstract-only 判定和正文充分性度量。
- `section-classification`：section kind、frontmatter、back matter、availability 与 section hints。
- `article-assembly`：中间结构合并成 `ArticleModel`。
- `asset-discovery`：figure、table、formula、supplementary 等资产候选识别。
- `asset-download`：资产候选下载和 provider-owned 下载链路。
- `asset-validation`：真实图片校验、尺寸阈值、preview acceptance 和失败诊断。
- `asset-link-rewrite`：远程 / 绝对资产链接改写为本地 Markdown 可用链接。
- `table-rendering`：HTML/XML 表格展平、降级和语义损失标记。
- `formula-rendering`：MathML / LaTeX / 公式图片 fallback 渲染。
- `markdown-normalization`：Markdown 块边界、空白、行内语义和去重。
- `references-rendering`：参考文献抽取与渲染。
- `final-rendering`：最终 Markdown / MCP payload 输出。
- `artifact-storage`：原始 payload、publisher HTML 和下载资产落盘。这里只允许保留重定向，具体规则归 [`providers.md`](providers.md)。

### 阶段流水图

```text
metadata
  -> provider-html-or-xml-extraction
  -> html-cleanup
  -> availability-quality
  -> section-classification
  -> article-assembly
  -> asset-discovery
  -> asset-download
  -> asset-validation
  -> asset-link-rewrite
  -> table-rendering / formula-rendering / references-rendering
  -> markdown-normalization
  -> final-rendering
```

`artifact-storage` 是旁路诊断与落盘阶段，不改变规则本身的用户可见提取 / 渲染语义。

### Owner 字段

- `Owner` 写维护这条行为的主要模块、profile 或数据模型；能写完整 dotted path 时必须写完整路径。
- 多模块共同维护时，写最小稳定边界，例如 `paper_fetch.extraction.html.figure_links + ArticleModel render_state`。
- 没有单一 owner 的旧规则可以写“跨模块，见对应测试”，但新增规则应优先给出 owner。
- owner 不是 public API 承诺；它是维护入口，帮助改代码时定位责任边界。

### Fixture 使用约定

- 代表性 HTML / XML 优先链接 `tests/fixtures/golden_criteria/` 下的真实 replay 样本。
- `tests/fixtures/block/` 只用于 access gate、paywall、abstract-only 等需要保留页面状态的 block fixture。
- `_scenarios/` 只能放最小结构场景；使用时必须说明它不是 DOI 级真实 replay，而是 contract scenario。
- 文档里直接链接的 fixture 必须位于 canonical fixture root，且文件必须存在；新增 fixture 后同步 manifest / catalog。

### 合并、退役和重定向

- 规则合并或拆分时不删除旧 anchor；旧 anchor 保留一个短条目，说明“已合并到”或“已拆分为”，并链接新规则。
- manifest 可以逐步迁移到新 anchor，但旧 anchor 必须继续可解析。
- 已迁出本文档职责范围的规则只保留重定向；实际行为规则放到对应文档。

### 维护工作流

1. 新增或改动用户可见提取 / 渲染行为时，先判断它属于现有规则、现有规则拆分，还是需要新规则；不要把单个 DOI 事故直接写成规则名。
2. 为规则补齐 `Owner：`、对应阶段、代表 fixture、owner 测试、边界说明；如果当前没有稳定 DOI 样本，必须进入“无稳定 DOI 样本规则汇总表”。
3. 长测试列表按 `Owner（generic/provider/models/cli）`、`Provider 覆盖`、`Service / live review 覆盖` 分组；只有一个测试函数锁住的规则，边界说明必须标注“测试覆盖度低”或等价风险。
4. 新增 provider 适用项时，同步更新对应 provider 的“共享规则另见”和“不适用 / 部分适用说明”。
5. 新增 canonical fixture 后，同步 `tests/fixtures/golden_criteria/manifest.json`、本文档的 fixture 反向索引，或“未直接挂规则 fixture 清单/用途说明”。
6. 修改文档后运行 `python3 scripts/validate_extraction_rules.py`，再按变更范围运行 integration / unit / lint。

### 新增规则 checklist

- 行为是否能用用户可见结果描述，而不是实现事故描述？
- `Owner：` 是否指向完整 dotted path 或明确的跨模块边界？
- 阶段是否来自“受控阶段清单”？
- 代表 fixture 是否来自 canonical root，或已进入“无稳定 DOI 样本规则汇总表”？
- 对应测试是否存在，且单测试规则是否标注覆盖风险？
- provider “共享规则另见”是否需要新增链接？
- fixture 反向索引或未挂规则清单是否已同步？
- `python3 scripts/validate_extraction_rules.py` 是否通过？

### 规则条目模板

- 规则名
  - 用行为级表述命名，不把 DOI 写进规则名。
- 通俗解释
  - 固定说明三件事：这条规则约束的是……；如果违反，用户会看到……；它对应的阶段是……。
- 代表性 HTML / XML
  - 优先列 repo 内稳定的真实样本，不展开 incident 复盘。
  - 如果当前只有最小复现测试，就直接写“当前无稳定 DOI 样本，直接见对应测试”，不要为了凑样本编造 DOI 级证据。
- 对应测试
  - 列出直接锁住该行为的 owner 测试；长列表用“Owner 测试”和“辅助覆盖测试”分组。
- 边界说明
  - 说明这条规则不约束什么，避免把样本现象误读成长期接口承诺。

### 无稳定 DOI 样本规则汇总表

| 规则 | 当前证据状态 | 后续补样本触发 | 下一步候选 fixture |
| --- | --- | --- | --- |
| [通用元数据边界](#rule-generic-metadata-boundaries) | 无 DOI 级 replay；已有 `_scenarios/generic_metadata_boundaries`。 | 出现真实 redirect stub 或站点 description 污染回归。 | redirect stub HTML，优先 Elsevier linkinghub / ScienceDirect 跳转页。 |
| [Provider 自有作者与摘要信号](#rule-provider-owned-authors) | DOM abstract 恢复首段分支无 DOI 级 replay；已有 `_scenarios/provider_dom_abstract_fallback`。 | 某 provider 的 DOM abstract fallback 需要 replay 锁定。 | 缺 datalayer / schema.org 但 DOM abstract 可恢复的 provider HTML。 |
| [图片和公式图片本地链接改写](#rule-rewrite-inline-figure-links) | 跨阶段链路无单一 DOI replay；已有 `_scenarios/inline_figure_link_rewrite`。 | 有完整“远程图 -> 下载资产 -> 相对 Markdown 链接”回放样本。 | 带 `body_assets/` 下载产物和原始远程图 URL 的完整 replay。 |
| [下载资产诊断字段](#rule-asset-download-diagnostic-fields) | 无 DOI 级 replay；已有 `_scenarios/asset_download_diagnostics`。 | 某 provider 诊断字段在真实回放中丢失。 | 含 accepted preview、失败 snippet 和 content type 的 provider asset replay。 |
| [表格展平或列表降级](#rule-table-flatten-or-list) | 共享 table helper 无 DOI 级 replay；已有 `_scenarios/table_flatten_or_list`。 | 新增 publisher 真实复杂表 replay。 | 非 Elsevier / Springer 的 rowspan、colspan 或无法展平 table HTML。 |
| [Availability 不计入正文充分性](#rule-availability-excluded-from-body-metrics) | 无单一样本覆盖全部 body metrics 分支；已有 `_scenarios/availability_body_metrics`。 | 真实页面只含 availability 却被误判全文。 | 只含 Data / Code Availability、正文为空或极短的 HTML replay。 |
| [Section hint 适配 availability](#rule-section-hints-normalize-availability) | dict/dataclass/order coercion 已有 `_scenarios/section_hints_availability`。 | 真实 section hints 顺序或形态回归。 | provider extraction 产出非 literal heading 但带 section hint 的 replay。 |
| [LaTeX normalization](#rule-formula-latex-normalization) | normalize 分支无 DOI 级 replay；已有 `_scenarios/formula_latex_normalization`。 | 真实 MathML 转换产出新 KaTeX 不兼容宏。 | 包含 publisher-specific MathML 宏或 mtext 转义的 XML / HTML。 |

## Generic

- 这里的 `Generic` 指跨 provider 共享的提取 / 渲染规则。
- 它现在只表示 shared extraction logic，不再表示可被路由命中的第六条 provider 或 public source。

<a id="rule-keep-semantic-parent-heading"></a>
### 保留语义父节标题

- 这条规则约束的是：只要 HTML 提取链已经识别出一个父节标题，后续的文章组装和最终 markdown 渲染就不能把这个父节标题吃掉，即使正文内容主要落在子节里。
- 如果违反，用户会看到：正文里直接从子节开始，像是 `Experimental design` 这样的内容突然失去上级章节，文档结构会断层。
- 它对应的阶段是：`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.models.ArticleModel` 与 provider section assembly。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/original.html`](../tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/original.html)
  - 这个样本能证明 `MATERIALS AND METHODS` 是语义父节，而 `Experimental design` 是其子节内容。
- 对应测试：
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_science_provider_replay_for_adl6155_keeps_materials_and_methods_wrapper_heading`
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_wiley_full_fixture_extracts_body_sections_from_real_html`
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_wiley_real_fixture_keeps_methods_subcontent_in_body`
  - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_preserves_empty_body_parent_headings`
- 边界说明：
  - 这条规则不是要求所有论文都必须出现 `MATERIALS AND METHODS` 这个固定字面值。
  - 它约束的是“父节语义不能在组装或渲染阶段丢失”，不是要求不同 publisher 的标题体系完全一致。
  - 当前直接 DOI 证据样本来自 Science；Wiley 与 models 测试证明同一父节保留行为不是 Science-specific 规则，后续不为凑数强行新增 fixture。

<a id="rule-no-trailing-figures-appendix"></a>
### 正文已内联 figure 时不再重复追加尾部 Figures 附录

- 这条规则约束的是：当 figure 已经以正文内联形式进入最终输出时，`asset_profile='body'` / `asset_profile='all'` 的正文图渲染不能再在文末重复拼一个尾部 `## Figures` 附录。
- 如果违反，用户会看到：正文已经出现过的 figure 在文末又来一遍，像是“正文 + 附录”重复渲染，结构和阅读顺序都会变差。
- 它对应的阶段是：`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.models.ArticleModel` render state。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1029_2004gb002273/original.html`](../tests/fixtures/golden_criteria/10.1029_2004gb002273/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_nature13376/original.html`](../tests/fixtures/golden_criteria/10.1038_nature13376/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_s41561-022-00983-6/original.html`](../tests/fixtures/golden_criteria/10.1038_s41561-022-00983-6/original.html)
  - [`../tests/fixtures/golden_criteria/10.1126_sciadv.aax6869/original.html`](../tests/fixtures/golden_criteria/10.1126_sciadv.aax6869/original.html)
  - [`../tests/fixtures/golden_criteria/10.1126_science.abb3021/original.html`](../tests/fixtures/golden_criteria/10.1126_science.abb3021/original.html)
  - 这些样本分别覆盖 Wiley root-cause 回放、旧 Nature HTML、新 Nature HTML，以及 Science live review 中“正文已有相对本地图片链接但资产模型里仍是绝对路径”的场景。
- 对应测试：
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_wiley_provider_replay_for_2004gb002273_body_assets_avoid_trailing_figures_noise`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_old_nature_downloaded_body_figures_inline_without_trailing_figures_block`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_new_nature_downloaded_body_figures_inline_without_trailing_figures_block`
  - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_to_ai_markdown_suppresses_trailing_figures_for_body_figures_already_inline`
  - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_to_ai_markdown_suppresses_trailing_figures_for_inline_relative_asset_suffix`
- 边界说明：
  - 这条规则只约束 `asset_profile='body'` / `asset_profile='all'` 的正文图渲染结果。
  - 它不是说系统永远不能输出 figure 附录，而是说正文 figure 已经内联时，不能再重复追加一个用户可见的尾部 Figures 块。
  - 如果正文里还有未锚定的 body figure，或者资产本来就不属于正文，这些内容仍然可以留在兜底附录里。
  - 去重比较必须能识别远程 URL、绝对路径、相对 `body_assets/...` 路径和 basename 后缀的等价关系；不能只做字符串全等比较。

<a id="rule-filter-publisher-ui-noise"></a>
### 出版社站点 UI 噪声不能泄漏进最终 markdown

- 这条规则约束的是：出版社页面里的操作按钮、图窗入口、站点工具栏和明显的站点动作词，不能随着 HTML 提取或后处理一起混进最终 markdown；`Permissions`、`Rights and permissions`、`Open Access` 这类站点许可 / 操作节只能按 heading 或 section 结构过滤，不能扩成普通正文词面 denylist。
- 如果违反，用户会看到：正文里夹杂 `Open in figure viewer`、`PowerPoint`、`Sign up for PNAS alerts`、`Request permissions`、Creative Commons 许可长文这类站点操作文案，看起来像把网页操作层一起抓进来了。
- 它对应的阶段是：`html-cleanup`、`markdown-normalization`、`asset-validation`、`final-rendering`。
- Owner：`paper_fetch.providers.html_noise` 与 provider-specific cleanup profile。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1029_2004gb002273/original.html`](../tests/fixtures/golden_criteria/10.1029_2004gb002273/original.html)
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html)
  - 这两个样本分别覆盖 figure viewer / PowerPoint 噪声和 PNAS 站点级 collateral 噪声。
- 对应测试：
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_science_fixture_markdown_omits_frontmatter_and_collateral_noise`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_wiley_provider_replay_for_2004gb002273_body_assets_avoid_trailing_figures_noise`
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_wiley_full_fixture_omits_real_page_collateral_noise`
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_pnas_full_fixture_omits_real_page_collateral_noise`
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_wiley_real_fixture_filters_frontmatter_and_viewer_noise`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_pnas_provider_keeps_frontmatter_once_and_filters_collateral_noise_in_final_render`
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_real_nature_fixture_keeps_source_data_without_chrome_sections`
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_science_real_fixture_does_not_leak_competing_interests_modal`
- 边界说明：
  - 这条规则过滤的是站点 UI 和操作噪声，不是过滤所有出现在图题或正文里的英文短语。
  - `download` 不是全局噪声词；`Source Data Fig. 1 (Download xlsx)`、supplementary file、figure/table asset download 这类有效材料入口必须保留。
  - `preview sentence` 和 AI alt disclaimer 也会被过滤，但它们属于 [Springer 访问提示规则](#rule-springer-access-hint-disclaimer)，不混在本条里定义。
  - 如果某段文本本来就是论文内容的一部分，即使它看起来像按钮词，也不能仅凭字面值删除。

<a id="rule-generic-metadata-boundaries"></a>
### 通用元数据抽取不能把站点描述误当摘要，也不能丢掉 redirect stub 的 lookup title

- 这条规则约束的是：通用 HTML metadata 抽取只能把真正的论文元数据写进文章模型，不能把站点级 description、标题回显或 redirect stub chrome 误当成摘要；如果页面只是 redirect stub，但里面确实带着可靠 lookup title，也要保留下来供后续解析链使用。
- 如果违反，用户会看到：标题被重复当成摘要、摘要字段被站点 description 污染，或者 Elsevier redirect stub 只剩 `Redirecting`，导致后续抓取与展示退化。
- 它对应的阶段是：`metadata`、`html-cleanup`。
- Owner：`paper_fetch.extraction.html._metadata`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/_scenarios/generic_metadata_boundaries/generic_description.html`](../tests/fixtures/golden_criteria/_scenarios/generic_metadata_boundaries/generic_description.html)
  - [`../tests/fixtures/golden_criteria/_scenarios/generic_metadata_boundaries/redirect_stub.html`](../tests/fixtures/golden_criteria/_scenarios/generic_metadata_boundaries/redirect_stub.html)
  - `_scenarios/generic_metadata_boundaries` 是 metadata contract scenario，不是 DOI 级真实 replay。
- 对应测试：
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_parse_html_metadata_does_not_treat_generic_description_as_abstract`
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_parse_html_metadata_uses_redirect_stub_lookup_title`
- 边界说明：
  - 这条规则不是承诺所有 publisher 的隐藏字段或脚本变量都会被完整解析。
  - 它只约束“不要制造假摘要、不要丢掉后续解析必需的 lookup title”。

<a id="rule-html-availability-contract"></a>
### HTML fulltext / abstract-only 判定必须和用户可见访问状态一致

- 这条规则约束的是：availability 判定必须把真正可读的正文 HTML 识别成 fulltext，同时把 access gate、abstract-only 页面和带登录 chrome 的摘要页识别成 abstract-only；不能因为站点噪声、机构登录提示或 ancillary sections 把结果判反。
- 如果违反，用户会看到：明明只有摘要的页面被当成全文返回，或者本来有正文的页面被误降级成 abstract-only，直接影响最终内容类型和 fallback 行为。
- 它对应的阶段是：`availability-quality`、`article-assembly`。
- Owner：`paper_fetch.quality.html_availability`；HTML container 评分、选择、清理的架构边界见 [architecture/target-architecture.md 的 Extraction 层](architecture/target-architecture.md#6-extraction-层)。
- 代表性 HTML / XML：
  - [`../tests/fixtures/block/10.1126_science.aeg3511/raw.html`](../tests/fixtures/block/10.1126_science.aeg3511/raw.html)
  - [`../tests/fixtures/golden_criteria/10.1126_science.aeg3511/original.html`](../tests/fixtures/golden_criteria/10.1126_science.aeg3511/original.html)
  - [`../tests/fixtures/block/10.1111_gcb.16414/raw.html`](../tests/fixtures/block/10.1111_gcb.16414/raw.html)
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html)
  - [`../tests/fixtures/block/10.1073_pnas.2509692123/raw.html`](../tests/fixtures/block/10.1073_pnas.2509692123/raw.html)
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html)
  - [`../tests/fixtures/block/10.1007_s00382-018-4286-0/raw.html`](../tests/fixtures/block/10.1007_s00382-018-4286-0/raw.html)
  - 这些样本分别覆盖 Science、Wiley、PNAS 和 Springer 的 paywall / entitled 对照场景。
- 对应测试：
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_pnas_abstract_fixture_is_rejected`
  - [`../tests/unit/test_html_availability.py`](../tests/unit/test_html_availability.py) 中的 `test_assess_html_rejects_science_paywall_sample_with_abstract`
  - [`../tests/unit/test_html_availability.py`](../tests/unit/test_html_availability.py) 中的 `test_assess_html_accepts_science_entitled_fulltext_fixture`
  - [`../tests/unit/test_html_availability.py`](../tests/unit/test_html_availability.py) 中的 `test_assess_html_rejects_springer_paywall_samples_without_promoting_ancillary_sections`
  - [`../tests/unit/test_html_availability.py`](../tests/unit/test_html_availability.py) 中的 `test_assess_html_rejects_wiley_paywall_metadata_with_abstract`
  - [`../tests/unit/test_html_availability.py`](../tests/unit/test_html_availability.py) 中的 `test_assess_html_accepts_wiley_fulltext_fixture_despite_login_chrome`
  - [`../tests/unit/test_html_availability.py`](../tests/unit/test_html_availability.py) 中的 `test_assess_html_rejects_pnas_paywall_metadata_with_abstract`
  - [`../tests/unit/test_html_availability.py`](../tests/unit/test_html_availability.py) 中的 `test_assess_html_accepts_pnas_fulltext_fixture_despite_institutional_login_chrome`
- 边界说明：
  - 这条规则不约束 provider 路由、PDF fallback 编排或 live 网络重试。
  - 它只约束“用户实际可见的 HTML 内容类型判定不能错位”。

<a id="rule-provider-owned-authors"></a>
### Provider 自有作者与摘要信号必须进入最终文章元数据

- 这条规则约束的是：publisher 自己暴露的作者与摘要信号，一旦已经被识别出来，就要稳定进入最终文章模型；优先使用更结构化的 provider-owned 信号，缺失时再回退到 DOM。
- 如果违反，用户会看到：作者列表为空、摘要字段丢失，或者 provider 已经识别出的摘要没有写入文章模型。
- 它对应的阶段是：`metadata`、`provider-html-or-xml-extraction`、`article-assembly`。
- Owner：`paper_fetch.providers._article_markdown_elsevier` 与 `paper_fetch.providers._browser_workflow_authors`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_science.adp0212/original.html`](../tests/fixtures/golden_criteria/10.1126_science.adp0212/original.html)
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html)
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html)
  - [`../tests/fixtures/golden_criteria/_scenarios/elsevier_author_groups_minimal/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_author_groups_minimal/original.xml)
  - [`../tests/fixtures/golden_criteria/_scenarios/provider_dom_abstract_fallback/payload.json`](../tests/fixtures/golden_criteria/_scenarios/provider_dom_abstract_fallback/payload.json)
  - `_scenarios/elsevier_author_groups_minimal` 是最小 contract scenario，不是 DOI 级真实 replay，用于锁住 Elsevier author groups 结构。
  - `_scenarios/provider_dom_abstract_fallback` 锁住“DOM abstract 恢复正文首段”分支；它不是 DOI 级真实 replay。
- 对应测试：
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_build_article_structure_extracts_authors_from_author_groups`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_science_provider_uses_extracted_dom_abstract_and_restores_lead_body_text`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_provider_owned_html_signals_populate_final_article_authors`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_science_provider_falls_back_to_dom_authors_when_datalayer_is_missing`
- 边界说明：
  - 这条规则不是要求所有 provider 都必须有统一的作者源字段。
  - 它约束的是“已识别的 provider-owned 元数据要稳定进入最终模型”，不是要求不存在的作者信息凭空生成。
  - 摘要重复去重不归本规则约束；前言摘要族顺序与去重见 [前言摘要族的顺序与去重必须稳定](#rule-stable-frontmatter-order)。

<a id="rule-preserve-subscripts-in-headings"></a>
### 已合并：标题和节标题里的上下标不能被打平成普通文本

> 已合并到 [正文、标题和表格里的行内语义格式不能被打平或拆裂](#rule-preserve-inline-semantics-in-body-and-tables)。

旧 anchor 保留用于 manifest、历史链接和外部引用。标题、节标题、frontmatter、正文、caption 和 table cell 中的 `sub` / `sup` 现在统一由同一条 inline semantics 规则约束。

<a id="rule-rewrite-inline-figure-links"></a>
### 已下载的正文图片和公式图片要改写成正文附近的本地链接

- 这条规则约束的是：正文里已经有 figure、table image 或 formula image 锚点时，最终 markdown 应该尽量把远程图链接或绝对本地路径改写成当前 markdown 文件可用的本地资源链接，而且图和图之间不能误绑；改写后还要重新规范 Markdown 图片块边界，不能让图片和标题、正文句子或公式围栏粘在一起。
- 如果违反，用户会看到：图片链接还是远程 URL、还是绝对路径、图 4 的本地资源被错绑到图 1 的 caption 上，或者出现 `Heading![Figure]`、`text.![Formula]` 这类坏 Markdown。
- 它对应的阶段是：`asset-link-rewrite`、`article-assembly`、`markdown-normalization`、`final-rendering`。
- Owner：`paper_fetch.extraction.html.figure_links`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/_scenarios/inline_figure_link_rewrite/article.md`](../tests/fixtures/golden_criteria/_scenarios/inline_figure_link_rewrite/article.md)
  - [`../tests/fixtures/golden_criteria/_scenarios/inline_figure_link_rewrite/assets.json`](../tests/fixtures/golden_criteria/_scenarios/inline_figure_link_rewrite/assets.json)
  - `_scenarios/inline_figure_link_rewrite` 覆盖“远程图 -> 已下载本地资源 -> 本地 Markdown 链接 -> 交叉引用不误绑”的 shared contract；它不是 DOI 级真实 replay。
- 对应测试：
  - Owner（generic）：
    - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_rewrite_inline_figure_links_prefers_local_paths_for_existing_science_image_blocks`
    - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_rewrite_inline_figure_links_is_data_driven_for_non_legacy_publisher`
    - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_rewrite_inline_figure_links_ignores_cross_references_in_asset_captions`
    - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_figure_link_injection_and_rewrite_share_path_preference`
  - Provider 覆盖：
    - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_science_provider_rewrites_inline_figure_links_to_downloaded_local_assets`
  - CLI / models 覆盖：
    - [`../tests/unit/test_cli.py`](../tests/unit/test_cli.py) 中的 `test_save_markdown_to_disk_rewrites_local_asset_links_relative_to_saved_file`
    - [`../tests/unit/test_cli.py`](../tests/unit/test_cli.py) 中的 `test_rewrite_markdown_asset_links_maps_remote_figure_urls_to_downloaded_local_assets`
    - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_rewrites_inline_asset_urls_to_downloaded_paths`
    - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_normalizes_after_inline_asset_url_rewrite`
    - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_normalize_markdown_text_separates_adjacent_block_images`
    - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_to_ai_markdown_separates_adjacent_section_images_after_asset_rewrites`
- 边界说明：
  - 这条规则只改写 Markdown 链接目标，不会去改普通正文里的纯文本路径。
  - 只有当系统手里确实有可用的本地资产时，才应该把链接改写成对应本地路径。

<a id="rule-image-download-tier-diagnostics"></a>
### 已拆分：图片下载必须验证真实图片、保留 tier 和尺寸诊断

> 已拆分为 [图片下载必须验证真实图片内容](#rule-image-download-validates-real-images)、[下载资产必须保留诊断字段](#rule-asset-download-diagnostic-fields) 和 [浏览器工作流图片下载必须使用 shared browser context 主链路](#rule-browser-primary-image-download-path)。

旧 anchor 保留用于 manifest、历史链接和外部引用。新规则分别约束真实性校验、诊断字段和 provider-owned 浏览器主链路。

<a id="rule-image-download-validates-real-images"></a>
### 图片下载必须验证真实图片内容

- 这条规则约束的是：正文图片下载不能把 Cloudflare challenge HTML、Chrome 图片查看器壳或过小的站点图标当成论文图片保存；preview 图只有尺寸达标并在 source trail 中标记为 accepted 时才能作为可接受降级。
- 如果违反，用户会看到：正文缺图，或本地图片文件其实是 HTML / 站点图标，后续渲染和 live review 都无法解释失败原因。
- 它对应的阶段是：`asset-download`、`asset-validation`、`availability-quality`。
- Owner：`paper_fetch.providers.html_assets` 与 `paper_fetch.providers._browser_workflow_fetchers`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html)
  - [`../tests/fixtures/golden_criteria/10.1126_sciadv.aax6869/original.html`](../tests/fixtures/golden_criteria/10.1126_sciadv.aax6869/original.html)
  - [`../tests/fixtures/golden_criteria/10.1126_science.abb3021/original.html`](../tests/fixtures/golden_criteria/10.1126_science.abb3021/original.html)
  - 这些样本覆盖 PNAS / Science CMS 图片直接 HTTP 请求被 challenge 或只能拿到站点标记为 preview 的图片时，如何区分真实故障和可接受降级。
- 对应测试：
  - Owner（provider）：
    - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_science_provider_records_preview_dimensions_and_acceptance`
    - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_science_provider_records_asset_failure_when_shared_playwright_preview_fails`
  - Service / live review 覆盖：
    - [`../tests/unit/test_service.py`](../tests/unit/test_service.py) 中的 `test_fetch_paper_accepts_preview_images_with_sufficient_dimensions`
    - [`../tests/unit/test_golden_criteria_live.py`](../tests/unit/test_golden_criteria_live.py) 中的 `test_science_preview_accepted_is_not_an_asset_issue`
    - [`../tests/unit/test_golden_criteria_live.py`](../tests/unit/test_golden_criteria_live.py) 中的 `test_formula_only_preview_fallback_is_not_an_asset_issue`
    - [`../tests/unit/test_golden_criteria_live.py`](../tests/unit/test_golden_criteria_live.py) 中的 `test_non_formula_preview_fallback_remains_an_asset_issue`
- 边界说明：
  - `download_tier="preview"` 不是天然错误；当下载阶段判定 preview 尺寸满足阈值，并在 source trail 中记录 `download:*_assets_preview_accepted` 时，它是诊断标签，不应自动映射为 `asset_download_failure`。
  - formula-only preview fallback 是公式图片语义的降级呈现，不自动归为 `asset_download_failure`；figure/table preview fallback 仍按资产问题处理，除非已有 accepted 诊断。

<a id="rule-asset-download-diagnostic-fields"></a>
### 下载资产必须保留诊断字段

- 这条规则约束的是：成功或失败的资产下载都要保留足够诊断信息；成功图片记录 `download_tier`、下载 URL、content type、字节数和尺寸，失败资产保留 status、content type、snippet、reason 和 recovery 轨迹。
- 如果违反，用户会看到：live review 只能笼统报 `asset_download_failure`，看不出是 full-size 被拦截、preview 可接受、supplementary 失败，还是图片真的缺失。
- 它对应的阶段是：`asset-validation`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.models.Asset` / `paper_fetch.models.Quality` 与 `paper_fetch.mcp.schemas`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/_scenarios/asset_download_diagnostics/article_payload.json`](../tests/fixtures/golden_criteria/_scenarios/asset_download_diagnostics/article_payload.json)
  - `_scenarios/asset_download_diagnostics` 锁住 MCP / model payload 的成功下载诊断字段；它不是 DOI 级真实 replay。
- 对应测试：
  - Owner（models / MCP）：
    - [`../tests/unit/test_mcp.py`](../tests/unit/test_mcp.py) 中的 `test_article_payload_preserves_asset_download_diagnostics`
  - Provider 覆盖：
    - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_browser_workflow_download_related_assets_retries_after_partial_failures`
    - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_browser_workflow_retries_only_failed_supplementary_assets`
    - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_browser_workflow_retries_only_failed_body_assets`
    - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_science_provider_records_asset_failure_when_shared_playwright_preview_fails`
- 边界说明：
  - 本规则只要求诊断字段不丢失，不要求所有 provider 使用同一种远端下载实现。
  - 诊断字段不能替代用户可见内容；caption、占位和 warnings 仍由渲染规则决定。

<a id="rule-browser-primary-image-download-path"></a>
### 浏览器工作流图片下载必须使用 shared browser context 主链路

- 这条规则约束的是：使用 browser workflow 的 provider 在下载正文 figure / table / formula 图片时，必须以 shared browser context 作为主链路；每次 download attempt 只创建一次 context/page，多图复用，preview fallback 也通过同一个 context 获取。
- 如果违反，用户会看到：目标站点明明在浏览器会话里可见图片，系统却因为普通 HTTP challenge 或重复 context 冷启动而稳定缺图。
- 它对应的阶段是：`asset-download`、`asset-validation`。
- Owner：`paper_fetch.providers._browser_workflow_fetchers`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html)
- 对应测试：
  - Owner（provider）：
    - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_pnas_provider_download_related_assets_uses_shared_playwright_primary_path_before_preview`
    - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_pnas_provider_downloads_preview_through_shared_playwright_when_no_full_size_candidate`
    - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_wiley_provider_download_related_assets_uses_shared_playwright_primary_path`
    - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_wiley_provider_download_related_assets_reuses_shared_playwright_fetcher_across_assets`
- 边界说明：
  - 这条规则目前适用于 `wiley`、`science`、`pnas` 的 browser workflow HTML 成功路径。
  - 它不改变 `elsevier` XML、`springer` direct HTML 或 PDF fallback 的下载语义。

<a id="rule-table-flatten-or-list"></a>
### 表格能展平就转 Markdown 表，展不平就退成可读列表

- 这条规则约束的是：表格如果只是多级表头、rowspan 这类还能讲清楚结构的复杂度，就要尽量展平成 Markdown 表；如果结构已经复杂到强行展平会误导，就退成清晰的列表说明。
- 如果违反，用户会看到：要么本来能读懂的表被糟糕地压扁成错列的 Markdown 表，要么复杂表直接丢信息，没有任何可读 fallback。
- 它对应的阶段是：`table-rendering`、`markdown-normalization`。
- Owner：`paper_fetch.extraction.html.tables`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/_scenarios/table_flatten_or_list/complex_table.html`](../tests/fixtures/golden_criteria/_scenarios/table_flatten_or_list/complex_table.html)
  - `_scenarios/table_flatten_or_list` 锁住无法安全展平时的列表降级；它不是 DOI 级真实 replay。
- 对应测试：
  - [`../tests/unit/test_science_pnas_postprocess_units.py`](../tests/unit/test_science_pnas_postprocess_units.py) 中的 `test_extract_science_pnas_markdown_flattens_multilevel_table_headers`
  - [`../tests/unit/test_science_pnas_postprocess_units.py`](../tests/unit/test_science_pnas_postprocess_units.py) 中的 `test_extract_science_pnas_markdown_flattens_rowspan_table_body_cells`
  - [`../tests/unit/test_science_pnas_postprocess_units.py`](../tests/unit/test_science_pnas_postprocess_units.py) 中的 `test_extract_science_pnas_markdown_falls_back_complex_table_to_bullets`
- 边界说明：
  - 这条规则不是要求所有表格最终都必须长成 Markdown 表。
  - 当结构已经超出安全展平范围时，退成列表是符合规则的正确结果，不是降级失败。
  - 共享 table helper 的唯一维护入口是 `paper_fetch.extraction.html.tables`；不得在 provider 层新增 `_html_tables` 兼容 re-export。

<a id="rule-stable-frontmatter-order"></a>
### 前言摘要族的顺序与去重必须稳定

- 这条规则约束的是：teaser、`Significance`、`Structured Abstract`、`Abstract` 这类前言摘要块一旦已经被识别出来，就必须在最终 markdown 里按阅读顺序稳定出现，不能重复注回正文；只有在确实需要把前言和正文切开时，才插入一次 `## Main Text`。
- 如果违反，用户会看到：同一段摘要在前言和正文里各出现一遍，或者 `Significance`、`Structured Abstract`、`Abstract` 顺序错乱，甚至正文开头被摘要块挤占。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`markdown-normalization`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.providers._science_pnas_postprocess` 与 `paper_fetch.models.ArticleModel`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_science.abp8622/original.html`](../tests/fixtures/golden_criteria/10.1126_science.abp8622/original.html)
  - 这个样本能证明 Science frontmatter 里的 teaser、`Structured Abstract`、`Abstract` 和正文边界需要稳定保留。
- 对应测试：
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_science_browser_workflow_does_not_reinject_teaser_before_structured_abstract`
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_science_real_frontmatter_fixture_preserves_structured_summaries_and_main_text`
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_pnas_real_fixture_keeps_significance_and_abstract_before_main_text`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_science_provider_keeps_frontmatter_sections_but_only_one_abstract_in_final_article`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_wiley_provider_deduplicates_near_matching_abstract_in_final_article_render`
  - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_splits_leading_inline_abstract_from_main_text`
  - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_does_not_duplicate_explicit_abstract_when_section_hints_are_present`
- 边界说明：
  - 这条规则不是要求所有文章都必须同时出现 teaser、`Significance`、`Structured Abstract` 和 `Abstract`。
  - 它约束的是“已识别前言块的顺序、去重和正文边界”，不是要求每个 publisher 都使用同一套标题名称。

<a id="rule-keep-parallel-multilingual-abstracts"></a>
### 并行多语言摘要要并存，单语非英文正文不能被误删

- 这条规则约束的是：如果页面或 XML 里明确存在并行的多语言摘要块，就要把它们都保留下来；如果只有单语的非英文摘要或正文，也必须原样保留，不能因为语言过滤把整篇文章删空。
- 如果违反，用户会看到：双语摘要只剩一种语言，或者葡萄牙语、西班牙语这类非英文正文整块消失，看起来像抓取失败。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`markdown-normalization`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.extraction.html.language` 与 provider abstract extraction adapters（`paper_fetch.providers._science_pnas_html` / `paper_fetch.providers._article_markdown_xml`）。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.16386/bilingual.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16386/bilingual.html)
  - [`../tests/fixtures/golden_criteria/10.1007_s13158-025-00473-x/bilingual.html`](../tests/fixtures/golden_criteria/10.1007_s13158-025-00473-x/bilingual.html)
  - [`../tests/fixtures/golden_criteria/10.1016_S1575-1813(18)30261-4/bilingual.xml`](<../tests/fixtures/golden_criteria/10.1016_S1575-1813(18)30261-4/bilingual.xml>)
  - 这些样本覆盖 Wiley、Springer 和 Elsevier 的稳定双语摘要场景；其他 provider 的并行摘要直接见对应测试。
- 对应测试：
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_wiley_multilingual_abstract_keeps_parallel_abstract_sections`
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_browser_workflow_preserves_parallel_multilingual_abstract_sections`
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_browser_workflow_keeps_non_english_article_when_no_parallel_language_variant_exists`
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_xml_multilingual_abstract_preserves_parallel_abstract_sections`
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_xml_non_english_only_article_is_preserved`
  - [`../tests/unit/test_regression_samples.py`](../tests/unit/test_regression_samples.py) 中的 `test_wiley_bilingual_fixture_preserves_parallel_abstract_sections`
  - [`../tests/unit/test_regression_samples.py`](../tests/unit/test_regression_samples.py) 中的 `test_springer_bilingual_fixture_preserves_parallel_abstract_sections`
  - [`../tests/unit/test_regression_samples.py`](../tests/unit/test_regression_samples.py) 中的 `test_elsevier_bilingual_fixture_preserves_parallel_abstract_sections`
  - [`../tests/unit/test_regression_samples.py`](../tests/unit/test_regression_samples.py) 中的 `test_sage_bilingual_fixture_preserves_parallel_abstract_sections`
  - [`../tests/unit/test_regression_samples.py`](../tests/unit/test_regression_samples.py) 中的 `test_tandf_bilingual_fixture_preserves_parallel_abstract_sections`
  - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_preserves_explicit_multilingual_abstract_sections`
- 边界说明：
  - 这条规则只约束结构上已经能识别为并行语言变体的块，不承诺自动识别所有翻译关系。
  - 它也不是说站点里的所有语言切换器、导航文案或重复 chrome 文本都要保留。

<a id="rule-keep-data-availability-once"></a>
### Data / Code Availability 必须保留且不能重复

- 这条规则约束的是：`Data Availability`、`Code Availability`、`Software Availability`、`Data, Materials, and Software Availability` 这类内容一旦被识别为 availability 声明，就必须作为独立结构节保留下来，而且最终输出里只能出现一次；它不能被误删、降成普通正文，也不能被 back matter 重复拼接。
- 如果违反，用户会看到：数据或代码可用性声明完全消失，或者同一节在正文和附录里各来一遍。
- 它对应的阶段是：`section-classification`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.extraction.section_hints` 与 `paper_fetch.models.ArticleModel` retained non-body section 渲染。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html)
  - 这个样本能证明 PNAS 的 `Data, Materials, and Software Availability` 需要单独保留且不能重复。
  - [`../tests/fixtures/golden_criteria/10.1038_s43247-024-01885-8/original.html`](../tests/fixtures/golden_criteria/10.1038_s43247-024-01885-8/original.html)
  - 这个样本能证明 Springer / Nature HTML 里的 `Data availability` 与 `Code availability` 都需要从正文外 back matter 补回。
- 对应测试：
  - Owner（provider）：
    - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_science_fixture_keeps_data_availability_but_filters_teaser_figure`
    - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_pnas_full_fixture_keeps_data_availability_and_renders_table_markdown`
    - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_pnas_collateral_data_availability_fixture_is_not_duplicated`
    - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_nature_fixture_keeps_data_and_code_availability_sections`
    - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_wiley_full_fixture_keeps_data_availability_but_filters_other_back_matter`
- 边界说明：
  - 这条规则不是要求所有 back matter 都必须保留；`Acknowledgements`、`Research Funding`、`Statement of Competing Interests`、`Electronic Supplementary Material` 这类结构标题会归入 back matter / supplementary 语义，不计入正文充分性。`Permissions` 和 `Open Access` 归入 auxiliary / chrome，见 [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)。
  - 它只约束“已经被识别成 data/code availability 的内容”；如果上游只剩普通标题文本且没有结构信号，仍可能先按一般正文节处理。

<a id="rule-availability-section-kind-mapping"></a>
### Availability 标题必须映射到稳定 section kind

- 这条规则约束的是：纯 `Data Availability` 归类为 `data_availability`；纯 `Code Availability` / `Software Availability` 归类为 `code_availability`；混合标题如 `Data, code, and materials availability` 和 `Data, Materials, and Software Availability` 仍归类为 `data_availability`，内容完整保留。
- 如果违反，用户会看到：同一类 availability 声明在不同 provider 下变成不稳定标题，或者 mixed availability 被错误拆分 / 丢失。
- 它对应的阶段是：`section-classification`、`article-assembly`。
- Owner：`paper_fetch.extraction.section_hints`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.rse.2025.114648/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.rse.2025.114648/original.xml)
  - 这个样本能证明 Elsevier XML 的 `ce:data-availability` 与普通 `Code availability` section 都需要归入共享 availability kind。
- 对应测试：
  - Owner（generic / provider）：
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_golden_fixture_classifies_data_and_code_availability_sections`
    - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_browser_workflow_returns_section_hints_for_structural_data_availability`
    - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_browser_workflow_returns_section_hints_for_structural_code_availability`
- 边界说明：
  - 本规则只约束 availability 类标题的 kind 映射，不决定这些节是否计入正文充分性；body metrics 见 [Availability 不计入正文充分性度量](#rule-availability-excluded-from-body-metrics)。

<a id="rule-availability-excluded-from-body-metrics"></a>
### Availability 不计入正文充分性度量

- 这条规则约束的是：`data_availability` 和 `code_availability` 都不计入正文充分性 / fulltext body metrics，但会在最终 `ArticleModel` 和 Markdown 渲染中作为 retained non-body sections 输出。
- 如果违反，用户会看到：只有 availability 的页面被误判成全文，或者真实 availability 声明因为“不算正文”而从最终输出消失。
- 它对应的阶段是：`availability-quality`、`section-classification`、`final-rendering`。
- Owner：`paper_fetch.quality.html_availability` 与 `paper_fetch.models.ArticleModel` retained section 渲染。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/_scenarios/availability_body_metrics/code_availability.md`](../tests/fixtures/golden_criteria/_scenarios/availability_body_metrics/code_availability.md)
  - `_scenarios/availability_body_metrics` 锁住只有 abstract + code availability 时仍应判为 abstract-only 且保留 availability；它不是 DOI 级真实 replay。
- 对应测试：
  - Owner（models）：
    - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_keeps_data_availability_without_counting_it_as_fulltext`
    - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_keeps_code_availability_without_counting_it_as_fulltext`
  - Provider 覆盖：
    - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_wiley_real_fixture_does_not_count_research_funding_as_body`
    - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_science_real_fixture_does_not_leak_competing_interests_modal`
- 边界说明：
  - 本规则不删除 availability；它只决定 availability 不参与“是否有足够正文”的质量判定。

<a id="rule-section-hints-normalize-availability"></a>
### Section hint 必须稳定适配 availability 节

- 这条规则约束的是：HTML 提取或中间结构提供的 section hint 必须按同一套 heading key 和顺序匹配语义适配到 availability 节；无论 hint 以 dict、对象还是 `SectionHint` dataclass 传入，最终渲染都要一致。
- 如果违反，用户会看到：结构信号已经标明的 availability 节仍被当成普通正文，或者 dict / dataclass 形态不同导致渲染顺序漂移。
- 它对应的阶段是：`section-classification`、`article-assembly`。
- Owner：`paper_fetch.extraction.section_hints`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/_scenarios/section_hints_availability/article.md`](../tests/fixtures/golden_criteria/_scenarios/section_hints_availability/article.md)
  - [`../tests/fixtures/golden_criteria/_scenarios/section_hints_availability/section_hints.json`](../tests/fixtures/golden_criteria/_scenarios/section_hints_availability/section_hints.json)
  - `_scenarios/section_hints_availability` 锁住 dict / object / dataclass hint 形态和 declared order；它不是 DOI 级真实 replay。
- 对应测试：
  - Owner（models / generic）：
    - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_uses_section_hints_for_nonliteral_data_availability`
    - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_uses_section_hints_for_nonliteral_code_availability`
    - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_coerces_dict_object_and_section_hint_in_declared_order`
    - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_browser_workflow_returns_section_hints_for_structural_data_availability`
    - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_browser_workflow_returns_section_hints_for_structural_code_availability`
- 边界说明：
  - 本规则只约束 section hint 适配，不定义新的 availability kind；kind 映射见 [Availability 标题必须映射到稳定 section kind](#rule-availability-section-kind-mapping)。
  - HTML semantics 与 `ArticleModel` 的解耦边界见 [`architecture/target-architecture.md` 的 Extraction 层](architecture/target-architecture.md#6-extraction-层)，不在本规则正文重复维护实现合约。

<a id="rule-keep-headingless-body-flat"></a>
### 无节标题正文必须保持扁平

- 这条规则约束的是：当文章正文本来就直接以连续段落展开、没有可靠的 body heading 时，组装和渲染阶段不能人为包一层重复标题、`## Full Text` 或同义伪节；如果需要区分前言和正文，最多只插入一次 `## Main Text` 作为边界。
- 如果违反，用户会看到：commentary、perspective 这类文章被套上并不存在的章节壳，或者文章标题又在正文里重复出现一次。
- 它对应的阶段是：`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.models.ArticleModel`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_science.aeg3511/original.html`](../tests/fixtures/golden_criteria/10.1126_science.aeg3511/original.html)
  - 这个样本能证明无显式正文小节时，文章正文应保持扁平展开而不是被包成伪章节。
- 对应测试：
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_science_perspective_fixture_extracts_fulltext_without_section_headings`
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_pnas_real_commentary_keeps_headingless_body_flat`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_pnas_provider_renders_headingless_commentary_without_synthetic_title_section`
  - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_keeps_headingless_body_flat_without_synthetic_heading`
  - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_structure_keeps_headingless_body_flat_without_synthetic_heading`
- 边界说明：
  - 这条规则不是说 `## Main Text` 永远不能出现。
  - 它约束的是“没有可靠正文节标题时不要硬造一层节结构”，不是禁止在前言和正文之间加一个必要的边界标题。

<a id="rule-preserve-inline-semantics-in-body-and-tables"></a>
### 正文、标题和表格里的行内语义格式不能被打平或拆裂

- 这条规则约束的是：标题、节标题、frontmatter、正文段落、图表 caption 和 Markdown 表格单元格里已经识别出的上下标、斜体变量、变量下标等行内语义，不能在清洗或渲染时被打平成普通空格文本，也不能被错误地拆成断开的 token。
- 如果违反，用户会看到：`CO<sub>2</sub>` 变成 `CO 2`、`TCID<sub>50</sub>` 变成 `TCID50`，`*h*<sub>0</sub>` 变成 `h0`，或者 `*x*` 和 `<sub>i</sub>` 被拆散到两行，看起来像坏标题、坏表格或坏公式。
- 它对应的阶段是：`html-cleanup`、`table-rendering`、`markdown-normalization`、`final-rendering`。
- Owner：`paper_fetch.extraction.html.inline`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_science.abp8622/original.html`](../tests/fixtures/golden_criteria/10.1126_science.abp8622/original.html)
  - 这个样本能证明 frontmatter / summary / main text 里的 `CO<sub>2</sub>` 和 `log<sub>10</sub>` 需要保持原有上下标语义。
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2406303121/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2406303121/original.html)
  - 这个样本能证明 PNAS 表格单元格和正文里的上下标、变量符号、单位格式需要保持原有行内语义。
- 对应测试：
  - Owner（generic）：
    - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_inline_normalization_is_shared_for_body_heading_and_table_text`
    - [`../tests/unit/test_science_pnas_postprocess_units.py`](../tests/unit/test_science_pnas_postprocess_units.py) 中的 `test_extract_science_pnas_markdown_normalizes_title_subscript_line_breaks`
  - Provider 覆盖：
    - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_springer_markdown_preserves_subscripts_in_section_headings`
    - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_pnas_full_fixture_keeps_data_availability_and_renders_table_markdown`
    - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_pnas_real_fixture_renders_table_and_inline_cell_formatting`
    - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_wiley_full_fixture_extracts_body_sections_from_real_html`
    - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_science_real_frontmatter_fixture_preserves_structured_summaries_and_main_text`
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_split_inline_variable_subscripts_are_rejoined_in_paragraphs`
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_inline_boundary_newlines_are_normalized`
- 边界说明：
  - 这条规则只约束已经识别成行内语义的内容，不承诺对复杂公式、整段 MathML 或所有数学符号做完整排版。
  - 它也不是说所有英文字母组合都必须自动识别成变量加下标。

<a id="rule-readable-equation-caption-spacing"></a>
### 公式块和图注句子的块间距必须可读

- 这条规则约束的是：`**Equation n.**` 和对应的 `$$...$$` display math 之间必须保持稳定的块级换行，公式后的解释句和 figure caption 的后续句子也不能被粘成一整块坏文本。
- 如果违反，用户会看到：`**Equation 1.**$$`、`$$where *P* is precipitation`、`2020.Time series` 这类明显粘连的坏渲染。
- 它对应的阶段是：`markdown-normalization`、`final-rendering`。
- Owner：`paper_fetch.providers._science_pnas_postprocess`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_science.adp0212/original.html`](../tests/fixtures/golden_criteria/10.1126_science.adp0212/original.html)
  - 这个样本能证明公式标签、display math、解释句和 figure caption 之间都需要稳定的块边界。
- 对应测试：
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_science_adp0212_fixture_splits_display_equations_and_caption_sentences`
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_science_real_fixture_keeps_formula_and_figure_caption_spacing`
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_shared_equation_normalization_handles_real_science_and_pnas_fixtures`
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_pnas_real_fixture_preserves_figures_equations_and_heading_trimming`
- 边界说明：
  - 这条规则不保证公式语义一定完全正确。
  - 它约束的是“公式块和图注句子的可读边界不能坏掉”，不是对编号体系或数学求值做承诺。
  - 当前直接 DOI 证据样本来自 Science；PNAS 后处理测试覆盖同一共享 spacing policy，后续不为凑数强行新增 fixture。

<a id="rule-preserve-formula-image-fallbacks"></a>
### HTML 公式图片 fallback 必须保留并进入资产链路

- 这条规则约束的是：HTML 中的 MathML、publisher fallback span、inline equation image 和 display equation image 要尽量转成可读公式；如果 MathML 无法转换或公式本来只以图片存在，就保留 `![Formula](...)`，并把它作为 `kind="formula"` 的正文资产候选进入下载和本地链接改写流程。
- 如果违反，用户会看到：公式静默消失、被渲染成 `[Formula unavailable]` 的假失败，或者正文里残留远程公式图片链接且无法跟下载资产对应。
- 它对应的阶段是：`html-cleanup`、`formula-rendering`、`asset-discovery`、`article-assembly`。
- Owner：`paper_fetch.extraction.html.formula_rules`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.15322/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.15322/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_nature12915/original.html`](../tests/fixtures/golden_criteria/10.1038_nature12915/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_nature13376/original.html`](../tests/fixtures/golden_criteria/10.1038_nature13376/original.html)
  - 这些样本分别覆盖 Wiley fallback formula image、旧 Nature display equation 图片 `_EquN_HTML.jpg` 和旧 Nature inline equation image `_IEqN_HTML.jpg`。
- 对应测试：
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_wiley_formula_image_fallbacks_are_preserved`
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_wiley_inline_mathml_with_fallback_span_does_not_emit_placeholder`
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_wiley_display_formula_can_fall_back_to_alt_image_span`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_old_nature_fixture_preserves_inline_equation_images`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_old_nature_fixture_keeps_single_methods_summary_and_methods_sections`
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_formula_rules_detect_real_formula_image_urls`
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_extract_formula_assets_reuses_shared_formula_rules`
  - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_rewrites_inline_asset_urls_to_downloaded_paths`
- 边界说明：
  - 这条规则不是保证所有 HTML 公式都能转成 LaTeX；保留公式图片 fallback 是正确输出。
  - Nature display equation 结构 `c-article-equation` / `c-article-equation__content` 和 `_Equ1_HTML.jpg` 这类 URL 必须渲染为 `![Formula](...)` 并进入 `kind="formula"` 资产链路。
  - 只有看起来属于公式容器、公式 URL 或公式 alt/title 的图片才进入公式资产链路，普通 `FigN_HTML` 正文图片仍按 figure/table 处理。

<a id="rule-formula-latex-normalization"></a>
### LaTeX normalization 必须产出 KaTeX 可渲染表达

- 这条规则约束的是：公式转换后的 LaTeX 要在公共 normalize 层修复 publisher-specific 输出，例如 MathML `mtext` 里出版商转义的标识符下划线、`\updelta` 这类 upright Greek 宏，以及 `\mspace{Nmu}` 这类 KaTeX 不兼容间距。
- 如果违反，用户会看到：`M\_NDVI` 渲染成 `M\textbackslash\_NDVI`，`\updelta` 无法渲染，或者公式因为 KaTeX 不支持的间距宏而失败。
- 它对应的阶段是：`formula-rendering`、`markdown-normalization`、`final-rendering`。
- Owner：`paper_fetch.formula.convert`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/_scenarios/formula_latex_normalization/samples.json`](../tests/fixtures/golden_criteria/_scenarios/formula_latex_normalization/samples.json)
  - `_scenarios/formula_latex_normalization` 锁住 publisher-specific LaTeX normalize 分支；它不是 DOI 级真实 replay。
- 对应测试：
  - Owner（generic）：
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_repairs_identifier_escaped_underscores`
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_does_not_globally_replace_textbackslash`
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_rewrites_upgreek_macros`
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_rewrites_mspace_for_katex`
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_scenario_samples_are_katex_compatible`
- 边界说明：
  - 这条规则不承诺所有 MathML 都能转换成功；失败占位和 provider-specific inline/display 行为由具体公式渲染规则约束。
  - `\textbackslash\_` 只修复夹在标识符字符之间的窄范围场景，不能全局替换正常文本里的 `\textbackslash`。`\mspace{Nmu}` 只在 `mu` 单位时改写为 `\mkernNmu`，其它单位保留原样。

## Springer

- 共享规则另见：
  - [HTML fulltext / abstract-only 判定必须和用户可见访问状态一致](#rule-html-availability-contract)
  - [Provider 自有作者与摘要信号必须进入最终文章元数据](#rule-provider-owned-authors)
  - [并行多语言摘要要并存，单语非英文正文不能被误删](#rule-keep-parallel-multilingual-abstracts)
  - [Data / Code Availability 必须保留且不能重复](#rule-keep-data-availability-once)
  - [Availability 标题必须映射到稳定 section kind](#rule-availability-section-kind-mapping)
  - [Availability 不计入正文充分性度量](#rule-availability-excluded-from-body-metrics)
  - [正文已内联 figure 时不再重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)
  - [正文、标题和表格里的行内语义格式不能被打平或拆裂](#rule-preserve-inline-semantics-in-body-and-tables)
  - [已下载的正文图片和公式图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links)
  - [表格能展平就转 Markdown 表，展不平就退成可读列表](#rule-table-flatten-or-list)
  - [HTML 公式图片 fallback 必须保留并进入资产链路](#rule-preserve-formula-image-fallbacks)
- 不适用 / 部分适用说明：
  - [浏览器工作流图片下载必须使用 shared browser context 主链路](#rule-browser-primary-image-download-path) 不适用于 Springer direct HTML；Springer 图片下载走 direct HTML 资产链路。
  - [前言摘要族的顺序与去重必须稳定](#rule-stable-frontmatter-order) 只在 Springer/Nature 页面暴露可识别 frontmatter 结构时适用，不要求所有 Springer 页面生成前言族。

<a id="rule-springer-chrome-heading-normalization"></a>
### 已拆分：Springer chrome 剪枝与编号标题空格规范化

> 已拆分为 [Springer article root 必须避开站点 chrome](#rule-springer-article-root-chrome-pruning) 和 [Springer 编号标题必须规范空格](#rule-springer-numbered-heading-spacing)。

旧 anchor 保留用于 manifest、历史链接和外部引用。新规则分别约束 article-root / chrome 剪枝，以及编号标题 inline span 的空格规范化。

<a id="rule-springer-article-root-chrome-pruning"></a>
### Springer article root 必须避开站点 chrome

- 这条规则约束的是：Springer / Springer Nature HTML 提取必须先选到可信 article root，再剪掉保存文章、期刊 CTA、Aims and scope、Submit manuscript、重复标题块、`About this article` / 权限许可等站点 chrome；正文之外的科学 back matter 只保留 `Acknowledgements`、`Data Availability`、`Author Contributions` 这类论文内容节。
- 如果违反，用户会看到：多语言摘要和正文之间插入 `Save article`、`View saved research`、重复论文标题或 Creative Commons 许可长文。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`html-cleanup`、`section-classification`。
- Owner：`paper_fetch.providers.html_springer_nature` 与 `paper_fetch.providers._springer_html`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html`](../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html)
  - [`../tests/fixtures/golden_criteria/10.1007_s13158-025-00473-x/bilingual.html`](../tests/fixtures/golden_criteria/10.1007_s13158-025-00473-x/bilingual.html)
  - 这两个样本分别覆盖 Springer classic chrome 泄漏，以及双语摘要后进入正文时不能重复标题和 CTA。
- 对应测试：
  - [`../tests/unit/test_springer_html_tables.py`](../tests/unit/test_springer_html_tables.py) 中的 `test_springer_classic_fixture_strips_chrome_and_spaces_numbered_headings`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_springer_bilingual_fixture_enters_body_without_duplicate_title_or_cta`
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_clean_markdown_registers_springer_nature_profile`
- 边界说明：
  - 这条规则过滤的是站点框架和操作入口，不是删除论文正文里自然出现的相同词面。
  - `springer_nature` 是显式注册的 shared noise profile；Springer/Nature 调用 shared Markdown cleanup 时不得静默回退到 generic profile。

<a id="rule-springer-numbered-heading-spacing"></a>
### Springer 编号标题必须规范空格

- 这条规则约束的是：Springer / Springer Nature HTML 中由多个 inline span 拼出的编号标题，最终必须渲染成带空格的真实标题。
- 如果违反，用户会看到：`## 1Introduction`、`### 3.1Glaciers` 这类编号和标题文本粘连的坏 Markdown。
- 它对应的阶段是：`html-cleanup`、`markdown-normalization`、`final-rendering`。
- Owner：`paper_fetch.providers.html_springer_nature`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html`](../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html)
  - 这个样本覆盖 Springer classic 编号标题由 inline span 拼接时的空格规范化。
- 对应测试：
  - [`../tests/unit/test_springer_html_tables.py`](../tests/unit/test_springer_html_tables.py) 中的 `test_springer_classic_fixture_strips_chrome_and_spaces_numbered_headings`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_springer_markdown_spaces_numbered_inline_heading_spans`
- 边界说明：
  - 它不要求所有编号标题都改写成某个统一编号体系，只要求已存在的编号和标题文本不能粘连或重复。

<a id="rule-nature-main-content-direct-children"></a>
### 已更名：Nature main-content 直接子节点遍历规则

> 已更名为 [Springer / Nature main-content 必须按直接子节点顺序进入正文](#rule-springer-main-content-direct-children)。

旧 anchor 保留用于 manifest、历史链接和外部引用。

<a id="rule-springer-main-content-direct-children"></a>
### Springer / Nature main-content 必须按直接子节点顺序进入正文

- 这条规则约束的是：Nature HTML 的 `div.main-content` 不能只因为存在直接 `section` 就只渲染这些 `section`；必须按直接子节点顺序处理正文 `div.c-article-section__content`、可渲染正文 `div` 和 `section`，否则 Matters Arising 这类页面会把正文段落漏掉，只剩 `Reporting summary`。
- 如果违反，用户会看到：`Forest age and water yield` 这类文章缺少真正正文，只剩 `Reporting summary` / Extended Data Table 占位，`Data availability` 也可能被错误地当成唯一正文。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`section-classification`。
- Owner：`paper_fetch.providers.html_springer_nature` 与 `paper_fetch.providers._springer_html`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1038_s41586-020-1941-5/original.html`](../tests/fixtures/golden_criteria/10.1038_s41586-020-1941-5/original.html)
  - [`../tests/fixtures/golden_criteria/_scenarios/springer_main_content_direct_children/original.html`](../tests/fixtures/golden_criteria/_scenarios/springer_main_content_direct_children/original.html)
  - 真实 replay 覆盖 `main-content` 中正文 `div` 位于 `Reporting summary` section 之前的结构；scenario 锁住直接子节点顺序的最小形态。
- 对应测试：
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_nature_matters_arising_fixture_keeps_main_content_before_reporting_summary`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_springer_main_content_scenario_keeps_direct_child_order`
- 边界说明：
  - 当前有一份 Nature Matters Arising replay 和一个最小 scenario；同类 Springer / Nature main-content 遍历改动仍应优先补第二个 DOI 级 fixture。
  - 正文外的 `Data availability` / `Code availability` 仍然允许从 scientific back matter 补回，但已经在正文遍历中出现的 availability 节不能重复输出。

<a id="rule-springer-original-html-artifact"></a>
### 已迁出：Springer 原始 article HTML 落盘

> 已迁出到 [`providers.md` 的 Springer artifact/storage 说明](providers.md#springer-原始-html-artifact)。

旧 anchor 保留用于历史链接。原始 HTML 文件名和下载目录形态属于 `artifact-storage`，不再作为提取 / 渲染规则维护。

<a id="rule-springer-supplementary-scope"></a>
### Springer supplementary 只能来自 supplementary-like section，Source Data 必须独立分类落盘

- 这条规则约束的是：Springer / Nature HTML 的普通 supplementary 只能从 `Supplementary information`、`Supplementary material(s)`、`Supporting information`、`Electronic supplementary material`、`Extended data`、`Extended data figures and tables` 这些 supplementary-like section 子树里识别；`Source data` 不能再混进普通 supplementary，而是要独立识别并在下载时落到 `source_data/` 子目录。`Peer Review File` / `Peer reviewer reports` 也必须排除。
- 如果违反，用户会看到：正文或 article chrome 里的普通 PDF/CSV/ZIP 被误当成 supplementary，`Peer Review File` 混入补充材料列表，或者 `Source Data` 和普通 supplementary 重复下载、重复落盘。
- 它对应的阶段是：`asset-discovery`、`asset-download`、`artifact-storage`。
- Owner：`paper_fetch.providers._springer_html` 与 `paper_fetch.extraction.html._assets`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1038_s41561-022-00912-7/original.html`](../tests/fixtures/golden_criteria/10.1038_s41561-022-00912-7/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_s41558-022-01584-2/original.html`](../tests/fixtures/golden_criteria/10.1038_s41558-022-01584-2/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_s43247-024-01270-5/original.html`](../tests/fixtures/golden_criteria/10.1038_s43247-024-01270-5/original.html)
  - 这几份 replay 分别覆盖独立 `Source data` section、`Extended data` 描述里的 `Source data` 内链，以及 supplementary section 中的 `Peer Review File` 排除。
- 对应测试：
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_extract_asset_html_scopes_leave_empty_supplementary_scope_without_supplementary_sections`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_real_nature_fixture_separates_source_data_from_supplementary_assets`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_real_nature_fixture_resolves_source_data_links_from_extended_data_descriptions`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_real_nature_fixture_skips_peer_review_files_from_supplementary_assets`
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_download_supplementary_assets_routes_source_data_into_subdirectory`
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_download_supplementary_assets_with_only_source_data_creates_only_source_data_subdirectory`
- 边界说明：
  - 这条规则只约束 Springer / Nature HTML asset discovery，不改变 Wiley / Science / PNAS 的 supplementary 判定范围。
  - `Extended Data` / `Extended Data Figures and Tables` 里的 figure / table page 链接仍然属于普通 supplementary 范围；只有独立 `Source data` section 或 `Extended data` 项里显式标注 `Source data` 的链接会被归到 source-data。
  - `Source Data` 的独立分类是内部实现细节；对外资产仍通过既有 supplementary 下载链路返回，只是路径被分流到 `source_data/`。

<a id="rule-springer-access-hint-disclaimer"></a>
### 访问提示、预览语和 AI 免责声明不能混进正文

- 这条规则约束的是：publisher 页面用来告诉用户“这里只是预览”“这是访问提示”“这段 alt 可能由 AI 生成”的站点说明，不能被当成论文正文或摘要输出。
- 如果违反，用户会看到：摘要或正文里多出 `This is a preview of subscription content`、`The alternative text for this image may have been generated using AI.` 这类明显不是论文内容的提示句。
- 它对应的阶段是：`html-cleanup`、`markdown-normalization`。
- Owner：`paper_fetch.providers.html_springer_nature` 与 `paper_fetch.providers.html_noise`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/block/10.1007_s00382-018-4286-0/raw.html`](../tests/fixtures/block/10.1007_s00382-018-4286-0/raw.html)
  - [`../tests/fixtures/golden_criteria/10.1038_s44221-022-00024-x/original.html`](../tests/fixtures/golden_criteria/10.1038_s44221-022-00024-x/original.html)
  - 这两个样本分别覆盖 Springer paywall preview 句子和 Nature figure AI disclaimer。
- 对应测试：
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_springer_paywall_article_markdown_strips_preview_sentence`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_springernature_fulltext_markdown_strips_ai_alt_disclaimer`
- 边界说明：
  - 这条规则删除的是明显的站点提示，不是删除所有提到 `preview`、`AI`、`generated` 的正常论文句子。
  - 如果某段话本来就是论文正文内容，即使包含相同词面，也不能仅凭关键词去掉。

<a id="rule-springer-caption-precedence"></a>
### 正文 figure 优先相信正式 caption，不相信噪声 fallback

- 这条规则约束的是：图已经有正式图题或图注时，渲染链必须优先使用这些正式内容，不能再把站点塞进来的 `data-title`、`alt`、朗读文本、下载入口和展示控件重新拼回图注里。
- 如果违反，用户会看到：同一张图的标题后面又多出一段重复、破碎或格式错乱的说明，常见表现是残留的 LaTeX、拆开的希腊字母、重复 caption、`PowerPoint slide` 或 `Full size image`。
- 它对应的阶段是：`asset-discovery`、`final-rendering`。
- Owner：`paper_fetch.providers._springer_html` 与 `paper_fetch.providers.html_springer_nature`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1038_nature12915/original.html`](../tests/fixtures/golden_criteria/10.1038_nature12915/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_nature13376/original.html`](../tests/fixtures/golden_criteria/10.1038_nature13376/original.html)
  - 这两个旧 Nature 样本覆盖正式 caption 存在时清理 `PowerPoint slide` / `Full size image` 这类控件文案。
- 对应测试：
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_springer_markdown_ignores_ai_alt_text_when_caption_exists`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_old_nature_fixture_keeps_single_methods_summary_and_methods_sections`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_old_nature_downloaded_body_figures_inline_without_trailing_figures_block`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_new_nature_downloaded_body_figures_inline_without_trailing_figures_block`
- 边界说明：
  - 这条规则不是说 `data-title` 或 `alt` 永远不能用。
  - 当 figure 真正缺少 caption / description 时，这些字段仍然可以作为兜底来源。
  - `PowerPoint slide`、`Full size image` 这类控件文案的兜底过滤见 [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)；本规则只负责 caption 来源选择。

<a id="rule-springer-methods-summary"></a>
### 旧 Nature 的 Methods Summary / Methods 结构必须归一且不重复

- 这条规则约束的是：旧 Nature 文章里如果同时存在 `Methods Summary` 和 `Online Methods` / 旧方法结构证据，最终结构必须归一成“`Methods Summary` 一次、`Methods` 一次”，不能重复堆出两个同义方法章节。
- 如果违反，用户会看到：文档里出现两个 `Methods Summary`，或者 `Online Methods`、`Methods` 混着出现，方法学结构会看起来像重复拼装。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.providers._springer_html` 与 `paper_fetch.models.ArticleModel`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1038_nature12915/original.html`](../tests/fixtures/golden_criteria/10.1038_nature12915/original.html)
  - 这个样本能证明旧 Nature 的 `Methods Summary` 与 `Online Methods` 需要按正文结构归一处理。
- 对应测试：
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_old_nature_fixture_keeps_single_methods_summary_and_methods_sections`
  - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_promotes_repeated_methods_summary_to_methods`
  - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_real_nature_markdown_keeps_methods_summary_without_structure_hints`
- 边界说明：
  - 这条规则不是要求所有论文都必须出现 `Methods Summary`。
  - 只有同篇 parsed sections 同时存在 `Methods Summary` 与 `Online Methods`，或 section hints / source selector 体现旧 Nature 方法结构时，才把 stripped `Methods Summary` body section 归一为 `Methods`。单独存在的真实 `Methods Summary` 正文节必须保留原 heading。

<a id="rule-springer-inline-table"></a>
### 正文内联 table 占位必须被真实表格替换，替不出来也不能把占位符漏给用户

- 这条规则约束的是：正文里如果先放了一个 table 占位，后续拿到 table page 时要把真实表格插回原位置；如果 table page 最终没拿到真正的表，也不能把内部占位符直接漏给用户。对于 Springer/Nature inline table 节点，只要 label 是 `Extended Data Table N` 且存在匹配的 `/tables/N` 页面链接，若 table page 实际是图片响应或只能从 HTML 中提取 full-size image，应输出 `kind="table"` 的 table 图片资产；若解析失败，应输出明确的 `[Table body unavailable: ...]` 降级占位。
- 如果违反，用户会看到：正文里残留像 `PAPER_FETCH_TABLE_PLACEHOLDER` 这样的内部标记，Extended Data Table 直接消失，或者文章因为某个 table page 没拿到表就整体变成异常结果。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`table-rendering`、`asset-discovery`、`final-rendering`。
- Owner：`paper_fetch.providers.springer` 与 `paper_fetch.extraction.html.tables`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/original.html`](../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/table1.html`](../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/table1.html)
  - [`../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html`](../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html)
  - [`../tests/fixtures/golden_criteria/10.1038_nature13376/original.html`](../tests/fixtures/golden_criteria/10.1038_nature13376/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_s41586-020-1941-5/original.html`](../tests/fixtures/golden_criteria/10.1038_s41586-020-1941-5/original.html)
  - 这几份样本分别覆盖“真实 Nature table page 被注回正文”、“Springer classic article 遇到坏 table page 也不能把占位符漏给用户”、旧 Nature Extended Data Table 图片 / 占位降级，以及非 `nature13376` 的 Extended Data Table 结构 fallback。
- 对应测试：
  - [`../tests/unit/test_springer_html_tables.py`](../tests/unit/test_springer_html_tables.py) 中的 `test_render_table_markdown_handles_real_springer_classic_table_page`
  - [`../tests/unit/test_springer_html_tables.py`](../tests/unit/test_springer_html_tables.py) 中的 `test_springer_html_injects_real_nature_inline_table_page_with_flattened_headers`
  - [`../tests/unit/test_springer_html_tables.py`](../tests/unit/test_springer_html_tables.py) 中的 `test_springer_html_keeps_article_success_when_inline_table_page_has_no_table`
  - [`../tests/unit/test_springer_html_tables.py`](../tests/unit/test_springer_html_tables.py) 中的 `test_generic_extended_data_table_image_response_renders_table_asset`
  - [`../tests/unit/test_springer_html_tables.py`](../tests/unit/test_springer_html_tables.py) 中的 `test_generic_extended_data_table_html_image_fallback_renders_table_asset`
  - [`../tests/unit/test_springer_html_tables.py`](../tests/unit/test_springer_html_tables.py) 中的 `test_regular_table_does_not_use_image_asset_fallback`
  - [`../tests/unit/test_springer_html_tables.py`](../tests/unit/test_springer_html_tables.py) 中的 `test_old_nature_extended_data_tables_render_table_image_or_degraded_placeholder`
- 边界说明：
  - 这条规则不是要求所有 table page 都必须成功转出表格。
  - 它约束的是“成功时正确注回，失败时不把内部占位符暴露给用户，也不让整篇文章失败”；当原始站点只提供 Extended Data Table 图片时，图片 fallback 是正确输出，不是图表丢失。
  - 普通 `Table N` 不默认启用图片 fallback，避免把非 Extended Data Table 的坏表页误当成图片表格。

## Elsevier

- Elsevier XML 元素级映射总表另见 [`../references/elsevier_markdown_mapping.md`](../references/elsevier_markdown_mapping.md)；下面只保留当前主干必须维持的用户可见 Markdown 行为约束。
- 共享规则另见：
  - [Provider 自有作者与摘要信号必须进入最终文章元数据](#rule-provider-owned-authors)
  - [并行多语言摘要要并存，单语非英文正文不能被误删](#rule-keep-parallel-multilingual-abstracts)
  - [正文、标题和表格里的行内语义格式不能被打平或拆裂](#rule-preserve-inline-semantics-in-body-and-tables)
  - [Data / Code Availability 必须保留且不能重复](#rule-keep-data-availability-once)
  - [Availability 标题必须映射到稳定 section kind](#rule-availability-section-kind-mapping)
  - [Section hint 必须稳定适配 availability 节](#rule-section-hints-normalize-availability)
  - [正文已内联 figure 时不再重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)
  - [已下载的正文图片和公式图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links)
  - [LaTeX normalization 必须产出 KaTeX 可渲染表达](#rule-formula-latex-normalization)
- 不适用 / 部分适用说明：
  - [HTML fulltext / abstract-only 判定必须和用户可见访问状态一致](#rule-html-availability-contract) 不适用于 Elsevier XML 主路径；PDF fallback 仍是 text-only。
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise) 和 [HTML 公式图片 fallback 必须保留并进入资产链路](#rule-preserve-formula-image-fallbacks) 不适用于 Elsevier XML 主路径。
  - [浏览器工作流图片下载必须使用 shared browser context 主链路](#rule-browser-primary-image-download-path) 不适用于 Elsevier 官方 XML/API。

<a id="rule-elsevier-formula-rendering"></a>
### 正文内联公式与 display formula 分开渲染，失败时给可见占位和 conversion notes

- 这条规则约束的是：Elsevier XML 段落里的行内数学要留在正文行内，display formula 要单独渲染成公式块；如果某个公式最终无法转换，也必须给用户一个可见占位，并在 conversion notes 里留下明确痕迹。
- 如果违反，用户会看到：段落里的单字母变量被误渲染成一串独立公式块，或者某个公式直接静默消失。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`formula-rendering`、`final-rendering`。
- Owner：`paper_fetch.providers._article_markdown_math` 与 `paper_fetch.providers._article_markdown_elsevier`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml)
  - [`../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2023.130125/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2023.130125/original.xml)
  - [`../tests/fixtures/golden_criteria/_scenarios/elsevier_formula_inline_display/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_formula_inline_display/original.xml)
  - [`../tests/fixtures/golden_criteria/_scenarios/elsevier_formula_missing/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_formula_missing/original.xml)
  - real Elsevier XML 覆盖 display formula 渲染为公式块；两个 scenario 分别锁住 inline/display 混排和 conversion failure 占位分支。
- 对应测试：
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_real_display_formula_renders_as_formula_block`
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_inline_math_symbols_stay_inline`
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_formula_placeholder_is_visible_when_conversion_fails`
- 边界说明：
  - 这条规则不是保证所有 Elsevier MathML 都能被完美转成 LaTeX。
  - 它约束的是“行内和 display 数学不能混渲，失败时不能静默丢失”；公共 LaTeX 宏兼容处理见 [LaTeX normalization 必须产出 KaTeX 可渲染表达](#rule-formula-latex-normalization)。
  - real XML 目前锁定 display formula 主干；inline math 与 conversion failure 由 scenario XML 锁定，后续如出现稳定 DOI replay，应优先补到本规则。

<a id="rule-elsevier-supplementary-materials"></a>
### Supplementary data 不进正文，统一收进 `## Supplementary Materials`

- 这条规则约束的是：`Supplementary data` 这类补充材料显示块不能混进正文叙述里，而是要统一落到文末的 `## Supplementary Materials` 区域，并保留基本的标题和说明。
- 如果违反，用户会看到：正文突然插进一个补充材料下载入口，或者补充材料完全消失。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`asset-discovery`、`final-rendering`。
- Owner：`paper_fetch.providers._article_markdown_elsevier` 与 `paper_fetch.models.ArticleModel`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.ecolind.2024.112140/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.ecolind.2024.112140/original.xml)
  - [`../tests/fixtures/golden_criteria/_scenarios/elsevier_supplementary_display/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_supplementary_display/original.xml)
  - [`../tests/fixtures/golden_criteria/_scenarios/elsevier_supplementary_asset_only/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_supplementary_asset_only/original.xml)
  - real Elsevier XML 覆盖 `ce:e-component` supplementary locator 与下载文件映射；两个 scenario 分别锁住 display 排除正文和无 display 资产兜底。
- 对应测试：
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_supplementary_display_is_omitted_from_body_and_listed_with_caption`
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_supplementary_asset_without_display_is_listed_as_supplementary_material`
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_real_supplementary_e_component_from_golden_xml_is_listed`
- 边界说明：
  - real XML 锁住 `ce:e-component` 主干；两个 scenario XML 分别锁住 supplementary display 的正文排除行为，以及无 display 时已下载 supplementary 文件仍进入 Supplementary Materials。
  - 这条规则不是说 supplementary 资产不能下载或不能暴露给用户。
  - 它约束的是“补充材料不属于正文主体”，不是限制 supplementary 元数据的存在。
  - 当 `asset_profile='all'` 时，supplementary 应作为独立文件资产下载并落到 `section="supplementary"` / `download_tier="supplementary_file"`；它不属于正文 figure inline 逻辑，也不会进入 MCP inline `ImageContent`。

<a id="rule-elsevier-appendix-context"></a>
### Appendix figure/table 保持 appendix 语境，不因正文交叉引用被提到正文

- 这条规则约束的是：凡是已经处在 appendix 语境里的 figure 和 table，就要继续留在 appendix 里渲染；即使正文提到 `Fig. A1` 或 `Table A1`，也不能把这些 appendix 资产提前到正文区。
- 如果违反，用户会看到：正文里突然混入 appendix 图表，或者 appendix 内容被拆散后前后顺序错乱。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.providers._article_markdown_elsevier` 与 `paper_fetch.models.ArticleModel`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.rse.2026.115369/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.rse.2026.115369/original.xml)
  - 这份 real Elsevier XML 同时覆盖 appendix figure、appendix table 和正文中的 appendix 交叉引用。
- 对应测试：
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_appendix_figure_renders_as_figure_block`
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_appendix_reference_keeps_asset_in_appendix`
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_appendix_table_renders_as_markdown_table`
- 边界说明：
  - 当前三个 owner 测试分别锁定 appendix figure、正文交叉引用顺序和 appendix table；新增 appendix 形态时应继续补独立测试。
  - 这条规则不是说正文里不能出现对 appendix 图表的交叉引用文字。
  - 它约束的是 appendix 资产的实际渲染位置和上下文，而不是正文文字是否能提到它们。

<a id="rule-elsevier-table-placement"></a>
### 已拆分：Elsevier 图表正文位置、去重和复杂表降级

> 已拆分为 [Elsevier 正文引用到的 figure / table 要就地插回](#rule-elsevier-inline-figure-table-placement)、[Elsevier 已消费图表不得在尾部重复追加](#rule-elsevier-consumed-figure-table-dedup) 和 [Elsevier 复杂 span 表必须保留语义展开和降级标记](#rule-elsevier-complex-table-span-degradation)。

旧 anchor 保留用于 manifest、历史链接和外部引用。

<a id="rule-elsevier-inline-figure-table-placement"></a>
### Elsevier 正文引用到的 figure / table 要就地插回

- 这条规则约束的是：Elsevier XML 正文里已经引用到的 figure / table 要尽量在引用位置附近渲染；没有正文锚点的浮动表才进入 `## Additional Tables`。
- 如果违反，用户会看到：正文提到 `Fig. 1` 或 `Table 1` 却找不到对应图表，阅读顺序被打断。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.providers._article_markdown_elsevier_document` 与 `paper_fetch.models.ArticleModel` structure rendering。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2021.126210/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2021.126210/original.xml)
  - [`../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml)
  - 这些 real Elsevier XML 覆盖正文图片插入和正文表格就地插回。
- 对应测试：
  - Owner（provider）：
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_table_placement_contracts`
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_article_from_structure_preserves_inline_elsevier_figures`
- 边界说明：
  - 本规则不要求没有正文锚点的 float 强行插入正文；这类图表仍可进入 Additional Figures / Tables。

<a id="rule-elsevier-consumed-figure-table-dedup"></a>
### Elsevier 已消费图表不得在尾部重复追加

- 这条规则约束的是：已经在正文消费过的 Elsevier 图表必须通过 render state 或 consumed key 从尾部资产附录里过滤掉。
- 如果违反，用户会看到：正文已经有的表在文末又以只有 caption 的 `## Tables` 重复出现。
- 它对应的阶段是：`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.models.ArticleModel` render state 与 `paper_fetch.providers._article_markdown_elsevier` asset planning。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2023.130125/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2023.130125/original.xml)
  - 这个样本覆盖已消费表格不再尾部重复。
- 对应测试：
  - Owner（models）：
    - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_to_ai_markdown_skips_inline_assets_and_labels_additional_tables`
  - Provider 覆盖：
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_table_placement_contracts`
- 边界说明：
  - 本规则只处理“已经消费过”的图表；未锚定或 appendix 语境的图表仍按对应规则输出。

<a id="rule-elsevier-complex-table-span-degradation"></a>
### Elsevier 复杂 span 表必须保留语义展开和降级标记

- 这条规则约束的是：遇到 rowspan / colspan / `namest` / `nameend` / `morerows` 这类复杂结构时，优先输出带 conversion notes 的语义展开 Markdown 表，并把质量标记为 `table_layout_degraded`，不能把“版式无法无损表达”误报成“语义内容丢失”。
- 如果违反，用户会看到：复杂表直接变成一张图 / 空摘要，或者没有说明地被压扁成错误 Markdown 表，无法被 AI 和用户继续读取。
- 它对应的阶段是：`table-rendering`、`final-rendering`。
- Owner：`paper_fetch.providers._article_markdown_elsevier_document` 与 `paper_fetch.models.Quality`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2021.126210/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2021.126210/original.xml)
  - [`../tests/fixtures/golden_criteria/10.1016_j.rse.2024.114346/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.rse.2024.114346/original.xml)
  - [`../tests/fixtures/golden_criteria/_scenarios/elsevier_complex_table_span/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_complex_table_span/original.xml)
  - real Elsevier XML 覆盖 conversion note 和 `table_layout_degraded` 质量标记；scenario XML 锁住 span 表的语义展开细节。
- 对应测试：
  - Owner（provider）：
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_complex_table_spans_are_semantically_expanded`
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_real_complex_table_records_layout_degradation_quality`
- 边界说明：
  - 当前用 scenario XML 锁住 span 展平细节，用 real XML 锁住 conversion note 和质量标记。
  - 这条规则不是要求复杂表在 Markdown 里必须零损失复原。
  - 它约束的是“优先给用户可读的表格文本和降级提示”，不是承诺所有单元格跨度都能无损还原。
  - `table_layout_degraded` 表示 Markdown 版式无法表达真实合并单元格；只有行列语义内容真的丢失时，才应升级为 `table_semantic_loss` / `figure_table_loss`。

<a id="rule-elsevier-xml-references"></a>
### Elsevier XML 参考文献必须优先使用结构化 bibliography，保持编号和作者信息

- 这条规则约束的是：Elsevier XML 里存在 `<ce:bibliography>` / `<ce:bib-reference>` / `<sb:reference>` 时，文章模型的 `references` 必须优先从这些结构化节点构建，保留原始顺序、编号、作者、标题、来源、页码、年份和 DOI；字段缺失时必须回退到 visible raw reference text 或显式 `[Reference text unavailable]`，不能直接跳过 bib 条目。Crossref metadata references 只能作为兜底。
- 如果违反，用户会看到：参考文献从 `1. A. Anav, P. Friedlingstein...` 退化成没有作者、没有编号的 bullet，如 `- Remote sensing of drought: Progress, challenges and opportunities`，或者 XML 里存在的 bib 条目在最终 references 中消失。
- 它对应的阶段是：`references-rendering`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.providers._article_markdown_elsevier_document`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml)
  - 这个样本能证明 Elsevier XML bibliography 中的 label、作者、题名、期刊卷期页码和 DOI 需要进入最终 references。
- 对应测试：
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_build_article_structure_extracts_numbered_xml_references`
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_references_fall_back_without_skipping_bib_entries`
- 边界说明：
  - 这条规则不要求所有 Elsevier 文献都有完整 DOI 或页码；缺失字段不能凭空生成。
  - 它约束的是“结构化 XML references 存在时必须优先使用并保持条目数量”，不是禁止在 XML 缺 references 时回退到 metadata references。

<a id="rule-elsevier-graphical-abstract"></a>
### Graphical abstract 不进入 Additional Figures

- 这条规则约束的是：graphical abstract 这类站点或期刊 frontmatter 资产不能混进 `## Additional Figures`，即使它们也有图片文件。
- 如果违反，用户会看到：正文无关的 graphical abstract 和真正的正文 figure 混在同一个附录块里，图列表会被污染。
- 它对应的阶段是：`asset-discovery`、`final-rendering`。
- Owner：`paper_fetch.providers._article_markdown_elsevier` 与 `paper_fetch.models.ArticleModel`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.scitotenv.2022.158499/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.scitotenv.2022.158499/original.xml)
  - 这份 real Elsevier XML 覆盖 `class="graphical"` abstract figure 与正文 figure 同时存在的场景。
- 对应测试：
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_graphical_abstract_assets_do_not_appear_in_additional_figures`
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_graphical_abstract_only_document_does_not_create_additional_figures`
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_real_graphical_abstract_from_golden_xml_is_excluded_from_figures`
- 边界说明：
  - real XML 锁住 Graphical abstract 主干；两个最小资产归类测试分别覆盖“有正文 figure”和“只有 graphical abstract”两种边界。
  - 这条规则不是说 graphical abstract 必须从所有输出里彻底删除。
  - 它约束的是 graphical abstract 不能被误归到正文 figure 附录里。

## Wiley

- 共享规则另见：
  - [HTML fulltext / abstract-only 判定必须和用户可见访问状态一致](#rule-html-availability-contract)
  - [Provider 自有作者与摘要信号必须进入最终文章元数据](#rule-provider-owned-authors)
  - [保留语义父节标题](#rule-keep-semantic-parent-heading)
  - [前言摘要族的顺序与去重必须稳定](#rule-stable-frontmatter-order)
  - [并行多语言摘要要并存，单语非英文正文不能被误删](#rule-keep-parallel-multilingual-abstracts)
  - [Data / Code Availability 必须保留且不能重复](#rule-keep-data-availability-once)
  - [Availability 标题必须映射到稳定 section kind](#rule-availability-section-kind-mapping)
  - [Availability 不计入正文充分性度量](#rule-availability-excluded-from-body-metrics)
  - [Section hint 必须稳定适配 availability 节](#rule-section-hints-normalize-availability)
  - [正文已内联 figure 时不再重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)
  - [正文、标题和表格里的行内语义格式不能被打平或拆裂](#rule-preserve-inline-semantics-in-body-and-tables)
  - [已下载的正文图片和公式图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links)
  - [图片下载必须验证真实图片内容](#rule-image-download-validates-real-images)
  - [下载资产必须保留诊断字段](#rule-asset-download-diagnostic-fields)
  - [浏览器工作流图片下载必须使用 shared browser context 主链路](#rule-browser-primary-image-download-path)
  - [表格能展平就转 Markdown 表，展不平就退成可读列表](#rule-table-flatten-or-list)
  - [HTML 公式图片 fallback 必须保留并进入资产链路](#rule-preserve-formula-image-fallbacks)
- 不适用 / 部分适用说明：
  - [LaTeX normalization 必须产出 KaTeX 可渲染表达](#rule-formula-latex-normalization) 只在 Wiley HTML MathML 成功进入 LaTeX 转换时适用；公式图片 fallback 仍由 HTML 公式图片规则约束。

<a id="rule-wiley-abbreviations-trailing"></a>
### Abbreviations 只在正文后保留，不得提前打断正文结构

- 这条规则约束的是：如果 Wiley 页面里存在 `Abbreviations` 区块，它可以作为正文后的辅助节保留，但不能提前到正文主线前面，也不能插进正文章节和正文表格中间打断阅读顺序。
- 如果违反，用户会看到：文章还没进入主体内容，`Abbreviations` 就先冒出来，或者它把正文叙述和正文表格硬切成两段。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.providers._science_pnas_postprocess`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1111_cas.16395/original.html`](../tests/fixtures/golden_criteria/10.1111_cas.16395/original.html)
  - [`../tests/fixtures/golden_criteria/_scenarios/wiley_abbreviations_trailing/original.html`](../tests/fixtures/golden_criteria/_scenarios/wiley_abbreviations_trailing/original.html)
  - real replay 能证明 `Abbreviations` 可以保留但只能放在正文和正文表格之后；scenario 锁住 frontmatter glossary 移到正文后的最小形态。
- 对应测试：
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_wiley_real_fixture_appends_abbreviations_after_body_content`
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_wiley_abbreviations_scenario_moves_frontmatter_glossary_after_body`
- 边界说明：
  - 当前只有一份 Wiley replay 加一个 scenario；后续若新增真实 Wiley abbreviations 页面，应优先补第二个 DOI 级 fixture。
  - 这条规则不是要求所有 Wiley 文章都必须输出 `Abbreviations`。
  - 它约束的是“存在该区块时的落点”，不是强制生成一个缺失的缩写表。

<a id="rule-wiley-supporting-information-assets"></a>
### Wiley supplementary 只能来自 Supporting Information 区块，正文 figure 不得误归 supplementary

- 这条规则约束的是：Wiley supplementary 只允许从 `Supporting Information` accordion/content 中提取，并且只接受 `downloadSupplement` 或文件名/参数带 `sup-*` 的真实 supporting file 链接。正文 `<figure>` 里的 `/cms/asset/...fig-*.jpg|png|webp` 只能保留为 figure 资产，不能再被并行归类成 supplementary；`downloadSupplement` 的 `file` / `filename` query 要作为 `filename_hint` 保留，落盘时优先使用真实文件名。
- 如果违反，用户会看到：`asset_profile=all` 下正文 figure 被重复当作 supplementary 文件下载，`article.assets` 混进一批 `fig-*.jpg/.png` 伪 supplementary；真正的 supporting file 可能落成 `downloadSupplement.bin`，难以辨认。
- 它对应的阶段是：`asset-discovery`、`provider-html-or-xml-extraction`、`asset-download`、`artifact-storage`。
- Owner：`paper_fetch.providers._science_pnas_html`、`paper_fetch.providers._wiley_html` 与 `paper_fetch.extraction.html._assets`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.16414/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16414/original.html)
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html)
  - real Wiley fixture 覆盖正文 figure、supporting cross-reference 与 `Supporting Information` 文件表；第二份 Wiley fixture 锁住同一 DOM 语义在另一篇文章中的稳定性。
- 对应测试：
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_wiley_asset_scopes_only_collect_supporting_information_downloads`
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_wiley_real_fixture_supporting_information_only_yields_true_supplementary_asset`
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_download_supplementary_assets_uses_wiley_filename_hint_for_octet_stream`
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_wiley_body_figures_are_not_promoted_to_supplementary_without_supporting_information`
- 边界说明：
  - 这条规则不是说 Wiley supplementary 不能是图片；只要链接本身是 `downloadSupplement` 或 filename/query 带 `sup-*`，即使最终文件是图像格式，也仍然属于 supplementary 文件。
  - 它约束的是“supplementary 的来源范围和链接形态”，不是要求正文里所有指向 `Figure S1` 的交叉引用都必须变成下载资产。

<a id="rule-wiley-reference-text"></a>
### Wiley 参考文献必须使用可见 citation 文本而不是 DOI-only 或链接 chrome

- 这条规则约束的是：Wiley HTML references 要从可见 citation body 中抽取作者、题名、期刊等文本，删除 `Google Scholar`、`Crossref`、`getFTR` 和隐藏链接区，不能把 DOI-only 链接当成完整 reference。
- 如果违反，用户会看到：参考文献只剩 DOI，或者每条 reference 后面混进一串站点跳转和检索入口。
- 它对应的阶段是：`references-rendering`、`html-cleanup`。
- Owner：`paper_fetch.providers._html_references` 与 `paper_fetch.providers._wiley_html`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.15322/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.15322/original.html)
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html)
- 对应测试：
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_wiley_references_use_visible_citation_text_not_doi_only`
- 边界说明：
  - 单测试规则：当前用一条参数化测试覆盖两份 Wiley replay，锁住可见 citation body 优先级；新增 Wiley reference DOM 变体时应继续扩充 fixture 参数或拆出独立测试。
  - 这条规则只过滤 publisher reference chrome，不会补全原始 HTML 中没有的 bibliographic 字段。

## Science

<a id="rule-science-pnas-supplementary-sections"></a>
### Science / PNAS supplementary 只能来自真实 supplementary section

- 这条规则约束的是：Science / Science Advances / PNAS 的 supplementary 文件只允许从 Atypon article back matter 中的 `Supplementary Material(s)` / `Supporting Information` section 子树识别，并且只保留 publisher `/doi/suppl/.../suppl_file/...` 附件。正文、Data Availability、文章导航、页内锚点或 supplementary section 内引用文献里的普通 `.csv` / `.txt` / `.pdf` / `#supplementary-materials` 链接不能被当作 supplementary。
- 如果违反，用户会看到：`asset_profile=all` 下正文数据链接或 supplementary references 中的外部 PDF 被错误下载成 supplementary，或者真实 `core-supplementary-materials` 里的 PDF/XLSX 附件被漏掉。
- 它对应的阶段是：`asset-discovery`、`provider-html-or-xml-extraction`、`asset-download`。
- Owner：`paper_fetch.providers._science_pnas_html` 与 `paper_fetch.extraction.html._assets`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/original.html`](../tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/original.html)
  - [`../tests/fixtures/block/10.1073_pnas.2509692123/raw.html`](../tests/fixtures/block/10.1073_pnas.2509692123/raw.html)
  - Science fixture 覆盖正文 Data Availability 中 `.txt` 数据链接和真实 Supplementary Materials PDF；PNAS fixture 覆盖正文中指向 supplementary section 的页内锚点和真实 Supporting Information PDF/XLSX。
- 对应测试：
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_extract_scoped_html_assets_empty_supplementary_scope_does_not_scan_body`
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_science_real_fixture_supplementary_comes_only_from_supplementary_section`
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_pnas_real_fixture_supplementary_ignores_body_anchor_to_section`
- 边界说明：
  - 这条规则不改变 Science / PNAS 正文图片和公式图片的提取范围；只约束 supplementary 文件发现 scope。
  - 如果页面没有真实 supplementary section，supplementary scope 应为空，不能回退扫描 body。

- 共享规则另见：
  - [HTML fulltext / abstract-only 判定必须和用户可见访问状态一致](#rule-html-availability-contract)
  - [Provider 自有作者与摘要信号必须进入最终文章元数据](#rule-provider-owned-authors)
  - [保留语义父节标题](#rule-keep-semantic-parent-heading)
  - [前言摘要族的顺序与去重必须稳定](#rule-stable-frontmatter-order)
  - [并行多语言摘要要并存，单语非英文正文不能被误删](#rule-keep-parallel-multilingual-abstracts)
  - [Data / Code Availability 必须保留且不能重复](#rule-keep-data-availability-once)
  - [Availability 标题必须映射到稳定 section kind](#rule-availability-section-kind-mapping)
  - [Availability 不计入正文充分性度量](#rule-availability-excluded-from-body-metrics)
  - [Section hint 必须稳定适配 availability 节](#rule-section-hints-normalize-availability)
  - [无节标题正文必须保持扁平](#rule-keep-headingless-body-flat)
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)
  - [正文、标题和表格里的行内语义格式不能被打平或拆裂](#rule-preserve-inline-semantics-in-body-and-tables)
  - [正文已内联 figure 时不再重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)
  - [已下载的正文图片和公式图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links)
  - [图片下载必须验证真实图片内容](#rule-image-download-validates-real-images)
  - [下载资产必须保留诊断字段](#rule-asset-download-diagnostic-fields)
  - [浏览器工作流图片下载必须使用 shared browser context 主链路](#rule-browser-primary-image-download-path)
  - [表格能展平就转 Markdown 表，展不平就退成可读列表](#rule-table-flatten-or-list)
  - [公式块和图注句子的块间距必须可读](#rule-readable-equation-caption-spacing)
  - [HTML 公式图片 fallback 必须保留并进入资产链路](#rule-preserve-formula-image-fallbacks)
- 不适用 / 部分适用说明：
  - [LaTeX normalization 必须产出 KaTeX 可渲染表达](#rule-formula-latex-normalization) 只在 MathML 进入 LaTeX 转换时适用；纯公式图片 fallback 仍按 HTML 公式图片规则处理。

## PNAS

PNAS 的 supplementary 资产范围见 [Science / PNAS supplementary 只能来自真实 supplementary section](#rule-science-pnas-supplementary-sections)；其余用户可见行为约束主要归入共享规则。

- 共享规则另见：
  - [HTML fulltext / abstract-only 判定必须和用户可见访问状态一致](#rule-html-availability-contract)
  - [Provider 自有作者与摘要信号必须进入最终文章元数据](#rule-provider-owned-authors)
  - [前言摘要族的顺序与去重必须稳定](#rule-stable-frontmatter-order)
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)
  - [并行多语言摘要要并存，单语非英文正文不能被误删](#rule-keep-parallel-multilingual-abstracts)
  - [Data / Code Availability 必须保留且不能重复](#rule-keep-data-availability-once)
  - [Availability 标题必须映射到稳定 section kind](#rule-availability-section-kind-mapping)
  - [Availability 不计入正文充分性度量](#rule-availability-excluded-from-body-metrics)
  - [Section hint 必须稳定适配 availability 节](#rule-section-hints-normalize-availability)
  - [无节标题正文必须保持扁平](#rule-keep-headingless-body-flat)
  - [正文、标题和表格里的行内语义格式不能被打平或拆裂](#rule-preserve-inline-semantics-in-body-and-tables)
  - [正文已内联 figure 时不再重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)
  - [已下载的正文图片和公式图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links)
  - [图片下载必须验证真实图片内容](#rule-image-download-validates-real-images)
  - [下载资产必须保留诊断字段](#rule-asset-download-diagnostic-fields)
  - [浏览器工作流图片下载必须使用 shared browser context 主链路](#rule-browser-primary-image-download-path)
  - [表格能展平就转 Markdown 表，展不平就退成可读列表](#rule-table-flatten-or-list)
  - [公式块和图注句子的块间距必须可读](#rule-readable-equation-caption-spacing)
  - [HTML 公式图片 fallback 必须保留并进入资产链路](#rule-preserve-formula-image-fallbacks)
- 不适用 / 部分适用说明：
  - [LaTeX normalization 必须产出 KaTeX 可渲染表达](#rule-formula-latex-normalization) 只在 MathML 进入 LaTeX 转换时适用；PNAS 公式图片 fallback 仍按 HTML 公式图片规则处理。

## Fixture 反向索引

本表覆盖本文档直接链接的 fixture。一个 fixture 可锁住多条规则；替换 fixture 时必须同步检查这些规则。

| Fixture | 关联规则 |
| --- | --- |
| [`../tests/fixtures/block/10.1007_s00382-018-4286-0/raw.html`](../tests/fixtures/block/10.1007_s00382-018-4286-0/raw.html) | [HTML availability](#rule-html-availability-contract), [Springer access hint](#rule-springer-access-hint-disclaimer) |
| [`../tests/fixtures/block/10.1073_pnas.2509692123/raw.html`](../tests/fixtures/block/10.1073_pnas.2509692123/raw.html) | [HTML availability](#rule-html-availability-contract), [Science / PNAS supplementary sections](#rule-science-pnas-supplementary-sections) |
| [`../tests/fixtures/block/10.1111_gcb.16414/raw.html`](../tests/fixtures/block/10.1111_gcb.16414/raw.html) | [HTML availability](#rule-html-availability-contract) |
| [`../tests/fixtures/block/10.1126_science.aeg3511/raw.html`](../tests/fixtures/block/10.1126_science.aeg3511/raw.html) | [HTML availability](#rule-html-availability-contract) |
| [`../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html`](../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html) | [Springer chrome](#rule-springer-article-root-chrome-pruning), [Springer numbered heading spacing](#rule-springer-numbered-heading-spacing), [Springer inline table](#rule-springer-inline-table) |
| [`../tests/fixtures/golden_criteria/10.1007_s13158-025-00473-x/bilingual.html`](../tests/fixtures/golden_criteria/10.1007_s13158-025-00473-x/bilingual.html) | [Multilingual abstracts](#rule-keep-parallel-multilingual-abstracts), [Springer chrome](#rule-springer-article-root-chrome-pruning) |
| [`../tests/fixtures/golden_criteria/10.1016_S1575-1813(18)30261-4/bilingual.xml`](<../tests/fixtures/golden_criteria/10.1016_S1575-1813(18)30261-4/bilingual.xml>) | [Multilingual abstracts](#rule-keep-parallel-multilingual-abstracts) |
| [`../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml) | [Elsevier formula rendering](#rule-elsevier-formula-rendering), [Elsevier inline figure/table placement](#rule-elsevier-inline-figure-table-placement), [Elsevier references](#rule-elsevier-xml-references) |
| [`../tests/fixtures/golden_criteria/10.1016_j.ecolind.2024.112140/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.ecolind.2024.112140/original.xml) | [Elsevier supplementary materials](#rule-elsevier-supplementary-materials) |
| [`../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2021.126210/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2021.126210/original.xml) | [Elsevier inline figure/table placement](#rule-elsevier-inline-figure-table-placement), [Elsevier complex span table](#rule-elsevier-complex-table-span-degradation) |
| [`../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2023.130125/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2023.130125/original.xml) | [Elsevier formula rendering](#rule-elsevier-formula-rendering), [Elsevier consumed table dedup](#rule-elsevier-consumed-figure-table-dedup) |
| [`../tests/fixtures/golden_criteria/10.1016_j.rse.2024.114346/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.rse.2024.114346/original.xml) | [Elsevier complex span table](#rule-elsevier-complex-table-span-degradation) |
| [`../tests/fixtures/golden_criteria/10.1016_j.rse.2025.114648/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.rse.2025.114648/original.xml) | [Availability kind mapping](#rule-availability-section-kind-mapping) |
| [`../tests/fixtures/golden_criteria/10.1016_j.rse.2026.115369/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.rse.2026.115369/original.xml) | [Elsevier appendix context](#rule-elsevier-appendix-context) |
| [`../tests/fixtures/golden_criteria/10.1016_j.scitotenv.2022.158499/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.scitotenv.2022.158499/original.xml) | [Elsevier graphical abstract](#rule-elsevier-graphical-abstract) |
| [`../tests/fixtures/golden_criteria/10.1029_2004gb002273/original.html`](../tests/fixtures/golden_criteria/10.1029_2004gb002273/original.html) | [No trailing figures](#rule-no-trailing-figures-appendix), [Publisher UI noise](#rule-filter-publisher-ui-noise) |
| [`../tests/fixtures/golden_criteria/10.1038_nature12915/original.html`](../tests/fixtures/golden_criteria/10.1038_nature12915/original.html) | [Formula image fallback](#rule-preserve-formula-image-fallbacks), [Springer caption precedence](#rule-springer-caption-precedence), [Springer methods summary](#rule-springer-methods-summary) |
| [`../tests/fixtures/golden_criteria/10.1038_nature13376/original.html`](../tests/fixtures/golden_criteria/10.1038_nature13376/original.html) | [No trailing figures](#rule-no-trailing-figures-appendix), [Formula image fallback](#rule-preserve-formula-image-fallbacks), [Springer caption precedence](#rule-springer-caption-precedence), [Springer inline table](#rule-springer-inline-table) |
| [`../tests/fixtures/golden_criteria/10.1038_s41561-022-00983-6/original.html`](../tests/fixtures/golden_criteria/10.1038_s41561-022-00983-6/original.html) | [No trailing figures](#rule-no-trailing-figures-appendix) |
| [`../tests/fixtures/golden_criteria/10.1038_s41586-020-1941-5/original.html`](../tests/fixtures/golden_criteria/10.1038_s41586-020-1941-5/original.html) | [Springer / Nature main-content](#rule-springer-main-content-direct-children), [Springer inline table](#rule-springer-inline-table) |
| [`../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/original.html`](../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/original.html) | [Springer inline table](#rule-springer-inline-table) |
| [`../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/table1.html`](../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/table1.html) | [Springer inline table](#rule-springer-inline-table) |
| [`../tests/fixtures/golden_criteria/10.1038_s43247-024-01885-8/original.html`](../tests/fixtures/golden_criteria/10.1038_s43247-024-01885-8/original.html) | [Data / Code Availability](#rule-keep-data-availability-once) |
| [`../tests/fixtures/golden_criteria/10.1038_s44221-022-00024-x/original.html`](../tests/fixtures/golden_criteria/10.1038_s44221-022-00024-x/original.html) | [Springer access hint](#rule-springer-access-hint-disclaimer) |
| [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html) | [Provider metadata](#rule-provider-owned-authors), [Publisher UI noise](#rule-filter-publisher-ui-noise), [Image validation](#rule-image-download-validates-real-images), [Browser image path](#rule-browser-primary-image-download-path), [Data / Code Availability](#rule-keep-data-availability-once) |
| [`../tests/fixtures/golden_criteria/10.1073_pnas.2406303121/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2406303121/original.html) | [Inline semantics](#rule-preserve-inline-semantics-in-body-and-tables) |
| [`../tests/fixtures/golden_criteria/10.1111_cas.16395/original.html`](../tests/fixtures/golden_criteria/10.1111_cas.16395/original.html) | [Wiley abbreviations](#rule-wiley-abbreviations-trailing) |
| [`../tests/fixtures/golden_criteria/10.1111_gcb.15322/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.15322/original.html) | [Formula image fallback](#rule-preserve-formula-image-fallbacks), [Wiley references](#rule-wiley-reference-text) |
| [`../tests/fixtures/golden_criteria/10.1111_gcb.16386/bilingual.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16386/bilingual.html) | [Multilingual abstracts](#rule-keep-parallel-multilingual-abstracts) |
| [`../tests/fixtures/golden_criteria/10.1111_gcb.16414/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16414/original.html) | [Wiley supporting information assets](#rule-wiley-supporting-information-assets) |
| [`../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html) | [HTML availability](#rule-html-availability-contract), [Provider metadata](#rule-provider-owned-authors), [Wiley references](#rule-wiley-reference-text) |
| [`../tests/fixtures/golden_criteria/10.1126_sciadv.aax6869/original.html`](../tests/fixtures/golden_criteria/10.1126_sciadv.aax6869/original.html) | [No trailing figures](#rule-no-trailing-figures-appendix), [Image validation](#rule-image-download-validates-real-images) |
| [`../tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/original.html`](../tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/original.html) | [Semantic parent heading](#rule-keep-semantic-parent-heading), [Science / PNAS supplementary sections](#rule-science-pnas-supplementary-sections) |
| [`../tests/fixtures/golden_criteria/10.1126_science.abb3021/original.html`](../tests/fixtures/golden_criteria/10.1126_science.abb3021/original.html) | [No trailing figures](#rule-no-trailing-figures-appendix), [Image validation](#rule-image-download-validates-real-images) |
| [`../tests/fixtures/golden_criteria/10.1126_science.abp8622/original.html`](../tests/fixtures/golden_criteria/10.1126_science.abp8622/original.html) | [Stable frontmatter](#rule-stable-frontmatter-order), [Inline semantics](#rule-preserve-inline-semantics-in-body-and-tables) |
| [`../tests/fixtures/golden_criteria/10.1126_science.adp0212/original.html`](../tests/fixtures/golden_criteria/10.1126_science.adp0212/original.html) | [Provider metadata](#rule-provider-owned-authors), [Equation spacing](#rule-readable-equation-caption-spacing) |
| [`../tests/fixtures/golden_criteria/10.1126_science.aeg3511/original.html`](../tests/fixtures/golden_criteria/10.1126_science.aeg3511/original.html) | [Headingless body](#rule-keep-headingless-body-flat) |
| [`../tests/fixtures/golden_criteria/_scenarios/asset_download_diagnostics/article_payload.json`](../tests/fixtures/golden_criteria/_scenarios/asset_download_diagnostics/article_payload.json) | [Asset diagnostics](#rule-asset-download-diagnostic-fields) |
| [`../tests/fixtures/golden_criteria/_scenarios/availability_body_metrics/code_availability.md`](../tests/fixtures/golden_criteria/_scenarios/availability_body_metrics/code_availability.md) | [Availability body metrics](#rule-availability-excluded-from-body-metrics) |
| [`../tests/fixtures/golden_criteria/_scenarios/elsevier_author_groups_minimal/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_author_groups_minimal/original.xml) | [Provider metadata](#rule-provider-owned-authors) |
| [`../tests/fixtures/golden_criteria/_scenarios/elsevier_complex_table_span/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_complex_table_span/original.xml) | [Elsevier complex span table](#rule-elsevier-complex-table-span-degradation) |
| [`../tests/fixtures/golden_criteria/_scenarios/elsevier_formula_inline_display/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_formula_inline_display/original.xml) | [Elsevier formula rendering](#rule-elsevier-formula-rendering) |
| [`../tests/fixtures/golden_criteria/_scenarios/elsevier_formula_missing/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_formula_missing/original.xml) | [Elsevier formula rendering](#rule-elsevier-formula-rendering) |
| [`../tests/fixtures/golden_criteria/_scenarios/elsevier_supplementary_asset_only/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_supplementary_asset_only/original.xml) | [Elsevier supplementary materials](#rule-elsevier-supplementary-materials) |
| [`../tests/fixtures/golden_criteria/_scenarios/elsevier_supplementary_display/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_supplementary_display/original.xml) | [Elsevier supplementary materials](#rule-elsevier-supplementary-materials) |
| [`../tests/fixtures/golden_criteria/_scenarios/formula_latex_normalization/samples.json`](../tests/fixtures/golden_criteria/_scenarios/formula_latex_normalization/samples.json) | [LaTeX normalization](#rule-formula-latex-normalization) |
| [`../tests/fixtures/golden_criteria/_scenarios/generic_metadata_boundaries/generic_description.html`](../tests/fixtures/golden_criteria/_scenarios/generic_metadata_boundaries/generic_description.html) | [Generic metadata boundaries](#rule-generic-metadata-boundaries) |
| [`../tests/fixtures/golden_criteria/_scenarios/generic_metadata_boundaries/redirect_stub.html`](../tests/fixtures/golden_criteria/_scenarios/generic_metadata_boundaries/redirect_stub.html) | [Generic metadata boundaries](#rule-generic-metadata-boundaries) |
| [`../tests/fixtures/golden_criteria/_scenarios/inline_figure_link_rewrite/article.md`](../tests/fixtures/golden_criteria/_scenarios/inline_figure_link_rewrite/article.md) | [Inline figure link rewrite](#rule-rewrite-inline-figure-links) |
| [`../tests/fixtures/golden_criteria/_scenarios/inline_figure_link_rewrite/assets.json`](../tests/fixtures/golden_criteria/_scenarios/inline_figure_link_rewrite/assets.json) | [Inline figure link rewrite](#rule-rewrite-inline-figure-links) |
| [`../tests/fixtures/golden_criteria/_scenarios/provider_dom_abstract_fallback/payload.json`](../tests/fixtures/golden_criteria/_scenarios/provider_dom_abstract_fallback/payload.json) | [Provider metadata](#rule-provider-owned-authors) |
| [`../tests/fixtures/golden_criteria/_scenarios/section_hints_availability/article.md`](../tests/fixtures/golden_criteria/_scenarios/section_hints_availability/article.md) | [Section hints availability](#rule-section-hints-normalize-availability) |
| [`../tests/fixtures/golden_criteria/_scenarios/section_hints_availability/section_hints.json`](../tests/fixtures/golden_criteria/_scenarios/section_hints_availability/section_hints.json) | [Section hints availability](#rule-section-hints-normalize-availability) |
| [`../tests/fixtures/golden_criteria/_scenarios/springer_main_content_direct_children/original.html`](../tests/fixtures/golden_criteria/_scenarios/springer_main_content_direct_children/original.html) | [Springer / Nature main-content](#rule-springer-main-content-direct-children) |
| [`../tests/fixtures/golden_criteria/_scenarios/table_flatten_or_list/complex_table.html`](../tests/fixtures/golden_criteria/_scenarios/table_flatten_or_list/complex_table.html) | [Table flatten/list](#rule-table-flatten-or-list) |
| [`../tests/fixtures/golden_criteria/_scenarios/wiley_abbreviations_trailing/original.html`](../tests/fixtures/golden_criteria/_scenarios/wiley_abbreviations_trailing/original.html) | [Wiley abbreviations](#rule-wiley-abbreviations-trailing) |

## 未直接挂规则 fixture 清单

下列 manifest sample 当前未被上面的 fixture 反向索引直接挂到单条规则。它们作为 golden corpus、block corpus、live review 或跨 publisher regression 样本保留；新增规则引用它们时，应把对应 sample 从本清单移入反向索引。

<!-- extraction-rules-unlinked-fixtures:start -->
| 范围 | Sample | 用途说明 |
| --- | --- | --- |
| block / Springer | `10.1007_s11430-021-9892-6__block`, `10.1007_s12652-019-01399-8__block`, `10.1007_s13351-020-9829-8__block` | Springer block corpus 的 access gate / abstract-only 回归池；当前不直接定义单条提取规则。 |
| block / PNAS | `10.1073_pnas.2523032123__block`, `10.1073_pnas.2534432123__block`, `10.1073_pnas.2607267123__block` | PNAS block corpus 的 provider availability 回归池。 |
| block / Science | `10.1126_science.167.3914.61__block`, `10.1126_science.6985744__block`, `10.1126_science.7809609__block` | Science block corpus 的历史页面状态回归池。 |
| block / Wiley | `10.1111_gcb.16386__block`, `10.1111_gcb.16758__block`, `10.1111_gcb.16998__block` | Wiley block corpus 的 access gate / entitlement 回归池。 |
| golden / Elsevier | `10.1016_j.agrformet.2024.110321`, `10.1016_j.ecolind.2023.110326`, `10.1016_j.scitotenv.2022.158109` | Elsevier golden corpus 的 provider breadth 和 expected payload 回归，不直接承载新增规则。 |
| golden / Springer | `10.1038_d41586-022-01795-9`, `10.1038_d41586-023-01829-w`, `10.1038_s41467-022-30729-2`, `10.1038_s41561-022-00974-7`, `10.1038_s41612-021-00218-2` | Springer / Nature golden corpus 的结构多样性回归池。 |
| golden / PNAS | `10.1073_pnas.1915921117`, `10.1073_pnas.2208095119`, `10.1073_pnas.2305050120`, `10.1073_pnas.2310157121`, `10.1073_pnas.2314265121`, `10.1073_pnas.2317456120`, `10.1073_pnas.2322622121`, `10.1073_pnas.2402656121`, `10.1073_pnas.2410294121` | PNAS golden corpus 的 article-type 和 live review breadth 回归池。 |
| golden / Science | `10.1126_sciadv.abf8021`, `10.1126_sciadv.abg9690`, `10.1126_sciadv.abj3309`, `10.1126_sciadv.adm9732`, `10.1126_science.ade0347`, `10.1126_science.ady3136` | Science / Science Advances golden corpus 的 article-type 和 expected payload 回归池。 |
| golden / Wiley | `10.1111_cas.16117`, `10.1111_gcb.16011`, `10.1111_gcb.16455`, `10.1111_gcb.16561`, `10.1111_gcb.16745`, `10.1111_gcb.16758`, `10.1111_gcb.17141` | Wiley golden corpus 的 article-type、asset 和 expected payload 回归池。 |
| golden / other publishers | `10.1080_19455224.2025.2547671`, `10.1345_aph.1M379` | 非核心 provider 的 multilingual / content regression 样本。 |
<!-- extraction-rules-unlinked-fixtures:end -->

## 使用建议

- 新增回归测试时，优先把规则写成行为约束，再用 DOI 级样本去证明它。
- 做 root-cause 排障时，先判断问题是在 HTML 提取、文章组装、资产清洗，还是最终渲染阶段，再决定该把证据补到哪条规则下。
- 后续如果要补“既有规则”，继续沿用同一模板，不要把 incident 记录直接搬进这里。
