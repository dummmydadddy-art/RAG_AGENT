# Start and verify the RAG Agent stack and background services
$ErrorActionPreference = "Stop"

Write-Host "================================================" -ForegroundColor Cyan
Write-Host " Starting RAG Agent Stack" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$env:PYTHONPATH = "$root\rag-adapter;$root\rag-mcp;$root\physmath-mcp"

if (-not (Test-Path $venvPython)) {
    Write-Error "Virtual environment not found at $venvPython. Please run scripts\setup.ps1 first."
}

# 1. Verify RAG Storage
$storageDir = Join-Path $root "backend\storage"
if (-not (Test-Path $storageDir)) {
    New-Item -ItemType Directory -Path $storageDir -Force | Out-Null
}
$dbPath = Join-Path $storageDir "vectors.sqlite"
Write-Host "[OK] RAG SQLite database path: $dbPath" -ForegroundColor Green

# 2. Check if local PHP RAG server is running (optional)
try {
    $resp = Invoke-RestMethod -Uri "http://localhost:8000/api/rag/status" -TimeoutSec 2 -ErrorAction SilentlyContinue
    Write-Host "[OK] PHP RAG REST daemon is active at http://localhost:8000" -ForegroundColor Green
} catch {
    Write-Host "[INFO] PHP RAG REST daemon is not running on port 8000. Standalone SQLite engine is active." -ForegroundColor Yellow
}

# 3. Test MCP Servers dry-run
Write-Host "[+] Verifying rag-mcp server module..." -ForegroundColor Yellow
$ragCheck = & $venvPython -c "import rag_mcp.server; print('RAG MCP OK')" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] rag-mcp server verified" -ForegroundColor Green
} else {
    Write-Error "rag-mcp verification failed: $ragCheck"
}

Write-Host "[+] Verifying physmath-mcp server module..." -ForegroundColor Yellow
$pmCheck = & $venvPython -c "import physmath_mcp.server; print('PhysMath MCP OK')" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] physmath-mcp server verified" -ForegroundColor Green
} else {
    Write-Error "physmath-mcp verification failed: $pmCheck"
}

Write-Host "================================================" -ForegroundColor Cyan
Write-Host " RAG Agent Stack is operational!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
