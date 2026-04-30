param([string]$EnvFile)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. "$PSScriptRoot/flaresolverr_source_common.ps1"
$config = Read-FlareSolverrSourceEnv -EnvFile $EnvFile

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $config.LogFile) | Out-Null

try {
    Invoke-FlareSolverrSourceProbe -ServiceUrl $config.ServiceUrl | Out-Null
    Write-Host "FlareSolverr is already reachable at $($config.ServiceUrl)"
    exit 0
} catch {
}

if (-not (Test-Path -LiteralPath $config.ExecutablePath)) {
    throw "Missing bundled FlareSolverr executable: $($config.ExecutablePath)"
}
if (-not (Test-Path -LiteralPath $config.ChromePath)) {
    throw "Missing bundled Chromium executable: $($config.ChromePath)"
}

Remove-Item -LiteralPath $config.PidFile -Force -ErrorAction SilentlyContinue

$envNames = @("LOG_LEVEL", "HEADLESS", "TZ", "HOST", "PORT")
$previousEnv = @{}
foreach ($name in $envNames) {
    $previousEnv[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

try {
    [Environment]::SetEnvironmentVariable("LOG_LEVEL", [string]$config.LogLevel, "Process")
    [Environment]::SetEnvironmentVariable("HEADLESS", [string]$config.Headless, "Process")
    [Environment]::SetEnvironmentVariable("TZ", [string]$config.TimeZone, "Process")
    [Environment]::SetEnvironmentVariable("HOST", [string]$config.Host, "Process")
    [Environment]::SetEnvironmentVariable("PORT", [string]$config.Port, "Process")

    $stderrLog = [System.IO.Path]::ChangeExtension($config.LogFile, ".err.log")
    $process = Start-Process `
        -FilePath $config.ExecutablePath `
        -WorkingDirectory $config.BundleDir `
        -RedirectStandardOutput $config.LogFile `
        -RedirectStandardError $stderrLog `
        -WindowStyle Hidden `
        -PassThru
} finally {
    foreach ($name in $envNames) {
        [Environment]::SetEnvironmentVariable($name, $previousEnv[$name], "Process")
    }
}

Set-Content -LiteralPath $config.PidFile -Value ([string]$process.Id) -Encoding ASCII

for ($i = 0; $i -lt $config.StartupWaitSeconds; $i++) {
    Start-Sleep -Seconds 1
    try {
        Invoke-FlareSolverrSourceProbe -ServiceUrl $config.ServiceUrl | Out-Null
        Write-Host "FlareSolverr started at $($config.ServiceUrl)"
        Write-Host "PID: $($process.Id)"
        exit 0
    } catch {
    }
}

Write-Error "FlareSolverr failed to start. See $($config.LogFile)"
exit 1
