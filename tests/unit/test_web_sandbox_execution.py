"""
tests/unit/test_web_sandbox_execution.py

Unit test suite for Win32 Job Object sandbox execution and AST security guard:
- Direct WindowsJobSandbox memory limit (256MB), timeout (5.0s), stdin isolation
- AST security guard pre-execution screening for Python, TypeScript, PHP, and SQL
- POST /api/execute endpoint validation, execution, and security blocking

Total: 15 comprehensive unit tests.
"""

from __future__ import annotations

import sys
import time
import pytest
from starlette.testclient import TestClient

from scripts.security.ast_guard import AstSecurityGuard
from scripts.security.windows_sandbox import WindowsJobSandbox
from src.web.app import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Creates in-memory TestClient bound to the FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


# ============================================================================
# 1. DIRECT WIN32 JOB OBJECT SANDBOX TESTS (4 tests)
# ============================================================================

def test_sandbox_benign_python_execution() -> None:
    """WindowsJobSandbox must execute clean Python code and capture stdout."""
    sandbox = WindowsJobSandbox(max_memory_mb=256, timeout_seconds=5.0)
    script = "print('FAST_RESULT_' + str(sum([1, 2, 3, 4, 5])))"
    res = sandbox.run_python_script(script)

    assert res.success is True
    assert res.exit_code == 0
    assert "FAST_RESULT_15" in res.stdout
    assert res.timed_out is False
    assert res.memory_breached is False
    assert res.duration_seconds < 3.0


def test_sandbox_timeout_enforcement() -> None:
    """WindowsJobSandbox must kill infinite loop within specified timeout."""
    sandbox = WindowsJobSandbox(max_memory_mb=256, timeout_seconds=1.0)
    script = "import time\nwhile True:\n    time.sleep(0.05)"
    t0 = time.time()
    res = sandbox.run_python_script(script)
    elapsed = time.time() - t0

    assert res.success is False
    assert res.timed_out is True
    assert elapsed < 3.0  # Must be killed quickly around 1.0s


def test_sandbox_memory_limit_enforcement() -> None:
    """WindowsJobSandbox must terminate memory bomb allocating > limit."""
    # Allocate 180MB with a 64MB limit
    sandbox = WindowsJobSandbox(max_memory_mb=64, timeout_seconds=5.0)
    script = "arr = bytearray(180 * 1024 * 1024)\nprint('ALLOCATED')"
    res = sandbox.run_python_script(script)

    assert res.success is False
    assert res.memory_breached is True or res.exit_code != 0
    assert "ALLOCATED" not in res.stdout


def test_sandbox_stdin_isolation() -> None:
    """WindowsJobSandbox must supply DEVNULL to stdin to prevent child hanging."""
    sandbox = WindowsJobSandbox(max_memory_mb=256, timeout_seconds=2.0)
    # Trying to read input should raise EOFError immediately and not hang
    script = """
try:
    s = input()
    print("READ:", s)
except EOFError:
    print("EOF_SUCCESS")
"""
    t0 = time.time()
    res = sandbox.run_python_script(script)
    elapsed = time.time() - t0

    assert res.success is True
    assert "EOF_SUCCESS" in res.stdout
    assert elapsed < 2.0


# ============================================================================
# 2. AST SECURITY GUARD TESTS (6 tests)
# ============================================================================

def test_ast_guard_blocks_os_import() -> None:
    """AstSecurityGuard must block import of os."""
    guard = AstSecurityGuard()
    code = "import os\nprint(os.name)"
    report = guard.check_python(code)
    assert report.is_safe is False
    assert any(v.category == "forbidden_import" for v in report.violations)


def test_ast_guard_blocks_subprocess_import() -> None:
    """AstSecurityGuard must block subprocess and Popen."""
    guard = AstSecurityGuard()
    code = "from subprocess import Popen\nPopen(['cmd'])"
    report = guard.check_python(code)
    assert report.is_safe is False
    assert any(v.category == "forbidden_import" for v in report.violations)


def test_ast_guard_blocks_socket_network() -> None:
    """AstSecurityGuard must block socket and networking modules."""
    guard = AstSecurityGuard()
    code = "import socket\ns = socket.socket()"
    report = guard.check_python(code)
    assert report.is_safe is False
    assert any(v.category == "forbidden_import" for v in report.violations)


