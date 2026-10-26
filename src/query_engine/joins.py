from typing import Any, Dict, List
from src.query_engine.scanner import TableScanner


class HashJoin:
    """
    In-memory inner Hash Join across two columnar table scans.
    """

    def __init__(
        self,
        left: TableScanner,
        right: TableScanner,
        left_on: str,
        right_on: str,
    ) -> None:
        self.left = left
        self.right = right
        self.left_on = left_on
        self.right_on = right_on

    def execute(self) -> Dict[str, List[Any]]:
        left_data = self.left.scan()
        right_data = self.right.scan()

        # Build phase on left
        hash_table: Dict[Any, List[int]] = {}
        left_keys = left_data.get(self.left_on, [])
        for idx, key in enumerate(left_keys):
            hash_table.setdefault(key, []).append(idx)

        # Probe phase on right
        output_cols = list(left_data.keys()) + [c for c in right_data.keys() if c not in left_data]
        joined: Dict[str, List[Any]] = {c: [] for c in output_cols}

        right_keys = right_data.get(self.right_on, [])
        for r_idx, r_key in enumerate(right_keys):
            matching_l_indices = hash_table.get(r_key, [])
            for l_idx in matching_l_indices:
                for c in left_data:
                    joined[c].append(left_data[c][l_idx])
                for c in right_data:
                    if c not in left_data:
                        joined[c].append(right_data[c][r_idx])

        return joined
