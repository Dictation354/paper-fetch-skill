# 工具契约

CLI 入口为 `paper-fetch`，命令包括 fetch、lookup、resolve、check、fetch-assets、doctor、auth、browser-preflight 和 update。

## 文件回执

默认及文件输出的 stdout 每篇一行 JSON，独立契约 `contract="paper-fetch/receipt"`、`schema_version=2`。同一份回执在正文产物与 manifest 落盘后原子写入 `.paper-fetch-results/<run_id>/<index>/receipt.json`，覆盖成功、失败和协作取消。回执包含以下字段。

- 原始 `index/query`、规范 `identity/doi`、生命周期 `status` 和与退出码判断一致的 `target_satisfied`。
- `error`：无异常为 null；有异常时含 status、reason、provider、route、stage、http_status、retryable，沿用脱敏。
- `acceptance` 七分面摘要、`content_kind`、`source/acquisition`。
- 绝对 `body_path`、`section_index_path`、`manifest_path`、`diagnostic_paths`、`image_index_path`、`output_paths`。
- `truncated` 与 `fallback_codes/warning_codes/failure_codes`。

原因码稳定去重并包含资产验收的 issue/failure codes，例如 `asset_not_archived`。

回执不携带正文、完整 trace 或浏览器凭证。完整验收报告与 trace 在逐篇 schema-v3 manifest（`request` 与 `acceptance`）及诊断文件中。`--manifest` 额外写指定路径；默认 manifest 仍独立保留。批量最终汇总按输入顺序保存。

建库以回执或最终 `batch-results.jsonl` 为入口，按 DOI、经验证且唯一的规范 URL、最后按 manifest 路径识别记录；保留实际获取状态。普通目录扫描排除 `.paper-fetch-results` 内部快照，不能把 `body.md` 计作另一篇论文。

`body_path=null` 表示没有交付 Markdown 文件；以实际路径和验收判断结果，不依据请求推断交付。根据本地 reader 实际返回范围续读。

`section_index_path` 指向 `sections.json`。其中 `sections` 每项含 `title`、`level`、`start_line`、直属内容末行 `end_line` 和包含子节的整章末行 `subtree_end_line`。旧索引按标题层级推导整章末行。行号对应 `body_path`，从 1 开始，两端包含；已完成的全文结果均具备经校验的 `body_path` 和 `section_index_path`。

## 已有正文查找

`lookup (--doi DOI | --query-file PATH) --output-dir DIR [--output-dir DIR ...] [--include-legacy]` 只读查找未截断的验收全文。按完成时间从新到旧核对正文与章节索引快照，同一时间按目录传入顺序。单篇命中返回原回执，未命中返回含 DOI 的 `status=not_found` 对象。

批量按输入顺序返回 JSONL，每条带 `index`。`lookup --query-file` 各项的 `index` 始终为该 DOI 在查询文件中的行号，从 1 开始。无效输入返回 `status=invalid_doi`、原 `query` 和 `doi=null`，有效 DOI 未命中时返回 `status=not_found` 和规范 DOI。全部命中退出 0，任一项未命中或 DOI 无效退出 1，命令参数错误退出 2。

所有目录均无现行命中时，`--include-legacy` 按目录顺序检查历史结果。命中返回 `paper-fetch/legacy-lookup`（`schema_version=1`、`status=found`、`acceptance=historical_unverified`），并提供 `source`。v8/v2 sidecar 提供绝对 `sidecar_path`、`sidecar_version` 和 `body_json_pointer=/payload/markdown`。旧 manifest 或带受管 frontmatter 的 Markdown 提供绝对 `body_path`，来自 manifest 时还提供 `manifest_path`。

## 正文导出

单篇 `--output -` 按 `--format markdown|json|both` 输出正文；批量不支持 --output。默认目录为保留的临时目录；显式 --output-dir 优先。`--artifact-mode none|markdown-assets|all` 控制 provider 原始文件及资产，不阻止正文、manifest 与诊断交付。

## 补图与探测

`fetch-assets --manifest PATH` 与 `--query` 互斥。选择器为重复 `--asset-id`、重复 `--asset-url` 或 `--kind {formula,figure,table}` 三者之一。命令从 v3 manifest 复用论文身份和图片索引。

Skill 调用 `fetch-assets` 时显式传 `--compact`。stdout 的单行 JSON 包括 `schema_version=1`、`contract=paper-fetch/asset-receipt`、`doi`、`status`、`results` 和 `details_path`。成功项包含 `status=ok`、`asset_id` 和绝对 `path`，有 `body_positions` 时还包含 `kind` 和去重、升序的 `lines`。失败项包含 `status=failed`、`asset_id` 或未匹配的 `selector`，以及 `reason`。命令级错误提供脱敏的 `status` 和简短 `reason`，`results` 为空。普通调用直接输出详细 JSON。

`details_path` 指向同次调用原子保存的脱敏明细，含图注和逐项诊断。`formula`、`figure`、`table` 的完整 `body_positions` 见 `images.json` 和下载明细，`line`、`column` 均从 1 开始。明细随显式输出目录或本次保留的临时目录存放。明细写入失败时该字段为 `null`，stderr 给出提示，仍按回执交付实际下载结果。

`resolve` 和 `check` 均接受 `--query` 或 `--query-file`，stdout 始终为 JSONL。当前 `--progress {auto,text,jsonl,none}` 只做参数解析。`check` 只探测。歧义时根据候选消歧后重试。

## 退出码

取得全文（含降级）为 0。仅摘要、元数据或失败为 1，结果保留。参数错误为 2。批量任一项未满足目标即非零。独立附件任务依据附件验收判断是否满足目标。补图全部成功为 0，部分成功或失败为 1，参数错误为 2。
