# 三层测试

| 层级 | 责任 | 输入与执行边界 |
| --- | --- | --- |
| unit | 局部解析、状态、请求、错误分类、模型和渲染选项 | 最小来源片段或现有 contract scenario；依赖在边界 mock；允许临时文件和必要的线程 |
| integration | provider/service/CLI/MCP、acceptance、cache/artifact、安装器和进程契约 | 受控响应、代表性输入；真实浏览器仅使用已准备 runtime 和本地页面 |
| golden | 完整论文回放、HTML/XML 内容、资产集合、正负样本及来源 | 现有 canonical manifest/catalog/provider adapter；PDF 仅获取、身份、完整性、来源及转换结果透传 |

```bash
PYTHONPATH=src uv run python -m pytest tests/unit -q
PYTHONPATH=src uv run python -m pytest tests/integration -q
PYTHONPATH=src uv run python -m pytest tests/golden -q
```

默认 pytest 和 `scripts/dev-preflight.sh` 执行 unit＋integration。发布前执行
`bash scripts/dev-preflight.sh --with-golden`，并完成部署说明中的 build/install
终验。`--with-golden` 与 `--fast`、`--skip-integration` 冲突即报错。
显式 golden 路径执行全部可执行样本，调试用
路径、nodeid 或 `-k`。不改变默认 worker 数，普通 PR/push CI 不运行 golden。

`tests/support/` 存放 transport、采集记录、服务调用和原文断言 helper，测试模块
不互相导入。原文证据仍由唯一 manifest 管理。golden 的 exact/ reviewed 内容
断言可显式使用 `support/replay.py`：同一 manifest 样本（含论文、路由和固定 adapter
选项）在本轮会话内构建一次，跨 worker 加锁复用；每次调用得到独立深拷贝。
临时结果不会写回 corpus，不跨会话复用。cache/retry/隔离和变更输入的测试直接
调用原构建器，保持独立运行。

全层保留默认网络和用户目录隔离。unit 收集及执行禁止真实进程、真实 PDF 转换、
整篇构建器及 canonical 全文输入读取；标记不能绕过边界。unit 可读取已登记的真实片段和
`_scenarios` 最小场景，并使用转换 mock。具体拦截入口见
[layer_policy.py](support/layer_policy.py)。

原生 macOS 共享 Byparr 门禁通过 `PYTEST_XDIST_AUTO_NUM_WORKERS=2` 限制同时启动的
浏览器及其 GPU 探测进程。浏览器测试使用运行时默认请求预算，隔离子进程复用预置的
Camoufox 依赖缓存；出版社 profile、cookies 与 storage-state 仍在隔离目录中。

## 证据台账

`test-evidence.json` 是内部 v2 台账：每个模块声明默认分类，仅不同契约的测试
使用 `overrides`，新增普通测试无需逐函数登记。收集时直接应用分类；独立的
`test_evidence_ledger_integrity` 检查失效模块、例外和跨模块模板引用。
运行时审计仍覆盖收集期读取、共享 fixture、进程内缓存和跨 worker 构建缓存。
来源读取只证明使用了什么证据，不替代数值、对象归属、顺序和位置断言。

`template_gap` 使用 `template_review={status,scope,evidence_tests,remaining}`：
`mechanism` 证明局部机制，`covered` 关联该范围的离线内容测试，`partial` 列出具体缺口。
仅 `partial` 可有非空 `remaining`；引用必须指向已登记的内容测试，不能由机制或 live 代替。
review 不改变测试 kind 或资产来源。`evidence_cache` 与跨 worker golden cache 必须传播
read set。

来源分类、逐资产证据、签名 URL 回放、拒绝与撤回记录统一见
[Fixture conventions](fixtures/README.md)。测试运行结果保存在仓库外或已忽略的
本地运行目录，不作为当前测试的执行输入。

## 可选本地工具验证

工具应预先准备；以下命令不下载或安装图片工具。Windows 用 PowerShell 设置同名变量，
分别指向 `gswin64c.exe` 与 `vips.exe`：

```bash
PAPER_FETCH_TEST_GHOSTSCRIPT_BIN=/absolute/path/to/gs \
  PAPER_FETCH_TEST_VIPS_BIN=/absolute/path/to/vips \
  PYTHONPATH=src uv run python -m pytest tests/integration/test_offline_optional_tools.py -q
PAPER_FETCH_REVIEW_READER_ROOT=/path/to/LitRoot \
  PYTHONPATH=src uv run python -m pytest tests/integration/test_markdown_math_review.py -q
```

