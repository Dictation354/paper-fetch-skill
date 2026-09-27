# 资产观测与耗时专项审计（2026-09-27）

基于当前工作树，承接 19 个 provider 的 live 抽样。本文记录两处观测修复、T&F 的确定性等待修复，以及排除浏览器预检后的耗时分析。Wiley `10.1111/gcb.15322` 的源页面仅提供位图公式，继续保留公式语义降级；本次不修改其验收标准。

原始矩阵：[报告](../.paper-fetch-runs/publisher-live-20260927-02/report.md)。本次证据目录：`.paper-fetch-runs/asset-observability-20260927/`。测试使用当前源码与现有依赖，保留此前工作树中的 Wiley 修改。

## 已修复的问题

### Elsevier 下载记录在 XML 组装时丢失

下载器已产生 `asset_timing`，但 figure/table/supplement registry 重新构造记录时没有传递它。现在继承下载记录，再覆盖 XML 提供的标题、caption、link 等语义字段，同时保留 tier、fetcher、尺寸、字节数与来源。覆盖有 XML 对应项及未匹配下载资产。

修复后 live 样例 `10.1016/j.rse.2025.114648` 的 11/11 图完整落盘，均有计时、`download_tier=object_reference` 和 `final_fetcher=direct_http`。fetch 为 9.774 秒；11 项 body stream 累计 1.593 秒，TTFB 累计 6.704 秒。并行资产的累计时间不能直接解释为整篇墙钟时间。

### T&F 后端被写成字符串 `"None"`

下载回退边界对可选 backend 直接调用 `str()`，使 `None` 成为非空字符串，并压过 `selected_browser` 的兜底值。同时，共享图片 fetcher 未向 memoized wrapper 暴露真实后端。

现在只规范化真实字符串；未知后端保留空值，fetcher 兜底为 `selected_browser`。当前明确只创建 Camoufox context 的共享图片 fetcher 及线程包装器显式声明 `camoufox`。修复后两轮 T&F 各 9 个资产的 backend/final_fetcher 均为 `camoufox`。

### T&F 每张图片重复等待 10 秒

慢路径依次尝试 warmed article image、page fetch、context request、图片导航。此次可控复现中，图片导航等待 `DOMContentLoaded`，9 次均在约 10 秒后抛出 `TimeoutError`；此时图片实际已可用，但异常分支丢弃导航 response，随后通过 canvas 重绘为 PNG。9 次浏览器资产调用累计 96.794 秒，单是导航超时就约 90 秒。

仅对 T&F 图片导航改用 `wait_until="commit"`，随后沿用响应体、MIME/图片字节验收与已有就绪回退。真实浏览器 integration 测试验证能够保留原始响应字节。没有增加重试或调整其它 provider 的导航策略。

## Live 对比及质量边界

下表使用 catalog 测试原生 `performance.fetch_wall_seconds`，均排除预检。外围 `*-observed.json` 还包含关闭与快照开销，因此其 107.447/31.590 秒与表中数字略有差异。

| 路径 | 修复前 fetch | 修复后 fetch | 资产质量 |
|---|---:|---:|---|
| T&F，固定已有 browser-only 资产路径 | 107.271 s | 31.412 s | 前：9 全尺寸；后：8 全尺寸、1 accepted preview |
| T&F，同路径修复后补跑 | — | 13.928 s | 9/9 全尺寸 |
| Elsevier，默认路径 | 本轮未另建修复前速度基准 | 9.774 s | 11/11 全尺寸，观测字段完整 |

T&F 测试插件只在测试进程中把资产计划指定为已有 `browser_only`，目的是稳定覆盖原矩阵的浏览器资产恢复路径；这不是产品默认策略。修复前默认路径另一次测得 12.149 秒，说明默认 HTTP 资产成功时本来就不受该导航超时影响，不能把这次默认路径与慢路径混算为代码收益。

首轮修复后 Figure 7 的全尺寸候选在 page fetch 阶段两次返回 403，导航得到 HTML，原有策略转入预览候选；预览等待又触发一次 15.320 秒的 `target_image_not_loaded` 轮询。该轮质量真实记录为 500×275 的 accepted preview。补跑恢复为 1500×826 的全尺寸图；9 图均为原始 JPEG，其它图尺寸也与修复前一致。两轮均无 10 秒图片导航超时。不能由少量 live 样本推断固定加速倍数或保证每次都能取得全尺寸。

证据：[修复前受控路径](../.paper-fetch-runs/asset-observability-20260927/browser-baseline/live-acceptance.json)、[修复后](../.paper-fetch-runs/asset-observability-20260927/after/live-acceptance.json)、[修复后补跑](../.paper-fetch-runs/asset-observability-20260927/after-repeat/live-acceptance.json)。各目录的 `tandf-phases.json` 保存阶段开始时间、线程与耗时。

## 预检之外的优化空间

### T&F：已去掉固定重复等待，剩余图片预热轮询值得局部优化

确定收益来自消除每图等待 `DOMContentLoaded` 的固定超时。剩余长尾位于 `_payload_from_warmed_article_image`：发现目标但未加载时，在最多 15 秒内反复 page fetch 和轮询。首轮修复后仅预览候选命中；补跑九次该阶段合计只有 0.055 秒。因此它是条件性长尾，不是每篇固定开销。

后续可在 T&F 内区分“图片仍在加载”和“当前候选已明确不可获取”，减少无意义轮询；需先补失败原因契约，不能直接缩短所有 provider 的预热期限。本次保留这段既有策略。

### PNAS：图片传输长尾未复现，不宜直接修改重试或并发

