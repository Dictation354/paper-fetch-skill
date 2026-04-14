# Science / PNAS FlareSolverr Workflow

这份文档只覆盖 `science` / `pnas` 的 repo-local 工作流。

这两个 provider 当前不走通用“装完包就能用”的路径，而是依赖当前仓库里的 `vendor/flaresolverr/`、本地 Playwright Chromium，以及一组显式限速变量。

## 范围与边界

- `science` / `pnas` 是公开 provider 名字：`provider_hint`、`preferred_providers`、最终 `source` 都可能直接出现它们。
- metadata 仍由 Crossref 提供。
- 正文链路是 `FlareSolverr HTML first -> Playwright PDF fallback -> metadata-only fallback`。
- `source` 固定返回 `science` 或 `pnas`；HTML 成功还是 PDF fallback 成功，只放在 `source_trail`。
- `asset_profile=body|all` 当前会降级成 text-only，不阻塞正文成功。
- 这条链路只保证在当前仓库 checkout 中运行。脱离仓库的 wheel / sdist 环境会明确报缺少 repo-local 资源。
- 使用目标站点时的 ToS、robots、授权或合规风险由操作者自己承担。

## 必要环境变量

以下变量对 `science` / `pnas` 生效：

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

- `FLARESOLVERR_ENV_FILE` 必填，不会自动猜 preset。
- 三条限速变量也必填；未配置时 provider 直接拒绝运行。
- 默认限速账本写到用户数据目录下的 `science_pnas_rate_limits.json`，只影响 `science` / `pnas`。

## 一次性准备

推荐直接使用仓库脚本：

```bash
./install-formula-tools.sh
```

它会：

- 调 `vendor/flaresolverr/setup_flaresolverr_source.sh`
- 调 `python3 -m playwright install chromium`
- 对 headless preset 检查 `Xvfb`

如果你只想单独准备 Science / PNAS 依赖，也可以手动执行：

```bash
bash ./vendor/flaresolverr/setup_flaresolverr_source.sh
python3 -m playwright install chromium
```

headless preset 依赖 `Xvfb`。在 Debian / Ubuntu 上通常是：

```bash
sudo apt-get update
sudo apt-get install -y xvfb
```

## 选择 preset

仓库里带了两份 preset：

- `vendor/flaresolverr/.env.flaresolverr-source-headless`
- `vendor/flaresolverr/.env.flaresolverr-source-wslg`

建议：

- 普通 Linux 桌面或服务器优先用 `headless`
- 需要可见浏览器窗口和交互调试时用 `wslg`

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

如果你想直接探活控制端口，也可以用：

```bash
curl --noproxy '*' -fsS -X POST http://127.0.0.1:8191/v1 \
  -H 'Content-Type: application/json' \
  -d '{"cmd":"sessions.list"}'
```

## 手动 smoke

Science HTML 成功样例：

```bash
PYTHONPATH=src python3 -m paper_fetch.cli --query "10.1126/science.ady3136"
```

PNAS PDF fallback 样例：

```bash
PYTHONPATH=src python3 -m paper_fetch.cli --query "10.1073/pnas.81.23.7500"
```

也可以跑仓库里的 live smoke：

```bash
PAPER_FETCH_RUN_LIVE=1 \
FLARESOLVERR_ENV_FILE="$PWD/vendor/flaresolverr/.env.flaresolverr-source-headless" \
FLARESOLVERR_MIN_INTERVAL_SECONDS=20 \
FLARESOLVERR_MAX_REQUESTS_PER_HOUR=30 \
FLARESOLVERR_MAX_REQUESTS_PER_DAY=200 \
PYTHONPATH=src python3 -m unittest tests.live.test_live_science_pnas -q
```

## 常见失败

- `not_configured`: 通常是 `FLARESOLVERR_ENV_FILE` 没设、preset 文件不存在、repo-local `vendor/flaresolverr/` 缺失，或本地服务没启动。
- `rate_limited`: 命中了本地限速账本。
- HTML 失败但 provider 仍成功：这是正常的 `HTML -> PDF fallback` 路径，结果会在 `source_trail` 里体现。
- `asset_profile=body|all` 仍没有图：这是当前实现约束，`science` / `pnas` v1 只承诺正文 markdown。

更底层的 vendor 参考资料保留在 [`vendor/flaresolverr/`](../vendor/flaresolverr/)。
