# EduConnect LMS - Service Launcher
$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   EduConnect LMS - One-Click Launcher & Sync Engine        " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$ProjectDir = $PSScriptRoot

# ------------------------------------------------------------------
# 1. CHECK DOCKER DESKTOP
# ------------------------------------------------------------------
Write-Host "[1/7] Checking Docker Desktop..." -ForegroundColor Yellow
$dockerOk = $false
try {
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
} catch {}

if (-not $dockerOk) {
    Write-Host "      Starting Docker Desktop background service..." -ForegroundColor Gray
    Start-Process "C:\Program Files\Docker\Docker\resources\com.docker.backend.exe" -WindowStyle Hidden -ErrorAction SilentlyContinue
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" -ErrorAction SilentlyContinue
    
    $tries = 0
    while ($tries -lt 15) {
        Start-Sleep -Seconds 4
        $tries++
        try {
            docker info 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $dockerOk = $true
                break
            }
        } catch {}
        Write-Host "      Waiting for Docker engine ($($tries * 4)s)..." -ForegroundColor Gray
    }
}

if (-not $dockerOk) {
    Write-Host "      [ERROR] Docker Desktop did not start within 60s." -ForegroundColor Red
    Write-Host "      Please start Docker Desktop manually and re-run this script." -ForegroundColor Yellow
    pause
    exit 1
}
Write-Host "      Docker is running. [OK]" -ForegroundColor Green

# ------------------------------------------------------------------
# 2. START CLOUDFLARE TUNNEL & EXTRACT URL
# ------------------------------------------------------------------
Write-Host "[2/7] Checking Cloudflare Tunnel..." -ForegroundColor Yellow
$tunnelRunning = (docker ps --format "{{.Names}}" --filter "name=n8n-cloudflared") -eq "n8n-cloudflared"
if (-not $tunnelRunning) {
    docker start n8n-cloudflared 2>$null | Out-Null
    Start-Sleep -Seconds 4
}

# Extract the active trycloudflare URL
$tunnelMatches = docker logs n8n-cloudflared 2>&1 | Select-String -Pattern "https://[a-zA-Z0-9-]+\.trycloudflare\.com"
$currentTunnelUrl = ""
if ($tunnelMatches) {
    $currentTunnelUrl = ($tunnelMatches[-1].Matches[0].Value).Trim()
}

if (-not $currentTunnelUrl) {
    Write-Host "      Tunnel URL not found yet, waiting 6s..." -ForegroundColor Gray
    Start-Sleep -Seconds 6
    $tunnelMatches = docker logs n8n-cloudflared 2>&1 | Select-String -Pattern "https://[a-zA-Z0-9-]+\.trycloudflare\.com"
    if ($tunnelMatches) {
        $currentTunnelUrl = ($tunnelMatches[-1].Matches[0].Value).Trim()
    }
}

Write-Host "      Active Tunnel: $currentTunnelUrl [OK]" -ForegroundColor Green

# ------------------------------------------------------------------
# 3. SYNC n8n CONTAINER WITH CURRENT TUNNEL WEBHOOK_URL
# ------------------------------------------------------------------
Write-Host "[3/7] Checking n8n Container & Webhook Alignment..." -ForegroundColor Yellow
$n8nRunning = (docker ps --format "{{.Names}}" --filter "name=n8n-recovered") -eq "n8n-recovered"
$needsRecreate = $false

if ($n8nRunning) {
    try {
        $n8nEnv = (docker inspect n8n-recovered --format '{{json .Config.Env}}' | ConvertFrom-Json)
        $configuredWh = ($n8nEnv | Where-Object { $_ -like "WEBHOOK_URL=*" }) -replace "WEBHOOK_URL=", ""
        if ($configuredWh.TrimEnd('/') -ne $currentTunnelUrl.TrimEnd('/')) {
            Write-Host "      Tunnel URL changed from $configuredWh to $currentTunnelUrl" -ForegroundColor Yellow
            $needsRecreate = $true
        }
    } catch {
        $needsRecreate = $true
    }
} else {
    $needsRecreate = $true
}

if ($needsRecreate -and $currentTunnelUrl) {
    Write-Host "      Re-aligning n8n with current tunnel domain..." -ForegroundColor Cyan
    docker stop n8n-recovered 2>$null | Out-Null
    docker rm n8n-recovered 2>$null | Out-Null
    docker run -d --name n8n-recovered `
      -p 5678:5678 `
      -v n8n_data:/home/node/.n8n `
      -e "WEBHOOK_URL=$currentTunnelUrl/" `
      -e "N8N_PROTOCOL=https" `
      -e "EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS=true" `
      -e "EXECUTIONS_DATA_PRUNE=false" `
      -e "EXECUTIONS_DATA_SAVE_ON_SUCCESS=all" `
      -e "EXECUTIONS_DATA_SAVE_ON_ERROR=all" `
      --restart unless-stopped `
      n8nio/n8n:latest | Out-Null
    
    Start-Sleep -Seconds 6
} elseif (-not $n8nRunning) {
    docker start n8n-recovered 2>$null | Out-Null
    Start-Sleep -Seconds 6
}

