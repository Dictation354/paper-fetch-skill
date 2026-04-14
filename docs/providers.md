# 出版商能力与配置说明

## 总览

当前项目对已接入 provider 的策略如下：

| 出版商 | 元数据 | 全文 | 附件下载 | Markdown |
| --- | --- | --- | --- | --- |
| Elsevier | 优先官方，失败时回退 Crossref | 官方全文 XML | 支持分层下载：`none` 不下载，`body` 下载正文 figure + 正文表格原图，`all` 下载全部识别资产 | 支持 |
| Springer | 官方 Meta API | 优先 Full Text API，其次 Open Access API | 支持分层下载：`none` 不下载，`body` 下载正文 figure + 正文表格原图，`all` 下载全部识别资产 | 支持 |
| Wiley | 当前未接官方 metadata endpoint，走 Crossref | 官方 TDM endpoint | 当前按单文件全文处理 | 默认不支持正文 Markdown |
| Science | Crossref metadata + Crossref/domain 路由信号 | repo-local FlareSolverr 抓 HTML，失败时带 cookies 的 Playwright PDF fallback | 当前固定按 text-only 处理，`body|all` 会降级 | 支持 |
| PNAS | Crossref metadata + Crossref/domain 路由信号 | repo-local FlareSolverr 抓 HTML，失败时带 cookies 的 Playwright PDF fallback | 当前固定按 text-only 处理，`body|all` 会降级 | 支持 |

## Provider 路由与判定

当前运行时的 provider 决策已经从“DOI 前缀主导”收口到“Crossref publisher / landing-page domain 主导，DOI 只做最后 fallback”。

统一规则如下：

- 路由信号强弱顺序固定为：`domain > publisher > DOI fallback`
- `resolve_paper().provider_hint` 表示 Crossref/domain-first 的最佳 hint，不再等同于 DOI 前缀猜测
- 纯 DOI 查询在需要时会额外做一次 Crossref DOI metadata lookup，用 `publisher + landing_page_url` 推导更准确的 hint
- `10.1016/...`、`10.1007/...`、`10.1111/...` / `10.1002/...` 这类 DOI 前缀规则仍保留，但只在更强信号缺失时兜底
- `10.1126/...` 和 `10.1073/...` 现在也会分别把 `provider_hint` 推向 `science` / `pnas`，但仍然遵循 `domain > publisher > DOI fallback`

官方 provider probe 现在统一按三态解释：

- `positive`: 官方 probe 明确命中
- `negative`: 官方 probe 返回 `no_result`
- `unknown`: `no_access`、`rate_limited`、`error`、`not_configured`、`not_supported`

这意味着：

- `negative` 只表示“这次 metadata probe 没打中”，是弱负信号，不会在没有更优候选时永久排除该 publisher 的 fulltext 尝试
- `unknown` 不会被解释成“不是这家”，只表示当前无法确认
- Wiley 由于没有对称的官方 metadata probe，当前保持 signal-selected，在 fulltext 阶段确认

### `preferred_providers` 的当前语义

- 继续严格限制最终允许使用的 official/fulltext/html 路径
- 允许内部调用 Crossref 只做 routing signal，即使 allow-list 没有包含 `crossref`
- 当 `preferred_providers=["crossref"]` 时，不会再探测官方 provider，行为保持 Crossref-only
- `preferred_providers` 现在可以显式指定 `science` / `pnas`
- `science` / `pnas` 与 Wiley 一样，不要求先有成功的官方 metadata probe 才允许进入全文抓取

### `source_trail` 里的路由标记

当前会额外记录一组 routing diagnostics，用来区分“路由信号”与“真实结果来源”：

- `route:crossref_signal_ok`
- `route:signal_domain_<provider>`
- `route:signal_publisher_<provider>`
- `route:signal_doi_<provider>`
- `route:probe_<provider>_positive|negative|unknown`
- `route:provider_selected_<provider>`
- `fulltext:science_html_ok`
- `fulltext:science_pdf_fallback_ok`
- `fulltext:pnas_html_ok`
- `fulltext:pnas_pdf_fallback_ok`
- `fallback:science_html_managed_by_provider`
- `fallback:pnas_html_managed_by_provider`
- `download:science_assets_skipped_text_only`
- `download:pnas_assets_skipped_text_only`

现有的 `metadata:<provider>_ok`、`fulltext:<provider>_*` 仍只表示真实来源或真实抓取尝试，不用于表达 route-only 的信号。

