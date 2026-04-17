---
status: implemented
owner: paper-fetch-skill
source_of_truth: docs/providers.md
---

# Science / PNAS 集成落地记录

这份文档不再是待执行草案，而是当前仓库已落地实现的摘要说明。

当前事实来源以本仓库代码与文档为准：

- [docs/providers.md](docs/providers.md)
- [docs/flaresolverr.md](docs/flaresolverr.md)
- [docs/architecture/target-architecture.md](docs/architecture/target-architecture.md)
- [src/paper_fetch/providers/_science_pnas.py](src/paper_fetch/providers/_science_pnas.py)
- [src/paper_fetch/providers/_pdf_fallback.py](src/paper_fetch/providers/_pdf_fallback.py)
- [tests/provider_benchmark_samples.py](tests/provider_benchmark_samples.py)

## 当前状态

`science`、`pnas`、`wiley` 现在已经统一收敛到同一套 provider-owned 浏览器工作流：

- 共享 `_science_pnas.bootstrap_browser_workflow(...)`
- 共享 `_science_pnas.fetch_seeded_browser_pdf_payload(...)`
- 共享 `_pdf_fallback.fetch_pdf_with_playwright(...)`
- 共享 `_pdf_candidates.extract_pdf_candidate_urls_from_html(...)`

其中：

- `science`
  - `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> metadata-only`
- `pnas`
  - `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> metadata-only`
- `wiley`
  - `FlareSolverr HTML -> Wiley TDM API PDF -> seeded-browser publisher PDF/ePDF -> metadata-only`

`wiley` 只保留自己的 TDM token 探测、TDM API PDF 下载和 Wiley 专属 source trail / warning 语义；不再单独维护另一套 HTML/bootstrap/browser-PDF 实现。

## 已删除的旧冗余

以下旧旁路已经移除，不再是当前架构的一部分：

- `src/paper_fetch/live_science_paths.py`
- `scripts/live_science_path_matrix.py`
- `tests/live/test_live_science_paths.py`
- `tests/unit/test_live_science_paths.py`
- `tests/fixtures/science_path_samples.json`

这意味着现在不再存在：

- Science 专用 live path harness
- 第二套 Science-only PDF 获取逻辑
- 第二套 HTML 中 PDF 候选提取器
- `fetch_pdf_with_playwright(..., publisher=...)` 这类已失效的内部接口

## 基准样本

当前 provider 基准样本统一集中在：

- [tests/provider_benchmark_samples.py](tests/provider_benchmark_samples.py)

固定主样本为：

| Provider | DOI | 年份 | live 主验证 |
| --- | --- | --- | --- |
| `elsevier` | `10.1016/j.rse.2025.114648` | 2025 | 官方 XML/API |
| `springer` | `10.1038/d41586-023-01829-w` | 2023 | direct HTML |
| `science` | `10.1126/science.ady3136` | 2026 | provider HTML |
| `wiley` | `10.1111/cas.16117` | 2024 | live 主套件验证 TDM API lane |
| `pnas` | `10.1073/pnas.2406303121` | 2024 | 当前稳定成功 provider path |

补充说明：

- retained live 主套件里，`wiley` 的主验证固定为官方 TDM API lane。
- `wiley` 的 browser-PDF retained 分支通过额外 live proof 验证，而不是依赖主套件自然触发。
- 所有基准 DOI 都在 2020 年之后。

## 验证结论

当前仓库已经通过这两组基准：

离线回归：

```bash
PYTHONPATH=src python3 -m unittest \
  tests.unit.test_pdf_fallback_helpers \
  tests.unit.test_provider_waterfalls \
  tests.unit.test_science_pnas_provider \
  tests.unit.test_regression_samples -q
```

retained live：

```bash
PAPER_FETCH_RUN_LIVE=1 \
PAPER_FETCH_ENV_FILE=/home/dictation/paper-fetch-skill/.env \
PYTHONPATH=src python3 -m unittest \
  tests.live.test_live_publishers \
  tests.live.test_live_science_pnas \
  tests.live.test_live_mcp -q
```

另外还单独做过 Wiley browser-PDF live proof：

- DOI: `10.1111/cas.16117`
- 禁用 `WILEY_TDM_CLIENT_TOKEN`
- 使用同一套 live bootstrap 强制执行 provider-owned browser-PDF 分支
- 结果满足：
  - `source=wiley_browser`
  - `has_fulltext=True`
  - `source_trail` 包含 `fulltext:wiley_pdf_browser_ok`
  - `source_trail` 包含 `fulltext:wiley_pdf_fallback_ok`

## 运行时要求

当前落地实现的运维要求没有变化：

- `science` / `pnas` / `wiley` browser-PDF 与 `elsevier` browser fallback 依赖 repo-local `vendor/flaresolverr`
- `science` / `pnas` / `wiley` browser-PDF 依赖 Playwright Chromium
- `FLARESOLVERR_ENV_FILE` 与三条本地限速变量必须显式配置
- `WILEY_TDM_CLIENT_TOKEN` 只在 Wiley 官方 TDM API lane 需要；browser-PDF 分支可以在本地 runtime 就绪时独立运行

## 历史说明

早期 Science / PNAS 接入工作参考过外部已验证原型，但该原型不再是当前仓库的事实来源，也不应再被视为运行时依赖。

如果后续实现与本文冲突，以当前仓库中的 provider 代码、tests 与上述三份文档为准。
