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
$OfflineManagedBegin = "# BEGIN paper-fetch offline managed"
$OfflineManagedEnd = "# END paper-fetch offline managed"
$RuntimeEnvKeys = @(
    "PYTHONUTF8",
    "PYTHONIOENCODING",
    "PAPER_FETCH_ENV_FILE",
    "PAPER_FETCH_DOWNLOAD_DIR",
    "PAPER_FETCH_FORMULA_TOOLS_DIR",
    "PAPER_FETCH_IMAGE_TOOLS_DIR",
    "MATHML_TO_LATEX_NODE_BIN",
    "PLAYWRIGHT_NODEJS_PATH",
    "PAPER_FETCH_BROWSER_HEADLESS"
)
$OfflineEnvKeys = @($RuntimeEnvKeys | Where-Object { $_ -ne "PAPER_FETCH_ENV_FILE" })
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
    $script:OfflineManagedBegin = [string]$manifest.managed_blocks.offline.begin
    $script:OfflineManagedEnd = [string]$manifest.managed_blocks.offline.end
    $script:RuntimeEnvKeys = @($manifest.runtime.env_keys | ForEach-Object { [string]$_ })
    Normalize-RuntimeEnvKeys
    $script:OfflineEnvKeys = @(
        $script:RuntimeEnvKeys | Where-Object { $_ -ne "PAPER_FETCH_ENV_FILE" }
    )

    if ([string]::IsNullOrWhiteSpace($script:SkillName) -or
        [string]::IsNullOrWhiteSpace($script:OfflineManagedBegin) -or
        [string]::IsNullOrWhiteSpace($script:OfflineManagedEnd) -or
        $script:RuntimeEnvKeys.Count -eq 0 -or
        $script:OfflineEnvKeys.Count -eq 0) {
        throw "installer manifest is missing required installer constants."
    }
}

function Normalize-RuntimeEnvKeys {
    $filtered = New-Object System.Collections.Generic.List[string]
    $seenHeadless = $false
    foreach ($key in $script:RuntimeEnvKeys) {
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
    $script:RuntimeEnvKeys = $filtered.ToArray()
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
    return Join-Path $InstallRoot "runtime/node/node.exe"
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

function Get-RuntimeEnv {
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
        PLAYWRIGHT_NODEJS_PATH = (ConvertTo-FullPath (Get-MathmlToLatexNode))
        PAPER_FETCH_BROWSER_HEADLESS = "true"
    }
    $ordered = [ordered]@{}
    foreach ($key in $RuntimeEnvKeys) {
        if (-not $values.ContainsKey($key)) {
            throw "Unknown runtime env key in installer manifest: $key"
        }
        $ordered[$key] = $values[$key]
    }
    return $ordered
}

function Set-ProcessRuntimeEnv {
    foreach ($entry in (Get-RuntimeEnv).GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, [string]$entry.Value, "Process")
    }
}

function Get-OfflineEnvValue {
    param([string]$Name)

    $envMap = Get-RuntimeEnv
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
    $codexSkill = Join-Path (Join-Path (Join-Path $env:USERPROFILE ".agents") "skills") $SkillName
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
    $codexSkill = Join-Path (Join-Path (Join-Path $env:USERPROFILE ".agents") "skills") $SkillName
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

function Invoke-SmokeChecks {
    $texmath = ConvertTo-FullPath (Join-Path (Join-Path $InstallRoot "formula-tools") "bin/texmath.exe")
    $node = ConvertTo-FullPath (Get-MathmlToLatexNode)
    $gs = Join-Path (Join-Path $InstallRoot "image-tools") "bin/gswin64c.exe"
    $vips = Join-Path (Join-Path $InstallRoot "image-tools") "bin/vips.exe"

    Set-ProcessRuntimeEnv
    Write-Log "Running bundled Python smoke checks"
    Invoke-RuntimePythonScript -Script @'
import paper_fetch
from paper_fetch.diagnostics import provider_status_payload

payload = provider_status_payload()
assert "providers" in payload
'@

    $browserRuntimeCheck = @'
import playwright
import pymupdf
from paper_fetch.providers.browser_runtime.preparation import verify_package_installation; verify_package_installation()
'@
    Invoke-RuntimePythonScript -Script $browserRuntimeCheck
    Invoke-RuntimePythonScript -Arguments @($texmath) -Script @'
import subprocess
import sys

result = subprocess.run([sys.argv[1], "--version"], capture_output=True, text=True, errors="replace")
if result.returncode:
    print(f"texmath smoke check failed (exit {result.returncode}):", file=sys.stderr)
    print(result.stdout + result.stderr, file=sys.stderr)
    raise SystemExit(result.returncode)
'@
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
    }
    "Smoke" {
        $bundledSkill = Join-Path (Join-Path $InstallRoot "skills") $SkillName
        Test-SkillBundleIntegrity -SkillDir $bundledSkill
        Invoke-SmokeChecks
    }
}

exit 0