## 默认输出与资产层级

CLI、Python API、MCP 现在统一采用下面的默认策略：

- `asset_profile="none"`
- `max_tokens="full_text"`
- `include_refs` 默认不显式收紧
  - `full_text` 模式下默认等价于 `all`
  - 数值 `max_tokens` 模式下默认等价于 `top10`

`asset_profile` 的语义如下：

- `none`
  - 不下载 assets
  - Markdown 保留 figure captions
  - 不输出远程图片 URL
  - 不输出 supplementary 链接
- `body`
  - 下载并渲染正文 figure
  - 下载并渲染正文表格原图
  - 不包含 appendix / supplementary
- `all`
  - 下载并渲染当前 provider 已识别的全部相关资产

额外规则：

- `--no-download` / `download_dir=None` 优先级最高；即使 profile 是 `body` / `all`，也不会落盘
- 没有本地文件时，AI Markdown 会自动降级为 captions-only / 无 supplementary 链接
- HTML fallback 现在也会在允许落盘且 profile 是 `body` / `all` 时，尝试把页面里的 `<figure><img>` 下载到本地 `*_assets/` 目录；对 Nature / Springer 这类带 `Full size image` figure 页面的网站，会优先解析 full-size 图链接；`all` 还会额外抓取站点已识别的 supplementary / extended-data 资产
- `full_text` 模式不再受旧的固定 `8000` 默认值约束

## 配置文件位置

默认主配置文件位置是：

```text
~/.config/paper-fetch/.env
```

如果你在仓库里维护一个开发用 `.env`，它不会被运行时自动加载。开发场景下请显式设置：

```bash
PAPER_FETCH_ENV_FILE=/path/to/.env
```

## 通用环境变量

#### `PAPER_FETCH_SKILL_USER_AGENT`

请求时使用的 `User-Agent`。建议配置成稳定的项目标识。

#### `CROSSREF_MAILTO`

拼到 Crossref 请求里的联系邮箱。Crossref 推荐携带。

#### `PAPER_FETCH_DOWNLOAD_DIR`

显式覆盖 CLI / MCP 的默认下载目录。

补充说明：

- MCP 默认共享缓存 resources 只覆盖默认共享下载目录
- 如果你在 MCP `fetch_paper(..., download_dir=...)` 里显式传了目录，就会写入那个隔离目录，并由 `list_cached(download_dir)` / `get_cached(doi, download_dir)` 读取

#### `XDG_DATA_HOME`

未设置 `PAPER_FETCH_DOWNLOAD_DIR` 时，用来推导默认下载目录根路径；CLI 与 MCP 都会落到 `paper-fetch/downloads/` 下。

## Science / PNAS 额外环境变量

#### `FLARESOLVERR_URL`

Science / PNAS 本地 FlareSolverr 服务地址。默认值：

```text
http://127.0.0.1:8191/v1
```

#### `FLARESOLVERR_ENV_FILE`

Science / PNAS 必填。必须显式指向当前仓库 `vendor/flaresolverr/` 下的一份 preset，例如：

```text
vendor/flaresolverr/.env.flaresolverr-source-headless
```

不会自动猜 preset。

#### `FLARESOLVERR_SOURCE_DIR`

可选。覆盖 repo-local FlareSolverr workflow 根目录。默认值是当前仓库里的：

```text
vendor/flaresolverr/
```

#### `FLARESOLVERR_MIN_INTERVAL_SECONDS`

Science / PNAS 必填。本地强制最小请求间隔。

#### `FLARESOLVERR_MAX_REQUESTS_PER_HOUR`

Science / PNAS 必填。本地强制每小时最大请求数。

#### `FLARESOLVERR_MAX_REQUESTS_PER_DAY`

Science / PNAS 必填。本地强制每天最大请求数。

## 速率限制与缓存

### 进程内 HTTP 缓存

`HttpTransport` 带一个短 TTL 的 LRU GET 缓存（见 `src/paper_fetch/http.py` 的
`DEFAULT_CACHE_TTL_SECONDS` / `DEFAULT_CACHE_CAPACITY`）。`paper-fetch` 的
resolve 阶段和 metadata 阶段会复用同一个 transport，因此同一 DOI 的重复
Crossref / 出版商 GET 会直接命中缓存，不会真正发请求。

