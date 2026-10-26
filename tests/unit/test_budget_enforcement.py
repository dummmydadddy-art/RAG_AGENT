"""
Unit tests for Operational Budget Enforcement (Phase 4).
Verifies that any budget ceiling breach halts execution cleanly and emits an incident record.
"""

import os
import pytest
from pathlib import Path
from scripts.budget_guard import (
    BudgetGuard,
    BudgetBreachedError,
    load_budget_config,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def guard(tmp_path):
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    return BudgetGuard(
        config_path=ROOT / ".agents" / "config" / "budgets.yaml",
        trace_dir=traces_dir,
    )


def test_iteration_budget_within_limits(guard):
    # Limit is 4
    assert guard.check_task_iteration("TASK-01", 1) is True
    assert guard.check_task_iteration("TASK-01", 4) is True


def test_iteration_budget_breach_stops_run(guard):
    with pytest.raises(BudgetBreachedError) as exc_info:
        guard.check_task_iteration("TASK-01", 5)

    err = exc_info.value
    assert err.metric == "max_iterations_per_task"
    assert err.limit == 4
    assert err.observed == 5
    assert "breached ceiling" in str(err)


def test_retries_budget_breach_stops_run(guard):
    # Limit is 2
    assert guard.check_task_retries("TASK-02", 2) is True
    with pytest.raises(BudgetBreachedError) as exc_info:
        guard.check_task_retries("TASK-02", 3)
    assert exc_info.value.metric == "max_retries_on_failure"


def test_debate_rounds_breach_stops_run(guard):
    # Limit is 2
    assert guard.check_debate_rounds("team-run-1", 2) is True
    with pytest.raises(BudgetBreachedError) as exc_info:
        guard.check_debate_rounds("team-run-1", 3)
    assert exc_info.value.metric == "max_debate_rounds"


def test_parallel_implementers_breach_stops_run(guard):
    # Limit is 3
    assert guard.check_parallel_implementers("team-run-1", 3) is True
    with pytest.raises(BudgetBreachedError) as exc_info:
        guard.check_parallel_implementers("team-run-1", 4)
    assert exc_info.value.metric == "max_parallel_implementers"


def test_timeout_budget_breach_stops_run(guard):
    # Limit is 300s
    assert guard.check_task_wall_time("TASK-03", 299.5) is True
    with pytest.raises(BudgetBreachedError) as exc_info:
        guard.check_task_wall_time("TASK-03", 305.0)
    assert exc_info.value.metric == "timeout_seconds_per_task"


def test_lessons_injection_breach_stops_run(guard):
    # Limit is 5 lessons
    assert guard.check_lessons_injection(["L1", "L2", "L3", "L4", "L5"]) is True
    with pytest.raises(BudgetBreachedError) as exc_info:
        guard.check_lessons_injection(["L1", "L2", "L3", "L4", "L5", "L6"])
    assert exc_info.value.metric == "max_lessons_injected"


def test_breach_incident_record_written(guard):
    with pytest.raises(BudgetBreachedError):
        guard.check_task_iteration("TASK-05", 6)

    # Verify breach incident JSON was written to traces_dir
    breach_files = list(guard.trace_dir.glob("breach_*.json"))
    assert len(breach_files) == 1
    content = breach_files[0].read_text(encoding="utf-8")
    assert "TASK-05" in content
    assert "max_iterations_per_task" in content
