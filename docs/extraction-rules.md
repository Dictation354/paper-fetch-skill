# 提取与渲染规则

修订日期：2026-09-19（7.0）

本文维护 HTML/XML 提取、组装和渲染的用户可见约束，DOI 仅作来源证据，不能成为
特判规则。路由、运行时及资产获取见 [providers.md](providers.md)，阶段与代码 owner
见 [架构映射](architecture/overview.md#extraction-stage-module-map)。测试分层、固定来源
预期及当前样本选择见 [tests/README.md](../tests/README.md)；历史事故记录另行归档。

### 维护边界

规则只描述用户可见的提取与渲染语义。实现 owner 由代码和 provider-local 测试负责，fixture 身份与预期由 `tests/fixtures/golden_criteria/manifest.json` 负责。已发布的显式 HTML anchor ID 继续保留；旧 ID 直接落到对应规范章节，不再显示重复标题。

<a id="rule-pdf-conversion-boundary"></a>
### PDF 转换边界：禁止格式清洗与质量修复

- 所有 PDF 解析与转换质量问题均不纳入改进、fixture 补齐或验收目标，以现有 `pymupdf4llm` 的转换输出为边界。
- 禁止在该输出之上做任何格式清洗或内容修复，包括标题层级修复、封面／页眉／页脚／水印删除、空白或断行整理、跨栏内容拼接或重排、引用分条／编号归一化／去重／重排、正文与后置内容重建、公式／OCR／表格修复及导出占位图修复。
- 禁令覆盖 shared 转换包装、provider、文章组装、最终渲染及其他后处理层；不得以通用规则、单篇 DOI 特判、已有实现或测试要求为例外。本文 HTML／XML 清洗规则不得套用于 PDF 输出。
- PDF 获取、合法访问、真实文件及完整论文身份校验、统一 acceptance、候选回退／降级、原始文件与转换器导出资产落盘、必要的本地资产路径改写和来源记录仍按既有契约执行；这些操作不得借机改写 PDF 转换内容，也不得新增 PDF 排版或解析保真验收要求。
- 正文 PDF 候选排除参考文献、站点页脚中的 PDF 链接，以及明确的预览／补充材料链接。下载后仍检查原始及最终 URL、文件开头的补充材料标记和论文身份；DOI 不足以确认身份时，传入的目标标题必须得到文件内标题或开头文本支持。未核实文件不得因 `allow_pdf_only`、有效 PDF 文件头或可转换为 Markdown 而被接受为正文；失败后继续既有候选回退，最终按现有流程降级。此检查不改写转换内容，也不按 PDF 页数短就认定为预览。
- 旧版标题修复、共享 PDF 引用分离及 AIP 上标编号归一化规则自本修订起撤销。历史代码、样本和质量断言仅说明已有实现，不构成有效规则或继续维护清洗的依据。相关清洗实现及其质量断言已移除，当前测试验证转换器输出原样通过组装和渲染。

## Generic

- 这里的 `Generic` 指跨 provider 共享的提取 / 渲染规则。
- 它只表示 shared extraction logic，不表示可被路由命中的第六条 provider 或 public source。
- Front matter 的 publication watermark 只匹配短 masthead 标签：必须是短文本、无句子标点、token 数受限，并且呈标题式或全大写；`science` / `pnas` / `ams` / `bams` / `acs` / `iopscience` 等 provider 词面只作为 provider-scoped keyword 参与判断，长正文句子里出现这些词不能被当作 front matter。
- 反爬 / 访问阻断文本中的通用 token 统一维护在 `COMMON_ACCESS_BLOCK_TOKENS`，provider 规则只追加自身增量，避免把通用 challenge 语义复制到单个 provider。

资产渲染与诊断 contract 由 [正文已内联 figure 时避免重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix)、[Markdown 图片 alt 只保留短标签](#rule-short-markdown-image-alt-labels)、[已下载的正文图片和公式图片要改写成正文附近的本地链接](#rule-rewrite-inline-figure-links) 和 [下载资产必须保留诊断字段](#rule-asset-download-diagnostic-fields) 共同维护；[图片下载必须验证真实图片内容](#rule-image-download-validates-real-images) 独立约束 payload 真实性和 preview acceptance。

<a id="rule-html-byte-decoding-and-cleanup-bounds"></a>
### HTML bytes 解码和清洗 fallback 边界

- HTML/JSON bytes 转文本必须优先保留真实字符集，通用 HTML cleanup 在无内容根时不能对整页逐节点跑噪声分类，raw trafilatura fallback 不能无上限处理大型原文 HTML。
- 代表性 HTML / XML：
  - 当前无稳定 DOI 样本，直接见对应测试；后续出现真实 charset 或 no-root 性能回归时补入 replay fixture。
- 边界说明：
  - 解码顺序固定为 UTF-8 BOM / UTF-8、HTTP charset、HTML meta charset、`charset-normalizer`、UTF-8 replacement fallback。
  - no-root cheap cleanup 仍会删除 drop tags、cleanup selectors、extraction cleanup selectors 和 ORCID links；它只跳过逐节点 `should_drop_html_element()` 分类。
  - raw trafilatura fallback 默认上限是 `RAW_TRAFILATURA_FALLBACK_CHAR_LIMIT = 1_000_000` 字符；超过上限时跳过 raw fallback，但 cleaned HTML 的 parser fallback 仍继续执行。

<a id="rule-keep-semantic-parent-heading"></a>
### 保留语义父节标题

- 只要 HTML 提取链已经识别出一个父节标题，后续的文章组装和最终 markdown 渲染就不能把这个父节标题吃掉，即使正文内容主要落在子节里。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/original.html`](../tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/original.html)
  - 这个样本能证明 `MATERIALS AND METHODS` 是语义父节，而 `Experimental design` 是其子节内容。
- 边界说明：
  - 这条规则不是要求所有论文都必须出现 `MATERIALS AND METHODS` 这个固定字面值。
  - 它约束的是“父节语义不能在组装或渲染阶段丢失”，不是要求不同 publisher 的标题体系完全一致。
  - 当前直接 DOI 证据样本来自 Science；Wiley 与 models 测试证明同一父节保留行为不是 Science-specific 规则，后续不为凑数强行新增 fixture。

<a id="rule-no-trailing-figures-appendix"></a>
### 正文已内联 figure 时避免重复追加尾部 Figures 附录

- 当 figure 已经以正文内联形式进入最终输出时，`asset_profile='body'` / `asset_profile='all'` 的正文图渲染不能再在文末重复拼一个尾部 `## Figures` 附录；arXiv official HTML 会在正文 figure caption 附近先插入原始图片 Markdown 链接，下载后再改写到 `body_assets/...`。如果图片无法锚定正文但仍可下载，尾部可以作为 fallback 保留图片，但不能重复整段 caption。
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

<a id="rule-springer-supplementary-scope"></a>
<a id="rule-wiley-supporting-information-assets"></a>
<a id="rule-atypon-browser-workflow-supplementary-sections"></a>
<a id="rule-ieee-supplementary-scope"></a>
<a id="rule-supplementary-discovery-explicit-scope"></a>
### Supplementary discovery 必须来自明确附件 scope

- supplementary / supporting / multimedia 文件发现必须先由 provider 切出明确附件 scope，再在该 scope 内解析附件链接；不能在整篇正文里全局扫描 `data`、`code`、`.csv`、`.zip`、`.mp4`、`.pdf` 这类词面或后缀并直接归为 supplementary。
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
| Wiley | `Supporting Information` accordion/content 内的 `downloadSupplement` 或 `sup-*` supporting file 链接；`file` / `filename` / `attachment` / 非布尔 `download` query 可作为落盘 `filename_hint`。 | 正文 `<figure>` 的 `/cms/asset/...fig-*` 只归 body figure，不并行归 supplementary；`download=true` 不作为文件名。 |
| Science / PNAS | Atypon back matter 的真实 `Supplementary Material(s)` / `Supporting Information` section 子树和 publisher `/doi/suppl/.../suppl_file/...` 附件。 | 正文 figure/formula、Data Availability 链接、页内 `#supplementary-materials` 导航和 supplementary references 中的外部 PDF 不归 supplementary。 |
| ACS | 当前 Silverchair `.widget-ArticleDataSupplements` 中的稳定 publisher `/article-supplement/` 附件。 | 嵌入 Figshare viewer/downloader、正文 figure/table asset、citation/download chrome 和机构 OpenURL 链接不归 canonical supplementary。 |
| IEEE | 明确 Supplementary / Supporting Material / Multimedia section，IEEE 附件语义容器，或 landing metadata `sections.multimedia=true` 加 `/rest/document/{article_number}/multimedia` payload；只有 `asset_profile=all` 下载这些附件。 | `asset_profile=body` 只下载正文 figure/table/formula；正文 `data` / `dataset` / `code` / `media` / repository 链接和文件后缀不能单独触发 supplementary。 |
| Copernicus | NLM/JATS XML 中的 `supplementary-material`、`inline-supplementary-material` 和明确 `xlink:href` 附件节点。 | 正文 Data/Code Availability 普通仓库链接不凭文本或后缀升级为 supplementary。 |
| IOP | 正文页的 `#supplDataLink` 或同 DOI `/article/{doi}/data[N]` 入口只是索引；复用文章浏览器 cookie/Referer 打开索引页后，只接受 `#supplementarydata` 内 `id=SM数字` 的真实附件。 | `/data` HTML 本身、正文 figure 的 Standard/High-resolution 控件、页脚 WeChat QR 和未编号链接都不归 supplementary；索引 challenge、DOI 不匹配或空附件必须记录 asset failure。 |

- 边界说明：
  - 这条规则不定义每个 publisher 的完整 DOM selector、REST endpoint 或 URL allowlist；这些细节由 provider-specific helper 维护，本文只保留用户可见 contract。
  - 它也不限制附件文件类型。只要来源 scope 明确，supplementary 可以是 PDF、Office 文档、压缩包、数据表、图片或视频。
  - IOP 附件下载仍即时使用 publisher 返回的 AWS 签名 URL，但最终资产/失败诊断会复用 HTTP URL 脱敏规则隐藏 `X-Amz-*`、`Signature` 和 `AWSAccessKeyId` 值。

<a id="rule-filter-publisher-ui-noise"></a>
### 出版社站点 UI 噪声不能泄漏进最终 markdown

- 出版社页面里的操作按钮、图窗入口、站点工具栏和明显的站点动作词，不能随着 HTML 提取或后处理一起混进最终 markdown；`Permissions`、`Rights and permissions`、`Open Access` 这类站点许可 / 操作节只能按 heading 或 section 结构过滤，不能扩成普通正文词面 denylist。
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

- 通用 HTML metadata 抽取只能把真正的论文元数据写进文章模型，不能把站点级 description、标题回显或 redirect stub chrome 误当成摘要；如果页面只是 redirect stub，但里面确实带着可靠 lookup title，也要保留下来供后续解析链使用。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/_scenarios/generic_metadata_boundaries/generic_description.html`](../tests/fixtures/golden_criteria/_scenarios/generic_metadata_boundaries/generic_description.html)
  - [`../tests/fixtures/golden_criteria/_scenarios/generic_metadata_boundaries/redirect_stub.html`](../tests/fixtures/golden_criteria/_scenarios/generic_metadata_boundaries/redirect_stub.html)
  - `_scenarios/generic_metadata_boundaries` 是 metadata contract scenario，不是 DOI 级真实 replay。
- 边界说明：
  - 这条规则不是承诺所有 publisher 的隐藏字段或脚本变量都会被完整解析。
  - 它只约束“不要制造假摘要、不要丢掉后续解析必需的 lookup title”。

<a id="rule-html-availability-contract"></a>
### HTML fulltext / abstract-only 判定必须和用户可见访问状态一致

- availability 判定必须把真正可读的正文 HTML 识别成 fulltext，同时把 access gate、abstract-only 页面和带登录 chrome 的摘要页识别成 abstract-only；不能因为站点噪声、机构登录提示或 ancillary sections 把结果判反。
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
  - Springer 的准备／PDF 恢复路径必须保留已有 HTML 失败的具体诊断：`springer_html` trace 携带诊断失败码（例如 `abstract_only`）、说明和 HTTP 状态；有落盘诊断时以 `target` 关联其路径。PDF 成功后仍保留该事件及 `content.diagnostics.html_failure`，供最终失败原因与降级验收使用。

<a id="rule-provider-owned-authors"></a>
### Provider 自有作者与摘要信号必须进入最终文章元数据

作者备用结构的真实依据须区分自然触发与共存：arXiv 单个 creator 的 person-names 回退有原文；Wiley/Springer/Science/PNAS 的备用结构可与首选来源共存，不因此证明首选字段自然缺失；Springer 表格子页的 JSON-LD 不作为文章页回退证据。保留既有 pipeline 顺序。Springer DOM 遍历命中作者 li 时，若含显式姓名节点，复用该节点文本，避免带单位序号的外层文本再次作为作者输出。对应真实断言见 [test_original_author_branches.py](../tests/golden/test_original_author_branches.py)。

- publisher 自己暴露的作者与摘要信号，一旦已经被识别出来，就要稳定进入最终文章模型；优先使用更结构化的 provider-owned 信号，缺失时再回退到 DOM。
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

<a id="rule-short-markdown-image-alt-labels"></a>
### Markdown 图片 alt 只保留短标签

- 系统生成或重写的 Markdown 图片行必须只使用短 alt 标签；figure 输出 `Figure N` / `Figure`，table 输出 `Table N` / `Table`，listing 输出 `Listing N` / `Listing`，formula / equation 输出 `Formula`，其它图片输出 `Image`。完整 caption 必须保留在下一段或原正文 caption 中，不能塞进 `![alt]`。
- 代表性 HTML / XML：
  - 当前无稳定 DOI 样本，直接见对应测试；复杂 caption 与本地资产改写已进入“无稳定 DOI 样本规则汇总表”。
- 边界说明：
  - 这条规则不删除 caption，也不改变 `Asset.heading` / `Asset.caption` 数据；它只约束最终 Markdown 图片引用行。
  - 第三方原始 Markdown 只有在项目注入图片或重写图片链接时才会被短 alt 规范化。
  - `Figure 2.2`、`Figure A.1` 这类结构短标签必须保留；它们不是长 caption。
  - 本地化时优先保留当前正文出现位置的图号；同一图片文件可在不同位置对应不同图号。仅当当前 alt 缺少编号时，才使用资产 heading 补足。DDPM 原文的 Figure 13/14 与 Figure 1/6 复用文件，但图号不能被覆盖。
  - `Listing 1` 这类代码清单标签也是结构短标签；publisher 把 listing 作为 figure image 发布时不能降级成 `Figure` 或 `Image`。

<a id="rule-rewrite-inline-figure-links"></a>
### 已下载的正文图片和公式图片要改写成正文附近的本地链接

- 正文里已经有 figure、table image 或 formula image 锚点时，最终 markdown 应该尽量把远程图链接或绝对本地路径改写成当前 markdown 文件可用的本地资源链接，而且图和图之间不能误绑；只有真实存在的本地文件才能生成相对路径。未匹配本地资产的 `/cms/...` 根相对链接应使用有效的 publisher `landing_page_url` 补成完整远程 URL；没有有效 HTTP(S) 基址时保留原链接。改写后还要重新规范 Markdown 图片块边界和短 alt 标签，不能让图片和标题、正文句子或公式围栏粘在一起。
- IEEE Xplore 的 `div.figcaption` 在 provider 内转换为语义 `figcaption`，保留嵌套 JATS `fig` 中的图注；否则正文只剩图号。真实 [`TDEI 原文`](../tests/fixtures/golden_criteria/10.1109_TDEI.2024.3373549/original.html) 的 Fig. 1 图注、图片身份和原位输出由 [`IEEE 回放`](../tests/golden/test_ieee_provider_pdf_golden.py) 验证。
- Springer/Nature 的 Box 和新闻图片 `img.src` 若为 `//media...`，由 `providers.html_springer_nature` 在原始 DOM 渲染入口按同篇 `source_url` 补足协议；不改变资产清单的本地路径、full/preview 字段或下载状态，不在最终 Markdown 全局替换。补协议后仍沿用既有图片身份匹配与尺寸选择。[三篇真实来源回放](../tests/golden/test_relative_image_sources.py) 核对 `s42003-021-02908-2`、`d41586-022-01795-9`、`d41586-023-01829-w` 的三处源图地址及 provenance。
- 公式图片锚点只能按 formula 资产改写；它不能被 inline figure 注入逻辑当作 figure 占位，也不能消耗后续正文 figure 的本地资产。
- PLOS XML 的最终文件渲染按完整远程地址匹配已下载资产，保留查询参数中的对象身份；未匹配的公式必须保留原远程引用，不能通过共享的 `/article/file` 路径或文件名绑定到另一公式。[整篇部分下载回归](../tests/golden/test_plos_partial_asset_output.py) 覆盖 0/1/2/7 个公式下载完成条件。
- arXiv 源码图优先按 HTML 图片路径与源码成员唯一对应；只有 HTML 缺少地址或使用生成占位地址时，才允许高相似且唯一的图注匹配。不能按图索引或第一个剩余成员填充缺口；同一成员在原文不同位置合法复用时应全部保留。
- arXiv 源码下载记录保留 HTML 图地址作为 `original_url`，源码压缩包及成员继续记录在 `download_url`、`source_url`、`source_path`。插图按图号、来源别名及出现位置判断是否已有图片，不能全文按文件名去重。
- arXiv 组装保留未下载正文图，并核对最终 Markdown 图片与原始正文 figure 节点；未本地化的正文图必须进入资产验收分母。文章首页的博客、搜索等外围图标不计入正文资产。`none` 不下载资产，但文章模型仍可保留发现记录。
- arXiv 嵌套算法／表格的占位符应在其原文外层 figure 位置回填，不能因渲染器跳过容器而默认认为文末追加保留了原文顺序；无法定位时继续输出位置丢失诊断。回归见 [arXiv 复核测试](../tests/golden/test_arxiv_review_regressions.py)。
- 已存在的 Markdown 图片块会按 alt 和图片 URL basename 提取 `Figure N` 去重键；即使 caption label 暂时不可用或同一 figure 资产重复出现，正文里的 `Figure N` 交叉引用也不能再触发第二次插图。
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
    - [`../tests/golden/test_arxiv_provider.py`](../tests/golden/test_arxiv_provider.py) 中的 `test_html_route_inlines_single_official_html_figure_without_trailing_figures`
    - [`../tests/golden/test_arxiv_provider.py`](../tests/golden/test_arxiv_provider.py) 中的 `test_html_route_inlines_all_images_from_shared_caption_figures_once`
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

- HTML-derived Markdown 中已经识别出的数字引用 sentinel 要稳定渲染为 `<sup>...</sup>`；引用前缀和周边标点要清理到可读形态；同时不能把普通数字文本、年份范围、同位素上标或 Markdown 图片 opener `![...]` 当成引用标点处理。
- 代表性 HTML / Markdown：
  - 当前以 shared citation unit tests 覆盖；真实 provider 回放中出现的 DOI 级 citation DOM 归各 provider 结构规则承载。
- 边界说明：
  - 这条规则不尝试修复 publisher 源 HTML 里语义已经损坏的 citation range；它只约束共享 Markdown normalize 层不能制造新的坏标点或破坏图片块。
  - 括号引用识别的 160 字符上限是保守阈值，用来避免跨长段误吞普通括号内容；放宽该阈值需要新增长段误吞和真实 citation fixture 覆盖。
  - Springer/Nature inline article link unwrap、Extended Data label 和 figure-line pattern 位于 provider helper，由调用方显式传入 `clean_citation_markers()`；shared 默认只保留通用 numeric/label cleanup。
  - `<sup>` / `<sub>` 前空格由 shared inline token joiner 决定：citation sentinel 和括号脚注默认 tight；源 HTML 原本无空格的上下标邻接保持 tight；源 HTML 原本有 prose 空格时默认保留。额外收紧只允许基于通用 symbol-shape 规则，例如 signed numeric superscript after compact symbol、短单位形态的 unsigned numeric superscript、uppercase chemical-like base 的 numeric subscript，以及单字母/斜体数学符号的 numeric sup/sub；不维护单位或化学 base 白名单。
  - HTML/XML 的科学上下标不得在 provider DOM 清理、标题、摘要、图注或表格路径中展平成普通文字。Royal Society、MDPI、Science/Wiley 标题、OUP 表内 MathML、Annual Reviews 表内脚注及 Taylor & Francis 布局列表均使用现有行内／公式渲染器保留其结构；这不改变 PDF 转换边界。
  - Provider-specific reference payload、bibliography 抽取和 Crossref fallback 优先级不属于本规则。

<a id="rule-image-download-tier-diagnostics"></a>
<a id="rule-image-download-validates-real-images"></a>
### 图片下载必须验证真实图片内容

- 正文图片下载不能把 Cloudflare challenge HTML、Chrome 图片查看器壳或过小的站点图标当成论文图片保存；preview 图只有尺寸达标或 provider 明确接受，并在 `Asset.preview_accepted` 中保存该事实时，才算可接受结果。publisher 只提供的规范公式位图属于显式 accepted preview，不要求伪造 full-size tier。下载后的统一审计必须用 `filetype` 读取真实 MIME、用 `imagesize` 读取尺寸，并记录文件实际字节数和 `SHA256`，不能信任扩展名、响应头或 provider 声明值代替文件事实。
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

- 成功或失败的资产下载都要保留足够诊断信息；成功图片记录请求 profile、逻辑 kind、`download_tier`、路径、下载 URL、原始 full-size / preview 候选 URL、声明 content type、真实 MIME、实际字节数、尺寸、`SHA256` 和 provenance，失败资产保留 failure code、status、content type、snippet、reason 和 recovery 轨迹。结构化摘要必须同时给出 `requested`、`total`、`full_size`、`preview`、`failed`、`placeholder_suspected`、`not_requested`、`not_archived`，以及按 kind 的同类计数。
- 如果违反，用户只会看到笼统的 `asset_download_failure`，看不出是 full-size 被拦截、preview 可接受、supplementary 失败，还是图片真的缺失。
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

- 使用 browser workflow 的 provider 在下载正文 figure / table / formula 图片时，必须以 `RuntimeContext` / browser runtime facade 管理的 selected-browser context 作为主链路。同一进程内按 browser 配置复用 keyed browser manager，每个阶段创建隔离的 seeded context/page，preview fallback 也通过同一调用线程的 context 获取。Atypon/AMS 这类 lazy image 页面里的 `Blank.svg` / `Blank.png` 只允许作为待加载占位信号，不能作为成功正文 asset 保存；当 `download_url` / `full_size_url` 指向真实 `full-*.jpg` 时，下载候选和最终 `source_url` 必须指向真实图片响应。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html`](../tests/fixtures/golden_criteria/10.1073_pnas.2309123120/original.html)
    - [`../tests/unit/test_browser_asset_download.py`](../tests/unit/test_browser_asset_download.py) 中的 `test_browser_workflow_image_candidates_prefer_download_url`
    - [`../tests/unit/test_browser_asset_download.py`](../tests/unit/test_browser_asset_download.py) 中的 `test_browser_image_payload_rejects_blank_placeholder_url`
    - [`../tests/unit/test_atypon_browser_workflow_provider_asset_downloads.py`](../tests/unit/test_atypon_browser_workflow_provider_asset_downloads.py) 中的 `test_pnas_provider_download_related_assets_recovers_original_through_shared_browser`
    - [`../tests/unit/test_atypon_browser_workflow_provider_retries.py`](../tests/unit/test_atypon_browser_workflow_provider_retries.py) 中的 `test_wiley_provider_download_related_assets_uses_shared_browser_primary_path`
    - [`../tests/unit/test_atypon_browser_workflow_provider_retries.py`](../tests/unit/test_atypon_browser_workflow_provider_retries.py) 中的 `test_wiley_provider_download_related_assets_reuses_shared_browser_fetcher_across_assets`
    - [`../tests/unit/test_atypon_browser_workflow_provider_asset_downloads.py`](../tests/unit/test_atypon_browser_workflow_provider_asset_downloads.py) 中的 `test_ams_provider_download_related_assets_downloads_full_size_figure`
- 边界说明：
  - 这条规则目前适用于 `wiley`、`science`、`pnas`、`ams`、`annualreviews`、`royalsocietypublishing`、`acs`、`iop`、`aip`、`mdpi` 的 browser workflow HTML 成功路径。
  - 它不改变 `elsevier` XML、`springer` direct HTML 或 PDF fallback 的下载语义。

<a id="rule-table-flatten-or-list"></a>
### 表格能展平就转 Markdown 表，展不平就退成可读列表

- HTML、JATS 和 CALS 表格先进入同一个 provider-neutral cell/row IR 与占位网格规范化器；多级表头、rowspan 和局部 colspan 能安全展开时生成 Markdown 表并归为正常规范化，重叠、越界、ragged 或超限网格则退成保留 cell 文本的可读列表。无可靠编号和 caption 的表格不能额外输出孤立 `**Table**` 标题；无可靠表头时不能把 `Column 1` 这类内部占位当成用户可见表头。表头前覆盖整表宽度的标题提升为普通文本，正文中的整表宽度分组保留为首列分组行；不同分组下的列名仍要扁平化为 `Configuration / n_r`、`Inference / MMLU` 这类可读表头。
- Science 对明确单行表头、无嵌套表及无 `rowspan` / `colspan` 的源表，可将短数据行缺失的尾格留空，保留浏览器的列顺序；必须附源缺格说明，不能补造缺失文本。`sciadv.abj3309` 表 3 末行只有两个源单元格，原文第二格止于 “at year”，第三格缺失；输出保留三列并留空第三格，三项表格退化/语义损失计数为零，因为已有字段及列结构均被保留。复杂跨度与其他 provider 继续使用既有规则。回归见 [`../tests/golden/test_science_springer_source_boundaries.py`](../tests/golden/test_science_springer_source_boundaries.py)。
- Science 的局部 HTML 归一化将超出 `thead` / `tbody` / `tfoot` 实际剩余行数的 rowspan 限定在当前行组内；`sciadv.adm9732` 最后 3 行误写 rowspan=4，修复后 Covariates 续行保留在所属模型的第 7 列。回归：[`test_science_real_tables_preserve_headers_cells_and_scripts`](../tests/golden/test_atypon_browser_workflow_markdown.py)，输入为 [`original.html`](../tests/fixtures/golden_criteria/10.1126_sciadv.adm9732/original.html)。共享表格的非法 span 降级规则不变。
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

- 同一个 XML 表题下出现多个 CALS `tgroup` 时，每组必须使用自己的 `cols` / `colspec`、表头、正文行和源内前缀独立解析，并按源顺序渲染为多个 Markdown 网格或可读列表；没有 `tgroup` 的 HTML-like JATS 表继续作为单组处理。表格编号、caption 和脚注只输出一次，`(a) WBGT` 这类源内分组前缀放在对应网格之前；源中没有分组标题时只分隔网格，不能虚构标题，也不能把不同列宽强行拼成一张表。
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

- HTML `<ol>` 应渲染为 Markdown `1. item` / `2. item` 编号列表，不能先把 LaTeXML 或 publisher 的可见 item marker 当正文，再额外套一层 bullet，形成 `- 1.` 后接正文的坏列表；HTML `<ul>` 应保留 Markdown `- item` bullet，但要去掉条目开头由上游 HTML 显式输出的 `•` / `◦` / `▪` 这类无序列表 marker，不能形成 `- •` 后接正文的双 marker。
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

- arXiv official HTML 中 panel figure 可能没有自己的 `figcaption`，并且图片只有 `alt="Refer to caption"` 这类占位文本；最终 Figures 附录的图片 alt 不能退化成泛化的 `Figure`，而应在 caption 缺失时从 LaTeXML DOM id 推出结构短标签，例如 `S4.F2.2` 渲染为 `Figure 2.2`。
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

- LaTeXML 会把多个主图和多个 `figcaption` 放进同一个 `<figure>`，例如同一个 DOM 节点里连续出现 `Figure 9` / `Figure 10` 或 `Figure 11` / `Figure 12` / `Figure 13`。资产抽取必须按图片顺序产出多条 figure asset，正文 Markdown 也必须把多个 caption 渲染成独立块，并把可匹配的图片链接原位内联到对应 caption 附近。
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

- arXiv official HTML route 只能从清洗后的 `article.ltx_document` 正文流收集 section hints；`Abstract` 不标记为正文，`References` / `Bibliography` 与 Data / Code Availability 继续按共享语义分类，其它由正文渲染链路输出的 article DOM 标题默认标记为 `body`，包括 `Metrics.`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06667v1/original.html`](../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06667v1/original.html)
  - 这个样本能证明 `Metrics.` 是 arXiv article DOM 中的正文小标题，后续 `Table 1` 和正文指标说明必须作为 body 保留。
- 边界说明：
  - 这不是 `Metrics` 标题白名单；规则依据是 arXiv official HTML 的 LaTeXML article DOM 结构和正文渲染链路。
  - 非 arXiv provider 仍使用共享 `metrics` 噪声语义；arXiv 页面外部的 metrics / citation chrome 也必须继续被排除。
  - `article.ltx_document` 内已经删除的 frontmatter、TOC/nav/header/footer、bibliography 内部条目和 LaTeXML chrome 不应产生正文 section hint。

<a id="rule-arxiv-html-artifact-cleanup"></a>
### arXiv LaTeXML HTML 伪影不能泄漏到最终 Markdown

- arXiv official HTML 路径需要清理明确的 LaTeXML 转换伪影，包括 `Refer to caption` 图片占位 alt、重复 footnote marker、裸 `****` 表格标题、`Column N` 占位表头、重复分组行、可见 list marker、TeX annotation 内部嵌套 `$...$` 定界符、普通 prose 的源 HTML 硬换行和未定义宏噪声。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06665v1/original.html`](../tests/fixtures/golden_criteria/10.48550_arxiv.2605.06665v1/original.html)
  - 这个样本覆盖 footnote marker、空 label 表格、首行标题推断和多图 caption。
- 边界说明：
  - 清理只针对确定的转换伪影；真实正文中的强调、项目符号、脚注内容、表格数据、display math、代码块和独立图片块必须保留必要换行。
  - official HTML 缺失的内容不从 PDF 猜测重建。

<a id="rule-stable-frontmatter-order"></a>
### 前言摘要族的顺序与去重必须稳定

- teaser、`Significance`、`Structured Abstract`、`Abstract` 这类前言摘要块一旦已经被识别出来，就必须在最终 markdown 里按阅读顺序稳定出现，不能重复注回正文；只有在确实需要把前言和正文切开时，才插入一次 `## Main Text`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_science.abp8622/original.html`](../tests/fixtures/golden_criteria/10.1126_science.abp8622/original.html)
  - 这个样本能证明 Science frontmatter 里的 teaser、`Structured Abstract`、`Abstract` 和正文边界需要稳定保留。
- 边界说明：
  - 这条规则不是要求所有文章都必须同时出现 teaser、`Significance`、`Structured Abstract` 和 `Abstract`。
  - 它约束的是“已识别前言块的顺序、去重和正文边界”，不是要求每个 publisher 都使用同一套标题名称。

<a id="rule-keep-parallel-multilingual-abstracts"></a>
### 并行多语言摘要要并存，单语非英文正文不能被误删

- 如果页面或 XML 里明确存在并行的多语言摘要块，就要把它们都保留下来；如果只有单语的非英文摘要或正文，也必须原样保留，不能因为语言过滤把整篇文章删空。
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

- `Data Availability`、`Code Availability`、`Software Availability`、`Data, Materials, and Software Availability` 这类 availability 声明一旦被结构信号识别，就必须作为 retained non-body section 保留且最终只出现一次；纯 `Data Availability` 映射为 `data_availability`，纯 `Code Availability` / `Software Availability` 映射为 `code_availability`，混合标题保留完整内容并归入稳定 availability kind；`data_availability` 和 `code_availability` 不计入 fulltext body metrics；provider 传入的 dict、对象或 `SectionHint` dataclass hints 必须按同一 heading key 和 declared order 适配。
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
<a id="rule-availability-excluded-from-body-metrics"></a>
<a id="rule-section-hints-normalize-availability"></a>
<a id="rule-keep-headingless-body-flat"></a>
### 无节标题正文必须保持扁平

- 当文章正文本来就直接以连续段落展开、没有可靠的 body heading 时，组装和渲染阶段不能人为包一层重复标题、`## Full Text` 或同义伪节；如果需要区分前言和正文，最多只插入一次 `## Main Text` 作为边界。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_science.aeg3511/original.html`](../tests/fixtures/golden_criteria/10.1126_science.aeg3511/original.html)
  - 这个样本能证明无显式正文小节时，文章正文应保持扁平展开而不是被包成伪章节。
- 边界说明：
  - 这条规则不是说 `## Main Text` 永远不能出现。
  - 它约束的是“没有可靠正文节标题时不要硬造一层节结构”，不是禁止在前言和正文之间加一个必要的边界标题。

<a id="rule-preserve-subscripts-in-headings"></a>
<a id="rule-preserve-inline-semantics-in-body-and-tables"></a>
### 正文、标题和表格里的行内语义格式不能被打平或拆裂

- 标题、节标题、frontmatter、正文段落、图表 caption 和 Markdown 表格单元格里已经识别出的上下标、斜体变量、变量下标和 inline MathML operator，必须先保留为 text / citation / sup-sub / math / br 等结构化 inline token，再由 shared joiner 或 provider-owned inline renderer 统一决定空格；不能在清洗或渲染时被打平成普通空格文本，也不能被错误地拆成断开的 token。行内 HTML spacing 只在 citation、括号脚注和高置信 symbol-shape tight 场景收紧，默认保留 prose 空格。
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
    - [`../tests/golden/test_atypon_browser_workflow_markdown.py`](../tests/golden/test_atypon_browser_workflow_markdown.py) 中的 `test_pnas_full_fixture_keeps_data_availability_and_renders_table_markdown`
    - [`../tests/golden/test_atypon_browser_workflow_postprocess.py`](../tests/golden/test_atypon_browser_workflow_postprocess.py) 中的 `test_pnas_real_fixture_renders_table_and_inline_cell_formatting`
    - [`../tests/golden/test_atypon_browser_workflow_markdown.py`](../tests/golden/test_atypon_browser_workflow_markdown.py) 中的 `test_wiley_full_fixture_extracts_body_sections_from_real_html`
    - [`../tests/golden/test_atypon_browser_workflow_postprocess.py`](../tests/golden/test_atypon_browser_workflow_postprocess.py) 中的 `test_science_real_frontmatter_fixture_preserves_structured_summaries_and_main_text`
    - [`../tests/golden/test_ams_provider.py`](../tests/golden/test_ams_provider.py) 中的 `test_ams_aies_fixture_preserves_inline_mathml_formulas`
    - [`../tests/golden/test_ams_provider.py`](../tests/golden/test_ams_provider.py) 中的 `test_ams_caption_inline_markup_is_preserved`
    - [`../tests/golden/test_ams_provider.py`](../tests/golden/test_ams_provider.py) 中的 `test_ams_inline_renderer_preserves_body_subscripts_and_spacing`
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_split_inline_variable_subscripts_are_rejoined_in_paragraphs`
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_inline_boundary_newlines_are_normalized`
- 边界说明：
  - 这条规则只约束已经识别成行内语义的内容，不承诺对复杂公式、整段 MathML 或所有数学符号做完整排版。
  - 它也不是说所有英文字母组合都必须自动识别成变量加下标。
  - AMS 的 `inline-formula` 常把真实 MathML 放在 `script[type="math/mml"]`，caption 和正文也常包含斜体变量、连续下标和上下标后的 prose 括号；AMS 归一化必须先暴露这些结构，再交给 AMS 专用 inline renderer 和共享公式转换器。

<a id="rule-ams-footnotes-stay-linked-to-body-markers"></a>
### AMS/BAMS 脚注必须集中在 Footnotes 小节

- AMS/BAMS HTML 中 `.footnoteGroup` 里的正文脚注要作为正文说明区的一部分集中输出，而不是在正文末尾散落成无标题 URL 或孤立段落。正文中的 `<sup>n</sup>` 标记必须保留，脚注条目使用 `<sup>n</sup> text`。
- 代表性 HTML：
  - [`../tests/fixtures/golden_criteria/10.1175_bams-d-24-0223.1/original.html`](../tests/fixtures/golden_criteria/10.1175_bams-d-24-0223.1/original.html)
- 边界说明：
  - 这条规则只处理 AMS/BAMS 显式脚注组，不把 References、Acknowledgments、Data availability 或普通 URL 段落识别成脚注。
  - 测试覆盖度低：当前只有 BAMS `footnoteGroup` fixture 锁住该行为；后续遇到非 BAMS AMS 脚注结构时应补 provider-specific replay。

<a id="rule-readable-equation-caption-spacing"></a>
### 公式块和图注句子的块间距必须可读

- `**Equation n.**` 和对应的 `$$...$$` display math 之间必须保持稳定的块级换行，公式后的解释句和 figure caption 的后续句子也不能被粘成一整块坏文本。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1126_science.adp0212/original.html`](../tests/fixtures/golden_criteria/10.1126_science.adp0212/original.html)
  - 这个样本能证明公式标签、display math、解释句和 figure caption 之间都需要稳定的块边界。
- 边界说明：
  - 这条规则不保证公式语义一定完全正确。
  - 它约束的是“公式块和图注句子的可读边界不能坏掉”，不是对编号体系或数学求值做承诺。
  - 当前直接 DOI 证据样本来自 Science；PNAS 后处理测试覆盖同一共享 spacing policy，后续不为凑数强行新增 fixture。

<a id="rule-preserve-formula-image-fallbacks"></a>
### HTML 公式图片 fallback 必须保留并进入资产链路

- HTML 中的 MathML、publisher fallback span、inline equation image 和 display equation image 要尽量转成可读公式；如果 MathML 无法转换或公式本来只以图片存在，就保留 `![Formula](...)`，并把它作为 `kind="formula"` 的正文资产候选进入下载和本地链接改写流程。
- Annual Reviews 的 `.disp-formula img` 根相对路径按原文 URL 补成绝对链接，保留正文编号及位置。新样本 [`annurev-control-090419-075625`](../tests/fixtures/golden_criteria/10.1146_annurev-control-090419-075625/original.html) 的公式 1、2 是 GIF，[`专项回放`](../tests/golden/test_annualreviews_provider.py) 验证链接和身份；人工转录见同目录 `reviewed-equations.json`，不宣称 OCR 或 LaTeX 转换。
- Annual Reviews 图注子树的公式图片只在图注内渲染，不作为该 figure 的独立主图再次枚举；渲染副本预先保留图注 Markdown，原 DOM 仍供公式资产发现使用。不按全文 URL 去重，其他源对象中合法复用的图片仍按源次数保留。`annurev-control-090419-075625` 的全部 128 幅独立公式图片（含 Figure 3 图注 124–127）、主图源顺序与 138 条书目见 [`对象回归`](../tests/golden/test_annualreviews_object_ownership.py)。
- display formula 的候选优先级必须是：可转换的 MathML / 显式 TeX、公式图片、非编号可见文本、`[Formula unavailable]`。`(1)`、`Equation 1.` 这类编号只属于 equation label，不能冒充 LaTeX，也不能抢在已有公式图片之前生成 `$$ (1) $$` 伪公式。
- 已经形成的完整 `$$ ... $$` display-math 块属于 Markdown 辅助块，正文后处理不能再用“短全大写 front matter”启发式把它删除；单独的 `$$` 围栏仍按原有块边界规则处理。
- 公式图片 URL 中的强信号（如 `_IEqN_HTML`、`_EquN_HTML`、`math-*`）优先于 figure-context 排除，即使裸公式图片位于 figure caption 中也必须进入 formula 资产链路；只有 URL 没有公式信号时，figure / Silverchair figure wrapper 才用于避免把普通正文图按文件名、alt/title 或 caption 中的 `Equation` 误判为公式。
- 只有公式 bitmap 候选且 publisher 没有更大版本时，下载结果继续如实记录 `download_tier="preview"`，同时设置 `preview_accepted=true`；它不伪装成 full-size，也不单独产生 `asset_fidelity_degraded`。
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

- 公式转换后的 LaTeX 要在公共 normalize 层修复 publisher-specific 输出，例如 MathML `mtext` 里出版商转义的标识符下划线、`\updelta` 这类 upright Greek 宏、`\mspace{Nmu}` 这类 KaTeX 不兼容间距，以及无语义的零宽 spacing（如 `\hspace{0pt}` 和 MathML 零宽连接符）。
- HTML MathML 的 `merror` 仅保留源中仍可读取的子结构（包括分数、指数及括号），不猜补或宣称修复上游公式；转换结果保留原始 `raw_mathml`，OUP 另在提取诊断与文章 warning 中保留源 `merror` 数量。
- `mspace` 的已知尺寸在真实转换 backend 入口统一保护并恰一次恢复：物理单位直接保留（例如 `40pt` → `\hspace{40pt}`），`em`/`ex` 保持相对单位，CSS `px` 按 `0.75bp` 换算；不能把 `pt` 当 `em` 生成异常 `mu` 间距。命名数学间距保留对应 `mu`，未知单位沿用既有转换行为。预处理复用有界安全 MathML 解析；标记恢复失败不得泄漏标记或静默删去间距。
- 两项真实全文回放见 [`../tests/golden/test_mathml_semantics.py`](../tests/golden/test_mathml_semantics.py)：OUP `btaa153` 与 PNAS `2310157121` 分别通过已安装的 `texmath` 和 `mathml-to-latex` backend；最小实际进程边界归 integration，尺寸及安全边界归 unit。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/_scenarios/formula_latex_normalization/samples.json`](../tests/fixtures/golden_criteria/_scenarios/formula_latex_normalization/samples.json)
  - `_scenarios/formula_latex_normalization` 锁住 publisher-specific LaTeX normalize 分支；它不是 DOI 级真实 replay。
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_repairs_identifier_escaped_underscores`
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_does_not_globally_replace_textbackslash`
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_rewrites_upgreek_macros`
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_rewrites_mspace_for_katex`
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_removes_only_zero_width_spacing`
    - [`../tests/unit/test_formula_conversion.py`](../tests/unit/test_formula_conversion.py) 中的 `test_normalize_latex_scenario_samples_are_katex_compatible`
    - [`../tests/golden/test_arxiv_provider.py`](../tests/golden/test_arxiv_provider.py) 中的 `test_html_route_normalizes_math_without_duplicate_fallback_text`
- 边界说明：
  - 这条规则不承诺所有 MathML 都能转换成功；失败占位和 provider-specific inline/display 行为由具体公式渲染规则约束。
  - `\textbackslash\_` 只修复夹在标识符字符之间的窄范围场景，不能全局替换正常文本里的 `\textbackslash`。`\mspace{Nmu}` 只在 `mu` 单位时改写为 `\mkernNmu`，其它单位保留原样；`\hspace{0pt}` 这类零宽 spacing 会移除，但非零宽 `\hspace{...}` 必须保留。

## Springer

Springer 的 `Ethics compliance` / `Ethics statement` 若在 DOM 中属于 Methods（或 Materials and methods / Methodology）section，须保留为正文小节，完整保留机构、许可编号、数字及相邻节顺序。该例外只作用于 provider 的 section hints；页尾 Ethics declarations、Competing interests 和全局伦理分类不变。真实两篇全文及同名页尾边界见 [`../tests/golden/test_science_springer_source_boundaries.py`](../tests/golden/test_science_springer_source_boundaries.py)。

提前发布通知页若只有摘要、无充分 HTML 正文，应进入既有 PDF 回退；通知本身不构成正文。真实 `s41419-026-09210-1` 回归验证 PDF 候选与目标身份传递，不将 PDF 转换质量纳入验收。

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
<a id="rule-springer-article-root-chrome-pruning"></a>
### Springer article root 必须避开站点 chrome

- Springer / Springer Nature HTML 提取必须先选到可信 article root，再剪掉保存文章、期刊 CTA、Aims and scope、Submit manuscript、重复标题块、`About this article` / 权限许可等站点 chrome；正文之外的科学 back matter 只保留 `Acknowledgements`、`Data Availability`、`Author Contributions` 这类论文内容节。
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

- Springer / Springer Nature HTML 中由多个 inline span 拼出的编号标题，最终必须渲染成带空格的真实标题。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html`](../tests/fixtures/golden_criteria/10.1007_s10584-011-0143-4/article.html)
  - 这个样本覆盖 Springer classic 编号标题由 inline span 拼接时的空格规范化。
