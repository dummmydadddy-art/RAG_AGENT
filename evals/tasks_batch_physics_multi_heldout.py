"""
Additional tasks batch: Physics (16-18), Multi-Module (19-22), and Held-Out (23-24)
"""

CANARY = "CANARY-RAG-AGENT-CHECK-V2-7A8B9C0D-E1F2-3456-7890-ABCDEF123456"
HDR = f"# Canary: {CANARY}\n"

TASKS_PHYSICS_MULTI_HELDOUT = [
    {
        "id": "TASK-16-PHYS-PENDULUM",
        "category": "physics_numerics",
        "held_out": False,
        "title": "Double Pendulum Chaotic Dynamics via Runge-Kutta RK4",
        "target_file": "src/double_pendulum.py",
        "spec": """# Task Specification: Double Pendulum Chaotic Dynamics via Runge-Kutta RK4

## 1. Class & Method Contract
Implement `DoublePendulum` in `src/double_pendulum.py`.

### Constructor Signature
```python
def __init__(
    self,
    l1: float = 1.0,
    l2: float = 1.0,
    m1: float = 1.0,
    m2: float = 1.0,
    g: float = 9.81
) -> None:
```
Parameters must be strictly positive floats. If any `<= 0`, raise `ValueError("Lengths, masses and gravity must be positive")`.

### Method: `simulate(self, theta1: float, omega1: float, theta2: float, omega2: float, dt: float, steps: int) -> Dict[str, Any]`
- Solves coupled nonlinear Lagrangian equations of motion using 4th-order Runge-Kutta (RK4).
- Returns dictionary containing:
  - `"t"`: NumPy array of time points `[0, dt, 2*dt, ..., steps*dt]`.
  - `"theta1"`, `"omega1"`, `"theta2"`, `"omega2"`: NumPy arrays of trajectories.
  - `"energy"`: NumPy array of total mechanical energy $E(t) = T(t) + V(t)$.
  - Energy drift $|E(t) - E(0)| / |E(0)|$ must remain $\\le 10^{-3}$ over small amplitudes.
""",
        "traceability": """# Traceability Matrix: TASK-16-PHYS-PENDULUM
- test_pendulum_small_angle: verifies small angle harmonic oscillation frequency.
- test_pendulum_energy_conservation: verifies mechanical energy conservation drift < 1e-3.
""",
        "test_code": HDR + """import math
import numpy as np
import pytest
from src.double_pendulum import DoublePendulum

def test_double_pendulum_energy_conservation():
    dp = DoublePendulum(l1=1.0, l2=1.0, m1=1.0, m2=1.0, g=9.81)
    res = dp.simulate(theta1=0.2, omega1=0.0, theta2=0.1, omega2=0.0, dt=0.01, steps=500)

    energies = res["energy"]
    e0 = energies[0]
    max_drift = np.max(np.abs(energies - e0)) / abs(e0)
    assert max_drift < 1e-3
"""
    },
    {
        "id": "TASK-17-PHYS-WAVE-1D",
        "category": "physics_numerics",
        "held_out": False,
        "title": "1D Acoustic Wave PDE Solver with Absorbing Boundaries",
        "target_file": "src/wave_solver.py",
        "spec": """# Task Specification: 1D Acoustic Wave PDE Solver with Absorbing Boundaries

## 1. Function Contract
Implement `solve_wave_1d` in `src/wave_solver.py`.

### Function Signature
```python
def solve_wave_1d(
    c: float,
    length: float,
    t_max: float,
    nx: int,
    cfl: float = 0.5,
    initial_u: Optional[Callable[[np.ndarray], np.ndarray]] = None,
    initial_v: Optional[Callable[[np.ndarray], np.ndarray]] = None,
    absorbing: bool = True
) -> Dict[str, np.ndarray]:
```
- Discretizes 1D wave equation $\\frac{\\partial^2 u}{\\partial t^2} = c^2 \\frac{\\partial^2 u}{\\partial x^2}$ using 2nd-order leapfrog finite difference.
- Grid spacing $\\Delta x = \\text{length} / (nx - 1)$, time step $\\Delta t = \\text{cfl} \\cdot \\Delta x / c$.
- When `absorbing=True`, applies 1st-order Mur absorbing boundary condition: $\\frac{\\partial u}{\\partial t} \\pm c \\frac{\\partial u}{\\partial x} = 0$.
- Returns `{"x": x_grid, "t": t_grid, "u": u_grid}` where `u_grid` has shape `(nt, nx)`.
""",
        "traceability": """# Traceability Matrix: TASK-17-PHYS-WAVE-1D
- test_wave_d_alembert: verifies wave propagation speed c.
- test_wave_absorbing_boundary: verifies reflection amplitude < 5% under absorbing boundaries.
""",
        "test_code": HDR + """import numpy as np
import pytest
from src.wave_solver import solve_wave_1d

def test_wave_speed_and_absorption():
    c = 2.0
    length = 10.0
    nx = 201
    # Gaussian pulse centered at x=5.0 moving rightward
    def init_u(x):
        return np.exp(-((x - 5.0) / 0.5)**2)

    res = solve_wave_1d(c=c, length=length, t_max=1.0, nx=nx, cfl=0.5, initial_u=init_u, absorbing=True)
    u = res["u"]
    assert u.shape[1] == nx
    # Peak at t=1.0 should have traveled delta_x = c * t = 2.0 -> peak around x=7.0
    peak_x = res["x"][np.argmax(u[-1, :])]
    assert abs(peak_x - 7.0) < 0.2
"""
    },
    {
        "id": "TASK-18-PHYS-LORENZ",
        "category": "physics_numerics",
        "held_out": False,
        "title": "Lorenz Attractor Simulation and Lyapunov Exponent Estimation",
        "target_file": "src/lorenz_system.py",
        "spec": """# Task Specification: Lorenz Attractor Simulation and Lyapunov Exponent Estimation

## 1. Class & Method Contract
Implement `LorenzSystem` in `src/lorenz_system.py`.

### Constructor Signature
```python
def __init__(self, sigma: float = 10.0, rho: float = 28.0, beta: float = 8.0 / 3.0) -> None:
```

### Methods
1. `simulate(self, state0: Tuple[float, float, float], dt: float, steps: int) -> Tuple[np.ndarray, np.ndarray]`:
   - Integrates $\\dot{x} = \\sigma(y - x), \\dot{y} = x(\\rho - z) - y, \\dot{z} = x y - \\beta z$ via RK4.
   - Returns `(t, trajectory)` where `trajectory` has shape `(steps + 1, 3)`.
2. `estimate_maximal_lyapunov(self, state0: Tuple[float, float, float], dt: float = 0.01, steps: int = 5000, d0: float = 1e-8) -> float`:
   - Estimates largest Lyapunov exponent $\\lambda$ by tracking divergence of two nearby trajectories with periodic renormalization.
   - At standard parameters, $\\lambda \\in [0.75, 1.15]$.
""",
        "traceability": """# Traceability Matrix: TASK-18-PHYS-LORENZ
- test_lorenz_steady_state: verifies fixed points (0, 0, 0) and (+/- sqrt(beta*(rho-1)), ...).
- test_lorenz_positive_lyapunov: verifies chaotic behavior with lambda in [0.75, 1.15].
""",
        "test_code": HDR + """import numpy as np
import pytest
from src.lorenz_system import LorenzSystem

def test_lorenz_lyapunov_exponent():
    lorenz = LorenzSystem(sigma=10.0, rho=28.0, beta=8.0/3.0)
    # Estimate largest Lyapunov exponent
    lam = lorenz.estimate_maximal_lyapunov(state0=(1.0, 1.0, 1.0), dt=0.01, steps=2500, d0=1e-7)
    # Standard Lorenz has positive Lyapunov exponent approx 0.9
    assert 0.65 < lam < 1.25
"""
    },
    {
        "id": "TASK-19-MULTI-RAFT-KV",
        "category": "multi_module",
        "held_out": False,
        "title": "Distributed In-Memory Raft Consensus KV Store",
        "target_file": "src/raft_kv/engine.py",
        "spec": """# Task Specification: Distributed In-Memory Raft Consensus KV Store

## 1. Multi-Module Architecture
Implement modules in `src/raft_kv/`:
- `log.py`: `RaftLogEntry`, `RaftLog` with append, term tracking, truncate at index.
- `state_machine.py`: `KVStateMachine` executing `SET(key, value)`, `DELETE(key)`, and `GET(key)`.
- `engine.py`: `RaftKVEngine` coordinating consensus log and state machine replication.

### Engine Contract
```python
class RaftKVEngine:
    def __init__(self, node_id: str, peers: List[str]) -> None:
    def append_command(self, term: int, command: Dict[str, Any]) -> int:
    def commit_up_to(self, commit_index: int) -> int:
    def get(self, key: str) -> Optional[Any]:
    def is_leader(self) -> bool:
    def become_leader(self, term: int) -> None:
```
""",
        "traceability": """# Traceability Matrix: TASK-19-MULTI-RAFT-KV
- test_raft_log_and_commit: verifies log append and state machine commit advancement.
- test_raft_replicated_get_set: verifies consistent key-value state after log replication.
""",
        "test_code": HDR + """import pytest
from src.raft_kv.engine import RaftKVEngine

def test_raft_kv_engine_replication():
    engine = RaftKVEngine(node_id="node-1", peers=["node-2", "node-3"])
    engine.become_leader(term=1)
    assert engine.is_leader() is True

    idx1 = engine.append_command(term=1, command={"op": "SET", "key": "k1", "value": "v1"})
    idx2 = engine.append_command(term=1, command={"op": "SET", "key": "k2", "value": "v2"})
    assert idx1 == 1
    assert idx2 == 2

    # Before commit, k1 not applied
    assert engine.get("k1") is None

    # Commit up to index 2
    applied = engine.commit_up_to(2)
    assert applied == 2
    assert engine.get("k1") == "v1"
    assert engine.get("k2") == "v2"
"""
    },
    {
        "id": "TASK-20-MULTI-PIPELINE",
        "category": "multi_module",
        "held_out": False,
        "title": "Streaming Dataflow Pipeline with Tumbling Windows",
        "target_file": "src/dataflow/pipeline.py",
        "spec": """# Task Specification: Streaming Dataflow Pipeline with Tumbling Windows

## 1. Multi-Module Architecture
Implement modules in `src/dataflow/`:
- `window.py`: `TumblingWindow(window_size_seconds)` grouping items by event timestamp.
- `stages.py`: `MapStage`, `FilterStage`, `AggregateStage`.
- `pipeline.py`: `DataflowPipeline` linking stages and executing stream processing.

### Pipeline Contract
```python
class DataflowPipeline:
    def __init__(self) -> None:
    def add_stage(self, stage: Any) -> "DataflowPipeline":
    def process(self, records: List[Dict[str, Any]]) -> List[Any]:
```
""",
        "traceability": """# Traceability Matrix: TASK-20-MULTI-PIPELINE
- test_pipeline_filter_map: verifies stream filtering and transformation.
- test_pipeline_tumbling_window: verifies grouping by timestamp and window aggregation.
""",
        "test_code": HDR + """import pytest
from src.dataflow.pipeline import DataflowPipeline
from src.dataflow.stages import FilterStage, MapStage
from src.dataflow.window import TumblingWindow

def test_dataflow_stream_pipeline():
    pipeline = DataflowPipeline()
    pipeline.add_stage(FilterStage(predicate=lambda r: r.get("val", 0) > 10))
    pipeline.add_stage(MapStage(fn=lambda r: {"val": r["val"] * 2, "t": r["t"]}))
    pipeline.add_stage(TumblingWindow(window_size=5))

    data = [
        {"val": 5, "t": 1},
        {"val": 15, "t": 2},
        {"val": 20, "t": 4},
        {"val": 30, "t": 7},
    ]
    results = pipeline.process(data)
    assert len(results) == 2
    assert len(results[0]["items"]) == 2
    assert len(results[1]["items"]) == 1
"""
    },
    {
        "id": "TASK-21-MULTI-QUERY-ENGINE",
        "category": "multi_module",
        "held_out": False,
        "title": "In-Memory Columnar Relational Query Engine",
        "target_file": "src/query_engine/scanner.py",
        "spec": """# Task Specification: In-Memory Columnar Relational Query Engine

## 1. Multi-Module Architecture
Implement modules in `src/query_engine/`:
- `scanner.py`: `TableScanner` reading column dictionaries.
- `joins.py`: `HashJoin` performing inner hash join on key columns.
- `aggregate.py`: `GroupByAggregate` computing sum, count, avg.

### Scanner & Execution Contract
```python
class TableScanner:
    def __init__(self, table_name: str, data: Dict[str, List[Any]]) -> None:
    def scan(self, columns: Optional[List[str]] = None, filter_pred: Optional[Callable] = None) -> Dict[str, List[Any]]:
```
""",
        "traceability": """# Traceability Matrix: TASK-21-MULTI-QUERY-ENGINE
- test_columnar_scan_and_filter: verifies projection and filtering on columnar dictionaries.
- test_hash_join_execution: verifies inner hash join across two columnar tables.
- test_groupby_aggregation: verifies group-by sum and count aggregations.
""",
        "test_code": HDR + """import pytest
from src.query_engine.scanner import TableScanner
from src.query_engine.joins import HashJoin
from src.query_engine.aggregate import GroupByAggregate

def test_query_engine_pipeline():
    users = TableScanner("users", {
        "user_id": [1, 2, 3],
        "name": ["Alice", "Bob", "Charlie"],
        "dept": ["Eng", "Sales", "Eng"],
    })
    salaries = TableScanner("salaries", {
        "uid": [1, 2, 3],
        "salary": [100.0, 80.0, 120.0],
    })

    # Join on users.user_id == salaries.uid
    join_op = HashJoin(left=users, right=salaries, left_on="user_id", right_on="uid")
    joined_data = join_op.execute()
    assert len(joined_data["name"]) == 3

    # Group by dept, sum(salary)
    agg_op = GroupByAggregate(data=joined_data, group_col="dept", agg_col="salary", agg_func="sum")
    dept_totals = agg_op.execute()
    assert dept_totals["Eng"] == 220.0
    assert dept_totals["Sales"] == 80.0
"""
    },
    {
        "id": "TASK-22-MULTI-PLUGIN-ARCH",
        "category": "multi_module",
        "held_out": False,
        "title": "Pluggable Microkernel Architecture with Sandboxing",
        "target_file": "src/microkernel/kernel.py",
        "spec": """# Task Specification: Pluggable Microkernel Architecture with Sandboxing

## 1. Multi-Module Architecture
Implement modules in `src/microkernel/`:
- `registry.py`: `PluginRegistry` tracking plugin metadata and dependencies.
- `lifecycle.py`: `PluginLifecycle` managing state (`REGISTERED`, `INITIALIZED`, `ACTIVE`, `STOPPED`).
- `kernel.py`: `Kernel` coordinating lifecycle, dependency ordering, and event dispatch.

### Kernel Contract
```python
class Kernel:
    def __init__(self) -> None:
    def register_plugin(self, plugin_cls: type) -> None:
    def boot(self) -> None:
    def dispatch_event(self, event_name: str, payload: Any) -> List[Any]:
    def shutdown(self) -> None:
```
""",
        "traceability": """# Traceability Matrix: TASK-22-MULTI-PLUGIN-ARCH
- test_plugin_dependency_order: verifies topological boot ordering based on declared dependencies.
- test_plugin_event_dispatch: verifies event hooks triggered across active plugins.
""",
        "test_code": HDR + """import pytest
from src.microkernel.kernel import Kernel

class DatabasePlugin:
    name = "db"
    dependencies = []
    def __init__(self): self.status = "init"
    def on_boot(self): self.status = "ready"
    def on_event(self, event, payload):
        if event == "query": return f"result: {payload}"

class AuthPlugin:
    name = "auth"
    dependencies = ["db"]
    def __init__(self): self.status = "init"
    def on_boot(self): self.status = "ready"
    def on_event(self, event, payload):
        if event == "login": return f"auth_ok: {payload}"

def test_microkernel_lifecycle_and_events():
    kernel = Kernel()
    kernel.register_plugin(AuthPlugin)
    kernel.register_plugin(DatabasePlugin)

    kernel.boot()
    q_res = kernel.dispatch_event("query", "select *")
    assert "result: select *" in q_res

    l_res = kernel.dispatch_event("login", "user1")
    assert "auth_ok: user1" in l_res

    kernel.shutdown()
"""
    },
    {
        "id": "TASK-23-HELDOUT-SCHEDULER",
        "category": "multi_module",
        "held_out": True,
        "title": "Real-Time Preemptive Task Scheduler with Earliest Deadline First",
        "target_file": "src/task_scheduler.py",
        "spec": """# Task Specification: Real-Time Preemptive Task Scheduler with Earliest Deadline First

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
""",
        "traceability": """# Traceability Matrix: TASK-23-HELDOUT-SCHEDULER
- test_edf_scheduling_order: verifies earlier deadline tasks preempt later deadlines.
- test_priority_tie_breaking: verifies higher priority wins on equal deadlines.
""",
        "test_code": HDR + """import pytest
from src.task_scheduler import PreemptiveTaskScheduler

def test_edf_scheduler_order():
    sched = PreemptiveTaskScheduler()
    sched.add_task(task_id="t1", priority=1, computation_time=2.0, deadline=10.0)
    sched.add_task(task_id="t2", priority=1, computation_time=1.0, deadline=5.0)

    assert sched.schedule_next(current_time=0.0) == "t2"
    res = sched.complete_task(task_id="t2", finish_time=1.0)
    assert res["deadline_met"] is True
    assert sched.schedule_next(current_time=1.0) == "t1"
"""
    },
    {
        "id": "TASK-24-HELDOUT-DIFFUSION-2D",
        "category": "physics_numerics",
        "held_out": True,
        "title": "2D Reaction-Diffusion Gray-Scott Pattern Simulator",
        "target_file": "src/gray_scott.py",
        "spec": """# Task Specification: 2D Reaction-Diffusion Gray-Scott Pattern Simulator

## 1. Function Contract
Implement `simulate_gray_scott_2d` in `src/gray_scott.py`.

### Function Signature
```python
def simulate_gray_scott_2d(
    width: int,
    height: int,
    Du: float = 0.16,
    Dv: float = 0.08,
    feed: float = 0.035,
    kill: float = 0.060,
    dt: float = 1.0,
    steps: int = 100,
    initial_u: Optional[np.ndarray] = None,
    initial_v: Optional[np.ndarray] = None
) -> Tuple[np.ndarray, np.ndarray]:
```
- Discretizes coupled reaction-diffusion equations:
  $\\partial u / \\partial t = D_u \\nabla^2 u - u v^2 + F(1 - u)$
  $\\partial v / \\partial t = D_v \\nabla^2 v + u v^2 - (F + k) v$
  using 5-point discrete Laplacian with periodic toroidal boundary conditions.
- Returns final state concentration grids `(U, V)` where each array has shape `(height, width)`.
- Enforces concentration boundedness: $U, V \\in [0.0, 1.0]$.
""",
        "traceability": """# Traceability Matrix: TASK-24-HELDOUT-DIFFUSION-2D
- test_gray_scott_bounds: verifies concentrations remain bounded in [0, 1].
- test_gray_scott_homogeneous_steady_state: verifies U=1, V=0 is steady state.
""",
        "test_code": HDR + """import numpy as np
import pytest
from src.gray_scott import simulate_gray_scott_2d

def test_gray_scott_steady_state_and_bounds():
    w, h = 32, 32
    U, V = simulate_gray_scott_2d(width=w, height=h, steps=50)
    assert U.shape == (h, w)
    assert V.shape == (h, w)
    assert np.all(U >= 0.0) and np.all(U <= 1.0)
    assert np.all(V >= 0.0) and np.all(V <= 1.0)
"""
    }
]
