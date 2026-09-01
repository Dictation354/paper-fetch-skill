# 迁移到 6.0

6.0 是破坏性边界，不提供兼容 facade。

## Provider capability

不要读取 `ProviderSpec.requires_playwright` 或 `requires_browser_runtime`。从 provider 的 `routes` 判断 browser 是否 available、required 或 optional；新增内置 provider 时必须登记到 `paper_fetch.providers` 的显式模块清单，并为每条公开路径声明 route。

不要导入 `build_provider_registry`。使用标准 provider catalog / registry 入口。`RawFulltextPayload` 只接受并公开 typed 字段；原先通过 `metadata` 传递的 route、正文、诊断、资产与 trace 必须写入对应字段。

## MCP

`tools/list` 不再包含 `outputSchema`。调用方应按工具文档发起请求，并从 `CallToolResult.structured_content` 读取既有 `schema_version`、`status`、内容和错误字段。不要依赖已删除的 `paper_fetch.mcp.output_schemas`。

缓存索引和条目不再暴露为动态 MCP resources，也不再发送 `resources/list_changed` 通知。调用方应使用 `list_cached` / `get_cached` 并显式传递相同的 `download_dir` scope；`batch_fetch` 的 `resource_uri` 字段已删除，归档结果改用 `output_artifacts[*].path` 与 `sha256`。静态 `resource://paper-fetch/provider-catalog` 保持不变。

## Provider 开发工具

旧的 source-tree quality/review 包、provider manifest/review、capture/scaffold/snapshot/sync-back 和 drift/benchmark 入口均已删除。新增 provider 直接维护 runtime bundle、provider-local 测试与 golden fixture manifest；见 [`provider-development.md`](provider-development.md)。

## Release 资产

Stable Release 只公开九个安装包和 checksum；Rolling prerelease 另含 `dependency-manifest.json`。依赖比较之外的构建 evidence 不再是公开下载接口。
