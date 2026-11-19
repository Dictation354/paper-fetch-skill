# CLI 使用说明

## 命令面

| 命令 | 用途 |
| --- | --- |
| fetch | 单篇或 query-file 批量抓取正文、归档或附件 |
| lookup | 按 DOI 查找指定项目中已有的验收全文 |
| resolve | 独立身份解析与消歧，支持单篇和批量 |
| check | 仅探测全文可用性，支持单篇和批量 |
| fetch-assets | 按 manifest 或 query 定向补图 |
| doctor | 静态诊断 |
| browser-preflight | 实际浏览器预检 |
| auth | 人工认证并保存原生 profile |
| update | 更新官方安装 |

## 基本用法

```bash
paper-fetch fetch --progress text --query "10.1186/1471-2105-11-421"
paper-fetch fetch --query DOI --output-dir ./papers
paper-fetch fetch --query DOI --output - --format markdown
paper-fetch lookup --doi DOI --output-dir ./papers
paper-fetch resolve --query "paper title"
paper-fetch check --query-file queries.txt --batch-concurrency 4
```

## 主输出

fetch 默认为 temporary_read。完整 Markdown、逐篇 schema-v3 manifest、章节和图片索引及必要诊断保存至独立系统临时目录。stdout 输出版本化 JSON 回执。目录在命令退出后保留，由用户或系统清理。显式 --output-dir、资产范围和格式优先。

单篇 `--output -` 按 --format 输出正文；显式文件 --output 则保存正文并返回 JSON 回执。--format 为 markdown、json 或 both；文件输出同时保存可供阅读的 Markdown。--include-refs 默认为 all；--max-tokens 默认为 full_text，可显式指定数值。未显式 --output 时，在输出目录生成安全命名的主文件。

回执独立契约为 `paper-fetch/receipt`、`schema_version=2`，顶层保留便捷字段 index/query、identity/doi、status、target_satisfied、error、acceptance（七分面状态、has_fulltext/has_abstract、token_estimate 与 asset_summary）、content_kind、source/acquisition、body_path、section_index_path、manifest_path、diagnostic_paths、image_index_path、output_paths、truncated/truncation_reason 及 fallback_codes/warning_codes/failure_codes。请求资产时，`asset_summary` 包含 `requested`、`profile`、`discovered`、`local`、`full_size`、`failed`、`not_archived` 和 `issue_codes`。路径均为绝对路径。

`status` 保持任务生命周期含义；`target_satisfied` 直接复用退出码使用的目标满足判断。`error` 无异常为 null，有异常时投影 status、reason、provider、route、stage、http_status、retryable 并脱敏。顶层原因码稳定去重并包含资产验收 issue/failure codes，例如 `asset_not_archived`。

完整 trace 和验收细节保存在 manifest 与诊断文件。取得全文（包括降级全文）退出 0；仅摘要、元数据或失败退出 1，保留结果；参数错误退出 2。正文截断标记不表示本地 reader 已读取的范围。

按 `section_index_path` 打开 `sections.json`，其中 `sections` 每项含 `title`、`level`、`start_line` 和 `end_line`。行号对应正文快照 `body.md`，从 1 开始，两端包含；已完成的全文结果统一提供经校验的 `body_path` 与 `section_index_path`。每章止于下一标题前一行或文末。Nature 的无标题引言可从 `Main` 起读。

## 单篇 manifest

每篇完成后立即原子保存独立 manifest，回执给出实际路径；`--manifest PATH` 可额外写指定文件。建库以 stdout 回执或最终 `batch-results.jsonl` 为入口，依次按 DOI、已验证且唯一的规范 URL、manifest 路径识别记录，并保留实际获取状态。普通目录扫描排除 `.paper-fetch-results` 内部快照，不能把 `body.md` 计作另一篇论文。

无需整批完成即可恢复身份、正文、章节与图片索引及诊断路径。manifest schema v3 由 `paper_fetch.manifest` 统一生成（打包 JSON Schema 为 `manifest-record-v3.schema.json`），顶层包含 run_id、record_id、index、attempt、request、request_fingerprint、record_status、acceptance（schema v3）、trace、warnings、error 和 output_artifacts；原始 query 与请求参数从 `record.request` 读取，身份、DOI、来源、acquisition、语义损失、资产摘要和原因码统一从 `record.acceptance` 读取，不在顶层重复镜像。

