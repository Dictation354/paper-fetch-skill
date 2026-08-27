param(
    [Parameter(Mandatory = $true)]
    [string]$SetupPath,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedVersion
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
        "offline.env"
    ) | Sort-Object
    $expectedDirectories = @("downloads")
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
    Write-Host "==> Silent install of final EXE"
    Invoke-NativeChecked -FilePath $SetupPath -Arguments $installArguments
    Invoke-InstalledSmoke -InstallRoot $installRoot

    $offlineEnv = Join-Path $installRoot "offline.env"
    Add-Content -LiteralPath $offlineEnv -Encoding UTF8 -Value 'USER_LIFECYCLE_SENTINEL="preserve"'
    $userPayload = Join-Path $installRoot "downloads/user-owned.txt"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $userPayload) | Out-Null
    Set-Content -LiteralPath $userPayload -Encoding UTF8 -Value "preserve"
    $externalUserPayload = Join-Path $fakeProfile ".codex/user-owned.txt"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $externalUserPayload) | Out-Null
    Set-Content -LiteralPath $externalUserPayload -Encoding UTF8 -Value "preserve"

    Write-Host "==> In-place overwrite upgrade with the same verified EXE"
    Invoke-NativeChecked -FilePath $SetupPath -Arguments $installArguments
    Invoke-InstalledSmoke -InstallRoot $installRoot
    if (-not (Select-String -LiteralPath $offlineEnv -SimpleMatch "USER_LIFECYCLE_SENTINEL" -Quiet)) {
        throw "Overwrite upgrade did not preserve offline.env user content."
    }
    if (-not (Test-Path -LiteralPath $userPayload -PathType Leaf)) {
        throw "Overwrite upgrade did not preserve install-root user content."
    }
    if (-not (Test-Path -LiteralPath $externalUserPayload -PathType Leaf)) {
        throw "Overwrite upgrade did not preserve external user content."
    }

    $uninstallers = @(Get-ChildItem -LiteralPath $installRoot -Filter "unins*.exe" -File)
    if ($uninstallers.Count -ne 1 -or $uninstallers[0].Name -ne "unins000.exe") {
        throw (
            "Expected the synchronized upgrade to install only unins000.exe; " +
            "found [$($uninstallers.Name -join ', ')]."
        )
    }
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
        (Join-Path $fakeProfile ".codex/skills/paper-fetch-skill"),
        (Join-Path $fakeProfile ".claude/skills/paper-fetch-skill"),
        (Join-Path $fakeAntigravity "skills/paper-fetch-skill")
    )) {
        if (Test-Path -LiteralPath $managedSkill) {
            throw "Silent uninstall left managed skill content: $managedSkill"
        }
    }
    if (-not (Test-Path -LiteralPath $externalUserPayload -PathType Leaf)) {
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
