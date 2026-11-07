"""
tests/unit/test_desktop_app_integration.py

Comprehensive unit tests for desktop app mode and shortcut integration:
1. Windows Desktop and Start Menu shortcut creation and path resolution
2. Standalone desktop app window mode (Edge/Chrome --app discovery and arguments)
3. App window process tracking and supervisor lifecycle coordination
4. One-time setup vs instant subsequent launch (.installed.json marker)
5. Backend failure detection and workspace movement validation
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.launcher.desktop_window import (
    build_app_window_command,
    find_desktop_browser,
    launch_desktop_window,
)
from scripts.launcher.installer import (
    clear_installation_marker,
    get_installation_marker_path,
    is_installed,
    mark_as_installed,
)
from scripts.launcher.shortcut import (
    create_windows_shortcut,
    ensure_desktop_and_start_menu_shortcuts,
    get_desktop_dir,
    get_start_menu_programs_dir,
    resolve_target_executable,
)


# ============================================================================
# 1. Shortcut Creation & Resolution Tests
# ============================================================================


def test_get_desktop_dir_via_ctypes():
    """Resolves desktop directory via Win32 SHGetFolderPathW when available."""
    fake_desktop = r"C:\Users\TestUser\Desktop"
    if sys.platform == "win32":
        with patch("ctypes.create_unicode_buffer") as mock_buf:
            buf_inst = MagicMock()
            buf_inst.value = fake_desktop
            mock_buf.return_value = buf_inst
            with patch("ctypes.windll.shell32.SHGetFolderPathW", return_value=0):
                d = get_desktop_dir()
                assert d == Path(fake_desktop)


def test_get_desktop_dir_fallback():
    """Falls back to USERPROFILE/Desktop or Path.home()/Desktop."""
    with patch("sys.platform", "win32"):
        with patch.dict(os.environ, {"USERPROFILE": r"C:\Users\FallbackUser"}):
            with patch("ctypes.windll.shell32.SHGetFolderPathW", side_effect=Exception("API error")), patch(
                "subprocess.run", side_effect=Exception("PowerShell unavailable")
            ):
                d = get_desktop_dir()
                assert d == Path(r"C:\Users\FallbackUser\Desktop")


def test_get_start_menu_programs_dir():
    """Resolves Start Menu Programs folder."""
    with patch.dict(os.environ, {"APPDATA": r"C:\Users\FallbackUser\AppData\Roaming"}):
        if sys.platform == "win32":
            with patch("ctypes.windll.shell32.SHGetFolderPathW", return_value=1), patch(
                "subprocess.run", side_effect=Exception("PS error")
            ):
                p = get_start_menu_programs_dir()
                assert p == Path(r"C:\Users\FallbackUser\AppData\Roaming\Microsoft\Windows\Start Menu\Programs")


def test_resolve_target_executable_frozen():
    """When sys.frozen is True, target path is sys.executable with --workspace argument."""
    fake_exe = Path(r"C:\RAG-Agent\RAG-Agent-Launcher.exe")
    with patch("sys.frozen", True, create=True), patch("sys.executable", str(fake_exe)):
        target, args = resolve_target_executable(fake_exe.parent)
        assert target == fake_exe
        assert f'--workspace "{fake_exe.parent.resolve()}"' in args


def test_resolve_target_executable_dist_exe(tmp_path: Path):
    """When dist/RAG-Agent-Launcher.exe exists, target is the compiled executable with workspace argument."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    launcher_exe = dist_dir / "RAG-Agent-Launcher.exe"
    launcher_exe.write_text("")

    with patch("sys.frozen", False, create=True):
        target, args = resolve_target_executable(tmp_path)
        assert target == launcher_exe.resolve()
        assert f'--workspace "{tmp_path.resolve()}"' in args


def test_resolve_target_executable_dev_mode(tmp_path: Path):
    """In dev mode without dist exe, target is Python with scripts/launcher/launcher.py and workspace args."""
    with patch("sys.frozen", False, create=True):
        target, args = resolve_target_executable(tmp_path)
        assert target == Path(sys.executable).resolve()
        assert "launcher.py" in args
        assert f'--workspace "{tmp_path.resolve()}"' in args


