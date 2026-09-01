# 提取与渲染规则

修订日期：2026-08-07

这份文档解决：

- 当前主干必须维持的提取 / 组装 / 渲染行为约束有哪些
- 每条规则约束了什么用户可见结果
- 哪些真实 HTML / XML 样本和哪些测试在锁定这些规则

这份文档不解决：

- provider 路由、运行时限速、环境变量和部署细节
- 单次事故的时间线、排障过程或 root-cause 复盘全文
- 某篇 DOI 的特殊例外规则

provider、routing 和 waterfall 的 canonical 事实来源是 [`providers.md`](providers.md) 与 `paper_fetch.provider_catalog.PROVIDER_CATALOG`；本文只维护用户可见的提取 / 渲染规则。`references/` 下的文件只保留 API 约束和补充说明，不作为 provider 路由事实来源。系统分层与业务主线见 [`architecture/overview.md`](architecture/overview.md)，受控阶段到 canonical module 的映射见 [`overview.md` 的 Extraction 阶段映射](architecture/overview.md#extraction-stage-module-map)。

## 规则怎么读

- 这里说的“规则”，指当前主干必须维持的行为约束，不是某篇 DOI 的特判。
- DOI 可以出现在文档里，但只能作为“证据样本”和“测试样本”，不能变成规则本身。
- 每条规则都尽量先用通俗语言描述“约束了什么”，再补充它落在哪个阶段、由哪些样本和测试锁住。
- 新增或修改规则以 HTML/XML/PDF 证据和可复现测试为准；个别渲染规则只有最小复现测试，没有额外 DOI 样本。

### 受控阶段清单

规则里的“对应阶段”只能使用或映射到这些阶段名，避免同一层行为出现多套说法：

- `metadata`：标题、作者、摘要、provider-owned 信号和 redirect stub lookup metadata。
- `provider-html-or-xml-extraction`：publisher HTML/XML 到中间结构的提取。
- `html-cleanup`：站点 chrome、UI 噪声、caption fallback 和正文清洗。
- `availability-quality`：fulltext / abstract-only 判定和正文充分性度量。
- `section-classification`：section kind、frontmatter、back matter、availability 与 section hints。
- `article-assembly`：中间结构合并成 `ArticleModel`。
- `asset-discovery`：figure、table、formula、supplementary 等资产候选识别。
- `asset-download`：资产候选下载和 provider-owned 下载链路。
- `asset-validation`：真实图片校验、尺寸阈值、preview acceptance 和失败诊断。
- `asset-link-rewrite`：远程 / 绝对资产链接改写为本地 Markdown 可用链接。
- `table-rendering`：HTML/XML 表格展平、降级和语义损失标记。
- `formula-rendering`：MathML / LaTeX / 公式图片 fallback 渲染。
- `markdown-normalization`：Markdown 块边界、空白、行内语义和去重。
- `references-rendering`：参考文献抽取与渲染。
- `final-rendering`：最终 Markdown / MCP payload 输出。
- `artifact-storage`：原始 payload、publisher HTML 和下载资产落盘。这里只允许保留重定向，具体规则归 [`providers.md`](providers.md)。

### 阶段流水图

```text
metadata
  -> provider-html-or-xml-extraction
  -> html-cleanup
  -> availability-quality
  -> section-classification
  -> article-assembly
  -> asset-discovery
  -> asset-download
  -> asset-validation
  -> asset-link-rewrite
  -> table-rendering / formula-rendering / references-rendering
  -> markdown-normalization
  -> final-rendering
```

`artifact-storage` 是旁路诊断与落盘阶段，不改变规则本身的用户可见提取 / 渲染语义。

### 维护边界

规则只描述用户可见的提取与渲染语义。实现 owner 由代码和 provider-local 测试负责，fixture 身份与预期由 `tests/fixtures/golden_criteria/manifest.json` 负责；本文不维护测试文件清单、兼容锚点治理、unstable DOI 表或 fixture 反向索引。

## Generic

- 这里的 `Generic` 指跨 provider 共享的提取 / 渲染规则。
- 它只表示 shared extraction logic，不表示可被路由命中的第六条 provider 或 public source。
- Front matter 的 publication watermark 只匹配短 masthead 标签：必须是短文本、无句子标点、token 数受限，并且呈标题式或全大写；`science` / `pnas` / `ams` / `bams` / `acs` / `iopscience` 等 provider 词面只作为 provider-scoped keyword 参与判断，长正文句子里出现这些词不能被当作 front matter。
- 反爬 / 访问阻断文本中的通用 token 统一维护在 `COMMON_ACCESS_BLOCK_TOKENS`，provider 规则只追加自身增量，避免把通用 challenge 语义复制到单个 provider。

资产渲染与诊断 contract 由 [正文已内联 figure 时避免重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)、[Markdown 图片 alt 只保留短标签](#rule-short-markdown-image-alt-labels)、[已下载的正文图片和公式图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links) 和 [下载资产必须保留诊断字段](#rule-asset-download-diagnostic-fields) 共同维护；[图片下载必须验证真实图片内容](#rule-image-download-validates-real-images) 独立约束 payload 真实性和 preview acceptance。

<a id="rule-html-byte-decoding-and-cleanup-bounds"></a>
### HTML bytes 解码和清洗 fallback 边界

- 这条规则约束的是：HTML/JSON bytes 转文本必须优先保留真实字符集，通用 HTML cleanup 在无内容根时不能对整页逐节点跑噪声分类，raw trafilatura fallback 不能无上限处理大型原文 HTML。
- 如果违反，用户会看到：非 UTF-8 页面出现乱码；无 `article/main/[role=main]` 的大页面清洗异常变慢；cleaned HTML 已经很小但 raw fallback 又把数 MB 原文交给 trafilatura，导致抓取延迟放大。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`html-cleanup`、`markdown-normalization`。
- Owner：`paper_fetch.extraction.html._runtime` 与 `paper_fetch.providers.base.ProviderClient`。
- 代表性 HTML / XML：
  - 当前无稳定 DOI 样本，直接见对应测试；后续出现真实 charset 或 no-root 性能回归时补入 replay fixture。
- 边界说明：
  - 解码顺序固定为 UTF-8 BOM / UTF-8、HTTP charset、HTML meta charset、`charset-normalizer`、UTF-8 replacement fallback。
  - no-root cheap cleanup 仍会删除 drop tags、cleanup selectors、extraction cleanup selectors 和 ORCID links；它只跳过逐节点 `should_drop_html_element()` 分类。
  - raw trafilatura fallback 默认上限是 `RAW_TRAFILATURA_FALLBACK_CHAR_LIMIT = 1_000_000` 字符；超过上限时跳过 raw fallback，但 cleaned HTML 的 parser fallback 仍继续执行。

<a id="rule-keep-semantic-parent-heading"></a>
### 保留语义父节标题

- 这条规则约束的是：只要 HTML 提取链已经识别出一个父节标题，后续的文章组装和最终 markdown 渲染就不能把这个父节标题吃掉，即使正文内容主要落在子节里。
- 如果违反，用户会看到：正文里直接从子节开始，像是 `Experimental design` 这样的内容突然失去上级章节，文档结构会断层。
- 它对应的阶段是：`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.models.ArticleModel` 与 provider section assembly。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/original.html`](../tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/original.html)
  - 这个样本能证明 `MATERIALS AND METHODS` 是语义父节，而 `Experimental design` 是其子节内容。
- 边界说明：
  - 这条规则不是要求所有论文都必须出现 `MATERIALS AND METHODS` 这个固定字面值。
  - 它约束的是“父节语义不能在组装或渲染阶段丢失”，不是要求不同 publisher 的标题体系完全一致。
  - 当前直接 DOI 证据样本来自 Science；Wiley 与 models 测试证明同一父节保留行为不是 Science-specific 规则，后续不为凑数强行新增 fixture。

<a id="rule-no-trailing-figures-appendix"></a>
### 正文已内联 figure 时避免重复追加尾部 Figures 附录

- 这条规则约束的是：当 figure 已经以正文内联形式进入最终输出时，`asset_profile='body'` / `asset_profile='all'` 的正文图渲染不能再在文末重复拼一个尾部 `## Figures` 附录；arXiv official HTML 会在正文 figure caption 附近先插入原始图片 Markdown 链接，下载后再改写到 `body_assets/...`。如果图片无法锚定正文但仍可下载，尾部可以作为 fallback 保留图片，但不能重复整段 caption。
- 如果违反，用户会看到：正文已经出现过的 figure 在文末又来一遍，像是“正文 + 附录”重复渲染，结构和阅读顺序都会变差。
- 它对应的阶段是：`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.models.ArticleModel` render state。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1029_2004gb002273/original.html`](../tests/fixtures/golden_criteria/10.1029_2004gb002273/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_nature13376/original.html`](../tests/fixtures/golden_criteria/10.1038_nature13376/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_s41561-022-00983-6/original.html`](../tests/fixtures/golden_criteria/10.1038_s41561-022-00983-6/original.html)
  - [`../tests/fixtures/golden_criteria/10.1126_sciadv.aax6869/original.html`](../tests/fixtures/golden_criteria/10.1126_sciadv.aax6869/original.html)
  - [`../tests/fixtures/golden_criteria/10.1126_science.abb3021/original.html`](../tests/fixtures/golden_criteria/10.1126_science.abb3021/original.html)
  - [`../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06667v1/original.html`](../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06667v1/original.html)
  - 这些样本分别覆盖 Wiley root-cause 回放、早期 Nature HTML、新 Nature HTML、Science 回归中“正文已有相对本地图片链接但资产模型里仍是绝对路径”的场景，以及 arXiv official HTML 中正文 figure 图片应原位内联、尾部 `Figures` 只作为未消费图片 fallback 的场景。
- 边界说明：
  - 这条规则只约束 `asset_profile='body'` / `asset_profile='all'` 的正文图渲染结果。
  - 它不是说系统永远不能输出 figure 附录，而是说正文 figure 已经内联时，不能再重复追加一个用户可见的尾部 Figures 块。
  - 如果正文里还有未锚定的 body figure，或者资产本来就不属于正文，这些内容仍然可以留在兜底附录里。
  - 去重扫描必须覆盖最终会渲染的 lead、abstract、body 和 retained section；不能只看普通 body section，否则摘要/Significance 中已经内联的本地图仍会在尾部重复追加。
  - 去重比较必须能识别远程 URL、绝对路径、相对 `body_assets/...` 路径和 basename 后缀的等价关系；不能只做字符串全等比较。
  - 本规则定义 render-state / caption 去重；本地链接改写和下载诊断字段分别见 [已下载的正文图片和公式图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links) 与 [下载资产必须保留诊断字段](#rule-asset-download-diagnostic-fields)。

<a id="rule-supplementary-discovery-explicit-scope"></a>
### Supplementary discovery 必须来自明确附件 scope

- 这条规则约束的是：supplementary / supporting / multimedia 文件发现必须先由 provider 切出明确附件 scope，再在该 scope 内解析附件链接；不能在整篇正文里全局扫描 `data`、`code`、`.csv`、`.zip`、`.mp4`、`.pdf` 这类词面或后缀并直接归为 supplementary。
- 如果违反，用户会看到：正文 Data Availability、Code Availability、普通数据仓库、正文 figure 文件或 reference 链接被误下载到 `supplementary`，而真正的 publisher 附件范围反而和正文混在一起。
- 它对应的阶段是：`asset-discovery`、`provider-html-or-xml-extraction`。
- Owner：`paper_fetch.extraction.html.assets` 与 provider-specific asset scope helpers。
- 代表性 HTML / metadata：
  - [`../tests/fixtures/golden_criteria/10.1109_RITA.2026.3668995/landing.html`](../tests/fixtures/golden_criteria/10.1109_RITA.2026.3668995/landing.html)
  - [`../tests/fixtures/golden_criteria/10.1109_RITA.2026.3668995/multimedia.json`](../tests/fixtures/golden_criteria/10.1109_RITA.2026.3668995/multimedia.json)
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.16414/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16414/original.html)
  - [`../tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/original.html`](../tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_s41561-022-00912-7/original.html`](../tests/fixtures/golden_criteria/10.1038_s41561-022-00912-7/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_s41558-022-01584-2/original.html`](../tests/fixtures/golden_criteria/10.1038_s41558-022-01584-2/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_s43247-024-01270-5/original.html`](../tests/fixtures/golden_criteria/10.1038_s43247-024-01270-5/original.html)
  - [`../tests/fixtures/golden_criteria/10.1088_1748-9326_ab7d02/original.html`](../tests/fixtures/golden_criteria/10.1088_1748-9326_ab7d02/original.html)
  - 这些样本分别覆盖 IEEE landing `sections.multimedia` + multimedia payload、Wiley `Supporting Information` 区块、Science supplementary section 与正文 Data Availability 普通链接的边界、Springer / Nature `Source data`、Extended Data 和 peer-review 文件排除，以及 IOP 正文页 `/data` 索引与 figure 下载控件/二维码之间的边界。IOP `SM0001` 索引页形态由 provider 单测中的精简真实 DOM 固定。
- Provider 差异表：

| Provider | 明确附件 scope | 关键排除 |
| --- | --- | --- |
| Springer / Nature | `Supplementary information`、`Supplementary material(s)`、`Supporting information`、`Electronic supplementary material`、`Extended data`、`Extended data figures and tables`；`Source data` 独立落到 `source_data/`。 | 正文 / chrome 里的普通 PDF/CSV/ZIP、`Peer Review File` / `Peer reviewer reports` 不归 supplementary。 |
| Wiley | `Supporting Information` accordion/content 内的 `downloadSupplement` 或 `sup-*` supporting file 链接。 | 正文 `<figure>` 的 `/cms/asset/...fig-*` 只归 body figure，不并行归 supplementary。 |
| Science / PNAS | Atypon back matter 的真实 `Supplementary Material(s)` / `Supporting Information` section 子树和 publisher `/doi/suppl/.../suppl_file/...` 附件。 | 正文 Data Availability 链接、页内 `#supplementary-materials` 导航和 supplementary references 中的外部 PDF 不归 supplementary。 |
| ACS | 当前 Silverchair `.widget-ArticleDataSupplements` 中的稳定 publisher `/article-supplement/` 附件。 | 嵌入 Figshare viewer/downloader、正文 figure/table asset、citation/download chrome 和机构 OpenURL 链接不归 canonical supplementary。 |
| IEEE | 明确 Supplementary / Supporting Material / Multimedia section，IEEE 附件语义容器，或 landing metadata `sections.multimedia=true` 加 `/rest/document/{article_number}/multimedia` payload。 | 正文 `data` / `dataset` / `code` / `media` / repository 链接和文件后缀不能单独触发 supplementary。 |
| Copernicus | NLM/JATS XML 中的 `supplementary-material`、`inline-supplementary-material` 和明确 `xlink:href` 附件节点。 | 正文 Data/Code Availability 普通仓库链接不凭文本或后缀升级为 supplementary。 |
| IOP | 正文页的 `#supplDataLink` 或同 DOI `/article/{doi}/data[N]` 入口只是索引；复用文章浏览器 cookie/Referer 打开索引页后，只接受 `#supplementarydata` 内 `id=SM数字` 的真实附件。 | `/data` HTML 本身、正文 figure 的 Standard/High-resolution 控件、页脚 WeChat QR 和未编号链接都不归 supplementary；索引 challenge、DOI 不匹配或空附件必须记录 asset failure。 |

- 边界说明：
  - 这条规则不定义每个 publisher 的完整 DOM selector、REST endpoint 或 URL allowlist；这些细节由 provider-specific helper 维护，本文只保留用户可见 contract。
  - 它也不限制附件文件类型。只要来源 scope 明确，supplementary 可以是 PDF、Office 文档、压缩包、数据表、图片或视频。
  - IOP 附件下载仍即时使用 publisher 返回的 AWS 签名 URL，但最终资产/失败诊断会复用 HTTP URL 脱敏规则隐藏 `X-Amz-*`、`Signature` 和 `AWSAccessKeyId` 值。

<a id="rule-filter-publisher-ui-noise"></a>
### 出版社站点 UI 噪声不能泄漏进最终 markdown

- 这条规则约束的是：出版社页面里的操作按钮、图窗入口、站点工具栏和明显的站点动作词，不能随着 HTML 提取或后处理一起混进最终 markdown；`Permissions`、`Rights and permissions`、`Open Access` 这类站点许可 / 操作节只能按 heading 或 section 结构过滤，不能扩成普通正文词面 denylist。
- 如果违反，用户会看到：正文里夹杂 `Open in figure viewer`、`PowerPoint`、`Sign up for PNAS alerts`、`Request permissions`、Creative Commons 许可长文这类站点操作文案，看起来像把网页操作层一起抓进来了。
- 它对应的阶段是：`html-cleanup`、`markdown-normalization`、`asset-validation`、`final-rendering`。
- Owner：`paper_fetch.extraction.html.cleanup_policy.CleanupPolicy`、`paper_fetch.extraction.html.availability_policy.AvailabilityPolicy`、provider cleanup policy 与 provider structural hooks。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1029_2004gb002273/original.html`](../tests/fixtures/golden_criteria/10.1029_2004gb002273/original.html)
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html)
  - 这两个样本分别覆盖 figure viewer / PowerPoint 噪声和 PNAS 站点级 collateral 噪声。
- 边界说明：
  - 这条规则过滤的是站点 UI 和操作噪声，不是过滤所有出现在图题或正文里的英文短语。
  - Markdown promo contains token 只删除短的孤立 UI 行，例如独立 `Learn more`、短标签后的标点或短 `To learn more, ...` 提示；正文自然句里出现 `learn more` 不能被删除。
  - 整句站点文案和 chrome selector / heading / attr 常量是易受站点改版影响的回归点；更新这些规则时必须回看对应 provider fixture，并用用户可见提取结果验证，而不是锁定源码 marker。
  - provider 专用 DOM hook 可以保留在 provider 文件中处理必须晚于结构归一化的逻辑，例如先读取 AMS gallery / full-size 图片链接再删除 gallery chrome；普通 chrome 数据本身仍应来自 provider cleanup policy。
  - `download` 不是全局噪声词；`Source Data Fig. 1 (Download xlsx)`、supplementary file、figure/table asset download 这类有效材料入口必须保留。
  - `preview sentence` 和 AI alt disclaimer 也会被过滤，但它们属于 [Springer 访问提示规则](#rule-springer-access-hint-disclaimer)，不混在本条里定义。
  - 如果某段文本本来就是论文内容的一部分，即使它看起来像按钮词，也不能仅凭字面值删除。

<a id="rule-generic-metadata-boundaries"></a>
### 通用元数据抽取不能把站点描述误当摘要，也不能丢掉 redirect stub 的 lookup title

- 这条规则约束的是：通用 HTML metadata 抽取只能把真正的论文元数据写进文章模型，不能把站点级 description、标题回显或 redirect stub chrome 误当成摘要；如果页面只是 redirect stub，但里面确实带着可靠 lookup title，也要保留下来供后续解析链使用。
- 如果违反，用户会看到：标题被重复当成摘要、摘要字段被站点 description 污染，或者 Elsevier redirect stub 只剩 `Redirecting`，导致后续抓取与展示退化。
- 它对应的阶段是：`metadata`、`html-cleanup`。
- Owner：`paper_fetch.extraction.html._metadata`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/_scenarios/generic_metadata_boundaries/generic_description.html`](../tests/fixtures/golden_criteria/_scenarios/generic_metadata_boundaries/generic_description.html)
  - [`../tests/fixtures/golden_criteria/_scenarios/generic_metadata_boundaries/redirect_stub.html`](../tests/fixtures/golden_criteria/_scenarios/generic_metadata_boundaries/redirect_stub.html)
  - `_scenarios/generic_metadata_boundaries` 是 metadata contract scenario，不是 DOI 级真实 replay。
- 边界说明：
  - 这条规则不是承诺所有 publisher 的隐藏字段或脚本变量都会被完整解析。
  - 它只约束“不要制造假摘要、不要丢掉后续解析必需的 lookup title”。

<a id="rule-html-availability-contract"></a>
### HTML fulltext / abstract-only 判定必须和用户可见访问状态一致

