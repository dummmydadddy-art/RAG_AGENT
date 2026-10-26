from typing import Any, Callable, Dict, List, Optional


class TableScanner:
    """
    Columnar table scanner with projection and row-predicate pushdown.
    """

    def __init__(self, table_name: str, data: Dict[str, List[Any]]) -> None:
        self.table_name = table_name
        self.data = {k: list(v) for k, v in data.items()}
        # Compute row count from first column
        first_col = next(iter(self.data.values())) if self.data else []
        self.num_rows = len(first_col)

    def scan(
        self,
        columns: Optional[List[str]] = None,
        filter_pred: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> Dict[str, List[Any]]:
        selected_cols = columns if columns is not None else list(self.data.keys())
        out: Dict[str, List[Any]] = {c: [] for c in selected_cols}

        for row_idx in range(self.num_rows):
            row_dict = {col: self.data[col][row_idx] for col in self.data}
            if filter_pred is None or filter_pred(row_dict):
                for col in selected_cols:
                    out[col].append(self.data[col][row_idx])

        return out
