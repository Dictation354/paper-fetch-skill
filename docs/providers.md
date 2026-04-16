# Provider 能力与运行时行为

这份文档解决：

- 各 provider 能做什么、不能做什么
- 运行时如何做路由和回退
- 默认输出策略与下载行为
- 配置项、环境变量、限速与缓存护栏

这份文档不解决：

- agent runtime 的安装与 MCP 注册
- Elsevier browser fallback / Wiley / Science / PNAS 的具体启动脚本与运维排障
- 架构分层和数据契约的完整背景

部署入口见 [`deployment.md`](deployment.md)，Elsevier browser fallback / Wiley / Science / PNAS 运维细节见 [`flaresolverr.md`](flaresolverr.md)，架构说明见 [`architecture/target-architecture.md`](architecture/target-architecture.md)。

## Provider 能力矩阵

| Provider | 元数据 | 全文主路径 | 资产下载 | Markdown 能力 | 备注 |
| --- | --- | --- | --- | --- | --- |
| `crossref` | 支持 | 不负责 publisher fulltext | 不支持 | 不适用 | 负责 resolve、routing signal、metadata merge 与 metadata-only fallback |
| `elsevier` | 官方 API | `官方 XML/API -> FlareSolverr HTML` | XML 路线支持 `none` / `body` / `all`；browser fallback 当前 text-only | 强 | 公开来源可能是 `elsevier_xml` 或 `elsevier_browser` |
| `springer` | 依赖 Crossref merge | `direct HTML -> direct HTTP PDF` | HTML 路线支持 `none` / `body` / `all`；PDF fallback 当前 text-only | 强 | `nature.com` 继续挂在 `springer` provider / `springer_html` source 下 |
| `wiley` | 依赖 Crossref merge | `FlareSolverr HTML -> Wiley TDM API PDF` | 当前固定 text-only | 中 | HTML 依赖 repo-local FlareSolverr；PDF fallback 依赖 `WILEY_TDM_CLIENT_TOKEN` |
| `science` | 依赖 Crossref | `FlareSolverr HTML -> seeded-browser PDF` | 当前固定 text-only | 中 | 与 `wiley` 共用浏览器工作流基座 |
| `pnas` | 依赖 Crossref | `FlareSolverr HTML -> seeded-browser PDF` | 当前固定 text-only | 中 | 与 `wiley` 共用浏览器工作流基座 |

## 路由规则

当前 provider 决策统一按更强信号优先：

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
   - 当 publisher fulltext 不可用，或调用方允许走 metadata-only 结果时，最终结果可能公开表现为 `source="crossref_meta"` 或 `source="metadata_only"`。

### `preferred_providers` 的语义

- 它严格限制最终允许进入的 provider-owned fulltext / generic HTML 路径。
- 它不阻止系统内部调用 `crossref` 做路由判断。
- 如果显式设为 `["crossref"]`，行为会收敛成 Crossref-only。
- 当前可显式指定的 provider 名包括：
  - `elsevier`
  - `springer`
  - `wiley`
  - `science`
  - `pnas`
  - `crossref`

## 抓取瀑布与回退语义

统一主线如下：

```text
resolve
-> metadata / routing
-> provider fulltext
-> generic HTML fallback 或 provider 内部 fallback
-> metadata-only fallback
```

### 1. resolve

- 输入可以是 DOI、URL 或标题。
- 标题查询会走 Crossref 候选打分。
- 如果标题候选不够确定，会返回 `ambiguous`，而不是直接抓取错误论文。

### 2. metadata 与路由

- 系统会先尽可能拿到 Crossref metadata。
- 只有 `elsevier` 还会参加 publisher metadata probe。
- `springer`、`wiley`、`science`、`pnas` 在 `probe_official_provider()` 和 `has_fulltext()` 中都只依赖 Crossref / landing-page 信号，不再调用 publisher metadata API。
- 最终会合并 primary / secondary metadata，统一生成正文抓取需要的元数据。

### 3. provider 全文主路径

- `elsevier`
  - 固定顺序是 `官方 XML/API -> FlareSolverr HTML -> metadata-only`。
  - XML/API 成功时公开 `source="elsevier_xml"`。
  - 浏览器 HTML 成功时公开 `source="elsevier_browser"`。
- `springer`
  - 固定顺序是 `direct HTML -> direct HTTP PDF -> metadata-only`。
  - 优先抓取 publisher landing HTML，不足正文时再走 direct HTTP PDF。
  - 优先使用 merged metadata 中的 `landing_page_url`，缺失时回退 DOI 解析。
  - 成功时公开 `source="springer_html"`。
- `wiley`
  - 使用 provider 自管 HTML + 官方 API PDF waterfall。
  - 固定顺序是 `FlareSolverr HTML -> Wiley TDM API PDF -> metadata-only`。
  - 成功时公开 `source="wiley_browser"`。