- 这条规则约束的是：availability 判定必须把真正可读的正文 HTML 识别成 fulltext，同时把 access gate、abstract-only 页面和带登录 chrome 的摘要页识别成 abstract-only；不能因为站点噪声、机构登录提示或 ancillary sections 把结果判反。
- 如果违反，用户会看到：明明只有摘要的页面被当成全文返回，或者本来有正文的页面被误降级成 abstract-only，直接影响最终内容类型和 fallback 行为。
- 它对应的阶段是：`availability-quality`、`article-assembly`。
- Owner：`paper_fetch.quality.html_availability` 与 `paper_fetch.extraction.html.provider_rules`；HTML container 评分、选择、清理的架构边界见 [architecture/overview.md 的 Extraction 层](architecture/overview.md#6-extraction-层)。
- 代表性 HTML / XML：
  - [`../tests/fixtures/block/10.1146_annurev.pp.19.060168.001235/raw.html`](../tests/fixtures/block/10.1146_annurev.pp.19.060168.001235/raw.html)
  - [`../tests/fixtures/block/10.1126_science.aeg3511/raw.html`](../tests/fixtures/block/10.1126_science.aeg3511/raw.html)
  - [`../tests/fixtures/golden_criteria/10.1126_science.aeg3511/original.html`](../tests/fixtures/golden_criteria/10.1126_science.aeg3511/original.html)
  - [`../tests/fixtures/block/10.1111_gcb.16414/raw.html`](../tests/fixtures/block/10.1111_gcb.16414/raw.html)
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html)
  - [`../tests/fixtures/block/10.1073_pnas.2509692123/raw.html`](../tests/fixtures/block/10.1073_pnas.2509692123/raw.html)
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html)
  - [`../tests/fixtures/block/10.1007_s00382-018-4286-0/raw.html`](../tests/fixtures/block/10.1007_s00382-018-4286-0/raw.html)
  - 这些样本分别覆盖 Annual Reviews 空全文 shell、Science、Wiley、PNAS 和 Springer 的 paywall / entitled 对照场景。
- 边界说明：
  - 这条规则不约束 provider 路由、PDF fallback 编排或 live 网络重试。
  - 它只约束“用户实际可见的 HTML 内容类型判定不能错位”。
  - availability 相关阈值分三组维护：near-duplicate / inflated abstract 保护渲染层不重复输出摘要；HTML body scoring 保护 access gate 与真实正文判定；provider body thresholds 只覆盖 XML/纯文本 provider 的最小正文量。这些阈值只随回归样本一起调整，不能在单个 provider 内临时覆盖。
  - HTML 接受条件是“可信 container scope + 实质正文证据 + 无 blocking signal”。真实 `article`、有内容的显式 body container，或包含上述实质子容器的 page-level root 才属于可信 scope；空 `fulltext` ID/class 只是 marker，不能与页面其它位置的推荐卡片拼成正文证据。
  - `main` / `body` 的页面总字数、段落数、heading 数和重复 UI 数量不能独立证明全文。provider 把选中节点包装成合成 `<article>` 时必须传递原始 selector/scope，并在 diagnostics 的 body metrics 中保留 `container_scope`、`container_scope_trusted`、`container_selector` 与 `container_synthetic`。
  - Most Read、Most Cited、Recommended 和 Related 等 auxiliary section 后的卡片不计入正文；重复这些 UI 不能把拒绝翻成接受，把相同 UI 附加到真实正文也不能把接受翻成拒绝。
  - Publisher 私有的 availability override（例如 Science perspective、Elsevier canonical abstract URL、Springer preview wall vs body run、Springer/Nature article-in-press notice）必须通过 provider `AvailabilityPolicy` / `ProviderHtmlRules.availability` 注册；access-gate 文案统一来自 `paper_fetch.extraction.html.signals.ACCESS_GATE_LABELS` / `ACCESS_GATE_PATTERNS`，Markdown 降噪只引用 `MARKDOWN_ACCESS_NOISE_LABELS`，不得在 provider 后处理或 runtime 中复制。
  - Springer/Nature 的 `We are providing an unedited version of this manuscript` 只是 Article-in-Press 访问提示；没有真实 `post_abstract_body_run` 时必须作为 blocking fallback signal，触发 provider 内部 PDF fallback，不能用这段提示撑起 HTML fulltext 判定。

<a id="rule-provider-owned-authors"></a>
### Provider 自有作者与摘要信号必须进入最终文章元数据

- 这条规则约束的是：publisher 自己暴露的作者与摘要信号，一旦已经被识别出来，就要稳定进入最终文章模型；优先使用更结构化的 provider-owned 信号，缺失时再回退到 DOM。
- 如果违反，用户会看到：作者列表为空、摘要字段丢失，或者 provider 已经识别出的摘要没有写入文章模型。
- 它对应的阶段是：`metadata`、`provider-html-or-xml-extraction`、`article-assembly`。
- Owner：`paper_fetch.providers._article_markdown_elsevier` 与 `paper_fetch.providers._html_authors`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_science.adp0212/original.html`](../tests/fixtures/golden_criteria/10.1126_science.adp0212/original.html)
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html)
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html)
  - [`../tests/fixtures/golden_criteria/_scenarios/elsevier_author_groups_minimal/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_author_groups_minimal/original.xml)
  - [`../tests/fixtures/golden_criteria/_scenarios/provider_dom_abstract_fallback/payload.json`](../tests/fixtures/golden_criteria/_scenarios/provider_dom_abstract_fallback/payload.json)
  - `_scenarios/elsevier_author_groups_minimal` 是最小 contract scenario，不是 DOI 级真实 replay，用于锁住 Elsevier author groups 结构。
  - `_scenarios/provider_dom_abstract_fallback` 锁住“DOM abstract 恢复正文首段”分支；它不是 DOI 级真实 replay。
- 边界说明：
  - 这条规则不是要求所有 provider 都必须有统一的作者源字段。
  - 它约束的是“已识别的 provider-owned 元数据要稳定进入最终模型”，不是要求不存在的作者信息凭空生成。
  - 摘要重复去重不归本规则约束；前言摘要族顺序与去重见 [前言摘要族的顺序与去重必须稳定](#rule-stable-frontmatter-order)。

<a id="rule-preserve-subscripts-in-headings"></a>
### 兼容锚点：标题和节标题里的上下标不能被打平成普通文本

> 参见 [正文、标题和表格里的行内语义格式不能被打平或拆裂](#rule-preserve-inline-semantics-in-body-and-tables)。

兼容锚点保留用于 manifest 和外部引用。标题、节标题、frontmatter、正文、caption 和 table cell 中的 `sub` / `sup` 统一由同一条 inline semantics 规则约束。

<a id="rule-short-markdown-image-alt-labels"></a>
### Markdown 图片 alt 只保留短标签

- 这条规则约束的是：系统生成或重写的 Markdown 图片行必须只使用短 alt 标签；figure 输出 `Figure N` / `Figure`，table 输出 `Table N` / `Table`，listing 输出 `Listing N` / `Listing`，formula / equation 输出 `Formula`，其它图片输出 `Image`。完整 caption 必须保留在下一段或原正文 caption 中，不能塞进 `![alt]`。
- 如果违反，用户会看到：`[EMIM][Ac]`、`[AO10]`、化学式、长 figure caption 或未平衡方括号进入 Markdown 图片 opener，导致图片行解析不稳定，或者图片 alt 被当作正文 caption 的重复副本。
- 它对应的阶段是：`asset-link-rewrite`、`table-rendering`、`formula-rendering`、`markdown-normalization`、`final-rendering`。
- Owner：`paper_fetch.markdown.images`。
- 代表性 HTML / XML：
  - 当前无稳定 DOI 样本，直接见对应测试；复杂 caption 与本地资产改写已进入“无稳定 DOI 样本规则汇总表”。
- 边界说明：
  - 这条规则不删除 caption，也不改变 `Asset.heading` / `Asset.caption` 数据；它只约束最终 Markdown 图片引用行。
  - 第三方原始 Markdown 只有在项目注入图片或重写图片链接时才会被短 alt 规范化。
  - `Figure 2.2`、`Figure A.1` 这类结构短标签必须保留；它们不是长 caption。
  - `Listing 1` 这类代码清单标签也是结构短标签；publisher 把 listing 作为 figure image 发布时不能降级成 `Figure` 或 `Image`。

<a id="rule-rewrite-inline-figure-links"></a>
### 已下载的正文图片和公式图片要改写成正文附近的本地链接

- 这条规则约束的是：正文里已经有 figure、table image 或 formula image 锚点时，最终 markdown 应该尽量把远程图链接或绝对本地路径改写成当前 markdown 文件可用的本地资源链接，而且图和图之间不能误绑；只有真实存在的本地文件才能生成相对路径。未匹配本地资产的 `/cms/...` 根相对链接应使用有效的 publisher `landing_page_url` 补成完整远程 URL；没有有效 HTTP(S) 基址时保留原链接。改写后还要重新规范 Markdown 图片块边界和短 alt 标签，不能让图片和标题、正文句子或公式围栏粘在一起。
- 公式图片锚点只能按 formula 资产改写；它不能被 inline figure 注入逻辑当作 figure 占位，也不能消耗后续正文 figure 的本地资产。
- 已存在的 Markdown 图片块会按 alt 和图片 URL basename 提取 `Figure N` 去重键；即使 caption label 暂时不可用或同一 figure 资产重复出现，正文里的 `Figure N` 交叉引用也不能再触发第二次插图。
- 如果违反，用户会看到：图片链接还是不可用的根相对 URL、绝对路径，或被伪造成 `../../cms/...` 这类不存在的本地路径；也可能出现图 4 的本地资源被错绑到图 1 的 caption、table 图片被错改成下一张 figure，或者 `Heading![Figure]`、`text.![Formula]` 这类坏 Markdown。
- 它对应的阶段是：`asset-link-rewrite`、`article-assembly`、`markdown-normalization`、`final-rendering`。
- Owner：`paper_fetch.extraction.html.figure_links` 与 `paper_fetch.workflow.rendering`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/_scenarios/inline_figure_link_rewrite/article.md`](../tests/fixtures/golden_criteria/_scenarios/inline_figure_link_rewrite/article.md)
  - [`../tests/fixtures/golden_criteria/_scenarios/inline_figure_link_rewrite/assets.json`](../tests/fixtures/golden_criteria/_scenarios/inline_figure_link_rewrite/assets.json)
  - `_scenarios/inline_figure_link_rewrite` 覆盖“远程图 -> 已下载本地资源 -> 本地 Markdown 链接 -> 交叉引用不误绑”的 shared contract；它不是 DOI 级真实 replay。
    - [`../tests/unit/test_atypon_browser_workflow_postprocess.py`](../tests/unit/test_atypon_browser_workflow_postprocess.py) 中的 `test_rewrite_inline_figure_links_prefers_local_paths_for_existing_science_image_blocks`
    - [`../tests/unit/test_atypon_browser_workflow_postprocess.py`](../tests/unit/test_atypon_browser_workflow_postprocess.py) 中的 `test_rewrite_inline_figure_links_is_data_driven_for_non_legacy_publisher`
    - [`../tests/unit/test_atypon_browser_workflow_postprocess.py`](../tests/unit/test_atypon_browser_workflow_postprocess.py) 中的 `test_rewrite_inline_figure_links_ignores_cross_references_in_asset_captions`
    - [`../tests/unit/test_atypon_browser_workflow_postprocess.py`](../tests/unit/test_atypon_browser_workflow_postprocess.py) 中的 `test_figure_link_injection_and_rewrite_share_path_preference`
    - [`../tests/unit/test_atypon_browser_workflow_postprocess.py`](../tests/unit/test_atypon_browser_workflow_postprocess.py) 中的 `test_inject_inline_figure_links_preserves_table_image_blocks`
    - [`../tests/unit/test_atypon_browser_workflow_postprocess.py`](../tests/unit/test_atypon_browser_workflow_postprocess.py) 中的 `test_inline_figure_injection_skips_body_reference_for_existing_image_label`
  - Provider 覆盖：
    - [`../tests/unit/test_atypon_browser_workflow_provider_html.py`](../tests/unit/test_atypon_browser_workflow_provider_html.py) 中的 `test_science_provider_rewrites_inline_figure_links_to_downloaded_local_assets`
    - [`../tests/unit/test_arxiv_provider.py`](../tests/unit/test_arxiv_provider.py) 中的 `test_html_route_inlines_single_official_html_figure_without_trailing_figures`
    - [`../tests/unit/test_arxiv_provider.py`](../tests/unit/test_arxiv_provider.py) 中的 `test_html_route_inlines_all_images_from_shared_caption_figures_once`
  - CLI / models 覆盖：
    - [`../tests/unit/test_cli.py`](../tests/unit/test_cli.py) 中的 `test_save_markdown_to_disk_rewrites_local_asset_links_relative_to_saved_file`
    - [`../tests/unit/test_cli.py`](../tests/unit/test_cli.py) 中的 `test_rewrite_markdown_asset_links_maps_remote_figure_urls_to_downloaded_local_assets`
    - [`../tests/unit/test_cli.py`](../tests/unit/test_cli.py) 中的 `test_rewrite_markdown_asset_links_prefers_downloaded_root_relative_formula`
    - [`../tests/unit/test_cli.py`](../tests/unit/test_cli.py) 中的 `test_rewrite_markdown_asset_links_expands_unmatched_cms_url_from_landing_page` 与 `test_rewrite_markdown_asset_links_keeps_cms_url_without_valid_landing_page`
    - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_rewrites_inline_asset_urls_to_downloaded_paths`
    - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_normalizes_after_inline_asset_url_rewrite`
    - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_normalize_markdown_text_separates_adjacent_block_images`
    - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_to_ai_markdown_separates_adjacent_section_images_after_asset_rewrites`
- 边界说明：
  - 这条规则只改写 Markdown 链接目标，不会去改普通正文里的纯文本路径。
  - 只有当系统手里确实有可用的本地资产时，才应该把链接改写成对应本地路径。
  - 已下载资产匹配优先于 publisher 远程 fallback；远程 fallback 只修复未匹配的 `/cms/...`，不把任意缺失的绝对本地路径猜成网页 URL。
  - `![Table ...]`、`![Extended Data Table ...]` 和 `![Supplementary Table ...]` 图片块不参与 figure 顺序 fallback；table image 的原位链接由 table/provider 链路维护。
  - 对 preview 降级，正文里如果仍引用 full-size 远端 URL，也必须能通过 `original_url` / `full_size_url` / `preview_url` / `download_url` / `source_url` 映射到实际保存的本地 preview 文件。

<a id="rule-markdown-inline-citation-normalization"></a>
### Markdown inline citation normalize 不能破坏非引用语义和图片块边界

- 这条规则约束的是：HTML-derived Markdown 中已经识别出的数字引用 sentinel 要稳定渲染为 `<sup>...</sup>`；引用前缀和周边标点要清理到可读形态；同时不能把普通数字文本、年份范围、同位素上标或 Markdown 图片 opener `![...]` 当成引用标点处理。
- 如果违反，用户会看到：数字引用丢失或残留内部 sentinel，`ref. <sup>21</sup>` 这类前缀清理失败，`of <sup>6</sup>Li` 被挤成 `of<sup>6</sup>Li`，句末出现多余空格/标点，或者正文图片前的空行被标点清理吃掉，形成 `sentence.![Figure]` 这类坏 Markdown。
- 它对应的阶段是：`markdown-normalization`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.markdown.citations`。
- 代表性 HTML / Markdown：
  - 当前以 shared citation unit tests 覆盖；真实 provider 回放中出现的 DOI 级 citation DOM 归各 provider 结构规则承载。
- 边界说明：
  - 这条规则不尝试修复 publisher 源 HTML 里语义已经损坏的 citation range；它只约束共享 Markdown normalize 层不能制造新的坏标点或破坏图片块。
  - 括号引用识别的 160 字符上限是保守阈值，用来避免跨长段误吞普通括号内容；放宽该阈值需要新增长段误吞和真实 citation fixture 覆盖。
  - Springer/Nature inline article link unwrap、Extended Data label 和 figure-line pattern 位于 provider helper，由调用方显式传入 `clean_citation_markers()`；shared 默认只保留通用 numeric/label cleanup。
  - `<sup>` / `<sub>` 前空格由 shared inline token joiner 决定：citation sentinel 和括号脚注默认 tight；源 HTML 原本无空格的上下标邻接保持 tight；源 HTML 原本有 prose 空格时默认保留。额外收紧只允许基于通用 symbol-shape 规则，例如 signed numeric superscript after compact symbol、短单位形态的 unsigned numeric superscript、uppercase chemical-like base 的 numeric subscript，以及单字母/斜体数学符号的 numeric sup/sub；不维护单位或化学 base 白名单。
  - Provider-specific reference payload、bibliography 抽取和 Crossref fallback 优先级不属于本规则。

<a id="rule-image-download-tier-diagnostics"></a>
### 兼容锚点：图片下载必须验证真实图片、保留 tier 和尺寸诊断

> 参见 [图片下载必须验证真实图片内容](#rule-image-download-validates-real-images)、[下载资产必须保留诊断字段](#rule-asset-download-diagnostic-fields) 和 [浏览器工作流图片下载必须使用 shared browser 主链路](#rule-browser-primary-image-download-path)。

兼容锚点保留用于 manifest 和外部引用。当前规则分别约束真实性校验、诊断字段和 provider-owned 浏览器主链路。

<a id="rule-image-download-validates-real-images"></a>
### 图片下载必须验证真实图片内容

- 这条规则约束的是：正文图片下载不能把 Cloudflare challenge HTML、Chrome 图片查看器壳或过小的站点图标当成论文图片保存；preview 图只有尺寸达标或 provider 明确接受，并在 `Asset.preview_accepted` 中保存该事实时，才算可接受结果。publisher 只提供的规范公式位图属于显式 accepted preview，不要求伪造 full-size tier。下载后的统一审计必须用 `filetype` 读取真实 MIME、用 `imagesize` 读取尺寸，并记录文件实际字节数和 `SHA256`，不能信任扩展名、响应头或 provider 声明值代替文件事实。
- 如果违反，用户会看到：正文缺图，或本地图片文件其实是 HTML / 站点图标，最终诊断无法解释失败原因。
- 它对应的阶段是：`asset-download`、`asset-validation`、`availability-quality`。
- Owner：`paper_fetch.extraction.html.assets` 与 `paper_fetch.providers.browser_workflow.fetchers`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html)
  - [`../tests/fixtures/golden_criteria/10.1126_sciadv.aax6869/original.html`](../tests/fixtures/golden_criteria/10.1126_sciadv.aax6869/original.html)
  - [`../tests/fixtures/golden_criteria/10.1126_science.abb3021/original.html`](../tests/fixtures/golden_criteria/10.1126_science.abb3021/original.html)
  - [`../tests/fixtures/golden_criteria/10.1126_science.adz3492/original.html`](../tests/fixtures/golden_criteria/10.1126_science.adz3492/original.html)
  - [`../tests/fixtures/golden_criteria/10.1126_science.adz3492/body_assets/science.adz3492-f1.svg`](../tests/fixtures/golden_criteria/10.1126_science.adz3492/body_assets/science.adz3492-f1.svg)
  - 这些样本覆盖 PNAS / Science CMS 图片直接 HTTP 请求被 challenge、只能拿到站点标记为 preview 的图片，或 preview 资产是顶层 SVG 文档时，如何区分真实故障和可接受降级。
    - [`../tests/unit/test_atypon_browser_workflow_provider_asset_downloads.py`](../tests/unit/test_atypon_browser_workflow_provider_asset_downloads.py) 中的 `test_science_provider_records_preview_dimensions_and_acceptance`
    - [`../tests/unit/test_atypon_browser_workflow_provider_asset_failures.py`](../tests/unit/test_atypon_browser_workflow_provider_asset_failures.py) 中的 `test_science_provider_replay_for_adz3492_saves_svg_body_asset`
    - [`../tests/unit/test_atypon_browser_workflow_provider_asset_failures.py`](../tests/unit/test_atypon_browser_workflow_provider_asset_failures.py) 中的 `test_science_provider_records_asset_failure_when_shared_browser_preview_fails`
    - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_formula_bitmap_download_is_an_accepted_preview`
  - Service / acceptance 覆盖：
    - [`../tests/unit/test_service_probe_and_assets.py`](../tests/unit/test_service_probe_and_assets.py) 中的 `test_fetch_paper_accepts_preview_images_with_sufficient_dimensions`
    - [`../tests/unit/test_asset_quality.py`](../tests/unit/test_asset_quality.py) 中的 `test_accepted_preview_is_complete_and_fallback_preview_is_fidelity_only`
  - 统一真实性审计：
    - [`../tests/unit/test_asset_quality.py`](../tests/unit/test_asset_quality.py) 中的 `test_valid_png_jpeg_svg_and_pseudo_extension_record_real_facts`
    - [`../tests/unit/test_asset_quality.py`](../tests/unit/test_asset_quality.py) 中的 `test_placeholder_signals_are_suspected_and_never_delete_files`
    - [`../tests/unit/test_asset_quality.py`](../tests/unit/test_asset_quality.py) 中的 `test_formula_dimensions_and_duplicate_hashes_are_not_placeholder_signals` 与 `test_formula_payload_and_path_failures_remain_diagnostic`
    - [`../tests/unit/test_asset_quality.py`](../tests/unit/test_asset_quality.py) 中的 `test_missing_path_and_explicit_failure_are_definite_and_classified`
- 边界说明：
  - `download_tier="preview"` 不是天然错误；当下载阶段判定 preview 尺寸满足阈值，或 provider 明确把该 preview 标记为可接受，并设置 `preview_accepted=true` 时，它不应写入普通 warning，也不产生 asset issue。source trail 只保留摘要诊断，不能代替该结构化字段。
  - 任意 kind 的 fallback preview 都产生 `asset_fidelity_degraded`，但不产生 `asset_download_failure`；只有 accepted preview 且无其它 issue 时，资产分面保持 `complete`，并继续满足 `preview = accepted_preview + fallback_preview`。
  - `Blank.svg` / `Blank.png` URL、零字节、异常小文件、无效真实 MIME、MIME 与扩展名不一致，以及多个不同逻辑 figure/table 共享完全相同 `SHA256`，都只是保守的 `placeholder_suspected` 信号。公式位图不使用 `tiny_dimensions` 或 `duplicate_sha256` 推断占位，因为规范表达式本来可能很小或重复；但公式仍检查 blank URL、零字节、异常小文件、无效 MIME、扩展名不符、文件缺失或不可读。审计器不会据此删除、覆盖或改写文件，也不会声称已经完成视觉语义判断。
  - 明确的下载 failure diagnostic、声明了本地路径但文件不存在或不可读，才属于确定的资产失败；这些失败仍不能把已经成功的正文内容改判成抓取失败。
  - `asset_profile=none` 时，保留下来的远程链接逐项记为 `not_requested`，不能对它们执行本地存在性失败判定；请求了对应 kind、但 no-download / artifact policy 禁止归档时记为 `not_archived`。`body` profile 不请求 supplement，`all` 才请求 supplement 和 decoration。
  - `figure`、`formula`、`table`、`supplement`、`decoration` 必须分别汇总；公式占位嫌疑不能冒充正文主图失败，主图失败也不能被公式成功掩盖。
  - 图片可用性与正文完整性是两个独立分面：preview、疑似占位、未归档或资产失败只降低资产分面；是否 fulltext 仍由正文验收规则决定。

<a id="rule-asset-download-diagnostic-fields"></a>
### 下载资产必须保留诊断字段

- 这条规则约束的是：成功或失败的资产下载都要保留足够诊断信息；成功图片记录请求 profile、逻辑 kind、`download_tier`、路径、下载 URL、原始 full-size / preview 候选 URL、声明 content type、真实 MIME、实际字节数、尺寸、`SHA256` 和 provenance，失败资产保留 failure code、status、content type、snippet、reason 和 recovery 轨迹。结构化摘要必须同时给出 `requested`、`total`、`full_size`、`preview`、`failed`、`placeholder_suspected`、`not_requested`、`not_archived`，以及按 kind 的同类计数。
- 如果违反，用户只会看到笼统的 `asset_download_failure`，看不出是 full-size 被拦截、preview 可接受、supplementary 失败，还是图片真的缺失。
- 它对应的阶段是：`asset-validation`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.extraction.html.assets.download`、`paper_fetch.extraction.html.assets.state`、`paper_fetch.models.Asset` / `paper_fetch.models.Quality` 与 `paper_fetch.mcp.schemas`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/_scenarios/asset_download_diagnostics/article_payload.json`](../tests/fixtures/golden_criteria/_scenarios/asset_download_diagnostics/article_payload.json)
  - `_scenarios/asset_download_diagnostics` 锁住 MCP / model payload 的成功下载诊断字段；它不是 DOI 级真实 replay。
    - [`../tests/unit/test_mcp_payload_cache.py`](../tests/unit/test_mcp_payload_cache.py) 中的 `test_article_payload_preserves_asset_download_diagnostics`
    - [`../tests/unit/test_asset_quality.py`](../tests/unit/test_asset_quality.py) 中的 `test_asset_summary_model_and_legacy_cache_payloads_are_compatible`
    - [`../tests/unit/test_workflow_acceptance.py`](../tests/unit/test_workflow_acceptance.py) 中的 `test_audited_quality_asset_summary_matches_explicit_acceptance_adapter`
  - Provider 覆盖：
    - [`../tests/unit/test_asset_retry_policy.py`](../tests/unit/test_asset_retry_policy.py) 中的 `test_provider_asset_retry_policies_round_trip_merge_and_retry`
    - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_springer_asset_retry_policy_reconciles_preview_and_full_formula_urls`
    - [`../tests/unit/test_cli_manifest_v2.py`](../tests/unit/test_cli_manifest_v2.py) 中的 `test_springer_formula_rendition_aliases_produce_complete_manifest`
    - [`../tests/unit/test_atypon_browser_workflow_provider_retries.py`](../tests/unit/test_atypon_browser_workflow_provider_retries.py) 中的 `test_browser_workflow_download_related_assets_retries_after_partial_failures`
    - [`../tests/unit/test_atypon_browser_workflow_provider_retries.py`](../tests/unit/test_atypon_browser_workflow_provider_retries.py) 中的 `test_browser_workflow_retries_only_failed_supplementary_assets`
    - [`../tests/unit/test_atypon_browser_workflow_provider_retries.py`](../tests/unit/test_atypon_browser_workflow_provider_retries.py) 中的 `test_browser_workflow_retries_only_failed_body_assets`
    - [`../tests/unit/test_atypon_browser_workflow_provider_asset_failures.py`](../tests/unit/test_atypon_browser_workflow_provider_asset_failures.py) 中的 `test_science_provider_records_asset_failure_when_shared_browser_preview_fails`
- 边界说明：
  - 本规则只要求诊断字段不丢失，不要求所有 provider 使用同一种远端下载实现。
  - Springer/Nature 的 `media.springernature.com/lwNN/springer-static/...` 与对应 `/full/...` 是同一远端对象的尺寸 rendition；provider 必须复用既有 full-size URL promotion 规则规范化 retry identity。成功的 `/full/...` 本地记录覆盖预览别名后只能进入一次逻辑资产验收，不能让无本地路径的 `lwNN` 别名另计为 `missing_path` 或 `asset_remote_only`；真正没有对应本地记录的远端资产仍按失败处理。
  - Browser workflow 的 retry 只覆盖网络、超时、browser context/fetch error 和 challenge 类可恢复失败；404、非目标 content type、unsupported scheme 等确定性失败不触发重试。403、429 和 5xx 只有在 reason 同时指向 challenge 或 browser fetch/context 临时失败时才重试。
  - 诊断字段不能替代用户可见内容；caption、占位和 warnings 仍由渲染规则决定。
  - EPS/TIFF 源转换失败后，如果后续 JPG/PNG 候选成功，最终资产保持成功且记录 `conversion_degraded` provenance；不能保留一个虚假的最终 asset failure。只有所有候选均失败时才计入 `failed`。
  - 旧 cache 或旧模型缺少结构化资产摘要时按“尚未审计”的空摘要读取；不能把字段缺失解释成资产完整，也不能因此拒绝反序列化。

<a id="rule-browser-primary-image-download-path"></a>
### 浏览器工作流图片下载必须使用浏览器上下文或浏览器等价请求头

- 这条规则约束的是：使用 browser workflow 的 provider 在下载正文 figure / table / formula 图片时，必须以 `RuntimeContext` / browser runtime facade 管理的 selected-browser context 作为主链路。同一进程内按 browser 配置复用 keyed browser manager，每个阶段创建隔离的 seeded context/page，preview fallback 也通过同一调用线程的 context 获取。Atypon/AMS 这类 lazy image 页面里的 `Blank.svg` / `Blank.png` 只允许作为待加载占位信号，不能作为成功正文 asset 保存；当 `download_url` / `full_size_url` 指向真实 `full-*.jpg` 时，下载候选和最终 `source_url` 必须指向真实图片响应。
- 如果违反，用户会看到：目标站点明明在浏览器会话里可见图片，系统却因为普通 HTTP challenge 或重复 context 冷启动而稳定缺图，或者所有本地图片都变成相同的 `Blank.png` 占位图。
- 它对应的阶段是：`asset-download`、`asset-validation`。
- Owner：`paper_fetch.providers.browser_workflow.fetchers`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html)
    - [`../tests/unit/test_browser_asset_download.py`](../tests/unit/test_browser_asset_download.py) 中的 `test_browser_workflow_image_candidates_prefer_download_url`
    - [`../tests/unit/test_browser_asset_download.py`](../tests/unit/test_browser_asset_download.py) 中的 `test_browser_image_payload_rejects_blank_placeholder_url`
    - [`../tests/unit/test_atypon_browser_workflow_provider_asset_downloads.py`](../tests/unit/test_atypon_browser_workflow_provider_asset_downloads.py) 中的 `test_pnas_provider_download_related_assets_uses_shared_browser_primary_path_before_preview`
    - [`../tests/unit/test_atypon_browser_workflow_provider_asset_failures.py`](../tests/unit/test_atypon_browser_workflow_provider_asset_failures.py) 中的 `test_pnas_provider_downloads_preview_through_shared_browser_when_no_full_size_candidate`
    - [`../tests/unit/test_atypon_browser_workflow_provider_retries.py`](../tests/unit/test_atypon_browser_workflow_provider_retries.py) 中的 `test_wiley_provider_download_related_assets_uses_shared_browser_primary_path`
    - [`../tests/unit/test_atypon_browser_workflow_provider_retries.py`](../tests/unit/test_atypon_browser_workflow_provider_retries.py) 中的 `test_wiley_provider_download_related_assets_reuses_shared_browser_fetcher_across_assets`
    - [`../tests/unit/test_atypon_browser_workflow_provider_asset_downloads.py`](../tests/unit/test_atypon_browser_workflow_provider_asset_downloads.py) 中的 `test_ams_provider_download_related_assets_downloads_full_size_figure`
- 边界说明：
  - 这条规则目前适用于 `wiley`、`science`、`pnas`、`ams`、`annualreviews`、`royalsocietypublishing`、`acs`、`iop`、`aip`、`mdpi` 的 browser workflow HTML 成功路径。
  - 它不改变 `elsevier` XML、`springer` direct HTML 或 PDF fallback 的下载语义。

<a id="rule-table-flatten-or-list"></a>
### 表格能展平就转 Markdown 表，展不平就退成可读列表

- 这条规则约束的是：HTML、JATS 和 CALS 表格先进入同一个 provider-neutral cell/row IR 与占位网格规范化器；多级表头、rowspan 和局部 colspan 能安全展开时生成 Markdown 表并归为正常规范化，重叠、越界、ragged 或超限网格则退成保留 cell 文本的可读列表。无可靠编号和 caption 的表格不能额外输出孤立 `**Table**` 标题；无可靠表头时不能把 `Column 1` 这类内部占位当成用户可见表头。表头前覆盖整表宽度的标题提升为普通文本，正文中的整表宽度分组保留为首列分组行；不同分组下的列名仍要扁平化为 `Configuration / n_r`、`Inference / MMLU` 这类可读表头。
- 如果违反，用户会看到：要么本来能读懂的表被糟糕地压扁成错列的 Markdown 表，要么复杂表直接丢信息，没有任何可读 fallback，或者表格前出现孤立 `****` / `Column N` / 整行重复的分组标题，甚至出现 header / separator 列数不一致的坏 GFM pipe table。
- 它对应的阶段是：`table-rendering`、`markdown-normalization`。
- Owner：`paper_fetch.extraction.table_grid`、`paper_fetch.extraction.xml_tables` 与 Markdown/HTML compatibility adapters。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/_scenarios/table_flatten_or_list/complex_table.html`](../tests/fixtures/golden_criteria/_scenarios/table_flatten_or_list/complex_table.html)
  - `_scenarios/table_flatten_or_list` 锁住无法安全展平时的列表降级；它不是 DOI 级真实 replay。
  - [`../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06556v1/original.html`](../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06556v1/original.html)
  - 这个样本能证明 arXiv official HTML 中无 caption 的 `ltx_tabular` 应直接输出 Markdown 表，而不是额外输出裸 `**Table**`；跨列表题行要作为表格前普通文本保留，后续真实列名和数据行必须组成合法 GFM pipe table。
  - [`../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06665v1/original.html`](../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06665v1/original.html)
  - 这个样本能证明 LaTeXML 表格首行真实标题可提升为表头，整行 colspan 分组标题只能出现一次，且空 label 不能渲染成孤立 `****`。
- 边界说明：
  - 这条规则不是要求所有表格最终都必须长成 Markdown 表。
  - 当结构已经超出安全展平范围时，退成列表是符合规则的正确结果，不是降级失败。
  - 合法的整表宽度分组、rowspan 和局部 colspan 成功展开后只记录规范化 reason，不触发 `table_layout_degraded`；非法或不一致的 span/列定义仍触发该质量标记。
  - 无法形成可靠矩形但 cell 文本完整保留时记录 `table_fallback_count` 和布局降级，不误报 `table_semantic_loss`；只有内容确实遗失才升级语义损失。
  - `paper_fetch.extraction.html.tables` 只保留 HTML 解析和兼容入口，网格占位、表头扁平化与内部状态的 canonical owner 是 `paper_fetch.extraction.table_grid`。

<a id="rule-xml-table-groups"></a>
### CALS 多个 `tgroup` 必须按各自列定义独立渲染

- 这条规则约束的是：同一个 XML 表题下出现多个 CALS `tgroup` 时，每组必须使用自己的 `cols` / `colspec`、表头、正文行和源内前缀独立解析，并按源顺序渲染为多个 Markdown 网格或可读列表；没有 `tgroup` 的 HTML-like JATS 表继续作为单组处理。表格编号、caption 和脚注只输出一次，`(a) WBGT` 这类源内分组前缀放在对应网格之前；源中没有分组标题时只分隔网格，不能虚构标题，也不能把不同列宽强行拼成一张表。
- 如果违反，用户会看到：后一个 `tgroup` 被前一个的列宽截断、21 行数据只剩一部分、WBGT/T/AT 顺序错乱，或者一张表被合并成 header / separator 列数不一致的坏 GFM 表。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`table-rendering`、`markdown-normalization`。
- Owner：`paper_fetch.extraction.xml_tables`、`paper_fetch.extraction.markdown_render.tables`、`paper_fetch.providers._article_markdown_elsevier` 与 `paper_fetch.providers._article_markdown_jats_blocks`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.apgeog.2012.04.006/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.apgeog.2012.04.006/original.xml)
  - [`../tests/fixtures/golden_criteria/10.1016_j.envres.2018.12.059/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.envres.2018.12.059/original.xml)
  - 前一个样本锁住同一表题下两个不同列宽的 `tgroup`，源行数分别为 6 与 21；后一个样本锁住按 WBGT、T、AT 顺序输出三个 `tgroup`，每组各 21 个源行。
