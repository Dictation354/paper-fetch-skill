# 未提交变更精简与修复验证记录（2026-09-19）

这是本次实施的历史记录，不是测试输入。比较基线为任务开始时的未提交工作区，
不是 Git HEAD；原有未提交工作保留。版本保持 6.2.4，未提交、发布或触发 GitHub CI。

## 八类问题与处理

| 问题 | 实施结果 | 验证边界 |
| --- | --- | --- |
| 无效付费墙传播 | 审核原有 75 处调用，删除本地处理、导入、诊断等 22 处；请求、provider、fallback 和异常包装处保留 53 处 | 确认同篇正文受限才终止；隐藏提示、其他论文、普通 HTTP 错误和资产拒绝继续走原契约 |
| 付费墙职责分散、重复解析 | 受限结果组装归入 `providers/base.py`；provider 选择器归已有 availability policy；检测输入未变时跳过正文解析，始终检查新诊断 | 两个 provider 执行入口、身份变化、组装诊断、RuntimeContext 缓存及 metadata-only 行为 |
| 重试耦合与局部重复 | 请求策略和重试上下文显式携带可选 `body_access_provider`；编译器仅为正文路由赋值，IEEE 手写入口补齐；builder 合并 metadata/abstract，Wiley 复用 DOM | cooldown 名称不再决定正文检查；资产/metadata 默认不启用；重试默认值保持原值 |
| PLOS 链接往返转换 | 在现有 render policy 增加可选改写函数，以论文 DOI＋对象 ID 直接选择本地文件或官方远程链接，移除组装前替换及组装后恢复 | 零/部分/全部下载、资产预设、来源对象及 acceptance 分母；落盘禁用 basename 误匹配 |
| 台账与运行时证据重复 | 内部台账 v2 使用模块默认分类和必要 override；定义与跨模块引用完整性检查独立运行；统一读取集合管理 | 新普通测试无需函数登记；来源、收集期、共享 fixture、缓存和跨 worker 负例仍保留；unit 执行边界保留 |
| 动态内容预期解析过重 | 复杂表格网格和 MathML 来源事实固化到现有 expected，绑定源文件 SHA-256、节点哈希与定位；删除动态网格/来源公式转换 | 预期来自原始 HTML/XML，不来自生产输出；保留数值、上下标、对象归属、顺序和位置负例；PDF 输出不纳入内容修复 |
| 回放重复及日期报告依赖 | 复用 capture helper 读取记录、校验 hash/size 和构造响应；当前选择、资产和拒绝记录归 manifest/provenance/expected | URL 默认精确；仅指定 provider 的 Silverchair CDN 忽略明确签名参数，保留对象、尺寸、其他 query 和 fragment；长期测试不读取日期报告 |
| 重复实体与采集事件混淆 | 同一样本、相同来源分类下按 SHA-256 和实际字节合并实体，manifest 逻辑名映射保留；采集事件不合并 | 活动引用可解析，原始响应字节不变；独立 URL、时间、状态、headers 和身份记录保留 |

## 实际规模

- 删除 242 个重复实体，原实体合计 **129,808,300 字节**。
- fixture 文件数从 3,130 减至 2,888；总大小从 969,834,487 减至
  844,931,500 字节，计入固定来源预期后净减少 **124,902,987 字节**。
- 台账从 427,917 减至 183,918 字节（7,751 行减至 4,241 行）。
- 既有 Python 文件的生产代码净增 45 行、测试代码净增 102 行：删除重复流程和
  动态解析后，显式策略字段、固定预期绑定与负例校验抵消了行数减少；不将职责迁移
  宣称为代码净删减。台账及二进制实体是主要体积缩减来源。
- 当前 provenance 保留 2,057 个采集事件，其中 233 个通过 `original_body_file`
  保留旧采集名称。27 个派生记录因本地路径更新而变更 hash/size，使用
  `entity_maintenance` 记录旧值；原始网络响应不按此方式改写。
