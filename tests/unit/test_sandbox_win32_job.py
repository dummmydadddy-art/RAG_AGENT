"""
tests/unit/test_sandbox_win32_job.py

Unit tests for Standardized Win32 Job Object Sandbox module (src/sandbox/win32_job.py).
Verifies:
1. ExecutionResult dataclass schema and defaults.
2. AST safety guard (blocking forbidden modules, calls, dunders, reflections).
3. False-positive protection (allowing list.remove, set.remove, standard math/collections).
4. Sandboxed execution under Win32 Job Object (memory ceiling, timeout, active processes, stdin).
5. Auto-discovery and execution of test_* functions.
6. ctypes fallback and graceful degradation paths.
"""

import sys
import unittest
from unittest.mock import patch

import pytest

from src.sandbox.win32_job import (
    ExecutionResult,
    Win32JobSandbox,
    WindowsJobSandbox,
    check_ast_safety,
    execute_sandboxed_code,
)


class TestExecutionResultDataclass:
    """Verifies ExecutionResult dataclass schema."""

    def test_execution_result_dataclass(self):
        res = ExecutionResult(
            success=True,
            stdout="hello",
            stderr="",
            returncode=0,
            duration_s=0.12,
            peak_memory_bytes=1048576,
            timeout=False,
            ast_violation=False,
            error_message="",
        )
        assert res.success is True
        assert res.stdout == "hello"
        assert res.stderr == ""
        assert res.returncode == 0
        assert res.duration_s == 0.12
        assert res.peak_memory_bytes == 1048576
        assert res.timeout is False
        assert res.ast_violation is False
        assert res.error_message == ""


class TestASTSafetyVisitor:
    """Verifies static AST inspection rules."""

    def test_ast_safe_code(self):
        code = """
import math
from collections import deque, Counter
import heapq
import itertools

def solve(arr):
    q = deque(arr)
    c = Counter(arr)
    h = []
    for x in arr:
        heapq.heappush(h, x)
    return math.sqrt(len(q)) + sum(c.values())
"""
        is_safe, error = check_ast_safety(code)
        assert is_safe is True
        assert error is None

    def test_ast_blocks_forbidden_imports(self):
        forbidden = [
            "import os",
            "import sys",
            "import subprocess",
            "import shutil",
            "import socket",
            "import multiprocessing",
            "from os import path",
            "from subprocess import Popen",
        ]
        for snippet in forbidden:
            is_safe, error = check_ast_safety(snippet)
            assert is_safe is False, f"Expected forbidden import to fail: {snippet}"
            assert "forbidden module" in (error or "")

    def test_ast_blocks_eval_exec(self):
        snippets = [
            "eval('1 + 1')",
            "exec('x = 2')",
            "__import__('os')",
            "compile('1 + 1', '<string>', 'eval')",
        ]
        for snippet in snippets:
            is_safe, error = check_ast_safety(snippet)
            assert is_safe is False, f"Expected forbidden call to fail: {snippet}"
            assert "Call to dangerous function" in (error or "")

    def test_ast_blocks_file_operations(self):
        snippets = [
            "open('test.txt', 'w')",
            "import math\nmath.unlink('file')",
            "def foo(x):\n    x.rmdir()",
            "x.rmtree('dir')",
        ]
        for snippet in snippets:
            is_safe, error = check_ast_safety(snippet)
            assert is_safe is False, f"Expected file operation to fail: {snippet}"

    def test_ast_blocks_dunder_reflection(self):
        snippets = [
            "x = ().__class__.__bases__[0].__subclasses__()",
            "b = __builtins__",
            "g = globals()",
            "l = locals()",
            "v = vars()",
            "getattr(int, '__subclasses__')",
        ]
        for snippet in snippets:
            is_safe, error = check_ast_safety(snippet)
            assert is_safe is False, f"Expected dunder reflection to fail: {snippet}"

    def test_ast_blocks_system_calls(self):
        snippets = [
            "getattr(x, 'system')('calc')",
            "x.system('calc')",
            "x.popen('ls')",
            "x.spawn()",
            "x.fork()",
        ]
        for snippet in snippets:
            is_safe, error = check_ast_safety(snippet)
            assert is_safe is False, f"Expected system call to fail: {snippet}"

    def test_ast_syntax_error(self):
        bad_syntax = "def invalid_syntax(:"
        is_safe, error = check_ast_safety(bad_syntax)
        assert is_safe is False
        assert "Syntax error" in (error or "")

    def test_ast_allows_standard_libraries(self):
        code = """
import math, cmath, random, time
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
import collections, heapq, itertools, functools, bisect, copy, queue, threading, decimal, fractions

@dataclass
class Node:
    val: int

q = queue.Queue()
t = threading.Lock()
"""
        is_safe, error = check_ast_safety(code)
        assert is_safe is True, f"Standard libraries should be allowed, got error: {error}"
        assert error is None

    def test_ast_allows_list_and_set_remove(self):
        """Regression test ensuring container .remove() is not flagged as destructive."""
        code = """
items = [1, 2, 3, 4]
items.remove(2)
assert items == [1, 3, 4]

s = {10, 20, 30}
s.remove(20)
assert s == {10, 30}
"""
        is_safe, error = check_ast_safety(code)
        assert is_safe is True, f"Container .remove() must be permitted, got: {error}"
        assert error is None


