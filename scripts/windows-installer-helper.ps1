param(
    [ValidateSet("Install", "Uninstall", "Smoke")]
    [string]$Action = "Install",
    [string]$InstallRoot,
    [switch]$SkipSmoke
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$SkillName = "paper-fetch-skill"
$McpName = "paper-fetch"
$CodexManagedBegin = "# BEGIN paper-fetch installer managed"
$CodexManagedEnd = "# END paper-fetch installer managed"

if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
    $InstallRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
} else {
    $InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
}

function Write-Log {
    param([string]$Message)
    Write-Host "==> $Message"
}

function Write-Warn {
    param([string]$Message)
    Write-Warning $Message
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments = @(),
        [switch]$IgnoreFailure
    )

    & $FilePath @Arguments | ForEach-Object { Write-Host $_ }
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0 -and -not $IgnoreFailure) {
        throw "Command failed with exit code ${exitCode}: $FilePath $($Arguments -join ' ')"
    }
}

function Get-RuntimePython {
    return Join-Path (Join-Path $InstallRoot "runtime") "python.exe"
}

function ConvertTo-FullPath {
    param([string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Quote-DotenvValue {
    param([string]$Value)
    $escaped = (ConvertTo-FullPath $Value).Replace("\", "/").Replace("'", "\'")
    return "'$escaped'"
}

function ConvertTo-TomlString {
    param([string]$Value)
    $escaped = $Value.Replace("\", "\\").Replace('"', '\"')
    return '"' + $escaped + '"'
}

function Get-McpEnv {
    $offlineEnv = Join-Path $InstallRoot "offline.env"
    $downloads = Join-Path $InstallRoot "downloads"
    $formulaTools = Join-Path $InstallRoot "formula-tools"
    $playwright = Join-Path $InstallRoot "ms-playwright"
    $flaresolverrSource = Join-Path (Join-Path $InstallRoot "vendor") "flaresolverr"
    $flaresolverrEnv = Join-Path $flaresolverrSource ".env.flaresolverr-source-windows"

    return [ordered]@{
        PYTHONUTF8 = "1"
        PYTHONIOENCODING = "utf-8"
        PAPER_FETCH_ENV_FILE = (ConvertTo-FullPath $offlineEnv)
        PAPER_FETCH_MCP_PYTHON_BIN = (ConvertTo-FullPath (Get-RuntimePython))
        PAPER_FETCH_DOWNLOAD_DIR = (ConvertTo-FullPath $downloads)
        PAPER_FETCH_FORMULA_TOOLS_DIR = (ConvertTo-FullPath $formulaTools)
        PLAYWRIGHT_BROWSERS_PATH = (ConvertTo-FullPath $playwright)
        FLARESOLVERR_URL = "http://127.0.0.1:8191/v1"
        FLARESOLVERR_ENV_FILE = (ConvertTo-FullPath $flaresolverrEnv)
        FLARESOLVERR_SOURCE_DIR = (ConvertTo-FullPath $flaresolverrSource)
    }
}

function Set-ProcessRuntimeEnv {
    foreach ($entry in (Get-McpEnv).GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, [string]$entry.Value, "Process")
    }
}

function Write-ManagedEnvFile {
    $target = Join-Path $InstallRoot "offline.env"
    $envMap = Get-McpEnv
    $lines = New-Object System.Collections.Generic.List[string]
    if (Test-Path -LiteralPath (Join-Path $InstallRoot ".env.example")) {
        foreach ($line in Get-Content -LiteralPath (Join-Path $InstallRoot ".env.example")) {
            $lines.Add($line)
        }
    } else {
        $lines.Add('ELSEVIER_API_KEY=""')
    }
    $lines.Add("")
    $lines.Add("# BEGIN paper-fetch offline managed")
    foreach ($name in @(
        "PAPER_FETCH_DOWNLOAD_DIR",
        "PAPER_FETCH_FORMULA_TOOLS_DIR",
        "PLAYWRIGHT_BROWSERS_PATH",
        "FLARESOLVERR_URL",
        "FLARESOLVERR_ENV_FILE",
        "FLARESOLVERR_SOURCE_DIR",
        "PYTHONUTF8",
        "PYTHONIOENCODING"
    )) {
        $value = [string]$envMap[$name]
        if ($name -in @("PYTHONUTF8", "PYTHONIOENCODING", "FLARESOLVERR_URL")) {
            $lines.Add("$name='$value'")
        } else {
            $lines.Add("$name=$(Quote-DotenvValue $value)")
        }
    }
    $lines.Add("# END paper-fetch offline managed")
    [System.IO.File]::WriteAllLines($target, $lines, [System.Text.UTF8Encoding]::new($false))
}

function Copy-InstalledSkill {
    param([string]$Destination)

    $source = Join-Path (Join-Path $InstallRoot "skills") $SkillName
    if (-not (Test-Path -LiteralPath (Join-Path $source "SKILL.md") -PathType Leaf)) {
        throw "Missing bundled skill source: $source"
    }

    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $Destination
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Copy-Item -Path (Join-Path $source "*") -Destination $Destination -Recurse -Force
}

function Install-Skills {
    $codexSkill = Join-Path (Join-Path (Join-Path $env:USERPROFILE ".codex") "skills") $SkillName
    $claudeSkill = Join-Path (Join-Path (Join-Path $env:USERPROFILE ".claude") "skills") $SkillName

    Write-Log "Installing Codex skill to $codexSkill"
    Copy-InstalledSkill $codexSkill
    Write-Log "Installing Claude Code skill to $claudeSkill"
    Copy-InstalledSkill $claudeSkill
}

function Remove-Skills {
    foreach ($base in @(".codex", ".claude")) {
        $skillDir = Join-Path (Join-Path (Join-Path $env:USERPROFILE $base) "skills") $SkillName
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $skillDir
        Write-Log "Removed $skillDir"
    }
}

function Get-NormalizedPathPart {
    param([string]$Path)
    try {
        return ([System.IO.Path]::GetFullPath($Path)).TrimEnd("\").ToLowerInvariant()
    } catch {
        return $Path.TrimEnd("\").ToLowerInvariant()
    }
}

function Add-UserPathEntry {
    param([string]$Entry)

    $normalizedEntry = Get-NormalizedPathPart $Entry
    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if (-not [string]::IsNullOrWhiteSpace($current)) {
        $parts = @($current -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    }
    foreach ($part in $parts) {
        if ((Get-NormalizedPathPart $part) -eq $normalizedEntry) {
            return
        }
    }
    $parts += [System.IO.Path]::GetFullPath($Entry)
    [Environment]::SetEnvironmentVariable("Path", ($parts -join ";"), "User")
    $env:Path = "$Entry;$env:Path"
    Write-Log "Added $Entry to the user PATH"
}

function Remove-UserPathEntry {
    param([string]$Entry)

    $normalizedEntry = Get-NormalizedPathPart $Entry
    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    if ([string]::IsNullOrWhiteSpace($current)) {
        return
    }
    $kept = New-Object System.Collections.Generic.List[string]
    foreach ($part in @($current -split ";")) {
        if ([string]::IsNullOrWhiteSpace($part)) {
            continue
        }
        if ((Get-NormalizedPathPart $part) -ne $normalizedEntry) {
            $kept.Add($part)
        }
    }
    [Environment]::SetEnvironmentVariable("Path", ($kept.ToArray() -join ";"), "User")
    Write-Log "Removed $Entry from the user PATH"
}

function Backup-File {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        $stamp = Get-Date -Format "yyyyMMddHHmmss"
        Copy-Item -LiteralPath $Path -Destination "$Path.bak-$stamp" -Force
    }
}

function Remove-CodexMcpTables {
    param([string[]]$Lines)

    $result = New-Object System.Collections.Generic.List[string]
    $skip = $false
    foreach ($line in $Lines) {
        if ($line -eq $CodexManagedBegin) {
            $skip = $true
            continue
        }
        if ($line -eq $CodexManagedEnd) {
            $skip = $false
            continue
        }
        if ($line -match '^\s*\[mcp_servers\.paper-fetch(?:\..*)?\]\s*$') {
            $skip = $true
            continue
        }
        if ($skip -and $line -match '^\s*\[') {
            $skip = $false
        }
        if (-not $skip) {
            $result.Add($line)
        }
    }
    return $result.ToArray()
}

function Write-CodexConfigToml {
    $codexHome = Join-Path $env:USERPROFILE ".codex"
    $configPath = Join-Path $codexHome "config.toml"
    New-Item -ItemType Directory -Force -Path $codexHome | Out-Null
    Backup-File $configPath

    $existing = @()
    if (Test-Path -LiteralPath $configPath -PathType Leaf) {
        $existing = Get-Content -LiteralPath $configPath
    }
    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($line in (Remove-CodexMcpTables $existing)) {
        $lines.Add($line)
    }

    $python = ConvertTo-FullPath (Get-RuntimePython)
    $lines.Add("")
    $lines.Add($CodexManagedBegin)
    $lines.Add("[mcp_servers.paper-fetch]")
    $lines.Add("command = $(ConvertTo-TomlString $python)")
    $lines.Add('args = ["-X", "utf8", "-m", "paper_fetch.mcp.server"]')
    $lines.Add("")
    $lines.Add("[mcp_servers.paper-fetch.env]")
    foreach ($entry in (Get-McpEnv).GetEnumerator()) {
        $lines.Add("$($entry.Key) = $(ConvertTo-TomlString ([string]$entry.Value))")
    }
    $lines.Add($CodexManagedEnd)
    [System.IO.File]::WriteAllLines($configPath, $lines, [System.Text.UTF8Encoding]::new($false))
    Write-Log "Updated Codex MCP config at $configPath"
}

function Remove-CodexConfigToml {
    $configPath = Join-Path (Join-Path $env:USERPROFILE ".codex") "config.toml"
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        return
    }
    Backup-File $configPath
    $lines = Remove-CodexMcpTables (Get-Content -LiteralPath $configPath)
    [System.IO.File]::WriteAllLines($configPath, $lines, [System.Text.UTF8Encoding]::new($false))
    Write-Log "Removed Codex MCP config from $configPath"
}

function Register-CodexMcp {
    $codex = Get-Command codex -ErrorAction SilentlyContinue
    $python = ConvertTo-FullPath (Get-RuntimePython)
    if ($null -ne $codex) {
        try {
            Write-Log "Registering Codex MCP server '$McpName' with Codex CLI"
            Invoke-Checked -FilePath $codex.Source -Arguments @("mcp", "remove", $McpName) -IgnoreFailure
            $args = @("mcp", "add")
            foreach ($entry in (Get-McpEnv).GetEnumerator()) {
                $args += @("--env", "$($entry.Key)=$($entry.Value)")
            }
            $args += @($McpName, "--", $python, "-X", "utf8", "-m", "paper_fetch.mcp.server")
            Invoke-Checked -FilePath $codex.Source -Arguments $args
            return
        } catch {
            Write-Warn "Codex CLI MCP registration failed; falling back to config.toml. $($_.Exception.Message)"
        }
    }
    Write-CodexConfigToml
}

function Unregister-CodexMcp {
    $codex = Get-Command codex -ErrorAction SilentlyContinue
    if ($null -ne $codex) {
        Invoke-Checked -FilePath $codex.Source -Arguments @("mcp", "remove", $McpName) -IgnoreFailure
    }
    Remove-CodexConfigToml
}

function Register-ClaudeMcp {
    $claude = Get-Command claude -ErrorAction SilentlyContinue
    if ($null -eq $claude) {
        Write-Log "Claude CLI not found; installed the skill and skipped Claude MCP registration"
        return
    }

    try {
        $python = ConvertTo-FullPath (Get-RuntimePython)
        Write-Log "Registering Claude MCP server '$McpName' with Claude CLI"
        Invoke-Checked -FilePath $claude.Source -Arguments @("mcp", "remove", "-s", "user", $McpName) -IgnoreFailure
        $args = @("mcp", "add", "-s", "user")
        foreach ($entry in (Get-McpEnv).GetEnumerator()) {
            $args += @("-e", "$($entry.Key)=$($entry.Value)")
        }
        $args += @($McpName, "--", $python, "-X", "utf8", "-m", "paper_fetch.mcp.server")
        Invoke-Checked -FilePath $claude.Source -Arguments $args
    } catch {
        Write-Warn "Claude MCP registration failed and was skipped. $($_.Exception.Message)"
    }
}

function Unregister-ClaudeMcp {
    $claude = Get-Command claude -ErrorAction SilentlyContinue
    if ($null -ne $claude) {
        Invoke-Checked -FilePath $claude.Source -Arguments @("mcp", "remove", "-s", "user", $McpName) -IgnoreFailure
    }
}

function Invoke-SmokeChecks {
    $python = ConvertTo-FullPath (Get-RuntimePython)
    $texmath = ConvertTo-FullPath (Join-Path (Join-Path $InstallRoot "formula-tools") "bin/texmath.exe")
    $playwright = ConvertTo-FullPath (Join-Path $InstallRoot "ms-playwright")

    Set-ProcessRuntimeEnv
    Write-Log "Running bundled Python smoke checks"
    Invoke-Checked -FilePath $python -Arguments @(
        "-X", "utf8", "-c",
        "import paper_fetch; from paper_fetch.mcp.tools import provider_status_payload; payload = provider_status_payload(); assert 'providers' in payload"
    )

    $playwrightCheck = @'
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright

root = Path(sys.argv[1]).resolve()
manager = sync_playwright().start()
try:
    executable = Path(manager.chromium.executable_path).resolve()
finally:
    manager.stop()

assert executable.is_file(), executable
assert root in executable.parents, (root, executable)
'@
    Invoke-Checked -FilePath $python -Arguments @("-X", "utf8", "-c", $playwrightCheck, $playwright)
    Invoke-Checked -FilePath $texmath -Arguments @("--help")
}

switch ($Action) {
    "Install" {
        Write-ManagedEnvFile
        Install-Skills
        Add-UserPathEntry (Join-Path $InstallRoot "bin")
        Register-CodexMcp
        Register-ClaudeMcp
        if (-not $SkipSmoke) {
            Invoke-SmokeChecks
        }
    }
    "Uninstall" {
        try { Remove-Skills } catch { Write-Warn $_.Exception.Message }
        try { Remove-UserPathEntry (Join-Path $InstallRoot "bin") } catch { Write-Warn $_.Exception.Message }
        try { Unregister-CodexMcp } catch { Write-Warn $_.Exception.Message }
        try { Unregister-ClaudeMcp } catch { Write-Warn $_.Exception.Message }
    }
    "Smoke" {
        Invoke-SmokeChecks
    }
}
