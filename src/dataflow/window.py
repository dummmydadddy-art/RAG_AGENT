from typing import Any, Dict, List


class TumblingWindow:
    """
    Groups streaming records into non-overlapping tumbling time windows based on timestamp key 't'.
    """

    def __init__(self, window_size: float) -> None:
        if window_size <= 0:
            raise ValueError("Window size must be positive")
        self.window_size = float(window_size)

    def process(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        windows: Dict[int, List[Dict[str, Any]]] = {}
        for r in records:
            t = float(r.get("t", 0.0))
            w_idx = int(t // self.window_size)
            windows.setdefault(w_idx, []).append(r)

        results = []
        for w_idx in sorted(windows.keys()):
            w_start = w_idx * self.window_size
            w_end = w_start + self.window_size
            results.append({
                "window": [w_start, w_end],
                "items": windows[w_idx],
                "count": len(windows[w_idx]),
            })
        return results
