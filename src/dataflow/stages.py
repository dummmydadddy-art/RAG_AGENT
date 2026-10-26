from typing import Any, Callable, Dict, List


class MapStage:
    """
    Applies transformation function to each record in stream.
    """

    def __init__(self, fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        self.fn = fn

    def process(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self.fn(r) for r in records]


class FilterStage:
    """
    Filters records matching predicate.
    """

    def __init__(self, predicate: Callable[[Dict[str, Any]], bool]) -> None:
        self.predicate = predicate

    def process(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [r for r in records if self.predicate(r)]


class AggregateStage:
    """
    Reduces stream of records using an accumulator function.
    """

    def __init__(self, key_fn: Callable[[Dict[str, Any]], Any], reduce_fn: Callable[[Any, Any], Any]) -> None:
        self.key_fn = key_fn
        self.reduce_fn = reduce_fn

    def process(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped: Dict[Any, List[Dict[str, Any]]] = {}
        for r in records:
            k = self.key_fn(r)
            grouped.setdefault(k, []).append(r)

        return [{"key": k, "values": v} for k, v in grouped.items()]
