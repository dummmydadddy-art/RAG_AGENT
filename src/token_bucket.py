import threading
import time
from typing import Callable, Optional


class TokenBucket:
    """
    Thread-safe Token Bucket rate limiter with virtual or monotonic clock injection.
    """

    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        time_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        if capacity <= 0.0:
            raise ValueError("Capacity must be positive")
        if refill_rate <= 0.0:
            raise ValueError("Refill rate must be positive")

        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.time_fn = time_fn if time_fn is not None else time.monotonic
        self.tokens = self.capacity
        self.last_update = self.time_fn()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = self.time_fn()
        elapsed = now - self.last_update
        if elapsed > 0:
            added = elapsed * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + added)
            self.last_update = now

    def consume(self, tokens: float = 1.0) -> bool:
        if tokens <= 0.0:
            raise ValueError("Tokens to consume must be positive")

        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def available_tokens(self) -> float:
        with self._lock:
            self._refill()
            return self.tokens
