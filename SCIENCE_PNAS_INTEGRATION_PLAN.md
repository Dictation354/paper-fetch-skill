---
status: draft
owner: paper-fetch-skill
source_of_truth: /home/dictation/test
---

# Science / PNAS 接入扩展计划

本计划的**唯一事实来源**是 `/home/dictation/test` 目录下已经端到端验证过的成品：

- [fetch_fulltext.py](/home/dictation/test/fetch_fulltext.py) — 2135 行主抓取流水线
- [MAIN_CHAIN_WORKFLOW.zh-CN.md](/home/dictation/test/MAIN_CHAIN_WORKFLOW.zh-CN.md) — 已验证链路的中文说明
- [FLARESOLVERR_SOURCE_WORKFLOW.md](/home/dictation/test/FLARESOLVERR_SOURCE_WORKFLOW.md) — FlareSolverr 启停流程
- `setup_/start_/run_/stop_flaresolverr_source.sh` + `flaresolverr_source_common.sh`
- `.env.flaresolverr-source-wslg` / `.env.flaresolverr-source-headless`（及 `.example`）

**重要**：`~/test` 仅作为事实来源供比对与抽取，**所有运行时依赖必须复制进本项目**，项目落地后不得在运行期依赖 `~/test` 路径存在。复制策略见下文"依赖内化"一节。

凡本计划描述与 `~/test` 行为冲突，**以 `~/test` 为准**，不得凭推测改写。

## 决策前提（已拍板）

1. **目标期刊**：Science (AAAS) 与 PNAS，作为当前 provider 矩阵的补齐项。
2. **FlareSolverr 是核心依赖**，不再是可选后端。没有 FlareSolverr，该项目对 Science/PNAS 失去意义。
3. **FlareSolverr 走本地源码路线，不走 Docker**。Docker 路线在目标主机已被证明走不通。
4. **ToS 风险由使用者承担**，项目文档需显式告知；默认仍**只对 Science/PNAS provider 启用** FlareSolverr 调用，不改变其它 provider 的行为。
5. **PDF fallback 属于主链路的一部分**，不是附加项——PNAS 的 HTML 路径经常落到摘要页，必须复用 FlareSolverr 解出的 cookies + user-agent 给后续 PDF 抓取加 seed（见 `~/test` 中 `extract_flaresolverr_browser_context_seed`、`fetch_html_with_flaresolverr`）。

## 运行时形态

- FlareSolverr 由 `~/test` 的 `setup_flaresolverr_source.sh` 在**本机**检出官方上游源码至 `.work/FlareSolverr`，并创建 `.venv-flaresolverr` 虚拟环境、下载含内置 Chrome 的 `.flaresolverr` 发布包。
- 默认 preset 为 `.env.flaresolverr-source-headless`（`HEADLESS=true + Xvfb`）；在当前 WSLg 主机上**实际验证可用**的 preset 是 `.env.flaresolverr-source-wslg`（`HEADLESS=false`，复用 WSLg 显示环境）。本项目的集成层**不得**假设 headless preset 在所有主机都能跑通，必须让用户显式传 preset 路径。
- 服务监听地址固定为 `http://127.0.0.1:8191/v1`。健康检查必须**绕过 HTTP 代理**（参考 `~/test` 的 `curl --noproxy '*'` 做法），否则在有本地代理的机器上会误报不可用。
- 后台启动必须通过 `setsid` 进入独立 session；`HEADLESS=false` 时通过 `script` 保持 PTY 挂接——这两点是 `~/test` 已验证稳定的前提，不要改成 `nohup ... &`。

## 仓库改动清单

### 1. 新增模块（`src/paper_fetch/providers/`）

- `_flaresolverr.py` — FlareSolverr HTTP 客户端
  - 从 [fetch_fulltext.py](/home/dictation/test/fetch_fulltext.py) 抽出：`post_to_flaresolverr`、`fetch_html_with_flaresolverr`、`extract_flaresolverr_browser_context_seed`、`normalize_browser_cookies_for_playwright`、`redact_flaresolverr_response_payload`、`save_flaresolverr_failure_artifacts`、`build_local_service_session`。
  - 保留原脚本的错误分类（`flaresolverr_timeout` / `flaresolverr_transport_error` / `invalid_flaresolverr_response` / `flaresolverr_session_create_failed`），上层依赖这些 kind 决定是否重试。
  - 不得自行重写 challenge 处理逻辑；按原脚本的 session 生命周期（创建 session → 发 request → 复用 cookies → 结束时释放）严格照搬。
