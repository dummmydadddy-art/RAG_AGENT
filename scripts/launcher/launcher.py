"""
scripts/launcher/launcher.py

Main CLI Entrypoint for RAG-Agent Windows Launcher:
- Authoritative workspace root resolution supporting frozen (.exe) and dev (.py) modes
- CLI flags: --check-only, --workspace, --no-browser, --port-web, --port-php, --help
- Multi-service supervision (Ollama, PHP Vector API, FastAPI Web Gateway)
- Health probe polling on /api/health and default browser auto-launch
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import List, Optional

# Ensure repository root is on sys.path for direct CLI execution and frozen mode
_CURRENT_FILE = Path(__file__).resolve()
_REPO_ROOT = _CURRENT_FILE.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.launcher.desktop_window import launch_desktop_window
from scripts.launcher.installer import (
    check_bytecode_imports,
    clear_installation_marker,
    ensure_environment,
    find_venv_python,
    is_installed,
    mark_as_installed,
)
from scripts.launcher.model_checker import ensure_ollama_and_models, probe_ollama_daemon
from scripts.launcher.preflight import run_all_preflight_checks
from scripts.launcher.shortcut import ensure_desktop_and_start_menu_shortcuts
from scripts.launcher.supervisor import MultiServiceSupervisor



def get_workspace_root(override_path: Optional[str] = None) -> Path:
    """
    Authoritative workspace root resolution across frozen (.exe) and development modes.
    """
    if override_path:
        p = Path(override_path).resolve()
        if p.exists():
            return p
        raise FileNotFoundError(f"Specified workspace path does not exist: {override_path}")

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        # Scenario 1: executable is inside dist/
        if exe_dir.name.lower() == "dist" and (exe_dir.parent / "requirements.txt").exists():
            return exe_dir.parent
        # Scenario 2: executable was copied to workspace root
        if (exe_dir / "requirements.txt").exists() or (exe_dir / "backend").exists():
            return exe_dir
        # Scenario 3: current working directory contains workspace markers
        cwd = Path.cwd().resolve()
        if (cwd / "requirements.txt").exists() or (cwd / "backend").exists():
            return cwd
        return exe_dir
    else:
        # Development mode (python scripts/launcher/launcher.py)
        script_dir = Path(__file__).resolve().parent
        root = script_dir.parent.parent
        if (root / "requirements.txt").exists() or (root / "PROJECT.md").exists():
            return root
        cwd = Path.cwd().resolve()
        if (cwd / "requirements.txt").exists():
            return cwd
        return root


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parses command-line arguments for the launcher."""
    parser = argparse.ArgumentParser(
        prog="RAG-Agent-Launcher",
        description="One-Click Windows Launcher & Multi-Service Supervisor for RAG-Agent",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Run pre-flight checks and environment validation without launching background services",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default=None,
        help="Explicitly override the workspace root directory path",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Suppress automatic browser opening after services become healthy",
    )
    parser.add_argument(
        "--port-web",
        type=int,
        default=8080,
        help="Local port for FastAPI ChatGPT Web Gateway (default: 8080)",
    )
    parser.add_argument(
        "--port-php",
        type=int,
        default=8000,
        help="Local port for PHP Vector API (default: 8000)",
    )
    parser.add_argument(
        "--port-ollama",
        type=int,
        default=11434,
        help="Local port for Ollama Daemon (default: 11434)",
    )
    parser.add_argument(
        "--force-install",
        action="store_true",
        help="Force full environment re-creation and dependency installation even if already installed",
    )
    parser.add_argument(
        "--no-shortcut",
        action="store_true",
        help="Suppress automatic Desktop and Start Menu shortcut creation",
    )
    parser.add_argument(
        "--window-mode",
        choices=["app", "browser"],
        default="app",
        help="Application window mode: 'app' for standalone frameless desktop window, 'browser' for standard web browser (default: app)",
    )
    parser.add_argument(
        "--window-size",
        type=str,
        default="1300,880",
        help="Window dimensions WIDTH,HEIGHT for desktop app mode (default: 1300,880)",
    )
    return parser.parse_args(argv if argv is not None else sys.argv[1:])



