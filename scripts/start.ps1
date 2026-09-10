param([switch]$Preview)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create Python environment.' }
    & $pythonPath -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Failed to install dependencies.' }
}
if ($Preview) {
    $env:USE_SQLITE = 'True'
    Write-Host 'Local preview uses SQLite. PostgreSQL remains the default for normal execution.'
} else {
    $env:USE_SQLITE = 'False'
}
$env:GENFIN_DEBUG = 'True'
& $pythonPath manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Database unavailable. Start PostgreSQL with docker compose up -d, or use -Preview.' }
& $pythonPath manage.py runserver 127.0.0.1:8000
