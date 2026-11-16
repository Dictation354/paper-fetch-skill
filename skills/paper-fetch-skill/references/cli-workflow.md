# CLI 工作流

## 入口发现

优先 `paper-fetch --help`；命令不在 PATH 时检查用户指定环境，或受管安装目录的 `bin/paper-fetch`（Windows 为 `bin/paper-fetch.cmd`）。源码环境可用项目 Python 执行 `-m paper_fetch.cli`。不要为普通阅读自动安装或修改宿主配置。

## 单篇

```bash
paper-fetch fetch --query "10.1186/1471-2105-11-421"
```

解析 stdout 的单行 JSON，读取 `body_path`。默认保留完整正文、逐篇 manifest、诊断和图片索引。`--output-dir ./papers` 指定目录；`--output - --format markdown` 显式导出正文到 stdout；文件输出模式继续返回 JSON。

## 批量

每行一个 query 的 UTF-8 文件：

```bash
paper-fetch fetch --query-file queries.txt --batch-concurrency 4 --output-dir ./papers
```

不支持 `--output`。每完成一篇立即落盘 manifest、输出回执；重复 DOI 复用抓取并逐项映射。最终汇总按输入顺序写入 `batch-results.jsonl`。取消后可独立读取已经完成的逐篇文件。

## 进度与取消

`--progress jsonl` 将 protocol 1 事件写入 stderr。阶段区分 `waiting_profile`、`executing_browser` 和终态，附排队及执行耗时。`--control-stdin` 需同时启用 JSONL 进度；取消命令详见 CLI 帮助对应的项目文档。正常 profile 等待没有排队超时。

读取 stdout 回执后再搜索本地正文；读取输出被截断时根据实际返回范围续读。