def test_create_windows_shortcut_success(tmp_path: Path):
    """Generates PowerShell command using Base64 EncodedCommand and successfully creates shortcut."""
    shortcut_path = tmp_path / "RAG Agent.lnk"
    target_path = tmp_path / "RAG-Agent-Launcher.exe"
    working_dir = tmp_path
    icon_path = tmp_path / "icon.ico"
    target_path.write_text("")
    icon_path.write_text("")

    def fake_run(cmd, *args, **kwargs):
        shortcut_path.write_text("fake_lnk")
        return MagicMock(returncode=0)

    with patch("subprocess.run", side_effect=fake_run) as mock_run:
        res = create_windows_shortcut(
            shortcut_path=shortcut_path,
            target_path=target_path,
            working_dir=working_dir,
            arguments=f'--workspace "{working_dir}"',
            icon_path=icon_path,
            description="RAG Agent Test",
        )
        assert res is True
        assert shortcut_path.exists()
        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        assert "-EncodedCommand" in cmd_args
        # Decode the script from base64
        enc_idx = cmd_args.index("-EncodedCommand") + 1
        decoded_script = base64.b64decode(cmd_args[enc_idx]).decode("utf-16le")
        assert "WScript.Shell" in decoded_script
        assert "CreateShortcut" in decoded_script
        assert str(target_path) in decoded_script


def test_create_windows_shortcut_failure(tmp_path: Path):
    """Returns False when PowerShell invocation fails."""
    shortcut_path = tmp_path / "Failed.lnk"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="Failed to create shortcut")
        res = create_windows_shortcut(
            shortcut_path=shortcut_path,
            target_path=tmp_path / "test.exe",
            working_dir=tmp_path,
        )
        assert res is False
        assert not shortcut_path.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only shortcut integration test")
def test_create_windows_shortcut_real_windows(tmp_path: Path):
    """Performs real end-to-end Windows shortcut creation via WScript.Shell without mocking."""
    shortcut_path = tmp_path / "Real_Test.lnk"
    target_path = Path(sys.executable)
    working_dir = tmp_path
    args = f'--workspace "{tmp_path}" --test-flag'

    ok = create_windows_shortcut(
        shortcut_path=shortcut_path,
        target_path=target_path,
        working_dir=working_dir,
        arguments=args,
        description="Live Windows Shortcut Test",
    )
    assert ok is True
    assert shortcut_path.exists()
    assert shortcut_path.stat().st_size > 0


def test_ensure_desktop_and_start_menu_shortcuts_skips_when_exists(tmp_path: Path):
    """Does not re-run shortcut creation if shortcut already exists and force=False."""
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir()
    existing_lnk = desktop_dir / "RAG Agent.lnk"
    existing_lnk.write_text("existing")

    with patch("scripts.launcher.shortcut.get_desktop_dir", return_value=desktop_dir), patch(
        "scripts.launcher.shortcut.get_start_menu_programs_dir", return_value=tmp_path / "Programs"
    ), patch("scripts.launcher.shortcut.create_windows_shortcut") as mock_create:
        res = ensure_desktop_and_start_menu_shortcuts(tmp_path, force=False)
        assert res["desktop"] == existing_lnk
        mock_create.assert_not_called()


def test_ensure_desktop_and_start_menu_shortcuts_creates_when_missing(tmp_path: Path):
    """Creates shortcut when not present on desktop."""
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir()
    programs_dir = tmp_path / "Programs"
    programs_dir.mkdir()

    with patch("scripts.launcher.shortcut.get_desktop_dir", return_value=desktop_dir), patch(
        "scripts.launcher.shortcut.get_start_menu_programs_dir", return_value=programs_dir
    ), patch("scripts.launcher.shortcut.create_windows_shortcut", return_value=True) as mock_create:
        res = ensure_desktop_and_start_menu_shortcuts(tmp_path, force=False)
        assert res["desktop"] == desktop_dir / "RAG Agent.lnk"
        assert mock_create.call_count >= 1


def test_ensure_desktop_and_start_menu_shortcuts_force_recreates(tmp_path: Path):
    """Re-creates shortcut even when present if force=True."""
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir()
    existing_lnk = desktop_dir / "RAG Agent.lnk"
    existing_lnk.write_text("existing")

    with patch("scripts.launcher.shortcut.get_desktop_dir", return_value=desktop_dir), patch(
        "scripts.launcher.shortcut.get_start_menu_programs_dir", return_value=tmp_path / "Programs"
    ), patch("scripts.launcher.shortcut.create_windows_shortcut", return_value=True) as mock_create:
        res = ensure_desktop_and_start_menu_shortcuts(tmp_path, force=True)
        assert res["desktop"] == existing_lnk
        assert mock_create.call_count >= 1


# ============================================================================
# 2. Native Desktop Window Mode Tests
# ============================================================================