## 按 DOI 复用项目正文

```bash
paper-fetch lookup --doi DOI --output-dir ./papers
```

命令只读扫描该目录内的 `.paper-fetch-results` 下逐篇 schema-v3 manifest。按完成时间从新到旧检查验收通过且未截断的全文，核验正文（`body.md`）与章节索引（`sections.json`）均存在且大小、哈希与快照一致，不符时尝试下一条。命中时根据已保存的结果输出一行 v2 `paper-fetch/receipt` 并退出 0。未命中输出一行含 `status=not_found` 和 `doi` 的 JSON 并退出 1。参数错误退出 2。

## 批量抓取

```bash
paper-fetch fetch --query-file queries.txt --output-dir ./papers --batch-concurrency 4
```

UTF-8 文本每行一个查询。支持 1–8 个执行名额，默认 1。按规范 DOI 去重抓取，所有输入仍有独立 index/query 和 manifest。每篇完成就输出一行回执（完成顺序）；最终 --batch-results（默认 output-dir/batch-results.jsonl）按输入顺序原子保存 schema-v3 记录。有未满足目标的项即返回非零。批量不支持 --output 或单篇 --manifest。

## 任务预设

- temporary_read：默认临时文件，无持久缓存，无正文图片下载。
- cacheable_read：在所选输出目录复用合格缓存，并保存新结果。
- archive：归档到所选输出目录，复用合格缓存；显式选择 body/all 下载图片或材料。

独立 check 对应可读性分诊；query-file 与 archive 组合对应批量归档。预设只填未指定选项。

## 定向补取图片

```bash
paper-fetch fetch-assets --compact --manifest /absolute/path/manifest.json \
  --asset-id img_first --asset-id img_second
paper-fetch fetch-assets --manifest /absolute/path/manifest.json --kind formula
paper-fetch fetch-assets --query DOI --asset-url https://example.org/figure.png
```

`--manifest` 与 `--query` 互斥。`--asset-id`、`--asset-url` 可重复，或使用 `--kind formula`，三种选择器互斥。`fetch-assets` 从 v3 manifest 恢复论文身份和已有图片索引。默认文件保存在本次调用的系统临时目录，进程退出后仍可访问。用 `--output-dir` 指定存放位置。

默认 stdout 返回详细 JSON。`--compact` 输出一行 JSON，包含 `schema_version=1`、`contract=paper-fetch/asset-receipt`、`doi`、总体 `status`、逐项 `results` 和 `details_path`。成功项包含 `status=ok`、`asset_id` 和绝对 `path`。失败项包含 `status=failed`、`asset_id` 或未匹配的 `selector`，以及 `reason`。总体结果为 `ok`、`partial` 或 `error`。命令级错误使用相应的错误状态和简短、脱敏的 `reason`，且 `results` 为空。无法确定 DOI 时 `doi` 为 `null`。

紧凑模式每次调用原子保存一份独立的脱敏明细，其中保留图注和逐项诊断。`details_path` 为明细的绝对路径，跟随 `--output-dir` 或本次保留的临时目录。明细写入失败时，`details_path` 为 `null`，stderr 给出简短提示，回执仍包含实际文件路径和下载结果。

全部成功退出 0，部分成功或失败退出 1，参数错误退出 2。参数错误由命令行解析器报告。

## 独立补充材料任务

```bash
paper-fetch fetch --target supplementary --preset archive --query DOI --output-dir ./papers
```

独立获取附件、Source Data、Extended Data 或媒体。仅 `--target supplementary` 默认下载附件，三个抓取预设均使用 `asset_profile=all`、`artifact_mode=markdown-assets`，显式参数优先。随正文取材料用 `--asset-profile all`。显式 `--asset-profile none` 或 `--artifact-mode none` 仅保留发现结果。通过 acceptance.asset_summary 的 local、not_archived、failed 及实际文件，区分仅发现链接、部分下载、完整下载。附件任务根据其统一验收结果判断退出状态。

## 主输出与 Artifact

