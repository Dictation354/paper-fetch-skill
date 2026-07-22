# 新增 Provider 开发标准

> Human reference only. AI/coordinator provider onboarding must use [`onboarding/coordinator-spec.md`](../onboarding/coordinator-spec.md) and related authority docs.

这份文档是后续接入新出版社 provider 的人工教程和解释性参考。目标是让人类维护者理解当前架构边界，减少后续因为路由、typed payload、资产语义、测试夹具或文档事实来源不一致造成的返工。

本文不作为 AI/coordinator worker 的行为输入，也不定义机器编排事实源。AI/coordinator onboarding 的入口索引是 [`onboarding/README.md`](../onboarding/README.md)；行为事实源分别见 [`coordinator-spec.md`](../onboarding/coordinator-spec.md)、[`provider-manifest.md`](../onboarding/provider-manifest.md)、[`provider-manifest.schema.json`](../onboarding/provider-manifest.schema.json)、[`agent-task-brief.md`](../onboarding/agent-task-brief.md)、[`hard-constraints.md`](../onboarding/hard-constraints.md) 和 [`acceptance.md`](../onboarding/acceptance.md)。

当前已支持 provider 的能力矩阵、运行时行为和环境变量仍以 [`providers.md`](providers.md) 为准；系统分层、typed contract 和 owner 边界仍以 [`architecture/overview.md`](architecture/overview.md) 为准；用户可见提取 / 渲染规则仍以 [`extraction-rules.md`](extraction-rules.md) 为准。

## 端到端流程速览

新增 provider 的人工开发流程通常是 **Step 0 → Step 6**。AI/coordinator 的固定 task DAG 不以本节为准，必须使用 [`onboarding/coordinator-spec.md`](../onboarding/coordinator-spec.md)。

| Step | 任务 | 详细规约 | 预估 |
|---|---|---|---|
| 0 | 写设计：routing 信号、主路径顺序、asset_profile 语义、probe 边界、abstract-only 策略 | §1 | 30 min |
| 1 | 按正交能力清单收 fixtures：≥9 篇 HTML/XML + 1-2 篇 PDF fallback + 1-2 篇 block | §8 + 附录 A | 1-3 天 |
| 2 | Scaffold 起步：跑生成脚本生成 provider bundle / fixture / manifest / starter test 骨架 | §1.5 | 10 min |
| 3 | 实现 extraction 与客户端，并执行 Markdown Review Loop：baseline Markdown → 阅读审查 → correction 写断言 → 修 provider | §2–§8 | 2-5 天 |
| 4 | Prototype 通过（Commit A）：所有 non-null fixture purpose 的 Markdown 干净、provider-local 断言覆盖、第一次写 snapshot 三产物 | §8 | 1 天 |
| 5 | 重构对齐 canonical owner（Commit B）：grep 自己代码删 local helper | §5 + 附录 B | 半天 |
| 6 | 端到端收尾：实现 `probe_status()` + 同步 `docs/providers.md` / `extraction-rules.md` / `CHANGELOG.md` | §9 | 半天 |

最终验收以 §10「完成定义」+ §10.5「PR Checklist」 为准。

### 几条贯穿全流程的硬约束

- **先设计后写代码**（Step 0 不可省）：决定 fixture 选择策略与主链顺序，跳过会导致 Step 1 收偏「快乐路径」、Step 3 重写客户端。
- **fixtures 用真实 DOI 文献，不接受脑补 DOM**（Step 1）：项目把真实文献 replay 当作行为契约的"源"，不是「跑通了再说」的辅助。
- **Markdown Review Loop 强制执行**（Step 3/4）：每篇 non-null fixture 先生成 baseline Markdown，人工阅读 `extracted.md` 审查，把每个 correction 写成 provider-local 断言，再修 provider 清洗 / 转换并重复到全部 fixture 干净；之后才写 snapshot 三产物。
- **Prototype 和重构分两次 commit**（Step 4 / Step 5）：先固化「跑通」状态，再做 canonical owner 对齐，避免重构发现要回退 fixtures 时连带丢失 prototype 进度。
- **中心模块零编辑**（S1-S6 落地后）：新 provider PR 不应触动 `provider_catalog.py` / `provider_rules.py` / `quality/html_signals.py` / `quality/html_availability.py`——全部走 `ProviderBundle` 自注册。详见附录 D。

## 核心原则

新增 provider 不是新增一段独立抓取脚本，而是接入已有的 provider-owned waterfall：

```text
resolve
-> metadata / routing
-> provider-owned fulltext waterfall
-> provider-managed abstract-only or metadata-only fallback
-> typed ArticleModel / FetchEnvelope rendering
```

必须遵守这些原则：

- Provider 身份、路由信号、默认资产策略、status 顺序和 registry factory 统一来自 provider entry module 顶部注册的 `ProviderBundle`；`PROVIDER_CATALOG` 和 source map 由 bundle discovery 懒加载派生。内置 entry module 由显式清单管理；新增动态 entry 必须包含真实 `register_provider_bundle(...)` 调用，注释、docstring 或普通字符串不会触发 discovery。
- Provider 主链必须返回 typed payload：`ProviderContent`、`ProviderFetchResult`、`ProviderArtifacts`、`warnings`、`trace` 和 `merged_metadata`。
- 不允许通过 `raw_payload.metadata[...]` 读写结构化状态；它只是 read-only compatibility view。
- Provider 层只做 publisher adapter；通用 HTML、表格、公式、引用、资产验证、availability 判定优先挂到已有 canonical owner。
- HTML / XML / PDF / browser fallback 的顺序由 provider 自己明确声明，并用 `source_trail` 和 warnings 暴露可观测行为。
- 资产失败不能覆盖已成功的正文 Markdown；资产问题应进入 warnings、`article.quality.asset_failures` 和 download trace。
- 新增用户可见提取 / 渲染行为时，必须同步规则文档、fixtures 和测试。
- 新增 provider 的规则和核心测试默认必须基于真实 DOI 文献的 HTML / XML replay；这些文献样本统一放入 `tests/fixtures/golden_criteria/` 并登记 manifest。

## 1. 先写设计，再写 client

