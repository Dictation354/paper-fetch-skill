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
$InstallerManifestPath = Join-Path $RepoDir "installer/manifest.json"
$InstallerManifest = Get-Content -LiteralPath $InstallerManifestPath -Raw | ConvertFrom-Json
$SkillName = [string]$InstallerManifest.skill.name
$OfflineManagedBegin = [string]$InstallerManifest.managed_blocks.offline.begin
$OfflineManagedEnd = [string]$InstallerManifest.managed_blocks.offline.end
$WindowsSetupBaseName = [string]$InstallerManifest.packages.windows_setup_base_name
$BuildDir = if ($env:PAPER_FETCH_OFFLINE_BUILD_DIR) {
    [System.IO.Path]::GetFullPath($env:PAPER_FETCH_OFFLINE_BUILD_DIR)
} else {
    Join-Path $RepoDir ".offline-build"
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $RepoDir "dist"
}
$ProjectWheelPath = ""
$DependencyWheelhouse = ""

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

function Copy-RuntimeAssets {
    param([string]$Staging)

    Write-Log "Copying runtime installer assets"
    $installerDir = Join-Path $Staging "installer"
    $scriptsDir = Join-Path $Staging "scripts"
    $skillsDir = Join-Path $Staging "skills"
    New-Item -ItemType Directory -Force -Path $installerDir, $scriptsDir, $skillsDir | Out-Null

    Copy-Item -LiteralPath $InstallerManifestPath -Destination (Join-Path $installerDir "manifest.json")
    Copy-Item -LiteralPath (Join-Path (Join-Path $RepoDir "scripts") "windows-installer-helper.ps1") -Destination (Join-Path $scriptsDir "windows-installer-helper.ps1")

    $sourceSkill = Join-Path (Join-Path $RepoDir "skills") $SkillName
    if (-not (Test-Path -LiteralPath (Join-Path $sourceSkill "SKILL.md") -PathType Leaf)) {
        throw "Missing static skill source at $sourceSkill."
    }
    Copy-Item -LiteralPath $sourceSkill -Destination $skillsDir -Recurse
}

function Build-ProjectWheelhouse {
    $projectDist = Join-Path $BuildDir "project-dist"
    $wheelhouse = Join-Path $BuildDir "windows-runtime-wheelhouse"
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $projectDist, $wheelhouse
    New-Item -ItemType Directory -Force -Path $projectDist, $wheelhouse | Out-Null

    Write-Log "Building project wheel"
    Invoke-Native $PythonBin -m pip wheel --no-deps --wheel-dir $projectDist $RepoDir

    $wheels = @(Get-ChildItem -Path $projectDist -Filter "paper_fetch_skill-*.whl")
    if ($wheels.Count -ne 1) {
        throw "Expected one built project wheel, found $($wheels.Count)."
    }
    $projectWheelPath = $wheels[0].FullName
    $script:ProjectWheelPath = $projectWheelPath
    $script:DependencyWheelhouse = $wheelhouse

    Write-Log "Downloading Windows dependency wheelhouse"
    Invoke-Native $PythonBin -m pip download --dest $wheelhouse --only-binary=:all: $projectWheelPath
    $cloakbrowserWheels = @(Get-ChildItem -Path $wheelhouse -Filter "cloakbrowser-*.whl" -ErrorAction SilentlyContinue)
    if ($cloakbrowserWheels.Count -eq 0) {
        throw "Dependency wheelhouse is missing cloakbrowser-*.whl."
    }
}

