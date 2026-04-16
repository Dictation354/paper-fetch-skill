# Provider 能力与运行时行为

这份文档解决：

- 各 provider 能做什么、不能做什么
- 运行时如何做路由和回退
- 默认输出策略与下载行为
- 配置项、环境变量、限速与缓存护栏

这份文档不解决：

- agent runtime 的安装与 MCP 注册
- Science / PNAS 的具体启动脚本与运维排障
- 架构分层和数据契约的完整背景

部署入口见 [`deployment.md`](deployment.md)，Science / PNAS 运维细节见 [`flaresolverr.md`](flaresolverr.md)，架构说明见 [`architecture/target-architecture.md`](architecture/target-architecture.md)。

## Provider 能力矩阵

| Provider | 元数据 | 全文主路径 | 资产下载 | Markdown 能力 | 备注 |
| --- | --- | --- | --- | --- | --- |
| `crossref` | 支持 | 不负责正文抓取 | 不支持 | 不适用 | 既是 metadata 来源，也可能只是 routing signal |
| `elsevier` | 官方 API，失败可回退 Crossref | 官方全文 API，优先 XML | `none` / `body` / `all` | 强 | 适合结构化正文和资产下载 |
| `springer` | 官方 Meta API | Full Text API 或 Open Access API | `none` / `body` / `all` | 强 | XML 路径最稳定 |
| `wiley` | 当前不走官方 metadata | 官方 TDM endpoint | 当前按单文件全文处理 | 中 | 常见是 PDF 提取，不默认承诺高保真结构 |
| `science` | 依赖 Crossref | provider 自管 `HTML -> PDF fallback` | 当前固定 text-only | 中 | 依赖 repo-local FlareSolverr 工作流 |
| `pnas` | 依赖 Crossref | provider 自管 `HTML -> PDF fallback` | 当前固定 text-only | 中 | 依赖 repo-local FlareSolverr 工作流 |

## 路由规则

当前 provider 决策不再以 DOI 前缀为唯一依据，而是统一按更强信号优先：

```text
domain > publisher > DOI fallback
```

具体含义：

- `domain`
  - 由落地页 URL 或 Crossref metadata 的 `landing_page_url` 推导。
- `publisher`
  - 由 Crossref metadata 的 `publisher` 推导。
- `DOI fallback`
  - 在前两类信号都不够时，才使用 DOI 前缀兜底。

### `provider_hint` 的含义

- `resolve_paper().provider_hint` 表示“当前最可信的 provider 提示”。
- 它来自 domain、publisher、DOI 信号综合判断。
- 它不是“保证最终一定由该 provider 成功返回”的承诺。

### `crossref` 作为 signal 与 source 的区别

`crossref` 有两种角色：

1. 作为 routing signal
   - 用于拿 `publisher`、`landing_page_url`、`license`、`fulltext_links` 等信号。
   - 此时不会自动把最终结果的 `source` 变成 `crossref_meta`。
2. 作为 public source
   - 当官方 provider 不可用，或调用方允许走 metadata-only 结果时，最终结果可能公开表现为 `source="crossref_meta"` 或 `source="metadata_only"`。

### `preferred_providers` 的语义

- 它严格限制最终允许进入的 official/fulltext/html 路径。
- 它不阻止系统内部调用 `crossref` 做路由判断。
- 如果显式设为 `["crossref"]`，行为会收敛成 Crossref-only。
- 当前也可以显式指定 `science`、`pnas`。

## 抓取瀑布与回退语义

统一主线如下：

```text
resolve
-> metadata / routing
-> official provider fulltext
-> HTML fallback 或 provider 内部 fallback
-> metadata-only fallback
```

### 1. resolve

- 输入可以是 DOI、URL 或标题。
- 标题查询会走 Crossref 候选打分。
- 如果标题候选不够确定，会返回 `ambiguous`，而不是直接抓取错误论文。

### 2. metadata 与路由

- 系统会先尽可能拿到 Crossref metadata。
- 命中官方 provider 时，还可能做轻量 metadata probe。
- 最终会合并 primary / secondary metadata，统一生成正文抓取需要的元数据。

### 3. 官方全文路径

- `elsevier`
  - 优先拿 XML，必要时可能落 PDF/binary 本地副本。
- `springer`
  - 优先 Full Text API，其次 Open Access API。