- 边界说明：
  - 每个分组独立聚合质量状态；`exact` / `normalized` 成功组不计降级，只有真实失败并退成列表的组才各计一次 `table_fallback_count` / `table_layout_degraded_count`。
  - 某个分组失败不能拖累其它可安全展开的分组；失败组仍须保留全部可读 cell 文本。
  - 本规则只扩展内部 XML 表格 IR 和渲染，不改变 Article、CLI 或 MCP 的公共数据结构。

<a id="rule-html-list-marker-rendering"></a>
### HTML 列表必须只保留一层 Markdown marker

- 这条规则约束的是：HTML `<ol>` 应渲染为 Markdown `1. item` / `2. item` 编号列表，不能先把 LaTeXML 或 publisher 的可见 item marker 当正文，再额外套一层 bullet，形成 `- 1.` 后接正文的坏列表；HTML `<ul>` 应保留 Markdown `- item` bullet，但要去掉条目开头由上游 HTML 显式输出的 `•` / `◦` / `▪` 这类无序列表 marker，不能形成 `- •` 后接正文的双 marker。
- 如果违反，用户会看到：算法步骤、定义步骤或实验流程被渲染成 `- 1.`、`- 2.`，或者无序列表变成 `- •` 加下一行正文，既不像正常 Markdown 列表，也不适合继续给模型解析。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`markdown-normalization`。
- Owner：`paper_fetch.providers._html_section_markdown`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06556v1/original.html`](../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06556v1/original.html)
  - [`../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06665v1/original.html`](../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06665v1/original.html)
  - [`../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06667v1/original.html`](../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06667v1/original.html)
  - 这些样本能证明 arXiv official HTML 中 `ol.ltx_enumerate` 的 visible `ltx_tag_item` 需要被去掉，并由 Markdown 有序列表 marker 表达顺序；`ul.ltx_itemize` 中可见的 bullet 字符也只能作为 HTML marker 处理，不能作为正文残留。
- 边界说明：
  - 本规则只约束列表 marker 的 Markdown 语义，不要求重建复杂嵌套列表版式。
  - 无序列表不能因此被改成编号列表。
  - 只清理列表条目开头的已知无序 marker 字符；正文中非列表位置的真实 bullet 字符必须保留。

<a id="rule-arxiv-figure-panel-alt-labels"></a>
### arXiv panel figure 缺 caption 时用 DOM 短标签作 alt

- 这条规则约束的是：arXiv official HTML 中 panel figure 可能没有自己的 `figcaption`，并且图片只有 `alt="Refer to caption"` 这类占位文本；最终 Figures 附录的图片 alt 不能退化成泛化的 `Figure`，而应在 caption 缺失时从 LaTeXML DOM id 推出结构短标签，例如 `S4.F2.2` 渲染为 `Figure 2.2`。
- 如果违反，用户会看到：文末图片连续显示为 `![Figure](...)`，无法区分 panel；或者每个 panel 都复制父 figure 长 caption，造成重复和虚构的子图说明。
- 它对应的阶段是：`asset-discovery`、`html-cleanup`、`final-rendering`。
- Owner：`paper_fetch.extraction.html.assets.figures` 与 `paper_fetch.providers.arxiv`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06598v1/original.html`](../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06598v1/original.html)
- 这个样本能证明 `S4.F2.2` / `S4.F5.6` 这类 captionless panel figure 需要用 DOM id 生成短标签并作为正文图片 alt，同时 `Refer to caption` 不能进入 Markdown 或 asset caption。
- 边界说明：
  - 这条规则不要求重建上游 HTML 缺失的 panel caption，也不从父 caption 拆分或猜测子图语义。
  - `Figure 2.2` 是结构短标签，可用于 Markdown image alt；它不是论文作者提供的 caption。
  - arXiv HTML 的 Markdown 图片 alt 优先使用 `Figure N` / `Figure N.M` 这类短标签；长 caption 保留在正文 caption 或 asset caption 中，不塞进 alt。
  - 测试覆盖度低：当前只有 arXiv LaTeXML panel figure fixture 直接锁住该行为；后续若其它 publisher 也暴露 captionless panel 结构，应另补 provider-specific replay。

<a id="rule-arxiv-multi-image-figure-captions"></a>
### arXiv 一个 figure 内的多图多 caption 必须逐张保留