def test_ast_guard_blocks_open_call() -> None:
    """AstSecurityGuard must block direct open() calls."""
    guard = AstSecurityGuard()
    code = "f = open('hacked.txt', 'w')\nf.write('pwned')"
    report = guard.check_python(code)
    assert report.is_safe is False
    assert any(v.category == "forbidden_call" for v in report.violations)


def test_ast_guard_blocks_eval_exec() -> None:
    """AstSecurityGuard must block dynamic eval() and exec()."""
    guard = AstSecurityGuard()
    code = "eval('__import__(\"os\").system(\"dir\")')"
    report = guard.check_python(code)
    assert report.is_safe is False
    assert any(v.category == "forbidden_call" for v in report.violations)


def test_ast_guard_blocks_dunder_reflection() -> None:
    """AstSecurityGuard must block reflection attacks using dunder attributes or getattr."""
    guard = AstSecurityGuard()
    code = "getattr(__builtins__, 'eval')('1+1')"
    report = guard.check_python(code)
    assert report.is_safe is False
    assert any(v.category in ("reflection_escape", "dunder_access") for v in report.violations)


# ============================================================================
# 3. POLYGLOT SECURITY & API EXECUTION TESTS (5 tests)
# ============================================================================

def test_polyglot_typescript_security_blocked(client: TestClient) -> None:
    """POST /api/execute with dangerous TypeScript payload must return security_status: blocked."""
    payload = {
        "language": "typescript",
        "code": "const fs = require('fs'); fs.unlinkSync('database.db');",
    }
    resp = client.post("/api/execute", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["security_status"] == "blocked"
    assert len(data["violations"]) > 0


def test_polyglot_php_security_blocked(client: TestClient) -> None:
    """POST /api/execute with destructive PHP command must return security_status: blocked."""
    payload = {
        "language": "php",
        "code": "<?php system('whoami'); ?>",
    }
    resp = client.post("/api/execute", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["security_status"] == "blocked"
    assert len(data["violations"]) > 0


def test_polyglot_sql_security_blocked(client: TestClient) -> None:
    """POST /api/execute with forbidden DDL DROP TABLE must return security_status: blocked."""
    payload = {
        "language": "sql",
        "code": "DROP TABLE users;",
    }
    resp = client.post("/api/execute", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["security_status"] == "blocked"
    assert len(data["violations"]) > 0


def test_polyglot_sql_in_memory_execution(client: TestClient) -> None:
    """POST /api/execute with safe SQL query executes in in-memory SQLite database."""
    payload = {
        "language": "sql",
        "code": "SELECT 42 AS answer, 'STEM' AS topic;",
    }
    resp = client.post("/api/execute", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["security_status"] == "clean"
    assert "42" in data["stdout"]
    assert "STEM" in data["stdout"]


def test_execute_endpoint_via_testclient(client: TestClient) -> None:
    """POST /api/execute with safe Python script executes in sandbox and returns ExecuteResponse."""
    payload = {
        "language": "python",
        "code": "def fib(n):\n    return n if n <= 1 else fib(n-1) + fib(n-2)\nprint('FIB_10:', fib(10))",
        "timeout_seconds": 3.0,
        "memory_limit_mb": 256,
    }
    resp = client.post("/api/execute", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["exit_code"] == 0
    assert data["sandboxed"] is True
    assert data["security_status"] == "clean"
    assert "FIB_10: 55" in data["stdout"]
    assert data["duration_seconds"] > 0.0


def test_execute_endpoint_rejects_unsupported_language(client: TestClient) -> None:
    """POST /api/execute with unknown/unsupported language must return success=False and honest error."""
    payload = {
        "language": "brainfuck",
        "code": "++++++++[>++++[>++>+++>+++>+<<<<-]>+>+>->>+[<]<-]>>.",
    }
    resp = client.post("/api/execute", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["exit_code"] == 1
    assert data["runtime"] == "unsupported-runtime"
    assert "unsupported language" in data["error_message"].lower()


def test_execute_endpoint_uninstalled_compiler_returns_honest_failure(client: TestClient) -> None:
    """POST /api/execute for compiled language without host compiler must return honest failure."""
    payload = {
        "language": "cpp",
        "code": "int main() { return 0; }",
    }
    resp = client.post("/api/execute", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["exit_code"] == 1
    assert data["runtime"] == "unsupported-runtime"
    assert "not installed on this host" in data["error_message"]
    assert "clang++ or g++" in data["error_message"]

