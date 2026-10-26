import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evals.crypto_utils import encrypt_evals

TASKS_DIR = ROOT / "evals" / "tasks"
ENCRYPTED_ARCHIVE = ROOT / "evals" / "hidden_evals.enc"
DEFAULT_PASSPHRASE = "antigravity-eval-secret-2026"

CANARY = "CANARY-RAG-AGENT-CHECK-V2-7A8B9C0D-E1F2-3456-7890-ABCDEF123456"

TASKS = [
    {
        "id": "TASK-01-CODE-LRU",
        "category": "pure_coding",
        "held_out": False,
        "title": "Thread-safe LRU Cache with Expiration TTL",
        "target_file": "src/lru_cache.py",
        "spec": """# Task Specification: Thread-safe LRU Cache with Expiration TTL

## 1. Class & Method Contract
Implement `LRUCache` in `src/lru_cache.py`.

### Constructor Signature
```python
def __init__(
    self,
    capacity: int,
    default_ttl_seconds: Optional[float] = None,
    time_fn: Optional[Callable[[], float]] = None
) -> None:
```
- `capacity`: Maximum number of entries stored simultaneously. Must be an integer > 0. If `capacity <= 0` or not an `int`, raise `ValueError("Capacity must be positive")`.
- `default_ttl_seconds`: Optional default time-to-live in seconds. If provided, must be a float or int > 0.0. If `<= 0.0`, raise `ValueError("TTL must be positive")`. Default is `None` (entries do not expire unless overridden).
- `time_fn`: Monotonic clock callable returning current time in float seconds. Defaults to `time.monotonic` if `None`. Allows deterministic testing of time-dependent eviction without sleeping.

### Method Contracts
1. `put(self, key: str, value: Any, ttl: Optional[float] = None) -> None`:
   - `key`: Must be a string. If not an instance of `str`, raise `TypeError("Key must be a string")`.
   - `ttl`: Optional individual TTL in seconds. If `ttl is None`, falls back to `default_ttl_seconds`. If explicitly provided and `<= 0.0`, raise `ValueError("TTL must be positive")`.
   - Expiration calculation: If effective TTL is positive, expiration timestamp is `current_time + effective_ttl`; otherwise `None` (no expiration).
   - Key update vs insertion:
     - If `key` is already present (even if expired): updates value, updates expiration timestamp, and updates access order (marks as most recently used). Does not evict any other key.
     - If `key` is new:
       - First, purges all expired keys from internal storage.
       - Next, if `len(self) >= capacity`: evicts the least recently used (LRU) non-expired key.
       - Inserts the new key with its expiration timestamp and marks as most recently used (MRU).

2. `get(self, key: str) -> Optional[Any]`:
   - `key`: Must be a string. If not an instance of `str`, raise `TypeError("Key must be a string")`.
   - If `key` does not exist or has expired (`current_time >= expiration_time`), removes the expired key if present and returns `None`.
   - If `key` exists and has not expired, updates its access order (marks as most recently used) and returns `value`.

3. `delete(self, key: str) -> bool`:
   - `key`: Must be a string. If not an instance of `str`, raise `TypeError("Key must be a string")`.
   - If `key` exists and has not expired: removes `key` from cache and returns `True`.
   - If `key` does not exist or has already expired: removes expired key if present and returns `False`.

4. `clear(self) -> None`:
   - Removes all stored keys and values from the cache.

5. `__len__(self) -> int`:
   - Returns the current number of non-expired keys stored in the cache. Calling `__len__` is non-mutating and does not alter the LRU access order.

6. `__contains__(self, key: str) -> bool`:
   - `key`: Must be a string. If not an instance of `str`, raise `TypeError("Key must be a string")`.
   - Returns `True` if `key` is present and unexpired, `False` otherwise.
   - Checking containment MUST NOT alter the LRU access order.

## 2. Concurrency & Invariants
- All public methods must be thread-safe under concurrent multi-threaded execution using `threading.RLock()`.
""",
        "traceability": """# Traceability Matrix: TASK-01-CODE-LRU

| Test Assertion | Spec Sentence Justification |
|---|---|
| `assert LRUCache(capacity=0)` raises `ValueError` | "If capacity <= 0 or not an int, raise ValueError(\\"Capacity must be positive\\")" |
| `assert LRUCache(capacity=2, default_ttl_seconds=-1)` raises `ValueError` | "If <= 0.0, raise ValueError(\\"TTL must be positive\\")" |
| `cache.put("a", 1); cache.put("b", 2); cache.get("a"); cache.put("c", 3); assert cache.get("b") is None` | "evicts the least recently used (LRU) non-expired key" and "updates its access order (marks as most recently used)" |
| `clock.advance(10.0); assert cache.get("k") is None` | "If key does not exist or has expired (current_time >= expiration_time), removes the expired key if present and returns None." |
| `assert len(cache) == 0` after expiration | "Returns the current number of non-expired keys stored in the cache." |
| `cache.put(123, "val")` raises `TypeError` | "key: Must be a string. If not an instance of str, raise TypeError(\\"Key must be a string\\")" |
| `cache.get(123)` raises `TypeError` | "key: Must be a string. If not an instance of str, raise TypeError(\\"Key must be a string\\")" |
| `assert cache.delete("nonexistent") is False` | "If key does not exist or has already expired: removes expired key if present and returns False." |
| `assert "a" in cache` without updating LRU | "Checking containment MUST NOT alter the LRU access order." |
| Overwriting existing key does not evict other keys | "If key is already present (even if expired): updates value... Does not evict any other key." |
| 10 threads concurrently put and get 100 keys; `assert len(cache) <= capacity` | "All public methods must be thread-safe under concurrent multi-threaded execution using threading.RLock()." |
""",
        "test_code": f"""# CANARY: {CANARY}
import threading
from typing import Any
import pytest
from src.lru_cache import LRUCache


class MockClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.current = start

    def __call__(self) -> float:
        return self.current

    def advance(self, delta: float) -> None:
        self.current += delta


def test_capacity_validation():
    with pytest.raises(ValueError, match="Capacity must be positive"):
        LRUCache(capacity=0)
    with pytest.raises(ValueError, match="Capacity must be positive"):
        LRUCache(capacity=-5)


def test_ttl_validation():
    with pytest.raises(ValueError, match="TTL must be positive"):
        LRUCache(capacity=5, default_ttl_seconds=0.0)
    with pytest.raises(ValueError, match="TTL must be positive"):
        LRUCache(capacity=5, default_ttl_seconds=-1.5)


def test_lru_eviction_and_access_order():
    clock = MockClock()
    cache = LRUCache(capacity=2, time_fn=clock)
    cache.put("k1", "v1")
    cache.put("k2", "v2")
    assert cache.get("k1") == "v1"  # k1 is now MRU, k2 is LRU
    cache.put("k3", "v3")  # Evicts k2
    assert cache.get("k2") is None
    assert cache.get("k1") == "v1"
    assert cache.get("k3") == "v3"


def test_ttl_expiration_with_mock_clock():
    clock = MockClock()
    cache = LRUCache(capacity=5, default_ttl_seconds=10.0, time_fn=clock)
    cache.put("k1", "v1")
    cache.put("k2", "v2", ttl=2.0)  # Overridden TTL

    assert cache.get("k1") == "v1"
    assert cache.get("k2") == "v2"
    assert len(cache) == 2

    # Advance clock by 5s: k2 expired, k1 valid
    clock.advance(5.0)
    assert cache.get("k2") is None
    assert cache.get("k1") == "v1"
    assert len(cache) == 1

    # Advance clock by 6s: k1 expired
    clock.advance(6.0)
    assert cache.get("k1") is None
    assert len(cache) == 0


def test_type_error_on_non_string_key():
    cache = LRUCache(capacity=5)
    with pytest.raises(TypeError, match="Key must be a string"):
        cache.put(12345, "value")
    with pytest.raises(TypeError, match="Key must be a string"):
        cache.get(12345)
    with pytest.raises(TypeError, match="Key must be a string"):
        cache.delete(12345)
    with pytest.raises(TypeError, match="Key must be a string"):
        _ = 12345 in cache


def test_contains_does_not_alter_lru():
    clock = MockClock()
    cache = LRUCache(capacity=2, time_fn=clock)
    cache.put("k1", "v1")
    cache.put("k2", "v2")

    assert "k1" in cache  # Inquiry should NOT make k1 MRU
    cache.put("k3", "v3")  # Should evict k1 (since k2 was most recently put)
    assert cache.get("k1") is None
    assert cache.get("k2") == "v2"
    assert cache.get("k3") == "v3"


def test_overwrite_existing_key_does_not_evict():
    clock = MockClock()
    cache = LRUCache(capacity=2, time_fn=clock)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("a", 10)  # Overwrite 'a'
    assert cache.get("a") == 10
    assert cache.get("b") == 2
    assert len(cache) == 2


def test_delete_and_clear():
    cache = LRUCache(capacity=5)
    cache.put("a", 1)
    assert cache.delete("a") is True
    assert cache.delete("a") is False
    assert len(cache) == 0

    cache.put("b", 2)
    cache.put("c", 3)
    cache.clear()
    assert len(cache) == 0
    assert cache.get("b") is None


def test_multithreaded_concurrency():
    cache = LRUCache(capacity=50)

    def worker(worker_id: int):
        for i in range(100):
            k = f"key_{{worker_id}}_{{i % 25}}"
            cache.put(k, i)
            _ = cache.get(k)
            _ = len(cache)

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(cache) <= 50
"""
    },
    {
        "id": "TASK-02-CODE-GRAPH",
        "category": "pure_coding",
        "held_out": False,
        "title": "Topological Sorter with Cycle Detection",
        "target_file": "src/dependency_graph.py",
        "spec": """# Task Specification: Topological Sorter with Cycle Detection

## 1. Class & Method Contract
Implement `CycleError` and `DependencyGraph` in `src/dependency_graph.py`.

### Exception Contract
```python
class CycleError(Exception):
    \"\"\"Raised when a dependency cycle is detected in the graph.\"\"\"
    pass
```

### Class Signature
```python
class DependencyGraph:
    def __init__(self) -> None:
        \"\"\"Initializes an empty directed dependency graph.\"\"\"
```

### Method Contracts
1. `add_node(self, node: str, weight: float = 1.0) -> None`:
   - Adds a node with a non-negative execution duration `weight` (default 1.0).
   - `node` must be a non-empty string. If not or empty, raise `ValueError("Node must be a non-empty string")`.
   - If `node` already exists, updates its weight to the newly provided value.
   - If `weight < 0.0`, raise `ValueError("Weight must be non-negative")`.

2. `add_dependency(self, dependent: str, dependency: str) -> None`:
   - Adds a directed edge where `dependent` depends on `dependency` (edge: `dependency -> dependent`).
   - Both `dependent` and `dependency` must be non-empty strings; otherwise raise `ValueError("Node must be a non-empty string")`.
   - Implicitly registers `dependent` or `dependency` with default weight 1.0 if not previously added.
   - If `dependent == dependency`, immediately raise `CycleError("Self-dependency detected")`.
   - Multi-edges are idempotent: adding an existing edge again has no additional effect.

3. `topological_sort(self) -> list[str]`:
   - Returns a valid linear ordering of all nodes such that for every directed dependency `u -> v`, `u` appears before `v`.
   - **Deterministic Tie-Breaking**: When multiple nodes have zero remaining in-degrees, sort them in lexicographical ascending order (e.g. `["A", "B"]`).
   - If the graph contains any directed cycle, raise `CycleError("Graph contains a cycle")`.
   - Returns empty list `[]` for an empty graph.

4. `critical_path_depth(self) -> float`:
   - Returns the maximum cumulative weight along any directed path through the graph (`dependency -> dependent`).
   - Path weight includes the weights of all nodes in the path (source through target inclusive).
   - An isolated single node `u` with weight `W` is a valid path with cumulative weight `W`.
   - For an empty graph, returns `0.0`. Returns the maximum cumulative weight across all connected components.
   - If the graph contains a directed cycle, raise `CycleError("Graph contains a cycle")`.

5. `detect_cycles(self) -> list[list[str]]`:
   - Returns a list of elementary directed cycles.
   - Each cycle is represented as a list of node names tracing the loop from start back to start (e.g. `["A", "B", "A"]`).
   - Canonical normalization: each cycle is cyclically rotated so that its lexicographically smallest node appears at index 0 (and at the end).
   - The outer list of cycles is sorted lexicographically by the first node (and subsequent nodes).
   - If the graph is acyclic (a DAG), returns empty list `[]`.
""",
        "traceability": """# Traceability Matrix: TASK-02-CODE-GRAPH

| Test Assertion | Spec Sentence Justification |
|---|---|
| `assert graph.add_node("A", weight=-2)` raises `ValueError` | "If weight < 0.0, raise ValueError(\\"Weight must be non-negative\\")" |
| `assert graph.add_dependency("A", "A")` raises `CycleError` | "If dependent == dependency, immediately raise CycleError(\\"Self-dependency detected\\")" |
| Diamond DAG `A->B, A->C, B->D, C->D` topological sort order | "Returns a valid linear ordering of all nodes such that for every directed dependency u -> v, u appears before v." |
| Tie-breaking: `assert graph.topological_sort() == ["A", "B", "C"]` | "When multiple nodes have zero remaining in-degrees, sort them in lexicographical ascending order" |
| Cyclic graph `A->B->C->A` raises `CycleError` in sort | "If the graph contains any directed cycle, raise CycleError(\\"Graph contains a cycle\\")." |
| Critical path `A(2)->B(3)->D(1)` equals `6.0` | "Returns the maximum cumulative weight along any directed path through the graph" |
| Empty graph returns `[]` and `0.0` | "Returns empty list [] for an empty graph." and "For an empty graph, returns 0.0." |
| Isolated single node critical path equals node weight | "An isolated single node u with weight W is a valid path with cumulative weight W." |
| `detect_cycles()` returns `[["A", "B", "A"]]` with canonical normalization | "Each cycle is represented as a list of node names tracing the loop from start back to start... cyclically rotated so that its lexicographically smallest node appears at index 0" |
""",
        "test_code": f"""# CANARY: {CANARY}
import pytest
from src.dependency_graph import DependencyGraph, CycleError


def test_weight_validation():
    g = DependencyGraph()
    with pytest.raises(ValueError, match="Weight must be non-negative"):
        g.add_node("A", weight=-0.5)


def test_self_dependency_raises_cycle_error():
    g = DependencyGraph()
    with pytest.raises(CycleError, match="Self-dependency"):
        g.add_dependency("A", "A")


def test_topological_sort_diamond_dag():
    g = DependencyGraph()
    g.add_dependency("B", "A")  # A -> B
    g.add_dependency("C", "A")  # A -> C
    g.add_dependency("D", "B")  # B -> D
    g.add_dependency("D", "C")  # C -> D

    order = g.topological_sort()
    assert order.index("A") < order.index("B")
    assert order.index("A") < order.index("C")
    assert order.index("B") < order.index("D")
    assert order.index("C") < order.index("D")


def test_deterministic_lexicographical_tie_breaking():
    g = DependencyGraph()
    g.add_node("Z")
    g.add_node("A")
    g.add_node("M")
    assert g.topological_sort() == ["A", "M", "Z"]


def test_topological_sort_cycle_error():
    g = DependencyGraph()
    g.add_dependency("B", "A")
    g.add_dependency("C", "B")
    g.add_dependency("A", "C")
    with pytest.raises(CycleError, match="cycle"):
        g.topological_sort()


def test_critical_path_depth():
    g = DependencyGraph()
    g.add_node("A", 2.0)
    g.add_node("B", 3.0)
    g.add_node("C", 1.5)
    g.add_node("D", 4.0)

    g.add_dependency("B", "A")  # A(2) -> B(3)
    g.add_dependency("C", "A")  # A(2) -> C(1.5)
    g.add_dependency("D", "B")  # B(3) -> D(4) = path A->B->D total 9.0
    g.add_dependency("D", "C")  # C(1.5) -> D(4) = path A->C->D total 7.5

    assert abs(g.critical_path_depth() - 9.0) < 1e-9


def test_isolated_node_critical_path():
    g = DependencyGraph()
    g.add_node("X", 7.5)
    assert abs(g.critical_path_depth() - 7.5) < 1e-9


def test_empty_graph():
    g = DependencyGraph()
    assert g.topological_sort() == []
    assert g.critical_path_depth() == 0.0
    assert g.detect_cycles() == []


def test_detect_cycles():
    g = DependencyGraph()
    g.add_dependency("B", "A")
    g.add_dependency("A", "B")

    cycles = g.detect_cycles()
    assert len(cycles) == 1
    assert cycles[0] == ["A", "B", "A"]
"""
    },
    {
        "id": "TASK-03-MATH-HALLEY",
        "category": "pure_maths",
        "held_out": False,
        "title": "Halley's Root Finder with Bracket Fallback",
        "target_file": "src/root_finder.py",
        "spec": """# Task Specification: Halley's Root Finder with Bracket Fallback

## 1. Function Contract
Implement `find_root_halley` in `src/root_finder.py`.

### Function Signature
```python
def find_root_halley(
    f: Callable[[float], float],
    df: Callable[[float], float],
    d2f: Callable[[float], float],
    x0: float,
    tol: float = 1e-10,
    max_iter: int = 50,
    bracket: Optional[tuple[float, float]] = None
) -> dict[str, Any]:
```

### Parameter Validations
- `tol`: Float > 0.0. If `tol <= 0.0`, raise `ValueError("tol must be positive")`.
- `max_iter`: Integer >= 1. If `max_iter < 1`, raise `ValueError("max_iter must be >= 1")`.
- `bracket`: Optional tuple of two floats `(a, b)`. If provided:
  - Must satisfy `a < b`. If not, raise `ValueError("Invalid bracket: a must be strictly less than b")`.
  - Initial guess `x0` must lie within `[a, b]`. If `x0 < a` or `x0 > b`, raise `ValueError("Initial guess x0 must lie within bracket [a, b]")`.
  - Initial sign condition: `f(a) * f(b)` must be `<= 0.0`. If `f(a) * f(b) > 0`, raise `ValueError("Bracket endpoints must have opposite signs")`.
  - If `f(a) == 0.0`, return immediately: `{"root": a, "iterations": 0, "converged": True, "f_val": 0.0}`.
  - If `f(b) == 0.0`, return immediately: `{"root": b, "iterations": 0, "converged": True, "f_val": 0.0}`.

### Zero-Iteration Check
- Before starting iterations, if `abs(f(x0)) < tol`, return immediately:
  `{"root": x0, "iterations": 0, "converged": True, "f_val": f(x0)}`.

### Numerical Algorithm & Iteration
At iteration `n` (starting at `n = 0` with `x_n = x0`):
1. Compute function and derivatives: $f_n = f(x_n)$, $df_n = df(x_n)$, $d2f_n = d2f(x_n)$.
2. Compute the Halley denominator:
   $$D_n = 2 (df_n)^2 - f_n \cdot d2f_n$$
3. Candidate Halley step:
   $$x_{cand} = x_n - \frac{2 f_n \cdot df_n}{D_n}$$
4. Safeguarding & Fallback Logic:
   - **If `bracket = (a, b)` was provided**:
     - Maintain and update the active bracket $(a, b)$ based on the sign of $f(x_n)$: if $f(a) \cdot f(x_n) \le 0$, new bracket is $(a, x_n)$; else $(x_n, b)$.
     - If $|D_n| < 10^{-15}$ OR $x_{cand} \le a$ OR $x_{cand} \ge b$:
       Execute a bisection fallback step:
       $$x_{next} = \frac{a + b}{2.0}$$
     - Else:
       $$x_{next} = x_{cand}$$
   - **If `bracket is None`**:
     - If $|D_n| < 10^{-15}$, raise `ZeroDivisionError("Halley denominator vanished and no bracket supplied for bisection fallback")`.
     - Else:
       $$x_{next} = x_{cand}$$
5. Convergence Check:
   - If $|f(x_{next})| < tol$ OR $|x_{next} - x_n| < tol$:
     Return `{"root": x_{next}, "iterations": n + 1, "converged": True, "f_val": f(x_{next})}`.
   - Set $x_{n+1} = x_{next}$.
6. If loop reaches `max_iter` iterations without converging, return:
   `{"root": x_{last}, "iterations": max_iter, "converged": False, "f_val": f(x_{last})}`.
""",
        "traceability": """# Traceability Matrix: TASK-03-MATH-HALLEY

| Test Assertion | Spec Sentence Justification |
|---|---|
| `assert find_root_halley(..., tol=0.0)` raises `ValueError` | "If tol <= 0.0, raise ValueError(\\"tol must be positive\\")" |
| `assert find_root_halley(..., bracket=(2, 1))` raises `ValueError` | "Must satisfy a < b. If not, raise ValueError(\\"Invalid bracket: a must be strictly less than b\\")" |
| `assert find_root_halley(..., bracket=(0, 2), x0=5.0)` raises `ValueError` | "Initial guess x0 must lie within [a, b]. If x0 < a or x0 > b, raise ValueError(\\"Initial guess x0 must lie within bracket [a, b]\\")" |
| `assert find_root_halley(..., bracket=(1, 3))` on $f(x)=x^2+1$ raises `ValueError` | "If f(a) * f(b) > 0, raise ValueError(\\"Bracket endpoints must have opposite signs\\")" |
| Smooth cubic root found in $\le 5$ iterations | "Candidate Halley step: $x_{cand} = x_n - 2 f df / D_n$" (cubic convergence rate) |
| Halley denominator vanishing with bracket triggers bisection step | "If |D_n| < 1e-15 or x_cand outside (a, b): Execute a bisection fallback step: x_next = (a + b) / 2.0" |
| Halley denominator vanishing without bracket raises `ZeroDivisionError` | "If |D_n| < 1e-15, raise ZeroDivisionError(\\"Halley denominator vanished and no bracket supplied for bisection fallback\\")" |
| Initial root hit $f(x0) == 0$ returns 0 iterations | "Before starting iterations, if abs(f(x0)) < tol, return immediately: iterations: 0" |
""",
        "test_code": f"""# CANARY: {CANARY}
import math
import pytest
from src.root_finder import find_root_halley


def test_halley_validation():
    f = lambda x: x**2 - 2
    df = lambda x: 2 * x
    d2f = lambda x: 2.0

    with pytest.raises(ValueError, match="tol must be positive"):
        find_root_halley(f, df, d2f, 1.0, tol=-1e-5)

    with pytest.raises(ValueError, match="strictly less than b"):
        find_root_halley(f, df, d2f, 1.0, bracket=(2.0, 1.0))

    with pytest.raises(ValueError, match="must lie within bracket"):
        find_root_halley(f, df, d2f, 5.0, bracket=(0.0, 2.0))

    with pytest.raises(ValueError, match="opposite signs"):
        find_root_halley(f, df, d2f, 3.0, bracket=(2.0, 4.0))  # f(2)=2, f(4)=14 both positive


def test_halley_cubic_convergence_sqrt2():
    f = lambda x: x**2 - 2.0
    df = lambda x: 2.0 * x
    d2f = lambda x: 2.0

    res = find_root_halley(f, df, d2f, x0=1.5, tol=1e-12, max_iter=20)
    assert res["converged"] is True
    assert abs(res["root"] - math.sqrt(2.0)) < 1e-12
    assert res["iterations"] <= 4  # Cubic convergence achieves 1e-12 in <= 4 steps


def test_bracket_bisection_fallback_on_zero_derivative():
    # Function with extremum / vanishing denominator: f(x) = x^3 - x - 2
    f = lambda x: x**3 - x - 2.0
    df = lambda x: 3.0 * x**2 - 1.0
    d2f = lambda x: 6.0 * x

    # With bracket [1.0, 2.0] where f(1)=-2, f(2)=4
    res = find_root_halley(f, df, d2f, x0=1.0 / math.sqrt(3.0), bracket=(1.0, 2.0), tol=1e-10)
    assert res["converged"] is True
    assert abs(f(res["root"])) < 1e-9


def test_vanishing_denominator_without_bracket_raises():
    # If D vanishes and no bracket supplied:
    f = lambda x: 1.0
    df = lambda x: 0.0
    d2f = lambda x: 0.0
    with pytest.raises(ZeroDivisionError):
        find_root_halley(f, df, d2f, x0=1.0, bracket=None)


def test_zero_iteration_root_hit():
    f = lambda x: x - 3.0
    df = lambda x: 1.0
    d2f = lambda x: 0.0
    res = find_root_halley(f, df, d2f, x0=3.0, tol=1e-8)
    assert res["iterations"] == 0
    assert res["converged"] is True
    assert res["root"] == 3.0
"""
    },
    {
        "id": "TASK-04-MATH-QUATERNION",
        "category": "pure_maths",
        "held_out": False,
        "title": "3D Rotation Quaternion with SLERP",
        "target_file": "src/quaternion.py",
        "spec": """# Task Specification: 3D Rotation Quaternion with SLERP

## 1. Class & Method Contract
Implement `Quaternion` in `src/quaternion.py`.

### Constructor Signature
```python
def __init__(self, w: float, x: float, y: float, z: float) -> None:
```
Accepts float or int components, converted and stored internally as floats.

### Alternative Constructors
- `@classmethod from_axis_angle(cls, axis: tuple[float, float, float], angle_rad: float) -> "Quaternion"`:
  - If axis vector norm $\sqrt{a_x^2 + a_y^2 + a_z^2} < 10^{-15}$, raise `ValueError("Axis vector cannot have zero length")`.
  - Normalizes `axis` to unit vector $\mathbf{u} = \mathbf{axis} / \|\mathbf{axis}\|$.
  - Constructs unit quaternion:
    $$q = \left(\cos\left(\frac{\theta}{2}\right), u_x \sin\left(\frac{\theta}{2}\right), u_y \sin\left(\frac{\theta}{2}\right), u_z \sin\left(\frac{\theta}{2}\right)\right)$$

### Properties & Unary Methods
1. `norm(self) -> float`: Returns Euclidean magnitude $\sqrt{w^2 + x^2 + y^2 + z^2}$.
2. `conjugate(self) -> "Quaternion"`: Returns $(w, -x, -y, -z)$.
3. `inverse(self) -> "Quaternion"`:
   - If `norm() < 1e-15`, raise `ZeroDivisionError("Cannot invert zero-norm quaternion")`.
   - Returns `self.conjugate() / (self.norm() ** 2)`.
4. `normalize(self) -> "Quaternion"`:
   - If `norm() < 1e-15`, raise `ZeroDivisionError("Cannot normalize zero-norm quaternion")`.
   - Returns `self / self.norm()`.

### Arithmetic Operators
1. `__add__(self, other: "Quaternion") -> "Quaternion"`: Component-wise addition.
2. `__sub__(self, other: "Quaternion") -> "Quaternion"`: Component-wise subtraction.
3. `__mul__(self, other: Union["Quaternion", float, int]) -> "Quaternion"`:
   - If `other` is `Quaternion`: Hamilton quaternion product.
   - If `other` is `float` or `int`: Scalar multiplication $(s \cdot w, s \cdot x, s \cdot y, s \cdot z)$.
   - Otherwise, returns `NotImplemented`.
4. `__rmul__(self, scalar: Union[float, int]) -> "Quaternion"`:
   - Scalar multiplication on left ($s \cdot q$). Returns `NotImplemented` if `scalar` is not `float` or `int`.
5. `__truediv__(self, scalar: Union[float, int]) -> "Quaternion"`:
   - Component-wise division by scalar. If $|scalar| < 10^{-15}$, raise `ZeroDivisionError("Division by zero")`.
6. `__eq__(self, other: Any) -> bool`:
   - Returns `True` if `other` is a `Quaternion` and all corresponding components agree within absolute tolerance $10^{-9}$.

### Geometry & Rotation Methods
1. `to_rotation_matrix(self) -> list[list[float]]`:
   - Normalizes `self` to unit quaternion $\hat{q} = (w, x, y, z)$. If `norm() < 1e-15`, raise `ZeroDivisionError("Cannot normalize zero-norm quaternion")`.
   - Returns standard $3 \times 3$ rotation matrix as a nested list of floats:
     $$R = \\begin{bmatrix} 1 - 2(y^2 + z^2) & 2(xy - wz) & 2(xz + wy) \\\\ 2(xy + wz) & 1 - 2(x^2 + z^2) & 2(yz - wx) \\\\ 2(xz - wy) & 2(yz + wx) & 1 - 2(x^2 + y^2) \\end{bmatrix}$$
2. `rotate_vector(self, v: tuple[float, float, float]) -> tuple[float, float, float]`:
   - Normalizes `self` to $\hat{q}$. If `norm() < 1e-15`, raise `ZeroDivisionError("Cannot normalize zero-norm quaternion")`.
   - Computes $q_{rot} = \hat{q} \cdot (0, v_x, v_y, v_z) \cdot \hat{q}^{-1}$.
   - Returns rotated 3D tuple $(x', y', z')$.
3. `@staticmethod slerp(q1: "Quaternion", q2: "Quaternion", t: float) -> "Quaternion"`:
   - Spherical linear interpolation between two quaternions for parameter $t \in [0.0, 1.0]$.
   - Normalizes inputs $q_1$ and $q_2$.
   - Computes dot product $\cos(\Omega) = w_1 w_2 + x_1 x_2 + y_1 y_2 + z_1 z_2$.
   - If $\cos(\Omega) < 0.0$, inverts $q_2 \leftarrow -q_2$ and $\cos(\Omega) \leftarrow -\cos(\Omega)$ to take the shortest arc.
   - If $\cos(\Omega) > 0.9995$ (nearly collinear), falls back to normalized linear interpolation (NLERP): $\text{normalize}((1 - t) q_1 + t q_2)$.
   - Otherwise, computes standard SLERP:
     $$\frac{\sin((1 - t)\Omega)}{\sin(\Omega)} q_1 + \frac{\sin(t \Omega)}{\sin(\Omega)} q_2$$
""",
        "traceability": """# Traceability Matrix: TASK-04-MATH-QUATERNION

| Test Assertion | Spec Sentence Justification |
|---|---|
| `Quaternion.from_axis_angle((0, 0, 0), 1.0)` raises `ValueError` | "If axis vector norm < 1e-15, raise ValueError(\\"Axis vector cannot have zero length\\")" |
| `Quaternion(0, 0, 0, 0).inverse()` raises `ZeroDivisionError` | "If norm() < 1e-15, raise ZeroDivisionError(\\"Cannot invert zero-norm quaternion\\")" |
| Quaternion Hamilton multiplication non-commutativity ($i \cdot j = k$, $j \cdot i = -k$) | "Hamilton quaternion product." |
| Scalar left and right multiplication `2.0 * q == q * 2.0` | "Scalar multiplication on left... Scalar multiplication (s*w, s*x, s*y, s*z)" |
| 90 degree Z-axis rotation matrix transforms $(1, 0, 0)$ to $(0, 1, 0)$ | "to_rotation_matrix... Returns standard 3x3 rotation matrix" |
| `rotate_vector` transforms $(1, 0, 0)$ to $(0, 1, 0)$ under 90 deg Z rotation | "rotate_vector... Computes q_rot = q_unit * (0, v) * q_unit^-1" |
| SLERP at $t=0.0$ returns $q_1$; at $t=1.0$ returns $q_2$; at $t=0.5$ bisects angle | "Spherical linear interpolation between two quaternions for parameter t in [0.0, 1.0]" |
| SLERP with opposite polarity takes shortest arc | "If cos(Omega) < 0.0, inverts q2 <- -q2 and cos(Omega) <- -cos(Omega) to take the shortest arc." |
""",
        "test_code": f"""# CANARY: {CANARY}
import math
import pytest
from src.quaternion import Quaternion


def test_axis_angle_validation():
    with pytest.raises(ValueError, match="zero length"):
        Quaternion.from_axis_angle((0.0, 0.0, 0.0), math.pi / 2)


def test_zero_norm_inverse():
    q = Quaternion(0.0, 0.0, 0.0, 0.0)
    with pytest.raises(ZeroDivisionError):
        q.inverse()


def test_hamilton_product():
    # i = (0, 1, 0, 0), j = (0, 0, 1, 0), k = (0, 0, 0, 1)
    i = Quaternion(0, 1, 0, 0)
    j = Quaternion(0, 0, 1, 0)
    k = Quaternion(0, 0, 0, 1)

    ij = i * j
    ji = j * i
    assert ij == k
    assert ji == Quaternion(0, 0, 0, -1)


def test_scalar_multiplication():
    q = Quaternion(1.0, 2.0, 3.0, 4.0)
    assert q * 2.0 == Quaternion(2.0, 4.0, 6.0, 8.0)
    assert 2.0 * q == Quaternion(2.0, 4.0, 6.0, 8.0)


def test_vector_rotation_90_deg_z():
    q = Quaternion.from_axis_angle((0.0, 0.0, 1.0), math.pi / 2)
    v_rot = q.rotate_vector((1.0, 0.0, 0.0))
    assert abs(v_rot[0] - 0.0) < 1e-9
    assert abs(v_rot[1] - 1.0) < 1e-9
    assert abs(v_rot[2] - 0.0) < 1e-9


def test_rotation_matrix_orthonormality():
    q = Quaternion.from_axis_angle((1.0, 1.0, 1.0), 1.2)
    R = q.to_rotation_matrix()
    # Check R * R^T = I
    for r in range(3):
        for c in range(3):
            dot = sum(R[r][k] * R[c][k] for k in range(3))
            expected = 1.0 if r == c else 0.0
            assert abs(dot - expected) < 1e-7


def test_slerp_interpolation():
    q1 = Quaternion(1.0, 0.0, 0.0, 0.0)
    q2 = Quaternion.from_axis_angle((0.0, 1.0, 0.0), math.pi / 2)

    mid = Quaternion.slerp(q1, q2, 0.5)
    expected_mid = Quaternion.from_axis_angle((0.0, 1.0, 0.0), math.pi / 4)
    assert mid == expected_mid
"""
    },
    {
        "id": "TASK-05-PHYS-KEPLER",
        "category": "physics_numerics",
        "held_out": False,
        "title": "2D Kepler Orbit Symplectic Integrator",
        "target_file": "src/kepler_solver.py",
        "spec": """# Task Specification: 2D Kepler Orbit Symplectic Integrator

## 1. Function Contract
Implement `solve_kepler_orbit` in `src/kepler_solver.py`.

### Function Signature
```python
def solve_kepler_orbit(
    r0: tuple[float, float],
    v0: tuple[float, float],
    gm: float,
    dt: float,
    steps: int
) -> dict[str, Any]:
```

### Parameter Validations
- `r0`: 2D initial position tuple `(x0, y0)`. Must be a tuple/list of length 2. If not, raise `ValueError("Initial conditions must be 2D vectors")`.
- `v0`: 2D initial velocity tuple `(vx0, vy0)`. Must be a tuple/list of length 2. If not, raise `ValueError("Initial conditions must be 2D vectors")`.
- Initial radius magnitude $\|r_0\| = \sqrt{x_0^2 + y_0^2}$: If $\|r_0\| < 10^{-12}$, raise `ValueError("Initial radius cannot be zero")`.
- `gm`: Standard gravitational parameter $G \cdot M$. Must be a float > 0.0. If `gm <= 0.0`, raise `ValueError("GM parameter must be positive")`.
- `dt`: Simulation timestep in seconds. Must be a float > 0.0. If `dt <= 0.0`, raise `ValueError("Time step dt must be positive")`.
- `steps`: Total integration steps. Must be an integer >= 1. If `steps < 1`, raise `ValueError("Steps must be at least 1")`.

### Symplectic Integration Scheme
The solver must integrate the Newtonian 2D two-body gravitational dynamics:
$$\mathbf{a}(\mathbf{r}) = -\frac{GM}{\|\mathbf{r}\|^3} \mathbf{r}$$
using the **Velocity Verlet (symplectic)** numerical integration scheme:
1. $\mathbf{a}_n = \mathbf{a}(\mathbf{r}_n)$
2. $\mathbf{r}_{n+1} = \mathbf{r}_n + \mathbf{v}_n dt + \frac{1}{2} \mathbf{a}_n dt^2$
3. $\mathbf{a}_{n+1} = \mathbf{a}(\mathbf{r}_{n+1})$
4. $\mathbf{v}_{n+1} = \mathbf{v}_n + \frac{1}{2} (\mathbf{a}_n + \mathbf{a}_{n+1}) dt$

### Physical Invariants & Diagnostics
At every step $n \in \{0, 1, \dots, steps\}$:
1. **Specific Mechanical Energy**:
   $$E_n = \frac{1}{2} \|\mathbf{v}_n\|^2 - \frac{GM}{\|\mathbf{r}_n\|}$$
2. **Specific Angular Momentum** (z-component):
   $$L_{z, n} = x_n v_{y, n} - y_n v_{x, n}$$
3. For bound Keplerian orbits, the relative variations $\frac{|E_n - E_0|}{|E_0|}$ and $\frac{|L_{z, n} - L_{z, 0}|}{|L_{z, 0}|}$ must remain bounded within $10^{-4}$ over 10 complete orbits.

### Return Dictionary Specification
Returns a dictionary containing exactly:
- `"position"`: `list[tuple[float, float]]` of length `steps + 1`.
- `"velocity"`: `list[tuple[float, float]]` of length `steps + 1`.
- `"energy"`: `list[float]` of length `steps + 1`.
- `"angular_momentum"`: `list[float]` of length `steps + 1`.
- `"time"`: `list[float]` of length `steps + 1` where $t_n = n \cdot dt$.
""",
        "traceability": """# Traceability Matrix: TASK-05-PHYS-KEPLER

| Test Assertion | Spec Sentence Justification |
|---|---|
| `assert solve_kepler_orbit((0, 0), (1, 0), gm=1.0, dt=0.01, steps=10)` raises `ValueError` | "If ||r0|| < 1e-12, raise ValueError(\\"Initial radius cannot be zero\\")" |
| `assert solve_kepler_orbit((1, 0), (0, 1), gm=-1.0, dt=0.01, steps=10)` raises `ValueError` | "If gm <= 0.0, raise ValueError(\\"GM parameter must be positive\\")" |
| `assert solve_kepler_orbit((1, 0), (0, 1), gm=1.0, dt=-0.1, steps=10)` raises `ValueError` | "If dt <= 0.0, raise ValueError(\\"Time step dt must be positive\\")" |
| `assert solve_kepler_orbit((1, 0), (0, 1), gm=1.0, dt=0.01, steps=0)` raises `ValueError` | "If steps < 1, raise ValueError(\\"Steps must be at least 1\\")" |
| Circular orbit circularity $\|r_n\| \approx 1.0$ | "using the Velocity Verlet (symplectic) numerical integration scheme" |
| Angular momentum conservation $\Delta L / L_0 < 1e-7$ | "the relative variations ... must remain bounded within 1e-4" |
| Specific energy conservation $\Delta E / E_0 < 1e-4$ | "the relative variations |E_n - E_0| / |E_0| ... must remain bounded within 1e-4" |
| All output list lengths equal `steps + 1` | "Returns a dictionary containing exactly: position ... of length steps + 1" |
""",
        "test_code": f"""# CANARY: {CANARY}
import math
import pytest
from src.kepler_solver import solve_kepler_orbit


def test_kepler_validations():
    with pytest.raises(ValueError, match="Initial radius cannot be zero"):
        solve_kepler_orbit((0.0, 0.0), (0.0, 1.0), gm=1.0, dt=0.01, steps=10)

    with pytest.raises(ValueError, match="GM parameter must be positive"):
        solve_kepler_orbit((1.0, 0.0), (0.0, 1.0), gm=0.0, dt=0.01, steps=10)

    with pytest.raises(ValueError, match="Time step dt must be positive"):
        solve_kepler_orbit((1.0, 0.0), (0.0, 1.0), gm=1.0, dt=-0.01, steps=10)

    with pytest.raises(ValueError, match="Steps must be at least 1"):
        solve_kepler_orbit((1.0, 0.0), (0.0, 1.0), gm=1.0, dt=0.01, steps=0)


def test_circular_orbit_conservation():
    # Unit circle orbit: r0 = (1.0, 0.0), v0 = (0.0, 1.0), GM = 1.0. Period T = 2*pi
    dt = 0.005
    steps = int(math.ceil(2 * math.pi / dt))  # 1 full orbit
    res = solve_kepler_orbit(r0=(1.0, 0.0), v0=(0.0, 1.0), gm=1.0, dt=dt, steps=steps)

    assert len(res["position"]) == steps + 1
    assert len(res["energy"]) == steps + 1
    assert len(res["angular_momentum"]) == steps + 1

    # Check radius stays 1.0 +- 1e-3
    for x, y in res["position"]:
        r = math.sqrt(x**2 + y**2)
        assert abs(r - 1.0) < 1e-3

    # Check angular momentum conservation (exact in central force)
    L0 = res["angular_momentum"][0]
    for L in res["angular_momentum"]:
        assert abs(L - L0) < 1e-7

    # Check energy conservation
    E0 = res["energy"][0]
    for E in res["energy"]:
        rel_err = abs((E - E0) / E0)
        assert rel_err < 1e-4
"""
    },
    {
        "id": "TASK-06-PHYS-HEAT-1D",
        "category": "physics_numerics",
        "held_out": True,
        "title": "1D Transient Heat Conduction via Crank-Nicolson",
        "target_file": "src/heat_solver.py",
        "spec": """# Task Specification: 1D Transient Heat Conduction via Crank-Nicolson

## 1. Function Contract
Implement `solve_heat_1d_crank_nicolson` in `src/heat_solver.py`.

### Function Signature
```python
def solve_heat_1d_crank_nicolson(
    alpha: float,
    length: float,
    nx: int,
    t_final: float,
    dt: float,
    u0_fn: Callable[[float], float]
) -> dict[str, Any]:
```

### Parameter Validations
- `alpha`: Thermal diffusivity coefficient. Must be float > 0.0. If `alpha <= 0.0`, raise `ValueError("alpha must be positive")`.
- `length`: Domain length $L$ in meters. Must be float > 0.0. If `length <= 0.0`, raise `ValueError("length must be positive")`.
- `nx`: Number of spatial grid points. Must be integer >= 3. If `nx < 3`, raise `ValueError("nx must be at least 3")`.
- `t_final`: Simulation duration in seconds. Must be float > 0.0. If `t_final <= 0.0`, raise `ValueError("t_final must be positive")`.
- `dt`: Time step in seconds. Must be float > 0.0. If `dt <= 0.0`, raise `ValueError("dt must be positive")`.

### Spatial & Temporal Discretization
1. Spatial grid spacing: $\Delta x = \frac{length}{nx - 1}$.
   Grid points: $x_i = i \cdot \Delta x$ for $i \in \{0, 1, \dots, nx - 1\}$.
2. Number of time steps: $N_t = \max(1, \text{round}(t_{final} / dt))$.
   Actual reached simulated time: $t_{reached} = N_t \cdot dt$.
3. Initial condition: $u^0(x_i) = u0\_fn(x_i)$.
4. Boundary condition enforcement: Homogeneous Dirichlet boundaries $u(0, t) = 0.0$ and $u(length, t) = 0.0$ are enforced for all time steps. Specifically, $u^n_0 = 0.0$ and $u^n_{nx-1} = 0.0$ for all $n \ge 0$.

### Crank-Nicolson Linear System
Solves $\\frac{\\partial u}{\\partial t} = \\alpha \\frac{\\partial^2 u}{\\partial x^2}$ using the unconditionally stable second-order Crank-Nicolson scheme.
For interior nodes $i \in \\{1, \\dots, nx - 2\\}$:
Let $r = \\frac{\\alpha \\Delta t}{2 (\\Delta x)^2}$.
$$-r u^{n+1}_{i-1} + (1 + 2r) u^{n+1}_i - r u^{n+1}_{i+1} = r u^n_{i-1} + (1 - 2r) u^n_i + r u^n_{i+1}$$
This tridiagonal system must be solved efficiently at each time step using the Thomas algorithm (tridiagonal matrix algorithm) in $O(nx)$ operations without computing full matrix inverses.

### Return Dictionary Specification
Returns a dictionary containing:
- `"x"`: `list[float]` of spatial grid coordinates of length `nx`.
- `"u"`: `list[float]` of temperature values at $t = t_{reached}$ of length `nx`.
- `"time"`: `float` $t_{reached}$.
- `"max_temp"`: `float` $\max(u)$ at final time.
""",
        "traceability": """# Traceability Matrix: TASK-06-PHYS-HEAT-1D

| Test Assertion | Spec Sentence Justification |
|---|---|
| `assert solve_heat_1d_crank_nicolson(alpha=-1.0, ...)` raises `ValueError` | "If alpha <= 0.0, raise ValueError(\\"alpha must be positive\\")" |
| `assert solve_heat_1d_crank_nicolson(alpha=1.0, length=0.0, ...)` raises `ValueError` | "If length <= 0.0, raise ValueError(\\"length must be positive\\")" |
| `assert solve_heat_1d_crank_nicolson(..., nx=2)` raises `ValueError` | "If nx < 3, raise ValueError(\\"nx must be at least 3\\")" |
| `assert solve_heat_1d_crank_nicolson(..., dt=0.0)` raises `ValueError` | "If dt <= 0.0, raise ValueError(\\"dt must be positive\\")" |
| Boundary nodes $u[0] == 0.0$ and $u[-1] == 0.0$ | "Homogeneous Dirichlet boundaries u(0, t) = 0.0 and u(length, t) = 0.0 are enforced for all time steps." |
| Analytical fundamental mode decay $e^{-\\alpha (\\pi / L)^2 t}$ matches within $10^{-3}$ | "Solves du/dt = alpha d2u/dx2 using the unconditionally stable second-order Crank-Nicolson scheme." |
| Thermal energy non-negative and maximum temperature decays monotonically | "Maximum principle for the heat equation" |
""",
        "test_code": f"""# CANARY: {CANARY}
import math
import pytest
from src.heat_solver import solve_heat_1d_crank_nicolson


def test_heat_solver_validations():
    u0 = lambda x: math.sin(math.pi * x)
    with pytest.raises(ValueError, match="alpha must be positive"):
        solve_heat_1d_crank_nicolson(alpha=0.0, length=1.0, nx=21, t_final=0.1, dt=0.01, u0_fn=u0)

    with pytest.raises(ValueError, match="length must be positive"):
        solve_heat_1d_crank_nicolson(alpha=1.0, length=-1.0, nx=21, t_final=0.1, dt=0.01, u0_fn=u0)

    with pytest.raises(ValueError, match="nx must be at least 3"):
        solve_heat_1d_crank_nicolson(alpha=1.0, length=1.0, nx=2, t_final=0.1, dt=0.01, u0_fn=u0)

    with pytest.raises(ValueError, match="dt must be positive"):
        solve_heat_1d_crank_nicolson(alpha=1.0, length=1.0, nx=21, t_final=0.1, dt=-0.01, u0_fn=u0)


def test_analytical_sine_decay():
    # Exact solution: u(x, t) = e^(-alpha * pi^2 * t / L^2) * sin(pi * x / L)
    alpha = 0.1
    L = 1.0
    nx = 51
    t_final = 0.2
    dt = 0.005
    u0 = lambda x: math.sin(math.pi * x / L)

    res = solve_heat_1d_crank_nicolson(alpha=alpha, length=L, nx=nx, t_final=t_final, dt=dt, u0_fn=u0)

    assert res["u"][0] == 0.0
    assert res["u"][-1] == 0.0

    expected_decay = math.exp(-alpha * (math.pi / L)**2 * res["time"])
    mid_idx = nx // 2
    actual_mid = res["u"][mid_idx]
    expected_mid = expected_decay * math.sin(math.pi * res["x"][mid_idx] / L)

    assert abs(actual_mid - expected_mid) < 1e-3
"""
    },
    {
        "id": "TASK-07-MULTI-EVENT-BUS",
        "category": "multi_module",
        "held_out": True,
        "title": "Asynchronous Event Bus with DLQ and Middleware",
        "target_file": "src/event_system/bus.py",
        "spec": """# Task Specification: Asynchronous Event Bus with DLQ and Middleware

## 1. Multi-Module Package Contract
Implement the event bus package across three files in `src/event_system/`:
1. `src/event_system/events.py`
2. `src/event_system/dead_letter.py`
3. `src/event_system/bus.py`

### Module 1: `src/event_system/events.py`
```python
from dataclasses import dataclass, field
from typing import Any, Optional
import time

@dataclass
class Event:
    id: str
    topic: str
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
```
- `id`: Non-empty string. If not `isinstance(id, str)` or empty string, raise `ValueError("Event id must be a non-empty string")`.
- `topic`: Non-empty string. If not `isinstance(topic, str)` or empty string, raise `ValueError("Event topic must be a non-empty string")`.
- `payload`: Must be an instance of `dict`. If not, raise `TypeError("Payload must be a dict")`.

### Module 2: `src/event_system/dead_letter.py`
```python
class DeadLetterQueue:
    def __init__(self) -> None:
        ...
```
1. `put(self, event: Event, failure_reason: str, retry_count: int) -> None`:
   - Records failed event as a dictionary: `{"event": event, "failure_reason": str(failure_reason), "retry_count": int(retry_count)}`.
2. `get_failed_events(self, topic: Optional[str] = None) -> list[dict[str, Any]]`:
   - Returns a shallow copy list of stored failure records.
   - If `topic` is provided, filters for events where `event.topic == topic`.
   - Inspection is non-destructive (does not remove events).
3. `clear(self) -> None`:
   - Clears all records from the DLQ.
4. `__len__(self) -> int`:
   - Returns the total count of failed events in the queue.

### Module 3: `src/event_system/bus.py`
```python
class EventBus:
    def __init__(self, dlq: Optional[DeadLetterQueue] = None, max_retries: int = 2) -> None:
        ...
```
- `dlq`: Optional `DeadLetterQueue` instance.
- `max_retries`: Non-negative integer. If `max_retries < 0`, raise `ValueError("max_retries must be non-negative")`.
- `subscribe(self, topic: str, handler: Callable[[Event], Awaitable[None]]) -> None`:
   - Subscribes an async handler to a topic.
   - Wildcard `"*"` matches all published event topics.
- `unsubscribe(self, topic: str, handler: Callable[[Event], Awaitable[None]]) -> bool`:
   - Unregisters handler. Returns `True` if found and removed, `False` otherwise.
- `add_middleware(self, middleware_fn: Callable[[Event, Callable[[Event], Awaitable[None]]], Awaitable[None]]) -> None`:
   - Registers middleware in FIFO execution order. If middleware does not await `next_handler(event)`, event dispatch is short-circuited.
- `async publish(self, event: Event) -> None`:
   - Dispatches `event` through middleware chain.
   - Handlers matching `event.topic` and wildcard `"*"` are deduplicated so that each unique handler is called at most once per event.
   - Matching handlers are executed concurrently via `asyncio.gather`.
   - If a handler raises an exception, it is immediately retried up to `max_retries` times (total attempts = $1 + \text{max\_retries}$).
   - If all retries fail:
     - If `dlq` is configured: writes to DLQ via `dlq.put(event, str(error), max_retries)`.
     - If `dlq is None`: raises `RuntimeError(f"Handler failed after {max_retries} retries with no DLQ configured")`.
""",
        "traceability": """# Traceability Matrix: TASK-07-MULTI-EVENT-BUS

| Test Assertion | Spec Sentence Justification |
|---|---|
| `Event("", "topic", {})` raises `ValueError` | "id: Non-empty string. If not isinstance(id, str) or empty string, raise ValueError(\\"Event id must be a non-empty string\\")" |
| `EventBus(max_retries=-1)` raises `ValueError` | "If max_retries < 0, raise ValueError(\\"max_retries must be non-negative\\")" |
| Wildcard subscriber `*` receives event | "Wildcard \\"*\\" matches all published event topics." |
| Middleware executes in order and can short-circuit | "If middleware does not await next_handler(event), event dispatch is short-circuited." |
| Handler failure retried `max_retries` times before DLQ routing | "If a handler raises an exception, it is immediately retried up to max_retries times... writes to DLQ via dlq.put" |
| Handler failure with `dlq=None` raises `RuntimeError` | "If dlq is None: raises RuntimeError" |
| Unsubscribe returns `True` then `False` | "Returns True if found and removed, False otherwise." |
""",
        "test_code": f"""# CANARY: {CANARY}
import asyncio
import pytest
from src.event_system.events import Event
from src.event_system.dead_letter import DeadLetterQueue
from src.event_system.bus import EventBus


def test_event_validation():
    with pytest.raises(ValueError, match="Event id must be a non-empty string"):
        Event(id="", topic="user.created", payload={{"name": "Alice"}})

    with pytest.raises(ValueError, match="Event topic must be a non-empty string"):
        Event(id="evt1", topic="", payload={{"name": "Alice"}})


@pytest.mark.asyncio
async def test_publish_and_wildcard_subscribe():
    bus = EventBus()
    received = []

    async def on_user(event: Event):
        received.append(("user", event.id))

    async def on_wildcard(event: Event):
        received.append(("all", event.id))

    bus.subscribe("user.created", on_user)
    bus.subscribe("*", on_wildcard)

    e1 = Event(id="e1", topic="user.created", payload={{"val": 1}})
    await bus.publish(e1)

    assert ("user", "e1") in received
    assert ("all", "e1") in received


@pytest.mark.asyncio
async def test_middleware_pipeline_short_circuit():
    bus = EventBus()
    called = []

    async def mw_block(event: Event, next_handler):
        if event.payload.get("blocked"):
            return  # Short circuit
        await next_handler(event)

    async def handler(event: Event):
        called.append(event.id)

    bus.add_middleware(mw_block)
    bus.subscribe("test", handler)

    await bus.publish(Event(id="e1", topic="test", payload={{"blocked": True}}))
    assert len(called) == 0

    await bus.publish(Event(id="e2", topic="test", payload={{"blocked": False}}))
    assert called == ["e2"]


@pytest.mark.asyncio
async def test_retry_and_dlq_routing():
    dlq = DeadLetterQueue()
    bus = EventBus(dlq=dlq, max_retries=2)
    attempts = 0

    async def failing_handler(event: Event):
        nonlocal attempts
        attempts += 1
        raise ValueError("Simulated network timeout")

    bus.subscribe("order.process", failing_handler)
    event = Event(id="ord1", topic="order.process", payload={{"order_id": 99}})

    await bus.publish(event)

    assert attempts == 3  # 1 initial + 2 retries
    assert len(dlq) == 1
    failed = dlq.get_failed_events("order.process")
    assert len(failed) == 1
    assert failed[0]["event"].id == "ord1"
    assert "Simulated network timeout" in failed[0]["failure_reason"]
"""
    },
    {
        "id": "TASK-08-RETRIEVAL-SYMPLECTIC",
        "category": "retrieval_dependent",
        "held_out": False,
        "title": "Symplectic Störmer-Verlet Integrator via Project Conventions",
        "target_file": "src/integrator.py",
        "spec": """# Task Specification: Symplectic Störmer-Verlet Integrator via Project Conventions

## 1. Scope & Directives
Implement the numerical integrator in `src/integrator.py`.

### Mandatory Knowledge Retrieval Requirement
- You MUST follow this project's exact Hamiltonian integrator conventions.
- Do NOT assume formulas or coordinate conventions from memory or parametric recall.
- **Action**: Query the RAG engine using `rag_search` on the `knowledge` collection for project integrator conventions to retrieve:
  1. The function signature and parameter validations.
  2. The exact coordinate and momentum conventions ($q$ vs $p$).
  3. The two-step coordinate recursion formula.
  4. The startup step for the first position $q_1$.
  5. The momentum recovery conventions for boundary and interior points.
- The evaluation runner will audit your execution trace to verify that a `rag_search` call was issued and successfully returned the project's integrator conventions knowledge document.
""",
        "traceability": """# Traceability Matrix: TASK-08-RETRIEVAL-SYMPLECTIC

| Test Assertion | Spec Sentence Justification |
|---|---|
| Trace contains `rag_search` call returning knowledge entry ID | "The evaluation runner will audit your execution trace to verify that a rag_search call was issued" |
| Startup step $q_1 = q_0 + dt \cdot p_0 - 0.5 dt^2 V'(q_0)$ | Retrieved from project knowledge entry convention (startup condition for the first position step) |
| Position update $q_{n+1} = 2 q_n - q_{n-1} - dt^2 V'(q_n)$ | Retrieved from project knowledge entry convention (Störmer-Verlet position recurrence) |
| Harmonic oscillator energy conservation $< 10^{-4}$ over 1000 steps | Derived from symplectic nature specified in retrieved knowledge entry |
| Initial momentum $p_0 = p_0$ | Retrieved from project knowledge entry convention (initial momentum boundary condition) |
| Interior momentum recovery $p_n = (q_{n+1} - q_{n-1}) / (2 dt)$ | Retrieved from project knowledge entry convention (interior momentum recovery) |
| Final momentum recovery $p_{steps} = (q_{steps} - q_{steps-1})/dt - 0.5 dt V'(q_{steps})$ | Retrieved from project knowledge entry convention (final momentum boundary condition) |
| Signature `solve_stormer_verlet(q0, p0, dV_dq_fn, dt, steps)` | Retrieved from project knowledge entry convention (function interface) |
""",
        "test_code": f"""# CANARY: {CANARY}
import math
import pytest
from src.integrator import solve_stormer_verlet


def test_integrator_validations():
    dV_dq = lambda q: q
    with pytest.raises(ValueError, match="Time step dt must be positive"):
        solve_stormer_verlet(q0=1.0, p0=0.0, dV_dq_fn=dV_dq, dt=0.0, steps=10)

    with pytest.raises(ValueError, match="Steps must be at least 1"):
        solve_stormer_verlet(q0=1.0, p0=0.0, dV_dq_fn=dV_dq, dt=0.01, steps=0)


def test_harmonic_oscillator_startup_and_recursion():
    # V(q) = 0.5 * q^2 => dV/dq = q. Exact solution: q(t) = cos(t), p(t) = -sin(t)
    dt = 0.01
    q0 = 1.0
    p0 = 0.0
    dV_dq = lambda q: q

    res = solve_stormer_verlet(q0=q0, p0=p0, dV_dq_fn=dV_dq, dt=dt, steps=100)

    assert "q" in res and "p" in res and "time" in res
    assert len(res["q"]) == 101
    assert len(res["p"]) == 101
    assert len(res["time"]) == 101

    # Check startup step formula q1 = q0 + dt*p0 - 0.5*dt^2 * dV_dq(q0)
    expected_q1 = q0 + dt * p0 - 0.5 * (dt**2) * dV_dq(q0)
    assert abs(res["q"][1] - expected_q1) < 1e-12

    # Check initial momentum p0
    assert abs(res["p"][0] - p0) < 1e-12

    # Check interior momentum recovery formula: p_n = (q_{{n+1}} - q_{{n-1}}) / (2*dt)
    for n in range(1, 100):
        expected_pn = (res["q"][n + 1] - res["q"][n - 1]) / (2.0 * dt)
        assert abs(res["p"][n] - expected_pn) < 1e-12

    # Check final momentum recovery formula
    expected_p_final = (res["q"][100] - res["q"][99]) / dt - 0.5 * dt * dV_dq(res["q"][100])
    assert abs(res["p"][100] - expected_p_final) < 1e-12


def test_harmonic_oscillator_symplectic_conservation():
    dt = 0.01
    steps = 1000
    res = solve_stormer_verlet(q0=1.0, p0=0.0, dV_dq_fn=lambda q: q, dt=dt, steps=steps)

    # Initial energy E0 = 0.5 * p^2 + 0.5 * q^2 = 0.5
    E0 = 0.5 * (res["p"][0]**2 + res["q"][0]**2)

    for n in range(steps + 1):
        En = 0.5 * (res["p"][n]**2 + res["q"][n]**2)
        assert abs((En - E0) / E0) < 1e-4
"""
    }
]