- 这条规则约束的是：LaTeXML 会把多个主图和多个 `figcaption` 放进同一个 `<figure>`，例如同一个 DOM 节点里连续出现 `Figure 9` / `Figure 10` 或 `Figure 11` / `Figure 12` / `Figure 13`。资产抽取必须按图片顺序产出多条 figure asset，正文 Markdown 也必须把多个 caption 渲染成独立块，并把可匹配的图片链接原位内联到对应 caption 附近。
- 如果违反，用户会看到：后续主图没有被下载；`Figure 10`、`Figure 12`、`Figure 13` 的 caption 被并进前一个 caption；正文只有 caption 而图片集中追加到尾部 `Figures`；或者 Figures 附录只有第一张图。
- 它对应的阶段是：`asset-discovery`、`provider-html-or-xml-extraction`、`final-rendering`。
- Owner：`paper_fetch.extraction.html.assets.figures`、`paper_fetch.providers._html_section_markdown` 与 `paper_fetch.providers.arxiv`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06665v1/original.html`](../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06665v1/original.html)
  - 这个样本能证明同一 `Figure 2` caption 下的 `x2.png` / `x3.png` 都应作为正文主图资产保留。
  - [`../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06667v1/original.html`](../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06667v1/original.html)
  - 这个样本能证明同一 LaTeXML figure 中的 `Figure 9` / `Figure 10` 和 `Figure 11` / `Figure 12` / `Figure 13` 必须拆成独立 caption 与独立图片资产。
- 边界说明：
  - 多张图片共享同一个 caption 时，每张图片都应使用自身 asset URL 和 `Figure N` / `Figure N.M` 短 alt；caption 仍保留为正文文本，不复制进 alt，也不能为每张图片重复扩写一遍。
  - 资产顺序、父 figure id、图片 id 都应保留，便于后续下载诊断和本地链接改写。
  - arXiv HTML extraction diagnostics 需要记录 `inline_figure_image_count`、`inline_figure_asset_match_count` 和 `inline_figure_asset_miss_count`，便于区分已原位消费的图片和只能走尾部 fallback 的资产。

<a id="rule-arxiv-article-dom-body-heading-hints"></a>
### arXiv article DOM 正文标题必须由结构 hint 保留

- 这条规则约束的是：arXiv official HTML route 只能从清洗后的 `article.ltx_document` 正文流收集 section hints；`Abstract` 不标记为正文，`References` / `Bibliography` 与 Data / Code Availability 继续按共享语义分类，其它由正文渲染链路输出的 article DOM 标题默认标记为 `body`，包括 `Metrics.`。
- 如果违反，用户会看到：论文正文里的 `Metrics.` 被通用 publisher UI 噪声规则误归为 diagnostics，相关正文和表格从可渲染正文中消失；或者页面外的 article views / citation metrics chrome 被错误注入正文。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`section-classification`、`article-assembly`。
- Owner：`paper_fetch.providers.arxiv` 与 `paper_fetch.models.ArticleModel`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06667v1/original.html`](../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06667v1/original.html)
  - 这个样本能证明 `Metrics.` 是 arXiv article DOM 中的正文小标题，后续 `Table 1` 和正文指标说明必须作为 body 保留。
- 边界说明：
  - 这不是 `Metrics` 标题白名单；规则依据是 arXiv official HTML 的 LaTeXML article DOM 结构和正文渲染链路。
  - 非 arXiv provider 仍使用共享 `metrics` 噪声语义；arXiv 页面外部的 metrics / citation chrome 也必须继续被排除。
  - `article.ltx_document` 内已经删除的 frontmatter、TOC/nav/header/footer、bibliography 内部条目和 LaTeXML chrome 不应产生正文 section hint。

<a id="rule-arxiv-html-artifact-cleanup"></a>
### arXiv LaTeXML HTML 伪影不能泄漏到最终 Markdown

- 这条规则约束的是：arXiv official HTML 路径需要清理明确的 LaTeXML 转换伪影，包括 `Refer to caption` 图片占位 alt、重复 footnote marker、裸 `****` 表格标题、`Column N` 占位表头、重复分组行、可见 list marker、TeX annotation 内部嵌套 `$...$` 定界符、普通 prose 的源 HTML 硬换行和未定义宏噪声。
- 如果违反，用户会看到：正文里残留 `<sup>1</sup><sup>1</sup>1`、`- •`、`\addsec`、`\hspace{0pt}`、`****`、`Column 1`，普通段落被源 HTML 换行切碎，公式因 `\text{... $x>x_{\tau}$ ...}` 被 Markdown/KaTeX 提前截断，或者图片 alt 被长数学 caption 截断。
- 它对应的阶段是：`html-cleanup`、`table-rendering`、`markdown-normalization`、`final-rendering`。
- Owner：`paper_fetch.providers.arxiv` 与共享 `paper_fetch.extraction.html.tables` / `paper_fetch.providers._html_section_markdown`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06665v1/original.html`](../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06665v1/original.html)
  - 这个样本覆盖 footnote marker、空 label 表格、首行标题推断和多图 caption。
- 边界说明：
  - 清理只针对确定的转换伪影；真实正文中的强调、项目符号、脚注内容、表格数据、display math、代码块和独立图片块必须保留必要换行。
  - official HTML 缺失的内容不从 PDF 猜测重建。

<a id="rule-stable-frontmatter-order"></a>
### 前言摘要族的顺序与去重必须稳定

- 这条规则约束的是：teaser、`Significance`、`Structured Abstract`、`Abstract` 这类前言摘要块一旦已经被识别出来，就必须在最终 markdown 里按阅读顺序稳定出现，不能重复注回正文；只有在确实需要把前言和正文切开时，才插入一次 `## Main Text`。
- 如果违反，用户会看到：同一段摘要在前言和正文里各出现一遍，或者 `Significance`、`Structured Abstract`、`Abstract` 顺序错乱，甚至正文开头被摘要块挤占。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`markdown-normalization`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.providers._atypon_browser_workflow_postprocess` 与 `paper_fetch.models.ArticleModel`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_science.abp8622/original.html`](../tests/fixtures/golden_criteria/10.1126_science.abp8622/original.html)
  - 这个样本能证明 Science frontmatter 里的 teaser、`Structured Abstract`、`Abstract` 和正文边界需要稳定保留。
- 边界说明：
  - 这条规则不是要求所有文章都必须同时出现 teaser、`Significance`、`Structured Abstract` 和 `Abstract`。
  - 它约束的是“已识别前言块的顺序、去重和正文边界”，不是要求每个 publisher 都使用同一套标题名称。

<a id="rule-keep-parallel-multilingual-abstracts"></a>
### 并行多语言摘要要并存，单语非英文正文不能被误删

- 这条规则约束的是：如果页面或 XML 里明确存在并行的多语言摘要块，就要把它们都保留下来；如果只有单语的非英文摘要或正文，也必须原样保留，不能因为语言过滤把整篇文章删空。
- 如果违反，用户会看到：双语摘要只剩一种语言，或者葡萄牙语、西班牙语这类非英文正文整块消失，看起来像抓取失败。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`markdown-normalization`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.extraction.html.language` 与 provider abstract extraction adapters（`paper_fetch.providers.atypon_browser_workflow` / `paper_fetch.providers._article_markdown_xml`）。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.16386/bilingual.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16386/bilingual.html)
  - [`../tests/fixtures/golden_criteria/10.1007_s13158-025-00473-x/bilingual.html`](../tests/fixtures/golden_criteria/10.1007_s13158-025-00473-x/bilingual.html)
  - [`../tests/fixtures/golden_criteria/10.1016_S1575-1813(18)30261-4/bilingual.xml`](<../tests/fixtures/golden_criteria/10.1016_S1575-1813(18)30261-4/bilingual.xml>)
  - 这些样本覆盖 Wiley、Springer 和 Elsevier 的稳定双语摘要场景；其他 provider 的并行摘要直接见对应测试。
- 边界说明：
  - 这条规则只约束结构上已经能识别为并行语言变体的块，不承诺自动识别所有翻译关系。
  - 它也不是说站点里的所有语言切换器、导航文案或重复 chrome 文本都要保留。

<a id="rule-keep-data-availability-once"></a>
### Availability section contract 必须保留、归类、排除正文度量并适配 hints

- 这条规则约束的是：`Data Availability`、`Code Availability`、`Software Availability`、`Data, Materials, and Software Availability` 这类 availability 声明一旦被结构信号识别，就必须作为 retained non-body section 保留且最终只出现一次；纯 `Data Availability` 映射为 `data_availability`，纯 `Code Availability` / `Software Availability` 映射为 `code_availability`，混合标题保留完整内容并归入稳定 availability kind；`data_availability` 和 `code_availability` 不计入 fulltext body metrics；provider 传入的 dict、对象或 `SectionHint` dataclass hints 必须按同一 heading key 和 declared order 适配。
- 如果违反，用户会看到：数据或代码可用性声明完全消失、重复出现、被误当成正文撑起 fulltext 判定、不同 provider 下 kind 不稳定，或结构 hint 已经标明 availability 但最终仍按普通正文渲染。
- 它对应的阶段是：`availability-quality`、`section-classification`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.extraction.section_hints`、`paper_fetch.quality.html_availability` 与 `paper_fetch.models.ArticleModel` retained non-body section 渲染。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html)
  - 这个样本能证明 PNAS 的 `Data, Materials, and Software Availability` 需要单独保留且不能重复。
  - [`../tests/fixtures/golden_criteria/10.1038_s43247-024-01885-8/original.html`](../tests/fixtures/golden_criteria/10.1038_s43247-024-01885-8/original.html)
  - 这个样本能证明 Springer / Nature HTML 里的 `Data availability` 与 `Code availability` 都需要从正文外 back matter 补回。
  - [`../tests/fixtures/golden_criteria/10.1016_j.rse.2025.114648/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.rse.2025.114648/original.xml)
  - 这个样本能证明 Elsevier XML 的 `ce:data-availability` 与普通 `Code availability` section 都需要归入共享 availability kind。
  - [`../tests/fixtures/golden_criteria/_scenarios/availability_body_metrics/code_availability.md`](../tests/fixtures/golden_criteria/_scenarios/availability_body_metrics/code_availability.md)
  - [`../tests/fixtures/golden_criteria/_scenarios/section_hints_availability/article.md`](../tests/fixtures/golden_criteria/_scenarios/section_hints_availability/article.md)
  - [`../tests/fixtures/golden_criteria/_scenarios/section_hints_availability/section_hints.json`](../tests/fixtures/golden_criteria/_scenarios/section_hints_availability/section_hints.json)
  - 两个 `_scenarios/` 目录分别锁住“只有 abstract + code availability 时仍应判为 abstract-only 且保留 availability”，以及 dict / object / dataclass hint 形态和 declared order；它们不是 DOI 级真实 replay。
- 边界说明：
  - 这条规则不是要求所有 back matter 都必须保留；`Acknowledgements`、`Research Funding`、`Statement of Competing Interests`、`Electronic Supplementary Material` 这类结构标题会归入 back matter / supplementary 语义，不计入正文充分性。`Permissions` 和 `Open Access` 归入 auxiliary / chrome，见 [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)。
  - 它只约束“已经被结构信号识别成 availability 的内容”；如果上游只剩普通标题文本且没有结构信号，仍可能先按一般正文节处理。
  - 结构信号优先于单一 DOI 现象；fixture 只是证明样本，不构成 DOI 或 publisher 特判。

<a id="rule-availability-section-kind-mapping"></a>
### 兼容锚点：Availability 标题必须映射到稳定 section kind

> 参见 [Availability section contract 必须保留、归类、排除正文度量并适配 hints](#rule-keep-data-availability-once)。

兼容锚点保留用于 manifest、测试标记和外部引用。

<a id="rule-availability-excluded-from-body-metrics"></a>
### 兼容锚点：Availability 不计入正文充分性度量

> 参见 [Availability section contract 必须保留、归类、排除正文度量并适配 hints](#rule-keep-data-availability-once)。

兼容锚点保留用于 manifest、测试标记和外部引用。
覆盖测试包括 [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_keeps_code_availability_without_counting_it_as_fulltext`。

<a id="rule-section-hints-normalize-availability"></a>
### 兼容锚点：Section hint 必须稳定适配 availability 节

> 参见 [Availability section contract 必须保留、归类、排除正文度量并适配 hints](#rule-keep-data-availability-once)。

兼容锚点保留用于 manifest、测试标记和外部引用。HTML semantics 与 `ArticleModel` 的解耦边界见 [`architecture/overview.md` 的 Extraction 层](architecture/overview.md#6-extraction-层)。
覆盖测试包括 [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_article_from_markdown_coerces_dict_object_and_section_hint_in_declared_order`。

<a id="rule-keep-headingless-body-flat"></a>
### 无节标题正文必须保持扁平

- 这条规则约束的是：当文章正文本来就直接以连续段落展开、没有可靠的 body heading 时，组装和渲染阶段不能人为包一层重复标题、`## Full Text` 或同义伪节；如果需要区分前言和正文，最多只插入一次 `## Main Text` 作为边界。
- 如果违反，用户会看到：commentary、perspective 这类文章被套上并不存在的章节壳，或者文章标题又在正文里重复出现一次。
- 它对应的阶段是：`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.models.ArticleModel`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_science.aeg3511/original.html`](../tests/fixtures/golden_criteria/10.1126_science.aeg3511/original.html)
  - 这个样本能证明无显式正文小节时，文章正文应保持扁平展开而不是被包成伪章节。
- 边界说明：
  - 这条规则不是说 `## Main Text` 永远不能出现。
  - 它约束的是“没有可靠正文节标题时不要硬造一层节结构”，不是禁止在前言和正文之间加一个必要的边界标题。

<a id="rule-preserve-inline-semantics-in-body-and-tables"></a>
### 正文、标题和表格里的行内语义格式不能被打平或拆裂

- 这条规则约束的是：标题、节标题、frontmatter、正文段落、图表 caption 和 Markdown 表格单元格里已经识别出的上下标、斜体变量、变量下标和 inline MathML operator，必须先保留为 text / citation / sup-sub / math / br 等结构化 inline token，再由 shared joiner 或 provider-owned inline renderer 统一决定空格；不能在清洗或渲染时被打平成普通空格文本，也不能被错误地拆成断开的 token。行内 HTML spacing 只在 citation、括号脚注和高置信 symbol-shape tight 场景收紧，默认保留 prose 空格。
- 如果违反，用户会看到：`CO<sub>2</sub>` 变成 `CO 2`、`TCID<sub>50</sub>` 变成 `TCID50`，`of <sup>6</sup>Li` 变成 `of<sup>6</sup>Li`，`*h*<sub>0</sub>` 变成 `h0`，或者 `*x*` 和 `<sub>i</sub>` 被拆散到两行，看起来像坏标题、坏表格或坏公式。
- 它对应的阶段是：`html-cleanup`、`table-rendering`、`markdown-normalization`、`final-rendering`。
- Owner：`paper_fetch.extraction.html.inline`；AMS 覆盖由 `paper_fetch.providers._ams_html` compatibility facade 暴露，canonical owner 是 `paper_fetch.providers._ams_dom` / `paper_fetch.providers._ams_markdown`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_science.abp8622/original.html`](../tests/fixtures/golden_criteria/10.1126_science.abp8622/original.html)
  - 这个样本能证明 frontmatter / summary / main text 里的 `CO<sub>2</sub>` 和 `log<sub>10</sub>` 需要保持原有上下标语义。
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2406303121/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2406303121/original.html)
  - 这个样本能证明 PNAS 表格单元格和正文里的上下标、变量符号、单位格式需要保持原有行内语义。
  - [`../tests/fixtures/golden_criteria/10.1175_aies-d-23-0093.1/original.html`](../tests/fixtures/golden_criteria/10.1175_aies-d-23-0093.1/original.html)
  - [`../tests/fixtures/golden_criteria/10.1175_jpo-d-23-0234.1/original.html`](../tests/fixtures/golden_criteria/10.1175_jpo-d-23-0234.1/original.html)
  - 这些 AMS 样本能证明正文短下标、caption MathML 和图注上下标不能退化成 `νn`、`ϕ 2` 或紧贴 prose 括号。
    - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_inline_normalization_is_shared_for_body_heading_and_table_text`
    - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_inline_normalization_preserves_isotope_superscript_spacing`
    - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_inline_normalization_tightens_high_confidence_sup_sub_spacing`
    - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_inline_token_joiner_is_shared_by_body_heading_and_table_cells`
    - [`../tests/unit/test_html_shared_helpers.py`](../tests/unit/test_html_shared_helpers.py) 中的 `test_inline_math_operators_are_preserved_in_body_and_table_cells`
    - [`../tests/unit/test_atypon_browser_workflow_postprocess_units.py`](../tests/unit/test_atypon_browser_workflow_postprocess_units.py) 中的 `test_extract_atypon_browser_workflow_markdown_normalizes_title_subscript_line_breaks`
  - Provider 覆盖：
    - [`../tests/unit/test_springer_html_regressions.py`](../tests/unit/test_springer_html_regressions.py) 中的 `test_springer_markdown_preserves_subscripts_in_section_headings`
    - [`../tests/unit/test_atypon_browser_workflow_markdown.py`](../tests/unit/test_atypon_browser_workflow_markdown.py) 中的 `test_pnas_full_fixture_keeps_data_availability_and_renders_table_markdown`
    - [`../tests/unit/test_atypon_browser_workflow_postprocess.py`](../tests/unit/test_atypon_browser_workflow_postprocess.py) 中的 `test_pnas_real_fixture_renders_table_and_inline_cell_formatting`
    - [`../tests/unit/test_atypon_browser_workflow_markdown.py`](../tests/unit/test_atypon_browser_workflow_markdown.py) 中的 `test_wiley_full_fixture_extracts_body_sections_from_real_html`
    - [`../tests/unit/test_atypon_browser_workflow_postprocess.py`](../tests/unit/test_atypon_browser_workflow_postprocess.py) 中的 `test_science_real_frontmatter_fixture_preserves_structured_summaries_and_main_text`
    - [`../tests/unit/test_ams_provider.py`](../tests/unit/test_ams_provider.py) 中的 `test_ams_aies_fixture_preserves_inline_mathml_formulas`
    - [`../tests/unit/test_ams_provider.py`](../tests/unit/test_ams_provider.py) 中的 `test_ams_caption_inline_markup_is_preserved`
    - [`../tests/unit/test_ams_provider.py`](../tests/unit/test_ams_provider.py) 中的 `test_ams_inline_renderer_preserves_body_subscripts_and_spacing`
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_split_inline_variable_subscripts_are_rejoined_in_paragraphs`
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_inline_boundary_newlines_are_normalized`
- 边界说明：
  - 这条规则只约束已经识别成行内语义的内容，不承诺对复杂公式、整段 MathML 或所有数学符号做完整排版。
  - 它也不是说所有英文字母组合都必须自动识别成变量加下标。
  - AMS 的 `inline-formula` 常把真实 MathML 放在 `script[type="math/mml"]`，caption 和正文也常包含斜体变量、连续下标和上下标后的 prose 括号；AMS 归一化必须先暴露这些结构，再交给 AMS 专用 inline renderer 和共享公式转换器。

<a id="rule-ams-footnotes-stay-linked-to-body-markers"></a>
### AMS/BAMS 脚注必须集中在 Footnotes 小节

- 这条规则约束的是：AMS/BAMS HTML 中 `.footnoteGroup` 里的正文脚注要作为正文说明区的一部分集中输出，而不是在正文末尾散落成无标题 URL 或孤立段落。正文中的 `<sup>n</sup>` 标记必须保留，脚注条目使用 `<sup>n</sup> text`。
- 如果违反，用户会看到：正文出现 `<sup>1</sup>` 但找不到对应脚注，或者 `https://www.top500.org.`、`https://git-scm.com/docs.` 这类脚注 URL 直接漂在 Acknowledgments 前面。
- 它对应的阶段是：`html-cleanup`、`markdown-normalization`。
- Owner：`paper_fetch.providers._ams_html` compatibility facade；canonical owner 是 `paper_fetch.providers._ams_dom` / `paper_fetch.providers._ams_markdown`。
- 代表性 HTML：
  - [`../tests/fixtures/golden_criteria/10.1175_bams-d-24-0223.1/original.html`](../tests/fixtures/golden_criteria/10.1175_bams-d-24-0223.1/original.html)
- 边界说明：
  - 这条规则只处理 AMS/BAMS 显式脚注组，不把 References、Acknowledgments、Data availability 或普通 URL 段落识别成脚注。
  - 测试覆盖度低：当前只有 BAMS `footnoteGroup` fixture 锁住该行为；后续遇到非 BAMS AMS 脚注结构时应补 provider-specific replay。

<a id="rule-readable-equation-caption-spacing"></a>
### 公式块和图注句子的块间距必须可读

- 这条规则约束的是：`**Equation n.**` 和对应的 `$$...$$` display math 之间必须保持稳定的块级换行，公式后的解释句和 figure caption 的后续句子也不能被粘成一整块坏文本。
- 如果违反，用户会看到：`**Equation 1.**$$`、`$$where *P* is precipitation`、`2020.Time series` 这类明显粘连的坏渲染。
- 它对应的阶段是：`markdown-normalization`、`final-rendering`。
- Owner：`paper_fetch.providers._wiley_html`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_science.adp0212/original.html`](../tests/fixtures/golden_criteria/10.1126_science.adp0212/original.html)
  - 这个样本能证明公式标签、display math、解释句和 figure caption 之间都需要稳定的块边界。
- 边界说明：
  - 这条规则不保证公式语义一定完全正确。
  - 它约束的是“公式块和图注句子的可读边界不能坏掉”，不是对编号体系或数学求值做承诺。
  - 当前直接 DOI 证据样本来自 Science；PNAS 后处理测试覆盖同一共享 spacing policy，后续不为凑数强行新增 fixture。

<a id="rule-preserve-formula-image-fallbacks"></a>
### HTML 公式图片 fallback 必须保留并进入资产链路

- 这条规则约束的是：HTML 中的 MathML、publisher fallback span、inline equation image 和 display equation image 要尽量转成可读公式；如果 MathML 无法转换或公式本来只以图片存在，就保留 `![Formula](...)`，并把它作为 `kind="formula"` 的正文资产候选进入下载和本地链接改写流程。
- display formula 的候选优先级必须是：可转换的 MathML / 显式 TeX、公式图片、非编号可见文本、`[Formula unavailable]`。`(1)`、`Equation 1.` 这类编号只属于 equation label，不能冒充 LaTeX，也不能抢在已有公式图片之前生成 `$$ (1) $$` 伪公式。
- 已经形成的完整 `$$ ... $$` display-math 块属于 Markdown 辅助块，正文后处理不能再用“短全大写 front matter”启发式把它删除；单独的 `$$` 围栏仍按原有块边界规则处理。
- 公式图片 URL 中的强信号（如 `_IEqN_HTML`、`_EquN_HTML`、`math-*`）优先于 figure-context 排除，即使裸公式图片位于 figure caption 中也必须进入 formula 资产链路；只有 URL 没有公式信号时，figure / Silverchair figure wrapper 才用于避免把普通正文图按文件名、alt/title 或 caption 中的 `Equation` 误判为公式。
- 只有公式 bitmap 候选且 publisher 没有更大版本时，下载结果继续如实记录 `download_tier="preview"`，同时设置 `preview_accepted=true`；它不伪装成 full-size，也不单独产生 `asset_fidelity_degraded`。
- 如果违反，用户会看到：公式静默消失、编号被渲染成 `$$ (1) $$` 伪公式、被渲染成 `[Formula unavailable]` 的假失败，或者正文里残留远程公式图片链接且无法跟下载资产对应。
- 它对应的阶段是：`html-cleanup`、`formula-rendering`、`asset-discovery`、`markdown-normalization`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.extraction.html.formula_rules`、`paper_fetch.providers.atypon_browser_workflow.formulas` 与 Atypon browser-workflow Markdown postprocess。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.15322/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.15322/original.html)
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.16011/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16011/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_nature12915/original.html`](../tests/fixtures/golden_criteria/10.1038_nature12915/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_nature13376/original.html`](../tests/fixtures/golden_criteria/10.1038_nature13376/original.html)
  - 这些样本分别覆盖 Wiley 无标签与有 `(N)` 标签的 fallback formula image、早期 Nature display equation 图片 `_EquN_HTML.jpg` 和早期 Nature inline equation image `_IEqN_HTML.jpg`。
- 边界说明：
  - 这条规则不是保证所有 HTML 公式都能转成 LaTeX；保留公式图片 fallback 是正确输出。
  - 只有编号而没有可转换结构、公式图片或其它公式文本时，应保留 equation label 并明确输出 `[Formula unavailable]`，不能根据编号猜造表达式。
  - Nature display equation 结构 `c-article-equation` / `c-article-equation__content` 和 `_Equ1_HTML.jpg` 这类 URL 必须渲染为 `![Formula](...)` 并进入 `kind="formula"` 资产链路；其中 publisher-specific class / selector 只通过 `ProviderHtmlRules` 和显式 `noise_profile="springer_nature"` 生效，不进入 generic 默认 token。
  - 只有看起来属于公式容器、公式 URL、公式 fallback 属性或公式 alt/title 的图片才进入公式资产链路，普通 `FigN_HTML` 正文图片仍按 figure/table 处理。
  - 普通 figure 的文件名或图注只是提到 equation 时仍属于 figure；figure caption 中显式命中 `math-N`、`_IEqN` 或 `_EquN` 的图片才覆盖 figure-context 排除。

<a id="rule-formula-latex-normalization"></a>
### LaTeX normalization 必须产出 KaTeX 可渲染表达

- 这条规则约束的是：公式转换后的 LaTeX 要在公共 normalize 层修复 publisher-specific 输出，例如 MathML `mtext` 里出版商转义的标识符下划线、`\updelta` 这类 upright Greek 宏、`\mspace{Nmu}` 这类 KaTeX 不兼容间距，以及无语义的零宽 spacing（如 `\hspace{0pt}` 和 MathML 零宽连接符）。
- 如果违反，用户会看到：`M\_NDVI` 渲染成 `M\textbackslash\_NDVI`，`\updelta` 无法渲染，公式因为 KaTeX 不支持的间距宏而失败，或者正文 / caption 里残留 `\hspace{0pt}`、`S​O` 这类不可读噪声。
- 它对应的阶段是：`formula-rendering`、`markdown-normalization`、`final-rendering`。
- Owner：`paper_fetch.formula.convert`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/_scenarios/formula_latex_normalization/samples.json`](../tests/fixtures/golden_criteria/_scenarios/formula_latex_normalization/samples.json)
  - `_scenarios/formula_latex_normalization` 锁住 publisher-specific LaTeX normalize 分支；它不是 DOI 级真实 replay。
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_repairs_identifier_escaped_underscores`
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_does_not_globally_replace_textbackslash`
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_rewrites_upgreek_macros`
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_rewrites_mspace_for_katex`
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_removes_only_zero_width_spacing`
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_scenario_samples_are_katex_compatible`
    - [`../tests/unit/test_arxiv_provider.py`](../tests/unit/test_arxiv_provider.py) 中的 `test_html_route_normalizes_math_without_duplicate_fallback_text`
- 边界说明：
  - 这条规则不承诺所有 MathML 都能转换成功；失败占位和 provider-specific inline/display 行为由具体公式渲染规则约束。
  - `\textbackslash\_` 只修复夹在标识符字符之间的窄范围场景，不能全局替换正常文本里的 `\textbackslash`。`\mspace{Nmu}` 只在 `mu` 单位时改写为 `\mkernNmu`，其它单位保留原样；`\hspace{0pt}` 这类零宽 spacing 会移除，但非零宽 `\hspace{...}` 必须保留。

## Springer

- 共享规则另见：
  - [HTML fulltext / abstract-only 判定必须和用户可见访问状态一致](#rule-html-availability-contract)
  - [Provider 自有作者与摘要信号必须进入最终文章元数据](#rule-provider-owned-authors)
  - [并行多语言摘要要并存，单语非英文正文不能被误删](#rule-keep-parallel-multilingual-abstracts)
  - [Availability section contract 必须保留、归类、排除正文度量并适配 hints](#rule-keep-data-availability-once)
  - [正文已内联 figure 时避免重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)
  - [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope)
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)
  - [正文、标题和表格里的行内语义格式不能被打平或拆裂](#rule-preserve-inline-semantics-in-body-and-tables)
  - [已下载的正文图片和公式图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links)
  - [表格能展平就转 Markdown 表，展不平就退成可读列表](#rule-table-flatten-or-list)
  - [HTML 公式图片 fallback 必须保留并进入资产链路](#rule-preserve-formula-image-fallbacks)
  - [下载资产必须保留诊断字段](#rule-asset-download-diagnostic-fields)
- 不适用 / 部分适用说明：
  - [浏览器工作流图片下载必须使用 shared browser 主链路](#rule-browser-primary-image-download-path) 不适用于 Springer direct HTML；Springer 图片下载走 direct HTML 资产链路。
  - [前言摘要族的顺序与去重必须稳定](#rule-stable-frontmatter-order) 只在 Springer/Nature 页面暴露可识别 frontmatter 结构时适用，不要求所有 Springer 页面生成前言族。

<a id="rule-springer-chrome-heading-normalization"></a>
### 兼容锚点：Springer chrome 剪枝与编号标题空格规范化

> 参见 [Springer article root 必须避开站点 chrome](#rule-springer-article-root-chrome-pruning) 和 [Springer 编号标题必须规范空格](#rule-springer-numbered-heading-spacing)。

兼容锚点保留用于 manifest 和外部引用。当前规则分别约束 article-root / chrome 剪枝，以及编号标题 inline span 的空格规范化。

<a id="rule-springer-article-root-chrome-pruning"></a>
### Springer article root 必须避开站点 chrome

- 这条规则约束的是：Springer / Springer Nature HTML 提取必须先选到可信 article root，再剪掉保存文章、期刊 CTA、Aims and scope、Submit manuscript、重复标题块、`About this article` / 权限许可等站点 chrome；正文之外的科学 back matter 只保留 `Acknowledgements`、`Data Availability`、`Author Contributions` 这类论文内容节。
- 如果违反，用户会看到：多语言摘要和正文之间插入 `Save article`、`View saved research`、重复论文标题或 Creative Commons 许可长文。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`html-cleanup`、`section-classification`。
- Owner：`paper_fetch.extraction.html.renderer`、`paper_fetch.providers.html_springer_nature`、`paper_fetch.providers._springer_html` compatibility facade 与 canonical `paper_fetch.providers._springer_dom` / `paper_fetch.providers._springer_markdown`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html`](../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html)
  - [`../tests/fixtures/golden_criteria/10.1007_s13158-025-00473-x/bilingual.html`](../tests/fixtures/golden_criteria/10.1007_s13158-025-00473-x/bilingual.html)
  - 这两个样本分别覆盖 Springer classic chrome 泄漏，以及双语摘要后进入正文时不能重复标题和 CTA。
- 边界说明：
  - 这条规则过滤的是站点框架和操作入口，不是删除论文正文里自然出现的相同词面。
  - Creative Commons 许可剪枝必须命中真实 `creativecommons.org/licenses/...` 链接，并且不能因为子节点有许可链接而删除 `article` / `main` / `body` 这类正文根节点。
  - `springer_nature` 是显式注册的 shared noise profile；Springer/Nature 调用 shared Markdown cleanup 时不得静默回退到 generic profile。

<a id="rule-springer-numbered-heading-spacing"></a>
### Springer 编号标题必须规范空格

- 这条规则约束的是：Springer / Springer Nature HTML 中由多个 inline span 拼出的编号标题，最终必须渲染成带空格的真实标题。
- 如果违反，用户会看到：`## 1Introduction`、`### 3.1Glaciers` 这类编号和标题文本粘连的坏 Markdown。
- 它对应的阶段是：`html-cleanup`、`markdown-normalization`、`final-rendering`。
- Owner：`paper_fetch.providers.html_springer_nature`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html`](../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html)
  - 这个样本覆盖 Springer classic 编号标题由 inline span 拼接时的空格规范化。
- 边界说明：
  - 它不要求所有编号标题都改写成某个统一编号体系，只要求已存在的编号和标题文本不能粘连或重复。

<a id="rule-nature-main-content-direct-children"></a>
### 兼容锚点：Nature main-content 直接子节点遍历规则

> 参见 [Springer / Nature main-content 必须按直接子节点顺序进入正文](#rule-springer-main-content-direct-children)。

兼容锚点保留用于 manifest 和外部引用。

<a id="rule-springer-main-content-direct-children"></a>
### Springer / Nature main-content 必须按直接子节点顺序进入正文

- 这条规则约束的是：Nature HTML 的 `div.main-content` 不能只因为存在直接 `section` 就只渲染这些 `section`；必须按直接子节点顺序处理正文 `div.c-article-section__content`、可渲染正文 `div` 和 `section`，否则 Matters Arising 这类页面会把正文段落漏掉，只剩 `Reporting summary`。
- 如果违反，用户会看到：`Forest age and water yield` 这类文章缺少真正正文，只剩 `Reporting summary` / Extended Data Table 占位，`Data availability` 也可能被错误地当成唯一正文。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`section-classification`。
- Owner：`paper_fetch.providers.html_springer_nature`、`paper_fetch.providers._springer_html` compatibility facade 与 canonical `paper_fetch.providers._springer_dom`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1038_s41586-020-1941-5/original.html`](../tests/fixtures/golden_criteria/10.1038_s41586-020-1941-5/original.html)
  - [`../tests/fixtures/golden_criteria/_scenarios/springer_main_content_direct_children/original.html`](../tests/fixtures/golden_criteria/_scenarios/springer_main_content_direct_children/original.html)
  - 真实 replay 覆盖 `main-content` 中正文 `div` 位于 `Reporting summary` section 之前的结构；scenario 锁住直接子节点顺序的最小形态。
