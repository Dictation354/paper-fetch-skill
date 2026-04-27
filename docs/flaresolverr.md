# Wiley / Science / PNAS FlareSolverr 工作流

这份文档解决：

- `wiley` / `science` / `pnas` 的 repo-local 运行边界
- 必填变量与 preset 选择
- 一次性准备、启动、检查、停止
- smoke 命令与常见失败排障

这份文档不解决：

- 通用 provider 能力矩阵
- MCP 安装与注册
- 架构分层和 probe 语义

通用运行时说明见 [`providers.md`](providers.md)，安装与注册见 [`deployment.md`](deployment.md)。

## 范围与边界

`wiley` / `science` / `pnas` 当前遵循这些边界：

- 它们是公开 provider 名字，可能出现在 `provider_hint`、`preferred_providers` 中
- metadata 仍由 `crossref` 提供
- `wiley` 的正文链路是 provider 自管的 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> Wiley TDM API PDF -> abstract-only / metadata-only`
- `science` / `pnas` 的正文链路仍是 provider 自管的 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> abstract-only / metadata-only`
- `wiley` 的 `WILEY_TDM_CLIENT_TOKEN` 只启用官方 TDM API PDF lane；这条 lane 会在 browser PDF/ePDF fallback 失败或本地 browser runtime 不可用时继续尝试，但不会下载 HTML 资产
- `wiley` 的 HTML / browser PDF/ePDF 路径与 `science` / `pnas` 共用同一套 provider-owned 浏览器 bootstrap 与 browser-PDF executor，不再保留单独的 Science path harness
- `source` 公开可能是 `wiley_browser`、`science` 或 `pnas`
- `FlareSolverr HTML` 成功路径支持 `asset_profile=body|all` 的正文资产下载；PDF/ePDF fallback 仍是 text-only
- `wiley` / `science` / `pnas` 的正文 figure / table / formula 图片资产下载以 shared Playwright browser context 为主链路；每次 download attempt 创建一次 context/page，多图复用同一个 seeded browser context
- 图片候选仍优先 full-size/original，全部失败后才尝试 preview；preview 也通过同一个 browser context 下载，目标 provider 不再使用 `playwright_canvas_fallback` tier
- 正文图片下载在单次 attempt 内会对 figure page 和图片候选 URL 做缓存，并以固定并发上限 `3` 拉取 payload；文件写入仍按资产原顺序完成
- 当图片 URL 在 Playwright `fetch()` 下返回 Cloudflare challenge HTML，但 FlareSolverr/Selenium 已能显示图片文档时，仓库本地 FlareSolverr patch 会返回 `solution.imagePayload`，下载器只接受这份浏览器导出的 PNG；`imagePayload` 缺失或无效时会记录明确失败原因，不再退回截图裁剪
- 这条链路只保证在当前仓库 checkout 中运行
- 站点 ToS、robots、授权与合规风险由操作者自行承担

## 必填环境变量

FlareSolverr / seeded-browser 路径的最小必填配置：

```bash
export FLARESOLVERR_ENV_FILE="$PWD/vendor/flaresolverr/.env.flaresolverr-source-headless"
```

可选变量：

```bash
export FLARESOLVERR_URL="http://127.0.0.1:8191/v1"
export FLARESOLVERR_SOURCE_DIR="$PWD/vendor/flaresolverr"
```

说明：

- `science` / `pnas` 必须走这组 browser 配置
- `wiley` 的 HTML 与 seeded-browser PDF/ePDF 路径也必须走这组配置；只配置 `WILEY_TDM_CLIENT_TOKEN` 时只能尝试官方 TDM API PDF lane
- `FLARESOLVERR_ENV_FILE` 不会自动猜 preset
- 本地 FlareSolverr 限速变量与账本已移除；browser workflow 不再读取 `FLARESOLVERR_MIN_INTERVAL_SECONDS`、`FLARESOLVERR_MAX_REQUESTS_PER_HOUR` 或 `FLARESOLVERR_MAX_REQUESTS_PER_DAY`

## preset 选择

仓库里当前带了两份 preset：

- `vendor/flaresolverr/.env.flaresolverr-source-headless`
- `vendor/flaresolverr/.env.flaresolverr-source-wslg`

建议：

- 普通 Linux 桌面或服务器优先用 `headless`
- 需要可见浏览器窗口和交互调试时用 `wslg`

## 一次性准备

推荐直接执行：

```bash
./install-formula-tools.sh
```

它会顺手准备：

