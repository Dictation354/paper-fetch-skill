# check 探测语义

`paper-fetch check` 是单篇和 query-file 批量的低成本全文可用性预判，复用 Python `probe_has_fulltext()`。它只做 metadata/landing 请求，不触发正文 waterfall，也不写正文目录；静态诊断用 `paper-fetch doctor`。

## 与真实抓取的区别

| 入口 | 证据 | 结论 |
| --- | --- | --- |
| check | metadata、路由及 landing meta | 可能可用或证据不足 |
| fetch | 完整 provider 抓取和统一验收 | 最终 has_fulltext 与 acceptance |

license、全文链接或 citation_pdf_url 不证明当前可成功获取；probe 没有正信号时，后续 HTML/PDF 路径仍可能成功。两者不要求逐案一致。

## 证据与状态

公开 probe 状态为 `confirmed_yes`、`likely_yes`、`unknown`、`no`；当前实现只主动
生成 `likely_yes` 与 `unknown`。判断位于 `paper_fetch.workflow.routing.probe_has_fulltext`：

| 正信号 | `evidence` |
| --- | --- |
| Crossref license | `crossref_license` |
| Crossref fulltext link | `crossref_fulltext_link` |
| catalog 允许的 provider metadata probe 成功（如 Elsevier、arXiv） | `provider_probe:<provider>` |
| landing meta 包含 PDF 地址 | `landing_page_citation_pdf_url` |

至少一个正信号得到 `likely_yes`；没有正信号得到 `unknown`，不能把它解释成无全文。
metadata/probe 请求失败的 warnings 表达证据不足或环境受限，不是负结论。
具体 provider probe 能力由 runtime catalog 决定，不另维护工具侧名单。

## 调用和返回

```bash
paper-fetch check --query "10.1186/1471-2105-11-421"
paper-fetch check --query-file queries.txt --batch-concurrency 4
```

每项返回一行 JSON：schema_version=1、contract=paper-fetch/check，包含输入 index/query、解析 doi/title、status、state、evidence 与 warnings。按输入顺序输出；歧义或失败保留逐项错误及候选。state 为探测结论，不能当作已经取得全文。

真正获取和阅读使用 `paper-fetch fetch`，读取回执的 acceptance 与 body_path。获取成功与已实际阅读仍需区分。

## 扩展边界

probe 不承担正文下载或 provider HEAD/OPTIONS 深度探测。新增证据保持 metadata 级成本，不为追求与 fetch 一致而复制完整 waterfall。

完整流程见 [架构](overview.md)，配置与回退见 [provider 说明](../providers.md)，探测核对与报告见 [acceptance](../../skills/paper-fetch-skill/references/acceptance.md#探测核对与报告)。
