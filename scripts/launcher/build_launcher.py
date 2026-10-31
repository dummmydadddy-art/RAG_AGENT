"""
scripts/launcher/build_launcher.py

Automated PyInstaller build script for RAG-Agent:
- Ensures pyinstaller is installed in active .venv
- Compiles scripts/launcher/launcher.py into dist/RAG-Agent-Launcher.exe (--onefile, --console)
- Executes post-build verification gates: --help and --check-only
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def get_workspace_root() -> Path:
    """Resolves repository workspace root."""
    return Path(__file__).resolve().parents[2]


def ensure_pyinstaller(venv_python: Path) -> None:
    """Ensures pyinstaller is installed in the target environment."""
    print("[*] Checking for PyInstaller...")
    try:
        res = subprocess.run(
            [str(venv_python), "-m", "PyInstaller", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            print(f"[+] PyInstaller is installed (v{res.stdout.strip()}).")
            return
    except Exception:
        pass

    print("[*] Installing pyinstaller via pip...")
    res = subprocess.run(
        [str(venv_python), "-m", "pip", "install", "pyinstaller"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Failed to install PyInstaller:\n{res.stderr}")
    print("[+] PyInstaller installed successfully.")


def build_executable(workspace_root: Path, venv_python: Path) -> Path:
    """Compiles launcher into dist/RAG-Agent-Launcher.exe."""
    launcher_entrypoint = workspace_root / "scripts" / "launcher" / "launcher.py"
    dist_dir = workspace_root / "dist"
    build_dir = workspace_root / "build" / "launcher"

    dist_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)

    target_exe = dist_dir / "RAG-Agent-Launcher.exe"

    pyinstaller_args = [
        str(venv_python),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        "--name",
        "RAG-Agent-Launcher",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(build_dir),
        "--specpath",
        str(build_dir),
        "--paths",
        str(workspace_root),
        # Hidden imports
        "--hidden-import",
        "urllib.request",
        "--hidden-import",
        "webbrowser",
        "--hidden-import",
        "subprocess",
        "--hidden-import",
        "signal",
        "--hidden-import",
        "socket",
        "--hidden-import",
        "ctypes",
        "--hidden-import",
        "ctypes.wintypes",
        "--hidden-import",
        "scripts.launcher.preflight",
        "--hidden-import",
        "scripts.launcher.installer",
        "--hidden-import",
        "scripts.launcher.model_checker",
        "--hidden-import",
        "scripts.launcher.supervisor",
        "--hidden-import",
        "scripts.launcher.launcher",
        "--hidden-import",
        "scripts.security.windows_sandbox",
        str(launcher_entrypoint),
    ]

    print(f"[*] Compiling {launcher_entrypoint.name} via PyInstaller...")
    start_time = time.time()
    res = subprocess.run(
        pyinstaller_args,
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
        timeout=300,
    )
    duration = time.time() - start_time

    if res.returncode != 0:
        print(f"[ERROR] PyInstaller compilation failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}", file=sys.stderr)
        raise RuntimeError("PyInstaller compilation failed.")

    if not target_exe.exists():
        raise FileNotFoundError(f"Expected compiled binary not found at {target_exe}")

    size_mb = target_exe.stat().st_size / (1024 * 1024)
    print(f"[+] Build complete in {duration:.2f}s!")
    print(f"[+] Executable artifact: {target_exe} ({size_mb:.2f} MB)")
    return target_exe


def verify_executable(target_exe: Path, workspace_root: Path) -> None:
    """Runs verification gates on the compiled executable."""
    print("\n" + "=" * 64)
    print("      Post-Build Verification Gates for RAG-Agent-Launcher.exe")
    print("=" * 64)

    # Gate 1: --help verification
    print("[*] Gate 1: Executing --help...")
    res = subprocess.run(
        [str(target_exe), "--help"],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=str(workspace_root),
    )
    if res.returncode != 0:
        raise RuntimeError(f"Gate 1 failed: --help returned {res.returncode}:\n{res.stderr}")
    assert "--check-only" in res.stdout
    assert "--workspace" in res.stdout
    print("[OK] Gate 1 passed: CLI --help responsive.")

    # Gate 2: --check-only verification
    print("[*] Gate 2: Executing --check-only...")
    res = subprocess.run(
        [str(target_exe), "--check-only"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(workspace_root),
    )
    if res.returncode != 0:
        raise RuntimeError(f"Gate 2 failed: --check-only returned {res.returncode}:\n{res.stderr}\nSTDOUT:\n{res.stdout}")
    assert "Pre-Flight Diagnostics" in res.stdout
    assert "Python" in res.stdout
    assert "PHP" in res.stdout
    assert "Ollama" in res.stdout
    assert "All check-only diagnostics completed successfully" in res.stdout or "completed successfully" in res.stdout
    print("[OK] Gate 2 passed: Standalone pre-flight & diagnostics verified.")
    print("=" * 64)
    print(" ALL VERIFICATION GATES PASSED CLEANLY!")
    print("=" * 64)


def main() -> int:
    workspace_root = get_workspace_root()
    venv_python = workspace_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        venv_python = Path(sys.executable)

    print("=" * 64)
    print("       RAG-Agent Launcher Automated Build System")
    print("=" * 64)
    print(f"[*] Workspace Root: {workspace_root}")
    print(f"[*] Python Runtime: {venv_python}")

    ensure_pyinstaller(venv_python)
    target_exe = build_executable(workspace_root, venv_python)
    verify_executable(target_exe, workspace_root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
