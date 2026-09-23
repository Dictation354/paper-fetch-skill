# 三层测试

| 层级 | 责任 | 输入与执行边界 |
| --- | --- | --- |
| unit | 局部解析、状态、请求、错误分类、模型和渲染选项 | 最小来源片段或现有 contract scenario；依赖在边界 mock；允许临时文件和必要的线程 |
| integration | provider/service/CLI/MCP、acceptance、cache/artifact、安装器和进程契约 | 受控响应、代表性输入；真实浏览器仅使用已准备 runtime 和本地页面 |
| golden | 完整论文回放、HTML/XML 内容、资产集合、正负样本及来源 | 现有 canonical manifest/catalog/provider adapter；PDF 仅获取、身份、完整性、来源及转换结果透传 |

```bash
PYTHONPATH=src uv run python -m pytest tests/unit -q
PYTHONPATH=src uv run python -m pytest tests/integration -q
PYTHONPATH=src uv run python -m pytest tests/golden -q
```

默认 pytest 和 `scripts/dev-preflight.sh` 执行 unit＋integration。发布前执行
`bash scripts/dev-preflight.sh --with-golden`，并完成部署说明中的 build/install
终验。`--with-golden` 与 `--fast`、`--skip-integration` 冲突即报错。
不再使用 full/shard 环境开关；显式 golden 路径执行全部可执行样本，调试用
路径、nodeid 或 `-k`。不改变默认 worker 数，普通 PR/push CI 不运行 golden。

`tests/support/` 存放 transport、采集记录、服务调用和原文断言 helper，测试模块
不互相导入。原文证据仍由唯一 manifest 管理。golden 的 exact/ reviewed 内容
断言可显式使用 `support/replay.py`：同一 manifest 样本（含论文、路由和固定 adapter
选项）在本轮会话内构建一次，跨 worker 加锁复用；每次调用得到独立深拷贝。
临时结果不会写回 corpus，不跨会话复用。cache/retry/隔离和变更输入的测试直接
调用原构建器，保持独立运行。

全层保留默认网络和用户目录隔离。unit 收集及执行禁止真实进程（包含 Python、
shell、fork）、真实 PDF 转换后端、整篇构建器及 canonical 全文输入读取；
`browser`、`live`、`allow_subprocess` 标记不能绕过。已有 `_scenarios` 的最小片段
可供 unit 读取。安全检查不导入 PDF 转换后端；转换单测可注入 fake module。
这些失败路径由 integration 中的子 pytest 验证。

`test-evidence.json` 是内部 v2 台账：每个模块声明默认分类，仅不同契约的测试
使用 `overrides`，新增普通测试无需逐函数登记。收集时直接应用分类；独立的
`test_evidence_ledger_integrity` 检查失效模块、例外和跨模块模板引用。
运行时审计仍覆盖收集期读取、共享 fixture、进程内缓存和跨 worker 构建缓存。
来源读取只证明使用了什么证据，不替代数值、对象归属、顺序和位置断言。

当前来源选择、资产集合与签名回放由 fixture manifest 管理；`rejected_sources`
和 `withdrawn_assets` 保留不可执行的拒绝与撤回记录。复杂表格的固定行列映射、
单元格和 MathML 事实存于样本 expected 的 `source_objects`，绑定源文件 SHA-256、
源节点哈希及对象索引。更新预期必须核对原始 HTML/XML，不能从生产输出生成。
简单节点选择和对象位置检查继续读取原文；输出比较保留数值和上下标边界。

同一样本、相同来源分类的重复实体通过 manifest 的 `assets` 逻辑名称指向保留文件。
provenance 中每次采集的 URL、时间、状态和 headers 保持独立，`body_file` 指向实体，
`original_body_file` 保留被合并的采集名称。URL 回放默认精确匹配；仅 ACS、AIP、
Oxford Academic、Royal Society 各自 Silverchair CDN 的签名回放忽略已知过期签名参数，
保留对象、尺寸及其他 query。
退役 provider 的来源负例保存在 `tests/fixtures/golden_criteria/_scenarios/`，在 manifest 中登记为
`synthetic` / `infrastructure`；`rejected_sources` 保留路径和拒绝哈希，
来源验证测试确保这些字节不能重新登记为真实原文。
测试运行结果保存在仓库外或已忽略的本地运行目录，不作为当前测试的执行输入。
