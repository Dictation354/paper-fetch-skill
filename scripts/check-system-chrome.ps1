param([string]$OutputPath = "")
$ErrorActionPreference = "Stop"
$ChromeUrl = "https://www.google.com/chrome/"
function Find-SystemChrome {
    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($env:PAPER_FETCH_CHROME_BINARY_PATH) {
        $candidates.Add($env:PAPER_FETCH_CHROME_BINARY_PATH.Trim())
    } else {
        foreach ($hive in @([Microsoft.Win32.RegistryHive]::CurrentUser, [Microsoft.Win32.RegistryHive]::LocalMachine)) {
            foreach ($view in @([Microsoft.Win32.RegistryView]::Registry64, [Microsoft.Win32.RegistryView]::Registry32)) {
                $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey($hive, $view)
                try {
                    $key = $base.OpenSubKey('SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe')
                    if ($null -ne $key) {
                        try { $value = [string]$key.GetValue(''); if ($value) { $candidates.Add($value) } } finally { $key.Dispose() }
                    }
                } finally { $base.Dispose() }
            }
        }
        foreach ($root in @($env:PROGRAMFILES, ${env:PROGRAMFILES(X86)}, $env:LOCALAPPDATA)) {
            if ($root) { $candidates.Add((Join-Path $root 'Google\Chrome\Application\chrome.exe')) }
        }
        $command = Get-Command chrome.exe -ErrorAction SilentlyContinue
        if ($command) { $candidates.Add($command.Source) }
    }
    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $file = Get-Item -LiteralPath $candidate
        $info = $file.VersionInfo
        if ($info.ProductName -ne 'Google Chrome') { continue }
        if ($info.FileVersion -notmatch '^\d+\.\d+\.\d+\.\d+$') { continue }
        if ([int]($info.FileVersion.Split('.')[0]) -lt 115) { continue }
        return "Google Chrome $($info.FileVersion): $($file.FullName)"
    }
    throw "System Google Chrome (115+) is required. PAPER_FETCH_CHROME_BINARY_PATH must point to valid Chrome. Install Chrome from $ChromeUrl and rerun the installer."
}
try {
    $message = Find-SystemChrome
    if ($OutputPath) { [IO.File]::WriteAllText($OutputPath, $message) }
    Write-Output $message
    exit 0
} catch {
    $message = $_.Exception.Message
    if ($OutputPath) { [IO.File]::WriteAllText($OutputPath, $message) }
    [Console]::Error.WriteLine($message)
    exit 1
}
