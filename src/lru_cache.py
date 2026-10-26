import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Optional


class LRUCache:
    """Thread-safe LRU Cache with TTL expiration and pluggable monotonic clock."""

    def __init__(
        self,
        capacity: int,
        default_ttl_seconds: Optional[float] = None,
        time_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity <= 0:
            raise ValueError("Capacity must be positive")

        if default_ttl_seconds is not None:
            if not isinstance(default_ttl_seconds, (int, float)) or default_ttl_seconds <= 0.0:
                raise ValueError("TTL must be positive")

        self.capacity: int = capacity
        self.default_ttl_seconds: Optional[float] = (
            float(default_ttl_seconds) if default_ttl_seconds is not None else None
        )
        self.time_fn: Callable[[], float] = time_fn if time_fn is not None else time.monotonic

        self._lock: threading.RLock = threading.RLock()
        # Storage: key -> (value, expiration_timestamp_or_None)
        self._cache: OrderedDict[str, tuple[Any, Optional[float]]] = OrderedDict()

    def _now(self) -> float:
        return self.time_fn()

    def _is_expired(self, key: str) -> bool:
        if key not in self._cache:
            return True
        _, exp = self._cache[key]
        if exp is None:
            return False
        return self._now() >= exp

    def _purge_expired(self) -> None:
        now = self._now()
        expired_keys = [k for k, (_, exp) in self._cache.items() if exp is not None and now >= exp]
        for k in expired_keys:
            self._cache.pop(k, None)

    def put(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        if not isinstance(key, str):
            raise TypeError("Key must be a string")

        effective_ttl: Optional[float]
        if ttl is not None:
            if not isinstance(ttl, (int, float)) or ttl <= 0.0:
                raise ValueError("TTL must be positive")
            effective_ttl = float(ttl)
        else:
            effective_ttl = self.default_ttl_seconds

        with self._lock:
            now = self._now()
            exp_time = now + effective_ttl if effective_ttl is not None else None

            if key in self._cache:
                self._cache[key] = (value, exp_time)
                self._cache.move_to_end(key, last=True)
                return

            self._purge_expired()

            if len(self._cache) >= self.capacity:
                self._cache.popitem(last=False)

            self._cache[key] = (value, exp_time)
            self._cache.move_to_end(key, last=True)

    def get(self, key: str) -> Optional[Any]:
        if not isinstance(key, str):
            raise TypeError("Key must be a string")

        with self._lock:
            if key not in self._cache:
                return None

            value, exp = self._cache[key]
            if exp is not None and self._now() >= exp:
                self._cache.pop(key, None)
                return None

            self._cache.move_to_end(key, last=True)
            return value

    def delete(self, key: str) -> bool:
        if not isinstance(key, str):
            raise TypeError("Key must be a string")

        with self._lock:
            if key not in self._cache:
                return False

            _, exp = self._cache[key]
            if exp is not None and self._now() >= exp:
                self._cache.pop(key, None)
                return False

            self._cache.pop(key, None)
            return True

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        with self._lock:
            now = self._now()
            return sum(1 for _, exp in self._cache.values() if exp is None or now < exp)

    def __contains__(self, key: str) -> bool:
        if not isinstance(key, str):
            raise TypeError("Key must be a string")

        with self._lock:
            if key not in self._cache:
                return False
            _, exp = self._cache[key]
            if exp is not None and self._now() >= exp:
                return False
            return True
