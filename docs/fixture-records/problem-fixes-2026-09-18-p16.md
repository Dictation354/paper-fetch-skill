# P16 IEEE iframe PDF 修复（2026-09-18）

结论：**已修复并验证**。IEEE `stamp.jsp` 主响应为 HTML、同篇 `getPDF.jsp` iframe 返回 PDF 时，现在不依赖点击或下载事件即可取得字节。其他 provider 保留既有浏览器 PDF 路径。

## 实现和边界

- 新增 `_ieee_pdf` provider helper：官方 HTTPS host、stamp 路径、唯一数字 `arnumber` 与 iframe 一致；响应还须来自包装页明确声明的直接子 iframe、为 2xx `application/pdf`。跨文章、跨域、伪子域、重复 article number 查询不被接纳。
- 导航前同时注册 response/download 监听，结束时移除监听；沿用 landing 预热、当前 browser context/cookies、Referer 和原有请求预算。stamp 主响应直接 PDF 与正常 download 事件继续支持。
- `_pdf_fallback` 只在 IEEE stamp guard 下调用新 helper，PDF 响应继续经过既有大小、PDF 结构和 DOI 身份检查，并走原 artifact 落盘。错 DOI 不保存合格 PDF。
- IEEE payload 保留 PDF 响应诊断（实际 PDF 来源、包装页、响应类型、身份），同时保留此前 HTML/direct-PDF 失败与 PDF 降级轨迹。统一 acceptance 的 `degraded` 语义未改。
- 不改共享 retry、全局候选策略、认证或 PDF 转换质量；测试中的 PDF renderer 是不透明边界，不对转换文本修复或做格式验收。

## 真实输入证据

本次未联网；复用已有同篇真实捕获。

- DOI：`10.1109/MPER.1985.5526567`。
- 标题：Network Observability: Identification of Observable Islands and Measurement Placement。
- [包装页](../../tests/fixtures/golden_criteria/10.1109_MPER.1985.5526567/acquisition/source-completion-2026-09-18/010-user-followup-browser_iframe_no_click_result_dom.html)：SHA-256 `13ffb0d7177a09d383cfb9395b0bb8d3ceb007eb8a638dac792ac75f3498870b`。
- [一页 PDF](../../tests/fixtures/golden_criteria/10.1109_MPER.1985.5526567/acquisition/source-completion-2026-09-18/009-user-followup-browser_iframe_no_click_pdf_response.pdf)：SHA-256 `2186ca10ab99812fcc89e96db651ca1a8961472dc8c9ef942888af470faf583e`。
- [原始 provenance](../../tests/fixtures/golden_criteria/10.1109_MPER.1985.5526567/acquisition/provenance.json) 的两个响应均为 HTTP 200；历史记录已去除 URL query。golden 用已知 article number 构造 canonical stamp 匹配上下文，实际 iframe URL 从原始 HTML 读取，再与捕获 PDF 的官方 host/path 对照，不把补回的 query 当原始记录。
- PDF 元数据中的 DOI、标题、文件页数通过独立身份检查；原始字节经现有 PDF 验收结果的身份状态为 `match`。PDF 内容格式不在本项验收范围。

## 验证

运行项目默认并行配置，没有使用 `-n 0`。

```bash
PYTHONPATH=src uv run python -m pytest tests/integration/test_ieee_iframe_pdf.py tests/golden/test_ieee_iframe_pdf.py tests/unit/test_ieee_iframe_pdf.py tests/unit/test_ieee_provider_pdf_golden.py tests/unit/test_pdf_fallback_helpers.py -q
scripts/test-macos-contract.sh --python .venv/bin/python
```

组合结果：**58 passed、8 subtests passed**。真实离线 Camoufox 的五种响应场景全部通过：iframe PDF、iframe 非 PDF、PDF DOI 不匹配、主导航直接 PDF、download 事件；验证了无点击、iframe 不产生 download、预热 cookie 与 Referer。

macOS 静态契约校验通过；原生 Linux Python 3.14 执行 portable 测试 **6 passed**。`docs/macos-adaptation-contract.toml` 已注明 IEEE 响应捕获仍使用原有 runtime 分发边界；这些 Linux 测试不替代 `macos-15` 原生 gate。定向 Ruff 检查与格式检查通过。

在线可用性结论仍限于已捕获样本和历史会话，不宣称所有 IEEE 论文或裸 HTTP 均可用。
