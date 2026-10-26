# Traceability Matrix: TASK-02-CODE-GRAPH

| Test Assertion | Spec Sentence Justification |
|---|---|
| `assert graph.add_node("A", weight=-2)` raises `ValueError` | "If weight < 0.0, raise ValueError(\"Weight must be non-negative\")" |
| `assert graph.add_dependency("A", "A")` raises `CycleError` | "If dependent == dependency, immediately raise CycleError(\"Self-dependency detected\")" |
| Diamond DAG `A->B, A->C, B->D, C->D` topological sort order | "Returns a valid linear ordering of all nodes such that for every directed dependency u -> v, u appears before v." |
| Tie-breaking: `assert graph.topological_sort() == ["A", "B", "C"]` | "When multiple nodes have zero remaining in-degrees, sort them in lexicographical ascending order" |
| Cyclic graph `A->B->C->A` raises `CycleError` in sort | "If the graph contains any directed cycle, raise CycleError(\"Graph contains a cycle\")." |
| Critical path `A(2)->B(3)->D(1)` equals `6.0` | "Returns the maximum cumulative weight along any directed path through the graph" |
| Empty graph returns `[]` and `0.0` | "Returns empty list [] for an empty graph." and "For an empty graph, returns 0.0." |
| Isolated single node critical path equals node weight | "An isolated single node u with weight W is a valid path with cumulative weight W." |
| `detect_cycles()` returns `[["A", "B", "A"]]` with canonical normalization | "Each cycle is represented as a list of node names tracing the loop from start back to start... cyclically rotated so that its lexicographically smallest node appears at index 0" |