- `science.py` — Science/AAAS provider
  - 复用 `~/test` 中 `infer_publisher` 对 `science.org` / `www.science.org` 的判定。
  - landing 候选：`["https://www.science.org", "https://science.org"]`，构造规则见 `build_html_candidates` / `build_pdf_candidates`。
- `pnas.py` — PNAS provider
  - landing 候选：`["https://www.pnas.org", "https://pnas.org"]`。
  - 强制启用 PDF fallback（PNAS HTML 路径常命中摘要页，`looks_like_abstract_redirect` 命中后必须走 PDF 分支）。

### 2. HTML → Markdown 管线

- **不**照搬 `~/test` 自带的 `html_to_markdown` / `render_html_blocks` / `select_best_container`；而是让 Science/PNAS provider 把 FlareSolverr 返回的 HTML 交给现有 [_article_markdown.py](src/paper_fetch/providers/_article_markdown.py) 与 [_article_markdown_common.py](src/paper_fetch/providers/_article_markdown_common.py) 的通用管线。
- 但是 `select_best_container` 中 **Science/PNAS 专用的容器打分与清洗规则**（`score_container` / `should_drop_node` / `clean_container` 在 publisher 为 `"science"` / `"pnas"` 分支的逻辑）必须保留，作为规则补丁合入 [html_noise.py](src/paper_fetch/providers/html_noise.py) 或新建一个 `html_aaas.py`——以能跑出和 `~/test` 等价的 Markdown 结果为准，发现偏差就回退照搬。
- `markdown_looks_like_fulltext` 的质量阈值必须保留，作为"是否需要走 PDF fallback"的触发条件之一。

### 3. PDF fallback 通道

- 新增 `src/paper_fetch/providers/_pdf_fallback.py`，承担：
  - 接收 `_flaresolverr.py` 产出的 `browser_cookies` + `user_agent` seed。
  - 调用 Playwright（已在 `requirements.txt` 中？需验证；若未在，列入依赖变更）以等价于 `~/test` 的方式下载 PDF，并重用 storage_state 的 sanitize 流程（`sanitize_storage_state`）。
  - PDF → text/markdown 转换沿用项目现有能力；若无等价实现，则**先照搬** `~/test` 的转换，不做"顺手重写"。

### 4. Resolve 层

- [resolve/](src/paper_fetch/resolve/) 增加 `science.org` / `pnas.org` 的 landing 解析分支，DOI → landing URL 的推断规则照 `~/test` 的 `build_html_candidates` / `build_pdf_candidates`。
- [publisher_identity.py](src/paper_fetch/publisher_identity.py) 增加对 AAAS 与 PNAS 的识别，触发条件与 `~/test` `infer_publisher` 对齐（包含 domain 匹配与元数据关键字 "aaas" / "proceedings of the national academy of sciences" 兜底）。

### 5. 配置与脚本

- [config.py](src/paper_fetch/config.py) 增加：
  - `FLARESOLVERR_URL`（默认 `http://127.0.0.1:8191/v1`）
  - `FLARESOLVERR_ENV_FILE`（指向**项目内**复制后的 `vendor/flaresolverr/.env.flaresolverr-source-wslg` 或 `-headless`，**必须由用户显式指定**具体 preset）
  - `FLARESOLVERR_SOURCE_DIR`（默认指向项目内 `vendor/flaresolverr/`，不再依赖 `~/test`）
  - 限速参数见后文"限速参数默认值"一节。
- [scripts/](scripts/) 下新增薄封装：`flaresolverr-up` / `flaresolverr-down` / `flaresolverr-status`，内部调用**项目内**复制后的 `vendor/flaresolverr/start_/stop_flaresolverr_source.sh` + 用户指定的 env 文件。
- [install-formula-tools.sh](install-formula-tools.sh) 增加一次性调用 `bash vendor/flaresolverr/setup_flaresolverr_source.sh` 的入口（可通过 flag 关掉），并检测 `xvfb` 包是否存在（仅 headless preset 需要）。

### 5a. 依赖内化（从 `~/test` 复制进项目）

