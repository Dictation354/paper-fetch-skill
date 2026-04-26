# 提取与渲染规则

这份文档解决：

- 当前主干必须维持的提取 / 组装 / 渲染行为约束有哪些
- 每条规则约束了什么用户可见结果
- 哪些真实 HTML / XML 样本和哪些测试在锁定这些规则

这份文档不解决：

- provider 路由、运行时限速、环境变量和部署细节
- 单次事故的时间线、排障过程或 root-cause 复盘全文
- 某篇 DOI 的特殊例外规则

provider 运行时行为见 [`providers.md`](providers.md)，系统分层与业务主线见 [`architecture/target-architecture.md`](architecture/target-architecture.md)。

## 规则怎么读

- 这里说的“规则”，指当前主干必须维持的行为约束，不是某篇 DOI 的特判。
- DOI 可以出现在文档里，但只能作为“证据样本”和“测试样本”，不能变成规则本身。
- 每条规则都尽量先用通俗语言描述“约束了什么”，再补充它落在哪个阶段、由哪些样本和测试锁住。
- 本轮新增规则以 HTML 证据为主；个别渲染规则当前只有最小复现测试，没有额外 DOI 样本。

### 规则条目模板

- 规则名
  - 用行为级表述命名，不把 DOI 写进规则名。
- 通俗解释
  - 固定说明三件事：这条规则约束的是……；如果违反，用户会看到……；它对应的阶段是……。
- 代表性 HTML / XML
  - 优先列 repo 内稳定的真实样本，不展开 incident 复盘。
  - 如果当前只有最小复现测试，就直接写“当前无稳定 DOI 样本，直接见对应测试”，不要为了凑样本编造 DOI 级证据。
- 对应测试
  - 列出直接锁住该行为的测试文件和测试名。
- 边界说明
  - 说明这条规则不约束什么，避免把样本现象误读成长期接口承诺。

## Generic

- 这里的 `Generic` 指跨 provider 共享的提取 / 渲染规则。
- 它现在只表示 shared extraction logic，不再表示可被路由命中的第六条 provider 或 public source。

<a id="rule-keep-semantic-parent-heading"></a>
### 保留语义父节标题

- 这条规则约束的是：只要 HTML 提取链已经识别出一个父节标题，后续的文章组装和最终 markdown 渲染就不能把这个父节标题吃掉，即使正文内容主要落在子节里。
- 如果违反，用户会看到：正文里直接从子节开始，像是 `Experimental design` 这样的内容突然失去上级章节，文档结构会断层。
- 它对应的阶段是：文章组装、最终渲染。
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

<a id="rule-no-trailing-figures-appendix"></a>
### 正文已内联 figure 时不再重复追加尾部 Figures 附录

- 这条规则约束的是：当 figure 已经以正文内联形式进入最终输出时，`asset_profile='body'` / `asset_profile='all'` 的正文图渲染不能再在文末重复拼一个尾部 `## Figures` 附录。
- 如果违反，用户会看到：正文已经出现过的 figure 在文末又来一遍，像是“正文 + 附录”重复渲染，结构和阅读顺序都会变差。
- 它对应的阶段是：资产清洗、最终渲染。
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

- 这条规则约束的是：出版社页面里的操作按钮、图窗入口、站点工具栏和明显的站点动作词，不能随着 HTML 提取或后处理一起混进最终 markdown。
- 如果违反，用户会看到：正文里夹杂 `Open in figure viewer`、`PowerPoint`、`Sign up for PNAS alerts` 这类站点操作文案，看起来像把网页操作层一起抓进来了。
- 它对应的阶段是：HTML 提取、共享 Markdown 后处理、资产清洗、最终渲染。
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
- 边界说明：
  - 这条规则过滤的是站点 UI 和操作噪声，不是过滤所有出现在图题或正文里的英文短语。
  - `preview sentence` 和 AI alt disclaimer 也会被过滤，但它们属于单独的访问提示规则，不混在本条里定义。
  - 如果某段文本本来就是论文内容的一部分，即使它看起来像按钮词，也不能仅凭字面值删除。

<a id="rule-generic-metadata-boundaries"></a>
### 通用元数据抽取不能把站点描述误当摘要，也不能丢掉 redirect stub 的 lookup title

- 这条规则约束的是：通用 HTML metadata 抽取只能把真正的论文元数据写进文章模型，不能把站点级 description、标题回显或 redirect stub chrome 误当成摘要；如果页面只是 redirect stub，但里面确实带着可靠 lookup title，也要保留下来供后续解析链使用。
- 如果违反，用户会看到：标题被重复当成摘要、摘要字段被站点 description 污染，或者 Elsevier redirect stub 只剩 `Redirecting`，导致后续抓取与展示退化。
- 它对应的阶段是：metadata 抽取、provider 前置清洗。
- 代表性 HTML / XML：
  - 当前无稳定 DOI 样本，直接见对应测试。
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
- 它对应的阶段是：provider-owned HTML 提取后的 availability 诊断、文章组装前的内容分级。
- 唯一实现位于 `paper_fetch.quality.html_availability`；provider 侧 `_html_availability.py` / `_science_pnas_html.py` 只保留兼容 re-export 或 wrapper，不再维护本地重复的 site-rule / availability 数据结构。
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
### Provider 自有作者与前言信号必须进入最终文章元数据且不能重复

- 这条规则约束的是：publisher 自己暴露的作者、摘要和前言结构信号，一旦已经被识别出来，就要稳定进入最终文章模型；优先使用更结构化的 provider-owned 信号，缺失时再回退到 DOM，可见结果里不能出现空作者、错摘要或重复摘要块。
- 如果违反，用户会看到：作者列表为空、摘要丢失，或者同一篇文章的摘要既出现在 metadata 又重复注回正文。
- 它对应的阶段是：provider 自有元数据提取、共享 browser-workflow 文章组装、最终渲染。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_science.adp0212/original.html`](../tests/fixtures/golden_criteria/10.1126_science.adp0212/original.html)
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html)
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html)
  - [`../tests/fixtures/golden_criteria/_scenarios/elsevier_author_groups_minimal/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_author_groups_minimal/original.xml)
  - 对于“DOM abstract 恢复正文首段”这个更小的场景，当前无稳定 DOI 样本，直接见对应测试。
