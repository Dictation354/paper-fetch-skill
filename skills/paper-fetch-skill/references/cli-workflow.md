# CLI 工作流

CLI 是单篇/批量本地归档、shell 自动化和人工检查 manifest/JSONL 的正常执行面，不是 MCP 失败后的专用 fallback。先按 [`workflow.md`](workflow.md) 解析身份、去重和选择 [`presets.md`](presets.md)，再运行本文件中的命令；MCP 宿主内 progress/cancel 或结构化批量结果则优先使用 `batch_fetch`。

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

文本归档显式选择主输出、artifact 和资产范围；只有需要单篇可审计记录时再加 `--manifest`：

```bash
paper-fetch fetch --query "10.1186/1471-2105-11-421" \
  --format markdown \
  --output ./papers/example.md \
  --output-dir ./papers \
  --manifest ./papers/example.manifest.json \
  --artifact-mode none \
  --asset-profile none \
  --include-refs all \
  --max-tokens full_text
```

正文图改为 `--artifact-mode markdown-assets --asset-profile body`；补充材料改为 `--artifact-mode markdown-assets --asset-profile all`。用户还要求全部正文资产本地化时加 `--require-local-body-assets`，要求全部为 full-size 时加 `--require-full-size-body-assets`（自动隐含 local）。两项默认关闭且不适用于 `asset-profile=none`。`--artifact-mode all` 只在用户还要求原始 provider/cache/debug payload 时使用。

## 批量归档

UTF-8 query file 每行一个 DOI、URL 或标题；空行和 `#` 开头行忽略。正常批量主路径是：

```bash
paper-fetch fetch --query-file ./queries.txt \
  --format markdown \
  --output-dir ./papers \
  --batch-concurrency 4 \
  --batch-results ./papers/batch-results.jsonl \
  --artifact-mode none \
  --asset-profile none \
  --include-refs all \
  --max-tokens full_text
```

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

- `--format markdown|json|both` 控制 stdout、显式 `--output` 或默认主输出格式；`--save-markdown` 是额外 Markdown 副本，不是主输出开关。
- `--artifact-mode none` 不禁止显式主输出、`--output-dir` 默认主输出或 `--save-markdown`。
- Runtime fetch failure 的结构化 JSON 写 stderr；argparse 参数错误仍使用标准 stderr/exit 2。歧义、访问、限流、网络和取消的重试只遵循 [`failure-handling.md`](failure-handling.md)。
- 实际进入 browser 的 CLI fetch 只使用已准备的 managed Camoufox；缺失时先显式运行 `python -m camoufox fetch`。该边界不影响静态 doctor，也不改变论文产物的 artifact mode。
- 使用 `paper-fetch --help` 和 `paper-fetch fetch|doctor|browser-preflight --help` 读取当前安装的有效枚举和默认值，不从旧安装或外部仓库文档猜测。
- 安装/升级完整性由安装器在复制前后及三个宿主目标上直接调用独立 verifier；源码 installer 可用 `./scripts/install-codex-skill.sh [--project] --check` 做严格只读同步检查。普通 `doctor` 只报告业务 runtime/provider readiness。

## 窄 fallback

- MCP 不可用但 shell/console script 可用时，选择 CLI 是正常执行面切换，仍使用上面的完整预设和验收，不降级参数或成功标准。
- `paper-fetch` console script 不在 PATH、但当前 `python3` 能成功导入已安装包时，可把命令前缀替换为 `python3 -m paper_fetch.cli`。先用 `python3 -m paper_fetch.cli --help` 验证入口；不要复制或重写抓取实现。
- Python 包也未安装、环境不可写或用户禁止 shell 时，停止该执行面并报告缺失能力；转回可用 MCP，或按安装流程恢复环境。不得用 web snippet、搜索摘要或自写 downloader 冒充论文全文。
