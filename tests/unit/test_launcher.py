"""
tests/unit/test_launcher.py

Comprehensive unit tests for the Windows Launcher modules:
- preflight: Python 3.11+, PHP 8.3+, Ollama detection, version parsing, diagnostics
- installer: .venv detection, virtualenv creation, bytecode import verification
- model_checker: Ollama daemon probing, model tag verification, Modelfile creation
- supervisor: Win32 Job Object isolation, port probing, external service safety, graceful cleanup
- launcher: Authoritative workspace root resolution (frozen vs dev), CLI argument parsing
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from scripts.launcher.installer import (
    check_bytecode_imports,
    ensure_environment,
    find_venv_python,
)
from scripts.launcher.launcher import get_workspace_root, parse_args
from scripts.launcher.model_checker import (
    ModelCheckResult,
    ensure_ollama_and_models,
    probe_ollama_daemon,
)
from scripts.launcher.preflight import (
    PreflightReport,
    PreflightResult,
    detect_ollama,
    detect_php,
    detect_python,
    run_all_preflight_checks,
)
from scripts.launcher.supervisor import MultiServiceSupervisor


# ============================================================================
# Pre-Flight Tests
# ============================================================================


def test_detect_python_current_runtime_ok():
    """Detects current runtime when sys.version_info >= (3, 11)."""
    with patch("sys.version_info", (3, 12, 1, "final", 0)), patch(
        "sys.executable", "C:\\Python312\\python.exe"
    ):
        res = detect_python(min_version=(3, 11))
        assert res.available is True
        assert res.name == "Python"
        assert res.version == "3.12.1"
        assert res.path == Path("C:\\Python312\\python.exe")
        assert res.error_message is None


def test_detect_python_current_runtime_too_low_falls_back_to_path():
    """Falls back to PATH and finds a modern python when current runtime is < 3.11."""
    with patch("sys.version_info", (3, 10, 2, "final", 0)), patch(
        "shutil.which", return_value="C:\\tools\\python.exe"
    ), patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="3.11.8\n")
        res = detect_python(min_version=(3, 11))
        assert res.available is True
        assert res.version == "3.11.8"
        assert res.path == Path("C:\\tools\\python.exe")


def test_detect_python_missing_entirely():
    """Returns available=False with clear remediation when no Python >= 3.11 exists."""
    with patch("sys.version_info", (3, 9, 0, "final", 0)), patch(
        "shutil.which", return_value=None
    ), patch.dict(os.environ, {"LOCALAPPDATA": "", "ProgramFiles": "", "ProgramFiles(x86)": ""}):
        res = detect_python(min_version=(3, 11))
        assert res.available is False
        assert "Python 3.11+" in res.error_message
        assert "winget install Python.Python.3.11" in res.remediation


def test_detect_python_found_in_localappdata():
    """Detects Python in %LOCALAPPDATA%\\Programs\\Python when PATH does not have python."""
    fake_py = Path("C:\\Users\\test\\AppData\\Local\\Programs\\Python\\Python312\\python.exe")
    with patch("sys.version_info", (3, 9, 0, "final", 0)), patch(
        "shutil.which", return_value=None
    ), patch.dict(
        os.environ, {"LOCALAPPDATA": "C:\\Users\\test\\AppData\\Local", "ProgramFiles": ""}
    ), patch("pathlib.Path.exists", return_value=True), patch(
        "pathlib.Path.glob", return_value=[fake_py.parent]
    ), patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="3.12.2\n")
        res = detect_python(min_version=(3, 11))
        assert res.available is True
        assert res.version == "3.12.2"
        assert res.path == fake_py



def test_detect_python_when_frozen_discovers_host_python():
    """When sys.frozen is True, skips sys.executable (the launcher .exe) and discovers host python."""
    fake_launcher_exe = Path("D:\\RAG-Agent\\dist\\RAG-Agent-Launcher.exe")
    fake_host_python = "C:\\Python312\\python.exe"
    with patch("sys.frozen", True, create=True), patch(
        "sys.executable", str(fake_launcher_exe)
    ), patch("shutil.which", return_value=fake_host_python), patch(
        "subprocess.run"
    ) as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="3.12.1\n")
        res = detect_python(min_version=(3, 11))
        assert res.available is True
        assert res.version == "3.12.1"
        assert res.path != fake_launcher_exe
        assert res.path == Path(fake_host_python)



def test_detect_php_found_on_path():
    """Detects PHP 8.3+ via standard PATH."""
    with patch("shutil.which", return_value="C:\\php\\php.exe"), patch(
        "pathlib.Path.exists", return_value=True
    ), patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="8.3.16\n")
        res = detect_php(min_version=(8, 3))
        assert res.available is True
        assert res.name == "PHP"
        assert res.version == "8.3.16"
        assert res.path == Path("C:\\php\\php.exe")


def test_detect_php_found_in_winget_packages():
    """Detects PHP in WinGet package directory when PATH does not have php."""
    fake_winget_php = (
        Path("C:\\Users\\test\\AppData\\Local\\Microsoft\\WinGet\\Packages\\PHP.PHP.8.3_xyz\\php.exe")
    )
    with patch("shutil.which", return_value=None), patch.dict(
        os.environ, {"LOCALAPPDATA": "C:\\Users\\test\\AppData\\Local"}
    ), patch("pathlib.Path.glob") as mock_glob, patch(
        "pathlib.Path.exists", return_value=True
    ), patch("subprocess.run") as mock_run:
        mock_glob.return_value = [fake_winget_php.parent]
        mock_run.return_value = MagicMock(returncode=0, stdout="8.3.32\n")

        res = detect_php(min_version=(8, 3))
        assert res.available is True
        assert "8.3" in res.version


def test_detect_php_version_below_minimum():
    """Reports failure if PHP version is < 8.3."""
    with patch("shutil.which", return_value="C:\\php\\php.exe"), patch(
        "pathlib.Path.exists", return_value=True
    ), patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="8.1.2\n")
        res = detect_php(min_version=(8, 3))
        assert res.available is False
        assert "PHP 8.3+" in res.error_message
        assert "winget install PHP.PHP.8.3" in res.remediation


def test_detect_ollama_found():
    """Detects Ollama on PATH or AppData and extracts version."""
    with patch("shutil.which", return_value="C:\\Users\\test\\AppData\\Local\\Programs\\Ollama\\ollama.exe"), patch(
        "pathlib.Path.exists", return_value=True
    ), patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ollama version is 0.40.4\n")
        res = detect_ollama()
        assert res.available is True
        assert res.name == "Ollama"
        assert res.version == "0.40.4"


def test_detect_ollama_missing():
    """Reports failure and remediation if Ollama is not installed."""
    with patch("shutil.which", return_value=None), patch(
        "pathlib.Path.exists", return_value=False
    ):
        res = detect_ollama()
        assert res.available is False
        assert "Ollama" in res.name
        assert "winget install Ollama.Ollama" in res.remediation


def test_run_all_preflight_checks_aggregate():
    """Aggregates all pre-flight results into PreflightReport."""
    py_res = PreflightResult("Python", True, "3.12.0", Path("python.exe"))
    php_res = PreflightResult("PHP", True, "8.3.0", Path("php.exe"))
    ol_res = PreflightResult("Ollama", True, "0.4.0", Path("ollama.exe"))
    with patch("scripts.launcher.preflight.detect_python", return_value=py_res), patch(
        "scripts.launcher.preflight.detect_php", return_value=php_res
    ), patch("scripts.launcher.preflight.detect_ollama", return_value=ol_res):
        report = run_all_preflight_checks()
        assert report.all_passed is True
        formatted = report.format_report()
        assert "[OK]   Python" in formatted
        assert "[OK]   PHP" in formatted
        assert "[OK]   Ollama" in formatted


# ============================================================================
# Installer & Bootstrapping Tests
# ============================================================================


def test_find_venv_python(tmp_path: Path):
    """Finds python executable inside .venv on Windows and POSIX."""
    scripts_dir = tmp_path / ".venv" / "Scripts"
    scripts_dir.mkdir(parents=True)
    venv_py = scripts_dir / "python.exe"
    venv_py.write_text("")

    found = find_venv_python(tmp_path)
    assert found == venv_py


def test_check_bytecode_imports_success(tmp_path: Path):
    """Returns True when python -c import returns 0."""
    py = tmp_path / "python.exe"
    py.write_text("")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert check_bytecode_imports(py) is True


def test_check_bytecode_imports_failure(tmp_path: Path):
    """Returns False when python -c import fails."""
    py = tmp_path / "python.exe"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        assert check_bytecode_imports(py) is False


def test_ensure_environment_fast_path(tmp_path: Path):
    """Uses existing .venv without running pip when imports succeed."""
    scripts_dir = tmp_path / ".venv" / "Scripts"
    scripts_dir.mkdir(parents=True)
    venv_py = scripts_dir / "python.exe"
    venv_py.write_text("")

    with patch("scripts.launcher.installer.check_bytecode_imports", return_value=True), patch(
        "subprocess.run"
    ) as mock_run:
        res = ensure_environment(tmp_path)
        assert res == venv_py
        mock_run.assert_not_called()


def test_ensure_environment_bootstraps_venv_and_pip(tmp_path: Path):
    """Creates .venv and installs requirements if .venv is absent."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("pytest\n")

    host_py = Path("C:\\Python312\\python.exe")

    def fake_run(cmd, *args, **kwargs):
        # Simulate venv creation creating the binary
        if "venv" in cmd:
            scripts_dir = tmp_path / ".venv" / "Scripts"
            scripts_dir.mkdir(parents=True, exist_ok=True)
            (scripts_dir / "python.exe").write_text("")
        return MagicMock(returncode=0)

    with patch("subprocess.run", side_effect=fake_run) as mock_run, patch(
        "scripts.launcher.installer.check_bytecode_imports", return_value=False
    ):
        res = ensure_environment(tmp_path, host_python=host_py)
        assert res.name == "python.exe"
        assert mock_run.call_count >= 2  # venv creation + pip install


