# 2026-09-18 有界资产实体补证

本记录补充此前 P05／P18／P19 的离线结论，不改写历史记录。298 个目标使用已捕获原文独立映射的官方候选；实际 67 次 HTTP 请求，66 个 HTTP 200 可解析实体，1 个 HTTP 403。T&F 首次请求被拒即停止该 provider，余下 231 个未调度。Wiley 先前 HTTP 403／Camoufox 超时后无状态变化，本轮没有再次请求。没有认证、签名、访问边界、全局 retry 或 cache 调整。

66 个响应已另存各论文 `acquisition/asset-evidence-2026-09-18/`，保留原捕获并登记 provenance 与 fixture manifest。请求 URL 哈希、时间、状态、响应 SHA-256、字节、类型、解析结果及文件索引见 [机器证据](problem-fixes-2026-09-18-asset-evidence.json)。精确官方 URL（含原查询串／签名）以各响应 provenance 为准；报告显示地址可能经日志脱敏，不能用其复造请求。首轮脚本本地参数校验失败发生在联网前；记录中的 invocation 2 仍是首个 HTTP 请求，无 HTTP 重试。

## P05：53 个历史对象全部组装

新增 ACS 10、AIP 6、Royal 13 个实体，连同已验证的 24 个文件共 53 个。旧／新正文对象 ID、路径与 rendition 映射沿用 [此前独立核验](problem-fixes-2026-09-18-p05.json)，新 URL 的到期日不作为成功证据。所有文件经既有下载、旧正文组装及统一 acceptance：53 个旧 URL 均不再出现在最终正文，各本地对象输出一次，逐篇完整原分母保留。Royal `rsos.150470` 的两张既有 viewer 捕获继续复用，另三张使用新实体；不同 preview／full-size 事实仍分开记录。

| DOI | 原对象／本地 | body 资产状态 | full-size／accepted preview／fallback preview |
| --- | ---: | --- | ---: |
| `10.1021/acsomega.3c06992` | 8/8 | complete | 8/0/0 |
| `10.1021/acsomega.4c03987` | 10/10 | degraded | 0/9/1 |
| `10.1063/5.0188905` | 6/6 | complete | 0/6/0 |
| `10.1093/bioinformatics/btaa823` | 9/9 | complete | 9/0/0 |
| `10.1098/rsif.2019.0334` | 5/5 | complete | 5/0/0 |
| `10.1098/rsos.201188` | 3/3 | complete | 2/1/0 |
| `10.1098/rsos.201200` | 3/3 | complete | 3/0/0 |
| `10.1098/rspb.2020.0097` | 2/2 | complete | 1/1/0 |
| `10.1098/rsta.2019.0558` | 2/2 | complete | 2/0/0 |
| `10.1098/rsos.150470` | 5/5 | complete | 3/2/0 |

十篇 `local_body_assets_satisfied=true`。ACS `4c03987` 仍有一个未获 accepted-preview 身份的回退图，保留 `asset_fidelity_degraded`；未宣称全部 full-size 或 overall complete。远程链接 profile 的原语义未改变。

## P18：34 个目标图形实体闭合，全文分母不缩小

29 个 object SVG 均取得真实 HTTP 200 可解析响应；DDPM 的 5 个内联 SVG 复用已捕获 DOM，经原 ArtifactStore／预算机制落盘。34 个节点均实际本地化且在正文输出一次，图形／子图身份与原位图注保留。整篇其他图片仍按原候选计入，不能把目标集合完成写成所有论文资产 complete。

| arXiv | 全文 body 候选 | 本地目标 | body 状态 |
| --- | ---: | ---: | --- |
| `1406.2661v1` | 10 | 4 | degraded |
| `2006.11239v2` | 23 | 5 | degraded |
| `2605.06659v1` | 1 | 1 | complete |
| `2605.06663v1` | 13 | 12 | degraded |
| `2605.06665v1` | 9 | 7 | degraded |
| `2605.06666v1` | 6 | 3 | degraded |
| `2605.06667v1` | 16 | 2 | degraded |

合计全文 78 个 body 候选，34 个目标实体本地可读，其余 44 个本轮未获取。

## P19：八个原位公式 PNG 与局部组装修复

两篇 8 个 inline-graphic 都取得真实 PNG（并非按扩展名猜测 GIF），逐个 PyMuPDF 解码且经主代理目视确认是清晰公式，不是响应占位图；未做 OCR 或将识别文字回写。真实回归逐项核对源 `inline-formula` 的 info:doi → provenance requested URL 的 id → downloaded.download_url → 文件 SHA → 最终该源位置的本地链接及顺序，不能以哈希集合相同代替身份核验。

实体组装暴露两个 PLOS 局部问题：同一 `/article/file` 的不同 query 曾相互误配；未获取的 info:doi 资产曾漏出严格本地验收分母。现按真实 DOI 对象身份在 PLOS 组装时匹配，未下载对象恢复各自官方 HTTP 链接及来源；不改全局 matcher／acceptance。Article sections、重复渲染、body／all／none 的既有公式行为经最小零／部分／全部下载回归。

pbio 全文 body 9 个候选中 1 个本地，pcbi 18 个中 7 个本地：共 27 个 body 候选、8 本地、19 未获取。公式图片本身的完整分母为 11（pbio 4、pcbi 7），另 3 个 pbio display 公式未获取；含 supplementary 的所有候选为 32。8 个新图仍保留 preview/fidelity 降级事实，两篇 body 均 degraded，不声称全文资产 complete。

## 仍保留的外部证据缺口

P17 原文 232 个公式 GIF 地址各不相同。首个官方地址响应 HTTP 403（HTML、5864 字节，SHA-256 `03cc4161d67b0b6d7e6b0b09058e34cb4b33a7cb34b4a0463c0f29be9333cfe7`），停止同 provider，余 231 未调度；不能推称它们逐项 403。P02 Wiley 的既有拒绝／超时是独立缺口，本轮没有请求或新增可读像素证据。

## 验证与复现

- 真实整篇与实体回放：`tests/golden/test_completed_asset_evidence.py`（19 篇）及 `tests/support/asset_evidence_replay.py`；新测试已登记 ledger。
- PLOS 最小边界：`tests/unit/test_plos_asset_identity_assembly.py`；既有 PLOS／JATS 回归随官方 HTTP 链接契约更新。
- 新来源全量验证由主代理完成：`tests/integration/test_fixture_provenance.py`，7 passed、1807 subtests passed（新增 66 个响应检查）。
- 关联定向：`PYTHONPATH=src uv run python -m pytest tests/unit/test_plos_provider.py tests/unit/test_plos_asset_identity_assembly.py tests/golden/test_plos_provider.py tests/golden/test_jats_problem_fixes.py tests/golden/test_completed_asset_evidence.py -q` → **40 passed，47.91s**（默认并行）。上述改动文件 Ruff 通过。

最终 19 篇 Markdown、Article JSON、acceptance JSON 与真实本地文件保存在 `.paper-fetch-runs/problem-fixes-2026-09-18/asset-evidence/final/`；逐篇路径、文件 SHA 和完整 acceptance 已收录机器证据。离线回放禁止真实 socket 连接。验收字段中的 attempted／failed 是原资产审计语义；实际网络次数仅按上文 HTTP 记录统计，未获取对象不伪报成实际网络失败。
