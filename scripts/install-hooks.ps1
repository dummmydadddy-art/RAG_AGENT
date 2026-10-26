# Install Git Guard Hooks for RAG-Agent
$RepoRoot = Split-Path -Parent $PSScriptRoot
$GitHooksDir = Join-Path $RepoRoot ".git\hooks"

if (-not (Test-Path $GitHooksDir)) {
    Write-Host "[ERROR] .git/hooks directory not found. Is this a git repository?" -ForegroundColor Red
    exit 1
}

Write-Host "Installing Git Guard Hooks into $GitHooksDir..." -ForegroundColor Cyan

# 1. pre-push hook
$PrePushDst = Join-Path $GitHooksDir "pre-push"
$PrePushContent = "#!/bin/sh`n# Pre-push hook calling Python script`nif [ -f .venv/Scripts/python.exe ]; then`n    .venv/Scripts/python.exe scripts/hooks/pre_push.py ""`$@""`nelif [ -f .venv/bin/python ]; then`n    .venv/bin/python scripts/hooks/pre_push.py ""`$@""`nelse`n    python scripts/hooks/pre_push.py ""`$@""`nfi`n"

[System.IO.File]::WriteAllText($PrePushDst, $PrePushContent)
Write-Host "  [OK] Installed pre-push hook" -ForegroundColor Green

# 2. pre-commit hook
$PreCommitDst = Join-Path $GitHooksDir "pre-commit"
$PreCommitContent = "#!/bin/sh`n# Pre-commit hook calling Python script`nif [ -f .venv/Scripts/python.exe ]; then`n    .venv/Scripts/python.exe scripts/hooks/pre_commit.py ""`$@""`nelif [ -f .venv/bin/python ]; then`n    .venv/bin/python scripts/hooks/pre_commit.py ""`$@""`nelse`n    python scripts/hooks/pre_commit.py ""`$@""`nfi`n"

[System.IO.File]::WriteAllText($PreCommitDst, $PreCommitContent)
Write-Host "  [OK] Installed pre-commit hook" -ForegroundColor Green
Write-Host "Git hooks successfully installed!" -ForegroundColor Cyan