- 对应测试：
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_build_article_structure_extracts_authors_from_author_groups`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_science_provider_uses_extracted_dom_abstract_and_restores_lead_body_text`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_provider_owned_html_signals_populate_final_article_authors`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_science_provider_falls_back_to_dom_authors_when_datalayer_is_missing`
- 边界说明：
  - 这条规则不是要求所有 provider 都必须有统一的作者源字段。
  - 它约束的是“已识别的 provider-owned 元数据要稳定进入最终模型”，不是要求不存在的作者信息凭空生成。

<a id="rule-preserve-subscripts-in-headings"></a>
### 标题和节标题里的上下标不能被打平成普通文本

- 这条规则约束的是：标题、节标题和前言摘要里已经用 HTML 上下标表示的内容，比如 `CO<sub>2</sub>`、`log<sub>10</sub>`，不能在清洗或渲染时被打平成普通空格文本。
- 如果违反，用户会看到：`CO<sub>2</sub>` 变成 `CO 2`，或者 `CO` 和 `<sub>2</sub>` 被换行拆开，标题读起来像坏掉了一样。
- 它对应的阶段是：标题提取、节标题渲染、正文清洗。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_science.abp8622/original.html`](../tests/fixtures/golden_criteria/10.1126_science.abp8622/original.html)
  - 这个样本能证明 frontmatter / summary / main text 里的 `CO<sub>2</sub>` 和 `log<sub>10</sub>` 需要保持原有上下标语义。
  - 对于“Springer 节标题里的上下标”这个更小的场景，当前无稳定 DOI 样本，直接见对应测试。
- 对应测试：
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_springer_markdown_preserves_subscripts_in_section_headings`
  - [`../tests/unit/test_science_pnas_postprocess_units.py`](../tests/unit/test_science_pnas_postprocess_units.py) 中的 `test_extract_science_pnas_markdown_normalizes_title_subscript_line_breaks`
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_science_real_frontmatter_fixture_preserves_structured_summaries_and_main_text`
- 边界说明：
  - 这条规则只约束已经抽取成 HTML 上下标的内容。
  - 它不是对复杂公式、MathML 或所有行内数学都做完整排版承诺。

<a id="rule-rewrite-inline-figure-links"></a>
### 已下载的正文图片和公式图片要改写成正文附近的本地链接

- 这条规则约束的是：正文里已经有 figure、table image 或 formula image 锚点时，最终 markdown 应该尽量把远程图链接或绝对本地路径改写成当前 markdown 文件可用的本地资源链接，而且图和图之间不能误绑；改写后还要重新规范 Markdown 图片块边界，不能让图片和标题、正文句子或公式围栏粘在一起。
- 如果违反，用户会看到：图片链接还是远程 URL、还是绝对路径、图 4 的本地资源被错绑到图 1 的 caption 上，或者出现 `Heading![Figure]`、`text.![Formula]` 这类坏 Markdown。
- 它对应的阶段是：资产匹配、文章组装、最终渲染、落盘改写。
- 规则 owner 是 `paper_fetch.extraction.html.figure_links`；provider 提取阶段的 figure 注入和下载后的 figure link rewrite 必须共用同一套 label / URL alias / downloaded path 优先级规则。
- 代表性 HTML / XML：
  - 当前没有单一 DOI 样本能完整覆盖“远程图 -> 已下载本地资源 -> 相对 markdown 路径 -> 交叉引用不误绑”的全过程，直接见对应测试。
- 对应测试：
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_science_provider_rewrites_inline_figure_links_to_downloaded_local_assets`
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_rewrite_inline_figure_links_prefers_local_paths_for_existing_science_image_blocks`
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_rewrite_inline_figure_links_is_data_driven_for_non_legacy_publisher`
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_rewrite_inline_figure_links_ignores_cross_references_in_asset_captions`
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_figure_link_injection_and_rewrite_share_path_preference`
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
### 图片下载必须验证真实图片、保留 tier 和尺寸诊断

- 这条规则约束的是：正文图片下载不能把 Cloudflare challenge HTML、Chrome 图片查看器壳或过小的站点图标当成论文图片保存；成功保存的图片资产应记录 `download_tier`、下载 URL、content type、字节数和尺寸，preview 图只有尺寸达标并在 source trail 中标记为 accepted 时才能作为可接受降级。
- 对 `wiley` / `science` / `pnas`，正文 figure / table / formula 图片下载必须使用 shared Playwright browser context 主链路；每次 download attempt 只创建一次 context/page，多图复用，preview fallback 也必须通过同一个 context 获取。
- 如果违反，用户会看到：正文缺图、图像文件其实是 HTML，或者 live review 只能笼统报 `asset_download_failure`，看不出是 full-size 被拦截、preview 可接受，还是图片真的缺失。
- 它对应的阶段是：资产候选排序、图片下载、图片校验、文章模型资产诊断。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html)
  - [`../tests/fixtures/golden_criteria/10.1126_sciadv.aax6869/original.html`](../tests/fixtures/golden_criteria/10.1126_sciadv.aax6869/original.html)
  - [`../tests/fixtures/golden_criteria/10.1126_science.abb3021/original.html`](../tests/fixtures/golden_criteria/10.1126_science.abb3021/original.html)
  - 这些样本覆盖 PNAS / Science CMS 图片直接 HTTP 请求被 challenge 或只能拿到站点标记为 preview 的图片时，如何区分真实故障和可接受降级。
