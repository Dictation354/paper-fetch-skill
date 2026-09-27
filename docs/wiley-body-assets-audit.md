# Wiley 正文资产串行导航审计

2026-09-27，在 WSL/Linux 原生 Python 3.14.7、Camoufox 152.0.4-beta.30 上验证。此记录不提供原生 macOS gate 或发布矩阵证据。

## 行为契约

正文资产阶段只创建一个自有 context/page，初始化继承正文 cookies 和浏览器配置。公式优先、组内保持正文顺序，逐候选导航图片 URL；每逻辑资产的导航、验证及预览回退共用 30 秒，并受请求总期限、取消及资产预算约束。每候选只主动导航一次。

监听器按当前导航请求及重定向链归属接受原始图片响应，要求对应 DOM 图片加载完成。Firefox 在 HTTP 重定向后可能保留初始 URL 作为 `currentSrc`，因此同时核对已确认的初始/最终 URL，且页面地址必须对应最终响应。初始挑战不会把 URL 永久标为已接收；后续成功清除候选终态失败，挑战和恢复时间线留在 `recovery_attempts`。

不追加 HTTP 下载、刷新、截图、canvas 导出或独立 figure 页面探测。普通单图失败继续使用原会话；取消、总期限、共享预算耗尽及结束时在所属线程清理。预览回退保留原图失败与 `preview_fallback` 降级，已耗尽预算而未导航的候选明确记录 `candidate_not_navigated`。已发现的 MathJax 备用公式位图也归档，正文 MathML/LaTeX 优先级不变。

## 线上矩阵

执行 `tests/live/test_live_wiley_page_assets.py`，因共享外部状态使用 `-n 0`；所有六个组合串行运行，输出到新目录 `.paper-fetch-runs/wiley-serial-20260927-01/`。每个目录保留 `page-asset-audit.json`、全文 Markdown、资产文件和原有抓取产物；根目录 `summary.json` 登记逐报告 SHA-256。此目录是本机复测产物，不是 committed golden fixture。

| 模式 | DOI 后缀 | 公式位图 | 正文原图 | 正文公式表示 | acceptance.overall |
| --- | --- | --- | --- | --- | --- |
| headed | gcb.15322 | 11/11 | 4/4 | 11 图片回退 | degraded |
| headed | gcb.16758 | 26/26 | 5/5 | 26 图片回退 | degraded |
| headed | gcb.16414 | 0/0 | 6/6 | 无 | complete |
| headless | gcb.15322 | 11/11 | 4/4 | 11 图片回退 | degraded |
| headless | gcb.16758 | 26/26 | 5/5 | 26 LaTeX | complete |
| headless | gcb.16414 | 0/0 | 6/6 | 无 | complete |

全部 104 个预期位图均落盘，逐文件 MIME、尺寸、SHA-256 与浏览器实际收到的字节相符；正文图均为 `full_size`，无预览降级或资产失败。六篇均取得全文，每篇只使用一个资产 context/page，主动导航数分别为 15、31、6（每模式一组），结束清理通过。线上文件为 74 个 PNG 和 30 个 JPEG；PNG 地址返回 WebP 并保留原字节及 `.webp` 扩展名的边界另由单元测试覆盖。

headed 的 gcb.16758 和 gcb.16414 各发生一次同候选挑战自然恢复，分别从导航起约 0.186 秒的挑战到 3.090 秒成功、0.178 秒的挑战到 2.579 秒成功。恢复后无终态图片失败；没有自动操作人工验证控件。

严格 `overall=complete` 断言结果为 **3 passed / 3 failed**：三个失败均保留现有 `formula_fallback` / `formula_fallback_present` 内容降级，asset 分面均为 complete。未放宽验收，也未以公式位图完整替代正文表示质量。因此“六个组合均 complete”的目标尚未达到；不存在缺失资产导致的降级。

## 本地验证

- `uv run python scripts/validate_macos_adaptation.py`：通过。系统 Python 缺少 PyYAML，使用现有项目环境执行。
- `scripts/test-macos-contract.sh --python /home/dictation/paper-fetch-skill/.venv/bin/python`：6 passed；仅 portable 证据。
- `PYTHONPATH=src uv run python -m pytest tests/unit -q`：2580 passed、375 subtests passed。
- `PYTHONPATH=src uv run python -m pytest tests/integration -q`（显式复用已安装 Camoufox binary）：157 passed、2 skipped、2144 subtests passed。
- Wiley provider / appendix / gcb.16758 相关 golden：11 passed。
- Wiley 抓取器 mypy 和改动文件 Ruff：通过。

常规测试沿用 pytest 默认并行配置。最小真实浏览器场景覆盖同 URL 挑战恢复、本地 HTTP 重定向、原字节、cookies 更新保留、串行页面复用、预览、持续挑战、导航等待异常和取消清理。初次完整 integration 中的短超时测试已分离初始化开销；另一次 Science 既有短窗口测试出现超时，单独复核及最后完整 integration 均通过，未修改 Science 行为。完整 unit 暴露的 MCP 未配置场景会探测本机图片工具，现已在该测试的依赖发现边界补 mock，不启动真实进程，不改变断言或产品逻辑。