def test_find_desktop_browser_winreg(tmp_path: Path):
    """Discovers browser via Windows App Paths registry."""
    fake_edge = tmp_path / "msedge.exe"
    fake_edge.write_text("")

    if sys.platform == "win32":
        mock_winreg = MagicMock()
        mock_key = MagicMock()
        mock_key.__enter__.return_value = mock_key
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = (str(fake_edge), 1)

        with patch.dict("sys.modules", {"winreg": mock_winreg}):
            browser = find_desktop_browser()
            assert browser == fake_edge


def test_find_desktop_browser_edge_priority(tmp_path: Path):
    """Discovers Microsoft Edge with top priority."""
    fake_edge = tmp_path / "msedge.exe"
    fake_edge.write_text("")
    with patch("shutil.which", return_value=str(fake_edge)), patch.dict("sys.modules", {"winreg": None}):
        browser = find_desktop_browser()
        assert browser == fake_edge


def test_find_desktop_browser_chrome_fallback(tmp_path: Path):
    """Falls back to Google Chrome if Edge is not found."""
    fake_chrome = tmp_path / "chrome.exe"
    fake_chrome.write_text("")

    def fake_which(cmd):
        if "chrome" in cmd:
            return str(fake_chrome)
        return None

    with patch.dict("sys.modules", {"winreg": None}), patch(
        "shutil.which", side_effect=fake_which
    ), patch(
        "scripts.launcher.desktop_window.os.environ.get", return_value=str(tmp_path / "nonexistent")
    ):
        browser = find_desktop_browser()
        assert browser == fake_chrome


def test_find_desktop_browser_none_found():
    """Returns None when neither Edge nor Chrome is found."""
    with patch.dict("sys.modules", {"winreg": None}), patch(
        "shutil.which", return_value=None
    ), patch("pathlib.Path.exists", return_value=False):
        browser = find_desktop_browser()
        assert browser is None


def test_build_app_window_command():
    """Constructs --app standalone window command line arguments with crash bubble suppression."""
    browser = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    url = "http://127.0.0.1:8080"
    user_data = Path(r"C:\RAG-Agent\backend\storage\desktop_profile")

    cmd = build_app_window_command(
        browser_path=browser,
        url=url,
        app_id="rag-agent",
        width=1300,
        height=880,
        user_data_dir=user_data,
    )
    assert cmd[0] == str(browser)
    assert f"--app={url}" in cmd
    assert "--window-size=1300,880" in cmd
    assert "--app-id=rag-agent" in cmd
    assert f"--user-data-dir={user_data}" in cmd
    assert "--hide-crash-restore-bubble" in cmd
    assert "--disable-session-crashed-bubble" in cmd


def test_launch_desktop_window_success(tmp_path: Path):
    """Spawns desktop window process in standalone mode."""
    fake_edge = tmp_path / "msedge.exe"
    fake_edge.write_text("")

    mock_proc = MagicMock()
    mock_proc.pid = 4321
    mock_proc.poll.return_value = None

    with patch("scripts.launcher.desktop_window.find_desktop_browser", return_value=fake_edge), patch(
        "subprocess.Popen", return_value=mock_proc
    ) as mock_popen:
        proc = launch_desktop_window("http://127.0.0.1:8080", tmp_path)
        assert proc == mock_proc
        mock_popen.assert_called_once()
        called_cmd = mock_popen.call_args[0][0]
        assert "--app=http://127.0.0.1:8080" in called_cmd


def test_launch_desktop_window_fallback_to_webbrowser(tmp_path: Path):
    """Falls back to webbrowser.open when no standalone browser is available."""
    with patch("scripts.launcher.desktop_window.find_desktop_browser", return_value=None), patch(
        "webbrowser.open"
    ) as mock_wb_open:
        proc = launch_desktop_window("http://127.0.0.1:8080", tmp_path)
        assert proc is None
        mock_wb_open.assert_called_once_with("http://127.0.0.1:8080")


# ============================================================================
# 3. One-Time Setup & Instant Subsequent Launch Tests
# ============================================================================


def test_installation_marker_lifecycle(tmp_path: Path):
    """Verifies creation, detection, and removal of .installed.json."""
    assert is_installed(tmp_path) is False

    # Simulate presence of venv python
    scripts_dir = tmp_path / ".venv" / "Scripts"
    scripts_dir.mkdir(parents=True)
    venv_py = scripts_dir / "python.exe"
    venv_py.write_text("")

    marker_path = mark_as_installed(
        tmp_path,
        details={
            "installed": True,
            "php_path": "C:\\php\\php.exe",
            "ollama_path": "C:\\ollama\\ollama.exe",
        },
    )
    assert marker_path.exists()
    assert is_installed(tmp_path) is True

    # Validate contents
    data = json.loads(marker_path.read_text(encoding="utf-8"))
    assert data["installed"] is True
    assert data["php_path"] == "C:\\php\\php.exe"

    clear_installation_marker(tmp_path)
    assert not marker_path.exists()
    assert is_installed(tmp_path) is False


