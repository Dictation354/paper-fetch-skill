# P06：MDPI / Science 保留文本对象链接

修复范围为三篇原文的五处 fragment。原因是表注、数据可用性声明保留了源链接，而参考文献与表格转换后没有输出原 HTML ID。沿用现有同篇来源页定位方式，仅在 MDPI / Science owner 中对原文确有对应对象的 ID 生效；不新增 Reference 字段，不调整其他 provider 或 PDF 路径。

| DOI | 原始 ID | 核验身份与目标 |
| --- | --- | --- |
| `10.3390/math11030657` | `B68-mathematics-11-00657` | 第 68 条 Lu / Dang，*Corporate governance and technological innovation: Comparison by industry.*；同篇书目对象地址。 |
| 同上 | `B69-mathematics-11-00657` | 第 69 条 *Industry classification guidelines for listed companies.*，证监会指南；同篇书目对象地址。 |
| 同上 | `table_body_display_mathematics-11-00657-t0A4` | Table A4 *Variables definition.*，首列表头 `Variable`；按 wrapper 内显式弹窗链接映射到可见 `mathematics-11-00657-t0A4`，不让链接停在隐藏 lightbox。 |
| `10.1126/science.abp8622` | `R43` | 第 43 条 *Materials and methods are available as supplementary materials.*；同篇书目对象地址。 |
| `10.1126/science.adp0212` | `R49` | 第 49 条 W. Zhang 的论文代码，Zenodo `10.5281/zenodo.11531548`；同篇书目对象地址。 |

三篇均复用 `tests/fixtures/golden_criteria/<DOI slug>/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html`，入口复用 `build_verified_source_article`。`tests/golden/test_retained_object_links.py` 独立登记上述源 ID、对象文字和引用编号后，核对原文 callout、书目位置／表身份及最终完整链接；预期不从提取结果或快照反推。

`include_refs=all/top10/none` 均能追溯原对象。MDPI `max_tokens=6000` 的真实公开渲染保留 Table 3 表注、过滤 Appendix 的 Table A4 时，链接仍指向原文可见表对象。最小 unit 另覆盖部分引用、无有效来源 URL 时转无跳转文字、普通同名 ID 与外部链接不受影响。全部目标采用来源地址，不依赖 Markdown 阅读器的 heading slug 或新增空 anchor。

验证（项目默认 xdist 并行，无 `-n 0`）：

- `PYTHONPATH=src uv run python -m pytest tests/unit/test_retained_object_links.py tests/unit/test_retained_publisher_notes.py tests/golden/test_retained_object_links.py tests/golden/test_retained_publisher_notes.py tests/golden/test_mdpi_provider.py -q`：57 passed，45 subtests passed（其中附录过滤用例随后改为公开预算渲染验证）。
- `PYTHONPATH=src uv run python -m pytest tests/unit/test_retained_object_links.py tests/unit/test_mdpi_provider.py tests/unit/test_atypon_browser_workflow_provider_html.py tests/golden/test_retained_object_links.py tests/golden/test_atypon_browser_workflow_markdown.py -q`：52 passed，9 subtests passed，包含最终公开预算过滤用例。
- Ruff 对两个 provider owner、新 helper 和两个新增测试模块检查通过。

没有修改版本号、CI 或提交。
