param(
    [string]$PythonBin = $env:PAPER_FETCH_OFFLINE_PYTHON_BIN,
    [switch]$UserConfig,
    [switch]$NoUserConfig,
    [switch]$SkipSmoke
)

# Repo-local legacy Windows offline installer. Release users should run the
# Inno Setup .exe, which invokes scripts/windows-installer-helper.ps1.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($PythonBin)) {
    $PythonBin = "python"
}

$BundleRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$InstallerManifestPath = Join-Path $BundleRoot "installer/manifest.json"
$ManagedBegin = "# BEGIN paper-fetch offline managed"
$ManagedEnd = "# END paper-fetch offline managed"
$SkillName = "paper-fetch-skill"
$McpName = "paper-fetch"
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
$OfflineEnvKeys = @(
    "PAPER_FETCH_DOWNLOAD_DIR",
    "PAPER_FETCH_FORMULA_TOOLS_DIR",
    "PAPER_FETCH_IMAGE_TOOLS_DIR",
    "MATHML_TO_LATEX_NODE_BIN",
    "PAPER_FETCH_BROWSER_HEADLESS",
    "PYTHONUTF8",
    "PYTHONIOENCODING",
)

function Write-Log {
    param([string]$Message)
    Write-Host "==> $Message"
}

function Fail {
    param([string]$Message)
    throw $Message
}

function Import-InstallerManifest {
    if (-not (Test-Path -LiteralPath $InstallerManifestPath -PathType Leaf)) {
        Fail "Missing installer manifest: $InstallerManifestPath"
    }
    $manifest = Get-Content -LiteralPath $InstallerManifestPath -Raw | ConvertFrom-Json
    $script:ManagedBegin = [string]$manifest.managed_blocks.offline.begin
    $script:ManagedEnd = [string]$manifest.managed_blocks.offline.end
    $script:SkillName = [string]$manifest.skill.name
    $script:McpName = [string]$manifest.mcp.name
    $script:McpEnvKeys = @($manifest.mcp.env_keys | ForEach-Object { [string]$_ })
    if ($null -ne $manifest.env_sets -and $null -ne $manifest.env_sets.offline_env_keys) {
        $script:OfflineEnvKeys = @($manifest.env_sets.offline_env_keys | ForEach-Object { [string]$_ })
    }
    Normalize-McpEnvKeys

    if ([string]::IsNullOrWhiteSpace($script:ManagedBegin) -or
        [string]::IsNullOrWhiteSpace($script:ManagedEnd) -or
        [string]::IsNullOrWhiteSpace($script:SkillName) -or
        [string]::IsNullOrWhiteSpace($script:McpName) -or
        $script:McpEnvKeys.Count -eq 0 -or
        $script:OfflineEnvKeys.Count -eq 0) {
        Fail "installer manifest is missing required installer constants."
    }
}

