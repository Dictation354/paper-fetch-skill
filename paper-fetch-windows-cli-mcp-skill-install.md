# Paper Fetch Skill Windows 离线安装流程

本文档记录如何在 Windows 上从零安装 `paper-fetch-skill` 的 CLI、MCP server 和 Codex skill。

适用场景：

- 已经拿到 Windows x86_64 / CPython 3.13 的离线包。
- 离线包路径类似：`C:\Users\Dictation\Downloads\paper-fetch-skill-offline-windows-x86_64-cp313`
- 希望在 Codex 中使用 `paper-fetch` MCP 工具。
- 希望安装用户级 Codex skill：`paper-fetch-skill`。

本文以当前机器实际路径为例。

## 0. 目标安装结果

安装完成后，应具备：

- CLI 命令：`paper-fetch.exe`
- MCP server：`paper-fetch-mcp.exe`
- Codex skill：`C:\Users\Dictation\.codex\skills\paper-fetch-skill`
- Codex MCP 配置：`C:\Users\Dictation\.codex\config.toml`

MCP 应暴露这些工具：

```text
resolve_paper
has_fulltext
fetch_paper
list_cached
get_cached
batch_resolve
batch_check
provider_status
```

## 1. 准备路径变量

打开 PowerShell，先设置下面这些变量。

```powershell
$Bundle = 'C:\Users\Dictation\Downloads\paper-fetch-skill-offline-windows-x86_64-cp313'
$EnvName = 'paper-fetch'
$Conda = 'C:\Users\Dictation\miniforge3\Scripts\conda.exe'
$Python = 'C:\Users\Dictation\miniforge3\envs\paper-fetch\python.exe'
$CodexHome = 'C:\Users\Dictation\.codex'
$ConfigToml = "$CodexHome\config.toml"
```

检查离线包是否存在：

```powershell
Test-Path -LiteralPath $Bundle
Get-ChildItem -LiteralPath $Bundle -Force
```

至少应看到这些目录或文件：

```text
dist
wheelhouse
skills
offline.env
install-offline.ps1
ms-playwright
formula-tools
vendor
```

## 2. 准备 Python 环境

离线包名称中有 `cp313`，所以目标 Python 必须是 CPython 3.13 x64。

如果 Miniforge 环境已经存在，检查版本：

```powershell
& $Python -c "import sys, platform; print(sys.executable); print(sys.version); print(platform.architecture())"
```

如果环境不存在，可以创建：

```powershell
& $Conda create -n $EnvName python=3.13 -y
```

创建后重新设置：

```powershell
$Python = 'C:\Users\Dictation\miniforge3\envs\paper-fetch\python.exe'
```

再次检查：

```powershell
& $Python -c "import sys; print(sys.version); print(sys.implementation.name); print(f'cp{sys.version_info.major}{sys.version_info.minor}')"
```

期望输出中包含：

```text
cpython
cp313
```

## 3. 安装 CLI 和 MCP Python 包

有些最小 conda 环境没有 `pip`。先安装 `pip`：

```powershell
& $Python -m ensurepip
```

然后从离线包的 wheelhouse 安装 `paper-fetch-skill`：

```powershell
& $Python -m pip install --no-index --find-links "$Bundle\wheelhouse" --only-binary=:all: "$Bundle\dist\paper_fetch_skill-1.0.0-py3-none-any.whl"
```

这一步会把 CLI 和 MCP 入口装到：

```text
C:\Users\Dictation\miniforge3\envs\paper-fetch\Scripts\paper-fetch.exe
C:\Users\Dictation\miniforge3\envs\paper-fetch\Scripts\paper-fetch-mcp.exe
```

验证 Python 包能导入：

```powershell
& $Python -c "import paper_fetch; print(paper_fetch.__file__)"
```

验证 CLI 能启动：

```powershell
& 'C:\Users\Dictation\miniforge3\envs\paper-fetch\Scripts\paper-fetch.exe' --help
```

如果只想使用离线包自带 `.venv`，也可以先运行官方离线安装脚本：

```powershell
Set-Location -LiteralPath $Bundle
.\install-offline.ps1 -PythonBin $Python -NoUserConfig
```

但如果要统一使用 Miniforge 的 `paper-fetch` 环境，仍建议按上面的 `pip install --no-index` 安装到该环境。

## 4. 安装 Codex Skill

复制 skill 到用户级 Codex skill 目录：

```powershell
$SkillSrc = "$Bundle\skills\paper-fetch-skill"
$SkillDst = "$CodexHome\skills\paper-fetch-skill"

New-Item -ItemType Directory -Force -Path $SkillDst, "$SkillDst\agents", "$SkillDst\references" | Out-Null
Copy-Item -LiteralPath "$SkillSrc\SKILL.md" -Destination "$SkillDst\SKILL.md" -Force
Copy-Item -LiteralPath "$SkillSrc\references\*" -Destination "$SkillDst\references" -Recurse -Force
```

