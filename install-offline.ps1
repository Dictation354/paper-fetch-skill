param(
    [string]$PythonBin = $env:PAPER_FETCH_OFFLINE_PYTHON_BIN,
    [switch]$UserConfig,
    [switch]$NoUserConfig,
    [switch]$SkipSmoke
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($PythonBin)) {
    $PythonBin = "python"
}

$BundleRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$ManagedBegin = "# BEGIN paper-fetch offline managed"
$ManagedEnd = "# END paper-fetch offline managed"

function Write-Log {
    param([string]$Message)
    Write-Host "==> $Message"
}

function Fail {
    param([string]$Message)
    throw $Message
}

function Require-File {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Fail "Missing required bundled file: $Path"
    }
}

function Require-Dir {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        Fail "Missing required bundled directory: $Path"
    }
}

function ConvertTo-EnvPath {
    param([string]$Path)
    return [System.IO.Path]::GetFullPath($Path).Replace("\", "/")
}

function Quote-DotenvValue {
    param([string]$Value)
    $escaped = (ConvertTo-EnvPath $Value).Replace("'", "\'")
    return "'$escaped'"
}

function ConvertFrom-DotenvValue {
    param([string]$Value)
    $trimmed = $Value.Trim()
    if ($trimmed.Length -ge 2) {
        $first = $trimmed.Substring(0, 1)
        $last = $trimmed.Substring($trimmed.Length - 1, 1)
        if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
            return $trimmed.Substring(1, $trimmed.Length - 2)
        }
    }
    return $trimmed
}

function Test-RunningOnWindowsPlatform {
    if ($PSVersionTable.PSEdition -eq "Desktop") {
        return $true
    }
    $windowsVariable = Get-Variable -Name IsWindows -ErrorAction SilentlyContinue
    if ($null -ne $windowsVariable) {
        return [bool]$windowsVariable.Value
    }
    return [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT
}

function Get-WindowsProcessorArchitecture {
    $arch = $env:PROCESSOR_ARCHITEW6432
    if ([string]::IsNullOrWhiteSpace($arch)) {
        $arch = $env:PROCESSOR_ARCHITECTURE
    }
    if ([string]::IsNullOrWhiteSpace($arch)) {
        return "unknown"
    }
    return $arch
}

function Check-Platform {
    $runningOnWindows = Test-RunningOnWindowsPlatform
    if (-not $runningOnWindows) {
        Fail "This offline bundle supports Windows only."
    }
    $arch = Get-WindowsProcessorArchitecture
    if ($arch -ne "AMD64") {
        Fail "This offline bundle supports x86_64 only; detected $arch."
    }
}

function Invoke-PythonText {
    param([string]$Code, [string[]]$Arguments = @())
    $output = & $PythonBin -c $Code @Arguments
    if ($LASTEXITCODE -ne 0) {
        Fail "Python command failed with exit code $LASTEXITCODE."
    }
    return ($output -join "`n").Trim()
}

function Check-PythonAndManifest {
    $manifestPath = Join-Path $BundleRoot "offline-manifest.json"
    Require-File $manifestPath
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json

    if ($manifest.target.platform -ne "windows") {
        Fail "This installer requires a Windows bundle; manifest target.platform=$($manifest.target.platform)."
    }
    if ($manifest.target.arch -ne "x86_64") {
        Fail "This installer requires x86_64; manifest target.arch=$($manifest.target.arch)."
    }

    $version = Invoke-PythonText "import sys; print('.'.join(map(str, sys.version_info[:3])))"
    $tag = Invoke-PythonText "import sys; print(f'cp{sys.version_info.major}{sys.version_info.minor}' if sys.implementation.name == 'cpython' else sys.implementation.name)"
    $manifestTag = [string]$manifest.target.python_tag
    if ([string]::IsNullOrWhiteSpace($manifestTag)) {
        Fail "offline-manifest.json is missing target.python_tag."
    }
    if ($tag -ne $manifestTag) {
        Fail "bundle requires CPython $manifestTag; detected Python $version ($tag)."
    }
}

function Verify-Checksums {
    $checksumPath = Join-Path $BundleRoot "sha256sums.txt"
    Require-File $checksumPath
    Write-Log "Verifying bundled file checksums"

    foreach ($line in Get-Content -LiteralPath $checksumPath) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        if ($line -notmatch "^([A-Fa-f0-9]{64})\s+\*?(.+)$") {
            Fail "Invalid checksum line: $line"
        }
        $expected = $Matches[1].ToLowerInvariant()
        $relative = $Matches[2].Trim()
        if ($relative.StartsWith("./")) {
            $relative = $relative.Substring(2)
        }
        $path = Join-Path $BundleRoot ($relative.Replace("/", [System.IO.Path]::DirectorySeparatorChar))
        Require-File $path
        $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $expected) {
            Fail "Checksum mismatch for $relative"
        }
    }
}

