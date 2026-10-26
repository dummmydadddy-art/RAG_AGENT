import heapq
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ScheduledTask(BaseModel):
    task_id: str
    priority: int
    computation_time: float
    deadline: float
    remaining_time: float
    completed: bool = False


class PreemptiveTaskScheduler:
    """
    Real-time preemptive task scheduler implementing Earliest Deadline First (EDF) with priority tie-breaking.
    """

    def __init__(self) -> None:
        self.tasks: Dict[str, ScheduledTask] = {}

    def add_task(
        self,
        task_id: str,
        priority: int,
        computation_time: float,
        deadline: float,
    ) -> None:
        if computation_time <= 0.0 or deadline <= 0.0:
            raise ValueError("Computation time and deadline must be positive")

        task = ScheduledTask(
            task_id=task_id,
            priority=int(priority),
            computation_time=float(computation_time),
            deadline=float(deadline),
            remaining_time=float(computation_time),
        )
        self.tasks[task_id] = task

    def schedule_next(self, current_time: float = 0.0) -> Optional[str]:
        pending = [t for t in self.tasks.values() if not t.completed and t.remaining_time > 0]
        if not pending:
            return None

        # Sort by:
        # 1. Earliest deadline (ascending)
        # 2. Priority (descending: -priority)
        # 3. task_id (lexicographical)
        pending.sort(key=lambda t: (t.deadline, -t.priority, t.task_id))
        return pending[0].task_id

    def complete_task(self, task_id: str, finish_time: float) -> Dict[str, Any]:
        task = self.tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found in scheduler")

        task.completed = True
        task.remaining_time = 0.0
        met = bool(finish_time <= task.deadline)

        return {
            "task_id": task_id,
            "deadline": task.deadline,
            "finish_time": finish_time,
            "deadline_met": met,
        }
