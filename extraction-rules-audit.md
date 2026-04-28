# `docs/extraction-rules.md` 重复 / 冗余 / 被取代规则审计

本报告分析 `docs/extraction-rules.md` 当前内容，按"重复/冗余"和"被取代/可合并"分类列出问题点，并给出可在文档里直接落地的处理建议。

> 第一轮审计聚焦于"重复 / 被取代"（§1–§6），第二轮审计补充结构性、命名、边界和耦合问题（§7–§23），第三轮审计聚焦规则与代码/测试的一致性、覆盖盲点与演进可维护性（§24–§40）。

## 1. 明显重复：上下标规则一分为二（建议合并）

- **`rule-preserve-subscripts-in-headings`**（line 177）"标题和节标题里的上下标不能被打平成普通文本"
- **`rule-preserve-inline-semantics-in-body-and-tables`**（line 372）"正文和表格里的行内语义格式不能被打平或拆裂"

两条规则有强重叠：

- 第二条的 owner 段（line 378）已经显式说 "HTML **body、heading** 和 table cell 的空白、`sub`/`sup`、标点贴合必须通过 policy 表达"——heading sub/sup 已经在第二条管辖范围里。
- 共享测试 `test_inline_normalization_is_shared_for_body_heading_and_table_text` 直接证明了两者背后是同一套 inline normalization policy。
- 第一条单独存在的唯一独特点是 frontmatter 摘要里的 sub/sup（如 `test_extract_science_pnas_markdown_normalizes_title_subscript_line_breaks`），但 frontmatter 也属于"已识别为行内语义"的范畴。

**建议**：把"标题和节标题里的上下标"作为第二条规则的一个子情境合并进去（"已识别成行内语义的内容（包含 frontmatter / heading / 正文 / 表格 cell）"），保留 anchor `rule-preserve-subscripts-in-headings` 作为重定向。

## 2. 抽象去重职责被切两半（建议归口）

- **`rule-provider-owned-authors`**（line 156）"可见结果里不能出现空作者、错摘要或**重复摘要块**"
- **`rule-stable-frontmatter-order`**（line 269）"前言摘要族的顺序与去重必须稳定"

两条都管 abstract dedup。`rule-provider-owned-authors` 的核心其实只是"已识别的 provider-owned signals 要稳定进入文章模型"；"重复摘要"这块属于 frontmatter 顺序/去重职责。

**建议**：`rule-provider-owned-authors` 只保留"作者与摘要写入"语义，把"重复摘要块"明确划归 `rule-stable-frontmatter-order`，避免两个 anchor 都对同一种用户可见现象立约束。

## 3. 站点 UI 噪声 vs caption precedence vs preview/AI 免责（边界已定，但容易漂移）

- **Generic `rule-filter-publisher-ui-noise`**（line 86）：管 `Open in figure viewer`、`PowerPoint`、`Sign up for PNAS alerts` 等 UI 噪声；自述边界说"preview sentence 和 AI alt disclaimer 属于单独的访问提示规则"。
- **Springer `rule-springer-caption-precedence`**（line 508）：管 caption fallback，提到 `PowerPoint slide`、`Full size image`。
- **Springer "访问提示、预览语和 AI 免责声明不能混进正文"**（line 492，无 anchor）：单独管 preview sentence / AI disclaimer。

三条规则的过滤词面在 `PowerPoint` / `Full size image` 上有交叠：Generic 用"操作词 denylist"，Springer 用"caption 优先级"。逻辑不重复（一个删词，一个换源），但读者会以为重复。

**建议**：

- 给 line 492 那条加 anchor（如 `rule-springer-access-hint-disclaimer`），方便交叉引用。
- 在 `rule-springer-caption-precedence` 的边界说明里点明"`PowerPoint slide` 这类控件文案的过滤兜底由 `rule-filter-publisher-ui-noise` 处理；本规则只负责 caption 来源选择"。

## 4. 范围越界：一条规则不属于"提取与渲染"

**Springer "原始 article HTML 必须按下载目录形态稳定落盘"**（line 479，无 anchor）

这条约束的是 `ArtifactStore` 的落盘文件名形态，对应阶段是"原始抓取落盘"。文档开头明确写：

> 这份文档不解决：provider 路由、运行时限速、环境变量和**部署细节**

落盘形态属于 IO/artifact storage，不属于"提取/组装/渲染"任一阶段。

**建议**：把这条移到 `providers.md` 或一个 artifact-store 文档；如果要留，放进 `architecture/target-architecture.md`，不放在 extraction-rules。

## 5. 同一条规则在不同 provider 区里标题被截断（小问题）

Generic 规则原标题：**"已下载的正文图片和公式图片要改写成正文附近的本地链接"**（line 195）

但在 Elsevier（line 578）、Science（line 741）、PNAS（line 758）的"共享规则另见"里都被写作 **"已下载的正文图片要改写成正文附近的本地链接"**（少了"和公式图片"）。Wiley（line 696）正确。

**建议**：把 Elsevier/Science/PNAS 三处的链接文本同步成完整标题，避免"看上去像不同规则"。

## 6. 跨 provider 适用但只挂在 Springer 下（潜在被取代/应提升）

- `rule-springer-caption-precedence`（caption 优先级 / data-title / alt fallback）：同样适用于 Wiley、Science、PNAS（这些 provider 的 figure 也会出现 alt / data-title 噪声），但目前只挂在 Springer 节下。
- `rule-springer-access-hint-disclaimer`（line 492，preview / AI disclaimer）：理论上 Wiley 也存在 preview sentence 类噪声。

