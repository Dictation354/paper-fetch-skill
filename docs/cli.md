# CLI 使用说明

这份文档是 `paper-fetch` 命令行行为的权威说明，重点解释主输出、artifact、资产下载和常见参数组合。

## 基本用法

```bash
paper-fetch --query "10.1186/1471-2105-11-421"
```

`--query` 可以是 DOI、论文 landing URL 或标题查询。CLI 默认会优先尝试全文；如果全文不可用，可能返回摘要或 metadata-only 结果。MDPI 的经典数字 URL（例如 `https://www.mdpi.com/2072-4292/18/10/1673`）会先按已知 ISSN 到 journal code 映射推导 DOI；MDPI DOI / DOI URL 也会在 provider 阶段反推对应的数字 article URL，再进入 MDPI CDP browser provider，避免解析阶段被 MDPI direct HTTP/CDN 403 阻断；未知 ISSN 仍按通用 landing URL 解析。URL 中嵌入 DOI 时，resolver 会复用 provider path templates 清理已知 route 后缀，例如 Frontiers 的 `/full` / `/pdf` / `/xml`、IOP 的 `/pdf`、Wiley 的 `/fullpdf` 和 Springer PDF URL 的 `.pdf`，PLOS 这类 `id={doi}` query parameter 也会直接提取 DOI；未知 provider 的 DOI 后缀不会被猜测性剥离。旧式 SICI DOI（例如 `10.1175/1520-0469(1967)024<0241:TEOTAW>2.0.CO;2` 或 Wiley/Blackwell 的 `10.1002/(SICI)...<...>...`）会保留完整 `<...>` / `;` 后缀；对应的 AMS `view/...xml` 或 `downloadpdf/...pdf` URL 可作为 query。官方 PDF fallback 已经下载到真实 PDF 但无法转换成 Markdown 时，会保留已下载的 PDF artifact 并在 warning 中说明 PDF-only 状态，而不是降级成 Crossref metadata-only source。

## Browser 登录态

Browser workflow 优先连接已运行浏览器的 CDP endpoint；未配置时会通过 cloakbrowser 首次下载/定位 Chrome，并自动启动受控 CDP 浏览器。默认 managed 模式在同一进程内复用一个按 provider/browser 配置 keyed 的 browser manager，CLI/MCP 批量并发任务不会为同一个 provider profile 启动多个 Chrome 去抢 `.paper-fetch-profile.lock`；HTML、PDF fallback 和 browser-backed 资产下载仍各自打开隔离 context/page，并在调用线程建立自己的 CDP 连接，避免跨线程复用 Playwright sync 对象。自动浏览器默认按 publisher 复用本地 `publisher-browser-profiles/<provider>/storage-state.json`，以减少 Science/Wiley 等站点的冷启动 challenge；相关目录变量主要覆盖 managed Chrome 启动目录和 storage-state 保存位置，不承诺完整复用浏览器 profile 的其它状态。需要复用手动验证过的浏览器时，可先启动 Chrome/CloakBrowser 并设置 `CLOAKBROWSER_CDP_ENDPOINT`；外部 CDP 模式以现有 browser context 为准，storage-state 中的 cookies 会尽量注入，UA、viewport 等新 context 参数不保证生效。managed 和外部 CDP 的 runtime-shared browser-backed 资产下载都会串行化，以避免跨线程复用 Playwright sync 对象；普通 HTTP 资产下载仍按配置并发：

```bash
/path/to/chrome \
  --user-data-dir "$HOME/.cache/paper-fetch/browser-profile" \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9222 \
  --no-first-run

export CLOAKBROWSER_CDP_ENDPOINT="ws://127.0.0.1:9222/devtools/browser/..."
```

如果自动过盾失败，可用通用手动 fallback 打开 headed browser：

```bash
paper-fetch auth <provider>
paper-fetch auth wiley --url "https://onlinelibrary.wiley.com/doi/full/10.1111/example"
```

`provider` 来自 browser runtime catalog，例如 `wiley` / `science` / `pnas` / `ams` / `annualreviews` / `acs` / `iop` / `aip` / `mdpi`。未传 `--url` 时打开内置样例文章；传入 `--url` 时打开用户指定的失败文章页。命令强制 headed 模式，打印 managed Chrome 启动目录和 storage-state 路径，用户在浏览器中完成合法登录或验证后，在终端按 Enter 保存过滤后的本地 storage-state 并退出。

