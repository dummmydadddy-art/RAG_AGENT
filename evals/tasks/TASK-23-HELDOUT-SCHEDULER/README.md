# Task Specification: Real-Time Preemptive Task Scheduler with Earliest Deadline First

## 1. Class & Method Contract
Implement `PreemptiveTaskScheduler` and `ScheduledTask` in `src/task_scheduler.py`.

### Constructor Signature
```python
def __init__(self) -> None:
```

### Methods
1. `add_task(self, task_id: str, priority: int, computation_time: float, deadline: float) -> None`:
   - Adds real-time task with deadline $d$ and computation time $C$. Must satisfy $C > 0, d > 0$. If not, raise `ValueError`.
2. `schedule_next(self, current_time: float) -> Optional[str]`:
   - Returns next task ID to run under Earliest Deadline First (EDF) rule (minimal deadline among pending tasks).
   - If deadlines tie, breaks tie by higher priority (larger priority integer).
3. `complete_task(self, task_id: str, finish_time: float) -> Dict[str, Any]`:
   - Marks task complete; reports whether deadline was met (`finish_time <= deadline`).