当前底层传输已经切到 `urllib3.PoolManager`。同一进程里的重复请求会按 host 复用
HTTP/TLS 连接，官方 provider 那类 “metadata -> fulltext -> assets” 串行链路不再
为每一步重新建连。

POST 和非 GET 方法不走缓存。不同 header 组合会被视为不同 key，因此不同 provider
client 的 Accept / Authorization 不会互相污染。

当前缓存实现还额外做了两层保护：

- 缓存 key 会对敏感 query 参数和鉴权 header 做脱敏，不保留明文 `api_key` / token / `mailto`
- 只有小体积文本响应会进入缓存；PDF 和其他二进制正文不会缓存
- 开启 `paper_fetch.*` 的 `DEBUG` 日志时，会额外看到 HTTP / official provider / HTML fallback 的 url、状态、耗时和重试事件，便于 live 排障
- 缓存读写由 `threading.RLock` 保护；如果你自己在外面并发调多个 fetch，主要风险改成 provider 速率限制，而不是进程内 cache race

### HTTP 护栏与重试

`HttpTransport` 现在还带了两层运行时护栏：

- 默认 `max_response_bytes=32 MiB`；超过上限会直接抛 `RequestFailure`，而不是把超大正文 / supplement 一次性吃进内存
- 对 `HTTP 5xx` 和 timeout-class 网络错误支持有限指数退避重试；当前官方 provider 请求和 HTML fallback 请求都会启用
- transport 内部保留一个私有请求 seam 供测试 stub；对外公开的 `HttpTransport.request()` 签名与返回结构不变

重试策略保持比较保守：

- `429` 仍只按 `Retry-After` 处理，不和瞬时错误重试混用
- 瞬时错误默认只做两次额外尝试，退避序列固定为 `0.5s -> 1.0s`
- 非 timeout 的普通 `URLError` 仍会立即失败，避免把权限、DNS 或配置问题误当成短暂抖动

### 各 provider 的速率限制参考

以下数值以各家官方条款为准。除 `science` / `pnas` 的本地账本限速外，本仓库其余 provider 不自动 throttle，主要通过缓存 + "同一篇只抓一次" 的使用约束来避免超限。

| Provider | 建议速率 | 说明 |
| --- | --- | --- |
| Crossref | polite pool ~50 req/s；匿名池更低 | 务必通过 `CROSSREF_MAILTO` 进入 polite pool |
| Elsevier | ~10 req/s，每周 / 每日有机构配额 | 需要 `ELSEVIER_API_KEY` 与机构授权；超限返回 429 |
| Springer (Meta / OA / Full Text) | 每日配额，按 key 计费 | Meta / OA / Full Text 是三个独立 key、独立配额 |
| Wiley TDM | 按 token 每日配额 | 默认只能拿 PDF，一次请求代价高，尽量缓存结果 |
| Science / PNAS | 不依赖官方 API 配额；由本地账本强制限速 | 必须显式配置 `FLARESOLVERR_MIN_INTERVAL_SECONDS`、`FLARESOLVERR_MAX_REQUESTS_PER_HOUR`、`FLARESOLVERR_MAX_REQUESTS_PER_DAY`，未配置直接拒绝运行 |

Science / PNAS 和其他 provider 不同，这里会额外把请求事件记到用户数据目录下的本地账本，只对这两个通道生效。命中限制时返回 `rate_limited`，而不是静默继续请求。

### 并行调用提示

- 不要在同一会话里对同一 DOI / URL 并发触发多次抓取；缓存会去重，但 agent
  侧的 roundtrip 成本仍在。
- 需要处理多篇时按顺序串行，或至少把并发度限制在 2–3，避免被 Elsevier /
  Springer 触发 429。
- 首次 `paper-fetch` 返回后，直接复用它吐出的 Markdown / JSON，不要重复跑
  同一个 query。
- 如果第一次返回 `ambiguous`，先把 DOI 定下来再重试，不要同时对多个候选发起抓取。

## Elsevier

### 当前实现

- 路由到 Elsevier 不再只依赖 `10.1016/`；Crossref 的 `publisher=Elsevier BV`、`Elsevier Ltd`、`Elsevier Masson SAS` 以及 `linkinghub.elsevier.com` / `sciencedirect.com` 这类 domain 也会触发 Elsevier 优先路由。
- 路由到 `elsevier` 后，元数据会先尝试官方接口。
- 如果官方元数据接口当前 DOI 不可用或返回无记录，则自动回退到 Crossref。
- 全文优先走官方 Elsevier API，目标是获取 `text/xml`。
- 成功拿到 XML 后，会解析其中的 `object` 和 `attachment`：
  - 正文图片
  - appendix 图片
  - supplementary materials
  - 表格相关对象资源（如果官方 XML / objects 中可对上）
