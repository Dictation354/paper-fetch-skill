[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$ValidatorOnly
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot

try {
    & $Python scripts/validate_macos_adaptation.py
    if ($LASTEXITCODE -ne 0) {
        throw "macOS adaptation contract validation failed with exit code $LASTEXITCODE"
    }
    if ($ValidatorOnly) {
        return
    }

    $testNodes = @(
        & $Python scripts/validate_macos_adaptation.py --print-test-nodes windows
    )
    if ($LASTEXITCODE -ne 0) {
        throw "Could not select portable Windows contract tests."
    }
    if ($testNodes.Count -eq 0) {
        throw "No portable Windows contract tests were selected."
    }

    $previousPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $repoRoot "src"
        & $Python -m pytest @testNodes -q
        if ($LASTEXITCODE -ne 0) {
            throw "Portable Windows macOS contract tests failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        $env:PYTHONPATH = $previousPythonPath
    }
}
finally {
    Pop-Location
}
