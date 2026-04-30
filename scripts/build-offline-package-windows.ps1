param(
    [string]$OutputDir,
    [string]$PackageName,
    [string]$PythonBin = "python"
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
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

function Get-PythonTag {
    $tag = & $PythonBin -c "import sys; sys.exit(1) if sys.implementation.name != 'cpython' else None; print(f'cp{sys.version_info.major}{sys.version_info.minor}')"
    if ($LASTEXITCODE -ne 0) {
        throw "Offline package build requires CPython 3.11, 3.12, 3.13, or 3.14."
    }
    return $tag.Trim()
}

function Test-SupportedPythonTag {
    param([string]$PythonTag)
    return $PythonTag -in @("cp311", "cp312", "cp313", "cp314")
}

function Assert-Target {
    $isWindows = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
        [System.Runtime.InteropServices.OSPlatform]::Windows
    )
    if (-not $isWindows) {
        throw "Windows offline package build must run on Windows."
    }
    $arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
    if ($arch -ne [System.Runtime.InteropServices.Architecture]::X64) {
        throw "Windows offline package build currently targets x86_64 only; detected $arch."
    }
    $pythonTag = Get-PythonTag
    if (-not (Test-SupportedPythonTag $pythonTag)) {
        throw "Offline package build requires CPython 3.11, 3.12, 3.13, or 3.14; detected $pythonTag."
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

function Write-ManifestAndChecksums {
    param(
        [string]$Staging,
        [string]$Version,
        [string]$PythonTag
    )

    Write-Log "Writing manifest and checksums"
    $gitRevision = ""
    try {
        $gitRevision = (& git -C $RepoDir rev-parse HEAD).Trim()
    } catch {
        $gitRevision = $null
    }

    $projectWheels = @(Get-ChildItem -Path (Join-Path $Staging "dist") -Filter "paper_fetch_skill-*.whl" | Sort-Object Name)
    $wheelhouse = @(Get-ChildItem -Path (Join-Path $Staging "wheelhouse") -Filter "*.whl")
    $payload = [ordered]@{
        schema_version = 1
        name = "paper-fetch-skill-offline"
        project = "paper-fetch-skill"
        version = $Version
        built_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        git_revision = $gitRevision
        target = [ordered]@{
            platform = "windows"
            arch = "x86_64"
            python_tag = $PythonTag
        }
        entrypoint = "install-offline.ps1"
        components = [ordered]@{
            source_snapshot = "."
            project_wheels = @($projectWheels | ForEach-Object { "dist/$($_.Name)" })
            wheelhouse_count = $wheelhouse.Count
            playwright_browsers = "ms-playwright"
            formula_tools = "formula-tools"
            flaresolverr = [ordered]@{
                release_version = "v3.4.6"
                runtime_bundle = "vendor/flaresolverr/.flaresolverr/v3.4.6/flaresolverr"
                executable = "vendor/flaresolverr/.flaresolverr/v3.4.6/flaresolverr/flaresolverr.exe"
                patch = "return-image-payload"
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

function New-ZipArchive {
    param(
        [string]$StagingParent,
        [string]$Name,
        [string]$DestinationDir
    )

    New-Item -ItemType Directory -Force -Path $DestinationDir | Out-Null
    $archive = Join-Path $DestinationDir "$Name.zip"
    Remove-Item -Force -ErrorAction SilentlyContinue $archive
    Write-Log "Creating zip archive"
    Push-Location $StagingParent
    try {
        Compress-Archive -Path $Name -DestinationPath $archive -Force
    } finally {
        Pop-Location
    }
    Write-Host $archive
}

$pythonTag = Assert-Target
if ([string]::IsNullOrWhiteSpace($PackageName)) {
    $PackageName = "paper-fetch-skill-offline-windows-x86_64-$pythonTag"
}
$staging = Join-Path $BuildDir $PackageName
$version = Get-ProjectVersion

Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $staging
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

Copy-SourceSnapshot $staging
Build-ProjectWheelhouse $staging
$buildPython = New-BuildVenv $staging
Add-FormulaTools -Staging $staging -BuildPython $buildPython
Add-PlaywrightChromium -Staging $staging -BuildPython $buildPython
Add-FlareSolverrBundle $staging
Write-ManifestAndChecksums -Staging $staging -Version $version -PythonTag $pythonTag
New-ZipArchive -StagingParent $BuildDir -Name $PackageName -DestinationDir $OutputDir
