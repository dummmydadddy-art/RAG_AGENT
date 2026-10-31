"""
scripts/launcher/__init__.py

Package export for RAG-Agent Windows Launcher and Supervisor subsystem.
"""

from __future__ import annotations

from .installer import check_bytecode_imports, ensure_environment, find_venv_python
from .launcher import get_workspace_root, parse_args
from .model_checker import ModelCheckResult, ensure_ollama_and_models, probe_ollama_daemon
from .preflight import (
    PreflightReport,
    PreflightResult,
    detect_ollama,
    detect_php,
    detect_python,
    run_all_preflight_checks,
)
from .supervisor import MultiServiceSupervisor

__all__ = [
    "PreflightResult",
    "PreflightReport",
    "detect_python",
    "detect_php",
    "detect_ollama",
    "run_all_preflight_checks",
    "find_venv_python",
    "check_bytecode_imports",
    "ensure_environment",
    "ModelCheckResult",
    "probe_ollama_daemon",
    "ensure_ollama_and_models",
    "MultiServiceSupervisor",
    "get_workspace_root",
    "parse_args",
]
