# 迁移到 6.0

6.0 是破坏性边界，不提供兼容 facade。

## Provider capability

不要读取 `ProviderSpec.requires_playwright` 或 `requires_browser_runtime`。从 provider 的 `routes` 判断 browser 是否 available、required 或 optional；新增内置 provider 时必须登记到 `paper_fetch.providers` 的显式模块清单，并为每条公开路径声明 route。

不要导入 `build_provider_registry`。使用标准 provider catalog / registry 入口。`RawFulltextPayload` 只接受并公开 typed 字段；原先通过 `metadata` 传递的 route、正文、诊断、资产与 trace 必须写入对应字段。

## MCP

`tools/list` 不再包含 `outputSchema`。调用方应按工具文档发起请求，并从 `CallToolResult.structured_content` 读取既有 `schema_version`、`status`、内容和错误字段。不要依赖已删除的 `paper_fetch.mcp.output_schemas`。

## 开发工具

Markdown quality/review helper 位于 `paper_fetch_devtools`，不随生产 wheel 安装。递归 onboarding coordinator、`onboard_from_manifests.py`、`provider_agent.py`、evidence sidecar 与 geography 专用入口已删除。使用现有 capture、scaffold、snapshot、sync-back、provider governance 和 `bootstrap_review_artifact.py`；最终签核使用 `--finalize --confirmed-final-quality`。

## Release 资产

Stable Release 只公开九个安装包和 checksum；Rolling prerelease 另含 `dependency-manifest.json`。依赖比较之外的构建 evidence 不再是公开下载接口。
