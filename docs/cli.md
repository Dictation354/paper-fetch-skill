# CLI 使用说明

这份文档是 `paper-fetch` 命令行行为的权威说明，重点解释主输出、artifact、资产下载和常见参数组合。Agent 使用的自包含执行顺序见 [`../skills/paper-fetch-skill/references/cli-workflow.md`](../skills/paper-fetch-skill/references/cli-workflow.md)，意图/落盘矩阵见 [`presets.md`](../skills/paper-fetch-skill/references/presets.md)，产物复核见 [`acceptance.md`](../skills/paper-fetch-skill/references/acceptance.md)；安装后的 skill 不反向依赖本 `docs/` 目录。

## 命令面与兼容期

`paper-fetch --help` 会直接列出当前可用的 `fetch`、`auth`、`browser-preflight`、`manifest` 和 `doctor` 子命令；每个子命令都可以用 `--help` 查看有效默认值、枚举和落盘影响：

```bash
paper-fetch --help
paper-fetch fetch --help
paper-fetch auth --help
paper-fetch browser-preflight --help
paper-fetch manifest --help
paper-fetch doctor --help
```

新脚本应使用 `paper-fetch fetch ...`。原有的根级 `paper-fetch --query ...` / `paper-fetch --query-file ...` 调用至少保留一个兼容周期，并与显式 `fetch` 共用同一参数注册和执行路径；这一兼容层保持原有退出码及 stdout/stderr 契约。`paper-fetch manifest audit|reconcile` 是可调用的只读检查命令；单篇抓取的 `--manifest <path>` 是结果文件选项，二者不要混淆。`doctor` 是内置的只读、无网络静态诊断命令；自定义 CLI 组装仍可通过既有 registrar 替换该子命令。

## 基本用法

```bash
paper-fetch fetch --query "10.1186/1471-2105-11-421" \
  --format markdown \
  --output - \
  --output-dir ./.paper-fetch-tmp \
  --no-download \
  --artifact-mode none \
  --asset-profile none \
  --include-refs all \
  --max-tokens full_text
```

`--query` 可以是 DOI、论文 landing URL 或标题查询。CLI 默认会优先尝试全文；如果全文不可用，可能返回摘要或 metadata-only 结果。MDPI 的经典数字 URL（例如 `https://www.mdpi.com/2072-4292/18/10/1673`）会先按已知 ISSN 到 journal code 映射推导 DOI；MDPI DOI / DOI URL 也会在 provider 阶段反推对应的数字 article URL，再进入 MDPI selected-browser provider，避免解析阶段被 MDPI direct HTTP/CDN 403 阻断；未知 ISSN 仍按通用 landing URL 解析。URL 中嵌入 DOI 时，resolver 会复用 provider path templates 清理已知 route 后缀，例如 Frontiers 的 `/full` / `/pdf` / `/xml`、IOP 的 `/pdf`、Wiley 的 `/fullpdf` 和 Springer PDF URL 的 `.pdf`，PLOS 这类 `id={doi}` query parameter 也会直接提取 DOI；未知 provider 的 DOI 后缀不会被猜测性剥离。旧式 SICI DOI（例如 `10.1175/1520-0469(1967)024<0241:TEOTAW>2.0.CO;2` 或 Wiley/Blackwell 的 `10.1002/(SICI)...<...>...`）会保留完整 `<...>` / `;` 后缀；对应的 AMS `view/...xml` 或 `downloadpdf/...pdf` URL 可作为 query。官方 PDF fallback 已经下载到真实 PDF 但无法转换成 Markdown 时，会保留已下载的 PDF artifact 并在 warning 中说明 PDF-only 状态，而不是降级成 Crossref metadata-only source。

上面的命令是临时阅读：正文写 stdout，不归档论文文件。CLI 仍会准备显式的 `./.paper-fetch-tmp` 工作目录，因此不能承诺硬零写盘；完全不落盘请使用 MCP 的临时阅读预设。CLI 没有 cache-only / `prefer_cache` 预设，也没有与 `batch_check(mode="metadata")` 等价的低成本批量 probe。

## 任务预设

文本归档默认不下载图片，并使用 `--output` 或 `--output-dir` 作为主 Markdown：

```bash
paper-fetch fetch --query "10.1186/1471-2105-11-421" \
  --format markdown \
  --output ./papers/example.md \
  --output-dir ./papers \
  --artifact-mode none \
  --asset-profile none \
  --include-refs all \
  --max-tokens full_text
```

