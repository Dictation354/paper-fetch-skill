# P02 定向修复与核验（2026-09-18）

最新结论：**公式输出及原生 MathML 资产预处理已修复，26 个位置的图片实体证据已跨两轮补齐**。最新正式重抓为全文成功、5 张正文图和 25/26 张公式图本地化，仅公式 2 遇到验证页，严格本地验收仍为 degraded；该公式前轮已有可读实体。详见[后续修复与正式重抓记录](wiley-native-formula-assets-2026-09-18.md)。下文保留早期捕获、失败尝试和局部修复历史，不代表最新资产状态。

## 新全文来源

- DOI：`10.1111/gcb.16758`。
- 标题：Spring phenology rather than climate dominates the trends in peak of growing season in the Northern Hemisphere。
- [本轮原始 DOM](../../tests/fixtures/golden_criteria/10.1111_gcb.16758/acquisition/problem-fixes-2026-09-18-p02/002-rendered-dom.html)；[来源登记](../../tests/fixtures/golden_criteria/10.1111_gcb.16758/acquisition/provenance.json)。
- 请求和最终页面：`https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16758`，HTTP 200。
- 捕获时间：`2026-09-18T05:45:05.396552+00:00`；大小：1247149 bytes；SHA-256：`0f10808a0825a95c781db539819c770bf23481571faf44c48f20c6c2e02232ea`。
- 使用现有身份解析和 Camoufox runtime、既有 Wiley storage-state；保留原有访问检测，正常导航并逐个滚动公式等待 lazy 渲染，没有人工认证或挑战绕过。静态 doctor 为 ready。

此前 15 条捕获/产物哈希已逐一验证；五份旧文章 HTML/DOM 确实没有方法正文。该历史判断现由本次新全文证据补齐。旧 `original.html` 仅用于位置/地址对照，未替换新全文验收。PDF 未参与转换或修复。

## 局部修复

新 DOM 有 26 个空 MathML，滚动后仍无数学内容，但每处均有相邻 `.fallback__mathEquation[data-altimg]`。原路径从 MathML 内查找 fallback，遗漏了 MathJax wrapper 外的 19 个行内地址；七个 display 公式还能通过外层布局找到图片，却保留根相对路径。

`paper_fetch.providers._wiley_html.prepare_source_images` 现在解析 Wiley fallback 的根相对地址，并仅把紧邻 `mjx-container` 中唯一 MathML 与该地址绑定。仍优先结构化 MathML，不跨正文、其他元素或多个公式节点猜测身份，不改变共享转换策略。

真实新全文通过现有 canonical Wiley builder 回放：修复前 19 个 `[Formula unavailable]`、7 个图片回退；修复后 0 个缺失占位、26 个图片回退、0 个根相对图片链接。对应输出见 [fixed.md](../../.paper-fetch-runs/problem-fixes-2026-09-18/p02/fixed.md)。图片回退保持原位顺序，不声称恢复 TeX。

## 26 个位置与旧地址去向

位置为新 DOM 中 MathML 文档顺序。26 条新地址逐项等于旧输入的相邻 `data-altimg`；七处旧图片输出的位置是 1、2、3、4、5、7、25。下列路径全部以 `https://onlinelibrary.wiley.com` 解析为最终 Markdown 链接；其余 19 处也保留各自官方地址，未借用其他公式图片。

