param(
    [string]$OutputDir,
    [string]$PackageName,
    [string]$PythonBin = "python",
    [string]$EmbeddedPythonVersion = "3.13.13",
    [string]$InnoCompiler
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$BuildDir = if ($env:PAPER_FETCH_OFFLINE_BUILD_DIR) {
    [System.IO.Path]::GetFullPath($env:PAPER_FETCH_OFFLINE_BUILD_DIR)
} else {
    Join-Path $RepoDir ".offline-build"
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $RepoDir "dist"
}

function Write-Log {
    param([string]$Message)
    Write-Host "==> $Message"
}

function Invoke-Native {
    if ($args.Count -lt 1) {
        throw "Invoke-Native requires a command."
    }
    $FilePath = [string]$args[0]
    $Arguments = @()
    if ($args.Count -gt 1) {
        $Arguments = @($args[1..($args.Count - 1)])
    }
    & $FilePath @Arguments | ForEach-Object { Write-Host $_ }
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Command failed with exit code ${exitCode}: $FilePath $($Arguments -join ' ')"
    }
}

function Get-PythonTag {
    $tag = & $PythonBin -c "import sys; sys.exit(1) if sys.implementation.name != 'cpython' else None; print(f'cp{sys.version_info.major}{sys.version_info.minor}')"
    if ($LASTEXITCODE -ne 0) {
        throw "Windows setup build requires CPython 3.13 x64."
    }
    return $tag.Trim()
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

function Assert-Target {
    $runningOnWindows = Test-RunningOnWindowsPlatform
    if (-not $runningOnWindows) {
        throw "Windows setup build must run on Windows."
    }
    $arch = Get-WindowsProcessorArchitecture
    if ($arch -ne "AMD64") {
        throw "Windows setup build currently targets x86_64 only; detected $arch."
    }
    $pythonTag = Get-PythonTag
    if ($pythonTag -ne "cp313") {
        throw "Windows setup build uses the CPython 3.13 embeddable runtime; build with CPython 3.13, detected $pythonTag."
    }
    return $pythonTag
}

function Get-ProjectVersion {
    $version = & $PythonBin -c "import pathlib, sys, tomllib; print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))['project']['version'])" (Join-Path $RepoDir "pyproject.toml")
    if ($LASTEXITCODE -ne 0) {
        throw "Could not read project version from pyproject.toml."
    }
    return $version.Trim()
}

function Copy-SourceSnapshot {
    param([string]$Staging)

    Write-Log "Copying source snapshot"
    New-Item -ItemType Directory -Force -Path $Staging | Out-Null
    $excludeDirs = @(
        ".git",
        ".venv",
        ".offline-build",
        ".formula-tools",
        ".pytest_cache",
        ".ruff_cache",
        "build",
        "dist",
        "tests",
        "live-downloads",
        "__pycache__",
        (Join-Path $RepoDir "vendor/flaresolverr/.work"),
        (Join-Path $RepoDir "vendor/flaresolverr/.venv-flaresolverr"),
        (Join-Path $RepoDir "vendor/flaresolverr/.flaresolverr"),
        (Join-Path $RepoDir "vendor/flaresolverr/run_logs"),
        (Join-Path $RepoDir "vendor/flaresolverr/probe_outputs")
    )
    & robocopy $RepoDir $Staging /E /XD @excludeDirs /NFL /NDL /NJH /NJS /NC /NS | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed with exit code $LASTEXITCODE."
    }
    $global:LASTEXITCODE = 0
}

function Build-ProjectWheelhouse {
    param([string]$Staging)

    $projectDist = Join-Path $BuildDir "project-dist"
    $wheelhouse = Join-Path $Staging "wheelhouse"
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $projectDist
    New-Item -ItemType Directory -Force -Path $projectDist, $wheelhouse, (Join-Path $Staging "dist") | Out-Null

    Write-Log "Building project wheel"
    Invoke-Native $PythonBin -m pip wheel --no-deps --wheel-dir $projectDist $RepoDir

    $wheels = @(Get-ChildItem -Path $projectDist -Filter "paper_fetch_skill-*.whl")
    if ($wheels.Count -ne 1) {
        throw "Expected one built project wheel, found $($wheels.Count)."
    }
    $projectWheelPath = $wheels[0].FullName
    Copy-Item -LiteralPath $projectWheelPath -Destination (Join-Path $Staging "dist")

    Write-Log "Downloading Windows dependency wheelhouse"
    Invoke-Native $PythonBin -m pip download --dest $wheelhouse --only-binary=:all: $projectWheelPath
}

