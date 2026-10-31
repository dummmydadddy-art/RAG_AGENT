"""
scripts/launcher/installer.py

Virtual environment bootstrapping and dependency management for RAG-Agent:
- Detects existing .venv in workspace
- Automatically creates .venv via host Python if absent
- Fast bytecode import check to skip pip install on warm starts
- Automatic pip installation of requirements.txt when needed
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

from scripts.launcher.preflight import detect_python

REQUIRED_MODULES = [
    "fastapi",
    "uvicorn",
    "sse_starlette",
    "pydantic",
    "httpx",
    "yaml",
    "pytest",
    "pint",
    "sympy",
    "psutil",
]


def find_venv_python(workspace_root: Path) -> Optional[Path]:
    """Locates the Python binary within workspace_root/.venv."""
    candidates = [
        workspace_root / ".venv" / "Scripts" / "python.exe",  # Windows standard
        workspace_root / ".venv" / "bin" / "python",         # POSIX standard
    ]
    for cand in candidates:
        if cand.exists():
            return cand
    return None


def check_bytecode_imports(venv_python: Path) -> bool:
    """Fast-path check: verifies required packages import cleanly without invoking pip."""
    if not venv_python.exists():
        return False
    import_stmt = "import " + ", ".join(REQUIRED_MODULES)
    try:
        res = subprocess.run(
            [str(venv_python), "-c", import_stmt],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return res.returncode == 0
    except Exception:
        return False


def is_launcher_binary(path: Optional[Path]) -> bool:
    """Checks if a path points to the compiled launcher executable rather than standard Python."""
    if not path:
        return False
    name = path.name.lower()
    if "rag-agent-launcher" in name:
        return True
    if getattr(sys, "frozen", False):
        try:
            if path.resolve() == Path(sys.executable).resolve():
                return True
        except Exception:
            pass
    return False


def ensure_environment(
    workspace_root: Path,
    host_python: Optional[Path] = None,
    force_install: bool = False,
) -> Path:
    """
    Ensures a valid virtual environment with all required dependencies is ready.

    Returns the path to the virtualenv's Python binary.
    """
    venv_python = find_venv_python(workspace_root)
    needs_install = force_install

    # 1. Create .venv if absent
    if not venv_python:
        print("[*] Virtual environment (.venv) not found. Bootstrapping new environment...")
        if host_python and not is_launcher_binary(host_python):
            resolved_host = host_python
        else:
            # Re-resolve to a valid host system Python interpreter
            py_diag = detect_python()
            if py_diag.available and py_diag.path and not is_launcher_binary(py_diag.path):
                resolved_host = py_diag.path
            elif not getattr(sys, "frozen", False) and sys.version_info[:2] >= (3, 11) and not is_launcher_binary(Path(sys.executable)):
                resolved_host = Path(sys.executable)
            else:
                resolved_host = None

            if not resolved_host or is_launcher_binary(resolved_host):
                raise RuntimeError(
                    "Cannot bootstrap .venv: A host Python 3.11+ interpreter could not be located."
                )

        venv_dir = workspace_root / ".venv"
        print(f"[*] Running: {resolved_host} -m venv {venv_dir}")
        res = subprocess.run(
            [str(resolved_host), "-m", "venv", str(venv_dir)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if res.returncode != 0:
            raise RuntimeError(
                f"Failed to create virtual environment:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
            )

        venv_python = find_venv_python(workspace_root)
        if not venv_python:
            raise RuntimeError(f"Virtual environment created at {venv_dir} but python binary not found.")
        needs_install = True
        print("[+] Virtual environment created successfully.")
    else:
        # 2. Check bytecode imports if venv already exists
        if not needs_install:
            print("[*] Verifying existing Python environment imports...")
            if check_bytecode_imports(venv_python):
                print("[+] Fast-path: all core modules verified in .venv.")
                return venv_python
            else:
                print("[-] One or more core modules missing. Triggering pip installation...")
                needs_install = True

    # 3. Run pip install requirements.txt
    req_file = workspace_root / "requirements.txt"
    if req_file.exists():
        print(f"[*] Installing dependencies from {req_file.name}...")
        res = subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-r", str(req_file)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if res.returncode != 0:
            raise RuntimeError(
                f"Failed to install requirements.txt:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
            )
        print("[+] Dependencies installed successfully.")
    else:
        print(f"[!] Warning: {req_file} not found; skipping pip install.")

    return venv_python
