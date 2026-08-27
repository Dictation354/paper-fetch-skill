# 全出版社性能与图片质量优化报告（2026-08-26）

本文记录 19 家官方 provider 的资源下载性能优化、四家图片质量优化及同日
live 验证结果。报告中的公网耗时只代表本机、本时段和固定样本，不是长期 SLA。

> 2026-08-27 后续：本文的 Wiley 401/403 readiness 短路是修复前快照。
> 当前实现已改为稳定正文、精确 DOI、无阻断信号与最终全文验收共同约束的
> 有界复核；PF-LIVE-011 已经 headed 3/3 和 headless 1/1 专项关闭。原生
> SIGABRT 也已作为偶发/上游故障归档，不再阻塞当前门槛；详见
> [`problems.md`](../problems.md)。

## 1. 结论

实现侧已经完成以下收口：

- 所有会下载正文资源的 provider 都具有显式 `assets` route；catalog 当前为
  20 个 provider、82 条 route、40 个 route family。
- 公共资源默认并发为 2、单次直连超时为 20 秒；具备可靠浏览器恢复能力的
  provider 不再对同一失败资源执行多次长直连重试。
- 每篇论文先探测首个资源；同一 fetch-session/host 内，在直连失败且浏览器恢复
  成功后开启并发安全熔断，剩余同源资源直接复用已验证恢复路径。状态不跨论文
  持久化。
- 逐资源诊断补充候选解析、排队、DNS policy、连接到响应头、响应体、浏览器恢复、
  重试等待、转换、保存和总耗时；浏览器准备/释放也单独计时。IEEE 自定义链路
  产生相同结构的 13 条逐资源计时。
- Wiley 优先 `/doi/{doi}` 并对 401/403 readiness 短路；Science 仅复用指纹一致的
  preflight HTML；PNAS readiness 与 `#bodymatter` 解析器对齐；MDPI 对同源恢复
  使用 fetch 生命周期熔断。
- arXiv 优先官方 source archive 原图，Copernicus 优先官方 JATS 原图，AIP 使用
  最大 `srcset` 候选，T&F 使用既有最高质量官方候选。官方未暴露原图时，AIP/T&F
  输出稳定的 `official_full_size_not_exposed`，且不把预览标成 full-size。

性能和质量均有实质收益，但本轮 live 总体验收**未全部通过**：Wiley 当前被出版商
访问边界拒绝；AIP 计划内三轮只有一轮完整，并在并发 4 benchmark 中退化为 PDF；
修改前仅保存了一轮完整 19 家基线，无法事后补造计划要求的三轮前置中位数。

## 2. 条件与证据边界

- 固定样本来自
  [`tests/provider_benchmark_samples.py`](../tests/provider_benchmark_samples.py)。
- 串行 live 使用 `artifact_mode=all`、`asset_profile=body`、Camoufox 和 `-n 0`。
  使用 `-n 0` 是因为 live 测试依赖真实站点、浏览器 profile 与预检状态；普通
  unit/integration 验证仍使用 `pyproject.toml` 的默认并行配置。
- 修改前完整基线：
  `../.paper-fetch-runs/live-publisher-body-audit-20260826-clKtwI/live-acceptance.json`。
  该基线 19/19 complete，provider 总耗时为 607.489 秒；ACS 为 154.450 秒，AIP
  为 144.117 秒。
- 修改后三轮 targeted 结果：
  `../.paper-fetch-runs/perf-quality-20260826/round-{1,2,3}/live-acceptance.json`。
- 最终 19 家串行结果：
  `../.paper-fetch-runs/perf-quality-20260826/final-19-post-rollback/live-acceptance.json`。
- 并发 benchmark：
  [`benchmark.md`](../.paper-fetch-runs/perf-quality-20260826/benchmark-all-19/benchmark.md)
  和 `benchmark.json`。
- 四家严格图片结果：
  `../.paper-fetch-runs/perf-quality-20260826/strict-quality-round-{1,2,3}/`。

修改前不存在计划要求的热点两轮补测和全 19 家并发 1/2/4 报告；在代码已经修改后
重跑不能充当“修改前”证据。因此下文将唯一历史快照称为“基线”，不把它描述为
三轮中位数，也不对缺失数据作推算。

## 3. 性能结果

### 3.1 Targeted 三轮

时间均为端到端秒数。AIP 第三轮在 pytest 现场耗时约 113.933 秒，但异常发生在
terminal record 正常收口之前，JSON 中保留的 `total_seconds` 为 0；表中使用现场
墙钟并明确标为失败。

