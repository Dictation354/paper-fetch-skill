## Working Style
- 默认使用简体中文。
- 优先复用项目已有实现和依赖；不要仅因存在网络上的成熟包而新增依赖。
- 仅当改动影响公开行为、使用方式或项目契约时，同步对应文档。
- 提交时除非明确说明，不要触发 GitHub CI。

## Testing
- 默认并行运行测试，复用 `pyproject.toml` 中的 `pytest` 配置，不要在常规 unit / integration 验证中添加 `-n 0`。
- 完整 unit 验证使用 `PYTHONPATH=src uv run python -m pytest tests/unit -q`。
- 完整 integration 验证使用 `PYTHONPATH=src uv run python -m pytest tests/integration -q`。
- 只有 live 测试、依赖共享外部状态的测试，或明确需要排查顺序/竞态问题时，才使用 `-n 0` 串行运行，并在结果中说明原因。
- 仅当测试命令、依赖、平台矩阵或 CI 契约发生变化时同步 GitHub CI；普通代码修改不改 CI 配置。
- 每次更改版本号准备发布版本时，需要运行上述完整 unit、integration 以及 `uv run python scripts/sync_version.py --check`；发布候选还需按 `docs/deployment.md` 运行相应 build/install 终验。

## macOS Adaptation
- 修改 Unix 安装器、macOS 离线支持矩阵、安全不变量、Camoufox / Playwright 浏览器边界或原生/portable 证据边界时，同步精简后的 `docs/macos-adaptation-contract.toml`、对应测试和相关说明；全平台 release 资产事实继续由 workflow、installer manifest 与 release asset owner 维护，不复制进 macOS 契约。
- 先运行 `python scripts/validate_macos_adaptation.py`。原生 Windows 使用 `scripts/test-macos-contract.ps1`；WSL/Linux 使用 `scripts/test-macos-contract.sh`，且必须使用原生 Linux Python/venv。
- Windows 或 WSL 绿灯不能替代 `.github/workflows/verify.yml` 的原生 `macos-15`/CPython 3.14 gate；release 的 CPython 3.11–3.14 原生矩阵由 `.github/workflows/offline.yml` 覆盖。`/mnt/*` 下的 WSL checkout 只能执行降级的静态契约验证，不能提供 symlink、文件模式、大小写或原生 macOS 证据。

## Project Boundaries
- paper-fetch 只负责已知论文的身份解析、全文获取、验收与报告；不扩展为开放式领域检索、通用研究平台或新的工作流框架。
- 保留并复用现有状态机、五个预设、resolver/provider adapter、CLI/MCP 落盘语义、cache/artifact、统一 acceptance、来源追踪和合法访问约束。
- 单一 provider、执行面或失败路径的问题默认局部修复；除非存在明确的跨 provider 契约或回归证据，不调整全局 cache、retry、fallback、browser 或错误分类策略。