新增目录 `vendor/flaresolverr/`，在集成第一步就把以下文件从 `~/test` **原样复制**进来（不做任何修改，保持可 diff）：

- `setup_flaresolverr_source.sh`
- `start_flaresolverr_source.sh`
- `run_flaresolverr_source.sh`
- `stop_flaresolverr_source.sh`
- `flaresolverr_source_common.sh`
- `.env.flaresolverr-source-wslg` + `.env.flaresolverr-source-wslg.example`
- `.env.flaresolverr-source-headless` + `.env.flaresolverr-source-headless.example`
- `FLARESOLVERR_SOURCE_WORKFLOW.md`
- `MAIN_CHAIN_WORKFLOW.md` + `MAIN_CHAIN_WORKFLOW.zh-CN.md`

运行时产物目录（`.work/FlareSolverr`、`.venv-flaresolverr`、`.flaresolverr`）由 `setup_flaresolverr_source.sh` 在 `vendor/flaresolverr/` 下**就地**生成，不污染项目其它路径。`.gitignore` 中追加这三项。

`fetch_fulltext.py` 里被 `_flaresolverr.py` 抽取的函数也须在复制阶段一起固化到 `vendor/flaresolverr/fetch_fulltext.reference.py`（作为只读参考副本），后续本项目代码若需要比对行为一致性，以该副本为准，而非 `~/test` 原件。

升级策略：`vendor/flaresolverr/UPSTREAM.md` 记录复制时的 `~/test` 原始路径与时间戳；后续若 `~/test` 有新版本，走"先更新 vendor 副本 → 再更新本项目抽取代码"的顺序，严禁让运行时跨越项目边界读取 `~/test`。

### 6. CLI / MCP 暴露

- [cli.py](src/paper_fetch/cli.py) 对 Science/PNAS provider 新增前置检查：调用 FlareSolverr 健康检查（`sessions.list`，`--noproxy` 等价行为），不通过则给出明确的"请先启动 FlareSolverr，参考 `~/test/FLARESOLVERR_SOURCE_WORKFLOW.md`"报错。
- [mcp/](src/paper_fetch/mcp/) 的 agent surface 保持 ToS 警示：默认工具描述里注明 "Requires local FlareSolverr; user assumes ToS risk for Science/PNAS"。

## 测试与验证

- **基线样本**：从 `~/test` 曾经跑通过的 Science / PNAS DOI 中挑 ≥3 篇（1 篇命中 HTML 全文、1 篇需要 PDF fallback、1 篇 Cloudflare 挑战页），作为回归夹具。
- 单元测试照现有 [tests/](tests/) 风格编写：
  - `_flaresolverr.py` 对响应 payload 的解析用假数据覆盖四种错误 kind。
  - Science/PNAS HTML → Markdown 的 fixture 用 `~/test` 真实抓到的 HTML 存档。
- 端到端冒烟：在本机启动 FlareSolverr（WSLg preset）→ 跑 CLI → 比对输出 Markdown 与 `~/test` 同 DOI 的产物，允许空白差异但不允许结构差异。CI 不跑此步骤，标记为 `@pytest.mark.needs_flaresolverr`。

## 文档改动

- 更新 [README.md](README.md)：新增 "Science / PNAS" 小节，注明核心依赖、ToS 风险承担条款、快速启动命令。
- 新增 `docs/flaresolverr.md`（或直接链到 `~/test` 的两份 workflow 文档），但要注明 `~/test` 是事实来源、`.env.*-wslg` 是当前主机唯一已验证 preset。
- [CHANGELOG.md](CHANGELOG.md) 记一条 "Add Science/PNAS providers backed by local FlareSolverr (opt-in core dependency)"。

## 不做的事（避免 scope 膨胀）

- 不替换现有 Elsevier/Springer/Wiley/Nature provider 的 HTTP 路径。
- 不把 FlareSolverr 引入到非 Science/PNAS provider 的默认链路中。
- 不重写 `~/test` 里已经跑通的 challenge/PDF fallback 逻辑；凡需要修改，先在本仓库抽象，再对比 `~/test` 跑出等价结果。
- 不为 Science/PNAS 构造合规 TDM 通道（两家均不提供自助 TDM 接口），也不伪装成官方授权抓取。

## 落地顺序（建议）

