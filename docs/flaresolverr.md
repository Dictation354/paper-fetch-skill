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
- `wiley` 的正文链路是 provider 自管的 `FlareSolverr HTML -> Wiley TDM API PDF -> seeded-browser publisher PDF/ePDF -> abstract-only / metadata-only`
- `science` / `pnas` 的正文链路仍是 provider 自管的 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF -> abstract-only / metadata-only`
- `wiley` 的 `WILEY_TDM_CLIENT_TOKEN` 只启用官方 TDM API PDF lane；这条 lane 可以在本地 browser runtime 不可用时单独尝试，但不会下载 HTML 资产
- `wiley` 的 HTML / browser PDF/ePDF 路径与 `science` / `pnas` 共用同一套 provider-owned 浏览器 bootstrap 与 browser-PDF executor，不再保留单独的 Science path harness
- `source` 公开可能是 `wiley_browser`、`science` 或 `pnas`
- `FlareSolverr HTML` 成功路径支持 `asset_profile=body|all` 的正文资产下载；PDF/ePDF fallback 仍是 text-only
- Science / PNAS CMS 图片会优先尝试 full-size/original，普通 HTTP 被 challenge 或返回非图片时可用 Playwright 顶层 image document + canvas 导出保留可视内容；只有尺寸达标的 preview 才作为可接受降级
- 这条链路只保证在当前仓库 checkout 中运行
- 站点 ToS、robots、授权与合规风险由操作者自行承担

## 必填环境变量

FlareSolverr / seeded-browser 路径的最小必填配置：

```bash
export FLARESOLVERR_ENV_FILE="$PWD/vendor/flaresolverr/.env.flaresolverr-source-headless"
export FLARESOLVERR_MIN_INTERVAL_SECONDS=20
export FLARESOLVERR_MAX_REQUESTS_PER_HOUR=30
export FLARESOLVERR_MAX_REQUESTS_PER_DAY=200
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
- 三条限速变量对 browser 路径必填，未配置时 browser provider 直接拒绝运行
- 默认限速账本会同时影响 `wiley` / `science` / `pnas`

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
FLARESOLVERR_MIN_INTERVAL_SECONDS=20 \
FLARESOLVERR_MAX_REQUESTS_PER_HOUR=30 \
FLARESOLVERR_MAX_REQUESTS_PER_DAY=200 \
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

### `rate_limited`

- 命中了本地限速账本
- 需要等待账本窗口恢复，而不是继续重试

### HTML 失败但 provider 最终成功

- 对 `wiley` 来说，这可能是 `FlareSolverr HTML -> Wiley TDM API PDF`，也可能继续进入 seeded-browser publisher PDF/ePDF
- 对 `science` / `pnas` 来说，这可能是 `FlareSolverr HTML -> seeded-browser publisher PDF/ePDF` 的正常路径
- 最终成功与否以结果为准
- 细节看 `source_trail`

### `asset_profile=body|all` 仍没有图或只有 preview

- 先看 `source_trail` 和 `warnings`，区分 `download:*_asset_failures`、`download:*_assets_preview_fallback`、`download:*_assets_preview_accepted` 等轨迹
- `download_tier=preview` 本身只是诊断标签；当 source trail 带 `download:*_assets_preview_accepted` 且资产尺寸达标时，不应直接当作下载失败
- 如果 direct image URL 返回 `403`、`cf-mitigated: challenge` 或 `text/html`，Science / PNAS 会尝试 Playwright canvas fallback；仍失败时才按资产下载问题处理
- PDF/ePDF fallback 仍是 text-only；只有 HTML 成功路径承诺尝试正文资产下载

## 相关文档

- [`providers.md`](providers.md)
- [`deployment.md`](deployment.md)
- [`architecture/target-architecture.md`](architecture/target-architecture.md)
- [`../vendor/flaresolverr/`](../vendor/flaresolverr/)
