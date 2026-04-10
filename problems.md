# Paper Fetch Skill 可改进项

本文档记录当前仓库里仍值得继续观察的点，以及已经完成并固化的架构收口状态。

---

## 仍未处理

当前没有阻塞性开放项，也没有待完成的架构迁移主线。接下来主要继续观察真实论文里的边角 case：

- 极端公式块、代码块与 ASCII 表格混排时的 Markdown 保真度
- Wiley PDF 抽取在复杂版式论文上的稳定性
- 少数 publisher 页面在 HTML fallback 下的正文噪音过滤

---

## 本轮已完成

### 收口与验收固化

- ✅ 当前分支被明确视为 `core library + CLI + MCP + thin skill` 的已实现基线
- ✅ closeout 守卫测试会持续阻止 `tests/` 回退到 `sys.path` 注入、`spec_from_file_location`、`sys.modules[...]` 注入和裸旧模块导入
- ✅ CLI `--help` smoke 和 MCP stdio integration smoke 被纳入持续验收基线
- ✅ 最小 CI 会跑离线 `unittest`、CLI smoke 和 MCP smoke，不依赖外部 API key 或网络稳定性

### Thin Skill 与安装流

- ✅ 新增静态 skill 源文件：`skills/paper-fetch-skill/SKILL.md`
- ✅ skill 改为 MCP-first，默认引导使用 `resolve_paper` / `fetch_paper`，CLI 只作 fallback
- ✅ 新增 `scripts/install-claude-skill.sh` 与 `scripts/install-codex-skill.sh`
- ✅ 新增 `scripts/dev-bootstrap.sh`，把 repo-local `.venv`、`.env.example`、公式后端安装收回开发者工作流
- ✅ 删除根目录旧 installer、模板化 `SKILL.md` 渲染链路，以及 repo 内的 `agents/openai.yaml`
- ✅ README 改为新职责分层，并补充“如何手动把 `paper-fetch-mcp` 接到 Claude/Codex”
- ✅ `tests/test_skill_template.py` 改为静态 skill 断言和 installer smoke tests

### Core Library / CLI / MCP

- ✅ `src/paper_fetch/service.py` 提供统一 orchestration，CLI 和 MCP 共享同一抓取入口
- ✅ `paper-fetch` 与 `paper-fetch-mcp` 通过 `pyproject.toml` 暴露标准入口
- ✅ `fetch_paper` 返回固定 `FetchEnvelope` 形状，顶层保留 provenance 字段
- ✅ MCP 入口收敛为 `resolve_paper` 和 `fetch_paper`

### 运行时与抓取行为

- ✅ HTML fallback 保留自适应正文阈值，兼顾常规正文与短 commentary / editorial
- ✅ Wiley PDF 落盘副作用与 HTML fallback 已解耦，`--no-download` 只控制写盘
- ✅ `HttpTransport` 继续维持短 TTL 的 LRU GET 缓存，并明确标注非线程安全
- ✅ 配置加载顺序已收敛到：进程环境变量 -> `PAPER_FETCH_ENV_FILE` -> `~/.config/paper-fetch/.env` -> repo-local `.env`
