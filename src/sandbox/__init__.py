"""
src/sandbox/__init__.py

Standardized sandboxed execution package for untrusted code.
"""

from .win32_job import (
    ExecutionResult,
    Win32JobSandbox,
    WindowsJobSandbox,
    check_ast_safety,
    execute_sandboxed_code,
)

__all__ = [
    "ExecutionResult",
    "Win32JobSandbox",
    "WindowsJobSandbox",
    "check_ast_safety",
    "execute_sandboxed_code",
]
