# P18 / P23 / P24：arXiv 原文图形与 frontmatter 离线修复

本轮复用 7 篇已捕获的官方 LaTeXML HTML，没有联网、重新抓图或处理 PDF。逐篇 SHA-256、34 个 DOM 节点与最终目标、源 figure / caption、输出次数和实际本地状态见[机器映射](problem-fixes-2026-09-18-arxiv.json)。原始响应与获取记录仍在各 fixture 的 `acquisition/provenance.json`，golden 回放校验响应长度和 SHA-256。

## P18：34 个源图形节点已恢复；5 个本地向量、29 个远程实体缺口

| arXiv ID | object SVG | 内联 SVG | 最终对应节点 | 实际本地文件 |
| --- | ---: | ---: | ---: | ---: |
| 1406.2661v1 | 4 | 0 | 4 | 0 |
| 2006.11239v2 | 0 | 5 | 5 | 5 |
| 2605.06659v1 | 1 | 0 | 1 | 0 |
| 2605.06663v1 | 12 | 0 | 12 | 0 |
| 2605.06665v1 | 7 | 0 | 7 | 0 |
| 2605.06666v1 | 3 | 0 | 3 | 0 |
| 2605.06667v1 | 2 | 0 | 2 | 0 |

34 是源图形节点数，包含子图，并非 34 个不同 Figure。HTML 边界把正文 `object[data]` SVG 和 figure 中的 `svg.ltx_picture` 接入现有图片/资产管线，保留 DOM ID、子图身份、源顺序和图注。无 figure 包装的 `S5.SS1.g1/g2` 也保留在原段落。frontmatter 图标及行内数学 glyph 不纳入正文图资产。

29 个 object 引用均按已捕获响应的 final URL 解析为绝对地址，每个在最终 Markdown 中出现一次；本轮没有对应远程响应实体，没有验证当前远程可访问性，不能算作已下载。现有 arXiv HTML ArticleModel 仅接收下载结果；无下载时资产 acceptance 为 `unknown`，该既有契约未扩大修改。原始候选和节点身份保留在提取 payload 与本记录。

DDPM 的 5 个内联 SVG 已从捕获 DOM 序列化为可解析 SVG/XML，保留路径数量、节点 ID、viewBox，以及 foreignObject/XHTML/MathML 命名空间；经现有 RuntimeContext、AssetBudget 和 ArtifactStore 原子落盘。最终 Markdown 将这 5 个 data URI 各改写成一个真实本地文件引用。ArtifactStore 文件审计后，`body` 且要求本地资产的 acceptance 为 `complete`、`body_local=5`、`body_discovered=5`。此验收只覆盖本次选取的 5 个内联向量，不声称 DDPM 其他远程图片也已取得。未做浏览器像素等价性验收。

文件与 7 篇实际组装结果保存在 `.paper-fetch-runs/problem-fixes-2026-09-18/arxiv/`；各文件路径、字节数和 SHA-256 在机器映射中。`tests/support/arxiv_graphic_replay.py` 和对应 golden 可离线重建。合成 integration 另外验证 `asset_profile=none` 不写文件、预算拒绝不产生成功文件，并确认 object SVG 经现有下载器直接保存；合成响应不是这 29 个远程对象已下载的证据。

## P23：GAN 标题和无内容 frontmatter 表

标题清理排除 `h1.ltx_title_document .ltx_pubnotes`。生产提取 metadata、最终 YAML 和 H1 均为 `Generative Adversarial Nets`；摘要后只含排版 rule 的空表消失。有效摘要、Introduction、Advantages and disadvantages、Conclusions and future work 和正文图保留。最小边界回归确认有内容 frontmatter 表及 section 内表格不被此规则删除。

## P24：重复归因经原文核验纠正

原文确有独立 `A4.F13`、`A4.F14`，并有正文引用：Additional samples 提到 Figure 13，Figure 6 图注明确提到 Figs. 14 and 10。因此 Figure 13/14 是合法源内容，不能按原清单前提删除。

修复的是表格语义块在原位图标注前取走图片、留下相对 URL 的局部次序/表示问题：先统一来源上下文 URL、提取资产和标注原位图片，再转换语义表格；表格 cell 渲染保留图片。最终 Figure 1、6、13、14 各按自己的源对象输出一次，图注和上述引用保留，不另加人工 `## Figures`。两组共享图片 URL 各出现两次，对应两个合法源位置；全部图片 URL 为绝对远程地址或明确本地文件，没有悬空相对地址，没有全局 URL 去重。

## 验证

- arXiv 关联 unit / integration / golden：85 passed、74 subtests passed（52.77s，默认并行）；覆盖现有 provider 与原始 TeX source-first 回归。
- 新增 object SVG 下载边界后，integration＋七篇专项 golden：12 passed（6.18s）。
- 进一步加入五个本地 SVG 的 ArtifactStore 文件审计：专项 golden 10 passed（6.12s）。
- 默认 collection / 显式 golden 分层检查：1 passed（1.62s）。
- 定向 Ruff 和 `git diff --check` 通过。新增测试均登记在 `tests/test-evidence.json`；真实内容只位于 golden，共享 helper 在 `tests/support/`。

没有新增依赖、变更版本/CI、调整全局 cache/retry 或修改 PDF 转换。

后续阶段：本记录保留当时的离线验证与证据边界；当天稍后新增的真实图片/SVG响应、PLOS实体组装修复及实际分母见 [最终资产补证](problem-fixes-2026-09-18-asset-evidence.md)。此链接不把最初离线验证改写为联网结果。
