# Paper Fetch Skill 可改进项

本文档是当前仓库 backlog 的唯一真理源。架构 rationale 继续放在 `docs/architecture/target-architecture.md`，但后续收口项和剩余观察点只在这里维护。

---

## 仍未处理

当前没有阻塞性开放项，也没有待完成的架构迁移主线。除下列真实论文边角 case 外，本轮非边角 backlog 已完成收口：

- 极端公式块、代码块与 ASCII 表格混排时的 Markdown 保真度
- Wiley PDF 抽取在复杂版式论文上的稳定性
- 少数 publisher 页面在 HTML fallback 下的正文噪音过滤

---

## 本轮已完成

### 文档与资源语义

- ✅ `target-architecture.md` 不再并行维护 follow-on backlog；当前 backlog 只在本文件更新
- ✅ `references/` 明确降级为设计草稿 / 人工参考资料，不再自称运行时 authoritative 数据
- ✅ 当前 routing 真理源已明确回到运行时代码里的保守推断逻辑，而不是 `journal_lists.yaml`
- ✅ benchmark 产物路径从 tracked 的 `references/formula_backend_report.json` 挪到 `.formula-benchmarks/`
- ✅ `scripts/` 已明确保留为安装器与开发/诊断自动化入口，`scripts/__init__.py` 已删除，不再伪装成 Python package

### 运行时行为与安全性

- ✅ `HttpTransport` 的进程内 LRU GET 缓存已加 `threading.RLock` 保护
- ✅ CLI 默认下载目录已改为：`PAPER_FETCH_DOWNLOAD_DIR` -> `XDG_DATA_HOME/paper-fetch/downloads` -> 创建失败时回落 `./live-downloads`
- ✅ `--save-markdown` 与 Wiley raw/binary 落盘已统一走同一套目录解析逻辑

### 依赖与护栏

- ✅ `pyproject.toml` 已区分 runtime 依赖和 `dev` extra
- ✅ 新增 `ruff` 配置与独立 `lint` CI job
- ✅ 新增 `.github/dependabot.yml`，覆盖 `pip`、`npm`、`github-actions`
- ✅ `requirements.txt` 已收敛为开发者便利入口，不再平铺 runtime pins
- ✅ `scripts/dev-bootstrap.sh` 已改为直接安装 `.[dev]`，避免重复安装 runtime 依赖

### 可维护性

- ✅ `_article_markdown.py` 已拆分成共享 helper、公式渲染、Springer、Elsevier、文档装配五层，原模块保留薄 façade 兼容入口
- ✅ Markdown 回归测试继续覆盖 Elsevier / Springer 主路径，拆分后输出行为保持不变
- ✅ façade 兼容入口已有守卫测试，继续暴露 `render_mathml_expression`、`build_article_structure`、`write_article_markdown`

### 既有收口基线

- ✅ 当前分支继续视为 `core library + CLI + MCP + thin skill` 的已实现基线
- ✅ closeout 守卫测试持续阻止 `tests/` 回退到旧的导入 hack
- ✅ CLI `--help` smoke 和 MCP stdio integration smoke 已收编进 integration 验收基线
- ✅ `tests/` 继续按 `unit/ integration/ live/` 分层，根目录 `unittest discover -s tests -q` 保持可用
- ✅ 当前离线验收基线已覆盖 `ruff check .`、`tests/unit`、`tests/integration` 和根目录 `tests/` discover
