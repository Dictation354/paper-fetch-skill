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
- 正文链路是 provider 自管的 `HTML first -> PDF fallback -> metadata-only`
- `source` 公开为 `wiley_browser`、`science` 或 `pnas`
- `asset_profile=body|all` 当前会降级成 text-only
- 这条链路只保证在当前仓库 checkout 中运行
- 站点 ToS、robots、授权与合规风险由操作者自行承担

## 必填环境变量

最小必填配置：

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

- `FLARESOLVERR_ENV_FILE` 必填，不会自动猜 preset
- 三条限速变量也必填，未配置时 provider 直接拒绝运行
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
- Playwright Chromium
- `headless` preset 所需的 `Xvfb` 检查

如果你只想手动准备 Wiley / Science / PNAS 依赖：

```bash
bash ./vendor/flaresolverr/setup_flaresolverr_source.sh
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
PYTHONPATH=src python3 -m paper_fetch.cli --query "10.1002/adma.202310123"
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
PYTHONPATH=src python3 -m unittest tests.live.test_live_science_pnas -q
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

- 这是正常的 `HTML -> PDF fallback` 路径
- 最终成功与否以结果为准
- 细节看 `source_trail`

### `asset_profile=body|all` 仍没有图

- 这是当前实现约束
- `wiley` / `science` / `pnas` v1 只承诺正文 Markdown，不承诺资产下载

## 相关文档

- [`providers.md`](providers.md)
- [`deployment.md`](deployment.md)
- [`architecture/target-architecture.md`](architecture/target-architecture.md)
- [`../vendor/flaresolverr/`](../vendor/flaresolverr/)