| 位置 | 最近 section ID | 新旧相同的官方路径 | 修复后输出 | 远程像素核验 |
| ---: | --- | --- | --- | --- |
| 01 | `gcb16758-sec-0009` | `/cms/asset/632e9f32-336d-48a0-a71b-caf653454c0a/gcb16758-math-0001.png` | 第 1 个图片链接，身份/顺序匹配 | HTTP 403；Camoufox 超时 |
| 02 | `gcb16758-sec-0010` | `/cms/asset/17ff9e52-ec11-4552-bdb2-19f98ae8cd0d/gcb16758-math-0002.png` | 第 2 个图片链接，身份/顺序匹配 | 未请求 |
| 03 | `gcb16758-sec-0010` | `/cms/asset/4806ec43-9a73-4f4c-a13e-d0d6afc4e353/gcb16758-math-0003.png` | 第 3 个图片链接，身份/顺序匹配 | 未请求 |
| 04 | `gcb16758-sec-0011` | `/cms/asset/996e0f2d-fca0-4355-a20b-c33b44c14bb4/gcb16758-math-0004.png` | 第 4 个图片链接，身份/顺序匹配 | 未请求 |
| 05 | `gcb16758-sec-0011` | `/cms/asset/7320baf6-1aaf-4b4f-ba95-0881ba628b11/gcb16758-math-0005.png` | 第 5 个图片链接，身份/顺序匹配 | 未请求 |
| 06 | `gcb16758-sec-0012` | `/cms/asset/3484f212-2f2a-41a5-87c6-e325e61248ed/gcb16758-math-0006.png` | 第 6 个图片链接，身份/顺序匹配 | 未请求 |
| 07 | `gcb16758-sec-0012` | `/cms/asset/a1306bc1-da6e-4b9a-a889-9b8bf9f769c0/gcb16758-math-0007.png` | 第 7 个图片链接，身份/顺序匹配 | 未请求 |
| 08 | `gcb16758-sec-0012` | `/cms/asset/995fc9cc-77a8-4a53-9285-7027b471c831/gcb16758-math-0008.png` | 第 8 个图片链接，身份/顺序匹配 | 未请求 |
| 09 | `gcb16758-sec-0012` | `/cms/asset/2711e420-0495-4804-a9ac-e2a887903a08/gcb16758-math-0009.png` | 第 9 个图片链接，身份/顺序匹配 | 未请求 |
| 10 | `gcb16758-sec-0012` | `/cms/asset/8f24f698-8083-47dd-9ed8-19cd2d60e9dc/gcb16758-math-0010.png` | 第 10 个图片链接，身份/顺序匹配 | 未请求 |
| 11 | `gcb16758-sec-0012` | `/cms/asset/1b01b53a-8137-4abd-b12f-0709cac81b92/gcb16758-math-0011.png` | 第 11 个图片链接，身份/顺序匹配 | 未请求 |
| 12 | `gcb16758-sec-0012` | `/cms/asset/da70aee1-aac7-445e-b62d-fac68d82ec03/gcb16758-math-0012.png` | 第 12 个图片链接，身份/顺序匹配 | 未请求 |
| 13 | `gcb16758-sec-0012` | `/cms/asset/8993168e-c0a1-4991-afdb-1f7af86161e0/gcb16758-math-0013.png` | 第 13 个图片链接，身份/顺序匹配 | 未请求 |
| 14 | `gcb16758-sec-0012` | `/cms/asset/b514545b-bb40-4144-886d-fad9d72a63e8/gcb16758-math-0014.png` | 第 14 个图片链接，身份/顺序匹配 | 未请求 |
| 15 | `gcb16758-sec-0012` | `/cms/asset/6c5ed3db-d59e-4d88-8828-ed61f6166770/gcb16758-math-0015.png` | 第 15 个图片链接，身份/顺序匹配 | 未请求 |
| 16 | `gcb16758-sec-0012` | `/cms/asset/327e56e7-686a-4849-946f-a77190b4ae9a/gcb16758-math-0016.png` | 第 16 个图片链接，身份/顺序匹配 | 未请求 |
| 17 | `gcb16758-sec-0012` | `/cms/asset/b9915884-063c-4b1c-a488-ed786c7d9455/gcb16758-math-0017.png` | 第 17 个图片链接，身份/顺序匹配 | 未请求 |
| 18 | `gcb16758-sec-0012` | `/cms/asset/4bfe6b83-63e9-47d2-af76-39d086f81a03/gcb16758-math-0018.png` | 第 18 个图片链接，身份/顺序匹配 | 未请求 |
| 19 | `gcb16758-sec-0012` | `/cms/asset/0422e339-b612-4b5f-8fd9-7f23b75c7cab/gcb16758-math-0019.png` | 第 19 个图片链接，身份/顺序匹配 | 未请求 |
| 20 | `gcb16758-sec-0012` | `/cms/asset/20f1589b-1fd6-43ea-9a44-5f9a05449da9/gcb16758-math-0020.png` | 第 20 个图片链接，身份/顺序匹配 | 未请求 |
| 21 | `gcb16758-sec-0012` | `/cms/asset/b79f7d08-f11b-47f7-9dfa-5fab0a9225e2/gcb16758-math-0021.png` | 第 21 个图片链接，身份/顺序匹配 | 未请求 |
| 22 | `gcb16758-sec-0012` | `/cms/asset/36a83f0c-eb12-4982-8c02-a7f25e1e494f/gcb16758-math-0022.png` | 第 22 个图片链接，身份/顺序匹配 | 未请求 |
| 23 | `gcb16758-sec-0012` | `/cms/asset/b0010644-23c6-4d68-8564-47a7579b6c72/gcb16758-math-0023.png` | 第 23 个图片链接，身份/顺序匹配 | 未请求 |
| 24 | `gcb16758-sec-0012` | `/cms/asset/bcc8ea48-7253-43dd-ab8c-7e62aa531cfd/gcb16758-math-0024.png` | 第 24 个图片链接，身份/顺序匹配 | 未请求 |
| 25 | `gcb16758-sec-0012` | `/cms/asset/be79d1e0-066d-46ac-a976-598e27c31163/gcb16758-math-0025.png` | 第 25 个图片链接，身份/顺序匹配 | 未请求 |
| 26 | `gcb16758-sec-0012` | `/cms/asset/767f15b3-7bae-48d3-9f55-c62f62eae8f5/gcb16758-math-0026.png` | 第 26 个图片链接，身份/顺序匹配 | 未请求 |