- 对应测试：
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_pnas_provider_download_related_assets_uses_shared_playwright_primary_path_before_preview`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_pnas_provider_downloads_preview_through_shared_playwright_when_no_full_size_candidate`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_wiley_provider_download_related_assets_uses_shared_playwright_primary_path`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_wiley_provider_download_related_assets_reuses_shared_playwright_fetcher_across_assets`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_science_provider_records_preview_dimensions_and_acceptance`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_science_provider_records_asset_failure_when_shared_playwright_preview_fails`
  - [`../tests/unit/test_science_pnas_provider.py`](../tests/unit/test_science_pnas_provider.py) 中的 `test_browser_workflow_download_related_assets_retries_after_partial_failures`
  - [`../tests/unit/test_service.py`](../tests/unit/test_service.py) 中的 `test_fetch_paper_accepts_preview_images_with_sufficient_dimensions`
  - [`../tests/unit/test_mcp.py`](../tests/unit/test_mcp.py) 中的 `test_article_payload_preserves_asset_download_diagnostics`
  - [`../tests/unit/test_golden_criteria_live.py`](../tests/unit/test_golden_criteria_live.py) 中的 `test_science_preview_accepted_is_not_an_asset_issue`
  - [`../tests/unit/test_golden_criteria_live.py`](../tests/unit/test_golden_criteria_live.py) 中的 `test_formula_only_preview_fallback_is_not_an_asset_issue`
  - [`../tests/unit/test_golden_criteria_live.py`](../tests/unit/test_golden_criteria_live.py) 中的 `test_non_formula_preview_fallback_remains_an_asset_issue`
- 边界说明：
  - `wiley` / `science` / `pnas` 不再把 Playwright 当作 HTTP 失败后的 canvas fallback；目标 provider 成功下载时应记录 `download_tier="full_size"` 或 `download_tier="preview"`。
  - `download_tier="preview"` 不是天然错误；当下载阶段判定 preview 尺寸满足阈值，并在 source trail 中记录 `download:*_assets_preview_accepted` 时，它是诊断标签，不应自动映射为 `asset_download_failure`。
  - formula-only preview fallback 是公式图片语义的降级呈现，不自动归为 `asset_download_failure`；figure/table preview fallback 仍按资产问题处理，除非已有 accepted 诊断。
  - 如果只有低尺寸 preview、图片缺失、或 `download:*_assets_preview_fallback` / `download:*_asset_failures` 出现在轨迹里，仍应保留资产问题信号。

<a id="rule-table-flatten-or-list"></a>
### 表格能展平就转 Markdown 表，展不平就退成可读列表

- 这条规则约束的是：表格如果只是多级表头、rowspan 这类还能讲清楚结构的复杂度，就要尽量展平成 Markdown 表；如果结构已经复杂到强行展平会误导，就退成清晰的列表说明。
- 如果违反，用户会看到：要么本来能读懂的表被糟糕地压扁成错列的 Markdown 表，要么复杂表直接丢信息，没有任何可读 fallback。
- 它对应的阶段是：表格清洗、Markdown 渲染。
- 规则 owner 是 `paper_fetch.providers._html_tables`；Science/PNAS/Wiley 和 Springer/Nature 的 table 注入只能通过这个模块渲染 matrix、rowspan/colspan、Markdown table 或 fallback 列表。
- 代表性 HTML / XML：
  - 当前无稳定 DOI 样本，直接见对应测试。
- 对应测试：
  - [`../tests/unit/test_science_pnas_postprocess_units.py`](../tests/unit/test_science_pnas_postprocess_units.py) 中的 `test_extract_science_pnas_markdown_flattens_multilevel_table_headers`
  - [`../tests/unit/test_science_pnas_postprocess_units.py`](../tests/unit/test_science_pnas_postprocess_units.py) 中的 `test_extract_science_pnas_markdown_flattens_rowspan_table_body_cells`
  - [`../tests/unit/test_science_pnas_postprocess_units.py`](../tests/unit/test_science_pnas_postprocess_units.py) 中的 `test_extract_science_pnas_markdown_falls_back_complex_table_to_bullets`
- 边界说明：
  - 这条规则不是要求所有表格最终都必须长成 Markdown 表。
  - 当结构已经超出安全展平范围时，退成列表是符合规则的正确结果，不是降级失败。

<a id="rule-stable-frontmatter-order"></a>
### 前言摘要族的顺序与去重必须稳定

- 这条规则约束的是：teaser、`Significance`、`Structured Abstract`、`Abstract` 这类前言摘要块一旦已经被识别出来，就必须在最终 markdown 里按阅读顺序稳定出现，不能重复注回正文；只有在确实需要把前言和正文切开时，才插入一次 `## Main Text`。
- 如果违反，用户会看到：同一段摘要在前言和正文里各出现一遍，或者 `Significance`、`Structured Abstract`、`Abstract` 顺序错乱，甚至正文开头被摘要块挤占。
- 它对应的阶段是：HTML 提取、共享 Markdown 规范化、文章组装、最终渲染。
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
- 它对应的阶段是：HTML / XML 提取、共享 abstract 归一化、文章组装、最终渲染。
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
### Data Availability 必须保留且不能重复

- 这条规则约束的是：`Data Availability`、`Data, Materials, and Software Availability` 这类内容一旦被识别为数据可用性声明，就必须作为独立结构节保留下来，而且最终输出里只能出现一次；它不能被误删、降成普通正文，也不能被 back matter 重复拼接。
- 如果违反，用户会看到：数据可用性声明完全消失，或者同一节在正文和附录里各来一遍。
- 它对应的阶段是：HTML 提取、节分类、最终渲染。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html)
  - 这个样本能证明 PNAS 的 `Data, Materials, and Software Availability` 需要单独保留且不能重复。