- `wiley`
  - 通过 TDM endpoint 拿正文载体，常见情况是 PDF。
- `science` / `pnas`
  - 自己管理 HTML 与 PDF fallback，不走通用 `html_generic`。

### 4. HTML fallback

普通 provider 在官方链路失败后，可按 `strategy.allow_html_fallback` 进入通用 `html_generic` fallback：

- 会抓取落地页 HTML
- 提取正文 Markdown
- 在允许落盘且 `asset_profile` 为 `body` / `all` 时尝试下载 figure 资产
- 如果正文不足，会判定为 fallback 失败

### 5. metadata-only fallback

如果正文不可得，而 `strategy.allow_metadata_only_fallback=true`：

- 返回 metadata + abstract
- `has_fulltext=false`
- `warnings` 中显式说明已降级
- `source_trail` 中会带 `fallback:metadata_only`

如果关闭这个开关，正文不可得会直接抛错。

## Science / PNAS 的特殊语义

`science` / `pnas` 与其他 provider 的不同点是：

- metadata 仍来自 `crossref`
- 全文链路由 provider 自己控制
- 主链路是 `HTML first -> PDF fallback -> metadata-only`
- 不进入通用 `html_generic` fallback
- `asset_profile=body|all` 当前会降级成 text-only

因此：

- `strategy.allow_html_fallback=false` 不会关闭它们的 provider 内部 HTML 主路径
- 结果来源仍公开成 `source="science"` 或 `source="pnas"`
- HTML 成功还是 PDF fallback 成功，要看 `source_trail`

## 默认输出策略

CLI、Python API、MCP 当前统一采用这些默认值：

- `asset_profile="none"`
- `max_tokens="full_text"`
- `include_refs=null`

### `asset_profile`

- `none`
  - 不下载资产
  - Markdown 保留 figure caption
  - 不输出 supplementary 链接
- `body`
  - 下载正文 figure
  - 下载正文表格原图
  - 不包含 supplementary
- `all`
  - 下载当前 provider 已识别的全部相关资产

### `include_refs`

- `max_tokens="full_text"` 时，默认等价于 `all`
- `max_tokens=<整数>` 时，默认等价于 `top10`

### 下载行为

- `--no-download` 或 `download_dir=None` 优先级最高
- 即使 `asset_profile` 是 `body` / `all`，也不会落盘
- 没有本地文件时，Markdown 会自动退回 captions-only 或不展示本地资源链接

## 公开输出里最重要的字段

这些字段最适合拿来判断结果质量和来源：

- `source`
  - 粗粒度公开来源，如 `elsevier_xml`、`springer_xml`、`wiley_tdm`、`science`、`pnas`、`html_fallback`、`metadata_only`
- `has_fulltext`
  - 最终抓取瀑布后的 verdict
- `warnings`
  - 降级、截断、资产部分失败等信息
- `source_trail`
  - 更细粒度的路由、probe、fallback、下载轨迹
- `token_estimate_breakdown`
  - `abstract`、`body`、`refs` 的 token 估算

## 配置文件与环境变量入口

默认主配置文件：

```text
~/.config/paper-fetch/.env
```

如果你在开发场景里要使用仓库外的某个配置文件，显式设置：

```bash
PAPER_FETCH_ENV_FILE=/path/to/.env
```

### 通用环境变量

#### `PAPER_FETCH_SKILL_USER_AGENT`

- 自定义请求用 `User-Agent`。
- 建议配置为稳定项目标识。

#### `CROSSREF_MAILTO`

- Crossref polite pool 建议携带的联系邮箱。
- 会被拼入 Crossref 请求参数。

#### `PAPER_FETCH_DOWNLOAD_DIR`

- 覆盖默认下载目录。
- CLI 与 MCP 都会优先使用它。

#### `XDG_DATA_HOME`

- 在未配置 `PAPER_FETCH_DOWNLOAD_DIR` 时，用来推导用户数据目录。

### Elsevier

#### `ELSEVIER_API_KEY`

- 必填。
- Elsevier metadata 和全文 API 的核心凭证。

#### `ELSEVIER_INSTTOKEN`

- 可选。
- 机构授权场景补充凭证。

#### `ELSEVIER_AUTHTOKEN`

- 可选。
- Bearer token 形式的补充凭证。

#### `ELSEVIER_CLICKTHROUGH_TOKEN`

