"""
tests/unit/test_web_learning_routes.py

Comprehensive unit and contract test suite for Autonomous Self-Learning API:
1. GET /api/learning/status - Schema validation, fields, types, and SQLite count
2. GET /api/learning/status - Running, Stopped, and Idle state branches
3. POST /api/learning/start - Normal child process spawn and PID persistence
4. POST /api/learning/start - Already-running idempotent guard
5. POST /api/learning/start - Pydantic request constraints (interval, max_iter)
6. POST /api/learning/stop - Clean termination and state transition
7. POST /api/learning/stop - Already-stopped idempotent guard
8. POST /api/learning/stop - Fallback termination when graceful stop times out
9. Frontend static DOM & asset presence - learning-widget, badges, CSS, JS
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from src.web.app import app
from src.web.schemas import (
    LearningActionResponse,
    LearningStatusResponse,
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Creates in-memory TestClient bound to the FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


# ============================================================================
# 1. GET /api/learning/status TESTS
# ============================================================================

def test_get_learning_status_schema_and_structure(client: TestClient) -> None:
    """GET /api/learning/status returns HTTP 200 conforming to model."""
    resp = client.get("/api/learning/status")
    assert resp.status_code == 200
    data = resp.json()

    # Validate against Pydantic model contract
    parsed = LearningStatusResponse(**data)
    assert parsed.status in ("Running", "Stopped", "Idle")
    assert isinstance(parsed.uptime_seconds, float)
    assert isinstance(parsed.cycle_count, int)
    assert isinstance(parsed.total_lessons, int)
    assert parsed.total_lessons >= 0
    assert isinstance(parsed.details, dict)


def test_get_learning_status_mocked_running(client: TestClient) -> None:
    """GET /api/learning/status reports 'Running' when daemon is active."""
    mock_proc = MagicMock()
    mock_proc.pid = 9999
    mock_proc.create_time.return_value = time.time() - 360.0
    mock_proc.is_running.return_value = True

    with patch("src.web.routes.learning._find_running_daemon", return_value=mock_proc):
        resp = client.get("/api/learning/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "Running"
        assert data["pid"] == 9999
        assert data["uptime_seconds"] >= 355.0


def test_get_learning_status_mocked_stopped(client: TestClient, tmp_path: Path) -> None:
    """GET /api/learning/status reports 'Stopped' when process is absent but state exists."""
    with patch("src.web.routes.learning._find_running_daemon", return_value=None), \
         patch("src.web.routes.learning.STATE_FILE") as mock_state, \
         patch("src.web.routes.learning.PID_FILE") as mock_pid:
        mock_state.exists.return_value = True
        mock_state.read_text.return_value = json.dumps({
            "status": "Stopped",
            "cycle_count": 42,
            "last_cycle_timestamp": "2026-10-31T12:00:00Z"
        })
        mock_pid.exists.return_value = False

        resp = client.get("/api/learning/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "Stopped"
        assert data["pid"] is None
        assert data["uptime_seconds"] == 0.0
        assert data["cycle_count"] == 42
        assert data["last_cycle_timestamp"] == "2026-10-31T12:00:00Z"


def test_get_learning_status_mocked_idle(client: TestClient) -> None:
    """GET /api/learning/status reports 'Idle' when no process and no state files exist."""
    with patch("src.web.routes.learning._find_running_daemon", return_value=None), \
         patch("src.web.routes.learning.STATE_FILE") as mock_state, \
         patch("src.web.routes.learning.PID_FILE") as mock_pid:
        mock_state.exists.return_value = False
        mock_pid.exists.return_value = False

        resp = client.get("/api/learning/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "Idle"
        assert data["pid"] is None
        assert data["uptime_seconds"] == 0.0


def test_get_learning_status_reads_total_lessons_from_sqlite(client: TestClient) -> None:
    """GET /api/learning/status returns integer total_lessons matching sqlite query."""
    with patch("src.web.routes.learning._get_total_lessons", return_value=15):
        resp = client.get("/api/learning/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_lessons"] == 15


# ============================================================================
# 2. POST /api/learning/start TESTS
# ============================================================================

def test_post_learning_start_when_already_running(client: TestClient) -> None:
    """POST /api/learning/start returns 'already_running' idempotently if active."""
    mock_proc = MagicMock()
    mock_proc.pid = 5555

    with patch("src.web.routes.learning._find_running_daemon", return_value=mock_proc):
        resp = client.post("/api/learning/start", json={"interval_seconds": 15.0})
        assert resp.status_code == 200
        data = resp.json()
        parsed = LearningActionResponse(**data)
        assert parsed.status == "already_running"
        assert parsed.pid == 5555
        assert "already active" in parsed.message


def test_post_learning_start_spawns_process_successfully(client: TestClient) -> None:
    """POST /api/learning/start launches child process and returns 'started'."""
    mock_child = MagicMock()
    mock_child.pid = 12345

    with patch("src.web.routes.learning._find_running_daemon", return_value=None), \
         patch("subprocess.Popen", return_value=mock_child) as mock_popen, \
         patch("src.web.routes.learning.PID_FILE"), \
         patch("src.web.routes.learning.STATE_FILE"), \
         patch("src.web.routes.learning.STOP_FILE"):

        resp = client.post(
            "/api/learning/start",
            json={"interval_seconds": 25.0, "max_iterations": 10}
        )
        assert resp.status_code == 200
        data = resp.json()
        parsed = LearningActionResponse(**data)
        assert parsed.status == "started"
        assert parsed.pid == 12345
        assert "started successfully" in parsed.message

        assert mock_popen.called
        args, _ = mock_popen.call_args
        cmd_list = args[0]
        assert "--interval-seconds" in cmd_list
        assert "25.0" in cmd_list
        assert "--max-iterations" in cmd_list
        assert "10" in cmd_list


def test_post_learning_start_validation_interval_too_low(client: TestClient) -> None:
    """POST /api/learning/start rejects interval_seconds < 1.0 with 422."""
    resp = client.post("/api/learning/start", json={"interval_seconds": 0.5})
    assert resp.status_code == 422


def test_post_learning_start_validation_interval_too_high(client: TestClient) -> None:
    """POST /api/learning/start rejects interval_seconds > 3600.0 with 422."""
    resp = client.post("/api/learning/start", json={"interval_seconds": 3601.0})
    assert resp.status_code == 422


def test_post_learning_start_validation_iterations_negative(client: TestClient) -> None:
    """POST /api/learning/start rejects negative max_iterations with 422."""
    resp = client.post("/api/learning/start", json={"max_iterations": -1})
    assert resp.status_code == 422


# ============================================================================
# 3. POST /api/learning/stop TESTS
# ============================================================================

def test_post_learning_stop_when_not_running(client: TestClient) -> None:
    """POST /api/learning/stop returns 'not_running' idempotently if process absent."""
    with patch("src.web.routes.learning._find_running_daemon", return_value=None), \
         patch("src.web.routes.learning.PID_FILE"), \
         patch("src.web.routes.learning.STOP_FILE"):

        resp = client.post("/api/learning/stop")
        assert resp.status_code == 200
        data = resp.json()
        parsed = LearningActionResponse(**data)
        assert parsed.status == "not_running"
        assert parsed.pid is None
        assert "not currently running" in parsed.message


def test_post_learning_stop_graceful_clean_exit(client: TestClient) -> None:
    """POST /api/learning/stop cleanly terminates running daemon process."""
    mock_proc = MagicMock()
    mock_proc.pid = 8888
    # Returns False on second check, indicating clean stop
    mock_proc.is_running.side_effect = [True, False]

    with patch("src.web.routes.learning._find_running_daemon", return_value=mock_proc), \
         patch("src.web.routes.learning.PID_FILE"), \
         patch("src.web.routes.learning.STOP_FILE"), \
         patch("src.web.routes.learning.STATE_FILE"):

        resp = client.post("/api/learning/stop")
        assert resp.status_code == 200
        data = resp.json()
        parsed = LearningActionResponse(**data)
        assert parsed.status == "stopped"
        assert parsed.pid == 8888
        assert "terminated cleanly" in parsed.message


def test_post_learning_stop_fallback_terminate_on_timeout(client: TestClient) -> None:
    """POST /api/learning/stop invokes proc.terminate() if graceful shutdown times out."""
    mock_proc = MagicMock()
    mock_proc.pid = 9991
    mock_proc.is_running.return_value = True

    with patch("src.web.routes.learning._find_running_daemon", return_value=mock_proc), \
         patch("src.web.routes.learning.PID_FILE"), \
         patch("src.web.routes.learning.STOP_FILE"), \
         patch("src.web.routes.learning.STATE_FILE"), \
         patch("time.sleep", return_value=None):

        resp = client.post("/api/learning/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stopped"
        assert data["pid"] == 9991
        assert mock_proc.terminate.called


# ============================================================================
# 4. FRONTEND ASSET & DOM TESTS
# ============================================================================

def test_index_html_contains_learning_widget(client: TestClient) -> None:
    """index.html must render .learning-widget, badges, and toggle button in header."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert 'id="learning-widget"' in html or 'class="learning-widget"' in html
    assert 'id="learning-dot"' in html
    assert 'id="learning-status-label"' in html
    assert 'id="learning-cycles-pill"' in html
    assert 'id="learning-lessons-pill"' in html
    assert 'id="learning-toggle-btn"' in html


def test_main_css_contains_learning_widget_styles(client: TestClient) -> None:
    """GET /static/css/main.css must serve classes for learning widget and status states."""
    resp = client.get("/static/css/main.css")
    assert resp.status_code == 200
    css = resp.text

    assert ".learning-widget" in css
    assert ".learning-dot" in css
    assert ".learning-dot.running" in css
    assert ".learning-toggle-btn" in css
    assert "pulse-dot" in css


def test_telemetry_js_exports_learning_controller(client: TestClient) -> None:
    """GET /static/js/telemetry.js must export LearningWidgetController."""
    resp = client.get("/static/js/telemetry.js")
    assert resp.status_code == 200
    js = resp.text

    assert "export class LearningWidgetController" in js
    assert "handleToggle" in js
    assert "/api/learning/status" in js
    assert "pollInterval" in js