function Find-ProjectWheel {
    $wheels = @(Get-ChildItem -Path (Join-Path $BundleRoot "dist") -Filter "paper_fetch_skill-*.whl" -ErrorAction SilentlyContinue)
    if ($wheels.Count -eq 0) {
        $wheels = @(Get-ChildItem -Path (Join-Path $BundleRoot "wheelhouse") -Filter "paper_fetch_skill-*.whl" -ErrorAction SilentlyContinue)
    }
    if ($wheels.Count -ne 1) {
        Fail "Expected exactly one paper_fetch_skill wheel, found $($wheels.Count)."
    }
    return $wheels[0].FullName
}

function Check-BundleAssets {
    Require-Dir (Join-Path $BundleRoot "wheelhouse")
    Require-Dir (Join-Path $BundleRoot "ms-playwright")
    Require-File (Join-Path $BundleRoot "formula-tools/bin/texmath.exe")

    $flaresolverrDir = Join-Path $BundleRoot "vendor/flaresolverr"
    Require-Dir $flaresolverrDir
    Require-File (Join-Path $flaresolverrDir ".env.flaresolverr-source-windows")
    Require-File (Join-Path $flaresolverrDir "flaresolverr_source_common.ps1")
    Require-File (Join-Path $flaresolverrDir "start_flaresolverr_source.ps1")
    Require-File (Join-Path $flaresolverrDir "stop_flaresolverr_source.ps1")
    Require-File (Join-Path $BundleRoot "scripts/flaresolverr-up.ps1")
    Require-File (Join-Path $BundleRoot "scripts/flaresolverr-down.ps1")
    Require-File (Join-Path $BundleRoot "scripts/flaresolverr-status.ps1")
    Require-File (Join-Path $flaresolverrDir ".flaresolverr/v3.4.6/flaresolverr/flaresolverr.exe")
    Require-File (Join-Path $flaresolverrDir ".flaresolverr/v3.4.6/flaresolverr/_internal/chrome/chrome.exe")
}

function Install-ProjectVenv {
    param([string]$ProjectWheel)

    $venvDir = Join-Path $BundleRoot ".venv"
    $venvPython = Join-Path $venvDir "Scripts/python.exe"
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Log "Creating Python virtual environment at $venvDir"
        & $PythonBin -m venv $venvDir
        if ($LASTEXITCODE -ne 0) {
            Fail "Failed to create virtual environment."
        }
    }

    $env:PIP_NO_INDEX = "1"
    $env:PIP_FIND_LINKS = Join-Path $BundleRoot "wheelhouse"
    $env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
    $env:PIP_NO_BUILD_ISOLATION = "1"
    $env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1"
    $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $BundleRoot "ms-playwright"

    $userCache = Join-Path $env:USERPROFILE ".cache/ms-playwright"
    if ($env:PLAYWRIGHT_BROWSERS_PATH.StartsWith($userCache, [System.StringComparison]::OrdinalIgnoreCase)) {
        Fail "PLAYWRIGHT_BROWSERS_PATH must not point at the user cache: $($env:PLAYWRIGHT_BROWSERS_PATH)"
    }

    Write-Log "Installing paper-fetch-skill from bundled wheelhouse"
    & $venvPython -m pip install --no-index --find-links (Join-Path $BundleRoot "wheelhouse") --only-binary=:all: $ProjectWheel
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed to install paper-fetch-skill from bundled wheelhouse."
    }
}