def test_is_installed_false_when_venv_missing(tmp_path: Path):
    """Returns False if marker exists but .venv is gone."""
    marker_path = mark_as_installed(tmp_path, {"installed": True})
    assert marker_path.exists()
    # No .venv created
    assert is_installed(tmp_path) is False


def test_is_installed_false_when_workspace_moved(tmp_path: Path):
    """Returns False if workspace was relocated to a different directory."""
    scripts_dir = tmp_path / ".venv" / "Scripts"
    scripts_dir.mkdir(parents=True)
    venv_py = scripts_dir / "python.exe"
    venv_py.write_text("")

    old_root = tmp_path / "old_location"
    marker = mark_as_installed(tmp_path, {"workspace_root": str(old_root)})
    assert marker.exists()

    # Current path does not match recorded old_root
    assert is_installed(tmp_path) is False


def test_launcher_main_fast_launch_flow(tmp_path: Path):
    """When installed, launcher.main skips ensure_environment and proceeds immediately."""
    from scripts.launcher.launcher import main
    from scripts.launcher.model_checker import ModelCheckResult
    from scripts.launcher.preflight import PreflightReport, PreflightResult

    # Set up simulated installed workspace
    scripts_dir = tmp_path / ".venv" / "Scripts"
    scripts_dir.mkdir(parents=True)
    venv_py = scripts_dir / "python.exe"
    venv_py.write_text("")
    mark_as_installed(tmp_path, {"installed": True, "venv_python": str(venv_py)})

    mock_report = PreflightReport(
        results=[
            PreflightResult("Python", True, "3.12.0", Path("python.exe")),
            PreflightResult("PHP", True, "8.3.0", Path("php.exe")),
            PreflightResult("Ollama", True, "0.4.0", Path("ollama.exe")),
        ]
    )
    mock_model = ModelCheckResult(
        online=True,
        active_coder_model="stem-coder-expert:latest",
        has_embedding_model=True,
        started_by_us=False,
    )

    with patch("scripts.launcher.launcher.run_all_preflight_checks", return_value=mock_report), patch(
        "scripts.launcher.launcher.ensure_environment"
    ) as mock_ensure_env, patch(
        "scripts.launcher.launcher.ensure_desktop_and_start_menu_shortcuts"
    ) as mock_shortcuts, patch(
        "scripts.launcher.launcher.ensure_ollama_and_models", return_value=mock_model
    ), patch(
        "scripts.launcher.launcher.MultiServiceSupervisor"
    ) as mock_sup_cls, patch(
        "urllib.request.urlopen"
    ) as mock_url, patch(
        "scripts.launcher.launcher.launch_desktop_window"
    ) as mock_win, patch(
        "time.sleep", side_effect=KeyboardInterrupt
    ):
        mock_sup = MagicMock()
        mock_sup.is_port_listening.return_value = True
        mock_sup.processes = {}
        mock_sup.spawned_pids = set()
        mock_sup_cls.return_value = mock_sup

        resp = MagicMock(status=200)
        resp.__enter__.return_value = resp
        mock_url.return_value = resp

        rc = main(["--workspace", str(tmp_path)])
        assert rc == 0

        # Fast launch: ensure_environment is skipped!
        mock_ensure_env.assert_not_called()
        mock_shortcuts.assert_called_once_with(tmp_path, force=False)
        mock_sup.shutdown.assert_called_once()


