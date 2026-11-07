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
    AblationComparison,
    AccuracyHistoryResponse,
    AccuracyMetricPoint,
    HarvesterStatusResponse,
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


# ============================================================================
# 5. GET /api/learning/accuracy TESTS
# ============================================================================

def test_get_learning_accuracy_schema_and_structure(client: TestClient) -> None:
    """GET /api/learning/accuracy returns 200 OK and conforms to AccuracyHistoryResponse."""
    resp = client.get("/api/learning/accuracy")
    assert resp.status_code == 200
    data = resp.json()

    parsed = AccuracyHistoryResponse(**data)
    assert 0.0 <= parsed.current_pass_at_1 <= 1.0
    assert isinstance(parsed.history, list)
    if parsed.ablation:
        assert isinstance(parsed.ablation, AblationComparison)
        assert parsed.ablation.num_samples >= 0
        assert "pass_at_1" in parsed.ablation.deltas
        assert isinstance(parsed.ablation.lesson_advantage_demonstrated, bool)
    assert isinstance(parsed.summary, dict)


def test_get_learning_accuracy_mocked_history(client: TestClient) -> None:
    """GET /api/learning/accuracy properly formats tracker history and ablation data."""
    mock_point1 = MagicMock()
    mock_point1.id = "bench_001"
    mock_point1.timestamp = "2026-11-05T12:00:00Z"
    mock_point1.cycle_iteration = 1
    mock_point1.pass_at_1 = 0.50
    mock_point1.test_pass_rate = 0.60
    mock_point1.avg_patch_iterations = 1.0
    mock_point1.invariant_violation_rate = 0.10
    mock_point1.lessons_count = 5
    mock_point1.lessons_enabled = True
    mock_point1.details = {"domain": "dynamic_programming"}

    mock_point2 = MagicMock()
    mock_point2.id = "bench_002"
    mock_point2.timestamp = "2026-11-05T13:00:00Z"
    mock_point2.cycle_iteration = 2
    mock_point2.pass_at_1 = 1.0
    mock_point2.test_pass_rate = 1.0
    mock_point2.avg_patch_iterations = 0.0
    mock_point2.invariant_violation_rate = 0.0
    mock_point2.lessons_count = 10
    mock_point2.lessons_enabled = True
    mock_point2.details = {"domain": "graph_algorithms"}

    mock_ablation = {
        "num_samples": 4,
        "with_lessons": {"pass_at_1": 1.0, "test_pass_rate": 1.0, "invariant_compliance": 1.0},
        "without_lessons": {"pass_at_1": 0.25, "test_pass_rate": 0.25, "invariant_compliance": 0.25},
        "deltas": {"pass_at_1": 0.75, "test_pass_rate": 0.75, "invariant_compliance": 0.75},
        "lesson_advantage_demonstrated": True,
    }

    with patch("scripts.learning.accuracy_tracker.AccuracyTracker.get_history", return_value=[mock_point1, mock_point2]), \
         patch("scripts.learning.accuracy_tracker.AccuracyTracker.get_latest_metrics", return_value=mock_point2), \
         patch("scripts.learning.accuracy_tracker.AccuracyTracker.compare_ablation", return_value=mock_ablation), \
         patch("src.web.routes.learning._cached_ablation", None):

        resp = client.get("/api/learning/accuracy?force_ablation=true")
        assert resp.status_code == 200
        data = resp.json()

        assert data["current_pass_at_1"] == 1.0
        assert len(data["history"]) == 2
        assert data["history"][0]["id"] == "bench_001"
        assert data["history"][0]["pass_at_1"] == 0.50
        assert data["history"][0]["invariant_compliance"] == 0.90
        assert data["history"][1]["id"] == "bench_002"
        assert data["history"][1]["pass_at_1"] == 1.0

        assert data["ablation"]["num_samples"] == 4
        assert data["ablation"]["deltas"]["pass_at_1"] == 0.75
        assert data["ablation"]["lesson_advantage_demonstrated"] is True


