# Paper Fetch Skill 可改进项

本文档记录当前 skill 实现中可以优化的地方。条目按完成状态分两部分：
上半部分列出仍未处理的开放项，下半部分列出已完成的历史条目，供后来者对照。

---

## 仍未处理

当前没有阻塞性开放项。本轮已把原先的 bug、设计项和文档项全部落地；后续主要继续观察真实论文里的复杂 Markdown 结构（极端公式块、代码块、ASCII 表格混排）是否还会出现新的边角 case。

---

## 已完成

### SKILL.md 与模板

- ✅ **模板化 SKILL.md**：新增 [templates/skill_template.md](templates/skill_template.md) 与 [scripts/render_skill_template.py](scripts/render_skill_template.py)，[install.sh](install.sh) 与 [install-codex.sh](install-codex.sh) 在安装时渲染绝对路径版本写入 `~/.claude/skills/` 或 `~/.codex/skills/`。
- ✅ **删除死链 `scripts/fetch_article.py`**：模板不再引用该文件。
- ✅ **补全 Examples / When NOT to Use / stderr JSON schema / `--output-dir` / `--no-download`**：全部落到 [templates/skill_template.md](templates/skill_template.md)。
- ✅ **收紧 description 字段**：[templates/skill_template.md:3](templates/skill_template.md#L3) 强调 "one specific paper" 并显式排除综述 / 发现类请求，降低误触发。
- ✅ **删除仓库内陈旧 `.claude/skills/paper-fetch-skill/SKILL.md`**：避免双份真相；`./install.sh --project` 可随时重新生成项目级副本。
- ✅ **模板渲染完整性测试**：[tests/test_skill_template.py](tests/test_skill_template.py) 断言渲染结果不残留 `${` 变量，且 `build_context` 覆盖模板里出现的全部变量。

### 主流程（scripts/paper_fetch.py）

- ✅ **运算符优先级**：[scripts/paper_fetch.py:126-129](scripts/paper_fetch.py#L126-L129) 拆成明确的 if / else 三段。
- ✅ **Wiley 落盘解耦**：新增 `--no-download` 独立开关，落盘副作用抽到 [scripts/paper_fetch.py:183-211](scripts/paper_fetch.py#L183-L211) 的 `maybe_save_provider_payload`，与 `--no-html-fallback` 不再耦合。
- ✅ **`merge_metadata` 空串语义**：[scripts/paper_fetch.py:56-86](scripts/paper_fetch.py#L56-L86) 引入 `preserve_blank`，primary 显式置空字段不再被 secondary 覆盖。
- ✅ **空 front-matter 不再渲染空串字段**：`merge_metadata` 在出口收敛空白标量，`ArticleModel.to_ai_markdown` 只输出有值的 front-matter 字段，`title: ""` / `authors: ""` 这类空 YAML 已消失。
- ✅ **`merge_metadata` 作者列表改为语义去重**：公共层提取 `canonical_author_key` / `dedupe_authors` 后，`"Zhang, San"` 与 `"San Zhang"` 不再重复保留。
- ✅ **provider binary 落盘按 payload 语义判定**：`RawFulltextPayload` 新增 `needs_local_copy`，`maybe_save_provider_payload` 不再硬编码 `provider_name == "wiley"`。
- ✅ **删除未使用的函数参数**：[scripts/paper_fetch.py:214-224](scripts/paper_fetch.py#L214-L224) 的 `fetch_paper_model` 不再收 `include_refs` / `max_tokens`，截断逻辑统一在 `serialize_article`。
- ✅ **结构化 source trail**：`ArticleModel.quality.source_trail` 全链路记录决策（`resolve:doi_selected`、`fulltext:wiley_fail`、`fallback:html_ok` 等），替代原先只写字符串 warnings 的可观测性方案。

### resolve_query.py

- ✅ **硬编码阈值抽常量**：[scripts/resolve_query.py:26-35](scripts/resolve_query.py#L26-L35) 的 `CONFIDENT_SCORE_MIN` / `CONFIDENT_MARGIN_MIN` / `MIN_HTML_TITLE_LOOKUP_CHARS` / `HTML_TITLE_LOOKUP_DENYLIST`。
- ✅ **URL 路径 title 校验**：[scripts/resolve_query.py:118-122](scripts/resolve_query.py#L118-L122) 的 `is_viable_html_title_for_lookup` 挡掉 `Sign in` / `Just a moment` / `cookie` 等噪声 title。
- ✅ **成功分支清空 candidates**：[scripts/resolve_query.py:181](scripts/resolve_query.py#L181) 与 [scripts/resolve_query.py:207](scripts/resolve_query.py#L207) 在选出 top_one 后 `candidates=[]`，下游无需靠 `doi is None` 隐式约定。
- ✅ **URL 分支统一带 User-Agent**：[scripts/resolve_query.py:157](scripts/resolve_query.py#L157) 通过 `build_user_agent(active_env)` 注入，和下游 `HtmlGenericClient.fetch_article_model` 行为一致，不再出现 "resolve 403 但 HTML fallback 本能成" 的反常退路。
- ✅ **URL 分支 confidence 不再硬编码 0.4**：[scripts/resolve_query.py:174](scripts/resolve_query.py#L174) 现为 `0.95 if resolved_doi else 0.0`，有 DOI 的 URL 得到高置信度，无 DOI 的走 Crossref title 查 candidates 后用 `top_one["score"]` 真实换算。

### HTTP / 缓存层

- ✅ **HTTP 层缓存**：[scripts/fetch_common.py:116-192](scripts/fetch_common.py#L116-L192) 的 `HttpTransport` 带 TTL + LRU GET 缓存；`paper_fetch.py` 共享同一 transport，resolve 阶段与 metadata 阶段的重复 Crossref GET 直接命中缓存。
- ✅ **缓存只对文本类响应生效**：[scripts/fetch_common.py:27-30](scripts/fetch_common.py#L27-L30) 的 `DEFAULT_MAX_CACHEABLE_BODY_BYTES = 1MB` + `TEXTUAL_CONTENT_TYPES` 白名单；`_store_cached_response` 调 `_is_cacheable_response` 过滤。Wiley PDF 等二进制不再进内存缓存。
- ✅ **缓存 key 规范化，剔除敏感 header**：[scripts/fetch_common.py:163-169](scripts/fetch_common.py#L163-L169) 的 `_normalize_header_value_for_cache` 对 `SENSITIVE_CACHE_HEADER_NAMES`（`Wiley-TDM-Client-Token` / `X-ELS-APIKey` 等）统一替换成 `REDACTED_CACHE_VALUE`，明文 token 不再落进 key。
- ✅ **`sanitize_filename` 增加长度上限与 hash 兜底**：长 DOI 会截到安全长度，纯中文 / 纯符号标题会稳定回退到 `fulltext_<hash>`，避免保存阶段失败或文件名全撞到一起。
- ✅ **429 / Retry-After 识别与单次退避**：[scripts/fetch_common.py:254-271](scripts/fetch_common.py#L254-L271) 读 `Retry-After` 头并在 `max_rate_limit_wait_seconds` 内做一次 `time.sleep` 重试；[scripts/fetch_common.py:480-481](scripts/fetch_common.py#L480-L481) 的 `map_request_failure` 把 429 映射到独立的 `rate_limited` code 并透传 `retry_after_seconds`。
- ✅ **Fulltext 下载路径独立超时**：[scripts/fetch_common.py:24](scripts/fetch_common.py#L24) 新增 `DEFAULT_FULLTEXT_TIMEOUT_SECONDS = 90`，Wiley / Elsevier / Springer 的 PDF/XML 下载路径全部使用该常量（见 [scripts/providers/wiley.py:140](scripts/providers/wiley.py#L140) / [scripts/providers/elsevier.py:232](scripts/providers/elsevier.py#L232) / [scripts/providers/springer.py:151](scripts/providers/springer.py#L151)），metadata 路径仍用 20 秒默认值。
- ✅ **`HttpTransport` 明确标注非线程安全**：类 docstring、README 与 provider 文档都已说明“并发时每个线程 / worker 单独创建 transport”。

### Markdown / HTML fallback

- ✅ **`to_ai_markdown` 不再污染 `self.quality.warnings`**：截断 warning 仅在当次渲染上下文里处理，`to_json()` 不再被 Markdown 渲染副作用污染。
- ✅ **Markdown 正文归一化与标量归一化分离**：`normalize_markdown_text` 保留 fenced code、缩进块和 ASCII 表格，不再把 HTML fallback / Wiley PDF 路径里的结构拍平。
- ✅ **HTML fallback 改为自适应正文阈值**：常规正文仍按较高长度门槛把关，CJK-heavy 页面和带 DOI 的短 commentary / editorial 可在约 300 字符级别通过；真实样本 `10.1038/sj.bdj.2017.900` 已从 metadata-only 变为 `html_generic` 成功回退。

### resolve_query / 工程细节
- ✅ **依赖 pin**：[requirements.txt](requirements.txt) 已 pin `trafilatura==2.0.0` / `lxml==6.0.3` / `beautifulsoup4==4.14.3` / `PyMuPDF==1.27.2.2`。
- ✅ **Wiley PDF / `--no-download` / `--no-html-fallback` 测试覆盖**：[tests/test_paper_fetch.py:283-495](tests/test_paper_fetch.py#L283-L495) 四个用例分别覆盖 PDF 正文提取成功、`--no-download` 跳过落盘、PDF 提取失败回退 HTML、PDF 提取失败且 HTML fallback 关闭时退到 metadata-only。
- ✅ **`.env` 缺 key 的 `source_trail` 已区分 `not_configured`**：metadata/fulltext 路径都能记录 `metadata:<provider>_not_configured` / `fulltext:<provider>_not_configured`，和普通失败不再混淆。
- ✅ **repo 搬家后的重装提示已补齐**：README、模板和安装脚本都会明确提示“如果 repo 被移动，请重新运行安装脚本刷新绝对路径”。
- ✅ **provider 速率限制与缓存文档**：[docs/providers.md](docs/providers.md) "速率限制与缓存" 小节说明进程内缓存机制、各 provider 的参考速率、并行调用时的约束。
