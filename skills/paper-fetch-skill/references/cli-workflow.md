# CLI 工作流

CLI 是单篇/批量本地归档、shell 自动化和人工检查 manifest/JSONL 的正常执行面。明确目标可直接运行下列命令，由 fetch 内部解析身份；复杂映射再查 [`workflow.md`](workflow.md)。入口不可用时再读窄 fallback。MCP 宿主内 progress/cancel 或结构化批量结果则优先使用 `batch_fetch`。

以下单篇和批量示例默认获取正文；独立材料任务先按[任务目标](presets.md#任务目标)添加 `--target supplementary` 并选择材料落盘参数，沿用相同的输出目录、query file 和批量汇总设置，按[补充材料验收](acceptance.md#补充材料验收)核对结果。

## 单篇

临时 stdout 阅读仍会准备工作目录；只需避免论文产物和论文 cache 写盘时可用 MCP 临时阅读预设；两者的 runtime 准备仍可能写盘：

```bash
paper-fetch fetch --preset temporary_read --query "10.1186/1471-2105-11-421" \
  --progress jsonl 2>./progress.jsonl
```

归档命令与正文图/补充材料/严格资产参数只按[单篇本地归档](presets.md#3-单篇本地归档)及[共同规则](presets.md#共同规则)选择。需要单篇可审计记录时加 `--manifest ./papers/example.manifest.json`。

## 批量归档

```bash
paper-fetch fetch --preset archive --query-file ./queries.txt \
  --output-dir ./papers --batch-concurrency 4 \
  --batch-results ./papers/batch-results.jsonl --progress jsonl 2>./progress.jsonl
```

参数组合见[批量本地归档预设](presets.md#5-批量本地归档)。UTF-8 query file 每行一个规范目标；空行和 `#` 开头行忽略。先按[分块规则](presets.md#批量分块与证据等级)完成身份解析与去重，再生成 query file。

每篇主输出写入 `--output-dir`；batch JSONL 在整批结束时原子写入，每个输入恰好一个 schema-v2 terminal record，并按稳定 `index` 排列。机器调用直接消费 stderr 的 JSONL terminal 协议，每条 `type="terminal"` 的 `record` 就是完整 manifest record：

```python
import json
for line in progress_lines:
    event = json.loads(line)
    if event.get("paper_fetch_progress") and event.get("type") == "terminal":
        record = event["record"]
        print(record["index"], record["acceptance"]["overall"],
              record["acceptance"]["content"]["status"], record["output_artifacts"])
```

`record_status` 表示该输入的终态；内容完成结论读取 acceptance，并按 [`acceptance.md`](acceptance.md) 读取 `output_artifacts` 的实际路径及工具验收结论。每个输入都应有 terminal record，包括失败、限流、取消和未调度项。`--batch-results` 不提供恢复或 journal 语义；目标已存在且内容不同则保持拒绝，只有用户明确允许替换时才加 `--overwrite`。

## 输出和错误边界

- 自定义 `--format`、主输出、额外 Markdown 或 artifact 组合时，查 [CLI 输出/落盘矩阵](presets.md#cli-输出落盘矩阵)。
- Runtime fetch failure 的结构化 JSON 写 stderr；argparse 参数错误仍使用标准 stderr/exit 2。歧义、访问、限流、网络和取消的重试只遵循 [`failure-handling.md`](failure-handling.md)。
- 抓取自动准备 managed runtime；异常时读[环境参考](environment.md#运行时准备与授权)，无需单独更新检查。
- 使用 `paper-fetch --help` 和 `paper-fetch fetch|doctor|browser-preflight --help` 读取已安装版本的有效枚举和默认值。

## 窄 fallback

- MCP 不可用但 shell/console script 可用时，选择 CLI 是正常执行面切换，仍使用上面的完整预设和验收，不降级参数或成功标准。
- 按 PATH → 已配置或受管 wrapper → 可导入包发现入口。先用 `command -v paper-fetch`（PowerShell：`Get-Command paper-fetch`）；未命中时读取已有 MCP 注册 command/args 或安装路径，优先使用同一安装的 wrapper。Unix 默认入口 `~/.local/share/paper-fetch-skill/bin/paper-fetch`；Windows 用已配置安装根目录下 `bin/paper-fetch.cmd`。自定义安装沿用注册路径，不搜索或运行无关源码虚拟环境。
- 用找到的绝对 wrapper 执行 `--version` / `doctor --catalog --json`，保留其解释器和配置。没有 wrapper、但已知解释器能导入包时，才使用该解释器 `-m paper_fetch.cli`；不要默认系统 Python 能导入受管包。
- MCP 未注册：宿主没有该服务条目；启动失败：已有注册但进程报错；目录未刷新：运行版本正确但宿主仍暴露旧工具/参数。分别读取活动配置、启动错误或重载宿主/MCP 与工具目录；磁盘版本不能证明会话接口版本。普通 fetch 无需固定先查 catalog。
- Python 包也未安装、环境不可写或用户禁止 shell 时，停止该执行面并报告缺失能力；转回可用 MCP。仅在当前任务已有适用的安装授权时按安装流程恢复环境。不得用 web snippet、搜索摘要或自写 downloader 冒充论文全文。
