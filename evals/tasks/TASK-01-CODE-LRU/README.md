# Task Specification: Thread-safe LRU Cache with Expiration TTL

## 1. Class & Method Contract
Implement `LRUCache` in `src/lru_cache.py`.

### Constructor Signature
```python
def __init__(
    self,
    capacity: int,
    default_ttl_seconds: Optional[float] = None,
    time_fn: Optional[Callable[[], float]] = None
) -> None:
```
- `capacity`: Maximum number of entries stored simultaneously. Must be an integer > 0. If `capacity <= 0` or not an `int`, raise `ValueError("Capacity must be positive")`.
- `default_ttl_seconds`: Optional default time-to-live in seconds. If provided, must be a float or int > 0.0. If `<= 0.0`, raise `ValueError("TTL must be positive")`. Default is `None` (entries do not expire unless overridden).
- `time_fn`: Monotonic clock callable returning current time in float seconds. Defaults to `time.monotonic` if `None`. Allows deterministic testing of time-dependent eviction without sleeping.

### Method Contracts
1. `put(self, key: str, value: Any, ttl: Optional[float] = None) -> None`:
   - `key`: Must be a string. If not an instance of `str`, raise `TypeError("Key must be a string")`.
   - `ttl`: Optional individual TTL in seconds. If `ttl is None`, falls back to `default_ttl_seconds`. If explicitly provided and `<= 0.0`, raise `ValueError("TTL must be positive")`.
   - Expiration calculation: If effective TTL is positive, expiration timestamp is `current_time + effective_ttl`; otherwise `None` (no expiration).
   - Key update vs insertion:
     - If `key` is already present (even if expired): updates value, updates expiration timestamp, and updates access order (marks as most recently used). Does not evict any other key.
     - If `key` is new:
       - First, purges all expired keys from internal storage.
       - Next, if `len(self) >= capacity`: evicts the least recently used (LRU) non-expired key.
       - Inserts the new key with its expiration timestamp and marks as most recently used (MRU).

2. `get(self, key: str) -> Optional[Any]`:
   - `key`: Must be a string. If not an instance of `str`, raise `TypeError("Key must be a string")`.
   - If `key` does not exist or has expired (`current_time >= expiration_time`), removes the expired key if present and returns `None`.
   - If `key` exists and has not expired, updates its access order (marks as most recently used) and returns `value`.

3. `delete(self, key: str) -> bool`:
   - `key`: Must be a string. If not an instance of `str`, raise `TypeError("Key must be a string")`.
   - If `key` exists and has not expired: removes `key` from cache and returns `True`.
   - If `key` does not exist or has already expired: removes expired key if present and returns `False`.

4. `clear(self) -> None`:
   - Removes all stored keys and values from the cache.

5. `__len__(self) -> int`:
   - Returns the current number of non-expired keys stored in the cache. Calling `__len__` is non-mutating and does not alter the LRU access order.

6. `__contains__(self, key: str) -> bool`:
   - `key`: Must be a string. If not an instance of `str`, raise `TypeError("Key must be a string")`.
   - Returns `True` if `key` is present and unexpired, `False` otherwise.
   - Checking containment MUST NOT alter the LRU access order.

## 2. Concurrency & Invariants
- All public methods must be thread-safe under concurrent multi-threaded execution using `threading.RLock()`.