- 边界说明：
  - 当前有一份 Nature Matters Arising replay 和一个最小 scenario；同类 Springer / Nature main-content 遍历改动仍应优先补第二个 DOI 级 fixture。
  - 结构信号优先于单一 DOI：规则看的是 `main-content` 直接子节点顺序和正文容器形态，不以 `10.1038_s41586-020-1941-5` 本身作为特判。
  - 正文外的 `Data availability` / `Code availability` 仍然允许从 scientific back matter 补回，但已经在正文遍历中出现的 availability 节不能重复输出。

<a id="rule-springer-original-html-artifact"></a>
### 兼容锚点：Springer 原始 article HTML 落盘

> 参见 [`providers.md` 的 Provider artifact/storage 说明](providers.md#provider-原始-html-artifact)。

兼容锚点保留用于外部引用。原始 HTML 文件名和下载目录形态属于 `artifact-storage`，不是提取 / 渲染规则。

<a id="rule-springer-supplementary-scope"></a>
### 兼容锚点：Springer supplementary scope

> 参见 [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope) 的 provider 差异表。

兼容锚点保留用于 manifest、测试标记和外部引用。Springer / Nature 的 `Source Data` 仍通过 provider-specific helper 独立分流到 `source_data/`。

<a id="rule-springer-access-hint-disclaimer"></a>
### 访问提示、预览语和 AI 免责声明不能混进正文

- 这条规则约束的是：publisher 页面用来告诉用户“这里只是预览”“这是访问提示”“这段 alt 可能由 AI 生成”的站点说明，不能被当成论文正文或摘要输出。
- 如果违反，用户会看到：摘要或正文里多出 `This is a preview of subscription content`、`The alternative text for this image may have been generated using AI.` 这类明显不是论文内容的提示句。
- 它对应的阶段是：`html-cleanup`、`markdown-normalization`。
- Owner：`paper_fetch.providers.html_springer_nature`、`paper_fetch.providers._springer_html`、`paper_fetch.providers._springer_dom` / `paper_fetch.providers._springer_markdown` 与 `paper_fetch.extraction.html._runtime`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/block/10.1007_s00382-018-4286-0/raw.html`](../tests/fixtures/block/10.1007_s00382-018-4286-0/raw.html)
  - [`../tests/fixtures/golden_criteria/10.1038_s44221-022-00024-x/original.html`](../tests/fixtures/golden_criteria/10.1038_s44221-022-00024-x/original.html)
  - 这两个样本分别覆盖 Springer paywall preview 句子和 Nature figure AI disclaimer。
- 边界说明：
  - 这条规则删除的是明显的站点提示，不是删除所有提到 `preview`、`AI`、`generated` 的正常论文句子。
  - 如果某段话本来就是论文正文内容，即使包含相同词面，也不能仅凭关键词去掉。

<a id="rule-springer-caption-precedence"></a>
### 正文 figure 优先相信正式 caption，不相信噪声 fallback

- 这条规则约束的是：图已经有正式图题或图注时，渲染链必须优先使用这些正式内容，不能再把站点塞进来的 `data-title`、`alt`、朗读文本、下载入口和展示控件重新拼回图注里。
- 如果违反，用户会看到：同一张图的标题后面又多出一段重复、破碎或格式错乱的说明，常见表现是残留的 LaTeX、拆开的希腊字母、重复 caption、`PowerPoint slide` 或 `Full size image`。
- 它对应的阶段是：`asset-discovery`、`final-rendering`。
- Owner：`paper_fetch.providers._springer_html` compatibility facade、canonical `paper_fetch.providers._springer_dom` / `paper_fetch.providers._springer_assets` / `paper_fetch.providers._springer_markdown` 与 `paper_fetch.providers.html_springer_nature`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1038_nature12915/original.html`](../tests/fixtures/golden_criteria/10.1038_nature12915/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_nature13376/original.html`](../tests/fixtures/golden_criteria/10.1038_nature13376/original.html)
  - 这两个早期 Nature 样本覆盖正式 caption 存在时清理 `PowerPoint slide` / `Full size image` 这类控件文案。
- 边界说明：
  - 这条规则不是说 `data-title` 或 `alt` 永远不能用。
  - 当 figure 真正缺少 caption / description 时，这些字段仍然可以作为兜底来源。
  - `PowerPoint slide`、`Full size image` 这类控件文案的兜底过滤见 [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)；本规则只负责 caption 来源选择。

<a id="rule-springer-methods-summary"></a>
### 早期 Nature 的 Methods Summary / Methods 结构必须归一且不重复

- 这条规则约束的是：早期 Nature 文章里如果同时存在 `Methods Summary` 和 `Online Methods` / 早期方法结构证据，最终结构必须归一成“`Methods Summary` 一次、`Methods` 一次”，不能重复堆出两个同义方法章节。
- 如果违反，用户会看到：文档里出现两个 `Methods Summary`，或者 `Online Methods`、`Methods` 混着出现，方法学结构会看起来像重复拼装。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.providers._springer_html` compatibility facade、canonical `paper_fetch.providers._springer_assets` / `paper_fetch.providers._springer_markdown` 与 `paper_fetch.models.ArticleModel`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1038_nature12915/original.html`](../tests/fixtures/golden_criteria/10.1038_nature12915/original.html)
  - 这个样本能证明早期 Nature 的 `Methods Summary` 与 `Online Methods` 需要按正文结构归一处理。
- 边界说明：
  - 这条规则不是要求所有论文都必须出现 `Methods Summary`。
  - 结构信号优先于早期 Nature 单 DOI 样本；`10.1038_nature12915` 只是证明早期页面形态，规则依据是同篇 parsed sections、section hints 或 source selector 暴露的方法结构。
  - 只有同篇 parsed sections 同时存在 `Methods Summary` 与 `Online Methods`，或 section hints / source selector 体现早期 Nature 方法结构时，才把 stripped `Methods Summary` body section 归一为 `Methods`。单独存在的真实 `Methods Summary` 正文节必须保留原 heading。

<a id="rule-springer-inline-table"></a>
### 正文内联 table 占位必须被真实表格替换，替不出来也不能把占位符漏给用户

- 这条规则约束的是：正文里如果先放了一个 table 占位，后续拿到 table page 时要把真实表格插回原位置；如果 table page 最终没拿到真正的表，也不能把内部占位符直接漏给用户。对于 Springer/Nature inline table 节点，只要 label 是 `Extended Data Table N` 且存在匹配的 `/tables/N` 页面链接，若 table page 实际是图片响应或只能从 HTML 中提取 full-size image，应输出 `kind="table"` 的 table 图片资产；若解析失败，应输出明确的 `[Table body unavailable: ...]` 降级占位。
- 如果违反，用户会看到：正文里残留像 `PAPER_FETCH_TABLE_PLACEHOLDER` 这样的内部标记，Extended Data Table 直接消失，或者文章因为某个 table page 没拿到表就整体变成异常结果。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`table-rendering`、`asset-discovery`、`final-rendering`。
- Owner：`paper_fetch.providers.springer`、`paper_fetch.providers._springer_html` compatibility facade、canonical `paper_fetch.providers._springer_assets` 与 `paper_fetch.extraction.html.tables`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/original.html`](../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/table1.html`](../tests/fixtures/golden_criteria/10.1038_s43247-024-01295-w/table1.html)
  - [`../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html`](../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html)
  - [`../tests/fixtures/golden_criteria/10.1038_nature13376/original.html`](../tests/fixtures/golden_criteria/10.1038_nature13376/original.html)
  - [`../tests/fixtures/golden_criteria/10.1038_s41586-020-1941-5/original.html`](../tests/fixtures/golden_criteria/10.1038_s41586-020-1941-5/original.html)
  - 这几份样本分别覆盖“真实 Nature table page 被注回正文”、“Springer classic article 遇到坏 table page 也不能把占位符漏给用户”、早期 Nature Extended Data Table 图片 / 占位降级，以及非 `nature13376` 的 Extended Data Table 结构 fallback。
- 边界说明：
  - 这条规则不是要求所有 table page 都必须成功转出表格。
  - 它约束的是“成功时正确注回，失败时不把内部占位符暴露给用户，也不让整篇文章失败”；当原始站点只提供 Extended Data Table 图片时，图片 fallback 是正确输出，不是图表丢失。
  - 普通 `Table N` 不默认启用图片 fallback，避免把非 Extended Data Table 的坏表页误当成图片表格。

## Elsevier

- Elsevier XML 元素级映射总表另见 [`../references/elsevier_markdown_mapping.md`](../references/elsevier_markdown_mapping.md)；下面只保留当前主干必须维持的用户可见 Markdown 行为约束。
- 共享规则另见：
  - [Provider 自有作者与摘要信号必须进入最终文章元数据](#rule-provider-owned-authors)
  - [并行多语言摘要要并存，单语非英文正文不能被误删](#rule-keep-parallel-multilingual-abstracts)
  - [正文、标题和表格里的行内语义格式不能被打平或拆裂](#rule-preserve-inline-semantics-in-body-and-tables)
  - [CALS 多个 `tgroup` 必须按各自列定义独立渲染](#rule-xml-table-groups)
  - [Availability section contract 必须保留、归类、排除正文度量并适配 hints](#rule-keep-data-availability-once)
  - [正文已内联 figure 时避免重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)
  - [已下载的正文图片和公式图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links)
  - [LaTeX normalization 必须产出 KaTeX 可渲染表达](#rule-formula-latex-normalization)
- 不适用 / 部分适用说明：
  - [HTML fulltext / abstract-only 判定必须和用户可见访问状态一致](#rule-html-availability-contract) 不适用于 Elsevier XML 主路径；PDF fallback 的正文 Markdown 仍走共享 PDF 转换。
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise) 和 [HTML 公式图片 fallback 必须保留并进入资产链路](#rule-preserve-formula-image-fallbacks) 不适用于 Elsevier XML 主路径。
  - [浏览器工作流图片下载必须使用 shared browser 主链路](#rule-browser-primary-image-download-path) 不适用于 Elsevier 官方 XML/API。

<a id="rule-elsevier-formula-rendering"></a>
### 正文公式优先保留数学表达，locator 图片作为保真 fallback

- 这条规则约束的是：Elsevier XML 段落里的行内数学要留在正文行内，display formula 要单独渲染成公式块。若 `<formula>` 只通过 `<link locator="fx*">`（或 `xlink:href` 的末段）指向 `<objects>` 中的官方公式图片，渲染器必须按 object `ref` 选择最高优先级资源并在公式原位置输出图片；已下载时优先使用本地相对路径，`asset_profile=none` 时保留官方远程 URL。只有数学表达和官方图片都不存在时，才输出明确的 unavailable 占位并记录 `formula_missing`。
- 如果违反，用户会看到：段落里的单字母变量被误渲染成一串独立公式块，或者官方 XML 明明提供 fx 公式图却显示 `[Formula unavailable]`，甚至某个公式直接静默消失。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`formula-rendering`、`final-rendering`。
- Owner：`paper_fetch.providers._article_markdown_math` 与 `paper_fetch.providers._article_markdown_elsevier`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml)
  - [`../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2023.130125/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2023.130125/original.xml)
  - [`../tests/fixtures/golden_criteria/10.1016_j.uclim.2019.100528/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.uclim.2019.100528/original.xml)
  - [`../tests/fixtures/golden_criteria/_scenarios/elsevier_formula_inline_display/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_formula_inline_display/original.xml)
  - [`../tests/fixtures/golden_criteria/_scenarios/elsevier_formula_missing/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_formula_missing/original.xml)
  - real Elsevier XML 覆盖 display formula 渲染为公式块；`uclim` 样本锁住两个 locator 公式分别映射到官方 fx1/fx2 图片；两个 scenario 分别锁住 inline/display 混排和 conversion failure 占位分支。
- 边界说明：
  - 这条规则不是保证所有 Elsevier MathML 都能被完美转成 LaTeX。
  - locator 图片属于诚实的保真 fallback，不做 OCR、不伪造 LaTeX：每张图片计一次 `formula_fallback_count`，不计 `formula_missing_count`，文章总体质量仍为 `degraded`。
  - 公式上下文中的 `fx*` 按正文 `image` 处理；普通附录 Figure 使用的 `fx*` 仍保持 `appendix_image`，不能因公式兼容逻辑改变其位置或分类。
  - 它约束的是“行内和 display 数学不能混渲，失败时不能静默丢失”；公共 LaTeX 宏兼容处理见 [LaTeX normalization 必须产出 KaTeX 可渲染表达](#rule-formula-latex-normalization)。

<a id="rule-elsevier-supplementary-materials"></a>
### Supplementary data 不进正文，统一收进 `## Supplementary Materials`

- 这条规则约束的是：`Supplementary data` 这类补充材料显示块不能混进正文叙述里，而是要统一落到文末的 `## Supplementary Materials` 区域，并保留基本的标题和说明。
- 如果违反，用户会看到：正文突然插进一个补充材料下载入口，或者补充材料完全消失。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`asset-discovery`、`final-rendering`。
- Owner：`paper_fetch.providers._article_markdown_elsevier` 与 `paper_fetch.models.ArticleModel`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.ecolind.2024.112140/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.ecolind.2024.112140/original.xml)
  - [`../tests/fixtures/golden_criteria/_scenarios/elsevier_supplementary_display/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_supplementary_display/original.xml)
  - [`../tests/fixtures/golden_criteria/_scenarios/elsevier_supplementary_asset_only/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_supplementary_asset_only/original.xml)
  - real Elsevier XML 覆盖 `ce:e-component` supplementary locator 与下载文件映射；两个 scenario 分别锁住 display 排除正文和无 display 资产兜底。