如果需要在批量抓取前确认所有 browser-backed provider 的浏览器链路是否能过站点验证，可以先串行运行预检：

```bash
paper-fetch browser-preflight
paper-fetch browser-preflight --provider wiley --provider science --timeout-ms 120000
```

预检会按 runtime catalog 中 `requires_browser_runtime=True` 的 provider 顺序打开内置样例文章。成功时会保存对应 `publisher-browser-profiles/<provider>/storage-state.json`；失败时 stdout 保留逐 provider 汇总，stderr 打印失败出版社和 `paper-fetch auth <provider>` 人工认证提示。该命令会真实访问出版社样例页；它不同于 MCP/provider `provider_status()` 的本地能力检查。

普通 `paper-fetch --query ...` 抓取在未设置 `CLOAKBROWSER_HEADLESS=0` 且未配置外部 `CLOAKBROWSER_CDP_ENDPOINT` 时默认使用 managed headless Chrome，并确保启动参数包含 `--headless=new`。只有 `paper-fetch auth <provider>`、显式关闭 headless，或连接到已有 headed CDP 浏览器时才会显示浏览器窗口。

常用参数：

- `--url <url>`：覆盖内置样例文章，打开具体失败文章页。
- `--timeout-ms <ms>`：设置浏览器导航超时。
- `--browser-user-agent <ua>`：仅本次认证使用的 browser UA。
- storage-state 保存位置通过 `CLOAKBROWSER_PROFILE_DIR` 或 `CLOAKBROWSER_USER_DATA_DIR` 覆盖。

storage-state JSON 是主要复用状态，只是本地辅助状态，不绕过权限，也不是跨机器通用凭据；站点 session 可能按时间、网络、设备或浏览器指纹失效。未配置持久凭证不会阻止正常抓取；抓取仍会按当前 browser workflow 和 provider PDF / abstract-only / metadata fallback 运行。手动 auth 后再次抓取同一 provider 会复用同一个 publisher storage-state 文件。

## 批量抓取

批量模式使用 `--query-file <path>`，文件中每行一个 DOI、论文 landing URL 或标题；空行和以 `#` 开头的注释行会被忽略。`--query` 与 `--query-file` 互斥，必须二选一。

```bash
paper-fetch --query-file ./queries.txt --output-dir ./papers
```

批量模式不会把每篇正文打印到 stdout。每篇论文仍按 `--format` 写出主输出：

- `markdown`：`<output-dir>/<doi-or-title>.md`
- `json`：`<output-dir>/<doi-or-title>.json`
- `both`：`<output-dir>/<doi-or-title>.both.json`

如果未提供 `--output-dir`，CLI 使用默认下载目录。默认汇总文件是 `<output-dir>/batch-results.jsonl`，可用 `--batch-results <path>` 覆盖。每行是一条 JSON 结果，包含 `index`、`query`、`status`、`doi`、`source`、`output_path`、`saved_markdown_path`、`warnings` 和 `error`。

```bash
paper-fetch --query-file ./queries.txt \
  --output-dir ./papers \
  --batch-concurrency 4 \
  --batch-results ./papers/results.jsonl
```

`--batch-concurrency` 默认是 `1`，允许范围是 `1..8`。单篇失败不会终止整批，失败条目会写入 JSONL 的 `error` 字段；全部成功退出码为 `0`，存在失败则为非零，并优先按 `no_access`、`rate_limited`、`ambiguous` 映射到 `3`、`4`、`2`。

### 批量并行

批量抓取默认是串行执行，也就是 `--batch-concurrency 1`。当 `--batch-concurrency` 大于 `1` 时，CLI 会并行抓取多篇论文：

```bash
paper-fetch --query-file ./queries.txt \
  --output-dir ./papers \
  --batch-concurrency 4
```

上面的命令最多同时抓取 `4` 篇。每篇抓取会独立创建运行时上下文，避免跨任务共享 provider/runtime 状态；同一个 batch 会共享 HTTP transport，因此连接池、同 host 限流和请求缓存可以跨条目复用。JSONL 汇总仍由主线程写入，避免并发写文件。并行模式下 `batch-results.jsonl` 按任务完成顺序追加，不保证与输入文件顺序一致；需要还原输入顺序时使用每条记录里的 `index` 字段。

