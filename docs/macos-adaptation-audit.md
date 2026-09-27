# macOS 适配与证据边界

macOS 的机器合同见 [`macos-adaptation-contract.toml`](macos-adaptation-contract.toml)。它只记录长期支持矩阵、安全不变量和原生证据要求；全平台 release 事实继续由 workflow、installer manifest 与 release asset owner 维护。

## 支持范围

- 在线安装遵循 `pyproject.toml` 的 Python 版本范围。
- 离线安装包只面向 Apple Silicon；具体 CPython 矩阵和 runner 由 `.github/workflows/offline.yml` 定义。
- 安装包命名来自 `installer/manifest.json`，公开资产集合由 `scripts/prepare_release_assets.py` 定义。macOS 合同不复制全平台资产数量或依赖清单。
- 稳定发布的源码、离线构建与依赖快照验证工具来自同一个已验证 commit SHA，不支持跨 revision tooling overlay。

## 安全不变量

构建与安装必须继续拒绝错误架构、非标准 CPython ABI、未归属 staging、符号链接 payload 和未验证的 purge 路径。正式产物使用原子发布；quarantine 与 payload inventory 校验 fail closed。Camoufox 浏览器不打入离线包，核心安装不下载浏览器；可选向导仅在用户明确选择后预置，失败不回滚核心安装。受管 runtime 在实际启动浏览器前自动补全或更新，尊重已有渠道和固定版本；更新失败时可复用校验有效的本地版本。离线使用前仍需在联网阶段预先准备，预置不等于已验证完全断网启动。

## 证据等级

- `scripts/validate_macos_adaptation.py` 从项目元数据、workflow、installer manifest 和 release asset owner 读取当前事实并校验合同。
- Windows 与 Linux/WSL contract 入口只提供本地静态和纯 Python 预检查，不属于 CI 平台证据，也不证明 Mach-O、codesign、quarantine、文件模式、大小写或原生浏览器 bundle。
- `.github/workflows/verify.yml` 的原生 macOS gate 提供 CPython 3.14 与浏览器 bundle 证据；`.github/workflows/offline.yml` 覆盖发布矩阵。

本地修改涉及上述边界时，先运行 `python scripts/validate_macos_adaptation.py`，再在当前平台运行对应 contract 入口。原生发布证据只能由 macOS runner 提供。

Wiley 正文资产复用 Camoufox runtime，在资产阶段建立自有 context/page：监听器先于逐资产 URL 导航注册，每候选只主动导航一次，公式优先并在页面所属线程串行执行。每逻辑资产最多 30 秒，验证与预览回退共享该预算；cookies 仅初始化注入，允许浏览器自然完成挑战。当前导航及重定向链的原始响应与 DOM 加载证据共同决定成功，迟到响应不串图。普通单图失败继续复用页面；结束、总期限、共享预算耗尽或取消时解绑监听器并关闭自有页面和 context。Linux 最小浏览器集成测试验证原始响应、挑战恢复、导航异常后验收、会话复用和清理契约，不替代原生 macOS gate。

Wiley 的六组合线上结果与本地验证限制见 [正文资产串行导航审计](wiley-body-assets-audit.md)；其中资产完整不等同于公式正文表示通过统一验收。
