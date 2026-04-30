# Paper Fetch Skill Windows 安装器与排障

本文档说明 Windows x86_64 release asset `paper-fetch-skill-windows-x86_64-setup.exe` 的安装结果、验证方式，以及 legacy zip / developer package 的手动排障路径。

## 推荐流程：运行 setup exe

下载安装器后直接运行：

```powershell
.\paper-fetch-skill-windows-x86_64-setup.exe
```

默认安装目录：

```text
%LOCALAPPDATA%\PaperFetchSkill
```

安装器不要求管理员权限，会安装：

- `runtime\python.exe`：官方 CPython 3.13 x64 embeddable runtime
- `runtime\Lib\site-packages`：`paper-fetch-skill` 和 Python 依赖
- `bin\paper-fetch.cmd`、`bin\paper-fetch-mcp.cmd`
- `bin\flaresolverr-up.cmd`、`bin\flaresolverr-status.cmd`、`bin\flaresolverr-down.cmd`
- `ms-playwright\`、`formula-tools\`、`vendor\flaresolverr\`
- Codex skill：`%USERPROFILE%\.codex\skills\paper-fetch-skill`
- Claude Code skill：`%USERPROFILE%\.claude\skills\paper-fetch-skill`

安装器会把安装目录的 `bin` 写入用户 PATH。安装完成后新开 PowerShell，验证：

```powershell
paper-fetch --help
```

如果当前机器有 `codex` CLI，安装器会执行：

```text
codex mcp remove paper-fetch
codex mcp add ...
```

如果没有 `codex` CLI，安装器会备份并更新：

```text
%USERPROFILE%\.codex\config.toml
```

写入的 MCP 配置使用：

```text
command = %LOCALAPPDATA%\PaperFetchSkill\runtime\python.exe
args = -X utf8 -m paper_fetch.mcp.server
```

如果当前机器有 `claude` CLI，安装器会执行：

```text
claude mcp remove -s user paper-fetch
claude mcp add -s user ...
```

没有 Claude CLI 时，只安装 Claude Code skill，不猜测 Claude 的内部配置格式。

## 环境变量

安装器写入 `%LOCALAPPDATA%\PaperFetchSkill\offline.env`，并把 MCP env 固定指向安装目录内的运行组件：

```text
PYTHONUTF8=1
PYTHONIOENCODING=utf-8
PAPER_FETCH_ENV_FILE=%LOCALAPPDATA%\PaperFetchSkill\offline.env
PAPER_FETCH_MCP_PYTHON_BIN=%LOCALAPPDATA%\PaperFetchSkill\runtime\python.exe
PAPER_FETCH_DOWNLOAD_DIR=%LOCALAPPDATA%\PaperFetchSkill\downloads
PAPER_FETCH_FORMULA_TOOLS_DIR=%LOCALAPPDATA%\PaperFetchSkill\formula-tools
PLAYWRIGHT_BROWSERS_PATH=%LOCALAPPDATA%\PaperFetchSkill\ms-playwright
FLARESOLVERR_URL=http://127.0.0.1:8191/v1
FLARESOLVERR_ENV_FILE=%LOCALAPPDATA%\PaperFetchSkill\vendor\flaresolverr\.env.flaresolverr-source-windows
FLARESOLVERR_SOURCE_DIR=%LOCALAPPDATA%\PaperFetchSkill\vendor\flaresolverr
```

Elsevier 官方 XML/API 和 PDF fallback 仍需要用户申请 key，并写入：

```powershell
notepad "$env:LOCALAPPDATA\PaperFetchSkill\offline.env"
```

添加：

```text
ELSEVIER_API_KEY="..."
```

## FlareSolverr

Wiley / Science / PNAS 浏览器链路需要先启动 bundled FlareSolverr：

```powershell
flaresolverr-up
flaresolverr-status
```

停止：

```powershell
flaresolverr-down
```

## 最小 MCP 验证

用安装器内置 Python 检查 MCP server 可导入：

```powershell
$Root = "$env:LOCALAPPDATA\PaperFetchSkill"
& "$Root\runtime\python.exe" -X utf8 -c "import paper_fetch; import paper_fetch.mcp.server; from paper_fetch.mcp.tools import provider_status_payload; assert 'providers' in provider_status_payload()"
```

检查 Codex TOML fallback：

```powershell
$ConfigToml = "$env:USERPROFILE\.codex\config.toml"
Get-Content -LiteralPath $ConfigToml
```

修改 Codex / Claude Code skill 或 MCP 配置后，需要重启对应 host。

## 卸载行为

Windows 卸载器只清理安装器管理的内容：

- 删除安装目录
- 删除 `%USERPROFILE%\.codex\skills\paper-fetch-skill`
- 删除 `%USERPROFILE%\.claude\skills\paper-fetch-skill`
- 从用户 PATH 移除安装目录 `bin`
- 移除安装器管理的 Codex MCP 配置，或在有 CLI 时调用 `codex mcp remove paper-fetch`
- 在有 Claude CLI 时调用 `claude mcp remove -s user paper-fetch`

卸载器不会删除用户自己写入的其它 Codex / Claude 配置。

## Legacy / Developer Package 排障

旧版 Windows zip 或开发者 staging 仍可按手动方式排障，但不再是公开 release 推荐流程。前提是目录中包含：

```text
dist
wheelhouse
skills
offline.env
ms-playwright
formula-tools
vendor
```

如果使用旧 zip，目标 Python 必须匹配包名 ABI；例如 `cp313` 只能使用 CPython 3.13 x64。

```powershell
$Bundle = 'C:\Users\<you>\Downloads\paper-fetch-offline'
$Python = 'C:\Users\<you>\miniforge3\envs\paper-fetch\python.exe'

