"""
Unit tests for Git Guard Hooks (pre-push and pre-commit).
Enforces protection against pushing to main, canary leakage, and protected path mutations.
"""

import os
import sys
import pytest
from pathlib import Path

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.hooks.pre_push import check_push_allowed
from scripts.hooks.pre_commit import check_commit_allowed


def test_pre_push_blocks_main_branch():
    # Push line: local_ref local_sha remote_ref remote_sha
    push_lines = ["refs/heads/feature/phase-4 abc1234 refs/heads/main def5678"]
    allowed, msg = check_push_allowed(push_lines=push_lines, remote_name="origin", remote_url="https://github.com/org/rag-agent.git")
    assert allowed is False
    assert "Direct push to 'main' branch is strictly forbidden" in msg


def test_pre_push_allows_feature_branch():
    push_lines = ["refs/heads/feature/phase-4 abc1234 refs/heads/feature/phase-4 def5678"]
    allowed, msg = check_push_allowed(push_lines=push_lines, remote_name="origin", remote_url="https://github.com/org/rag-agent.git")
    assert allowed is True
    assert "Push allowed" in msg


def test_pre_push_blocks_external_lms_repo():
    push_lines = ["refs/heads/feature/phase-4 abc1234 refs/heads/feature/phase-4 def5678"]
    allowed, msg = check_push_allowed(push_lines=push_lines, remote_name="origin", remote_url="https://github.com/org/old-lms-repo.git")
    assert allowed is False
    assert "Pushing to external or legacy LMS repository is forbidden" in msg


def test_pre_commit_blocks_canary_leak():
    canary = "CANARY-RAG-AGENT-CHECK-V2-7A8B9C0D-E1F2-3456-7890-ABCDEF123456"
    files = {"src/some_file.py": f"# Leaked secret: {canary}"}
    allowed, msg = check_commit_allowed(staged_files=files)
    assert allowed is False
    assert "Canary token detected" in msg


def test_pre_commit_blocks_unauthorized_protected_path_modification(monkeypatch):
    monkeypatch.delenv("ALLOW_PROTECTED_OVERRIDE", raising=False)
    files = {".agents/rules/safety.md": "modified rule content"}
    allowed, msg = check_commit_allowed(staged_files=files)
    assert allowed is False
    assert "Protected path modification detected" in msg


def test_pre_commit_allows_protected_path_with_explicit_override(monkeypatch):
    monkeypatch.setenv("ALLOW_PROTECTED_OVERRIDE", "1")
    files = {".agents/rules/safety.md": "modified rule content"}
    allowed, msg = check_commit_allowed(staged_files=files)
    assert allowed is True
