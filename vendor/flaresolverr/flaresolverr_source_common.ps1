Set-StrictMode -Version Latest

function ConvertFrom-FlareSolverrEnvValue {
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

function Resolve-FlareSolverrPath {
    param(
        [Parameter(Mandatory=$true)][string]$RootDir,
        [Parameter(Mandatory=$true)][string]$PathValue
    )

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $RootDir $PathValue))
}

function Read-FlareSolverrSourceEnv {
    param([string]$EnvFile)

    $rootDir = $PSScriptRoot
    if ([string]::IsNullOrWhiteSpace($EnvFile)) {
        $EnvFile = Join-Path $rootDir ".env.flaresolverr-source-windows"
    }

    $values = @{
        FLARESOLVERR_ROOT_DIR = $rootDir
        FLARESOLVERR_ENV_FILE = $EnvFile
        FLARESOLVERR_DOWNLOAD_DIR = Join-Path $rootDir ".flaresolverr"
        FLARESOLVERR_RELEASE_VERSION = "v3.4.6"
        FLARESOLVERR_HOST = "127.0.0.1"
        FLARESOLVERR_PORT = "8191"
        LOG_LEVEL = "info"
        HEADLESS = "true"
        TZ = "Asia/Shanghai"
        STARTUP_WAIT_SECONDS = "30"
        FLARESOLVERR_LOG_FILE = Join-Path $rootDir "run_logs/flaresolverr-windows.log"
        FLARESOLVERR_PID_FILE = Join-Path $rootDir "run_logs/flaresolverr-windows.pid"
        PROBE_OUTPUT_ROOT = Join-Path $rootDir "probe_outputs"
    }

    if (Test-Path -LiteralPath $EnvFile) {
        foreach ($rawLine in Get-Content -LiteralPath $EnvFile) {
            $line = $rawLine.Trim()
            if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#") -or -not $line.Contains("=")) {
                continue
            }
            $equalsIndex = $line.IndexOf("=")
            $key = $line.Substring(0, $equalsIndex).Trim()
            $value = ConvertFrom-FlareSolverrEnvValue $line.Substring($equalsIndex + 1)
            if ($values.ContainsKey($key)) {
                $values[$key] = $value
            }
        }
    }

    foreach ($key in @("FLARESOLVERR_DOWNLOAD_DIR", "FLARESOLVERR_LOG_FILE", "FLARESOLVERR_PID_FILE", "PROBE_OUTPUT_ROOT")) {
        $values[$key] = Resolve-FlareSolverrPath -RootDir $rootDir -PathValue ([string]$values[$key])
    }

    $releaseDir = Join-Path ([string]$values["FLARESOLVERR_DOWNLOAD_DIR"]) ([string]$values["FLARESOLVERR_RELEASE_VERSION"])
    $bundleDir = Join-Path $releaseDir "flaresolverr"
    $executable = Join-Path $bundleDir "flaresolverr.exe"
    $chrome = Join-Path $bundleDir "_internal/chrome/chrome.exe"
    $hostName = [string]$values["FLARESOLVERR_HOST"]
    $port = [string]$values["FLARESOLVERR_PORT"]
    $serviceUrl = "http://${hostName}:${port}/v1"

    return [pscustomobject]@{
        RootDir = $rootDir
        EnvFile = $EnvFile
        DownloadDir = $values["FLARESOLVERR_DOWNLOAD_DIR"]
        ReleaseVersion = $values["FLARESOLVERR_RELEASE_VERSION"]
        ReleaseDir = $releaseDir
        BundleDir = $bundleDir
        ExecutablePath = $executable
        ChromePath = $chrome
        Host = $values["FLARESOLVERR_HOST"]
        Port = $values["FLARESOLVERR_PORT"]
        LogLevel = $values["LOG_LEVEL"]
        Headless = $values["HEADLESS"]
        TimeZone = $values["TZ"]
        StartupWaitSeconds = [int]$values["STARTUP_WAIT_SECONDS"]
        LogFile = $values["FLARESOLVERR_LOG_FILE"]
        PidFile = $values["FLARESOLVERR_PID_FILE"]
        ProbeOutputRoot = $values["PROBE_OUTPUT_ROOT"]
        ServiceUrl = $serviceUrl
    }
}

function Invoke-FlareSolverrSourceProbe {
    param([Parameter(Mandatory=$true)][string]$ServiceUrl)

    $body = @{ cmd = "sessions.list" } | ConvertTo-Json -Compress
    Invoke-RestMethod -Uri $ServiceUrl -Method Post -ContentType "application/json" -Body $body -TimeoutSec 10
}