- 边界说明：
  - real XML 锁住 `ce:e-component` 主干；两个 scenario XML 分别锁住 supplementary display 的正文排除行为，以及无 display 时已下载 supplementary 文件仍进入 Supplementary Materials。
  - 这条规则不是说 supplementary 资产不能下载或不能暴露给用户。
  - 它约束的是“补充材料不属于正文主体”，不是限制 supplementary 元数据的存在。
  - 当 `asset_profile='all'` 时，supplementary 应作为独立文件资产下载并落到 `section="supplementary"` / `download_tier="supplementary_file"`；它不属于正文 figure inline 逻辑，也不会进入 MCP inline `ImageContent`。

<a id="rule-elsevier-appendix-context"></a>
### Appendix figure/table 保持 appendix 语境，不因正文交叉引用被提到正文

- 这条规则约束的是：凡是已经处在 appendix 语境里的 figure 和 table，就要继续留在 appendix 里渲染；即使正文提到 `Fig. A1` 或 `Table A1`，也不能把这些 appendix 资产提前到正文区。
- 如果违反，用户会看到：正文里突然混入 appendix 图表，或者 appendix 内容被拆散后前后顺序错乱。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.providers._article_markdown_elsevier` 与 `paper_fetch.models.ArticleModel`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.rse.2026.115369/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.rse.2026.115369/original.xml)
  - 这份 real Elsevier XML 同时覆盖 appendix figure、appendix table 和正文中的 appendix 交叉引用。
- 边界说明：
  - 当前三个 owner 测试分别锁定 appendix figure、正文交叉引用顺序和 appendix table；新增 appendix 形态时应继续补独立测试。
  - 这条规则不是说正文里不能出现对 appendix 图表的交叉引用文字。
  - 它约束的是 appendix 资产的实际渲染位置和上下文，而不是正文文字是否能提到它们。

<a id="rule-elsevier-table-placement"></a>
### 兼容锚点：Elsevier 图表正文位置、去重和复杂表规范化

> 参见 [Elsevier 正文引用到的 figure / table 要就地插回](#rule-elsevier-inline-figure-table-placement)、[Elsevier 已消费图表不得在尾部重复追加](#rule-elsevier-consumed-figure-table-dedup) 和 [Elsevier 复杂 span 表必须区分成功规范化与异常降级](#rule-elsevier-complex-table-span-degradation)。

兼容锚点保留用于 manifest 和外部引用。

<a id="rule-elsevier-inline-figure-table-placement"></a>
### Elsevier 正文引用到的 figure / table 要就地插回

- 这条规则约束的是：Elsevier XML 正文里已经引用到的 figure / table 要尽量在引用位置附近渲染；没有正文锚点的浮动表才进入 `## Additional Tables`。
- 如果违反，用户会看到：正文提到 `Fig. 1` 或 `Table 1` 却找不到对应图表，阅读顺序被打断。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.providers._article_markdown_elsevier_document` 与 `paper_fetch.models.ArticleModel` structure rendering。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2021.126210/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2021.126210/original.xml)
  - [`../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml)
  - 这些 real Elsevier XML 覆盖正文图片插入和正文表格就地插回。
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_table_placement_contracts`
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_article_from_structure_preserves_inline_elsevier_figures`
- 边界说明：
  - 本规则不要求没有正文锚点的 float 强行插入正文；这类图表仍可进入 Additional Figures / Tables。

<a id="rule-elsevier-consumed-figure-table-dedup"></a>
### Elsevier 已消费图表不得在尾部重复追加

- 这条规则约束的是：已经在正文消费过的 Elsevier 图表必须通过 render state 或 consumed key 从尾部资产附录里过滤掉。
- 如果违反，用户会看到：正文已经有的表在文末又以只有 caption 的 `## Tables` 重复出现。
- 它对应的阶段是：`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.models.ArticleModel` render state 与 `paper_fetch.providers._article_markdown_elsevier` asset planning。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2023.130125/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2023.130125/original.xml)
  - 这个样本覆盖已消费表格避免尾部重复。
    - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_to_ai_markdown_skips_inline_assets_and_labels_additional_tables`
  - Provider 覆盖：
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_table_placement_contracts`
- 边界说明：
  - 本规则只处理“已经消费过”的图表；未锚定或 appendix 语境的图表仍按对应规则输出。

<a id="rule-elsevier-complex-table-span-degradation"></a>
### Elsevier 复杂 span 表必须区分成功规范化与异常降级

- 这条规则约束的是：Elsevier CALS 的 `colspec` / `colname` / `namest` / `nameend` / `morerows` 必须进入共享 XML adapter 和网格规范化器。多层 `<thead>` 应按列合并成一个 Markdown header，合法跨度完成语义展开后归为 `normalized`，保留 `merged_span_expanded` 内部 reason，但不得产生 `table_layout_degraded` 或用户 conversion note；非法 span/列定义继续标记布局降级，冲突或不规则网格必须保留 cell 文本为可读列表，不能抛异常或误报语义内容丢失。
- 如果违反，用户会看到：复杂表直接变成一张图 / 空摘要，或者没有说明地被压扁成错误 Markdown 表，无法被 AI 和用户继续读取。
- 它对应的阶段是：`table-rendering`、`final-rendering`。
- Owner：`paper_fetch.extraction.table_grid`、`paper_fetch.extraction.xml_tables`、`paper_fetch.providers._article_markdown_elsevier_document` 与 `paper_fetch.models.Quality`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2021.126210/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2021.126210/original.xml)
  - [`../tests/fixtures/golden_criteria/10.1016_j.rse.2024.114346/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.rse.2024.114346/original.xml)
  - [`../tests/fixtures/golden_criteria/_scenarios/elsevier_complex_table_span/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_complex_table_span/original.xml)
  - real Elsevier XML 覆盖合法 span 不产生 conversion note 或 `table_layout_degraded`；scenario XML 锁住 span 表的语义展开细节。
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_complex_table_spans_are_normalized_without_quality_loss`
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_real_complex_table_records_successful_normalization`
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_real_multilevel_header_is_flattened_without_body_header_row`
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_overlapping_cals_columns_use_readable_list_fallback`
- 边界说明：
  - scenario XML 锁住 span 展平细节，real XML 同时锁住多层表头、无表格 conversion note 和无误报质量标记。
  - 这条规则不是要求复杂表在 Markdown 里必须零损失复原。
  - 它约束的是“优先给用户可读的表格文本，并只对异常结构给出降级提示”，不是承诺所有单元格跨度都按源站视觉样式呈现。
  - `table_layout_degraded` 表示源 span/列定义异常导致原布局无法可靠验证；视觉合并关系被成功展开不属于质量损失，只有行列语义内容真的丢失时，才应升级为 `table_semantic_loss` / `figure_table_loss`。

<a id="rule-fulltext-reference-priority"></a>
### 全文 references 优先于 metadata/Crossref fallback

- 这条规则约束的是：任何 fulltext provider 从 HTML / XML / 出版社 REST 成功抽取非空 references 时，文章模型和最终 Markdown 的 references 必须以这些全文/出版社 references 为准。metadata / Crossref references 只能在 provider references 为空、失败或不可用时兜底，不能在全文 refs 非空时追加未匹配的 title-only 或 DOI-only 条目。
- 如果违反，用户会看到：编号完整的全文 references 后面混入 `- ...` fallback bullet，或出版社 references 被 Crossref metadata 条目污染。
- 它对应的阶段是：`references-rendering`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.models.builders` 与 `paper_fetch.providers.ieee`。
- Provider 差异表：

| Provider | 全文 reference 来源 | Provider 小节只保留的差异 |
| --- | --- | --- |
| Elsevier | XML `<ce:bibliography>` / `<ce:bib-reference>` / `<sb:reference>`。 | 保留结构化 label、作者、题名、来源、页码、年份和 DOI；缺字段时保留 raw citation text 或显式占位。 |
| Wiley | HTML reference item 的可见 citation body。 | 清理 `Google Scholar`、`Crossref`、`getFTR` 和隐藏链接区，不把 DOI-only 链接当完整 reference。 |
| IEEE | `/rest/document/{article_number}/references` 的可见 citation text。 | payload 非空时覆盖 Crossref / metadata fallback；payload 为空或不可用时才保留 fallback。 |

- 边界说明：
  - 这条规则不禁止 metadata-only 结果用 bullet 形式渲染 references；它只禁止在全文 references 非空时把 metadata/Crossref fallback 作为额外条目追加。

<a id="rule-elsevier-xml-references"></a>
### Elsevier XML 参考文献必须优先使用结构化 bibliography，保持编号和作者信息

- 这条规则约束的是：Elsevier XML 里存在 `<ce:bibliography>` / `<ce:bib-reference>` / `<sb:reference>` 时，文章模型的 `references` 必须优先从这些结构化节点构建，保留原始顺序、编号、作者、标题、来源、页码、年份和 DOI；字段缺失时必须回退到 visible raw reference text 或显式 `[Reference text unavailable]`，不能直接跳过 bib 条目。Crossref metadata references 只能作为兜底，不能在结构化 XML references 非空时追加未匹配条目。
- 如果违反，用户会看到：参考文献从 `1. A. Anav, P. Friedlingstein...` 退化成没有作者、没有编号的 bullet，如 `- Remote sensing of drought: Progress, challenges and opportunities`，或者 XML 里存在的 bib 条目在最终 references 中消失。
- 它对应的阶段是：`references-rendering`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.providers._article_markdown_elsevier_document`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml)
  - 这个样本能证明 Elsevier XML bibliography 中的 label、作者、题名、期刊卷期页码和 DOI 需要进入最终 references。
- 边界说明：
  - 这条规则不要求所有 Elsevier 文献都有完整 DOI 或页码；缺失字段不能凭空生成。
  - 全文 references 与 metadata / Crossref fallback 的优先级归 [全文 references 优先于 metadata/Crossref fallback](#rule-fulltext-reference-priority)；本规则只约束 Elsevier XML 的来源和结构化字段保留差异。
  - 它约束的是“结构化 XML references 存在时必须优先使用并保持条目数量”，不是禁止在 XML 缺 references 时回退到 metadata references。

<a id="rule-elsevier-graphical-abstract"></a>
### Graphical abstract 不进入 Additional Figures

- 这条规则约束的是：graphical abstract 这类站点或期刊 frontmatter 资产不能混进 `## Additional Figures`，即使它们也有图片文件。
- 如果违反，用户会看到：正文无关的 graphical abstract 和真正的正文 figure 混在同一个附录块里，图列表会被污染。
- 它对应的阶段是：`asset-discovery`、`final-rendering`。
- Owner：`paper_fetch.providers._article_markdown_elsevier` 与 `paper_fetch.models.ArticleModel`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.scitotenv.2022.158499/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.scitotenv.2022.158499/original.xml)
  - 这份 real Elsevier XML 覆盖 `class="graphical"` abstract figure 与正文 figure 同时存在的场景。
- 边界说明：
  - real XML 锁住 Graphical abstract 主干；两个最小资产归类测试分别覆盖“有正文 figure”和“只有 graphical abstract”两种边界。
  - 这条规则不是说 graphical abstract 必须从所有输出里彻底删除。
  - 它约束的是 graphical abstract 不能被误归到正文 figure 附录里。

## Wiley

