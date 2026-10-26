# Setup script for RAG Agent Python Environment
$ErrorActionPreference = "Stop"

Write-Host "================================================" -ForegroundColor Cyan
Write-Host " RAG Agent Environment Setup" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# 1. Verify Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Error "Python was not found in PATH. Please install Python 3.11 or newer."
}
$pyVersion = python --version 2>&1
Write-Host "[OK] Found Python: $pyVersion" -ForegroundColor Green

# 2. Configure Git longpaths
git config core.longpaths true
Write-Host "[OK] Configured git core.longpaths true" -ForegroundColor Green

# 3. Create Virtual Environment
$venvPath = Join-Path $PSScriptRoot "..\.venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "[+] Creating virtual environment at .venv..." -ForegroundColor Yellow
    python -m venv $venvPath
    Write-Host "[OK] Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "[OK] Virtual environment already exists" -ForegroundColor Green
}

$venvPython = Join-Path $venvPath "Scripts\python.exe"
$venvPip = Join-Path $venvPath "Scripts\pip.exe"

# 4. Install / Update dependencies
Write-Host "[+] Installing dependencies from requirements.txt..." -ForegroundColor Yellow
& $venvPip install --upgrade pip --quiet
& $venvPip install -r (Join-Path $PSScriptRoot "..\requirements.txt") --quiet

Write-Host "[OK] Dependencies installed successfully" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host " Setup complete! Virtualenv: $venvPath" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
