# 离线可选配置向导验证记录

日期：2026-09-13。实现覆盖 Linux/macOS 离线入口和 Windows Inno EXE，未修改源码在线安装入口、版本号或 GitHub CI 配置，未发布版本或触发 CI。

## 已完成的验证

| 验证 | 结果及证据范围 |
| --- | --- |
| macOS 静态契约、WSL/Linux 契约脚本 | `uv run python scripts/validate_macos_adaptation.py`、`bash scripts/test-macos-contract.sh` 通过，6 项测试；使用 `/home` 下的原生 Linux CPython 3.14 / venv。系统 Python 缺少 PyYAML，所以静态验证使用项目 uv 环境。 |
| 完整 unit | `PYTHONPATH=src uv run python -m pytest tests/unit -q`：2566 passed、1 skipped、576 subtests passed。 |
| 完整 integration | `PYTHONPATH=src uv run python -m pytest tests/integration -q`：23 passed、4 skipped、11 subtests passed。两个新增图片用例默认因系统 PATH 无工具而跳过，另行通过下述实际二进制验证；原生 macOS gate 未启用。 |
| 可选向导及安全边界 | 46 项定向 unit 通过，包括全部跳过、独立选择、有效工具复用、转换失败后候选回退、非交互、dotenv 转义/去重/原子失败、外部 env 只读、隐藏输入请求清理、SID ACL 命令、APT/t64、Homebrew、断网/摘要失败/恶意 ZIP/取消、UAC 失败、注册冲突及卸载保留。libvips 新增/修改文件及新增空目录均保留。 |
| Linux 完整离线包 | 使用 `scripts/build-offline-package.sh` 构建 CPython 3.14 包，通过 `scripts/verify-offline-package.sh` 的安装、升级、配置保留、非交互模块、卸载、purge 和网络/构建命令防护。设置 `PAPER_FETCH_OFFLINE_SKIP_FETCH_SMOKE=1`，未执行外部论文抓取。 |
| Linux 实际图片转换 | 将 Ubuntu 仓库 Ghostscript 10.06.0、libvips 8.18.0 及所需库仅解压到临时目录，未安装系统包。显式设置测试工具路径后，`tests/integration/test_offline_optional_tools.py` 两项通过：应用转换链实际处理 EPS/TIFF，再以既有 PyMuPDF 解码 PNG 并检查尺寸、像素。 |
| Linux 本地 Camoufox | 复用既有有效缓存 `152.0.4-beta.30`，禁止准备函数被调用；Playwright 以绝对路径启动，访问 `about:blank` 并执行本地表达式成功。未下载、访问出版社、登录或保存 provider state。 |
| Windows Inno 编译及隔离样本生命周期 | 在 Windows 上使用官方 Inno 6.5.4 portable 编译器成功编译。用独立 AppId、临时 payload 和不改宿主配置的 helper 样本，验证静默安装、先卸载再升级、静默卸载、凭据及可选文件保留，且未执行可选向导。这是安装器行为证据，不是完整发行 EXE 的终验。 |
| Windows 固定 libvips 资产 | [官方 8.18.6 x64 all ZIP](https://github.com/libvips/build-win64-mxe/releases/tag/v8.18.6) 下载后核对 manifest SHA-256，使用实现中的安全解压器保留完整目录；在 Windows 原生执行 `vips.exe --version`、TIFF → PNG，再校验实际 PNG 尺寸及像素，均通过。 |
| Windows 固定 Ghostscript 资产 | [官方 10.08.0 x64 EXE](https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/tag/gs10080) 已实际下载并核对 manifest SHA-256；没有在当前宿主安装或卸载 Ghostscript。 |
| 静态检查 | 新增 Python 代码/测试的 Ruff、Bash 语法、`git diff --check` 通过。 |

完整及定向常规测试均使用项目默认 pytest 并行配置，未添加 `-n 0`。独立原生安装样本按安装 → 升级 → 卸载顺序运行，因为它们共享同一安装目录和注册状态。

## 尚未完成的原生终验

- 原生 macOS 15+ arm64 上的完整安装向导、Homebrew 选择、quarantine 拒绝及 Camoufox 空白页启动；WSL/Linux 绿灯不能替代 `.github/workflows/verify.yml` 的 macOS gate。现有 `tests/integration/test_camoufox_native_macos.py` 已补入可选向导验证，仍需在原生 runner 上执行。
- 完整 Windows 发行 EXE 的交互式凭据输入及实际文件 DACL、各独立组件选择、Ghostscript 官方安装/UAC 取消、更改安装目录、注册冲突修复说明、官方卸载/UAC 取消，以及完整发行 EXE 的升级/卸载终验。临时样本与 mock 测试不能替代这些结果。
- 未宣称完整断网的浏览器支持，也未验证任何出版社访问能力。

## 原生复验入口

核心包继续使用 `scripts/verify-offline-package.sh` 和 `scripts/verify-windows-installer-lifecycle.ps1`。Windows lifecycle gate 已增加独立可选文件/清单的升级与默认静默卸载保留检查。交互项按 [部署文档](deployment.md) 的选择说明逐项验证；首次全部留空/不选，随后分别选择各组件，并重复失败、取消、升级和清理场景。

图片工具已准备好时，可在各原生平台显式指定二进制并运行实际转换测试：

```bash
PAPER_FETCH_TEST_GHOSTSCRIPT_BIN=/absolute/path/to/gs \
PAPER_FETCH_TEST_VIPS_BIN=/absolute/path/to/vips \
PYTHONPATH=src uv run python -m pytest tests/integration/test_offline_optional_tools.py -q
```

Windows 用 PowerShell 设置相同两个测试环境变量，分别指向 `gswin64c.exe`、`vips.exe`，再运行同一 pytest 文件。测试不下载或安装任何工具。原生 macOS 浏览器验证继续使用已有的 `PAPER_FETCH_RUN_NATIVE_CAMOUFOX_TEST=1` gate，须事先按部署说明准备缓存。
