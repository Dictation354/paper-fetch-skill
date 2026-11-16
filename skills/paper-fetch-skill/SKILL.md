---
name: paper-fetch-skill
description: "获取、下载或核验指定论文全文或补充材料，或探测全文可用性。支持 DOI、URL、arXiv ID、标题和引用条目；阅读、总结、比较或翻译已知论文而需要全文时使用。不用于尚无明确候选的开放式领域检索。"
---

# 论文抓取

获取已知论文并继续完成用户要求的阅读、总结、比较或翻译。优先使用用户指定文件或已有结果；身份不明时先消歧。搜索摘要和网页片段不能当作论文全文。

## 最短阅读路径

```bash
paper-fetch fetch --query "10.1186/1471-2105-11-421"
```

读取 stdout 的 JSON 回执，保存 `query`、`identity`、`acceptance`、`body_path` 和 `manifest_path`。默认正文及图片索引保存在独立系统临时目录，命令退出后仍可读取；不下载正文图片、不使用持久缓存。按回执的绝对路径打开本地 Markdown，用搜索定位章节，再按任务需要分段阅读。

依据读取工具**实际交付**的行、字符和截断信息续读，不能把请求的范围当成已读范围。区分取得全文与已阅读的内容；局部问题只需读取相关证据。核对公式定义、符号或图内数值时实际查看表达或图片，图注与链接不能替代原图。优先复用已有图片，需要补取时：

```bash
paper-fetch fetch-assets --manifest /absolute/path/manifest.json --asset-id img_example
```

随后打开返回的实际图片路径。补图沿用原论文身份与图片索引，不重新抓取全文。

## 参数与边界

- 尊重用户明确的来源、路径、资产范围及覆盖授权。默认预设只补全未指定选项。
- 多篇使用 `--query-file queries.txt --batch-concurrency 4`；逐篇回执按完成顺序输出，最终 `batch-results.jsonl` 按输入顺序保存。保存每篇身份、路径及实际阅读进度。
- 仅解析用 `paper-fetch resolve --query ...`；仅探测用 `paper-fetch check --query ...`，都支持 query-file；探测不自动升级为抓取。
- 依据 acceptance 判断全文、摘要、元数据及降级。全文降级结果仍可成功；仅摘要、元数据或失败退出码为 1，保留文件回执；参数错误为 2。
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