不算"重复"，但属于"应该往 Generic 提升"的候选。如果未来给 Wiley 加同名规则，就会出现真正的重复。

**建议**：这两条若要扩展到其他 provider，下次重构时直接提升进 Generic，而不是在 Wiley/Science 节下复制。

---

## 总结

真正建议立刻动手的：

| 类型 | 处理 |
| --- | --- |
| **可合并**（重复） | 把 `rule-preserve-subscripts-in-headings` 合并进 `rule-preserve-inline-semantics-in-body-and-tables` |
| **职责漂移** | `rule-provider-owned-authors` 只留 author/abstract 写入，重复摘要去重交给 `rule-stable-frontmatter-order` |
| **范围越界** | line 479 的"原始 article HTML 落盘"规则迁出本文档 |
| **小修** | 给 line 492 规则加 anchor；统一三处规则交叉引用文本 |

建议先做"小修"（加 anchor、统一交叉引用文本），合并和职责调整需要更动测试归属，建议单独一轮。

---

# 第二轮：结构 / 命名 / 边界耦合层面的问题

## 7. 缺少 anchor 的规则破坏文档可链接性

document 中所有规则原则上都带 `<a id="rule-...">`，但有两条没有：

- line 479 "Springer 原始 article HTML 必须按下载目录形态稳定落盘"
- line 492 "访问提示、预览语和 AI 免责声明不能混进正文"

后果：

- 其他规则的边界说明无法 link 到这两条。例如 `rule-filter-publisher-ui-noise`（line 108–109）边界说明明确写"preview sentence 和 AI alt disclaimer 属于单独的访问提示规则"，但因为 line 492 没有 anchor，这句话只能口头描述，无法跳转。
- 落盘那条本身已建议迁出本文档（见 §4），但只要还在 doc 里就应有 anchor。

**建议**：分别加上 `rule-springer-original-html-artifact` 和 `rule-springer-access-hint-disclaimer`。

## 8. Provider 区"共享规则另见"列表手工维护，列漏不一致

各 provider 节顶部的"共享规则另见"列表是手工维护的，存在以下不一致：

| Generic 规则 | Springer | Elsevier | Wiley | Science | PNAS |
| --- | --- | --- | --- | --- | --- |
| `rule-html-availability-contract` | ✓ | — | ✓ | ✓ | ✓ |
| `rule-stable-frontmatter-order` | — | — | — | ✓ | ✓ |
| `rule-table-flatten-or-list` | — | — | — | ✓ | ✓ |
| `rule-readable-equation-caption-spacing` | — | — | — | ✓ | ✓ |
| `rule-keep-headingless-body-flat` | — | — | — | ✓ | ✓ |
| `rule-keep-data-availability-once` | — | — | ✓ | ✓ | ✓ |
| `rule-rewrite-inline-figure-links` | — | ✓ | ✓ | ✓ | ✓ |
| `rule-image-download-tier-diagnostics` | — | — | ✓ | ✓ | ✓ |

具体疑点：

- **Springer 节没有列任何 figure download / inline link rewrite 规则**，但 Springer/Nature 也下载图片并改写本地链接（`rule-rewrite-inline-figure-links` 的测试 `test_rewrite_inline_figure_links_is_data_driven_for_non_legacy_publisher` 就涵盖非 legacy publisher）。要么是漏列，要么是 Springer 走另一条链路（应在文档说明）。
- **Wiley 节没有列 `rule-stable-frontmatter-order`**，但该规则下的测试 `test_wiley_provider_deduplicates_near_matching_abstract_in_final_article_render` 直接是 Wiley 测试。属于明显漏列。
- **Elsevier 节没有列 `rule-html-availability-contract` 和 `rule-keep-data-availability-once`**：前者合理（Elsevier 走 XML，不做 HTML availability），后者不合理（`test_elsevier_golden_fixture_classifies_data_and_code_availability_sections` 就在该规则下）。

**建议**：要么由脚本基于"该规则的测试是否触及该 provider"自动生成共享列表，要么至少一次性补齐当前漏列；同时在文档前言说明列表生成方式。

## 9. anchor 命名前缀不统一

- 大部分 provider 规则使用 `rule-<provider>-...`：`rule-springer-...`、`rule-elsevier-...`、`rule-wiley-...`。
- 但 `rule-nature-main-content-direct-children` 出现在 Springer 节下却用 `nature-` 前缀；其他 Springer 节规则用 `springer-` 前缀。
- 同时 generic 规则**没有**统一前缀（如 `rule-generic-...`），混用 `rule-keep-...`、`rule-no-...`、`rule-html-...`、`rule-preserve-...`、`rule-filter-...`。

**建议**：

- 锁定一种前缀方案：要么"区域 + 行为"（`rule-generic-keep-semantic-parent-heading`），要么"行为词起首"（去掉 nature 等子前缀，统一到 `rule-springer-main-content-direct-children`）。
- 当前有两种风格混用，未来重命名成本高。

## 10. 单条规则承担多条独立行为约束（违反"一规则一行为"模板）

模板要求"用行为级表述命名"，但以下规则其实是 N 条规则被拼在一个 anchor 下：

- **`rule-elsevier-table-placement`**（line 632）：标题"正文引用到的 figure / table 要就地插回；已消费图表不得再追加；复杂 span 表保留语义展开和降级标记" — 三个分号 = 三条约束。
  1. 正文引用图表就地插回。
  2. 已消费图表不得再追加（dedup）。
  3. 复杂 span 表保留语义展开 + 降级标记。
