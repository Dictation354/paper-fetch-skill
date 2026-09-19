# P09：独立输出对象验收（2026-09-18）

复用 `tests/support/object_content.py` 及既有真实源回放，仅加强测试，没有修改生产提取、矢量序列化或快照。

- **P06 五个目标**：原文确认 MDPI B68、B69、Table A4 及 Science R43、R49 的身份，再检查输出指向同篇正确对象。删除引文链接、改到同篇另一个真实对象、未知对象或不存在的本地 fragment 均必须失败。覆盖 all／top10（部分）／none；已有 appendix 过滤回归仍在。最小 unit 另验证源目标本身被删除时不能接受。
- **P08 出现次数**：原文登记主图地址与全部 128 个公式图片的出现序列，保留正文位置断言。删除／重复主图或 Figure 3 图注的四个公式图片均拒绝；复制整个 Figure 3 图片加图注块也会同时违反主图和公式次数。预期来自原文，未按输出归零或全篇 URL 去重。
- **P18 类型、位置、内容**：七篇原文的 29 个 object SVG 和五个内联 SVG，分别按源 data URL／节点 ID 与完整源树登记，检查实际图形表示、资产类型、正文位置和出现次序。每个源图形删除或复制后均须失败。五个内联 SVG 在 Markdown 和实际落盘文件两处比对完整源树：所有属性、路径 `d`、祖先 `transform`、foreignObject 文本及 MathML 标签／属性／文字；另验证 SVG、XHTML 和 MathML namespace。故意改写路径但保留 path 数量也必须失败。
- **P24 合法复用**：DDPM 原文 Figure 1／6／13／14 的两个图片地址各出现两次；源出现序列和各 figure 标签均通过，不能误删后面的合法源对象。

最小片段在 [unit](../../tests/unit/test_output_object_oracles.py)；真实源与完整资产留在既有 [P06 golden](../../tests/golden/test_retained_object_links.py)、[Annual Reviews golden](../../tests/golden/test_annualreviews_object_ownership.py)、[arXiv golden](../../tests/golden/test_arxiv_graphic_nodes.py)。新增定义及增强范围已登记 `tests/test-evidence.json`。

首轮 32 passed／2 failed 发现的是测试解析器对无 XML 声明 SVG 字节的编码误判：把 UTF-8 `−` 识别为 `âˆ’`。源输出字节 UTF-8 解码和 ElementTree 均保留原字符；改为明确 UTF-8 后复验，不放宽源内容比较，也未修改生产代码。

最终定向 unit／golden 加 evidence／layer policy：63 passed（50.07s）；使用项目默认并行。Ruff 和 diff 检查通过。

本项证明输出对象关联、次数、表示和五个已捕获内联 SVG 的内容保真；29 个远程 object SVG 仍仅有来源 URL，不能据此声称取得远程图片实体。没有新增文章采集，也不重复计数 P06／P08／P18 的内容修复。

后续阶段：本记录保留当时的离线验证与证据边界；当天稍后新增的真实图片/SVG响应、PLOS实体组装修复及实际分母见 [最终资产补证](problem-fixes-2026-09-18-asset-evidence.md)。此链接不把最初离线验证改写为联网结果。
