"""
scripts/launcher/preflight.py

Pre-flight environment diagnostics for the RAG-Agent Windows Launcher:
- Python 3.11+ verification
- PHP 8.3+ detection (PATH, WinGet packages, standard directories)
- Ollama detection (PATH, AppData, Program Files)
- Diagnostic reporting and PowerShell remediation instructions
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class PreflightResult:
    """Diagnostic outcome for a single prerequisite runtime."""

    name: str
    available: bool
    version: Optional[str]
    path: Optional[Path]
    error_message: Optional[str] = None
    remediation: Optional[str] = None


@dataclass
class PreflightReport:
    """Consolidated diagnostic report across all prerequisite runtimes."""

    results: List[PreflightResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.available for r in self.results)

    @property
    def python_result(self) -> Optional[PreflightResult]:
        for r in self.results:
            if r.name == "Python":
                return r
        return None

    @property
    def php_result(self) -> Optional[PreflightResult]:
        for r in self.results:
            if r.name == "PHP":
                return r
        return None

    @property
    def ollama_result(self) -> Optional[PreflightResult]:
        for r in self.results:
            if r.name == "Ollama":
                return r
        return None

    @property
    def python_path(self) -> Optional[Path]:
        res = self.python_result
        return res.path if res and res.available else None

    @property
    def php_path(self) -> Optional[Path]:
        res = self.php_result
        return res.path if res and res.available else None

    @property
    def ollama_path(self) -> Optional[Path]:
        res = self.ollama_result
        return res.path if res and res.available else None

    def format_report(self) -> str:
        lines = [
            "=" * 64,
            "           RAG-Agent Launcher: Pre-Flight Diagnostics",
            "=" * 64,
        ]
        for r in self.results:
            status = "[OK]  " if r.available else "[FAIL]"
            ver = f"v{r.version}" if r.version else "N/A"
            loc = str(r.path) if r.path else "Not found"
            lines.append(f"{status} {r.name:8s}: {ver:12s} ({loc})")
            if not r.available:
                if r.error_message:
                    lines.append(f"       Reason     : {r.error_message}")
                if r.remediation:
                    lines.append(f"       Remediation: {r.remediation}")
        lines.append("=" * 64)
        if self.all_passed:
            lines.append("All pre-flight checks passed successfully.")
        else:
            lines.append("One or more prerequisites are missing. Please remediate before launching.")
        lines.append("=" * 64)
        return "\n".join(lines)

    def print_report(self) -> None:
        print(self.format_report())


def detect_python(min_version: Tuple[int, int] = (3, 11)) -> PreflightResult:
    """Verifies that Python >= min_version is available."""
    # 1. Check current runtime environment first (only if running as an unfrozen script)
    if not getattr(sys, "frozen", False) and sys.version_info[:2] >= min_version:
        major = sys.version_info[0]
        minor = sys.version_info[1]
        micro = sys.version_info[2] if len(sys.version_info) > 2 else 0
        v_str = f"{major}.{minor}.{micro}"
        return PreflightResult(
            name="Python",
            available=True,
            version=v_str,
            path=Path(sys.executable),
        )

    # 2. Check PATH and common launchers
    candidates: List[str] = []
    for cmd in ["python", "python3", "py"]:
        found = shutil.which(cmd)
        if found and found not in candidates:
            candidates.append(found)

    # 3. Check Windows standard installer directories and WinGet locations
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        # Check standard user Python installations (%LOCALAPPDATA%\Programs\Python\Python3*)
        prog_python = Path(local_app_data) / "Programs" / "Python"
        if prog_python.exists():
            try:
                for pdir in sorted(prog_python.glob("Python3*"), reverse=True):
                    pexe = pdir / "python.exe"
                    if pexe.exists() and str(pexe) not in candidates:
                        candidates.append(str(pexe))
            except Exception:
                pass

        # Check WinGet package directory
        winget_dir = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_dir.exists():
            try:
                for pkg_dir in sorted(winget_dir.glob("Python.Python.3*"), reverse=True):
                    pexe = pkg_dir / "python.exe"
                    if pexe.exists() and str(pexe) not in candidates:
                        candidates.append(str(pexe))
            except Exception:
                pass

    # 4. Check Program Files
    for prog_files in [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")]:
        if prog_files:
            try:
                for ver_folder in ["Python313", "Python312", "Python311"]:
                    pf_exe = Path(prog_files) / ver_folder / "python.exe"
                    if pf_exe.exists() and str(pf_exe) not in candidates:
                        candidates.append(str(pf_exe))
            except Exception:
                pass

    for cand in candidates:
        try:
            res = subprocess.run(
                [
                    cand,
                    "-c",
                    "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}\\n{sys.executable}')",
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if res.returncode == 0:
                lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
                if not lines:
                    continue
                v_str = lines[0]
                parts = tuple(map(int, v_str.split(".")[:2]))
                if parts >= min_version:
                    discovered_path = Path(cand)
                    if len(lines) > 1:
                        target = Path(lines[1])
                        if target.exists() and "rag-agent-launcher" not in target.name.lower():
                            discovered_path = target

                    if "rag-agent-launcher" in discovered_path.name.lower():
                        continue
                    if getattr(sys, "frozen", False):
                        try:
                            if discovered_path.resolve() == Path(sys.executable).resolve():
                                continue
                        except Exception:
                            pass

                    return PreflightResult(
                        name="Python",
                        available=True,
                        version=v_str,
                        path=discovered_path,
                    )
        except Exception:
            continue

    return PreflightResult(
        name="Python",
        available=False,
        version=None,
        path=None,
        error_message=f"Python {min_version[0]}.{min_version[1]}+ is not found.",
        remediation="Install Python 3.11 via 'winget install Python.Python.3.11' or https://www.python.org/downloads/",
    )


def detect_php(min_version: Tuple[int, int] = (8, 3)) -> PreflightResult:
    """Detects PHP >= min_version via PATH, WinGet directories, or standard folders."""
    candidate_paths: List[Path] = []

    # 1. Standard PATH lookup
    path_php = shutil.which("php")
    if path_php:
        candidate_paths.append(Path(path_php))

    # 2. WinGet package directory in %LOCALAPPDATA%
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_dir = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_dir.exists():
            for pkg_dir in winget_dir.glob("PHP.PHP.8.3*"):
                php_exe = pkg_dir / "php.exe"
                if php_exe.exists():
                    candidate_paths.append(php_exe)

    # 3. Known standard directories
    candidate_paths.extend(
        [
            Path("C:/tools/php83/php.exe"),
            Path("C:/tools/php/php.exe"),
            Path("C:/php83/php.exe"),
            Path("C:/php/php.exe"),
            Path("C:/Program Files/PHP/v8.3/php.exe"),
            Path("C:/Program Files/PHP/php.exe"),
        ]
    )

    checked_paths = set()
    found_older_version: Optional[str] = None

    for p in candidate_paths:
        resolved_str = str(p.resolve()) if p.exists() else str(p)
        if resolved_str in checked_paths:
            continue
        checked_paths.add(resolved_str)

        if p.exists():
            try:
                res = subprocess.run(
                    [str(p), "-r", "echo PHP_VERSION;"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if res.returncode == 0:
                    v_str = res.stdout.strip()
                    # e.g. 8.3.32 or 8.3.16-dev
                    clean_match = re.match(r"^(\d+)\.(\d+)", v_str)
                    if clean_match:
                        parts = (int(clean_match.group(1)), int(clean_match.group(2)))
                        if parts >= min_version:
                            return PreflightResult(
                                name="PHP",
                                available=True,
                                version=v_str,
                                path=p,
                            )
                        else:
                            found_older_version = v_str
            except Exception:
                continue

    if found_older_version:
        error_msg = f"PHP {min_version[0]}.{min_version[1]}+ required, but found older version {found_older_version}."
    else:
        error_msg = f"PHP {min_version[0]}.{min_version[1]}+ is missing or not found."

    return PreflightResult(
        name="PHP",
        available=False,
        version=found_older_version,
        path=None,
        error_message=error_msg,
        remediation="Install PHP 8.3 via 'winget install PHP.PHP.8.3' or 'choco install php --version=8.3.16'",
    )


def detect_ollama() -> PreflightResult:
    """Detects Ollama on PATH, LocalAppData, or Program Files."""
    candidate_paths: List[Path] = []

    # 1. Standard PATH lookup
    path_ollama = shutil.which("ollama")
    if path_ollama:
        candidate_paths.append(Path(path_ollama))

    # 2. LocalAppData Programs directory
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidate_paths.append(Path(local_app_data) / "Programs" / "Ollama" / "ollama.exe")

    # 3. Standard Program Files
    candidate_paths.append(Path("C:/Program Files/Ollama/ollama.exe"))

    checked_paths = set()
    for p in candidate_paths:
        resolved_str = str(p.resolve()) if p.exists() else str(p)
        if resolved_str in checked_paths:
            continue
        checked_paths.add(resolved_str)

        if p.exists():
            try:
                res = subprocess.run(
                    [str(p), "--version"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if res.returncode == 0:
                    raw = res.stdout.strip()
                    # e.g. "ollama version is 0.40.4"
                    v_str = re.sub(r"^ollama\s+version\s+is\s+", "", raw, flags=re.IGNORECASE).strip()
                    return PreflightResult(
                        name="Ollama",
                        available=True,
                        version=v_str,
                        path=p,
                    )
            except Exception:
                continue

    return PreflightResult(
        name="Ollama",
        available=False,
        version=None,
        path=None,
        error_message="Ollama is not installed or not in PATH.",
        remediation="Install Ollama for Windows via 'winget install Ollama.Ollama' or https://ollama.com/download/windows",
    )


def run_all_preflight_checks() -> PreflightReport:
    """Executes all pre-flight checks and returns a consolidated report."""
    results = [
        detect_python(),
        detect_php(),
        detect_ollama(),
    ]
    return PreflightReport(results=results)