function New-BuildVenv {
    param([string]$Staging)

    $buildVenv = Join-Path $BuildDir "build-venv-windows"
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $buildVenv
    Invoke-Native $PythonBin -m venv $buildVenv
    $buildPython = Join-Path $buildVenv "Scripts/python.exe"
    Invoke-Native $buildPython -m pip install --quiet --upgrade pip
    $projectWheel = @(Get-ChildItem -Path (Join-Path $Staging "dist") -Filter "paper_fetch_skill-*.whl")[0].FullName
    Invoke-Native $buildPython -m pip install --no-index --find-links (Join-Path $Staging "wheelhouse") $projectWheel
    return $buildPython
}

function Add-EmbeddedPythonRuntime {
    param([string]$Staging)

    $runtime = Join-Path $Staging "runtime"
    $archive = Join-Path $BuildDir "python-$EmbeddedPythonVersion-embed-amd64.zip"
    $url = "https://www.python.org/ftp/python/$EmbeddedPythonVersion/python-$EmbeddedPythonVersion-embed-amd64.zip"

    Write-Log "Downloading CPython $EmbeddedPythonVersion embeddable x64 runtime"
    if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $url -OutFile $archive
    }
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $runtime
    New-Item -ItemType Directory -Force -Path $runtime | Out-Null
    Expand-Archive -LiteralPath $archive -DestinationPath $runtime -Force

    $pth = Join-Path $runtime "python313._pth"
    if (-not (Test-Path -LiteralPath $pth -PathType Leaf)) {
        throw "Missing embeddable runtime _pth file: $pth"
    }
    $lines = New-Object System.Collections.Generic.List[string]
    $sawSitePackages = $false
    foreach ($line in Get-Content -LiteralPath $pth) {
        if ($line.Trim() -eq "Lib/site-packages") {
            $sawSitePackages = $true
        }
        if ($line.Trim() -eq "#import site") {
            if (-not $sawSitePackages) {
                $lines.Add("Lib/site-packages")
                $sawSitePackages = $true
            }
            $lines.Add("import site")
        } elseif ($line.Trim() -ne "import site") {
            $lines.Add($line)
        }
    }
    if (-not $sawSitePackages) {
        $lines.Add("Lib/site-packages")
    }
    if (-not ($lines -contains "import site")) {
        $lines.Add("import site")
    }
    [System.IO.File]::WriteAllLines($pth, $lines, [System.Text.UTF8Encoding]::new($false))
}

function Install-EmbeddedPythonPackages {
    param([string]$Staging)

    $runtime = Join-Path $Staging "runtime"
    $sitePackages = Join-Path $runtime "Lib/site-packages"
    $projectWheel = @(Get-ChildItem -Path (Join-Path $Staging "dist") -Filter "paper_fetch_skill-*.whl")[0].FullName
    New-Item -ItemType Directory -Force -Path $sitePackages | Out-Null

    Write-Log "Installing project and dependencies into embedded runtime"
    $previousSkip = $env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD
    try {
        $env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1"
        Invoke-Native $PythonBin -m pip install --no-index --find-links (Join-Path $Staging "wheelhouse") --target $sitePackages $projectWheel
    } finally {
        $env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = $previousSkip
    }

    $runtimePython = Join-Path $runtime "python.exe"
    Invoke-Native $runtimePython -X utf8 -c "import paper_fetch; import paper_fetch.mcp.server; print('embedded runtime ok')"
}

function Remove-BuildOnlyArtifacts {
    param([string]$Staging)

    Write-Log "Removing build-only wheel artifacts from Windows staging"
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $Staging "wheelhouse")
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $Staging "dist")
}

