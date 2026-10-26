import heapq
from collections import defaultdict, deque
from typing import Dict, List, Set


class CycleError(Exception):
    """Raised when a dependency cycle is detected in the graph."""

    pass


class DependencyGraph:
    """Directed acyclic dependency graph supporting topological sorting, cycle detection, and critical path analysis."""

    def __init__(self) -> None:
        self._weights: Dict[str, float] = {}
        # Adjacency: u -> set of v (u must be completed before v can run: dependency -> dependent)
        self._adj: Dict[str, Set[str]] = defaultdict(set)
        # Reverse adjacency: v -> set of u (dependent -> dependencies)
        self._rev_adj: Dict[str, Set[str]] = defaultdict(set)

    def add_node(self, node: str, weight: float = 1.0) -> None:
        if not isinstance(node, str) or len(node) == 0:
            raise ValueError("Node must be a non-empty string")
        if not isinstance(weight, (int, float)) or weight < 0.0:
            raise ValueError("Weight must be non-negative")

        self._weights[node] = float(weight)
        if node not in self._adj:
            self._adj[node] = set()
        if node not in self._rev_adj:
            self._rev_adj[node] = set()

    def add_dependency(self, dependent: str, dependency: str) -> None:
        if not isinstance(dependent, str) or len(dependent) == 0:
            raise ValueError("Node must be a non-empty string")
        if not isinstance(dependency, str) or len(dependency) == 0:
            raise ValueError("Node must be a non-empty string")

        if dependent == dependency:
            raise CycleError("Self-dependency detected")

        if dependency not in self._weights:
            self.add_node(dependency, 1.0)
        if dependent not in self._weights:
            self.add_node(dependent, 1.0)

        # dependency -> dependent
        self._adj[dependency].add(dependent)
        self._rev_adj[dependent].add(dependency)

    def topological_sort(self) -> List[str]:
        if not self._weights:
            return []

        # Kahn's algorithm with min-heap for deterministic tie-breaking
        in_degree = {node: len(self._rev_adj[node]) for node in self._weights}
        heap = [node for node, deg in in_degree.items() if deg == 0]
        heapq.heapify(heap)

        result: List[str] = []
        while heap:
            curr = heapq.heappop(heap)
            result.append(curr)
            for nxt in sorted(self._adj[curr]):
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    heapq.heappush(heap, nxt)

        if len(result) < len(self._weights):
            raise CycleError("Graph contains a cycle")

        return result

    def critical_path_depth(self) -> float:
        if not self._weights:
            return 0.0

        # Topological sort validates DAG and gives evaluation order
        topo_order = self.topological_sort()

        # dp[u]: max path weight ending at node u
        dp: Dict[str, float] = {node: self._weights[node] for node in self._weights}

        for u in topo_order:
            for v in self._adj[u]:
                if dp[u] + self._weights[v] > dp[v]:
                    dp[v] = dp[u] + self._weights[v]

        return max(dp.values())

    def detect_cycles(self) -> List[List[str]]:
        """Finds all elementary cycles using Johnson's cycle finding algorithm or DFS."""
        if not self._weights:
            return []

        # Find all simple cycles using DFS
        all_cycles: List[List[str]] = []
        visited_in_path: List[str] = []
        visited_set: Set[str] = set()

        def dfs(start_node: str, curr_node: str) -> None:
            visited_in_path.append(curr_node)
            visited_set.add(curr_node)

            for neighbor in sorted(self._adj[curr_node]):
                if neighbor == start_node and len(visited_in_path) >= 1:
                    # Found cycle
                    cycle = list(visited_in_path) + [start_node]
                    all_cycles.append(cycle)
                elif neighbor not in visited_set and neighbor > start_node:
                    # Enforce start_node is the smallest node in the cycle to prevent duplicate rotations
                    dfs(start_node, neighbor)

            visited_set.remove(curr_node)
            visited_in_path.pop()

        nodes = sorted(self._weights.keys())
        for n in nodes:
            dfs(n, n)

        # Normalize each cycle: rotate so that the smallest node is at start (and end)
        normalized_cycles: Set[tuple] = set()
        for cycle in all_cycles:
            # cycle is [A, B, ..., A]
            nodes_in_cycle = cycle[:-1]
            if not nodes_in_cycle:
                continue
            min_node = min(nodes_in_cycle)
            min_idx = nodes_in_cycle.index(min_node)
            rotated = nodes_in_cycle[min_idx:] + nodes_in_cycle[:min_idx]
            canonical = tuple(rotated + [min_node])
            normalized_cycles.add(canonical)

        result = [list(c) for c in sorted(normalized_cycles)]
        return result
