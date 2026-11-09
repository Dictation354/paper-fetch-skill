# Elsevier XML 实现与规则索引

Elsevier XML 使用官方 Article Retrieval XML 的 Journal Article / CEP DTD 元素语义，
资产来自 `<object>` 与 `attachment-metadata-doc`。元素分类与 Markdown 行为分别由以下代码和规则维护。

| 实现 | 职责 |
| --- | --- |
| [_elsevier_xml_rules.py](../src/paper_fetch/providers/_elsevier_xml_rules.py) | `ELSEVIER_ELEMENT_RULES` 元素分类、忽略标题及资产角色 |
| [_elsevier_objects.py](../src/paper_fetch/providers/_elsevier_objects.py) | 官方对象选择与候选优先级 |
| [_article_markdown_elsevier.py](../src/paper_fetch/providers/_article_markdown_elsevier.py) | XML 遍历、段落与 display block 渲染 |

用户可见行为集中在[提取规则的 Elsevier 章节](../docs/extraction-rules.md#elsevier)：

- [公式与 locator 图片](../docs/extraction-rules.md#rule-elsevier-formula-rendering)、[共享 TeX 边界](../docs/extraction-rules.md#rule-formula-latex-normalization)。
- [补充材料](../docs/extraction-rules.md#rule-elsevier-supplementary-materials)、[附录上下文](../docs/extraction-rules.md#rule-elsevier-appendix-context)、[图文摘要](../docs/extraction-rules.md#rule-elsevier-graphical-abstract)。
- [图表原位渲染](../docs/extraction-rules.md#rule-elsevier-inline-figure-table-placement)、[已消费资产去重](../docs/extraction-rules.md#rule-elsevier-consumed-figure-table-dedup)。
- [CALS table groups](../docs/extraction-rules.md#rule-xml-table-groups)、[复杂表格跨度](../docs/extraction-rules.md#rule-elsevier-complex-table-span-degradation)、[结构化参考文献](../docs/extraction-rules.md#rule-elsevier-xml-references)。

[ScienceDirect HTML 解析](../docs/extraction-rules.md#sciencedirect-html-专用解析)单独定义 HTML 专用行为。
XML 模型转换无网络副作用；验收后的参考文献 DOI 补全由获取流程负责。