class TestWin32JobSandboxExecution:
    """Verifies execution of code within Win32JobSandbox."""

    def test_execute_benign_code_success(self):
        solution = """
def multiply(a: int, b: int) -> int:
    return a * b
"""
        test_suite = """
assert multiply(3, 4) == 12
assert multiply(-2, 5) == -10
assert multiply(0, 100) == 0
"""
        res = execute_sandboxed_code(solution, test_suite, timeout=5.0)
        assert res.success is True
        assert res.returncode == 0
        assert res.duration_s > 0.0
        assert res.peak_memory_bytes > 0
        assert res.timeout is False
        assert res.ast_violation is False
        assert "Execution completed successfully" in res.stdout

    def test_execute_failing_assertion(self):
        solution = "def add(a, b): return a + b + 1"
        test_suite = "assert add(2, 2) == 4"
        res = execute_sandboxed_code(solution, test_suite, timeout=5.0)
        assert res.success is False
        assert res.returncode != 0
        assert "AssertionError" in res.stderr
        assert res.timeout is False
        assert res.ast_violation is False

    def test_execute_auto_discovers_test_functions(self):
        solution = """
def square(x):
    return x * x
"""
        test_suite = """
def test_positive():
    assert square(5) == 25

def test_negative():
    assert square(-4) == 16
"""
        res = execute_sandboxed_code(solution, test_suite, timeout=5.0)
        assert res.success is True
        assert res.returncode == 0
        assert "Executed 2 test functions successfully" in res.stdout

    def test_execute_timeout_enforcement(self):
        infinite_loop = """
import time
while True:
    time.sleep(0.1)
"""
        res = execute_sandboxed_code(infinite_loop, "assert True", timeout=1.0)
        assert res.success is False
        assert res.timeout is True
        assert res.returncode == -1
        assert "timed out after 1.0s" in res.error_message

    def test_execute_memory_limit_enforcement(self):
        """Allocating far beyond max_memory_mb triggers MemoryError or OS termination."""
        sandbox = Win32JobSandbox(max_memory_mb=64, timeout_seconds=5.0)
        memory_bomb = "x = bytearray(200 * 1024 * 1024)"
        res = sandbox.run_python_script(memory_bomb)
        assert res.success is False
        assert (
            "memory limit exceeded" in res.error_message.lower()
            or "memoryerror" in res.stderr.lower()
            or res.returncode != 0
        )

    def test_execute_active_process_limit(self):
        """Spawning more processes than active_process_limit triggers WinError 1816."""
        sandbox = Win32JobSandbox(active_process_limit=2, timeout_seconds=5.0)
        # We run a raw script via run_python_script that attempts to spawn 2 child processes
        # (which would make 3 total active processes in the Job Object)
        multi_proc = """
import subprocess, sys
try:
    p1 = subprocess.Popen([sys.executable, "-c", "pass"])
    p2 = subprocess.Popen([sys.executable, "-c", "pass"])
    print("SPAWNED_SUCCESS")
except OSError as e:
    print(f"OS_ERROR: {e}")
"""
        res = sandbox.run_python_script(multi_proc)
        assert "1816" in res.stdout or "quota" in res.stdout.lower() or res.returncode != 0

    def test_execute_stdin_isolation(self):
        """Calling input() raises immediate EOFError because stdin=subprocess.DEVNULL."""
        script = """
try:
    val = input()
    print(f"read: {val}")
except EOFError:
    print("EOF_REACHED")
"""
        res = execute_sandboxed_code(script, "assert True", timeout=3.0)
        # Note: input() is blocked by AST guard when calling execute_sandboxed_code
        assert res.ast_violation is True

        # Now test directly with sandbox.run_python_script (which bypasses AST)
        sandbox = Win32JobSandbox(timeout_seconds=3.0)
        res_raw = sandbox.run_python_script(script)
        assert res_raw.success is True
        assert "EOF_REACHED" in res_raw.stdout

    def test_execute_ast_violation_preempts_execution(self):
        """AST security violations preempt subprocess execution with zero duration and zero peak memory."""
        malicious = "import os\nos.system('calc')"
        res = execute_sandboxed_code(malicious, "assert True", timeout=5.0)
        assert res.success is False
        assert res.ast_violation is True
        assert res.duration_s == 0.0
        assert res.peak_memory_bytes == 0
        assert "Import of forbidden module 'os'" in res.error_message

    def test_ctypes_fallback_path(self):
        """Verifies sandbox functions cleanly when HAS_WIN32JOB is False (ctypes fallback)."""
        sandbox = Win32JobSandbox(max_memory_mb=128, timeout_seconds=5.0)
        with patch.object(sandbox, "_create_win32job", return_value=None):
            with patch("src.sandbox.win32_job.HAS_WIN32JOB", False):
                res = sandbox.run_python_script("print('ctypes fallback works')")
                assert res.success is True
                assert "ctypes fallback works" in res.stdout

    def test_unsupported_language(self):
        res = execute_sandboxed_code("fn main() {}", "test", language="rust")
        assert res.success is False
        assert res.ast_violation is False
        assert "not supported" in res.error_message

    def test_windows_job_sandbox_alias(self):
        """Verifies WindowsJobSandbox is an exact alias for Win32JobSandbox."""
        assert WindowsJobSandbox is Win32JobSandbox

    def test_execute_numpy_within_256mb_sandbox(self):
        """Verify single-threaded BLAS defaults prevent OpenBLAS 256 MB OOM on numpy import."""
        code = "import numpy as np\ndef sum_vec(xs):\n    return int(np.array(xs).sum())\n"
        tests = "assert sum_vec([1, 2, 3, 4]) == 10\n"
        res = execute_sandboxed_code(code, tests, language="python", timeout=5.0, max_memory_mb=256)
        assert res.success is True, f"numpy inside 256MB sandbox failed: {res.stderr} | {res.error_message}"
        assert res.peak_memory_bytes < 128 * 1024 * 1024

