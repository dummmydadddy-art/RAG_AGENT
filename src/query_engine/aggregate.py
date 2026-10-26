from typing import Any, Dict, List


class GroupByAggregate:
    """
    Columnar Group-By aggregation for sum, count, and average operations.
    """

    def __init__(
        self,
        data: Dict[str, List[Any]],
        group_col: str,
        agg_col: str,
        agg_func: str = "sum",
    ) -> None:
        self.data = data
        self.group_col = group_col
        self.agg_col = agg_col
        self.agg_func = agg_func.lower()

    def execute(self) -> Dict[Any, float]:
        groups = self.data.get(self.group_col, [])
        vals = self.data.get(self.agg_col, [])

        buckets: Dict[Any, List[float]] = {}
        for g, v in zip(groups, vals):
            buckets.setdefault(g, []).append(float(v))

        out: Dict[Any, float] = {}
        for g, v_list in buckets.items():
            if self.agg_func == "sum":
                out[g] = float(sum(v_list))
            elif self.agg_func == "count":
                out[g] = float(len(v_list))
            elif self.agg_func in ("avg", "mean"):
                out[g] = float(sum(v_list) / len(v_list)) if v_list else 0.0
            else:
                raise ValueError(f"Unknown aggregation function: {self.agg_func}")

        return out
