param(
    [switch]$OpenBrowser,
    [switch]$RestartApi
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$backendDir = Join-Path $projectRoot 'backend'
$frontendDir = Join-Path $projectRoot 'frontend'

function Test-ListeningPort([int]$Port) {
    return $null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Stop-ListeningPort([int]$Port) {
    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    $processIds = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($processId in $processIds) {
        Stop-Process -Id $processId -Force -ErrorAction Stop
        Write-Host "Stopped API listener process $processId on port $Port."
    }
}

if (-not (Test-Path $pythonExe)) {
    throw "Python virtual environment not found: $pythonExe"
}

if ($RestartApi -and (Test-ListeningPort 8000)) {
    Stop-ListeningPort 8000
    Start-Sleep -Milliseconds 300
}

if (-not (Test-ListeningPort 8000)) {
    $env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
    $env:OLLAMA_MODEL = 'qwen2.5:0.5b'
    $env:NEWS_POLL_INTERVAL_SECONDS = '300'
    Start-Process -FilePath $pythonExe -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--reload' -WorkingDirectory $backendDir -WindowStyle Hidden
    Write-Host 'Started AtlasIQ API on http://127.0.0.1:8000'
} else {
    Write-Host 'AtlasIQ API is already listening on port 8000.'
}

if (-not (Test-ListeningPort 5173)) {
    Start-Process -FilePath 'npm.cmd' -ArgumentList 'run', 'dev', '--', '--host', '127.0.0.1' -WorkingDirectory $frontendDir -WindowStyle Hidden
    Write-Host 'Started AtlasIQ Web on http://127.0.0.1:5173'
} else {
    Write-Host 'AtlasIQ Web is already listening on port 5173.'
}

if ($OpenBrowser) {
    Start-Process 'http://127.0.0.1:5173'
}

Write-Host 'Use .\scripts\start-local.ps1 -RestartApi after a backend restart is needed. Run .\scripts\verify.ps1 for local checks.'