- 对基线全部 fixture 逐项核对（含去重映射）无缺失；2,829 个原逻辑路径的字节
  保持一致，变化仅为 expected、manifest、provenance 和派生采集索引/上下文。
  原始 HTML/XML/PDF、响应实体和资产没有内容修改。

## 必须保留的复杂性

自动证据审计、fixture/cache/worker 传播与 unit 执行隔离继续存在。这些机制检验
证据使用范围，不能替代内容断言。来源固定预期仍验证哈希和对象归属；输出比较保留
分数参数、数值及上下标边界，否则会丢失真实负例覆盖。不同模板、失败路径和对象
位置检查没有因表面相似而合并。

保留 52 个相同字节的独立资产文件，原因是对应官方重新采集测试直接验证各自的
文件名和目录资产集合。按样本的保留数量如下；这些记录仍在既有 manifest 和
provenance 中，不引入 symlink、LFS 或额外存储服务。

| 样本 | 保留副本数 |
| --- | ---: |
| 10.48550/arxiv.1406.2661v1 | 4 |
| 10.48550/arxiv.2006.11239v2 | 4 |
| 10.48550/arxiv.2605.06659v1 | 1 |
| 10.48550/arxiv.2605.06663v1 | 12 |
| 10.48550/arxiv.2605.06665v1 | 7 |
| 10.48550/arxiv.2605.06666v1 | 3 |
| 10.48550/arxiv.2605.06667v1 | 2 |
| 10.1371/journal.pcbi.1003118 | 7 |
| 10.1371/journal.pbio.0040298 | 1 |
| 10.1111/gcb.16758 | 2 |
| 10.1088/1748-9326/ab7d02 | 5 |
| 10.1088/2058-9565/ac3460 | 2 |
| 10.1021/ja00160a040 | 2 |

跨论文、跨来源分类的相同字节不合并；canonical 原始输入优先保留，其次保留
provenance 引用的响应实体。历史报告允许保留旧路径，仅供追溯，不参与执行选择。

## 验证

基线收集 5,580 项：unit 2,547、integration 149、golden 2,884。
基线完整执行为 5,575 passed、5 skipped，另有 36,755 个通过的子断言。
基线存在 6 个 mypy 错误及 6 个未格式化文件，本次均已修复。

最终三个套件依次运行，各自沿用 pyproject 的默认并行配置，没有添加 `-n 0`。

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=src uv run python -m pytest tests/unit -q` | 2,551 passed；373 subtests passed；89.43 s |
| `PYTHONPATH=src uv run python -m pytest tests/integration -q` | 149 passed、4 skipped；2,144 subtests passed；46.35 s |
| `PYTHONPATH=src uv run python -m pytest tests/golden -q` | 2,883 passed、1 skipped；34,238 subtests passed；549.14 s |
| `uv run ruff check .` | 通过 |
| `uv run ruff format --check .` | 通过 |
| `uv run mypy src` | 307 个源文件通过 |
| `uv run python scripts/sync_version.py --check` | 6.2.4 同步通过 |
| `git diff --check` | 通过 |
| `uv run python scripts/validate_macos_adaptation.py` | 通过 |
| `bash scripts/test-macos-contract.sh` | 原生 Linux venv 执行，6 passed；1.74 s |

三个套件合计 **5,583 passed、5 skipped**，另有 **36,755 subtests passed**；
相较基线新增 8 项契约测试，既有子断言总数保持不变。套件保留解析器/依赖警告，
没有未解决的测试失败。

中间回归曾暴露去重路径引用、PLOS 官方链接表示及 AnnualReviews 选择器问题，
均局部修复后复验。多个完整套件同时运行时出现过 Science/PNAS 浏览器超时；
完整 integration 独立运行后通过，没有通过扩大重试、修改全局超时或关闭并行掩盖。
系统默认 Python 缺少 yaml，契约验证使用项目 uv 环境完成。
Linux portable 结果不替代原生 macOS gate。本次没有准备发布候选，未运行发布
build/install 终验，也未改动版本或 CI 安排。