function Add-FormulaTools {
    param(
        [string]$Staging,
        [string]$BuildPython
    )

    Write-Log "Bundling formula tools"
    $target = Join-Path $Staging "formula-tools"
    Invoke-Native $BuildPython -m paper_fetch.formula.install --target-dir $target --no-node
    $texmath = Join-Path $target "bin/texmath.exe"
    if (-not (Test-Path -LiteralPath $texmath)) {
        throw "Missing bundled texmath.exe: $texmath"
    }
    Invoke-Native $texmath --help

    $stageNodeWorkspace = @'
from pathlib import Path
import sys

from paper_fetch.formula.install import stage_bundled_node_workspace

stage_bundled_node_workspace(Path(sys.argv[1]))
'@
    Invoke-Native $BuildPython -c $stageNodeWorkspace $target
}

function Add-PlaywrightChromium {
    param(
        [string]$Staging,
        [string]$BuildPython
    )

    Write-Log "Bundling Playwright Chromium"
    $previous = $env:PLAYWRIGHT_BROWSERS_PATH
    try {
        $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $Staging "ms-playwright"
        Invoke-Native $BuildPython -m playwright install chromium
    } finally {
        $env:PLAYWRIGHT_BROWSERS_PATH = $previous
    }
}

function Add-FlareSolverrBundle {
    param([string]$Staging)

    $flareVersion = "v3.4.6"
    $flareBuild = Join-Path $BuildDir "flaresolverr-windows-build"
    $flareRepo = Join-Path $flareBuild "FlareSolverr"
    $flareVenv = Join-Path $flareBuild ".venv-flaresolverr-build"
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $flareBuild
    New-Item -ItemType Directory -Force -Path $flareBuild | Out-Null

    Write-Log "Preparing patched FlareSolverr source"
    Invoke-Native git clone --depth 1 --branch $flareVersion https://github.com/FlareSolverr/FlareSolverr.git $flareRepo
    $patchPath = Join-Path $RepoDir "vendor/flaresolverr/patches/return-image-payload.patch"
    Invoke-Native git -C $flareRepo apply $patchPath
    if (-not (Select-String -Path (Join-Path $flareRepo "src/dtos.py") -Pattern "returnImagePayload" -Quiet)) {
        throw "Patched FlareSolverr source is missing returnImagePayload."
    }
    if (-not (Select-String -Path (Join-Path $flareRepo "src/flaresolverr_service.py") -Pattern "imagePayload" -Quiet)) {
        throw "Patched FlareSolverr source is missing imagePayload."
    }

    Write-Log "Building flaresolverr_windows_x64.zip from patched source"
    Invoke-Native $PythonBin -m venv $flareVenv
    $flarePython = Join-Path $flareVenv "Scripts/python.exe"
    Invoke-Native $flarePython -m pip install --upgrade pip setuptools wheel pyinstaller
    Invoke-Native $flarePython -m pip install -r (Join-Path $flareRepo "requirements.txt")
    Push-Location (Join-Path $flareRepo "src")
    try {
        Invoke-Native $flarePython ".\build_package.py"
    } finally {
        Pop-Location
    }

    $zipPath = Join-Path $flareRepo "dist/flaresolverr_windows_x64.zip"
    if (-not (Test-Path -LiteralPath $zipPath)) {
        throw "Missing built FlareSolverr Windows zip: $zipPath"
    }

    $releaseDir = Join-Path $Staging "vendor/flaresolverr/.flaresolverr/$flareVersion"
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $releaseDir
    New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
    Expand-Archive -LiteralPath $zipPath -DestinationPath $releaseDir -Force

    $exe = Join-Path $releaseDir "flaresolverr/flaresolverr.exe"
    $chrome = Join-Path $releaseDir "flaresolverr/_internal/chrome/chrome.exe"
    if (-not (Test-Path -LiteralPath $exe)) {
        throw "Missing extracted FlareSolverr executable: $exe"
    }
    if (-not (Test-Path -LiteralPath $chrome)) {
        throw "Missing extracted FlareSolverr Chromium executable: $chrome"
    }
}

