param(
    [ValidateSet("Install", "Uninstall", "Smoke")]
    [string]$Action = "Install",
    [string]$InstallRoot,
    [string]$LogPath,
    [switch]$SkipSmoke
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$SkillName = "paper-fetch-skill"
$McpName = "paper-fetch"
$OfflineManagedBegin = "# BEGIN paper-fetch offline managed"
$OfflineManagedEnd = "# END paper-fetch offline managed"
$CodexManagedBegin = "# BEGIN paper-fetch installer managed"
$CodexManagedEnd = "# END paper-fetch installer managed"
$McpEnvKeys = @(
    "PYTHONUTF8",
    "PYTHONIOENCODING",
    "PAPER_FETCH_ENV_FILE",
    "PAPER_FETCH_DOWNLOAD_DIR",
    "PAPER_FETCH_FORMULA_TOOLS_DIR",
    "PAPER_FETCH_IMAGE_TOOLS_DIR",
    "MATHML_TO_LATEX_NODE_BIN",
    "PAPER_FETCH_BROWSER_HEADLESS"
)
$OfflineEnvKeys = @($McpEnvKeys | Where-Object { $_ -ne "PAPER_FETCH_ENV_FILE" })
$InstallerWarnings = New-Object System.Collections.Generic.List[string]

if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
    $InstallRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
} else {
    $InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
}

function Import-InstallerManifest {
    $manifestPath = Join-Path $InstallRoot "installer/manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "Missing installer manifest: $manifestPath"
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $script:SkillName = [string]$manifest.skill.name
    $script:McpName = [string]$manifest.mcp.name
    $script:OfflineManagedBegin = [string]$manifest.managed_blocks.offline.begin
    $script:OfflineManagedEnd = [string]$manifest.managed_blocks.offline.end
    $script:CodexManagedBegin = [string]$manifest.managed_blocks.codex.begin
    $script:CodexManagedEnd = [string]$manifest.managed_blocks.codex.end
    $script:McpEnvKeys = @($manifest.mcp.env_keys | ForEach-Object { [string]$_ })
    Normalize-McpEnvKeys
    $script:OfflineEnvKeys = @(
        $script:McpEnvKeys | Where-Object { $_ -ne "PAPER_FETCH_ENV_FILE" }
    )

    if ([string]::IsNullOrWhiteSpace($script:SkillName) -or
        [string]::IsNullOrWhiteSpace($script:McpName) -or
        [string]::IsNullOrWhiteSpace($script:OfflineManagedBegin) -or
        [string]::IsNullOrWhiteSpace($script:OfflineManagedEnd) -or
        [string]::IsNullOrWhiteSpace($script:CodexManagedBegin) -or
        [string]::IsNullOrWhiteSpace($script:CodexManagedEnd) -or
        $script:McpEnvKeys.Count -eq 0 -or
        $script:OfflineEnvKeys.Count -eq 0) {
        throw "installer manifest is missing required installer constants."
    }
}

function Normalize-McpEnvKeys {
    $filtered = New-Object System.Collections.Generic.List[string]
    $seenHeadless = $false
    foreach ($key in $script:McpEnvKeys) {
        if ($key -in @(
            "PLAYWRIGHT_BROWSERS_PATH"
        )) {
            continue
        }
        if ($key -eq "PAPER_FETCH_BROWSER_HEADLESS") {
            $seenHeadless = $true
        }
        $filtered.Add($key)
    }
    if (-not $seenHeadless) {
        $filtered.Add("PAPER_FETCH_BROWSER_HEADLESS")
    }
    $script:McpEnvKeys = $filtered.ToArray()
}

Import-InstallerManifest

function Write-Log {
    param([string]$Message)
    Write-Host "==> $Message"
    Write-InstallerLogLine -Level "INFO" -Message $Message
}

function Write-Warn {
    param([string]$Message)
    Write-Warning $Message
    Write-InstallerLogLine -Level "WARN" -Message $Message
}

