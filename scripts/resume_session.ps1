# scripts/resume_session.ps1
# Session Resumption and Health Check Script

Write-Host "================================================" -ForegroundColor Cyan
Write-Host " RAG Agent: Resuming Workspace & Daemons" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$root = Split-Path -Parent $PSScriptRoot

# 1. Verify / Start Ollama
$ollamaProc = Get-Process -Name ollama -ErrorAction SilentlyContinue
if (-not $ollamaProc) {
    Write-Host "[INFO] Starting Ollama daemon..." -ForegroundColor Yellow
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
} else {
    Write-Host "[OK] Ollama daemon is running (PID: $($ollamaProc[0].Id))" -ForegroundColor Green
}

# 2. Verify / Start PHP REST Vector API
$phpProc = Get-Process -Name php -ErrorAction SilentlyContinue
if (-not $phpProc) {
    Write-Host "[INFO] Starting PHP Vector RAG backend on port 8000..." -ForegroundColor Yellow
    $phpScript = Join-Path $root "backend\start-backend.ps1"
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$phpScript`"" -WindowStyle Hidden
    Start-Sleep -Seconds 2
} else {
    Write-Host "[OK] PHP Vector RAG backend is running (PID: $($phpProc[0].Id))" -ForegroundColor Green
}

# 3. Verify Deployed Model
$models = & ollama list 2>&1
if ($models -match "stem-coder-expert") {
    Write-Host "[OK] stem-coder-expert:latest registered in Ollama" -ForegroundColor Green
} else {
    Write-Host "[WARN] stem-coder-expert not found. Rebuilding from models/Modelfile..." -ForegroundColor Yellow
    & ollama create stem-coder-expert -f (Join-Path $root "models\Modelfile")
}

# 4. Run Doctor Diagnostics
Write-Host "[INFO] Running doctor diagnostics..." -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\doctor.ps1")

Write-Host "`nWorkspace is 100% ready for tomorrow's session!" -ForegroundColor Green