function Write-CmdWrappers {
    param([string]$Staging)

    Write-Log "Writing command wrappers"
    $bin = Join-Path $Staging "bin"
    New-Item -ItemType Directory -Force -Path $bin | Out-Null

    $paperFetch = @'
@echo off
setlocal
set "PAPER_FETCH_ROOT=%~dp0.."
if not defined PAPER_FETCH_ENV_FILE set "PAPER_FETCH_ENV_FILE=%PAPER_FETCH_ROOT%\offline.env"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
"%PAPER_FETCH_ROOT%\runtime\python.exe" -X utf8 -m paper_fetch.cli %*
exit /b %ERRORLEVEL%
'@
    Set-Content -LiteralPath (Join-Path $bin "paper-fetch.cmd") -Value $paperFetch -Encoding ASCII

    $mcp = @'
@echo off
setlocal
set "PAPER_FETCH_ROOT=%~dp0.."
if not defined PAPER_FETCH_ENV_FILE set "PAPER_FETCH_ENV_FILE=%PAPER_FETCH_ROOT%\offline.env"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
"%PAPER_FETCH_ROOT%\runtime\python.exe" -X utf8 -m paper_fetch.mcp.server %*
exit /b %ERRORLEVEL%
'@
    Set-Content -LiteralPath (Join-Path $bin "paper-fetch-mcp.cmd") -Value $mcp -Encoding ASCII

    foreach ($name in @("up", "down", "status")) {
        $scriptName = "flaresolverr-$name.ps1"
        $wrapper = @"
@echo off
setlocal
set "PAPER_FETCH_ROOT=%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PAPER_FETCH_ROOT%\scripts\$scriptName" "%PAPER_FETCH_ROOT%\vendor\flaresolverr\.env.flaresolverr-source-windows" %*
exit /b %ERRORLEVEL%
"@
        Set-Content -LiteralPath (Join-Path $bin "flaresolverr-$name.cmd") -Value $wrapper -Encoding ASCII
    }
}

function Add-SkillAgentManifest {
    param([string]$Staging)

    $agentDir = Join-Path (Join-Path (Join-Path $Staging "skills") "paper-fetch-skill") "agents"
    New-Item -ItemType Directory -Force -Path $agentDir | Out-Null
    $content = @'
interface:
  display_name: "Paper Fetch Skill"
  short_description: "Fetch AI-friendly paper text by DOI, URL, or title"
  default_prompt: "Use $paper-fetch-skill whenever you need the text, readability, or full-text availability of a specific paper or a citation list of identifiable papers."
'@
    [System.IO.File]::WriteAllText((Join-Path $agentDir "openai.yaml"), $content, [System.Text.UTF8Encoding]::new($false))
}

function Write-DefaultOfflineEnv {
    param([string]$Staging)

    $content = @"
ELSEVIER_API_KEY=""

# BEGIN paper-fetch offline managed
PAPER_FETCH_DOWNLOAD_DIR='$($Staging.Replace("\", "/"))/downloads'
PAPER_FETCH_FORMULA_TOOLS_DIR='$($Staging.Replace("\", "/"))/formula-tools'
PLAYWRIGHT_BROWSERS_PATH='$($Staging.Replace("\", "/"))/ms-playwright'
FLARESOLVERR_URL='http://127.0.0.1:8191/v1'
FLARESOLVERR_ENV_FILE='$($Staging.Replace("\", "/"))/vendor/flaresolverr/.env.flaresolverr-source-windows'
FLARESOLVERR_SOURCE_DIR='$($Staging.Replace("\", "/"))/vendor/flaresolverr'
PYTHONUTF8='1'
PYTHONIOENCODING='utf-8'
# END paper-fetch offline managed
"@
    [System.IO.File]::WriteAllText((Join-Path $Staging "offline.env"), $content, [System.Text.UTF8Encoding]::new($false))
}

