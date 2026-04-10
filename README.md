# Paper Fetch Skill 文档

## 架构收口状态

当前分支已经完成 `core library + CLI + MCP + thin skill` 的架构收口。本轮的目标不再是继续做 `scripts/ -> src/` 迁移，而是把已经落地的结构通过文档、测试和 CI 固化下来。

当前收口基线：

- `src/paper_fetch/` 是唯一的运行时代码入口
- `paper-fetch` 与 `paper-fetch-mcp` 是稳定的包入口
- `skills/paper-fetch-skill/SKILL.md` 是静态、MCP-first 的 thin skill
- 本地默认验收基线是 `python3 -m unittest discover -s tests -q`、CLI `--help` smoke、以及 MCP stdio integration smoke
- `.github/workflows/ci.yml` 复用同一套离线验收基线，不依赖外部 API key 或 live publisher 稳定性

后续工作重点是稳定性和边角 case，而不是继续做机械式目录搬迁。像 `references/` 资源归位、`outputs.py`、`formula/backends.py` 这类调整都属于后续 refinement。

## 当前定位

这个仓库当前采用并已经跑通 `core library + CLI + MCP + thin skill` 结构：

- `src/paper_fetch/` 提供可复用的抓取逻辑、模型和 provider 适配
- `paper-fetch` 是给人类、CI 和终端 smoke test 用的稳定 CLI
- `paper-fetch-mcp` 是给 agent runtime 用的 stdio MCP server
- `skills/paper-fetch-skill/SKILL.md` 是静态、MCP-first 的 thin skill

当前推荐的 agent 工作流是：

1. 先用 `resolve_paper(query)` 做 DOI / URL / 标题归一化与消歧
2. 再用 `fetch_paper(query, modes, strategy, include_refs, max_tokens)` 取正文或元数据
3. 只有在当前 runtime 没接 MCP 时，才回退到 CLI `paper-fetch --query ...`

## CLI 主入口

```bash
paper-fetch --query "<DOI | URL | 题名>"
```

默认行为：

- 默认 `stdout` 输出 AI-friendly Markdown
- 默认不落盘，不产生临时文件；但 Wiley 若官方 TDM 返回 PDF / binary，默认会落到 `live-downloads/`
- 加上 `--save-markdown` 可在任何 provider 成功取到全文时，把渲染后的 AI Markdown 另存一份到 `--output-dir`（默认 `live-downloads/`）
- 题名或 URL 解析歧义时，非零退出并在 `stderr` 输出候选 JSON
- 优先官方 API / XML；Wiley PDF 会优先尝试内存提取正文；官方路径不够用时再走 HTML fallback，最后退到 Crossref metadata-only

常用参数：

- `--format markdown|json|both`
- `--output -|<path>`
- `--output-dir <dir>`
- `--no-download`
- `--save-markdown`
- `--include-refs none|top10|all`
- `--max-tokens 8000`
- `--no-html-fallback`

输出合同：

- `--format markdown`: `stdout` 输出 Markdown
- `--format json`: `stdout` 输出 `ArticleModel` JSON
- `--format both`: `stdout` 输出 `{"article": ..., "markdown": ...}`
- `ArticleModel.quality` 里会包含 `warnings` 和结构化 `source_trail`
- 出错时 `stderr` 始终输出 JSON，格式为 `{"status":"error|ambiguous","reason":"...","candidates":[...]}`

## MCP 入口

当前仓库提供一个 stdio MCP server：

```bash
python3 -m pip install .
paper-fetch-mcp
```

本轮只支持 stdio transport，不提供 HTTP/SSE server。首批工具只有两个：

- `resolve_paper(query)`
- `fetch_paper(query, modes, strategy, include_refs, max_tokens)`

`fetch_paper` 的返回始终是固定 JSON 对象形状，顶层保留 `source`、`warnings`、`source_trail`、`has_fulltext`、`token_estimate` 等 provenance 字段；未请求的 `article` / `markdown` / `metadata` 字段会返回 `null`，不会切换成裸字符串。

这里的 `source` 是开放字符串合同，不是闭合 enum；调用方需要把未知值当成“新增 provenance 类型”而不是错误。

## Skill 安装

### Claude Code

```bash
./scripts/install-claude-skill.sh
```

这个安装脚本只做三件事：

