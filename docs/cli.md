# CLI 使用说明

## 命令面

| 命令 | 用途 |
| --- | --- |
| fetch | 单篇或 query-file 批量抓取正文、归档或附件 |
| resolve | 独立身份解析与消歧，支持单篇和批量 |
| check | 仅探测全文可用性，支持单篇和批量 |
| fetch-assets | 按 manifest 或 query 定向补图 |
| doctor | 静态诊断 |
| browser-preflight | 实际浏览器预检 |
| auth | 人工认证并保存原生 profile |
| update | 更新官方安装 |

## 基本用法

```bash
paper-fetch fetch --query "10.1186/1471-2105-11-421"
paper-fetch fetch --query DOI --output-dir ./papers
paper-fetch fetch --query DOI --output - --format markdown
paper-fetch resolve --query "paper title"
paper-fetch check --query-file queries.txt --batch-concurrency 4
```

## 主输出

fetch 默认为 temporary_read：完整 Markdown、逐篇 schema-v2 manifest、图片索引和必要诊断保存至独立系统临时目录。stdout 只输出版本化 JSON 回执。目录在命令退出后保留，由用户或系统清理；不默认下载正文图片或写持久缓存。显式 --output-dir、资产范围和格式优先。

单篇 `--output -` 按 --format 输出正文；显式文件 --output 则保存正文并返回 JSON 回执。--format 为 markdown、json 或 both；文件输出同时保存可供阅读的 Markdown。--include-refs 默认为 all；--max-tokens 默认为 full_text，可显式指定数值。未显式 --output 时，在输出目录生成安全命名的主文件。

回执独立契约为 `paper-fetch/receipt`、schema_version=1，含 index/query、identity/doi、acceptance、content_kind、source/acquisition、body_path、manifest_path、diagnostic_paths、image_index_path、output_paths、truncated 及 fallback_codes/warning_codes/failure_codes。路径均为绝对路径；回执不含正文、完整 trace 或浏览器凭证。

完整 trace 和验收细节保存在 manifest 与诊断文件。取得全文（包括降级全文）退出 0；仅摘要、元数据或失败退出 1，保留结果；参数错误退出 2。正文截断标记不表示本地 reader 已读取的范围。

## 单篇 manifest

每篇完成后立即原子保存独立 manifest，回执给出实际路径；`--manifest PATH` 可额外写指定文件。无需整批完成即可恢复身份、正文、图片索引和诊断路径。manifest schema v2 由 `paper_fetch.manifest` 统一生成，含 run_id、record_id、index、attempt、query、identity、acceptance、acquisition、原因码、trace、output_artifacts 和文件快照。

## 批量抓取

```bash
paper-fetch fetch --query-file queries.txt --output-dir ./papers --batch-concurrency 4
```

UTF-8 文本每行一个查询。支持 1–8 个执行名额，默认 1。按规范 DOI 去重抓取，所有输入仍有独立 index/query 和 manifest。每篇完成就输出一行回执（完成顺序）；最终 --batch-results（默认 output-dir/batch-results.jsonl）按输入顺序原子保存 schema-v2 记录。有未满足目标的项即返回非零。批量不支持 --output 或单篇 --manifest。

## 任务预设

- temporary_read：默认临时文件，无持久缓存，无正文图片下载。
- cacheable_read：在所选输出目录复用合格缓存，并保存新结果。
- archive：归档到所选输出目录，复用合格缓存；显式选择 body/all 下载图片或材料。

独立 check 对应可读性分诊；query-file 与 archive 组合对应批量归档。预设只填未指定选项。

## 定向补取图片

```bash
paper-fetch fetch-assets --manifest /absolute/path/manifest.json --asset-id img_example
paper-fetch fetch-assets --manifest /absolute/path/manifest.json --kind formula
paper-fetch fetch-assets --query DOI --asset-url https://example.org/figure.png
```

--manifest 与 --query 互斥。--asset-id、--asset-url 可重复，或使用 --kind formula，三种选择器互斥。manifest 恢复论文身份和已有图片索引，不重新抓取全文；下载后返回实际文件路径。默认图片保存在系统临时目录并保留，--output-dir 可指定位置。

## 独立补充材料任务

```bash
paper-fetch fetch --target supplementary --preset archive --query DOI --output-dir ./papers
```

独立获取附件、Source Data、Extended Data 或媒体，不以正文成功为前置条件。随正文取材料用 --asset-profile all。附件任务根据其统一验收结果判断退出状态。

## 主输出与 Artifact

--artifact-mode none 不保留 provider artifact 或下载图片，但仍交付正文、manifest、图片索引与诊断。markdown-assets 保存 Markdown 与所选资产、必要 PDF 来源；all 另保留 provider 原始数据。--asset-profile none/body/all 选择下载范围。--require-local-body-assets 与 --require-full-size-body-assets 将本地归档或原图要求纳入验收；后者隐含前者。PDF 转换输出不清洗、不修复。

## 实时进度与机器取消

--progress auto/text/jsonl/none 将进度写到 stderr。JSONL progress protocol_version=1，以 run_id/index 标识事件。--control-stdin 要求 --progress jsonl，stdin 每行 JSON：

```json
{"protocol_version":1,"run_id":"<run_id>","command":"cancel","index":1}
{"protocol_version":1,"run_id":"<run_id>","command":"cancel","index":null}
```

排队状态为 waiting_profile，取得使用权后为 executing_browser；诊断记录 profile_queue_seconds 和 browser_execution_seconds。等待无超时，可取消；执行期间也响应取消，context 由所属线程关闭后释放锁。

## Browser 登录态

所有浏览器路线使用配置解析后的实际 profile 路径作为资源键，展开用户目录、解析符号链接并按平台规范化大小写。不同 profile 可并行，同 profile 在批内与跨进程排队。等待者让出执行名额，不阻塞其他空闲 profile；HTTP/API 不申请 profile 资源，出版社限流独立保留。页面预算在取得锁后建立，同一请求内重用、页面重试及 fallback 共用剩余预算；HTTP 时限独立。

外部浏览器占用报 browser_profile_external_occupancy；provider 归属冲突报 browser_profile_provider_conflict。抓取、补图、auth 和 browser-preflight 使用同一协调机制。

## 静态诊断、真实预检与人工认证

```bash
paper-fetch doctor --help
paper-fetch browser-preflight --provider wiley
paper-fetch auth wiley
```

doctor 不联网；browser-preflight 实际检查浏览器路线；auth 打开人工认证。配置及安装见 [部署指南](deployment.md)，profile 细节见 [浏览器运行时](browser-runtime.md)。

## 更新官方安装包

`paper-fetch update` 验证并运行最新稳定官方安装包。安装、升级、卸载会清理可确认归属本工具的旧注册和 wrapper（包含自定义名称），保留其他服务、登录态、论文和缓存。静态 Skill 的 --check 仅检查，不清理。

## 默认目录

临时阅读使用独立系统临时目录；--output-dir 优先。缓存/归档流程沿用配置中的 PAPER_FETCH_DOWNLOAD_DIR 或用户数据目录，缓存按身份、请求与 credential scope 核验；新索引为 .paper-fetch-cache.json，旧索引仅兼容读取。
