# 任务预设

预设仅补全未显式传入的选项。普通正文默认完整 references 和 `full_text`，资产范围为 none。

## 1 临时阅读

```bash
paper-fetch fetch --query DOI
```

默认 `temporary_read`，正文在独立临时目录，退出后保留，无持久缓存及正文图片下载。

## 2 可缓存阅读

```bash
paper-fetch fetch --preset cacheable_read --query DOI --output-dir ./papers
```

抓取流程复用当前目录内身份、请求语义、credential scope 和文件核验均匹配的缓存。新索引名为 `.paper-fetch-cache.json`；旧索引仅兼容读取。

## 3 单篇本地归档

```bash
paper-fetch fetch --preset archive --query DOI --output-dir ./papers
```

需要图片时显式加 `--asset-profile body`；同时要补充材料用 all。只要附件时用 `--target supplementary`：三个抓取预设均默认 `asset_profile=all`、`artifact_mode=markdown-assets`；显式参数优先，`--asset-profile none` 或 `--artifact-mode none` 禁止下载，保留索引与验收。缓存选择和输出目录仍按各预设规则。

## 4 批量可读性分诊

```bash
paper-fetch check --query-file queries.txt --batch-concurrency 4
```

仅探测可用性，不抓取全文；每条结果保留 index/query 和解析身份。

## 5 批量本地归档

```bash
paper-fetch fetch --preset archive --query-file queries.txt --output-dir ./papers --batch-concurrency 4
```

每项有独立 manifest，最终汇总按输入顺序生成；有未满足目标的项返回非零。