- **`rule-springer-chrome-heading-normalization`**（line 445）：chrome 剪枝 + 编号标题空格规范化是两件不相关的事。
- **`rule-image-download-tier-diagnostics`**（line 220）：实际包含
  1. 不能把 challenge HTML / chrome / 图标当图片。
  2. 必须记录 download_tier 等诊断字段。
  3. preview 阈值与 accepted 标记。
  4. Wiley/Science/PNAS 必须使用 shared Playwright context 主链路（provider-specific 实现细节）。
  5. Cloudflare challenge 时优先从已加载 `<img>` 导出 PNG（恢复链路细节）。
- **`rule-keep-data-availability-once`**（line 317）：除"保留 + 不重复"外，还附带 4 条不同概念约束（标题归类映射、不计入 body metrics、SectionHint dataclass 适配层、back matter/auxiliary 二级归类）。
- **`rule-elsevier-formula-rendering`**（line 580）：行内 vs display 分渲 + 失败占位 + `\textbackslash\_` 修复 + `\updelta` 上立宏 + `\mspace{Nmu}` 改写 — 5 个 sub-rule。

**建议**：每条拆分。否则：

- 修任一子约束都要碰大块文档；
- "代表性 HTML/XML"和"对应测试"块成了大杂烩，无法对应单一 sub-behavior；
- 边界说明里堆叠多个例外，反而不可读。

## 11. Generic 规则里夹带 provider-specific 行为约束

`Generic` 章节自述"跨 provider 共享的提取/渲染规则"，但以下条目中嵌入了硬编码 provider 名：

- `rule-html-availability-contract`（line 133）："Science / PNAS / Wiley 的 browser workflow 通过 selection policy 传入 browser-workflow 评分..."
- `rule-image-download-tier-diagnostics`（line 224）："对 `wiley` / `science` / `pnas`，正文 figure / table / formula 图片下载必须使用 shared Playwright browser context 主链路"
- `rule-image-download-tier-diagnostics`（line 246）：再次只针对 `wiley` / `science` / `pnas`。

**建议**：要么提升成 generic 行为约束（不点名 provider，统一描述"使用浏览器主链路下载图片的 provider 必须..."），要么把这一段 sub-rule 移到对应 provider 节。当前"generic 规则名 + provider 名嵌入正文"会给读者造成"哪些规则真正是 generic"的认知混乱。

## 12. 阶段标签自由命名，无清单可枚举

模板要求每条规则写"它对应的阶段是……"。但实际出现的阶段名没有受控清单，目前至少有 30 种写法（部分相同概念用不同名称）：

- "HTML 提取" / "HTML article-root 选择" / "HTML 清洗" / "正文清洗" / "标题提取"
- "节标题渲染" / "节分类" / "section hints"
- "文章组装" / "图表组装" / "公式渲染" / "公式转换"
- "资产抽取" / "资产清洗" / "资产匹配" / "资产候选排序" / "资产归类"
- "图片下载" / "图片校验" / "table page 注入" / "table 图片 fallback"
- "共享 Markdown 后处理" / "共享 Markdown 规范化" / "共享 abstract 归一化"
- "落盘改写" / "原始抓取落盘"
- "metadata 抽取" / "provider 前置清洗" / "前言清洗"
- "质量标记" / "文章模型资产诊断" / "References 渲染"

后果：

- 想反查"哪些规则约束 'figure 资产清洗' 阶段"无法直接 grep。
- 同一个阶段的不同写法（"资产清洗" vs "资产抽取" vs "资产归类"）让读者无法判断是同一阶段还是不同阶段。

**建议**：在文档前言加"阶段术语清单"，把每条规则的"对应阶段"约束到清单里的一个或多个 token。

## 13. owner 模块字段写得有的有、有的没有

显式标注 owner 模块的规则：

- `rule-html-availability-contract` → `paper_fetch.quality.html_availability`
- `rule-rewrite-inline-figure-links` → `paper_fetch.extraction.html.figure_links`
- `rule-table-flatten-or-list` → `paper_fetch.providers._html_tables`
- `rule-keep-data-availability-once` → `paper_fetch.extraction.section_hints`
- `rule-preserve-inline-semantics-in-body-and-tables` → `paper_fetch.extraction.html.inline`
- `rule-preserve-formula-image-fallbacks` → `paper_fetch.extraction.html.formula_rules`
- `rule-springer-chrome-heading-normalization` → `springer_nature` shared noise profile

其他规则均无此字段。混合状态会让人误以为"未标 owner = 没有单一 owner / 散落在多模块"，实际只是写漏了。

**建议**：要么所有规则都标 owner（哪怕值是"散落多模块，参见对应测试"），要么这条字段作为可选并在文档前言说明取舍。

## 14. "代表性 HTML / XML"格式参差

模板写"优先列 repo 内稳定的真实样本，不展开 incident 复盘"。实际文档里：

- 部分规则只列 fixture，无任何注释。
- 部分规则在 fixture 列表后跟一句"这些样本能证明 X"。
- 部分规则在 fixture 列表后跟"这些样本分别覆盖 A、B、C"。
- 部分规则写"当前无稳定 DOI 样本，直接见对应测试"——一共 5+ 条规则使用此免责声明：
  - `rule-rewrite-inline-figure-links`（line 203）
  - `rule-table-flatten-or-list`（line 261）
  - `rule-elsevier-supplementary-materials`（line 609）
  - `rule-elsevier-graphical-abstract`（line 679）
  - 落盘规则（line 485）

**建议**：

