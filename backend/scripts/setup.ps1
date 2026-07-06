# Windows setup: Poetry + Python 3.12
$ErrorActionPreference = "Stop"

$Python312 = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
if (-not $Python312) {
    Write-Host "Python 3.12 not found. Install with:"
    Write-Host "  winget install Python.Python.3.12"
    exit 1
}

$PoetryDir = "$env:APPDATA\Python\Scripts"
if (-not (Test-Path "$PoetryDir\poetry.exe")) {
    Write-Host "Poetry not found. Install with:"
    Write-Host "  py -3.12 -m pip install poetry"
    exit 1
}

$env:Path = "$PoetryDir;$(Split-Path $Python312);$env:Path"

Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "Using Python: $Python312"
poetry config virtualenvs.in-project true --local
poetry env use $Python312
poetry lock --no-update 2>$null; if ($LASTEXITCODE -ne 0) { poetry lock }
poetry install

Write-Host ""
Write-Host "Done. Activate venv:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  poetry run pytest"
Write-Host "  poetry run uvicorn src.main:app --reload"