& $Python -c "import sys; print(sys.version); print(f'cp{sys.version_info.major}{sys.version_info.minor}')"
& $Python -m ensurepip

$ProjectWheels = @(Get-ChildItem -LiteralPath "$Bundle\dist" -Filter 'paper_fetch_skill-*.whl')
if ($ProjectWheels.Count -ne 1) { throw "Expected exactly one paper_fetch_skill wheel, found $($ProjectWheels.Count)." }
& $Python -m pip install --no-index --find-links "$Bundle\wheelhouse" --only-binary=:all: $ProjectWheels[0].FullName
& $Python -c "import paper_fetch; print(paper_fetch.__file__)"
```

手动注册 Codex MCP 时，推荐直接调用确定的 Python：

```toml
[mcp_servers.paper-fetch]
command = 'C:\Users\<you>\miniforge3\envs\paper-fetch\python.exe'
args = ['-X', 'utf8', '-m', 'paper_fetch.mcp.server']

[mcp_servers.paper-fetch.env]
PYTHONUTF8 = "1"
PYTHONIOENCODING = "utf-8"
PAPER_FETCH_ENV_FILE = 'C:\Users\<you>\Downloads\paper-fetch-offline\offline.env'
PAPER_FETCH_MCP_PYTHON_BIN = 'C:\Users\<you>\miniforge3\envs\paper-fetch\python.exe'
PAPER_FETCH_DOWNLOAD_DIR = 'C:\Users\<you>\Downloads\paper-fetch-offline\downloads'
PAPER_FETCH_FORMULA_TOOLS_DIR = 'C:\Users\<you>\Downloads\paper-fetch-offline\formula-tools'
PLAYWRIGHT_BROWSERS_PATH = 'C:\Users\<you>\Downloads\paper-fetch-offline\ms-playwright'
FLARESOLVERR_URL = 'http://127.0.0.1:8191/v1'
FLARESOLVERR_ENV_FILE = 'C:\Users\<you>\Downloads\paper-fetch-offline\vendor\flaresolverr\.env.flaresolverr-source-windows'
FLARESOLVERR_SOURCE_DIR = 'C:\Users\<you>\Downloads\paper-fetch-offline\vendor\flaresolverr'
```
