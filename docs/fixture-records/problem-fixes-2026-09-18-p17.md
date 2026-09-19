# P17：T&F 公式来源恢复（2026-09-18）

**输出路径已修复；GIF 像素可读性尚未核验。** 本次复用原有来源、公式转换、资产发现和损失计数，仅修改 T&F owner。

- DOI：`10.1080/08839514.2024.2375110`。
- [原始捕获 DOM](../../tests/fixtures/golden_criteria/10.1080_08839514.2024.2375110/acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html)，4205925 bytes，SHA-256 `91b0a5c5bf896ab6ce93d53a9947d484df85482fa46f3c2611885e78f209d9dc`；真实来源身份校验匹配。
- 原文 `.hlFld-Fulltext` 有 232 对相邻图片／MathJax 表示（186 inline、46 display），共 464 个 `//:0` 占位图片。旧 Markdown 的 92 个坏链接是 46 个 display 各输出两次，并非 92 个独立公式。
- 每对图片表示的 `data-formula-source` 提供不同的官方 GIF 地址，MathJax 表示只有 CHTML，没有该公式原始 MathML／TeX。页面表格 JSON 中另有 MathML，不拿它替换无对应身份的正文公式。

`prepare_source_images` 恢复官方地址并保留真实 TeX 数据；配对步骤优先可转换源公式，否则使用同对 GIF，一次输出。只有展示树且没有可用图片时保留 `[Formula unavailable]`。配对不跨正文，也不全篇按 URL 去重。原始含 MathML 的既有 T&F 样本继续输出结构化公式。

[新增全文 golden](../../tests/golden/test_tandf_formula_sources.py) 独立读取原始 DOM 的每对表示，逐个验证全部 232 个来源地址、输出顺序、正文前后位置、显式编号及 formula 资产候选身份；覆盖旧 92 个坏位置所属的全部 46 个 display 公式。输出 `formula_fallback_count=232 / formula_missing_count=0`，无 `//:0`。该计数明确包含全部行内回退，不用归零掩盖降级。

[最小 unit](../../tests/unit/test_tandf_formula_sources.py) 覆盖 MathML／TeX 优先、相对地址解析、重复运行、合法 URL 复用、坏 JSON／无图片／非出版社地址、孤立展示树／占位节点及跨正文配对边界；完整源仅用于 golden。测试证据已登记。

验证使用项目默认并行配置：

- 相关 T&F unit、provider golden、LST golden 与新增回归：57 passed。
- 追加全文资产链路断言：1 passed。
- 最后边界补充后的最小 unit、全文公式及既有 MathML／LST 定向复验：24 passed。
- 改动文件 Ruff 检查通过。

没有本次 GIF 下载响应或可验证像素，因此这里只证明来源身份、公式到地址的对应和资产候选链路，未宣称下载成功或图片可读；关闭图片可读性剩余项仍需合法资产获取证据。未改 Wiley、PDF、共享策略、版本或 CI。

后续阶段：本记录保留当时的离线验证与证据边界；当天稍后新增的真实图片/SVG响应、PLOS实体组装修复及实际分母见 [最终资产补证](problem-fixes-2026-09-18-asset-evidence.md)。此链接不把最初离线验证改写为联网结果。