- 列入"无稳定 DOI 样本"的规则单独建一个汇总表，方便后续补样本。
- "代表性 HTML/XML"的注释格式至少统一为"`<fixture>` — 覆盖 X 行为"逐条列出。

## 15. 同一 fixture 被多条规则点名做"代表样本"，缺乏聚合视图

高扇出 fixture 示例：

- `10.1073_pnas.2309123120` 被 5 条规则列为代表样本：
  - `rule-html-availability-contract`、`rule-provider-owned-authors`、`rule-image-download-tier-diagnostics`、`rule-filter-publisher-ui-noise`、`rule-keep-data-availability-once`
- `10.1126_science.adp0212`：被 2 条规则列为代表样本（`rule-provider-owned-authors`、`rule-readable-equation-caption-spacing`）
- `10.1126_science.abp8622`：被 2 条（`rule-preserve-subscripts-in-headings`、`rule-stable-frontmatter-order`）
- `10.1038_nature12915`、`10.1038_nature13376`：分别在 3+ 条规则下出现。

不是问题本身，但说明：

- 如果 fixture 被替换，要更新多条规则的"代表性 HTML/XML"段。
- 文档没有一个"fixture → 它锁住哪些规则"的反向索引。

**建议**：在 doc 末尾或单独 reference 文件中维护反向索引表，避免 fixture 修改时漏改。

## 16. 测试归属重复，存在隐性维护成本

同一个测试函数被多条规则列为"对应测试"：

- `test_old_nature_fixture_keeps_single_methods_summary_and_methods_sections` → 3 条规则（caption-precedence / methods-summary / formula-image-fallbacks）。
- `test_old_nature_downloaded_body_figures_inline_without_trailing_figures_block` → 2 条（no-trailing-figures-appendix / caption-precedence）。
- `test_new_nature_downloaded_body_figures_inline_without_trailing_figures_block` → 同上。
- `test_wiley_full_fixture_extracts_body_sections_from_real_html` → 2 条（keep-semantic-parent-heading / preserve-inline-semantics-in-body-and-tables）。
- `test_wiley_provider_replay_for_2004gb002273_body_assets_avoid_trailing_figures_noise` → 2 条（no-trailing-figures-appendix / filter-publisher-ui-noise）。
- `test_science_real_fixture_does_not_leak_competing_interests_modal` → 2 条（filter-publisher-ui-noise / keep-data-availability-once）。
- `test_pnas_full_fixture_keeps_data_availability_and_renders_table_markdown` → 2 条（keep-data-availability-once / preserve-inline-semantics-in-body-and-tables）。

**建议**：测试复用本身合理，但建议把"主 owner 测试"和"次要触及测试"在条目里区分（例如用粗体或子列表），让"重命名/删除一个测试要找哪条规则"有清晰路径。

## 17. 边界说明里硬编码他规则的概念名，但没有 link

很多规则的边界段提到了别的规则的概念，但没用 anchor link 串起来：

- `rule-filter-publisher-ui-noise` 边界说明（line 108）：提到"preview sentence 和 AI alt disclaimer 也会被过滤，但它们属于单独的访问提示规则"——但没 link 到 line 492。
- `rule-keep-data-availability-once` 边界说明（line 350）：提到 `Permissions` / `Open Access` / `Acknowledgements` / `Research Funding` 归 auxiliary / chrome / back matter，但没 link 到 `rule-filter-publisher-ui-noise` 或类似规则。
- `rule-springer-caption-precedence` 提到 `PowerPoint slide` / `Full size image`，但没 link 到 `rule-filter-publisher-ui-noise`。

**建议**：所有"我不管，那条规则管"的描述都应改为 anchor link，避免概念漂移。

## 18. 规则名长度悬殊，长标题暗示职责堆叠

短标题规则（< 12 字）：`保留语义父节标题`、`无节标题正文必须保持扁平`、`Graphical abstract 不进入 Additional Figures`。

长标题规则（≥ 30 字）：

- `正文引用到的 figure / table 要就地插回；已消费图表不得再追加；复杂 span 表保留语义展开和降级标记`
- `通用元数据抽取不能把站点描述误当摘要，也不能丢掉 redirect stub 的 lookup title`
- `正文内联 table 占位必须被真实表格替换，替不出来也不能把占位符漏给用户`

长标题往往是 §10 中"多职责合一"的征兆。即使不拆，也建议精简成"一句话核心约束"，把次要约束移入"边界说明"或独立子规则。

## 19. 部分规则没有"如果违反，用户会看到……"句

模板要求"固定说明三件事：约束的是……；如果违反，用户会看到……；它对应的阶段是……"。

抽查发现：

- 所有 generic / provider 规则**都有**前两句，第三句"对应阶段"基本都有。
- **但**少数规则的"违反后果"句过于抽象（仅说"会出现错误"），不符合模板要求"具体到用户可见现象"。例：`rule-generic-metadata-boundaries` 的违反后果"标题被重复当成摘要、摘要字段被站点 description 污染" — 已经具体；模板贯彻得不错，**未发现明显违规**。

此条记录为"模板贯彻情况巡检通过"，无需修改。

## 20. Generic 章节中存在仅一个 provider 样本的"准 generic"规则

`Generic` 章节自述"shared extraction logic"。但部分 generic 规则的代表性样本仅来自单一 provider：

- `rule-keep-semantic-parent-heading`：唯一样本 `10.1126_sciadv.adl6155`（Science）；测试覆盖 Wiley 和 Models 渲染层。
- `rule-readable-equation-caption-spacing`：唯一样本 `10.1126_science.adp0212`（Science）。
- `rule-preserve-subscripts-in-headings`：唯一样本 `10.1126_science.abp8622`（Science）。

