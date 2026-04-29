# 项目冗余代码审计（2026-04-29）

## 处理状态

2026-04-29 已按“全量清理”处理 §1-§4：
- §1、§2 的重复/近似重复 helper 已统一到 `paper_fetch.extraction.html.shared`，provider 与 quality 侧改为 import 共享实现。
- §3 的死代码已删除：`providers/_html_text.py`、`browser_workflow.preferred_html_candidate_from_landing_page` 兼容 wrapper、`fallback_figure_heading`。
- §4 的 `_article_markdown.py` facade 已删除，Elsevier 调用方改为直接依赖 `_article_markdown_elsevier_document` / `_article_markdown_math`；`_science_html._normalized_author_tokens` 已内联。
- §5 仍按审计结论保留，不做合并。

按确定性从高到低排列。

## 1. 完全重复定义的工具函数（同字节）

**`_direct_child_tags` 和 `_class_tokens`** — 两处一字不差：
- `src/paper_fetch/providers/_science_pnas_html.py:230-238`
- `src/paper_fetch/quality/html_availability.py:254-262`

**`_image_magic_type`** — 两处一字不差：
- `src/paper_fetch/providers/_browser_workflow_fetchers.py:183`
- `src/paper_fetch/extraction/html/_assets.py:148`

**`_short_text`** — 两处一字不差：
- `src/paper_fetch/providers/_science_pnas_postprocess.py:42`
- `src/paper_fetch/providers/_science_pnas_html.py:241`

**建议**：上移到 `extraction/html/` 或 `utils.py` 的共享层，让两侧 import。

## 2. 几乎相同但有细微分叉的双胞胎

**`_html_text_snippet` / `_html_title_snippet`**
- `src/paper_fetch/providers/_browser_workflow_fetchers.py:226,237`
- `src/paper_fetch/extraction/html/_assets.py:169,180`

差别只在前者多了 `html_lib.unescape(...)` 解 entity；这种"两份各自演化"的拷贝最危险，应统一到带 `unescape` 的版本。

**`_soup_root` / `_append_text_block`**
- `src/paper_fetch/providers/_science_pnas_postprocess.py:33,48`
- `src/paper_fetch/providers/_science_pnas_html.py:407,415`

逻辑等价但写法不同（局部变量名、循环结构略改）。

## 3. 没有任何调用方的死代码

**`src/paper_fetch/providers/_html_text.py`**（整个文件，9 行）

只导出一个 `extract_doi_from_text`，全局每个调用点都是 `from publisher_identity import extract_doi as extract_doi_from_text`，没有任何模块从 `_html_text` 导入。可整文件删除。

**`browser_workflow.preferred_html_candidate_from_landing_page`**（`src/paper_fetch/providers/browser_workflow.py:132-141`）

自带 docstring `"Backward-compatible provider-name wrapper for legacy imports."`，但 `src/`、`tests/`、`scripts/`、`docs/` 全无导入方；测试都是从 `_science_pnas_profiles` 直接导。可删，并从同文件 `__all__:93` 同步移除。

**`fallback_figure_heading`**（`src/paper_fetch/providers/_article_markdown_common.py:146`，并列在 `__all__:34`）

模块内外均无调用方。`fallback_table_heading` 有调用方，前者是孤儿。

## 4. 价值偏弱的薄壳层

**`src/paper_fetch/providers/_article_markdown.py` 门面**（9 个 re-export，33 行）

实际只有 `elsevier.py` 通过它取 `build_article_structure / write_article_markdown`；math 系列 5 个符号的所有调用方都直接 import 自 `_article_markdown_math`，再 re-export 是无效层。`ArticleStructure` 的 re-export 0 调用。建议要么把 `_article_markdown_math` 的导出从该 facade 移走，要么直接让 `elsevier.py` 直接 import 子模块、删掉 facade。

**`_science_html._normalized_author_tokens`**（`src/paper_fetch/providers/_science_html.py:52-53`）

单行函数，`return normalized_author_tokens(value)`，内部仅 1 处用（line 66）。直接 inline 即可。

## 5. 看似重复但属合理分叉（不建议改）

每个 provider 的 `extract_authors / positive_signals / finalize_extraction / blocking_fallback_signals / _extract_dom_authors`（science / pnas / wiley / springer 各一份）—— 实现差异显著（不同 selector、不同 datalayer），是按 publisher 拆分的策略实现，不应合并。

`install.sh` vs `install-offline.sh` —— 一个走在线源码安装、一个走离线 bundle，目标不同；只有少量 usage block 可抽公共 helper，性价比不高。

`src/paper_fetch/providers/html_assets.py` facade —— 看似纯转发，但其中两个函数注入了默认 `cookie_opener_builder / opener_requester`，是有意的依赖注入层，不算冗余。

---

## 优先级建议

| 段落 | 操作 | 估计代码量 |
| --- | --- | --- |
| §1、§3 | 无脑可删 / 抽共享层 | 约 60–90 行 |
| §2 | 先统一实现再删另一份 | 4 个函数 |
| §4 | 结构清理，留到下一轮 refactor | 1 个 facade + 1 个 wrapper |
| §5 | 不改 | — |

## 验证命令

```bash
grep -rn "^def _direct_child_tags\|^def _class_tokens\|^def _image_magic_type\|^def _short_text\|^def _soup_root\|^def _append_text_block\|^def _html_text_snippet\|^def _html_title_snippet" src/
grep -rn "extract_doi_from_text\|fallback_figure_heading" src/ tests/
grep -rn "preferred_html_candidate_from_landing_page" src/ tests/ scripts/ docs/
```