function Normalize-McpEnvKeys {
    $filtered = New-Object System.Collections.Generic.List[string]
    $seenHeadless = $false
    foreach ($key in $script:McpEnvKeys) {
        if ($key -in @(
            "PLAYWRIGHT_BROWSERS_PATH",
            "CLOAKBROWSER_BINARY_PATH",
            "CLOAKBROWSER_PROFILE_DIR",
            "CLOAKBROWSER_USER_DATA_DIR"
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

function Quote-DotenvString {
    param([string]$Value)
    $escaped = $Value.Replace("'", "\'")
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
    Require-File (Join-Path $BundleRoot "formula-tools/bin/texmath.exe")
    $cloakbrowserWheels = @(Get-ChildItem -Path (Join-Path $BundleRoot "wheelhouse") -Filter "cloakbrowser-*.whl" -ErrorAction SilentlyContinue)
    if ($cloakbrowserWheels.Count -eq 0) {
        Fail "Bundled wheelhouse is missing cloakbrowser-*.whl."
    }
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

    Write-Log "Installing paper-fetch-skill from bundled wheelhouse"
    & $venvPython -m pip install --no-index --find-links (Join-Path $BundleRoot "wheelhouse") --only-binary=:all: $ProjectWheel
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed to install paper-fetch-skill from bundled wheelhouse."
    }
}

function Get-OfflineEnvValue {
    param([string]$Name)

    switch ($Name) {
        "PAPER_FETCH_DOWNLOAD_DIR" { return (Join-Path $BundleRoot "downloads") }
        "PAPER_FETCH_FORMULA_TOOLS_DIR" { return (Join-Path $BundleRoot "formula-tools") }
        "PAPER_FETCH_IMAGE_TOOLS_DIR" { return (Join-Path $BundleRoot "image-tools") }
        "MATHML_TO_LATEX_NODE_BIN" { return (Join-Path $BundleRoot ".venv/Lib/site-packages/playwright/driver/node.exe") }
        "PAPER_FETCH_BROWSER_HEADLESS" { return "true" }
        "PYTHONUTF8" { return "1" }
        "PYTHONIOENCODING" { return "utf-8" }
        default { Fail "Unknown offline env key in installer manifest: $Name" }
    }
}

function Format-DotenvAssignment {
    param([string]$Name, [string]$Value)

    if ($Name -in @("PYTHONUTF8", "PYTHONIOENCODING", "PAPER_FETCH_BROWSER_HEADLESS")) {
        return "$Name=$(Quote-DotenvString $Value)"
    }
    return "$Name=$(Quote-DotenvValue $Value)"
}

function New-ManagedEnvLines {
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("")
    $lines.Add($ManagedBegin)
    foreach ($name in $OfflineEnvKeys) {
        $lines.Add((Format-DotenvAssignment -Name $name -Value ([string](Get-OfflineEnvValue $name))))
    }
    $lines.Add("# Optional: connect to an already-running Chrome/CloakBrowser CDP endpoint.")
    $lines.Add("# CLOAKBROWSER_CDP_ENDPOINT='ws://127.0.0.1:9222/devtools/browser/...'")
    $lines.Add("# Optional: use a preinstalled Chrome/CloakBrowser binary instead of cloakbrowser download.")
    $lines.Add("# CLOAKBROWSER_BINARY_PATH='C:/path/to/chrome.exe'")
    $lines.Add($ManagedEnd)
    return $lines.ToArray()
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
$imageBin = Join-Path $InstallRoot "image-tools/bin"
$env:PATH = "$venvScripts;$formulaBin;$imageBin;$env:PATH"
if ([string]::IsNullOrWhiteSpace($env:PAPER_FETCH_DOWNLOAD_DIR)) {
    $env:PAPER_FETCH_DOWNLOAD_DIR = Join-Path $InstallRoot "downloads"
}
if ([string]::IsNullOrWhiteSpace($env:PAPER_FETCH_FORMULA_TOOLS_DIR)) {
    $env:PAPER_FETCH_FORMULA_TOOLS_DIR = Join-Path $InstallRoot "formula-tools"
}
if ([string]::IsNullOrWhiteSpace($env:PAPER_FETCH_IMAGE_TOOLS_DIR)) {
    $env:PAPER_FETCH_IMAGE_TOOLS_DIR = Join-Path $InstallRoot "image-tools"
}
if ([string]::IsNullOrWhiteSpace($env:MATHML_TO_LATEX_NODE_BIN)) {
    $env:MATHML_TO_LATEX_NODE_BIN = Join-Path $InstallRoot ".venv/Lib/site-packages/playwright/driver/node.exe"
}
if ([string]::IsNullOrWhiteSpace($env:PAPER_FETCH_BROWSER_HEADLESS)) {
    $env:PAPER_FETCH_BROWSER_HEADLESS = "true"
}
if ([string]::IsNullOrWhiteSpace($env:PYTHONUTF8)) {
    $env:PYTHONUTF8 = "1"
}
if ([string]::IsNullOrWhiteSpace($env:PYTHONIOENCODING)) {
    $env:PYTHONIOENCODING = "utf-8"
}
'@
    [System.IO.File]::WriteAllText($target, $content, [System.Text.UTF8Encoding]::new($false))
}

function Test-BrowserRuntimePackage {
    $venvPython = Join-Path $BundleRoot ".venv/Scripts/python.exe"
    $code = @'
import cloakbrowser
import playwright
from paper_fetch.runtime_browser import BrowserContextManager

assert hasattr(cloakbrowser, "ensure_binary")
assert BrowserContextManager is not None
'@
    & $venvPython -c $code
    if ($LASTEXITCODE -ne 0) {
        Fail "Browser runtime package smoke check failed."
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
    & (Join-Path $BundleRoot ".venv/Lib/site-packages/playwright/driver/node.exe") --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Fail "bundled node.exe --version failed."
    }
    Test-BrowserRuntimePackage

    $env:PAPER_FETCH_ENV_FILE = Join-Path $BundleRoot "offline.env"
    $env:PAPER_FETCH_IMAGE_TOOLS_DIR = Join-Path $BundleRoot "image-tools"
    $env:MATHML_TO_LATEX_NODE_BIN = Join-Path $BundleRoot ".venv/Lib/site-packages/playwright/driver/node.exe"
    $env:PAPER_FETCH_BROWSER_HEADLESS = "true"
    & (Join-Path $BundleRoot ".venv/Scripts/python.exe") -c "from paper_fetch.mcp.fetch_tool import provider_status_payload; payload = provider_status_payload(); assert 'providers' in payload"
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

Import-InstallerManifest
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
$offlineEnv = Join-Path $BundleRoot "offline.env"
Write-Host "Activate it with: . $activateScript"
Write-Host "Default browser backend: Camoufox (headless: true)"
Write-Host "The first real fetch may download Camoufox; fully offline hosts must preinstall its complete runtime."
Write-Host "Use PAPER_FETCH_BROWSER_BACKEND=cloakbrowser only for deprecated compatibility."
Write-Host "Elsevier setup: request a key at https://dev.elsevier.com/, then add ELSEVIER_API_KEY=`"...`" to $offlineEnv before fetching Elsevier papers."
