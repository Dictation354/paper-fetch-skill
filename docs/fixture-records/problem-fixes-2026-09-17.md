# 真实来源问题修复验证

2026-09-17，按 P15、P01、P13、P14、P03、P04、P06 顺序串行调用子代理，
主代理逐项审阅并执行完整三层验证。所有修复基于既有真实 HTML/XML 和来源记录；
保留工作区原有改动，未修改 PDF 转换、版本或 CI，未提交或发布。

## 修复与原文验收

| 问题 | 修复结果与证据边界 |
| --- | --- |
| P15 | 移除 SAGE 活跃 fixture、manifest、专属用例和证据登记；旧字节及失败采集移入[历史归档](retired/10.1345_aph.1M379/README.md)，拒绝 hash 继续生效。Springer、Wiley 的真实多语言摘要增加逐段核对，Elsevier 的真实缺陷由 P13 修复。 |
| P01 | 正式书目解析识别 `.biblioentry` 和 `.citations`；Science 恢复 100 条、PNAS 正文恢复 78 条、commentary 恢复 21 条非空书目，逐条核对正文、编号、DOI、渲染顺序。 |
| P13 | Elsevier 按源顺序遍历全部 `abstract`，逐段核对西班牙语四段、英语四段的标题及内容。 |
| P14 | MDPI 合并身份匹配的 Preview/frame/script，保留两处 CO₂，错误占位为 0；空 Preview 的 MathML/TeX 回退、display 语义和真实缺失诊断均有最小回归。 |
| P03 | Wiley 公式 1 处、AMS 图片表格 7 处在 DOM 渲染前按同篇来源补齐域名。资产候选清单完全相同，保留 preview/full、远程及下载状态。 |
| P04 | Springer/Nature 三处图片在 DOM 渲染前补齐协议；Box 使用既有资产清单的 full-size，新闻保留原 `lw767` 图片。 |
| P06 | Royal Society 六个正文链接按原文 `data-legacyid` 对应到实际标题 ID，输出同篇来源页链接：`s2 → 19033670` 四处，`s3 → 19033689` 两处。核对链接文本、顺序、次数及源目标；其他链接保持原行为。 |

P01 的计数更正：commentary 两份捕获字节相同，第 22 个书目节点确为
`<div class="citations" id="r22"></div>`，无正文、DOI 或隐藏子节点。
因此原报告的“22 条”是节点数，不能作为 22 条完整书目的预期；回归明确验证
21 条非空书目加一个空源节点，没有编造缺失内容。

完整 golden 首轮暴露八处旧预期：七处图片地址断言要求根相对 URL，另有
Elsevier `10.1016/j.apgeog.2012.04.006` 的摘要计数。后者 XML 第二个
`abstract` 虽标记 `class="graphical"`，实际包含独立 Highlights 文本；核对
原输入后，仅把结构基线的摘要数 1→2、总节数 9→10，并增加完整内容和顺序回归。
该 XML 仍为来源未验证输入，未升级来源分类。图片断言按同篇来源解析地址，
继续核对原始图片身份与顺序。首轮失败日志保留为 `validation/golden-first.log`。

当前活跃 manifest 为 **255 项**（202 个 golden-family、53 个其他条目）；
登记资产 **2168 个**：真实捕获 1149、来源未验证 287、派生/辅助 690、
synthetic 23、机制场景 19。无可核验文章原文的条目为 128 个
（126 未验证、2 synthetic）。原 HTTP403、运行时拒绝及来源 hash 仍保留；
本次离线内容修复不证明在线访问已验收成功或远程图片当前可下载。

## 完整验证

全部复用 `pyproject.toml` 的默认并行配置，未使用 `-n 0`。最终三层均通过；
integration 的四项及 golden 的一项条件跳过均为既有用例，未新增 skip/xfail。

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=src uv run python -m pytest tests/unit -q` | 2365 passed，373 subtests passed |
| `PYTHONPATH=src uv run python -m pytest tests/integration -q` | 127 passed，4 skipped，1450 subtests passed |
| `PYTHONPATH=src uv run python -m pytest tests/golden -q` | 2533 passed，1 skipped，34168 subtests passed |

原始日志保存在 [validation](../../.paper-fetch-runs/problem-fixes-2026-09-17/validation/)。
真实输入回归主要位于 `tests/golden/test_reacquired_source_inputs.py`、
`test_regression_samples.py`、`test_mdpi_provider.py`、`test_relative_image_sources.py`
和 `test_royalsocietypublishing_provider.py`，测试证据登记同步更新。

## 静态检查与既有限制

- 全仓 `ruff check src tests`、本次涉及 Python 文件的格式检查及 `git diff --check` 通过。
- `validate_macos_adaptation.py` 与 `sync_version.py --check` 通过；版本保持 6.2.4。
- 全包 mypy 仍有修复开始前的六处错误：`models/builders.py` 四处、
  `workflow/fulltext.py` 一处、`providers/plos.py` 一处；本轮未新增类型错误。
- 全仓格式检查仍有七个既有文件未通过：`providers/_pdf_fallback.py`、
  `providers/_playwright_browser.py`、`providers/browser_workflow/html_extraction.py`、
  `providers/elsevier.py`、`quality/html_availability.py`、
  `tests/unit/test_frontiers_provider.py`、`tests/unit/test_iop_provider.py`。
  这些文件的无关改动未扩大处理，因此不将全仓 preflight 表述为全部通过。

未变更 macOS 浏览器、安装器或支持矩阵；本次静态检查不替代原生 macOS gate。