## 主输出

主输出是本次命令最终要给用户的结果正文或结构化结果。它由 `--format`、`--output` 和 `--output-dir` 共同决定。

- `--format markdown|json|both` 控制主输出格式，默认是 `markdown`。
- 未提供 `--output-dir` 且未显式传 `--output` 时，主输出打印到 stdout。
- 提供 `--output-dir <dir>` 且未显式传 `--output` 时，主输出写入该目录，不打印正文到 stdout。
- 显式 `--output -` 会强制打印到 stdout，即使同时提供 `--output-dir`。
- 显式 `--output <path>` 会把主输出写到该路径，`--output-dir` 只作为 artifact / 资产目录。

当 `--output-dir` 承接主输出时，默认文件名来自 DOI 或标题并经过安全化处理：

| 格式 | 主输出文件 |
| --- | --- |
| `markdown` | `<doi>.md` |
| `json` | `<doi>.json` |
| `both` | `<doi>.both.json` |

例如 DOI `10.1016/test` 会写成 `10.1016_test.md`。

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

- Markdown artifact：`<doi>.md`
- 资产目录：`<doi>_assets/`
- PDF fallback 源文件，文件名优先使用 provider 抓取后合并的标题、作者和年份元数据
- provider 原始 HTML/XML/PDF
- HTTP textual cache：`.paper-fetch-http-cache/`
- adapter cache 或调试 JSON sidecar
- 资产下载诊断

`--artifact-mode none` 只关闭 artifact，不关闭主输出。因此下面命令仍会写主输出：

```bash
paper-fetch --query "10.1016/test" --format json --output-dir ./papers --artifact-mode none
```

结果是：

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

`--artifact-mode all` 保留完整调试 artifact，包括 provider HTML/PDF、辅助 artifact、HTTP textual cache 和调试 JSON sidecar 等。

`--artifact-mode none` 不保存 provider artifact 或资产；显式 `--output <path>`、`--save-markdown`，以及未显式 `--output` 时由 `--output-dir` 承接的主输出仍可写文件。

`--no-download` 等价于 `--artifact-mode none`。

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
paper-fetch --query "10.1016/test" \
  --format json \
  --output ./article.json \
  --output-dir ./papers \
  --save-markdown
```

如果主输出本身已经是 `--output-dir` 下的默认 Markdown 文件，CLI 会避免重复写同一个 Markdown。

## 常见命令

| 命令 | stdout | 主输出文件 | artifact / 资产 |
| --- | --- | --- | --- |
| `paper-fetch --query ...` | 打印 Markdown | 无显式主输出文件 | 拿到全文时在默认目录保存 Markdown/正文资产 |
| `paper-fetch --query ... --output-dir ./papers` | 不打印正文 | `./papers/<doi>.md` | 拿到全文时在 `./papers` 下保存正文资产 |
| `paper-fetch --query ... --format json --output-dir ./papers` | 不打印正文 | `./papers/<doi>.json` | 拿到全文时默认还保存 Markdown artifact 和正文资产 |
| `paper-fetch --query ... --format both --output-dir ./papers` | 不打印正文 | `./papers/<doi>.both.json` | 拿到全文时默认还保存 Markdown artifact 和正文资产 |
| `paper-fetch --query ... --output - --output-dir ./papers` | 打印 Markdown | 无默认主输出文件 | `./papers` 只用于 artifact/资产 |
| `paper-fetch --query ... --output ./result.md --output-dir ./papers` | 不打印正文 | `./result.md` | `./papers` 只用于 artifact/资产 |
| `paper-fetch --query ... --format json --output-dir ./papers --artifact-mode none` | 不打印正文 | `./papers/<doi>.json` | 不保存 artifact/资产 |
| `paper-fetch --query ... --output - --artifact-mode none` | 打印 Markdown | 无 | 不保存 artifact/资产 |
| `paper-fetch --query-file ./queries.txt --output-dir ./papers` | 不打印正文 | 每篇 `./papers/<doi-or-title>.md`，另有 `batch-results.jsonl` | 拿到全文时在 `./papers` 下保存正文资产 |

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