| Provider | 历史基线 | 三轮结果 | 修改后中位数 | 相对变化 | 结论 |
| --- | ---: | --- | ---: | ---: | --- |
| ACS | 154.450 | 34.554 / 29.766 / 73.326 | 34.554 | -77.6% | 3/3 complete；达到 30% 门槛，未再出现约 120 秒单资源直连等待 |
| AIP | 144.117 | 134.914 failed / 49.092 complete / ≈113.933 failed | ≈113.933 | -20.9% | 未达到计划内三轮性能和稳定性门槛 |
| Science | 28.036 | 20.814 / 17.268 / 24.257 | 20.814 | -25.8% | 达到 15% 门槛 |
| PNAS | 33.598 | 30.948 / 29.610 / 26.885 | 29.610 | -11.9%，-3.988s | 达到绝对 3 秒门槛 |
| IEEE | 29.508 | 32.868 / 26.198 / 29.693 | 29.693 | +0.6% | preflight HTML 复用无收益，已撤回；保留正式导航、完整性校验和逐资源计时 |
| MDPI | 21.014 | 19.168 / 15.023 / 14.851 | 15.023 | -28.5% | 达到 15% 门槛 |
| arXiv | 4.248 | 6.594 / 4.326 / 6.137 | 6.137 | +44.5%，+1.889s | 官方 source 原图带来可见成本；质量收益保留，性能门槛未通过 |
| Copernicus | 10.965 | 13.754 / 13.636 / 12.936 | 13.636 | +24.4%，+2.671s | 官方 JATS 原图带来可见成本；质量收益保留，性能门槛未通过 |
| T&F | 11.920 | 11.204 / 13.320 / 12.595 | 12.595 | +5.7%，+0.675s | 未同时超过 10% 和 1 秒回退阈值 |
| Wiley | 40.772 | 2.959 skip / 2.871 skip / 3.061 skip | 不可比 | 不可比 | 三轮均为 `publisher_access_denied`，短路有效但不能作为性能胜利 |

AIP 另有三轮成功 HTML 抓取 49.092、48.230、24.125 秒，中位数 48.230 秒，较
历史单轮基线降低 66.5%；三轮均为 4 个本地预览且原因一致。但这些补充成功样本
不能替换计划内失败轮次，所以只用于证明约 120 秒资源阻塞已消失，不用于宣告总门槛
通过。

ACS 三轮逐资源计时聚合中，8 个资源的连接到响应头总和分别为 2.247、2.058、
42.191 秒；AIP 成功 HTML 轮次的 4 个资源总资源阶段约 2.1～22.5 秒。公共直连硬
超时为 20 秒，产物中未再出现单个约 120 秒的直连等待。

### 3.2 最终 19 家串行快照

| Provider | 基线 | 最终 | 变化 | 最终状态 |
| --- | ---: | ---: | ---: | --- |
| Elsevier | 8.413 | 7.656 | -9.0% | complete |
| Springer | 26.385 | 26.666 | +1.1% | complete |
| Wiley | 40.772 | 2.995 | 不可比 | skipped / publisher access denied |
| Science | 28.036 | 10.672 | -61.9% | complete |
| PNAS | 33.598 | 28.141 | -16.2% | complete |
| IEEE | 29.508 | 28.645 | -2.9% | complete；已撤回无收益复用 |
| arXiv | 4.248 | 4.927 | +16.0%，+0.679s | complete |
| Copernicus | 10.965 | 13.186 | +20.3%，+2.221s | complete |
| AMS | 37.281 | 37.836 | +1.5% | complete |
| MDPI | 21.014 | 15.260 | -27.4% | complete |
| Royal Society | 10.927 | 9.868 | -9.7% | complete |
| Annual Reviews | 21.327 | 22.120 | +3.7% | complete |
| PLOS | 4.225 | 4.238 | +0.3% | complete |
| Oxford Academic | 7.899 | 7.676 | -2.8% | complete |
| ACS | 154.450 | 29.555 | -80.9% | complete |
| IOP | 8.495 | 7.516 | -11.5% | complete |
| AIP | 144.117 | 44.238 | -69.3% | complete |
| Frontiers | 3.909 | 4.316 | +10.4%，+0.407s | complete |
| T&F | 11.920 | 12.661 | +6.2%，+0.741s | complete |

最终 pytest 为 18 passed、1 skipped，墙钟 318.48 秒。19 条 provider record 的耗时
总和为 318.172 秒，表面较 607.489 秒降低 47.6%；由于 Wiley 的 2.995 秒是访问
拒绝而非成功抓取，这个总和不能直接作为 19/19 性能胜利。排除 Wiley 后，可比较
provider 的单轮和为 566.717 → 315.177 秒（-44.4%），仍超过总体 20% 目标，但
它不是计划要求的“各 provider 三轮中位数之和”。

### 3.3 并发 1/2/4

| 并发 | 墙钟 | 吞吐（篇/秒） | 相对加速 | complete | non-complete |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 287.689s | 0.063 | 1.000× | 18 | 1 |
| 2 | 158.084s | 0.114 | 1.820× | 18 | 1 |
| 4 | 156.950s | 0.115 | 1.833× | 17 | 2 |