function Write-InstallerLogLine {
    param(
        [string]$Level,
        [string]$Message
    )

    if ([string]::IsNullOrWhiteSpace($LogPath)) {
        return
    }
    try {
        $logDir = Split-Path -Parent $LogPath
        if (-not [string]::IsNullOrWhiteSpace($logDir)) {
            New-Item -ItemType Directory -Force -Path $logDir | Out-Null
        }
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value "$timestamp [$Level] $Message"
    } catch {
        Write-Warning "Could not write installer helper log: $($_.Exception.Message)"
    }
}

function Invoke-InstallerStep {
    param(
        [string]$Name,
        [scriptblock]$ScriptBlock,
        [switch]$Required
    )

    try {
        & $ScriptBlock
    } catch {
        $message = "$Name failed: $($_.Exception.Message)"
        if ($Required) {
            throw $message
        }
        $script:InstallerWarnings.Add($message)
        Write-Warn $message
    }
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

function Invoke-RuntimePythonScript {
    param(
        [string]$Script,
        [string[]]$Arguments = @()
    )

    $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("paper-fetch-smoke-{0}.py" -f [System.Guid]::NewGuid().ToString("N"))
    try {
        [System.IO.File]::WriteAllText($scriptPath, $Script, [System.Text.UTF8Encoding]::new($false))
        Invoke-Checked -FilePath (ConvertTo-FullPath (Get-RuntimePython)) -Arguments (@("-X", "utf8", $scriptPath) + $Arguments)
    } finally {
        Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
    }
}

function Get-RuntimePython {
    return Join-Path (Join-Path $InstallRoot "runtime") "python.exe"
}

function Get-MathmlToLatexNode {
    return Join-Path $InstallRoot "runtime/Lib/site-packages/playwright/driver/node.exe"
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

function Quote-DotenvString {
    param([string]$Value)
    $escaped = $Value.Replace("'", "\'")
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
    $imageTools = Join-Path $InstallRoot "image-tools"

    $values = @{
        PYTHONUTF8 = "1"
        PYTHONIOENCODING = "utf-8"
        PAPER_FETCH_ENV_FILE = (ConvertTo-FullPath $offlineEnv)
        PAPER_FETCH_DOWNLOAD_DIR = (ConvertTo-FullPath $downloads)
        PAPER_FETCH_FORMULA_TOOLS_DIR = (ConvertTo-FullPath $formulaTools)
        PAPER_FETCH_IMAGE_TOOLS_DIR = (ConvertTo-FullPath $imageTools)
        MATHML_TO_LATEX_NODE_BIN = (ConvertTo-FullPath (Get-MathmlToLatexNode))
        PAPER_FETCH_BROWSER_HEADLESS = "true"
    }
    $ordered = [ordered]@{}
    foreach ($key in $McpEnvKeys) {
        if (-not $values.ContainsKey($key)) {
            throw "Unknown MCP env key in installer manifest: $key"
        }
        $ordered[$key] = $values[$key]
    }
    return $ordered
}

function Set-ProcessRuntimeEnv {
    foreach ($entry in (Get-McpEnv).GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, [string]$entry.Value, "Process")
    }
}

function Get-OfflineEnvValue {
    param([string]$Name)

    $envMap = Get-McpEnv
    if (-not $envMap.Contains($Name)) {
        throw "Unknown offline env key in installer manifest: $Name"
    }
    return [string]$envMap[$Name]
}

function Format-DotenvAssignment {
    param([string]$Name, [string]$Value)

    if ($Name -in @("PYTHONUTF8", "PYTHONIOENCODING", "PAPER_FETCH_BROWSER_HEADLESS")) {
        return "$Name=$(Quote-DotenvString $Value)"
    }
    return "$Name=$(Quote-DotenvValue $Value)"
}

function Remove-ManagedEnvBlock {
    param([string[]]$Lines)

    $result = New-Object System.Collections.Generic.List[string]
    $skip = $false
    foreach ($line in $Lines) {
        if ($line -eq $OfflineManagedBegin) {
            $skip = $true
            continue
        }
        if ($line -eq $OfflineManagedEnd) {
            $skip = $false
            continue
        }
        if (-not $skip) {
            $result.Add($line)
        }
    }
    return $result.ToArray()
}

function Write-ManagedEnvFile {
    $target = Join-Path $InstallRoot "offline.env"
    $lines = New-Object System.Collections.Generic.List[string]
    if (Test-Path -LiteralPath $target -PathType Leaf) {
        $existing = Get-Content -LiteralPath $target
        foreach ($line in (Remove-ManagedEnvBlock $existing)) {
            $lines.Add($line)
        }
    } elseif (Test-Path -LiteralPath (Join-Path $InstallRoot ".env.example") -PathType Leaf) {
        foreach ($line in Get-Content -LiteralPath (Join-Path $InstallRoot ".env.example")) {
            $lines.Add($line)
        }
    } else {
        $lines.Add('ELSEVIER_API_KEY=""')
    }
    $lines.Add("")
    $lines.Add($OfflineManagedBegin)
    foreach ($name in $OfflineEnvKeys) {
        $value = [string](Get-OfflineEnvValue $name)
        $lines.Add((Format-DotenvAssignment -Name $name -Value $value))
    }
    $lines.Add($OfflineManagedEnd)
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
    Test-SkillBundleIntegrity -SkillDir $Destination
}

function Test-SkillBundleIntegrity {
    param([string]$SkillDir)

    $manifestPath = Join-Path $InstallRoot "offline-manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "Missing offline manifest: $manifestPath"
    }
    $verifier = Join-Path $InstallRoot "scripts/skill_integrity.py"
    if (-not (Test-Path -LiteralPath $verifier -PathType Leaf)) {
        throw "Missing Skill verifier: $verifier"
    }
    Invoke-Checked -FilePath (ConvertTo-FullPath (Get-RuntimePython)) -Arguments @(
        "-X", "utf8", $verifier, "verify", "--manifest", $manifestPath,
        "--skill-dir", $SkillDir
    )
}

