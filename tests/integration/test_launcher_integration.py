"""
tests/integration/test_launcher_integration.py

Integration tests for the Windows Launcher CLI:
- Validates CLI invocations (--help, --check-only, --workspace)
- Validates structured diagnostic output
- Validates exit codes and error handling
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_EXE = sys.executable
LAUNCHER_SCRIPT = REPO_ROOT / "scripts" / "launcher" / "launcher.py"


def test_launcher_cli_help():
    """Validates python scripts/launcher/launcher.py --help returns exit code 0."""
    res = subprocess.run(
        [str(PYTHON_EXE), str(LAUNCHER_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(REPO_ROOT),
    )
    assert res.returncode == 0
    assert "RAG-Agent" in res.stdout
    assert "--check-only" in res.stdout
    assert "--workspace" in res.stdout
    assert "--no-browser" in res.stdout


def test_launcher_cli_check_only():
    """Validates python scripts/launcher/launcher.py --check-only runs preflight and exits 0."""
    res = subprocess.run(
        [str(PYTHON_EXE), str(LAUNCHER_SCRIPT), "--check-only"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
    )
    assert res.returncode == 0, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}"
    assert "Pre-Flight Checks" in res.stdout
    assert "Python" in res.stdout
    assert "PHP" in res.stdout
    assert "Ollama" in res.stdout
    assert "Check-only mode requested" in res.stdout


def test_launcher_cli_check_only_with_workspace_override():
    """Validates --workspace override pointing to valid repo root."""
    res = subprocess.run(
        [
            str(PYTHON_EXE),
            str(LAUNCHER_SCRIPT),
            "--check-only",
            "--workspace",
            str(REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
    )
    assert res.returncode == 0
    assert "Workspace Root:" in res.stdout
    assert str(REPO_ROOT) in res.stdout


def test_launcher_cli_invalid_workspace_path():
    """Validates error exit when --workspace points to nonexistent directory."""
    res = subprocess.run(
        [
            str(PYTHON_EXE),
            str(LAUNCHER_SCRIPT),
            "--check-only",
            "--workspace",
            "C:\\NonExistent_Directory_XYZ_98765",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(REPO_ROOT),
    )
    assert res.returncode != 0
    assert "does not exist" in res.stderr or "does not exist" in res.stdout