用户明确要求正文图时改用 `--artifact-mode markdown-assets --asset-profile body`；明确要求补充材料时改用 `--artifact-mode markdown-assets --asset-profile all`。`--artifact-mode all` 是原始 provider 载荷、HTTP cache 和调试 sidecar 的保留策略，不是补充材料开关。

CLI 适合单篇或批量本地归档；需要 MCP 宿主内 progress/cancel、结构化批量 acceptance 或不便解析 CLI stdout 时可使用 `batch_fetch`。临时阅读、可缓存阅读、批量可读性分诊和 MCP 批量归档的参数矩阵见技能包的 [`presets.md`](../skills/paper-fetch-skill/references/presets.md)。

## 单篇 manifest

单篇抓取只有显式传入 `--manifest <path>` 才写 schema v2 manifest；默认不创建 manifest 文件，也不改变普通 stdout 阅读行为：

```bash
paper-fetch fetch --query "10.1186/1471-2105-11-421" \
  --format markdown \
  --output ./papers/example.md \
  --output-dir ./papers \
  --artifact-mode none \
  --asset-profile none \
  --manifest ./papers/example.manifest.json
```

该文件包含一条与批量 JSONL 完全相同的 v2 record。主输出和额外保存的 Markdown 都先通过原子替换完成最终写入，record 随后读取最终文件的 size、SHA256 和 mtime；因此 `output_artifacts` 描述的是 record 建立时的最终文件，而不是临时 `.part` 文件。显式 manifest 自身也通过原子替换写入，且 manifest 路径不能与主输出或额外 Markdown 路径相同。目标 manifest 或最终输出已存在时默认拒绝替换；人工检查后可显式传 `--overwrite`。单篇不能同时使用 `--query-file` 和 `--manifest`；批量结果使用 `--batch-results`。

单篇 manifest 与批量 run 使用同一只读审计逻辑。例如：

```bash
paper-fetch manifest audit ./papers/example.manifest.json
```

## 静态诊断、真实预检与人工认证

`doctor` 汇总 provider 配置、Playwright、本地 Camoufox runtime 配置以及 Ghostscript/libvips 的本地状态。它不会启动浏览器、下载 Camoufox runtime、访问出版社页面或安装工具：

```bash
paper-fetch doctor
paper-fetch doctor --provider wiley --detail compact
paper-fetch doctor --group browser --json
paper-fetch doctor --env-file /path/to/offline.env --json
paper-fetch doctor --install-root ~/.local/share/paper-fetch-skill --json
```

`--provider` 只返回一个 catalog provider；`--group` 支持 `all`、`official`、`browser`、`direct` 和 `metadata`；`--detail compact` 的每个 provider 只保留 `provider/status/reason_code/reason/suggested_action`，`full` 额外保留原有 checks、配置来源与本地能力。provider、group 或 detail 非法时会在参数校验阶段拒绝。配置诊断只报告变量名、是否存在以及来源层，不回显 token、cookie、endpoint 或其它配置值。`--install-root` 显式核对一个离线安装目录；未指定时会从当前 module、entrypoint、`PAPER_FETCH_ENV_FILE` 或 PATH CLI 附近发现 `offline-manifest.json`。`--json` 的 `install_provenance` 会列出 source/distribution/UA/PATH CLI/offline manifest/installed runtime 的版本与路径，并逐一校验 bundle 和 Codex、Claude、Antigravity 三份 skill；纯源码开发态没有可发现的 offline manifest 时返回 `not_applicable`，版本或 hash 不一致返回 `drift`。

诊断顺序固定为：先用 `doctor` / MCP `provider_status` 检查静态配置与本地依赖；browser-backed provider 需要真实链路证明时再运行 CLI `browser-preflight` 或 MCP `browser_preflight`；只有预检或实际抓取明确要求登录/验证时，才显式运行 `auth`。`doctor` 退出码为 `0=ready`、`1=degraded`、`2=error`；它的 `ready` 仍不表示出版社网页当前可访问。

`doctor` 和 `provider_status` 始终只读、无网络。真正进入浏览器的 CLI `fetch`、
`auth`、`browser-preflight` 默认允许首次按需准备 managed Camoufox，并把下载/修复/
更新阶段写到 stderr。可在任一命令传 `--no-browser-auto-prepare`，或设置
`PAPER_FETCH_BROWSER_AUTO_PREPARE=false`，确保缺失 runtime 时直接返回结构化失败而
不联网。反向的 `--browser-auto-prepare` 会覆盖全局关闭。

## Browser 登录态