function New-ManagedEnvLines {
    $flaresolverrEnv = Join-Path $BundleRoot "vendor/flaresolverr/.env.flaresolverr-source-windows"
    $downloadDir = Join-Path $BundleRoot "downloads"
    $formulaToolsDir = Join-Path $BundleRoot "formula-tools"
    $playwrightDir = Join-Path $BundleRoot "ms-playwright"
    $flaresolverrDir = Join-Path $BundleRoot "vendor/flaresolverr"
    return @(
        "",
        $ManagedBegin,
        "PAPER_FETCH_DOWNLOAD_DIR=$(Quote-DotenvValue $downloadDir)",
        "PAPER_FETCH_FORMULA_TOOLS_DIR=$(Quote-DotenvValue $formulaToolsDir)",
        "PLAYWRIGHT_BROWSERS_PATH=$(Quote-DotenvValue $playwrightDir)",
        "FLARESOLVERR_URL='http://127.0.0.1:8191/v1'",
        "FLARESOLVERR_ENV_FILE=$(Quote-DotenvValue $flaresolverrEnv)",
        "FLARESOLVERR_SOURCE_DIR=$(Quote-DotenvValue $flaresolverrDir)",
        $ManagedEnd
    )
}

function Write-ManagedEnvFile {
    param([string]$Target)

    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Target) | Out-Null
    $existing = @()
    if (Test-Path -LiteralPath $Target) {
        $existing = Get-Content -LiteralPath $Target
    } elseif (Test-Path -LiteralPath (Join-Path $BundleRoot ".env.example")) {
        $existing = Get-Content -LiteralPath (Join-Path $BundleRoot ".env.example")
    }

    $lines = New-Object System.Collections.Generic.List[string]
    $skip = $false
    foreach ($line in $existing) {
        if ($line -eq $ManagedBegin) {
            $skip = $true
            continue
        }
        if ($line -eq $ManagedEnd) {
            $skip = $false
            continue
        }
        if (-not $skip) {
            $lines.Add($line)
        }
    }
    foreach ($line in (New-ManagedEnvLines)) {
        $lines.Add($line)
    }
    [System.IO.File]::WriteAllLines($Target, $lines, [System.Text.UTF8Encoding]::new($false))
}

function Write-ActivateScript {
    $target = Join-Path $BundleRoot "Activate-Offline.ps1"
    $content = @'
Set-StrictMode -Version Latest

$InstallRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
if ([string]::IsNullOrWhiteSpace($env:PAPER_FETCH_ENV_FILE)) {
    $env:PAPER_FETCH_ENV_FILE = Join-Path $InstallRoot "offline.env"
}

function ConvertFrom-OfflineEnvValue {
    param([string]$Value)
    $trimmed = $Value.Trim()
    if ($trimmed.Length -ge 2) {
        $first = $trimmed.Substring(0, 1)
        $last = $trimmed.Substring($trimmed.Length - 1, 1)
        if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
            return $trimmed.Substring(1, $trimmed.Length - 2)
        }
    }
    return $trimmed
}

