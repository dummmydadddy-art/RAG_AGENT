"""
src/web/routes/learning.py

FastAPI route handlers for managing the Autonomous Self-Learning Daemon:
- GET /api/learning/status: Reports daemon status (Running/Stopped/Idle), PID, uptime, cycle count, total lessons.
- POST /api/learning/start: Spawns scripts/learning/autonomous_self_play.py as a supervised child process.
- POST /api/learning/stop: Gracefully terminates the daemon process.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import psutil
from fastapi import APIRouter, HTTPException

from src.web.config import get_config
from src.web.database import get_vectors_connection
from src.web.schemas import (
    LearningActionResponse,
    LearningStartRequest,
    LearningStatusResponse,
)

logger = logging.getLogger("web.routes.learning")
router = APIRouter(prefix="/learning", tags=["Autonomous Learning"])

REPO_ROOT = Path(__file__).resolve().parents[3]
LOG_DIR = REPO_ROOT / "evals" / "logs"
PID_FILE = LOG_DIR / "autonomous_self_play.pid"
STATE_FILE = LOG_DIR / "autonomous_self_play_state.json"
STOP_FILE = LOG_DIR / "autonomous_self_play.stop"


def _ensure_vectors_wal() -> None:
    """Ensures vectors.sqlite is in WAL mode to avoid writer-reader lock contention."""
    try:
        cfg = get_config()
        if cfg.vectors_db_path.exists():
            with sqlite3.connect(str(cfg.vectors_db_path), timeout=5.0) as conn:
                conn.execute("PRAGMA journal_mode = WAL;")
                conn.execute("PRAGMA busy_timeout = 10000;")
    except Exception as e:
        logger.warning(f"Could not enforce WAL mode on vectors.sqlite: {e}")


def _find_running_daemon() -> Optional[psutil.Process]:
    """Scans running processes for active autonomous_self_play.py instances."""
    # 1. Check PID file first
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                cmdline = proc.cmdline()
                if any("autonomous_self_play.py" in arg for arg in cmdline):
                    return proc
        except Exception:
            pass

    # 2. Process table scan fallback
    current_pid = os.getpid()
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.info["pid"] == current_pid:
                continue
            name = (proc.info.get("name") or "").lower()
            if "python" not in name:
                continue
            cmd = proc.info.get("cmdline") or []
            if "-c" in cmd or any("pytest" in a for a in cmd):
                continue
            if any("autonomous_self_play.py" in arg for arg in cmd):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return None


def _get_total_lessons() -> int:
    """Queries vectors.sqlite for total count of harvested lessons in read-only mode."""
    _ensure_vectors_wal()
    try:
        with get_vectors_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM rag_documents WHERE collection = 'lessons';")
            row = cursor.fetchone()
            return int(row[0]) if row else 0
    except Exception as e:
        logger.warning(f"Error querying harvested lessons from vectors.sqlite: {e}")
        return 0


def _read_state_file() -> Dict[str, Any]:
    """Reads persistent state JSON file if present."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _get_cycle_from_log() -> int:
    """Scans autonomous_self_play.log for the most recent cycle index."""
    log_file = LOG_DIR / "autonomous_self_play.log"
    if not log_file.exists():
        return 0
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        for line in reversed(lines[-200:]):
            m = re.search(r"Cycle #(\d+)", line)
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return 0