4.0 的唯一浏览器后端是原生 Firefox/Juggler Camoufox。HTML、PDF fallback、图片/补充文件、preflight 和 auth 都通过同一 browser-runtime facade；失败不会静默切换其它 backend。默认 core 安装不包含浏览器依赖，使用这些命令前需安装 `paper-fetch-skill[browser]` 或 `[full]`。完整配置见 [`browser-backends.md`](browser-backends.md)。

如果自动过盾失败，可用通用手动 fallback 打开 headed browser：

```bash
paper-fetch auth <provider>
paper-fetch auth wiley --url "https://onlinelibrary.wiley.com/doi/full/10.1111/example"
```

`provider` 来自 browser runtime catalog，例如 `wiley` / `science` / `pnas` / `ams` / `mdpi` / `royalsocietypublishing` / `annualreviews` / `acs` / `iop` / `aip`。未传 `--url` 时打开内置样例文章；传入 `--url` 时打开用户指定的失败文章页。命令强制 headed 模式，打印所选后端的 profile 和 storage-state 路径，用户在浏览器中完成合法登录或验证后，在终端按 Enter 保存过滤后的本地 storage-state 并退出。AMS 抓取不强制预先认证；无保存状态时仍会启动浏览器尝试静默验证，只有站点验证未自动完成时才需要 `paper-fetch auth ams`。

如果需要在批量抓取前确认所有 browser-backed provider 的浏览器链路是否能过站点验证，可以先串行运行预检：

```bash
paper-fetch browser-preflight
paper-fetch browser-preflight --provider wiley --provider science --timeout-ms 120000
```

预检会按 runtime catalog 中 `requires_browser_runtime=True` 的 provider 顺序使用内置样例 DOI/URL 构造正常 HTML candidates，并复用 provider HTML bootstrap、同一 browser context 重试和 availability 判定。内置样例优先选择结构较轻、已有 fixture 覆盖的 full-text 页面，降低预热耗时；成功时会保存对应 `publisher-browser-profiles/<provider>/storage-state.json`。IEEE 会等待最多 15 秒，只有匹配文章号的 `#article` 才算 ready；初始 HTTP 202 不会单独决定结果，持续 AWS WAF 页报告 `aws_waf_challenge`，顶层状态仍为 `challenge`。结果使用唯一 `status/reason_code/stage/message` 契约：`challenge/auth_required` 才建议人工认证，`network_timeout` 建议重试，`extraction_error` 指向页面/selector 诊断，`runtime_error` 先修复本地运行时，`cancelled` 显式重跑。失败时 stdout 还会在可用时输出脱敏 final URL、Chrome exit/stderr 与 diagnostic artifact。该命令只验证 HTML 路径，不触发 PDF fallback；它会真实访问出版社样例页，不同于 MCP `provider_status()` 的本地能力检查。

MCP 的 `browser_preflight` 直接调用同一个 preflight 核心。无参数时与 CLI 一样检查全部 browser provider；单 provider 可传 `provider`，并可同时指定 `test_url`、`timeout_ms`、`browser_user_agent`、`storage_state_path`、`save_storage_state`、`browser_auto_prepare` 和 `detail="full|compact"`。MCP 的 managed runtime 准备默认关闭；只有 `browser_auto_prepare=true` 或环境显式开启时才安装/修复/更新，并通过 MCP logging notification 报告进度。`test_url` / `storage_state_path` 要求显式单 provider；默认 `save_storage_state=true`，因此该 open-world 工具不是只读操作。返回逐 provider `ready/challenge/auth_required/network_timeout/extraction_error/runtime_error/cancelled`、下一步与进度；compact 每项只保留路由字段。一个 provider 失败不抹掉其它已完成结果，取消保留已完成结果并停止后续调度。该工具始终报告未尝试 PDF fallback 和 auth；需要登录或处理 challenge 时只建议用户显式运行 `paper-fetch auth <provider>`。

普通 `paper-fetch fetch --query ...` 默认使用 managed headless Camoufox；`PAPER_FETCH_BROWSER_HEADLESS` 控制 headed/headless。只有 `paper-fetch auth <provider>` 或显式关闭 headless 时才显示窗口。

常用参数：

- `--url <url>`：覆盖内置样例文章，打开具体失败文章页。
- `--timeout-ms <ms>`：设置浏览器导航超时。
- `--browser-user-agent <ua>`：Camoufox 会拒绝该参数，以保持生成的 Firefox 指纹一致。
- `--browser-auto-prepare` / `--no-browser-auto-prepare`：允许/禁止本次 CLI 命令维护
  managed Camoufox；默认允许，环境变量可改变默认。