def test_ensure_environment_re_resolves_when_host_python_is_launcher_binary(tmp_path: Path):
    """When host_python points to RAG-Agent-Launcher.exe, automatically re-resolves to real python."""
    launcher_exe = Path("D:\\RAG-Agent\\dist\\RAG-Agent-Launcher.exe")
    fake_host_py = Path("C:\\Python312\\python.exe")
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("pytest\n")

    executed_cmds = []

    def fake_run(cmd, *args, **kwargs):
        executed_cmds.append(cmd)
        if "venv" in cmd:
            scripts_dir = tmp_path / ".venv" / "Scripts"
            scripts_dir.mkdir(parents=True, exist_ok=True)
            (scripts_dir / "python.exe").write_text("")
        return MagicMock(returncode=0)

    with patch("subprocess.run", side_effect=fake_run), patch(
        "scripts.launcher.installer.check_bytecode_imports", return_value=False
    ), patch(
        "scripts.launcher.installer.detect_python",
        return_value=PreflightResult(
            name="Python",
            available=True,
            version="3.12.1",
            path=fake_host_py,
        ),
    ):
        res = ensure_environment(tmp_path, host_python=launcher_exe)
        assert res.name == "python.exe"
        # Confirm that -m venv was called with fake_host_py, NOT launcher_exe
        venv_cmds = [c for c in executed_cmds if "-m" in c and "venv" in c]
        assert len(venv_cmds) == 1
        assert venv_cmds[0][0] == str(fake_host_py)
        assert "RAG-Agent-Launcher" not in venv_cmds[0][0]



