# CLI 工作流

CLI 是单篇/批量本地归档、shell 自动化和人工检查 manifest/JSONL 的正常执行面。先按 [`workflow.md`](workflow.md) 解析身份、去重、选择 [`presets.md`](presets.md) 并检查适用的本地/cache，再运行当前单篇或批量章节的命令；入口不可用时再读窄 fallback。MCP 宿主内 progress/cancel 或结构化批量结果则优先使用 `batch_fetch`。

## 单篇

临时 stdout 阅读仍会准备工作目录；要求完全不落盘时改用 MCP 临时阅读预设：

```bash
paper-fetch fetch --query "10.1186/1471-2105-11-421" \
  --format markdown \
  --output - \
  --output-dir ./.paper-fetch-tmp \
  --artifact-mode none \
  --asset-profile none \
  --include-refs all \
  --max-tokens full_text
```

归档命令与正文图/补充材料/严格资产参数只按[单篇本地归档](presets.md#3-单篇本地归档)及[共同规则](presets.md#共同规则)选择。需要单篇可审计记录时加 `--manifest ./papers/example.manifest.json`。

## 批量归档

按[批量本地归档预设](presets.md#5-批量本地归档)运行命令。UTF-8 query file 每行一个规范目标；空行和 `#` 开头行忽略。先按[分块规则](presets.md#批量分块与证据等级)完成身份解析与去重，再生成 query file。

每篇主输出写入 `--output-dir`；batch JSONL 在整批结束时原子写入，每个输入恰好一个 schema-v2 terminal record，并按稳定 `index` 排列。可用 Python 标准库检查记录：

```bash
python3 - ./papers/batch-results.jsonl <<'PY'
import json
from pathlib import Path
import sys

for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    record = json.loads(line)
    paths = [item["path"] for item in record["output_artifacts"]]
    print(record["index"], record["record_status"], record["acceptance"]["overall"], paths)
PY
```

`record_status` 表示该输入的终态；内容完成结论读取 acceptance，并按 [`acceptance.md`](acceptance.md) 检查 `output_artifacts` 的真实路径/hash。每个输入都应有 terminal record，包括失败、限流、取消和未调度项。`--batch-results` 不提供恢复或 journal 语义；目标已存在且内容不同则保持拒绝，只有用户明确允许替换时才加 `--overwrite`。

## 输出和错误边界

- 自定义 `--format`、主输出、额外 Markdown 或 artifact 组合时，查 [CLI 输出/落盘矩阵](presets.md#cli-输出落盘矩阵)。
- Runtime fetch failure 的结构化 JSON 写 stderr；argparse 参数错误仍使用标准 stderr/exit 2。歧义、访问、限流、网络和取消的重试只遵循 [`failure-handling.md`](failure-handling.md)。
- 抓取自动准备 managed runtime；异常时读[环境参考](environment.md#运行时准备与授权)，无需单独更新检查。
- 使用 `paper-fetch --help` 和 `paper-fetch fetch|doctor|browser-preflight --help` 读取当前安装的有效枚举和默认值，不从旧安装或外部仓库文档猜测。

## 窄 fallback

- MCP 不可用但 shell/console script 可用时，选择 CLI 是正常执行面切换，仍使用上面的完整预设和验收，不降级参数或成功标准。
- `paper-fetch` console script 不在 PATH、但当前 `python3` 能成功导入已安装包时，可把命令前缀替换为 `python3 -m paper_fetch.cli`。先用 `python3 -m paper_fetch.cli --help` 验证入口；不要复制或重写抓取实现。
- Python 包也未安装、环境不可写或用户禁止 shell 时，停止该执行面并报告缺失能力；转回可用 MCP。仅在当前任务已有适用的安装授权时按安装流程恢复环境。不得用 web snippet、搜索摘要或自写 downloader 冒充论文全文。