这些规则确实是 generic 行为（多 provider 测试覆盖），但单样本会让读者怀疑它"实质上是 Science 规则"。属于"代表性 HTML/XML"块覆盖度不足问题。

**建议**：要么补一份非 Science 的稳定 fixture，要么在边界说明里点明"行为约束跨 provider，仅证据样本暂时来自 Science"。

## 21. 边界说明出现"内部实现细节"而非"行为约束的范围"

部分规则的边界段写的是实现选择，与"边界说明 = 这条规则不约束什么"的模板意图相悖：

- `rule-image-download-tier-diagnostics` 边界说明（line 247）："如果同一个浏览器页面已成功加载图片，但页面内 `fetch()` 再取同一 URL 时被 Cloudflare challenge 返回 HTML 拦截，优先从 FlareSolverr/Selenium 已加载的 `<img>` 导出 PNG 字节；恢复链路只接受 `solution.imagePayload`，不再退回图片文档 screenshot 裁剪。"
  - 这是恢复链路的实现细节，不是"本规则不约束什么"。
- `rule-html-availability-contract` 第 132–133 行同样写了大量"统一实现位于 X 模块"的实现声明，应放进 owner 模块字段而非规则正文。

**建议**：实现细节迁到 owner 模块字段或 `providers.md`；边界说明只保留"行为不覆盖什么场景"。

## 22. Wiley 节缺失 `rule-stable-frontmatter-order` 但实际承接了它的 dedup 测试

明显错位案例（与 §8 互补）：

- `rule-stable-frontmatter-order`（line 269，Generic）：测试列表（line 282–283）包含 `test_wiley_provider_deduplicates_near_matching_abstract_in_final_article_render` 这条 Wiley provider 测试。
- 但 Wiley 节顶部"共享规则另见"列表（line 685–698）**没有列**这条规则。
- 同样 Springer 节顶部也未列 `rule-stable-frontmatter-order`，虽然 Springer 双语样本和 frontmatter 顺序同样可能被它影响。

**建议**：补 Wiley / Springer 节的 cross-reference。

## 23. 命名违反"行为级表述"模板的条目

模板规定"用行为级表述命名，不把 DOI 写进规则名"——所有规则都遵守了不写 DOI 的约定。但部分规则名仍偏"对象化"而非"行为化"：

- `Graphical abstract 不进入 Additional Figures`（对象化：以"对象去向"命名，行为隐含在介词里）。
- `HTML 公式图片 fallback 必须保留并进入资产链路`（行为化 + 对象化混合）。
- `Appendix figure/table 保持 appendix 语境，不因正文交叉引用被提到正文`（行为化）。

不算严重违规，记录用于命名规范化下一轮收口。

---

# 第二轮总结

| 类型 | 行动建议 |
| --- | --- |
| **结构** | §7 给两条无 anchor 规则补 anchor；§10 拆分多职责规则（4 条候选）；§13 补 owner 模块字段或统一改为可选 |
| **一致性** | §8/§22 补齐 provider "共享规则另见"列表；§9 统一 anchor 命名前缀；§12 引入"阶段术语清单"；§14 统一"代表性 HTML/XML"格式 |
| **耦合** | §11 把 generic 规则中的 provider 硬编码迁出；§17 边界说明用 anchor link 替代名词引用；§21 边界说明清出实现细节 |
| **可维护性** | §15 加 fixture → 规则反向索引；§16 区分主/次 owner 测试；§20 补单 provider 样本规则的多 provider 证据 |
| **命名** | §18/§23 长标题精简，命名风格规范化 |

**优先级建议**：

1. P0（影响阅读正确性）：§7 加 anchor、§8/§22 补共享规则列表。
2. P1（影响维护成本）：§10 拆 4 条多职责规则、§17 边界说明改 link。
3. P2（一致性收口）：§9 命名前缀、§12 阶段术语、§14/§13/§21 字段格式。

---

# 第三轮：与代码/测试的一致性、覆盖盲点、演进可维护性

> 一致性核验已先做：文档里 144 个测试函数名全部能在 `tests/` 下找到对应 `def test_...`；35 条 fixture 路径全部存在；`paper_fetch.quality.html_availability` / `paper_fetch.extraction.html.figure_links` 等 owner 模块路径在 src 中可定位。`providers/_html_availability.py` 已确实被移除（line 132 的 deprecation 描述属实）。下面问题不是"指错路径"，而是更深层的结构和覆盖问题。

## 24. 测试密度极不均，单测试规则风险高

每条规则挂的测试数量分布悬殊：

| 测试数 | 规则示例 |
| --- | --- |
| 14 | `rule-keep-data-availability-once` |
| 12 | `rule-image-download-tier-diagnostics`、`rule-keep-parallel-multilingual-abstracts` |
| 10+ | `rule-rewrite-inline-figure-links` |
| 1 | `rule-elsevier-supplementary-materials`、`rule-elsevier-graphical-abstract`、`rule-wiley-abbreviations-trailing`、`rule-wiley-reference-text`、line 479 落盘规则 |

**问题**：

- 单测试规则一旦该测试被重构/重命名/合并，规则的"对应测试"段会瞬间空。
- 高密度规则（如 `rule-keep-data-availability-once` 14 个测试）说明它实际承担多职责（与 §10 互证），应该拆分。
- 文档没有针对"单测试规则"做风险标记，读者看不出哪些规则的证据非常薄。

