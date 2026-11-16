# 工具契约

CLI 入口为 `paper-fetch`，命令包括 fetch、resolve、check、fetch-assets、doctor、auth、browser-preflight 和 update。

## 文件回执

默认及文件输出的 stdout 每篇一行 JSON，独立契约 `contract="paper-fetch/receipt"`、`schema_version=1`。包含：

- 原始 `index/query`、规范 `identity/doi`。
- `acceptance` 七分面摘要、`content_kind`、`source/acquisition`。
- 绝对 `body_path`、`manifest_path`、`diagnostic_paths`、`image_index_path`、`output_paths`。
- `truncated` 与 `fallback_codes/warning_codes/failure_codes`。

回执不携带正文、完整 trace 或浏览器凭证。完整 trace 在逐篇 schema-v2 manifest 和诊断文件中。`--manifest` 额外写指定路径；默认 manifest 仍独立保留。批量最终汇总按输入顺序保存。

`body_path=null` 表示没有交付 Markdown 文件；以实际路径和验收判断结果，不依据请求推断交付。根据本地 reader 实际返回范围续读。

## 正文导出

单篇 `--output -` 按 `--format markdown|json|both` 输出正文；批量不支持 --output。默认目录为保留的临时目录；显式 --output-dir 优先。`--artifact-mode none|markdown-assets|all` 控制 provider 原始文件及资产，不阻止正文、manifest 与诊断交付。

## 补图与探测

`fetch-assets --manifest PATH` 与 `--query` 互斥。选择器为重复 `--asset-id`、重复 `--asset-url` 或 `--kind formula` 三者之一。返回实际本地文件路径，不重抓全文。

resolve 和 check 均接受 --query 或 --query-file；check 只探测。歧义时根据候选消歧后重试，不把候选当作已确认论文。

## 退出码

取得全文（含降级）为 0；仅摘要、元数据或失败为 1，结果保留；参数错误为 2。批量任一项未满足目标即非零。独立附件任务依据附件验收判断是否满足目标。