- 检查 `python3`
- 在当前 `python3` 环境里执行 `python3 -m pip install .`
- 把静态 `skills/paper-fetch-skill/SKILL.md` 复制到 `~/.claude/skills/paper-fetch-skill/`

可选参数：

- `--project`: 改为写入当前仓库的 `.claude/skills/`
- `--uninstall`: 删除已安装 skill

### Codex

```bash
./scripts/install-codex-skill.sh
```

Codex 安装器和 Claude 版相同，但会额外生成一个最小 `agents/openai.yaml` shim 到安装后的 skill 目录。

可选参数：

- `--project`: 改为写入当前仓库的 `.codex/skills/`
- `--uninstall`: 删除已安装 skill

补充说明：

- 如果设置了 `CODEX_HOME`，Codex 安装器会写到 `$CODEX_HOME/skills/`
- 这两个安装器都不会创建 repo-local `.venv`
- 这两个安装器都不会复制 `.env.example`
- 这两个安装器都不会自动改写 Claude/Codex 的 MCP 配置

### 升级规则

- 仓库代码升级后，请重新运行对应 installer，把新版本包重新装进当前 Python 环境
- skill 已改成静态文件，repo 移动本身不需要重新渲染 skill
- 如果当前 Python 环境不可写，installer 会失败并提示先激活可写虚拟环境，或改用 `./scripts/dev-bootstrap.sh`

## 开发者 Bootstrap

如果你想要一个 repo-local 开发环境，而不是直接把包装进当前 Python 环境，使用：

```bash
./scripts/dev-bootstrap.sh
```

默认行为：

- 创建或复用 `./.venv/`
- 安装 `requirements.txt`
- 以 editable 方式安装当前仓库
- 若缺少 `.env`，从 `.env.example` 复制一份模板
- 运行 `install-formula-tools.sh`

可选参数：

- `--system`: 改为安装到当前 `python3` 环境
- `--no-node`: 跳过 `mathml-to-latex` 的 Node fallback
- `--skip-env-file`: 不复制 `.env.example`

## 手动接入 MCP

安装脚本不会自动修改 Claude/Codex 的运行时配置。要启用 MCP：

1. 先在目标 runtime 实际会使用的 Python 环境里运行对应 installer，确保 `paper-fetch-mcp` 可执行
2. 在 Claude 或 Codex 的 MCP 配置里新增一个 stdio server，命令指向 `paper-fetch-mcp`
3. 重启客户端后，优先通过 `resolve_paper` / `fetch_paper` 调用这个工具

如果你的 runtime 不能直接找到 `paper-fetch-mcp`，也可以显式注册：

```bash
python3 -m paper_fetch.mcp.server
```

具体配置文件格式取决于 Claude/Codex 版本，本仓库不自动写入用户配置。

## 配置加载顺序

运行时配置按以下优先级加载：

1. 进程环境变量
2. `PAPER_FETCH_ENV_FILE`
3. `~/.config/paper-fetch/.env`
4. 仓库根目录 `.env`

常用变量：

- `PAPER_FETCH_SKILL_USER_AGENT`
- `CROSSREF_MAILTO`
- 出版商对应的 API key / token
- `PAPER_FETCH_DOWNLOAD_DIR`

详细变量说明见 [docs/providers.md](docs/providers.md)。

## 处理流程

`paper-fetch` / `paper-fetch-mcp` 的主链路是：

1. `src/paper_fetch/resolve/query.py` 统一解析输入
2. 有 DOI 时优先尝试官方 metadata
3. 优先尝试官方全文 raw payload
4. Elsevier / Springer XML 直接转成统一 `ArticleModel`
5. Wiley 如果官方 TDM 返回 PDF / binary，会先尝试用 PyMuPDF 从内存提取正文；是否落盘由 `--no-download` 控制
6. Wiley PDF 提取失败，或其他 provider 官方路径失败时，尝试 `src/paper_fetch/providers/html_generic.py`
7. HTML 也不够好时，退到 Crossref metadata-only

## 当前支持

官方优先 provider：

- `Elsevier`
- `Springer`
- `Wiley`

统一 metadata / fallback：

- `Crossref`

HTML fallback：