- 可选。
- clickthrough 场景补充凭证。

### Springer

#### `SPRINGER_META_API_KEY`

- 元数据 API 凭证。

#### `SPRINGER_OPENACCESS_API_KEY`

- Open Access API 凭证。

#### `SPRINGER_FULLTEXT_API_KEY`

- Full Text API 凭证。

#### `SPRINGER_FULLTEXT_URL_TEMPLATE`

- Full Text API URL 模板。

#### `SPRINGER_FULLTEXT_AUTH_HEADER`

- Full Text API 自定义鉴权 header 名。

#### `SPRINGER_FULLTEXT_ACCEPT`

- Full Text API `Accept` 值，默认 `application/xml`。

### Wiley

#### `WILEY_TDM_URL_TEMPLATE`

- Wiley TDM endpoint 模板。

#### `WILEY_TDM_TOKEN`

- Wiley TDM 凭证。

#### `WILEY_TDM_AUTH_HEADER`

- 鉴权 header 名，默认 `Wiley-TDM-Client-Token`。

### Science / PNAS

#### `FLARESOLVERR_URL`

- 本地 FlareSolverr 服务地址。
- 默认 `http://127.0.0.1:8191/v1`。

#### `FLARESOLVERR_ENV_FILE`

- 必填。
- 必须显式指向当前仓库 `vendor/flaresolverr/` 下的 preset。

#### `FLARESOLVERR_SOURCE_DIR`

- 可选。
- 覆盖 repo-local FlareSolverr workflow 根目录。

#### `FLARESOLVERR_MIN_INTERVAL_SECONDS`

- 必填。
- Science / PNAS 本地最小请求间隔。

#### `FLARESOLVERR_MAX_REQUESTS_PER_HOUR`

- 必填。
- Science / PNAS 每小时上限。

#### `FLARESOLVERR_MAX_REQUESTS_PER_DAY`

- 必填。
- Science / PNAS 每日上限。

更具体的启动与排障步骤见 [`flaresolverr.md`](flaresolverr.md)。

## 运行时护栏

### 进程内 HTTP 缓存

`HttpTransport` 带短 TTL 的进程内 GET 缓存：

- 同一 DOI 的重复 Crossref / metadata 请求可直接命中缓存
- 只有小体积文本响应会入缓存
- PDF 和其他大体积二进制正文不会缓存
- 缓存 key 会脱敏 `api_key`、token、`mailto` 等敏感字段

### HTTP 重试与大小限制

默认护栏包括：

- `max_response_bytes=32 MiB`
- 对 `5xx` 和 timeout 级网络错误做有限短重试
- `429` 只按 `Retry-After` 处理，不混进瞬时错误重试
- 底层使用 `urllib3.PoolManager` 复用连接

### provider_status

`provider_status()` 只检查本地条件，不主动探测远端 publisher API 连通性。

返回顺序固定是：

- `crossref`
- `elsevier`
- `springer`
- `wiley`
- `science`
- `pnas`

provider 级状态固定为：

- `ready`
- `partial`
- `not_configured`
- `rate_limited`
- `error`

### 限速与并发建议

- 除 `science` / `pnas` 的本地账本限速外，其余 provider 不做强制自动 throttle。
- 推荐不要对同一 DOI 并发触发多次抓取。
- 批量处理 citation list 时，建议串行，或把并发度压到 2 到 3。
- `batch_resolve()` / `batch_check()` 默认 `concurrency=1`。
- 同一 host 内部仍保持串行，避免对单一 publisher 形成并发冲击。

## 哪些内容最稳，哪些能力更窄

更适合优先期待稳定表现的内容：

- `elsevier` / `springer` 的结构化正文
- 标准 DOI 解析与 Crossref 元数据
- MCP `fetch_paper()` 返回的 envelope 级 provenance 字段

能力相对更窄或更依赖环境的内容：

- `wiley` 的 PDF 提取路径
- `science` / `pnas` 的 repo-local 浏览器工作流
- HTML fallback 的页面清洗效果

## 相关文档

- [`README.md`](../README.md)
- [`deployment.md`](deployment.md)
- [`flaresolverr.md`](flaresolverr.md)
- [`architecture/target-architecture.md`](architecture/target-architecture.md)
- [`architecture/probe-semantics.md`](architecture/probe-semantics.md)
