# Annual Reviews：P08 / P26

生产改动仅在 `_annualreviews_html.py`，不调整共享渲染、全篇 URL 去重、资产发现或 PDF 转换。真实原文来自 P08/P26 所列五篇捕获；`tests/golden/test_annualreviews_object_ownership.py` 复用 `build_verified_source_article`、`source_prose_blocks`、`assert_object_position`、`assert_source_tables`，源对象预期不从输出或快照推导。

## P08：Figure 3 与图注公式归属

原文 `10.1146/annurev-control-090419-075625` 的 `#itemFullTextId #f3` 只有一个主图，图注有 `eq-075625-124/125/126/127.gif` 四幅公式。旧输出重复了主图与 125–127：figure 图片枚举把图注公式当成独立主图，后续 figure-link 注入又将首个公式位置替换为主图。

现仅在 Annual Reviews 渲染副本中预渲染图注子树，让公式留在图注文字中，再复用原 figure renderer。用于资产发现的 DOM 保持全部公式 img。原文实际为**全部 128 个独立公式图片**，不是“另外 128 个”；修复保留这 128 个完整序列和每幅相邻正文位置，四幅图注公式按 124→127 出现在 Figure 3 图注，各主图按原 figure ID 顺序一次。138 条引用逐项对照源文本、编号和输出顺序。

最小 unit 额外用两个独立 figure 复用同一主图 URL、各自图注重复同一公式 URL，以及正文复用公式，经过渲染与 figure-link 注入后仍保留源次数，防止全文 URL 去重掩盖问题。

## P26：五篇九处标题语义

| DOI 后缀（均为 `10.1146/annurev-`） | 原文对象 | 输出 |
| --- | --- | --- |
| `control-030123-013355` | `t1`、`t2`、`t3` 表题；Terms And Definitions | 三处普通加粗表题；H2 术语节 |
| `control-090419-075625` | `t1` 表题 | 普通加粗表题 |
| `environ-102511-084654` | Terms And Definitions | H2 术语节 |
| `med-120811-171056` | `t1` 表题；Terms And Definitions | 普通加粗表题；H2 术语节 |
| `neuro-062111-150343` | Footnotes | H2 脚注节 |

五个表题均依据 `.table-caption-container` 和对应源表核验身份，断言不再形成文章 Section；原 caption、全部单元格与表注及相邻正文位置继续验收。三个术语节与一个脚注节属于 `article-level-0-back` 的独立后置内容，按主节 H2 呈现；逐项检查术语／定义及脚注原文顺序、节级别和位置。没有按网页 modal 的 H4 字号机械映射。

`control-030123-013355/expected.json` 仅减去独立原文核验的三个表题伪章节：`sections: 21→18`、`body_sections: 18→15`。表格内容断言通过后才更新计数，其他计数和内容预期不变。

验证（默认 xdist 并行，无 `-n 0`）：

- `PYTHONPATH=src uv run python -m pytest tests/unit/test_annualreviews_object_ownership.py tests/unit/test_annualreviews_provider.py tests/golden/test_annualreviews_object_ownership.py tests/golden/test_annualreviews_provider.py tests/golden/test_annualreviews_complete_formula_assets.py -q`：33 passed。
- `PYTHONPATH=src uv run python -m pytest tests/golden/test_golden_corpus.py -k annualreviews -q`：38 passed，1037 subtests passed；仅上述三个表题伪章节的旧 summary 计数失败，已按原文更新。
- 最终以 `tests/golden/test_annualreviews_object_ownership.py` 及 `test_golden_corpus_expected_summary_matches_current_extractor[annualreviews:10.1146/annurev-control-030123-013355]` 定向复验：7 passed，包含每幅公式都必须具备相邻原文定位证据的最终断言。
- Ruff 和定向 `git diff --check` 通过。

未修改版本、CI，未提交。