function Write-ManifestAndChecksums {
    param(
        [string]$Staging,
        [string]$Version,
        [string]$PythonTag
    )

    Write-Log "Writing standalone manifest and checksums"
    $gitRevision = ""
    try {
        $gitRevision = (& git -C $RepoDir rev-parse HEAD).Trim()
    } catch {
        $gitRevision = $null
    }

    $payload = [ordered]@{
        schema_version = 2
        name = "paper-fetch-skill-windows-setup"
        project = "paper-fetch-skill"
        version = $Version
        built_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        git_revision = $gitRevision
        target = [ordered]@{
            platform = "windows"
            arch = "x86_64"
            python_tag = $PythonTag
            python_runtime = "cpython-$EmbeddedPythonVersion-embed-amd64"
        }
        entrypoint = "paper-fetch-skill-windows-x86_64-setup.exe"
        components = [ordered]@{
            runtime = "runtime"
            bin = "bin"
            skills = "skills/paper-fetch-skill"
            project_wheels = @()
            wheelhouse_count = 0
            playwright_browsers = "ms-playwright"
            formula_tools = "formula-tools"
            flaresolverr = [ordered]@{
                release_version = "v3.4.6"
                runtime_bundle = "vendor/flaresolverr/.flaresolverr/v3.4.6/flaresolverr"
                executable = "vendor/flaresolverr/.flaresolverr/v3.4.6/flaresolverr/flaresolverr.exe"
                patch = "return-image-payload"
            }
            installer = [ordered]@{
                inno_setup = "installer/paper-fetch-skill.iss"
                post_install_helper = "scripts/windows-installer-helper.ps1"
            }
        }
    }
    $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $Staging "offline-manifest.json") -Encoding UTF8

    $checksumLines = Get-ChildItem -LiteralPath $Staging -Recurse -File |
        Where-Object { $_.Name -ne "sha256sums.txt" } |
        Sort-Object FullName |
        ForEach-Object {
            $relative = [System.IO.Path]::GetRelativePath($Staging, $_.FullName).Replace("\", "/")
            $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            "$hash  ./$relative"
        }
    $checksumLines | Set-Content -LiteralPath (Join-Path $Staging "sha256sums.txt") -Encoding ASCII
}

function Find-InnoCompiler {
    if (-not [string]::IsNullOrWhiteSpace($InnoCompiler)) {
        if (Test-Path -LiteralPath $InnoCompiler -PathType Leaf) {
            return [System.IO.Path]::GetFullPath($InnoCompiler)
        }
        $explicit = Get-Command $InnoCompiler -ErrorAction SilentlyContinue
        if ($null -ne $explicit) {
            return $explicit.Source
        }
        throw "Could not find Inno Setup compiler at $InnoCompiler."
    }

    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    foreach ($candidate in @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6/ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6/ISCC.exe")
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }
    throw "Inno Setup compiler (ISCC.exe) was not found. Install Inno Setup 6 or pass -InnoCompiler."
}

function Build-InnoInstaller {
    param(
        [string]$Staging,
        [string]$Version,
        [string]$SetupBaseName
    )

    $iscc = Find-InnoCompiler
    $script = Join-Path $RepoDir "installer/paper-fetch-skill.iss"
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    $setupPath = Join-Path $OutputDir "$SetupBaseName.exe"
    Remove-Item -Force -ErrorAction SilentlyContinue $setupPath

    Write-Log "Building Inno Setup installer"
    Invoke-Native $iscc "/DSourceDir=$Staging" "/DAppVersion=$Version" "/DOutputDir=$OutputDir" "/DSetupBaseName=$SetupBaseName" $script
    if (-not (Test-Path -LiteralPath $setupPath -PathType Leaf)) {
        throw "Missing built installer: $setupPath"
    }
    Write-Host $setupPath
}

$pythonTag = Assert-Target
if ([string]::IsNullOrWhiteSpace($PackageName)) {
    $PackageName = "paper-fetch-skill-windows-x86_64-setup"
}
$staging = Join-Path $BuildDir "paper-fetch-standalone"
$version = Get-ProjectVersion

Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $staging
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

Copy-SourceSnapshot $staging
Build-ProjectWheelhouse $staging
$buildPython = New-BuildVenv $staging
Add-EmbeddedPythonRuntime $staging
Install-EmbeddedPythonPackages $staging
Remove-BuildOnlyArtifacts $staging
Add-FormulaTools -Staging $staging -BuildPython $buildPython
Add-PlaywrightChromium -Staging $staging -BuildPython $buildPython
Add-FlareSolverrBundle $staging
Write-CmdWrappers $staging
Add-SkillAgentManifest $staging
Write-DefaultOfflineEnv $staging
Write-ManifestAndChecksums -Staging $staging -Version $version -PythonTag $pythonTag
Build-InnoInstaller -Staging $staging -Version $version -SetupBaseName $PackageName
