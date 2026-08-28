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

    $previousPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $repoRoot "src"
        & $Python -m pytest `
            tests/unit/test_macos_adaptation_validator.py `
            tests/integration/test_macos_adaptation_contract.py -q
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