创建 Codex agent 元数据文件：

```powershell
@'
interface:
  display_name: "Paper Fetch Skill"
  short_description: "Fetch AI-friendly paper text by DOI, URL, or title"
  default_prompt: "Use $paper-fetch-skill whenever you need the text, readability, or full-text availability of a specific paper or a citation list of identifiable papers."
'@ | Set-Content -LiteralPath "$SkillDst\agents\openai.yaml" -Encoding utf8
```

检查 skill 文件：

```powershell
Get-ChildItem -LiteralPath $SkillDst -Force
Get-ChildItem -LiteralPath "$SkillDst\references" -Force
Get-Content -LiteralPath "$SkillDst\SKILL.md" -TotalCount 20
Get-Content -LiteralPath "$SkillDst\agents\openai.yaml"
```

## 5. 配置 Codex MCP

编辑文件：

```text
C:\Users\Dictation\.codex\config.toml
```

加入或替换下面这段配置。

注意：

- `PYTHONUTF8` 和 `PYTHONIOENCODING` 很重要。Windows 下如果不设置，MCP 输出可能包含非 UTF-8 字节，导致 `Transport closed`。
- TOML 单引号字符串可以直接写 Windows 反斜杠路径。

```toml
[mcp_servers.paper-fetch]
command = 'C:\Users\Dictation\miniforge3\envs\paper-fetch\Scripts\paper-fetch-mcp.exe'

[mcp_servers.paper-fetch.env]
PYTHONUTF8 = "1"
PYTHONIOENCODING = "utf-8"
PAPER_FETCH_ENV_FILE = 'C:\Users\Dictation\Downloads\paper-fetch-skill-offline-windows-x86_64-cp313\offline.env'
PAPER_FETCH_MCP_PYTHON_BIN = 'C:\Users\Dictation\miniforge3\envs\paper-fetch\python.exe'
PAPER_FETCH_DOWNLOAD_DIR = 'C:\Users\Dictation\Downloads\paper-fetch-skill-offline-windows-x86_64-cp313\downloads'
PAPER_FETCH_FORMULA_TOOLS_DIR = 'C:\Users\Dictation\Downloads\paper-fetch-skill-offline-windows-x86_64-cp313\formula-tools'
PLAYWRIGHT_BROWSERS_PATH = 'C:\Users\Dictation\Downloads\paper-fetch-skill-offline-windows-x86_64-cp313\ms-playwright'
FLARESOLVERR_URL = 'http://127.0.0.1:8191/v1'
FLARESOLVERR_ENV_FILE = 'C:\Users\Dictation\Downloads\paper-fetch-skill-offline-windows-x86_64-cp313\vendor\flaresolverr\.env.flaresolverr-source-windows'
FLARESOLVERR_SOURCE_DIR = 'C:\Users\Dictation\Downloads\paper-fetch-skill-offline-windows-x86_64-cp313\vendor\flaresolverr'
```

检查 TOML 是否能解析：

```powershell
& $Python -c "import tomllib; cfg=tomllib.load(open(r'C:\Users\Dictation\.codex\config.toml','rb')); print(cfg['mcp_servers']['paper-fetch']['command'])"
```

## 6. 验证 MCP Server

先确认 provider 状态函数能跑：

```powershell
$env:PAPER_FETCH_ENV_FILE = "$Bundle\offline.env"
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PLAYWRIGHT_BROWSERS_PATH = "$Bundle\ms-playwright"

& $Python -c "from paper_fetch.mcp.tools import provider_status_payload; payload = provider_status_payload(); print([p.get('provider') for p in payload['providers']])"
```

然后用 MCP Python client 做一次 stdio 握手和工具列表验证：

```powershell
@'
import asyncio, tomllib
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

cfg = tomllib.load(open(r'C:\Users\Dictation\.codex\config.toml', 'rb'))
server = cfg['mcp_servers']['paper-fetch']

async def main():
    params = StdioServerParameters(command=server['command'], env=server['env'])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print('tools=' + ','.join(tool.name for tool in tools.tools))
            result = await session.call_tool('provider_status', {})
            print('provider_status_prefix=' + result.content[0].text[:120].replace('\n', ' '))

asyncio.run(main())
'@ | & $Python -
```

成功时应看到类似：

```text
tools=resolve_paper,has_fulltext,fetch_paper,list_cached,get_cached,batch_resolve,batch_check,provider_status
provider_status_prefix={   "providers": [
```

## 7. 重启 Codex

安装或修改 MCP 配置后，需要重启 Codex。

原因：

- Codex 启动时扫描 skill。
- MCP 配置通常不会在当前会话里完整热加载。
- 如果当前会话里调用 MCP 仍显示 `Transport closed`，重启后再试。