开发前先在 issue、TODO 或设计段落中写清楚：

- Provider 名称、公开 `source` 名称和是否 official。
- 路由信号：domain、Crossref publisher alias、DOI prefix，按 `domain > publisher > DOI fallback` 理解优先级。
- 主路径顺序：例如 `landing HTML -> XML -> cleaned HTML -> PDF fallback -> abstract-only`。
- 每一步成功和失败的判定条件，尤其是 access gate、abstract-only、空壳 HTML、非 PDF wrapper 和正文不足。
- 权限边界：是否需要 API key、机构授权或 CDP 浏览器上下文；不自动登录、不处理 CAPTCHA、不伪造授权。
- `asset_profile` 语义：`none` / `body` / `all` 下分别下载什么，PDF fallback 是否应保存 `pymupdf4llm` 导出的 PDF 图片。
- `probe_status()` 的本地检查边界见 [`providers.md`](providers.md#provider-status-local-boundary)。

如果 provider 是开放获取出版社，默认优先 direct HTTP / XML / HTML；不要为了“更稳”直接引入 browser runtime。只有明确存在动态渲染、CDN 对普通 HTTP 拦截或 challenge runtime 需求时，才考虑接入 selected-browser runtime。

## 1.5 用 scaffold 起步

设计和首批 DOI 确认后，先用 scaffold 生成 provider-owned 骨架：

```bash
python3 scripts/scaffold_provider.py --name newpub --doi 10.1234/sample [--fulltext-client]
```

脚本会生成 provider entry module、fixture 占位、manifest pending 条目和 starter test。随后必须在生成文件中补齐：

- `ProviderSpec`：provider 名称、公开 source、routing 信号、URL 模板、默认资产策略、status 顺序和 client factory。
- `ProviderHtmlRules` facet：cleanup、heading、formula、asset、availability 等 provider-owned HTML 规则；没有 availability 信号时显式 `no_signals=True`。
- hook 函数体：只保留 publisher adapter 逻辑，通用解析、availability、asset、table、formula、citation 逻辑复用 canonical owner。
- fixture：把真实 DOI replay 放入 `tests/fixtures/golden_criteria/<doi_slug>/`，完成后把 manifest 的 `expected_outcome` 从 `pending` 改为稳定结果。

<a id="provider-bundle"></a>
## 2. 填完整 ProviderBundle

新增 provider 的第一批代码改动应该集中在 provider entry module，例如 `src/paper_fetch/providers/newpub.py` 顶部；scaffold 初期的 `_newpub_html.py` 只作为 provider-owned helper / compatibility facade：

- 调用 `register_provider_bundle(ProviderBundle(...))`，一次性声明 `catalog=ProviderSpec(...)`、`html_rules=ProviderHtmlRules(...)`、`sources=(...)`，以及需要的 asset retry / metadata merge 配置。
- `sources` 只登记实际写入 `ArticleModel.source` / envelope `source` 的公开来源；provider 内部 route marker 不单独登记。例如 Springer HTML / PDF fallback 分别公开 `springer_html` / `springer_pdf`，二者都映射到 `springer` provider。
- `domains` 只登记明确 host；需要覆盖同一注册域下持续新增子域时，用 `domain_suffixes`，例如 Copernicus 使用 `("copernicus.org",)` 而不是穷举 journal 子域。
- `probe_capability` 必须描述 routing 能力：有可提前调用的官方 metadata API 时设为 `metadata_api`；只可作为 DOI/domain/publisher 路由信号时设为 `routing_signal`。通用 routing 会按该字段决定是否发起早期 metadata probe。
- 选择默认 `asset_default`：公开 HTML/XML 路线通常是 `body`；metadata-only 或没有资产能力的是 `none`。
- 选择 `provider_managed_abstract_only`：provider 能可靠返回自己的摘要页时设为 `True`；否则保持 `False` 并走通用 metadata-only fallback。
- Atypon/browser-workflow、Springer Link 以及 Copernicus DOI-derived route 这类固定候选 URL 模板必须放在 `html_path_templates` / `xml_path_templates` / `landing_path_templates` / `pdf_path_templates` / `crossref_pdf_position` / `base_domains`。需要从 landing/source URL 派生 PDF 的路径转换放在 `pdf_source_path_templates`。provider-owned HTML/XML 模块可以读取这些字段，但不能再维护第二份路径模板常量。
- 需要 API endpoint 或 API-like landing 过滤时，在 `api_hosts` / `api_url_templates` 声明；不要在 provider 或通用 `utils` 里散落 host 与 URL 模板常量。
- 需要 metadata probe 早出口时，在 `metadata_probe_short_circuit` 声明延迟回调路径或 callable，并在 provider 模块内注册回调；workflow 不按 provider 名称分支。
- 需要保留 provider 原始 HTML artifact 时，用 `persist_provider_html=True` 声明；`ArtifactStore` 只读取 catalog 字段。
- 需要从 XML 文件推断 provider 时，用 `xml_root_tags` / `xml_file_tokens` 声明；公式采样不会在 `formula/convert.py` 里维护 provider 名白名单。
- 需要跳过通用 HTML managed fallback marker 时，用 `emits_html_managed_marker=False` 表达；不要在 workflow 中按 provider 名字分支。
- 正文长度阈值统一走 `body_text_thresholds`。通用 HTML 使用默认阈值；确有差异的 provider 只覆盖差异字段。
- `client_factory_path` 指向最终 client，例如 `paper_fetch.providers.mdpi:MdpiClient`。
- `status_order` 插入稳定顺序，避免 UI / MCP status 抖动。

```python
register_provider_bundle(
    ProviderBundle(
        catalog=ProviderSpec(
            name="newpub",
            display_name="New Publisher",
            official=True,
            domains=("example.org",),
            doi_prefixes=("10.1234",),
            publisher_aliases=("New Publisher",),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            client_factory_path="paper_fetch.providers.newpub:NewpubClient",
            status_order=90,
        ),
        sources=("newpub",),
    )
)
```

不要手写新的 provider 常量列表，也不要修改中心模块的 provider 字典或规则表。`preferred_providers`、MCP provider status、registry clients、默认 asset profile 和 provider identity 都应该继续从 bundle discovery 派生。新增后至少补 provider 相关 unit test 的 DOI、domain、publisher 推断样例，并让 `tests/unit/test_provider_bundle_completeness.py` 通过。

<a id="client-contract"></a>
## 3. Client Contract + Markdown Review Loop

优先继承 `paper_fetch.providers.base.ProviderClient`。新 provider 的全文主链默认声明为 class-level `waterfall_steps`，元素必须是 `WaterfallStep`；只有像 `BrowserWorkflowClient` 这样已经覆盖 `fetch_raw_fulltext()` 的模板实现，才可以用 `route_order` 保存字符串路线标签。只在确有特殊模板流程时覆盖必要 hook：

- `to_article_model(metadata, raw_payload, *, downloaded_assets=None, asset_failures=None, context=None)`
- `html_to_markdown(html_text, source_url, *, metadata, context)`，仅 HTML 路线需要
- `download_related_assets(...)`，仅有资产能力时实现
- `probe_status()`
- `describe_artifacts()`，仅 PDF fallback 或特殊 artifact 策略需要覆盖
- `maybe_recover_fetch_result_payload()`，仅 HTML 抽取后发现 abstract-only 还需要继续 PDF fallback 时覆盖

推荐 client 模板：

```python
from . import _newpub_html as _provider_rules
from ._waterfall import DEFAULT_WATERFALL_CONTINUE_CODES, WaterfallStep
from .base import ProviderClient


class NewpubClient(ProviderClient):
    name = "newpub"
    waterfall_steps = (
        WaterfallStep(
            label="html",
            run=_provider_rules.newpub_fetch_html_step,
            failure_marker="fulltext:newpub_html_failed",
            success_markers=("fulltext:newpub_html_ok",),
            continue_codes=DEFAULT_WATERFALL_CONTINUE_CODES,
        ),
        WaterfallStep(
            label="xml",
            run=_provider_rules.newpub_fetch_xml_step,
            failure_marker="fulltext:newpub_xml_failed",
            success_markers=("fulltext:newpub_xml_ok",),
            continue_codes=DEFAULT_WATERFALL_CONTINUE_CODES,
        ),
        WaterfallStep(
            label="pdf",
            run=_provider_rules.newpub_fetch_pdf_step,
            failure_marker="fulltext:newpub_pdf_failed",
            success_markers=("fulltext:newpub_pdf_ok",),
            continue_codes=DEFAULT_WATERFALL_CONTINUE_CODES,
        ),
    )
```

step 函数放在 provider-owned 模块中，签名使用 `def newpub_fetch_html_step(client, doi, metadata, *, context)`，成功时返回 `RawFulltextPayload`，失败时抛 `ProviderFailure`。如果 `waterfall_steps` 为空，`ProviderClient.fetch_raw_fulltext()` 会抛 `NotImplementedError`，提示子类声明 steps 或覆盖方法。

`ProviderClient.fetch_result()` 已经负责：

- 创建 / 复用 `RuntimeContext`
- 调用 raw payload、abstract-only recovery、HTML 自动 Markdown fallback
- 控制资产下载时机
- 调用 `to_article_model`
- 组装 `ProviderFetchResult`
- 合并 warnings、trace 和 artifacts

新 provider 不应绕开这条 template method 自己拼最终结果。已有 provider 的复杂 `fetch_raw_fulltext()` 覆盖实现可以保留；新增 scaffold 默认使用 `waterfall_steps`。

### Provider mypy 分批纳入

当前 mypy 覆盖面包含核心模型、workflow、MCP、HTTP/metadata/markdown、runtime/config/quality、provider base/protocols、provider catalog、PDF fallback shared helpers、HTML extraction、browser runtime、browser workflow、Atypon browser workflow、formula core、shared JATS/common Markdown helpers、CloakBrowser helper，以及第一批真实 provider：`src/paper_fetch/providers/copernicus.py` 和 `src/paper_fetch/providers/_article_markdown_copernicus.py`。后续新增 provider typing 批次必须先跑 targeted mypy 清零，再把文件加入 `pyproject.toml` 的 `[tool.mypy].files`；本地 preflight 与 CI 都通过 `pyproject.toml` 的 `no_site_packages = true` 避免开发机第三方 stub 与 CI Python 版本不一致时阻断项目文件检查。

下一批 backlog 是 arXiv，不应混入 Copernicus 或其它 provider 批次。开始前先运行：

```bash
PYTHONPATH=src python3 -m mypy src/paper_fetch/providers/arxiv.py src/paper_fetch/providers/_arxiv_*.py --show-error-codes
```

已知待处理类型边界主要集中在尚未纳入的 provider 批次，例如 arXiv 相关 helper 的 `ProviderMetadata` / `dict[str, Any]` 协议收敛、SourceKind 显式标注、只读列表参数改用 `Sequence[...]`，以及 `_arxiv_assets.py` 内的局部变量重定义和可空赋值问题。修复时不得通过文件级 `type: ignore`、扩大 `ignore_missing_imports` 或 `ignore_errors` 掩盖错误。

实现过程中必须把 Markdown Review Loop 当作主循环：

1. 对 manifest 中每个 non-null `fixtures.doi_samples.<purpose>` 生成 baseline Markdown；AI/coordinator manifest 字段定义以 [`onboarding/provider-manifest.md`](../onboarding/provider-manifest.md) 和 [`provider-manifest.schema.json`](../onboarding/provider-manifest.schema.json) 为准。
2. 逐篇阅读 Markdown，记录 `fixture/purpose -> issue -> assertion -> fix`。
3. 每个 issue 先落到 `tests/unit/test_<provider>_provider.py` 的 provider-local 断言，再修改 provider-owned 清洗 / 转换代码。
4. 主成功路径至少保留一个正向 Markdown 内容断言和一个负向站点 chrome / access noise / boilerplate 断言。
5. 禁止保留 scaffold skipped placeholder 或 review-loop placeholder；所有 non-null purpose 都必须在 provider test 中点名覆盖。

## 4. Fulltext Waterfall

provider 内部多步骤 fallback 应声明 `paper_fetch.providers._waterfall.WaterfallStep` 序列，并由 `ProviderClient.fetch_raw_fulltext()` 默认调用 `run_provider_waterfall()`，而不是散落嵌套 `try/except`。已有 provider 如已覆盖 `fetch_raw_fulltext()`，可在覆盖方法内部继续局部调用 `run_provider_waterfall()`。

每个 step 要定义：

- `label`
- `run`
- `failure_marker`
- `success_markers`
- `continue_codes`
- `failure_warning`
- `success_warning`

错误类别使用稳定的 `ProviderFailure.code`：

- `no_result`：该路线没有可用全文，可继续 fallback。
- `no_access`：权限或 access gate 不满足，通常继续 provider-managed 降级。
- `rate_limited`：远端限流，保留 `retry_after_seconds`。
- `not_configured`：本地缺环境变量、API key、runtime。
- `not_supported`：该 provider 不支持该输入或能力。
- `error`：其它不可归类错误。

成功判定不能只看 HTTP `200`。必须校验 payload 形态和正文充分性，例如：

- XML 有正文 section，而不是只有 metadata。
- HTML 有 provider article container、章节或足够正文段落。
- PDF fallback 返回真实 PDF payload，而不是 HTML access page、JS wrapper 或错误页。
- Markdown 通过 `quality.html_availability` 或结构化 availability 判定，不把 abstract-only 当 fulltext。

<a id="extraction-owner-reuse"></a>
## 5. Extraction Owner 复用规则

新增 provider 时优先复用这些 owner，不新增平行 helper：

- Landing HTML：`paper_fetch.extraction.html.landing.fetch_landing_html`
- Metadata parsing：`paper_fetch.extraction.html._metadata`
- HTML-to-Markdown 编排：`paper_fetch.extraction.html.renderer`
- HTML DOM parsing：`beautifulsoup4` 是主依赖，provider / extraction 代码直接 `from bs4 import ...`；不要新增 `BeautifulSoup is None` / `Tag is None` 运行时 fallback。
- Fulltext / abstract-only 判定：`paper_fetch.quality.html_availability`
- Section hints：`paper_fetch.extraction.section_hints`、`paper_fetch.extraction.html.semantics`
- Access-gate 文案与匹配顺序：`paper_fetch.extraction.html.signals.ACCESS_GATE_LABELS` / `ACCESS_GATE_PATTERNS`
- 通用 figure/table label core 与 Extended Data prefix 判断：`paper_fetch.common_patterns`
- Reference anchor 判定：`paper_fetch.extraction.html.semantics` 中的 `looks_like_reference_anchor()` / `has_explicit_reference_marker()` 以及底层 `paper_fetch.extraction.citation_anchors.looks_like_reference_href()`；不要在 provider 或 runtime 中复制 `data-test`、`role`、`class`、`href` fragment 规则。
- HTML table：`paper_fetch.extraction.html.tables`
- Markdown block rendering：`paper_fetch.extraction.markdown_render`，统一 table / figure / formula / caption / list 的 IR 和最终行渲染；provider 只保留 HTML/XML/DOM -> IR 或 compatibility entry 的转换层。
- Citation cleanup：`paper_fetch.markdown.citations`，只负责 numeric payload / Markdown cleanup；reference href 判定委托 `citation_anchors`
- Markdown image alt / image line rendering：`paper_fetch.markdown.images`，统一生成 `Figure N` / `Table N` / `Listing N` / `Formula` / `Image` 短 alt，caption 不进入 `![alt]`
- Formula rules：`paper_fetch.extraction.html.formula_rules`、`paper_fetch.providers._article_markdown_math`
- Image MIME / dimensions：`paper_fetch.extraction.image_payloads`
- Asset discovery / download：`paper_fetch.extraction.html.assets`
- HTTP header lookup：`paper_fetch.http.headers.header_value`，provider / asset / PDF fallback 统一使用这个大小写不敏感 header helper。
- Final rendering：`paper_fetch.models`

Provider-specific 代码只负责：

- 找到 publisher 的 article container 或 XML root。
- 把 publisher DOM/XML 映射成已有中间结构。
- 在自己的 provider entry module 顶部 `register_provider_bundle(ProviderBundle(...))` 声明 `ProviderSpec`、`ProviderHtmlRules` 和 availability data。bundle 内的 HTML rules 持有 publisher cleanup profile、Markdown promo tokens、availability site rule、access-block tokens、availability policy、公式 container/selector、supplementary 文本扩展和必要 alias；运行时通过 bundle discovery 合成 DOM / Markdown 清洗规则。不要在 `_runtime.py`、`formula_rules.py`、`assets/supplementary.py`、`quality/issues.py`、`quality/html_signals.py` 或 `quality/html_availability.py` 直接追加 publisher 私有 token。
- Provider-specific figure/table caption regex 可以保留行首锚定、caption remainder、Extended Data 变体或 ar5iv 兼容分支，但应复用 `common_patterns` 的 label core / prefix helper 或在旁边说明差异。
- Provider HTML availability signal 也通过 bundle 内 `ProviderHtmlRules.availability` 声明；必须提供 `signal_set` 或显式 `no_signals=True`。
- 新 access-gate 文案先登记到共享 `ACCESS_GATE_LABELS` 或 `ACCESS_GATE_PATTERNS`；只有会阻断全文访问的文案进入 `ACCESS_GATE_PATTERNS`，机构访问确认等非阻断提示只保留在 `MARKDOWN_ACCESS_NOISE_LABELS` 等降噪词表中。provider markdown/postprocess break tokens 只放非访问门的站点 chrome。
- 定义 asset scope 和 fallback 候选。
- 把提取结果写入 `ProviderContent.diagnostics`，而不是塞进 raw metadata compatibility view。

如果确实需要新增共享能力，应优先放到 canonical owner 模块，并同步 `docs/architecture/overview.md` 的阶段映射和 `docs/extraction-rules.md` 的规则说明。

## 6. 资产下载标准

`asset_profile` 的语义必须稳定：

- `none`：不下载本地资产；Markdown 必须保留正文已有或 provider 可解析出的远程图片链接，只有无法解析远程图片时才退回 caption / captions-only。
- `body`：只下载 provider-cleaned 正文 scope 中的 figure、正文表格原图和可识别公式图片 fallback。
- `all`：在 `body` 基础上额外下载明确 supplementary / supporting / multimedia scope 中的附件。

Supplementary discovery 必须来自明确附件 scope。不能在整篇正文里凭 `data`、`code`、`.csv`、`.zip`、`.mp4`、`.pdf` 等词面或后缀全局扫描并归为 supplementary。
Publisher 私有的 supplementary 属性或埋点必须由 provider extractor 处理，不能放进通用 `paper_fetch.extraction.html.assets`。例如 Wiley 的 `data-test="supp-info-link"` / `data-track-action="view supplementary info"` 归 Wiley extractor 所有。

资产输出和失败诊断必须保留：

- `kind`
- `section`
- `render_state`
- `download_tier`
- `download_url`
- `original_url`
- `preview_url`
- `full_size_url`
- `content_type`
- `downloaded_bytes`
- `width`
- `height`
- failure 的 `status`、`content_type`、`title_snippet`、`body_snippet`、`reason`

正文已内联消费的图表应设置 `render_state="inline"`，避免最终 Markdown 尾部重复追加 `Figures` / `Tables`。PDF fallback 的图片资产由共享 `pymupdf4llm` 转换导出；provider 不应再用 HTML/XML asset downloader 二次处理 PDF route。

## 7. Runtime 与请求策略

所有 provider 网络请求应走 `RuntimeContext.transport` / `HttpTransport`，不要直接用 `requests`、`urllib` 或临时 session。

建议规则：

- Fulltext 路线使用 `DEFAULT_FULLTEXT_TIMEOUT_SECONDS`。
- 可重试的 publisher GET 使用 `retry_on_transient=True`。
- API 或限流敏感路线根据现有 provider 模式启用 rate-limit retry。
- API / metadata 路线用 `build_user_agent(env)` 构造稳定工具 UA；publisher-facing HTML/PDF 直连用浏览器形态 UA，例如 `build_publisher_user_agent(env)` 或 browser workflow 现有 header helper，避免把 `paper-fetch-skill/...` 发给出版社 CDN。
- 官方 PDF fallback 优先走 `PdfFallbackStrategy`；如果直接调用 `pdf_fetch_result_from_response()` / `pdf_fetch_result_from_bytes()`，应显式允许真实 PDF 的 PDF-only 保留，避免扫描 PDF 无法转 Markdown 时降级成 Crossref metadata-only source。
- `context.parse_cache` 用于同一次 fetch 内复用 XML root、HTML extraction payload、asset extraction payload。
- Browser runtime 只能通过 `RuntimeContext`、browser runtime facade 或现有 browser workflow helper 管理；生产路径统一使用所选后端打开 context/page。只有显式 CloakBrowser 后端可以连接 external CDP。
- Browser workflow 的 browser-backed HTML、PDF fallback 与资产下载必须通过 `RuntimeContext` / `BrowserContextManager` 管理的 keyed browser manager；managed Chrome 生命周期按进程共享，具体 context/page 必须在调用线程通过线程本地 CDP 连接创建。不得把主线程持有的同步 Playwright page/context 交给 worker 线程使用。
- 普通 HTTP 资产下载仍可并发；只有显式 thread-private browser fetcher 才能在 worker 线程创建并关闭自己的 page/context/manager，且必须在同一个 worker 线程内关闭这些 sync browser 对象，否则容易残留浏览器子进程。

不要新增需要全局状态的缓存或隐藏环境变量。新环境变量必须写入 provider docs、status check、部署说明或 `.env.example`，并在 tests 中覆盖缺失和配置成功两种状态。

<a id="testing-standard"></a>
## 8. 测试标准

新增 provider 至少需要这些测试层：

- Bundle / identity：provider unit test 覆盖 domain、publisher alias、DOI prefix、source 映射、默认 asset profile、registry client。
- Request options：覆盖 timeout、headers、retry、API key 或 browser runtime 配置。
- Waterfall：覆盖主路径成功、第一路径失败后 fallback 成功、全部失败后降级、`source_trail` 和 warnings。
- Extraction：用真实 replay 或最小 scenario 覆盖标题、作者、摘要、章节、表格、公式、references、availability 判定。
- Assets：覆盖 `none` / `body` / `all`、正文图、表格图、公式 fallback、supplementary scope、失败诊断和本地链接改写。
- Provider-managed fallback：确认该 provider 失败后不走通用 HTML fallback，而是 provider-managed abstract-only 或 metadata-only。
- Status：覆盖本地 ready、not_configured、partial 或 error。
- CLI / MCP：通常不需要新增专门列表测试，除非 provider 引入新公开参数；provider 名应由 catalog 自动进入 allow-list。

真实文献样本标准：

- 用户可见规则、provider markdown 抽取、availability、references、表格、公式和资产语义的核心测试，默认必须基于真实 DOI 文献的 `original.html` 或 `original.xml`。
- 这些真实文献 replay 必须放在 `tests/fixtures/golden_criteria/<doi_slug>/`，并在 `tests/fixtures/golden_criteria/manifest.json` 中登记 DOI、publisher、source URL、资产路径和用途。
- 文档中引用的代表性文献也必须指向 `tests/fixtures/golden_criteria/` 下的 canonical fixture，不能指向 `live-downloads/`、临时导出目录、开发者本机路径或散落 top-level 文件。
- 一个 provider 首次接入时，至少要有覆盖主成功路径的真实文献 fixture；复杂能力最好拆成多篇真实文献覆盖，例如一篇正文结构、一篇表格、一篇公式、一篇 supplementary / asset scope。
- `_scenarios/` 只用于最小结构 contract、边界条件或真实文献难以稳定复现的细分分支；它不能替代 provider 主路径的真实文献证据。
- `tests/fixtures/block/` 只用于 access gate、paywall、abstract-only、challenge 等负样本页面；负样本同样应尽量保留真实页面状态。
- 如果某条规则暂时只能用最小 scenario 覆盖，必须在 `docs/extraction-rules.md` 的“无稳定 DOI 样本规则汇总表”说明原因、后续补真实文献样本的触发条件和候选 fixture。

Fixtures 规则：

- DOI-backed replay 放在 `tests/fixtures/golden_criteria/<doi_slug>/`。
- 最小结构场景放在 `tests/fixtures/golden_criteria/_scenarios/<scenario_slug>/`。
- access gate、paywall、abstract-only 等负样本放在 `tests/fixtures/block/`。
- 新 fixture 必须同步 `tests/fixtures/golden_criteria/manifest.json` 和 fixture catalog。
- 不从 `live-downloads/`、临时目录或散落 top-level 文件读取测试样本。
- Step 1 录制真实 DOI replay 时优先使用 `python3 scripts/capture_fixture.py --doi <doi> --purpose <purpose>`，脚本会写 canonical fixture 路径并把 manifest 条目置为 `expected_outcome="pending"`；需要先看写入计划时加 `--dry-run`。
- Step 4 第一次固化预期前，必须完成 Markdown Review Loop：所有 non-null fixture purpose 都已有 provider-local 断言，主成功路径同时有 Markdown 正断言和站点 chrome 负断言；随后使用 `python3 scripts/snapshot_expected.py --doi <doi> --review` 审核用户可见摘要、agent review prompt 和 pending quality report，再运行不带 `--review` 的命令写入 `expected.json`（只含 `has` / `counts` / `expected_content_kind` 摘要）、`extracted.md`（唯一人工 golden Markdown baseline）、`markdown-quality-prompt.md` 和 pending `markdown-quality.json`，并同步 manifest outcome/assets。

Golden corpus 规则：

- provider 稳定后，补 representative fixture 和 snapshot 产物。
- `expected.json` 应锁用户可见 summary，不锁无意义格式噪声；Markdown 语义基准只看 `extracted.md`。
- agent 必须按 `markdown-quality-prompt.md` 阅读 `extracted.md` 并写回 `markdown-quality.json`；该报告必须 `review_method: agent_prompt`、`status: pass` 且没有 blocking issue，最终批量人工 review 才能通过 `finalize-review-artifact --confirmed-final-quality` 把 `markdown_semantic_reviewed` 标为 true。
- 如果 agent-authored report 为 fail，可用 `repair-markdown-quality --provider <provider> --doi <doi>` 进入自动修复闭环；该命令仍要求先补/更新 provider-local regression test，再修实现并重新 snapshot/review，不会自动把 `markdown_semantic_reviewed` 改为 true。
- live-only 样本放入 live sample 集合，并受 `PAPER_FETCH_RUN_LIVE=1` 保护。
- 预期 metadata-only 或当前不支持的样本，要在 manifest 标注 expected outcome，避免进入 provider bug 队列。

常规验证命令：

```bash
PYTHONPATH=src python3 -m pytest tests/unit -q
PYTHONPATH=src python3 -m pytest tests/integration -q
```

这两条常规 unit / integration 命令默认复用 `pyproject.toml` 中的 `pytest-xdist` 配置，不要额外加 `-n 0`。完整 golden corpus regression 也按 fixture 参数化运行，默认保持并行：

```bash
PAPER_FETCH_RUN_FULL_GOLDEN=1 PYTHONPATH=src python3 -m pytest tests/integration/test_golden_corpus.py -q
```

如果改了 `docs/extraction-rules.md`，还必须运行：

```bash
python3 scripts/validate_extraction_rules.py
```

只有 live 测试、共享外部状态测试或排查顺序问题时才串行运行，并在结果中说明原因。

<a id="docs-sync-standard"></a>
## 9. 文档同步标准

新增 provider 合并前必须同步：

- `docs/providers.md`
  - 能力矩阵
  - routing 信号
  - fulltext waterfall
  - fallback 语义
  - `asset_profile` 行为
  - 环境变量和 status 说明
- `docs/extraction-rules.md`
  - 任何用户可见提取 / 渲染新规则
  - 新 fixture、Owner、阶段、测试
- `docs/architecture/overview.md`
  - 只有新增 canonical owner、阶段边界或 runtime contract 时才更新
- `docs/deployment.md` / `.env.example`
  - 只有新增用户必须配置的环境变量时更新
- `tests/provider_benchmark_samples.py` 或 live samples
  - 有稳定 live smoke 样本时更新
- golden corpus / integration 同步点
  - 新增 provider 的真实 replay 进入 golden corpus 后，必须注册 `tests.golden_corpus_adapters.GoldenCorpusAdapter`，并确认 MCP provider status、benchmark sample、live review support 均从 `ProviderBundle + manifest` 派生或显式登记。
- `CHANGELOG.md`
  - 对用户可见的新 provider 能力和限制做简短记录

`scripts/scaffold_provider.py` 默认会同步 `docs/providers.md`、`docs/extraction-rules.md` 和 `CHANGELOG.md` 的 scaffold 占位；这些占位由 `<!-- SCAFFOLD: ... -->` marker 定位，并带 `TODO(scaffold-<provider>)` 注释。生成后必须把能力矩阵、routing、waterfall、`asset_profile`、status/env 和低稳定样本说明改成真实内容；只有临时验证脚手架结构时才使用 `--no-sync-docs` 跳过文档占位。

`references/api_notes.md` 和 `references/routing_rules.md` 的定位以 [`providers.md`](providers.md#provider-canonical-sources) 为准。

## 10. 完成定义

新增 provider 只有同时满足以下条件，才算接入完成：

- Provider 已在入口模块顶部注册完整 `ProviderBundle`，bundle discovery 能派生 catalog/source map，registry 能构建 client。
- `preferred_providers=["<provider>"]` 可限制进入该 provider 主链。
- 主路径、fallback、warnings、`source_trail` 和公开 `source` 稳定。
- `fetch_paper()` 成功时返回 `ArticleModel`，失败时按策略返回 provider-managed abstract-only 或 metadata-only。
- `asset_profile` 三种模式行为清楚，资产失败不破坏正文。
- `probe_status()` 能解释本地环境是否可用。
- 代表 fixtures、unit tests、必要 integration/golden tests 已补齐。
- 文档已同步，且不与 `providers.md` / provider bundle 的事实来源冲突。

<a id="pr-checklist"></a>
### 10.5 PR Checklist

合并前至少确认以下项：

- [ ] 已跑 scaffold 脚本生成骨架（或手工等价）
- [ ] 入口模块顶部 `register_provider_bundle` 已填充完整 `ProviderBundle`
- [ ] `ProviderHtmlRules.availability` 含 `signal_set` 或显式 `no_signals=True`
- [ ] `golden_criteria/<doi>/` 至少有一篇真实文献 fixture
- [ ] 每个 non-null manifest fixture purpose 已完成 Markdown Review Loop 并写入 provider-local 断言
- [ ] 主成功路径同时包含 Markdown 正断言和站点 chrome / access noise / boilerplate 负断言
- [ ] `manifest.json` 条目已填充（`expected_outcome` 不是 `pending`）
- [ ] `tests.golden_corpus_adapters.GoldenCorpusAdapter` 已注册，代表 fixture 覆盖主路径
- [ ] MCP provider status、benchmark sample、live review support 已随 `ProviderBundle + manifest` 同步
- [ ] `tests/unit/test_newpub_provider.py` 覆盖 fulltext / abstract-only / blocked
- [ ] `tests/unit/test_provider_bundle_completeness.py` 通过
- [ ] `docs/providers.md` 能力矩阵已同步
- [ ] `docs/extraction-rules.md` 新规则已同步（若有用户可见行为）
- [ ] `PROVIDER_CATALOG` / `provider_rules.py` / `quality/html_signals.py` / `quality/html_availability.py` 均未手动编辑
- [ ] `CHANGELOG.md` 记录

## 反模式

避免这些实现方式：

- 只靠 DOI 字符串拼全文 URL，不从 landing page 或 Crossref 信号发现 publisher 暴露的链接。
- 把任意 HTML 页面交给通用 extractor，当作 public HTML fallback。
- 用 HTTP `200` 判断成功，不校验 fulltext marker、正文长度、access gate 或 PDF payload。
- 在 provider 里直接拼最终 `FetchEnvelope`，绕过 `ProviderClient.fetch_result()`。
- 把 `route`、`markdown_text`、`source_trail`、diagnostics 写进 `raw_payload.metadata`。
- 为单篇 DOI 写硬编码特判，而不是沉淀为行为规则、fixture 和测试。
- 为已有 canonical owner 再造一套 table、formula、citation、asset 或 availability helper。
- 全文扫描 supplementary 文件后缀，导致正文数据链接、reference PDF 或站点 chrome 被误下载。
- 资产下载失败后把已经成功的正文 Markdown 判为失败。
- 新增 provider 后只改代码，不更新 docs、fixtures 和 status surface。

---

<a id="appendix-a-fixtures"></a>
## 附录 A：Fixtures 正交能力清单（Step 1 用）

收集 fixtures 时按能力维度铺开，不要积累 8-9 篇相似快乐路径。**首次接入最少这 11 篇**，缺一项后期 Step 3 会发现该能力没写过：

| 维度 | 数量 | 放置位置 | 说明 |
|---|---|---|---|
| 基础正文 structure（标题/作者/摘要/章节/参考文献） | 1 | `golden_criteria/<doi_slug>/` | 主成功路径 |
| 表格（含 inline + 复杂 caption） | 1 | `golden_criteria/<doi_slug>/` | 覆盖 `paper_fetch.extraction.html.tables` |
| 数学公式（含 MathML / image fallback） | 1 | `golden_criteria/<doi_slug>/` | 覆盖 `formula_rules` + math 渲染 |
| 图片 figure（含 multi-panel） | 1 | `golden_criteria/<doi_slug>/` | 覆盖 figure caption / 资产抽取 |
| Supplementary scope（asset_profile=all 触发） | 1 | `golden_criteria/<doi_slug>/` | 覆盖 supplementary 抽取边界 |
| References 复杂样式 | 1 | `golden_criteria/<doi_slug>/` | 覆盖 reference anchor 判定 |
| Abstract-only（provider 主动返回） | 1 | `block/` | 覆盖 provider-managed abstract-only |
| Access gate / paywall | 1 | `block/` | 覆盖 `ACCESS_GATE_PATTERNS` |
| 空壳 HTML / 非 PDF wrapper | 1 | `block/` | 覆盖正文不足判定 |
| PDF fallback 触发条件 | 1-2 | `golden_criteria/<doi_slug>/` | 覆盖 `maybe_recover_fetch_result_payload()` |

每篇 fixture 进 `tests/fixtures/golden_criteria/manifest.json`，初次 `expected_outcome` 可写 `pending`；Step 4 通过后改为 `fulltext` / `abstract-only` / `blocked`。

---

<a id="appendix-b-owner-reuse"></a>
## 附录 B：Owner 复用 grep 清单（Step 5 重构对齐用）

在自己的 `_X_html.py` / `X.py` 内逐条 grep。每条命中都要么删除并改 import canonical owner，要么在代码旁注释说明 publisher-specific 差异。

```bash
# HTTP header lookup（必须走 paper_fetch.http.headers.header_value）
git grep -nE "def _header_value|def _response_header" -- src/paper_fetch/providers/X.py src/paper_fetch/providers/_X_html.py

# Asset retry / merge（必须走 AssetRetryPolicy）
git grep -nE "def _merge_X_assets|def _is_retryable_X_asset_failure" -- src/paper_fetch/providers/

# DOI URL 候选（必须走 ProviderSpec 模板）
git grep -nE "def _doi_(xml|pdf|landing)_candidate" -- src/paper_fetch/providers/X.py

# Markdown table / figure / formula 渲染（必须走 paper_fetch.extraction.markdown_render）
git grep -nE "_render_(table|figure|formula)_markdown\b" -- src/paper_fetch/providers/_X_html.py

# 自己写的 access-gate 文案（必须先登记 ACCESS_GATE_LABELS / ACCESS_GATE_PATTERNS）
git grep -nE "\"check access\"|\"purchase this article\"|\"sign in\"" -- src/paper_fetch/providers/_X_html.py

# 自己写的 reference anchor 判定（必须走 citation_anchors）
git grep -nE "looks_like_reference|data-test.*reference|role.*doc-biblio" -- src/paper_fetch/providers/_X_html.py

# session cache 自定义 key（必须走 SessionCacheKey）
git grep -nE "_session_cache_key_X_" -- src/paper_fetch/providers/

# author extraction 自己写 fallback 链（必须走 AuthorExtractionPipeline）
git grep -nE "def _X_author_(meta|jsonld|dom)_fallback" -- src/paper_fetch/providers/

# BeautifulSoup 死防御（项目已要求 bs4 是硬依赖）
git grep -nE "BeautifulSoup is None|Tag is None" -- src/paper_fetch/providers/

# raw_payload.metadata 写诊断（必须走 ProviderContent.diagnostics）
git grep -nE "raw_payload\.metadata\[" -- src/paper_fetch/providers/X.py
```

任何一条非空且无注释解释 → 立即改。

本清单已机械化为 `tests/unit/test_provider_owner_reuse.py`；命中且没有
`# OWNER_REUSE_EXCEPTION: <一句话原因>` 注释会导致 CI 失败。

---

<a id="appendix-c-pr-checklist"></a>
## 附录 C：PR Checklist（Step 4-6 验收用）

合并前所有项必须勾选：

```
设计 / Bundle
- [ ] 设计段已写（routing / 主路径 / asset_profile / probe / abstract-only 策略）
- [ ] 已跑 scaffold 脚本生成骨架（或手工等价）
- [ ] provider 入口模块顶部 register_provider_bundle 已填完整 ProviderBundle
- [ ] ProviderHtmlRules.availability 含 signal_set 或显式 no_signals=True
- [ ] preferred_providers=["<name>"] 可限制进入主链

Fixtures（按附录 A 11 维清单）
- [ ] golden_criteria/<doi>/ 至少有一篇真实文献 fixture
- [ ] structure / table / formula / figure / supplementary / refs：各 1 篇真实 DOI HTML 或 XML
- [ ] 每个 non-null fixture purpose 已执行 Markdown Review Loop，记录 issue → assertion → fix
- [ ] abstract-only / access-gate / 空壳：各 1 篇 block fixture
- [ ] PDF fallback：1-2 篇
- [ ] manifest.json 条目已填充（expected_outcome 不是 pending）
- [ ] `expected.json` 锁了用户可见 summary，`extracted.md` 是人工 Markdown baseline，`markdown-quality-prompt.md` 存在，`markdown-quality.json` 是 agent-authored pass 报告

实现
- [ ] ProviderClient 子类只覆盖必要 hook，未绕过 fetch_result() template
- [ ] Fulltext fallback 声明为 `waterfall_steps`；只有已有 provider 的覆盖实现才局部调用 `run_provider_waterfall()`
- [ ] asset_profile 三模式（none / body / all）行为明确
- [ ] probe_status() 实现，覆盖 ready / not_configured / partial

测试
- [ ] provider unit test 已覆盖 domain / publisher / DOI 推断
- [ ] tests/unit/test_newpub_provider.py 覆盖 fulltext / abstract-only / blocked
- [ ] tests/unit/test_newpub_provider.py 覆盖每个 non-null fixture purpose，且包含 Markdown 正断言和站点 chrome 负断言
- [ ] tests/unit/test_provider_bundle_completeness.py 通过
- [ ] tests/integration/test_golden_corpus.py 跑通（PAPER_FETCH_RUN_FULL_GOLDEN=1）

重构对齐（Step 5）
- [ ] 附录 B 全部 grep 已自查
- [ ] 没有 local helper 跟 canonical owner 重复

中心模块零编辑（详见附录 D）
- [ ] PROVIDER_CATALOG / provider_rules.py / quality/html_signals.py / quality/html_availability.py 均未手动编辑

文档
- [ ] docs/providers.md 能力矩阵 + routing + waterfall + asset_profile + status 同步
- [ ] docs/extraction-rules.md 用户可见新规则同步（若有）
- [ ] docs/architecture/overview.md 新 canonical owner 同步（若有）
- [ ] docs/deployment.md / .env.example 新环境变量同步（若有）
- [ ] CHANGELOG.md 用户可见能力记录
```

---

<a id="appendix-d-central-module-zero-edit"></a>
## 附录 D：中心模块零编辑保证（S1-S6 落地后）

新 provider PR **不应触动**以下文件（这些文件的 git diff 行数应为 0）：

| 文件 | 为什么不动 | 怎么补充 provider 行为 |
|---|---|---|
| `src/paper_fetch/provider_catalog.py` | 不维护 provider 行为 | 在 provider entry module 顶部 `register_provider_bundle(ProviderBundle(catalog=ProviderSpec(...)))`；scaffold 初期 `_X_html.py` 只可作为兼容 facade |
| `src/paper_fetch/extraction/html/provider_rules.py` | 不维护 provider-owned helper 字典 | 同上，bundle 内 `html_rules=ProviderHtmlRules(...)` 直接持 provider-owned helper 引用 |
| `src/paper_fetch/quality/html_signals.py` | 不维护 provider 专属 signal 函数 | 在 bundle 的 `availability.datalayer_signal_set` / `text_marker_signal_set` 填数据 |
| `src/paper_fetch/quality/html_availability.py` | 不维护 provider 名分支 | 在 bundle 的 `availability.overrides` 填数据 |

如果你的 PR 触动了这 4 个文件中的任何一个，**说明 provider 行为没有放在 bundle 注册边界内**，CI `test_no_central_provider_functions.py` 会失败。

新 provider 的所有编辑应集中在：
- `src/paper_fetch/providers/_X_html.py`（hooks + signal sets + authors / references）
- `src/paper_fetch/providers/X.py`（fulltext client，可选）
- `tests/fixtures/golden_criteria/<doi_slug>/*` + `manifest.json` 追加条目
- `tests/unit/test_X_provider.py`
- `docs/providers.md` / `docs/extraction-rules.md` / `CHANGELOG.md` 追加段