def test_launcher_main_desktop_window_close_initiates_shutdown(tmp_path: Path):
    """When desktop window process terminates, supervisor terminates child services and exits."""
    from scripts.launcher.launcher import main
    from scripts.launcher.model_checker import ModelCheckResult
    from scripts.launcher.preflight import PreflightReport, PreflightResult

    scripts_dir = tmp_path / ".venv" / "Scripts"
    scripts_dir.mkdir(parents=True)
    venv_py = scripts_dir / "python.exe"
    venv_py.write_text("")
    mark_as_installed(tmp_path, {"installed": True, "venv_python": str(venv_py)})

    mock_report = PreflightReport(
        results=[
            PreflightResult("Python", True, "3.12.0", Path("python.exe")),
            PreflightResult("PHP", True, "8.3.0", Path("php.exe")),
            PreflightResult("Ollama", True, "0.4.0", Path("ollama.exe")),
        ]
    )

    mock_model = ModelCheckResult(
        online=True,
        active_coder_model="stem-coder-expert:latest",
        has_embedding_model=True,
        started_by_us=False,
    )

    mock_app_proc = MagicMock()
    mock_app_proc.pid = 9876
    # First poll alive, second poll user closed window
    mock_app_proc.poll.side_effect = [None, 0]

    with patch("scripts.launcher.launcher.run_all_preflight_checks", return_value=mock_report), patch(
        "scripts.launcher.launcher.ensure_desktop_and_start_menu_shortcuts"
    ), patch(
        "scripts.launcher.launcher.ensure_ollama_and_models", return_value=mock_model
    ), patch(
        "scripts.launcher.launcher.MultiServiceSupervisor"
    ) as mock_sup_cls, patch(
        "urllib.request.urlopen"
    ) as mock_url, patch(
        "scripts.launcher.launcher.launch_desktop_window", return_value=mock_app_proc
    ), patch(
        "time.sleep"
    ):
        mock_sup = MagicMock()
        mock_sup.is_port_listening.return_value = True
        mock_sup.processes = {}
        mock_sup.spawned_pids = set()
        mock_sup_cls.return_value = mock_sup

        resp = MagicMock(status=200)
        resp.__enter__.return_value = resp
        mock_url.return_value = resp

        rc = main(["--workspace", str(tmp_path)])
        assert rc == 0
        # Desktop window was registered with supervisor
        assert mock_sup.processes["desktop_window"] == mock_app_proc
        assert 9876 in mock_sup.spawned_pids
        mock_sup.assign_process_to_job.assert_called_with(mock_app_proc)
        # Supervisor shutdown was triggered by window close
        mock_sup.shutdown.assert_called_once()


def test_launcher_main_backend_crash_initiates_shutdown(tmp_path: Path):
    """When a critical backend service terminates with error, supervisor detects it and shuts down."""
    from scripts.launcher.launcher import main
    from scripts.launcher.model_checker import ModelCheckResult
    from scripts.launcher.preflight import PreflightReport, PreflightResult

    scripts_dir = tmp_path / ".venv" / "Scripts"
    scripts_dir.mkdir(parents=True)
    venv_py = scripts_dir / "python.exe"
    venv_py.write_text("")
    mark_as_installed(tmp_path, {"installed": True, "venv_python": str(venv_py)})

    mock_report = PreflightReport(
        results=[
            PreflightResult("Python", True, "3.12.0", Path("python.exe")),
            PreflightResult("PHP", True, "8.3.0", Path("php.exe")),
            PreflightResult("Ollama", True, "0.4.0", Path("ollama.exe")),
        ]
    )

    mock_model = ModelCheckResult(
        online=True,
        active_coder_model="stem-coder-expert:latest",
        has_embedding_model=True,
        started_by_us=False,
    )

    mock_app_proc = MagicMock()
    mock_app_proc.pid = 9876
    mock_app_proc.poll.return_value = None  # Desktop window is still open

    # Simulate web gateway crashing
    mock_web_proc = MagicMock()
    mock_web_proc.poll.return_value = 1  # Exited with error code 1

    with patch("scripts.launcher.launcher.run_all_preflight_checks", return_value=mock_report), patch(
        "scripts.launcher.launcher.ensure_desktop_and_start_menu_shortcuts"
    ), patch(
        "scripts.launcher.launcher.ensure_ollama_and_models", return_value=mock_model
    ), patch(
        "scripts.launcher.launcher.MultiServiceSupervisor"
    ) as mock_sup_cls, patch(
        "urllib.request.urlopen"
    ) as mock_url, patch(
        "scripts.launcher.launcher.launch_desktop_window", return_value=mock_app_proc
    ), patch(
        "time.sleep"
    ):
        mock_sup = MagicMock()
        mock_sup.is_port_listening.return_value = True
        mock_sup.processes = {"web_gateway": mock_web_proc}
        mock_sup.spawned_pids = set()
        mock_sup_cls.return_value = mock_sup

        resp = MagicMock(status=200)
        resp.__enter__.return_value = resp
        mock_url.return_value = resp

        rc = main(["--workspace", str(tmp_path)])
        assert rc == 1
        # Shutdown was triggered due to web gateway crash
        mock_sup.shutdown.assert_called_once()
