# P20 / P21 MathML 转换回归（2026-09-18）

使用已有真实采集全文，无新联网、无旧输出替代原文。两篇都经现有源身份检查匹配 DOI。

## 来源与问题

- `tests/fixtures/golden_criteria/10.1093_bioinformatics_btaa153/acquisition/source-completion-2026-09-18/001-http_response_entity.html`：SHA-256 `46be9b9ab7d81b201a9f2edc1d4d43f6ddf4cb01a05ec794779024d67e4e4bb3`。
- `tests/fixtures/golden_criteria/10.1073_pnas.2310157121/acquisition/source-completion-2026-09-18/002-camoufox-selector-dom.html`：SHA-256 `57680d9b1f3e979c3fdfa59915c772bcf4003450ef599ea9363c7c7a9ebb6e2c`。

- P20：OUP `math merror` 共 1 处，其中实际包含 `(k−1)/K` 的 `mfrac` 与 `)`；原 texmath 输出丢掉这些子节点。源本身标记错误，只能保留仍可读的结构，不能据此证明原公式完整正确。
- P21：PNAS `math#me3 mspace` 明确 `width="40pt"`；原 texmath 输出 `\mkern7200mu`，mathml-to-latex 原行为则丢掉尺寸。公式下标仍存在，问题是尺寸转换。

## 实现与验收

`formula/semantics.py` 在现有实际 backend 入口临时将 `merror` 子结构作为 `mrow` 送入转换，并保护明确尺寸、在 backend 成功后恰一次恢复正确 LaTeX。转换结果 `raw_mathml` 保留原始文本。复用 `parse_mathml_fragment` 的 defusedxml 与字节、节点、深度限制；拒绝输入不交给 backend。标记缺失或重复返回既有失败结果，不泄漏标记。未改 backend 选择、重试或 fallback 策略。

OUP 提取诊断记录 `source_mathml_error_count=1`，文章 warning 明确说明可读子节点被保留、上游错误未被修正。全文 golden 也保留此诊断语义。

实际安装的 texmath 与 mathml-to-latex 两个 backend 都验证：

- OUP 分数 `\frac{k - 1}{K})` 仍在 Θ 指数内，原有 C、w、t 结构保留；源错误 warning 存在。
- PNAS 公式 3 为 `\hspace{40pt}`，无 `\mkern7200mu`；在同一公式块核验 annual、Clearing、Fire、Logging、Windthrow、Other、No change、Growth 八项下标。

最小 unit 覆盖物理/相对/命名/负数/零间距、未知单位、merror 分数结构、标记唯一及恢复失败、安全 XML 拒绝、OUP warning 传递。integration 使用实际外部进程；golden 对两篇完整真实输入各回放两种 backend。没有增加依赖，没有修改 PDF 转换、浏览器边界、CI 或版本。

## 验证

`PYTHONPATH=src uv run python -m pytest tests/unit/test_mathml_semantics.py tests/unit/test_formula_conversion.py tests/unit/test_oxfordacademic_provider.py tests/integration/test_mathml_semantics.py tests/golden/test_mathml_semantics.py -q`

结果：55 passed、4 subtests passed，使用默认并行设置，实际 backend 回归无 skip。定向 Ruff 检查通过。

边界：保留上游 merror 事实，不判断该源公式整体数学正确性；未做各阅读器截图或字体尺寸验收，未将 PDF 转换质量纳入目标。
