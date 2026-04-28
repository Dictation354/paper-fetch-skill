## Working Style
- 默认使用中文。
- 当存在已有的包或者代码块（包括本地的和网络上成熟的包）时，必须使用或者复用，禁止自己用其他方式写代码实现功能。
- 更新代码之后请同步文档。

## Testing
- 默认并行运行测试，复用 `pyproject.toml` 中的 `pytest` 配置，不要在常规 unit / integration 验证中添加 `-n 0`。
- 完整 unit 验证使用 `PYTHONPATH=src python3 -m pytest tests/unit -q`。
- 只有 live 测试、依赖共享外部状态的测试，或明确需要排查顺序/竞态问题时，才使用 `-n 0` 串行运行，并在结果中说明原因。