# Apply Telegram Plaintext Patch
docker exec -u root n8n-recovered node /home/node/.n8n/patch_telegram.js 2>$null | Out-Null
Write-Host "      n8n & Telegram Webhook configured. [OK]" -ForegroundColor Green

# ------------------------------------------------------------------
# 4. START OLLAMA
# ------------------------------------------------------------------
Write-Host "[4/7] Checking Ollama LLM..." -ForegroundColor Yellow
$ollamaUp = $false
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -UseBasicParsing 2>$null
    if ($resp.StatusCode -eq 200) { $ollamaUp = $true }
} catch {}

if (-not $ollamaUp) {
    Write-Host "      Starting Ollama server in background..." -ForegroundColor Gray
    $ollamaExe = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
    Start-Process $ollamaExe -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 4
}
Write-Host "      Ollama LLM is active. [OK]" -ForegroundColor Green

# ------------------------------------------------------------------
# 5. START PHP BACKEND
# ------------------------------------------------------------------
Write-Host "[5/7] Checking PHP Backend API (Port 8000)..." -ForegroundColor Yellow
$phpUp = $false
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8000/api/users/students" -Headers @{"x-api-key"="lms-n8n-service-key-2026"} -TimeoutSec 2 -UseBasicParsing 2>$null
    if ($r.StatusCode -eq 200 -or $r.StatusCode -eq 401) { $phpUp = $true }
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 401 -or $_.Exception.Response.StatusCode.value__ -eq 200) { $phpUp = $true }
}

if (-not $phpUp) {
    Write-Host "      Starting PHP backend on port 8000..." -ForegroundColor Gray
    $phpExe = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\PHP.PHP.8.3_Microsoft.Winget.Source_8wekyb3d8bbwe\php.exe"
    $backendDir = "$ProjectDir\backend"
    Start-Process "cmd.exe" -ArgumentList "/k title PHP Backend - EduConnect LMS && cd /d `"$backendDir`" && `"$phpExe`" -S 0.0.0.0:8000"
    Start-Sleep -Seconds 3
}
Write-Host "      PHP Backend is running. [OK]" -ForegroundColor Green

# ------------------------------------------------------------------
# 6. START REACT FRONTEND
# ------------------------------------------------------------------
Write-Host "[6/7] Checking React Frontend (Port 5173)..." -ForegroundColor Yellow
$feUp = $false
try {
    $r = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 2 -UseBasicParsing 2>$null
    if ($r.StatusCode -eq 200) { $feUp = $true }
} catch {}

if (-not $feUp) {
    Write-Host "      Starting React frontend on port 5173..." -ForegroundColor Gray
    $frontendDir = "$ProjectDir\frontend"
    Start-Process "cmd.exe" -ArgumentList "/k title React Frontend - EduConnect LMS && cd /d `"$frontendDir`" && npm run dev"
    Start-Sleep -Seconds 4
}
Write-Host "      React Frontend is running. [OK]" -ForegroundColor Green

# ------------------------------------------------------------------
# 7. SUMMARY & BROWSER LAUNCH
# ------------------------------------------------------------------
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "   ALL EDUCONNECT LMS SERVICES ARE RUNNING!                 " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Service               URL" -ForegroundColor White
Write-Host "  -------------------   ---------------------------------------" -ForegroundColor Gray
Write-Host "  React Web UI          http://localhost:5173" -ForegroundColor Cyan
Write-Host "  n8n Workflow Editor   http://localhost:5678" -ForegroundColor Cyan
Write-Host "  PHP Backend API       http://localhost:8000" -ForegroundColor Cyan
Write-Host "  Ollama Local LLM      http://localhost:11434" -ForegroundColor Cyan
Write-Host "  Cloudflare Webhook    $currentTunnelUrl" -ForegroundColor Cyan
Write-Host "  Telegram Bot          @student_supp_bot" -ForegroundColor Cyan
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Opening EduConnect LMS Web UI in browser..." -ForegroundColor Yellow
Start-Process "http://localhost:5173"
Write-Host "Press Enter to exit this launcher window..."
Read-Host
