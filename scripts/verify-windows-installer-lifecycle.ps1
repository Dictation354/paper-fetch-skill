param(
    [Parameter(Mandatory = $true)]
    [string]$SetupPath,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedVersion,
    [string]$PreviousSetupPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$UninstallSuccessLogMarker = "Uninstallation process succeeded."

if (-not $IsWindows) {
    throw "The final EXE lifecycle gate must run on native Windows."
}
$SetupPath = [System.IO.Path]::GetFullPath($SetupPath)
if (-not (Test-Path -LiteralPath $SetupPath -PathType Leaf)) {
    throw "Missing final Windows installer: $SetupPath"
}
if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) {
    throw "RUNNER_TEMP is required for the isolated installer lifecycle gate."
}

function Invoke-NativeChecked {
    param(
        [string]$FilePath,
        [string[]]$Arguments = @(),
        [int[]]$AllowedExitCodes = @(0)
    )

    & $FilePath @Arguments | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -notin $AllowedExitCodes) {
        throw "Command failed with exit code $LASTEXITCODE`: $FilePath $($Arguments -join ' ')"
    }
}

function Invoke-InstalledSmoke {
    param([string]$InstallRoot)

    $cli = Join-Path $InstallRoot "bin/paper-fetch.cmd"
    $runtime = Join-Path $InstallRoot "runtime/python.exe"
    $helper = Join-Path $InstallRoot "scripts/windows-installer-helper.ps1"
    foreach ($path in @($cli, $runtime, $helper)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Installed smoke is missing $path"
        }
    }

    $runtimeCheck = @'
import json, os, subprocess, sys, tomllib
from pathlib import Path
root = Path(sys.argv[1])
pin = json.loads((root / "installer/manifest.json").read_text())["embedded_runtimes"]["windows_cpython_x86_64"]
assert sys.version.split()[0] == pin["version"]
assert (root / "runtime/python314._pth").is_file()
assert not (root / "runtime/python313._pth").exists()
assert not (root / "runtime/python313.dll").exists()
node = root / "runtime/node/node.exe"
node_pin = json.loads((root / "installer/manifest.json").read_text())["embedded_runtimes"]["windows_node_x86_64"]
assert subprocess.check_output([str(node), "--version"], text=True).strip() == "v" + node_pin["version"]
config = tomllib.loads((Path(os.environ["USERPROFILE"]) / ".codex/config.toml").read_text())
assert config["user_lifecycle_sentinel"] == "preserve"
entries = [config["mcp_servers"]["paper-fetch"]]
antigravity = json.loads((Path(os.environ["ANTIGRAVITY_HOME"]) / "mcp_config.json").read_text())
entries.append(antigravity["mcpServers"]["paper-fetch"])
for entry in entries:
    for key in ("MATHML_TO_LATEX_NODE_BIN", "PLAYWRIGHT_NODEJS_PATH"):
        assert Path(entry["env"][key]) == node, entry
os.environ["PLAYWRIGHT_NODEJS_PATH"] = str(node)
from playwright.sync_api import sync_playwright
with sync_playwright() as driver:
    assert driver.chromium.name == "chromium"
'@
    Invoke-NativeChecked -FilePath $runtime -Arguments @("-X", "utf8", "-c", $runtimeCheck, $InstallRoot)

    $codexSkill = Join-Path $env:USERPROFILE ".agents/skills/paper-fetch-skill"
    Invoke-NativeChecked -FilePath $runtime -Arguments @(
        "-X", "utf8", (Join-Path $InstallRoot "scripts/skill_integrity.py"),
        "verify", "--manifest", (Join-Path $InstallRoot "offline-manifest.json"),
        "--skill-dir", $codexSkill
    )
    if (Test-Path -LiteralPath (Join-Path $env:USERPROFILE ".codex/skills/paper-fetch-skill")) {
        throw "Verified install left the legacy Codex skill discoverable."
    }

    $versionOutput = (& $cli --version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $versionOutput -notmatch [regex]::Escape($ExpectedVersion)) {
        throw "Installed CLI did not report expected version $ExpectedVersion`: $versionOutput"
    }

    $doctorOutput = & $cli doctor --json
    $doctorExit = $LASTEXITCODE
    if ($doctorExit -notin @(0, 1)) {
        throw "Installed doctor returned unexpected exit code $doctorExit."
    }
    $doctor = ($doctorOutput -join [Environment]::NewLine) | ConvertFrom-Json
    if ($null -eq $doctor.provider_status) {
        throw "Installed doctor JSON is missing provider_status."
    }

    Invoke-NativeChecked -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $helper,
        "-Action", "Smoke",
        "-InstallRoot", $InstallRoot
    )
    Invoke-NativeChecked -FilePath $cli -Arguments @("browser-preflight", "--help")
    Invoke-NativeChecked -FilePath $runtime -Arguments @(
        "-X", "utf8", "-m", "paper_fetch.offline_setup",
        "--install-root", $InstallRoot, "--non-interactive"
    )
}