def test_get_learning_accuracy_error_handling(client: TestClient) -> None:
    """GET /api/learning/accuracy handles internal tracker exceptions gracefully."""
    with patch("scripts.learning.accuracy_tracker.AccuracyTracker.get_history", side_effect=RuntimeError("Database lock contention")):
        resp = client.get("/api/learning/accuracy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_pass_at_1"] == 1.0
        assert data["history"] == []
        assert "Database lock contention" in data["summary"]["error"]


# ============================================================================
# 6. GET /api/learning/harvester TESTS
# ============================================================================

def test_get_learning_harvester_schema_and_structure(client: TestClient) -> None:
    """GET /api/learning/harvester returns 200 OK conforming to HarvesterStatusResponse."""
    resp = client.get("/api/learning/harvester")
    assert resp.status_code == 200
    data = resp.json()

    parsed = HarvesterStatusResponse(**data)
    assert parsed.status in ("healthy", "error", "degraded", "idle")
    assert parsed.total_sources_scraped >= 0
    assert parsed.ingested_chunks >= 0
    assert 3.0 <= parsed.shannon_entropy_score <= 6.0
    assert parsed.max_chunks == 500
    assert 0.0 <= parsed.fifo_queue_utilization <= 100.0


def test_get_learning_harvester_mocked_status(client: TestClient) -> None:
    """GET /api/learning/harvester returns mocked harvester and entropy metrics correctly."""
    mock_status = {
        "total_sources_scraped": 42,
        "ingested_chunks": 125,
        "shannon_entropy_score": 4.85,
        "fifo_queue_utilization": 25.0,
        "max_chunks": 500,
        "material_chunks_count": 125,
        "stem_knowledge_docs_count": 42,
        "last_run": "2026-11-06T15:30:00Z",
        "details": {"ceiling": 500, "entropy": 4.85, "utilization_pct": 25.0},
    }

    with patch("scripts.learning.web_harvester.WebHarvester.get_status", return_value=mock_status):
        resp = client.get("/api/learning/harvester")
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "healthy"
        assert data["total_sources_scraped"] == 42
        assert data["ingested_chunks"] == 125
        assert data["shannon_entropy_score"] == 4.85
        assert data["fifo_queue_utilization"] == 25.0
        assert data["max_chunks"] == 500
        assert data["material_chunks_count"] == 125
        assert data["stem_knowledge_docs_count"] == 42
        assert data["last_run"] == "2026-11-06T15:30:00Z"


def test_get_learning_harvester_error_handling(client: TestClient) -> None:
    """GET /api/learning/harvester returns resilient error response when harvester fails."""
    with patch("scripts.learning.web_harvester.WebHarvester.get_status", side_effect=Exception("Disk I/O error")):
        resp = client.get("/api/learning/harvester")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert data["ingested_chunks"] == 0
        assert "Disk I/O error" in data["details"]["error"]


# ============================================================================
# 7. EXPANDED FRONTEND ASSET & DOM TESTS
# ============================================================================

