# 重构审计结论

下面是对仓库结构的扫描结果，按"收益 vs. 风险"分档。所有判断都基于代码实际状态（行数、重复符号、调用关系），不需要新增设计就能落地。

---

## 一、零风险、收益立即可见（纯删重复）

### 1. `_first_url_from_srcset` / `_soup_attr_url` 在两处逐字重复
- `src/paper_fetch/extraction/html/_assets.py:524, 549`
- `src/paper_fetch/providers/_springer_html.py:536, 546`

两处实现一模一样。Springer 模块直接 `from ..extraction.html._assets import …` 即可，省一份代码并避免后续走偏。

### 2. 作者抽取在 4 个 provider 里几乎复制粘贴
`_node_author_text` / `_extract_dom_authors` / `extract_authors` 同时存在于：
- `providers/_pnas_html.py:43,59`
- `providers/_science_html.py:65,80`
- `providers/_springer_html.py:177,181,206`
- `providers/_wiley_html.py:90,106,123`

仓库里已经有 `_browser_workflow_authors.py`，正确的做法是把"通用 DOM 作者抽取 + 出版商特异化 hook"抽到一个 `_html_authors.py`，4 个 provider 只保留各自的过滤/归一规则（如 Springer 的 collective author / AI 免责）。这是最值得做的去重。

### 3. `providers/html_assets.py` 只是 42 行 re-export 门面
`providers/html_assets.py:1-43` 是 `extraction/html/_assets` 的兼容门面，且仅被仓库内自己使用（grep 显示外部无依赖）。两条路：
- 直接删，调用方改为 `from ..extraction.html._assets import …`；
- 或者保留门面但只让外部 (skill 用户脚本/测试) 用，内部全部直连真模块。

继续保留的成本是：每次新增 helper 都要在两处写。

---

## 二、明显能减规模、改动机械

### 4. `models.py` 2828 行，混了 6 类职责
当前文件包含：
- 数据 schema（`Metadata` / `Section` / `Asset` / `Reference` / `Quality` / `ArticleModel` / `FetchEnvelope`）
- Markdown 行/图像归一化（`normalize_markdown_text`、`_normalize_markdown_image_block_boundaries`、`_collapse_display_math_padding` …）
- token 估算和预算（`estimate_tokens`、`truncate_text_to_tokens`）
- 内容分级和质量降级（`_refresh_article_quality`、`apply_quality_assessment`、`_diagnostics_require_downgrade`）
- 渲染管线（`build_rendered_block`、`render_section_block`、`append_*_block_with_budget`）
- section 解析（`lines_to_sections`、`split_leading_inline_abstract`、`_abstract_sections_from_blocks`）

把它拆成 `models/` 包（`schema.py` / `markdown.py` / `tokens.py` / `quality.py` / `render.py` / `sections.py`）就够了，公共 API 再用 `models/__init__.py` re-export 一遍——150 个 top-level 名字按 6 个文件分摊后，可读性会变质变。零行为变化，只要测试通过就完事。

### 5. `extraction/html/_assets.py` 1809 行也是同类问题
里面同时承载图像 srcset 解析、figure / formula / supplementary 抽取、cookie opener、_FigureParser、download_*、identity key 等。拆成 `extraction/html/assets/` 包（`figures.py` / `formulas.py` / `supplementary.py` / `download.py` / `dom.py`）即可，跟 (4) 同一思路。

### 6. `_browser_workflow_fetchers.py` 里两套 Playwright fetcher 共享 80% 状态
- `_SharedPlaywrightImageDocumentFetcher`（line 398, ~560 行）
- `_SharedPlaywrightFileDocumentFetcher`（line 1181, ~260 行）

`__init__` 几乎一样的字段（`_browser_context_seed_getter`、`_seed_urls_getter`、`_playwright_manager`、`_browser`、`_context`、`_page`、`_warmed_seed_urls`、`_last_failure_by_url`、`_recovery_attempts_by_url`、`_challenge_recovery`、`_runtime_context`、`_use_runtime_shared_browser`），`_ThreadLocalShared*` 两个再各自包一层。提一个 `_BasePlaywrightDocumentFetcher` 把生命周期、warm-up、failure 记账、challenge recovery 落到基类，子类只暴露 "fetch_one(url, asset)"——能砍掉数百行并且让"图像 vs. 文件"的差异点变可见。

---

## 三、需要思考一点架构、但收益最大

### 7. 三个 provider 各写一份"figure / supplementary / scoped assets"
对照：

| 函数                          | 通用版                                      | provider 各自版                                    |
|-------------------------------|---------------------------------------------|---------------------------------------------------|
| `extract_figure_assets`       | `extraction/html/_assets.py:809`            | `_springer_html.py:728`                            |
| `extract_supplementary_assets`| `extraction/html/_assets.py:868`            | `_springer_html.py:811`、`_science_pnas_html.py:604`、`_wiley_html.py:251` |
| `extract_scoped_html_assets`  | `extraction/html/_assets.py:903`            | `_springer_html.py:968`、`_science_pnas_html.py:612`、`_wiley_html.py:290` |

这些差异本质上是"出版商特异 selector + 是否支持 supplementary 链接 + figure/source-data 范围切分"。如果改成"通用引擎 + publisher policy（dataclass 或 protocol）"，一来 1k+ 行能合掉，二来后面要新增 ams/jp/aps/mdpi/copernicus（todo.md 第 8 条）就只是写一个 policy 文件，而不是再 fork 一份 `_xxx_html.py`。这是与你 todo 路线最契合的一条。

### 8. `_science_pnas_html.py` 1847 行 + 三个外围
`_pnas_html.py` (121 行) + `_science_html.py` (225 行) + `_science_pnas_profiles.py` + `_science_pnas_postprocess.py` + `_science_pnas_html.py` 已经是隐式包结构。直接物化成 `providers/science_pnas/` 包并把 1.8k 主文件按职责切分（profile 选择 / 容器选择 / supplementary / figure scope / postprocess），跟 (4)(5) 同一类操作。

---

## 四、可考虑、但不建议先做

- **`mcp/tools.py` 1223 行**：log bridge + 6 个 tool entry + batch + payload 构造。可拆，但目前一个文件读起来还行，先不动。
- **`utils.py` 278 行**：成长的 grab-bag（URL / 文本归一 / 文件名 / asset path），等到出现下次新增功能再拆。
- **`golden_criteria_live.py` (1300) / `geography_live.py` (696) / `geography_issue_artifacts.py`** 是诊断/报表型代码、只有 tests/live 在用，挪到 `paper_fetch/diagnostics/` 子包能降低主包的概念表面积，但不紧迫。

---

## 建议次序

1. **(1)(2)(3) 一次提交**：纯去重、删除门面、合并作者抽取——半天工作量，回归压力小。
2. **(6) Playwright fetcher 基类**：一次提交，行数收益和阅读收益都明显。
3. **(7) Provider HTML asset 引擎统一**：与 todo "新增 mdpi / copernicus / ametsoc" 协同，节奏上放到这个新增工作之前做。
4. **(4)(5)(8) 大文件分包**：纯模块级搬迁，建议每个独立 PR，便于 review 和回退。