每个 provider 的观测峰值均为 1，没有 provider lane 重叠。当前实现从并发 1 到 2/4
没有吞吐回退，但 benchmark 总结果为 fail：Wiley 三档均访问受限；AIP 在并发 4
退化为 PDF，产生 source/acceptance drift。由于缺少修改前同条件 benchmark，不能
证明“相对修改前无 10% 吞吐回退”。

## 4. 图片质量三轮

四家均使用固定 DOI、`asset_profile=body`、`artifact_mode=all` 和
`--require-full-size-body-assets`，每次使用独立输出目录。表中计数仅包含请求的正文
资产；Copernicus 另有一个未请求 supplement，不进入正文 full-size 分母。

| Provider | 每轮结果（3/3 一致） | 尺寸 | 哈希与标注 | 结论 |
| --- | --- | --- | --- | --- |
| arXiv | 1/1 `arxiv_source` full-size | 2745×1370 | 每轮 1 个唯一 SHA；无 preview 标注 | 通过 |
| Copernicus | 8/8 full-size | 8 张均宽 2067，高 1396～3188 | 每轮 8 个唯一 SHA；无 preview 标注 | 通过 |
| AIP | 0 full-size，4/4 本地 preview | 宽 520，高 287～553 | 每轮 4 个唯一 SHA；4/4 原因均为 `official_full_size_not_exposed` | 合法保留预览，未误标 |
| T&F | 0 full-size，9/9 本地 preview | 8 张宽 500，另 1 张 457×500 | 每轮 9 个唯一 SHA；9/9 原因均为 `official_full_size_not_exposed` | 合法保留预览，未误标 |

AIP/T&F 的 strict full-size 义务本身不会被预览满足；本轮接受的是计划定义的例外：
三轮均无法从官方页面发现更大候选，保留不低于原基线的最高质量预览，并提供稳定、
可审计的机器原因。没有使用 PDF 渲染图冒充官方 HTML 原图。

## 5. 保留与撤回

保留：

- 显式 assets route、20 秒超时、并发 2、恢复型 provider 的直连重试 0；
- 首资源探测、fetch/host 熔断、并发安全和完整计时；
- Wiley 状态短路、Science 安全复用、PNAS readiness、MDPI 熔断；
- arXiv/Copernicus 官方原图和 AIP/T&F 稳定预览原因；
- IEEE 正式正文导航、正文完整性校验及 13 项资产计时。

撤回：

- IEEE preflight HTML 复用。三轮中位数 29.693 秒，相对 29.508 秒基线没有达到
  15% 或 3 秒收益门槛。撤回后 targeted 复验为 25.882 秒，最终全量为 28.645 秒，
  均保持 13/13 full-size。
- Springer/AMS 并发提升到 3 未启用；没有 A/B 证据证明收益，继续使用并发 2。
- 没有引入跨 provider 浏览器进程复用。

## 6. 自动化验证

本地最终验证：

- `PYTHONPATH=src uv run python -m pytest tests/unit -q`：2912 passed，1 skipped，
  568 subtests，158.53 秒；使用项目默认并行配置。
- integration/devtools 相关集合：284 passed，2 skipped，15 subtests，101.87 秒。
- Ruff、format、复杂度治理门：通过；45 个既有复杂度例外没有增加。
- provider catalog 治理：20 providers、82 routes、40 families，通过。
- `python scripts/validate_macos_adaptation.py`：通过，contract v4.1.0、9 个 change。
- `scripts/test-macos-contract.sh`：163 passed、24 subtests。该结果来自 WSL/Linux
  原生 Linux Python，只是静态/便携契约证据，不能替代原生 `macos-15`/CPython
  3.14 gate。
- 对本任务产物执行通用 secret scan：1504 个文件、0 命中、0 错误。运行时没有
  可扫描的敏感环境变量名（`scanned_secret_name_count=0`），因此这不能替代携带真实
  凭据时的 raw/URL-encoded sentinel 验证。
- 已同步 GitHub CI workflow 的本地覆盖，但未触发远程 GitHub CI。

## 7. 未解决风险与后续门槛

1. Wiley 必须在合法可访问的会话/网络条件下恢复 complete，之后重跑完整 19 家；
   访问拒绝不能作为性能收益。
2. AIP 需解决“预检 ready、正式抓取偶发 HTML 不完整/转 PDF”的稳定性，并重新完成
   三轮全胜及并发 4 无 drift；当前补跑成功不能覆盖失败。
3. arXiv/Copernicus 的 full-size 质量提升分别增加约 1.9/2.7 秒 targeted 中位数。
   若性能门槛必须严格优先于图片质量，应继续优化同一 fetch 内的官方原图发现与下载，
   或由产品决策明确接受这一质量换时延，而不是把当前结果宣告为性能通过。
4. 需要在任何后续代码修改之前、相同环境中重新建立三轮串行基线，并补齐修改前并发
   1/2/4 benchmark；当前缺口无法通过事后重跑修复。
5. 原生 macOS 与 release CPython 3.11～3.14 矩阵仍需 GitHub CI 提供最终证据。