def test_index_html_contains_accuracy_and_harvester_pills(client: TestClient) -> None:
    """index.html must contain pass@1 pill, harvester pill, and learning drawer."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert 'id="learning-pass1-pill"' in html
    assert 'id="learning-harvester-pill"' in html
    assert 'id="learning-drawer"' in html
    assert 'id="drawer-pass1-pill"' in html
    assert 'id="drawer-harvester-pill"' in html
    assert 'id="drawer-entropy-pill"' in html
    assert 'id="learning-drawer-close"' in html


def test_main_css_contains_accuracy_and_harvester_styles(client: TestClient) -> None:
    """main.css must serve styles for accuracy pill, harvester pill, and telemetry drawer."""
    resp = client.get("/static/css/main.css")
    assert resp.status_code == 200
    css = resp.text

    assert ".accuracy-pill" in css
    assert ".harvester-pill" in css
    assert ".learning-drawer" in css
    assert ".learning-telemetry-grid" in css
    assert ".telemetry-metric-row" in css


def test_telemetry_js_fetches_accuracy_and_harvester(client: TestClient) -> None:
    """telemetry.js must fetch /api/learning/accuracy and /api/learning/harvester."""
    resp = client.get("/static/js/telemetry.js")
    assert resp.status_code == 200
    js = resp.text

    assert "/api/learning/accuracy" in js
    assert "/api/learning/harvester" in js
    assert "renderAccuracy" in js
    assert "renderHarvester" in js
    assert "toggleDrawer" in js
    assert "Escape" in js
    assert "contains" in js


# ============================================================================
# 8. EDGE CASE & CONCURRENCY TESTS
# ============================================================================

def test_get_learning_accuracy_limit_validation(client: TestClient) -> None:
    """GET /api/learning/accuracy rejects limit out-of-bounds (1 <= limit <= 500) with 422."""
    resp_zero = client.get("/api/learning/accuracy?limit=0")
    assert resp_zero.status_code == 422

    resp_neg = client.get("/api/learning/accuracy?limit=-5")
    assert resp_neg.status_code == 422

    resp_too_high = client.get("/api/learning/accuracy?limit=501")
    assert resp_too_high.status_code == 422

    resp_valid = client.get("/api/learning/accuracy?limit=10")
    assert resp_valid.status_code == 200


def test_get_learning_accuracy_concurrency(client: TestClient) -> None:
    """Concurrent requests to /api/learning/accuracy succeed cleanly without lock errors."""
    import concurrent.futures

    def fetch_acc():
        return client.get("/api/learning/accuracy")

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(fetch_acc) for _ in range(12)]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            assert res.status_code == 200
            data = res.json()
            assert "current_pass_at_1" in data


def test_get_learning_harvester_status_degraded_when_full(client: TestClient) -> None:
    """GET /api/learning/harvester reports 'degraded' when FIFO queue reaches 100% capacity."""
    mock_status = {
        "total_sources_scraped": 600,
        "ingested_chunks": 500,
        "shannon_entropy_score": 4.60,
        "fifo_queue_utilization": 100.0,
        "max_chunks": 500,
        "material_chunks_count": 500,
        "stem_knowledge_docs_count": 600,
        "last_run": "2026-11-07T12:00:00Z",
        "details": {"ceiling": 500, "entropy": 4.60, "utilization_pct": 100.0},
    }

    with patch("scripts.learning.web_harvester.WebHarvester.get_status", return_value=mock_status):
        resp = client.get("/api/learning/harvester")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["fifo_queue_utilization"] == 100.0


def test_get_learning_harvester_status_idle_when_empty(client: TestClient) -> None:
    """GET /api/learning/harvester reports 'idle' when 0 items scraped and 0 chunks exist."""
    mock_status = {
        "total_sources_scraped": 0,
        "ingested_chunks": 0,
        "shannon_entropy_score": 4.5,
        "fifo_queue_utilization": 0.0,
        "max_chunks": 500,
        "material_chunks_count": 0,
        "stem_knowledge_docs_count": 0,
        "last_run": None,
        "details": {"ceiling": 500, "entropy": 4.5, "utilization_pct": 0.0},
    }

    with patch("scripts.learning.web_harvester.WebHarvester.get_status", return_value=mock_status):
        resp = client.get("/api/learning/harvester")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "idle"


def test_web_harvester_db_path_default_not_none() -> None:
    """WebHarvester() without arguments must resolve db_path to a Path, not None."""
    from scripts.learning.web_harvester import WebHarvester
    from pathlib import Path
    h = WebHarvester()
    assert h.db_path is not None
    assert isinstance(h.db_path, Path)
    assert h.db_path.name == "vectors.sqlite"


