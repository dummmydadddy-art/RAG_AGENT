from typing import Any, List, Optional, Tuple


class IntervalNode:
    def __init__(self, start: float, end: float, data: Any = None) -> None:
        self.start = float(start)
        self.end = float(end)
        self.data = data
        self.max_end = float(end)
        self.left: Optional[IntervalNode] = None
        self.right: Optional[IntervalNode] = None


class IntervalTree:
    """
    Augmented interval tree for stabbing and range overlap queries.
    """

    def __init__(self) -> None:
        self.root: Optional[IntervalNode] = None

    def insert(self, start: float, end: float, data: Any = None) -> None:
        if start > end:
            raise ValueError("Start must be <= end")

        def _insert(node: Optional[IntervalNode]) -> IntervalNode:
            if node is None:
                return IntervalNode(start, end, data)

            if start < node.start:
                node.left = _insert(node.left)
            else:
                node.right = _insert(node.right)

            node.max_end = max(node.max_end, end)
            return node

        self.root = _insert(self.root)

    def query_point(self, point: float) -> List[Tuple[float, float, Any]]:
        return self.query_overlap(point, point)

    def query_overlap(self, start: float, end: float) -> List[Tuple[float, float, Any]]:
        results: List[Tuple[float, float, Any]] = []

        def _search(node: Optional[IntervalNode]) -> None:
            if node is None:
                return

            if node.max_end < start:
                return

            if node.left is not None and node.left.max_end >= start:
                _search(node.left)

            # Check overlap: max(start, node.start) <= min(end, node.end)
            if max(start, node.start) <= min(end, node.end):
                results.append((node.start, node.end, node.data))

            if node.right is not None and node.start <= end:
                _search(node.right)

        _search(self.root)
        results.sort(key=lambda item: (item[0], item[1]))
        return results
