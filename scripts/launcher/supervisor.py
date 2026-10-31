"""
scripts/launcher/supervisor.py

Unified Multi-Service Supervisor for RAG-Agent on Windows:
- Win32 Job Object isolation with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (0x2000)
- Explicit PID tree tracking ensuring external background tasks are never terminated
- Standard output and error redirection to rotating log files in evals/logs/
- Signal handling for SIGINT, SIGTERM, and Windows Console Close events
- Safe port detection to avoid binding collisions
"""

from __future__ import annotations

import ctypes
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TextIO

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectExtendedLimitInformation = 9


def assign_process_to_job(h_job: int, proc_handle: int) -> bool:
    """Safely assigns a process handle to a Win32 Job Object."""
    if sys.platform != "win32" or not h_job or not proc_handle:
        return False
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        res = kernel32.AssignProcessToJobObject(h_job, proc_handle)
        return bool(res)
    except Exception:
        return False


class MultiServiceSupervisor:
    """
    Supervises child service processes under a Win32 Job Object sandbox.
    Explicitly tracks spawned child PIDs to ensure external tasks are never disturbed.
    """

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.log_dir = workspace_root / "evals" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.processes: Dict[str, subprocess.Popen] = {}
        self.spawned_pids: Set[int] = set()
        self.external_services: Dict[str, int] = {}
        self._log_handles: Dict[str, TextIO] = {}
        self._is_shutdown = False

        self.h_job = self._init_win32_job()
        self._register_signal_handlers()

    def _init_win32_job(self) -> Optional[int]:
        """Initializes a Win32 Job Object configured with KILL_ON_JOB_CLOSE."""
        if sys.platform != "win32":
            return None
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            h_job = kernel32.CreateJobObjectW(None, None)
            if not h_job:
                return None

            from scripts.security.windows_sandbox import (
                JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
            )

            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            res = kernel32.SetInformationJobObject(
                h_job,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            if not res:
                kernel32.CloseHandle(h_job)
                return None
            return h_job
        except Exception:
            return None

    def _register_signal_handlers(self) -> None:
        """Registers handlers for SIGINT, SIGTERM, and Windows Console close events."""
        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except Exception:
            pass

        if sys.platform == "win32":
            try:
                HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)

                def console_ctrl_handler(ctrl_type: int) -> bool:
                    # 0: CTRL_C, 1: CTRL_BREAK, 2: CTRL_CLOSE, 5: LOGOFF, 6: SHUTDOWN
                    self.shutdown()
                    return True

                self._ctrl_handler = HandlerRoutine(console_ctrl_handler)
                ctypes.windll.kernel32.SetConsoleCtrlHandler(self._ctrl_handler, True)
            except Exception:
                pass

    def _handle_signal(self, signum: int, frame: Any) -> None:
        self.shutdown()
        sys.exit(0)

    def is_port_listening(
        self, port: int, host: str = "127.0.0.1", timeout: float = 0.5
    ) -> bool:
        """Probes whether a local TCP port is already open and accepting connections."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    def register_external_service(self, name: str, port: int) -> None:
        """
        Marks a service as externally running.
        The supervisor will NOT spawn this service and will NEVER terminate it on shutdown.
        """
        self.external_services[name] = port

    def is_external(self, name: str) -> bool:
        """Checks if a service was registered as externally managed."""
        return name in self.external_services

    def assign_process_to_job(self, proc: Any) -> bool:
        """
        Safely assigns a process (subprocess.Popen or handle) to this supervisor's Win32 Job Object.
        """
        if sys.platform != "win32" or not self.h_job or not proc:
            return False
        try:
            handle = getattr(proc, "_handle", None)
            if handle is None and isinstance(proc, int):
                handle = proc
            if handle is not None:
                return assign_process_to_job(self.h_job, int(handle))
        except Exception:
            return False
        return False

    def spawn_service(
        self,
        name: str,
        cmd: List[str],
        cwd: Path,
        env: Optional[Dict[str, str]] = None,
    ) -> subprocess.Popen:
        """
        Spawns a child service, isolates it in the Win32 Job Object, and redirects stdout/stderr.
        """
        log_path = self.log_dir / f"{name}.log"
        log_file = open(log_path, "a", encoding="utf-8")
        self._log_handles[name] = log_file

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=log_file,
            stderr=log_file,
            env=merged_env,
            creationflags=creationflags,
        )

        if self.h_job and sys.platform == "win32":
            self.assign_process_to_job(proc)

        self.processes[name] = proc
        self.spawned_pids.add(proc.pid)
        return proc

    def shutdown(self) -> None:
        """
        Gracefully terminates all child processes spawned by this supervisor.
        Strictly preserves pre-existing and external processes.
        """
        if self._is_shutdown:
            return
        self._is_shutdown = True

        print("[*] Initiating graceful shutdown of supervised services...")
        for name, proc in list(self.processes.items()):
            if self.is_external(name):
                continue

            if proc.poll() is None:
                try:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3.0)
                    except subprocess.TimeoutExpired:
                        if sys.platform == "win32":
                            subprocess.run(
                                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                capture_output=True,
                            )
                        else:
                            proc.kill()
                except Exception:
                    pass

        # Close Win32 Job Object handle
        if self.h_job and sys.platform == "win32":
            try:
                ctypes.windll.kernel32.CloseHandle(self.h_job)
            except Exception:
                pass
            self.h_job = None

        # Close all open log file descriptors
        for name, handle in list(self._log_handles.items()):
            try:
                handle.flush()
                handle.close()
            except Exception:
                pass
        self._log_handles.clear()
        self.processes.clear()
        self.spawned_pids.clear()
        print("[+] All supervised child services stopped cleanly.")
