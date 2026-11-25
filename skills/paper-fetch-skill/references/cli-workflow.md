# CLI 工作流

## 入口发现

优先运行 `paper-fetch --help`。命令不在 PATH 时检查用户指定环境。Unix 离线安装可直接调用 `~/.local/bin/paper-fetch` 或安装目录的 `bin/paper-fetch`，Windows 使用安装目录的 `bin/paper-fetch.cmd`。源码环境可用项目 Python 执行 `-m paper_fetch.cli`。不要为普通阅读自动安装或修改宿主配置。

## 单篇

```bash
paper-fetch fetch --progress text --query "10.1186/1471-2105-11-421"
```

解析 stdout 的单行 JSON，按 `section_index_path` 的章节范围读取 `body_path`。默认保留完整正文、逐篇 manifest、回执、诊断、章节和图片索引。`--output-dir ./papers` 指定目录。`--output - --format markdown` 显式导出正文到 stdout，回执仍保存在 `receipt.json`。

## 复用已交付正文

`paper-fetch lookup (--doi DOI | --query-file PATH) --output-dir DIR [--output-dir DIR ...] [--include-legacy]` 优先选最近的可校验全文。单篇返回一个 JSON 对象。批量文件每行一个 DOI，stdout 按输入顺序逐项输出 JSONL。`lookup --query-file` 各项的 `index` 始终为该 DOI 在查询文件中的行号，从 1 开始。

所有目录均无现行命中时，`--include-legacy` 按目录顺序回退到历史 v8/v2 sidecar、旧 manifest 或带受管 frontmatter 的 Markdown。按 `sidecar_path` 和 `body_json_pointer` 或直接按 `body_path` 读取，交接注明 `historical_unverified`。返回 `not_found` 时按任务需要抓取。

## 批量

同一任务的同出版社 DOI 放入同一个 UTF-8 查询文件，每行一个查询，由批内调度安排名额。

```bash
paper-fetch fetch --progress text --query-file queries.txt --batch-concurrency 4 --output-dir ./papers > receipts.jsonl
```

逐篇 manifest 和 `receipt.json` 随每个输入的终态保存。重复 DOI 复用抓取并逐项映射。stdout 回执按完成顺序写入 `receipts.jsonl`，最终 manifest 汇总按输入顺序写入 `batch-results.jsonl`。宿主截断输出时读取落盘的 `receipts.jsonl`，也可从文本进度开头 `receipts=…` 指向的运行目录打开 `<index>/receipt.json`。协作取消后仍可用同一路径恢复已完成项。

## 定向补图

`paper-fetch fetch-assets --manifest PATH --compact --kind {formula,figure,table}` 按类型补取索引中的图片。成功项有 `body_positions` 时，紧凑回执还提供 `kind` 和去重、升序的 `lines`。完整行列位置见 `images.json` 或 `details_path`。

## 进度与取消

独立 `resolve` 和 `check` 当前仅解析 `--progress {auto,text,jsonl,none}`，stdout 始终为 JSONL。

自动抓取显式传 `--progress text`，即使 stderr 接入管道也显示进度。`executing_browser` 显示排队耗时，`browser_finished` 同时显示排队和执行耗时。Wiley TDM 和 Copernicus 直连 PDF 的下载、转换耗时及转换缓存状态见逐篇诊断。`--progress jsonl` 将 protocol 1 事件写入 stderr。`--control-stdin` 需同时启用 JSONL 进度，取消命令详见 CLI 契约。正常 profile 等待没有排队超时。

在宿主异步工具中把单次等待或超时设为 60–120 秒。HTTP/XML 路线通常需要 5–15 秒，浏览器路线（`science`、`wiley`、`pnas`、`ieee`、`ams` 或 Elsevier 参考文献 HTML 回退）通常需要 20–90 秒。避免每 1–5 秒轮询。

读取输出被截断时，根据实际返回范围续读。
