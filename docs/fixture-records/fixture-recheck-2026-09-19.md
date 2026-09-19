# Fixture 再次核查：抓取、转换、组装与落盘

日期：2026-09-19。核查时确认的 **2 项问题现已修复**：PLOS 部分下载时公式图片被错误替换，以及 arXiv 合法复用图片的图号被覆盖。下文保留修复前复现证据，修复后验证见末尾。未修改 fixture 原文、expected 或历史采集结果。

## 修复前已确认问题

### R1 · P1：PLOS 最终落盘将未下载公式替换成另一公式

样本：`10.1371/journal.pcbi.1003118`。使用现有 `original.xml` 和正式采集保存的 7 个公式 PNG，控制下载完成记录后，依次执行 `parse_plos_xml → PlosClient.to_article_model → to_ai_markdown → workflow.rendering.rewrite_markdown_asset_links`。

| 已下载公式数 | provider 输出中的不同公式地址 | 最终落盘中的不同公式地址 | 结果 |
| ---: | ---: | ---: | --- |
| 0 | 7 | 7 | 7 个远程公式地址均保留 |
| 1（e001） | 7 | **1** | **e002–e007 全部错绑为 e001，共 6 处** |
| 2（e001、e002） | 7 | 7 | 其余远程公式地址保留 |
| 7 | 7 | 7 | 7 个不同本地公式地址保留 |