- `science` / `pnas`
  - 与 `wiley` 共享同一套浏览器工作流基座。
  - 公开 `source` 继续保持 `science` / `pnas`。

### 4. 通用 `html_generic` fallback

通用 HTML fallback 仍然存在，但只服务“非 provider-owned HTML 路径”的场景，例如：

- 未命中 provider 自管 HTML 主链时的网页提取

它不再参与这些 provider 的 fulltext 主链或失败回退：

- `elsevier`
- `springer`
- `wiley`
- `science`
- `pnas`

对这些 provider 来说：

- `elsevier` 会先在 provider 内部做 HTML fallback，再决定是否 metadata-only
- `springer` 会先在 provider 内部做 direct HTTP PDF fallback，再决定是否 metadata-only
- `wiley` 先在 provider 内部做 Wiley TDM API PDF fallback，再决定是否 metadata-only
- `science` / `pnas` 先在 provider 内部做 seeded-browser PDF fallback，再决定是否 metadata-only

### 5. metadata-only fallback

如果正文不可得，而 `strategy.allow_metadata_only_fallback=true`：

- 返回 metadata + abstract
- `has_fulltext=false`
- `warnings` 中显式说明已降级
- `source_trail` 中会带 `fallback:metadata_only`

如果关闭这个开关，正文不可得会直接抛错。

## Elsevier / Springer / Wiley / Science / PNAS 的特殊语义

这五个 provider 的共同点是：

- metadata 仍主要来自 `crossref`
- fulltext 主路径由 provider 自己控制
- 不回到通用 `html_generic` fallback

但它们的 fulltext 形态不同：

- `elsevier`
  - provider 自管 `官方 XML/API -> FlareSolverr HTML`
  - 成功轨迹会组合 `fulltext:elsevier_xml_fail`、`fulltext:elsevier_html_ok|fail`
- `springer`
  - provider 自管 `direct HTML -> direct HTTP PDF`
  - 成功轨迹是 `fulltext:springer_html_*`，PDF fallback 成功时会带 `fulltext:springer_pdf_fallback_ok`
- `wiley`
  - provider 自管 HTML + Wiley TDM API PDF waterfall
  - 成功轨迹是 `fulltext:wiley_html_*` / `fulltext:wiley_pdf_api_ok` / `fulltext:wiley_pdf_fallback_ok`
- `science` / `pnas`
  - provider 自管浏览器工作流
  - 继续保持现有 `science` / `pnas` 风格的公开来源与轨迹命名

因此：

- `strategy.allow_html_fallback=false` 不会关闭它们自己的 provider 主路径
- 对 `elsevier` 来说，它不会关闭内部 FlareSolverr HTML fallback
- 对 `springer` 来说，它不会关闭 direct HTML 主路径
- 对 `wiley` 来说，它不会关闭内部 `FlareSolverr HTML -> Wiley TDM API PDF`
- 对 `science` / `pnas` 来说，它不会关闭内部 `FlareSolverr HTML -> seeded-browser PDF`

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

对 `elsevier` browser fallback、`springer` PDF fallback、`wiley` / `science` / `pnas` 而言：

- 当前 `asset_profile=body|all` 会降级成 text-only
- 不阻塞正文成功，但不会承诺完整资产下载

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
  - 粗粒度公开来源，如 `elsevier_xml`、`elsevier_browser`、`springer_html`、`wiley_browser`、`science`、`pnas`、`html_fallback`、`crossref_meta`、`metadata_only`
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

Springer direct HTML / direct HTTP PDF 路线当前没有额外必填 publisher env：

- `provider_status()` 中会稳定表现为本地 `html_route` 已就绪
- 不再需要任何 Springer publisher 凭证

### Elsevier browser fallback / Wiley / Science / PNAS

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
- Elsevier browser fallback / Wiley / Science / PNAS 本地最小请求间隔。

#### `FLARESOLVERR_MAX_REQUESTS_PER_HOUR`

- 必填。
- Elsevier browser fallback / Wiley / Science / PNAS 每小时上限。

#### `FLARESOLVERR_MAX_REQUESTS_PER_DAY`

- 必填。
- Elsevier browser fallback / Wiley / Science / PNAS 每日上限。

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

### `provider_status()`

`provider_status()` 只检查本地条件，不主动探测远端 publisher API 连通性。

当前 provider 语义大致是：

- `elsevier`
  - 同时检查 API key 与 browser fallback runtime，就绪度可能表现为 `ready` / `partial` / `not_configured`。
- `springer`
  - 返回本地 direct HTML route 就绪状态；不依赖 FlareSolverr。
- `wiley` / `science` / `pnas`
  - 统一检查 `runtime_env`、`repo_local_workflow`、`flaresolverr_health`、`rate_limit_window`。
