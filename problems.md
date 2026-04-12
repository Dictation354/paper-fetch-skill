# Paper Fetch Skill 可改进项

本文档是当前仓库 backlog 的唯一真理源。架构 rationale 继续放在 `docs/architecture/target-architecture.md`，但后续收口项和剩余观察点只在这里维护。

---

## 仍未处理

### 优先级 P0（正确性 / 安全性）

- 当前无 P0 项。

### 优先级 P1（可维护性)

- **HTTP transport 没有连接复用**（`src/paper_fetch/http.py:205-223`）。`urllib.request.urlopen` 每次都新建 TCP+TLS；对 Elsevier/Springer/Wiley 一次 fetch 多条请求的链路（metadata→fulltext→figures→supplementary），同一域名建连成本占大头。两条路径：(a) 继续用 stdlib，但用 `http.client.HTTPSConnection` per host pool 串行复用；(b) 引入 `urllib3` / `httpx` 为 runtime 依赖直接 pool。动 transport 涉及 cache 行为与测试 stub，建议单独 PR。
- **`ArticleModel.to_ai_markdown` 仍承担太多职责**（`src/paper_fetch/models.py:264-407`）。虽然 `RenderContext` 和热路径规范化已收口，但主函数仍混合 front matter、abstract、section 选择和多类 block 拼装。后续若继续重构，优先把“渲染计划生成”和“budget 驱动追加”拆成更小 helper。
- **缺少结构化日志**。全仓只用 `source_trail` 列表 + 错误分支的 stderr JSON；一旦线上某个 live fetch 走偏，重现只能靠 rerun。加一个 `logging.getLogger("paper_fetch.*")`，保留现有 trail 语义，让 `_try_official_provider` / `_try_html_fallback` 在每一步 debug 级打印 url、状态、耗时。不改 public API，纯 opt-in。
- **provider metadata 仍是松散 `dict[str, Any]`**。`metadata.get("landing_page_url")` / `metadata.get("publisher")` / `metadata.get("fulltext_links")` 在 6+ 处读写，字段漂移无人抓得住。换成 `typing.TypedDict`，零运行时成本，ruff 能静态抓未知 key；可以分几次递进。

### 优先级 P2（体验 / 结果质量）

- **`Asset.path` / `caption` / `url` 类型不统一**（`src/paper_fetch/models.py:204-211`），一部分 `str | None`、一部分默认 `""`。统一成 `str | None`，渲染层判空更直接。
- **`_try_official_provider` 往 `raw_payload.metadata` 里塞 `downloaded_assets` / `asset_failures`**（`src/paper_fetch/service.py:494-495`）是隐式共享状态。由调用方以返回值传递更清晰。

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
- ✅ 文本归一化 helper 已收口到 `utils.normalize_text()`；`models.normalize_text` 保留为兼容导出，`safe_text()` 直接复用同一实现
- ✅ `extend_unique()` 已下沉到 `utils.py`，CLI 与 service 不再各维护一份副本
- ✅ service/html fallback 两处同名异义 `merge_metadata()` 已完成消歧，改为 `merge_primary_secondary_metadata()` / `merge_html_metadata()`
- ✅ HTML lookup denylist 与可复用标题判定逻辑已统一到共享 `html_lookup.py`

### 运行时行为与安全性