- 下载行为由 `asset_profile` 决定：
  - `none`: 不下载
  - `body`: 只下载正文图片和正文表格原图
  - `all`: 下载全部已识别资产
- 当 CLI / MCP 主链路允许下载且 profile 允许时，这些关联 assets 会和全文一起写到本地 `*_assets/` 目录。
- 对 XML 会进一步生成本地 Markdown。
- AI Markdown 会和 profile 保持一致：
  - `none`: 保留 figure captions，不输出图片和 supplementary 链接
  - `body`: 输出正文 figure + 正文表格原图
  - `all`: 输出全部本地 figure / table-image / supplementary 链接

当前 Elsevier Markdown 里的表格策略已经和 Springer 收敛到同一模式：

- 结构化 `ce:table` 会转成 Markdown 表格
- 正文中引用过的表格会尽量就近插入
- 复杂 CALS 表格不会静默丢失：
  - 正文附近仍保留表题、caption、legend / table-footnote
  - 若官方对象资源存在表格原图，则一并保留原图
  - 降级说明统一放到文末 `Conversion Notes`
- 未在正文消费到的 body table 会落到 `Additional Tables`

### 环境变量

#### `ELSEVIER_API_KEY`

Elsevier API key。必须配置，否则官方 Elsevier 链路不会工作。

#### `ELSEVIER_INSTTOKEN`

机构级 insttoken。适用于需要机构授权的场景。

#### `ELSEVIER_AUTHTOKEN`

可选 bearer token。如果你的 Elsevier 账户流程提供这个字段，可以填这里。

#### `ELSEVIER_CLICKTHROUGH_TOKEN`

用于 Elsevier click-through / TDM 授权场景的 token。

### 现状说明

- Elsevier 全文 XML 链路当前已经验证可用。
- 附件自动下载也已验证可用。
- Elsevier 表格 Markdown 链路当前已支持结构化表格、复杂表格 fallback、`Additional Tables`、`Conversion Notes`。
- 部分 DOI 的官方 metadata endpoint 不稳定，因此实现里保留了 Crossref 元数据回退。

## Springer

### 当前实现

Springer 现在是“分离配置”的版本：

1. 元数据使用 `Springer Meta API`
2. 全文优先尝试你单独配置的 `Springer Full Text API`
3. 如果没有 Full Text API 配置，或该接口失败，则退到 `Springer Open Access API`

拿到 XML 后会：

- 按 `asset_profile` 分层下载相关 assets
- 生成 Markdown
- 当 CLI / MCP 主链路允许下载且 profile 允许时，这些关联 assets 会和全文一起写到本地 `*_assets/` 目录。
- AI Markdown 会和 profile 保持一致：
  - `none`: 保留 figure captions，不输出图片和 supplementary 链接
  - `body`: 输出正文 figure + 正文表格原图
  - `all`: 输出全部本地 figure / table-image / supplementary 链接

当前 Springer article XML 转换层已经覆盖：

- figure 正文就近插入
- supplementary materials 全局收集
- `table-wrap` 的结构化表格 / 图像表格 / 显式 fallback
- 文末 `Additional Tables` 与 `Conversion Notes`

### 环境变量

#### `SPRINGER_META_API_KEY`

填写 Springer `Meta API` 的 key，只用于元数据检索。

#### `SPRINGER_OPENACCESS_API_KEY`

填写 Springer `Open Access API` 的 key，只用于开放获取全文。

#### `SPRINGER_FULLTEXT_API_KEY`

填写你单独申请的 `Full Text API` key。这个 key 不等同于 Meta API 或 Open Access API。

#### `SPRINGER_FULLTEXT_URL_TEMPLATE`

Full Text API 的 URL 模板。支持以下占位符：

- `{doi}`: URL 编码后的 DOI
- `{raw_doi}`: 原始 DOI
- `{api_key}`: URL 编码后的 API key

#### `SPRINGER_FULLTEXT_AUTH_HEADER`

如果你的 Full Text API 需要自定义 header 传 key，可以在这里配置 header 名。