function New-BuildVenv {
    $buildVenv = Join-Path $BuildDir "build-venv-windows"
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $buildVenv
    Invoke-Native $PythonBin -m venv $buildVenv
    $buildPython = Join-Path $buildVenv "Scripts/python.exe"
    Invoke-Native $buildPython -m pip install --quiet --upgrade pip
    if ([string]::IsNullOrWhiteSpace($script:ProjectWheelPath) -or [string]::IsNullOrWhiteSpace($script:DependencyWheelhouse)) {
        throw "Project wheelhouse must be built before creating the Windows build venv."
    }
    Invoke-Native $buildPython -m pip install --no-index --find-links $script:DependencyWheelhouse $script:ProjectWheelPath
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
    if ([string]::IsNullOrWhiteSpace($script:ProjectWheelPath) -or [string]::IsNullOrWhiteSpace($script:DependencyWheelhouse)) {
        throw "Project wheelhouse must be built before installing embedded runtime packages."
    }
    New-Item -ItemType Directory -Force -Path $sitePackages | Out-Null

    Write-Log "Installing project and dependencies into embedded runtime"
    $previousSkip = $env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD
    try {
        $env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1"
        Invoke-Native $PythonBin -m pip install --no-index --find-links $script:DependencyWheelhouse --only-binary=:all: --target $sitePackages $script:ProjectWheelPath
    } finally {
        $env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = $previousSkip
    }

    $runtimePython = Join-Path $runtime "python.exe"
    Invoke-Native $runtimePython -X utf8 -c "import paper_fetch; import paper_fetch.mcp.server; print('embedded runtime ok')"
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

function Add-ImageTools {
    param(
        [string]$Staging,
        [string]$BuildPython
    )

    Write-Log "Bundling image conversion tools"
    $target = Join-Path $Staging "image-tools"
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Invoke-Native $BuildPython -m paper_fetch.image_tools.install --target-dir $target --offline-bundle --repo-root $RepoDir
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

    $imageTools = @'
@echo off
setlocal
set "PAPER_FETCH_ROOT=%~dp0.."
"%PAPER_FETCH_ROOT%\runtime\python.exe" -X utf8 -m paper_fetch.image_tools.install %*
exit /b %ERRORLEVEL%
'@
    Set-Content -LiteralPath (Join-Path $bin "paper-fetch-install-image-tools.cmd") -Value $imageTools -Encoding ASCII
}

function Add-SkillAgentManifest {
    param([string]$Staging)

    $agentDir = Join-Path (Join-Path (Join-Path $Staging "skills") $SkillName) "agents"
    New-Item -ItemType Directory -Force -Path $agentDir | Out-Null
    $content = @"
interface:
  display_name: "$($InstallerManifest.skill.display_name)"
  short_description: "$($InstallerManifest.skill.short_description)"
  default_prompt: "$($InstallerManifest.skill.default_prompt)"
"@
    [System.IO.File]::WriteAllText((Join-Path $agentDir "openai.yaml"), $content, [System.Text.UTF8Encoding]::new($false))
}

function Write-DefaultOfflineEnv {
    param([string]$Staging)

    $content = @"
ELSEVIER_API_KEY=""

$OfflineManagedBegin
PAPER_FETCH_DOWNLOAD_DIR='$($Staging.Replace("\", "/"))/downloads'
PAPER_FETCH_FORMULA_TOOLS_DIR='$($Staging.Replace("\", "/"))/formula-tools'
PAPER_FETCH_IMAGE_TOOLS_DIR='$($Staging.Replace("\", "/"))/image-tools'
MATHML_TO_LATEX_NODE_BIN='$($Staging.Replace("\", "/"))/runtime/Lib/site-packages/playwright/driver/node.exe'
CLOAKBROWSER_HEADLESS='true'
PAPER_FETCH_BROWSER_USER_AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'
# Optional: connect to an already-running Chrome/CloakBrowser CDP endpoint.
# CLOAKBROWSER_CDP_ENDPOINT='ws://127.0.0.1:9222/devtools/browser/...'
# Optional: use a preinstalled Chrome/CloakBrowser binary instead of cloakbrowser download.
# CLOAKBROWSER_BINARY_PATH='C:/path/to/chrome.exe'
PYTHONUTF8='1'
PYTHONIOENCODING='utf-8'
$OfflineManagedEnd
"@
    [System.IO.File]::WriteAllText((Join-Path $Staging "offline.env"), $content, [System.Text.UTF8Encoding]::new($false))
}

function Write-OfflineReadme {
    param([string]$Staging)

    $content = @'
# Paper Fetch Windows Offline Installer

This installer includes the embedded Python runtime, installed Python packages, formula tools, and image-tools configuration for optional conversion tools.
The offline build does not bundle Ghostscript/libvips from the build host PATH; AMS EPS/TIFF source figure conversion falls back to webpage JPG/PNG candidates when those tools are unavailable.
It does not redistribute a browser binary for browser-backed providers; cloakbrowser downloads or locates Chrome on first use.
Formula conversion uses the bundled Playwright driver Node via `MATHML_TO_LATEX_NODE_BIN`; do not rely on a bare `node` from PATH in Codex Desktop sessions.

Browser-backed providers auto-start a managed cloakbrowser Chrome when `CLOAKBROWSER_CDP_ENDPOINT` is unset.
Set `CLOAKBROWSER_CDP_ENDPOINT` only when you want to reuse an already-running browser, or set `CLOAKBROWSER_BINARY_PATH` to use a preinstalled Chrome binary.
Set `CLOAKBROWSER_HEADLESS=false` only when running with a display-capable session.
'@
    [System.IO.File]::WriteAllText((Join-Path $Staging "README.offline.md"), $content, [System.Text.UTF8Encoding]::new($false))
}

function Write-ManifestAndChecksums {
    param(
        [string]$Staging,
        [string]$Version,
        [string]$PythonTag,
        [string]$SetupBaseName
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
        name = [string]$InstallerManifest.packages.windows_manifest_name
        project = [string]$InstallerManifest.project
        version = $Version
        built_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        git_revision = $gitRevision
        target = [ordered]@{
            platform = "windows"
            arch = "x86_64"
            python_tag = $PythonTag
            python_runtime = "cpython-$EmbeddedPythonVersion-embed-amd64"
        }
        entrypoint = "$SetupBaseName.exe"
        components = [ordered]@{
            runtime = "runtime"
            bin = "bin"
            skills = "skills/$SkillName"
            installer_manifest = "installer/manifest.json"
            command_wrappers = "bin"
            formula_tools = "formula-tools"
            image_tools = "image-tools"
            cloakbrowser = [ordered]@{
                python_package = "runtime/Lib/site-packages"
                browser_binary = "not_bundled"
            }
            installer = [ordered]@{
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

function Assert-RuntimeOnlyStaging {
    param([string]$Staging)

    Write-Log "Verifying Windows runtime-only staging layout"
    foreach ($relative in @(
        "runtime/python.exe",
        "runtime/Lib/site-packages/paper_fetch/__init__.py",
        "bin/paper-fetch.cmd",
        "bin/paper-fetch-mcp.cmd",
        "bin/paper-fetch-install-image-tools.cmd",
        "skills/$SkillName/SKILL.md",
        "installer/manifest.json",
        "scripts/windows-installer-helper.ps1"
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $Staging $relative))) {
            throw "Windows runtime staging is missing required path: $relative"
        }
    }

    foreach ($relative in @(
        "src",
        "tests",
        ".github",
        "wheelhouse",
        "dist",
        "pyproject.toml"
    )) {
        if (Test-Path -LiteralPath (Join-Path $Staging $relative)) {
            throw "Windows runtime staging must not include source/build path: $relative"
        }
    }
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
    $PackageName = $WindowsSetupBaseName
}
$staging = Join-Path $BuildDir "paper-fetch-standalone"
$version = Get-ProjectVersion

Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $staging
New-Item -ItemType Directory -Force -Path $BuildDir, $staging | Out-Null

Copy-RuntimeAssets $staging
Build-ProjectWheelhouse
$buildPython = New-BuildVenv
Add-EmbeddedPythonRuntime $staging
Install-EmbeddedPythonPackages $staging
Add-FormulaTools -Staging $staging -BuildPython $buildPython
Add-ImageTools -Staging $staging -BuildPython $buildPython
Write-CmdWrappers $staging
Add-SkillAgentManifest $staging
Write-DefaultOfflineEnv $staging
Write-OfflineReadme $staging
Assert-RuntimeOnlyStaging $staging
Write-ManifestAndChecksums -Staging $staging -Version $version -PythonTag $pythonTag -SetupBaseName $PackageName
Build-InnoInstaller -Staging $staging -Version $version -SetupBaseName $PackageName
