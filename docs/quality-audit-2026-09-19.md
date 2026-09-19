# 2026-09-19 质量问题修复记录

对应 `papers/audit-2026-09-19/quality-issues.md` 的 Q1–Q14。
本次在已有工作区改动上完成局部修复，不改变版本、依赖或 GitHub CI。
原审计 Markdown、采集文件和 acceptance 是修复前证据，未用新结果覆盖。

| 问题 | 修复与验证 |
| --- | --- |
| Q1 | 表格中的图片保留在单元格内；GAN 原始 HTML 经最终 Markdown 渲染后仍保留面板行。 |
| Q2 | Springer 排除将 Reporting summary 当摘要的误识别；主文、Reporting summary 顺序与原文一致。 |
| Q3 | 保留 Extended Data Table 的题注和官方表页入口；未声称下载或核验表页单元格。 |
| Q4 | Wiley 移除引用的 `.bullet` 显示编号，编号由既有有序引用组装负责；两篇 HTML 回放验证。 |
| Q5 | Copernicus PDF 身份请求去除元数据题名的 HTML 标签；两份现有正式 PDF 均通过原身份阈值，PDF 字节和转换输出透传。 |
| Q6 | Copernicus 空图表 xref 从明确 rid 目标恢复 label；周围已有 Fig./Table 时避免重复前缀，已有引用文字不改。 |
| Q7 | JATS 节标题使用现有内联公式渲染；ACP 原 XML 的科学上下标得到保留。 |
| Q8 | OUP 排除 Abstract 标题和幻灯片下载控件造成的伪摘要，保留真实摘要；三篇 HTML 回放验证。 |
| Q9 | PLOS 按结构化姓名节点保留姓名和相邻作者边界，覆盖 person-group 和直接 mixed-citation 两种结构；三篇有来源记录的 XML 逐个姓名核对实际空格及词边界。 |
| Q10 | 复用工作区已有 ACS 图像式表格发现修复；真实 DOM 发现 10 个资产，Table 2 未落地时 9/10 不能通过严格本地验收。 |
| Q11 | 删除按相同文本合并单元格的逻辑，保留空列与重复值；最小回归和同轮审计 HTML 的最终输出逐列核对通过。 |
| Q12 | Science 通过可见控件展开引用列表，包括连续分页；缺失正文引用目标时记录 `reference_targets_missing` 并降级。历史真实 DOM 的 100 条引用和第 55 条均可提取。 |
| Q13 | Royal Society 完整 HTML 引用优先于元数据裸 DOI；三份有来源记录的 HTML 逐条核对作者、题名、年份。 |
| Q14 | IEEE stamp 失败后在剩余预算内从同篇文章页点击官方 PDF 链接；离线真实浏览器覆盖同页、popup、错误身份拒绝，并保留原 PDF 验收及降级来源。 |

Q11 同轮输入 SHA256 为 `7c4ccbae4c42cade606ba1cd796e2ef601b4d3b2678263e53e30a42b98ad9561`。
修复后的 Table 1 目标行仍为五列：前三列空白，第 4、5 列分别为 `IV-2SLS`；
Table 2 目标行仍为四列：首列空白，第 2、3、4 列分别为 `(0.0002)`。
详细离线结果保存在审计目录的 `fix-validation.json`。

## 回归入口

- [最小机制与统一验收回归](../tests/unit/test_audit_quality_regressions.py)
- [真实来源回放](../tests/golden/test_audit_quality_regressions.py)
- [IEEE 真实浏览器 PDF 契约](../tests/integration/test_ieee_iframe_pdf.py)
- [Science 真实浏览器引用加载契约](../tests/integration/test_science_reference_loading.py)

完整验证使用项目默认 pytest 并行配置：

```bash
PYTHONPATH=src uv run python -m pytest tests/unit -q
PYTHONPATH=src uv run python -m pytest tests/integration -q
PYTHONPATH=src uv run python -m pytest tests/golden -q
PYTHONPATH=src uv run python -m pytest tests/golden -k 'plos or royalsocietypublishing or royal or audit_quality' -q
bash scripts/test-macos-contract.sh --python .venv/bin/python
```

本轮末次本地结果如下；完整执行日志保存在审计目录的 `fix-results/`。

- unit：2516 passed，373 subtests passed。
- integration：142 passed，4 skipped，2144 subtests passed；新增浏览器用例均实际执行。
- golden：完整回归 2877 passed、1 skipped、34238 subtests passed；末次 PLOS／Royal Society 修改另经 218 项 provider 定向回归、2772 项子测试通过。
- macOS 静态契约通过，原生 Linux Python 的 portable 契约 6 passed。
- 全仓 `ruff check .` 和 `git diff --check` 通过。
- mypy 仍为先前记录的 6 项错误，位于 `models/builders.py`、`providers/plos.py`、`workflow/fulltext.py`；本次未新增类型错误，也不宣称全仓 preflight 已通过。

仅更新 Forest age and water yield 的三个旧 expected 字段：摘要存在性、摘要节数、正文节数。
Wiley 的原文比较 oracle 单独去除明确的显示编号节点，仍逐条比较书目信息和数字，不以新输出反写原文。

本轮验证使用既有来源和离线浏览器回放，没有进行新的线上可用性复测。
原清单中的访问受限、未取得的资源及明确预览降级仍按原证据报告。
Linux 静态与 portable 检查不能替代 macOS 原生 gate；PDF 转换质量不属于本次改动或验收范围。