if (Test-Path -LiteralPath $env:PAPER_FETCH_ENV_FILE) {
    foreach ($rawLine in Get-Content -LiteralPath $env:PAPER_FETCH_ENV_FILE) {
        $line = $rawLine.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            continue
        }
        $equalsIndex = $line.IndexOf("=")
        $key = $line.Substring(0, $equalsIndex).Trim()
        $value = ConvertFrom-OfflineEnvValue $line.Substring($equalsIndex + 1)
        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

$venvActivate = Join-Path $InstallRoot ".venv/Scripts/Activate.ps1"
if (Test-Path -LiteralPath $venvActivate) {
    . $venvActivate
}

$venvScripts = Join-Path $InstallRoot ".venv/Scripts"
$formulaBin = Join-Path $InstallRoot "formula-tools/bin"
$env:PATH = "$venvScripts;$formulaBin;$env:PATH"
if ([string]::IsNullOrWhiteSpace($env:PAPER_FETCH_FORMULA_TOOLS_DIR)) {
    $env:PAPER_FETCH_FORMULA_TOOLS_DIR = Join-Path $InstallRoot "formula-tools"
}
if ([string]::IsNullOrWhiteSpace($env:PLAYWRIGHT_BROWSERS_PATH)) {
    $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $InstallRoot "ms-playwright"
}
if ([string]::IsNullOrWhiteSpace($env:FLARESOLVERR_SOURCE_DIR)) {
    $env:FLARESOLVERR_SOURCE_DIR = Join-Path $InstallRoot "vendor/flaresolverr"
}
'@
    [System.IO.File]::WriteAllText($target, $content, [System.Text.UTF8Encoding]::new($false))
}

function Check-PlaywrightBrowser {
    $venvPython = Join-Path $BundleRoot ".venv/Scripts/python.exe"
    $root = Join-Path $BundleRoot "ms-playwright"
    $code = @'
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
    & $venvPython -c $code $root
    if ($LASTEXITCODE -ne 0) {
        Fail "Playwright resolved Chromium outside the offline bundle."
    }
}

function Run-SmokeChecks {
    if ($SkipSmoke) {
        return
    }

    Write-Log "Running local smoke checks"
    & (Join-Path $BundleRoot ".venv/Scripts/paper-fetch.exe") --help | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Fail "paper-fetch --help failed."
    }
    & (Join-Path $BundleRoot "formula-tools/bin/texmath.exe") --help | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Fail "texmath.exe --help failed."
    }
    Check-PlaywrightBrowser

    $env:PAPER_FETCH_ENV_FILE = Join-Path $BundleRoot "offline.env"
    $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $BundleRoot "ms-playwright"
    & (Join-Path $BundleRoot ".venv/Scripts/python.exe") -c "from paper_fetch.mcp.tools import provider_status_payload; payload = provider_status_payload(); assert 'providers' in payload"
    if ($LASTEXITCODE -ne 0) {
        Fail "provider_status_payload smoke check failed."
    }
}

function UserConfigPath {
    $base = $env:LOCALAPPDATA
    if ([string]::IsNullOrWhiteSpace($base)) {
        $base = Join-Path $env:USERPROFILE "AppData/Local"
    }
    return Join-Path $base "paper-fetch/.env"
}

if ($UserConfig -and $NoUserConfig) {
    Fail "Use only one of -UserConfig or -NoUserConfig."
}

Check-Platform
Check-PythonAndManifest
Verify-Checksums
Check-BundleAssets
$projectWheel = Find-ProjectWheel
Install-ProjectVenv $projectWheel

Write-Log "Writing repo-local offline.env"
Write-ManagedEnvFile (Join-Path $BundleRoot "offline.env")
Write-ActivateScript

if ($UserConfig) {
    $target = UserConfigPath
    Write-Log "Merging offline runtime block into $target"
    Write-ManagedEnvFile $target
}

Run-SmokeChecks

Write-Host ""
Write-Host "Offline installation complete."
$activateScript = Join-Path $BundleRoot "Activate-Offline.ps1"
$flaresolverrEnv = Join-Path $BundleRoot "vendor/flaresolverr/.env.flaresolverr-source-windows"
$offlineEnv = Join-Path $BundleRoot "offline.env"
Write-Host "Activate it with: . $activateScript"
Write-Host "FlareSolverr env: $flaresolverrEnv"
Write-Host "Elsevier setup: request a key at https://dev.elsevier.com/, then add ELSEVIER_API_KEY=`"...`" to $offlineEnv before fetching Elsevier papers."
