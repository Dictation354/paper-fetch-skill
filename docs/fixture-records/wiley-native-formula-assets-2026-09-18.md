# Wiley 原生 MathML 资产预处理修复与正式重抓

结论：错误地址选择已修复。正式 CLI 重抓取得全文、5 张正文图和 25/26 张公式图，之前失败的 19 张行内公式图片全部成功。仅公式 2 本轮返回 `cloudflare_challenge`；该公式在前一轮已有同官方 URL 的可读 PNG。跨两轮已有全部 26 个公式的图片实体证据，但本轮严格本地资产验收仍为 `degraded`。

## 原因和局部修复

原生 MathML 同时提供 `location="graphic/..."`，相邻 fallback 提供 `/cms/asset/...`。资产发现先处理 MathML，优先读取其自身 `location`，随后以图片 basename 去重，导致后出现的正确 fallback 地址被丢弃。7 个块公式从外层容器开始查找，先遇到 fallback，因此表现为 7 个正确地址、19 个错误地址。此前保存的原生 DOM 离线回放生成的错误 URL 与正式失败清单逐项相同。

Wiley 的 `prepare_source_images` 现在同时支持紧邻原生 `<math>` 和含唯一 MathML 的 MathJax wrapper；若存在 `location`，图片文件名必须匹配才绑定。`extract_formula_assets` 在通用资产发现前复用该预处理，使官方地址优先参与发现与去重。只修改 Wiley provider，不调整共享地址优先级、去重、浏览器、重试或 PDF 转换；正文继续优先使用结构化 MathML。

新增的[原生 MathML DOM](../../tests/fixtures/golden_criteria/10.1111_gcb.16758/acquisition/problem-fixes-2026-09-18-p02/native-mathml-dom.html)逐字节来自此前已授权捕获，SHA-256 为 `65f6ed0fb9231a745d8adb299a4ece5ee245b3faa87c1f2f52f09c9f6f194aac`；来源登记保留捕获区间和 HTTP 200，未替换旧捕获。

## 验证

新增最小用例在修复前出现 3 项失败，复现错误地址和原生 MathML 未绑定；修复后通过。覆盖原生/MathJax 两种表示、相邻多公式独立绑定、文件名不匹配不绑定和结构化数学优先。新增 golden 调用正式 Wiley 资产发现入口，逐项核对两种真实 DOM 的全部 26 个官方 URL。

```bash
PYTHONPATH=src uv run python -m pytest \
  tests/unit/test_wiley_inline_formula_fallback.py \
  tests/unit/test_wiley_provider.py \
  tests/unit/test_atypon_browser_workflow_provider_asset_downloads.py \
  tests/golden/test_wiley_gcb16758_formulas.py \
  tests/golden/test_wiley_provider.py \
  tests/integration/test_fixture_provenance.py -q
```

结果：34 passed、1808 subtests passed，使用项目默认并行配置。三个改动 Python 文件的 Ruff 检查通过。本次未更改版本号或 CI；不把此前完整测试结果当作本次改动后的全量验证。

## 正式 CLI 重抓

运行时间：2026-09-18 09:45:20–09:45:54 UTC，耗时 34.460 秒，退出码 0。使用当前 checkout 的正式 CLI、既有 Camoufox 状态、新输出目录，无 monkeypatch；`asset_profile=body`、`artifact_mode=markdown-assets`，保存完整 Markdown 与 JSON，并要求正文资产全部本地化。完整命令见 [run.json](../../.paper-fetch-runs/wiley-official-fixed-20260918T094520Z/run.json)。

| 验收项 | 结果 |
| --- | --- |
| 身份 | `10.1111/gcb.16758`，resolved |
| 获取路径 | `wiley / browser_html / html / browser`，未使用 PDF fallback |
| 正文 | fulltext；结构化公式缺失和回退计数均为 0 |
| 正文图 | 5/5，均为 full-size |
| 公式图片 | 25/26，本地可读；25 张均为出版社认可的公式位图 |
| 原 19 张失败公式 | 全部本轮下载成功，使用 `/cms/asset/` |
| 当前失败 | 公式 2：正确官方 URL，`cloudflare_challenge` |
| 严格本地资产 | 30/31，`local_body_assets_satisfied=false` |
| 总验收 | degraded |

已逐个解码本轮 30 个图片文件，核验尺寸、大小和 SHA-256；主 JSON 与 Markdown 的哈希均与 manifest 相符。另核验前轮公式 2 的官方 URL、PNG 实体与尺寸，形成 26 个位置的跨轮证据清单。没有把前轮文件复制进本轮输出，也没有修改本轮 manifest 或将其宣称为 complete。

- [本轮 manifest](../../.paper-fetch-runs/wiley-official-fixed-20260918T094520Z/manifest.json)
- [逐资产与跨轮证据核验](../../.paper-fetch-runs/wiley-official-fixed-20260918T094520Z/verification.json)
- [正文 Markdown](../../.paper-fetch-runs/wiley-official-fixed-20260918T094520Z/Huang_et_al_2023_Spring_phenology_rather_than_climate_dominates_the_trends_in_peak_of_growing_season_in_the_Northern_Hemisphere.md)
- [前轮正式抓取 manifest](../../.paper-fetch-runs/wiley-official-20260918T092630Z/manifest.json)

本次完成了资产预处理修复及重新抓取；未再次请求被验证页阻挡的公式 2。
