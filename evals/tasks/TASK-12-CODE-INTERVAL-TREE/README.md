# Task Specification: Augmented Interval Tree for Range Stabbing

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
