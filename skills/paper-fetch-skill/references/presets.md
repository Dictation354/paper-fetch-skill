# 任务预设与落盘矩阵

明确目标直接 fetch，歧义时再查看候选。五种任务使用三个原生 fetch 预设及 batch_check；显式参数覆盖预设，包括嵌套 strategy 与 false。

## 共同规则

fetch_paper、batch_fetch 默认 preset="temporary_read"、modes=["markdown"]、include_refs="all"、max_tokens="full_text"、metadata fallback 开启、asset_profile="none"。正文始终由 content_ref / read_content 分页消费。响应只在 structuredContent 中提供业务载荷，并返回 preset、effective_options、acceptance 和 output_artifacts。

| preset | 复用缓存 | 下载/缓存写入 | 保存 Markdown | 默认资产 |
| --- | --- | --- | --- | --- |
| temporary_read | 否 | 否 | 否 | none |
| cacheable_read | 是 | 仅缓存 | 否 | none |
| archive | 是 | 否 | 是 | none |

cacheable_read 需要 download_dir 或配置的 scope。archive 需要输出路径，仅给 markdown_output_dir 时也用该目录承接 scope。显式 no_download=false 可允许归档写入 sidecar。显式 strategy.asset_profile="body" 或 "all" 时，未提供的 no_download 补 false、artifact_mode 补 markdown-assets；显式值始终优先。原始 provider/debug 产物仅在显式 artifact_mode="all" 时保存。批量 JSONL 仅由 batch_results 决定。

## 任务目标

默认 target="paper"。只要补充材料时设 target="supplementary"，直接发现材料，不先获取正文。archive 默认下载附件并保存材料索引；只要远程清单可显式设 no_download=true。材料与正文缓存分别匹配。

## 五个预设

### 1. 临时阅读

```json
{"query":"10.1186/1471-2105-11-421","preset":"temporary_read"}
```

默认禁止论文产物和缓存写入，不要求 scope。多篇把 query 改为 queries，并使用 batch_fetch。保存规范身份、content_ref 和 next_offset，后续追问复用句柄。

### 2. 可缓存阅读

```json
{"query":"10.1186/1471-2105-11-421","preset":"cacheable_read","download_dir":"./.paper-fetch-cache"}
```

直接在指定 scope 内做严格请求匹配，命中复用，否则获取并写入缓存；无需先调用 get_cached。

### 3. 单篇本地归档

```json
{"query":"10.1186/1471-2105-11-421","preset":"archive","markdown_output_dir":"./papers","markdown_filename":"example.md"}
```

按 output_artifacts 的实际绝对路径和 verification_status 消费保存结果；仅异常或用户要求时重算 hash。正文仍可由句柄读取。

CLI 文本归档：

```bash
paper-fetch fetch --preset archive --query "10.1186/1471-2105-11-421" --output ./papers/example.md --output-dir ./papers --progress jsonl
```

### 4. 批量可读性分诊

```json
{"queries":["10.1000/first","10.1000/second"],"mode":"metadata","concurrency":4}
```

使用 batch_check；单篇同样适用。仅返回可用性证据，不获取全文，不自动升级任务。likely probe 不能替代全文 acceptance。

### 5. 批量本地归档

```json
{"queries":["10.1000/first","10.1000/second"],"preset":"archive","concurrency":4,"markdown_output_dir":"./papers","batch_results":"./papers/batch-results.jsonl"}
```

CLI 批量归档：

```bash
paper-fetch fetch --preset archive --query-file ./queries.txt \
  --output-dir ./papers --batch-concurrency 4 \
  --batch-results ./papers/batch-results.jsonl --progress jsonl
```

单篇和批量使用同一展开逻辑及正文句柄。别名共享获取及句柄，保留每条原始输入的 index。JSONL 按输入顺序原子写入，不提供恢复语义。

## CLI 输出/落盘矩阵

CLI 主输出由 --output/--output-dir 决定，--save-markdown 是额外副本。CLI `--preset temporary_read|archive` 仅补全未指定选项，默认完整 Markdown、全部引用、无正文资产。temporary_read 默认 stdout、artifact-mode none；archive 默认在输出目录写主文本，独立材料 archive 默认下载附件并保存索引。显式 output/output-dir/format/asset 选项优先，query-file 仍逐篇输出；manifest/progress 按任务选择。CLI 始终准备工作目录；--artifact-mode none 禁止 provider 产物，--asset-profile none 禁止正文资产。

## MCP 输出/落盘矩阵

正文始终为句柄；保存文件由 save_markdown 决定，缓存读取由 prefer_cache 决定，provider/asset/cache 写入由 no_download 决定，具体产物范围由 artifact_mode 与 asset_profile 决定。浏览器组件准备和原生 profile 独立于论文落盘选项。

## 本地优先决策树

用户指定文件或来源优先。否则复用有效会话句柄，再读取身份和内容可证明的本地正文；允许缓存且 scope 已知时使用 cacheable_read。get_cached 用于明确检查缓存，status=hit 不能替代 request_satisfied。

## 批量分块与证据等级

所有批量工具每次最多 50 条。超过 50 条按原顺序分块，例如 113 条拆为 [1..50]、[51..100]、[101..113]。每块显式传 concurrency，宿主保存全局原始 index 映射，不按完成顺序重新编号。完整阅读通过 read_content 消费正文，验收摘要和未读片段均不能代表已读全文。