- 边界说明：
  - 它不要求所有编号标题都改写成某个统一编号体系，只要求已存在的编号和标题文本不能粘连或重复。

<a id="rule-nature-main-content-direct-children"></a>
<a id="rule-springer-main-content-direct-children"></a>
### Springer / Nature main-content 必须按直接子节点顺序进入正文

- Nature HTML 的 `div.main-content` 不能只因为存在直接 `section` 就只渲染这些 `section`；必须按直接子节点顺序处理正文 `div.c-article-section__content`、可渲染正文 `div` 和 `section`，否则 Matters Arising 这类页面会把正文段落漏掉，只剩 `Reporting summary`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1038_s41586-020-1941-5/original.html`](../tests/fixtures/golden_criteria/10.1038_s41586-020-1941-5/original.html)
  - [2018 无 section 正文块原文](../tests/fixtures/golden_criteria/10.1038_s41556-018-0103-6/acquisition/requested-templates-2026-09-16/article-response.html)
  - [2019 Methods 内 Reporting summary 与正文外 Data availability 原文](../tests/fixtures/golden_criteria/10.1038_s41467-019-11472-7/acquisition/requested-templates-2026-09-16/article-response.html)
  - 真实 replay 分别覆盖正文 div 顺序和 Methods 内 Reporting summary；以各篇自然结构为准，不要求 Main、Data availability、Reporting summary 同级共存。
- 边界说明：
  - 已有 Matters Arising、2018 无 section 正文及 2018–2019 完整正文回放；提取和最终渲染均须保留各自的自然顺序。
  - 结构信号优先于单一 DOI：规则看的是 `main-content` 直接子节点顺序和正文容器形态，不以 `10.1038_s41586-020-1941-5` 本身作为特判。
  - 正文外的 `Data availability` / `Code availability` 仍然允许从 scientific back matter 补回，但已经在正文遍历中出现的 availability 节不能重复输出。

<a id="rule-springer-original-html-artifact"></a>
<a id="rule-springer-access-hint-disclaimer"></a>
### 访问提示、预览语和 AI 免责声明不能混进正文

- publisher 页面用来告诉用户“这里只是预览”“这是访问提示”“这段 alt 可能由 AI 生成”的站点说明，不能被当成论文正文或摘要输出。
- 代表性 HTML / XML：
  - [`../tests/fixtures/block/10.1007_s00382-018-4286-0/raw.html`](../tests/fixtures/block/10.1007_s00382-018-4286-0/raw.html)
  - [`../tests/fixtures/golden_criteria/10.1038_s44221-022-00024-x/original.html`](../tests/fixtures/golden_criteria/10.1038_s44221-022-00024-x/original.html)
  - 这两个样本分别覆盖 Springer paywall preview 句子和 Nature figure AI disclaimer。
- 边界说明：
  - 这条规则删除的是明显的站点提示，不是删除所有提到 `preview`、`AI`、`generated` 的正常论文句子。
  - 如果某段话本来就是论文正文内容，即使包含相同词面，也不能仅凭关键词去掉。

<a id="rule-springer-caption-precedence"></a>
### 正文 figure 优先相信正式 caption，不相信噪声 fallback

- 图已经有正式图题或图注时，渲染链必须优先使用这些正式内容，不能再把站点塞进来的 `data-title`、`alt`、朗读文本、下载入口和展示控件重新拼回图注里。
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

- 早期 Nature 文章里如果同时存在 `Methods Summary` 和 `Online Methods` / 早期方法结构证据，最终结构必须归一成“`Methods Summary` 一次、`Methods` 一次”，不能重复堆出两个同义方法章节。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1038_nature12915/original.html`](../tests/fixtures/golden_criteria/10.1038_nature12915/original.html)
  - 这个样本能证明早期 Nature 的 `Methods Summary` 与 `Online Methods` 需要按正文结构归一处理。
