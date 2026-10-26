"""
Additional tasks batch: Pure Coding (09-12) and Pure Maths (13-15)
"""

CANARY = "CANARY-RAG-AGENT-CHECK-V2-7A8B9C0D-E1F2-3456-7890-ABCDEF123456"
HDR = f"# Canary: {CANARY}\n"

TASKS_CODING_MATHS = [
    {
        "id": "TASK-09-CODE-TRIE",
        "category": "pure_coding",
        "held_out": False,
        "title": "Prefix Trie with Autocomplete and Longest Prefix",
        "target_file": "src/prefix_trie.py",
        "spec": """# Task Specification: Prefix Trie with Autocomplete and Longest Prefix

## 1. Class Contract
Implement `PrefixTrie` in `src/prefix_trie.py`.

### Constructor Signature
```python
def __init__(self) -> None:
```
Initializes an empty prefix trie.

### Methods
1. `insert(self, word: str, value: Any = None) -> None`:
   - Inserts string `word` into trie associated with optional `value`.
   - If `word` is empty (`""`), raise `ValueError("Word cannot be empty")`.
   - If `not isinstance(word, str)`, raise `TypeError("Word must be a string")`.
   - If `word` already exists, updates associated value.

2. `search(self, word: str) -> Optional[Any]`:
   - Returns associated value if exact `word` is in trie; returns `None` if absent.

3. `starts_with(self, prefix: str) -> bool`:
   - Returns `True` if any inserted word starts with `prefix`; `True` if `prefix == ""` and trie non-empty; `False` otherwise.

4. `autocomplete(self, prefix: str, limit: int = 10) -> List[Tuple[str, Any]]`:
   - Returns up to `limit` words beginning with `prefix` and their values, sorted lexicographically by word.

5. `longest_prefix_of(self, word: str) -> str`:
   - Returns the longest matching word stored in the trie that is a prefix of `word`. Returns `""` if none match.
""",
        "traceability": """# Traceability Matrix: TASK-09-CODE-TRIE
- test_insert_and_search: verifies insert and search contracts.
- test_autocomplete_ordering: verifies lexicographical sorting up to limit.
- test_longest_prefix: verifies longest_prefix_of matching.
- test_type_and_value_errors: verifies empty word ValueError and non-string TypeError.
""",
        "test_code": HDR + """import pytest
from src.prefix_trie import PrefixTrie

def test_trie_basic_operations():
    trie = PrefixTrie()
    trie.insert("apple", 100)
    trie.insert("app", 50)
    trie.insert("application", 200)

    assert trie.search("apple") == 100
    assert trie.search("app") == 50
    assert trie.search("appl") is None
    assert trie.starts_with("app") is True
    assert trie.starts_with("banana") is False

def test_trie_autocomplete_and_longest_prefix():
    trie = PrefixTrie()
    trie.insert("car", 1)
    trie.insert("cart", 2)
    trie.insert("carpet", 3)
    trie.insert("cat", 4)

    auto = trie.autocomplete("car", limit=2)
    assert len(auto) == 2
    assert [w for w, _ in auto] == ["car", "carpet"]

    assert trie.longest_prefix_of("cartography") == "cart"
    assert trie.longest_prefix_of("dog") == ""

def test_trie_validation():
    trie = PrefixTrie()
    with pytest.raises(ValueError):
        trie.insert("")
    with pytest.raises(TypeError):
        trie.insert(123)
"""
    },
    {
        "id": "TASK-10-CODE-TOKEN-BUCKET",
        "category": "pure_coding",
        "held_out": False,
        "title": "Thread-safe Token Bucket Rate Limiter",
        "target_file": "src/token_bucket.py",
        "spec": """# Task Specification: Thread-safe Token Bucket Rate Limiter

## 1. Class Contract
Implement `TokenBucket` in `src/token_bucket.py`.

### Constructor Signature
```python
def __init__(
    self,
    capacity: float,
    refill_rate: float,
    time_fn: Optional[Callable[[], float]] = None
) -> None:
```
- `capacity`: Maximum bucket capacity (tokens). Must be float/int > 0. If `<= 0`, raise `ValueError("Capacity must be positive")`.
- `refill_rate`: Refill rate in tokens per second. Must be float/int > 0. If `<= 0`, raise `ValueError("Refill rate must be positive")`.
- `time_fn`: Monotonic clock callable returning current time in float seconds. Defaults to `time.monotonic`.

### Methods
1. `consume(self, tokens: float = 1.0) -> bool`:
   - Refills available tokens based on elapsed time since last call up to `capacity`.
   - If `tokens <= 0`, raise `ValueError("Tokens to consume must be positive")`.
   - If `available_tokens >= tokens`: deducts `tokens` and returns `True`.
   - If `available_tokens < tokens`: deducts zero tokens and returns `False`.
   - Thread-safe across concurrent threads.

2. `available_tokens(self) -> float`:
   - Returns current tokens available after applying fractional refill up to the query time.
""",
        "traceability": """# Traceability Matrix: TASK-10-CODE-TOKEN-BUCKET
- test_token_bucket_consume: verifies token consumption and exhaustion.
- test_token_bucket_refill: verifies time_fn clock advancement and token accumulation up to capacity.
- test_token_bucket_thread_safety: verifies concurrent threads consuming tokens without race conditions.
""",
        "test_code": HDR + """import pytest
import threading
from src.token_bucket import TokenBucket

def test_token_bucket_consume_and_refill():
    curr_time = 100.0
    def mock_time():
        return curr_time

    bucket = TokenBucket(capacity=10.0, refill_rate=2.0, time_fn=mock_time)
    assert bucket.available_tokens() == 10.0

    # Consume 6
    assert bucket.consume(6.0) is True
    assert bucket.available_tokens() == 4.0

    # Try consuming 5 -> fails
    assert bucket.consume(5.0) is False
    assert bucket.available_tokens() == 4.0

    # Advance clock by 2.0s -> +4 tokens -> total 8.0
    curr_time += 2.0
    assert abs(bucket.available_tokens() - 8.0) < 1e-6
    assert bucket.consume(8.0) is True

def test_token_bucket_thread_safety():
    bucket = TokenBucket(capacity=500.0, refill_rate=1.0)
    successes = []

    def worker():
        for _ in range(50):
            if bucket.consume(1.0):
                successes.append(1)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()

    # Total consumed cannot exceed capacity 500
    assert len(successes) <= 500
"""
    },
    {
        "id": "TASK-11-CODE-RING-BUFFER",
        "category": "pure_coding",
        "held_out": False,
        "title": "Circular Ring Buffer with Overwrite Policy",
        "target_file": "src/ring_buffer.py",
        "spec": """# Task Specification: Circular Ring Buffer with Overwrite Policy

## 1. Class Contract
Implement `RingBuffer`, `BufferFullError`, and `BufferEmptyError` in `src/ring_buffer.py`.

### Constructor Signature
```python
def __init__(self, capacity: int, overwrite: bool = False) -> None:
```
- `capacity`: Maximum elements in buffer. Must be integer > 0. If `<= 0`, raise `ValueError("Capacity must be positive")`.
- `overwrite`: If `True`, pushing to a full buffer drops the oldest element. If `False`, pushing to a full buffer raises `BufferFullError`.

### Methods
1. `push(self, item: Any) -> None`: Inserts `item` at the tail.
2. `pop(self) -> Any`: Removes and returns item from head. If empty, raises `BufferEmptyError`.
3. `peek(self) -> Any`: Returns item from head without removing. If empty, raises `BufferEmptyError`.
4. `is_empty(self) -> bool` and `is_full(self) -> bool`.
5. `__len__(self) -> int` and `__iter__(self)` yielding elements in FIFO order.
""",
        "traceability": """# Traceability Matrix: TASK-11-CODE-RING-BUFFER
- test_ring_buffer_fifo: verifies FIFO ordering and len.
- test_ring_buffer_full_error: verifies BufferFullError when overwrite=False.
- test_ring_buffer_overwrite: verifies dropping oldest element when overwrite=True.
""",
        "test_code": HDR + """import pytest
from src.ring_buffer import RingBuffer, BufferFullError, BufferEmptyError

def test_ring_buffer_basic():
    rb = RingBuffer(capacity=3, overwrite=False)
    assert rb.is_empty() is True
    rb.push(1)
    rb.push(2)
    rb.push(3)
    assert rb.is_full() is True
    assert len(rb) == 3
    assert list(rb) == [1, 2, 3]

    with pytest.raises(BufferFullError):
        rb.push(4)

    assert rb.pop() == 1
    assert rb.peek() == 2
    assert len(rb) == 2

def test_ring_buffer_overwrite():
    rb = RingBuffer(capacity=3, overwrite=True)
    rb.push("a")
    rb.push("b")
    rb.push("c")
    rb.push("d")  # over-writes 'a'
    assert list(rb) == ["b", "c", "d"]
    assert rb.pop() == "b"
"""
    },
    {
        "id": "TASK-12-CODE-INTERVAL-TREE",
        "category": "pure_coding",
        "held_out": False,
        "title": "Augmented Interval Tree for Range Stabbing",
        "target_file": "src/interval_tree.py",
        "spec": """# Task Specification: Augmented Interval Tree for Range Stabbing

## 1. Class Contract
Implement `IntervalTree` in `src/interval_tree.py`.

### Constructor Signature
```python
def __init__(self) -> None:
```

### Methods
1. `insert(self, start: float, end: float, data: Any = None) -> None`:
   - Inserts interval `[start, end]`. Must satisfy `start <= end`. If `start > end`, raise `ValueError("Start must be <= end")`.
2. `query_point(self, point: float) -> List[Tuple[float, float, Any]]`:
   - Returns all intervals containing `point` (`start <= point <= end`), sorted by `start` ascending.
3. `query_overlap(self, start: float, end: float) -> List[Tuple[float, float, Any]]`:
   - Returns all intervals overlapping `[start, end]` (i.e. `max(start, i.start) <= min(end, i.end)`), sorted by `start`.
""",
        "traceability": """# Traceability Matrix: TASK-12-CODE-INTERVAL-TREE
- test_interval_tree_point_query: verifies point stabbing inside intervals.
- test_interval_tree_overlap_query: verifies overlapping intervals query.
- test_interval_tree_validation: verifies start <= end enforcement.
""",
        "test_code": HDR + """import pytest
from src.interval_tree import IntervalTree

def test_interval_tree_queries():
    tree = IntervalTree()
    tree.insert(15, 20, "A")
    tree.insert(10, 30, "B")
    tree.insert(17, 19, "C")
    tree.insert(5, 20, "D")
    tree.insert(12, 15, "E")
    tree.insert(30, 40, "F")

    # Query point 18 -> should hit A, B, C, D
    pts = tree.query_point(18)
    labels = set(lbl for _, _, lbl in pts)
    assert labels == {"A", "B", "C", "D"}

    # Overlap query [25, 35] -> should hit B, F
    overlaps = tree.query_overlap(25, 35)
    ov_labels = set(lbl for _, _, lbl in overlaps)
    assert ov_labels == {"B", "F"}

def test_interval_tree_validation():
    tree = IntervalTree()
    with pytest.raises(ValueError):
        tree.insert(25, 10)
"""
    },
    {
        "id": "TASK-13-MATH-POLYNOMIAL",
        "category": "pure_maths",
        "held_out": False,
        "title": "Chebyshev Polynomial Root Finder via Companion Matrix",
        "target_file": "src/chebyshev_roots.py",
        "spec": """# Task Specification: Chebyshev Polynomial Root Finder via Companion Matrix

## 1. Function Contract
Implement `find_chebyshev_roots` in `src/chebyshev_roots.py`.

### Function Signature
```python
def find_chebyshev_roots(
    coeffs: List[float],
    domain: Tuple[float, float] = (-1.0, 1.0)
) -> List[float]:
```
- `coeffs`: Coefficients $c_0, c_1, \\dots, c_n$ for expansion $P(x) = \\sum_{k=0}^n c_k T_k(x)$ where $T_k$ are Chebyshev polynomials of the first kind.
- Finds all real roots of $P(x)$ strictly within the interval `[domain[0], domain[1]]`.
- Uses Frobenius/Colleague companion matrix eigenvalue decomposition.
- Returns list of sorted unique real roots within tolerance `1e-6`.
""",
        "traceability": """# Traceability Matrix: TASK-13-MATH-POLYNOMIAL
- test_chebyshev_known_roots: verifies roots of T_2(x) = 2x^2 - 1 at +/- sqrt(0.5).
- test_chebyshev_domain_filtering: verifies only roots inside domain are returned.
""",
        "test_code": HDR + """import math
import pytest
from src.chebyshev_roots import find_chebyshev_roots

def test_chebyshev_roots_T2():
    # T2(x) = -1*T0 + 0*T1 + 1*T2 = 2x^2 - 1 -> roots at +/- 1/sqrt(2) approx +/- 0.70710678
    roots = find_chebyshev_roots([0.0, 0.0, 1.0])
    assert len(roots) == 2
    expected = 1.0 / math.sqrt(2.0)
    assert abs(roots[0] - (-expected)) < 1e-5
    assert abs(roots[1] - expected) < 1e-5

def test_chebyshev_roots_T3():
    # T3(x) = 4x^3 - 3x -> roots at -sqrt(3)/2, 0, sqrt(3)/2
    roots = find_chebyshev_roots([0.0, 0.0, 0.0, 1.0])
    assert len(roots) == 3
    exp_val = math.sqrt(3.0) / 2.0
    assert abs(roots[0] - (-exp_val)) < 1e-5
    assert abs(roots[1] - 0.0) < 1e-5
    assert abs(roots[2] - exp_val) < 1e-5
"""
    },
    {
        "id": "TASK-14-MATH-FFT",
        "category": "pure_maths",
        "held_out": False,
        "title": "Cooley-Tukey Radix-2 1D Fast Fourier Transform",
        "target_file": "src/fft_solver.py",
        "spec": """# Task Specification: Cooley-Tukey Radix-2 1D Fast Fourier Transform

## 1. Function Contract
Implement `fft_1d` and `ifft_1d` in `src/fft_solver.py`.

### Function Signatures
```python
def fft_1d(x: List[complex]) -> List[complex]:
def ifft_1d(X: List[complex]) -> List[complex]:
```
- Computes Discrete Fourier Transform $X_k = \\sum_{n=0}^{N-1} x_n e^{-i 2\\pi k n / N}$ using Cooley-Tukey Radix-2 algorithm.
- Input length $N$ must be a power of 2 ($N = 2^p$). If not, raise `ValueError("Input length must be a power of 2")`.
- `ifft_1d` satisfies Parseval and invertibility: `ifft_1d(fft_1d(x)) == x` within numerical tolerance $10^{-10}$.
""",
        "traceability": """# Traceability Matrix: TASK-14-MATH-FFT
- test_fft_impulse_and_constant: verifies transform of delta and constant signals.
- test_fft_roundtrip_invertibility: verifies ifft(fft(x)) == x.
- test_fft_power_of_two_enforcement: verifies ValueError on non-power-of-2 inputs.
""",
        "test_code": HDR + """import math
import cmath
import pytest
from src.fft_solver import fft_1d, ifft_1d

def test_fft_roundtrip():
    signal = [complex(math.sin(i * 0.4), math.cos(i * 0.2)) for i in range(16)]
    transformed = fft_1d(signal)
    assert len(transformed) == 16
    recovered = ifft_1d(transformed)
    for orig, rec in zip(signal, recovered):
        assert abs(orig - rec) < 1e-10

def test_fft_validation():
    with pytest.raises(ValueError):
        fft_1d([1.0, 2.0, 3.0])  # length 3 is not power of 2
"""
    },
    {
        "id": "TASK-15-MATH-SIMPLEX",
        "category": "pure_maths",
        "held_out": False,
        "title": "Two-Phase Simplex Algorithm for Linear Programming",
        "target_file": "src/simplex_solver.py",
        "spec": """# Task Specification: Two-Phase Simplex Algorithm for Linear Programming

## 1. Function Contract
Implement `solve_linear_program` in `src/simplex_solver.py`.

### Function Signature
```python
def solve_linear_program(
    c: List[float],
    A: List[List[float]],
    b: List[float]
) -> Dict[str, Any]:
```
- Solves standard form maximization: $\\max c^T x$ subject to $A x \\le b$ and $x \\ge 0$.
- Implements two-phase simplex with slack variables.
- Returns dictionary:
  `{"status": "optimal" | "unbounded" | "infeasible", "objective_value": Optional[float], "solution": Optional[List[float]]}`.
""",
        "traceability": """# Traceability Matrix: TASK-15-MATH-SIMPLEX
- test_simplex_standard_max: verifies optimal solution and objective value on standard bounded LP.
- test_simplex_infeasible: verifies status='infeasible' on contradictory constraints.
""",
        "test_code": HDR + """import pytest
from src.simplex_solver import solve_linear_program

def test_simplex_standard_bounded():
    # max 3*x1 + 2*x2 subject to:
    # 2*x1 + x2 <= 100
    # x1 + x2 <= 80
    # x1 <= 40
    # x1, x2 >= 0
    # Optimal at (20, 60) -> obj = 3*20 + 2*60 = 180
    c = [3.0, 2.0]
    A = [[2.0, 1.0], [1.0, 1.0], [1.0, 0.0]]
    b = [100.0, 80.0, 40.0]

    res = solve_linear_program(c, A, b)
    assert res["status"] == "optimal"
    assert abs(res["objective_value"] - 180.0) < 1e-4
    sol = res["solution"]
    assert abs(sol[0] - 20.0) < 1e-4
    assert abs(sol[1] - 60.0) < 1e-4
"""
    }
]