1. 把 `~/test/fetch_fulltext.py` 中 FlareSolverr 相关函数抽成 `_flaresolverr.py`，配最小单测。
2. 跑通最小 PNAS provider（单 DOI，HTML 路径）。
3. 接入 PDF fallback，验证 PNAS 摘要页回退。
4. 复制/适配 Science provider。
5. 补 publisher_identity / resolve / cli / mcp 暴露。
6. 接 scripts + install 脚本 + 文档。
7. 回归夹具 + 手动端到端冒烟。

## 已确认决策（此前的开放项）

- **依赖内化**：`~/test` 中 FlareSolverr 工作流的全部运行时文件复制到本项目 `vendor/flaresolverr/`，运行时不再跨越项目边界。具体见 §5a。
- **Playwright 依赖**：需新增。[pyproject.toml](pyproject.toml) 的 `[project].dependencies` 中追加：

  ```
  "playwright>=1.47,<2",
  ```

  同时在 [install-formula-tools.sh](install-formula-tools.sh) 或新建的 `scripts/install-playwright-browsers.sh` 中追加一次性 `python -m playwright install chromium` 步骤（Chromium 二进制不会由 pip 自动下载）。`~/test` 的 PDF fallback 仅使用 Chromium，不需要 firefox / webkit。

## 限速参数默认值

已查询：
- **science.org 的 Terms of Service** 只规定 "不得以超过人类正常浏览速率的频率发起请求"，**未给出具体数值**。
- **science.org/robots.txt** 无 `Crawl-delay` 指令。
- **pnas.org/robots.txt** 同样**无 `Crawl-delay` 指令**，仅列出路径级 `Disallow`。
- 两家均未公开针对订阅用户或 TDM 的官方速率上限。

**结论**：公开资料没有权威数值。三项参数仍设为**必填**配置，启动时若未显式给出，CLI 与 MCP 入口**直接拒绝运行 Science/PNAS provider**，避免静默跑飞烧掉机构 IP。

- `FLARESOLVERR_MIN_INTERVAL_SECONDS`（单 session 两次 challenge 之间的最小间隔，秒）
- `FLARESOLVERR_MAX_REQUESTS_PER_HOUR`（单主机对同一出版商域名的每小时上限）
- `FLARESOLVERR_MAX_REQUESTS_PER_DAY`（单主机对同一出版商域名的每日上限）

### 推荐初始值（需用户 opt-in 后生效）

| 参数 | 推荐值 | 取值理由 |
| --- | --- | --- |
| `FLARESOLVERR_MIN_INTERVAL_SECONDS` | `20` | FlareSolverr challenge + 页面渲染自然耗时 10–20 s，此值接近"人类自然节奏"；低于 10 s 会被 Cloudflare 行为分析标记。**不建议下调**。 |
| `FLARESOLVERR_MAX_REQUESTS_PER_HOUR` | `30` | 对应单研究者"集中阅读一小时"的密度上限（平均 2 分钟 1 篇）；从 Elsevier/Wiley 公开滥用案例反推的保守带，出版商通常不会在该量级触发告警。 |
| `FLARESOLVERR_MAX_REQUESTS_PER_DAY` | `200` | 对应"一个人全天持续工作"的上限，真实研究者难以读完；超过该值就不像人类行为。 |

**这些数值是工程判断，不是权威上限**。仓库代码**不得**把它们作为隐式默认——用户必须在 `config.py` 或环境变量中显式写入后方可生效。CLI 在首次运行时可读取一份示例文件 `vendor/flaresolverr/limits.example.env` 并提示用户复制到项目配置，但复制动作由用户完成。

**使用建议（写入 `README.md` 的 Science/PNAS 小节）**：

- 首次大批量运行前，先用这组值跑 10–20 篇，观察是否被挑战页阻断或封 IP，再决定是否维持。
- 若运行在**机构代理 IP** 后面，把每日上限砍半至 `100`，一旦被封影响的是整个机构。
- 仅个人偶尔单篇抓取的场景可按需放宽小时/日上限，但**最小间隔 20 秒是底线**，不建议下调。

Sources:
- [Terms of Service | Science | AAAS](https://www.science.org/content/page/terms-service)
- [pnas.org robots.txt](https://www.pnas.org/robots.txt)
- [science.org robots.txt](https://www.science.org/robots.txt)
