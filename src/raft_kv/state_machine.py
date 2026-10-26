from typing import Any, Dict, Optional


class KVStateMachine:
    """
    Key-Value state machine driven deterministically by committed log entries.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}

    def apply(self, command: Dict[str, Any]) -> Any:
        op = command.get("op", "").upper()
        key = command.get("key")
        if op == "SET":
            val = command.get("value")
            self._store[key] = val
            return val
        elif op == "DELETE":
            return self._store.pop(key, None)
        elif op == "GET":
            return self._store.get(key)
        return None

    def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)
