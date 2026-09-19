# 问题清单修复与验证（2026-09-18）

按用户要求串行委派子代理处理 `problems.md`，主代理复核改动与结果。保留任务开始时的未提交修改，不提交、不更改版本或触发 CI。PDF 转换质量不在本次范围内。

## 已完成的局部修复

| 问题 | 当前结果 | 验证与剩余边界 |
| --- | --- | --- |
| P02 | Wiley 公式输出及原生 MathML 资产预处理已修复 | 两种真实 DOM 的 26 条官方地址核验通过；后续定向 34 项、1808 子测试通过。正式重抓 25/26 公式本地化，剩余公式前轮已有实体；跨轮 26 张可读，本轮严格归档仍 degraded。[最新记录](wiley-native-formula-assets-2026-09-18.md) |
| P05 | ACS 表内图片候选、OUP 签名重复计数及历史正文资产组装已修复 | 53/53 对象本地化，完整原分母保留；ACS 一个 fallback preview 仍 degraded。[最初离线记录](problem-fixes-2026-09-18-p05.md) · [最终实体证据](problem-fixes-2026-09-18-asset-evidence.md) |
| P06 | MDPI/Science 五处失效 fragment 已修复 | 原文对象身份、引用 all/top/none、表注及实际 token 预算过滤已验证；两组关联回归 57、52 项通过。[记录](problem-fixes-2026-09-18-p06.md) |
| P07 | 旧回放入口不再将 DOI 占位当可信标题 | 三篇 JSON/YAML/H1 标题一致；源身份不符被拒绝，PDF 回放原行为保留。最终定向复验 33 项通过。[记录](problem-fixes-2026-09-18-p07.md) |
| P08、P26 | Annual Reviews 图注公式归属、表题和术语/脚注层级已修复 | 128 幅源公式的次数/顺序/位置、138 条书目，以及五篇九处层级回归通过；合法重复保留。[记录](problem-fixes-2026-09-18-annualreviews.md) |
| P16 | IEEE 同篇 iframe PDF 响应接入既有验收 | 58 项测试、8 子测试通过，覆盖真实离线 Camoufox 的五种路径；Linux 契约及 6 项 portable 测试通过，不替代原生 macOS。[记录](problem-fixes-2026-09-18-p16.md) |
| P17 | T&F 无效公式图片地址和双重表示已修复 | 原 92 个坏输出对应 46 个显示公式；全文 232 公式的来源/位置/资产身份通过，GIF 像素可读性仍待核验。相关 57 项、最终 24 项回归通过。[记录](problem-fixes-2026-09-18-p17.md) |
| P18、P23、P24 | arXiv 图形、标题和相对地址已修复 | 34/34 目标图形本地化，全文 78 候选中的其他 44 个仍未获取；GAN 标题修复，DDPM 源文 Figure 13/14 合法重复保留。[原文记录](problem-fixes-2026-09-18-arxiv.md) · [实体证据](problem-fixes-2026-09-18-asset-evidence.md) |

| P20、P21 | MathML 错误节点子内容及明确间距已修复 | 两个真实 backend 的 OUP/PNAS 全文回放保留分数、指数、八项下标及 `\hspace{40pt}`；55 项、4 子测试通过，保留上游错误告警。[记录](problem-fixes-2026-09-18-mathml.md) |

| P19、P22 | PLOS 行内公式与 Copernicus 空引文已恢复 | 八张公式 PNG 逐身份/位置组装，PLOS 局部修复 query 误配并保留全文 27 候选分母；83 正文空引文恢复 101 目标，声明另一目标。[JATS 记录](problem-fixes-2026-09-18-jats.md) · [实体证据](problem-fixes-2026-09-18-asset-evidence.md) |

| P25、P27 | Science 三列表展示与 Springer Methods 伦理已恢复 | 表格缺失尾格明确留空，两篇伦理全文及节序核对；41 项、19 子测试通过，15 项摘要与一项既有跨度表回归通过。[记录](problem-fixes-2026-09-18-science-springer.md) |

| P09 | 独立原文对象与损坏输出反例已补齐 | 链接目标、图块次数/位置、完整 SVG 树和本地文件均验证，删除/重复/篡改被拒绝，合法复用通过；63 项通过。[记录](problem-fixes-2026-09-18-p09.md) |

清单 18 项均已逐项处理；后续 P02 修复及跨轮实体核验后，17 项局部修复或原归因纠正及对应证据完成。P17 的公式图片实体证据仍未闭合；P02 最新单轮归档仍有 1 张公式受验证页限制。P05/P18/P19 的具体目标已核验，整篇其他未获取资产与 preview/fidelity 降级保持真实状态，详见 [问题清单](../../problems.md)。

## 初轮检查

- `PYTHONPATH=src uv run python -m pytest tests/unit -q`：2368 passed、373 subtests passed。
- `PYTHONPATH=src uv run python -m pytest tests/integration -q`：127 passed、4 skipped、1784 subtests passed。
- `PYTHONPATH=src uv run python -m pytest tests/golden -q`：2771 passed、1 skipped、34168 subtests passed。该轮在修复前启动，运行期间 Wiley 有局部改动，不能替代最终修复集合的全量验证。
- `uv run python scripts/validate_macos_adaptation.py`：通过。系统 `python` 缺 PyYAML，改用项目既有虚拟环境执行；没有更改依赖。
- 初轮 Ruff 通过；mypy 原有 6 处错误，位于 `models/builders.py`、`providers/plos.py` 和 `workflow/fulltext.py`。后续验证应区分既有错误与新增错误。

