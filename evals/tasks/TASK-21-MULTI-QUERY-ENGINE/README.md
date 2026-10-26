# Task Specification: In-Memory Columnar Relational Query Engine

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