**建议**：单测试规则在边界说明里显式标注"测试覆盖度低，行为可由相邻规则联动验证"；或要求新增规则至少 2 个测试。

## 25. 文档收录的测试只占总测试 ~20%，存在大量"未挂规则"的相关测试

`tests/` 下共有 704 个 `test_*` 函数，文档里被点名的只有 144 个（约 20%）。

抽查 `test_models_render.py` 中包含 `data_availability` 的所有测试：

- 已挂在 `rule-keep-data-availability-once`：`test_article_from_markdown_keeps_data_availability_without_counting_it_as_fulltext`、`test_article_from_markdown_keeps_code_availability_without_counting_it_as_fulltext`、`test_article_from_markdown_uses_section_hints_for_nonliteral_data_availability` 等。
- 但还有大量 `test_models_render.py` / `test_html_shared_helpers.py` 中的测试覆盖相同主题，没在规则下列出。

**问题**：

- 当文档说"该行为由这 N 个测试锁定"时，读者会以为这 N 个就是全部，实际还有更多 silent guarantee。
- 一旦文档外的测试因为重构被删，会出现"行为退化但规则文档无法发现"。

**建议**：要么规则下"对应测试"声明只列**主要 owner 测试**（其他用"等"），并明确标注；要么用脚本/manifest 自动同步全部相关测试。

## 26. Generic 行为规则的测试散布在 provider-named 测试文件，命名误导

文档列在 `Generic` 章节下的规则，其测试几乎都来自 provider-named 文件：

- `rule-keep-semantic-parent-heading` 的对应测试来自 `test_science_pnas_provider.py`、`test_science_pnas_markdown.py`、`test_science_pnas_postprocess.py`、`test_models_render.py` —— 都不是 `test_generic_*.py`。
- `rule-rewrite-inline-figure-links`、`rule-image-download-tier-diagnostics` 同样几乎全部由 `test_science_pnas_*` 锁定。

**问题**：

- 读者只看测试文件名会以为规则是"Science/PNAS 专属"，但规则文档强调它是 generic。
- 测试文件迁移/拆分（例如把 generic 部分拆出 `test_html_extraction_generic.py`）时，规则文档与代码不会同步更新。

**建议**：要么测试文件按 generic vs provider 分目录（建议在 `tests/unit/generic/` 下放 generic-policy 测试），要么在规则的"对应测试"段标注每个测试是 generic-policy 还是 provider-specific verification。

## 27. fixture 引用密度极不平均，部分 publisher 没有独立证据

抽样 fixture 引用次数：

- `10.1073_pnas.2309123120`：被 5 条规则点名为代表样本。
- `10.1126_sciadv.aax6869`、`10.1126_science.abb3021`：被 2–3 条 generic 规则点名。
- `10.1038_nature12915`、`10.1038_nature13376`：被 4–5 条 Springer/generic 规则点名。
- 反观 fixture 目录里的 `10.1038_d41586-022-01795-9`、`10.1038_s41467-022-30729-2`、`10.1016_j.scitotenv.2022.158109`、`10.1126_science.7809609`（block 样本）等**完全没出现在规则文档里**。

**问题**：

- 文档里的"代表性 HTML/XML"实际偏向少数高曝光 fixture，未挂规则的 fixture 是不是被回归测试覆盖、是否还该保留？
- Sage、Tandf、IEEE、ACM 等 publisher 仅在 `rule-keep-parallel-multilingual-abstracts` 通过 regression 测试出现一次，没有独立 publisher 节，也没有独立规则。

**建议**：列出"未被任何规则点名"的 fixture，做一次清理（要么补规则，要么标记为纯 regression 测试用）。

## 28. Elsevier 节遗漏 HTML availability 规则可能不准

Elsevier 节顶部"共享规则另见"未列 `rule-html-availability-contract`。该规则确实主要服务 HTML provider（Science/PNAS/Wiley/Springer），但是否 Elsevier 完全不走 HTML availability？检查 `paper_fetch/providers/elsevier.py` 是否有 HTML availability 调用：

- 规则文档前言说"provider 路由不在本文档讨论范围"，但 Elsevier 实际可能走 ScienceDirect HTML fallback（参考 `_article_markdown_elsevier_document.py` 是否包含 HTML 路径）。

**建议**：对每个 provider 节做一次"哪些 generic 规则适用 / 不适用 / 部分适用"的复核，并在文档里 explicit 声明（避免读者反向推断）。

## 29. 文档没有规则版本号 / 修订日期 / 退役清单

- 没有"上次修订"或"规则版本号"。
- 没有 changelog 或"曾经存在但已被合并/退役的规则"列表。
- §1–§6 已识别的"应合并/取代"规则一旦真合并，旧 anchor 是否保留为重定向？文档没有约定。

**建议**：

- 加 `## 修订记录` 或链接到 git log。
- 当合并/退役规则时，保留旧 anchor 并标注 `> 已合并到 [新规则](#...)`，避免外部链接断裂。

## 30. 规则与 `providers.md` / `target-architecture.md` 之间无双向链接

- 文档前言只单向声明"provider 运行时见 providers.md"。
- 规则正文里多次出现 provider 硬编码（§11），但不指向 `providers.md` 中对应 provider 章节。
- 同样 `architecture/target-architecture.md` 里描述的"分层"（extraction / quality / providers），与本文档规则的"对应阶段"标签没有对照表。