- ✅ `HttpTransport` 的进程内 LRU GET 缓存已加 `threading.RLock` 保护
- ✅ `HttpTransport` 新增默认 `32 MiB` 响应大小上限；超限直接抛 `RequestFailure`，避免大 PDF / supplementary 一次性读爆内存
- ✅ `HttpTransport` 的 gzip 分支现在会先按压缩体字节数做上限检查，再解压；避免对手端在解压前用超大 gzip 打满内存
- ✅ `save_payload()` 与所有走该入口的 provider/HTML asset 落盘现在都改成 `.part -> replace` 原子写；临时写失败不会污染最终文件
- ✅ `HttpTransport.request()` 新增 `retry_on_transient`，对 `HTTP 5xx` 与 timeout-class 网络错误做有限指数退避；当前已启用 `retry_on_rate_limit=True` 的 provider / HTML 请求链路已同步打开
- ✅ `429` 缺少 `Retry-After` 时现在会退化到一次短退避重试，仍受 `max_rate_limit_wait_seconds` 上限约束
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
- ✅ `html_generic.py` 已拆分成 `html_noise.py` / `html_assets.py` / `html_nature.py` / `html_generic.py` façade；现有 `HtmlGenericClient`、`parse_html_metadata` 和常用 helper 入口保持兼容
- ✅ `ArticleModel.to_ai_markdown()` 已收敛到单一路径；`max_tokens="full_text"` 现在会先归一成 `math.inf` 预算，再复用同一套渲染/裁剪逻辑
- ✅ `estimate_tokens()` 继续保留为安全入口，但裁剪热路径已改用“已 normalized 文本”的轻量 token 估算 helper，避免在 section/group/reference 循环里重复 normalize
- ✅ `ArticleModel.to_ai_markdown()` 已引入 `RenderContext`，把剩余 budget、truncation 标记和 warning 收口到单一状态对象
- ✅ section / asset / reference 渲染热路径现在复用 `RenderedBlock` 预计算结果，不再在循环里重复执行 `normalize_markdown_text()`
- ✅ `max_tokens="full_text"` 的字符串 sentinel 现在只停留在公开输入边界；渲染内部已先归一化成 `token_budget + full_text_requested`
- ✅ `_fetch_article()` 已拆成 `_try_official_provider()` / `_try_html_fallback()` / `_fallback_to_metadata_only()`，主流程改成线性串联，warning 与 `source_trail` 语义保持不变
- ✅ HTTP GET 缓存键已从“全部请求头”收敛为语义白名单：`accept`、`accept-language` 和认证/权限相关头；`User-Agent` 这类 incidental header 不再导致 cache miss
- ✅ DOI 提取逻辑已统一到 `publisher_identity.extract_doi()`；`resolve/query.py` 与 `html_generic.py` 不再各自维护一份 DOI regex
- ✅ 新增共享 `safe_text()` helper，已替换本轮 models/service 等维护性收口中的链式 `normalize_text(str(x or \"\"))` 噪音
- ✅ 已补守卫测试，覆盖 `full_text` 与大预算渲染等价、缓存键白名单行为、共享 DOI 提取
- ✅ 单个超大 `tests/unit/test_paper_fetch.py` 已拆成 `test_cli.py` / `test_service.py` / `test_models_render.py`，共享 stub/fixture 已下沉到 `tests/unit/_paper_fetch_support.py`
- ✅ `HttpTransportCacheTests` 已拆到独立的 `test_http_cache.py`，`test_fetch_common.py` 只保留通用 helper / packaging 守卫
- ✅ P0 HTTP/落盘修复已补守卫测试：覆盖 gzip 压缩体上限、429 无 `Retry-After` 短退避，以及 `save_payload()` 原子写失败不污染旧文件
- ✅ 渲染管线重构已保持守卫测试绿：覆盖 `full_text` 与大预算渲染等价、CLI Markdown 输出兼容，以及 token budget 裁剪行为不变

### 既有收口基线

- ✅ 当前分支继续视为 `core library + CLI + MCP + thin skill` 的已实现基线
- ✅ closeout 守卫测试持续阻止 `tests/` 回退到旧的导入 hack
- ✅ CLI `--help` smoke 和 MCP stdio integration smoke 已收编进 integration 验收基线
- ✅ `tests/` 继续按 `unit/ integration/ live/` 分层，根目录 `unittest discover -s tests -q` 保持可用
- ✅ 当前离线验收基线已覆盖 `ruff check .`、`tests/unit`、`tests/integration` 和根目录 `tests/` discover

### 体验 / 结果质量

- ✅ Wiley PDF 抽取现在会按 heading 行拆成 `Abstract` / `Introduction` / `Methods` / `Results` 等 section，`max_tokens` 裁剪重新具备 section-priority 语义
- ✅ CLI 退出码已细化为 `ambiguous=2`、`no_access=3`、`rate_limited=4`，其余失败保留 `1`
- ✅ CLI `modes` 组合逻辑已收敛到 `_compute_modes(args)`，并补了为何文件输出/`--save-markdown` 需要 `article` 模式的注释
- ✅ CLI Markdown 资产链接改成“占位符渲染 -> 定点替换相对路径”；不会再对整段正文做绝对路径字符串替换
- ✅ `HttpTransport` 的进程内 GET 缓存已新增总体字节上限；超过预算时按 LRU 淘汰旧响应，避免长会话常驻 ~128 MiB 文本缓存
- ✅ `HttpTransport` 现在默认发送 `Accept-Encoding: gzip`，并会用标准库透明解压 gzip 响应后再执行响应体大小限制
- ✅ `extract_full_size_figure_image_url()` 不再对全部候选排序；命中 `/full/` 或 `springernature.com` 候选时会提前返回
- ✅ `fetch_paper` 在 metadata 模式下不再伪造空 `Metadata()`；只返回真实的 `article.metadata`