- 边界说明：
  - 这条规则不是要求所有论文都必须出现 `Methods Summary`。
  - 结构信号优先于早期 Nature 单 DOI 样本；`10.1038_nature12915` 只是证明早期页面形态，规则依据是同篇 parsed sections、section hints 或 source selector 暴露的方法结构。
  - 只有同篇 parsed sections 同时存在 `Methods Summary` 与 `Online Methods`，或 section hints / source selector 体现早期 Nature 方法结构时，才把 stripped `Methods Summary` body section 归一为 `Methods`。单独存在的真实 `Methods Summary` 正文节必须保留原 heading。

<a id="rule-springer-inline-table"></a>
### 正文内联 table 占位必须被真实表格替换，替不出来也不能把占位符漏给用户

- 正文里如果先放了一个 table 占位，后续拿到 table page 时要把真实表格插回原位置；如果 table page 最终没拿到真正的表，也不能把内部占位符直接漏给用户。对于 Springer/Nature inline table 节点，只要 label 是 `Extended Data Table N` 且存在匹配的 `/tables/N` 页面链接，若 table page 实际是图片响应或只能从 HTML 中提取 full-size image，应输出 `kind="table"` 的 table 图片资产；若解析失败，应输出明确的 `[Table body unavailable: ...]` 降级占位。
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

