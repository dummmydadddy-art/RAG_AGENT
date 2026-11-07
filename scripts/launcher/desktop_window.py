"""
scripts/launcher/desktop_window.py

Native Desktop Window Mode for RAG-Agent:
- Discovers standalone browser runtimes (Microsoft Edge on Windows 10/11, Google Chrome)
- Launches frameless standalone desktop app window (--app mode) without browser chrome (no address bar, no tabs)
- Allocates an isolated app user-data profile in backend/storage/desktop_profile
- Enables tracking of the native window process lifecycle for graceful service termination
- Provides automatic fallback to default web browser when standalone browser is unavailable
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import List, Optional


def find_desktop_browser() -> Optional[Path]:
    """
    Locates a Chromium-based browser executable suitable for --app mode.
    Prioritizes Microsoft Edge (pre-installed on Windows 10/11), followed by Google Chrome.
    """
    # 1. Check Microsoft Edge via PATH and standard Windows locations
    edge_which = shutil.which("msedge.exe") or shutil.which("msedge")
    if edge_which and Path(edge_which).exists():
        return Path(edge_which)

    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    local_app_data = os.environ.get("LOCALAPPDATA", "")

    edge_candidates = [
        Path(program_files_x86) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(program_files) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]
    if local_app_data:
        edge_candidates.append(
            Path(local_app_data) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        )

    for cand in edge_candidates:
        if cand.exists():
            return cand

    # 2. Check Google Chrome via PATH and standard Windows locations
    chrome_which = shutil.which("chrome.exe") or shutil.which("chrome")
    if chrome_which and Path(chrome_which).exists():
        return Path(chrome_which)

    chrome_candidates = [
        Path(program_files) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(program_files_x86) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    if local_app_data:
        chrome_candidates.append(
            Path(local_app_data) / "Google" / "Chrome" / "Application" / "chrome.exe"
        )

    for cand in chrome_candidates:
        if cand.exists():
            return cand

    return None


def build_app_window_command(
    browser_path: Path,
    url: str,
    app_id: str = "rag-agent",
    width: int = 1300,
    height: int = 880,
    user_data_dir: Optional[Path] = None,
) -> List[str]:
    """
    Builds the command list for launching Chromium in standalone --app window mode.
    """
    cmd = [
        str(browser_path),
        f"--app={url}",
        f"--window-size={width},{height}",
        f"--app-id={app_id}",
    ]
    if user_data_dir:
        cmd.append(f"--user-data-dir={user_data_dir}")

    # Prevent first-run dialogs and default browser prompts
    cmd.extend([
        "--no-first-run",
        "--no-default-browser-check",
    ])
    return cmd


def launch_desktop_window(
    url: str,
    workspace_root: Path,
    width: int = 1300,
    height: int = 880,
    app_id: str = "rag-agent",
    prefer_browser: bool = False,
) -> Optional[subprocess.Popen]:
    """
    Launches RAG-Agent in a dedicated frameless desktop window.

    Returns the subprocess.Popen handle of the desktop window for lifecycle tracking,
    or None if fallback to default web browser was used.
    """
    if prefer_browser:
        print("[*] Opening application in standard web browser...")
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"[!] Could not launch web browser: {e}", file=sys.stderr)
        return None

    browser_path = find_desktop_browser()
    if not browser_path:
        print("[!] Standalone browser (Edge/Chrome) not detected. Falling back to default web browser...")
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"[!] Could not launch web browser: {e}", file=sys.stderr)
        return None

    # Dedicated isolated profile directory
    profile_dir = workspace_root / "backend" / "storage" / "desktop_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    cmd = build_app_window_command(
        browser_path=browser_path,
        url=url,
        app_id=app_id,
        width=width,
        height=height,
        user_data_dir=profile_dir,
    )

    print(f"[*] Launching native desktop app window using: {browser_path.name}")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(workspace_root),
        )
        print(f"[+] Native desktop app window launched (PID: {proc.pid}).")
        return proc
    except Exception as e:
        print(f"[!] Failed to launch native window ({e}). Falling back to web browser...", file=sys.stderr)
        webbrowser.open(url)
        return None
