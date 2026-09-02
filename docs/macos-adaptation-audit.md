# macOS 适配与证据边界

macOS 的机器合同见 [`macos-adaptation-contract.toml`](macos-adaptation-contract.toml)。它只记录长期支持矩阵、安全不变量和原生证据要求；全平台 release 事实继续由 workflow、installer manifest 与 release asset owner 维护。

## 支持范围

- 在线安装遵循 `pyproject.toml` 的 Python 版本范围。
- 离线安装包只面向 Apple Silicon；具体 CPython 矩阵和 runner 由 `.github/workflows/offline.yml` 定义。
- 安装包命名来自 `installer/manifest.json`，公开资产集合由 `scripts/prepare_release_assets.py` 定义。macOS 合同不复制全平台资产数量或依赖清单。
- 稳定发布的源码、离线构建与依赖快照验证工具来自同一个已验证 commit SHA，不支持跨 revision tooling overlay。

## 安全不变量

构建与安装必须继续拒绝错误架构、非标准 CPython ABI、未归属 staging、符号链接 payload 和未验证的 purge 路径。正式产物使用原子发布；quarantine 与 payload inventory 校验 fail closed。Camoufox 浏览器不打入离线包，安装过程不下载浏览器；需要受管 runtime 时由用户显式运行 `python -m camoufox fetch`，离线使用前必须在联网阶段预先准备。

## 证据等级

- `scripts/validate_macos_adaptation.py` 从项目元数据、workflow、installer manifest 和 release asset owner 读取当前事实并校验合同。
- Windows 与 Linux/WSL contract 入口只提供本地静态和纯 Python 预检查，不属于 CI 平台证据，也不证明 Mach-O、codesign、quarantine、文件模式、大小写或原生浏览器 bundle。
- `.github/workflows/verify.yml` 的原生 macOS gate 提供 CPython 3.14 与浏览器 bundle 证据；`.github/workflows/offline.yml` 覆盖发布矩阵。

本地修改涉及上述边界时，先运行 `python scripts/validate_macos_adaptation.py`，再在当前平台运行对应 contract 入口。原生发布证据只能由 macOS runner 提供。