- 官方 PDF 的 HTTP 200 不能覆盖授权限制：响应头 `x-els-status` 明确声明 `limited to first page` 时，PDF route 返回 `no_access`，不把同篇首页预览报告为全文；其它 WARNING 或没有该声明的正常 PDF 仍走原有验收。真实输入与回放见 `tests/golden/test_acquired_publisher_inputs.py`。

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

- Elsevier XML 段落里的行内数学要留在正文行内，display formula 要单独渲染成公式块。若 `<formula>` 只通过 `<link locator="fx*">`（或 `xlink:href` 的末段）指向 `<objects>` 中的官方公式图片，渲染器必须按 object `ref` 选择最高优先级资源并在公式原位置输出图片；已下载时优先使用本地相对路径，`asset_profile=none` 时保留官方远程 URL。只有数学表达和官方图片都不存在时，才输出明确的 unavailable 占位并记录 `formula_missing`。
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

- `Supplementary data` 这类补充材料显示块不能混进正文叙述里，而是要统一落到文末的 `## Supplementary Materials` 区域，并保留基本的标题和说明。
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

- 凡是已经处在 appendix 语境里的 figure 和 table，就要继续留在 appendix 里渲染；即使正文提到 `Fig. A1` 或 `Table A1`，也不能把这些 appendix 资产提前到正文区。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.rse.2026.115369/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.rse.2026.115369/original.xml)
  - 这份 real Elsevier XML 同时覆盖 appendix figure、appendix table 和正文中的 appendix 交叉引用。