**建议**：在 doc 前言加双向链接索引（"`rule-html-availability-contract` 对应架构层 `quality/`；provider 实现见 `providers/_science_pnas_html.py`"），让规则成为代码与架构之间的桥梁。

## 31. Owner 模块路径分散在 `extraction/` 和 `providers/` 两类

显式标注的 owner 模块：

| 规则 | owner 模块 | 模块所在层 |
| --- | --- | --- |
| `rule-html-availability-contract` | `paper_fetch.quality.html_availability` | `quality/` |
| `rule-rewrite-inline-figure-links` | `paper_fetch.extraction.html.figure_links` | `extraction/` |
| `rule-table-flatten-or-list` | `paper_fetch.providers._html_tables` | `providers/`（带下划线，私有） |
| `rule-keep-data-availability-once` | `paper_fetch.extraction.section_hints` | `extraction/` |
| `rule-preserve-inline-semantics-in-body-and-tables` | `paper_fetch.extraction.html.inline` | `extraction/` |
| `rule-preserve-formula-image-fallbacks` | `paper_fetch.extraction.html.formula_rules` | `extraction/` |
| `rule-springer-chrome-heading-normalization` | `springer_nature` shared noise profile | （非完整模块路径） |

**问题**：

- `rule-table-flatten-or-list` 的 owner 在 `providers/_html_tables.py`，是私有模块；其他规则的 owner 在 `extraction/html/*.py`，是公开模块路径。这暗示 table 规则尚未迁移到统一 extraction 层。
- `rule-springer-chrome-heading-normalization` 写的是 profile 名而非模块路径，与其他规则格式不一。

**建议**：

- 把 `_html_tables.py` 提升到 `extraction/html/tables.py` 或显式说明为何留在 providers。
- 规则 owner 字段必须写"完整 dotted path"，profile 名不算 owner 模块。

## 32. `rule-elsevier-formula-rendering` 含 LaTeX 后处理细节，未必属于 Elsevier

该规则包含：

1. 行内 vs display 分渲（Elsevier-specific）。
2. 失败时给可见占位（generic 行为，应共享）。
3. `\textbackslash\_` 标识符修复（generic LaTeX normalize，应共享）。
4. `\updelta` upgreek 改写（generic LaTeX normalize，应共享）。
5. `\mspace{Nmu}` 改写为 `\mkernNmu`（generic LaTeX normalize，应共享）。

第 3–5 项的对应测试在 `test_formula_conversion.py`（generic 单元测试），不属于 Elsevier-specific 测试。

**问题**：把 generic LaTeX 后处理塞进 Elsevier 规则，使得 Wiley/Science 的相同问题无规则可循。

**建议**：把 LaTeX normalization 拆为 generic 规则（如 `rule-formula-latex-normalization`），Elsevier 节只保留 `行内 vs display 分渲 + 失败占位` 两条 Elsevier-specific 行为。

## 33. Science / PNAS provider 节没有任何 specific 规则

Science 节（line 728）和 PNAS 节（line 747）只有"共享规则另见"列表，没有任何 specific 规则。

对比：

- Springer 节有 6 条 specific 规则。
- Elsevier 节有 6 条 specific 规则。
- Wiley 节有 2 条 specific 规则。
- Science / PNAS 节有 0 条 specific 规则。

**问题**：

- 这是"已经全部上升为 generic"还是"尚未识别 specific 规则"？文档没说。
- Generic 规则正文里多次硬编码 `science / pnas`（§11），暗示这两个 provider 有差异化行为，但又被声称"无 specific 规则"——逻辑矛盾。
- 如果未来发现 Science 独有现象，是新增 `rule-science-*` 还是改 generic？无章可循。

**建议**：在 Science/PNAS 节顶部加一段说明，明确"当前所有 Science/PNAS 行为约束已全部归入 generic 规则；硬编码 provider 名属于 generic 规则的 sub-clause"。

## 34. `_scenarios/` 人造场景仅在一处使用，未声明使用规则

`rule-provider-owned-authors` 引用了 `_scenarios/elsevier_author_groups_minimal/original.xml`（人造场景），其他规则全部使用真实 DOI 样本。

**问题**：

- `_scenarios/` 目录的使用规则不明：何时可以引用人造样本？
- 模板说"当前无稳定 DOI 样本，直接见对应测试"，但这里既不是"无稳定 DOI 样本"也不是真实样本，而是"人造 minimal scenario"——违反模板意图。

**建议**：要么在模板里允许 `_scenarios/` 作为代表样本（声明使用条件），要么把这条引用移到测试段，不放在"代表性 HTML/XML"段。

## 35. 规则之间的执行顺序未声明

例如：

- `rule-springer-caption-precedence`（caption 优先级）与 `rule-filter-publisher-ui-noise`（删 PowerPoint 等控件）有重叠目标（让 `PowerPoint slide` 不出现在 caption 里）。
- 如果两条规则其中一条失效，输出会发生什么？文档没说。
- `rule-rewrite-inline-figure-links` vs `rule-image-download-tier-diagnostics`：rewrite 依赖 download 已成功；如果 download 失败但 rewrite 仍执行，会发生什么？

**问题**：规则集合是 declarative，但实际是按 pipeline 阶段顺序执行；规则间存在隐式依赖，没人描述。

**建议**：在文档前言加一张"阶段流水图"，标注每条规则在哪一段、依赖什么前置阶段成功。

## 36. 实现细节渗透规则正文 / 边界（多处）

除 §21 已列两条外，再追加：