- storage-state 保存位置优先通过 `PAPER_FETCH_BROWSER_PROFILE_DIR` 或 `PAPER_FETCH_BROWSER_USER_DATA_DIR` 覆盖。

storage-state JSON 是主要复用状态，只是本地辅助状态，不绕过权限，也不是跨机器通用凭据；站点 session 可能按时间、网络、设备或浏览器指纹失效。未配置持久凭证不会阻止正常抓取；抓取仍会按当前 browser workflow 和 provider PDF / abstract-only / metadata fallback 运行。手动 auth 后再次抓取同一 provider 会复用同一个 publisher storage-state 文件。

## 批量抓取

批量模式使用 `--query-file <path>`，文件中每行一个 DOI、论文 landing URL 或标题；空行和以 `#` 开头的注释行会被忽略。`--query` 与 `--query-file` 互斥，必须二选一。

```bash
paper-fetch fetch --query-file ./queries.txt \
  --format markdown \
  --output-dir ./papers \
  --batch-concurrency 1 \
  --batch-results ./papers/batch-results.jsonl \
  --artifact-mode none \
  --asset-profile none \
  --include-refs all \
  --max-tokens full_text
```

批量模式不会把每篇正文打印到 stdout。每篇论文仍按 `--format` 写出主输出：

- `markdown`：`<output-dir>/<paper-stem>.md`
- `json`：`<output-dir>/<paper-stem>.json`
- `both`：`<output-dir>/<paper-stem>.both.json`

论文元数据无法提供标题且 query 也不含 DOI 时，`paper-stem` 使用规范化 query 的 16 位 SHA-256 摘要（例如 `unknown_unknown_article_<digest>`）。该回退在并发和续跑之间保持稳定，避免不同 URL 结果争用同一个匿名文件名，也不会把完整 query 写入文件名。

如果未提供 `--output-dir`，CLI 使用默认下载目录。默认事件文件是 `<output-dir>/batch-results.jsonl`，可用 `--batch-results <path>` 覆盖；原子 run 摘要默认写在事件文件同目录的 `run-manifest.json`，可用 `--run-manifest <path>` 覆盖。JSONL 每行是一条 schema v2 attempt record；旧的 `index`、`query`、`status`、`doi`、`source`、`output_path`、`saved_markdown_path`、`warnings` 和 `error` 九个顶层字段保持原名和原语义，旧消费者可以继续只读取这些字段。v2 只做增量扩展，不要求消费者一次理解所有新增字段。

```bash
paper-fetch fetch --query-file ./queries.txt \
  --format markdown \
  --output-dir ./papers \
  --batch-concurrency 4 \
  --batch-results ./papers/results.jsonl \
  --artifact-mode none \
  --asset-profile none \
  --include-refs all \
  --max-tokens full_text
```

`--batch-concurrency` 默认是 `1`，允许范围是 `1..8`。CLI 使用共享增量 runner，只维持有限的 in-flight 项。某个可静态识别的 provider lane 被限速后，不再向该 lane 提交新任务；无法从 URL/DOI 可靠判断 provider 的标题查询进入通用 lane。批量解析和 provider lane 排队不计入单篇论文的 request deadline；该预算在 fetch worker 真正取得执行槽时开始，而单篇内部的 HTML、browser、PDF 与 fallback 仍共享同一 deadline。已提交任务正常终态化，未调度项也各写一条 `record_status=aborted`、`status=aborted` 的记录。一次正常完成的批量运行保证输入数、record 数和唯一 `index` 数相等。第一次 Ctrl-C 只发出协作式取消并等待在途 worker 收敛；超过宽限期 runner 才关闭共享 browser manager，第二次 Ctrl-C 可立即升级强制关闭。

单个条目的普通 provider 错误不会停止其它 lane；失败条目会写入 JSONL 的 `error` 字段。全部调用成功且没有 aborted 时退出码为 `0`；工具失败或 aborted 为非零，并继续按 `no_access`、`rate_limited`、`ambiguous` 优先映射到 `3`、`4`、`2`，其它失败/aborted 为 `1`。`acceptance.overall=degraded` 本身不会把退出码升级为非零。

### 批量并行

批量抓取默认是串行执行，也就是 `--batch-concurrency 1`。当 `--batch-concurrency` 大于 `1` 时，CLI 会并行抓取多篇论文：

