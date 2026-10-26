# Topological Sorter with Cycle Detection and Dependency Depth

**Category**: pure_coding
**Held Out**: False

## Specification
Implement `DependencyGraph` in `src/dependency_graph.py`.
Methods:
- `add_node(name: str) -> None`: Adds a node.
- `add_dependency(node: str, depends_on: str) -> None`: Declares that `node` depends on `depends_on`.
- `topological_sort() -> list[str]`: Returns valid execution order (dependencies before dependents). Raises `CycleError` with detected cycle if cyclic.
- `get_critical_path_depth() -> int`: Returns length of longest dependency chain (number of nodes in critical path). Empty graph returns 0.