## 图片访问与剩余条件

首张图片使用现有 HTTP transport 请求返回 403，立即停止该路径；随后按用户指定 Camoufox、既有 provider 状态和正常浏览器图片入口读取同一地址，`Page.goto` 在 115813 ms 超时。未改变访问权限或执行认证。其余 25 张未请求，不能把首张失败外推成全部失败。没有捕获到可验证像素，不把绝对链接或本地 Markdown 当作图片可读证明。

- [HTTP 请求结果](../../.paper-fetch-runs/problem-fixes-2026-09-18/p02/assets.json)。
- [Camoufox 图片结果](../../.paper-fetch-runs/problem-fixes-2026-09-18/p02/browser-assets.json)。
- [浏览器全文抓取结果](../../.paper-fetch-runs/problem-fixes-2026-09-18/p02/result.json)。

剩余关闭条件是 26 个图片的合法可读资产或其他可验证公式内容；当前仅能证明新全文身份、逐位置图片关联和正确输出。无需继续改共享 cache/retry/browser/PDF 行为。

### 用户要求的一次重试

2026-09-18 再次使用既有 Camoufox provider 状态打开论文页，HTTP 200，DOI 与首个公式地址匹配，仍有 26 个公式 fallback。页面内 `fetch` 读取发生 `Permission denied to access property "constructor"`，没有取得图片 HTTP 状态；该错误不能归因于图片服务器。记录见 [页面内读取结果](../../.paper-fetch-runs/problem-fixes-2026-09-18/p02-retry-3/result.json)。

随后为完成这次核验，重新打开论文页并使用该 Camoufox context 的 Playwright 请求接口，共享会话 cookies、携带论文页 Referer，仅定向请求首图一次。返回 **HTTP 403**，`Content-Type: text/html; charset=UTF-8`，6047 bytes，SHA-256 `6a64e4c4a7b2331b8560236d4738fe60de08adb5bc8c59b6556eeaea923e34ad`；图片解码失败，没有取得像素。这是共享浏览器会话的 HTTP API 请求，不是浏览器图片导航成功的证据。记录见 [请求结果](../../.paper-fetch-runs/problem-fixes-2026-09-18/p02-retry-3-context-request/result.json) 和 [原始响应](../../.paper-fetch-runs/problem-fixes-2026-09-18/p02-retry-3-context-request/image-response.bin)。

本次未定向请求其余 25 张，未改变生产代码或绕过访问检测；P02 仍保持图片实体证据未闭合。

## 验证

离线回放套用现有 `evaluate_fetch_acceptance`：`overall=degraded`、`identity=resolved`、`content=fulltext`、公式 `fallback_count=26 / missing_count=0`、`output=complete`。回放未执行资产下载，故 `asset.audited=false / status=unknown`；回放 envelope 无生产 acquisition，故 `provenance=partial`，真实采集来源另由 fixture provenance 保存。该验收不冒充在线完整下载成功，详见 [acceptance.json](../../.paper-fetch-runs/problem-fixes-2026-09-18/p02/acceptance.json)。

- 定向 unit：`PYTHONPATH=src uv run python -m pytest tests/unit/test_wiley_inline_formula_fallback.py tests/unit/test_atypon_browser_workflow_markdown.py -q`：23 passed。
- 定向 golden：`PYTHONPATH=src uv run python -m pytest tests/golden/test_wiley_gcb16758_formulas.py tests/golden/test_wiley_provider.py -q`：6 passed。
- 新单测只用最小片段覆盖公式图片身份、结构化数学优先、跨正文/元素边界；新 golden 使用本轮真实完整 DOM，逐项核对 26 条输出、顺序、来源哈希和公式损失诊断。两组均使用项目默认并行配置。
- 生产和测试改动的 Ruff 检查通过。