原矩阵 fetch 46.668 秒，Figure 2/4 的 body stream 分别约 22.92/23.29 秒。未改 PNAS 代码的专项复跑 fetch 16.940 秒，4 个图片响应体读取累计仅 0.313 秒，4/4 全尺寸；预检另计 26.323 秒。

该对比支持“本轮主要是可变网络/服务端传输长尾”，不能证明固定解析开销造成原来的约 23 秒等待。优先方向是观测慢响应的首块/后续块到达时间、连接复用；需在同一路径复现后再决定局部调整。已有资产池并行，盲目增加并发或缩短全局 timeout 没有本轮证据支持。

### Science：抓取中的页面等待更重，解析重复工作其次

如果严格按出版社计，排除预检后的前三名是 T&F、PNAS、Science；arXiv 是平台，另列下节。Science 原矩阵 fetch 38.996 秒，专项复跑 28.950 秒，5/5 全尺寸图。预检另计 30.230 秒。

此次给浏览器、provider 页面准备与 HTML 提取加入只读阶段计时，按开始时间排除预检，抓取阶段分解如下：

| 抓取内阶段 | 墙钟时间 | 解释 |
|---|---:|---|
| 浏览器 HTML 获取包络 | 22.272 s | 包含下列就绪和页面准备，不能重复相加 |
| 正文就绪等待 | 9.310 s | 线程 CPU 0.117 s，主要在等待页面条件 |
| provider 页面准备 | 6.292 s | Science 可见参考文献控件展开/覆盖检查；线程 CPU 0.038 s |
| Markdown 提取 | 3.250 s | 线程 CPU 3.228 s，主要是本地解析 |
| 提取内 availability 评估 | 2.073 s | 包含结构分析 1.644 s；结构分析内 clean_container 1.306 s，三者嵌套 |
| 五图网络阶段累计 | 1.908 s | DNS、TTFB、body stream 之和；不是主要热点 |

优化优先级：先核对 Science 的正文稳定与参考文献覆盖完成条件，减少条件已满足后的等待及重复浏览器调用；不能靠直接删等待冒漏正文/引用的风险。其次评估在该 provider 内复用已选择/清理的 DOM 与结构证据，避免 availability 再解析同一片段。后者仅 Markdown 提取包络就给出约 3.25 秒的收益上界，不能解释或消除全部约 29 秒。尚未验证可安全省略的步骤，因此本次没有调整共享 readiness/acceptance。

作为上一轮的相邻慢样例，AMS 也做了补测，但本轮在预检两候选后以 `aws_waf_challenge` 跳过（35.982 秒），未进入 fetch；不能用它评价预检之外的改善，也不重复请求绕过挑战。

证据：[Science/AMS acceptance](../.paper-fetch-runs/asset-observability-20260927/science-ams/live-acceptance.json)、[Science HTML 阶段](../.paper-fetch-runs/asset-observability-20260927/science-ams/science-html-phases.json)。插件通过 `thread_time()` 记录调用线程 CPU，不代表整个浏览器进程 CPU。

### arXiv（额外平台分析）：稳定耗时主要来自限速

作为 provider 排名，arXiv 原矩阵 fetch 43.629 秒，专项复跑 43.112 秒。`source_assets` 仍配置 `qps=1/3`。17 次 rate-slot span 跨线程累计 64.806 秒，但区间并集只有 37.079 秒，约占 fetch 的 86%；实际 HTTP request 阶段累计 5.405 秒。不能把跨线程等待累计值当成墙钟时间。

限速约束决定了增加资产线程数很难改善单篇耗时。可评估请求去重或复用已经取得的 source archive，但本次尚未发现可直接删除的重复请求；保留现有节流。

证据：[默认路径复跑](../.paper-fetch-runs/asset-observability-20260927/baseline/live-acceptance.json)、[arXiv 阶段](../.paper-fetch-runs/asset-observability-20260927/baseline/arxiv-phases.json)。

## 验证

- 完整 unit：2586 passed，375 subtests。
- 完整 integration：158 passed，2 skipped，2144 subtests；新增原始图片响应契约另单独运行通过。
- Elsevier golden：185 passed，3695 subtests。
- 专项 live 共 8 passed、1 skipped：默认路径 T&F/PNAS/arXiv 3 passed；修复前受控 T&F 1 passed；修复后 T&F/Elsevier 2 passed；T&F 补跑 1 passed；Science/AMS 1 passed、1 skipped。跳过仅为 AMS 预检挑战。
- Ruff 检查通过；4 个变更源码文件 mypy 通过；`git diff --check` 通过。
- macOS 机器契约校验通过；Linux portable contract 6 passed。Linux 实测不替代原生 macOS gate。

unit/integration/golden 均复用项目默认并行配置。live 为避免共享浏览器/外部状态干扰使用 `-n 0`。本次没有改版本、提交或触发 CI。

复跑入口（每次使用新的输出目录；保留现有工具/凭据配置）：

```bash
mkdir -p .paper-fetch-runs/recheck
PYTHONPATH=src:.paper-fetch-runs/asset-observability-20260927 \
PAPER_FETCH_RUN_LIVE=1 PAPER_FETCH_LIVE_ARTIFACT_DIR="$PWD/.paper-fetch-runs/recheck" \
uv run python .paper-fetch-runs/asset-observability-20260927/run_live.py tandf --browser-only
```

测试插件、逐阶段 JSON、原始 envelope、acceptance、实际资产与日志留在证据目录；受控路径插件仅用于诊断，不修改产品配置。阶段 span 存在嵌套，不能直接相加；主线程栈采样也不能用来精确计算 CPU 百分比。
