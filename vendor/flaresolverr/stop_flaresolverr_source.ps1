param([string]$EnvFile)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. "$PSScriptRoot/flaresolverr_source_common.ps1"
$config = Read-FlareSolverrSourceEnv -EnvFile $EnvFile

$pidText = ""
if (Test-Path -LiteralPath $config.PidFile) {
    $pidText = (Get-Content -LiteralPath $config.PidFile -Raw).Trim()
}

if ([string]::IsNullOrWhiteSpace($pidText)) {
    Remove-Item -LiteralPath $config.PidFile -Force -ErrorAction SilentlyContinue
    Write-Host "No running FlareSolverr process found."
    exit 0
}

$processId = [int]$pidText
$process = Get-Process -Id $processId -ErrorAction SilentlyContinue
if ($null -eq $process) {
    Remove-Item -LiteralPath $config.PidFile -Force -ErrorAction SilentlyContinue
    Write-Host "Removed stale PID file."
    exit 0
}

Stop-Process -Id $processId -Force
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if ($null -eq (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
        Remove-Item -LiteralPath $config.PidFile -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped FlareSolverr PID $processId"
        exit 0
    }
}

Write-Error "FlareSolverr PID $processId did not exit after 30 seconds."
exit 1
