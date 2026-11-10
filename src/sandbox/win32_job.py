"""
src/sandbox/win32_job.py

Standardized Win32 Job Object Sandbox Module.
Provides isolated execution for untrusted code with:
- Win32 Job Object kernel limits (memory ceiling <= 256 MB, active processes <= 2).
- Automatic termination of child process trees on job close (JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE).
- Strict execution timeouts and stdin isolation (stdin=subprocess.DEVNULL).
- Peak memory consumption telemetry via QueryInformationJobObject (PeakJobMemoryUsed).
- Dual Windows backend: pywin32 (`win32job`) with transparent ctypes fallback.
- Pre-execution AST safety analysis blocking malicious calls and modules while permitting standard container methods.
"""

from __future__ import annotations

import ast
import ctypes
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

# Win32 Kernel Constants
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x0100
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x0200
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x0008
JobObjectExtendedLimitInformation = 9

# Detect pywin32
HAS_WIN32JOB = False
try:
    if sys.platform == "win32":
        import win32api
        import win32job
        import win32process
        HAS_WIN32JOB = True
except ImportError:
    HAS_WIN32JOB = False


# Ctypes structures for secondary Windows fallback
if sys.platform == "win32":
    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]


@dataclass
class ExecutionResult:
    """Consolidated result returned by execute_sandboxed_code and Win32JobSandbox."""
    success: bool
    stdout: str
    stderr: str
    returncode: int
    duration_s: float
    peak_memory_bytes: int
    timeout: bool
    ast_violation: bool
    error_message: str


