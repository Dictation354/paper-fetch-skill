# P05：历史签名图片对象与最终资产映射

本轮只处理 P05；全部离线，未请求远程图片、启动浏览器、修改签名、扩大全局 cache/retry 或修整 PDF。机器证据见 [逐对象映射与验收](problem-fixes-2026-09-18-p05.json)。

## 已证实的结果

十篇历史 Markdown 的 **53 个图片对象均完成原始正文→新捕获正文的身份核对**。逐项记录旧/新 URL、源文件 SHA-256、发布者 `path-from-xml`、DOM ID、原图/预览字段及最终链接；49 处有相同 host/path 的当前 URL，Royal `rsos.150470` 的其余 4 处通过同一发布者对象的原图/预览声明核对。身份核对没有把不同 rendition 的字节视为相同，也不证明远端当前可访问。

| DOI | 对象数 | 已捕获文件经过旧正文组装 | 另有文件、未完成本次组装 | 缺图片实体证据 |
| --- | ---: | ---: | ---: | ---: |
| 10.1021/acsomega.3c06992 | 8 | 8 | 0 | 0 |
| 10.1021/acsomega.4c03987 | 10 | 0 | 0 | 10 |
| 10.1063/5.0188905 | 6 | 0 | 0 | 6 |
| 10.1093/bioinformatics/btaa823 | 9 | 9 | 0 | 0 |
| 10.1098/rsif.2019.0334 | 5 | 5 | 0 | 0 |
| 10.1098/rsos.150470 | 5 | 2 | 0 | 3 |
| 10.1098/rsos.201188 | 3 | 0 | 0 | 3 |
| 10.1098/rsos.201200 | 3 | 0 | 0 | 3 |
| 10.1098/rspb.2020.0097 | 2 | 0 | 0 | 2 |
| 10.1098/rsta.2019.0558 | 2 | 0 | 0 | 2 |
| 合计 | 53 | **24** | **0** | **29** |

22 个已组装对象复用 2026-09-15 的合法捕获源与图像响应，经既有候选提取、`download_assets`、provider `to_article_model`、最终 Markdown 渲染。图像实体的 size/SHA-256 与 provenance 一致；JPEG/PNG 可解码，SVG 可解析；每个本地链接实际存在并匹配对应捕获文件。三篇的 `body` 和严格 `require_local_body_assets=true` 资产分面均为 `complete`，分别为 8/8、9/9、5/5；旧签名不再留在对应最终图片链接中。正文保持原始旧捕获内容，无人工替换正文 URL。

Royal `rsos.150470` 的 Figure 1、2 也已复用真实捕获的 article/viewer/image 完成旧正文→本地文件→最终Markdown，两个链接各出现一次，文件hash与捕获一致。Figure 1沿用文章已声明的原图直链；Figure 2经现有Royal viewer解析得到原图。响应记录的签名虽已脱敏，但同论文、完整对象路径、rendition和非签名参数与原始article/viewer逐项一致，离线transport绑定不证明任何签名当前有效。整篇仍保留5对象完整分母，严格local为2/5、`degraded`，其余3张远程图片没有被隐藏或缩小验收范围。

其余未落盘对象保留远程资产事实。`none` 为 `not_requested`；`body` 保留既有远程链接并由现有 evaluator 报告 `degraded`；严格 local 不满足。这里没有把远程 profile 改成必须下载，也没有把一个未过期 URL 计为成功下载。所有直接 payload 回放的 `overall` 仍为 `degraded`：不伪造完整 acquisition provenance 来升级为真实 fetch 成功。

## 修复的实际 owner

1. **ACS 表内 Graphic 漏发现。** `acsomega.4c03987` 的 `.table-wrap .fig-graphic#gr8/#gr9` 在真实新正文中有完整签名图片 URL，但原先只发现八张普通 Figure。ACS 的资产提取副本现在也暴露两张表内 Graphic；正文表格和 URL 原值不变，候选由 8 变为 10，未臆造 full-size。最小回归证明旧签名正文可绑定到对应当前 rendition 的本地路径；真实全文回归证明两对象被发现。两张图的真实像素尚未捕获，不能宣称已完成本地归档。
2. **OUP 同对象因签名改变而重复计数。** 原合并以完整签名 URL 为键；旧正文配九张真实新捕获图片时，Markdown 已本地化，Article 却仍含九个旧远程重复项，严格 local 为 degraded。仅修改 Oxford 的图像合并键：比较 OUP CDN 的 host、完整 path/rendition 与非签名参数；请求/来源 URL 的签名仍原样保留。修复后九对象只计一次，严格 local 通过。不同论文路径、预览/原图、host 或 crop 参数均不合并。

这些修复不承诺缓存自动刷新。将新远程候选单独配给旧正文的回放仍保留 ACS 两张表内 Graphic 的旧签名；OUP 仅配新远程链接也不等于本地归档。生产使用新捕获正文时按该正文链接输出；旧正文复用的成功证据限于上面的 24 个本地对象与最小边界回归。

## 仍缺的证据与关闭条件

- Royal 两张现有实体已完成组装；没有留下已知可执行的本地组装步骤。缺口仅剩下列没有实体的29对象。
- 剩余 29 对象缺少图像实体。逐项对象名、对应源 DOM、URL 和 rendition 见 JSON 中 `status=remote_bytes_unverified`；它们未被判定为 403、损坏或不可获取。
- P05 **部分修复、证据缺口保留**。关闭需要补齐尚未完成的旧正文资产组装证据，或明确限定只要求保留远程链接的使用范围；不得把本次对象身份对应或新签名期限替代图片可访问性证据。

## 复核

- `tests/golden/test_historical_signed_assets.py`：四篇、24 个真实捕获图片，旧正文→现有下载/组装→严格 local acceptance；前三篇资产完整，Royal五对象中2个本地、3个远程。
- `tests/golden/test_acs_provider.py`：真实 ACS 表内 Graphic 候选及原 URL 保留。
- `tests/unit/test_acs_table_graphic_assets.py`：最小结构、排除导航、旧签名到本地路径的组装边界；不宣称实际文件可读性。
- `tests/unit/test_oxford_signed_asset_identity.py`：签名更换合并及跨对象/rendition/host/crop 负例。
- 最终 Markdown 与完整 acceptance 位于 `.paper-fetch-runs/problem-fixes-2026-09-18/p05/<sample_id>/`，路径和 SHA-256 已写入机器记录。

验证结果（沿用默认 pytest 并行配置）：相关 ACS/OUP unit、golden 与三篇历史资产回归 **48 passed**；新增 ACS 组装边界及测试分层/证据登记 integration **32 passed**；改动文件 Ruff 检查通过。此前相关捕获资产/Royal golden **22 passed**。未执行联网验证、版本发布或 CI。

Royal追加核验：`PYTHONPATH=src uv run python -m pytest tests/golden/test_historical_signed_assets.py -k royal -q` → **2 passed in 4.36s**；变更文件Ruff通过。无联网，也未修改Royal生产代码；复用既有原图优先与viewer补充逻辑即可完成。

后续阶段：本记录保留当时的离线验证与证据边界；当天稍后新增的真实图片/SVG响应、PLOS实体组装修复及实际分母见 [最终资产补证](problem-fixes-2026-09-18-asset-evidence.md)。此链接不把最初离线验证改写为联网结果。
