# Paper Fetch Skill 可改进项

本文档是当前仓库 backlog 的唯一真理源。架构 rationale 继续放在 `docs/architecture/target-architecture.md`，但后续收口项和剩余观察点只在这里维护。

---

## 仍未处理

### 优先级 P0（正确性 / 安全性）

- 当前无 P0 项。

### 优先级 P1（可维护性)

- **`html_generic.py` 1615 行未拆分**
  - 与 `problems.md` 里已完成的 `_article_markdown` 拆分不对称；承担了 HTML 清洗 / figure 识别 / supplementary 识别 / Nature 专用路径 / markdown 清洗 / 资产下载 / client 类
  - 建议拆成 `html_noise.py` / `html_assets.py` / `html_nature.py` / `html_generic.py`（只剩 `HtmlGenericClient` + `parse_html_metadata`）

### 优先级 P2（体验 / 结果质量）

- **Wiley PDF 抽取结果全部塞进单个 section**
  - [src/paper_fetch/providers/wiley.py:68-72](src/paper_fetch/providers/wiley.py#L68-L72) `pdf_text_to_markdown` 把整个 PDF 文本塞进 `## Full Text`；`lines_to_sections` 因此只能产出一个 section，`max_tokens` 裁剪失去 section-priority 意义
  - 最小改动：对 `WILEY_PDF_FULLTEXT_MARKERS` 做行首匹配，把 Introduction / Methods 等行升格成 `## Introduction`
- **CLI 退出码粒度过粗**
  - [src/paper_fetch/cli.py:189-191](src/paper_fetch/cli.py#L189-L191) `ProviderFailure` 与 `PaperFetchFailure`（除 ambiguous）全部 `exit 1`
  - 建议 `no_access=3` / `rate_limited=4` 等细化，便于 shell / agent 决策
- **CLI `modes` 组合逻辑分散难读**
  - [src/paper_fetch/cli.py:141-165](src/paper_fetch/cli.py#L141-L165) 4 行 if-else 构造 modes，`"markdown"` 但输出到文件时为何 add `"article"` 没有解释；抽 `_compute_modes(args)` 并加注释
- **HTTP 缺 `Accept-Encoding: gzip`**
  - 对 Crossref / Elsevier JSON/XML 明显省带宽；若要保持零外部依赖，需要自己处理 gzip 解压
- **`extract_full_size_figure_image_url` 全量排序**
  - [src/paper_fetch/providers/html_generic.py:574-588](src/paper_fetch/providers/html_generic.py#L574-L588) 对所有 img/source 完全排序；应在命中首个 `/full/` 或 `springernature.com` 时提前 return
- **`fetch_paper` metadata 模式 fallback 隐藏 upstream 状态**
  - [src/paper_fetch/service.py:529-531](src/paper_fetch/service.py#L529-L531) envelope.metadata 为 None 时塞入空 `Metadata()`，掩盖上游实际未生成 metadata 的情况；应直接 `metadata_model_from_mapping(article.metadata)`
- **`MaxTokensMode = int | Literal["full_text"]` sentinel 类型混用**
  - [src/paper_fetch/models.py:337](src/paper_fetch/models.py#L337) `max_tokens - estimate_tokens(...)` 若 caller 误把 `"full_text"` 走到该分支会 TypeError；用 `None` 或 `math.inf` 代替 sentinel 更干净
- **`test_paper_fetch.py` 1697 行 all-in-one**
  - 按被测模块拆成 `test_service.py` / `test_models_render.py` / `test_http_cache.py` 便于定位与并行

### 原有真实论文边角 case

- 极端公式块、代码块与 ASCII 表格混排时的 Markdown 保真度
- Wiley PDF 抽取在复杂版式论文上的稳定性
- 少数 publisher 页面在 HTML fallback 下的正文噪音过滤

---

## 本轮已完成

### 文档与资源语义

- ✅ `target-architecture.md` 不再并行维护 follow-on backlog；当前 backlog 只在本文件更新
- ✅ `references/` 明确降级为设计草稿 / 人工参考资料，不再自称运行时 authoritative 数据
- ✅ 当前 routing 真理源已明确回到运行时代码里的保守推断逻辑，而不是 `journal_lists.yaml`
- ✅ benchmark 产物路径从 tracked 的 `references/formula_backend_report.json` 挪到 `.formula-benchmarks/`
- ✅ `scripts/` 已明确保留为安装器与开发/诊断自动化入口，`scripts/__init__.py` 已删除，不再伪装成 Python package

### 运行时行为与安全性

- ✅ `HttpTransport` 的进程内 LRU GET 缓存已加 `threading.RLock` 保护
- ✅ `HttpTransport` 新增默认 `32 MiB` 响应大小上限；超限直接抛 `RequestFailure`，避免大 PDF / supplementary 一次性读爆内存
- ✅ `HttpTransport.request()` 新增 `retry_on_transient`，对 `HTTP 5xx` 与 timeout-class 网络错误做有限指数退避；当前已启用 `retry_on_rate_limit=True` 的 provider / HTML 请求链路已同步打开
- ✅ `429` 仍只走 `Retry-After` 语义，不与瞬时错误重试混用
- ✅ CLI 默认下载目录已改为：`PAPER_FETCH_DOWNLOAD_DIR` -> `XDG_DATA_HOME/paper-fetch/downloads` -> 创建失败时回落 `./live-downloads`
- ✅ `--save-markdown` 与 Wiley raw/binary 落盘已统一走同一套目录解析逻辑
- ✅ `maybe_download_provider_assets()` 只降级处理 `ProviderFailure | RequestFailure | OSError`；`AttributeError` / `TypeError` 等编程错误不再被伪装成 partial download
- ✅ `resolve_query()` 的 landing-page fetch 只包装 `RequestFailure`；HTML 解析与后续逻辑里的编程错误继续向外冒泡
- ✅ provider 路由已从“DOI prefix 主导”切到“Crossref publisher / landing-page domain 主导，DOI 只做最后 fallback”
- ✅ `resolve_paper().provider_hint` 已改成 Crossref/domain-first 语义；纯 DOI 在需要时会补一次 Crossref DOI metadata lookup
- ✅ `fetch_metadata_for_resolved_query()` 已改成三态 probe：`positive=命中`、`negative=no_result`、`unknown=no_access/rate_limited/error/not_configured/not_supported`
- ✅ `preferred_providers` 继续限制最终来源链路，但允许内部 Crossref 仅作为 routing signal 使用
- ✅ `source_trail` 已补充 `route:*` 诊断标记，用于区分路由信号与真实 metadata/fulltext 来源

### 依赖与护栏

- ✅ `pyproject.toml` 已区分 runtime 依赖和 `dev` extra
- ✅ runtime 依赖已从补丁级 `==` pin 改成 library 友好的 `>=,<` 范围约束；精确开发安装继续收敛在 `requirements.txt` / lockfile
- ✅ `pyproject.toml` 已显式声明 `pydantic>=2,<3`，不再依赖 `mcp` 的传递依赖碰巧托底
- ✅ 新增 `ruff` 配置与独立 `lint` CI job
- ✅ 新增 `.github/dependabot.yml`，覆盖 `pip`、`npm`、`github-actions`
- ✅ `requirements.txt` 已收敛为开发者便利入口，不再平铺 runtime pins
- ✅ `scripts/dev-bootstrap.sh` 已改为直接安装 `.[dev]`，避免重复安装 runtime 依赖

### 可维护性

- ✅ `_article_markdown.py` 已拆分成共享 helper、公式渲染、Springer、Elsevier、文档装配五层，原模块保留薄 façade 兼容入口
- ✅ Markdown 回归测试继续覆盖 Elsevier / Springer 主路径，拆分后输出行为保持不变
- ✅ façade 兼容入口已有守卫测试，继续暴露 `render_mathml_expression`、`build_article_structure`、`write_article_markdown`
- ✅ `ArticleModel.to_ai_markdown()` 已收敛到单一路径；`max_tokens="full_text"` 现在会先归一成 `math.inf` 预算，再复用同一套渲染/裁剪逻辑
- ✅ `estimate_tokens()` 继续保留为安全入口，但裁剪热路径已改用“已 normalized 文本”的轻量 token 估算 helper，避免在 section/group/reference 循环里重复 normalize
- ✅ `_fetch_article()` 已拆成 `_try_official_provider()` / `_try_html_fallback()` / `_fallback_to_metadata_only()`，主流程改成线性串联，warning 与 `source_trail` 语义保持不变
- ✅ HTTP GET 缓存键已从“全部请求头”收敛为语义白名单：`accept`、`accept-language` 和认证/权限相关头；`User-Agent` 这类 incidental header 不再导致 cache miss
- ✅ DOI 提取逻辑已统一到 `publisher_identity.extract_doi()`；`resolve/query.py` 与 `html_generic.py` 不再各自维护一份 DOI regex
- ✅ 新增共享 `safe_text()` helper，已替换本轮 models/service 等维护性收口中的链式 `normalize_text(str(x or \"\"))` 噪音
- ✅ 已补守卫测试，覆盖 `full_text` 与大预算渲染等价、缓存键白名单行为、共享 DOI 提取

### 既有收口基线

- ✅ 当前分支继续视为 `core library + CLI + MCP + thin skill` 的已实现基线
- ✅ closeout 守卫测试持续阻止 `tests/` 回退到旧的导入 hack
- ✅ CLI `--help` smoke 和 MCP stdio integration smoke 已收编进 integration 验收基线
- ✅ `tests/` 继续按 `unit/ integration/ live/` 分层，根目录 `unittest discover -s tests -q` 保持可用
- ✅ 当前离线验收基线已覆盖 `ruff check .`、`tests/unit`、`tests/integration` 和根目录 `tests/` discover