- 使用 `trafilatura` 提取正文
- 使用 `citation_*` / `dc.*` meta 提取 DOI、标题、作者、期刊、日期
- 过滤 cookie、sign in、subscribe、navigation 类噪音
- 对 CJK-heavy 正文和带 DOI 的 short communication / editorial 使用自适应正文阈值，不再硬卡单一 800 字符门槛

Wiley 特殊行为：

- Wiley 官方 metadata endpoint 当前未实现，元数据仍走 Crossref
- Wiley 官方 TDM 当前仍以 PDF / binary 为主
- `paper-fetch` 会优先尝试从 Wiley PDF 中直接提取正文给 agent 使用
- `--no-download` 只关闭落盘副作用，不会关闭 PDF 正文提取
- 未显式指定 `--output-dir` 且未开启 `--no-download` 时，Wiley PDF 默认保存到当前工作目录下的 `live-downloads/`

### 并行调用建议

- 同一篇论文不要在同一会话里高并发重复抓取
- 更稳的做法是先抓一次，再复用返回的 Markdown / JSON
- 如果你自己在外面包线程池或 worker 池，不要共享同一个 `HttpTransport` 实例；它的进程内缓存不是线程安全的

## 本地验证

如果你只是想直接验证当前收口基线：

```bash
python3 -m pip install .
python3 -m unittest discover -s tests -q
paper-fetch --query "<DOI | URL | 题名>"
paper-fetch-mcp
```

如果你要做 repo-local 开发，则先跑：

```bash
./scripts/dev-bootstrap.sh
```

## Live Smoke Tests

仓库内提供一个 opt-in 的真实出版商 smoke test：

```bash
PYTHONPATH=src python -m unittest discover -s tests -q
PAPER_FETCH_RUN_LIVE=1 PYTHONPATH=src python -m unittest tests.test_live_publishers -q
```

说明：

- 默认离线测试不会真的访问外网；`tests/test_live_publishers.py` 会自动跳过
- 只有在显式设置 `PAPER_FETCH_RUN_LIVE=1`，并且环境变量或 `.env` 里填了对应 publisher 的 key / token 时，才会真正发起真实请求
- 当前 live smoke 样本按 `2026-04-10` 实测通过：
  - Elsevier DOI `10.1016/j.rse.2025.114648`
  - Springer DOI `10.1186/1471-2105-11-421`
  - Wiley DOI `10.1002/ece3.9361`
  - Elsevier URL `https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525`
  - 短正文 HTML fallback `https://www.nature.com/articles/sj.bdj.2017.900`

## 主要模块

- `src/paper_fetch/cli.py`: CLI 主入口与输出投影
- `src/paper_fetch/service.py`: fetch orchestration 与 `FetchEnvelope` 契约
- `src/paper_fetch/resolve/query.py`: DOI / URL / 题名统一解析
- `src/paper_fetch/models.py`: 统一内部模型与 AI Markdown / JSON 序列化
- `src/paper_fetch/providers/html_generic.py`: HTML fallback provider
- `src/paper_fetch/providers/crossref.py`: Crossref metadata 与题名候选
- `src/paper_fetch/providers/elsevier.py`: Elsevier metadata / raw fulltext / XML 适配
- `src/paper_fetch/providers/springer.py`: Springer metadata / raw fulltext / XML 适配
- `src/paper_fetch/providers/wiley.py`: Wiley raw fulltext、PDF 提取与 PDF-aware fallback
- `src/paper_fetch/providers/_article_markdown.py`: XML 结构解析与 provider Markdown 渲染
- `src/paper_fetch/publisher_identity.py`: DOI 归一化与 provider 推断
- `src/paper_fetch/providers/registry.py`: provider client registry

## 推荐回归命令

```bash
PYTHONPATH=src python -m unittest \
  tests.test_mcp \
  tests.test_mcp_integration \
  tests.test_config \
  tests.test_elsevier_markdown \
  tests.test_springer_markdown \
  tests.test_formula_conversion \
  tests.test_publisher_identity \
  tests.test_resolve_query \
  tests.test_html_generic \
  tests.test_paper_fetch \
  tests.test_skill_template
```

## 已知边界

- Wiley 官方 TDM 在当前流程里仍以 PDF / binary 为主；运行时会尝试 PDF 文本抽取，但保真度通常不如 XML
- HTML fallback 更偏“读正文给 agent”，不是高保真网页归档
- 复杂表格、公式和少数 publisher-specific 结构，仍以 XML 专用链路为最佳
