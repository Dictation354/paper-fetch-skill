# 文档总览

本文档集描述当前产品功能、使用方式和开发契约。使用入口见 [项目首页](../README.md)，
版本变更见 [中文更新日志](../CHANGELOG_CN.md) / [English changelog](../CHANGELOG.md)。

## 推荐阅读路径

| 任务 | 入口 |
| --- | --- |
| 获取已知论文、设置输出和资产预设 | [CLI](cli.md) → [provider 能力与行为](providers.md) |
| 安装、配置、MCP 注册、升级或发布 | [部署指南](deployment.md) |
| 准备浏览器、人工认证、排障 | [browser backends](browser-backends.md) → [runtime 边界](browser-runtime.md) |
| 修改提取、组装、渲染 | [架构](architecture/overview.md) → [提取规则](extraction-rules.md) |
| 新增 provider | [开发流程与契约](adding-a-provider.md) |
| 检查探测与验收 | [probe 语义](architecture/probe-semantics.md) → [测试分层与证据](../tests/README.md) |
| 修改 macOS/Unix 安装或浏览器边界 | [适配说明](deployment.md#macos-适配与证据边界) → [机器契约](macos-adaptation-contract.toml) |

## 文档职责与事实来源

- provider 路由和能力由运行时 `ProviderBundle` / catalog 管理，用户语义集中在
  [providers.md](providers.md)；文档不维护第二套规则注册表。
- 提取与渲染约束集中在 [extraction-rules.md](extraction-rules.md)，代码 owner 和
  回归入口由源码与 provider-local 测试管理。[PDF 内容](extraction-rules.md#rule-pdf-conversion-boundary)只允许现有转换器输出透传。
- 测试命令与台账维护集中在 [测试说明](../tests/README.md)；
  [fixture 约定](../tests/fixtures/README.md)定义来源和资产证据规则，
  [fixture manifest](../tests/fixtures/golden_criteria/manifest.json)记录当前可执行样本与来源选择。
- 发布构建、安装验收与平台证据统一见 [发布前检查](deployment.md#release-checklist)。
  协作要求见 [AGENTS.md](../AGENTS.md)。
- CLI 参数以 `paper-fetch <command> --help` 与 [cli.py](../src/paper_fetch/cli.py) 为准，
  MCP 入参与返回值以 [schemas.py](../src/paper_fetch/mcp/schemas.py)、tool adapter 和契约测试为准。
- 安装后的 [skill bundle](../skills/paper-fetch-skill/SKILL.md) 必须自包含，因此其
  预设、环境与验收摘要保留必要重复；不能改成依赖未随包安装的 `docs/` 链接。
- 字段含义、默认值、cache 与资产语义在 [providers.md](providers.md) 维护，
  来源与质量字段见其[公开输出字段](providers.md#public-output-fields)。
- 当前契约放在主题文档，版本沿革放在中英文更新日志；fixture 中的论文 Markdown 和采集记录是测试证据，不能按工作说明清理。