class ASTSafetyVisitor(ast.NodeVisitor):
    """
    AST visitor inspecting Python source code for security violations.
    Permits STEM and algorithmic libraries while blocking system modifications.
    """

    FORBIDDEN_MODULES: Set[str] = {
        "os", "sys", "subprocess", "shutil", "socket", "urllib", "requests",
        "http", "ctypes", "posix", "nt", "importlib", "pickle", "shelve",
        "webbrowser", "winreg", "pty", "commands", "cgi", "cgitb",
        "builtins", "multiprocessing",
    }

    FORBIDDEN_CALLS: Set[str] = {
        "eval", "exec", "open", "compile", "breakpoint", "input",
        "__import__", "exit", "quit",
    }

    FORBIDDEN_ATTRIBUTES: Set[str] = {
        "__builtins__", "__subclasses__", "__bases__", "__class__",
        "__globals__", "__code__", "__closure__", "system", "popen",
        "spawn", "fork", "kill", "unlink", "rmdir", "rmtree", "execl", "execv",
    }

    def __init__(self) -> None:
        super().__init__()
        self.violations: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root in self.FORBIDDEN_MODULES:
                self.violations.append(
                    f"Line {node.lineno}: Import of forbidden module '{alias.name}' is prohibited."
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            root = node.module.split(".")[0]
            if root in self.FORBIDDEN_MODULES:
                self.violations.append(
                    f"Line {node.lineno}: Import from forbidden module '{node.module}' is prohibited."
                )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in ("__builtins__", "globals", "locals", "vars"):
            self.violations.append(
                f"Line {node.lineno}: Direct access to namespace variable '{node.id}' is prohibited."
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in self.FORBIDDEN_CALLS:
                self.violations.append(
                    f"Line {node.lineno}: Call to dangerous function '{func_name}' is prohibited."
                )
            elif func_name in ("getattr", "setattr", "delattr"):
                if (
                    len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant)
                    and isinstance(node.args[1].value, str)
                ):
                    attr_val = node.args[1].value
                    if attr_val in self.FORBIDDEN_ATTRIBUTES:
                        self.violations.append(
                            f"Line {node.lineno}: Reflection access to forbidden attribute '{attr_val}' is prohibited."
                        )
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in self.FORBIDDEN_ATTRIBUTES:
                self.violations.append(
                    f"Line {node.lineno}: Method call to forbidden attribute '{attr_name}' is prohibited."
                )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in self.FORBIDDEN_ATTRIBUTES:
            self.violations.append(
                f"Line {node.lineno}: Access to sensitive attribute '{node.attr}' is prohibited."
            )
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            if node.slice.value in ("__builtins__", "os", "subprocess", "sys"):
                self.violations.append(
                    f"Line {node.lineno}: Subscript lookup of forbidden key '{node.slice.value}' is prohibited."
                )
        self.generic_visit(node)


def check_ast_safety(code: str) -> Tuple[bool, Optional[str]]:
    """
    Parses Python code and checks for AST safety violations.
    Returns (is_safe, error_message).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"

    visitor = ASTSafetyVisitor()
    visitor.visit(tree)
    if visitor.violations:
        return False, visitor.violations[0]
    return True, None


class Win32JobSandbox:
    """
    Sandboxed execution engine utilizing Win32 Job Objects.
    Enforces memory ceiling, active process limit, and execution timeout.
    """

    def __init__(
        self,
        max_memory_mb: int = 256,
        timeout_seconds: float = 5.0,
        active_process_limit: int = 2,
    ) -> None:
        self.max_memory_mb = max_memory_mb
        self.timeout_seconds = timeout_seconds
        self.active_process_limit = active_process_limit
        self.is_windows = sys.platform == "win32"
        self._kernel32 = (
            ctypes.WinDLL("kernel32", use_last_error=True)
            if self.is_windows
            else None
        )

    @property
    def _use_win32job(self) -> bool:
        return self.is_windows and HAS_WIN32JOB

    def _create_win32job(self) -> Optional[object]:
        """Creates Job Object using pywin32 win32job."""
        try:
            h_job = win32job.CreateJobObject(None, "")
            info = win32job.QueryInformationJobObject(
                h_job, win32job.JobObjectExtendedLimitInformation
            )
            limit_flags = (
                win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                | win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY
                | win32job.JOB_OBJECT_LIMIT_JOB_MEMORY
                | win32job.JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            )
            info["BasicLimitInformation"]["LimitFlags"] = limit_flags
            info["BasicLimitInformation"]["ActiveProcessLimit"] = self.active_process_limit

            mem_bytes = self.max_memory_mb * 1024 * 1024
            info["ProcessMemoryLimit"] = mem_bytes
            info["JobMemoryLimit"] = mem_bytes

            win32job.SetInformationJobObject(
                h_job, win32job.JobObjectExtendedLimitInformation, info
            )
            return h_job
        except Exception:
            return None

    def _create_ctypes_job(self) -> Optional[int]:
        """Creates Job Object using ctypes kernel32 fallback."""
        if not self._kernel32:
            return None
        try:
            h_job = self._kernel32.CreateJobObjectW(None, None)
            if not h_job:
                return None

            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            limit_flags = (
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                | JOB_OBJECT_LIMIT_PROCESS_MEMORY
                | JOB_OBJECT_LIMIT_JOB_MEMORY
                | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            )
            info.BasicLimitInformation.LimitFlags = limit_flags
            info.BasicLimitInformation.ActiveProcessLimit = self.active_process_limit

            mem_bytes = self.max_memory_mb * 1024 * 1024
            info.ProcessMemoryLimit = mem_bytes
            info.JobMemoryLimit = mem_bytes

            res = self._kernel32.SetInformationJobObject(
                h_job,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            if not res:
                self._kernel32.CloseHandle(h_job)
                return None
            return h_job
        except Exception:
            return None

    def _query_peak_memory(self, h_job: object) -> int:
        """Queries peak memory used by the Job Object in bytes."""
        if not h_job:
            return 0
        try:
            if self._use_win32job:
                info = win32job.QueryInformationJobObject(
                    h_job, win32job.JobObjectExtendedLimitInformation
                )
                return int(info.get("PeakJobMemoryUsed", 0))
            elif self._kernel32:
                info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                res = self._kernel32.QueryInformationJobObject(
                    h_job,
                    JobObjectExtendedLimitInformation,
                    ctypes.byref(info),
                    ctypes.sizeof(info),
                    None,
                )
                if res:
                    return int(info.PeakJobMemoryUsed)
        except Exception:
            pass
        return 0

    def _close_job(self, h_job: object) -> None:
        """Closes the Job Object handle."""
        if not h_job:
            return
        try:
            if self._use_win32job:
                win32api.CloseHandle(h_job)
            elif self._kernel32:
                self._kernel32.CloseHandle(h_job)
        except Exception:
            pass

    def run_command(
        self,
        cmd_args: List[str],
        timeout: Optional[float] = None,
        env_vars: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> ExecutionResult:
        """Executes a command within the sandboxed Job Object."""
        effective_timeout = timeout if timeout is not None else self.timeout_seconds
        t0 = time.time()
        env = os.environ.copy()
        # Prevent native BLAS/OMP libraries (e.g. OpenBLAS via numpy) from spawning
        # multi-core thread arenas that breach the 256 MB Win32 Job Object cap.
        for _blas_var in (
            "OPENBLAS_NUM_THREADS",
            "OMP_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
        ):
            env.setdefault(_blas_var, "1")
        if env_vars:
            env.update(env_vars)

        h_job = None
        if self._use_win32job:
            h_job = self._create_win32job()
        if not h_job and self.is_windows:
            h_job = self._create_ctypes_job()

        proc = None
        peak_bytes = 0
        timed_out = False
        stdout = ""
        stderr = ""
        exit_code = -1

        try:
            proc = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                stdin=subprocess.DEVNULL,
                env=env,
                cwd=cwd,
            )

            if h_job:
                try:
                    if self._use_win32job:
                        win32job.AssignProcessToJobObject(h_job, int(proc._handle))
                    elif self._kernel32:
                        self._kernel32.AssignProcessToJobObject(h_job, int(proc._handle))
                except Exception:
                    # Process might have already completed
                    pass

            stdout, stderr = proc.communicate(timeout=effective_timeout)
            exit_code = proc.returncode

        except subprocess.TimeoutExpired:
            timed_out = True
            if proc:
                try:
                    proc.kill()
                    stdout, stderr = proc.communicate()
                except Exception:
                    pass
            exit_code = -1
        except Exception as e:
            stderr = str(e)
            exit_code = -1
        finally:
            if h_job:
                peak_bytes = self._query_peak_memory(h_job)
                self._close_job(h_job)

        duration = round(time.time() - t0, 4)

        # Detect memory breach conditions
        mem_limit_bytes = self.max_memory_mb * 1024 * 1024
        memory_breached = (
            exit_code in (-1073741523, 3221225773, 137)
            or "MemoryError" in (stderr or "")
            or "out of memory" in (stderr or "").lower()
            or (peak_bytes >= mem_limit_bytes and mem_limit_bytes > 0)
        )

        success = (exit_code == 0) and not timed_out and not memory_breached
        error_msg = ""
        if timed_out:
            error_msg = f"Execution timed out after {effective_timeout}s"
        elif memory_breached:
            error_msg = f"Process memory limit exceeded ({self.max_memory_mb} MB ceiling)"
        elif exit_code != 0:
            error_msg = stderr.strip() or f"Process failed with exit code {exit_code}"

        return ExecutionResult(
            success=success,
            stdout=stdout,
            stderr=stderr,
            returncode=exit_code,
            duration_s=duration,
            peak_memory_bytes=peak_bytes,
            timeout=timed_out,
            ast_violation=False,
            error_message=error_msg,
        )

    def run_python_script(
        self,
        script_content: str,
        timeout: Optional[float] = None,
        env_vars: Optional[Dict[str, str]] = None,
        interpreter_path: Optional[str] = None,
    ) -> ExecutionResult:
        """Writes script to a secure temporary file and executes it within the sandbox."""
        py_exe = interpreter_path or sys.executable
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
            tmp.write(script_content)
            tmp_path = tmp.name

        try:
            cmd = [py_exe, "-u", tmp_path]
            return self.run_command(cmd, timeout=timeout, env_vars=env_vars)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass


# Backwards compatibility alias
WindowsJobSandbox = Win32JobSandbox


def execute_sandboxed_code(
    source_code: str,
    test_suite: str,
    language: str = "python",
    timeout: float = 5.0,
    max_memory_mb: int = 256,
) -> ExecutionResult:
    """
    Standardized entrypoint to execute untrusted code and tests in the sandbox.

    Performs:
    1. Pre-execution static AST safety analysis.
    2. Test runner assembly (auto-discovering `test_*` functions).
    3. Kernel-level Win32 Job Object execution with memory & process ceilings.
    """
    lang = language.lower()
    if lang != "python":
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=f"Language '{language}' execution is not supported by Win32 Job sandbox.",
            returncode=-1,
            duration_s=0.0,
            peak_memory_bytes=0,
            timeout=False,
            ast_violation=False,
            error_message=f"Language '{language}' execution is not supported.",
        )

    # 1. AST Safety Screening
    combined_code = f"{source_code}\n\n{test_suite}\n"
    is_safe, violation_msg = check_ast_safety(combined_code)
    if not is_safe:
        err = violation_msg or "AST Security Violation"
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=err,
            returncode=-1,
            duration_s=0.0,
            peak_memory_bytes=0,
            timeout=False,
            ast_violation=True,
            error_message=err,
        )

    # 2. Construct Isolated Runner Script
    runner_script = f"""# Isolated Sandboxed Python Test Runner
import sys

# User Solution
{source_code}

# Test Suite
{test_suite}

# Auto-execute discoverable test functions
_test_funcs = [k for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
if _test_funcs:
    for _tf in _test_funcs:
        globals()[_tf]()
    print(f"Executed {{len(_test_funcs)}} test functions successfully")
else:
    print("Execution completed successfully")
"""

    # 3. Execute inside Win32 Job Object Sandbox
    sandbox = Win32JobSandbox(
        max_memory_mb=max_memory_mb,
        timeout_seconds=timeout,
        active_process_limit=2,
    )
    return sandbox.run_python_script(runner_script, timeout=timeout)
