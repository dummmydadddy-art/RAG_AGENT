"""
Operational Budget Guard for Self-Learning Coding Agent.
Enforces limits from .agents/config/budgets.yaml and halts runs upon ceiling breach.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / ".agents" / "config" / "budgets.yaml"
DEFAULT_TRACE_DIR = Path(__file__).resolve().parents[1] / ".agents" / "traces"


class BudgetBreachedError(RuntimeError):
    """Raised when an execution parameter breaches operational budget ceilings."""

    def __init__(self, metric: str, limit: Any, observed: Any, task_or_run_id: str):
        self.metric = metric
        self.limit = limit
        self.observed = observed
        self.task_or_run_id = task_or_run_id
        super().__init__(
            f"Operational budget breached ceiling: {metric} limit={limit}, "
            f"observed={observed} on {task_or_run_id}. Execution halted."
        )


def load_budget_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        # Fallback defaults matching architecture spec
        return {
            "task_execution": {
                "max_iterations_per_task": 4,
                "max_retries_on_failure": 2,
                "timeout_seconds_per_task": 300,
            },
            "team_debate": {
                "max_debate_rounds": 2,
                "max_parallel_implementers": 3,
                "timeout_seconds_per_round": 180,
            },
            "resource_limits": {
                "max_prompt_tokens": 32000,
                "max_lessons_injected": 5,
                "max_lesson_tokens": 1500,
            },
            "physmath_sandbox": {
                "timeout_seconds": 5.0,
                "max_memory_mb": 512,
                "allow_network": False,
            },
        }

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class BudgetGuard:
    """Monitors running tasks and team debates against operational budgets."""

    def __init__(self, config_path: Optional[Path] = None, trace_dir: Optional[Path] = None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config = load_budget_config(self.config_path)
        self.trace_dir = trace_dir or DEFAULT_TRACE_DIR
        self.trace_dir.mkdir(parents=True, exist_ok=True)

    def _record_breach(self, task_or_run_id: str, metric: str, limit: Any, observed: Any, details: str = ""):
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        incident = {
            "timestamp": timestamp,
            "task_or_run_id": task_or_run_id,
            "metric": metric,
            "limit": limit,
            "observed": observed,
            "details": details,
            "status": "HALTED",
        }
        breach_file = self.trace_dir / f"breach_{timestamp}_{metric}.json"
        breach_file.write_text(json.dumps(incident, indent=2), encoding="utf-8")

    def check_task_iteration(self, task_id: str, current_iteration: int) -> bool:
        limit = self.config.get("task_execution", {}).get("max_iterations_per_task", 4)
        if current_iteration > limit:
            self._record_breach(task_id, "max_iterations_per_task", limit, current_iteration)
            raise BudgetBreachedError("max_iterations_per_task", limit, current_iteration, task_id)
        return True

    def check_task_retries(self, task_id: str, retries: int) -> bool:
        limit = self.config.get("task_execution", {}).get("max_retries_on_failure", 2)
        if retries > limit:
            self._record_breach(task_id, "max_retries_on_failure", limit, retries)
            raise BudgetBreachedError("max_retries_on_failure", limit, retries, task_id)
        return True

    def check_debate_rounds(self, run_id: str, current_round: int) -> bool:
        limit = self.config.get("team_debate", {}).get("max_debate_rounds", 2)
        if current_round > limit:
            self._record_breach(run_id, "max_debate_rounds", limit, current_round)
            raise BudgetBreachedError("max_debate_rounds", limit, current_round, run_id)
        return True

    def check_parallel_implementers(self, run_id: str, count: int) -> bool:
        limit = self.config.get("team_debate", {}).get("max_parallel_implementers", 3)
        if count > limit:
            self._record_breach(run_id, "max_parallel_implementers", limit, count)
            raise BudgetBreachedError("max_parallel_implementers", limit, count, run_id)
        return True

    def check_task_wall_time(self, task_id: str, elapsed_seconds: float) -> bool:
        limit = self.config.get("task_execution", {}).get("timeout_seconds_per_task", 300)
        if elapsed_seconds > limit:
            self._record_breach(task_id, "timeout_seconds_per_task", limit, elapsed_seconds)
            raise BudgetBreachedError("timeout_seconds_per_task", limit, elapsed_seconds, task_id)
        return True

    def check_lessons_injection(self, lessons: List[str], token_count: Optional[int] = None) -> bool:
        limit = self.config.get("resource_limits", {}).get("max_lessons_injected", 5)
        if len(lessons) > limit:
            self._record_breach("retrieval", "max_lessons_injected", limit, len(lessons))
            raise BudgetBreachedError("max_lessons_injected", limit, len(lessons), "retrieval")
        return True