- 对应测试：
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_science_fixture_keeps_data_availability_but_filters_teaser_figure`
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_pnas_full_fixture_keeps_data_availability_and_renders_table_markdown`
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_pnas_collateral_data_availability_fixture_is_not_duplicated`
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_browser_workflow_returns_section_hints_for_structural_data_availability`
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_wiley_full_fixture_keeps_data_availability_but_filters_other_back_matter`
  - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_keeps_data_availability_without_counting_it_as_fulltext`
  - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_uses_section_hints_for_nonliteral_data_availability`
- 边界说明：
  - 这条规则不是要求所有 back matter 都必须保留；像 `Conflict of Interest`、`Supporting Information` 这类节仍然可以按各 provider 规则过滤。
  - 它只约束“已经被识别成 data availability 的内容”；如果上游只剩普通标题文本且没有结构信号，仍可能先按一般正文节处理。

<a id="rule-keep-headingless-body-flat"></a>
### 无节标题正文必须保持扁平

- 这条规则约束的是：当文章正文本来就直接以连续段落展开、没有可靠的 body heading 时，组装和渲染阶段不能人为包一层重复标题、`## Full Text` 或同义伪节；如果需要区分前言和正文，最多只插入一次 `## Main Text` 作为边界。
- 如果违反，用户会看到：commentary、perspective 这类文章被套上并不存在的章节壳，或者文章标题又在正文里重复出现一次。
- 它对应的阶段是：文章组装、最终渲染。
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
### 正文和表格里的行内语义格式不能被打平或拆裂

- 这条规则约束的是：正文段落、图表 caption 和 Markdown 表格单元格里已经识别出的上下标、斜体变量、变量下标等行内语义，不能在清洗或渲染时被打平成普通空格文本，也不能被错误地拆成断开的 token。
- 如果违反，用户会看到：`TCID<sub>50</sub>` 变成 `TCID50`，`*h*<sub>0</sub>` 变成 `h0`，或者 `*x*` 和 `<sub>i</sub>` 被拆散到两行，看起来像坏表格或坏公式。
- 它对应的阶段是：正文清洗、表格渲染、最终渲染。
- HTML inline normalization 的规则 owner 是 `paper_fetch.extraction.html.inline`；HTML body、heading 和 table cell 的空白、`sub`/`sup`、标点贴合必须通过 policy 表达，不能在 provider 模块复制 regex。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2406303121/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2406303121/original.html)
  - 这个样本能证明 PNAS 表格单元格和正文里的上下标、变量符号、单位格式需要保持原有行内语义。
- 对应测试：
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_pnas_full_fixture_keeps_data_availability_and_renders_table_markdown`
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_pnas_real_fixture_renders_table_and_inline_cell_formatting`
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_wiley_full_fixture_extracts_body_sections_from_real_html`
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_inline_normalization_is_shared_for_body_heading_and_table_text`
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_split_inline_variable_subscripts_are_rejoined_in_paragraphs`
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_inline_boundary_newlines_are_normalized`
- 边界说明：
  - 这条规则只约束已经识别成行内语义的内容，不承诺对复杂公式、整段 MathML 或所有数学符号做完整排版。
  - 它也不是说所有英文字母组合都必须自动识别成变量加下标。

<a id="rule-readable-equation-caption-spacing"></a>
### 公式块和图注句子的块间距必须可读

- 这条规则约束的是：`**Equation n.**` 和对应的 `$$...$$` display math 之间必须保持稳定的块级换行，公式后的解释句和 figure caption 的后续句子也不能被粘成一整块坏文本。
- 如果违反，用户会看到：`**Equation 1.**$$`、`$$where *P* is precipitation`、`2020.Time series` 这类明显粘连的坏渲染。
- 它对应的阶段是：共享 Markdown 后处理、最终渲染。
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

<a id="rule-preserve-formula-image-fallbacks"></a>
### HTML 公式图片 fallback 必须保留并进入资产链路