- `vendor/flaresolverr/` 源码工作流
- `wiley` / `science` / `pnas` 所需的 Playwright Chromium
- `headless` preset 所需的 `Xvfb` 检查

如果你只想手动准备 Wiley / Science / PNAS 依赖：

```bash
bash ./vendor/flaresolverr/setup_flaresolverr_source.sh
```

如果你还要启用 `wiley` / `science` / `pnas` 的 seeded-browser PDF/ePDF fallback，再补：

```bash
python3 -m playwright install chromium
```

`headless` preset 依赖 `Xvfb`。在 Debian / Ubuntu 上通常是：

```bash
sudo apt-get update
sudo apt-get install -y xvfb
```

## 启动 / 检查 / 停止

启动：

```bash
./scripts/flaresolverr-up "$FLARESOLVERR_ENV_FILE"
```

状态检查：

```bash
./scripts/flaresolverr-status "$FLARESOLVERR_ENV_FILE"
```

停止：

```bash
./scripts/flaresolverr-down "$FLARESOLVERR_ENV_FILE"
```

这三个 wrapper 都要求显式传 preset，或者先设置 `FLARESOLVERR_ENV_FILE`。

如果你想直接探活控制端口，也可以：

```bash
curl --noproxy '*' -fsS -X POST http://127.0.0.1:8191/v1 \
  -H 'Content-Type: application/json' \
  -d '{"cmd":"sessions.list"}'
```

## 手动 smoke

Wiley 样例：

```bash
PYTHONPATH=src python3 -m paper_fetch.cli --query "10.1002/adma.202310122"
```

Science HTML 成功样例：

```bash
PYTHONPATH=src python3 -m paper_fetch.cli --query "10.1126/science.ady3136"
```

PNAS PDF fallback 样例：

```bash
PYTHONPATH=src python3 -m paper_fetch.cli --query "10.1073/pnas.81.23.7500"
```

也可以跑 live smoke：

```bash
PAPER_FETCH_RUN_LIVE=1 \
FLARESOLVERR_ENV_FILE="$PWD/vendor/flaresolverr/.env.flaresolverr-source-headless" \
PYTHONPATH=src pytest -n 0 \
  tests/live/test_live_publishers.py::LivePublisherTests::test_wiley_doi_live_fulltext \
  tests/live/test_live_science_pnas.py
```

## 常见失败与排障

### `not_configured`

通常表示：

- `FLARESOLVERR_ENV_FILE` 没设
- preset 文件不存在
- `vendor/flaresolverr/` 缺失
- 本地 FlareSolverr 服务没启动

### HTML 失败但 provider 最终成功

- 对 `wiley` 来说，这可能是 `FlareSolverr HTML -> Wiley TDM API PDF`，也可能继续进入 seeded-browser publisher PDF/ePDF
- 对 `science` / `pnas` 来说，这可能是 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF` 的正常路径
- 最终成功与否以结果为准
- 细节看 `source_trail`

### `asset_profile=body|all` 仍没有图或只有 preview

- 先看 `source_trail` 和 `warnings`，区分 `download:*_asset_failures`、`download:*_assets_preview_fallback`、`download:*_assets_preview_accepted` 等轨迹
- `download_tier=preview` 本身只是诊断标签；当 source trail 带 `download:*_assets_preview_accepted` 且资产尺寸达标时，不应直接当作下载失败
- formula-only preview fallback 不自动算 live review 的 `asset_download_failure`；figure/table preview fallback 仍需要 accepted 轨迹或其它证据才能降噪
- `wiley` / `science` / `pnas` 不再先走普通 HTTP 直连；full-size 与 preview 候选都会通过 seeded Playwright browser context 获取。若刷新 FlareSolverr seed 后仍失败，才按资产下载问题处理
- seeded Playwright 图片获取里的页面内 `fetch()` 带有短超时；如果候选图实际落到 Cloudflare `Just a moment...` 等非图片页面，会快速失败并进入下一候选或刷新 seed 重试，而不是长期卡住整个 live review
- 如果最终仍失败，失败详情会保留在 `article.quality.asset_failures` 和顶层 `quality.asset_failures`：包括 `status`、`content_type`、`title_snippet`、`body_snippet`、以及 asset-level FlareSolverr recovery 的 `recovery_attempts`
- PDF/ePDF fallback 仍是 text-only；只有 HTML 成功路径承诺尝试正文资产下载

## 相关文档

- [`providers.md`](providers.md)
- [`deployment.md`](deployment.md)
- [`architecture/target-architecture.md`](architecture/target-architecture.md)
- [`../vendor/flaresolverr/`](../vendor/flaresolverr/)
