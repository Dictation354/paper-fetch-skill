## Working Style
- 默认使用简体中文。
- 当存在已有的包或者代码块（包括本地的和网络上成熟的包）时，必须使用或者复用，禁止自己用其他方式写代码实现功能。
- 更新代码之后请同步文档。
- 提交时除非明确说明，不要触发 Github CI。

## Testing
- 默认并行运行测试，复用 `pyproject.toml` 中的 `pytest` 配置，不要在常规 unit / integration 验证中添加 `-n 0`。
- 完整 unit 验证使用 `PYTHONPATH=src uv run python -m pytest tests/unit -q`。
- 只有 live 测试、依赖共享外部状态的测试，或明确需要排查顺序/竞态问题时，才使用 `-n 0` 串行运行，并在结果中说明原因。
- 修改代码和本地测试后，需要同步 Github CI。

## macOS Adaptation
- 修改 Unix 安装器、离线构建/验证、平台目录、公式工具、Camoufox / Playwright 浏览器边界或 release CI 时，同步 `docs/macos-adaptation-contract.toml`、对应测试和相关说明。
- 先运行 `python scripts/validate_macos_adaptation.py`。原生 Windows 使用 `scripts/test-macos-contract.ps1`；WSL/Linux 使用 `scripts/test-macos-contract.sh`，且必须使用原生 Linux Python/venv。
- Windows 或 WSL 绿灯不能替代 `.github/workflows/ci.yml` 的原生 `macos-15`/CPython 3.14 gate；release 的 CPython 3.11–3.14 原生矩阵由 `.github/workflows/offline.yml` 覆盖。`/mnt/*` 下的 WSL checkout 只能执行降级的静态契约验证，不能提供 symlink、文件模式、大小写或原生 macOS 证据。
