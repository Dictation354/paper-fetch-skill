# 三层测试重设计验证

> 历史验证记录；当前测试契约与命令见 `tests/README.md`。

2026-09-16，在当前已有依赖的 WSL/Linux 工作区验证。使用 CPython 3.14.7，
保持 `pyproject.toml` 的 `-n auto`、网络隔离和临时用户目录配置；未调整 worker 数，
未安装浏览器、未访问出版社、未触发 GitHub CI。

## 测试结果

完整 unit 连续三次以独立进程运行，外层 `time.perf_counter()` 计时包含 uv、
解释器、pytest 启动、收集和退出。只额外添加 `--durations=30` 保存长尾明细。
命令、环境及原始时间见 [timings.json](test-layer-results/timings.json)。

| 层级／轮次 | 结果 | 总耗时（秒） | 耗时明细 |
| --- | --- | ---: | --- |
| unit-1 | 2240 passed | 68.89 | [unit-1.log](test-layer-results/unit-1.log) |
| unit-2 | 2240 passed | 68.86 | [unit-2.log](test-layer-results/unit-2.log) |
| unit-3 | 2240 passed | 68.68 | [unit-3.log](test-layer-results/unit-3.log) |
| integration | 102 passed，4 skipped | 43.09 | [integration.log](test-layer-results/integration.log) |
| golden | 869 passed，1 skipped | 429.12 | [golden.log](test-layer-results/golden.log) |

以三轮 unit 的均值加本次 integration 计，两个默认层串行合计约 **111.90 秒**；
golden 的 429.12 秒单独报告。unit 均值较原基线降低约 86.3%。

unit 原实测基线为 500.56 秒；最终三轮均低于 120 秒。integration 和 golden
分别独立完整运行，报告其全部耗时，不将它们混入 unit 提速数字。

## 收集与覆盖核对

默认 `PYTHONPATH=src uv run python -m pytest --collect-only -q` 收集 2346 项：
unit 2240、integration 106、golden 0。显式 `tests/golden --collect-only -q`
收集 870 项；其中 exact 回放 141 项，与唯一 manifest/catalog 的全部可执行
exact 集合逐项一致，不依赖 full/shard 开关。见 [collection.json](test-layer-results/collection.json)
及 [默认收集](test-layer-results/collect-default.log)、[golden 收集](test-layer-results/collect-golden.log)。

[迁移清单](test-layer-migration.json) 对照工作开始时的文件快照，记录 446 个测试函数
的旧、新位置，以及 37 个函数体／装饰器变更。原 2380 个测试函数中，1931 个
位置不变，删除 3 个，新增 9 个，最终 2386 个；参数展开计数以 pytest 收集为准。
删除项仅为两项撤销的 PDF 正文／页序／引用质量测试，以及被完整入口验证替代的旧分片测试。
PDF 剩余测试保留身份、完整性、来源、获取和原样转换透传；不评价转换文本质量。

integration 的子 pytest 证明真实进程、shell、PDF 后端导入、全文构建器、canonical
全文读取在 unit 中明确失败，且 `browser`／`live`／`allow_subprocess` 均不能绕过。
另验证 golden 构建只执行一次、每次返回独立副本、清空内存缓存后复用本轮会话文件、
不同路由分别构建。缓存、重试、隔离用例仍独立执行。

integration 和 golden 的条件跳过均沿用旧测试。golden 保留的一个跳过来自已有
采集记录缺少已核验 binary 的资产样本；没有把该样本伪称为成功，也没有为提速新增 skip。

## 质量与平台检查

- 全仓 `ruff check .` 通过；本次测试文件及两处授权生产修复的格式检查通过。
- `scripts/sync_version.py --check` 通过，版本仍为 6.2.4。
- `scripts/validate_macos_adaptation.py` 通过；原生 workflow 引用的全部测试路径和 nodeid 仍有效。
- `git diff --check` 通过。
- 全仓 `ruff format --check .` 仍报告六个已有生产文件需格式化：`_pdf_common.py`、
  `_pdf_fallback.py`、`_playwright_browser.py`、`browser_workflow/html_extraction.py`、
  `providers/elsevier.py`、`quality/html_availability.py`。见 [格式检查](test-layer-results/format.log)。
- 生产包 mypy 仍有六处已有错误，位于 `models/builders.py`、`providers/plos.py`、
  `workflow/fulltext.py`。见 [类型检查](test-layer-results/mypy.log)。这些文件的既有改动未扩大处理，
  因此当前全仓 preflight 不能宣称绿灯。

`bash scripts/test-macos-contract.sh --python .venv/bin/python` 在原生 Linux Python 下通过：
静态契约通过，portable 测试 6 passed。见 [执行记录](test-layer-results/macos-portable.log)。

本次不是版本发布，未执行发布资产 build/install 终验。发布前仍须完成三层、全部质量门禁、
版本一致性及部署文档中的既有 build/install 终验；Linux 静态和 portable 结果不替代
`macos-15`／CPython 3.14 原生 gate 或 release 的 CPython 3.11–3.14 原生矩阵。

## 两处授权生产修复

全量回放暴露的两处冲突已由用户明确授权：IEEE 的 PDF 分支保留转换结果首尾空白；
付费墙检测排除 Science 标记为 `data-active-pane="false"` 的 `core-collateral-*` 面板。
对应 unit 验证 PDF 原样透传，以及 inactive／active 面板的相反结果；原有全文回放继续验证。
其它 provider、转换、cache、retry 和 browser 策略未因本次分层重设计而修改。
