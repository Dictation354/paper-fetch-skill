param([string]$EnvFile = $env:FLARESOLVERR_ENV_FILE)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$vendorDir = Join-Path $repoDir "vendor/flaresolverr"

if ([string]::IsNullOrWhiteSpace($EnvFile)) {
    $EnvFile = Join-Path $vendorDir ".env.flaresolverr-source-windows"
}
if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Missing FlareSolverr env file: $EnvFile"
}

. (Join-Path $vendorDir "flaresolverr_source_common.ps1")
$config = Read-FlareSolverrSourceEnv -EnvFile $EnvFile
Invoke-FlareSolverrSourceProbe -ServiceUrl $config.ServiceUrl | ConvertTo-Json -Depth 8