- 共享规则另见：
  - [HTML fulltext / abstract-only 判定必须和用户可见访问状态一致](#rule-html-availability-contract)
  - [Provider 自有作者与摘要信号必须进入最终文章元数据](#rule-provider-owned-authors)
  - [保留语义父节标题](#rule-keep-semantic-parent-heading)
  - [前言摘要族的顺序与去重必须稳定](#rule-stable-frontmatter-order)
  - [并行多语言摘要要并存，单语非英文正文不能被误删](#rule-keep-parallel-multilingual-abstracts)
  - [Availability section contract 必须保留、归类、排除正文度量并适配 hints](#rule-keep-data-availability-once)
  - [正文已内联 figure 时避免重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)
  - [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope)
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)
  - [正文、标题和表格里的行内语义格式不能被打平或拆裂](#rule-preserve-inline-semantics-in-body-and-tables)
  - [已下载的正文图片和公式图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links)
  - [图片下载必须验证真实图片内容](#rule-image-download-validates-real-images)
  - [下载资产必须保留诊断字段](#rule-asset-download-diagnostic-fields)
  - [浏览器工作流图片下载必须使用 shared browser 主链路](#rule-browser-primary-image-download-path)
  - [表格能展平就转 Markdown 表，展不平就退成可读列表](#rule-table-flatten-or-list)
  - [HTML 公式图片 fallback 必须保留并进入资产链路](#rule-preserve-formula-image-fallbacks)
  - [公式块和图注句子的块间距必须可读](#rule-readable-equation-caption-spacing)
- 不适用 / 部分适用说明：
  - [LaTeX normalization 必须产出 KaTeX 可渲染表达](#rule-formula-latex-normalization) 只在 Wiley HTML MathML 成功进入 LaTeX 转换时适用；公式图片 fallback 仍由 HTML 公式图片规则约束。

<a id="rule-wiley-abbreviations-trailing"></a>
### Abbreviations 只在正文后保留，不得提前打断正文结构

- 这条规则约束的是：如果 Wiley 页面里存在 `Abbreviations` 区块，它可以作为正文后的辅助节保留，但不能提前到正文主线前面，也不能插进正文章节和正文表格中间打断阅读顺序。
- 如果违反，用户会看到：文章还没进入主体内容，`Abbreviations` 就先冒出来，或者它把正文叙述和正文表格硬切成两段。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.providers._wiley_html` 的 Wiley DOM postprocess。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1111_cas.16395/original.html`](../tests/fixtures/golden_criteria/10.1111_cas.16395/original.html)
  - [`../tests/fixtures/golden_criteria/_scenarios/wiley_abbreviations_trailing/original.html`](../tests/fixtures/golden_criteria/_scenarios/wiley_abbreviations_trailing/original.html)
  - real replay 能证明 `Abbreviations` 可以保留但只能放在正文和正文表格之后；scenario 锁住 frontmatter glossary 移到正文后的最小形态。
- 边界说明：
  - 当前只有一份 Wiley replay 加一个 scenario；后续若新增真实 Wiley abbreviations 页面，应优先补第二个 DOI 级 fixture。
  - 这条规则不是要求所有 Wiley 文章都必须输出 `Abbreviations`。
  - 结构信号优先于单一 DOI：规则看的是 `Abbreviations` 区块相对正文主线和正文表格的位置，不以 `10.1111_cas.16395` 本身作为特判。
  - 它约束的是“存在该区块时的落点”，不是强制生成一个缺失的缩写表。

<a id="rule-wiley-supporting-information-assets"></a>
### 兼容锚点：Wiley supplementary scope

> 参见 [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope) 的 provider 差异表。

兼容锚点保留用于 manifest、测试标记和外部引用。Wiley `downloadSupplement` 的 `file` / `filename` / `attachment` / `download` query 仍作为 `filename_hint` 保留并优先用于落盘；布尔型 `download=true` 不作为文件名。

<a id="rule-wiley-reference-text"></a>
### Wiley 参考文献必须使用可见 citation 文本而不是 DOI-only 或链接 chrome

- 这条规则约束的是：Wiley HTML references 要从可见 citation body 中抽取作者、题名、期刊等文本，删除 `Google Scholar`、`Crossref`、`getFTR` 和隐藏链接区，不能把 DOI-only 链接当成完整 reference。
- 如果违反，用户会看到：参考文献只剩 DOI，或者每条 reference 后面混进一串站点跳转和检索入口。
- 它对应的阶段是：`references-rendering`、`html-cleanup`。
- Owner：`paper_fetch.providers._html_references` 与 `paper_fetch.providers._wiley_html`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.15322/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.15322/original.html)
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html)
- 边界说明：
  - 单测试规则：当前用一条参数化测试覆盖两份 Wiley replay，锁住可见 citation body 优先级；新增 Wiley reference DOM 变体时应继续扩充 fixture 参数或拆出独立测试。
  - 结构信号优先于单一 DOI：规则看的是 Wiley reference item 的可见 citation body 和链接 chrome 边界，不以 `10.1111_gcb.15322` 或 `10.1111_gcb.16998` 作为特判。
  - 全文 references 与 metadata / Crossref fallback 的优先级归 [全文 references 优先于 metadata/Crossref fallback](#rule-fulltext-reference-priority)；本规则只约束 Wiley HTML 的来源和清洗差异。
  - 这条规则只过滤 publisher reference chrome，不会补全原始 HTML 中没有的 bibliographic 字段。

## Science

<a id="rule-atypon-browser-workflow-supplementary-sections"></a>
### 兼容锚点：Science / PNAS supplementary section scope

> 参见 [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope) 的 provider 差异表。

兼容锚点保留用于 manifest、测试标记和外部引用。Science / PNAS 正文图片和公式图片范围不受 supplementary contract 影响。

- Owner：`paper_fetch.providers._science_html` 与 `paper_fetch.providers.atypon_browser_workflow`；browser-workflow candidate routing 由 Atypon-only `paper_fetch.providers._atypon_browser_workflow_profiles` 暴露。
- 共享规则另见：
  - [HTML fulltext / abstract-only 判定必须和用户可见访问状态一致](#rule-html-availability-contract)
  - [Provider 自有作者与摘要信号必须进入最终文章元数据](#rule-provider-owned-authors)
  - [保留语义父节标题](#rule-keep-semantic-parent-heading)
  - [前言摘要族的顺序与去重必须稳定](#rule-stable-frontmatter-order)
  - [并行多语言摘要要并存，单语非英文正文不能被误删](#rule-keep-parallel-multilingual-abstracts)
  - [Availability section contract 必须保留、归类、排除正文度量并适配 hints](#rule-keep-data-availability-once)
  - [无节标题正文必须保持扁平](#rule-keep-headingless-body-flat)
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)
  - [正文、标题和表格里的行内语义格式不能被打平或拆裂](#rule-preserve-inline-semantics-in-body-and-tables)
  - [正文已内联 figure 时避免重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)
  - [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope)
  - [已下载的正文图片和公式图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links)
  - [图片下载必须验证真实图片内容](#rule-image-download-validates-real-images)
  - [下载资产必须保留诊断字段](#rule-asset-download-diagnostic-fields)
  - [浏览器工作流图片下载必须使用 shared browser 主链路](#rule-browser-primary-image-download-path)
  - [表格能展平就转 Markdown 表，展不平就退成可读列表](#rule-table-flatten-or-list)
  - [公式块和图注句子的块间距必须可读](#rule-readable-equation-caption-spacing)
  - [HTML 公式图片 fallback 必须保留并进入资产链路](#rule-preserve-formula-image-fallbacks)
- 不适用 / 部分适用说明：
  - [LaTeX normalization 必须产出 KaTeX 可渲染表达](#rule-formula-latex-normalization) 只在 MathML 进入 LaTeX 转换时适用；纯公式图片 fallback 仍按 HTML 公式图片规则处理。
  - Science / Atypon 正文中的 boxed text（例如 `Box 1`）必须作为普通内容块保留，不能因为内部正文引用 `Fig. N` 就被误标成 figure caption 或触发 figure 图片注入。

## PNAS

PNAS 的 supplementary 资产范围见 [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope) 的 provider 差异表；其余用户可见行为约束主要归入共享规则。

- Owner：`paper_fetch.providers._pnas_html` 与 `paper_fetch.providers.atypon_browser_workflow`；browser-workflow candidate routing 由 Atypon-only `paper_fetch.providers._atypon_browser_workflow_profiles` 暴露。
- 共享规则另见：
  - [HTML fulltext / abstract-only 判定必须和用户可见访问状态一致](#rule-html-availability-contract)
  - [Provider 自有作者与摘要信号必须进入最终文章元数据](#rule-provider-owned-authors)
  - [前言摘要族的顺序与去重必须稳定](#rule-stable-frontmatter-order)
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)
  - [并行多语言摘要要并存，单语非英文正文不能被误删](#rule-keep-parallel-multilingual-abstracts)
  - [Availability section contract 必须保留、归类、排除正文度量并适配 hints](#rule-keep-data-availability-once)
  - [无节标题正文必须保持扁平](#rule-keep-headingless-body-flat)
  - [正文、标题和表格里的行内语义格式不能被打平或拆裂](#rule-preserve-inline-semantics-in-body-and-tables)
  - [正文已内联 figure 时避免重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)
  - [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope)
  - [已下载的正文图片和公式图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links)
  - [图片下载必须验证真实图片内容](#rule-image-download-validates-real-images)
  - [下载资产必须保留诊断字段](#rule-asset-download-diagnostic-fields)
  - [浏览器工作流图片下载必须使用 shared browser 主链路](#rule-browser-primary-image-download-path)
  - [表格能展平就转 Markdown 表，展不平就退成可读列表](#rule-table-flatten-or-list)
  - [公式块和图注句子的块间距必须可读](#rule-readable-equation-caption-spacing)
  - [HTML 公式图片 fallback 必须保留并进入资产链路](#rule-preserve-formula-image-fallbacks)
- 不适用 / 部分适用说明：
  - [LaTeX normalization 必须产出 KaTeX 可渲染表达](#rule-formula-latex-normalization) 只在 MathML 进入 LaTeX 转换时适用；PNAS 公式图片 fallback 仍按 HTML 公式图片规则处理。

## AMS

<a id="rule-ams-html-body-assets-formulas"></a>
### AMS HTML 必须保留完整正文并把图表图片回填原位

- 这条规则约束的是：AMS HTML 要从 `#articleBody` / `.container-fulltext-display` 等完整正文容器抽取正文，保留后部 section、Acknowledgments 和 Data availability；正文中的 figure 与 image-only `.tableWrap` 要在原始位置渲染图片块与 caption；MathJax 渲染层旁边的扁平 fallback 文本不能和结构化公式重复出现；display equation 编号只来自源站明确 label 或 AMS `E...` 公式 id，`UE...` 无编号公式不合成 `Equation n.`；AMS 专用 inline renderer 要在正文和 caption 中保留 MathML、上下标和斜体变量，并保守修复上下标后 prose 括注的空格。
- AMS 默认用 selected-browser 请求 `journals.ametsoc.org/view/...xml`；浏览器 HTML 失败或正文质量门槛不通过时，沿用同一 runtime/storage-state 和页面 seed 尝试 AMS `downloadpdf` PDF fallback。
- AMS figure 资产候选必须优先使用源 HTML 的 `Download Figure` EPS/TIFF 链接，并保留网页 full-size JPG/PNG 作为回退；PowerPoint 下载项不是图片资产。EPS/TIFF 下载请求必须继承浏览器 UA/Referer，下载成功后应通过图片转换后端转成 PNG 用于 Markdown，本地同时保留原始源文件和转换元数据。
- 如果违反，用户会看到：BAMS 正文在 section 2 后提前截断，图表只剩文末附录或只剩 `Table 1.` 文本无图片，`Fig . 1.` 这类标签噪声泄漏，同一公式同时出现 LaTeX 和粘连的可见 fallback 文本，`UE1` 被误渲染成重复的 `Equation 1.`，或者 caption 里出现 `ϕ 2`、正文里出现 `νn` / `</sub>(i.e.` 这类行内语义退化。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`asset-discovery`、`asset-link-rewrite`、`formula-rendering`、`final-rendering`。
- Owner：`paper_fetch.providers._ams_html` compatibility facade、canonical `paper_fetch.providers._ams_dom` / `paper_fetch.providers._ams_assets` / `paper_fetch.providers._ams_markdown`、`paper_fetch.providers.atypon_browser_workflow`、`paper_fetch.extraction.html.figure_links` 与 `paper_fetch.models.render`。
- 代表性 HTML：
  - [`../tests/fixtures/golden_criteria/10.1175_bams-d-24-0223.1/original.html`](../tests/fixtures/golden_criteria/10.1175_bams-d-24-0223.1/original.html)
  - [`../tests/fixtures/golden_criteria/10.1175_jamc-d-24-0048.1/original.html`](../tests/fixtures/golden_criteria/10.1175_jamc-d-24-0048.1/original.html)
  - [`../tests/fixtures/golden_criteria/10.1175_waf-d-24-0019.1/original.html`](../tests/fixtures/golden_criteria/10.1175_waf-d-24-0019.1/original.html)
  - [`../tests/fixtures/golden_criteria/10.1175_jpo-d-23-0234.1/original.html`](../tests/fixtures/golden_criteria/10.1175_jpo-d-23-0234.1/original.html)
  - [`../tests/fixtures/golden_criteria/10.1175_jtech-d-24-0028.1/original.html`](../tests/fixtures/golden_criteria/10.1175_jtech-d-24-0028.1/original.html)
- 边界说明：
  - Atypon 共享 asset extractor 负责正文 figure、公式图片和 supplementary material；AMS `.tableWrap` 常只有表格截图而没有真实 HTML `<table>`，只在 AMS 专用补充步骤中降级为 `kind="table"` 图片资产，并按 URL 去重，避免同一个 tableWrap 图片同时作为 generic figure 和 AMS table 发出；后续 figure 链接注入也不能把 `Table` 图片块当作 figure 顺序 fallback 消费。
  - AMS `Download Figure` 源图是在 DOM 归一化删除下载菜单前读取并合并回正文 figure 资产的；后续下载阶段识别 EPS/TIFF payload 或 URL 扩展名，再走 Ghostscript/libvips 转换。转换失败不得让正文图直接失败，必须继续 full-size JPG/PNG fallback。
  - MathML script type 只在 `extraction/html/formula_rules.py` 维护，AMS HTML 归一化与 HTML availability 诊断复用同一组 `math/mml` / `application/mathml+xml` / `text/mml` 判定。
  - AMS display formula 不为了单调性重编号，也不为无编号公式创建 `Equation n.`；子公式如 `7a`、`9b` 保留源站原始 label。
  - AMS Data availability 如果被源站 DOM 排在 appendix 之后，Markdown 后处理只把该 section 移回 Acknowledgments 之后、首个 Appendix 之前；不移动 References、Footnotes 或 appendix 内图表。
  - 已在正文图片块消费的 AMS figure / table 资产必须通过 URL、路径或 basename 等价关系从尾部 `Figures` / `Tables` 附录中过滤。
  - 这条规则不改变 AMS 的 waterfall 和 no-XML 语义；`citation_xml_url` / `/doc/...xml` 仍不作为 AMS 正文来源。
- 共享规则另见：
  - [正文已内联 figure 时避免重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)
  - [已下载的正文图片和公式图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links)
  - [表格能展平就转 Markdown 表，展不平就退成可读列表](#rule-table-flatten-or-list)
  - [LaTeX normalization 必须产出 KaTeX 可渲染表达](#rule-formula-latex-normalization)
  - [浏览器工作流图片下载必须使用 shared browser 主链路](#rule-browser-primary-image-download-path)

## MDPI

<a id="rule-mdpi-browser-html-cleanup"></a>
### 兼容锚点：MDPI browser HTML cleanup

> 参见 [display object anchoring / dedupe](#rule-mdpi-display-object-anchoring-dedupe)、[formula inline / display rendering](#rule-mdpi-formula-inline-display-rendering)、[references numbering / link cleanup](#rule-mdpi-references-numbering-link-cleanup) 和 [article body semantics / chrome removal](#rule-mdpi-body-semantics-chrome-removal)。兼容锚点保留用于外部引用。

<a id="rule-mdpi-display-object-anchoring-dedupe"></a>
### MDPI display object 必须按正文引用锚定并去重

- 这条规则约束的是：MDPI figure、table、HTML `<table>` 和正文中的 inline figure asset 必须在 DOM 阶段按正文首次 `Figure N` / `Fig. N` / `Table N` 引用附近回填；已经插入正文的 display object 不得在 Conclusions 后或尾部 appendix 再次出现；未引用对象只按源顺序插入 References 前；Markdown image alt 只能使用短标签，caption 不得写入 `![alt]` 并破坏 Markdown 语法。
- 如果违反，用户会看到：figure/table 统一落在文末，正文引用后没有可见对象，裸 `Figure 1.` / `Table 1.` 与完整 caption 重复，HTML table 被拆成散乱字段，或者带 `[AO10]` 的 caption 进入图片 alt 导致 Markdown 图片语法异常。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`table-rendering`、`asset-discovery`、`asset-link-rewrite`、`final-rendering`。
- Owner：`paper_fetch.providers._mdpi_html` compatibility facade、canonical `paper_fetch.providers._mdpi_dom` / `paper_fetch.providers._mdpi_assets` / `paper_fetch.providers._mdpi_markdown` 与 `paper_fetch.models.render`。
- 代表性 HTML：
  - [`../tests/fixtures/golden_criteria/10.3390_su12072826/original.html`](../tests/fixtures/golden_criteria/10.3390_su12072826/original.html)
  - [`../tests/fixtures/golden_criteria/10.3390_rs16010010/original.html`](../tests/fixtures/golden_criteria/10.3390_rs16010010/original.html)
- 边界说明：
  - 复杂 HTML table 可以降级为单个去重文本块；这条规则不承诺所有 rowspan/colspan 都能无损还原，但不允许重复 caption、丢失锚定位置或拆成散乱多行字段。
  - 已在正文图片块消费的 figure / table 资产必须通过 URL、路径或 basename 等价关系从尾部 `Figures` / `Tables` 附录中过滤。
  - PDF fallback 不适用本 HTML display object 锚定规则；PDF 图片只由共享 PDF 转换导出并按正文 asset 记录。

<a id="rule-mdpi-formula-inline-display-rendering"></a>
### MDPI formula 必须区分 inline 与 display 渲染

- 这条规则约束的是：MDPI MathML 必须进入共享 MathML -> LaTeX 转换链路；`.html-disp-formula-info` 和 `math[display=block]` 渲染成 `$$ ... $$` Markdown 块并保留源站 `(1)` / `(2)` 编号；段落内 inline 公式、变量、上下标和 `html-italic` / `html-bold` 样式 wrapper 必须保持行内；没有 MathML 的 HTML-only 化学式 / 反应式必须保留 `<sub>` / `<sup>` 语义并压缩成单个公式块。
- 如果违反，用户会看到：`lnYit=β0+∑...` / `∂Ci∂t=...` 被压成无 LaTeX 分隔符的 Unicode 拼接文本，`where L is ...` / `C is a modelling constant` / `ω<sub>eng</sub> is ...` 被空行切成独立 `L`、`C`、`<sup>−1</sup>` 段，HTML-only 公式出现 `IO`、`<sub>4</sub>`、`<sup>−</sup>` 独立碎片行，或可解析公式输出 `[Formula unavailable]`。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`html-cleanup`、`formula-rendering`、`markdown-normalization`。
- Owner：`paper_fetch.providers._mdpi_html` compatibility facade、canonical `paper_fetch.providers._mdpi_dom` / `paper_fetch.providers._mdpi_markdown` 与 `paper_fetch.extraction.html.formula_rules`。
- 代表性 HTML：
  - [`../tests/fixtures/golden_criteria/10.3390_math11030657/original.html`](../tests/fixtures/golden_criteria/10.3390_math11030657/original.html)
  - [`../tests/fixtures/golden_criteria/10.3390_w15040758/original.html`](../tests/fixtures/golden_criteria/10.3390_w15040758/original.html)
  - [`../tests/fixtures/golden_criteria/10.3390_ijerph18094484/original.html`](../tests/fixtures/golden_criteria/10.3390_ijerph18094484/original.html)
- 边界说明：
  - 段落内只包裹 inline 文本、citation、inline MathML、`<sub>` / `<sup>` 或样式 span 的 MDPI `div` wrapper 应在 provider DOM 阶段转为 inline；真正的 display formula、figure/table、HTML table、list、heading、section、references 不适用这条 inline 化规则。
  - 公式编号只保留源站显式编号；provider 不为了单调性重编号，也不为无编号公式创建 `Equation n.`。

<a id="rule-mdpi-references-numbering-link-cleanup"></a>
### MDPI references 必须保留源编号并清理站点链接

- 这条规则约束的是：MDPI reference `li data-content` 里的出版社编号必须写回 raw citation，并在最终 References 中保留为编号列表；Google Scholar / CrossRef / PubMed / Green Version 等 UI 链接不能进入 Markdown 或 reference raw text；全文 references 优先于 metadata / Crossref fallback。
- 如果违反，用户会看到：参考文献从 `1.` / `2.` 编号退化成 bullet，被 `[ Google Scholar ]`、`[ CrossRef ]`、`[ PubMed ]` 或 Green Version 链接打断，或者 provider 已解析的全文 reference 被 metadata fallback 覆盖。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`html-cleanup`、`references-rendering`、`final-rendering`。
- Owner：`paper_fetch.providers._mdpi_html` compatibility facade、canonical `paper_fetch.providers._mdpi_references` / `paper_fetch.providers._mdpi_markdown` 与 `paper_fetch.models.render`。
- 代表性 HTML：
  - [`../tests/fixtures/golden_criteria/10.3390_w15040758/original.html`](../tests/fixtures/golden_criteria/10.3390_w15040758/original.html)
- 边界说明：
  - MDPI references 只保留源 HTML 已提供的编号；metadata / Crossref fallback references 不在 provider 内人工补号。
  - 只清理 reference UI 操作链接，不删除 citation 标题、期刊名、DOI 或正文内正常链接。

<a id="rule-mdpi-body-semantics-chrome-removal"></a>
### MDPI article body 必须保留正文语义并移除 chrome

- 这条规则约束的是：MDPI selected-browser HTML 只能从 article container 中抽取题名、摘要、正文 section、references、figures、tables、formula 和明确 supplementary section；article menu、下载按钮、分享/引用/metrics、SciProfiles 等站点 chrome 不能进入最终 Markdown，也不能通过全页后缀扫描把正文外链接误判为 supplementary；`#html-keywords` 只进入 `metadata.keywords`，不能进入 Abstract 或独立 Markdown section。
- 如果违反，用户会看到：`Browse Figures`、`Download PDF`、`Article Metrics`、`Share and Cite` 等站点 chrome 混入正文，摘要标题后的单独冒号或 `Keywords:` 残留到正文，`data-nested="2"` 的小节被错误渲染成四级 heading，或者 `asset_profile=body` 下载到正文 scope 外的 supplementary 文件。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`html-cleanup`、`asset-discovery`、`markdown-normalization`。
- Owner：`paper_fetch.providers._mdpi_html` compatibility facade；canonical owner 是 `paper_fetch.providers._mdpi_dom` / `paper_fetch.providers._mdpi_assets` / `paper_fetch.providers._mdpi_markdown`。
- 代表性 HTML：
  - [`../tests/fixtures/golden_criteria/10.3390_membranes15030093/original.html`](../tests/fixtures/golden_criteria/10.3390_membranes15030093/original.html)
  - [`../tests/fixtures/golden_criteria/10.3390_s23010001/original.html`](../tests/fixtures/golden_criteria/10.3390_s23010001/original.html)
  - [`../tests/fixtures/golden_criteria/10.3390_foods10081757/original.html`](../tests/fixtures/golden_criteria/10.3390_foods10081757/original.html)
- 边界说明：
  - MDPI XML 链接不是本 provider 的 success route；waterfall 和 PDF fallback 语义归 [`providers.md`](providers.md)。
  - Markdown 归一化只能压缩单行内多余空格/制表符，不能压平 `\n\n` 块边界或行首 heading；否则 ArticleModel 会把 HTML 主路径误判为非全文并触发 PDF fallback。
  - `asset_profile=all` 只扩展明确 supplementary/app section 内的 `/s1` 等附件链接；普通正文里的 `Download` 字样不能作为全局附件发现规则。
  - PDF fallback 不适用本 HTML 清洗和资产发现规则；PDF 图片只由共享 PDF 转换导出并按正文 asset 记录。
- 共享规则另见：
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)
  - [表格能展平就转 Markdown 表，展不平就退成可读列表](#rule-table-flatten-or-list)
  - [LaTeX normalization 必须产出 KaTeX 可渲染表达](#rule-formula-latex-normalization)
  - [Markdown 图片 alt 只保留短标签](#rule-short-markdown-image-alt-labels)
  - [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope)
  - [浏览器工作流图片下载必须使用 shared browser 主链路](#rule-browser-primary-image-download-path)
  - [全文 references 优先于 metadata/Crossref fallback](#rule-fulltext-reference-priority)

## ACS

<a id="rule-acs-silverchair-body-assets-references"></a>
### ACS 当前 Silverchair 页面必须保留完整正文并隔离嵌入 viewer

- 这条规则约束的是：ACS selected-browser HTML 必须把当前 `.article-body` 作为完整提取根，等待 `.article-body` / `.widget-ArticleFulltext` 稳定，并保留正文 section、table、`.fig.fig-section`、MathML formula 与 `.ref-list .ref`；Supporting Information 中动态加载的 Figshare `<article>` 不能被通用 content selector 误选为正文。
- 如果违反，用户会看到：正文只剩 abstract 或 Supporting Information viewer、21 个 display formula 丢失、figure modal/view-large 控件进入 Markdown、references 只剩 DOI/chrome，或者补充文件链接从正文 scope 泄漏。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`html-cleanup`、`asset-discovery`、`references-rendering`、`artifact-storage`。
- Owner：`paper_fetch.providers._acs_html`、`paper_fetch.providers.atypon_browser_workflow` 与共享 Silverchair figure/reference helper。
- 代表性 replay：
  - [`../tests/fixtures/golden_criteria/10.1021_acsomega.4c03987/original.html`](../tests/fixtures/golden_criteria/10.1021_acsomega.4c03987/original.html)：当前 Silverchair structure/table/figure/supplementary/reference 页面，8 个 figures、3 个 tables、45 条 references。
  - [`../tests/fixtures/golden_criteria/10.1021_acsomega.3c06992/original.html`](../tests/fixtures/golden_criteria/10.1021_acsomega.3c06992/original.html)：当前 Silverchair formula 页面，21 个 display formulas、2 个 tables、8 个 figures、20 条 references。
  - [`../tests/fixtures/golden_criteria/10.1021_acsomega.2c02828/original.pdf`](../tests/fixtures/golden_criteria/10.1021_acsomega.2c02828/original.pdf)：由 selected Camoufox runtime 捕获的当前 `article-pdf` fallback。
- 边界说明：
  - figure normalization 把一个 `.fig.fig-section` 折叠成一条带 label/caption 的正文图，不输出 `Open figure viewer`、`View Large`、`Close modal` 或重复 modal 文本；`/view-large/figure/` 是 full-size 页面候选，抓取这类图页时显式跳过 article-body readiness，并最多等待 5 秒直至 `img.content-image[src]` / `img.content-image[data-src]` 出现，元素就绪后立即返回；CDN `m_*.png` 仍作为可接受 preview。
  - references 必须从清洗前的 `.ref-list .ref` 提取可见 citation；优先读取 `.year`，并移除 Crossref/ADS/OpenURL 操作 chrome，再由 provider 渲染一份编号 references。
  - supplementary 只从清洗前的 `.widget-ArticleDataSupplements` 建立独立 scope，并只接受稳定 `/article-supplement/` publisher 链接；嵌入 Figshare downloader 不作为 canonical 附件。
  - PDF fallback Markdown 仍由共享转换器负责；页面 footer 和双栏 references 顺序是 PDF 布局限制，不应反向写成 ACS DOI 特例。
- 共享规则另见：
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)
  - [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope)
  - [浏览器工作流图片下载必须使用 shared browser 主链路](#rule-browser-primary-image-download-path)
  - [全文 references 优先于 metadata/Crossref fallback](#rule-fulltext-reference-priority)

## IOP

<a id="rule-iop-body-challenge-cleanup"></a>
### IOP article HTML 必须拒绝 challenge 并清理站点 chrome

- 这条规则约束的是：IOPScience selected-browser HTML 只能从 article body / `articleBody` 语义容器中抽取题名、摘要、正文 section、body table、formula image、figure caption 和 references；`Download PDF`、metrics、citation/export、导航、相关内容和 Radware/hCaptcha challenge 页面不能进入最终 Markdown。
- 如果违反，用户会看到：Radware Bot Manager / hCaptcha 页面被当成正文，或者 `Download PDF`、`Article metrics`、`Export citation` 等 IOPScience 操作文案混入 article Markdown。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`html-cleanup`、`availability-quality`、`markdown-normalization`。
- Owner：`paper_fetch.providers._iop_html` 与 `paper_fetch.providers.iop`。
- 代表性 HTML：
  - [`../tests/fixtures/golden_criteria/10.1088_1748-9326_ab7d02/original.html`](../tests/fixtures/golden_criteria/10.1088_1748-9326_ab7d02/original.html)
  - [`../tests/fixtures/golden_criteria/10.1088_2058-9565_ac3460/original.html`](../tests/fixtures/golden_criteria/10.1088_2058-9565_ac3460/original.html)
- 代表性 PDF：
  - [`../tests/fixtures/golden_criteria/10.1088_1748-9326_aa9f73/original.pdf`](../tests/fixtures/golden_criteria/10.1088_1748-9326_aa9f73/original.pdf)
- 边界说明：
  - IOP PDF fallback 只接受真实 PDF magic bytes 或 `application/pdf` payload；Radware/hCaptcha HTML wrapper 必须被拒绝。
  - IOP `math/tex` 公式已经渲染成 Markdown LaTeX 时，公式 GIF fallback 不作为 body asset 下载；正文 `_online` figure preview 作为已接受的 figure 资产诊断处理。
  - IOP Appendix figure caption 已经出现在正文时，尾部 fallback `Figures` 可以保留图片，但不能重复整段 caption；已原位内联的正文 figure 资产仍保留其 caption 诊断字段。
  - 本 provider 不实现未授权的 IOP XML/PDF TDM route。
- 共享规则另见：
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)
  - [全文 references 优先于 metadata/Crossref fallback](#rule-fulltext-reference-priority)
  - [浏览器工作流图片下载必须使用 shared browser 主链路](#rule-browser-primary-image-download-path)

## Royal Society Publishing

- 共享规则另见：
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)
  - [正文内联图不得在文末重复出现 Figures 附录](#rule-no-trailing-figures-appendix)
  - [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope)

<a id="rule-royalsociety-silverchair-markdown-cleanup"></a>
### Royal Society Silverchair figure caption 与原图分层必须保真

- 这条规则约束的是：Royal Society Publishing 的 Silverchair HTML 图像资产必须从 `div.fig-section` 读取真实 figure label/caption，并把 `DownloadImage.aspx` 中的签名 CDN 原图、`/view-large/figure/` HTML 查看页和 `m_*` preview 分别建模为 `full_size_url`、`figure_page_url` 和 `preview_url`；查看页不能冒充原图。
- 如果违反，用户会看到：`## Figures` 下只有多个 `- Figure`、caption 缺失，或查看页返回 HTML 后错误降级为低分辨率 preview。
- 它对应的阶段是：`asset-discovery`、`markdown-normalization`、`final-rendering`。
- Owner：`paper_fetch.providers._royalsocietypublishing_html`。
- 代表性 HTML：
  - [`../tests/fixtures/golden_criteria/10.1098_rsta.2019.0558/original.html`](../tests/fixtures/golden_criteria/10.1098_rsta.2019.0558/original.html)
  - [`../tests/fixtures/golden_criteria/10.1098_rsos.150470/original.html`](../tests/fixtures/golden_criteria/10.1098_rsos.150470/original.html)
- 边界说明：
  - 这条规则只针对 Royal Society Publishing/Silverchair 的 HTML figure wrapper；共享 figure container 判定只接受真实 `<figure>`、精确 `class="figure"` 这类显式通用 figure 容器，或显式 Silverchair `fig fig-section` / `js-fig-section` / 受这些祖先约束的 `graphic-wrap`，不能因为普通正文 wrapper、section、anchor id/href 中出现 `-f` 或 `figure` 就提升为 figure。
  - 原图入口必须在删除 `.download-slide` 前从原始正文 DOM 提取；caption 仍从清理后的 DOM 获取，避免 `<sub>` / `<sup>` 等 inline markup 引入额外空格。
  - `DownloadImage.aspx` 的嵌套 URL 只接受 HTTP(S) Silverchair CDN host，保留 `Expires`、`Signature`、`Key-Pair-Id`，并要求原图 basename 与当前 figure 的 viewer/preview basename 一致；分组 slide 指向相邻 figure 时不能串图。
  - 同一逻辑 figure 的 viewer、原图和 preview 按 DOM id 与去除 `m_`/扩展名后的规范化 figure basename 合并；直接原图优先，缺失时才从 viewer 动态发现原图，最后才使用 preview。
  - PDF fallback Markdown 统一由 shared `pymupdf4llm` 转换产生；`body/all` 且允许 artifact 落盘时，PDF 图片由 shared 转换导出到 `<doi>_assets/`。provider 只负责获取并校验真实 PDF、设置 source/route，不添加 provider-owned Markdown cleanup、front matter reconstruction、水印移除或 reference extraction。
  - HTML 正文已包含可读 figure caption 时，远程图 URL 可以只作为资产原始链接保留；最终 Markdown 至少要保留 caption 文本，不能输出空 caption placeholder。

## IEEE

- 共享规则另见：
  - [全文 references 优先于 metadata/Crossref fallback](#rule-fulltext-reference-priority)
  - [正文内联图不得在文末重复出现 Figures 附录](#rule-no-trailing-figures-appendix)
  - [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope)
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)
  - [HTML 公式图片 fallback 必须保留并进入资产链路](#rule-preserve-formula-image-fallbacks)
  - [Markdown inline citation normalize 不能破坏非引用语义和图片块边界](#rule-markdown-inline-citation-normalization)

<a id="rule-ieee-real-html-semantics"></a>
### 兼容锚点：IEEE REST HTML 真实语义规则

> 参见 [IEEE REST HTML 必须保留正文结构和标题层级](#rule-ieee-html-structure)、[IEEE landing metadata 和 references payload 必须覆盖 fallback](#rule-ieee-landing-metadata-references)、[IEEE mediastore 正文图表资产必须锚定并去重](#rule-ieee-mediastore-body-assets)；IEEE supplementary / multimedia scope 见 [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope)。

兼容锚点保留用于 manifest 和外部引用。

<a id="rule-ieee-html-structure"></a>
### IEEE REST HTML 必须保留正文结构和标题层级

- 这条规则约束的是：IEEE Xplore REST `#article` HTML 要按真实 DOM 结构抽取正文，而不是依赖 synthetic 片段。`SECTION I.` 这类裸 marker 必须清理；`div.section` / `div.section_2` 嵌套层级必须保留为主节 `##`、字母子节 `###`、数字子节 `####`；`tex-math` / `disp-formula` 必须渲染成可见 LaTeX，不能输出 `[Formula unavailable]`。
- 如果违反，用户会看到：章节层级被压平、公式消失、`SECTION I.` 泄漏，或者 `#article` 外的站点 chrome 被混进正文。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`html-cleanup`、`formula-rendering`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.providers.ieee` 与 `paper_fetch.providers._html_section_markdown`。
- 代表性 HTML：
  - [`../tests/fixtures/golden_criteria/10.1109_ACCESS.2024.3352924/original.html`](../tests/fixtures/golden_criteria/10.1109_ACCESS.2024.3352924/original.html)
  - [`../tests/fixtures/golden_criteria/10.1109_CICTN64563.2025.10932570/original.html`](../tests/fixtures/golden_criteria/10.1109_CICTN64563.2025.10932570/original.html)
  - [`../tests/fixtures/golden_criteria/10.1109_TBME.2024.3434477/original.html`](../tests/fixtures/golden_criteria/10.1109_TBME.2024.3434477/original.html)
  - [`../tests/fixtures/golden_criteria/10.1109_TCOMM.2024.3395332/original.html`](../tests/fixtures/golden_criteria/10.1109_TCOMM.2024.3395332/original.html)
  - [`../tests/fixtures/golden_criteria/10.1109_TDEI.2024.3373549/original.html`](../tests/fixtures/golden_criteria/10.1109_TDEI.2024.3373549/original.html)
  - [`../tests/fixtures/golden_criteria/10.1109_TE.2024.3376795/original.html`](../tests/fixtures/golden_criteria/10.1109_TE.2024.3376795/original.html)
  - [`../tests/fixtures/golden_criteria/10.1109_TIM.2024.3509573/original.html`](../tests/fixtures/golden_criteria/10.1109_TIM.2024.3509573/original.html)
- 边界说明：
  - 这条规则不要求修复 publisher 源 HTML 中已经损坏的 caption 字符串；坏源样本只作为输入事实保留，不提升成主干 citation range 修复规则。

<a id="rule-ieee-landing-metadata-references"></a>
### IEEE landing metadata 和 references payload 必须覆盖 fallback

- 这条规则约束的是：IEEE landing metadata 的 IEEE Keywords / Index Terms / Author Keywords 要进入 `metadata.keywords`；IEEE `/rest/document/{article_number}/references` 成功返回非空 references 时，文章模型必须使用该 payload 的可见 citation text，不能把 Crossref / metadata fallback 追加到 numbered references 后面。payload 不可用或为空时，才保留 metadata / Crossref references。
- 如果违反，用户会看到：编号完整的 IEEE references 后面混入 `- ...` fallback bullet，或者 metadata-only DOI/title 条目污染出版社 reference list。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`references-rendering`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.providers.ieee` 与 `paper_fetch.models.builders`。
- 代表性 HTML / metadata：
  - [`../tests/fixtures/golden_criteria/10.1109_ACCESS.2024.3352924/landing.html`](../tests/fixtures/golden_criteria/10.1109_ACCESS.2024.3352924/landing.html)
  - [`../tests/fixtures/golden_criteria/10.1109_ACCESS.2024.3352924/references.json`](../tests/fixtures/golden_criteria/10.1109_ACCESS.2024.3352924/references.json)
- 边界说明：
  - 这条规则是 IEEE 对 [全文 references 优先于 metadata/Crossref fallback](#rule-fulltext-reference-priority) 的 provider 入口约束；不禁止 metadata-only 结果用 fallback references。

<a id="rule-ieee-mediastore-body-assets"></a>
### IEEE mediastore 正文图表资产必须锚定并按身份优先级去重

- 这条规则约束的是：IEEE dynamic HTML 中的正文 `figure-full` / `figure-full table` mediastore 图片必须抽取为正文 figure/table 资产，在首次 caption 位置以内联图片锚定；正文公式图片只能作为 formula fallback，不能抢占 table/figure 资产身份；`/assets/img/icon.support.gif` 这类 support icon 必须排除。
- 如果违反，用户会看到：正文缺图、表格截图被当作公式、support icon 被下载成正文图，或者同一 mediastore URL 同时以 table / figure / formula 多种身份进入资产列表。
- 它对应的阶段是：`asset-discovery`、`formula-rendering`、`article-assembly`、`final-rendering`。
- Owner：`paper_fetch.providers.ieee` 与 `paper_fetch.extraction.html.assets`。
- 代表性 HTML：
  - [`../tests/fixtures/golden_criteria/10.1109_CICTN64563.2025.10932570/original.html`](../tests/fixtures/golden_criteria/10.1109_CICTN64563.2025.10932570/original.html)
  - [`../tests/fixtures/golden_criteria/10.1109_TBME.2024.3434477/original.html`](../tests/fixtures/golden_criteria/10.1109_TBME.2024.3434477/original.html)
- 边界说明：
  - 已锚定正文图表不得在尾部 Figures / Tables 附录重复追加，归共享 [正文已内联 figure 时避免重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix) 约束。
  - 这条规则只约束正文 figure/table/formula 资产；supplementary / multimedia 文件附件见 [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope)。

<a id="rule-ieee-supplementary-scope"></a>
### 兼容锚点：IEEE supplementary / multimedia scope

> 参见 [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope) 的 provider 差异表。

兼容锚点保留用于 manifest、测试标记和外部引用。IEEE `asset_profile='body'` 仍只下载正文 figure/table/formula，`asset_profile='all'` 才下载 supplementary / multimedia 文件。

<a id="rule-ieee-html-access-waterfall"></a>
### IEEE HTML 可用性与 fallback 顺序

- 这条规则约束的是：IEEE block-page 检测只能使用人可见的页面文本；`script/style/svg/noscript/template` 中的 `captcha`、challenge 或 access token 不能拒收已经就绪的真实 `#article`。页面可正常发起自身 REST 子请求，DOM-only 验证不读取 REST response body 时也不能在网络层阻断该请求。可见区域中的验证码、人工验证或访问阻断文案仍必须 fail closed。
- 如果违反，用户会看到：约 6.1 万字符、74 个段落的完整 IEEE 正文因为内联脚本包含 `captcha` 而被误报为 challenge，或者测试通过阻断 REST 子请求制造出生产环境不会出现的失败。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`availability-quality`。
- Owner：`paper_fetch.providers._ieee_block_page` 与 `paper_fetch.providers._ieee_browser_html`。
- provider 路由、REST/DOM readiness 和 PDF fallback 细节参见 [`providers.md` 的 IEEE provider 说明](providers.md#ieee)。

该锚点继续兼容 manifest 与外部引用；本规则只约束检测语义，不改变既有 route 顺序。

## Copernicus

- 共享规则另见：
  - [全文 references 优先于 metadata/Crossref fallback](#rule-fulltext-reference-priority)
  - [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope)
  - [表格能展平就转 Markdown 表，展不平就退成可读列表](#rule-table-flatten-or-list)
  - [LaTeX normalization 必须产出 KaTeX 可渲染表达](#rule-formula-latex-normalization)
  - [Availability section contract 必须保留、归类、排除正文度量并适配 hints](#rule-keep-data-availability-once)

<a id="rule-copernicus-xml-jats-rendering"></a>
### Copernicus NLM/JATS XML 必须保留正文结构、公式、图表和 references

- 这条规则约束的是：Copernicus XML 主路径要从 NLM/JATS 结构中提取标题、作者、摘要、正文 section、figure/table caption、表格、MathML display formula、data/code availability、supplementary link 和 references，不能只把 XML 当纯文本拼接。
- 如果违反，用户会看到：章节层级丢失、公式不可见、图表 caption 或 supplementary 链接消失，或者 references 退化成 metadata fallback。
- 它对应的阶段是：`provider-html-or-xml-extraction`、`asset-discovery`、`table-rendering`、`formula-rendering`、`references-rendering`。
- Owner：`paper_fetch.providers._article_markdown_jats`（通用 JATS renderer）与 `paper_fetch.providers._article_markdown_copernicus`（Copernicus 适配层）。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.5194_acp-24-1-2024/original.xml`](../tests/fixtures/golden_criteria/10.5194_acp-24-1-2024/original.xml)
- 边界说明：
  - 单测试规则：当前 owner 测试使用最小 JATS fixture 锁住结构渲染 contract，并用合法但正文为空、无正文段落或正文过短的 JATS fixture 锁住 XML route 必须降级到 PDF；8 篇真实 Copernicus XML golden fixture 锁住 XML 主路径 corpus 级别回归；4 篇早期 abstract-only XML + PDF fixture 锁住 route fallback，不扩大本 XML 结构规则的适用范围。后续新增 JATS 变体时应扩充该单测或新增 provider-specific 规则。
  - 这条规则不承诺所有复杂表格布局都能零损失复原；复杂表格降级语义仍归 [表格能展平就转 Markdown 表，展不平就退成可读列表](#rule-table-flatten-or-list)。
  - PDF fallback 的正文 Markdown 走共享 PDF 转换，不适用本 XML 结构规则；PDF 图片只作为导出正文 asset 记录。

## 使用建议

- 新增回归测试时，优先把规则写成行为约束，再用 DOI 级样本去证明它。
- 做 root-cause 排障时，先判断问题是在 HTML 提取、文章组装、资产清洗，还是最终渲染阶段，再决定该把证据补到哪条规则下。
- 共享 heading、inline whitespace、citation sentinel、DOI 与 formula 识别常量应复用代码中的单一来源；provider 只保留真正改变语义的覆盖规则，避免测试路径和运行时 drift。
- 后续如果要补“既有规则”，继续沿用同一模板，不要把 incident 记录直接搬进这里。