@router.get("/status", response_model=LearningStatusResponse)
def get_learning_status() -> LearningStatusResponse:
    """Returns real-time daemon status, PID, uptime, cycles, and total lessons."""
    proc = _find_running_daemon()
    total_lessons = _get_total_lessons()
    state_data = _read_state_file()

    if proc is not None:
        try:
            uptime = max(0.0, time.time() - proc.create_time())
            pid = proc.pid
            status = "Running"
        except Exception:
            uptime = 0.0
            pid = None
            status = "Stopped"
    else:
        status = "Stopped" if (STATE_FILE.exists() or PID_FILE.exists()) else "Idle"
        pid = None
        uptime = 0.0

    cycle_count = state_data.get("cycle_count", state_data.get("iteration", _get_cycle_from_log()))
    last_timestamp = state_data.get("last_cycle_timestamp")
    if not last_timestamp and STATE_FILE.exists():
        try:
            last_timestamp = datetime.datetime.fromtimestamp(
                STATE_FILE.stat().st_mtime, tz=datetime.timezone.utc
            ).isoformat()
        except Exception:
            pass

    return LearningStatusResponse(
        status=status,
        pid=pid,
        uptime_seconds=round(uptime, 1),
        cycle_count=cycle_count,
        total_lessons=total_lessons,
        last_cycle_timestamp=last_timestamp,
        details={
            "interval_seconds": state_data.get("interval_seconds", 15.0),
            "current_domain": state_data.get("current_domain"),
            "current_language": state_data.get("current_language"),
            "max_iterations": state_data.get("max_iterations", 0),
        },
    )


@router.post("/start", response_model=LearningActionResponse)
def start_learning_daemon(req: LearningStartRequest = LearningStartRequest()) -> LearningActionResponse:
    """Spawns scripts/learning/autonomous_self_play.py as a supervised child process."""
    _ensure_vectors_wal()
    proc = _find_running_daemon()
    if proc is not None:
        return LearningActionResponse(
            status="already_running",
            pid=proc.pid,
            message=f"Autonomous self-learning daemon is already active (PID {proc.pid}).",
        )

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STOP_FILE.unlink(missing_ok=True)

    script_path = REPO_ROOT / "scripts" / "learning" / "autonomous_self_play.py"
    if not script_path.exists():
        raise HTTPException(status_code=500, detail=f"Daemon script not found at {script_path}")

    cmd = [
        sys.executable,
        str(script_path),
        "--interval-seconds",
        str(req.interval_seconds),
    ]
    if req.max_iterations > 0:
        cmd.extend(["--max-iterations", str(req.max_iterations)])

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    try:
        new_proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        PID_FILE.write_text(str(new_proc.pid), encoding="utf-8")

        initial_state = {
            "pid": new_proc.pid,
            "status": "Running",
            "start_time": time.time(),
            "interval_seconds": req.interval_seconds,
            "max_iterations": req.max_iterations,
            "last_cycle_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "cycle_count": 0,
        }
        STATE_FILE.write_text(json.dumps(initial_state, indent=2), encoding="utf-8")

        logger.info(f"Spawned autonomous self-learning daemon PID {new_proc.pid}")
        return LearningActionResponse(
            status="started",
            pid=new_proc.pid,
            message="Autonomous self-learning daemon started successfully.",
        )
    except Exception as e:
        logger.error(f"Failed to spawn learning daemon: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start learning daemon: {e}")


@router.post("/stop", response_model=LearningActionResponse)
def stop_learning_daemon() -> LearningActionResponse:
    """Gracefully requests daemon shutdown and terminates if not exited within 2.5s."""
    proc = _find_running_daemon()
    if proc is None:
        PID_FILE.unlink(missing_ok=True)
        STOP_FILE.unlink(missing_ok=True)
        return LearningActionResponse(
            status="not_running",
            pid=None,
            message="Autonomous self-learning daemon is not currently running.",
        )

    target_pid = proc.pid
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STOP_FILE.write_text("stop", encoding="utf-8")

    stopped_cleanly = False
    for _ in range(5):
        if not proc.is_running():
            stopped_cleanly = True
            break
        time.sleep(0.5)

    if not stopped_cleanly and proc.is_running():
        try:
            proc.terminate()
            proc.wait(timeout=2.0)
        except Exception as e:
            logger.warning(f"Termination exception for PID {target_pid}: {e}")

    PID_FILE.unlink(missing_ok=True)
    STOP_FILE.unlink(missing_ok=True)

    state_data = _read_state_file()
    state_data["status"] = "Stopped"
    state_data["stopped_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        STATE_FILE.write_text(json.dumps(state_data, indent=2), encoding="utf-8")
    except Exception:
        pass

    return LearningActionResponse(
        status="stopped",
        pid=target_pid,
        message="Autonomous self-learning daemon terminated cleanly.",
    )