```bash
paper-fetch fetch --query-file ./queries.txt \
  --format markdown \
  --output-dir ./papers \
  --batch-concurrency 4 \
  --batch-results ./papers/batch-results.jsonl \
  --artifact-mode none \
  --asset-profile none \
  --include-refs all \
  --max-tokens full_text
```

上面的命令最多同时抓取 `4` 篇。每篇抓取会独立创建运行时上下文，避免跨任务共享 provider 解析状态；同一个 batch 会共享 HTTP transport，并按 browser 配置共享且保留 managed browser manager，因此连接池、同 host 限流、请求缓存和 provider Chrome lifecycle 可以跨条目复用，而 context/page 仍逐条隔离。item context 在预解析阶段保留已解析身份，fetch worker 开始时只重置请求时钟，不丢弃该缓存。JSONL 汇总仍由主线程在每个终态到达时立即写入并 flush，避免并发写文件。并行模式下 `batch-results.jsonl` 按任务完成顺序追加，不保证与输入文件顺序一致；`index` 始终是输入文件过滤空行和注释后的稳定 1-based 序号，消费者必须按 `index` 关联或重排输入，不能把行号当成输入顺序。

### Run 目录、状态与 attempts

默认布局如下；显式路径可以把两个 manifest 文件放到其它位置：

```text
papers/
├── run-manifest.json       # 原子替换的 run 摘要
├── batch-results.jsonl     # append-only attempt events
└── <paper-stem>.md         # 每篇最终输出
```

跨进程 run/file locks 位于 `platformdirs` 解析出的当前用户 runtime 目录，不写进论文输出目录，也不计入论文输出或 attempt event。

`run-manifest.json` 记录 schema 版本、run id、工具版本、完整有序输入、关键抓取/渲染/输出配置及其 fingerprint、时间、状态统计和事件文件位置。状态从 `running` 开始，正常终态为 `completed`；键盘中断、协作式取消和其它持久化后的失败分别落为 `interrupted`、`cancelled`、`failed`。每条完成事件写入后都会 checkpoint 摘要，因此异常退出后仍可审计已经持久化的部分。

事件文件只追加 attempt，不会在恢复时改写历史记录。`index` 在同一 run 内始终对应原输入位置，`attempt` 从 `1` 连续递增；`record_id` 由 run/index/attempt 稳定确定。JSONL 仍按终态到达顺序排列，当前状态应按每个 `index` 的最大 `attempt` 重建。

### 只读 audit / reconcile

两个子命令都不写 manifest、不修改论文文件、不联网，也不自动修复；`reconcile` 只是更明确地表达“重新读取当前文件并与历史快照核对”，当前与 `audit` 使用同一审计引擎：

```bash
paper-fetch manifest audit ./papers/run-manifest.json
paper-fetch manifest reconcile ./papers/run-manifest.json
```

stdout 是稳定 JSON 报告，包含 manifest 类型、run 状态、输入/record/index 数、缺失 index、可复用与需重试 index，以及逐条 finding。审计会检查 run/attempt 结构、request fingerprint、最终文件存在性、size/SHA256、Markdown YAML front matter 的 DOI/source/content、输出与统一 acceptance 是否满足当前请求。front matter 使用结构化 YAML parser，不按文本正则猜测。

退出码含义如下：

| 退出码 | `status` | 含义 |
| ---: | --- | --- |
| `0` | `ok` | 结构和当前最终输出均可验证 |
| `1` | `manifest_stale` | 结构可读，但 run 未完成、记录/文件缺失或当前文件不再匹配历史快照/请求 |
| `2` | `invalid` | manifest、事件 JSONL 或 run/index/attempt 结构无效，不能安全恢复 |

### 安全 resume 与 overwrite

恢复时必须同时提供原始 query 文件及原运行的完整关键选项：

```bash
paper-fetch fetch --query-file ./queries.txt \
  --format markdown \
  --output-dir ./papers \
  --batch-concurrency 4 \
  --artifact-mode none \
  --asset-profile none \
  --include-refs all \
  --max-tokens full_text \
  --resume ./papers/run-manifest.json
```

CLI 先在 run lock 内执行只读审计。只有 query、工具版本和关键配置 fingerprint 全部匹配，且当前输出的 hash、front matter 与 acceptance 仍满足请求的 index 才会跳过。缺失、stale、失败或低于请求质量的 index 会产生下一条 attempt；输入顺序或关键配置变化会直接拒绝恢复并要求新建 run。`--resume` 不能与 `--run-manifest` 同时使用；显式 `--batch-results` 时必须与 run 摘要记录的事件路径一致。