def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI execution flow."""
    args = parse_args(argv)

    print("=" * 64)
    print("      RAG-Agent Windows One-Click Launcher & Supervisor")
    print("=" * 64)

    # 1. Resolve workspace root
    try:
        workspace_root = get_workspace_root(args.workspace)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    print(f"[*] Workspace Root: {workspace_root}")

    # Handle explicit reinstallation request
    if args.force_install:
        print("[*] Force-install requested: clearing installation marker...")
        clear_installation_marker(workspace_root)

    already_installed = is_installed(workspace_root)

    # 2. Run Pre-flight Checks
    print("[*] Running Pre-Flight Checks...")
    preflight = run_all_preflight_checks()
    preflight.print_report()

    if not preflight.all_passed:
        print("[!] Pre-flight validation failed. Please address the missing prerequisites.")
        return 1

    # Check-only mode handling
    if args.check_only:
        print("\n[*] Check-only mode requested. Inspecting virtualenv and Ollama tags...")
        venv_py = find_venv_python(workspace_root)
        if venv_py and check_bytecode_imports(venv_py):
            print(f"[OK] Virtual environment verified: {venv_py}")
        else:
            print("[INFO] Virtual environment needs bootstrapping on first full run.")

        if probe_ollama_daemon(port=args.port_ollama):
            print(f"[OK] Ollama daemon is responsive on port {args.port_ollama}.")
        else:
            print(f"[INFO] Ollama daemon is offline; will be auto-started on full run.")

        print("\n[OK] All check-only diagnostics completed successfully.")
        return 0

    # 3. Virtual Environment Bootstrapping / Fast Launch
    if already_installed:
        print("\n[*] Fast Launch: Verified existing installation.")
        print("    Skipping dependency installation checks for instant launch.")
        venv_python = find_venv_python(workspace_root)
        if not venv_python or not venv_python.exists():
            print("[!] Virtual environment binary missing; bootstrapping new environment...")
            venv_python = ensure_environment(workspace_root, preflight.python_path)
    else:
        print("\n[*] Initial Setup: Bootstrapping Python virtual environment and dependencies...")
        try:
            venv_python = ensure_environment(
                workspace_root, preflight.python_path, force_install=args.force_install
            )
        except Exception as e:
            print(f"[ERROR] Environment bootstrapping failed: {e}", file=sys.stderr)
            return 1

        # Persist installation marker for instant future starts
        mark_as_installed(
            workspace_root,
            {
                "php_path": str(preflight.php_path) if preflight.php_path else "",
                "ollama_path": str(preflight.ollama_path) if preflight.ollama_path else "",
                "venv_python": str(venv_python),
            },
        )

    # 4. Desktop Integration & Shortcut Verification
    if not args.no_shortcut:
        print("\n[*] Verifying desktop integration and shortcuts...")
        try:
            ensure_desktop_and_start_menu_shortcuts(
                workspace_root, force=args.force_install
            )
        except Exception as e:
            print(f"[!] Warning: Shortcut verification encountered an issue: {e}", file=sys.stderr)

    # 5. Ollama & Model Readiness
    print("\n[*] Ensuring Ollama daemon and model availability...")
    try:
        model_info = ensure_ollama_and_models(
            workspace_root, preflight.ollama_path, port=args.port_ollama
        )
    except Exception as e:
        print(f"[ERROR] Model verification failed: {e}", file=sys.stderr)
        return 1

    if not model_info.online:
        print(f"[ERROR] Ollama daemon could not be reached: {model_info.error_message}", file=sys.stderr)
        return 1

    print(f"[+] Active Polyglot Coding Model: {model_info.active_coder_model}")
    print(f"[+] Embedding Model Available: {model_info.has_embedding_model}")

    # 6. Multi-Service Supervision
    print("\n[*] Starting Multi-Service Supervisor...")
    supervisor = MultiServiceSupervisor(workspace_root)

    # Register spawned Ollama if started by model_checker
    if model_info.started_by_us and model_info.process:
        supervisor.processes["ollama"] = model_info.process
        supervisor.spawned_pids.add(model_info.process.pid)
        supervisor.assign_process_to_job(model_info.process)
    else:
        supervisor.register_external_service("ollama", args.port_ollama)

    # PHP Vector API Service (port 8000)
    if supervisor.is_port_listening(args.port_php):
        print(f"[+] Port {args.port_php} is already active. Registering external PHP Vector API.")
        supervisor.register_external_service("php_backend", args.port_php)
    else:
        print(f"[*] Spawning PHP Vector API on port {args.port_php}...")
        backend_dir = workspace_root / "backend"
        php_cmd = [str(preflight.php_path), "-S", f"0.0.0.0:{args.port_php}"]
        supervisor.spawn_service("php_backend", php_cmd, cwd=backend_dir)

    # FastAPI Web Gateway (port 8080)
    if supervisor.is_port_listening(args.port_web):
        print(f"[+] Port {args.port_web} is already active. Registering external Web Gateway.")
        supervisor.register_external_service("web_gateway", args.port_web)
    else:
        print(f"[*] Spawning FastAPI Web Gateway on port {args.port_web}...")
        py_path_sep = ";" if sys.platform == "win32" else ":"
        python_path_env = py_path_sep.join([
            str(workspace_root),
            str(workspace_root / "rag-adapter"),
            str(workspace_root / "rag-mcp"),
            str(workspace_root / "physmath-mcp"),
        ])
        env = {"PYTHONPATH": python_path_env}
        uvicorn_cmd = [
            str(venv_python),
            "-m",
            "uvicorn",
            "src.web.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port_web),
        ]
        supervisor.spawn_service("web_gateway", uvicorn_cmd, cwd=workspace_root, env=env)

    # 7. Health Probing & Desktop Window Launch
    health_url = f"http://127.0.0.1:{args.port_web}/api/health"
    web_url = f"http://127.0.0.1:{args.port_web}"
    print(f"\n[*] Probing gateway health on {health_url}...")

    is_healthy = False
    for i in range(60):  # 30 seconds max
        # Check if gateway process exited prematurely
        web_proc = supervisor.processes.get("web_gateway")
        if web_proc and web_proc.poll() is not None:
            print(f"[ERROR] Web Gateway process terminated unexpectedly with exit code {web_proc.poll()}.", file=sys.stderr)
            break

        try:
            req = urllib.request.Request(health_url, headers={"User-Agent": "RAG-Agent-Launcher"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    is_healthy = True
                    break
        except Exception:
            pass
        time.sleep(0.5)

    if not is_healthy:
        print(f"[ERROR] Web Gateway failed to report healthy on {health_url} within 30 seconds.", file=sys.stderr)
        log_file = workspace_root / "evals" / "logs" / "web_gateway.log"
        if log_file.exists():
            print(f"[INFO] Inspecting {log_file}:")
            try:
                lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
                for line in lines[-20:]:
                    print(f"  {line}")
            except Exception:
                pass
        supervisor.shutdown()
        return 1

    print(f"\n[+] RAG-Agent is live and operational at {web_url}!")
    app_proc: Optional[subprocess.Popen] = None
    if not args.no_browser:
        if args.window_mode == "app":
            try:
                w_str, h_str = args.window_size.split(",")
                win_w, win_h = int(w_str.strip()), int(h_str.strip())
            except Exception:
                win_w, win_h = 1300, 880

            app_proc = launch_desktop_window(
                url=web_url,
                workspace_root=workspace_root,
                width=win_w,
                height=win_h,
                app_id="rag-agent",
                prefer_browser=False,
            )
            if app_proc:
                supervisor.processes["desktop_window"] = app_proc
                supervisor.spawned_pids.add(app_proc.pid)
                supervisor.assign_process_to_job(app_proc)
        else:
            print("[*] Opening default web browser...")
            try:
                webbrowser.open(web_url)
            except Exception as e:
                print(f"[!] Could not launch browser automatically: {e}")

    print("\n" + "=" * 64)
    if app_proc:
        print(" RAG-Agent is running in standalone desktop window mode.")
        print(" Close the application window or press Ctrl+C in this console to terminate.")
    else:
        print(" RAG-Agent is running. Press Ctrl+C in this console to terminate.")
    print("=" * 64)

    exit_code = 0
    try:
        while True:
            if app_proc and app_proc.poll() is not None:
                print("\n[*] Native desktop app window closed by user. Terminating services...")
                break
            # Fail fast if critical background services crash prematurely
            web_proc = supervisor.processes.get("web_gateway")
            if web_proc:
                rc = web_proc.poll()
                if rc is not None:
                    print(f"\n[ERROR] Web Gateway terminated unexpectedly with exit code {rc}. Terminating services...", file=sys.stderr)
                    exit_code = 1
                    break
            php_proc = supervisor.processes.get("php_backend")
            if php_proc:
                rc = php_proc.poll()
                if rc is not None:
                    print(f"\n[ERROR] PHP backend terminated unexpectedly with exit code {rc}. Terminating services...", file=sys.stderr)
                    exit_code = 1
                    break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[*] Received shutdown signal.")
    finally:
        supervisor.shutdown()

    return exit_code



if __name__ == "__main__":
    sys.exit(main())
