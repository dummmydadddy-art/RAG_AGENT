# EduConnect LMS - Shutdown Script
Write-Host ""
Write-Host "============================================================" -ForegroundColor Red
Write-Host "   EduConnect LMS - Shutting Down All Services              " -ForegroundColor Red
Write-Host "============================================================" -ForegroundColor Red
Write-Host ""

Write-Host "[1/4] Stopping Web UI and Node processes..." -ForegroundColor Yellow
Get-Process -Name "*node*" -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "*React Frontend*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Stop-Process -Name "cmd" -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "*React Frontend*" }
Write-Host "      Done." -ForegroundColor Gray

Write-Host "[2/4] Stopping PHP Backend..." -ForegroundColor Yellow
Get-Process -Name "php" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "      Done." -ForegroundColor Gray

Write-Host "[3/4] Stopping Ollama..." -ForegroundColor Yellow
Get-Process -Name "ollama" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "      Done." -ForegroundColor Gray

Write-Host "[4/4] Stopping Docker containers..." -ForegroundColor Yellow
docker stop n8n-recovered n8n-cloudflared 2>$null | Out-Null
Write-Host "      Done." -ForegroundColor Gray

Write-Host ""
Write-Host "All EduConnect LMS services have been stopped." -ForegroundColor Green
Start-Sleep -Seconds 2
