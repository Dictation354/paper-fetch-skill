# 原文回归契约

这里保存可执行回归所需的精简证据，测试和基线刷新不读取过程报告。`expected.json` 在 fixture manifest 登记为 contract scenario 的辅助快照；实际内容证据仍来自各样本原文。

- `expected.json.cases`：稳定用例 ID、artifact/source 路径、原文结构契约和源 SHA-256。
- `expected.json.records`：稳定修复 ID、规则、原文正向片段及源文件 SHA-256。
- `expected.json.files`：样本身份、输入类型、current/historical 范围及源文件 SHA-256；刷新脚本仅重放 current 项，历史最小 artifact 保持原用途。
- `expected.json.samples`：原始错误表达式、历史公式与 fallback 计数、历史容器摘要及源文件 SHA-256；`current` 单独维护已验证基线的公式计数、容器摘要和文件 SHA-256；通过已安装 LitRoot 与公式工具重放，不用报告文本作为预期。

原始捕获、acquisition/provenance 和各样本 expected/extracted 仍由原目录维护。新增或移除样本时维护清单，不在测试或脚本里固定篇数。PDF 仅验证转换输出透传与持久化契约，不修复转换正文。