安全边界是“默认不覆盖”。新 run 的摘要、事件文件或最终输出已存在时会拒绝；resume 若需要替换仍存在的 stale/低质量输出，也会先拒绝。只有人工确认这些路径可以替换后才传 `--overwrite`。输出已缺失时可直接重新生成，无需 `--overwrite`。写入通过 path/run lock、同目录临时文件和原子替换完成；此机制不自动编辑用户 Markdown，也不提供跨机器同步。

### JSONL schema v2 字段

| 字段 | 含义 |
| --- | --- |
| `schema_version` / `minimum_reader_schema_version` | record schema 版本和最低 reader 版本，当前均为 `2` |
| `tool_version` | 产生记录的 paper-fetch 版本 |
| `run_id` / `record_id` | 同一批共享的 run UUID 和每条记录独立的 UUID；单篇也各有一个 |
| `index` / `attempt` | 稳定 1-based 输入序号和连续 attempt；resume 重试时递增 |
| `query` / `request` / `request_fingerprint` | 原始输入、影响抓取/渲染/输出的请求参数，以及规范 JSON 的 SHA256 指纹 |
| `record_status` / `status` | v2 终态 `completed/failed/aborted`，以及旧状态字段；成功调用仍是 `status=ok` |
| `identity` / `doi` / `source` | 规范化 identity、兼容 DOI 字段和最终 source |
| `started_at` / `completed_at` | 带时区的 attempt 开始和终态时间 |
| `acceptance` | 统一 identity/fetch/content/asset/output/provenance 验收；`overall` 可为 `complete/degraded/limited/failed/action_required` |
| `trace` / `fallback_codes` / `warning_codes` / `failure_codes` | 结构化 trace 与从统一验收派生的分类码，不从 warning 文本猜测 |
| `warnings` / `error` | 兼容 warning 列表和结构化错误；成功时 `error` 为 `null` |
| `semantic_losses` | 表格 fallback、布局降级、语义损失和公式 fallback/missing 计数 |
| `asset_summary` | 资产是否请求、完整/preview/失败/未归档、远程链接等统一摘要 |
| `output_artifacts` | 每个最终输出的 `path/kind/size/sha256/mtime/completed_at/verification_status` |
| `output_path` / `saved_markdown_path` | 从 `output_artifacts` 派生的两个旧兼容路径字段 |

`status=ok` 继续只表示该调用没有抛异常，不等于已取得完整正文。全文成功通常是 `acceptance.overall=complete` 或 `degraded`；preview、资产失败或语义损失可使其为 `degraded`；abstract-only / metadata-only 是 `limited`；工具或必需输出失败是 `failed` 或 `action_required`。因此旧脚本可继续检查 `status`，需要判断全文和资产质量的新脚本应读取 `acceptance`。

下面是为阅读裁剪过的一条完成记录；真实 JSONL 还会包含表中列出的全部验收子字段：

```json
{
  "schema_version": 2,
  "tool_version": "5.4.1",
  "run_id": "10000000-0000-4000-8000-000000000001",
  "record_id": "20000000-0000-4000-8000-000000000002",
  "index": 2,
  "attempt": 1,
  "query": "10.1186/1471-2105-11-421",
  "record_status": "completed",
  "status": "ok",
  "doi": "10.1186/1471-2105-11-421",
  "source": "publisher_html",
  "acceptance": {
    "overall": "complete",
    "content": {"status": "fulltext", "has_fulltext": true},
    "asset": {"status": "not_requested", "profile": "none"}
  },
  "semantic_losses": {
    "table_fallback_count": 0,
    "table_layout_degraded_count": 0,
    "table_semantic_loss_count": 0,
    "formula_missing_count": 0
  },
  "output_artifacts": [
    {
      "path": "papers/example.md",
      "kind": "primary_markdown",
      "size": 48231,
      "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "verification_status": "verified"
    }
  ],
  "output_path": "papers/example.md",
  "saved_markdown_path": null,
  "warnings": [],
  "error": null
}
```

## 主输出

主输出是本次命令最终要给用户的结果正文或结构化结果。它由 `--format`、`--output` 和 `--output-dir` 共同决定。

- `--format markdown|json|both` 控制主输出格式，默认是 `markdown`。
- 未提供 `--output-dir` 且未显式传 `--output` 时，主输出打印到 stdout。
- 提供 `--output-dir <dir>` 且未显式传 `--output` 时，主输出写入该目录，不打印正文到 stdout。
- 显式 `--output -` 会强制打印到 stdout，即使同时提供 `--output-dir`。
- 显式 `--output <path>` 会把主输出写到该路径，`--output-dir` 只作为 artifact / 资产目录。