LitRoot 需已安装依赖；公式审阅工具用法见[部署指南](../docs/deployment.md#独立-markdown-公式审阅)。

原生 Darwin arm64 验证需已预置 managed Camoufox 与 fpgen 模型：

```bash
PAPER_FETCH_RUN_NATIVE_CAMOUFOX_TEST=1 \
  PYTHONPATH=src uv run python -m pytest tests/integration/test_camoufox_native_macos.py -q -n 0
```

该测试的临时和持久 context 共用本地 runtime，故串行执行。它复用预置版本、禁用默认扩展、
使用固定 synthetic screen，验证本地启动与原生目录跨重启的 Cookie/localStorage 保留；
不验证默认扩展，也不以 JSON 回放代替持久目录。Windows/WSL 不能替代原生 macOS 证据。

## Live 测试

live 仅在本地具备合法访问条件时显式运行，依赖共享远端状态与浏览器线程边界，使用
`-n 0`。未启用 `PAPER_FETCH_RUN_LIVE=1` 时 publisher/MCP 测试跳过。
pytest 隔离用户目录、profile 和 storage-state，复用已由官方包管理器确认的浏览器依赖缓存；
出版社会话不写入共享 dependency cache。安装与准备见[部署指南](../docs/deployment.md#浏览器安装与准备)。

```bash
PAPER_FETCH_RUN_LIVE=1 PAPER_FETCH_LIVE_ARTIFACT_DIR=failures/live-publishers \
  PYTHONPATH=src uv run python -m pytest \
  tests/live/test_live_publishers.py tests/live/test_live_mcp.py \
  -q -n 0 -o junit_family=legacy --junitxml=failures/live-publishers.xml
```

publisher catalog 和 MCP 抓取用例只检查本地依赖、配置和凭据，直接执行 fetch；显式
CLI `browser-preflight` / MCP `browser_preflight` 保留为独立诊断，不作为抓取前置访问。
报告保留 `preflight=null`、`preflight_seconds=0`；导航、readiness 与资产 timing 来自本次
fetch 的诊断，各资产时间之和不代表整次抓取墙钟时间。MCP 每个用例使用独立持久目录，
失败也保留结果与诊断。

publisher catalog 按默认 `body` 资产策略要求统一 acceptance 为 `complete`，记录每个 provider
终态、墙钟时间、readiness、导航和资产 timing。`live-acceptance.json` 按 runtime catalog
报告已执行和未执行项。只有结构化 challenge/auth/no-access 边界可 skip；解析失败、空壳和
未知错误仍为失败。skip 不代表 catalog 验证完成。严格本地/原图验收使用公开的两个严格参数。
普通 publisher/MCP live 不由 GitHub Actions 触发。

AIP 冷启动专项为每轮创建独立 profile，要求 HTML 路线及完整 acceptance，不能由 PDF 降级通过：

```bash
PAPER_FETCH_RUN_LIVE=1 PAPER_FETCH_RUN_AIP_COLD_STABILITY=1 \
  PAPER_FETCH_LIVE_ARTIFACT_DIR=failures/aip-cold-start \
  PYTHONPATH=src uv run python -m pytest \
  tests/live/test_live_publishers.py::test_aip_cold_start_stability_uses_html_for_five_fresh_profiles \
  -q -n 0
```

IEEE 大型 GIF 专项独立运行，要求正文资产为 full-size、文件有效且由 Markdown 本地引用：

```bash
PAPER_FETCH_RUN_LIVE=1 PAPER_FETCH_RUN_IEEE_BROWSER_LIVE=1 \
  PAPER_FETCH_LIVE_ARTIFACT_DIR=failures/live-ieee-protected \
  PYTHONPATH=src uv run python -m pytest tests/live/test_live_ieee_protected.py \
  -q -n 0 -o junit_family=legacy --junitxml=failures/live-ieee-protected.xml
```

direct 成功接受 `direct_http`；仅在进入 browser recovery 时核对 Camoufox 与恢复 trace。
`asset-hashes.json` 保存目标和正文资产的 hash、size、fetcher、recovery 与 acceptance。
持续 AWS WAF 页面在 readiness 结束后以 `aws_waf_challenge` skip，不能视为成功访问。

补充材料点击专项使用新目录。`PAPER_FETCH_LIVE_STORAGE_STATE_SOURCE` 可指定已有合法状态的根目录，
测试从其中的 `<provider>-camoufox/storage-state.json` 复制 JSON 到隔离目录。
无附件、缓存、skip 和访问阻断不算下载成功：

```bash
PAPER_FETCH_RUN_SUPPLEMENT_CLICK=1 PAPER_FETCH_LIVE_ARTIFACT_DIR=failures/supplement-click \
  PYTHONPATH=src uv run python -m pytest tests/live/test_live_supplement_click.py -q -n 0
```

live 结果保存在已忽略的 `failures/` 或仓库外，不用 `git add -f` 提交，也不作为 fixture。
诊断与上传目录按现有脱敏及 sentinel 检查；长期归档保留 JUnit、`live-acceptance.json`，
IEEE 专项再保留 `asset-hashes.json`。原始全文、图片和页面诊断仅用于对应失败的排查。

## 派生产物重建

Elsevier 已登记样本的派生结果由现有脚本重建：

```bash
PYTHONPATH=src:. uv run python scripts/refresh_elsevier_baselines.py
```

脚本更新派生 Markdown、文章验收及哈希；源采集、资产与失败证据仍保留。