主代理对 P02 新增捕获执行来源验证：7 passed、1741 subtests passed。复核时将空白兄弟节点判断明确为 BeautifulSoup `NavigableString`，消除新增类型错误，相关 3 项 unit 通过。

## 中途全量回归

unit 2435 passed、373 subtests passed。golden 2808 passed、1 skipped、2 failed：ACS 新增表内图后旧测试不能假设首资产就是目标图，已改为按独立原文 DownloadImage 包装链接匹配；T&F 规范化消费输入占位标记，防止第二次执行追加缺失公式。两处修正的定向复验 37 passed。最终全量验证另记。

主代理复核 P20/P21 时补齐 `formula/semantics.py` 的字典与替换回调类型，避免新增 mypy 错误；相关 18 项 unit 通过。类型检查不将任务前已有错误算为本次新增。

## 生产修复集合完整验证

在 P25/P27 完成后执行，均使用项目默认并行配置；P09 新增测试与后续资产证据复验另记。

- 完整 unit：2470 passed、373 subtests passed（81.62s）。
- 完整 integration：136 passed、4 skipped、1785 subtests passed（69.95s）。
- 第一轮完整 golden：2784 passed、1 skipped；36 个失败用例、173 个失败子测试（pytest 汇总 209 failed），见下方原因及复验。
- 全部 src/tests Ruff 通过；mypy 恰为任务前已有 6 条错误，无新增错误。

P09 补充完整原文损坏输出与最小机制、证据登记/分层验证：63 passed，无生产改动。


### 完整回归发现的旧验收规则差异

完整 golden 揭示三个独立测试规则未覆盖修复后的表示，均已逐项对照原文，没有修改生产输出或放宽身份/内容要求：

1. MathML `mspace` 现在保留为 `\hspace{尺寸}`；数字及单元格/书目比较原先排除了 kern，却把 hspace 的排版数字误算成科学数值。只在测试比较中排除语法明确的尺寸，真实 P21 golden 仍严格验证 40pt；新增反例确认 x=3 不能用间距 2pt 冒充 x=2。
2. Copernicus 表内空引文现恢复为源书目作者年份，旧表格 oracle 把该格期待为空。源表副本保留整篇书目上下文，独立从 rid→ref→label 登记期待；删除引文或改年份仍失败。
3. PLOS 公式从 info:doi 映射到官方端点。图片 oracle 增加精确官方 host、期刊 route、type 及源 inline-formula 的资产 DOI 对应；异图、异期刊、异域均拒绝。

全部 36 个原失败用例的定向复验中，33 项已在首轮恢复，最后三项加最小反例 28 passed、233 subtests passed。修正后重新启动完整 unit、integration、golden；最终结果另记。P09 新增回归也包含在这轮完整集合中。

### 修正验收规则后的完整复验

- `PYTHONPATH=src uv run python -m pytest tests/unit -q`：2483 passed、373 subtests passed（106.82s）。
- `PYTHONPATH=src uv run python -m pytest tests/integration -q`：136 passed、4 skipped、1785 subtests passed（112.06s）。
- 此轮完整 golden：2809 passed、1 skipped、34238 subtests passed，另 11 个 `test_source_completion` 失败。新资产在运行期间追加，worker 已缓存旧 fixture 登记，报 `unregistered fixture input`；重新启动的来源验证为 7 passed、1807 subtests passed。最终须在证据集合冻结后复验。

最后资产补证已取得 66 个可解析实体并完成实际正文组装；关联 40 项通过，新来源 7 项、1807 子测试通过。[最终资产证据](problem-fixes-2026-09-18-asset-evidence.md)。

实体组装另发现 P19 的实际问题：七张不同公式图在最终 Markdown 被误映射至同一文件，以及 info:doi 未下载候选未计入分母。继续在 PLOS owner 局部修复并增加真实资产回归；不将“已下载”直接等同于问题关闭。

## 固定代码与证据集合后的最终验证

PLOS 最后局部修复、66 个新响应、全部测试及登记已固定后重新执行，期间不再修改代码、fixture 或 ledger：

- 完整 unit：2486 passed、373 subtests passed（93.21s）。
- 完整 integration：136 passed、4 skipped、1851 subtests passed（93.14s）。
- 完整 golden：2839 passed、1 skipped、34238 subtests passed（611.87s）。
- 全部 src/tests Ruff 通过；本任务变更的 70 个 Python 文件格式检查通过；diff 空白检查通过。
- 最终 mypy 仍为最初六处：builders 四处、PLOS 既存下载映射一处、fulltext 一处；没有新增类型错误。
- macOS 契约静态验证通过，P16 的 Linux portable 六项回归通过；没有以 Linux 结果代替原生 macOS gate。

原始全文和已有捕获响应字节均未改写或删除；任务开始前的未提交修改保留。没有更改版本、提交或触发 GitHub CI。

当时结果：固定集合的完整 unit、integration、golden 全部通过。此后 P02 的公式图片证据已跨轮补齐，后续改动与定向验证见上方最新记录；P17 外部公式图片证据缺口继续保留；P05 的 preview/fidelity，以及 P18/P19 整篇其他未获取候选，不因目标修复完成而升级为 overall complete。
