"""
scripts/security/windows_sandbox.py

Native Win32 Job Object Execution Sandbox for Windows.
Enforces:
- Hard process memory limits (default 256 MB)
- Hard job memory limits
- Active process limits (default <= 2)
- Automatic termination of child process trees on closure (KILL_ON_JOB_CLOSE)
- Strict timeouts and stdin isolation (stdin=subprocess.DEVNULL)
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

# Win32 Constants
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x0100
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x0200
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x0008
JobObjectExtendedLimitInformation = 9


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
class SandboxExecutionResult:
    """Consolidated result of a sandboxed execution."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    memory_breached: bool = False
    error_message: Optional[str] = None


class WindowsJobSandbox:
    """
    Executes commands and Python scripts within an isolated Win32 Job Object
    with strict memory and process limits.
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
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True) if self.is_windows else None

    def _create_configured_job(self) -> Optional[int]:
        """Creates and configures a Win32 Job Object with resource limits."""
        if not self.is_windows or not self._kernel32:
            return None

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

    def run_command(
        self,
        cmd_args: List[str],
        timeout: Optional[float] = None,
        env_vars: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> SandboxExecutionResult:
        """Executes a command within the sandboxed Job Object."""
        effective_timeout = timeout if timeout is not None else self.timeout_seconds
        t0 = time.time()
        h_job = self._create_configured_job()

        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        try:
            # Spawn process with stdin=DEVNULL to prevent pipe inheritance hang
            proc = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                stdin=subprocess.DEVNULL,
                env=env,
                cwd=cwd,
            )

            # Assign process to Job Object immediately
            if h_job and self._kernel32:
                self._kernel32.AssignProcessToJobObject(h_job, int(proc._handle))

            stdout, stderr = proc.communicate(timeout=effective_timeout)
            duration = time.time() - t0
            exit_code = proc.returncode

            # Check for memory termination exit codes on Windows
            # STATUS_COMMITMENT_LIMIT is 0xC000012D (unsigned: 3221225773, signed: -1073741523)
            # Exit code 137 or MemoryError in stderr
            memory_breached = (
                exit_code in (-1073741523, 3221225773, 137)
                or "MemoryError" in (stderr or "")
                or "out of memory" in (stderr or "").lower()
            )

            return SandboxExecutionResult(
                success=(exit_code == 0),
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=round(duration, 3),
                timed_out=False,
                memory_breached=memory_breached,
                error_message=None if exit_code == 0 else f"Process exited with code {exit_code}",
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - t0
            proc.kill()
            stdout, stderr = proc.communicate()
            return SandboxExecutionResult(
                success=False,
                exit_code=-1,
                stdout=stdout or "",
                stderr=stderr or "Execution timed out",
                duration_seconds=round(duration, 3),
                timed_out=True,
                memory_breached=False,
                error_message=f"Execution timed out after {effective_timeout}s",
            )
        except Exception as e:
            duration = time.time() - t0
            return SandboxExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=round(duration, 3),
                timed_out=False,
                memory_breached=False,
                error_message=str(e),
            )
        finally:
            if h_job and self._kernel32:
                self._kernel32.CloseHandle(h_job)

    def run_python_script(
        self,
        script_content: str,
        env_vars: Optional[Dict[str, str]] = None,
        interpreter_path: Optional[str] = None,
    ) -> SandboxExecutionResult:
        """Writes script to a secure temporary file and executes it in the Job Object."""
        python_exe = interpreter_path or sys.executable
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
            tmp.write(script_content)
            tmp_path = tmp.name

        try:
            cmd = [python_exe, "-u", tmp_path]
            return self.run_command(cmd, env_vars=env_vars)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
