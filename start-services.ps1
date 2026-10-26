# EduConnect LMS - Startup Script
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   EduConnect LMS - Starting All Services                   " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/4] Starting Docker containers (n8n & Cloudflare)..." -ForegroundColor Yellow
docker start n8n-recovered n8n-cloudflared 2>$null | Out-Null
Start-Sleep -Seconds 4
docker exec -u root n8n-recovered node /home/node/.n8n/patch_telegram.js 2>$null | Out-Null
Write-Host "      Docker containers started & Telegram patched." -ForegroundColor Gray

Write-Host "[2/4] Starting PHP Backend (Port 8000)..." -ForegroundColor Yellow
Start-Process -FilePath "php" -ArgumentList "-S 127.0.0.1:8000 index.php" -WorkingDirectory "$PSScriptRoot\backend" -WindowStyle Minimized
Write-Host "      PHP Backend running at http://127.0.0.1:8000" -ForegroundColor Gray

Write-Host "[3/4] Starting Vite Frontend (Port 5173)..." -ForegroundColor Yellow
Start-Process -FilePath "cmd.exe" -ArgumentList "/c npm run dev" -WorkingDirectory "$PSScriptRoot\frontend" -WindowStyle Minimized
Write-Host "      React Frontend running at http://localhost:5173" -ForegroundColor Gray

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "   All EduConnect LMS services are online!                  " -ForegroundColor Green
Write-Host "   Web UI:    http://localhost:5173                         " -ForegroundColor Green
Write-Host "   API:       http://127.0.0.1:8000                         " -ForegroundColor Green
Write-Host "   n8n:       https://result-mechanism-agriculture-correspondence.trycloudflare.com " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