def generate_task_suite():
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    encrypted_payload: dict[str, str] = {}

    for t in TASKS:
        t_id = t["id"]
        t_dir = TASKS_DIR / t_id
        t_dir.mkdir(parents=True, exist_ok=True)

        # 1. Write task.json metadata
        meta = {
            "id": t_id,
            "category": t["category"],
            "held_out": t["held_out"],
            "title": t["title"],
            "target_file": t["target_file"],
            "canary": CANARY,
        }
        (t_dir / "task.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # 2. Write README.md contract specification
        (t_dir / "README.md").write_text(t["spec"].strip() + "\n", encoding="utf-8")

        # 3. Write traceability.md
        (t_dir / "traceability.md").write_text(t["traceability"].strip() + "\n", encoding="utf-8")

        # 4. Collect hidden check code for encryption
        encrypted_payload[t_id] = t["test_code"].strip()

    # 5. Encrypt all hidden test fixtures into evals/hidden_evals.enc
    encrypt_evals(encrypted_payload, DEFAULT_PASSPHRASE, ENCRYPTED_ARCHIVE)
    print(f"Successfully generated 8 tasks in {TASKS_DIR}")
    print(f"Encrypted hidden tests into {ENCRYPTED_ARCHIVE} (size: {ENCRYPTED_ARCHIVE.stat().st_size} bytes)")


if __name__ == "__main__":
    generate_task_suite()
