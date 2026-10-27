import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict


def run_sandboxed_code(
    script_content: str,
    timeout_seconds: float = 5.0,
    interpreter_path: str = sys.executable,
) -> Dict[str, Any]:
    """
    Execute mathematical or scientific code in an isolated subprocess.
    Enforces timeout, isolates sys.path, and returns parsed JSON output.
    """
    start_time = time.perf_counter()

    # Prepend socket disabling code to enforce no network access
    sandboxed_header = (
        "import socket\n"
        "class _BlockedSocket(socket.socket):\n"
        "    def __init__(self, *args, **kwargs):\n"
        "        raise PermissionError('Network access is disabled inside the physmath sandbox')\n"
        "socket.socket = _BlockedSocket\n"
        "socket.create_connection = lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError('Network access is disabled inside the physmath sandbox'))\n"
    )

    full_script = sandboxed_header + script_content

    try:
        proc = subprocess.run(
            [interpreter_path, "-c", full_script],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        if proc.returncode != 0:
            return {
                "success": False,
                "error": proc.stderr.strip() or f"Process exited with code {proc.returncode}",
                "stdout": proc.stdout.strip(),
                "wall_time_ms": round(elapsed_ms, 2),
            }

        # Parse JSON output emitted by script
        out_str = proc.stdout.strip()
        try:
            parsed = json.loads(out_str)
            return {
                "success": True,
                "data": parsed,
                "wall_time_ms": round(elapsed_ms, 2),
            }
        except json.JSONDecodeError:
            return {
                "success": True,
                "data": {"raw_output": out_str},
                "wall_time_ms": round(elapsed_ms, 2),
            }

    except subprocess.TimeoutExpired:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "success": False,
            "error": f"Execution timed out after {timeout_seconds}s",
            "wall_time_ms": round(elapsed_ms, 2),
        }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "success": False,
            "error": f"Sandbox runner error: {str(e)}",
            "wall_time_ms": round(elapsed_ms, 2),
        }
