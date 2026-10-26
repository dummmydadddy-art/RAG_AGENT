# Task Specification: Topological Sorter with Cycle Detection

## 1. Class & Method Contract
Implement `CycleError` and `DependencyGraph` in `src/dependency_graph.py`.

### Exception Contract
```python
class CycleError(Exception):
    """Raised when a dependency cycle is detected in the graph."""
    pass
```

### Class Signature
```python
class DependencyGraph:
    def __init__(self) -> None:
        """Initializes an empty directed dependency graph."""
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