- 这条规则约束的是：HTML 中的 MathML、publisher fallback span、inline equation image 和 display equation image 要尽量转成可读公式；如果 MathML 无法转换或公式本来只以图片存在，就保留 `![Formula](...)`，并把它作为 `kind="formula"` 的正文资产候选进入下载和本地链接改写流程。
- 如果违反，用户会看到：公式静默消失、被渲染成 `[Formula unavailable]` 的假失败，或者正文里残留远程公式图片链接且无法跟下载资产对应。
- 它对应的阶段是：HTML 清洗、公式渲染、资产抽取、文章组装。
- HTML formula discovery 的规则 owner 是 `paper_fetch.extraction.html.formula_rules`；公式 URL pattern、container tokens、candidate image attrs、MathML extraction、display/inline 判断和 formula image detection 只能在这里维护。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.15322/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.15322/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_nature13376/original.html`](../tests/fixtures/golden_criteria/10.1038_nature13376/original.html)
  - 这两个样本分别覆盖 Wiley fallback formula image 和旧 Nature inline equation image。
- 对应测试：
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_wiley_formula_image_fallbacks_are_preserved`
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_wiley_inline_mathml_with_fallback_span_does_not_emit_placeholder`
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_wiley_display_formula_can_fall_back_to_alt_image_span`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_old_nature_fixture_preserves_inline_equation_images`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_old_nature_fixture_keeps_single_methods_summary_and_methods_sections`
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_formula_rules_detect_mathml_display_and_formula_image_urls`
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_extract_formula_assets_reuses_shared_formula_rules`
  - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_rewrites_inline_asset_urls_to_downloaded_paths`
- 边界说明：
  - 这条规则不是保证所有 HTML 公式都能转成 LaTeX；保留公式图片 fallback 是正确输出。
  - 只有看起来属于公式容器、公式 URL 或公式 alt/title 的图片才进入公式资产链路，普通正文图片仍按 figure/table 处理。

## Springer

- 共享规则另见：
  - [HTML fulltext / abstract-only 判定必须和用户可见访问状态一致](#rule-html-availability-contract)
  - [正文已内联 figure 时不再重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)
  - [标题和节标题里的上下标不能被打平成普通文本](#rule-preserve-subscripts-in-headings)
  - [HTML 公式图片 fallback 必须保留并进入资产链路](#rule-preserve-formula-image-fallbacks)

<a id="rule-springer-chrome-heading-normalization"></a>
### 文章根选择必须避开 Springer 站点 chrome，编号标题必须规范空格

- 这条规则约束的是：Springer / Springer Nature HTML 提取必须先选到可信 article root，再剪掉保存文章、期刊 CTA、Aims and scope、Submit manuscript、重复标题块、`About this article` / 权限许可等站点 chrome；同时由多个 inline span 拼出的编号标题必须渲染成带空格的真实标题，正文之外的科学 back matter 只保留 `Acknowledgements`、`Data Availability`、`Author Contributions` 这类论文内容节。
- 如果违反，用户会看到：多语言摘要和正文之间插入 `Save article`、`View saved research`、重复论文标题、Creative Commons 许可长文，或者 `## 1Introduction`、`### 3.1Glaciers` 这类粘连标题。
- 它对应的阶段是：HTML article-root 选择、站点 chrome 剪枝、节标题规范化、科学 back matter 拼接。
- `springer_nature` 是显式注册的 shared noise profile；Springer/Nature 调用 shared Markdown cleanup 时不得静默回退到 generic profile。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html`](../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html)
  - [`../tests/fixtures/golden_criteria/10.1007_s13158-025-00473-x/bilingual.html`](../tests/fixtures/golden_criteria/10.1007_s13158-025-00473-x/bilingual.html)
  - 这两个样本分别覆盖 Springer classic 编号标题 / chrome 泄漏，以及双语摘要后进入正文时不能重复标题和 CTA。
- 对应测试：
  - [`../tests/unit/test_springer_html_tables.py`](../tests/unit/test_springer_html_tables.py) 中的 `test_springer_classic_fixture_strips_chrome_and_spaces_numbered_headings`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_springer_markdown_spaces_numbered_inline_heading_spans`
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_springer_bilingual_fixture_enters_body_without_duplicate_title_or_cta`
  - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_clean_markdown_registers_springer_nature_profile`
- 边界说明：
  - 这条规则过滤的是站点框架和操作入口，不是删除论文正文里自然出现的相同词面。
  - 它不要求所有编号标题都改写成某个统一编号体系，只要求已存在的编号和标题文本不能粘连或重复。

### Springer 原始 article HTML 必须按下载目录形态稳定落盘

- 这条规则约束的是：当 Springer 抓取链拿到 publisher article HTML 时，`ArtifactStore` 必须把可信的原始正文 HTML 单独落盘；如果 `download_dir` 本身就是 DOI slug 文章目录，文件名是 `original.html`，否则文件名是 `<doi_slug>_original.html`。
- 如果违反，用户会看到：找不到统一的原文源文件，或者把 `*_assets/` 里的 figure page、redirect page、辅助 HTML 误当成正文原文。
- 它对应的阶段是：原始抓取落盘。
- 代表性 HTML / XML：
  - 当前无稳定 DOI 样本，直接见对应测试。
- 对应测试：
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_springer_html_route_saves_original_html_in_article_dir`
- 边界说明：
  - 这条规则不是说 `*_assets/` 目录里绝对不能有 HTML 文件。
  - 它约束的是“可信原文源文件的稳定落点”，不是限制辅助页面的存在。

### 访问提示、预览语和 AI 免责声明不能混进正文

- 这条规则约束的是：publisher 页面用来告诉用户“这里只是预览”“这是访问提示”“这段 alt 可能由 AI 生成”的站点说明，不能被当成论文正文或摘要输出。
- 如果违反，用户会看到：摘要或正文里多出 `This is a preview of subscription content`、`The alternative text for this image may have been generated using AI.` 这类明显不是论文内容的提示句。
- 它对应的阶段是：HTML 提取、正文清洗。
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
- 它对应的阶段是：figure 文本抽取、最终渲染。
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

<a id="rule-springer-methods-summary"></a>
### 旧 Nature 的 Methods Summary / Methods 结构必须归一且不重复

- 这条规则约束的是：旧 Nature 文章里如果同时存在 `Methods Summary` 和 `Online Methods` / `Methods`，最终结构必须归一成“`Methods Summary` 一次、`Methods` 一次”，不能重复堆出两个同义方法章节。
- 如果违反，用户会看到：文档里出现两个 `Methods Summary`，或者 `Online Methods`、`Methods` 混着出现，方法学结构会看起来像重复拼装。
- 它对应的阶段是：HTML 结构归一、文章组装、最终渲染。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1038_nature12915/original.html`](../tests/fixtures/golden_criteria/10.1038_nature12915/original.html)
  - 这个样本能证明旧 Nature 的 `Methods Summary` 与 `Online Methods` 需要按正文结构归一处理。
- 对应测试：
  - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_old_nature_fixture_keeps_single_methods_summary_and_methods_sections`
  - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_promotes_repeated_methods_summary_to_methods`
- 边界说明：
  - 这条规则不是要求所有论文都必须出现 `Methods Summary`。
  - 它约束的是旧 Nature 这类结构已经被识别出来时，最终用户可见结构不能重复，也不能把 `Online Methods` 原样保留成一个平行重复节。

<a id="rule-springer-inline-table"></a>
### 正文内联 table 占位必须被真实表格替换，替不出来也不能把占位符漏给用户

