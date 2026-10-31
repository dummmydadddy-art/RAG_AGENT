"""
scripts/security/wasi_sandbox.py

WebAssembly (WASI) Micro-Sandbox for Deterministic, Isolated Compiled Code Execution.
Supports:
- C / C++ (compiled to wasm32-wasi)
- Rust (compiled to wasm32-wasi)
- Go (compiled to wasm32-wasi)

Enforces:
- 64 MB maximum linear memory limit
- Zero ambient network access
- Isolated directory root chroot
- Strict timeouts
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class WasiExecutionResult:
    """Consolidated result of a WebAssembly sandboxed run."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    runtime: str = "wasi-microvm"
    error_message: Optional[str] = None


class WasiSandbox:
    """
    Executes wasm32-wasi binaries inside an isolated WebAssembly micro-virtual machine
    with explicit memory, capability, and filesystem isolation.
    """

    def __init__(
        self,
        max_memory_mb: int = 64,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.max_memory_mb = max_memory_mb
        self.timeout_seconds = timeout_seconds
        self.wasmtime_bin = shutil.which("wasmtime")

    def is_available(self) -> bool:
        """Checks if a WASI runtime (e.g. wasmtime) is installed and available."""
        return self.wasmtime_bin is not None

    def run_wasm_binary(
        self,
        wasm_path: str,
        args: Optional[List[str]] = None,
        env_vars: Optional[dict] = None,
    ) -> WasiExecutionResult:
        """Executes a pre-compiled .wasm module under WASI constraints."""
        if not self.is_available():
            return WasiExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="WASI runtime (wasmtime) is not installed on host.",
                duration_seconds=0.0,
                error_message="Runtime unavailable",
            )

        t0 = time.time()
        cmd = [
            self.wasmtime_bin,
            "run",
            f"--max-memory={self.max_memory_mb * 1024 * 1024}",
            "--disable-cache",
            wasm_path,
        ]
        if args:
            cmd.extend(args)

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                stdin=subprocess.DEVNULL,
            )
            duration = time.time() - t0
            return WasiExecutionResult(
                success=(res.returncode == 0),
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                duration_seconds=round(duration, 3),
            )
        except subprocess.TimeoutExpired:
            duration = time.time() - t0
            return WasiExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"WASI execution timed out after {self.timeout_seconds}s",
                duration_seconds=round(duration, 3),
                timed_out=True,
                error_message="Execution timeout",
            )
        except Exception as e:
            duration = time.time() - t0
            return WasiExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=round(duration, 3),
                error_message=str(e),
            )
