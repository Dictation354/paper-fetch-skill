# P07：旧回放适配器标题

修复仅位于 `tests/golden_corpus.py`。`GoldenCorpusFixture.title` 的 DOI 展示回退仍保留，但 HTML/XML 的 `_base_metadata` 不再把缺失、空白或等于当前 DOI 的占位写入可信 title。明确声明的真实标题继续按既有 base-first 规则优先。PDF fallback 回放元数据保留原行为，本项不进入 PDF 转换路径。

Springer 回放继续使用原 HTML 元数据解析和合并；Elsevier 回放复用现有 `extract_elsevier_xml_identity` 从 XML `coredata` 取得独立身份与标题，再进入已有元数据合并。两条入口在合并前复用 `validate_extracted_identity`，不同 DOI 的源元数据直接拒绝，不能用 fixture DOI 遮盖冲突。缺少 fixture 和源标题时 title 保持缺失，沿用现有 `Untitled Article` 展示回退。

| DOI | 独立原文标题 |
| --- | --- |
| `10.1016/j.rse.2026.115369` | Sentinel-1 for offshore wind energy application |
| `10.1007/s10584-011-0143-4` | Hydrological response to climate change in a glacierized catchment in the Himalayas |
| `10.1038/nature12915` | A two-fold increase of carbon cycle sensitivity to tropical temperature variations |

`tests/golden/test_replay_source_titles.py` 使用 `source-completion-2026-09-18.json` 登记的三篇原始响应，先核验字节 SHA-256、源 DOI 和独立登记标题；再分别移除 fixture title、设置 DOI 占位，经 `CapturedSourceFixture` 与旧 canonical builder 构建。没有调用会注入正确标题的 `build_verified_source_article`，没有更改 fixture title 或快照遮蔽回归。Article JSON title、Markdown YAML title、唯一 H1 均与原文标题一致，JSON / YAML DOI 不变，全文身份保留。

最小 unit 覆盖 HTML/XML 源标题填充、空白和 DOI URL 占位、真实标题优先、无源标题、两条 adapter 在正文转换前拒绝不同 DOI。新增测试均登记于 `tests/test-evidence.json`。

`nature12915` 的原 H1 曾因错误 DOI title 被重复当正文。独立核对原文 `Sec1`–`Sec8`：Main、Methods Summary、Online Methods 及其五个子标题；golden 逐个断言这些原文标题与正文输出对应（沿用既有 Online Methods → Methods 规范化），确认只有八个正文节。其 expected.json 因此仅更正 `body_sections: 9→8`、`sections: 10→9`，不改变内容预期。

验证（复用项目默认并行配置，无 `-n 0`）：

- `PYTHONPATH=src uv run python -m pytest tests/unit/test_replay_metadata.py tests/golden/test_replay_source_titles.py -q`：22 passed。
- 追加 adapter unit 与全部 `test_golden_corpus_expected_summary_matches_current_extractor`：169 passed、7 failed；六个 PDF fallback 标题回归已通过保留既有元数据行为解决，另一项为上文 Nature 重复 H1 计数。
- 最终定向复验 `tests/unit/test_golden_corpus_adapters.py`、`tests/unit/test_replay_metadata.py`、`tests/golden/test_replay_source_titles.py` 与上述七个失败 node：33 passed。七个摘要 node 对应 `acsomega.2c02828`、`1748-9326/aa9f73`、`journal.pbio.0040298`、`en16186655`、`annurev-med-120811-171056`、`rsta.2020.0108`、`nature12915`；仍使用 `PYTHONPATH=src uv run python -m pytest ... -q` 默认并行。
- Ruff 对回放适配器与两个新增测试模块检查通过。

没有修改生产 owner、版本、CI 或提交。
