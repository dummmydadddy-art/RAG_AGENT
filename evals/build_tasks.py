import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "evals" / "tasks"
HIDDEN_DIR = Path("C:/Users/Mukul/.gemini/antigravity/hidden_evals")

TASKS_DIR.mkdir(parents=True, exist_ok=True)
HIDDEN_DIR.mkdir(parents=True, exist_ok=True)

TASKS = [
    {
        "id": "TASK-01-CODE-LRU",
        "category": "pure_coding",
        "held_out": False,
        "title": "Thread-safe LRU Cache with Expiration TTL",
        "description": """Implement `LRUCache(capacity: int, default_ttl_seconds: Optional[float] = None)` in `src/lru_cache.py`.
Methods:
- `put(key: str, value: Any, ttl: Optional[float] = None) -> None`: Stores or updates a key-value pair.
- `get(key: str) -> Optional[Any]`: Returns the value and marks the key as most recently used. Returns None if expired or not found.
- `delete(key: str) -> bool`: Removes key, returns True if existed.
- `__len__() -> int`: Returns current non-expired count.
- Thread-safe using `threading.RLock`.
When capacity is exceeded, evicts the least recently used item.""",
        "target_file": "src/lru_cache.py",
        "test_code": """import time
import threading
from src.lru_cache import LRUCache

def test_lru_eviction():
    cache = LRUCache(capacity=2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    cache.put("c", 3)  # Evicts "b"
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3

def test_ttl_expiration():
    cache = LRUCache(capacity=5, default_ttl_seconds=0.1)
    cache.put("k1", "v1")
    assert cache.get("k1") == "v1"
    time.sleep(0.15)
    assert cache.get("k1") is None

def test_concurrency():
    cache = LRUCache(capacity=100)
    def worker(idx):
        for i in range(50):
            cache.put(f"key_{idx}_{i}", i)
            _ = cache.get(f"key_{idx}_{i}")
    threads = [threading.Thread(target=worker, args=(t,)) for t in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(cache) <= 100
"""
    },
    {
        "id": "TASK-02-CODE-GRAPH",
        "category": "pure_coding",
        "held_out": False,
        "title": "Topological Sorter with Cycle Detection and Dependency Depth",
        "description": """Implement `DependencyGraph` in `src/dependency_graph.py`.
Methods:
- `add_node(name: str) -> None`: Adds a node.
- `add_dependency(node: str, depends_on: str) -> None`: Declares that `node` depends on `depends_on`.
- `topological_sort() -> list[str]`: Returns valid execution order (dependencies before dependents). Raises `CycleError` with detected cycle if cyclic.
- `get_critical_path_depth() -> int`: Returns length of longest dependency chain (number of nodes in critical path). Empty graph returns 0.""",
        "target_file": "src/dependency_graph.py",
        "test_code": """import pytest
from src.dependency_graph import DependencyGraph, CycleError

def test_dag_topological_sort():
    g = DependencyGraph()
    for n in ["A", "B", "C", "D"]: g.add_node(n)
    g.add_dependency("B", "A") # A -> B
    g.add_dependency("C", "B") # B -> C
    g.add_dependency("D", "B") # B -> D
    order = g.topological_sort()
    assert order.index("A") < order.index("B")
    assert order.index("B") < order.index("C")
    assert order.index("B") < order.index("D")
    assert g.get_critical_path_depth() == 3

def test_cycle_detection():
    g = DependencyGraph()
    g.add_dependency("X", "Y")
    g.add_dependency("Y", "Z")
    g.add_dependency("Z", "X")
    with pytest.raises(CycleError):
        g.topological_sort()
"""
    },
    {
        "id": "TASK-03-MATH-ROOTS",
        "category": "maths",
        "held_out": False,
        "title": "High-Precision Halley's Method Root Finder with Bracket Fallback",
        "description": """Implement `find_root(f, df, d2f, x0, tol=1e-12, max_iter=50)` in `src/root_finder.py`.
Uses Halley's iteration formula:
x_{n+1} = x_n - [2 * f(x_n) * f'(x_n)] / [2 * (f'(x_n))^2 - f(x_n) * f''(x_n)]
Returns dataclass `RootResult(root: float, iterations: int, converged: bool, residual: float)`.
Must converge for cubic polynomial x^3 - x - 2 = 0 to within 1e-11 in <= 15 iterations.""",
        "target_file": "src/root_finder.py",
        "test_code": """import math
from src.root_finder import find_root

def test_halley_cubic():
    f = lambda x: x**3 - x - 2.0
    df = lambda x: 3.0*x**2 - 1.0
    d2f = lambda x: 6.0*x
    res = find_root(f, df, d2f, x0=1.5, tol=1e-12)
    assert res.converged is True
    assert abs(res.root - 1.5213797068045376) < 1e-10
    assert abs(f(res.root)) < 1e-11
    assert res.iterations <= 10

def test_halley_transcendental():
    f = lambda x: math.cos(x) - x
    df = lambda x: -math.sin(x) - 1.0
    d2f = lambda x: -math.cos(x)
    res = find_root(f, df, d2f, x0=0.5, tol=1e-12)
    assert res.converged is True
    assert abs(res.root - 0.7390851332151607) < 1e-10
"""
    },
    {
        "id": "TASK-04-MATH-QUATERNION",
        "category": "maths",
        "held_out": True,
        "title": "Quaternion Algebra & 3D Spatial Rotation Matrix",
        "description": """Implement `Quaternion(w: float, x: float, y: float, z: float)` in `src/quaternion.py`.
Methods:
- `__add__`, `__mul__` (Hamilton product: i^2=j^2=k^2=ijk=-1)
- `conjugate() -> Quaternion`
- `norm() -> float` and `normalize() -> Quaternion`
- `to_rotation_matrix() -> list[list[float]]`: 3x3 orthonormal rotation matrix.
- `rotate_vector(v: tuple[float, float, float]) -> tuple[float, float, float]`: Rotates vector v via q * v * q^-1.""",
        "target_file": "src/quaternion.py",
        "test_code": """import math
from src.quaternion import Quaternion

def test_hamilton_product():
    i = Quaternion(0, 1, 0, 0)
    j = Quaternion(0, 0, 1, 0)
    k = Quaternion(0, 0, 0, 1)
    ij = i * j
    assert abs(ij.w) < 1e-9 and abs(ij.z - 1.0) < 1e-9

def test_vector_rotation_90deg():
    angle = math.pi / 2.0
    q = Quaternion(math.cos(angle/2.0), 0, 0, math.sin(angle/2.0))
    v = (1.0, 0.0, 0.0)
    v_rot = q.rotate_vector(v)
    assert abs(v_rot[0]) < 1e-7
    assert abs(v_rot[1] - 1.0) < 1e-7
    assert abs(v_rot[2]) < 1e-7
"""
    },
    {
        "id": "TASK-05-PHYS-KEPLER",
        "category": "physics_numerics",
        "held_out": False,
        "title": "Symplectic Velocity-Verlet Orbital Kepler Integrator",
        "description": """Implement `KeplerOrbitSolver(gm: float, r0: tuple[float, float], v0: tuple[float, float])` in `src/kepler_solver.py`.
Simulates 2-body gravitational dynamics d^2r/dt^2 = -GM r / |r|^3 using symplectic Velocity-Verlet.
Methods:
- `step(dt: float) -> None`: Advances position and velocity by dt.
- `compute_energy() -> float`: Returns specific orbital energy E = 0.5 * |v|^2 - GM / |r|.
- `run(total_time: float, dt: float) -> list[tuple[float, float]]`: Runs simulation and returns list of (x, y) positions.
Conserves energy over 1,000 steps with relative error |(E - E0) / E0| < 1e-4.""",
        "target_file": "src/kepler_solver.py",
        "test_code": """import math
from src.kepler_solver import KeplerOrbitSolver

def test_circular_orbit_energy_conservation():
    gm = 1.0
    r0 = (1.0, 0.0)
    v0 = (0.0, 1.0) # Circular orbit speed = sqrt(gm/r) = 1.0
    solver = KeplerOrbitSolver(gm=gm, r0=r0, v0=v0)
    e0 = solver.compute_energy()
    dt = 0.01
    traj = solver.run(total_time=20.0 * math.pi, dt=dt)
    e_final = solver.compute_energy()
    rel_err = abs((e_final - e0) / e0)
    assert rel_err < 1e-4
    final_pos = traj[-1]
    final_r = math.hypot(final_pos[0], final_pos[1])
    assert abs(final_r - 1.0) < 1e-3
"""
    },
    {
        "id": "TASK-06-PHYS-HEAT1D",
        "category": "physics_numerics",
        "held_out": True,
        "title": "1D Transient Heat Diffusion with Crank-Nicolson Solver",
        "description": """Implement `HeatEquation1D(length: float, alpha: float, nx: int)` in `src/heat_solver.py`.
Solves partial differential equation du/dt = alpha * d^2u/dx^2 on x in [0, length] with zero Dirichlet boundaries.
Uses unconditionally stable Crank-Nicolson implicit finite difference method.
Methods:
- `set_initial_condition(u0: list[float]) -> None`
- `step(dt: float) -> list[float]`: Advances one timestep and returns updated grid values.
- `solve(t_final: float, dt: float) -> list[float]`: Returns solution profile at t_final.""",
        "target_file": "src/heat_solver.py",
        "test_code": """import math
from src.heat_solver import HeatEquation1D

def test_crank_nicolson_diffusion():
    length = 1.0
    alpha = 0.01
    nx = 51
    solver = HeatEquation1D(length=length, alpha=alpha, nx=nx)
    dx = length / (nx - 1)
    u0 = [math.sin(math.pi * i * dx) for i in range(nx)]
    solver.set_initial_condition(u0)
    t_final = 1.0
    dt = 0.05
    u_num = solver.solve(t_final=t_final, dt=dt)
    decay_exact = math.exp(-alpha * (math.pi**2) * t_final)
    u_exact = [decay_exact * math.sin(math.pi * i * dx) for i in range(nx)]
    max_err = max(abs(u_num[i] - u_exact[i]) for i in range(nx))
    assert max_err < 5e-3
"""
    },
    {
        "id": "TASK-07-MULTI-EVENTBUS",
        "category": "multi_module",
        "held_out": False,
        "title": "Asynchronous Event Bus with Middleware & Dead Letter Queue",
        "description": """Implement a modular event system in `src/event_system/`:
- `src/event_system/events.py`: `Event(topic: str, payload: dict, id: Optional[str] = None)`
- `src/event_system/bus.py`: `EventBus` with `subscribe(topic: str, handler: Callable)`, `publish(event: Event)`, and middleware registration `use(middleware)`.
- `src/event_system/dead_letter.py`: `DeadLetterQueue` recording failed events after max retries (default 3 retries).
Middleware can inspect, mutate, or abort event delivery.""",
        "target_file": "src/event_system/bus.py",
        "test_code": """from src.event_system.events import Event
from src.event_system.bus import EventBus
from src.event_system.dead_letter import DeadLetterQueue

def test_event_bus_delivery_and_dlq():
    dlq = DeadLetterQueue(max_retries=2)
    bus = EventBus(dead_letter_queue=dlq)
    received = []
    def success_handler(e): received.append(e.payload['val'])
    def failing_handler(e): raise ValueError("Simulated handler crash")

    bus.subscribe("data.topic", success_handler)
    bus.subscribe("fail.topic", failing_handler)

    bus.publish(Event(topic="data.topic", payload={"val": 42}))
    assert received == [42]

    # Publishing to fail.topic should exceed retries and land in DLQ
    bus.publish(Event(topic="fail.topic", payload={"val": 99}))
    assert len(dlq.get_messages()) == 1
    assert dlq.get_messages()[0].payload['val'] == 99
"""
    },
    {
        "id": "TASK-08-RETRIEVAL-SYMPLECTIC",
        "category": "retrieval_knowledge",
        "held_out": False,
        "title": "Symplectic Stormer-Verlet Integrator citing Knowledge Base",
        "description": """Retrieve formulation from knowledge collection (ID: K-2026-PHYS-001).
Implement `StormerVerletIntegrator(force_fn: Callable[[float], float], dt: float, q0: float, v0: float)` in `src/stormer_verlet.py`.
Methods:
- `step() -> float`: Computes next position q_{n+1} and advances state.
- `get_state() -> tuple[float, float]`: Returns current (q, p).
Must cite `K-2026-PHYS-001` in the class docstring.""",
        "target_file": "src/stormer_verlet.py",
        "test_code": """import math
from src.stormer_verlet import StormerVerletIntegrator

def test_harmonic_oscillator_preservation():
    # Force F(q) = -k*q with k=1.0, m=1.0
    force = lambda q: -q
    dt = 0.05
    q0 = 1.0
    v0 = 0.0
    integrator = StormerVerletIntegrator(force_fn=force, dt=dt, q0=q0, v0=v0)
    for _ in range(200):
        integrator.step()
    q_final, p_final = integrator.get_state()
    # Energy E = 0.5 * p^2 + 0.5 * q^2 ~ 0.5
    energy = 0.5 * (p_final**2 + q_final**2)
    assert abs(energy - 0.5) < 5e-3
    # Check knowledge citation
    assert "K-2026-PHYS-001" in (integrator.__doc__ or "")
"""
    }
]

for task in TASKS:
    t_id = task["id"]
    t_dir = TASKS_DIR / t_id
    t_dir.mkdir(parents=True, exist_ok=True)
    (t_dir / "fixtures").mkdir(parents=True, exist_ok=True)

    # Write task metadata
    meta = {k: v for k, v in task.items() if k != "test_code"}
    (t_dir / "task.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Write README.md
    readme_content = f"# {task['title']}\n\n**Category**: {task['category']}\n**Held Out**: {task['held_out']}\n\n## Specification\n{task['description']}\n"
    (t_dir / "README.md").write_text(readme_content, encoding="utf-8")

    # Write hidden test check OUTSIDE repo
    h_dir = HIDDEN_DIR / t_id
    h_dir.mkdir(parents=True, exist_ok=True)
    (h_dir / "test_hidden.py").write_text(task["test_code"], encoding="utf-8")

print(f"Scaffolded {len(TASKS)} benchmark tasks into evals/tasks/ and hidden checks into {HIDDEN_DIR}")