function Wait-ForUninstallCompletion {
    param(
        [string]$InstallRoot,
        [string]$LogPath,
        [int]$TimeoutSeconds = 60
    )

    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $logCompleted = $false
    while ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        $logCompleted = $false
        if (Test-Path -LiteralPath $LogPath -PathType Leaf) {
            try {
                $logCompleted = Select-String `
                    -LiteralPath $LogPath `
                    -SimpleMatch $UninstallSuccessLogMarker `
                    -Quiet `
                    -ErrorAction Stop
            } catch [System.IO.IOException] {
                $logCompleted = $false
            }
        }
        $uninstallFiles = @(
            Get-ChildItem -LiteralPath $InstallRoot -Filter "unins*.*" -File |
                Where-Object { $_.Extension -in @(".exe", ".dat", ".msg") }
        )
        if ($logCompleted -and
            $uninstallFiles.Count -eq 0) {
            return
        }
        Start-Sleep -Milliseconds 100
    }

    $remaining = @(
        Get-ChildItem -LiteralPath $InstallRoot -Filter "unins*.*" -File |
            Where-Object { $_.Extension -in @(".exe", ".dat", ".msg") } |
            ForEach-Object { $_.Name }
    )
    throw (
        "Timed out waiting for the Inno uninstaller second phase. " +
        "log_completed=$($logCompleted.ToString().ToLowerInvariant()); " +
        "files=[$($remaining -join ', ')]"
    )
}

function Assert-ExactPreservedInstallTree {
    param([string]$InstallRoot)

    $expectedFiles = @(
        "downloads/user-owned.txt",
        "image-tools/libvips/lifecycle-fixture/user-owned.txt",
        "optional-tools.json",
        "offline.env"
    ) | Sort-Object
    $expectedDirectories = @("downloads", "image-tools", "image-tools/libvips", "image-tools/libvips/lifecycle-fixture") | Sort-Object
    $actualFiles = @()
    $actualDirectories = @()

    foreach ($item in @(Get-ChildItem -LiteralPath $InstallRoot -Recurse -Force)) {
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Silent uninstall left a reparse-point entry: $($item.FullName)"
        }
        $relative = [System.IO.Path]::GetRelativePath(
            $InstallRoot,
            $item.FullName
        ).Replace("\", "/")
        if ($item.PSIsContainer) {
            $actualDirectories += $relative
        } else {
            $actualFiles += $relative
        }
    }
    $actualFiles = @($actualFiles | Sort-Object)
    $actualDirectories = @($actualDirectories | Sort-Object)
    $fileDifference = @(
        Compare-Object -ReferenceObject $expectedFiles -DifferenceObject $actualFiles
    )
    $directoryDifference = @(
        Compare-Object `
            -ReferenceObject $expectedDirectories `
            -DifferenceObject $actualDirectories
    )
    if ($fileDifference.Count -ne 0 -or $directoryDifference.Count -ne 0) {
        throw (
            "Silent uninstall did not leave the exact preserved install tree. " +
            "files=[$($actualFiles -join ', ')]; " +
            "directories=[$($actualDirectories -join ', ')]"
        )
    }
}