- 这条规则约束的是：正文里如果先放了一个 table 占位，后续拿到 table page 时要把真实表格插回原位置；如果 table page 最终没拿到真正的表，也不能把内部占位符直接漏给用户。对于旧 Nature Extended Data Table，若 table page 实际是图片或只能拿到图片跳转，应输出 table 图片；若解析失败，应输出明确的 `[Table body unavailable: ...]` 降级占位。
- 如果违反，用户会看到：正文里残留像 `PAPER_FETCH_TABLE_PLACEHOLDER` 这样的内部标记，Extended Data Table 直接消失，或者文章因为某个 table page 没拿到表就整体变成异常结果。
- 它对应的阶段是：HTML 提取、table page 注入、table 图片 fallback、最终渲染。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/original.html`](../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/table1.html`](../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/table1.html)
  - [`../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html`](../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html)
  - [`../tests/fixtures/golden_criteria/10.1038_nature13376/original.html`](../tests/fixtures/golden_criteria/10.1038_nature13376/original.html)
  - 这几份样本分别覆盖“真实 Nature table page 被注回正文”、“Springer classic article 遇到坏 table page 也不能把占位符漏给用户”，以及旧 Nature Extended Data Table 图片 / 占位降级。
- 对应测试：
  - [`../tests/unit/test_springer_html_tables.py`](../tests/unit/test_springer_html_tables.py) 中的 `test_render_table_markdown_handles_real_springer_classic_table_page`
  - [`../tests/unit/test_springer_html_tables.py`](../tests/unit/test_springer_html_tables.py) 中的 `test_springer_html_injects_real_nature_inline_table_page_with_flattened_headers`
  - [`../tests/unit/test_springer_html_tables.py`](../tests/unit/test_springer_html_tables.py) 中的 `test_springer_html_keeps_article_success_when_inline_table_page_has_no_table`
  - [`../tests/unit/test_springer_html_tables.py`](../tests/unit/test_springer_html_tables.py) 中的 `test_old_nature_extended_data_tables_render_table_image_or_degraded_placeholder`
- 边界说明：
  - 这条规则不是要求所有 table page 都必须成功转出表格。
  - 它约束的是“成功时正确注回，失败时不把内部占位符暴露给用户，也不让整篇文章失败”；当原始站点只提供表格图片时，图片 fallback 是正确输出，不是图表丢失。

## Elsevier