当 `--output-dir` 承接主输出时，默认文件名来自安全化论文 stem：优先使用首作者姓氏、可选 `_et_al`、年份和标题；元数据不足时回退 query 中的 DOI，仍无法识别时使用规范化 query 的 16 位 SHA-256 摘要。格式决定后缀：

| 格式 | 主输出文件 |
| --- | --- |
| `markdown` | `<paper-stem>.md` |
| `json` | `<paper-stem>.json` |
| `both` | `<paper-stem>.both.json` |

需要精确文件名时，显式使用 `--output <path>`。

## 输出格式

- `markdown`：AI 友好的 Markdown 正文，适合直接阅读或交给 agent。
- `json`：结构化 `ArticleModel` JSON，适合程序消费。
- `both`：JSON 对象，包含 `article` 和 `markdown` 两部分。

`both` 的形状是：

```json
{
  "article": {},
  "markdown": "..."
}
```

## 主输出与 Artifact

主输出是用户请求的最终结果；artifact 是为了阅读、复现、调试或引用资产而保存的副产物。

常见 artifact 包括：

- Markdown artifact：`<paper-stem>.md`
- 资产目录：`<doi>_assets/` 或 provider 指定的同级资产目录
- PDF fallback 源文件，文件名优先使用 provider 抓取后合并的标题、作者和年份元数据
- provider 原始 HTML/XML/PDF
- HTTP textual cache：`.paper-fetch-http-cache/`
- adapter cache 或调试 JSON sidecar
- 资产下载诊断

`--artifact-mode none` 只关闭 artifact，不关闭主输出。因此下面命令仍会写主输出：

```bash
paper-fetch fetch --query "10.1016/test" \
  --format json \
  --output-dir ./papers \
  --artifact-mode none \
  --asset-profile none \
  --include-refs none \
  --max-tokens full_text
```

如果查询元数据不足以构造作者/年份/标题 stem，结果可能回退为：

```text
./papers/10.1016_test.json
```

不会额外保存 Markdown、资产或 provider 调试文件。

## Artifact 模式

CLI 默认：

```bash
--artifact-mode markdown-assets
--asset-profile body
```

`--artifact-mode markdown-assets` 保存 Markdown、按 `--asset-profile` 保存本地资产，并保留 PDF fallback 源文件；PDF 源文件名优先使用 provider 抓取后合并的标题、作者和年份元数据。不会保存 provider 原始 HTML/XML、调试 JSON sidecar 或 HTTP textual cache。

`--artifact-mode all` 保留完整调试 artifact，包括 provider HTML/PDF、辅助 artifact、HTTP textual cache 和调试 JSON sidecar。已到达页面但 extraction/availability 失败时，另在 `diagnostics/<provider>/<doi-or-url-digest>/<route>-<attempt>/` 保存 `diagnostic.json` 与 `page-sanitized.html`；后者删除脚本、表单、事件属性、email 和 URL query/userinfo，不保存原始失败 HTML 或截图。批量成功与终态失败 record 都将这些文件列为 `kind=diagnostic` 并快照 size/SHA-256。

`--artifact-mode none` 不保存 provider artifact 或资产；显式 `--output <path>`、`--save-markdown`，以及未显式 `--output` 时由 `--output-dir` 承接的主输出仍可写文件。

`--no-download` 是 CLI 的 `--artifact-mode none` alias，只关闭 provider artifact 和资产归档。它不表示“禁止所有写盘”，也不会阻止显式 `--output <path>`、由 `--output-dir` 承接的主输出或 `--save-markdown`。如果同时需要不下载资产，agent-facing 调用仍应显式传 `--asset-profile none`；该 alias 不改变公开的 `--asset-profile body` 默认值。

## 资产下载

`--asset-profile` 只控制本地内容资产下载范围，不决定主输出是否写文件。

- `none`：不下载本地资产；不主动清除 Markdown 中已有或 provider 可解析出的远程图片链接。
- `body`：默认值，保存正文图片、图表、公式图片等。
- `all`：在正文资产之外，额外保存可识别的补充材料等相关资产。

PDF fallback 在 `body` / `all` 且 artifact mode 允许资产落盘时，会保存 `pymupdf4llm` 从 PDF 导出的正文图片到 `<doi>_assets/`；`none` 或 `--artifact-mode none` 保持不保存本地图片资产。

当 artifact mode 或 `--no-download` 禁止资产落盘时，即使 `--asset-profile` 是 `body` 或 `all`，资产也不会保存。

