# 迁移到 6.0

6.0 是破坏性边界，不提供兼容 facade。

## Provider capability

不要读取 `ProviderSpec.requires_playwright` 或 `requires_browser_runtime`。从 provider 的 `routes` 判断 browser 是否 available、required 或 optional；新增内置 provider 时必须登记到 `paper_fetch.providers` 的显式模块清单，并为每条公开路径声明 route。

不要导入 `build_provider_registry`。使用标准 provider catalog / registry 入口。`RawFulltextPayload` 只接受并公开 typed 字段；原先通过 `metadata` 传递的 route、正文、诊断、资产与 trace 必须写入对应字段。

Provider extension 不再声明 `ProviderSpec.client_factory_path`。在模块完成 client 类定义后，把该类或同模块 typed callable 传给 `ProviderBundle.client_factory`；运行 callable 不属于 catalog/MCP 序列化字段。内置 provider 仍由固定模块清单 eager import，单个 factory 构造失败仍由 registry 隔离为失败 client。

`metadata_probe_short_circuit` 已从 `ProviderSpec` 移至 `ProviderBundle`；直接把 callable 传给 bundle。`ProviderBundle.asset_retry` 与 `ProviderBundle.metadata_merge` 已删除：资产重试由现有 provider/asset 下载路径负责，metadata 合并由 workflow 的既有 owner 负责，不再注册 bundle hook。

## MCP

`tools/list` 不再包含 `outputSchema`。调用方应按工具文档发起请求，并从 `CallToolResult.structured_content` 读取既有 `schema_version`、`status`、内容和错误字段。不要依赖已删除的 `paper_fetch.mcp.output_schemas`。

缓存索引和条目不再暴露为动态 MCP resources，也不再发送 `resources/list_changed` 通知。调用方应使用 `list_cached` / `get_cached` 并显式传递相同的 `download_dir` scope；`batch_fetch` 的 `resource_uri` 字段已删除，归档结果改用 `output_artifacts[*].path` 与 `sha256`。静态 `resource://paper-fetch/provider-catalog` 保持不变。

## Provider 开发工具

旧的 source-tree quality/review 包、provider manifest/review、capture/scaffold/snapshot/sync-back 和 drift/benchmark 入口均已删除。新增 provider 直接维护 runtime bundle、provider-local 测试与 golden fixture manifest；见 [`provider-development.md`](provider-development.md)。

## Release 资产

Stable Release 只公开九个安装包和 checksum。Merged dependency manifest 与逐目标构建 evidence 仅在构建期验证，不是公开下载接口。