- 边界说明：
  - 当前三个 owner 测试分别锁定 appendix figure、正文交叉引用顺序和 appendix table；新增 appendix 形态时应继续补独立测试。
  - 这条规则不是说正文里不能出现对 appendix 图表的交叉引用文字。
  - 它约束的是 appendix 资产的实际渲染位置和上下文，而不是正文文字是否能提到它们。

<a id="rule-elsevier-table-placement"></a>
<a id="rule-elsevier-inline-figure-table-placement"></a>
### Elsevier 正文引用到的 figure / table 要就地插回

- Elsevier XML 正文里已经引用到的 figure / table 要尽量在引用位置附近渲染；没有正文锚点的浮动表才进入 `## Additional Tables`。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2021.126210/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2021.126210/original.xml)
  - [`../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml)
  - 这些 real Elsevier XML 覆盖正文图片插入和正文表格就地插回。
    - [`../tests/golden/test_elsevier_markdown.py`](../tests/golden/test_elsevier_markdown.py) 中的 `test_elsevier_table_placement_contracts`
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_article_from_structure_preserves_inline_elsevier_figures`
- 边界说明：
  - 本规则不要求没有正文锚点的 float 强行插入正文；这类图表仍可进入 Additional Figures / Tables。

<a id="rule-elsevier-consumed-figure-table-dedup"></a>
### Elsevier 已消费图表不得在尾部重复追加

- 已经在正文消费过的 Elsevier 图表必须通过 render state 或 consumed key 从尾部资产附录里过滤掉。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2023.130125/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2023.130125/original.xml)
  - 这个样本覆盖已消费表格避免尾部重复。
    - [`../tests/unit/test_models_render.py`](../tests/unit/test_models_render.py) 中的 `test_to_ai_markdown_skips_inline_assets_and_labels_additional_tables`
  - Provider 覆盖：
    - [`../tests/golden/test_elsevier_markdown.py`](../tests/golden/test_elsevier_markdown.py) 中的 `test_elsevier_table_placement_contracts`
- 边界说明：
  - 本规则只处理“已经消费过”的图表；未锚定或 appendix 语境的图表仍按对应规则输出。

<a id="rule-elsevier-complex-table-span-degradation"></a>
### Elsevier 复杂 span 表必须区分成功规范化与异常降级

- Elsevier CALS 的 `colspec` / `colname` / `namest` / `nameend` / `morerows` 必须进入共享 XML adapter 和网格规范化器。多层 `<thead>` 应按列合并成一个 Markdown header，合法跨度完成语义展开后归为 `normalized`，保留 `merged_span_expanded` 内部 reason，但不得产生 `table_layout_degraded` 或用户 conversion note；非法 span/列定义继续标记布局降级，冲突或不规则网格必须保留 cell 文本为可读列表，不能抛异常或误报语义内容丢失。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2021.126210/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.jhydrol.2021.126210/original.xml)
  - [`../tests/fixtures/golden_criteria/10.1016_j.rse.2024.114346/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.rse.2024.114346/original.xml)
  - [`../tests/fixtures/golden_criteria/_scenarios/elsevier_complex_table_span/original.xml`](../tests/fixtures/golden_criteria/_scenarios/elsevier_complex_table_span/original.xml)
  - real Elsevier XML 覆盖合法 span 不产生 conversion note 或 `table_layout_degraded`；scenario XML 锁住 span 表的语义展开细节。
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_complex_table_spans_are_normalized_without_quality_loss`
    - [`../tests/golden/test_elsevier_markdown.py`](../tests/golden/test_elsevier_markdown.py) 中的 `test_elsevier_real_complex_table_records_successful_normalization`
    - [`../tests/golden/test_elsevier_markdown.py`](../tests/golden/test_elsevier_markdown.py) 中的 `test_elsevier_real_multilevel_header_is_flattened_without_body_header_row`
    - [`../tests/unit/test_elsevier_markdown.py`](../tests/unit/test_elsevier_markdown.py) 中的 `test_elsevier_overlapping_cals_columns_use_readable_list_fallback`
- 边界说明：
  - scenario XML 锁住 span 展平细节，real XML 同时锁住多层表头、无表格 conversion note 和无误报质量标记。
  - 这条规则不是要求复杂表在 Markdown 里必须零损失复原。
  - 它约束的是“优先给用户可读的表格文本，并只对异常结构给出降级提示”，不是承诺所有单元格跨度都按源站视觉样式呈现。
  - `table_layout_degraded` 表示源 span/列定义异常导致原布局无法可靠验证；视觉合并关系被成功展开不属于质量损失，只有行列语义内容真的丢失时，才应升级为 `table_semantic_loss` / `figure_table_loss`。

<a id="rule-fulltext-reference-priority"></a>
### 全文 references 优先于 metadata/Crossref fallback

- 任何 fulltext provider 从 HTML / XML / 出版社 REST 成功抽取非空 references 时，文章模型和最终 Markdown 的 references 必须以这些全文/出版社 references 为准。metadata / Crossref references 只能在 provider references 为空、失败或不可用时兜底，不能在全文 refs 非空时追加未匹配的 title-only 或 DOI-only 条目。
- Provider 差异表：

| Provider | 全文 reference 来源 | Provider 小节只保留的差异 |
| --- | --- | --- |
| Elsevier | XML `<ce:bibliography>` / `<ce:bib-reference>` / `<sb:reference>`。 | 保留结构化 label、作者、题名、来源、页码、年份和 DOI；缺字段时保留 raw citation text 或显式占位。 |
| Wiley | HTML reference item 的可见 citation body。 | 清理 `Google Scholar`、`Crossref`、`getFTR` 和隐藏链接区，不把 DOI-only 链接当完整 reference。 |
| Science / PNAS | `#bibliography .biblioentry` 及旧版 `role=listitem` 的可见 citation body。 | 保留原编号、正文、DOI 与顺序；只有编号而 citation 容器为空的源节点不伪装成完整书目，也不重排后续编号。PNAS `2317456120` 捕获页有 22 个节点，其中 `r22` 为空，仅能恢复 21 条正文。 |
| IEEE | `/rest/document/{article_number}/references` 的可见 citation text。 | payload 非空时覆盖 Crossref / metadata fallback；payload 为空或不可用时才保留 fallback。 |

- 边界说明：
  - 这条规则不禁止 metadata-only 结果用 bullet 形式渲染 references；它只禁止在全文 references 非空时把 metadata/Crossref fallback 作为额外条目追加。

### PDF 引用与科学后置内容的分离

此旧规则已撤销，统一遵守 [PDF 转换边界](#rule-pdf-conversion-boundary)。不再要求从 PDF 转换文本恢复引用分条、拼接续行、清理页脚、调整编号或重建后置内容。已有 metadata／官方结构化引用按既有来源契约使用，不据此清洗 PDF 文本。历史测试入口保留在 [案例覆盖清单](fixture-content-coverage.md)，不作为 PDF 解析质量验收目标。

<a id="rule-elsevier-xml-references"></a>
### Elsevier XML 参考文献必须优先使用结构化 bibliography，保持编号和作者信息

- Elsevier XML 里存在 `<ce:bibliography>` / `<ce:bib-reference>` / `<sb:reference>` 时，文章模型的 `references` 必须优先从这些结构化节点构建，保留原始顺序、编号、作者、标题、来源、页码、年份和 DOI；字段缺失时必须回退到 visible raw reference text 或显式 `[Reference text unavailable]`，不能直接跳过 bib 条目。Crossref metadata references 只能作为兜底，不能在结构化 XML references 非空时追加未匹配条目。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.agrformet.2024.109975/original.xml)
  - 这个样本能证明 Elsevier XML bibliography 中的 label、作者、题名、期刊卷期页码和 DOI 需要进入最终 references。
- 边界说明：
  - 这条规则不要求所有 Elsevier 文献都有完整 DOI 或页码；缺失字段不能凭空生成。
  - 全文 references 与 metadata / Crossref fallback 的优先级归 [全文 references 优先于 metadata/Crossref fallback](#rule-fulltext-reference-priority)；本规则只约束 Elsevier XML 的来源和结构化字段保留差异。
  - 它约束的是“结构化 XML references 存在时必须优先使用并保持条目数量”，不是禁止在 XML 缺 references 时回退到 metadata references。

<a id="rule-elsevier-graphical-abstract"></a>
### Graphical abstract 不进入 Additional Figures

- graphical abstract 这类站点或期刊 frontmatter 资产不能混进 `## Additional Figures`，即使它们也有图片文件。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1016_j.scitotenv.2022.158499/original.xml`](../tests/fixtures/golden_criteria/10.1016_j.scitotenv.2022.158499/original.xml)
  - 这份 real Elsevier XML 覆盖 `class="graphical"` abstract figure 与正文 figure 同时存在的场景。
- 边界说明：
  - real XML 锁住 Graphical abstract 主干；两个最小资产归类测试分别覆盖“有正文 figure”和“只有 graphical abstract”两种边界。
  - 这条规则不是说 graphical abstract 必须从所有输出里彻底删除。
  - 它约束的是 graphical abstract 不能被误归到正文 figure 附录里。

## Wiley

- Wiley `.fallback__mathEquation[data-altimg]` 与紧邻的 `mjx-container` 内唯一 MathML 属于同一公式；provider 预处理将该图片地址绑定到公式并解析根相对地址。结构化数学仍优先，空 MathML 使用图片回退；不得跨正文或其他元素借用相邻公式图片。真实依据见 [gcb.16758 定向核验](fixture-records/problem-fixes-2026-09-18-p02.md) 与 [26 处公式 golden](../tests/golden/test_wiley_gcb16758_formulas.py)。链接输出验证不替代图片下载与可读性验收。

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

- 如果 Wiley 页面里存在 `Abbreviations` 区块，它可以作为正文后的辅助节保留，但不能提前到正文主线前面，也不能插进正文章节和正文表格中间打断阅读顺序。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1111_cas.16395/original.html`](../tests/fixtures/golden_criteria/10.1111_cas.16395/original.html)
  - [`../tests/fixtures/golden_criteria/_scenarios/wiley_abbreviations_trailing/original.html`](../tests/fixtures/golden_criteria/_scenarios/wiley_abbreviations_trailing/original.html)
  - real replay 能证明 `Abbreviations` 可以保留但只能放在正文和正文表格之后；scenario 锁住 frontmatter glossary 移到正文后的最小形态。
- 边界说明：
  - 当前只有一份 Wiley replay 加一个 scenario；后续若新增真实 Wiley abbreviations 页面，应优先补第二个 DOI 级 fixture。
  - 这条规则不是要求所有 Wiley 文章都必须输出 `Abbreviations`。
  - 结构信号优先于单一 DOI：规则看的是 `Abbreviations` 区块相对正文主线和正文表格的位置，不以 `10.1111_cas.16395` 本身作为特判。
  - 它约束的是“存在该区块时的落点”，不是强制生成一个缺失的缩写表。

<a id="rule-wiley-reference-text"></a>
### Wiley 参考文献必须使用可见 citation 文本而不是 DOI-only 或链接 chrome

- Wiley HTML references 要从可见 citation body 中抽取作者、题名、期刊等文本，删除 `Google Scholar`、`Crossref`、`getFTR` 和隐藏链接区，不能把 DOI-only 链接当成完整 reference。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.15322/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.15322/original.html)
  - [`../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html`](../tests/fixtures/golden_criteria/10.1111_gcb.16998/original.html)