function Get-AntigravityHome {
    if (-not [string]::IsNullOrWhiteSpace($env:ANTIGRAVITY_HOME)) {
        return $env:ANTIGRAVITY_HOME
    }
    return (Join-Path (Join-Path $env:USERPROFILE ".gemini") "antigravity-cli")
}

function Install-Skills {
    $codexSkill = Join-Path (Join-Path (Join-Path $env:USERPROFILE ".codex") "skills") $SkillName
    $claudeSkill = Join-Path (Join-Path (Join-Path $env:USERPROFILE ".claude") "skills") $SkillName
    $antigravitySkill = Join-Path (Join-Path (Get-AntigravityHome) "skills") $SkillName

    Write-Log "Installing Codex skill to $codexSkill"
    Copy-InstalledSkill $codexSkill
    Write-Log "Installing Claude Code skill to $claudeSkill"
    Copy-InstalledSkill $claudeSkill
    Write-Log "Installing Antigravity skill to $antigravitySkill"
    Copy-InstalledSkill $antigravitySkill
}

function Remove-Skills {
    $codexSkill = Join-Path (Join-Path (Join-Path $env:USERPROFILE ".codex") "skills") $SkillName
    $claudeSkill = Join-Path (Join-Path (Join-Path $env:USERPROFILE ".claude") "skills") $SkillName
    $antigravitySkill = Join-Path (Join-Path (Get-AntigravityHome) "skills") $SkillName
    foreach ($skillDir in @($codexSkill, $claudeSkill, $antigravitySkill)) {
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
    $mcpTablePattern = '^\s*\[mcp_servers\.' + [regex]::Escape($McpName) + '(?:\..*)?\]\s*$'
    foreach ($line in $Lines) {
        if ($line -eq $CodexManagedBegin) {
            $skip = $true
            continue
        }
        if ($line -eq $CodexManagedEnd) {
            $skip = $false
            continue
        }
        if ($line -match $mcpTablePattern) {
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
    $lines.Add("[mcp_servers.$McpName]")
    $lines.Add("command = $(ConvertTo-TomlString $python)")
    $lines.Add('args = ["-X", "utf8", "-m", "paper_fetch.mcp.server"]')
    $lines.Add("")
    $lines.Add("[mcp_servers.$McpName.env]")
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
        $args += @("--", $McpName, $python, "-X", "utf8", "-m", "paper_fetch.mcp.server")
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

function Register-AntigravityMcp {
    # Antigravity has no `mcp add` CLI; it reads servers from mcp_config.json.
    $agHome = Get-AntigravityHome
    $configPath = Join-Path $agHome "mcp_config.json"
    New-Item -ItemType Directory -Force -Path $agHome | Out-Null
    Backup-File $configPath

    $python = ConvertTo-FullPath (Get-RuntimePython)
    $envMap = [ordered]@{}
    foreach ($entry in (Get-McpEnv).GetEnumerator()) {
        $envMap[$entry.Key] = [string]$entry.Value
    }
    $envJson = ($envMap | ConvertTo-Json -Compress -Depth 5)

    [Environment]::SetEnvironmentVariable("PF_CONFIG_PATH", (ConvertTo-FullPath $configPath), "Process")
    [Environment]::SetEnvironmentVariable("PF_MCP_NAME", $McpName, "Process")
    [Environment]::SetEnvironmentVariable("PF_PYTHON_BIN", $python, "Process")
    [Environment]::SetEnvironmentVariable("PF_ENV_JSON", $envJson, "Process")
    try {
        Write-Log "Registering Antigravity MCP server '$McpName' in $configPath"
        Invoke-RuntimePythonScript -Script @'
import json
import os
from pathlib import Path

path = Path(os.environ["PF_CONFIG_PATH"])
name = os.environ["PF_MCP_NAME"]

data = {}
if path.exists():
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Existing {path} is not valid JSON: {exc}")
if not isinstance(data, dict):
    raise SystemExit(f"Existing {path} must contain a JSON object")

servers = data.setdefault("mcpServers", {})
if not isinstance(servers, dict):
    raise SystemExit(f"'mcpServers' in {path} must be a JSON object")

env = json.loads(os.environ.get("PF_ENV_JSON") or "{}")
entry = {
    "command": os.environ["PF_PYTHON_BIN"],
    "args": ["-X", "utf8", "-m", "paper_fetch.mcp.server"],
}
if env:
    entry["env"] = env

servers[name] = entry
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
'@
    } finally {
        foreach ($key in @("PF_CONFIG_PATH", "PF_MCP_NAME", "PF_PYTHON_BIN", "PF_ENV_JSON")) {
            [Environment]::SetEnvironmentVariable($key, $null, "Process")
        }
    }
    Write-Log "Updated Antigravity MCP config at $configPath"
}

function Unregister-AntigravityMcp {
    $configPath = Join-Path (Get-AntigravityHome) "mcp_config.json"
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        return
    }
    Backup-File $configPath

    [Environment]::SetEnvironmentVariable("PF_CONFIG_PATH", (ConvertTo-FullPath $configPath), "Process")
    [Environment]::SetEnvironmentVariable("PF_MCP_NAME", $McpName, "Process")
    try {
        Invoke-RuntimePythonScript -Script @'
import json
import os
from pathlib import Path

path = Path(os.environ["PF_CONFIG_PATH"])
name = os.environ["PF_MCP_NAME"]
try:
    data = json.loads(path.read_text(encoding="utf-8") or "{}")
except json.JSONDecodeError:
    raise SystemExit(0)
if not isinstance(data, dict):
    raise SystemExit(0)
servers = data.get("mcpServers")
if isinstance(servers, dict):
    servers.pop(name, None)
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
'@
    } finally {
        foreach ($key in @("PF_CONFIG_PATH", "PF_MCP_NAME")) {
            [Environment]::SetEnvironmentVariable($key, $null, "Process")
        }
    }
    Write-Log "Removed Antigravity MCP config from $configPath"
}

function Invoke-SmokeChecks {
    $texmath = ConvertTo-FullPath (Join-Path (Join-Path $InstallRoot "formula-tools") "bin/texmath.exe")
    $node = ConvertTo-FullPath (Get-MathmlToLatexNode)
    $gs = Join-Path (Join-Path $InstallRoot "image-tools") "bin/gswin64c.exe"
    $vips = Join-Path (Join-Path $InstallRoot "image-tools") "bin/vips.exe"

    Set-ProcessRuntimeEnv
    Write-Log "Running bundled Python smoke checks"
    Invoke-RuntimePythonScript -Script @'
import paper_fetch
from paper_fetch.mcp.fetch_tool import provider_status_payload

payload = provider_status_payload()
assert "providers" in payload
'@

    $browserRuntimeCheck = @'
import camoufox
import playwright
import pymupdf
from paper_fetch.providers.browser_runtime.camoufox_manager import CamoufoxBrowserManager

assert hasattr(camoufox, "Camoufox")
assert CamoufoxBrowserManager is not None
'@
    Invoke-RuntimePythonScript -Script $browserRuntimeCheck
    Invoke-Checked -FilePath $texmath -Arguments @("--help")
    Invoke-Checked -FilePath $node -Arguments @("--version")
    if (Test-Path -LiteralPath $gs -PathType Leaf) {
        Invoke-Checked -FilePath $gs -Arguments @("--version")
    }
    if (Test-Path -LiteralPath $vips -PathType Leaf) {
        Invoke-Checked -FilePath $vips -Arguments @("--version")
    }
}

switch ($Action) {
    "Install" {
        $bundledSkill = Join-Path (Join-Path $InstallRoot "skills") $SkillName
        Invoke-InstallerStep -Name "bundled skill integrity" -Required -ScriptBlock { Test-SkillBundleIntegrity -SkillDir $bundledSkill }
        Invoke-InstallerStep -Name "offline.env update" -Required -ScriptBlock { Write-ManagedEnvFile }
        Invoke-InstallerStep -Name "skill installation" -Required -ScriptBlock { Install-Skills }
        Invoke-InstallerStep -Name "PATH update" -ScriptBlock { Add-UserPathEntry (Join-Path $InstallRoot "bin") }
        Invoke-InstallerStep -Name "Codex MCP registration" -ScriptBlock { Register-CodexMcp }
        Invoke-InstallerStep -Name "Claude MCP registration" -ScriptBlock { Register-ClaudeMcp }
        Invoke-InstallerStep -Name "Antigravity MCP registration" -ScriptBlock { Register-AntigravityMcp }
        if (-not $SkipSmoke) {
            Invoke-InstallerStep -Name "smoke checks" -ScriptBlock { Invoke-SmokeChecks }
        }
        if ($InstallerWarnings.Count -gt 0) {
            Write-Warn "Install helper completed with $($InstallerWarnings.Count) non-critical warning(s)."
            exit 2
        }
    }
    "Uninstall" {
        try { Remove-Skills } catch { Write-Warn $_.Exception.Message }
        try { Remove-UserPathEntry (Join-Path $InstallRoot "bin") } catch { Write-Warn $_.Exception.Message }
        try { Unregister-CodexMcp } catch { Write-Warn $_.Exception.Message }
        try { Unregister-ClaudeMcp } catch { Write-Warn $_.Exception.Message }
        try { Unregister-AntigravityMcp } catch { Write-Warn $_.Exception.Message }
    }
    "Smoke" {
        $bundledSkill = Join-Path (Join-Path $InstallRoot "skills") $SkillName
        Test-SkillBundleIntegrity -SkillDir $bundledSkill
        Invoke-SmokeChecks
    }
}

exit 0