- Elsevier XML 元素级映射总表另见 [`../references/elsevier_markdown_mapping.md`](../references/elsevier_markdown_mapping.md)；下面只保留当前主干必须维持的用户可见 Markdown 行为约束。
- 共享规则另见：
  - [Provider 自有作者与前言信号必须进入最终文章元数据且不能重复](#rule-provider-owned-authors)
  - [并行多语言摘要要并存，单语非英文正文不能被误删](#rule-keep-parallel-multilingual-abstracts)
  - [正文和表格里的行内语义格式不能被打平或拆裂](#rule-preserve-inline-semantics-in-body-and-tables)
  - [正文已内联 figure 时不再重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)
  - [已下载的正文图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links)

<a id="rule-elsevier-formula-rendering"></a>
### 正文内联公式与 display formula 分开渲染，失败时给可见占位和 conversion notes

- 这条规则约束的是：段落里的行内数学要留在正文行内，display formula 要单独渲染成公式块；如果某个公式最终无法转换，也必须给用户一个可见占位，并在 conversion notes 里留下明确痕迹。MathML `mtext` 里出版商转义的标识符下划线也要窄范围修复，不能渲染成 `\textbackslash\_`；出版商输出的 `\updelta` 这类 upright Greek 宏和 `\mspace{Nmu}` 也要规范化成 KaTeX 可渲染的 LaTeX。
- 如果违反，用户会看到：段落里的单字母变量被误渲染成一串独立公式块，某个公式直接静默消失，或者 `M\_NDVI` 这类变量显示成 `M\textbackslash\_NDVI`。
- 它对应的阶段是：XML 提取、公式转换、最终渲染。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml)
  - [`../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2023.130125/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2023.130125/original.xml)
  - 这些 real Elsevier XML 分别覆盖 display formula 渲染为公式块，以及 MathML `mtext` 中转义下划线的修复。
- 对应测试：
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_formula_rendering_contracts`
  - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_repairs_identifier_escaped_underscores`
  - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_does_not_globally_replace_textbackslash`
  - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_rewrites_upgreek_macros`
  - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_rewrites_mspace_for_katex`
  - 这个公共测试以 real XML 锁定 display formula 主干，并保留 synthetic 子场景覆盖 inline math 与 formula failure 这两类当前无稳定 DOI 的边界分支。
- 边界说明：
  - 这条规则不是保证所有 Elsevier MathML 都能被完美转成 LaTeX。
  - 它约束的是“行内和 display 数学不能混渲，失败时不能静默丢失”，以及只修复夹在标识符字符之间的 `\textbackslash\_`；不能全局替换正常文本里的 `\textbackslash`。`\mspace{Nmu}` 只在 `mu` 单位时改写为 `\mkernNmu`，其它单位保留原样。

<a id="rule-elsevier-supplementary-materials"></a>
### Supplementary data 不进正文，统一收进 `## Supplementary Materials`

- 这条规则约束的是：`Supplementary data` 这类补充材料显示块不能混进正文叙述里，而是要统一落到文末的 `## Supplementary Materials` 区域，并保留基本的标题和说明。
- 如果违反，用户会看到：正文突然插进一个补充材料下载入口，或者补充材料完全消失。
- 它对应的阶段是：XML 提取、资产归类、最终渲染。
- 代表性 HTML / XML：
  - 当前无稳定 DOI 样本，直接见对应测试。
- 对应测试：
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_supplementary_display_is_omitted_from_body_and_listed_with_caption`
- 边界说明：
  - 这条规则不是说 supplementary 资产不能下载或不能暴露给用户。
  - 它约束的是“补充材料不属于正文主体”，不是限制 supplementary 元数据的存在。

<a id="rule-elsevier-appendix-context"></a>
### Appendix figure/table 保持 appendix 语境，不因正文交叉引用被提到正文

- 这条规则约束的是：凡是已经处在 appendix 语境里的 figure 和 table，就要继续留在 appendix 里渲染；即使正文提到 `Fig. A1` 或 `Table A1`，也不能把这些 appendix 资产提前到正文区。
- 如果违反，用户会看到：正文里突然混入 appendix 图表，或者 appendix 内容被拆散后前后顺序错乱。
- 它对应的阶段是：XML 提取、文章组装、最终渲染。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.rse.2026.115369/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.rse.2026.115369/original.xml)
  - 这份 real Elsevier XML 同时覆盖 appendix figure、appendix table 和正文中的 appendix 交叉引用。
- 对应测试：
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_appendix_context_contracts`
  - 这个公共测试内部的 real 子场景分别锁定 appendix figure/table 的渲染位置和正文交叉引用的顺序关系。
- 边界说明：
  - 这条规则不是说正文里不能出现对 appendix 图表的交叉引用文字。
  - 它约束的是 appendix 资产的实际渲染位置和上下文，而不是正文文字是否能提到它们。

<a id="rule-elsevier-table-placement"></a>
### 正文引用到的 figure / table 要就地插回；已消费图表不得再追加；复杂 span 表保留语义展开和降级标记

- 这条规则约束的是：正文里已经引用到的 figure / table 要尽量在引用位置附近渲染；已经在正文消费过的图表必须通过 render state 或 consumed key 从尾部资产附录里过滤掉；没有正文锚点的浮动表进入 `## Additional Tables`。遇到 rowspan / colspan / `namest` / `nameend` / `morerows` 这类复杂结构时，优先输出带 conversion notes 的语义展开 Markdown 表，并把质量标记为 `table_layout_degraded`，不能把“版式无法无损表达”误报成“语义内容丢失”。
- 如果违反，用户会看到：正文提到 `Fig. 1` 或 `Table 1` 却找不到对应图表，正文已经有的表在文末又以只有 caption 的 `## Tables` 重复出现，或者复杂表直接变成一张图 / 空摘要，无法被 AI 和用户继续读取。
- 它对应的阶段是：XML 提取、图表组装、文章模型资产计划、最终渲染、质量标记。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2021.126210/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2021.126210/original.xml)
  - [`../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml)
  - [`../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2023.130125/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2023.130125/original.xml)
  - [`../tests/fixtures/golden_criteria/10.1016_j.rse.2024.114346/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.rse.2024.114346/original.xml)
  - 这些 real Elsevier XML 是 live review 中暴露图表二次组装和复杂表格质量标记问题的四篇样本，覆盖正文图片插入、正文表格就地插回、已消费表格不再尾部重复，以及 span 表的语义展开。
- 对应测试：
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_table_placement_contracts`
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_article_from_structure_preserves_inline_elsevier_figures`
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_complex_table_spans_are_semantically_expanded`
  - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_to_ai_markdown_skips_inline_assets_and_labels_additional_tables`
  - 这些测试以 real XML 锁定正文 table placement 主干，并保留 synthetic 子场景覆盖当前无稳定 DOI 的 unreferenced float、inline figure 保留和 render-state 过滤分支。
- 边界说明：
  - 这条规则不是要求复杂表在 Markdown 里必须零损失复原。
  - 它约束的是“优先给用户可读的图表文本、正文位置和降级提示”，不是承诺所有单元格跨度都能无损还原。
  - `table_layout_degraded` 表示 Markdown 版式无法表达真实合并单元格；只有行列语义内容真的丢失时，才应升级为 `table_semantic_loss` / `figure_table_loss`。

<a id="rule-elsevier-xml-references"></a>
### Elsevier XML 参考文献必须优先使用结构化 bibliography，保持编号和作者信息

- 这条规则约束的是：Elsevier XML 里存在 `<ce:bibliography>` / `<ce:bib-reference>` / `<sb:reference>` 时，文章模型的 `references` 必须优先从这些结构化节点构建，保留原始顺序、编号、作者、标题、来源、页码、年份和 DOI；字段缺失时必须回退到 visible raw reference text 或显式 `[Reference text unavailable]`，不能直接跳过 bib 条目。Crossref metadata references 只能作为兜底。
- 如果违反，用户会看到：参考文献从 `1. A. Anav, P. Friedlingstein...` 退化成没有作者、没有编号的 bullet，如 `- Remote sensing of drought: Progress, challenges and opportunities`，或者 XML 里存在的 bib 条目在最终 references 中消失。
- 它对应的阶段是：XML bibliography 解析、文章模型组装、References 渲染。
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
- 它对应的阶段是：资产归类、最终渲染。
- 代表性 HTML / XML：
  - 当前无稳定 DOI 样本，直接见对应测试。
- 对应测试：
  - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_graphical_abstract_assets_do_not_appear_in_additional_figures`
- 边界说明：
  - 这条规则不是说 graphical abstract 必须从所有输出里彻底删除。
  - 它约束的是 graphical abstract 不能被误归到正文 figure 附录里。

## Wiley

- 共享规则另见：
  - [HTML fulltext / abstract-only 判定必须和用户可见访问状态一致](#rule-html-availability-contract)
  - [Provider 自有作者与前言信号必须进入最终文章元数据且不能重复](#rule-provider-owned-authors)
  - [保留语义父节标题](#rule-keep-semantic-parent-heading)
  - [并行多语言摘要要并存，单语非英文正文不能被误删](#rule-keep-parallel-multilingual-abstracts)
  - [Data Availability 必须保留且不能重复](#rule-keep-data-availability-once)
  - [正文已内联 figure 时不再重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)
  - [正文和表格里的行内语义格式不能被打平或拆裂](#rule-preserve-inline-semantics-in-body-and-tables)
  - [已下载的正文图片和公式图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links)
  - [图片下载必须验证真实图片、保留 tier 和尺寸诊断](#rule-image-download-tier-diagnostics)
  - [HTML 公式图片 fallback 必须保留并进入资产链路](#rule-preserve-formula-image-fallbacks)

<a id="rule-wiley-abbreviations-trailing"></a>
### Abbreviations 只在正文后保留，不得提前打断正文结构

- 这条规则约束的是：如果 Wiley 页面里存在 `Abbreviations` 区块，它可以作为正文后的辅助节保留，但不能提前到正文主线前面，也不能插进正文章节和正文表格中间打断阅读顺序。
- 如果违反，用户会看到：文章还没进入主体内容，`Abbreviations` 就先冒出来，或者它把正文叙述和正文表格硬切成两段。
- 它对应的阶段是：HTML 提取、文章组装、最终渲染。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1111_cas.16395/original.html`](../tests/fixtures/golden_criteria/10.1111_cas.16395/original.html)
  - 这个样本能证明 `Abbreviations` 可以保留，但只能放在正文和正文表格之后。
- 对应测试：
  - [`../tests/unit/test_science_pnas_postprocess.py`](../tests/unit/test_science_pnas_postprocess.py) 中的 `test_wiley_real_fixture_appends_abbreviations_after_body_content`
- 边界说明：
  - 这条规则不是要求所有 Wiley 文章都必须输出 `Abbreviations`。
  - 它约束的是“存在该区块时的落点”，不是强制生成一个缺失的缩写表。

<a id="rule-wiley-reference-text"></a>
### Wiley 参考文献必须使用可见 citation 文本而不是 DOI-only 或链接 chrome

- 这条规则约束的是：Wiley HTML references 要从可见 citation body 中抽取作者、题名、期刊等文本，删除 `Google Scholar`、`Crossref`、`getFTR` 和隐藏链接区，不能把 DOI-only 链接当成完整 reference。
- 如果违反，用户会看到：参考文献只剩 DOI，或者每条 reference 后面混进一串站点跳转和检索入口。
- 它对应的阶段是：HTML references 抽取、站点链接噪声过滤。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.15322/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.15322/original.html)
- 对应测试：
  - [`../tests/unit/test_science_pnas_markdown.py`](../tests/unit/test_science_pnas_markdown.py) 中的 `test_wiley_references_use_visible_citation_text_not_doi_only`
- 边界说明：
  - 这条规则只过滤 publisher reference chrome，不会补全原始 HTML 中没有的 bibliographic 字段。

## Science

- 共享规则另见：
  - [HTML fulltext / abstract-only 判定必须和用户可见访问状态一致](#rule-html-availability-contract)
  - [Provider 自有作者与前言信号必须进入最终文章元数据且不能重复](#rule-provider-owned-authors)
  - [保留语义父节标题](#rule-keep-semantic-parent-heading)
  - [前言摘要族的顺序与去重必须稳定](#rule-stable-frontmatter-order)
  - [并行多语言摘要要并存，单语非英文正文不能被误删](#rule-keep-parallel-multilingual-abstracts)
  - [Data Availability 必须保留且不能重复](#rule-keep-data-availability-once)
  - [无节标题正文必须保持扁平](#rule-keep-headingless-body-flat)
  - [标题和节标题里的上下标不能被打平成普通文本](#rule-preserve-subscripts-in-headings)
  - [正文和表格里的行内语义格式不能被打平或拆裂](#rule-preserve-inline-semantics-in-body-and-tables)
  - [正文已内联 figure 时不再重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)
  - [已下载的正文图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links)
  - [图片下载必须验证真实图片、保留 tier 和尺寸诊断](#rule-image-download-tier-diagnostics)
  - [表格能展平就转 Markdown 表，展不平就退成可读列表](#rule-table-flatten-or-list)
  - [公式块和图注句子的块间距必须可读](#rule-readable-equation-caption-spacing)
  - [HTML 公式图片 fallback 必须保留并进入资产链路](#rule-preserve-formula-image-fallbacks)

## PNAS

- 共享规则另见：
  - [HTML fulltext / abstract-only 判定必须和用户可见访问状态一致](#rule-html-availability-contract)
  - [Provider 自有作者与前言信号必须进入最终文章元数据且不能重复](#rule-provider-owned-authors)
  - [前言摘要族的顺序与去重必须稳定](#rule-stable-frontmatter-order)
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)
  - [Data Availability 必须保留且不能重复](#rule-keep-data-availability-once)
  - [无节标题正文必须保持扁平](#rule-keep-headingless-body-flat)
  - [正文和表格里的行内语义格式不能被打平或拆裂](#rule-preserve-inline-semantics-in-body-and-tables)
  - [正文已内联 figure 时不再重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)
  - [已下载的正文图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links)
  - [图片下载必须验证真实图片、保留 tier 和尺寸诊断](#rule-image-download-tier-diagnostics)
  - [表格能展平就转 Markdown 表，展不平就退成可读列表](#rule-table-flatten-or-list)
  - [公式块和图注句子的块间距必须可读](#rule-readable-equation-caption-spacing)
  - [HTML 公式图片 fallback 必须保留并进入资产链路](#rule-preserve-formula-image-fallbacks)

## 使用建议

- 新增回归测试时，优先把规则写成行为约束，再用 DOI 级样本去证明它。
- 做 root-cause 排障时，先判断问题是在 HTML 提取、文章组装、资产清洗，还是最终渲染阶段，再决定该把证据补到哪条规则下。
- 后续如果要补“既有规则”，继续沿用同一模板，不要把 incident 记录直接搬进这里。
