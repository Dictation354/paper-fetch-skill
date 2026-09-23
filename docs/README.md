# 文档总览

使用入口见 [项目首页](../README.md)。从 6.x 升级先读 [7.0 迁移说明](migration-v7.md)，
公共变更见 [中文更新日志](../CHANGELOG_CN.md) / [English changelog](../CHANGELOG.md)。

## 推荐阅读路径

| 任务 | 入口 |
| --- | --- |
| 获取已知论文、设置输出和资产预设 | [CLI](cli.md) → [provider 能力与行为](providers.md) |
| 安装、配置、MCP 注册、升级或发布 | [部署指南](deployment.md) |
| 准备浏览器、人工认证、排障 | [browser backends](browser-backends.md) → [runtime 边界](browser-runtime.md) |
| 修改提取、组装、渲染 | [架构](architecture/overview.md) → [提取规则](extraction-rules.md) |
| 新增 provider | [开发流程与契约](adding-a-provider.md) |
| 检查探测与验收 | [probe 语义](architecture/probe-semantics.md) → [测试分层与证据](../tests/README.md) |
| 修改 macOS/Unix 安装或浏览器边界 | [适配说明](macos-adaptation-audit.md) → [机器契约](macos-adaptation-contract.toml) |

## 事实来源与维护

- provider 路由和能力由运行时 `ProviderBundle` / catalog 管理，用户语义集中在
  [providers.md](providers.md)；文档不维护第二套规则注册表。
- 提取与渲染约束集中在 [extraction-rules.md](extraction-rules.md)，代码 owner 和
  回归入口由源码与 provider-local 测试管理。PDF 内容只允许现有转换器输出透传。
- 当前可执行样本、来源选择、拒绝/撤回记录在
  [fixture manifest](../tests/fixtures/golden_criteria/manifest.json)，预期在各样本 expected，
  采集事件在 acquisition/provenance。[测试说明](../tests/README.md) 定义证据审计。
- 发布构建、安装验收与平台证据统一见 [发布前检查](deployment.md#release-checklist)。
  协作要求见 [AGENTS.md](../AGENTS.md)；早期大版本变更见 [6.0 迁移](migration-v6.md)。

## 术语表

| 术语 | 含义与详细契约 |
| --- | --- |
| `provider_hint` | resolve 的最佳提示，不承诺该 provider 一定成功 |
| `preferred_providers` | 全文 provider allow-list；Crossref 元数据与路由查询另按契约处理 |
| `source` / `source_trail` | 公开来源 / 实际执行轨迹；见 [输出字段](providers.md#public-output-fields) |
| `modes` | 返回 article、markdown、metadata，与获取策略分离 |
| `strategy` | 抓取与降级选项；五个预设见 [CLI](cli.md) |
| `asset_profile` | `none` / `body` / `all` 的资产范围，`none` 不代表删除远程链接 |
| `render_state` | 资产在正文内联、附录追加或抑制的状态 |
| `download_tier` | 实际下载层级；preview 能否接受由来源诊断与 acceptance 决定 |
| `semantic_losses` | 语义损失和布局降级计数，二者不能混为一谈 |
| `asset_failures` | 独立资产失败及恢复诊断，不直接证明正文受限 |
| `max_tokens` | 渲染预算；`full_text` 尽量保留正文，数值启用硬上限 |
| `download_dir` | 落盘与 cache scope；见 [下载和 Markdown 保存](providers.md#mcp-download-and-markdown-save) |

环境变量、默认值、cache 和资产恢复的完整语义集中在 [providers.md](providers.md)，
安装命令集中在 [deployment.md](deployment.md)，这里不重复维护。
