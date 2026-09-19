# P25 / P27 Science 表格与 Springer Methods 伦理（2026-09-18）

使用已有独立真实全文采集输入，无新联网。各输入经原文元数据 DOI 身份核验匹配；没有把旧 Markdown 当真值。

## 来源

- `tests/fixtures/golden_criteria/10.1126_sciadv.abj3309/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html`：SHA-256 `d8686473e20f2c99b976a737c5a99562dc4e7b9f0c29848119c2795f5b3f2827`。
- `tests/fixtures/golden_criteria/10.1038_s41467-022-32108-3/acquisition/template-gaps-2026-09-16/article-response.html`：SHA-256 `bc58449b4832822e74e670fb1c9b358aa270c2c26fd06b81420f7435bab4842f`。
- `tests/fixtures/golden_criteria/10.1038_s41522-026-01027-2/acquisition/template-gaps-2026-09-16/article-response.html`：SHA-256 `8e4929c8b3b6289b09d37cf51361a501cf64992e0b4e3c160bc183ccfd3294a5`。

## P25

Science 表 3 为三列表头，数据行宽为 3、3、2，无 rowspan / colspan。末行原文只有 Recent deforestation 与 “Percentage of the cell deforested at year”，没有第三个 td，也没有后续 t。源文本自身的缺口不是转换器能恢复的内容。

Science owner 新增狭窄的无跨度短行呈现：克隆源表并只为缺失尾格填空，复用现有 Markdown 表格渲染；源节点不修改。输出附注 “Source table note: data row 3 supplies 2 of 3 cells; missing trailing cells are left blank.” 不补造 t 或 Source。嵌套、跨度、空行、超宽行、多行 thead、tfoot 不进入此分支；其他 publisher 不使用此分支。

独立 golden 逐格核对全部表头和三行，保留字段及顺序，仅归一既有引文上下标展示。末行空第三格显式验证。列结构与源中已有内容均保留，因此 table_fallback_count / table_layout_degraded_count / table_semantic_loss_count 为零符合实际，而不是把保留内容误报语义损失。

## P27

两篇伦理段落原本仍在 DOM 和提取 Markdown 中，后续 section hints 将伦理标题分类为 references 导致正文渲染排除。Springer owner 依据 DOM 的 Methods / Materials and methods / Methodology section 祖先，将 Ethics compliance / Ethics statement hint 设为 body；没有修改全局 ethics 分类。

独立 golden 对两篇原文逐字比较完整伦理段落，并验证 Methods、前节、伦理小节及后节的顺序。46 years、全部州级机构与许可证说明、Australian Bird and Bat Banding Scheme、Animal Welfare Committee、Anhui Agricultural University、AHAUXMSQ2024053 均保留。页尾 Ethics declarations / Competing interests 沿用过滤；最小测试同时放置正文与页尾同名 Ethics statement，确保仅正文改变分类。

## 验证

- 默认并行定向 unit（新边界与既有 Springer HTML/table）＋三篇源独立 golden：41 passed、19 subtests passed。
- 既有 Science 真实跨度表回归：1 passed，既有 rowspan 修复未回归。
- 相关 canonical summary（Springer 与 Science abj3309）：15 passed，无需修改 expected summary。
- 三个生产文件定向 mypy 通过，五个变更代码/测试文件 Ruff 通过。

未修改 PDF 转换、浏览器运行边界、依赖、版本或 CI。P25 修复的是可忠实恢复的列展示，原文缺失字段仍明确未知；P27 仅保留正文 Methods 伦理，不扩大页尾正文范围。