$testRoot = Join-Path $env:RUNNER_TEMP "paper-fetch-installer-lifecycle-$([Guid]::NewGuid().ToString('N'))"
$installRoot = Join-Path $testRoot "install"
$fakeProfile = Join-Path $testRoot "profile"
$fakeAntigravity = Join-Path $testRoot "antigravity"
$originalUserProfile = $env:USERPROFILE
$originalAntigravityHome = $env:ANTIGRAVITY_HOME
$originalUserPath = [Environment]::GetEnvironmentVariable("Path", "User")

try {
    New-Item -ItemType Directory -Force -Path $fakeProfile, $fakeAntigravity | Out-Null
    $env:USERPROFILE = $fakeProfile
    $env:ANTIGRAVITY_HOME = $fakeAntigravity

    $installArguments = @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/SP-",
        "/DIR=$installRoot"
    )
    $legacyCodexSkill = Join-Path $fakeProfile ".codex/skills/paper-fetch-skill"
    New-Item -ItemType Directory -Force -Path $legacyCodexSkill | Out-Null
    Set-Content -LiteralPath (Join-Path $legacyCodexSkill "SKILL.md") -Value "legacy"
    $codexConfig = Join-Path $fakeProfile ".codex/config.toml"
    Set-Content -LiteralPath $codexConfig -Encoding UTF8 -Value 'user_lifecycle_sentinel = "preserve"'
    Write-Host "==> Silent fresh install of final cp314 EXE"
    Invoke-NativeChecked -FilePath $SetupPath -Arguments $installArguments
    Invoke-InstalledSmoke -InstallRoot $installRoot
    if ($PreviousSetupPath) {
        $freshUninstallLog = Join-Path $testRoot "fresh-uninstall.log"
        Invoke-NativeChecked -FilePath (Join-Path $installRoot "unins000.exe") -Arguments @(
            "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG=$freshUninstallLog"
        )
        Wait-ForUninstallCompletion -InstallRoot $installRoot -LogPath $freshUninstallLog
        Remove-Item -LiteralPath $installRoot -Recurse -Force
        Write-Host "==> Install verified legacy cp313 EXE before upgrading to cp314"
        Invoke-NativeChecked -FilePath $PreviousSetupPath -Arguments $installArguments
        Invoke-NativeChecked -FilePath (Join-Path $installRoot "runtime/python.exe") -Arguments @(
            "-c", "import sys; assert sys.version_info[:2] == (3, 13)"
        )
    }

    $offlineEnv = Join-Path $installRoot "offline.env"
    Add-Content -LiteralPath $offlineEnv -Encoding UTF8 -Value 'USER_LIFECYCLE_SENTINEL="preserve"'
    $userPayload = Join-Path $installRoot "downloads/user-owned.txt"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $userPayload) | Out-Null
    Set-Content -LiteralPath $userPayload -Encoding UTF8 -Value "preserve"
    $externalUserPayload = Join-Path $fakeProfile ".codex/user-owned.txt"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $externalUserPayload) | Out-Null
    Set-Content -LiteralPath $externalUserPayload -Encoding UTF8 -Value "preserve"

    # Optional content has a separate owner and must survive the old Inno
    # uninstaller during upgrade as well as default silent final uninstall.
    $optionalPayload = Join-Path $installRoot "image-tools/libvips/lifecycle-fixture/user-owned.txt"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $optionalPayload) | Out-Null
    Set-Content -LiteralPath $optionalPayload -Encoding UTF8 -Value "optional-preserve"
    $optionalInventory = Join-Path $installRoot "optional-tools.json"
    Set-Content -LiteralPath $optionalInventory -Encoding UTF8 -Value '{"schema_version":1,"tools":{}}'
    $optionalHash = (Get-FileHash -LiteralPath $optionalPayload).Hash
    $inventoryHash = (Get-FileHash -LiteralPath $optionalInventory).Hash
    if (Test-Path -LiteralPath (Join-Path $installRoot "optional-setup-results.txt")) {
        throw "Silent install must not run optional configuration."
    }

    New-Item -ItemType Directory -Force -Path $legacyCodexSkill | Out-Null
    Set-Content -LiteralPath (Join-Path $legacyCodexSkill "SKILL.md") -Value "legacy coexistence"
    Set-Content -LiteralPath (Join-Path $fakeProfile ".agents/skills/paper-fetch-skill/stale.md") -Value "stale"
    Write-Host "==> Upgrade to final cp314 EXE and verify retained user and host integration state"
    Invoke-NativeChecked -FilePath $SetupPath -Arguments $installArguments
    Invoke-InstalledSmoke -InstallRoot $installRoot
    if (-not (Select-String -LiteralPath $offlineEnv -SimpleMatch "USER_LIFECYCLE_SENTINEL" -Quiet)) {
        throw "Overwrite upgrade did not preserve offline.env user content."
    }
    if (-not (Test-Path -LiteralPath $userPayload -PathType Leaf) -or
        (Get-Content -LiteralPath $userPayload -Raw).Trim() -ne "preserve") {
        throw "Overwrite upgrade did not preserve install-root user content."
    }
    if (-not (Test-Path -LiteralPath $externalUserPayload -PathType Leaf) -or
        (Get-Content -LiteralPath $externalUserPayload -Raw).Trim() -ne "preserve") {
        throw "Overwrite upgrade did not preserve external user content."
    }

    if ((Get-FileHash -LiteralPath $optionalPayload).Hash -ne $optionalHash -or
        (Get-FileHash -LiteralPath $optionalInventory).Hash -ne $inventoryHash) {
        throw "Upgrade changed optional tool content or ownership inventory."
    }
    if (Test-Path -LiteralPath (Join-Path $installRoot "optional-setup-results.txt")) {
        throw "Silent upgrade must not run optional configuration."
    }

    Write-Host "==> In-place overwrite upgrade of cp314 installation"
    Invoke-NativeChecked -FilePath $SetupPath -Arguments $installArguments
    Invoke-InstalledSmoke -InstallRoot $installRoot

    $uninstallers = @(Get-ChildItem -LiteralPath $installRoot -Filter "unins*.exe" -File)
    if ($uninstallers.Count -ne 1 -or $uninstallers[0].Name -ne "unins000.exe") {
        throw (
            "Expected the synchronized upgrade to install only unins000.exe; " +
            "found [$($uninstallers.Name -join ', ')]."
        )
    }
    New-Item -ItemType Directory -Force -Path $legacyCodexSkill | Out-Null
    Set-Content -LiteralPath (Join-Path $legacyCodexSkill "SKILL.md") -Value "legacy coexistence"
    $uninstallLog = Join-Path $testRoot "final-uninstall.log"
    Write-Host "==> Silent uninstall of final EXE"
    Invoke-NativeChecked -FilePath $uninstallers[0].FullName -Arguments @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/LOG=$uninstallLog"
    )

    # The original Inno process exits before its TEMP-hosted second phase. Wait
    # for its success marker and all uninstaller files to disappear before
    # evaluating the exact preserved tree.
    Wait-ForUninstallCompletion -InstallRoot $installRoot -LogPath $uninstallLog
    Assert-ExactPreservedInstallTree -InstallRoot $installRoot
    foreach ($managedSkill in @(
        (Join-Path $fakeProfile ".agents/skills/paper-fetch-skill"),
        $legacyCodexSkill,
        (Join-Path $fakeProfile ".claude/skills/paper-fetch-skill"),
        (Join-Path $fakeAntigravity "skills/paper-fetch-skill")
    )) {
        if (Test-Path -LiteralPath $managedSkill) {
            throw "Silent uninstall left managed skill content: $managedSkill"
        }
    }
    if (-not (Test-Path -LiteralPath $externalUserPayload -PathType Leaf) -or
        (Get-Content -LiteralPath $externalUserPayload -Raw).Trim() -ne "preserve") {
        throw "Silent uninstall removed external user content."
    }
} finally {
    [Environment]::SetEnvironmentVariable("Path", $originalUserPath, "User")
    $env:USERPROFILE = $originalUserProfile
    $env:ANTIGRAVITY_HOME = $originalAntigravityHome
    if ($testRoot.StartsWith(
        [System.IO.Path]::GetFullPath($env:RUNNER_TEMP),
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
