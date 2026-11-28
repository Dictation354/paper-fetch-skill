---
name: paper-fetch-skill
description: "获取、下载或核验指定论文全文或补充材料，或探测全文可用性。支持 DOI、URL、arXiv ID、标题和引用条目；阅读、总结、比较或翻译已知论文而需要全文时使用。不用于尚无明确候选的开放式领域检索。"
---

# 论文抓取

获取已知论文并继续完成用户要求的阅读、总结、比较或翻译。优先使用用户指定文件或已有结果；身份不明时先消歧。搜索摘要和网页片段不能当作论文全文。

## 核心流程

有可读文件、回执、manifest 或交接记录时，核对论文身份和验收范围，直接复用满足要求的文件。正文回执中的 `body_path` 指向可读正文。只有 DOI 或链接且需要正文时，直接抓取。Unix 离线安装若未将命令加入 PATH，可用 `~/.local/bin/paper-fetch` 调用下例。

```bash
paper-fetch fetch --progress text --query "10.1186/1471-2105-11-421"
```

已知历史结果目录时，用 `paper-fetch lookup --doi <DOI> --output-dir <DIR>` 查单篇，用 `paper-fetch lookup --query-file <FILE> --output-dir <DIR>` 查一批 DOI。可重复传入 `--output-dir`。允许使用历史正文时，加 `--include-legacy` 回退到 v8/v2 sidecar、缺少 `sections.json` 的旧 manifest 或带受管 frontmatter 的 `.md` 文件。查到所需正文就直接读取，缺少时再用 `fetch`。只需解析论文身份时，用 `paper-fetch resolve --query <QUERY>`。

需要跨会话保留新结果时，用 `--preset cacheable_read` 并通过 `--output-dir` 指定任务输出目录。交接时记录论文身份、验收范围、`body_path`、`section_index_path`、`manifest_path`、`image_index_path`，以及已下载图片的 asset ID 和实际路径。

批量抓取时，在 `dois.txt` 中每行写一个 DOI。以下命令将 stdout 中的逐篇 JSON 回执写入 `receipts.jsonl`（每行一篇），进度仍输出到 stderr。

```bash
paper-fetch fetch --query-file dois.txt --batch-concurrency 4 --output-dir ./papers > receipts.jsonl
```

通过 `identity`、`target_satisfied`、`acceptance` 和 `error` 确认实际交付，并保留回执供后续复用。默认紧凑回执 `paper-fetch/receipt` 在顶层提供 `body_path`、`section_index_path` 和 `image_index_path`。直接用这些字段定位文件，完整产物清单见逐篇 manifest 的 `output_artifacts`。默认正文及索引保存在独立系统临时目录，命令退出后仍可读取。Nature 文章的无标题引言可从 `Main` 起读。

读取方法章时，按每篇回执分别操作。

1. 打开 `section_index_path`，按索引中的实际 `title` 找到方法章，例如 `2 **Materials and methods**`，记下其 `start_line` 和 `level`。
2. 优先用该项的 `subtree_end_line` 作为整章末行。旧索引缺少该字段时，从该项向后查找第一个 `level` 小于或等于方法章的标题，以该标题的 `start_line - 1` 为末行。如果方法章是最后一章，以最后一个索引项的 `end_line` 为末行。
3. 打开 `body_path`，从方法章的 `start_line` 读到上述末行（含）。即使父标题后紧接 `2.1`，这个范围也包含各子节的方法正文。

依据读取工具**实际交付**的行、字符和截断信息续读，不能把请求的范围当成已读范围。区分取得全文与已阅读的内容。局部问题只需读取相关证据。核对公式定义、符号或图内数值时实际查看表达或图片，图注与链接不能替代原图。

只缺图片时，从已有 `image_index_path` 定位缺失项。图片有 `body_positions` 时，可按已读正文的行范围筛选，再用原 manifest 补取对应的 `asset_id`。可以一次传入多个 ID。

```bash
paper-fetch fetch-assets --compact --manifest /absolute/path/manifest.json \
  --asset-id img_first --asset-id img_second
```

`--kind {formula,figure,table}` 按类型补取图片。从回执的 `results` 打开成功项的实际图片路径，并把 asset ID 和路径记入交接记录。需要跨会话保留新下载的图片时，将 `--output-dir` 指向任务输出目录。

只要补充材料时：

```bash
paper-fetch fetch --progress text --target supplementary --query DOI --output-dir ./papers
```

仅 `--target supplementary` 默认下载附件。随普通正文一起下载附件时用 `--asset-profile all`。显式 `--asset-profile none` 或 `--artifact-mode none` 仅保留发现结果。按[材料交接](references/reading-handoff.md)读取实际落盘文件，区分仅发现链接、部分下载和完整下载。

## 参数与边界

- 尊重用户明确的来源、路径、资产范围及覆盖授权。默认预设只补全未指定选项。
- 建库从逐篇回执或最终 `batch-results.jsonl` 读取，按 DOI、已验证规范 URL、最后按 manifest 路径识别论文，保留实际获取状态。普通目录扫描排除 `.paper-fetch-results`，避免重复计入正文快照。
- 同一任务的同出版社 DOI 一起交给 `--query-file`，由批内调度安排名额。宿主截断输出后，从文本进度开头提示的运行目录读取 `<index>/receipt.json`。保存每篇身份、路径及实际阅读进度。
- 仅解析用 `paper-fetch resolve --query ...`；仅探测用 `paper-fetch check --query ...`，都支持 query-file；探测不自动升级为抓取。
- 依据 `target_satisfied`、acceptance 和实际文件判断交付，`status` 只表示任务生命周期。依据 acceptance 判断全文、摘要、元数据及降级。全文降级结果仍可成功；仅摘要、元数据或失败退出码为 1，保留文件回执；参数错误为 2。
- AMS 联网正文、附件和补图必须先有 `paper-fetch auth ams` 成功且原生 profile 重开验证通过的状态。交互 CLI 缺少状态时先认证再继续；非交互及 `--control-stdin` 返回 `auth_required`。兼容缓存和已有本地文件可直接复用；resolve/check 不自动认证。
- 浏览器任务按实际 profile 目录排队，等待可取消且不消耗页面预算。返回 challenge/auth_required 时按[环境说明](references/environment.md)处理人工认证，遵守登录、验证码、付费墙及访问权限。
- PDF 正文以现有转换器输出为边界，不清洗或修复内容。
- 最终回答对应实际阅读的证据、用户要求与影响结论的降级，不追加固定审计或额外验证流程。

## 按需参考

- [CLI 工作流](references/cli-workflow.md)：入口发现、单篇、批量、进度与取消。
- [预设](references/presets.md)：临时阅读、缓存阅读、归档、探测与批量归档。
- [工具契约](references/tool-contract.md)：回执、manifest、路径与退出码。
- [工作流](references/workflow.md)：消歧与用户指定来源。
- [验收](references/acceptance.md)：实际交付与最终报告。
- [图件与材料](references/reading-handoff.md)：补图及文件读取。
- [环境](references/environment.md)与[失败处理](references/failure-handling.md)：实际遇到的问题。
