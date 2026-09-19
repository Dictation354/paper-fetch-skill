# 2026-09-19 正式 CLI 重新采集

> **后续复核更正：** 本轮结果进一步检查确认 5 项当前链路问题，涉及 8 篇。下文“待补采项为 0”和“277/277”仅覆盖当时已发现并登记的资产，不能证明最终正文图片身份、覆盖和出现次数正确；原始结果与用户对 T&F 公式的确认保持不变。当前待修项见 [problems.md](../../problems.md)及[复核证据](chain-review-2026-09-19.md)。

用户后续确认 T&F 当前结构化公式没有问题，接受本次正式抓取结果。**本轮27篇全文与已发现正文资产的采集目标已收口，待补采项为0。** 旧232个公式GIF不再作为本轮待办；未下载的历史事实、11篇degraded和原始响应证据边界保持不变。该结论不扩大为全仓历史模板或新增完整golden回放全部覆盖。

本轮按用户要求，直接使用当前 checkout 的正式 `python -m paper_fetch.cli fetch` 批量入口重新联网抓取。27 个规范 DOI 先经项目 `batch_resolve` 唯一解析；静态 doctor 全部 ready。使用全新输出目录，batch concurrency=4，复用项目 provider lane 限制和既有浏览器状态；未 monkeypatch、未调用自写下载器、未强制切换 provider、未修改生产代码或访问／缓存／重试策略。

参数：`--format json --save-markdown --artifact-mode all --asset-profile body --require-local-body-assets --include-refs all --max-tokens full_text`。实际命令、开始／结束时间和退出码见 [run.json](../../.paper-fetch-runs/official-reacquisition-2026-09-19/run.json)。耗时 380.21 秒，CLI exit 0。

## 当前结果

- 27/27 取得全文：17 HTML、2 XML、8 PDF fallback；统一 acceptance 为 **16 complete、11 degraded**，无 failed、limited、未调度。
- 当前发现的正文逻辑资产 **277/277 本地化**；对应 **276 个独立可读文件**。DDPM 两个逻辑资产复用一个实际文件，因此不按文件数冲销逻辑分母。AIP `1.39658` 的 PDF 路线当前发现正文资产为 0；本地化达标不等于出版社所有视觉对象均有独立图片。
- 独立复核 80 个主输出／Markdown／诊断快照的 size/SHA-256，逐个检查资产哈希及 SVG 结构／图片解码／PDF 可读取性。8 份原 PDF 全部可读，无加密、无修复；其中 3 份没有可直接提取的目标 DOI，另以正式同篇获取链及完整首页标题核对，未改变文件或转换输出。
- 已向现有 27 个 fixture 的 `acquisition/official-reacquisition-2026-09-19/` 追加 **372 个文件**：80 个输出快照、276 个资产文件、16 个原文文件（8 HTML、8 PDF），另存每篇 manifest／collection 并登记唯一 fixture manifest/provenance。历史原文件与 golden expected 未改写。

## 与上一轮缺口的对应

| 项目 | 本轮结果 |
| --- | --- |
| Wiley gcb.16758 | 31/31：5 张 full-size 正文图、26 张 accepted-preview 公式图；complete。此前单轮缺公式 2 已由本轮实际抓取补齐。 |
| 七篇 arXiv | 78/78 正文逻辑资产本地化；6 complete，DDPM 保留 asset_placeholder_suspected/degraded。 |
| 两篇 PLOS | 9/9、18/18，合计27/27；包含此前缺少的展示公式。保留公式 fallback、8 张 fallback-preview 和 asset_fidelity_degraded。 |
| T&F 08839514.2024.2375110 | 全文、5/5正文图，complete；当前公式为结构化输出，fallback/missing 均为0。用户确认当前公式没有问题，旧232个GIF不再列为本轮待补；仍保留未下载旧GIF的历史事实。 |
| 之前19篇中的17篇全文样本 | 全部正式重抓并启用正文资产；Wiley gcb.16758去重。此前已接受的两篇 limited 场景未重抓，其余已确认无权限条目也未调度。 |

## 逐篇验收