## `--save-markdown`

`--save-markdown` 是独立的 Markdown 保存步骤，只在实际拿到 full text 时写文件。

常见用途是主输出选择 JSON，但仍额外保存一份可阅读 Markdown：

```bash
paper-fetch fetch --query "10.1016/test" \
  --format json \
  --output ./article.json \
  --output-dir ./papers \
  --save-markdown \
  --artifact-mode none \
  --asset-profile none \
  --include-refs all \
  --max-tokens full_text
```

如果主输出本身已经是 `--output-dir` 下的默认 Markdown 文件，CLI 会避免重复写同一个 Markdown。

## 常见命令

| 命令 | stdout | 主输出文件 | artifact / 资产 |
| --- | --- | --- | --- |
| `paper-fetch fetch --query ... --output - --no-download --artifact-mode none --asset-profile none` | 打印 Markdown | 无显式主输出文件 | 无论文 artifact/资产；仍准备工作目录 |
| `paper-fetch fetch --query ... --output-dir ./papers --artifact-mode none --asset-profile none` | 不打印正文 | `./papers/<paper-stem>.md` | 不保存额外 artifact/资产 |
| `paper-fetch fetch --query ... --format json --output-dir ./papers --artifact-mode markdown-assets --asset-profile body` | 不打印正文 | `./papers/<paper-stem>.json` | 另保存 Markdown artifact、PDF fallback 与正文资产 |
| `paper-fetch fetch --query ... --format both --output-dir ./papers --artifact-mode markdown-assets --asset-profile all` | 不打印正文 | `./papers/<paper-stem>.both.json` | 另保存 Markdown artifact、PDF fallback、正文与补充资产 |
| `paper-fetch fetch --query ... --output - --output-dir ./papers --artifact-mode markdown-assets --asset-profile body` | 打印 Markdown | 无默认主输出文件 | `./papers` 只用于 Markdown artifact/PDF fallback/正文资产 |
| `paper-fetch fetch --query ... --output ./result.md --output-dir ./papers --artifact-mode none --asset-profile none` | 不打印正文 | `./result.md` | 不保存额外 artifact/资产 |
| `paper-fetch fetch --query ... --format json --output-dir ./papers --artifact-mode none --asset-profile none` | 不打印正文 | `./papers/<paper-stem>.json` | 不保存 artifact/资产 |
| `paper-fetch fetch --query ... --output - --artifact-mode none --asset-profile none` | 打印 Markdown | 无 | 不保存论文文件；仍准备工作目录 |
| `paper-fetch fetch --query-file ./queries.txt --output-dir ./papers --artifact-mode none --asset-profile none` | 不打印正文 | 每篇 `./papers/<paper-stem>.md`，另有 `batch-results.jsonl` 和 `run-manifest.json` | 文本批量归档，不保存额外 artifact/资产 |
| `paper-fetch doctor --group browser --json` | 打印静态诊断 JSON | 无 | 不访问网络、不启动浏览器、不写 storage-state |

## 渲染选项

- `--include-refs none|top10|all` 控制 references 渲染范围。
- `--asset-profile none|body|all` 控制本地内容资产范围；PDF fallback 在 `body` / `all` 下也会尝试保存 PDF 导出的正文图片。
- `--max-tokens full_text|<positive-int>` 控制 Markdown 渲染预算，默认是 `full_text`。
- `--version` 输出当前安装版本并退出。

## 默认目录

未显式设置目录时，CLI 使用 `PAPER_FETCH_DOWNLOAD_DIR` 或用户数据目录下的 `paper-fetch/downloads`。如果用户数据目录创建失败，会退回 repo-local `live-downloads`。

`--output-dir` 会覆盖本次命令的落盘目录。

CLI 会在开始抓取前创建最终输出目录，包括显式 `--output-dir` 和 `PAPER_FETCH_DOWNLOAD_DIR` 指向的目录。如果该路径已存在但不是目录，命令会以普通错误退出。显式 `--output <path>` 只控制主输出文件，不会自动创建该文件的父目录。

## 错误输出

运行时抓取失败会把 JSON 写到 stderr，stdout 不输出正文。常见形状：

```json
{
  "status": "no_access",
  "reason": "...",
  "candidates": null
}
```

常见 exit code：

| exit code | 含义 |
| --- | --- |
| `0` | 成功 |
| `1` | 通用错误 |
| `2` | 查询歧义或 argparse 参数错误 |
| `3` | 无访问权限 |
| `4` | 被限速 |