# ============================================================================
# Model Checker Tests
# ============================================================================


def test_probe_ollama_daemon_online():
    """Returns True when /api/tags responds with HTTP 200."""
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp

        assert probe_ollama_daemon() is True


def test_probe_ollama_daemon_offline():
    """Returns False when /api/tags raises an exception."""
    with patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
        assert probe_ollama_daemon() is False


def test_ensure_ollama_and_models_already_online_with_expert(tmp_path: Path):
    """Detects stem-coder-expert:latest and nomic-embed-text:latest when already online."""
    fake_tags_json = (
        b'{"models": [{"name": "stem-coder-expert:latest"}, {"name": "nomic-embed-text:latest"}]}'
    )

    with patch("scripts.launcher.model_checker.probe_ollama_daemon", return_value=True), patch(
        "urllib.request.urlopen"
    ) as mock_url:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = fake_tags_json
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp

        res = ensure_ollama_and_models(tmp_path, ollama_path=Path("ollama.exe"))
        assert res.online is True
        assert res.active_coder_model == "stem-coder-expert:latest"
        assert res.has_embedding_model is True
        assert res.started_by_us is False


def test_ensure_ollama_and_models_creates_model_if_missing(tmp_path: Path):
    """Executes 'ollama create' when stem-coder-expert is absent and GGUF + Modelfile exist."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    gguf_path = models_dir / "stem-coder-expert-q4_k_m.gguf"
    gguf_path.write_text("fake_gguf")
    modelfile = models_dir / "Modelfile"
    modelfile.write_text("FROM ./stem-coder-expert-q4_k_m.gguf\n")

    fake_tags_before = b'{"models": [{"name": "nomic-embed-text:latest"}]}'
    fake_tags_after = (
        b'{"models": [{"name": "stem-coder-expert:latest"}, {"name": "nomic-embed-text:latest"}]}'
    )

    with patch("scripts.launcher.model_checker.probe_ollama_daemon", return_value=True), patch(
        "urllib.request.urlopen"
    ) as mock_url, patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        resp1 = MagicMock(status=200, read=MagicMock(return_value=fake_tags_before))
        resp1.__enter__.return_value = resp1
        resp2 = MagicMock(status=200, read=MagicMock(return_value=fake_tags_after))
        resp2.__enter__.return_value = resp2
        mock_url.side_effect = [resp1, resp2]

        res = ensure_ollama_and_models(tmp_path, ollama_path=Path("ollama.exe"))
        assert res.active_coder_model == "stem-coder-expert:latest"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "create" in cmd
        assert "stem-coder-expert:latest" in cmd


def test_ensure_ollama_and_models_falls_back_to_qwen(tmp_path: Path):
    """Falls back to qwen2.5-coder:1.5b when stem-coder GGUF is not present."""
    fake_tags = (
        b'{"models": [{"name": "qwen2.5-coder:1.5b"}, {"name": "nomic-embed-text:latest"}]}'
    )
    with patch("scripts.launcher.model_checker.probe_ollama_daemon", return_value=True), patch(
        "urllib.request.urlopen"
    ) as mock_url:
        resp = MagicMock(status=200, read=MagicMock(return_value=fake_tags))
        resp.__enter__.return_value = resp
        mock_url.return_value = resp

        res = ensure_ollama_and_models(tmp_path, ollama_path=Path("ollama.exe"))
        assert res.active_coder_model == "qwen2.5-coder:1.5b"


# ============================================================================
# Supervisor Tests
# ============================================================================


def test_supervisor_initialization(tmp_path: Path):
    """Initializes supervisor, creates log directory, and provisions Job Object."""
    sup = MultiServiceSupervisor(tmp_path)
    assert (tmp_path / "evals" / "logs").exists()
    assert sup.processes == {}
    assert sup.spawned_pids == set()


def test_supervisor_is_port_listening():
    """Checks whether a port is listening via socket probe."""
    sup = MultiServiceSupervisor(Path("."))
    with patch("socket.create_connection") as mock_conn:
        mock_sock = MagicMock()
        mock_conn.return_value.__enter__.return_value = mock_sock
        assert sup.is_port_listening(8080) is True

    with patch("socket.create_connection", side_effect=OSError("Connection refused")):
        assert sup.is_port_listening(8080) is False


def test_supervisor_spawn_service_tracks_pid_and_job(tmp_path: Path):
    """Spawns service, assigns to Win32 Job Object, and records PID."""
    sup = MultiServiceSupervisor(tmp_path)
    mock_proc = MagicMock()
    mock_proc.pid = 9999
    mock_proc._handle = 12345

    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen, patch(
        "scripts.launcher.supervisor.assign_process_to_job"
    ) as mock_assign:
        proc = sup.spawn_service("test_svc", ["cmd.exe", "/c", "dir"], cwd=tmp_path)
        assert proc == mock_proc
        assert sup.processes["test_svc"] == mock_proc
        assert 9999 in sup.spawned_pids
        mock_assign.assert_called_once()


def test_supervisor_assign_process_to_job_method(tmp_path: Path):
    """Assigns an arbitrary Popen process handle to supervisor Job Object."""
    sup = MultiServiceSupervisor(tmp_path)
    mock_proc = MagicMock()
    mock_proc._handle = 54321

    with patch("scripts.launcher.supervisor.assign_process_to_job") as mock_assign:
        mock_assign.return_value = True
        with patch("sys.platform", "win32"):
            sup.h_job = 9999
            res = sup.assign_process_to_job(mock_proc)
            assert res is True
            mock_assign.assert_called_once_with(9999, 54321)


def test_supervisor_register_external_service_prevents_kill(tmp_path: Path):
    """Ensures externally pre-existing services are never terminated on shutdown."""
    sup = MultiServiceSupervisor(tmp_path)
    sup.register_external_service("ollama", 11434)
    assert sup.is_external("ollama") is True

    # Shutdown should do nothing to external services
    with patch("subprocess.Popen.terminate") as mock_term:
        sup.shutdown()
        mock_term.assert_not_called()


def test_supervisor_shutdown_terminates_spawned_processes(tmp_path: Path):
    """Terminates spawned processes gracefully and falls back to kill if alive."""
    sup = MultiServiceSupervisor(tmp_path)
    mock_proc = MagicMock()
    mock_proc.pid = 8888
    mock_proc.poll.side_effect = [None, 0]  # First poll alive, then dead after terminate
    sup.processes["dummy"] = mock_proc
    sup.spawned_pids.add(8888)

    sup.shutdown()
    mock_proc.terminate.assert_called_once()
    mock_proc.wait.assert_called_once()


# ============================================================================
# Launcher & CLI Entrypoint Tests
# ============================================================================


def test_get_workspace_root_override(tmp_path: Path):
    """Explicit --workspace override path is respected."""
    assert get_workspace_root(override_path=str(tmp_path)) == tmp_path.resolve()


def test_get_workspace_root_invalid_override():
    """Raises FileNotFoundError if explicit override path does not exist."""
    with pytest.raises(FileNotFoundError):
        get_workspace_root(override_path="nonexistent_folder_xyz_99")


def test_get_workspace_root_dev_mode():
    """Resolves repository root from launcher module directory in dev mode."""
    with patch("sys.frozen", False, create=True):
        root = get_workspace_root()
        assert (root / "PROJECT.md").exists() or (root / "requirements.txt").exists()


def test_get_workspace_root_frozen_mode(tmp_path: Path):
    """Resolves parent directory when frozen .exe is inside dist/."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    fake_exe = dist_dir / "RAG-Agent-Launcher.exe"
    fake_exe.write_text("")
    (tmp_path / "requirements.txt").write_text("")

    with patch("sys.frozen", True, create=True), patch(
        "sys.executable", str(fake_exe)
    ):
        root = get_workspace_root()
        assert root == tmp_path.resolve()


def test_parse_args_defaults():
    """Parses default CLI flags."""
    args = parse_args([])
    assert args.check_only is False
    assert args.no_browser is False
    assert args.workspace is None
    assert args.port_web == 8080
    assert args.port_php == 8000


def test_parse_args_check_only_and_custom_ports():
    """Parses custom flags correctly."""
    args = parse_args(["--check-only", "--no-browser", "--port-web", "9090", "--port-php", "9000"])
    assert args.check_only is True
    assert args.no_browser is True
    assert args.port_web == 9090
    assert args.port_php == 9000