重启后，在 Codex 中测试：

```text
调用 paper-fetch 的 provider_status
```

正常情况下会返回 provider 状态。

## 8. 当前这台机器上的实际状态

本机最终使用的是：

```text
Python:
C:\Users\Dictation\miniforge3\envs\paper-fetch\python.exe

CLI:
C:\Users\Dictation\miniforge3\envs\paper-fetch\Scripts\paper-fetch.exe

MCP:
C:\Users\Dictation\miniforge3\envs\paper-fetch\Scripts\paper-fetch-mcp.exe

Skill:
C:\Users\Dictation\.codex\skills\paper-fetch-skill

Config:
C:\Users\Dictation\.codex\config.toml

Offline env:
C:\Users\Dictation\Downloads\paper-fetch-skill-offline-windows-x86_64-cp313\offline.env
```

当前 MCP `provider_status` 的大致情况：

- `crossref`: ready
- `springer`: ready
- `wiley`: partial
- `elsevier`: not_configured，缺 `ELSEVIER_API_KEY`
- `science`: not_configured，FlareSolverr 未启动
- `pnas`: not_configured，FlareSolverr 未启动

## 9. 常见问题

### 9.1 `No module named pip`

运行：

```powershell
& $Python -m ensurepip
```

然后重新执行离线安装：

```powershell
& $Python -m pip install --no-index --find-links "$Bundle\wheelhouse" --only-binary=:all: "$Bundle\dist\paper_fetch_skill-1.0.0-py3-none-any.whl"
```

### 9.2 `No module named paper_fetch`

说明包没有安装到当前 `$Python` 对应的环境。

检查当前 Python：

```powershell
& $Python -c "import sys; print(sys.executable)"
```

重新安装：

```powershell
& $Python -m pip install --no-index --find-links "$Bundle\wheelhouse" --only-binary=:all: "$Bundle\dist\paper_fetch_skill-1.0.0-py3-none-any.whl"
```

### 9.3 MCP 调用报 `Transport closed`

常见原因有三个：

1. Codex 当前会话还在用旧配置，需要重启 Codex。
2. Windows 编码不是 UTF-8，需要在 MCP env 中设置：

```toml
PYTHONUTF8 = "1"
PYTHONIOENCODING = "utf-8"
```

3. `command` 路径指向了不存在的 `paper-fetch-mcp.exe`。

检查：

```powershell
Test-Path -LiteralPath 'C:\Users\Dictation\miniforge3\envs\paper-fetch\Scripts\paper-fetch-mcp.exe'
```

### 9.4 Elsevier 不可用

需要配置：

```text
ELSEVIER_API_KEY
```

可以写入：

```text
C:\Users\Dictation\Downloads\paper-fetch-skill-offline-windows-x86_64-cp313\offline.env
```

### 9.5 Wiley / Science / PNAS 不可用

这些路径依赖本地 FlareSolverr / browser runtime。

检查脚本：

```powershell
Get-ChildItem -LiteralPath "$Bundle\scripts" -Filter 'flaresolverr-*.ps1'
```

启动 FlareSolverr：

```powershell
& "$Bundle\scripts\flaresolverr-up.ps1"
```

查看状态：

```powershell
& "$Bundle\scripts\flaresolverr-status.ps1"
```

停止：

```powershell
& "$Bundle\scripts\flaresolverr-down.ps1"
```

## 10. 这次实际执行过的核心命令

这次实际安装时，关键命令如下：

```powershell
& 'C:\Users\Dictation\miniforge3\envs\paper-fetch\python.exe' -m ensurepip
```

```powershell
& 'C:\Users\Dictation\miniforge3\envs\paper-fetch\python.exe' -m pip install --no-index --find-links 'C:\Users\Dictation\Downloads\paper-fetch-skill-offline-windows-x86_64-cp313\wheelhouse' --only-binary=:all: 'C:\Users\Dictation\Downloads\paper-fetch-skill-offline-windows-x86_64-cp313\dist\paper_fetch_skill-1.0.0-py3-none-any.whl'
```

```powershell
$src = 'C:\Users\Dictation\Downloads\paper-fetch-skill-offline-windows-x86_64-cp313\skills\paper-fetch-skill'
$dst = 'C:\Users\Dictation\.codex\skills\paper-fetch-skill'

New-Item -ItemType Directory -Force -Path $dst, (Join-Path $dst 'agents'), (Join-Path $dst 'references') | Out-Null
Copy-Item -LiteralPath (Join-Path $src 'SKILL.md') -Destination (Join-Path $dst 'SKILL.md') -Force
Copy-Item -LiteralPath (Join-Path $src 'references\*') -Destination (Join-Path $dst 'references') -Recurse -Force
```

并在 `C:\Users\Dictation\.codex\config.toml` 中写入 `paper-fetch` MCP 配置。