- `rule-keep-data-availability-once` line 323："section hint 的 heading key、dict/object coercion 和顺序匹配由 `paper_fetch.extraction.section_hints` 统一提供，并从 HTML semantics 层复用；`ArticleModel` 只保留 `SectionHint` dataclass 适配层。"——这是 internal API 契约，不是用户可见行为。
- `rule-html-availability-contract` line 132–133："唯一实现位于 `paper_fetch.quality.html_availability`；provider 侧不再保留 `_html_availability.py` 兼容 re-export，`_science_pnas_html.py` 也不能维护本地重复的 site-rule / availability 数据结构。HTML container 评分、选择、清理同样由 `paper_fetch.quality.html_availability` 统一实现..."——这是模块解耦约束，应放进 `architecture/target-architecture.md`。
- `rule-image-download-tier-diagnostics` line 224："对 `wiley` / `science` / `pnas`，正文 figure / table / formula 图片下载必须使用 shared Playwright browser context 主链路；每次 download attempt 只创建一次 context/page，多图复用..."——这是 runtime impl 细节。

**建议**：把"实现合约"从规则正文剥离到独立的`architecture/extraction-impl.md`或 owner 模块字段，规则正文只保留用户可见行为。

## 37. 规则下"对应测试"列表混合 provider 和 generic 测试，缺分组

`rule-keep-data-availability-once` 的对应测试列表（14 个）混合了：

- Science 测试（`test_science_*`）
- PNAS 测试（`test_pnas_*`）
- Wiley 测试（`test_wiley_*`）
- Nature 测试（`test_nature_*`）
- Elsevier 测试（`test_elsevier_*`）
- Generic models 测试（`test_article_from_markdown_*`）
- Browser workflow 测试（`test_browser_workflow_*`）

**问题**：14 个测试一字排开，读者扫描时无法快速看到 "Science 部分覆盖了几个、Elsevier 部分覆盖了几个"。

**建议**：用 sub-bullet 分组（`- generic / models:` / `- by provider:`），让覆盖矩阵一目了然。

## 38. 缺少"如何新增规则"工作流文档

模板告诉读者怎么写一条规则，但没说：

- 添加新规则时是否要在所有相关 provider 节同步更新"共享规则另见"？由谁负责？
- anchor 命名是否要走 review？
- 一个测试可以挂在几条规则下？（当前实际情况是 1–3 条不等，无明文）
- 退役/合并旧规则的流程？

**建议**：在文档末尾追加 `## 维护工作流` 段：

- 新增规则的 checklist。
- 修改/退役规则的步骤。
- 规则与测试归属的约定。

## 39. 末尾"使用建议"段过短，未支撑长期维护

当前末尾 3 行（line 766–768）只说"新增回归测试时优先写规则、root-cause 时按阶段定位、不要把 incident 搬进来"。

未涵盖：

- 怎样判断"这条规则是否还在生效"
- 哪些规则属于硬合约（不可修改），哪些属于软合约（可演进）
- 规则与代码 review 的关系

**建议**：扩展为完整的"规则生命周期"段。

## 40. 规则文档没有自动化校验

- 没有 lint / CI 校验：
  - 所有 anchor 是否唯一？
  - 所有 fixture 路径是否存在？（本审计手工核验通过）
  - 所有测试名是否存在于 `tests/`？（本审计手工核验通过）
  - "共享规则另见"中的 anchor link 是否都有效？

**建议**：写一个 `scripts/validate_extraction_rules.py`，CI 跑：

1. 解析所有 `<a id="rule-*">` 与 `[label](#rule-*)`，校验 anchor 唯一且 link 有效。
2. 解析所有 fixture 路径，确认文件存在。
3. 解析所有 backtick 测试名，confirm 在 `tests/` 中存在 `def test_<name>`。
4. 校验"共享规则另见"列表中的每条都有有效 anchor。

否则下次重命名测试或迁移 fixture 后，本审计的"路径全部存在"结论会失效。

---

# 第三轮总结

| 类型 | 行动建议 |
| --- | --- |
| **覆盖盲点** | §24 单测试规则补强；§25 测试归属脚本化；§27 清理未挂规则的 fixture；§33 Science/PNAS 节加说明；§34 `_scenarios/` 使用条件 |
| **规则与代码** | §26 generic 测试目录化；§31 owner 模块路径统一；§28 复核 Elsevier HTML availability 适用性 |
| **规则与架构** | §30 双向链接；§32 拆 generic LaTeX normalization 出 Elsevier；§36 实现细节迁出规则正文 |
| **生命周期** | §29 加 changelog/版本号；§38 新增规则 checklist；§39 完整使用建议；§35 阶段流水图 |
| **自动化** | §40 加 lint 脚本到 CI |

**优先级建议（合并三轮）**：

- **P0**：§7（加 anchor）、§8/§22（共享规则列表）、§40（CI 校验脚本）。
- **P1**：§10（拆多职责规则）、§17（边界改 link）、§24（单测试规则补强）、§32（LaTeX normalization 提升）。
- **P2**：§26（测试目录化）、§29（版本号/changelog）、§30（架构双向链接）、§31（owner 路径统一）、§35（阶段流水图）。
- **P3**（一致性收口）：§9/§12/§13/§14/§21/§36/§37/§38/§39。

---

# 全部三轮发现总览

- **重复 / 被取代**：6 条（§1–§6）
- **结构 / 命名 / 边界**：17 条（§7–§23）
- **代码一致性 / 演进**：17 条（§24–§40）

合计 **40 条**问题。其中真正需要立即处理（P0+P1）的 **8 条**，其余可在 anchor/列表治理一次性收口或随后续改动逐步消化。
