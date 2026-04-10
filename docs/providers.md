# 出版商能力与配置说明

## 总览

当前项目对三家优先出版商的策略如下：

| 出版商 | 元数据 | 全文 | 附件下载 | Markdown |
| --- | --- | --- | --- | --- |
| Elsevier | 优先官方，失败时回退 Crossref | 官方全文 XML | 支持图片、补充材料，表格原图按官方对象资源可用性处理 | 支持 |
| Springer | 官方 Meta API | 优先 Full Text API，其次 Open Access API | 支持图片与补充材料 | 支持 |
| Wiley | 当前未接官方 metadata endpoint，走 Crossref | 官方 TDM endpoint | 当前按单文件全文处理 | 默认不支持正文 Markdown |

## 通用环境变量

#### `PAPER_FETCH_SKILL_USER_AGENT`

请求时使用的 `User-Agent`。建议配置成稳定的项目标识。

#### `CROSSREF_MAILTO`

拼到 Crossref 请求里的联系邮箱。Crossref 推荐携带。

#### `PAPER_FETCH_DOWNLOAD_DIR`

显式覆盖 CLI / MCP 的默认下载目录。

#### `XDG_DATA_HOME`

未设置 `PAPER_FETCH_DOWNLOAD_DIR` 时，用来推导默认下载目录根路径；CLI 与 MCP 都会落到 `paper-fetch/downloads/` 下。

## 速率限制与缓存

### 进程内 HTTP 缓存

`HttpTransport` 带一个短 TTL 的 LRU GET 缓存（见 `src/paper_fetch/http.py` 的
`DEFAULT_CACHE_TTL_SECONDS` / `DEFAULT_CACHE_CAPACITY`）。`paper-fetch` 的
resolve 阶段和 metadata 阶段会复用同一个 transport，因此同一 DOI 的重复
Crossref / 出版商 GET 会直接命中缓存，不会真正发请求。

POST 和非 GET 方法不走缓存。不同 header 组合会被视为不同 key，因此不同 provider
client 的 Accept / Authorization 不会互相污染。

当前缓存实现还额外做了两层保护：

- 缓存 key 会对敏感 query 参数和鉴权 header 做脱敏，不保留明文 `api_key` / token / `mailto`
- 只有小体积文本响应会进入缓存；PDF 和其他二进制正文不会缓存
- 缓存读写由 `threading.RLock` 保护；如果你自己在外面并发调多个 fetch，主要风险改成 provider 速率限制，而不是进程内 cache race

### 各 provider 的速率限制参考

以下数值以各家官方条款为准，本仓库不自动 throttle，只通过缓存 + "同一篇只抓一次" 的使用约束来避免超限。

| Provider | 建议速率 | 说明 |
| --- | --- | --- |
| Crossref | polite pool ~50 req/s；匿名池更低 | 务必通过 `CROSSREF_MAILTO` 进入 polite pool |
| Elsevier | ~10 req/s，每周 / 每日有机构配额 | 需要 `ELSEVIER_API_KEY` 与机构授权；超限返回 429 |
| Springer (Meta / OA / Full Text) | 每日配额，按 key 计费 | Meta / OA / Full Text 是三个独立 key、独立配额 |
| Wiley TDM | 按 token 每日配额 | 默认只能拿 PDF，一次请求代价高，尽量缓存结果 |

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

- 路由到 `elsevier` 后，元数据会先尝试官方接口。
- 如果官方元数据接口当前 DOI 不可用或返回无记录，则自动回退到 Crossref。
- 全文优先走官方 Elsevier API，目标是获取 `text/xml`。
- 成功拿到 XML 后，会解析其中的 `object` 和 `attachment`：
  - 正文图片
  - appendix 图片
  - supplementary materials
  - 表格相关对象资源（如果官方 XML / objects 中可对上）
- 对 XML 会进一步生成本地 Markdown。

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

- 下载正文图片
- 下载补充材料
- 生成 Markdown

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
- 当前 Springer OA XML 样本里，figure / supplementary / table-wrap 的 Markdown 链路已验证。

## Wiley

### 当前实现

- 官方 metadata endpoint 当前没有在本仓库里实现，因此元数据走 Crossref。
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

## 回退策略

### 元数据回退

- 优先官方元数据接口
- 官方元数据不可用时回退 Crossref

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

## Live Smoke 回归

仓库内提供一个 opt-in 的真实出版商 smoke test 文件：`tests/live/test_live_publishers.py`。

运行方式：

```bash
python -m unittest discover -s tests -q
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
- Springer live 验收当前以 `Meta API + Open Access API` 为准；如果你后续拿到了 `Full Text API` key，可在同一测试入口下继续扩展

## 不应误解的点

- Wiley 当前不是“通用 XML 全文已接通”的状态。
- Springer 的 `Meta API` 和 `Open Access API`、`Full Text API` 是三套不同配置。
- Elsevier 当前已经不是“只下 XML，不管附件”的状态，而是会自动拉图片和补充材料，并且对表格走正式 Markdown 渲染 / fallback 流程。