| DOI | 路线表示 | acceptance | 正文资产本地/发现 | 保留原因码 |
| --- | --- | --- | ---: | --- |
| `10.1080/08839514.2024.2375110` | html | complete | 5/5 | — |
| `10.1111/gcb.16758` | html | complete | 31/31 | — |
| `10.48550/arxiv.1406.2661v1` | html | complete | 10/10 | — |
| `10.48550/arxiv.2006.11239v2` | html | degraded | 23/23 | asset_placeholder_suspected |
| `10.48550/arxiv.2605.06659v1` | html | complete | 1/1 | — |
| `10.48550/arxiv.2605.06663v1` | html | complete | 13/13 | — |
| `10.48550/arxiv.2605.06665v1` | html | complete | 9/9 | — |
| `10.48550/arxiv.2605.06666v1` | html | complete | 6/6 | — |
| `10.48550/arxiv.2605.06667v1` | html | complete | 16/16 | — |
| `10.1371/journal.pbio.0040298` | xml | degraded | 9/9 | asset_fidelity_degraded, formula_fallback, formula_fallback_present |
| `10.1371/journal.pcbi.1003118` | xml | degraded | 18/18 | asset_fidelity_degraded, formula_fallback, formula_fallback_present |
| `10.1111/gcb.16998` | html | complete | 4/4 | — |
| `10.1126/science.aeg3511` | html | complete | 1/1 | — |
| `10.1088/1748-9326/ab7d02` | html | complete | 5/5 | — |
| `10.1088/2058-9565/ac3460` | html | complete | 2/2 | — |
| `10.1088/0034-4885/53/3/002` | pdf | degraded | 33/33 | abstract_only, asset_placeholder_suspected, weak_body_structure |
| `10.1088/1681-7575/ae1dfc` | html | complete | 11/11 | — |
| `10.1021/ja00160a040` | pdf | degraded | 5/5 | insufficient_body, asset_placeholder_suspected, weak_body_structure |
| `10.1021/jacs.6c10062` | html | complete | 5/5 | — |
| `10.1063/1.39658` | pdf | degraded | 0/0 | abstract_only, weak_body_structure |
| `10.1063/5.0260731` | html | complete | 3/3 | — |
| `10.1175/jpo-d-24-0098.1` | pdf | degraded | 13/13 | abstract_only, access_gate_detected, weak_body_structure |
| `10.1073/pnas.2607267123` | pdf | degraded | 2/2 | empty_article_shell, weak_body_structure |
| `10.1038/s41561-022-00912-7` | html | complete | 4/4 | — |
| `10.1098/rspa.1984.0023` | pdf | degraded | 35/35 | abstract_only, weak_body_structure |
| `10.1186/s40359-026-04991-8` | pdf | degraded | 3/3 | fulltext:springer_html:fail, weak_body_structure |
| `10.1038/s41419-026-09210-1` | pdf | degraded | 10/10 | fulltext:springer_html:fail, access_gate_detected, weak_body_structure |

## 来源与证据边界

官方 CLI 对不同 provider 的原始载荷落盘范围不同：本轮落盘 8 份原 HTML、8 份原 PDF；其余 provider 的生成 JSON／Markdown 只作为派生快照，不冒充原始 HTML/XML。独立 HTTP 响应状态、最终 URL、精确响应时间未由 CLI 暴露时保持未知；provenance 明确标注 CLI artifact、终态时间来源和派生／导出类型。PDF 导出图片与内联 SVG 不宣称为原始网络图片响应。

新增文件本轮完成采集、身份／字节／可读性核验与入库；不声称新增27篇完整 golden 内容回放。现有整篇原始输入及 expected 不变。T&F 当前正文成功与旧232个GIF的真实链路负样本是不同证据。PDF 转换排版、公式、OCR和占位图修复均不在范围内。

机器核验：[verification.json](../../.paper-fetch-runs/official-reacquisition-2026-09-19/verification.json)；官方终态：[batch-results.jsonl](../../.paper-fetch-runs/official-reacquisition-2026-09-19/batch-results.jsonl)；入库索引：[registered.json](../../.paper-fetch-runs/official-reacquisition-2026-09-19/registered.json)。

## 验证

`PYTHONPATH=src uv run python -m pytest tests/integration/test_fixture_provenance.py -q`：7 passed、2100 subtests passed。

`PYTHONPATH=src uv run python -m pytest tests/golden/test_completed_asset_evidence.py tests/golden/test_wiley_gcb16758_formulas.py -q`：22 passed。两条命令均使用项目默认并行配置。测试日志保存在本轮运行目录；这些既有 golden 回归通过不代表新增27篇完整内容回放。未运行 live pytest、未改版本、未提交或触发 GitHub CI。
