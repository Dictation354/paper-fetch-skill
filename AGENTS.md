## Working Style
- 默认使用简体中文。
- 优先复用项目已有实现和依赖；不要仅因存在网络上的成熟包而新增依赖。
- 仅当改动影响公开行为、使用方式或项目契约时，同步对应文档。
- 提交时除非明确说明，不要触发 GitHub CI。

## Local Environment
- 本地开发环境位于仓库根目录 `.venv/`，由 conda 管理；使用 Python 3.14，当前为 3.14.10。`.venv/conda-meta/pinned` 中保持 `python 3.14.*` 约束。
- 激活使用 `conda activate "$PWD/.venv"`；也可直接调用 `.venv/bin/python`。不要使用 conda base 或 PATH 中的其他 Python 执行项目命令。
- 本地环境的创建、重建与 Python 版本管理使用 conda；不要使用 `uv run`、`uv sync` 或 `uv venv` 接管 `.venv`。`uv pip` 安装依赖时必须显式指定 `--python .venv/bin/python`。
- 开发依赖包含 `dev` 和 `full`，按现有 `uv.lock` 恢复；项目使用可编辑安装：

```bash
uv export --frozen --extra dev --extra full --no-emit-project \
  --output-file /tmp/paper-fetch-requirements.txt > /dev/null
uv pip install --python .venv/bin/python --require-hashes \
  -r /tmp/paper-fetch-requirements.txt
uv pip install --python .venv/bin/python --no-deps --editable '.[dev,full]'
```

## Testing
- 默认并行运行测试，复用 `pyproject.toml` 中的 `pytest` 配置，不要在常规 unit / integration / golden 验证中添加 `-n 0`。
- 完整 unit 验证使用 `PYTHONPATH=src .venv/bin/python -m pytest tests/unit -q`。
- 完整 integration 验证使用 `PYTHONPATH=src .venv/bin/python -m pytest tests/integration -q`。
- 完整 golden 验证使用 `PYTHONPATH=src .venv/bin/python -m pytest tests/golden -q`；默认 pytest 和 preflight 只执行 unit＋integration，发布前用 `scripts/dev-preflight.sh --with-golden`。
- unit 仅保留最小片段／contract scenario 和边界 mock；真实进程／浏览器契约归 integration，整篇论文、完整资产和内容回放归 golden。共享 helper 放在 `tests/support/`，不要反向导入测试模块。
- 只有 live 测试、依赖共享外部状态的测试，或明确需要排查顺序/竞态问题时，才使用 `-n 0` 串行运行，并在结果中说明原因。
- 仅当 CI 的执行方式、依赖、平台矩阵或契约发生变化时同步 GitHub CI；普通代码修改和本地 conda 环境调用方式调整不改 CI 配置。
- 每次更改版本号准备发布版本时，需要运行上述完整 unit、integration、golden 以及 `.venv/bin/python scripts/sync_version.py --check`；发布候选还需按 `docs/deployment.md` 运行相应 build/install 终验。

## macOS Adaptation
- 修改 Unix 安装器、macOS 离线支持矩阵、安全不变量、Camoufox / Playwright 浏览器边界或原生/portable 证据边界时，同步精简后的 `docs/macos-adaptation-contract.toml`、对应测试和相关说明；全平台 release 资产事实继续由 workflow、installer manifest 与 release asset owner 维护，不复制进 macOS 契约。
- 先在项目 Python 环境中运行 `python scripts/validate_macos_adaptation.py`（本地 Linux 可直接使用 `.venv/bin/python`）。原生 Windows 使用 `scripts/test-macos-contract.ps1`；WSL/Linux 使用 `scripts/test-macos-contract.sh`，且必须使用原生 Linux Python 环境。
- Windows 或 WSL 绿灯不能替代 `.github/workflows/verify.yml` 的原生 `macos-15`/CPython 3.14 gate；release 的 CPython 3.11–3.14 原生矩阵由 `.github/workflows/offline.yml` 覆盖。`/mnt/*` 下的 WSL checkout 只能执行降级的静态契约验证，不能提供 symlink、文件模式、大小写或原生 macOS 证据。

## Project Boundaries
- paper-fetch 只负责已知论文的身份解析、全文获取、验收与报告；不扩展为开放式领域检索、通用研究平台或新的工作流框架。
- PDF 解析与转换质量不纳入改进、fixture 补齐或验收目标；以现有 `pymupdf4llm` 输出为边界，禁止在其上做任何格式清洗或内容修复，包括 shared/provider/组装/渲染层的标题修复、页眉页脚删除、断行合并、引用分条或重排、公式/OCR/表格修复及占位图修复。已有清洗代码、测试或历史规则不构成例外；完整约束见 `docs/extraction-rules.md#rule-pdf-conversion-boundary`。
- 保留并复用现有状态机、五个预设、resolver/provider adapter、CLI/MCP 落盘语义、cache/artifact、统一 acceptance、来源追踪和合法访问约束。
- 单一 provider、执行面或失败路径的问题默认局部修复；除非存在明确的跨 provider 契约或回归证据，不调整全局 cache、retry、fallback、browser 或错误分类策略。
