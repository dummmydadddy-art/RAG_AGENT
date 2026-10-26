"""
Unit tests for Unattended Weekly Scheduled Evaluation (Phase 4).
Verifies unattended execution, regression gate checking, automatic rollback on regression,
and generation of weekly reports.
"""

import os
import pytest
from pathlib import Path
from evals.scheduled_eval import (
    evaluate_scheduled_run,
    generate_weekly_report,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def sched_env(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def test_weekly_report_generation(sched_env):
    reports_dir = sched_env
    run_results = {
        "timestamp": "20261026_160000",
        "mode": "single",
        "lessons_mode": "on",
        "unattended": True,
        "store_hash": "abc1234def5678",
        "held_out_passed": 4,
        "held_out_total": 4,
        "held_out_pass_rate": 100.0,
        "overall_passed": 24,
        "overall_total": 24,
        "overall_pass_rate": 100.0,
        "regression_detected": False,
        "rollback_triggered": False,
        "tasks": [
            {"task_id": "TASK-01-CODE-LRU", "status": "PASS", "held_out": False},
            {"task_id": "TASK-06-PHYS-HEAT-1D", "status": "PASS", "held_out": True},
        ],
    }

    report_path = generate_weekly_report(run_results, output_dir=reports_dir)
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "# Weekly Scheduled Benchmark Report" in content
    assert "**Unattended Run**: True" in content
    assert "**Held-Out Regression Gate**: **PASSED**" in content
    assert "abc1234def5678" in content


def test_regression_gate_triggers_rollback(monkeypatch):
    rollback_called = False

    def mock_rollback():
        nonlocal rollback_called
        rollback_called = True
        return {"demoted_count": 2, "retired_count": 0}

    # Simulate run with a failed held-out task
    task_results = [
        {"task_id": "TASK-01-CODE-LRU", "status": "PASS", "held_out": False},
        {"task_id": "TASK-06-PHYS-HEAT-1D", "status": "FAIL", "held_out": True},
    ]

    res = evaluate_scheduled_run(
        task_results=task_results,
        store_hash="testhash123",
        rollback_fn=mock_rollback,
    )

    assert res["regression_detected"] is True
    assert res["rollback_triggered"] is True
    assert rollback_called is True
    assert res["held_out_pass_rate"] == 0.0


def test_regression_gate_passes_when_held_out_green():
    rollback_called = False

    def mock_rollback():
        nonlocal rollback_called
        rollback_called = True
        return {}

    task_results = [
        {"task_id": "TASK-01-CODE-LRU", "status": "PASS", "held_out": False},
        {"task_id": "TASK-06-PHYS-HEAT-1D", "status": "PASS", "held_out": True},
    ]

    res = evaluate_scheduled_run(
        task_results=task_results,
        store_hash="testhash123",
        rollback_fn=mock_rollback,
    )

    assert res["regression_detected"] is False
    assert res["rollback_triggered"] is False
    assert rollback_called is False
    assert res["held_out_pass_rate"] == 100.0