#### `SPRINGER_FULLTEXT_ACCEPT`

Full Text API 请求时的 `Accept` 值，默认是 `application/xml`。

### 现状说明

- `Meta API`、`Open Access API`、`Full Text API` 在实现里已经拆分。
- 这三者被当成不同权限层级处理，不再混用。
- 如果后续 Full Text API 审批通过，只需要补全对应环境变量即可。
- 当前 Springer OA XML 样本里，`none|body|all` 三档下的 figure / supplementary / table-wrap Markdown 链路已验证。
- 当 Springer / Nature / BMC 站点退到 HTML fallback 时，`body|all` 也会尝试把 HTML figure 图片下载到本地，并在 Markdown 中按本地路径内联；如果正文页提供 `Full size image` 按钮，会优先抓 full-size 图而不是正文缩略图。`all` 还会把已识别的 supplementary / extended-data figure / PDF 一起落盘并渲染到 `Supplementary Materials`。

## Wiley

### 当前实现

- 官方 metadata endpoint 当前没有在本仓库里实现，因此 metadata 仍走 Crossref；但 provider 路由不再只靠 DOI 前缀，而是优先参考 Crossref publisher / landing page signal。
- 全文使用 Wiley TDM endpoint。
- 当前实现把 Wiley 返回内容按“单个全文文件”处理。
- 根据当前已验证结果，默认获取的是 PDF。
- `paper-fetch` 命中 Wiley PDF 时会先尝试用 PyMuPDF 从字节流提取正文。
- PDF 正文提取失败时，如果 HTML fallback 仍开启，会继续尝试 HTML fallback。
- 是否把 Wiley PDF 落盘由 `--no-download` 控制，和 HTML fallback 不再耦合。

### 环境变量

#### `WILEY_TDM_URL_TEMPLATE`

Wiley TDM endpoint 模板。必须包含 DOI 占位符。

当前仓库中采用的默认示例是：

```text
https://api.wiley.com/onlinelibrary/tdm/v1/articles/{doi}
```

如果 Wiley 给你的接口说明不同，以 Wiley 官方说明为准。

#### `WILEY_TDM_TOKEN`

Wiley TDM token。

#### `WILEY_TDM_AUTH_HEADER`

发送 token 使用的 header 名，默认是：

```text
Wiley-TDM-Client-Token
```

### 现状说明

- 当前实现明确按“默认 PDF”处理 Wiley。
- 未显式指定 `--output-dir` 且未开启 `--no-download` 时，`paper-fetch` 会把 Wiley PDF 默认保存到 `PAPER_FETCH_DOWNLOAD_DIR`，否则走 `XDG_DATA_HOME/paper-fetch/downloads`（未设置时回落到 `~/.local/share/paper-fetch/downloads`）。
- 即使关闭落盘，运行时仍会优先尝试从 PDF 提取可用正文。
- 其他格式，例如 XML，不假定可用。
- 如果 Wiley 后续单独为你的账户开通 XML 或其他格式，并给出正式 endpoint / header / accept 说明，再扩展当前实现。

## Science / PNAS

### 当前实现

- `science` / `pnas` 现在是公开 provider 名字：
  - `resolve_paper().provider_hint` 可直接返回它们
  - `preferred_providers` 可显式指定它们
  - 成功结果里的 `source` 也直接写 `science` / `pnas`
- metadata 仍只来自 Crossref；当前没有接 AAAS / PNAS 官方 metadata endpoint。
- 路由语义和 Wiley 类似：Crossref 负责 metadata 与 routing signal，但不要求 metadata probe 成功后才允许进入全文抓取。
- provider 自己负责完整链路：
  - 先用 repo-local FlareSolverr 抓 landing/full HTML
  - 如果 HTML 被判定为摘要页、Cloudflare / 登录页、正文过短，或只有 `Abstract` / `References`，就转到 PDF fallback
  - PDF fallback 会把 FlareSolverr 解出的 cookies 和 user-agent 注入 Playwright Chromium，再访问 PDF candidates
  - PDF 转 markdown 用 `pymupdf4llm`
- 通用 `allow_html_fallback` 只控制“官方 provider 失败后的普通 landing-page HTML fallback”；它不会关闭 `science` / `pnas` provider 自己的 HTML 主路径。
- 对这两个 provider，service 会显式跳过通用 `html_generic` fallback，避免 FlareSolverr 失败后又走一遍无 cookies 的普通 HTML 路线。
- `asset_profile="body"` / `"all"` 当前不会阻塞正文成功，但会降级为 text-only，并在 `warnings` / `source_trail` 里附带说明。

