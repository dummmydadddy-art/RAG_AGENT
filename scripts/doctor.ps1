# Doctor Diagnostic Script for RAG Agent Phase 0
$ErrorActionPreference = "Continue"

Write-Host "================================================" -ForegroundColor Cyan
Write-Host " RAG Agent Phase 0 Doctor Diagnostics" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$allPassed = $true
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$venvPython = Join-Path $root ".venv\Scripts\python.exe"

function Check-Result($title, $passed, $details = "") {
    if ($passed) {
        Write-Host "  [PASS] $title" -ForegroundColor Green
        if ($details) { Write-Host "         $details" -ForegroundColor DarkGray }
    } else {
        Write-Host "  [FAIL] $title" -ForegroundColor Red
        if ($details) { Write-Host "         $details" -ForegroundColor Yellow }
        $global:allPassed = $false
    }
}

# 1. Git Repository & Longpaths Check
$isGit = Test-Path (Join-Path $root ".git")
$longpaths = (git config --get core.longpaths) -eq "true"
$branch = git rev-parse --abbrev-ref HEAD 2>$null
Check-Result "Git Repository & Longpaths" ($isGit -and $longpaths) "Branch: $branch | core.longpaths: $longpaths"

# 2. Rule Files & Character Limit Check (<12,000 chars)
$ruleFiles = Get-ChildItem (Join-Path $root ".agents\rules\*.md")
$rulesOk = $true
$ruleDetails = @()
foreach ($rf in $ruleFiles) {
    $content = Get-Content $rf.FullName -Raw
    $len = $content.Length
    $ruleDetails += "$($rf.Name): $len chars"
    if ($len -gt 12000) { $rulesOk = $false }
}
Check-Result "Agent Rules (<12,000 chars)" ($rulesOk -and ($ruleFiles.Count -ge 5)) ($ruleDetails -join ", ")

# 3. GEMINI.md Size (<1,500 tokens / 6,000 chars)
$geminiMd = Join-Path $root "GEMINI.md"
$geminiExists = Test-Path $geminiMd
$geminiLen = if ($geminiExists) { (Get-Content $geminiMd -Raw).Length } else { 0 }
Check-Result "GEMINI.md (<1,500 tokens)" ($geminiExists -and ($geminiLen -lt 6000)) "$geminiLen characters"

# 4. Python Environment & Dependencies
$pyOk = $false
if (Test-Path $venvPython) {
    $modCheck = & $venvPython -c "import mcp, pytest, sympy, scipy, numpy, pint, pydantic, httpx, yaml; print('OK')" 2>&1
    $pyOk = ($LASTEXITCODE -eq 0) -and ($modCheck -match "OK")
}
Check-Result "Python 3.11 Virtualenv Dependencies" $pyOk "Interpreter: $venvPython"

# 5. RAG Adapter & MCP Server Tests
$env:PYTHONPATH = "$root\rag-adapter;$root\rag-mcp;$root\physmath-mcp"
$testOutput = & $venvPython -m pytest -q (Join-Path $root "rag-adapter\tests\test_contract.py") (Join-Path $root "rag-mcp\tests\test_server.py") (Join-Path $root "physmath-mcp\tests\test_physmath.py") 2>&1
$testsPassed = ($LASTEXITCODE -eq 0)
$testSummary = ($testOutput | Select-String "passed in") -join ""
Check-Result "Automated Unit & Contract Tests" $testsPassed "$testSummary"

# 6. Antigravity MCP Server Configuration
$mcpConfigPath = "$env:USERPROFILE\.gemini\config\mcp_config.json"
$mcpOk = $false
$mcpDetails = "Not configured"
if (Test-Path $mcpConfigPath) {
    $cfg = Get-Content $mcpConfigPath -Raw | ConvertFrom-Json
    $hasRag = $null -ne $cfg.mcpServers.'rag-mcp'
    $hasPhys = $null -ne $cfg.mcpServers.'physmath-mcp'
    $mcpOk = $hasRag -and $hasPhys
    $mcpDetails = "rag-mcp: $hasRag | physmath-mcp: $hasPhys in $mcpConfigPath"
}
Check-Result "Antigravity MCP Server Registration" $mcpOk "$mcpDetails"

Write-Host "================================================" -ForegroundColor Cyan
if ($allPassed) {
    Write-Host " ALL PHASE 0 CHECKS GREEN!" -ForegroundColor Green
    exit 0
} else {
    Write-Host " SOME CHECKS FAILED. Review diagnostics above." -ForegroundColor Yellow
    exit 1
}