--artifact-mode none 不保留 provider artifact 或下载图片，但仍交付正文、manifest、图片索引与诊断。markdown-assets 保存 Markdown 与所选资产、必要 PDF 来源；all 另保留 provider 原始数据。--asset-profile none/body/all 选择下载范围。--require-local-body-assets 与 --require-full-size-body-assets 将本地归档或原图要求纳入验收；后者隐含前者。PDF 转换输出不清洗、不修复。

## 实时进度与机器取消

--progress auto/text/jsonl/none 将进度写到 stderr。JSONL progress protocol_version=1，以 run_id/index 标识事件。--control-stdin 要求 --progress jsonl，stdin 每行 JSON：

```json
{"protocol_version":1,"run_id":"<run_id>","command":"cancel","index":1}
{"protocol_version":1,"run_id":"<run_id>","command":"cancel","index":null}
```

排队状态为 waiting_profile，取得使用权后为 executing_browser；诊断记录 profile_queue_seconds 和 browser_execution_seconds。等待无超时，可取消；执行期间也响应取消，context 由所属线程关闭后释放锁。

manifest 的 `trace` 以 `duration_ms` 记录 resolver 和 Crossref 元数据的耗时。Springer 另记录 `springer_html_http` 主页面请求、`springer_html_parse` 响应解码及元数据解析，以及 `springer_html_extract` 本地正文提取的耗时。

## Browser 登录态

Byparr 使用按平台选择的浏览器引擎。运行 `paper-fetch doctor --catalog` 查看当前环境的配置。

所有浏览器路线使用配置解析后的实际 profile 路径作为资源键，展开用户目录、解析符号链接并按平台规范化大小写。不同 profile 可并行，同 profile 在批内与跨进程排队。等待者让出执行名额，不阻塞其他空闲 profile；HTTP/API 不申请 profile 资源，出版社限流独立保留。页面预算在取得锁后建立，同一请求内重用、页面重试及 fallback 共用剩余预算；HTTP 时限独立。

外部浏览器占用报 browser_profile_external_occupancy；provider 归属冲突报 browser_profile_provider_conflict。抓取、补图、auth 和 browser-preflight 使用同一协调机制。

AMS 正文、补充材料发现／下载和定向补图的联网入口必须有 `paper-fetch auth ams` 成功且同一原生 profile 重开验证通过的已保存状态。只有目录、Cookie 或普通抓取状态不能通过；正常 Cookie 更新不要求当前摘要与最初认证摘要相同。已有认证标记无需迁移。

CLI 在确认身份及缓存未命中后检查；交互终端先认证再继续，无交互终端及 `--control-stdin` 返回 `auth_required`（统一验收 action_required）。认证提示只写 stderr；批量由调度线程按实际 profile 集中认证，多个 CLI 按同一路径协调，等待可取消，取得协调权后重新检查。认证复用原有浏览器生命周期，不预持后续抓取租约。失败或取消停止对应 AMS 获取并保留原始阶段和原因，其他批量项继续；Python 接口只报告认证要求。兼容缓存及已有本地图片可直接复用；resolve/check 不自动打开认证窗口。

## 静态诊断、真实预检与人工认证

```bash
paper-fetch doctor --help
paper-fetch browser-preflight --provider wiley
paper-fetch auth wiley
```

doctor 不联网；browser-preflight 实际检查浏览器路线；auth 打开人工认证。配置及安装见 [部署指南](deployment.md)，profile 细节见 [浏览器运行时](browser-runtime.md)。

## 更新官方安装包

`paper-fetch update` 验证并运行最新稳定官方安装包。安装、升级和卸载仅管理当前版本的 runtime、PATH 与静态 Skill 目录，保留其他服务、登录态、论文和缓存。静态 Skill 的 `--check` 严格只读。

## 默认目录

临时阅读使用独立系统临时目录；`--output-dir` 优先。缓存/归档流程沿用配置中的 `PAPER_FETCH_DOWNLOAD_DIR` 或用户数据目录，以 v8 单文件指纹 sidecar（`<doi>.<request_fingerprint>.fetch-envelope.json`）保存缓存，先精确匹配请求指纹再扫描同 DOI 超集变体，按身份、请求语义、credential scope 与本地文件核验，不维护独立缓存索引文件。