### 运行边界

- 这两个通道只保证在当前仓库 checkout 中运行。
- 若你把项目单独安装成 wheel / sdist 后脱离仓库运行，命中 `science` / `pnas` 时会明确报缺少 repo-local `vendor/flaresolverr` 工作流，而不是静默退回普通 HTML fallback。
- 启动方式、preset 选择和排障见 [flaresolverr.md](flaresolverr.md)。
- 使用 `science` / `pnas` 的法律、条款、robots 或机构授权风险由操作者自己承担。

## 回退策略

### 元数据回退

- 优先官方元数据接口
- Crossref 既可以作为公开 metadata 来源，也可以只作为内部 routing signal
- 官方元数据 probe 返回 `no_result` 时，只记为弱负信号；如果没有更优 provider，仍允许继续尝试该 provider 的 fulltext
- 官方元数据不可用或未实现时，再回退到 Crossref / resolution-only metadata

### 全文回退

- 优先官方出版商全文接口
- 如果失败，并且 Crossref 暴露了可下载全文链接，则尝试从 `fulltext_links` 回退
- HTML fallback 对正文质量使用自适应阈值：常规正文仍要求约 `800` 字符，但 CJK-heavy 页面或带 DOI 的短 commentary / editorial 可在约 `300` 字符级别通过

## 当前更适合抓取的内容类型

### 最稳

- Elsevier XML
- Springer XML

### 可用但能力较窄

- Wiley PDF（可尝试正文提取，但不做 OCR）
- Science HTML-first 链路
- PNAS HTML-first + PDF fallback 链路

## Live Smoke 回归

仓库内提供三个 opt-in 的 live smoke 入口：

- `tests/live/test_live_publishers.py`: 直接打 service 层
- `tests/live/test_live_mcp.py`: 通过真实 stdio MCP server + MCP client 打 agent surface
- `tests/live/test_live_science_pnas.py`: repo-local FlareSolverr + Playwright 的 Science / PNAS smoke

运行方式：

```bash
PYTHONPATH=src python -m unittest discover -s tests -q
PAPER_FETCH_RUN_LIVE=1 PYTHONPATH=src python -m unittest discover -s tests/live -q
```

说明：

- 默认离线测试不会真的访问外网；live 文件会自动跳过
- 只有设置 `PAPER_FETCH_RUN_LIVE=1` 且本地环境变量齐全时，才会发起真实 publisher 请求
- 按 `2026-04-10` 的基线样本，当前 smoke 覆盖：
  - Elsevier DOI `10.1016/j.rse.2025.114648`
  - Springer DOI `10.1186/1471-2105-11-421`
  - Wiley DOI `10.1002/ece3.9361`
  - Elsevier URL `https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525`
  - 短正文 HTML fallback `https://www.nature.com/articles/sj.bdj.2017.900`
- `test_live_mcp.py` 当前重点验收：
  - Elsevier 官方全文 DOI 的 MCP `fetch_paper`
  - Nature 短正文 HTML fallback 的 MCP `fetch_paper`
  - client 侧 progress notifications 与 structured log notifications
- `test_live_science_pnas.py` 额外要求：
  - 本地 FlareSolverr 已启动并能通过 `sessions.list`
  - `FLARESOLVERR_ENV_FILE`
  - `FLARESOLVERR_MIN_INTERVAL_SECONDS`
  - `FLARESOLVERR_MAX_REQUESTS_PER_HOUR`
  - `FLARESOLVERR_MAX_REQUESTS_PER_DAY`
  - 当前覆盖 1 个 Science HTML DOI 和 1 个 PNAS PDF fallback DOI
- Springer live 验收当前以 `Meta API + Open Access API` 为准；如果你后续拿到了 `Full Text API` key，可在同一测试入口下继续扩展

## 不应误解的点

- Wiley 当前不是“通用 XML 全文已接通”的状态。
- Springer 的 `Meta API` 和 `Open Access API`、`Full Text API` 是三套不同配置。
- Elsevier 当前已经不是“只下 XML，不管附件”的状态，而是会自动拉图片和补充材料，并且对表格走正式 Markdown 渲染 / fallback 流程。
