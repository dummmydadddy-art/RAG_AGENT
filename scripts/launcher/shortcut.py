"""
scripts/launcher/shortcut.py

Windows Shortcut (.lnk) Generator for RAG-Agent:
- Resolves authoritative Windows Desktop and Start Menu Programs paths via Win32 Shell API
  with PowerShell [Environment]::GetFolderPath and profile environment fallbacks
- Binds shortcut to RAG-Agent-Launcher.exe (or python launcher.py in dev mode)
- Passes CLI arguments (--workspace "<path>") to ensure deterministic directory resolution
- Associates bundled assets/icon.ico (or embedded PE icon) for high-resolution desktop and taskbar presentation
- Creates 'RAG Agent.lnk' on user's Desktop and Start Menu for instant one-click launch
"""

from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

CSIDL_PROGRAMS = 0x0002
CSIDL_DESKTOPDIRECTORY = 0x0010


def get_desktop_dir() -> Path:
    """
    Resolves the authoritative Windows Desktop directory for the current user.
    Uses Win32 SHGetFolderPathW to respect localized and redirected user folders (e.g. OneDrive),
    with PowerShell [Environment]::GetFolderPath and profile environment fallbacks.
    """
    if sys.platform == "win32":
        try:
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOPDIRECTORY, None, 0, buf) == 0:
                if buf.value:
                    return Path(buf.value)
        except Exception:
            pass

        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                return Path(res.stdout.strip())
        except Exception:
            pass

    # Fallback to USERPROFILE / Desktop
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        return Path(user_profile) / "Desktop"

    return Path.home() / "Desktop"


def get_start_menu_programs_dir() -> Path:
    """
    Resolves the user's Start Menu Programs directory.
    Uses Win32 SHGetFolderPathW, PowerShell [Environment]::GetFolderPath, and APPDATA fallbacks.
    """
    if sys.platform == "win32":
        try:
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PROGRAMS, None, 0, buf) == 0:
                if buf.value:
                    return Path(buf.value)
        except Exception:
            pass

        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", "[Environment]::GetFolderPath('Programs')"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                return Path(res.stdout.strip())
        except Exception:
            pass

    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"

    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def resolve_target_executable(workspace_root: Path) -> Tuple[Path, str]:
    """
    Determines the launcher executable target and CLI arguments for the shortcut.
    Always includes --workspace to ensure the launcher binds to the correct project root
    regardless of how or from where the shortcut is invoked.
    """
    resolved_root = workspace_root.resolve()
    ws_arg = f'--workspace "{resolved_root}"'

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve(), ws_arg

    dist_exe = workspace_root / "dist" / "RAG-Agent-Launcher.exe"
    if dist_exe.exists():
        return dist_exe.resolve(), ws_arg

    # Development fallback: point to host Python interpreter executing launcher.py
    launcher_py = workspace_root / "scripts" / "launcher" / "launcher.py"
    return Path(sys.executable).resolve(), f'"{launcher_py.resolve()}" {ws_arg}'


def create_windows_shortcut(
    shortcut_path: Path,
    target_path: Path,
    working_dir: Path,
    arguments: str = "",
    icon_path: Optional[Path] = None,
    description: str = "RAG Agent - Local Polyglot AI Coding Assistant",
) -> bool:
    """
    Creates a Windows .lnk shortcut using WScript.Shell via PowerShell Base64 EncodedCommand.
    Uses UTF-16LE encoding to completely eliminate command-line quotation stripping and parsing bugs.
    """
    shortcut_path = Path(shortcut_path).resolve()
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)

    # Sanitize and quote paths for PowerShell script string
    s_path = str(shortcut_path).replace("'", "''")
    t_path = str(target_path).replace("'", "''")
    w_dir = str(working_dir).replace("'", "''")
    args = arguments.replace("'", "''")
    desc = description.replace("'", "''")

    icon_clause = ""
    if icon_path and Path(icon_path).exists():
        i_path = str(Path(icon_path).resolve()).replace("'", "''")
        if Path(icon_path).suffix.lower() == ".exe":
            icon_clause = f"$s.IconLocation = '{i_path},0'; "
        else:
            icon_clause = f"$s.IconLocation = '{i_path}'; "
    elif target_path and target_path.exists() and target_path.suffix.lower() == ".exe":
        t_resolved = str(target_path.resolve()).replace("'", "''")
        icon_clause = f"$s.IconLocation = '{t_resolved},0'; "

    ps_script = (
        f"$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{s_path}'); "
        f"$s.TargetPath = '{t_path}'; "
        f"$s.WorkingDirectory = '{w_dir}'; "
        f"$s.Arguments = '{args}'; "
        f"$s.Description = '{desc}'; "
        f"{icon_clause}"
        f"$s.Save();"
    )

    try:
        encoded_script = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded_script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return res.returncode == 0 and shortcut_path.exists()
    except Exception as e:
        print(f"[!] Warning: Could not create shortcut at {shortcut_path}: {e}", file=sys.stderr)
        return False


def ensure_desktop_and_start_menu_shortcuts(
    workspace_root: Path,
    name: str = "RAG Agent.lnk",
    icon_path: Optional[Path] = None,
    force: bool = False,
) -> Dict[str, Optional[Path]]:
    """
    Creates desktop and start menu shortcuts if they do not exist or if force=True.
    """
    resolved_icon = icon_path or (workspace_root / "assets" / "icon.ico")
    if not resolved_icon.exists() and getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bundled = Path(meipass) / "assets" / "icon.ico"
            if bundled.exists():
                resolved_icon = bundled

    if not resolved_icon.exists():
        resolved_icon = None

    desktop_dir = get_desktop_dir()
    desktop_shortcut = desktop_dir / name
    programs_dir = get_start_menu_programs_dir()
    start_menu_shortcut = programs_dir / name

    results: Dict[str, Optional[Path]] = {
        "desktop": None,
        "start_menu": None,
    }

    target_exe, args = resolve_target_executable(workspace_root)

    # Desktop shortcut
    if desktop_shortcut.exists() and not force:
        print(f"[+] Desktop shortcut already present: {desktop_shortcut}")
        results["desktop"] = desktop_shortcut
    else:
        print(f"[*] Creating Desktop shortcut: {desktop_shortcut}...")
        ok = create_windows_shortcut(
            shortcut_path=desktop_shortcut,
            target_path=target_exe,
            working_dir=workspace_root,
            arguments=args,
            icon_path=resolved_icon,
        )
        if ok:
            print(f"[+] Desktop shortcut created successfully.")
            results["desktop"] = desktop_shortcut
        else:
            print(f"[!] Failed to create Desktop shortcut.")

    # Start Menu shortcut
    if programs_dir.exists():
        if start_menu_shortcut.exists() and not force:
            results["start_menu"] = start_menu_shortcut
        else:
            ok_sm = create_windows_shortcut(
                shortcut_path=start_menu_shortcut,
                target_path=target_exe,
                working_dir=workspace_root,
                arguments=args,
                icon_path=resolved_icon,
            )
            if ok_sm:
                results["start_menu"] = start_menu_shortcut

    return results
