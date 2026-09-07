param(
    [switch]$BackendOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $pythonExe)) {
    throw "Python virtual environment was not found at $pythonExe. Run the README setup command first."
}

Push-Location (Join-Path $projectRoot 'backend')
try {
    & $pythonExe -m pytest -q
} finally {
    Pop-Location
}

if (-not $BackendOnly) {
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        npm run build
    } finally {
        Pop-Location
    }
}

Write-Host 'AtlasIQ local quality checks completed.' -ForegroundColor Green