根因：[`image_reference_candidates`](../../src/paper_fetch/models/markdown.py#L156) 将带不同 `id` 查询参数的 URL 同时转换为相同的 `/ploscompbiol/article/file` 路径；[`_local_asset_lookups`](../../src/paper_fetch/workflow/rendering.py#L136) 只索引已有本地文件。当只有一个公式本地化时，共享路径看起来没有歧义，随后 [`rewrite_image`](../../src/paper_fetch/workflow/rendering.py#L273) 把其他公式都绑定到它。

这会改变公式内容。PLOS provider 中已有的对象身份保护在组装阶段有效，但没有覆盖最终文件渲染。现有 `test_plos_asset_identity_assembly.py` 检查到 `to_ai_markdown` 为止，因此无法发现后续的再次错绑。建议优先修复该落盘匹配边界，并用上述 0/1/2/7 场景验证；不要将查询参数承载的对象身份降为端点路径或文件名。

证据边界：部分下载是受控注入的条件；XML 和图片字节来自现有真实 fixture。这证明当前代码在该条件下会错绑，不表示历史那次完整下载已经发生相同错误，也不宣称重新验证了在线可下载性或验收误报。

### R2 · P2：DDPM 合法复用图片本地化后，图片标签被覆盖

样本：`10.48550/arxiv.2006.11239v2`。现有完整 HTML 中：

| 原文对象 | 合法复用关系 | 本地化前图片标签 | 本地化后图片标签 |
| --- | --- | --- | --- |
| `A4.F13` | 与 Figure 1 共用 `cifar10_eps-fixedlarge-mse_20x20.png` | Figure 13 | **Figure 1** |
| `A4.F14` | 与 Figure 6 共用 `cifar10_eps-fixedlarge-mse_20_progressive.jpg` | Figure 14 | **Figure 6** |

根因：[`models.render.rewrite_markdown_asset_links`](../../src/paper_fetch/models/render.py#L448) 按图片地址命中第一个资产记录，[`_asset_image_markdown`](../../src/paper_fetch/models/render.py#L421) 优先采用该资产的 `heading`，覆盖当前出现位置的图片标签。文件渲染层也存在优先使用资产 heading 的逻辑。

本轮确认的是 Markdown 图片标签错误：图片文件和正文图注仍然正确，图片出现次数也没有增加。它影响以图片标签建立图文对应关系的下游使用者，不能表述为又一次下载错图。上轮新增回归比较了图片地址和次数，没有检查每个出现位置的图号，因而仍然通过。

建议保留当前正文出现位置的图号；同一文件可合法属于多个图号，不能按文件地址去重或统一改号。以相同方法核对 GAN、EMO、UniPool、Kubo-Thermalization、ActCam，未复现这一标签变化。

证据边界：复用现有原文和 arXiv 组装 helper，注入源码资产下载完成记录；不重新下载源码压缩包，不将模拟完成记录当作图片字节或线上获取证据。

## 核查与测试范围

- Canonical inventory：151 个可执行整篇样本、19 个 provider，其中 137 个 HTML/XML、14 个 PDF；另有 42 个 manifest-only、6 个 unit-only、3 个 synthetic 条目。manifest-only 不等于没有专项覆盖，也不能算入 canonical 整篇回放数。
- 运行完整 unit、integration、golden，均沿用 `pyproject.toml` 默认并行配置，没有使用 `-n 0`。
- 检查已有回放输出中的图片语法、资产对应关系及重复内容候选，再对上述两项执行跨阶段复现。arXiv 定义／定理重述本来就存在于原文，未把重复文本直接列为缺陷；Annual Reviews、IOP、MDPI 的下载入口有局部覆盖，未把绕开真实入口产生的通用 helper 差异列为产品问题。
- PDF 只验证现有获取、身份、来源和转换结果透传契约，不评估或清洗 `pymupdf4llm` 转换质量。
- 本轮离线执行，不能据此证明所有站点当前可访问，也不能将测试通过扩大为所有模板、失败组合及真实浏览器抓取均无缺陷。

| 验证 | 结果 |
| --- | --- |
| `uv run python scripts/validate_macos_adaptation.py` | 通过静态契约检查 |
| `PYTHONPATH=src uv run python -m pytest tests/unit -q` | **2501 passed**；373 subtests passed |
| `PYTHONPATH=src uv run python -m pytest tests/integration -q` | **136 passed、4 skipped**；2144 subtests passed |
| `PYTHONPATH=src uv run python -m pytest tests/golden -q` | **2854 passed、1 skipped**；34238 subtests passed |
| 本轮额外复现 | 两项缺陷均由断言确认；PLOS 4 种下载完成状态、arXiv 6 篇原文 |

修复前复现命令（脚本保留旧缺陷断言，不用于修复后验收）：

```bash
PYTHONPATH=src:. uv run python .paper-fetch-runs/fixture-recheck-2026-09-19/reproduce.py
```

[机器证据](fixture-recheck-2026-09-19.json)保存输入路径、SHA-256、控制条件和前后结果；[复现脚本与输出](../../.paper-fetch-runs/fixture-recheck-2026-09-19/)保存完整 Markdown、脚本和三层测试日志。没有修改版本、提交或触发 GitHub CI。

## 修复后验证

- R1：PLOS 最终文件渲染使用保留查询参数的完整资产地址匹配；不能唯一对应已下载文件时保留原文远程地址。修复限定于 PLOS，不调整其他 provider 的缓存、下载或回退策略。新增真实 XML 与公式图片字节的 golden 回归，覆盖 0/1/2/7 个公式下载成功的条件，并扩展最小 unit contract 到最终落盘阶段。
- R2：模型组装和最终文件渲染均优先保留当前图片出现位置的图号，只有缺少有效图号时才回退资产标题。DDPM 与其他 5 篇真实 arXiv 回放同时比较图片地址、出现次数和图片标签。
- 完整并行 unit：**2504 passed**，373 subtests passed；integration：**136 passed、4 skipped**，2144 subtests passed；golden：**2858 passed、1 skipped**，34238 subtests passed。静态 macOS 契约验证、此次代码的 Ruff 和 `git diff --check` 通过。
- Mypy 仍有 5 项工作区既有错误，位于 `models/builders.py` 和 `workflow/fulltext.py`；此次修改的两个渲染模块没有类型错误。
- 人工核验产物位于被 Git 忽略的 [`papers/`](../../papers/README.md)，包含重新转换的 Markdown、相对引用的正文图片、历史输入版本、不能转换的输入诊断和未能本地化的图片清单。离线源回放与本轮在线补取图片的证据分别保留；PDF 内容未作清洗。