- 边界说明：
  - 单测试规则：当前用一条参数化测试覆盖两份 Wiley replay，锁住可见 citation body 优先级；新增 Wiley reference DOM 变体时应继续扩充 fixture 参数或拆出独立测试。
  - 结构信号优先于单一 DOI：规则看的是 Wiley reference item 的可见 citation body 和链接 chrome 边界，不以 `10.1111_gcb.15322` 或 `10.1111_gcb.16998` 作为特判。
  - 全文 references 与 metadata / Crossref fallback 的优先级归 [全文 references 优先于 metadata/Crossref fallback](#rule-fulltext-reference-priority)；本规则只约束 Wiley HTML 的来源和清洗差异。
  - 这条规则只过滤 publisher reference chrome，不会补全原始 HTML 中没有的 bibliographic 字段。

## Science

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

- AMS HTML 要从 `#articleBody` / `.container-fulltext-display` 等完整正文容器抽取正文，保留后部 section、Acknowledgments 和 Data availability；正文中的 figure 与 image-only `.tableWrap` 要在原始位置渲染图片块与 caption；MathJax 渲染层旁边的扁平 fallback 文本不能和结构化公式重复出现；display equation 编号只来自源站明确 label 或 AMS `E...` 公式 id，`UE...` 无编号公式不合成 `Equation n.`；AMS 专用 inline renderer 要在正文和 caption 中保留 MathML、上下标和斜体变量，并保守修复上下标后 prose 括注的空格。
- AMS 默认用 selected-browser 请求 `journals.ametsoc.org/view/...xml`；浏览器 HTML 失败或正文质量门槛不通过时，沿用同一 runtime/storage-state 和页面 seed 尝试 AMS `downloadpdf` PDF fallback。
- AMS figure 资产候选必须优先使用源 HTML 的 `Download Figure` EPS/TIFF 链接，并保留网页 full-size JPG/PNG 作为回退；PowerPoint 下载项不是图片资产。EPS/TIFF 下载请求必须继承浏览器 UA/Referer，下载成功后应通过图片转换后端转成 PNG 用于 Markdown，本地同时保留原始源文件和转换元数据。
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

## Annual Reviews

- `.table-caption-container .table-label` 是表格标签，以普通加粗说明呈现，紧邻原图表说明和数据；不进入章节目录，也不沿用网页 H5 字号层级。文章后部已加载的 `#viewGlossaryPopup`、`#viewFootnotePopup` 分别将 Terms And Definitions、Footnotes 作为 H2，与文章主节同级，保留原内容和位置；不提升其他 modal 或真正的正文子标题。五篇九处源对象、表格全部单元格／表注、术语／脚注及相邻正文位置见 [`对象回归`](../tests/golden/test_annualreviews_object_ownership.py)。此规则只适用 HTML，不适用 PDF fallback。

## MDPI

- 正文图片的相对路径若与同页图集中显式 `https://pub.mdpi-res.com` 链接的完整路径一致，保留正文 URL 并将该 CDN 链接（含原 query）作为 `download_url`。不凭文件名拼接 CDN 地址；没有同路径链接时沿用原候选。真实 `math11030657` Figure 1 的原 HTML、PNG 和最终文章回放约束该行为，见 `tests/golden/test_acquired_article_assets.py`。
- 旧版 HTML 的科学附录可位于 `.html-back` 内：标题为 `Appendix` 的 `section[id^=app]` 需要连同正文复制，避免遗漏附录表格；父附录已纳入时不重复复制嵌套子节。这不包含 Supplementary Materials 下载区。真实 `math11030657` 的 Appendix A / Table A1–A4 约束该边界。
- 参考文献的 CrossRef 链接保留为 `Reference.doi`，同时继续清理可见引用中的 Google Scholar / CrossRef UI 文案；缺 DOI 时不生成字段。真实 `membranes15030093` 首、中、尾条约束作者、题名和 DOI。
- 表注中保留的书目／表格 fragment 若对应原 DOM 的书目或表对象，使用同篇 HTTP(S) 来源页的对象地址；表格弹窗 ID 按其 wrapper 显式链接映射到可见表对象 ID。原 HTML ID 不在 Markdown 输出中时不假造本地目标；无有效来源基址时保留无跳转文字。全部、部分、不输出参考文献或过滤附录时均保留对象身份。真实 `math11030657` 的 B68、B69、Table A4 见 `tests/golden/test_retained_object_links.py`。

<a id="rule-mdpi-browser-html-cleanup"></a>
<a id="rule-mdpi-display-object-anchoring-dedupe"></a>
### MDPI display object 必须按正文引用锚定并去重

- MDPI figure、table、HTML `<table>` 和正文中的 inline figure asset 必须在 DOM 阶段按正文首次 `Figure N` / `Fig. N` / `Table N` 引用附近回填；已经插入正文的 display object 不得在 Conclusions 后或尾部 appendix 再次出现；未引用对象只按源顺序插入 References 前；Markdown image alt 只能使用短标签，caption 不得写入 `![alt]` 并破坏 Markdown 语法。
- 代表性 HTML：
  - [`../tests/fixtures/golden_criteria/10.3390_su12072826/original.html`](../tests/fixtures/golden_criteria/10.3390_su12072826/original.html)
  - [`../tests/fixtures/golden_criteria/10.3390_rs16010010/original.html`](../tests/fixtures/golden_criteria/10.3390_rs16010010/original.html)
- 边界说明：
  - 复杂 HTML table 可以降级为单个去重文本块；这条规则不承诺所有 rowspan/colspan 都能无损还原，但不允许重复 caption、丢失锚定位置或拆成散乱多行字段。
  - 已在正文图片块消费的 figure / table 资产必须通过 URL、路径或 basename 等价关系从尾部 `Figures` / `Tables` 附录中过滤。
  - PDF fallback 不适用本 HTML display object 锚定规则；PDF 图片只由共享 PDF 转换导出并按正文 asset 记录。

<a id="rule-mdpi-formula-inline-display-rendering"></a>
### MDPI formula 必须区分 inline 与 display 渲染

- MDPI MathML 必须进入共享 MathML -> LaTeX 转换链路；`.html-disp-formula-info` 和 `math[display=block]` 渲染成 `$$ ... $$` Markdown 块并保留源站 `(1)` / `(2)` 编号；段落内 inline 公式、变量、上下标和 `html-italic` / `html-bold` 样式 wrapper 必须保持行内；没有 MathML 的 HTML-only 化学式 / 反应式必须保留 `<sub>` / `<sup>` 语义并压缩成单个公式块。
- MDPI browser DOM 中相邻且由 `MathJax-Element-*` / `*-Frame` 对应的 Preview、渲染 frame 和公式 script 属于同一个公式；只保留一份源 MathML，Preview 为空时使用 script 的 MathML / TeX，不能把渲染 UI 再输出为空公式。真正缺失的公式仍保留 `[Formula unavailable]`，MDPI 提取及文章质量的 `formula_missing_count` 必须对应实际占位数。
- 代表性 HTML：
  - [`../tests/fixtures/golden_criteria/10.3390_math11030657/original.html`](../tests/fixtures/golden_criteria/10.3390_math11030657/original.html)
  - [`../tests/fixtures/golden_criteria/10.3390_w15040758/original.html`](../tests/fixtures/golden_criteria/10.3390_w15040758/original.html)
  - [`../tests/fixtures/golden_criteria/10.3390_ijerph18094484/original.html`](../tests/fixtures/golden_criteria/10.3390_ijerph18094484/original.html)
  - [`s23010001 真实 browser DOM`](../tests/fixtures/golden_criteria/10.3390_s23010001/acquisition/assets-2026-09-15/mdpi-headless-002-browser_dom.html)：两处 CO₂ 的 Preview、frame、script 重复表示由 `tests/golden/test_mdpi_provider.py::MdpiProviderTests::test_mdpi_browser_dom_mathjax_formulas_are_not_duplicated` 回放；空 Preview、script fallback 和真正缺失边界由对应 unit 最小片段覆盖。
- 边界说明：
  - 段落内只包裹 inline 文本、citation、inline MathML、`<sub>` / `<sup>` 或样式 span 的 MDPI `div` wrapper 应在 provider DOM 阶段转为 inline；真正的 display formula、figure/table、HTML table、list、heading、section、references 不适用这条 inline 化规则。
  - 公式编号只保留源站显式编号；provider 不为了单调性重编号，也不为无编号公式创建 `Equation n.`。

<a id="rule-mdpi-references-numbering-link-cleanup"></a>
### MDPI references 必须保留源编号并清理站点链接

- MDPI reference `li data-content` 里的出版社编号必须写回 raw citation，并在最终 References 中保留为编号列表；Google Scholar / CrossRef / PubMed / Green Version 等 UI 链接不能进入 Markdown 或 reference raw text；全文 references 优先于 metadata / Crossref fallback。
- 代表性 HTML：
  - [`../tests/fixtures/golden_criteria/10.3390_w15040758/original.html`](../tests/fixtures/golden_criteria/10.3390_w15040758/original.html)
- 边界说明：
  - MDPI references 只保留源 HTML 已提供的编号；metadata / Crossref fallback references 不在 provider 内人工补号。
  - 只清理 reference UI 操作链接，不删除 citation 标题、期刊名、DOI 或正文内正常链接。

<a id="rule-mdpi-body-semantics-chrome-removal"></a>
### MDPI article body 必须保留正文语义并移除 chrome

- MDPI selected-browser HTML 只能从 article container 中抽取题名、摘要、正文 section、references、figures、tables、formula 和明确 supplementary section；article menu、下载按钮、分享/引用/metrics、SciProfiles 等站点 chrome 不能进入最终 Markdown，也不能通过全页后缀扫描把正文外链接误判为 supplementary；`#html-keywords` 只进入 `metadata.keywords`，不能进入 Abstract 或独立 Markdown section。
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

- ACS selected-browser HTML 必须把当前 `.article-body` 作为完整提取根，等待 `.article-body` / `.widget-ArticleFulltext` 稳定，并保留正文 section、table、`.fig.fig-section`、MathML formula 与 `.ref-list .ref`；Supporting Information 中动态加载的 Figshare `<article>` 不能被通用 content selector 误选为正文。
- 代表性 replay：
  - [`../tests/fixtures/golden_criteria/10.1021_acsomega.4c03987/original.html`](../tests/fixtures/golden_criteria/10.1021_acsomega.4c03987/original.html)：当前 Silverchair structure/table/figure/supplementary/reference 页面，8 个 figures、3 个 tables、45 条 references。
  - [`../tests/fixtures/golden_criteria/10.1021_acsomega.3c06992/original.html`](../tests/fixtures/golden_criteria/10.1021_acsomega.3c06992/original.html)：当前 Silverchair formula 页面，21 个 display formulas、2 个 tables、8 个 figures、20 条 references。
  - [`../tests/fixtures/golden_criteria/10.1021_acsomega.2c02828/original.pdf`](../tests/fixtures/golden_criteria/10.1021_acsomega.2c02828/original.pdf)：由 selected Camoufox runtime 捕获的当前 `article-pdf` fallback。
- 边界说明：
  - figure normalization 把一个 `.fig.fig-section` 折叠成一条带 label/caption 的正文图，不输出 `Open figure viewer`、`View Large`、`Close modal` 或重复 modal 文本；`/view-large/figure/` 仅保留为来源关联，不再触发额外查看器请求；正文真实 `DownloadImage.aspx` 包装必须继续解析为签名原图，CDN `m_*.png` 按 preview 质量规则处理。
  - references 必须从清洗前的 `.ref-list .ref` 提取可见 citation；优先读取 `.year`，并移除 Crossref/ADS/OpenURL 操作 chrome，再由 provider 渲染一份编号 references。
  - supplementary 只从清洗前的 `.widget-ArticleDataSupplements` 建立独立 scope，并只接受稳定 `/article-supplement/` publisher 链接；嵌入 Figshare downloader 不作为 canonical 附件。
  - PDF fallback Markdown 仍由共享转换器负责；页面 footer 和双栏 references 顺序是 PDF 布局限制，不应反向写成 ACS DOI 特例。
- 共享规则另见：
  - [出版社站点 UI 噪声不能泄漏进最终 markdown](#rule-filter-publisher-ui-noise)
  - [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope)
  - [浏览器工作流图片下载必须使用 shared browser 主链路](#rule-browser-primary-image-download-path)
  - [全文 references 优先于 metadata/Crossref fallback](#rule-fulltext-reference-priority)

## IOP

- 可见 bibliography 未加载时，可使用原始 HTML 的 `citation_reference` 元数据。空条目不生成引用，但保留后续条目的原始编号，避免正文引文错指；书籍条目保留 `citation_publisher`。真实 `ac3460` 的第 31 个 meta 为空，最后一条 Geurts / Extremely randomized trees 必须仍编号 45 并对应正文 `[45]`，不能重排为 44。

<a id="rule-iop-body-challenge-cleanup"></a>
### IOP article HTML 必须拒绝 challenge 并清理站点 chrome

- IOPScience selected-browser HTML 只能从 article body / `articleBody` 语义容器中抽取题名、摘要、正文 section、body table、formula image、figure caption 和 references；`Download PDF`、metrics、citation/export、导航、相关内容和 Radware/hCaptcha challenge 页面不能进入最终 Markdown。
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

- Royal Society Publishing 的 Silverchair HTML 图像资产必须从 `div.fig-section` 读取真实 figure label/caption，并把 `DownloadImage.aspx` 中的签名 CDN 原图、`/view-large/figure/` HTML 查看页和 `m_*` preview 分别建模为 `full_size_url`、`figure_page_url` 和 `preview_url`；查看页不能冒充原图。
- 正文章节链接在 Markdown 中保留同篇来源页的可定位目标：原始 `#fragment` 对应标题 `id` 时使用该 ID；Silverchair 的 `data-legacyid` 别名只按原 DOM 显式映射到标题真实 `id`。使用 HTTP(S) `source_url` 构成绝对链接，不猜测 Markdown 阅读器的标题 slug；没有明确目标或有效基址时保留原链接，其他链接不受此规则影响。真实回归：`10.1098/rsif.2019.0334` 的 6 个 `#s2` / `#s3` 链接。
- 代表性 HTML：
  - [`../tests/fixtures/golden_criteria/10.1098_rsta.2019.0558/original.html`](../tests/fixtures/golden_criteria/10.1098_rsta.2019.0558/original.html)
  - [`../tests/fixtures/golden_criteria/10.1098_rsos.150470/original.html`](../tests/fixtures/golden_criteria/10.1098_rsos.150470/original.html)
- 边界说明：
  - 这条规则只针对 Royal Society Publishing/Silverchair 的 HTML figure wrapper；共享 figure container 判定只接受真实 `<figure>`、精确 `class="figure"` 这类显式通用 figure 容器，或显式 Silverchair `fig fig-section` / `js-fig-section` / 受这些祖先约束的 `graphic-wrap`，不能因为普通正文 wrapper、section、anchor id/href 中出现 `-f` 或 `figure` 就提升为 figure。
  - 原图入口必须在删除 `.download-slide` 前从原始正文 DOM 提取；caption 仍从清理后的 DOM 获取，避免 `<sub>` / `<sup>` 等 inline markup 引入额外空格。
  - `DownloadImage.aspx` 的嵌套 URL 只接受 HTTP(S) Silverchair CDN host，保留 `Expires`、`Signature`、`Key-Pair-Id`，并要求原图 basename 与当前 figure 的 viewer/preview basename 一致；分组 slide 指向相邻 figure 时不能串图。
  - 同一逻辑 figure 的 viewer、原图和 preview 按 DOM id 与去除 `m_`/扩展名后的规范化 figure basename 合并；正文原图（包括真实 DownloadImage 包装中的 URL）优先；Royal 原文缺少匹配原图时继续从 viewer 发现，最后才使用 preview。rsos.150470 的分组 slide 会指向邻图，不能拿邻图原图代替当前图。
  - PDF fallback Markdown 统一由 shared `pymupdf4llm` 转换产生；`body/all` 且允许 artifact 落盘时，PDF 图片由 shared 转换导出到 `<doi>_assets/`。provider 负责获取并校验真实 PDF、设置 source/route；所有层均遵守 [PDF 转换边界](#rule-pdf-conversion-boundary)，禁止额外格式清洗。
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
<a id="rule-ieee-html-structure"></a>
### IEEE REST HTML 必须保留正文结构和标题层级

- IEEE Xplore REST `#article` HTML 要按真实 DOM 结构抽取正文，而不是依赖 synthetic 片段。`SECTION I.` 这类裸 marker 必须清理；`div.section` / `div.section_2` 嵌套层级必须保留为主节 `##`、字母子节 `###`、数字子节 `####`；`tex-math` / `disp-formula` 必须渲染成可见 LaTeX，不能输出 `[Formula unavailable]`。
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

- IEEE landing metadata 的 IEEE Keywords / Index Terms / Author Keywords 要进入 `metadata.keywords`；IEEE `/rest/document/{article_number}/references` 成功返回非空 references 时，文章模型必须使用该 payload 的可见 citation text，不能把 Crossref / metadata fallback 追加到 numbered references 后面。payload 不可用或为空时，才保留 metadata / Crossref references。
- 代表性 HTML / metadata：
  - [`../tests/fixtures/golden_criteria/10.1109_ACCESS.2024.3352924/landing.html`](../tests/fixtures/golden_criteria/10.1109_ACCESS.2024.3352924/landing.html)
  - [`../tests/fixtures/golden_criteria/10.1109_ACCESS.2024.3352924/references.json`](../tests/fixtures/golden_criteria/10.1109_ACCESS.2024.3352924/references.json)
- 边界说明：
  - 这条规则是 IEEE 对 [全文 references 优先于 metadata/Crossref fallback](#rule-fulltext-reference-priority) 的 provider 入口约束；不禁止 metadata-only 结果用 fallback references。

<a id="rule-ieee-mediastore-body-assets"></a>
### IEEE mediastore 正文图表资产必须锚定并按身份优先级去重

- IEEE dynamic HTML 中的正文 `figure-full` / `figure-full table` mediastore 图片必须抽取为正文 figure/table 资产，在首次 caption 位置以内联图片锚定；正文公式图片只能作为 formula fallback，不能抢占 table/figure 资产身份；`/assets/img/icon.support.gif` 这类 support icon 必须排除。
- 代表性 HTML：
  - [`../tests/fixtures/golden_criteria/10.1109_CICTN64563.2025.10932570/original.html`](../tests/fixtures/golden_criteria/10.1109_CICTN64563.2025.10932570/original.html)
  - [`../tests/fixtures/golden_criteria/10.1109_TBME.2024.3434477/original.html`](../tests/fixtures/golden_criteria/10.1109_TBME.2024.3434477/original.html)
- 边界说明：
  - 已锚定正文图表不得在尾部 Figures / Tables 附录重复追加，归共享 [正文已内联 figure 时避免重复追加尾部 Figures 附录](#rule-no-trailing-figures-appendix) 约束。
  - 这条规则只约束正文 figure/table/formula 资产；supplementary / multimedia 文件附件见 [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope)。

<a id="rule-ieee-html-access-waterfall"></a>
### IEEE HTML 可用性与 fallback 顺序

- IEEE block-page 检测只能使用人可见的页面文本；`script/style/svg/noscript/template` 中的 `captcha`、challenge 或 access token 不能拒收已经就绪的真实 `#article`。页面可正常发起自身 REST 子请求，DOM-only 验证不读取 REST response body 时也不能在网络层阻断该请求。可见区域中的验证码、人工验证或访问阻断文案仍必须 fail closed。
- provider 路由、REST/DOM readiness 和 PDF fallback 细节参见 [`providers.md` 的 IEEE provider 说明](providers.md#ieee)。

本规则只约束检测语义，不改变既有 route 顺序。

## Copernicus

- 共享规则另见：
  - [全文 references 优先于 metadata/Crossref fallback](#rule-fulltext-reference-priority)
  - [Supplementary discovery 必须来自明确附件 scope](#rule-supplementary-discovery-explicit-scope)
  - [表格能展平就转 Markdown 表，展不平就退成可读列表](#rule-table-flatten-or-list)
  - [LaTeX normalization 必须产出 KaTeX 可渲染表达](#rule-formula-latex-normalization)
  - [Availability section contract 必须保留、归类、排除正文度量并适配 hints](#rule-keep-data-availability-once)

<a id="rule-copernicus-xml-jats-rendering"></a>
### Copernicus NLM/JATS XML 必须保留正文结构、公式、图表和 references

- Copernicus XML 主路径要从 NLM/JATS 结构中提取标题、作者、摘要、正文 section、figure/table caption、表格、MathML display formula、data/code availability、supplementary link 和 references，不能只把 XML 当纯文本拼接。
- 空 `xref[ref-type=bibr]` 按 `rid` 指向的真实书目 label 恢复可读引文；Copernicus natbib 标签仅取已有作者年份短标签，多目标保持源顺序。已有显示文字不改写，未知目标明确报告，链接指向同篇官方 XML 对象，不能依赖可能被过滤的本地 References。
- 代表性 HTML / XML：
  - [`../tests/fixtures/golden_criteria/10.5194_acp-24-1-2024/original.xml`](../tests/fixtures/golden_criteria/10.5194_acp-24-1-2024/original.xml)
- 边界说明：
  - 单测试规则：当前 owner 测试使用最小 JATS fixture 锁住结构渲染 contract，并用合法但正文为空、无正文段落或正文过短的 JATS fixture 锁住 XML route 必须降级到 PDF；8 篇真实 Copernicus XML golden fixture 锁住 XML 主路径 corpus 级别回归；4 篇早期 abstract-only XML + PDF fixture 锁住 route fallback，不扩大本 XML 结构规则的适用范围。后续新增 JATS 变体时应扩充该单测或新增 provider-specific 规则。
  - 这条规则不承诺所有复杂表格布局都能零损失复原；复杂表格降级语义仍归 [表格能展平就转 Markdown 表，展不平就退成可读列表](#rule-table-flatten-or-list)。
  - PDF fallback 的正文 Markdown 走共享 PDF 转换，不适用本 XML 结构规则；PDF 图片只作为导出正文 asset 记录。

### Oxford Academic 层级、引用身份与后置内容

- Silverchair 原文的同级 DOM `h2` / `h3` / `h4` 必须按各自层级渲染，防止组装时丢弃没有直属段落的父章节；同名标题按原文出现顺序处理。
- 引用 Crossref 控件中的期刊 `(ISSN)` DOI 不能作为被引论文 DOI；保留原文可见作者、题名和出版信息。
- Oxford Academic 的 Acknowledgements / Funding，以及 Frontiers XML 的 Author contributions / Acknowledgments 必须保留在 References 前。沿用现有 provider 的 `body` hint 作为保留渲染类别，不表示这些后置内容是科学正文；它们不得混入参考文献列表。
- 对应阶段：`provider-html-or-xml-extraction`、`section-classification`、`article-assembly`、`references-rendering`。Owner：`_oxfordacademic_html` 与 `frontiers`。原文证据为 `10.1093/bioinformatics/btaa161` 和 `10.3389/fmars.2023.1101972`；回归见 [`test_reviewed_publisher_content.py`](../tests/golden/test_reviewed_publisher_content.py)，逐项比较原文标题、正文文本片段和全部可见引用，不读取历史 Markdown。

### AIP PDF 上标引用编号

此旧规则已撤销。AIP 与其他 provider 一样遵守 [PDF 转换边界](#rule-pdf-conversion-boundary)，禁止对 PDF 输出做上标编号归一化、断行合并或引用分条；已有实现与 31 条引用的历史断言不构成例外。

## 使用建议

- 新增回归测试时，优先把规则写成行为约束，再用 DOI 级样本去证明它。
- 做 root-cause 排障时，先判断问题是在 HTML 提取、文章组装、资产清洗，还是最终渲染阶段，再决定该把证据补到哪条规则下。
- 共享 heading、inline whitespace、citation sentinel、DOI 与 formula 识别常量应复用代码中的单一来源；provider 只保留真正改变语义的覆盖规则，避免测试路径和运行时 drift。
- 后续如果要补“既有规则”，继续沿用同一模板，不要把 incident 记录直接搬进这里。

Springer Classic 的非编号 author–year 文献列表按原顺序保留，不添加正文并不存在的编号；Springer 参考文献链接中的 `%2F` 在该 provider 内解码后识别 DOI。AMS 优先从可见 author–year 条目及其 DOI 链接提取引用，保留旧式含角括号的 DOI。图片形式的 Wiley 公式和 AMS 表格只保留资产身份，不声称 OCR 或结构化单元格还原。 Wiley 公式的 `/cms/asset/` 与 AMS 表格的 `/view/` 图片地址在 provider DOM 阶段按同篇 `source_url` 解析，再形成 Markdown fallback；preview/full 候选分别保留，远程 URL 不代表已下载，本地资产路径不参与解析。

Springer、Wiley 及共享浏览器 PDF 回退在 HTML/PDF 双失败时保留底层 PDF 失败的精确原因 trace；最终内容分类与既有降级规则一致。

JATS 已知公式容器内的 `inline-graphic` 与 `graphic` 均可作为图片回退，保留 MathML／TeX 优先级；容器外普通行内图片不因此升级为公式。PLOS XML 入口复用既有 DOI 图片路由，将同篇 inline-graphic 的 `info:doi` 身份解析为官方地址并进入原有资产链路；无有效图片仍报告缺失，不将图片地址保留称作 TeX 恢复或像素已下载。 PLOS 组装按同篇 info:doi 对象身份精确匹配资产，不能因官方 `/article/file` 端点相同而合并不同 query 的图片。已下载对象原位使用各自本地文件，未下载对象保留各自官方 HTTP 地址及来源并进入完整资产分母；规范源身份可保留在 Article 资产来源字段，临时组装表示不得泄漏到正文，重复渲染应稳定。

Taylor & Francis 的引用链接同时可能含当前页面 `doi` 与被引条目的 `refDoi` / `doiOfLink`；引用 DOI 仅从后两者或该条目的 getFTR `data-target` 补齐，不误用页面身份。复用共享编号引用文本抽取；真实 LST 样本的全部可见引用和首中尾 DOI 由 `test_reviewed_remaining_provider_content.py` 核对。

Taylor & Francis 的相邻 `.NLM_disp-formula-image`／`.NLM_disp-formula` 属于同一公式，只保留一个表示：优先真实 MathML／TeX；只有 MathJax CHTML 展示树时，不把字形顺序当作源公式，改用该对 `data-formula-source` 的官方图片地址。地址按同篇 `source_url` 解析，并进入既有 formula 资产链路；配对不跨正文，同一 URL 在不同公式的合法复用不去重。`//:0` 不是可用图片，无可用内容时保留缺失提示和 missing 计数。官方地址可输出不等于图片已下载或像素可读。

### 局部内容验收

- PDF 请求带有目标身份且身份结果为 `insufficient` 时，必须通过既有标题匹配才能接受；缺少、空白或不匹配的标题均返回 `pdf_identity_unverified`，清理临时文件并继续既有回退。独立 DOI 成功不要求标题；底层无目标身份调用契约保持。`allow_pdf_only` 不绕过身份验收，也不改写转换器输出。
- Oxford Academic `.table-wrap-foot` 按 DOM 顺序紧跟对应表格，位于下一正文块之前；保留标记、强调、公式和链接，移除下载控件。
- Science 仅提升致谢区中以明确数据／代码可用性粗体标签开头的可见独立段落。保留原文标题、正文和链接；混合数据／代码声明归 `data_availability`，纯代码归 `code_availability`。该节不增加正文充分性，普通致谢、资助及段落中途标签仍按原规则处理。
- Science 保留声明中的书目 fragment 仅按原 DOM `.citations[id]` 核验后转换为同篇来源页对象地址，无有效 HTTP(S) 来源基址时保留无跳转文字；不依赖最终 `include_refs` 筛选，也不把普通同名 ID 当成书目。真实 `science.abp8622` R43 与 `science.adp0212` R49 见 `tests/golden/test_retained_object_links.py`。
- AIP HTML 的 `.fig-modal` 是正文图的弹窗副本，在该 provider 的 DOM 清理阶段移除；保留 `.fig-section` 中完整图注和正文讨论。原文 `10.1063/5.0188905` 的图一、图五在最终文章中只出现一份图注，不扩大为全局相似段落去重。
- arXiv 源码图发现支持 `figure` / `figure*` 与已由原始 TeX 验证的 `extdatafigure` 环境，后者使用 `extdatacaption`；保留原始图路径、caption 和 label。`2606.00587v2` 的五张普通图与两张扩展数据图以已有源码成员和真实 PNG 回归；不声称通用自定义 LaTeX 环境展开或新的源码下载链已经验收。

- Springer/Nature 的 `.c-article-section__figure-description` 若含公式图片，在 provider DOM 阶段将该下方图注放到对应 figure 紧后，保留正文顺序并剔除原有下载控件，避免通用 figure 渲染把公式重复提取成下一张正文图。Springer 的未知、未编号图片不得按出现次序配给下一张编号图；其他 provider 的既有策略不变。`nature13376` 的四张原图及四张 extended-data table 图片由同篇真实响应回归，表格图片不作 OCR 或单元格恢复。
- Nature 的 expandable box 保留可展开内容；仅含图片的 `.c-article-box__content` 将原始标题作为该图片的粗体说明保留在原位置，避免生成仅有图片而被省略的正文节。真实 `s41467-022-32108-3` 验证两段 Box 原文，`s42003-021-02908-2` 验证图片型 Box 的标题与同篇 PNG。隐藏界面文字的过滤不变。

### 按证据保留出版社图片候选与 arXiv 结构

- ACS／Royal 的原始文章可能只有缩略图、查看器和 `DownloadImage.aspx` 包装；独立查看器中存在直链不能证明文章也有普通直链。保留同图、同 CDN 的解包装检查；ACS 删除缺少原图时另访问查看器的回退，Royal 因真实分组 figure 反例保留该路径。原文回归见 `tests/golden/test_requested_template_evidence.py`。
- PNAS 删除原图失败后的 preview 下载，以及没有原图时的 preview 下载；仍可从已有 figure-page 入口识别原图，并保留原图的浏览器恢复；浏览器 canvas/已加载图片须精确匹配目标 URL，不能以页面上的 preview 替代原图。原图失败按现有失败／远程资产验收报告，不以缩略图冲销。`tests/unit/test_provider_asset_candidate_boundaries.py` 覆盖串行浏览器和普通执行路径。其它 provider 的 preview 契约不变。
- arXiv HTML frontmatter 和 bibliography 只使用已验证的 LaTeXML 选择器；删除无 ltx 标记时猜测通用 h1、Abstract/References 容器和任意列表项的分支。官方 ID/API metadata 与已有 HTML/PDF 路线不变。
- Science 原生 canvas 导出字节单独记录 `capture_kind=browser_canvas_export`，HTTP 状态为未知。导出 helper 自带的 status 不能当成真实 HTTP 状态；文章导航 challenge 也不能替代图片请求 challenge。

### Elsevier 主文表格的文字回退必须区分附录引用

- `Table 1 of Appendix C`、`Supplementary Table 1` 不能触发主文 Table 1 的插入；Table 1 也不能匹配 Table 10。原有显式 XML 引用和附录归属继续优先。
- 真实回归：`10.1016/j.envres.2018.12.059` 的附录引用先于主文 Table 1 调用点；canonical 表格位置检查以正文调用段和相邻段落为依据，不以 XML 集中存放的 `floats` 顺序推断正文位置。

<a id="rule-arxiv-object-and-inline-svg"></a>
### arXiv LaTeXML 图形表示与合法重复位置

- arXiv HTML 的正文 `object[data]` SVG 和 figure 内 `svg.ltx_picture` 是图形内容，须接入现有图片/资产管线，保留 DOM/子图身份、源顺序与图注；不把 frontmatter 图标和普通行内数学 glyph 作为正文图。
- `object` URL 和普通图片相对 URL 先按原响应来源解析，再提取语义表格；表格 cell 中图片仍须输出。内联 SVG 保留原路径、文本与命名空间，可由已有 ArtifactStore/AssetBudget 落盘；远程链接不能当成本地下载证据。
- 相同 URL 在不同原文 figure 中可合法重复。DDPM 原文 `A4.F13/A4.F14` 及正文引用均存在，Figure 1/6/13/14 各原位保留一次；禁止因共享 URL 删除独立源对象。
- 标题提取排除 `h1.ltx_title_document .ltx_pubnotes`，metadata、YAML 与 H1 一致；仅删除无内容、无图形且不在正文 section/figure 内的 frontmatter 排版表，保留有效内容表。

### 来源对象与访问边界回归约束

- HTML 表格中的相同值仍属于各自单元格，不能按文本去重或移到首列；表格内图片不拆为独立 Markdown 段落。
- Springer 的 Reporting summary 保留在正文原位置，不作为摘要前置；只有官方入口的 Extended Data Table 保留题注和表页链接，不据此声称取得表格内容。`body/none` 跳过附表下载时，准备 HTML 到最终 Markdown 的整条路径仍保留说明与入口，包括主文容器外的节点。
- Wiley 参考文献的显示编号不进入引用正文；Royal Society 优先使用 HTML 完整书目；PLOS XML 作者姓名与相邻作者之间保留边界。
- Copernicus 的空图表 xref 按明确 rid 对应的 label 恢复文字，保留已有文字；章节标题经现有公式渲染器保留 MathML。PDF 身份比较仅去除该 provider 元数据题名中的 HTML 标记，不改变 PDF 转换结果或降低身份阈值。
- Oxford Academic 的 Abstract 标题和下载幻灯片控件不构成摘要内容；ACS 图像式表格计入正文资产发现和严格本地验收。ACS 表图使用所属表格标签区分身份；同为通用 `Graphic` alt 的不同表图不能在下载结果合并时互相覆盖。
- Science 在浏览器中展开可见参考文献控件；仍缺正文引用目标时输出 `reference_targets_missing` 及缺失列表，统一验收降级。
- IEEE 直接 stamp 路线未取得 PDF 时，可从同篇官方文章页点击可见 PDF 链接，捕获同篇 stamp/getPDF 的文档或下载响应（含 popup）；direct PDF 的 HTTP 502 允许进入该恢复路径。继续执行既有大小、身份和权限验收，保留 HTML 失败及 PDF 降级来源。
- arXiv HTML 作者列表短于官方 Atom 列表时保留 Atom 的完整有序列表；长度相同仍优先 HTML，不拼接不同拼写以免重复作者。
- Royal Society、T&F、ACS 等 browser-workflow HTML 题名的源换行作为空白归一为单行 H1；ACS HTML 小节标题同样不因源换行拆成普通段落。此行为只作用于 HTML 路线，不改写 PDF 转换器输出。
